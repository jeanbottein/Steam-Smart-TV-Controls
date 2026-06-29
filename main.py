import asyncio
import logging
import os
import sys
import time

import decky

ROOT = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))

from tv_core.driver import build_registry, list_brands, select_driver
from tv_core.edid import connected_displays
from tv_core.logs import prune_logs, read_log_tail
from tv_core.store import Store
from tv_core.wol import is_valid_mac, resolve_mac, send_magic_packet
from tv_driver_lg import LgDriver

POLL_SECONDS = 5
TRIGGER_ATTEMPTS = 3
RETRY_SECONDS = 3
LOG_TAIL_LINES = 200
# Let gamescope finish its own dock-time display reconfiguration before we perturb
# the HDMI link by switching inputs — doing both at once can crash the Steam client.
# Lower = snappier switch but closer to that collision window; 5s leaves some margin.
SETTLE_SECONDS = 5
# An input switch can make the TV briefly drop and re-add the HDMI link, which looks
# like the display reappearing. Ignore a display we just acted on for this long so a
# flapping link can't machine-gun switches.
COOLDOWN_SECONDS = 60
# When a TV is asleep, Wake-on-LAN it and wait this long for the control API to boot.
# A TV in standby answers in a few seconds; one that powered itself fully off (LG TVs
# do this after hours with no signal) needs a whole cold boot, so the budget is wide.
WAKE_TIMEOUT = 60
WAKE_POLL = 2
# A single magic packet can be dropped, and a cold NIC may miss the first few, so send
# a small burst each cycle rather than relying on one packet landing.
WAKE_BURST = 3
# Suspend freezes this whole process, so the poll loop never observes the docked
# display "disappear" and re-appear across a sleep — meaning rules would never fire on
# wake. CLOCK_BOOTTIME counts suspended time while CLOCK_MONOTONIC does not, so a jump
# in their difference larger than this (seconds) means we just resumed and should
# forget what we've seen and re-evaluate the connected displays from scratch.
RESUME_THRESHOLD = 10

# Keep the vendored websockets library from writing chatty connection logs.
logging.getLogger("websockets").setLevel(logging.WARNING)

REGISTRY = build_registry([LgDriver()])


