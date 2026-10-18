## Why

The tracker item. A Steam Deck launched from Desktop Mode (Konsole, `debug-menu.sh`) logged `host port=1` and `ports=0x3`: the script on port 0, the pad on port 1. `src/pad_input.c` mapped host slot N (the XInput user index, or the SDL slot) to guest port N, and the title reads player 1 from port 0 only, so the pad did nothing. Every earlier Deck log was taken in Game Mode, where Steam Input puts the pad on index 0, which hid the bug.

That log fits two causes, and does not tell them apart:
- the Deck's built-in pad alone on XInput user index 1, index 0 empty;
- Steam's inert virtual pad (28de:11ff) holding index 0, with the real pad on index 1. A Proton run on the bench with Steam Input on (no `PROTON_NO_STEAMINPUT`) reproduces this exactly: `pads=0:0,1:1`, START seen on port 1 (bench-logs 20261013-194641). The same run with `PROTON_NO_STEAMINPUT=1` gives `pads=0:0` and START on port 0 (20261013-195017).

Which cause the Deck has stays unknown until a Desktop Mode log shows the new `pads=` field (task 5.5). Both are fixed here: the first by giving ports out in the order pads come up, the second by handing an inert pad's port to the first pad that is pressed.

## What Changes

- **Toolkit (`fix/pad-only-state-r2`, the two commits of `fix/pad-only-state` 631c5f4 on posix-host/portability c8a8214f):** `xbox_InputGetPadState(slot, state)` reads one host pad alone, under the same probe and cache rule as `xbox_InputGetState` but without the keyboard and mouse merge that `xbox_InputGetState` does on slot 0. `xbox_InputMergeKbm(pad, kb)` exports that merge rule. `xbox_InputGetState` is now these two calls, so its behaviour is unchanged for Burnout 3 and the README example. `tests/input_map` counts keyboard reads with the fake backend.
- **New `src/pad_slots.c`/`.h`:** a pure slot-to-port map with no host or guest state, so `scripts/test_pad_slots.py` compiles it alone. A slot that comes up takes the lowest free port and keeps it until it goes away. A slot's first activity swaps it onto the lowest port held by a slot that has never been active. See design.md.
- **`pad_input.c`:**
  - The map is updated wherever the connected mask is computed: at init, and on the title's `XGetDevices`, `XGetDeviceChanges`, `XInputOpen` and `XInputGetCapabilities` calls (`cat_pad_connected_mask`). The one-second probe of idle slots reads them through `xbox_InputGetPadState`; the old "never probe slot 0 while the keyboard is on" exception is gone.
  - `cat_pad_get_state` reads the mapped slot through `xbox_InputGetPadState`. On port 0 only, when the keyboard or the mouse is on, it reads them through `xbox_InputKbmPoll` and merges them with `xbox_InputMergeKbm`. That is one read per poll, whatever slot drives port 0, because the poll consumes the mouse motion and steps `kbm_script`.
  - On each port-0 poll, while any pad holding a port has never been active, every such pad is read alone (a lone pad included, and whether or not the title polls its port) and the pressed ones go to `pad_slots_activity`, which marks them and swaps a first press onto an inert pad's lower port. The check runs before port 0's own read, so a press that moves a pad onto port 0 is seen there in the same poll. On a swap both pads' motors are stopped and the per-port host log state is cleared.
  - `cat_pad_rumble` forwards to the mapped slot.
  - A slot that comes back takes the port it held when it went, if that port is free and another pad holds one (sdl2-hotplug D2, restated at the title's ports, design.md decision 7). While port 0 has no source, the watch runs on the other ports' polls.
- **Log:** the `[INPUT] sources` line gains `pads=<slot:port,...|none>`. `[INPUT] t=<s> pads=<map>` is logged when a pad takes or gives up a port, and `[INPUT] t=<s> pads=<map> active=<slot mask>` when a first press moves one, the mask listing every pad that has been active. A first press that moves nothing is not logged.
- **No env key.** One pad on slot 0 behaves as before, and a swap only happens while a pad holding a lower port has never been pressed, so there is nothing to opt out of.

## Capabilities

### Modified Capabilities
- `input`: "A host pad can drive the pad" (slot N no longer means port N; a first press takes an inert pad's port; the keyboard and mouse are read once per port-0 poll in cat), "Rumble reaches the host controller" (the controller driving the port; motors stopped on a swap), "Input sources are logged" (`pads=`, `active=`).

## Non-goals

- Telling Steam's virtual pad apart by VID/PID: XInput does not expose them, and activity works on both backends.
- Hot-plug on SDL hosts is the tracker item (`sdl2-hotplug`, merged first). This change makes its stable-port rules part of the one slot-to-port map, at the title's ports (design.md decision 7), and leaves the backend's slots as they are.
- A way to pin a pad to a port by hand.

## Impact

- toolkit: `src/input/input_core.c`, `src/input/xinput_xbox.h`, `src/input/README.md`, `tests/input_map/test_main.c`. Cat needs this branch merged first; the squash sha goes in `game.toml` by the usual round.
- cat (`fix/pad-slot0-r2`, base main 04eaf77; the first rounds were `fix/pad-slot0` off 1f17f8e): `src/pad_slots.c`, `src/pad_slots.h`, `src/pad_input.c`, `src/recomp_manual.c` (comments), `CMakeLists.txt`, `scripts/test_pad_slots.py`, `docs/env.md` (the `RECOMP_HOST_PAD` row and refreshed line references).
- No change to goldens: they run with the host pad off (`pads=none`), and the sources line only gains a field.
