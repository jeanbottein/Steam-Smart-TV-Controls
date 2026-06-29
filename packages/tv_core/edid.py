"""Detect connected displays and give each a stable identity from its EDID.

Brand-agnostic: every TV driver matches auto-switch rules against these ids.
"""

import os

DRM_PATH = "/sys/class/drm"
NAME_OFFSETS = (54, 72, 90, 108)
MONITOR_NAME_TAG = 0xFC


def _read_text(path):
    try:
        with open(path, encoding="ascii", errors="ignore") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _read_edid(connector):
    try:
        with open(os.path.join(DRM_PATH, connector, "edid"), "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    return data if len(data) >= 128 else None


def _monitor_name(edid):
    for offset in NAME_OFFSETS:
        block = edid[offset:offset + 18]
        if block[0:3] == b"\x00\x00\x00" and block[3] == MONITOR_NAME_TAG:
            name = block[5:18].split(b"\x0a", 1)[0].decode("ascii", "ignore").strip()
            if name:
                return name
    return None


def _vendor_code(edid):
    packed = (edid[8] << 8) | edid[9]
    letters = "".join(chr(((packed >> shift) & 0x1F) + 0x40) for shift in (10, 5, 0))
    product = edid[10] | (edid[11] << 8)
    return f"{letters}{product:04X}"


def _identity(edid):
    return _monitor_name(edid) or _vendor_code(edid)


def connected_displays():
    """Return [{connector, id}] for every connected display with a readable EDID."""
    displays = []
    for connector in sorted(os.listdir(DRM_PATH)):
        if _read_text(os.path.join(DRM_PATH, connector, "status")) != "connected":
            continue
        edid = _read_edid(connector)
        if edid is not None:
            displays.append({"connector": connector, "id": _identity(edid)})
    return displays
