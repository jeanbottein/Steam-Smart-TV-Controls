import { ButtonItem, PanelSectionRow } from "@decky/ui";
import { useState } from "react";
import { readLogs } from "../api";

export function Logs() {
  const [text, setText] = useState<string | undefined>();

  const load = async () => {
    try {
      setText(await readLogs());
    } catch {
      setText("Failed to load logs.");
    }
  };

  return (
    <>
      <PanelSectionRow>
        <ButtonItem layout="below" bottomSeparator="none" onClick={load}>
          {text === undefined ? "View logs" : "Refresh logs"}
        </ButtonItem>
      </PanelSectionRow>
      {text === undefined ? null : (
        <PanelSectionRow>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: "11px",
              maxHeight: "300px",
              overflowY: "scroll",
              margin: 0,
              width: "100%",
            }}
          >
            {text || "No logs yet."}
          </pre>
        </PanelSectionRow>
      )}
    </>
  );
}
