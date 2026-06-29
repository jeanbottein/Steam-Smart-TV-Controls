"""Brand-agnostic TV driver contract and registry.

The core never imports a concrete driver. The plugin (composition root) builds
the registry from injected drivers, so adding a brand never touches this module.
"""


class TvDriver:
    name = ""  # stable brand id stored on each TV record
    label = ""  # human-readable brand name shown in the UI

    async def pair(self, host):
        """Pair with the TV at `host` and return opaque, JSON-serializable creds."""
        raise NotImplementedError

    async def list_inputs(self, host, creds):
        """Return [{id, label}] of selectable inputs."""
        raise NotImplementedError

    async def set_input(self, host, creds, input_id):
        """Switch the TV to `input_id`."""
        raise NotImplementedError

    async def reachable(self, host):
        """Return True if the TV at `host` answers on the network."""
        return False

    async def discover(self):
        """Return [{host, name}] of TVs found on the LAN for this brand.

        Optional: brands that can't (or don't yet) auto-discover return []. The
        core never knows *how* a driver finds TVs — only that it may return some.
        """
        return []


def build_registry(drivers):
    return {driver.name: driver for driver in drivers}


def list_brands(registry):
    return [{"id": driver.name, "label": driver.label} for driver in registry.values()]


def select_driver(registry, brand):
    driver = registry.get(brand)
    if driver is None:
        raise ValueError(f"unsupported brand: {brand}")
    return driver
