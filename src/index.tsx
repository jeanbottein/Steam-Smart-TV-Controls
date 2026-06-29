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

function Content() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [tvs, setTvs] = useState<Tv[]>([]);
  const [displays, setDisplays] = useState<Display[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [selectedHost, setSelectedHost] = useState("");
  const [inputs, setInputs] = useState<Input[]>([]);
  const [adding, setAdding] = useState(false);
  const [ready, setReady] = useState(false);

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
    // Initial load: resolve everything (including the selected TV's inputs) before
    // revealing the UI, so the Manual switch dropdown/button don't pop in afterward.
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
        if (host) {
          const list = await getInputs(host);
          if (active && list.length) setInputs(list);
        }
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
      <TvManage tvs={tvs} selectedHost={selectedHost} onChanged={refresh} />
      <Logs />
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

  return {
    name: "Smart TV Controls",
    titleView: <div className={staticClasses.Title}>Smart TV Controls</div>,
    content: <Content />,
    icon: <FaTv />,
    onDismount() {
      removeEventListener("auto_switch", listener);
    },
  };
});
