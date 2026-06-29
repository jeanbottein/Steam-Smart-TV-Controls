"""LG webOS LAN discovery via SSDP (UPnP M-SEARCH). LG-specific.

mDNS is a poor fit here: every webOS TV advertises the *same* `lgwebostv.local`
hostname, so a second TV renames itself to `lgwebostv-2.local` and you can't tell
which physical set is which. SSDP instead has each TV reply from its own IP, so
multiple TVs come back as distinct entries — and it needs no extra dependency,
just a few UDP datagrams. A TV in standby won't answer, so this complements (not
replaces) manual IP entry.
"""

import asyncio
import socket
from urllib.parse import urlparse

SSDP_ADDR = ("239.255.255.250", 1900)
# The search target webOS TVs answer to (same one Home Assistant's webostv uses).
SSDP_ST = "urn:lge-com:service:webos-second-screen:1"
SSDP_MX = 2  # max seconds a TV may wait before replying (advertised in the query)
COLLECT_SECONDS = 3  # how long we listen for unicast replies after searching
SEND_BURST = 3  # multicast can be lossy; send the query a few times
DESC_TIMEOUT = 2  # per-TV budget to fetch its description XML for a friendly name

_MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
    'MAN: "ssdp:discover"\r\n'
    f"MX: {SSDP_MX}\r\n"
    f"ST: {SSDP_ST}\r\n"
    "\r\n"
).encode()


def parse_headers(data):
    """Parse an SSDP/HTTP response into an upper-cased header dict (ignores the status line)."""
    headers = {}
    for line in data.decode("utf-8", "replace").split("\r\n")[1:]:
        key, sep, value = line.partition(":")
        if sep:
            headers[key.strip().upper()] = value.strip()
    return headers


def extract_tag(xml, tag):
    """Pull the text of the first <tag>…</tag> out of `xml`, or "" if absent."""
    open_tag, close_tag = f"<{tag}>", f"</{tag}>"
    start = xml.find(open_tag)
    if start == -1:
        return ""
    start += len(open_tag)
    end = xml.find(close_tag, start)
    return xml[start:end].strip() if end != -1 else ""


class _Collector(asyncio.DatagramProtocol):
    def __init__(self):
        self.locations = {}  # host -> LOCATION url (first reply per host wins)

    def datagram_received(self, data, addr):
        location = parse_headers(data).get("LOCATION", "")
        self.locations.setdefault(addr[0], location)


async def _friendly_name(location):
    """Best-effort fetch of the TV's UPnP <friendlyName>; "" on any failure."""
    if not location:
        return ""
    parsed = urlparse(location)
    if not parsed.hostname:
        return ""
    target = f"{parsed.path or '/'}{'?' + parsed.query if parsed.query else ''}"
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, parsed.port or 80), DESC_TIMEOUT
        )
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}\r\nConnection: close\r\n\r\n"
        )
        writer.write(request.encode())
        await writer.drain()
        body = await asyncio.wait_for(reader.read(), DESC_TIMEOUT)
        return extract_tag(body.decode("utf-8", "replace"), "friendlyName")
    except Exception:  # noqa: BLE001 - a missing name just means we fall back to the host
        return ""
    finally:
        if writer is not None:
            writer.close()


async def discover():
    loop = asyncio.get_event_loop()
    transport, collector = await loop.create_datagram_endpoint(
        _Collector, family=socket.AF_INET, local_addr=("0.0.0.0", 0), allow_broadcast=True
    )
    try:
        for _ in range(SEND_BURST):
            transport.sendto(_MSEARCH, SSDP_ADDR)
        await asyncio.sleep(COLLECT_SECONDS)
    finally:
        transport.close()
    # Resolve names concurrently: one slow/filtered description host shouldn't stall the
    # rest, so the whole phase is bounded by a single DESC_TIMEOUT, not the sum.
    hosts = list(collector.locations.items())
    names = await asyncio.gather(*(_friendly_name(location) for _, location in hosts))
    return [{"host": host, "name": name} for (host, _), name in zip(hosts, names)]
