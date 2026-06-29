"""Minimal LG webOS (SSAP) client over WebSocket. LG-specific."""

import asyncio
import json
import ssl

CONNECT_TIMEOUT = 6
PAIR_TIMEOUT = 60
REQUEST_TIMEOUT = 10
REACH_TIMEOUT = 2
REACH_PORTS = (3001, 3000)

REGISTER_MANIFEST = {
    "manifestVersion": 1,
    "permissions": [
        "LAUNCH",
        "CONTROL_INPUT_TV",
        "READ_INPUT_DEVICE_LIST",
        "READ_TV_CURRENT_CHANNEL",
        "WRITE_SETTINGS",
    ],
}


class WebOSError(Exception):
    pass


def _insecure_ssl():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class WebOSClient:
    def __init__(self, host):
        self._host = host
        self._socket = None
        self._counter = 0

    async def __aenter__(self):
        self._socket = await self._open()
        return self

    async def __aexit__(self, *_):
        if self._socket is not None:
            await self._socket.close()

    async def _open(self):
        # Imported lazily so the package is importable (e.g. under unit tests) without the
        # vendored `websockets`, which only `main.py` puts on sys.path at runtime.
        from websockets.asyncio.client import connect

        endpoints = [
            (f"wss://{self._host}:3001", _insecure_ssl()),
            (f"ws://{self._host}:3000", None),
        ]
        last_error = None
        for url, context in endpoints:
            try:
                return await asyncio.wait_for(connect(url, ssl=context), CONNECT_TIMEOUT)
            except Exception as error:  # noqa: BLE001 - report any connection failure
                last_error = error
        raise WebOSError(f"cannot reach {self._host}: {last_error}")

    async def _send(self, message):
        await self._socket.send(json.dumps(message))

    async def _receive(self, timeout):
        return json.loads(await asyncio.wait_for(self._socket.recv(), timeout))

    async def register(self, key):
        payload = {"forcePairing": False, "pairingType": "PROMPT", "manifest": REGISTER_MANIFEST}
        if key:
            payload["client-key"] = key
        await self._send({"type": "register", "id": "register", "payload": payload})
        while True:
            message = await self._receive(PAIR_TIMEOUT)
            if message.get("type") == "registered":
                return message["payload"]["client-key"]
            if message.get("type") == "error":
                raise WebOSError(message.get("error", "registration rejected"))

    async def _request(self, uri, payload=None):
        self._counter += 1
        message_id = f"req-{self._counter}"
        await self._send({"type": "request", "id": message_id, "uri": uri, "payload": payload or {}})
        while True:
            message = await self._receive(REQUEST_TIMEOUT)
            if message.get("id") != message_id:
                continue
            if message.get("type") == "error":
                raise WebOSError(message.get("error", uri))
            return message.get("payload", {})

    async def list_inputs(self):
        payload = await self._request("ssap://tv/getExternalInputList")
        return [
            {"id": device["id"], "label": device.get("label", device["id"])}
            for device in payload.get("devices", [])
        ]

    async def switch_input(self, input_id):
        await self._request("ssap://tv/switchInput", {"inputId": input_id})

    async def current_input(self):
        """Return the id of the external input currently on screen, or None.

        Maps the foreground app's id back to an entry in the external input list;
        returns None when the TV isn't on an external input (e.g. an app is open).
        """
        foreground = await self._request("ssap://com.webos.applicationManager/getForegroundAppInfo")
        app_id = foreground.get("appId")
        if not app_id:
            return None
        payload = await self._request("ssap://tv/getExternalInputList")
        for device in payload.get("devices", []):
            if device.get("appId") == app_id:
                return device["id"]
        return None


async def reachable(host):
    """Quick TCP probe of the webOS SSAP ports; no pairing or handshake."""
    for port in REACH_PORTS:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), REACH_TIMEOUT
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001 - closing is best-effort
                pass
            return True
        except Exception:  # noqa: BLE001 - try the next port, then report unreachable
            continue
    return False


async def pair(host, key=""):
    async with WebOSClient(host) as client:
        return await client.register(key)


async def fetch_inputs(host, key):
    async with WebOSClient(host) as client:
        await client.register(key)
        return await client.list_inputs()


async def set_input(host, key, input_id):
    async with WebOSClient(host) as client:
        await client.register(key)
        # Skip the switch (and its HDMI renegotiation) if we're already on this input.
        try:
            already_current = await client.current_input() == input_id
        except Exception:  # noqa: BLE001 - if the check fails, fall back to switching
            already_current = False
        if already_current:
            return
        await client.switch_input(input_id)
