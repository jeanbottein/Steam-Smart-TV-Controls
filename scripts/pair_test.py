#!/usr/bin/env python3
"""Standalone LG webOS pairing probe. Usage: python3 scripts/pair_test.py [HOST]

Diagnoses each step so we can see where pairing stalls:
  1. raw TCP reachability to ports 3000/3001
  2. WebSocket handshake
  3. SSAP register (accept the prompt on the TV)
"""

import asyncio
import os
import socket
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))

from tv_driver_lg import webos

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.182"


def _check_port(host, port, timeout=4):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError as error:
        print(f"   port {port}: UNREACHABLE ({error})")
        return False
    finally:
        pass


def probe_tcp(host):
    print(f"[1] TCP reachability to {host}")
    open_ports = [port for port in (3000, 3001) if _ok(host, port)]
    if not open_ports:
        print("   -> no SSAP port open. TV off, wrong IP, or different subnet/firewall.")
    return open_ports


def _ok(host, port):
    reachable = _check_port(host, port)
    if reachable:
        print(f"   port {port}: open")
    return reachable


async def probe_pair(host):
    print(f"[2] WebSocket + SSAP register to {host}")
    print("    >>> WATCH THE TV: accept the pairing prompt within 60s <<<")
    try:
        key = await webos.pair(host)
    except Exception as error:  # noqa: BLE001 - this is a diagnostic
        print(f"   FAILED: {type(error).__name__}: {error}")
        return None
    print(f"   PAIRED. client-key:\n   {key}")
    return key


async def main():
    if not probe_tcp(HOST):
        return
    await probe_pair(HOST)


if __name__ == "__main__":
    asyncio.run(main())
