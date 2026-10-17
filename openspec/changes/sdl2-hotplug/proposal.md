## Why

A controller connected after launch is ignored on the SDL hosts (macOS, native Linux), and one pulled and replugged never comes back (user, 2026-10-06; BLX-15). The toolkit's SDL backend (`src/input/xinput_device.c`) opens the controllers present at init and nothing else; its own comment says `SDL_CONTROLLERDEVICEADDED/REMOVED` are not handled. It is the last blocker for v1. The Windows/Proton build uses XInput, which probes each user index, and already follows the host.

`input-real-devices` (archived 2026-10-13) had the requirement "Hot-plugging follows the host" (insert/remove masks within a second, disconnected ports probed at most once a second, SDL device events with stable slots) and its task 9.1; both were dropped from it and parked on BLX-15 and BLX-78. The `input` spec's XInput-override requirement today limits the transitions to the controllers the SDL backend opened at start.

## What Changes

- **Toolkit, SDL backend only** (`src/input/xinput_device.c`): a port table under one mutex. A controller SDL adds is opened into a port, and one it loses is closed and its port freed. Ports never shift: a new pad takes the port its model (joystick GUID) last held when that is free and another pad is connected, else the lowest free port. An `SDL_AddEventWatch` only raises a flag. The thread that pumps SDL rescans on it, and at most once a second without it: the window's loop, or the poll itself in headless runs. Device-index calls never run on a poll thread beside the window's pump, because sdl2-compat's index list is unlocked. `[INPUT] host pad added/removed port=<n>` lines.
- **Toolkit, the SDL window's loop** (`src/video/fb_present_sdl.c`): calls `xbox_InputSdlPadSync()` once per loop, where the pads are opened and closed.
- **Toolkit test** `tests/input_hotplug_sdl` (POSIX): SDL virtual joysticks attached, detached and reattached through the public API, checking ports, masks, `ERROR_DEVICE_NOT_CONNECTED` and polls racing hot-plug.
- **cat**: the `input` delta below (the requirement restored, the override requirement's SDL sentence updated); the README known issue "A controller connected after launch is ignored" goes; TASKS.
- Nothing changes in cat's `pad_input.c` or `recomp_manual.c`: they already turn the toolkit's per-port connection state into the `ports=` lines and the `XGetDeviceChanges` masks.

Out of scope: SDL3 (BLX-78, `feat/sdl3-migration`, which keeps its own D8 and can take this code over), sticky slots and rebinding (BLX-26), the macOS `RECOMP_HOST_PAD` default (input-real-devices 9.3), any Windows, D3D11 or XInput change.

## Capabilities

### Modified Capabilities
- `input`: "The title's XInput entry points are overridden" (the SDL sentence), and the restored requirement "Hot-plugging follows the host".

## Impact

- Toolkit `posix-host/portability`: `src/input/xinput_device.c` (POSIX half), `src/video/fb_present_sdl.c` (exit path), `src/input/README.md`, `src/input/CMakeLists.txt`, `tests/input_hotplug_sdl/`. The `_WIN32` half of `xinput_device.c` and every Windows file are untouched, so the Windows/Proton exe is unchanged.
- cat: `README.md`, `TASKS.md`, this change. No env key, no `docs/env.md` row, no regeneration.
- Upstream: the SDL backend is upstream-shaped code in our fork; this fix rides with the SDL topic PR when the PR plan reaches it.
