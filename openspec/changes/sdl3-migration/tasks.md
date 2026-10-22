Conventions:
- **Branches.** Every branch is `feat/sdl3-migration`, in its own worktree under `wt/sdl3/`:
  - **toolkit**: off `posix-host/portability` in `wt/sdl3/xboxrecomp`;
  - **CLI**: off `main` in `wt/sdl3/xboxrecomp-cli`;
  - **cat**: off `main` in `wt/sdl3/cat`;
  - **b3**: off `main` in `wt/sdl3/b3`.

  ssx3 and jsrf are edited by their owner sessions, routed by the orchestrator.
- **Order.** One implementing agent takes the slices in the order of the table.
- **Deck runs** belong to the orchestrator: a slot in `notes/benches.md`, through `blinx2 bench` (which takes `flock` itself).
- **No sound on the Mac** without asking the user. 10.3 is the one run. Headless runs set `SDL_AUDIO_DRIVER=dummy`; the alias `SDL_AUDIODRIVER` keeps working.
- **Evidence:**
  - `bench-logs/<stamp>`, named in the task when it is ticked;
  - raw dumps and shots in `xbox-recomp/runs/sdl3/`, never inside a worktree;
  - nothing derived from the game is committed.
- **Mac builds** use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools` and `-DXBOXRECOMP_ENHANCE=ON`.
- **No CPU goldens.** The CPU backend is out of the routine gates; the renderer block is proven through Metal's readback mode.
- **Tracker:** The tracker item. Claim it before slice 1, `pt comment` at the end of each slice, `pt review` at 10.5.

Slice map (hours from design, Migration Plan):

| Slice | Where | Hours | Depends on |
|---|---|---|---|
| 1 Build system, env shim, CMake duplicate | toolkit | 2 | - |
| 2 Window, events, Metal layer | toolkit | 3 | 1 |
| 3 Renderer present and shots | toolkit | 3 | 2 |
| 4 Keyboard and mouse | toolkit | 4 | 2 |
| 5 Gamepad and hot-plug port | toolkit | 5 | 1 |
| 6 Audio stream | toolkit | 3 | 1 |
| 7 Upstream-bound files and toolkit docs | toolkit | 2 | 1-6 |
| 8 Toolkit Mac gates | Mac | 6 | 1-7 |
| 9 CLI | CLI | 5 | - |
| 10 Deck, Linux native, sound | orchestrator, Linux host, Mac + user | 4 | 8 |
| 11 Toolkit merge, public push and tag | orchestrator | 1 | 10, review |
| 12 Games | cat, b3, owners | 4 | 9, 11 |
| 13 Follow-through | orchestrator / agent | 2 | 12 |

## 1. Build system, the env shim and the CMake duplicate (toolkit)

- [ ] 1.1 Record the SDL3 version on the Mac:
  - `brew list --versions sdl3` (3.4.16 at writing; `brew upgrade sdl3` to 3.4.18 is fine);
  - `pkg-config --modversion sdl3`.

  Verify: `find_package(SDL3 3.2 CONFIG)` resolves in a scratch CMake project.
- [ ] 1.2 Replace the six `find_package(SDL2 REQUIRED)` sites with `find_package(SDL3 3.2 CONFIG REQUIRED)` and `SDL3::SDL3`:
  - `src/{apu,d3d,input,video}/CMakeLists.txt`;
  - `tests/input_keyboard_sdl`;
  - `tests/input_hotplug_sdl`.

  In `src/video/CMakeLists.txt`, delete the second block (:39-41), which adds `fb_present_sdl.c` a second time. The ctests' `ENVIRONMENT` becomes `SDL_VIDEO_DRIVER=dummy;SDL_AUDIO_DRIVER=dummy`. `tests/posix_ctest.sh:31` exports both spellings of the audio driver.

  Verify: `cmake` configures on the Mac, and `git grep -n SDL2 -- '*CMakeLists.txt'` is empty.
- [ ] 1.3 Add `src/platform/sdl_env.h`, header-only, with `xbox_sdl_env_compat()` per D10:
  - it uses `SDL_getenv` and `SDL_setenv_unsafe`, never libc `getenv`;
  - its comment says why: scripts and users still spell the SDL2 names, and these are SDL's variables, not `recomp_env` rows.

  Verify: a new ctest `tests/sdl_env` checks that an old name is copied and that an SDL3 name already set wins.
- [ ] 1.4 Headers and checks:
  - `<SDL.h>` and `<SDL_metal.h>` become `<SDL3/SDL.h>` and `<SDL3/SDL_metal.h>`;
  - checks on SDL calls that returned `int` become bool tests;
  - `SDL_INIT_GAMECONTROLLER` becomes `SDL_INIT_GAMEPAD`.

  Verify: the build's remaining errors are only those slices 2-6 fix.

## 2. Window, events and the Metal layer (toolkit)

- [ ] 2.1 `fb_present_sdl.c` window creation per D2:
  - `SDL_CreateWindow(name, w, h, flags)`, with `HIGH_PIXEL_DENSITY`;
  - for `present.fullscreen`, `SDL_WINDOW_FULLSCREEN` plus `SDL_SetWindowFullscreenMode(win, NULL)`;
  - `SDL_RegisterEvents` fails with 0;
  - `xbox_sdl_env_compat()` before init.

  Verify: `RECOMP_WINDOW_QUIT_AFTER=5` opens a centred window and exits through the quit path; Hor+ widens it as before; fullscreen opens borderless at the desktop size.
- [ ] 2.2 The event loop:
  - `SDL_EVENT_QUIT`;
  - `EXPOSED`, `RESIZED` and `PIXEL_SIZE_CHANGED` redraw;
  - events go to the input handlers first;
  - `xbox_InputSdlMouseSync()` and `xbox_InputSdlPadSync()` still run once per loop (:679, :682);
  - the cached `filter` read (:544) stays (D16).

  Verify: a resize redraws the last frame, and the `[PRESENT]` stats line prints at exit.
- [ ] 2.3 `fb_present_metal.m/.h`:
  - `SDL_GetWindowSizeInPixels` replaces `SDL_Metal_GetDrawableSize`;
  - the shot path uses `SDL_CreateSurface` and `SDL_DestroySurface`;
  - the header paths change;
  - `SDL_Metal_CreateView`, `GetLayer` and `DestroyView` stay.

  Verify: run windowed `@attract` with `RECOMP_PB_BACKEND=metal` at render scales 1 and 2, with `RECOMP_TRACE=metal_prof`. It reports no readback, and a move to another-scale display logs one drawable change.
- [ ] 2.4 The fallback: with `SDL_VIDEO_DRIVER=dummy` and Metal, the run falls back to the renderer and readback. Verify: the `gpu-backend` "Fallback" scenario.

## 3. Renderer present and shots (toolkit)

- [ ] 3.1 The renderer block per D4:
  - `SDL_CreateRenderer(win, NULL)` and `SDL_SetRenderVSync`;
  - `SDL_GetRendererName` in the `window up` line;
  - `SDL_SetRenderLogicalPresentation(..., LETTERBOX)`;
  - `SDL_RenderTexture` with an `SDL_FRect` from `nv2a_present_rect`;
  - `SDL_GetCurrentRenderOutputSize`;
  - `SDL_PIXELFORMAT_XRGB8888`;
  - `SDL_SCALEMODE_NEAREST` at texture creation, switched to `LINEAR` exactly where the filter paths did, with a comment that SDL3 defaults to linear;
  - `SDL_HINT_RENDER_SCALE_QUALITY` removed.

  Verify, in readback mode at `RECOMP_WINDOW_SCALE=2`:
  - a shot's 2x2 blocks are single dump pixels, and with `present.filter=linear` they are not;
  - `linear`, `integer`, overscan and Hor+ give the same rectangle as a shot taken before the change, kept in `runs/sdl3/`.
- [ ] 3.2 `shot_save` per D5. Verify: the Metal "Present parity" scenario, for the stock window and one resized window.
- [ ] 3.3 `RECOMP_PRESENT_VSYNC=0` still presents without waiting. Verify: with `RECOMP_PRESENT_STATS=1`, flips/s are above the display rate in readback mode.

## 4. Keyboard and mouse (toolkit)

- [ ] 4.1 `keyboard_sdl.c/.h` per D9:
  - `SDL_EVENT_KEY_DOWN/UP`, `ev->key.key`, `SDL_KMOD_GUI`, `SDLK_A..Z`;
  - the flattened window events;
  - `xbox_InputSdlInit(SDL_Window *)` with `SDL_StopTextInput(win)` when `SDL_TextInputActive(win)`;
  - the keycode `_Static_assert`s kept;
  - `[input.bindings]` unchanged.

  Verify: with `RECOMP_KEYBOARD=1 RECOMP_TRACE=key`, Return at the title gives START; Cmd-Tab releases a held key.
- [ ] 4.2 `mouse_sdl.c/.h` per D9:
  - `SDL_EVENT_MOUSE_*` event types;
  - `SDL_TOUCH_MOUSEID` still skipped;
  - `wheel.direction` flips;
  - a per-axis float remainder so `mouse.c` gets whole counts;
  - `xbox_InputSdlMouseSync` calls `SDL_SetWindowRelativeMouseMode` on the presenter's window.

  Verify, by hand on the Mac: capture and release, the release key, the wheel, and focus loss dropping capture.
- [ ] 4.3 `tests/input_keyboard_sdl`:
  - builds events with the SDL3 fields;
  - creates a hidden dummy window for `SDL_GetWindowRelativeMouseMode(win)` and `SDL_TextInputActive(win)`;
  - keeps every case and CHECK message;
  - adds sub-pixel motion cases (two 0.5 moves make one count).

  Verify: `ctest -R input_keyboard` is green.

## 5. Gamepad and the hot-plug port (toolkit)

- [ ] 5.1 `xinput_device.c`, POSIX half, per D8's table:
  - `SDL_Gamepad` and `SDL_GUID` in `struct sdl_slot`;
  - `device_watch` returns `bool` on the SDL3 device events and still only raises `g_rescan`;
  - `rescan()` uses `SDL_GetGamepads`, `SDL_GetGamepadGUIDForID` and `SDL_OpenGamepad`, frees the id array, and ignores ids already in the table;
  - the poll, rumble and name calls are renamed;
  - the `_Static_assert`s point at the `SDL_GAMEPAD_*` constants.

  Unchanged: the slot lock order, the GUID stickiness, the 250 ms boot wait, the once-a-second probe and the log lines. The pumping-thread comment says why the rule stays. The `_WIN32` half is untouched.

  Verify by hand on the Mac with `RECOMP_HOST_PAD=1`:
  - a pad attached before launch;
  - one connected at the title;
  - unplug and replug in stage 1-1 keeps port 0.
- [ ] 5.2 Port `tests/input_hotplug_sdl` to `SDL_AttachVirtualJoystick` (`SDL_VirtualJoystickDesc` with `SDL_JOYSTICK_TYPE_GAMEPAD`, 6 axes, 15 buttons, and per-model vendor and product ids), `SDL_DetachVirtualJoystick`, `SDL_SetJoystickVirtualButton` and `SDL_AddGamepadMapping`.
  - The 2.24 skip goes.
  - The `SDL_JOYSTICK_HIDAPI/IOKIT/MFI=0` environment stays.
  - Every scenario keeps its numbers.

  Verify: `ctest -R input_hotplug` is green, and fails with the event watch removed (one deliberate run).
- [ ] 5.3 `input_map.h/.c`: the comments say SDL3 and give the positional names; the README column header says "SDL3". `src/input/README.md`'s table and hot-plug paragraph (:295-307) follow. Verify: `ctest -R input_map` is green and fails while the README still says "SDL2".

## 6. Audio stream (toolkit)

- [ ] 6.1 `git mv src/apu/apu_sdl2.c src/apu/apu_sdl.c`. The CMake and comments follow; the `[SDL2]` prefixes and `[APU] Using SDL2 audio backend` become SDL3. `XA2_BACKEND_NAME` (`apu_xaudio2.h:15`) becomes `"SDL3"`, and the SDL2 comments in `apu_xaudio2.h` (:11, :106), `apu_xaudio2.c` (:17-18, :280) and `apu_core.c:794` say SDL3. Verify: `git grep -n -i sdl2 src/apu` is empty, and `[APU]`'s backend line (`apu_core.c:576`) prints SDL3.
- [ ] 6.0 Rebase onto the tracker item DSP merge. Re-check D6's assumptions there: the `{S16, 2, 48000}` output contract, the 256-frame EP period and the vclock. Note any change in the task note and follow DSP's values.
- [ ] 6.2 `apu_sdl.c` per D6:
  - `xbox_sdl_env_compat()` first;
  - the sample-frames hint;
  - `SDL_OpenAudioDeviceStream` with `{S16, 2, 48000}`;
  - the granted frames logged and used;
  - `SDL_ResumeAudioDevice`, `SDL_PutAudioStreamData`, `SDL_GetAudioStreamQueued`;
  - the shutdown order;
  - headless sets `SDL_AUDIO_DRIVER=dummy` without overwriting;
  - **on the dummy driver, `apu_vclock` stays the queue** and the stream stays paused and empty.

  Verify:
  - headless `@attract` logs `[SDL3] audio initialized: driver dummy`, and the WAV tap passes `audio_check.py`;
  - `RECOMP_AUDIO_BUF_SAMPLES=256` and `=1024` change the logged value.
- [ ] 6.3 The D7 include check: no TU includes both `apu_shim.h` and an SDL header. Verify: `ctest -R 'apu|audio'` is green (these do not link SDL), and the grep is in the task note.

## 7. Upstream-bound files and toolkit docs (toolkit)

- [ ] 7.1 `src/d3d/d3d8_gl.c`, nothing more than:
  - the header;
  - `SDL_CreateWindow(title, w, h, SDL_WINDOW_OPENGL)`;
  - `SDL_EVENT_QUIT`;
  - `SDL_GL_DestroyContext`;
  - bool checks;
  - `xbox_sdl_env_compat()`.

  Verify: it builds; `git diff origin/main -- src/d3d/d3d8_gl.c` stays small.
- [ ] 7.2 The setup scripts:
  - `tools/linux/install_deps.sh`: `libsdl3-dev`, `sdl3`, `SDL3-devel`, with the comment on sdl2-compat dropped;
  - `tools/macos/setup.sh:58`: `BREW_FORMULAE="sdl3 libepoxy"`.

  Verify: `bash -n` on both.
- [ ] 7.3 The toolkit docs listed in design Context:
  - `README.md`;
  - `docs/GETTING_STARTED.md`;
  - `docs/runtime/config.md`, with the SDL3 driver names and "the old names are accepted";
  - `docs/pipeline/06-debugging.md`;
  - a `CHANGELOG-blinx2.md` entry "POSIX hosts link SDL3 (was SDL2 / sdl2-compat)";
  - `src/input/README.md` (:13, :134, :151, :302) and the code comments listed in design Context (`win32_compat.c/.h`, `input_map.c/.h`, `keyboard_sdl.c`, `xinput_device.c`, `input_backend.h:3`, `xinput_xbox.h:87`, the hot-plug test, the CMake comments);
  - `templates/new-game/CMakeLists.txt:117`;
  - the README's native Linux note: the SDL3 3.2 floor, the distros that package it, and the source build of the pinned tarball for Ubuntu 24.04 and Debian 12 (D1).

  Verify: `git grep -n -i sdl2 -- README.md docs tools templates src tests` lists only history entries (`CHANGELOG-blinx2.md`, `CONTRIBUTORS.md`) and the alias lines (`sdl_env.h`, `docs/runtime/config.md`, `posix_ctest.sh`).

## 8. Toolkit Mac gates (design Gates 1-6)

- [ ] 8.1 Gates 1 and 2: the Mac build and `tests/posix_ctest.sh <build-dir>`, 0 FAIL, including `sdl_env`, `input_keyboard_sdl` and `input_hotplug_sdl`. Verify: the summary in the task note.
- [ ] 8.2 Gate 3: `blinx2 golden run --backend metal`, headless, from `wt/sdl3/cat` with `XBOXRECOMP_DIR` pointing at the toolkit worktree. Verify: PASS for every scenario, stamps named.
- [ ] 8.3 Gate 4: slices 2-5's windowed checks, no sound. Verify: shots in `runs/sdl3/`, results in the task note.
- [ ] 8.4 Gate 5: `b3/scripts/race_gate.py` on Metal, headless, against the toolkit worktree. Verify: pass, log named.
- [ ] 8.5 Gate 6: flips/s and `metal_prof` before and after, in layer and readback modes. Verify: numbers in the task note; a 25% drop or 1.5x frame-ms rise is flagged.
- [ ] 8.6 Hand the toolkit head to the orchestrator for slice 10 and the review. `pt comment ITEM` with the sha.

## 9. CLI

- [ ] 9.1 `manifest.py` (:69-72) and `docs/manifest.md`: `[toolchain] sdl3`, a string defaulting to `""`. Verify: `tests/test_manifest.py` covers the key and the default.
- [ ] 9.2 `pins.py pins_refresh` (:135-193): with the key set, record the GitHub release tarball `SDL3-<ver>.tar.gz` (`version`, `url`, `sha256`, `size`) under `sdl3`; without it, write no entry. `fetch.load_pins` accepts both. Verify: a fake-release test, and a game without the key writes the same two entries as today.
- [ ] 9.3 `doctor.py` on macOS:
  - an `sdl3:` line with the installed version, and the pin when there is one;
  - a `warning:` when the installed major.minor is older than the pin's;
  - never a blocker (D1).

  Verify: tests for older (warning), equal, newer and no pin, with a fake `pkg-config`.
- [ ] 9.4 `golden_run.run_env()` (:240) and every other driver export set both `SDL_AUDIODRIVER` and `SDL_AUDIO_DRIVER` (D10), with a comment saying until when. Verify: `test_golden_run.py:104` asserts both.
- [ ] 9.5 Fixtures:
  - `tests/testdata/game/game.toml:162-163`: brew `["sdl3", "openssl", "libepoxy"]`, no SDL companion;
  - `test_manifest.py:261`;
  - `test_package_lib.py:307-336`: keep a companion case with a neutral library, and list `libSDL3.0.dylib` as a direct dependency;
  - `test_wizard.py:382-395`;
  - `package/lib.py:856`: the docstring loses its sdl2-compat example;
  - the wizard fixtures: `runner_test.go:132-141`, `testdata/doctor-blocked.json:36`, `screens_test.go:404`, `gamecfg/testdata/blinx2.json:70`.

  Verify: `uv run pytest tests`, ruff, and `wizard/check.sh`.
- [ ] 9.6 Docs: `docs/porting.md:143-156` (`brew install sdl3 …`, `SDL_AUDIO_DRIVER`) and `docs/wizard.md:331`; `credits.py` unchanged. Release notes, then a release tag. Verify: `git grep -n -i sdl2` in the CLI lists only the transitional both-names lines.

## 10. Deck, Linux native and the sound run (design Gates 7-9)

- [ ] 10.1 Gate 7, by the orchestrator:
  - `blinx2 bench golden` on the integration build;
  - frame hashes and pace identical to the previous stamp;
  - `strings cat_recomp.exe | grep -c SDL_` is 0;
  - b3's Proton smoke.

  Verify: both stamps in the task note.
- [ ] 10.2 Gate 8, on the host Open Question 1 settled (option (d), 2026-10-21): built on the Mac in the sniper image (`linux-native-vulkan` tasks 1.5-1.7), run natively on the Deck (later the re-provisioned PC) as `linux-native-vulkan` task 1.8. The toolkit merge waits for it. Time-boxed to 2 h: a failure that is not SDL's (GL, epoxy, a distro quirk) becomes a TASKS follow-up. Deck runs take its flock through the orchestrator's slot:
  - a native cat build (CPU path) and the POSIX ctests;
  - a 30 s windowed `@attract` (`RECOMP_WINDOW_QUIT_AFTER=30`) logging `SDL <driver> renderer` and `[SDL3] audio initialized: driver <pipewire|pulseaudio>`;
  - a `scripts/vpad.py` pad present at launch, and one created after launch (`host pad added`).

  Verify: logs in `bench-logs/`, and a screenshot in `runs/sdl3/`.
- [ ] 10.3 Gate 9, the sound run. **Stop and ask the user right before it; never play unasked.**
  - One 60 s run: `RECOMP_HEADLESS=1 SDL_AUDIO_DRIVER=coreaudio RECOMP_AC97_READY=1 RECOMP_INPUT_SCRIPT=@attract`, with the WAV tap.
  - The user confirms the sound is clean, and `audio_check.py --log` passes.
  - The same run ticks `fps-pacing` 8.10 and gives the tracker item its rate ratio as a comment.

  Verify: the report and the user's word.
- [ ] 10.4 The review of the toolkit and CLI branches (orchestrator). Fixes go back to the branch's agent.
- [ ] 10.5 `pt review ITEM` with the toolkit and CLI tips and the gate evidence.

## 11. Toolkit merge, public push and tag (orchestrator)

- [ ] 11.1 Squash-merge the toolkit onto `posix-host/portability`, and the CLI onto `main` with its tag. The CLI squash sets `--author` and `GIT_COMMITTER_NAME/EMAIL` to `carlos <4037632+apexJCL@users.noreply.github.com>`. Keep the branches.
- [ ] 11.2 Wait for the user's go on the push round (Open Question 2). Then, in order (D11: the toolkit tag precedes the game pins because games pin the public tag):
  - the CLI: `scripts/audit-public.sh` over `origin/main..main`, `git log --format='%ae %ce' origin/main..main` shows only the noreply address, fast-forward push and the tag;
  - `blinx2/portability` with a new `blinx2-v0.x` tag, through the scrub-and-mailmap procedure and its audit.

  Verify: both tags resolve publicly.

## 12. Games

- [ ] 12.1 cat `game.toml`:
  - `[package] brew = ["sdl3", "openssl", "libepoxy"]` (:186);
  - the companion (:187) removed;
  - `[toolchain] sdl3 = "<1.1's major.minor.patch>"`;
  - `[cli]` and `[toolkit]` at the new tags;
  - `blinx2 pins refresh`.

  Verify: `uv run pytest scripts`, and `blinx2 doctor` prints the `sdl3:` line.
- [ ] 12.2 cat scripts and docs move to the SDL3 names, per the design's Games table:
  - `scripts/shots/run.sh`;
  - `scripts/soak.py`;
  - `scripts/test_launchers.py`;
  - `scripts/xemu_ref.py`;
  - `docs/env.md`: the `SDL_AUDIO_DRIVER` and `SDL_VIDEO_DRIVER` rows say "the SDL2 name is accepted", and `apu_sdl.c` is named;
  - `docs/packaging.md:116`;
  - `README.md`: tested with `sdl3 <ver>`; the macOS row says SDL3; `brew install sdl3 openssl libepoxy`;
  - `NOTICE`, if it lacks the SDL3 line;
  - the comments in `src/pad_slots.*`, `pad_input.c` and `main.c`;
  - the live text in `openspec/config.yaml`, `OPEN_QUESTIONS.md` and `RESUME.md`.

  Open and archived changes' task boilerplate is not edited; the alias keeps it true.

  Verify:
  - `uv run pytest scripts` and the ruff checks;
  - `blinx2 package macos`, then `otool -L` shows `@rpath/libSDL3.0.dylib` and no `libSDL2`;
  - `codesign --verify --deep --strict`;
  - the DMG smoke with a scratch `BLINX2_DATA_DIR` and `RECOMP_WINDOW_QUIT_AFTER=10`.
- [ ] 12.3 b3:
  - `game.toml:108` brew `["sdl3", "openssl", "libepoxy"]`, `[toolchain] sdl3`, and the pins;
  - `README.md:36`;
  - `docs/running.md:218,223`;
  - `packaging/launch.env.default.macos:8`;
  - `packaging/macos/README.part:25`;
  - `scripts/race_gate.py:540,562` (both names until its pin is SDL3);
  - `openspec/config.yaml:11`.

  Verify: `xbr doctor` prints the `sdl3:` line, and b3's macOS package passes the same `otool` check.
- [ ] 12.4 ssx3 (`game.toml:85-86`, which drops sdl2 and the companion) and jsrf (`:86`), each through its owner session: the same manifest move and pins. spartan only moves its toolkit pin. All three reword the template's `(SDL2,` comment at `CMakeLists.txt:123`. Verify: each owner reports its doctor line and package check.
- [ ] 12.5 The public rounds for the games: cat through `scripts/export-public.sh`, b3 through its export, after 11.2's tags, with the usual audits. Verify: each public `game.toml` pins tags that exist.

## 13. Follow-through

- [ ] 13.1 After the merges:
  - `blinx2 bench integrate --golden` on the Deck;
  - copy notes to `notes/sdl3/` and runs to `runs/sdl3/` with `cp -c`;
  - remove the worktrees;
  - update TASKS: this change done, the tracker item's SDL3 follow-up closed, `fps-pacing` 8.10 noted, and the line "SDL3 migration the tracker item stays post-v1" (TASKS.md:922) replaced by the 2026-10-21 order (DSP, then SDL3, then the release).

  Then `pt accept ITEM`.
- [ ] 13.2 One Mac CPU check (D14): `blinx2 golden run --backend cpu`, with the verdicts and flips/s in TASKS. A regression is a follow-up.
- [ ] 13.3 Hand `ipados-port` its facts (D15): the merge shas, the pin version and entry shape, and that hot-plug is ported.
- [ ] 13.4 In `enhance-menu-preview`, move the SDL2 wording to SDL3 (D16): spec :157 to "The SDL backend SHALL report the host-only buttons"; `tasks.md:58`; design :251, :911 (`SDL_SetRelativeMouseMode` → `SDL_SetWindowRelativeMouseMode`), :1032 (`SDL_RenderCopy` → `SDL_RenderTexture`), :1225-1236, :1416 (F-3) and :1640 (Open Question 1); and `assessment.md`. Skip this if 3A's agent already did it. Verify: `openspec validate enhance-menu-preview --strict`.
- [ ] 13.5 Upstream (D13): add "SDL3 on POSIX hosts" with its file list to the tracker item as a candidate. No PR now.
- [ ] 13.6 Archive with `openspec archive sdl3-migration` after `audio` (this change's `audio` delta modifies a requirement that change adds). Verify: `openspec validate --specs`.

## Resume note (2026-10-21, refreshed by the tracker item)

Nothing is implemented. Tracker:
- **The tracker item** is the implementation item; it absorbs the tracker item's SDL3 follow-up.
- The tracker item..292 (overlay phase 3) wait on it.
- User order (2026-10-21): DSP, then SDL3, then the release.

Start from these tips, or later ones:
- toolkit `posix-host/portability` 4559bae9;
- CLI `main` 85e24c9;
- cat `main` 77a01ca, plus this change once merged;
- b3 47f7fdd.

First steps:
1. The orchestrator dispatches the tracker item. Then `pt claim ITEM` and `pt context ITEM`.
2. Ask the user the two Open Questions in design.md if they are still open: the Linux-native gate host, and the public tag round.
3. Create the toolkit worktree (`git worktree add ../wt/sdl3/xboxrecomp -b feat/sdl3-migration posix-host/portability` from `xboxrecomp/`), then do 1.1.
4. Slices 1-8. The CLI (slice 9) can go in parallel or at any time.
5. 10.3 is the one stop-and-ask point on the Mac. 10.1 and 10.2 are orchestrator slots.

User decisions that still hold:
- rename to `apu_sdl.c`;
- `doctor` warns;
- hot-plug is in scope (now a port, D8);
- the CLI owns acquisition;
- B3 is included;
- the Linux-native distrobox gate is kept;
- the Windows build links no SDL;
- SDL3 goes before the overlay's phase 3;
- its own upstream PR when upstream work resumes after the releases.

The earlier versions (2026-10-06, 2026-10-11) are in this change's git history.
