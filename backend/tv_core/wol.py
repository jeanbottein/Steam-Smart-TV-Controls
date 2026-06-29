"""Wake-on-LAN: learn a host's MAC from the local ARP table and send magic packets.

Brand-agnostic. The MAC is captured while the TV is awake (at pairing, or whenever
it is reachable) so we can later wake it from standby the way Google Home does.
"""

import socket
import string


def _arp_mac(ip):
    try:
        with open("/proc/net/arp", encoding="ascii") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None
    for line in lines[1:]:  # skip the header row
        fields = line.split()
        if len(fields) >= 4 and fields[0] == ip:
            mac = fields[3]
            if mac and mac != "00:00:00:00:00:00":
                return mac
    return None


def resolve_mac(host):
    """Best-effort MAC for a host already seen on the local network (via ARP)."""
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return None
    return _arp_mac(ip)


def _hex_digits(mac):
    return mac.replace(":", "").replace("-", "").strip()


def is_valid_mac(mac):
    digits = _hex_digits(mac)
    return len(digits) == 12 and all(char in string.hexdigits for char in digits)


def send_magic_packet(mac, port=9):
    """Broadcast a Wake-on-LAN magic packet for `mac`. Returns False if mac is malformed."""
    if not is_valid_mac(mac):
        return False
    payload = b"\xff" * 6 + bytes.fromhex(_hex_digits(mac)) * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(payload, ("255.255.255.255", port))
    return True
