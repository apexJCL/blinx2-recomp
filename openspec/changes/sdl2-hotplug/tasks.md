Worktrees:
- `wt/hotplug/xboxrecomp`: toolkit, branch `feat/sdl2-hotplug` off `posix-host/portability` b6589fb1.
- `wt/hotplug/cat`: this spec, README and TASKS, branch `feat/sdl2-hotplug` off `main` 84907c9.

Mac runs are headless or windowed with `SDL_AUDIODRIVER=dummy`; builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools` and the shared Mac lock. No Deck run: nothing Windows-side changes (design D5).

## 0. Spec

- [x] 0.1 No Fable pass (the user, 2026-10-15). The Opus review at merge covers the code and this spec.

## 1. Toolkit

- [x] 1.1 `xinput_device.c` (POSIX half): the port table under `g_slot_lock`; `device_watch` (flag only); `rescan` and `maybe_rescan` (event, else once a second) on the pumping thread: `xbox_InputSdlPadSync` with a window, the poll headless (`SDL_GameControllerUpdate`); `open_device` with the port rule of design D2; `close_slot`; `get_state` and `set_state` under the mutex, closing a pad that is no longer attached at the first read. `[INPUT] host pad added/removed` lines.
- [x] 1.2 `fb_present_sdl.c`: `xbox_InputSdlPadSync()` once per event loop (design D1); exit unchanged, `xbox_InputAnyOpen` reads the table under the mutex (design D4).
- [x] 1.3 `src/input/README.md`: "Connection state and rumble" describes the SDL ports and the log lines.
- [x] 1.4 `tests/input_hotplug_sdl` (design D6), added in `src/input/CMakeLists.txt` for POSIX.

## 2. cat

- [x] 2.1 This change's `input` delta.
- [x] 2.2 `README.md`: the known issue "A controller connected after launch is ignored" and the macOS row's "Connect the controller before starting the game" removed.
- [x] 2.3 `TASKS.md` at merge: the "Gamepad hot-plug doesn't work on macOS" entry and the Input bullet's hot-plug line point here; G1-G3 on macOS recorded from the user's walk.

## 3. Gates

- [x] 3.1 Mac toolkit build; `tests/posix_ctest.sh` 0 FAIL, `input_hotplug_sdl` passing (toolkit 9e74027b: 73 pass, 1 skip `mmx_integer`, 0 FAIL; the hot-plug test 77 checks, 0 failed, five runs in a row). After the review fixes, toolkit 2b4f7565: 73 pass, 1 skip, 0 FAIL; the hot-plug test 84 checks with the boot case, 0 failed, five runs in a row).
- [x] 3.2 cat built against the toolkit worktree; `blinx2 golden` on Metal, verdicts and flips/s against the last run. 2026-10-16, toolkit 9e74027b: attract pass 44.6, stage1 pass 34.4, story pass 54.0 flips/s (10-16 voicehold base: 46.2 / 33.6; 10-12 kbm: 34.5 / 54.0), so no speed change. Also attract with `RECOMP_HOST_PAD=1` (the window-thread pad sync live, no pad attached): pass, 46.5 flips/s. Runs in `runs/hotplug/golden-metal{,-hostpad}`. After the review fixes (toolkit 2b4f7565, cat 98b518c): attract pass 43.9, stage1 pass 33.7, story pass 53.3; attract with `RECOMP_HOST_PAD=1` pass 46.4 flips/s; runs in `runs/hotplug/golden-metal{,-hostpad}-2`.
- [x] 3.3 Windows path: `git diff` shows no `_WIN32` or Windows-built file changed (design D5).

## 4. Hands-on (user, macOS)

- [x] 4.1 Checklist G1-G3 of `input-real-devices` with a real pad: unplug and replug in a menu and in play; the `[INPUT] host pad removed/added port=0` and `ports=0x0`/`ports=0x1` lines at the right moments; a pad connected after launch drives the title; a pad connected before launch shows `[INPUT] host pad added port=0` and `ports=0x1` from the first `ports` line, with no later insert.
  The user walked it on 2026-10-17 (8BitDo Ultimate 2 Wireless, `wt/hotplug` build, toolkit 2b4f7565). G2: `host pad added port=0` about 38 s after launch, and the pad drove the title. G3: a replug on the title (`removed`/`added port=0`) and one in play, both back on port 0. G1: `host pad added port=0` before the first `ports=0x1` line, no later insert. Logs `runs/blx15/mac.log`, `mac-g1.log`. The first try on an empty hdd crashed while building the Z: cache (247th open failed; BLX-193), unrelated to this change; `ulimit -n 4096` got past it.
