"""LG webOS driver package. All LG-specific code lives here."""

from tv_core.driver import TvDriver

from . import webos


class LgDriver(TvDriver):
    name = "lg"
    label = "LG (webOS)"

    async def pair(self, host):
        return await webos.pair(host)

    async def list_inputs(self, host, creds):
        return await webos.fetch_inputs(host, creds)

    async def set_input(self, host, creds, input_id):
        await webos.set_input(host, creds, input_id)

    async def reachable(self, host):
        return await webos.reachable(host)
