import { DropdownItem, PanelSection, PanelSectionRow, ToggleField } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { removeRule, setRule, type Display, type Input, type Rule, type Tv } from "../api";

interface AutoSwitchProps {
  tv: Tv;
  displays: Display[];
  rules: Rule[];
  inputs: Input[];
  onChanged: () => void;
}

export function AutoSwitch({ tv, displays, rules, inputs, onChanged }: AutoSwitchProps) {
  const rule = rules.find((item) => item.host === tv.host);
  const [enabled, setEnabled] = useState(false);
  const [deviceId, setDeviceId] = useState("");
  const [inputId, setInputId] = useState("");
  const savedDevice = useRef("");

  // Hydrate from the saved rule, falling back to the first screen/input so nothing is blank.
  useEffect(() => {
    setEnabled(rule?.enabled ?? false);
    setDeviceId(rule?.display_id ?? displays[0]?.id ?? "");
    setInputId(rule?.input_id ?? inputs[0]?.id ?? "");
    savedDevice.current = rule?.display_id ?? "";
  }, [tv.host, rule?.display_id, rule?.input_id, rule?.enabled, displays, inputs]);

  const persist = async (device: string, input: string, on: boolean) => {
    if (!device || !input) {
      return;
    }
    if (savedDevice.current && savedDevice.current !== device) {
      await removeRule(savedDevice.current);
    }
    await setRule(device, tv.host, input, on);
    savedDevice.current = device;
    onChanged();
  };

  const toggle = (on: boolean) => {
    setEnabled(on);
    persist(deviceId, inputId, on);
  };
  const pickDevice = (id: string) => {
    setDeviceId(id);
    persist(id, inputId, enabled);
  };
  const pickInput = (id: string) => {
    setInputId(id);
    persist(deviceId, id, enabled);
  };

  return (
    <PanelSection>
      <PanelSectionRow>
        <ToggleField label="AUTO SWITCH" checked={enabled} bottomSeparator="none" onChange={toggle} />
      </PanelSectionRow>
      {enabled ? (
        <Params
          displays={displays}
          inputs={inputs}
          deviceId={deviceId}
          inputId={inputId}
          pickDevice={pickDevice}
          pickInput={pickInput}
        />
      ) : null}
    </PanelSection>
  );
}

interface ParamsProps {
  displays: Display[];
  inputs: Input[];
  deviceId: string;
  inputId: string;
  pickDevice: (id: string) => void;
  pickInput: (id: string) => void;
}

function Params({ displays, inputs, deviceId, inputId, pickDevice, pickInput }: ParamsProps) {
  // Keep the saved screen selectable even while it's disconnected, so its name stays visible in the rule.
  const screenOptions = displays.map((display) => ({ data: display.id, label: display.id }));
  if (deviceId && !screenOptions.some((option) => option.data === deviceId)) {
    screenOptions.push({ data: deviceId, label: `${deviceId} (disconnected)` });
  }
  if (screenOptions.length === 0 || inputs.length === 0) {
    return <PanelSectionRow>Connect the screen and turn the TV on to configure this.</PanelSectionRow>;
  }
  return (
    <>
      <PanelSectionRow>
        <div style={{ fontSize: "0.8em", opacity: 0.6, paddingBottom: "2px" }}>
          When this screen is detected
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DropdownItem
          menuLabel="Trigger on screen"
          rgOptions={screenOptions}
          selectedOption={deviceId}
          bottomSeparator="none"
          childrenContainerWidth="max"
          onChange={(option) => pickDevice(option.data)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ fontSize: "0.8em", opacity: 0.6, paddingBottom: "2px" }}>Switch to this input</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DropdownItem
          menuLabel="Switch to input"
          rgOptions={inputs.map((input) => ({ data: input.id, label: input.label }))}
          selectedOption={inputId}
          bottomSeparator="none"
          childrenContainerWidth="max"
          onChange={(option) => pickInput(option.data)}
        />
      </PanelSectionRow>
    </>
  );
}
