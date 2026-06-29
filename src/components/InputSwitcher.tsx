import { ButtonItem, DropdownItem, Field, PanelSection, PanelSectionRow } from "@decky/ui";
import { toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { switchInput, type Input, type Tv } from "../api";

export function InputSwitcher({ tv, inputs }: { tv: Tv; inputs: Input[] }) {
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);

  // Keep the current pick if it still exists, else fall back to the first input.
  // Ignore an empty list so a transient refresh can't wipe the selection.
  useEffect(() => {
    if (inputs.length === 0) {
      return;
    }
    setSelected((cur) => (inputs.some((input) => input.id === cur) ? cur : inputs[0]?.id ?? ""));
  }, [inputs]);

  const send = async () => {
    if (!selected) {
      return;
    }
    setBusy(true);
    try {
      await switchInput(tv.host, selected);
      const label = inputs.find((input) => input.id === selected)?.label ?? selected;
      toaster.toast({ title: "Input switched", body: label });
    } catch (error) {
      toaster.toast({ title: "Switch failed", body: String(error) });
    } finally {
      setBusy(false);
    }
  };

  if (inputs.length === 0) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <Field label="MANUAL SWITCH" bottomSeparator="none" />
        </PanelSectionRow>
        <PanelSectionRow>No inputs found — make sure the TV is on.</PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <PanelSection>
      <PanelSectionRow>
        <Field label="MANUAL SWITCH" bottomSeparator="none" />
      </PanelSectionRow>
      <PanelSectionRow>
        <DropdownItem
          menuLabel="Select an input"
          rgOptions={inputs.map((input) => ({ data: input.id, label: input.label }))}
          selectedOption={selected}
          bottomSeparator="none"
          childrenContainerWidth="max"
          onChange={(option) => setSelected(option.data)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          bottomSeparator="standard"
          disabled={busy || !selected}
          onClick={send}
        >
          {busy ? "Switching…" : "Switch input"}
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}
