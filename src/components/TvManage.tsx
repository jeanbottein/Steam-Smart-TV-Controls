import { ButtonItem, ConfirmModal, PanelSection, PanelSectionRow, showModal } from "@decky/ui";
import { removeTv, tvLabel, type Tv } from "../api";

interface TvManageProps {
  tvs: Tv[];
  selectedHost: string;
  onChanged: () => void;
}

export function TvManage({ tvs, selectedHost, onChanged }: TvManageProps) {
  const selected = tvs.find((tv) => tv.host === selectedHost);
  if (!selected) {
    return null;
  }

  const confirmRemove = () => {
    showModal(
      <ConfirmModal
        strTitle="Remove this TV?"
        strDescription={`${tvLabel(selected)} will be unpaired. You'll need to pair it again to use it.`}
        strOKButtonText="Remove"
        onOK={async () => {
          await removeTv(selected.host);
          onChanged();
        }}
      />,
    );
  };

  return (
    <PanelSection>
      <PanelSectionRow>
        <ButtonItem layout="below" bottomSeparator="none" onClick={confirmRemove}>
          <span style={{ color: "#e74c3c" }}>Remove this TV</span>
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}
