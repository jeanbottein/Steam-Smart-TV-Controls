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
LOG_TAIL_LINES = 200
# Let gamescope finish its own dock-time display reconfiguration before we perturb
# the HDMI link by switching inputs — doing both at once can crash the Steam client.
# Lower = snappier switch but closer to that collision window; 5s leaves some margin.
SETTLE_SECONDS = 5
# An input switch can make the TV briefly drop and re-add the HDMI link, which looks
# like the display reappearing. Ignore a display we just acted on for this long so a
# flapping link can't machine-gun switches.
COOLDOWN_SECONDS = 60
# A newly-appeared display usually isn't actionable the instant it shows up: on cold boot
# the Deck's Wi-Fi isn't connected yet, and a TV woken from standby needs a moment before
# its control API answers. So rather than fire once and give up (which loses the switch
# whenever the network or TV is a beat slow — the cause of flaky dock-on-boot/resume), we
# keep re-attempting the rule on each poll until the switch lands or this budget elapses.
APPLY_BUDGET_SECONDS = 180
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
        settings_path = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "smart-tv-controls.json")
        self.store = Store(settings_path)
        self.seen = set()
        self.pending = {}  # display_id -> {after, deadline}: rules awaiting a successful switch
        self.inflight = set()  # display_ids with an attempt running (one at a time per display)
        self.last_success = {}  # display_id -> monotonic time of the last successful switch
        self.tasks = set()  # spawned attempts, kept alive and cancellable on unload
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

    async def discover_tvs(self, brand: str):
        """Auto-discover TVs on the LAN for `brand`; [] if the brand can't or it fails."""
        try:
            return await select_driver(REGISTRY, brand).discover()
        except Exception:  # noqa: BLE001 - discovery is best-effort; the UI still allows manual entry
            return []

    async def pair_tv(self, host: str, name: str, brand: str):
        creds = await select_driver(REGISTRY, brand).pair(host)
        label = name or host
        self.store.upsert_tv(host, label, brand, creds, resolve_mac(host))
        return {"host": host, "name": label, "brand": brand}

    async def remove_tv(self, host: str):
        self.store.remove_tv(host)

    async def switch_input(self, host: str, input_id: str):
        await self._set_input(self.store.find_tv(host), input_id)

    async def reapply_rules(self):
        """Re-assert the input rule for every currently-connected display — the equivalent
        of a console's "One Touch Play" when you press the controller's home button.

        Unlike the watch loop this ignores the appearance gate and the post-switch cooldown
        (the press is an explicit intent) and skips the gamescope settle delay, since no
        dock-time display reconfig is in flight. The driver no-ops when the TV is already on
        the target input, so pressing repeatedly is cheap. Reuses the same drain/attempt
        path, so retries, wake, and the one-attempt-per-display guard all still apply."""
        now = time.monotonic()
        present = {display["id"] for display in connected_displays()}
        queued = [
            rule["display_id"]
            for rule in self.store.rules
            if rule.get("enabled") and rule["display_id"] in present
        ]
        for did in queued:
            self.pending[did] = {"after": now, "deadline": now + APPLY_BUDGET_SECONDS}
        if queued:
            decky.logger.info(f"reapply requested for {queued}")
            self._drain(now)

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
        if not mac:  # never learned it (e.g. paired while offline) — the ARP table may be ready now
            mac = resolve_mac(tv["host"])
            if mac and is_valid_mac(mac):
                self.store.set_mac(tv["host"], mac)
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
                self.pending.clear()
                self.last_success.clear()
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
        # Level-driven, not edge-driven: an appearance *queues* a rule, and we keep
        # attempting queued rules every poll until the switch actually lands. Firing once on
        # the appearance lost the switch whenever the network or TV wasn't ready in that one
        # window — exactly the case on cold boot, and often on resume.
        now = time.monotonic()
        self._enqueue(self._take_appeared(), now)
        self._drain(now)

    def _take_appeared(self):
        present = {display["id"] for display in connected_displays()}
        appeared = present - self.seen
        self.seen = present
        return appeared

    def _enqueue(self, appeared, now):
        """Queue a rule (for repeated attempts) when its display newly appears."""
        for rule in self.store.rules:
            did = rule["display_id"]
            if not rule.get("enabled") or did not in appeared:
                continue
            # Debounce the link flap a switch itself can cause: ignore a re-appearance that
            # lands within COOLDOWN_SECONDS of this display's last *successful* switch.
            if now - self.last_success.get(did, -COOLDOWN_SECONDS) < COOLDOWN_SECONDS:
                continue
            self.pending[did] = {"after": now + SETTLE_SECONDS, "deadline": now + APPLY_BUDGET_SECONDS}

    def _drain(self, now):
        """Attempt each queued rule once per poll until it succeeds or its budget expires."""
        for rule in self.store.rules:
            did = rule["display_id"]
            slot = self.pending.get(did)
            if slot is None or did in self.inflight:
                continue
            if not rule.get("enabled"):  # disabled mid-budget — drop it from the queue
                self.pending.pop(did, None)
            elif now >= slot["deadline"]:
                self.pending.pop(did, None)
                decky.logger.info(f"auto-switch: gave up on {did} (not switchable within {APPLY_BUDGET_SECONDS}s)")
            elif did in self.seen and now >= slot["after"]:
                # Only switch while the display is actually connected, and only past the
                # gamescope settle delay. If it was undocked during settle we skip and let the
                # budget expire; a brief flap just defers the attempt to a later poll.
                self.inflight.add(did)
                self._spawn(self._attempt(rule, did))

    def _spawn(self, coro):
        task = asyncio.get_event_loop().create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _attempt(self, rule, did):
        """One switch attempt. On success the rule leaves the queue; on any failure it stays
        queued and the next poll retries (within the budget), so a TV or network that becomes
        ready a moment later still gets switched."""
        try:
            tv = self.store.find_tv(rule["host"])
            if tv is None:
                self.pending.pop(did, None)
                return
            if not await self._wake(tv):
                return  # asleep/unreachable right now — leave it queued for the next poll
            driver = select_driver(REGISTRY, tv["brand"])
            await driver.set_input(tv["host"], tv["creds"], rule["input_id"])
            self.last_success[did] = time.monotonic()
            self.pending.pop(did, None)
            decky.logger.info(f"auto-switch: {tv['name']} -> {rule['input_id']}")
            await decky.emit("auto_switch", tv["name"], rule["input_id"])
        except Exception as error:  # noqa: BLE001 - SSAP may not be ready just after boot; retry next poll
            decky.logger.info(f"auto-switch attempt for {did} failed: {error}")
        finally:
            self.inflight.discard(did)
