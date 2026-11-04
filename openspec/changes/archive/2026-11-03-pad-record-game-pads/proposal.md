## Why

`RECOMP_DEBUG=pad_record=<file>` wrote nothing in a BLiNX 2 play session.
The recorder runs in the toolkit's USB pad model, in
`usb_gamepad_report` (`src/usb/usb_gamepad.c`). BLiNX 2 does not use that
model: it answers the title's `XInputGetState` itself (`recomp_manual.c` →
`cat_pad_get_state` in `src/pad_input.c`). So the report never runs, the
recorder never opens its file, and `RECOMP_PAD_SCRIPT` and `RECOMP_PAD_LIVE`
press nothing either. A route played by hand cannot become a replayable
script.

The other games (BLiNX 1, Burnout 3, SSX 3, JSRF, KUF, Spartan) reach the
pad through the USB model. BLiNX 1 does this as a `UsbPadSource`. Their
recorder already runs, so they have no gap.

## What changes

- Toolkit (`usb_gamepad.h`): a tap for a game that answers `XInputGetState`
  itself:
  - `usb_gamepad_game_press(pad, &g)` presses the script's, the live file's
    and the synthetic press's buttons on top of the game's state;
  - `usb_gamepad_game_record(pad, &g)` writes the state the title gets to
    the pad record, on every poll, under the flip that poll's press used;
  - `usb_gamepad_game_pads()` names the pads those inputs drive.

  The tap uses the same flip count (the walker's) and the same step format
  as the USB path, so a record made on either path replays on either.
  `USB_GAMEPAD_HAVE_GAME_TAP` marks the header.
- cat (`cat_pad_get_state`): presses the toolkit script after the game's
  own sources and the mod pad filter. It records the state after
  `camera.free`, which is the state the title reads. The script's ports
  count as connected, so a replay needs no other source. A toolkit pin
  without the tap builds as before.
- A toolkit ctest, `tests/usb_pad_game`, that records a scripted run and
  replays the record.

Stock behaviour does not change. With neither variable set, the tap
presses nothing and records nothing.
