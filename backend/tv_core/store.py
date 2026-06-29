"""Persisted paired TVs, per-screen auto-switch rules, and the last-used TV.

A TV record is brand-agnostic: {host, name, brand, creds}. `creds` is whatever
opaque, JSON-serializable value the brand's driver returned from pairing.
"""

import json
import os


class Store:
    def __init__(self, path):
        self._path = path
        self._data = self._read() or {}
        self._data.setdefault("tvs", [])
        self._data.setdefault("rules", [])
        self._data.setdefault("selected", "")

    def _read(self):
        try:
            with open(self._path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2)

    @property
    def tvs(self):
        return self._data["tvs"]

    @property
    def rules(self):
        return self._data["rules"]

    @property
    def selected(self):
        return self._data["selected"]

    def set_selected(self, host):
        self._data["selected"] = host
        self._save()

    def find_tv(self, host):
        return next((tv for tv in self.tvs if tv["host"] == host), None)

    def upsert_tv(self, host, name, brand, creds, mac=None):
        tv = self.find_tv(host)
        if tv is None:
            tv = {"host": host}
            self.tvs.append(tv)
        tv.update({"name": name, "brand": brand, "creds": creds})
        if mac:
            tv["mac"] = mac
        self._save()

    def set_mac(self, host, mac):
        """Backfill a TV's MAC (for Wake-on-LAN) once we've seen it on the network."""
        tv = self.find_tv(host)
        if tv is None or not mac or tv.get("mac") == mac:
            return
        tv["mac"] = mac
        self._save()

    def cached_inputs(self, host):
        tv = self.find_tv(host)
        return tv.get("inputs", []) if tv else []

    def set_inputs(self, host, inputs):
        """Cache the input list and repoint any rule whose input no longer exists."""
        tv = self.find_tv(host)
        if tv is None or not inputs:
            return
        tv["inputs"] = inputs
        valid = {item["id"] for item in inputs}
        fallback = inputs[0]["id"]
        for rule in self.rules:
            if rule["host"] == host and rule["input_id"] not in valid:
                rule["input_id"] = fallback
        self._save()

    def remove_tv(self, host):
        self._data["tvs"] = [tv for tv in self.tvs if tv["host"] != host]
        self._data["rules"] = [rule for rule in self.rules if rule["host"] != host]
        if self.selected == host:
            self._data["selected"] = ""
        self._save()

    def set_rule(self, display_id, host, input_id, enabled):
        rule = next((item for item in self.rules if item["display_id"] == display_id), None)
        if rule is None:
            rule = {"display_id": display_id}
            self.rules.append(rule)
        rule.update({"host": host, "input_id": input_id, "enabled": enabled})
        self._save()

    def remove_rule(self, display_id):
        self._data["rules"] = [rule for rule in self.rules if rule["display_id"] != display_id]
        self._save()
