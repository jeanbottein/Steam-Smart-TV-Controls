# DeckaTV

A Decky Loader plugin for the Steam Deck that pairs with network TVs, lets you
switch their HDMI input from the Quick Access menu, and automatically switches a
TV to a chosen input when the Deck is docked to that specific screen.

The core is brand-agnostic. **LG (webOS)** ships as the first driver; other
brands plug in without touching the rest of the code.

## Features

- Pair one or more TVs (pick the brand, enter the IP).
- Manually switch any paired TV's input.
- Per-screen auto-switch rules: each connected display maps to a TV + input,
  applied the moment that screen appears (e.g. docking to the living-room TV
  jumps it to the Deck's HDMI port).

## Architecture

```
main.py                         composition root: builds the driver registry, wires the plugin
packages/
  tv_core/                      brand-agnostic core (knows no driver)
    driver.py                   TvDriver contract + registry (build/list/select)
    edid.py                     display detection
    store.py                    paired TVs + rules; TV = {host,name,brand,creds}
    tests/                      core unit tests (excluded from the release)
  tv_driver_lg/                 LG driver package (depends on tv_core)
    __init__.py                 LgDriver
    webos.py                    LG SSAP WebSocket client
src/                            React UI (generic; brand is just a dropdown)
py_modules/websockets/          vendored pure-Python dependency (built in CI)
```

Single repository, single release. Dependencies point one way:
`tv_driver_lg → tv_core`, and `main.py → both`. The core never imports a driver;
it only calls `pair`, `list_inputs`, and `set_input` on the `TvDriver` contract.
Displays are identified by EDID, so a rule follows the physical TV rather than a
port. A 5-second poll detects when a screen appears and applies its rule.

## Adding a new brand

1. Create `packages/tv_driver_<brand>/` with a `TvDriver` subclass implementing
   `pair`, `list_inputs`, `set_input`, plus a unique `name` and `label`.
2. Inject it in `main.py`: `build_registry([LgDriver(), <Brand>Driver()])`.

Nothing in `tv_core` changes; the brand appears in the UI dropdown automatically.

## Install (prebuilt)

1. Install Decky Loader on your Deck (Developer mode enabled — the plugin needs
   `_root` to read display info).
2. Extract `deckatv-<version>.zip` into `~/homebrew/plugins/`.
3. Restart Decky (or reboot). The plugin appears as "DeckaTV".

## Usage

1. Turn the TV on and connect it to your network.
2. Open the plugin, pick the brand, enter the IP, press **Pair**, and accept the
   prompt on the TV.
3. Use **Switch input** to change inputs manually.
4. Under **Auto-switch rules**, pick the TV and input for each screen and enable
   the toggle.

## Build from source

```bash
pnpm install
pnpm run build          # produces dist/index.js
```

The pure-Python `websockets` dependency is vendored under `py_modules/`.
