import { ButtonItem, DropdownItem, PanelSectionRow, TextField } from "@decky/ui";
import { toaster } from "@decky/api";
import { useEffect, useRef, useState } from "react";
import { discoverTvs, pairTv, type Brand, type DiscoveredTv } from "../api";

export function AddTv({ brands, onPaired }: { brands: Brand[]; onPaired: (host: string) => void }) {
  const [host, setHost] = useState("");
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [busy, setBusy] = useState(false);
  const [discovered, setDiscovered] = useState<DiscoveredTv[]>([]);
  const [scanning, setScanning] = useState(false);
  // Bumped on every new scan and on cleanup, so a stale/cancelled scan's result is dropped.
  const scanToken = useRef(0);

  // brands load async, so adopt the first one once it arrives (and keep any user choice).
  useEffect(() => {
    if (!brand && brands.length > 0) {
      setBrand(brands[0].id);
    }
  }, [brands, brand]);

  const scan = async () => {
    if (!brand) {
      return;
    }
    const token = ++scanToken.current;
    setScanning(true);
    try {
      const found = await discoverTvs(brand);
      if (token === scanToken.current) {
        setDiscovered(found);
      }
    } catch {
      if (token === scanToken.current) {
        setDiscovered([]);
      }
    } finally {
      if (token === scanToken.current) {
        setScanning(false);
      }
    }
  };

  // Scan automatically when the form opens or the brand changes. The cleanup bumps the
  // token so an in-flight scan is abandoned when the brand switches — or when this view
  // unmounts, which is exactly what pairing or cancelling does. So no background scan
  // ever outlives the Add form.
  useEffect(() => {
    setDiscovered([]);
    void scan();
    return () => {
      scanToken.current++;
      setScanning(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brand]);

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
          layout="below"
          rgOptions={brands.map((item) => ({ data: item.id, label: item.label }))}
          selectedOption={brand}
          onChange={(option) => setBrand(option.data)}
        />
      </PanelSectionRow>
      {scanning || discovered.length > 0 ? (
        <PanelSectionRow>
          <DropdownItem
            label={scanning ? "Scanning…" : "Discovered TVs"}
            layout="below"
            disabled={scanning || discovered.length === 0}
            rgOptions={discovered.map((tv) => ({ data: tv.host, label: tv.name || tv.host }))}
            selectedOption={host}
            onChange={(option) => setHost(option.data)}
          />
        </PanelSectionRow>
      ) : null}
      <PanelSectionRow>
        <ButtonItem layout="below" bottomSeparator="none" disabled={scanning} onClick={scan}>
          {scanning ? "Scanning…" : "Scan again"}
        </ButtonItem>
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
