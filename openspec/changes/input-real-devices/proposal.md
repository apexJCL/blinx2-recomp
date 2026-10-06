## Why

Input works, but only for scripts. The `input` change (10/12 tasks) replaced the seven XDK XInput entry points with overrides fed by `RECOMP_INPUT_SCRIPT`, and every golden run, every bench run and every milestone so far has been driven by a preset such as `@stage1`, which reaches stage 1-1 through the title's debug stage select. Nobody has played the game on Proton with a controller in their hands. The host-pad half of the overrides was merged but never verified (`input` tasks 3.2 and 3.3 are the ones still open), and reading it against the toolkit shows why it would not have gone well:

- the toolkit's XInput backend maps Black and White the opposite way from its own README, applies no deadzone policy, and only caches connection state at init;
- the SDL2 backend (macOS) has no hotplug, and nothing pumps it fast enough for a game poll;
- the keyboard works only while the old GDI framebuffer window has focus, so it does nothing with the D3D11 window that Proton runs;
- `pad_input.c` reports port 0 as connected whenever the host pad is enabled, even with nothing plugged in, and on Windows the host pad is on by default, so a controller left plugged into the bench would leak into golden runs;
- the lifted right-stick Y at `0x0021C457` is zero-extended (`movsx eax, bp` lifted as `LO16`), so a real pad's right stick is wrong in the negative half.

Also, the only route into play is the debug menu. The normal route, boot → logos → title → START → story → team editor → SAVE GAME → hub → stage 1-1, has never been scripted or checked, so the menus, the save prompt and the save itself are untested on Proton.

## What Changes

- **Real controllers on Proton** through the existing overrides: the four ports map to XInput user indices; connection state is real and hot-plug follows the host; Black = RB and White = LB; sticks, triggers and face buttons keep the Duke's scales; rumble reaches the pad and stops on exit. The right-stick Y lifter bug is fixed in the recompiler and `gen/` regenerated.
- **Keyboard fallback** in the D3D11 window (Proton) and the SDL window (macOS), on port 0, off by default. No mouse: the game has no use for one.
- **Source isolation**: when a script is set, host devices and the keyboard are off unless `RECOMP_HOST_PAD=1` is explicit; `bench.sh golden` pins them off; parse errors can be fatal (`RECOMP_INPUT_STRICT`); taps can be counted in polls. Every run logs its input sources.
- **Latency**: the pad is sampled at the game's own poll (frame start, after its vblank wait) with no host-side buffering; a trace mode measures poll phase and press-to-poll latency; a vblank getter is added to the toolkit for it.
- **A virtual pad** (`scripts/vpad.py`, a uinput Xbox 360 pad lifted from `xemu_ref.py`) as the automatable real-device path on the Linux/Proton host: the de-risking spike, the mapping/hotplug checks and the latency measurement all run through it without the user at the machine.
- **The normal route**: an event-driven `@story-hub` preset (title START → R0_opening → team editor → SAVE GAME → hub) becomes a golden scenario with per-run save isolation (`RECOMP_SAVE_DIR`); a manual checklist for a real pad; the menu prompts catalogued; xemu frames for comparison under the existing safety rules. `@story-stage1`, the hub → stage 1-1 leg, follows once the route through the training drill is mapped.
- **macOS later**: SDL hotplug, GameController verification (`input` 3.3), same enablement rules.

## Why a new change, not an extension of `input`

`input` is the scripted pad: ten of its twelve tasks are verified, three golden scenarios depend on its presets, and its spec delta is the baseline this change modifies. Its two open tasks are the verifications this change's phases 1 and 9 perform properly; they are marked as moved. Extending `input` would keep a nearly-finished change open for weeks and mix a stable, golden-covered feature with new toolkit work, a recompiler fix and a new capability. A separate change also gives the implementation sub-agents their own worktrees and branches. The dependency is explicit: `input` is archived first (its delta becomes `openspec/specs/input/spec.md`), and this change's `input` delta uses MODIFIED against those requirements.

## Capabilities

### New Capabilities
- `game-route`: the normal route from boot to play, scripted on game events as a regression check and checked by hand with a real controller.

### Modified Capabilities
- `input`: host controllers become a first-class, verified source (mapping, scales, hotplug, four ports, rumble, keyboard), isolated from scripted runs, with bounded sampling latency.

## Impact

- **cat** (`wt/inputspec/cat`, branch `input/spec2` or a branch derived from it): `src/pad_input.c` (sources, isolation, logging, trace, poll-counted taps, new presets), `src/recomp_manual.c` (connection reporting, capabilities), `scripts/vpad.py` (new), `scripts/bench.sh` and `analysis/golden/golden.json` (pinned env, `story` scenario; coordinate with the golden agent), `scripts/xemu_ref.py` (story scenario), `openspec/changes/deviations-register`, and the project notes. `gen/` is regenerated once for the lifter fix.
- **toolkit** (`wt/inputspec/xboxrecomp`, branch `input/main2`, derived from `posix-host/portability`): `src/input/` (mapping table and pure helpers, deadzone option, connection cache with backoff, SDL hotplug, shutdown), a shared key table used by `src/d3d/nv2a_pb_d3d11.c` and `src/video/fb_present_sdl.c`, `src/kernel/kernel_bridge.c` (vblank getter), `src/kernel/kernel_path.c` (`RECOMP_SAVE_DIR`), the recompiler's `movsx r32, r16` lifting, new ctests `tests/input_map` and a lifter test, README env table. All changes are small and upstreamable; `src/usb/` stays unused and `RECOMP_USB` off.
- **the Linux/Proton host**: runs by the bench agent and the user only, under `flock ~/.recomp-run.lock`, via `bench.sh`. The virtual pad is created only for a run and removed after it. The xemu scripts' rules stand: never touch the user's own xemu instance; frames and saves stay local.
- **Other changes**: `saves` (the SAVE GAME step exercises it on Proton; failures there are handed over, not fixed here), `bench-methodology` (golden env pinning), `deviations-register` (new entries), `audio` (untouched).

## Status

In progress (reviewed 2026-10-06 in the openspec cleanup). Merged: the Proton spike and a real pad on Proton (1.x), source isolation and determinism (2.x), host-pad fidelity, rumble and the lifter fix (3.x), the scripted story route, `RECOMP_SAVE_DIR`, the `story` golden and the real-pad checklist (6.1-6.6), the macOS SDL pad (9.2), and `RECOMP_SAVE_SEED` with `@story-load` (7.2's first half). `saves` is archived as superseded (its scope landed here and elsewhere), and `deviations-register` is now the main `deviations` spec.

Still open: the keyboard work of 4.x (the shared key table, the SDL keyboard for macOS and other POSIX hosts, the docs; today the key state comes only from the Win32 window procedure in `fb_present.c`); latency measurement (5.x; `xbox_VblankCount` exists, `xbox_VblankLastTickNs` does not); the xemu `story` scenario (6.7); hub to stage 1-1 without the debug menu, which is blocked by the rank-exam gate (7.1-7.3); deviation entries and env docs (8.x); SDL hot-plug (9.1, deferred to a final user check); and the macOS `RECOMP_HOST_PAD` default (9.3, with `packaging-ux` 8.3). The spec delta describes the finished change; archive only when these are done or dropped, so that the main `input` spec does not claim hot-plug or a keyboard on every host.
