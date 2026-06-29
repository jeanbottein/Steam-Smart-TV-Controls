import { DialogButton, DropdownItem, PanelSection, PanelSectionRow } from "@decky/ui";
import { tvLabel, type Tv } from "../api";
import { ReachabilityIndicator } from "./ReachabilityIndicator";

interface TvSectionProps {
  tvs: Tv[];
  selectedHost: string;
  onSelect: (host: string) => void;
  onAdd: () => void;
}

export function TvSection({ tvs, selectedHost, onSelect, onAdd }: TvSectionProps) {
  const selected = tvs.find((tv) => tv.host === selectedHost);
  if (tvs.length === 0) {
    return null;
  }

  return (
    <PanelSection>
      <PanelSectionRow>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <DropdownItem
              menuLabel="Select a TV"
              rgOptions={tvs.map((tv) => ({ data: tv.host, label: tvLabel(tv) }))}
              selectedOption={selectedHost}
              bottomSeparator="none"
              childrenContainerWidth="max"
              onChange={(option) => onSelect(option.data)}
            />
          </div>
          <DialogButton
            onClick={onAdd}
            style={{
              minWidth: 0,
              width: "44px",
              height: "40px",
              padding: 0,
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ fontSize: "1.5em", fontWeight: "bold", lineHeight: 1 }}>+</span>
          </DialogButton>
        </div>
      </PanelSectionRow>
      {selected && selected.name ? (
        <PanelSectionRow>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              fontSize: "0.8em",
              opacity: 0.6,
              paddingBottom: "8px",
            }}
          >
            <span style={{ fontWeight: "bold", marginRight: "6px" }}>Address</span>
            <span>{selected.host}</span>
            <ReachabilityIndicator host={selected.host} />
          </div>
        </PanelSectionRow>
      ) : null}
    </PanelSection>
  );
}
