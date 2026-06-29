import { ButtonItem, DropdownItem, PanelSectionRow, TextField } from "@decky/ui";
import { toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { pairTv, type Brand } from "../api";

export function AddTv({ brands, onPaired }: { brands: Brand[]; onPaired: (host: string) => void }) {
  const [host, setHost] = useState("");
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [busy, setBusy] = useState(false);

  // brands load async, so adopt the first one once it arrives (and keep any user choice).
  useEffect(() => {
    if (!brand && brands.length > 0) {
      setBrand(brands[0].id);
    }
  }, [brands, brand]);

  const canPair = Boolean(host && brand) && !busy;

  const pair = async () => {
    if (!canPair) {
      return;
    }
    setBusy(true);
    try {
      const tv = await pairTv(host, name, brand);
      toaster.toast({ title: "TV paired", body: tv.name || tv.host });
      setHost("");
      setName("");
      onPaired(tv.host);
    } catch (error) {
      toaster.toast({ title: "Pairing failed", body: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PanelSectionRow>
        <DropdownItem
          label="Brand"
          rgOptions={brands.map((item) => ({ data: item.id, label: item.label }))}
          selectedOption={brand}
          onChange={(option) => setBrand(option.data)}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <TextField
          label="IP or hostname"
          value={host}
          onChange={(event) => setHost(event.target.value.trim())}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <TextField label="Name (optional)" value={name} onChange={(event) => setName(event.target.value)} />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem layout="below" disabled={!canPair} onClick={pair}>
          {busy ? "Accept the prompt on your TV…" : "Pair"}
        </ButtonItem>
      </PanelSectionRow>
    </>
  );
}