class Plugin:
    async def _main(self):
        prune_logs(decky.DECKY_PLUGIN_LOG_DIR)
        settings_path = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "deckatv.json")
        self.store = Store(settings_path)
        self.seen = set()
        self.last_trigger = {}  # display_id -> monotonic time of the last switch
        self.tasks = set()  # in-flight delayed switches, kept alive and cancellable
        self.watcher = asyncio.get_event_loop().create_task(self._watch())

    async def _unload(self):
        watcher = getattr(self, "watcher", None)
        if watcher is not None:
            watcher.cancel()
        for task in list(getattr(self, "tasks", ())):
            task.cancel()

    async def list_brands(self):
        return list_brands(REGISTRY)

    async def list_tvs(self):
        return self.store.tvs

    async def get_selected_tv(self):
        return self.store.selected

    async def set_selected_tv(self, host: str):
        self.store.set_selected(host)

    async def list_rules(self):
        return self.store.rules

    async def list_displays(self):
        return connected_displays()

    async def read_logs(self):
        return read_log_tail(decky.DECKY_PLUGIN_LOG_DIR, LOG_TAIL_LINES)

    async def is_reachable(self, host: str):
        tv = self.store.find_tv(host)
        if tv is None:
            return False
        try:
            return await select_driver(REGISTRY, tv["brand"]).reachable(host)
        except Exception:  # noqa: BLE001 - any failure means "not reachable"
            return False

    async def get_inputs(self, host: str):
        """Return cached inputs immediately when offline; refresh the cache when online."""
        tv = self.store.find_tv(host)
        if tv is None:
            return []
        driver = select_driver(REGISTRY, tv["brand"])
        try:
            if not await driver.reachable(host):
                return self.store.cached_inputs(host)
            inputs = await driver.list_inputs(host, tv["creds"])
        except Exception:  # noqa: BLE001 - fall back to the last known list
            return self.store.cached_inputs(host)
        if inputs:
            self.store.set_inputs(host, inputs)
            if not tv.get("mac"):  # backfill the MAC for Wake-on-LAN while the TV is up
                self.store.set_mac(host, resolve_mac(host))
            return inputs
        return self.store.cached_inputs(host)

    async def pair_tv(self, host: str, name: str, brand: str):
        creds = await select_driver(REGISTRY, brand).pair(host)
        label = name or host
        self.store.upsert_tv(host, label, brand, creds, resolve_mac(host))
        return {"host": host, "name": label, "brand": brand}

    async def remove_tv(self, host: str):
        self.store.remove_tv(host)

    async def switch_input(self, host: str, input_id: str):
        await self._set_input(self.store.find_tv(host), input_id)

    async def set_rule(self, display_id: str, host: str, input_id: str, enabled: bool):
        self.store.set_rule(display_id, host, input_id, enabled)

    async def remove_rule(self, display_id: str):
        self.store.remove_rule(display_id)

    async def _set_input(self, tv, input_id):
        if tv is None:
            raise ValueError("unknown TV")
        if not await self._wake(tv):
            raise ConnectionError(f"{tv['name']} is unreachable and would not wake")
        await select_driver(REGISTRY, tv["brand"]).set_input(tv["host"], tv["creds"], input_id)

    async def _wake(self, tv):
        """Ensure the TV's control API is up, Wake-on-LAN-ing it from standby/off first.

        Returns True once it's reachable, False if it never came up within the budget
        (e.g. the TV is unplugged, or "Mobile TV On" / wake-over-LAN is disabled on it).
        """
        driver = select_driver(REGISTRY, tv["brand"])
        if await driver.reachable(tv["host"]):
            return True
        mac = tv.get("mac")
        if not mac or not is_valid_mac(mac):  # can't wake without a usable MAC
            return False
        deadline = time.monotonic() + WAKE_TIMEOUT
        while True:
            for _ in range(WAKE_BURST):
                send_magic_packet(mac)
            await asyncio.sleep(WAKE_POLL)
            if await driver.reachable(tv["host"]):
                return True
            if time.monotonic() >= deadline:
                return False

    async def _watch(self):
        last_error = None
        suspended = self._suspended_seconds()
        while True:
            now_suspended = self._suspended_seconds()
            if now_suspended - suspended > RESUME_THRESHOLD:
                # We just woke from sleep. The display never looked like it left, so
                # forget it (and any cooldown) and let this poll re-apply the rules.
                decky.logger.info("resume detected; re-evaluating displays")
                self.seen = set()
                self.last_trigger.clear()
            suspended = now_suspended
            last_error = await self._poll(last_error)
            await asyncio.sleep(POLL_SECONDS)

    @staticmethod
    def _suspended_seconds():
        # CLOCK_BOOTTIME includes time spent suspended; CLOCK_MONOTONIC does not. Their
        # difference is exactly how long the system has been asleep since boot.
        return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()

    async def _poll(self, last_error):
        """Apply rules once; log a persistent failure only when it changes."""
        try:
            await self._apply_rules()
            return None
        except Exception as error:  # noqa: BLE001 - never let the loop die
            message = str(error)
            if message != last_error:
                decky.logger.warning(f"auto-switch poll failed: {message}")
            return message

    async def _apply_rules(self):
        appeared = self._take_appeared()
        now = time.monotonic()
        ready = [rule for rule in self.store.rules if self._ready(rule, appeared, now)]
        for rule in ready:
            self.last_trigger[rule["display_id"]] = now
            self._spawn(self._trigger_later(rule))

    def _take_appeared(self):
        present = {display["id"] for display in connected_displays()}
        appeared = present - self.seen
        self.seen = present
        return appeared

    def _ready(self, rule, appeared, now):
        if not rule.get("enabled"):
            return False
        if rule["display_id"] not in appeared:
            return False
        return now - self.last_trigger.get(rule["display_id"], 0.0) >= COOLDOWN_SECONDS

    def _spawn(self, coro):
        task = asyncio.get_event_loop().create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _trigger_later(self, rule):
        # Wait out gamescope's own dock-time display setup before touching the HDMI link.
        await asyncio.sleep(SETTLE_SECONDS)
        await self._trigger(rule)

    async def _trigger(self, rule):
        tv = self.store.find_tv(rule["host"])
        if tv is None:
            return
        # Wake once, with the full budget. If it never comes up there's no point hammering
        # the input switch, so bail with a clear reason rather than three doomed attempts.
        if not await self._wake(tv):
            decky.logger.info(f"auto-switch: {tv['name']} never woke (check wake-over-LAN)")
            return
        driver = select_driver(REGISTRY, tv["brand"])
        for attempt in range(TRIGGER_ATTEMPTS):
            try:
                await driver.set_input(tv["host"], tv["creds"], rule["input_id"])
                decky.logger.info(f"auto-switch: {tv['name']} -> {rule['input_id']}")
                await decky.emit("auto_switch", tv["name"], rule["input_id"])
                return
            except Exception as error:  # noqa: BLE001 - SSAP may not be ready right after boot
                decky.logger.info(f"auto-switch attempt {attempt + 1} failed: {error}")
                await asyncio.sleep(RETRY_SECONDS)
