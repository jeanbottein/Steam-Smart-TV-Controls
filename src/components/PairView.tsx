import { ButtonItem, PanelSection, PanelSectionRow } from "@decky/ui";
import { AddTv } from "./AddTv";
import type { Brand, Tv } from "../api";

interface PairViewProps {
  brands: Brand[];
  tvs: Tv[];
  onPaired: (host: string) => void;
  onCancel: () => void;
}

export function PairView({ brands, tvs, onPaired, onCancel }: PairViewProps) {
  return (
    <PanelSection title={tvs.length === 0 ? "Add a TV" : "Add another TV"}>
      <>
        <AddTv brands={brands} onPaired={onPaired} />
        {tvs.length > 0 ? (
          <PanelSectionRow>
            <ButtonItem layout="below" bottomSeparator="none" onClick={onCancel}>
              <span style={{ color: "#e74c3c" }}>Cancel</span>
            </ButtonItem>
          </PanelSectionRow>
        ) : null}
      </>
    </PanelSection>
  );
}
