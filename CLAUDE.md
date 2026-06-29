# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DeckaTV is a [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin for the Steam Deck. It pairs with network TVs, switches their HDMI input from the Quick Access menu, and auto-switches a TV to a chosen input when the Deck is docked to that specific physical screen. A Python backend (`main.py` + `backend/`) talks to TVs and the OS; a React frontend (`src/`) is the Quick Access panel. The two communicate over Decky's `callable` RPC bridge (see `src/api.ts` ↔ the `async def` methods on `Plugin` in `main.py`).

### Layout

Decky loads the plugin from its root, so the files it requires there stay at the root and can't be moved: `main.py` (backend entry), `plugin.json`, `package.json`/`pnpm-lock.yaml`, and the build config `rollup.config.js` (defaults to `src/index.tsx`) / `tsconfig.json`. Everything else is grouped: `backend/` and `src/` are *your source* (Python + frontend); `scripts/` is build/deploy tooling; the gitignored `node_modules/`, `py_modules/`, `dist/` are *dependencies and build output*. The build/deploy scripts stage the root files + `backend/` + `py_modules/` + `dist/` into a flat plugin folder, so the deployed structure differs from the repo.

## Commands

```bash
make test        # unit tests: PYTHONPATH=backend pytest backend/tv_core/tests .github/scripts/tests -q
make build       # frontend only -> dist/index.js (rollup)
make deploy      # build + rsync into ~/homebrew/plugins/DeckaTV on this machine
make release     # build the distributable deckatv-<version>.zip
pnpm run watch   # rebuild the frontend on change

# run a single test
PYTHONPATH=backend python3 -m pytest backend/tv_core/tests/test_store.py -q
PYTHONPATH=backend python3 -m pytest backend/tv_core/tests/test_driver.py::<name> -q

# deploy to a Deck over SSH (defaults: deck@steamdeck.lan)
DECK_HOST=192.168.1.50 ./scripts/deploy_remote.sh
```

There is no Python linter config and no JS test suite; `make test` covers the core library and the release-version tooling only. `scripts/pair_test.py` is a manual, network-dependent smoke script (pairs against a real TV), not part of `make test`. The build/deploy scripts (`scripts/*.sh`) `cd` to the repo root themselves, so they can be run from anywhere.

## Architecture

Dependencies point one way: `tv_driver_lg → tv_core`, and `main.py → both`. **The core never imports a concrete driver.** `main.py` is the composition root — it builds the driver registry (`REGISTRY = build_registry([LgDriver()])`) and is the only place that names a brand.

- `backend/tv_core/` — brand-agnostic core.
  - `driver.py` — the `TvDriver` contract (`pair`, `list_inputs`, `set_input`, `reachable`) plus the registry (`build_registry`/`list_brands`/`select_driver`).
  - `store.py` — JSON-persisted state: paired TVs (`{host, name, brand, creds, mac?, inputs?}`), per-screen `rules`, and the last-selected TV. `creds` is whatever opaque JSON the driver's `pair` returned — the core never inspects it. `set_inputs` also repoints any rule whose cached input no longer exists.
  - `edid.py` — `connected_displays()` reads `/sys/class/drm`; each display's `id` is its EDID monitor name (falling back to a vendor+product code). Rules key off this EDID identity, so a rule follows the **physical TV**, not an HDMI port.
  - `wol.py` — Wake-on-LAN. MAC is learned from `/proc/net/arp` while the TV is awake (at pairing or any reachable moment) and backfilled into the store, so the TV can later be woken from standby.
- `backend/tv_driver_lg/` — the LG driver. `__init__.py` is the thin `TvDriver` subclass; `webos.py` is the LG SSAP-over-WebSocket client. All LG-specific code stays here.
- `src/` — React UI. Generic: brand is just a dropdown populated from `list_brands`. `index.tsx` is the panel root; `api.ts` declares every backend RPC.
- `py_modules/websockets/` — the pure-Python `websockets` dependency, **vendored** (gitignored; produced by `scripts/vendor_python.sh`, pinned version inside that script). `main.py` adds `py_modules/` and `backend/` to `sys.path` at import time.

### The auto-switch loop (`Plugin._watch` in `main.py`)

A 5s poll diffs `connected_displays()` against the last seen set. Application is **level-driven, not edge-driven**: a newly-appeared display *queues* its rule (`_enqueue` → `self.pending`), and every subsequent poll re-attempts queued rules (`_drain` → `_attempt`) until the switch actually lands or a budget expires. This is deliberate — firing once on the appearance lost the switch whenever the network/TV wasn't ready in that one window, which is exactly the case on cold boot (Wi-Fi not up yet) and often on resume. A successful switch stamps `last_success[display_id]`; one attempt per display runs at a time (`self.inflight`). The tuned constants at the top of `main.py` exist for real hardware hazards — read their comments before changing them:

- `SETTLE_SECONDS` — wait out gamescope's own dock-time display reconfig before perturbing the HDMI link (switching too early can crash the Steam client). Applied as the `after` delay before the first attempt.
- `APPLY_BUDGET_SECONDS` — how long a queued rule keeps getting retried (each poll) before giving up. Covers slow Wi-Fi association on boot and slow TV wake.
- `COOLDOWN_SECONDS` — an input switch can make the link flap and look like the display reappearing; a re-appearance within this window of the last *successful* switch is ignored (debounce).
- Suspend/resume: the process is frozen during sleep, so the docked display never appears to "leave and return." `_suspended_seconds()` compares `CLOCK_BOOTTIME` vs `CLOCK_MONOTONIC`; a jump past `RESUME_THRESHOLD` means we resumed, so `seen`/`pending`/`last_success` are cleared to re-queue and re-apply rules on wake.
- `_wake` Wake-on-LANs an unreachable TV (burst of magic packets) and waits up to `WAKE_TIMEOUT` for the control API; it opportunistically re-resolves the MAC from ARP if one was never learned. A TV with no resolvable MAC, or wake-over-LAN disabled, simply won't wake.

## Adding a new brand

1. Create `backend/tv_driver_<brand>/` with a `TvDriver` subclass implementing `pair`, `list_inputs`, `set_input`, `reachable`, plus a unique `name` (stable id stored on each TV) and `label` (UI text).
2. Inject it in `main.py`: `build_registry([LgDriver(), <Brand>Driver()])`.

Nothing in `tv_core` or `src/` changes — the brand appears in the UI dropdown automatically.

## Releases

Pushing to `main` triggers `.github/workflows/release.yml`, which runs `.github/scripts/determine_version.py` to compute the next semver from **conventional commits** since the latest tag, then tags and publishes a GitHub release with the built zip. Commit-type → bump: `ci`/`doc`/`docs` skipped; `chore`/`fix` → patch; anything else → minor; `!` or `BREAKING CHANGE:` → major. A non-conventional subject is ignored for versioning. If no commit warrants a bump, nothing is released. The release commit/tag is made detached (off `main`) so the branch isn't advanced.
