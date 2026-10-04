## Why

Nothing can press a button. The XAPI USB stack in `XPP` (OHCI host controller, XID class driver) is translated code, but nothing enumerates a device on macOS, so `XGetDevices` never reports a gamepad. The toolkit's `RECOMP_PAD_PRESS` goes through `usb_gamepad_report`, which is never called. Every test run therefore sits through about 84 s of intro movies before the title, and can never leave the title.

## What Changes

- Replace the seven XDK XInput entry points the game calls with hand-written overrides in `src/recomp_manual.c`, the same mechanism as the vblank pacer: `XGetDevices` `0x00367EEC`, `XGetDeviceChanges` `0x00367F0E`, `XInputOpen` `0x0036821D`, `XInputClose` `0x00368273`, `XInputGetCapabilities` `0x0036827F`, `XInputGetState` `0x00368457` and `XInputSetState` `0x003684CA`. A gamepad is reported on port 0. The USB path is bypassed, not fixed.
- Add `src/pad_input.c`, which supplies the pad state from two sources, merged:
  - a script, `RECOMP_INPUT_SCRIPT` (inline, a file, or a built-in `@preset`): a list of steps run in order, which wait on events (`wait open <text>` for a file open, `wait polls N`, `wait SECS`), tap a button until a file opens, or press and release buttons, analog values and sticks. Every change, step and matched open is logged as `[INPUT] t=...`;
  - the host pad through the toolkit's `xbox_input` (XInput, plus `RECOMP_KEYBOARD`, on Windows and Proton; SDL2 GameController elsewhere with `RECOMP_HOST_PAD=1`).
- Built-in presets on events, not wall time: `@skip-intro` and `@attract` (skip the intro movies, then press nothing, so the title's timer starts the attract demo) and `@new-game` (then START on the title, A on the story opening). The first presets were timed and broke when startup got faster: on Proton with D3D11 their START taps landed on the title and started a new game.
- Toolkit: a file-open hook, `xbox_FileOpenHook`, called after every `NtCreateFile` with the guest path and status. cat installs it before the game starts.
- Adding or removing an override needs a regen (`scripts/pipeline.sh recomp`).

## Capabilities

### New Capabilities
- `input`: controller input for the title, from a script or the host pad, through XInput overrides.

## Impact

- `src/recomp_manual.c`, new `src/pad_input.c`, `CMakeLists.txt`. gen/ must be regenerated so it declares the seven functions instead of defining them.
- Toolkit: `xbox_FileOpenHook` in `src/kernel/kernel_bridge.c` and `kernel.h` (two lines in `bridge_NtCreateFile`). `src/usb/ohci.c` stays unused (and `RECOMP_USB` stays off).
- `src/main.c` calls `cat_pad_early_init()` before the entry point.
