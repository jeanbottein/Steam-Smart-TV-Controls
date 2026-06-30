import { PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaTv } from "react-icons/fa";
import {
  getInputs,
  getSelectedTv,
  listBrands,
  listDisplays,
  listRules,
  listTvs,
  reapplyRules,
  setSelectedTv,
  type Brand,
  type Display,
  type Input,
  type Rule,
  type Tv,
} from "./api";
import { TvSection } from "./components/TvSection";
import { TvManage } from "./components/TvManage";
import { PairView } from "./components/PairView";
import { InputSwitcher } from "./components/InputSwitcher";
import { AutoSwitch } from "./components/AutoSwitch";
import { Logs } from "./components/Logs";

const sameInputs = (a: Input[], b: Input[]) =>
  a.length === b.length && a.every((item, i) => item.id === b[i].id && item.label === b[i].label);
const exists = (tvs: Tv[], host: string) => tvs.some((tv) => tv.host === host);
function pickSelected(tvs: Tv[], saved: string, current: string) {
  if (exists(tvs, saved)) return saved;
  if (exists(tvs, current)) return current;
  return tvs[0]?.host ?? "";
}

// The panel's React tree unmounts every time the Quick Access menu closes, but this
// module stays loaded for the whole session. Stashing the last rendered state here lets
// a reopen paint the full UI instantly (no "Loading…" flash) while a fresh load runs in
// the background to correct anything stale.
type Snapshot = {
  tvs: Tv[];
  displays: Display[];
  rules: Rule[];
  selectedHost: string;
  inputs: Input[];
};
let snapshot: Snapshot | null = null;

function Content() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [tvs, setTvs] = useState<Tv[]>(snapshot?.tvs ?? []);
  const [displays, setDisplays] = useState<Display[]>(snapshot?.displays ?? []);
  const [rules, setRules] = useState<Rule[]>(snapshot?.rules ?? []);
  const [selectedHost, setSelectedHost] = useState(snapshot?.selectedHost ?? "");
  const [inputs, setInputs] = useState<Input[]>(snapshot?.inputs ?? []);
  const [adding, setAdding] = useState(false);
  // Reveal immediately when we have a cached snapshot to show; otherwise gate on first load.
  const [ready, setReady] = useState(snapshot !== null);

  // Mirror the rendered state into the module-level snapshot so the next reopen is instant.
  useEffect(() => {
    snapshot = { tvs, displays, rules, selectedHost, inputs };
  }, [tvs, displays, rules, selectedHost, inputs]);

  const refresh = async () => {
    const [nextTvs, nextDisplays, nextRules, saved] = await Promise.all([
      listTvs(),
      listDisplays(),
      listRules(),
      getSelectedTv(),
    ]);
    setTvs(nextTvs);
    setDisplays(nextDisplays);
    setRules(nextRules);
    setSelectedHost((current) => pickSelected(nextTvs, saved, current));
  };

  useEffect(() => {
    listBrands().then(setBrands);
    let active = true;
    // Initial load: gate only on the fast local store reads (no live TV round-trip), so
    // the panel reveals immediately. Seed the Manual switch from the cached inputs that
    // already travel with each TV; the polling effect refreshes it from the TV in the
    // background. Blocking the whole UI on getInputs() here cost ~2s on every open.
    (async () => {
      try {
        const [nextTvs, nextDisplays, nextRules, saved] = await Promise.all([
          listTvs(),
          listDisplays(),
          listRules(),
          getSelectedTv(),
        ]);
        if (!active) return;
        setTvs(nextTvs);
        setDisplays(nextDisplays);
        setRules(nextRules);
        const host = pickSelected(nextTvs, saved, "");
        setSelectedHost(host);
        const cached = nextTvs.find((tv) => tv.host === host)?.inputs ?? [];
        if (cached.length) setInputs(cached);
      } catch {
        /* fall through to reveal the UI anyway */
      }
      if (active) setReady(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  // Poll the selected TV's inputs: returns the cached list when offline, refreshes
  // (and repoints any stale rule server-side) once the TV is reachable again.
  useEffect(() => {
    if (!selectedHost) {
      setInputs([]);
      return;
    }
    let active = true;
    // Don't clear here: keep showing the current inputs until the fresh list arrives,
    // so switching TVs (and the initial load) doesn't flash an empty Manual switch.
    const load = async () => {
      try {
        const list = await getInputs(selectedHost);
        if (!active) {
          return;
        }
        // Keep the same array (and never overwrite a good list with a transient
        // empty one) so a routine refresh can't reset the user's dropdown pick.
        setInputs((prev) => (list.length === 0 || sameInputs(prev, list) ? prev : list));
        setRules(await listRules()); // pick up any rule repointed to an existing input
      } catch {
        /* keep the last known list */
      }
    };
    load();
    const timer = setInterval(load, 8000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selectedHost]);

  const selectTv = (host: string) => {
    setSelectedHost(host);
    void setSelectedTv(host);
  };
  const onPaired = (host: string) => {
    setAdding(false);
    selectTv(host);
    refresh();
  };

  const selectedTv = tvs.find((tv) => tv.host === selectedHost);

  if (!ready) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <div style={{ textAlign: "center", opacity: 0.6, padding: "12px 0" }}>Loading…</div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (adding || tvs.length === 0) {
    return <PairView brands={brands} tvs={tvs} onPaired={onPaired} onCancel={() => setAdding(false)} />;
  }

  return (
    <>
      <TvSection tvs={tvs} selectedHost={selectedHost} onSelect={selectTv} onAdd={() => setAdding(true)} />
      {selectedTv ? <InputSwitcher tv={selectedTv} inputs={inputs} /> : null}
      {selectedTv ? (
        <AutoSwitch tv={selectedTv} displays={displays} rules={rules} inputs={inputs} onChanged={refresh} />
      ) : null}
      <PanelSection>
        <TvManage tvs={tvs} selectedHost={selectedHost} onChanged={refresh} />
        <Logs />
      </PanelSection>
    </>
  );
}

export default definePlugin(() => {
  const listener = addEventListener<[name: string, inputId: string]>(
    "auto_switch",
    (name, inputId) => {
      toaster.toast({ title: "TV input switched", body: `${name} → ${inputId}` });
    },
  );

  // "One Touch Play", like an Xbox/console home button: when the Steam overlay/menu gains
  // focus (the closest signal a plugin gets to the Steam button — the raw button is
  // captured by gamescope and never reaches plugin JS), re-assert the docked TV's input.
  // The backend no-ops when the TV is already on that input, so firing often is cheap; the
  // debounce just keeps focus churn from stacking calls. Registered here (not in the panel,
  // which only exists while the QAM is open) so it lives for the whole session.
  const steamClient = (window as unknown as { SteamClient?: any }).SteamClient;
  let lastReapply = 0;
  const onFocusChange = (event?: unknown) => {
    console.debug("[smart-tv-controls] focus change", event);
    const now = Date.now();
    if (now - lastReapply < 3000) return;
    lastReapply = now;
    void reapplyRules().catch(() => {
      /* best-effort: a failed reassert is retried by the normal poll loop */
    });
  };
  const focusReg = steamClient?.System?.UI?.RegisterForFocusChangeEvents?.(onFocusChange);

  return {
    name: "Smart TV Controls",
    titleView: <div className={staticClasses.Title}>Smart TV Controls</div>,
    content: <Content />,
    icon: <FaTv />,
    onDismount() {
      removeEventListener("auto_switch", listener);
      focusReg?.unregister?.();
    },
  };
});
