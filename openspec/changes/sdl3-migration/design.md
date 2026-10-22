## Context

Bases, re-read 2026-10-21:
- toolkit `posix-host/portability` 4559bae9;
- CLI `main` 85e24c9 (v0.9.0-8);
- cat `main` 77a01ca;
- b3 47f7fdd, ssx3 429de64, jsrf 21bc4d7, spartan f851ad0, kuf bffd4f1;
- upstream `origin/main` eb0aa1d5 (v0.14.0, already an ancestor of the toolkit tip).

The SDL facts come from the spike (`spike.md` in this change, sources fetched 2026-10-06) or from reading the files named here.

**How the counts below are measured:** "SDL lines" are the lines containing `SDL_` at 4559bae9 (`git grep -c SDL_ 4559bae9 -- <file>`), so they include our own `XBOX_SDL_*` names where a file uses them; for `input_map` the column gives both. They are not comparable with the 2026-10-11 table, which counted differently.

### Toolkit surface at 4559bae9

The tip is entirely SDL2. Nothing in the tree uses SDL3, upstream included. Since f8696da, 198 commits have touched 52 files that mention SDL (+9576/−893), mostly new input code and tests.

| File | Lines / SDL lines | What it does with SDL | Since f8696da | SDL3 work |
|---|---|---|---|---|
| `src/video/fb_present_sdl.c` | 877 / 84 | The one window and event loop, on the process main thread; the guest runs on a pthread. Frames come from the ack thread through three slots. An `SDL_Renderer` with a streaming texture presents for the CPU path and Metal's readback fallback. Also: `SDL_RegisterEvents` wake-ups, shots, `SDL_QUIT`, and per loop `xbox_InputSdlPadSync()` (:682) and `xbox_InputSdlMouseSync()` (:679) | +49 lines (Hor+ `win_w`, overscan, `present.surface`) | window creation, event names, the renderer block, shots, bool returns |
| `src/video/fb_present_metal.m/.h` | 444+21 / 17+2 | `SDL_WINDOW_METAL`, `SDL_Metal_CreateView/GetLayer/DestroyView`, `SDL_Metal_GetDrawableSize`, and shots through `SDL_CreateRGBSurfaceWithFormat` + `SDL_SaveBMP` (:307-328) | small | one function replaced, one surface API, header paths |
| `src/apu/apu_sdl2.c` | 266 / 25 | Push API: `SDL_OpenAudioDevice` with `RECOMP_AUDIO_BUF_SAMPLES`, `SDL_QueueAudio`, `SDL_GetQueuedAudioSize` for the pacer's depth. `SDL_setenv("SDL_AUDIODRIVER","dummy",0)` when headless. On the dummy driver the queue is the virtual device `apu_vclock` and SDL's device stays paused and empty | +87 lines (vclock) | stream API, the buffer hint, the file name |
| `src/apu/apu_shim.h` (upstream, from xemu) | 516 / 21 | Stubs **named like SDL3's audio API** (`SDL_AudioStream`, `SDL_OpenAudioDeviceStream`, `SDL_PutAudioStreamData`, ...) for xemu's monitor code. Never linked against SDL | +82 | none; must never share a TU with `<SDL3/SDL.h>` (D7) |
| `src/apu/apu_xaudio2.h/.c`, `apu_core.c` | — | No SDL call, but SDL2 by name: `#define XA2_BACKEND_NAME "SDL2"` (`apu_xaudio2.h:15`), printed by `apu_core.c:576` and :582; comments at `apu_xaudio2.h` :11, :106, `apu_xaudio2.c` :17-18, :280 and `apu_core.c:794` | unchanged | `XA2_BACKEND_NAME` becomes `"SDL3"`; comments |
| `src/input/xinput_device.c` (upstream's file, rewritten in the fork) | 357 / 47 | The POSIX half. The tracker item hot-plug: `struct sdl_slot {pad,id,guid,had}` under `g_slot_lock`; `SDL_AddEventWatch(device_watch)` only raises `g_rescan`; `rescan()` runs on the pumping thread (`xbox_InputSdlPadSync`), or headless on the poll thread, on the flag or once a second; GUID-sticky ports; a 250 ms boot wait on a condvar. Also poll and rumble. `_Static_assert`s tie `XBOX_SDL_*` to `SDL_CONTROLLER_*` (:143-151) | +262/−; 171→357 lines | gamepad renames; `SDL_GetGamepads` in the rescan (D8) |
| `src/input/input_map.h/.c` | 145+215 / no SDL API (21+25 with `XBOX_SDL_*`) | `XBOX_SDL_BUTTON_*`/`XBOX_SDL_AXIS_*` as plain enums (no SDL header); `XBOX_HOST_SDL_GAMEPAD`; `xbox_InputMapSdl`; the README table's "SDL2" column | unchanged | names and comments only; SDL3 keeps the values |
| `src/input/keyboard_sdl.c/.h` | 157+30 / 8+5 | `SDL_KEYDOWN/UP`, focus, hide and minimise events; `SDL_StopTextInput` at init (:114); key names | +113 (`[input.bindings]`, one key table) | field and constant renames; per-window text input |
| `src/input/mouse_sdl.c/.h` (new) | 95+26 / 24+4 | `xbox_InputSdlMouseEvent`: `SDL_MOUSEMOTION/BUTTON*/MOUSEWHEEL`, skips `SDL_TOUCH_MOUSEID`, honours `SDL_MOUSEWHEEL_FLIPPED`, handles focus, hide, minimise, close and `SDL_QUIT`. `xbox_InputSdlMouseSync` mirrors `mouse.c`'s capture state into `SDL_SetRelativeMouseMode` (:92) on the window thread | new (ced2743c, 2ef5e29a) | event types and fields; float deltas; `SDL_SetWindowRelativeMouseMode` (D9) |
| `src/input/mouse.c/.h`, `input_names.c`, `input_backend.h`, `xinput_xbox.h` | — | Host-neutral capture state machine and key and button names; SDL only in comments (`input_backend.h:3` says SDL2; `xinput_xbox.h:87` "SDL GameController slot N" names the SDL2 API) | new or unchanged | comments only |
| `src/d3d/d3d8_gl.c` (upstream) | 1073 / 24 | SDL window + GL 3.3 context for the HLE D3D8 OpenGL backend (:979-1011); `SDL_GL_SwapWindow` and `SDL_PollEvent` in Present (:551-556) | 5 lines | create-window call, an event name, `SDL_GL_DestroyContext`, header, bool checks |
| `tests/input_keyboard_sdl` | 350 / 76 | Synthetic key **and mouse** events against `keyboard_sdl.c` and `mouse_sdl.c`; `SDL_GetRelativeMouseMode` (:251, :306); `SDL_IsTextInputActive` (:343) | +196 | event fields; window-scoped relative mode and text input |
| `tests/input_hotplug_sdl` | 407 / 47 | `SDL_JoystickAttachVirtualEx`, `DetachVirtual`, `SetVirtualButton`, `SDL_GameControllerAddMapping` (:64-130); skips with exit 77 below SDL 2.24. Env `SDL_JOYSTICK_HIDAPI=0;SDL_JOYSTICK_IOKIT=0;SDL_JOYSTICK_MFI=0` plus the dummy drivers | new | SDL3 virtual-joystick API; the skip becomes the SDL3 floor |
| `tests/input_bindings`, `tests/input_map`, `tests/apu_vclock`, `tests/apu_monitor` | — | Link no SDL; comments only | new or unchanged | comments |
| `tests/posix_ctest.sh` | :31 | `export SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy}` | new | the SDL3 name; the old one stays accepted |
| CMake | 6 `find_package(SDL2 REQUIRED)` sites | `src/{apu,d3d,input}`, `src/video` **twice** (:15-17 and :39-41, with `fb_present_sdl.c` added at :16 and :40: a leftover from the v0.14.0 merge), the two SDL ctests. Tests are added at `src/input/CMakeLists.txt:62-67` under `if(NOT WIN32)` | +36 input, +11 video | `find_package(SDL3 3.2 CONFIG REQUIRED)` + `SDL3::SDL3`; the duplicate goes |

**Hints and variables in use:**
- `SDL_HINT_NO_SIGNAL_HANDLERS`, set in four places;
- `SDL_HINT_RENDER_SCALE_QUALITY` "nearest" (`fb_present_sdl.c:556`), which is gone in SDL3;
- `SDL_AUDIODRIVER` and `SDL_VIDEODRIVER` (`apu_sdl2.c`, the two test CMakeLists, `posix_ctest.sh`);
- `SDL_JOYSTICK_HIDAPI/IOKIT/MFI=0` (hot-plug test).

**Not used anywhere:**
- SDL threads and timers. `SDL_GetTicks` is used once; it returns `Uint64` in SDL3.
- `SDL_GAMECONTROLLERCONFIG` and `SDL_RENDER_DRIVER`.
- The properties API, touch, pen, `SDL_ShowCursor`, `SDL_SetWindowFullscreen`, `SDL_GameControllerGetType`, sensors and LEDs.

**Comment-only mentions:**
- `win32_compat.c` :1801, :1826 and `win32_compat.h:564`, `nv2a_pb_exec.c:6664`, `fb_present.c:138`, `window_title.h:4`;
- `input_map.c:204` (the README header string), `input_map.h` :6, :63, `keyboard_sdl.c` :16, :111, `xinput_device.c` :9, :69, :91, `tests/input_hotplug_sdl/test_main.c:16`, and the SDL2 comments in the apu, d3d, input and video CMake files;
- `apu_state.h:549`, `apu_vclock.h`;
- `recomp_env.h` descriptions ("SDL host"), which stay true;
- `templates/new-game/{src/main.c,CMakeLists.txt}` (`CMakeLists.txt:117`, which ssx3, jsrf and spartan copied to their own `CMakeLists.txt:123`).

**Toolkit docs naming SDL2:**
- `README.md` :103, :160, :488, :635, :732;
- `docs/GETTING_STARTED.md:26`;
- `docs/runtime/config.md` :319, :325, :358, :447;
- `docs/pipeline/06-debugging.md:376`;
- `src/input/README.md` (the SDL2 column; hot-plug at :295-307);
- `CONTRIBUTORS.md` :405, :849;
- `CHANGELOG-blinx2.md:49`;
- `tools/linux/install_deps.sh` (`libsdl2-dev`, `sdl2`, `SDL2-devel`; :56 "sdl2 resolves to sdl2-compat on current Arch");
- `tools/macos/setup.sh:58` (`BREW_FORMULAE="sdl2 libepoxy"`).

**What never links SDL:** the Windows build (`fb_present.c` GDI, `nv2a_pb_d3d11.c`, XInput, XAudio2). So Proton, the Deck, the steamos bundles and the Burnout 3 Proton runs use no SDL of ours. Proton's own `winebus` loads the Steam Linux Runtime's `libSDL2-2.0.so.0` (the host's only outside the runtime); that is not ours to change.

**What fb_present_sdl.c does not do yet:**
- overlay or menu, text, `SDL_ShowCursor`;
- live fullscreen: `SDL_WINDOW_FULLSCREEN_DESKTOP` is set only at creation (:566);
- live filter: `filter = eo->present_filter` is read once (:544).

These are `enhance-menu-preview` phase 3. `feat/enhmenu-p1` (b26689e1, not merged) adds no SDL call.

### CLI surface at 85e24c9

**Code:**
- `doctor.py`: `brew_formulae()` :62, `brew_missing()` :67, the report :168, the macOS blocker :301-312.
- `setup.py`: `host_blockers()` :64, with brew at :79-81.
- `pins.py`: `pins_refresh()` :135-193 writes `llvm_mingw` and `nsis`.
- `fetch.py`: `load_pins` :25, `download` :96.
- `manifest.py`:
  - `[toolchain]` :69-72 holds only `llvm_mingw` and `nsis`;
  - `[package]` :137-148;
  - companion validation :779-781.
- `golden_run.py`: `run_env()` :240 sets only `SDL_AUDIODRIVER`.
- `package/macos.py`: `companions()` :41; `wrap_macos` :176 calls `dylib_plan` :223.
- `package/incr.py:213`: `dylib_shas()` calls `dylib_plan` too.
- `package/lib.py:856`: a docstring that uses sdl2-compat as its example.
- `credits.py:54`: a version-free "SDL" credit, which stays.

Of these, `fetch.py`, `package/macos.py`'s `companions()`, `incr.py` and `credits.py` need no change: they are listed because the change relies on them working as they are.

**`config/setup-pins.json` schema:**

```
{_comment, llvm_mingw: {tag, assets: {name: {url, sha256, size}}}, nsis: {version, url, sha256, size}}
```

**Wizard (Go):** it installs Homebrew packages by parsing `doctor`'s `brew install …` blocker (`runner.Actions()` runner.go:239-262, `runBrew()` wizard.go:1093). The formula list is the game's `package.brew`, so the wizard needs no code change. Fixtures that name `sdl2`:
- `runner_test.go:132-141`;
- `testdata/doctor-blocked.json:36`;
- `screens_test.go:404`;
- `gamecfg/testdata/blinx2.json:70`.

**Tests and docs:**
- `tests/testdata/game/game.toml:162-163` (brew with sdl2 and sdl3, companion `libSDL3.dylib=brew:sdl3`);
- `test_manifest.py:261`;
- `test_package_lib.py:307-336`;
- `test_golden_run.py:104`;
- `test_wizard.py:382-395`;
- `docs/porting.md:143-156` (`brew install sdl2 …`, `SDL_AUDIODRIVER`);
- `docs/wizard.md:331`;
- `docs/manifest.md` :82-87, :184-185.

**Package targets:** windows, steamos (the Windows exe under GE-Proton) and macos. There is no Linux-native target.

### Games

| Game | macOS target | `[package] brew` | Companion | Toolkit pin | SDL names outside C |
|---|---|---|---|---|---|
| cat 77a01ca | yes | `sdl2, sdl3, openssl, libepoxy` (:186) | `libSDL3.dylib=brew:sdl3` (:187) | `blinx2-v0.5.1` | README :42, :161, :247, :351, :362, :494; `docs/env.md` :27-30, :46, :53-54, :84, :199, :216-217, :335; `docs/packaging.md:116`; `scripts/shots/run.sh:15`, `scripts/soak.py:21,208`, `scripts/test_launchers.py:95,126,140`, `scripts/xemu_ref.py:56-70`; comments `src/pad_slots.c:37`, `pad_slots.h:19`, `pad_input.c:10`, `main.c:1421`; `openspec/config.yaml:11`, `OPEN_QUESTIONS.md:85`, `WORKTREES.md:55`, `RESUME.md` :81, :88, :100, :136-138; the `SDL_AUDIODRIVER=dummy` boilerplate in about 13 open changes' tasks |
| b3 47f7fdd | yes | `sdl2, openssl, libepoxy` (:108) | none | `blinx2-v0.5.1` | `README.md:36`, `docs/running.md:218,223`, `packaging/launch.env.default.macos:8`, `packaging/macos/README.part:25`, `scripts/race_gate.py:540,562`, `openspec/config.yaml:11` |
| ssx3 429de64 (`ssx3/recomp`) | yes | `sdl2, sdl3, …` (:85) | yes (:86) | `blinx2-v0.5.0` | docs (owner session the SSX 3 session); the template's `(SDL2,` comment at `CMakeLists.txt:123` |
| jsrf 21bc4d7 (`jsrf/skates`) | yes | `sdl2, …` (:86) | none | `blinx2-v0.5.1` | docs; `CMakeLists.txt:123` comment |
| spartan f851ad0 (`spartan/tca`) | not yet | none | — | `blinx2-v0.5.1` | `CMakeLists.txt:123` comment |
| kuf bffd4f1 | Windows only | — | — | — | — |

No game calls SDL in C. Every game pins the **public** `blinx2/portability` tag, so SDL3 reaches a game only through a public push and a new tag. The bench builds `posix-host/portability` (`toolkit_branch`) for integration runs.

### Live specs naming SDL2 or the old variables

- `input`:50, "elsewhere (SDL2 GameController)": changed here.
- `input`:256 onwards, the hot-plug requirement (SDL device events, the virtual-controller ctest): changed here.
- `gpu-backend`:20, :27 and :53: changed here.
- `deployment`:107: changed here.
- `dev-tooling`:170, a scenario run with `SDL_AUDIODRIVER=dummy`: still true through the alias (D10), so it is left alone.
- `audio`: only in the open change `openspec/changes/audio`. This change's delta modifies the requirement that change adds, so this change archives after it.

### The overlay change

`enhance-menu-preview` (cat 54b7eb8, the tracker item; phases 3A-3D are the tracker item..292) puts an overlay quad in each presenter, the SDL renderer included (spec :94). Its design draws an `SDL_Texture` with blending (:250-252), toggles fullscreen on the main thread (:344, :898) and reads the filter live (:897). Its host-only buttons (guide, misc1, paddle1-4, touchpad) come from the SDL backend through a rename table already written for SDL3 (design :1232-1235). Its spec :157 says "The SDL2 backend SHALL report the host-only buttons". Its OQ1 (design :1640) is "SDL3 first", the user's order.

## Goals / Non-Goals

Goals:
- one SDL on every POSIX host, the one the host runs;
- stock behaviour unchanged pixel-for-pixel and pace-for-pace on every path;
- the Windows build untouched;
- hot-plug, keyboard and mouse behaving exactly as on SDL2;
- the iPad port able to build on it;
- the upstream-bound diff minimal;
- every game's manifest and docs correct.

Non-goals:
- sticky slots across launches, rebinding and input selection;
- touch and pen;
- main callbacks on desktop;
- the properties API for its own sake;
- a native Linux package;
- any D3D11, GDI or XAudio2 change;
- a renderer other than SDL's for the CPU path;
- the overlay itself;
- opening an upstream PR.

## Decisions

**D1. Version floor and pin.** The CMake floor is SDL3 **3.2** (`find_package(SDL3 3.2 CONFIG REQUIRED)`). `SDL_Metal_CreateView`, the gamepad API, the stream audio API, `SDL_SetWindowRelativeMouseMode` and the virtual-joystick descriptor are all in 3.2.0. Distro packages at or above it: Fedora 41+ (`SDL3-devel`), Ubuntu 25.04+ and Debian 13 (`libsdl3-dev`), Arch, and Homebrew. Ubuntu 24.04 LTS and Debian 12 have no SDL3 package; there the toolkit README gives the source build of the pinned tarball (`cmake -S SDL3-<ver> -B build && cmake --build build && cmake --install build`, then `SDL3_DIR` or `CMAKE_PREFIX_PATH`). Neither is a tested host.

One pinned source release lives in `config/setup-pins.json` under `sdl3`: `{version, url, sha256, size}`, the GitHub release tarball. `xbr pins refresh` writes it from `game.toml` `[toolchain] sdl3`, a new CLI manifest key whose default `""` means no pin and no check. It is the version each game's README names as tested, and the one `ipados-port` builds from (D15); at writing that is 3.4.18 (Homebrew stable; the Mac has 3.4.16).

Desktop builds take the package manager's SDL3 at or above the floor. `xbr doctor` prints the installed version (`pkg-config --modversion sdl3`, else the Homebrew prefix's `libSDL3.0.dylib`) next to the pin, and **warns, never fails** (user, 2026-10-06), when the installed major.minor is older than the pin's.

Why not vendor SDL3 for the desktop too: Steam's advice for Linux is to link the system SDL, Homebrew keeps the Mac current, and a vendored copy is one more thing to patch. iOS has no package manager, so there the pin is the build.

**D2. Window creation.** `SDL_CreateWindow(name, w, h, flags)`. SDL3 centres a new window by default, so the position constants go.

| Flag | SDL2 | SDL3 |
|---|---|---|
| HiDPI | `SDL_WINDOW_ALLOW_HIGHDPI` | `SDL_WINDOW_HIGH_PIXEL_DENSITY` |
| Layer path | `SDL_WINDOW_METAL` | unchanged |
| `present.fullscreen` | `SDL_WINDOW_FULLSCREEN_DESKTOP` | `SDL_WINDOW_FULLSCREEN`, then `SDL_SetWindowFullscreenMode(win, NULL)`, so it stays borderless at the desktop mode |
| Shown | `SDL_WINDOW_SHOWN` | gone; windows show by default |

`d3d8_gl.c` drops `SDL_WINDOWPOS_UNDEFINED` and `SDL_WINDOW_SHOWN` and keeps `SDL_WINDOW_OPENGL`.

Window size stays in points: `640 * scale`, widened by Hor+ through `nv2a_host_window_w`, which is unchanged. The layer's pixel size comes from `SDL_GetWindowSizeInPixels`.

**D3. Events.**
- `SDL_QUIT` becomes `SDL_EVENT_QUIT`.
- `SDL_EVENT_WINDOW_EXPOSED`, `SDL_EVENT_WINDOW_RESIZED` and `SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED` redraw the last frame. `RESIZED` was `SIZE_CHANGED`. A move to a display of another scale arrives only as `PIXEL_SIZE_CHANGED`, so the layer path listens to it too.
- `FOCUS_LOST`, `HIDDEN` and `MINIMIZED` release keys and mouse buttons and drop capture, as the SDL2 window events did.
- `SDL_RegisterEvents` returns 0 on failure (was `(Uint32)-1`). The headless fallback keeps its meaning.
- `SDL_WaitEventTimeout`, `SDL_PollEvent` and `SDL_PushEvent` keep their names.
- Unchanged: the custom frame and guest-done events, the wake coalescing, `RECOMP_WINDOW_QUIT_AFTER`, and the per-loop pad and mouse sync calls.
- Event filters and watches return `bool` (D8).

**D4. Renderer present (CPU path, Metal readback fallback).**
- **Create:** `SDL_CreateRenderer(win, NULL)`, then `SDL_SetRenderVSync(ren, vsync ? 1 : 0)`. The `[PRESENT] window up: SDL <driver> renderer` line reads `SDL_GetRendererName`.
- **Texture format:** `SDL_PIXELFORMAT_RGB888` becomes `SDL_PIXELFORMAT_XRGB8888`, the same bytes; RGB565 is unchanged.
- **Letterbox:** `SDL_SetRenderLogicalPresentation(ren, w, h, SDL_LOGICAL_PRESENTATION_LETTERBOX)` is SDL2's logical size. The integer filter, overscan and Hor+ keep their own rectangle (`nv2a_present_rect`) and draw with `SDL_RenderTexture(ren, tex, NULL, &SDL_FRect)`.
- **Output size:** `SDL_GetCurrentRenderOutputSize`.
- **Scale mode:** the texture's scale mode is set at creation to `SDL_SCALEMODE_NEAREST` for the stock path, because SDL3's default is linear and `SDL_HINT_RENDER_SCALE_QUALITY` no longer exists. `present.filter=linear` and the integer fallback set `SDL_SCALEMODE_LINEAR` exactly where `SDL_ScaleModeLinear` was set.

Proof that the stock picture did not change, without a CPU golden:
- the Metal "Present parity" scenario between layer and readback modes;
- the "Fallback" scenario under `SDL_VIDEO_DRIVER=dummy`;
- a `RECOMP_WINDOW_SHOT` at scale 2 whose 2x2 blocks are single dump pixels.

**D5. Shots.**
- **Renderer:** `SDL_RenderReadPixels(ren, NULL)` returns a surface; convert it with `SDL_ConvertSurface(s, SDL_PIXELFORMAT_BGR24)`, write it with `SDL_SaveBMP`, then destroy both surfaces.
- **Metal layer:** `SDL_CreateSurface(w, h, SDL_PIXELFORMAT_BGR24)` replaces `SDL_CreateRGBSurfaceWithFormat`.

The file names and bytes are the same as before.

**D6. Audio stream.** `apu_sdl2.c` becomes `apu_sdl.c` (a git rename; user, 2026-10-06). The steps:
1. Before open: `SDL_SetHint(SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES, "<RECOMP_AUDIO_BUF_SAMPLES>")`.
2. Open: `SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &(SDL_AudioSpec){SDL_AUDIO_S16, 2, 48000}, NULL, NULL)`. This binds a logical device that starts paused.
3. `SDL_GetAudioDeviceFormat(SDL_GetAudioStreamDevice(s), &have, &frames)` gives the granted buffer. It is logged, and it becomes `g_buf_samples` (capped as today), as `have.samples` did.
4. `SDL_ResumeAudioDevice`.
5. Submit with `SDL_PutAudioStreamData`.
6. Queue depth: `SDL_GetAudioStreamQueued`, the bytes the device thread has not pulled yet, the same meaning `SDL_GetQueuedAudioSize` had. The stream's input format stays ours (`S16`, 2, 48000), so the queued byte count is in our format and the pacer's arithmetic is unchanged. The device side is often `F32` in SDL3, so the stream converts S16→F32 internally, as SDL2 did behind `SDL_QueueAudio` when the device format differed; that is not ours to match.

**Rebase onto DSP first.** The tracker item (the DSP work) lands before this change. Slice 6 starts from its merge and re-checks what D6 assumes: the `{S16, 2, 48000}` output contract, the 256-frame EP period and the vclock. If DSP changes any of them, D6 follows DSP's values and the change is noted in the slice's task note.
7. Shutdown: `SDL_PauseAudioDevice`, `SDL_ClearAudioStream`, `SDL_DestroyAudioStream`.

**The virtual device stays.** When `SDL_GetCurrentAudioDriver()` is `"dummy"`, `queued_frames()` and the submit path use `apu_vclock` exactly as today, and the stream is left paused and empty. SDL3's dummy driver drains on a sleep loop just as SDL2's did, and the vclock's reason is SDL's dummy timing, not the API.

What does not change:
- the pacer (`mcpx_apu_pace_step`), the marks, `xa2_expect_drain`, the WAV tap and the `xa2_*` contract;
- the log lines, apart from the `[SDL3]` prefix and `[APU] Using SDL3 audio backend`.

Why a stream and not a stream callback: the pacer is a push model by design (`audio` spec "Output is paced by the device queue"). A callback would move pacing into SDL's thread, which is a different design.

Risk: SDL3 may not honour the sample-frames hint on some backend. The granted value is logged and used, so the marks adapt. Gate 9 (sound on the Mac) gives the tracker item its rate ratio on the stream API; a change there is recorded, not fixed here.

**D7. `apu_shim.h`.** Untouched. Its SDL3-named stubs serve xemu's monitor code in TUs that never include SDL. With real SDL3 headers in the tree, a TU that included both would redefine those names, so the rule becomes a check: `apu_sdl.c` includes `<SDL3/SDL.h>` and `apu_xaudio2.h` only, and slice 6's verify greps that no TU includes both `apu_shim.h` and an SDL header. If one ever must, the stubs get an `#ifndef SDL_h_` guard then. Not now, because the file is upstream's.

**D8. Gamepad and the hot-plug port.** The design is kept as it is and only its calls change:

| SDL2 (today) | SDL3 |
|---|---|
| `SDL_INIT_GAMECONTROLLER` | `SDL_INIT_GAMEPAD` |
| `SDL_GameController *` in `struct sdl_slot` | `SDL_Gamepad *` |
| `SDL_JoystickGUID` | `SDL_GUID` |
| `device_watch` on `SDL_JOYDEVICE*` / `SDL_CONTROLLERDEVICE*`, returning `int` | `SDL_EVENT_JOYSTICK_ADDED/REMOVED`, `SDL_EVENT_GAMEPAD_ADDED/REMOVED`, returning `bool` (`SDL_EventFilter`); still only raises `g_rescan` |
| `rescan()`: `SDL_NumJoysticks` + `SDL_IsGameController(i)` + `SDL_JoystickGetDeviceGUID(i)` + `SDL_GameControllerOpen(i)` | `SDL_GetGamepads(&n)` (instance ids, freed with `SDL_free`), `SDL_GetGamepadGUIDForID(id)`, `SDL_OpenGamepad(id)`; a closed slot is found by `SDL_GamepadConnected` |
| `SDL_GameControllerUpdate` (headless) | `SDL_UpdateGamepads` |
| `SDL_GameControllerGetButton/GetAxis` indexed 0..14, 0..5 | `SDL_GetGamepadButton/GetGamepadAxis`, the same indices |
| `SDL_GameControllerRumble` (int) | `SDL_RumbleGamepad` (bool) |
| `SDL_GameControllerName` | `SDL_GetGamepadName` |
| `_Static_assert`s on `SDL_CONTROLLER_BUTTON_A/START/LEFTSHOULDER/DPAD_RIGHT`, `SDL_CONTROLLER_AXIS_LEFTX/RIGHTY/TRIGGERRIGHT` | `SDL_GAMEPAD_BUTTON_SOUTH/START/LEFT_SHOULDER/DPAD_RIGHT`, `SDL_GAMEPAD_AXIS_LEFTX/RIGHTY/RIGHT_TRIGGER` |

What stays:
- the slot table and `g_slot_lock`, taken before SDL's joystick lock;
- the GUID stickiness and "ports never shift";
- the fifth pad waiting for a free port;
- the 250 ms boot wait and its condvar;
- `xbox_InputSdlPadSync()` from the window loop;
- the headless rescan on the poll thread;
- the once-a-second probe;
- the log lines.

**Enumeration stays on the pumping thread.** That rule exists because sdl2-compat's index list was unlocked. SDL3's `SDL_GetGamepads` is locked, so the rule is no longer strictly needed. But keeping it costs nothing and keeps the port one-for-one; the comment is reworded to say why it stays (one owner of open and close, and the boot wait already depends on it).

`input_map.h` keeps its enum values. The README column reads "SDL3" and the table test regenerates it.

Positional names: SDL3's SOUTH, EAST, WEST and NORTH are the Xbox A, B, X and Y positions, which is what the Duke mapping wants. There is no relabelling by `SDL_GetGamepadButtonLabel`.

The test port (`tests/input_hotplug_sdl`): `SDL_AttachVirtualJoystick(&SDL_VirtualJoystickDesc{.version = sizeof, .type = SDL_JOYSTICK_TYPE_GAMEPAD, .naxes = 6, .nbuttons = 15, .vendor_id/.product_id per model})` replaces `SDL_JoystickAttachVirtualEx`. Then `SDL_DetachVirtualJoystick`, `SDL_SetJoystickVirtualButton`, and `SDL_AddGamepadMapping` where a mapping is still needed. The GUID-model scenario needs three distinct GUIDs: the vendor and product ids in the descriptor give them. The skip below 2.24 becomes a compile-time floor. The hint variables stay as the env list: `SDL_JOYSTICK_HIDAPI`, `SDL_JOYSTICK_IOKIT` and `SDL_JOYSTICK_MFI` are the same names in SDL3. Every scenario in the live `input` spec keeps its numbers.

**D9. Keyboard and mouse.**

Keyboard:
- `ev->key.key` (was `keysym.sym`), `ev->key.mod & SDL_KMOD_GUI`, `ev->key.repeat`, `ev->key.down`;
- `SDLK_A..SDLK_Z` (values 'a'..'z', so the `_Static_assert`s keep holding), `SDLK_LGUI/RGUI`;
- `xbox_InputSdlInit` takes the window: `SDL_StopTextInput(win)`, guarded by `SDL_TextInputActive(win)`. SDL3 does not start text input by itself, so on desktop this is a no-op kept for the macOS press-and-hold reason.
- The key names in `input_names.c` are ours and need no change.

Mouse (`mouse_sdl.c`), following the TASKS kbm-port note (kbm-input 7.2):

| SDL2 | SDL3 |
|---|---|
| `SDL_MOUSEMOTION`, `SDL_MOUSEBUTTONDOWN/UP`, `SDL_MOUSEWHEEL` | `SDL_EVENT_MOUSE_MOTION`, `SDL_EVENT_MOUSE_BUTTON_DOWN/UP`, `SDL_EVENT_MOUSE_WHEEL` |
| `SDL_TOUCH_MOUSEID` | unchanged |
| `SDL_SetRelativeMouseMode(on)` | `SDL_SetWindowRelativeMouseMode(win, on)`; the sync gets the window from `fb_present_sdl.c` |
| `SDL_MOUSEWHEEL_FLIPPED` | `ev->wheel.direction == SDL_MOUSEWHEEL_FLIPPED`, the same flip |
| window focus, hide, minimise and close events | the flattened `SDL_EVENT_WINDOW_*` and `SDL_EVENT_QUIT` |

Two behaviours to hold on purpose:
- **Float deltas.** `xrel` and `yrel` are floats in SDL3, and `wheel.y` is a float. `mouse_sdl.c` keeps a per-axis remainder and hands `mouse.c` whole counts, so sensitivity and the scenario numbers are unchanged. `wheel.integer_y` (3.2) is not used, so a high-resolution wheel still steps once per notch.
- **Focus click-through.** `SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH` is only named in a comment today (TASKS:994). The SDL3 default is the same (off), so nothing is set.

The ctest builds its events with the SDL3 fields and keeps every case. Its relative-mode reads become `SDL_GetWindowRelativeMouseMode(win)` on the hidden dummy window it creates.

**D10. SDL's environment variables.** SDL3 reads `SDL_AUDIO_DRIVER` and `SDL_VIDEO_DRIVER`.

A new header `src/platform/sdl_env.h` provides `static inline void xbox_sdl_env_compat(void)`. It copies `SDL_AUDIODRIVER` into `SDL_AUDIO_DRIVER`, and `SDL_VIDEODRIVER` into `SDL_VIDEO_DRIVER`, when the SDL3 name is unset. It uses `SDL_getenv` and `SDL_setenv_unsafe`, SDL's own API, as `apu_sdl2.c` already does; it never calls libc `getenv`. These are SDL's variables, not `recomp_env` rows.

It is called first thing in every init site:
- `xbox_HostWindowMain`;
- `xa2_init`;
- the pad backend's `sdl_init`;
- `d3d8_gl.c`'s window creation.

Headless audio sets `SDL_AUDIO_DRIVER=dummy`, overwrite 0, as it set the old name.

Live docs and scripts move to the SDL3 names, in the toolkit, the CLI and every game. `docs/env.md` lists `SDL_AUDIO_DRIVER` with "`SDL_AUDIODRIVER` is accepted", and the same for video. Archived openspec changes are not edited.

**The CLI sets both spellings** in `golden_run.run_env()` and anywhere else it exports a driver. A CLI release serves games pinned to different toolkit tags; ssx3 is still on `blinx2-v0.5.0`. A golden run that set only the new name on an SDL2 toolkit would play sound on the Mac. Both names cost nothing, and the old one is removed once no game pins an SDL2 toolkit. `tests/posix_ctest.sh` exports both for the same reason.

**D11. Order and delivery: toolkit, public tag, CLI tag, games.** This deviates from the standing push order (CLI, then `blinx2-recomp`, then the toolkit fork) for one reason: every game pins the **public** toolkit tag, so the toolkit fork's tag must exist before any game can move its pin. The CLI still goes before any game's push.
1. **The toolkit branch** builds and passes its Mac gates against Homebrew `sdl3`, with cat's `XBOXRECOMP_DIR` pointing at the worktree and cat `main` unchanged. cat's `CMakeLists.txt` needs nothing: the toolkit's targets carry SDL3 publicly. It merges to `posix-host/portability` after the Deck golden.
2. **A public push of `blinx2/portability`** and a new tag (the next `blinx2-v0.x`) follows the toolkit scrub-and-mailmap procedure (`notes/public-toolkit-map/`), audited for host names, private paths, the personal email, assistant chat links, binaries and game data, fast-forward only. Which round carries it is Open Question 2, and the round waits for the user's go on it.
3. **The CLI branch** can land first or alongside, because it is independent of the toolkit. It changes doctor, pins, manifest, both env names and the fixtures, and needs a release tag because games pin the CLI by tag. Its squash merge sets `--author` and `GIT_COMMITTER_NAME/EMAIL` to `carlos <4037632+apexJCL@users.noreply.github.com>`; before the push, `scripts/audit-public.sh` runs over `origin/main..main` and `git log --format='%ae %ce' origin/main..main` shows only that address. The CLI's push goes before any game's.
4. **Each game** then makes one branch: `brew`, the companion, `[toolchain] sdl3`, the regenerated pins, the `[cli]` and `[toolkit]` pins at the new tags, and docs and scripts:
   - cat first, then b3;
   - ssx3 and jsrf through their owner sessions (the orchestrator routes them);
   - spartan only moves its toolkit pin.

   cat publishes through `scripts/export-public.sh` and b3 through its own export, each in the same batched round, after the CLI and the toolkit tag.

Until a game moves, it stays on SDL2 through `sdl2-compat`, which keeps working beside an installed `sdl3`.

**D12. Packaging, in the CLI and the manifests.** `xbr doctor` and `setup.host_blockers()` keep reading `[package] brew`. Every game with a macOS target sets it to `["sdl3", "openssl", "libepoxy"]` plus anything else it needs.

The companion entries go from cat and ssx3, because `otool -L` now lists `libSDL3.0.dylib` directly and `dylib_plan` walks it. That holds for Homebrew `sdl3`, whose install name is an absolute Homebrew path. An SDL3 built from source with an `@rpath` install name is not resolved by `dylib_plan`'s walk; a game built that way keeps its companion entry, and the README says Homebrew is the supported Mac source. Both `wrap_macos` and `incr.dylib_shas()` see it the same way. The CLI's `companions()` machinery and `--companion` stay: they are generic and tested with a neutral fixture. The `lib.py:856` docstring loses its sdl2-compat example.

The app's `Contents/Frameworks/` holds `libSDL3.0.dylib`, `libcrypto`, `libz` and whatever else `otool` finds.

The wizard: no Go change. Its fixtures name `sdl2` only as sample formulas and need no change; `wizard/check.sh` (gofmt, vet, test, staticcheck, double build) is the gate. The wizard shows a doctor warning it does not know, such as the SDL3 version warning, as text without a fix button: it has no "brew upgrade" action. That is acceptable for a warning (D1) and is a wizard follow-up if players hit it.

The steamos tar and the windows installer carry no SDL. A native Linux bundle is not a target; if one is ever added it links the runtime's SDL3 or bundles `libSDL3.so.0`, and that is its own change. Each game's `NOTICE` gains a line that the macOS app bundles SDL3 (zlib licence) if it does not already say so. The CLI's `credits.py` entry is version-free and stays.

**D13. Upstream.** Upstream (`origin/main` eb0aa1d5, v0.14.0) is SDL2 in:
- `xinput_device.c` and `d3d8_gl.c`;
- three `find_package` lines;
- `apu_sdl2.c`, `fb_present_sdl.c` and `keyboard_sdl.c` (its #191-derived files);
- `install_deps.sh`, `setup.sh` and `GETTING_STARTED.md`.

SDL2 and SDL3 export the same symbol names, so one process cannot link both; the shared files must move together.

The 2026-10-11 decision (user) stands as to shape: SDL3 goes upstream as its own topic PR, not folded into another. Its timing now follows the later rule: all upstream work waits for the stable BLiNX 2, Burnout 3 and SSX 3 releases and is then re-assessed. So this change opens no PR and does not edit `pr-stack-plan.md`'s rows. It records SDL3 as a candidate on the tracker item with its file list, and at that point the PR rules apply:
- Burnout 3 on the exact head on native Windows, Proton and the Mac;
- no tracker refs;
- few commits.

The upstream-bound files get the smallest mechanical diff now, so that PR stays cheap.

**D14. CPU, D3D11 and Metal agreement.** No render path changes. The present paths that change are the SDL ones: the CPU window on POSIX and the Metal readback fallback. The D3D11 and GDI windows are untouched.

The stock SDL present (nearest letterbox, vsync on, windowed) stays identical (D4). The filters, overscan and Hor+ keep their SDL/D3D11 parity because `nv2a_present_rect` is shared.

The CPU rasteriser only has to build. Its window is the renderer block, which the Metal readback runs exercise. The one post-merge Mac CPU check (`blinx2 golden run --backend cpu`, verdicts and flips/s in TASKS) covers the rest as a follow-up.

**D15. ipados-port consumes this.** Its spec on cat `spike/ipados` (84799f4) states the dependency (task 0.1), builds SDL3 static for iOS at the pinned version (its spec owns that requirement, "SDL3 pinned"; this change does not restate it), and plans its lifecycle events and hot-plug on the SDL path. This change hands it the merge shas, the `[toolchain] sdl3` version, the pin entry's shape, and that hot-plug is ported. `spike/ipados` is not edited.

**D16. The overlay comes after this.** The user's order (TASKS, 2026-10-21) is DSP, then SDL3, then the release; the overlay phases wait for SDL3.
- `enhance-menu-preview` 3A-3D are written once, in SDL3 terms: `SDL_RenderTexture`, `SDL_FRect`, `SDL_SetTextureBlendMode`, `SDL_SetWindowFullscreen` from the main thread, and the host-only buttons as `SDL_GAMEPAD_BUTTON_GUIDE`, `MISC1`, `RIGHT_PADDLE1..LEFT_PADDLE2` and `TOUCHPAD`.
- This change leaves the cached `filter` read (:544) and the creation-time fullscreen flag as they are; making them live is 3C's.
- When this change merges, its follow-through moves that change's SDL2 wording to SDL3: spec :157 becomes "The SDL backend SHALL report the host-only buttons"; `tasks.md:58`; the design's SDL2 rows and calls (:251, :911 `SDL_SetRelativeMouseMode`, :1032 `SDL_RenderCopy`, :1225-1236, :1416 F-3, :1640 Open Question 1); and `assessment.md`. That is a text edit in another open change, so it is done in the follow-through (task 13.4), not on this branch. If 3A starts first, 3A's agent does it.

**D17. Hosts and gates.** The SDL hosts are:
- the Mac (Metal; the packaged `.dmg` of cat, b3, ssx3 and jsrf);
- a native Linux build: not shipped, gated once;
- later, iOS.

The Deck, Proton and native Windows run the Windows build and link no SDL.

Gate hosts after the Linux/Proton host → Deck move (2026-10-16):

| Host | What runs there | Who |
|---|---|---|
| Mac | Build, ctests, Metal goldens (cat, and b3's `race_gate.py`), windowed checks, hot-plug by hand, packaging and DMG smoke for cat and b3, CLI, cat and wizard checks; one sound run only after asking | the implementing agent |
| Deck | `blinx2 bench golden` (D3D11) on the integration build: identical frames and pace, because the Windows build has no SDL; b3's Proton smoke on the same build | orchestrator slot (`flock`, `notes/benches.md`) |
| Native Windows | **Nothing planned**: the Windows build has no SDL and the Deck covers it. A run there needs the user's yes and a reboot | — |
| Linux native | The Linux-native gate (kept by the user, 2026-10-11; host decided 2026-10-21 as Open Question 1 option (d): Mac-built in the sniper image, run on the Deck, later the re-provisioned PC): native cat build, POSIX ctests, a windowed attract run with sound, a `vpad.py` pad before and after launch. On the Linux/Proton host every run is wrapped in `flock -w 3600 ~/.recomp-run.lock`. Time-boxed to 2 h: a Linux failure that is not SDL's (GL, epoxy, a distro quirk) becomes a TASKS follow-up, not a blocker | Open Question 1, which gates the merge |

## Gates (CLAUDE.md as of 2026-10-21, in order)

1. **Mac build** (`export DEVELOPER_DIR=/Library/Developer/CommandLineTools`): the toolkit branch with cat `main`, Release, `-DXBOXRECOMP_ENHANCE=ON` (basic enhancements always).
2. **POSIX ctests:** `tests/posix_ctest.sh <build-dir>`, 0 FAIL, naming `input_map`, `input_bindings`, `input_keyboard_sdl`, `input_hotplug_sdl`, `sdl_env` (new), `window_title`, `apu_*` and `apu_vclock`.
3. **Mac Metal goldens,** headless with `SDL_AUDIO_DRIVER=dummy`: `blinx2 golden run --backend metal` at stock resolution and rate, pace within `max_pace_diff`. No CPU golden (D14).
4. **Mac windowed checks, no sound:**
   - "Present parity" and "Fallback";
   - the 2x2 shot (D4);
   - keyboard and mouse by hand: capture, release key, wheel, Cmd-Tab release;
   - a pad with `RECOMP_HOST_PAD=1`: before launch, unplug and replug, after launch.
5. **Burnout 3 on the Mac,** Metal, headless: `b3/scripts/race_gate.py` against the toolkit worktree, pass.
6. **Performance:** `RECOMP_PRESENT_STATS=1` flips/s and the `metal_prof` present time, before and after, in layer and readback modes. Flag a 25% drop in flips/s or a 1.5x rise in frame ms.
7. **The Deck** (orchestrator): `blinx2 bench golden` (D3D11) on the integration build, with every scenario's frame hashes and pace identical to the previous stamp, and `strings cat_recomp.exe | grep -c SDL_` 0. Then b3's Proton smoke.
8. **Linux native** (Open Question 1, option (d)): the run in D17, as `linux-native-vulkan` Phase 0.
9. **Sound on the Mac:** `audio_check.py` with real sound. **The agent asks the user right before; it never plays unasked.** One run serves this change, `fps-pacing` 8.10 and the tracker item.
10. **CLI and games:**
    - CLI: `uv run pytest tests`, ruff, and `wizard/check.sh`;
    - cat: `uv run pytest scripts` and ruff;
    - packaging: `blinx2 package macos` and b3's, with `otool -L` showing `libSDL3.0.dylib` and no `libSDL2`, `codesign --verify --deep --strict`, and the DMG smoke with a scratch data root.
11. **Review** of every branch before merge; fixes go back to the branch's agent. After the merge:
    - `blinx2 bench integrate --golden` on the Deck;
    - TASKS;
    - one Mac CPU check (D14).

Goldens apply because the change touches the runtime, renderer present, audio and input. The game-repo branches (manifests and docs only) skip goldens, per the CLAUDE.md packaging and docs rule, apart from the macOS packaging smoke.

## Risks / Trade-offs

- **SDL3 ignores the sample-frames hint** on some backend: the marks follow the granted value, as they did with `have.samples`. The audible result is checked in gate 9.
- **A linear default slipping into the stock window:** gate 4's 2x2-block shot catches it.
- **Mouse feel changes through float deltas:** the per-axis remainder keeps whole counts. The ctest's motion cases, and the hands-on check, cover it.
- **Hot-plug on SDL3 posts `GAMEPAD_ADDED` for pads present at init:** the rescan opens by instance id and ignores ids already in the table, so the boot wait and the first `ports` line are unchanged. The "Boot with a pad attached" ctest checks it.
- **`apu_shim.h` clashes with real SDL3 headers:** D7's include check.
- **A distro without SDL3 3.2** (Ubuntu 24.04 LTS and older, Debian 12): no package, so a native build there needs the pinned tarball built from source (D1), which the toolkit README describes. Not a tested host.
- **Games on different toolkit tags during the rollout:** the CLI sets both driver names, and `sdl2-compat` stays installable for a game still on SDL2. `doctor` names exactly what each game's `brew` lists.
- **The public push is batched:** a game cannot move until the tag exists. That is the order in D11; nothing else waits on it.
- **Upstream never takes SDL3:** the shared files stay a standing diff, already the case for #191's files.
- **Pace drift on the Mac from the renderer's vsync wait:** the layer path (Metal default) does not use the renderer, and the readback-mode parity run gates the renderer path.

## Migration Plan and estimates

Branches named `feat/sdl3-migration`, in their own worktrees under `wt/sdl3/`. One implementing agent takes them in the order below; the ssx3 and jsrf edits go through their owner sessions.

| Slice | Where | Estimate | Depends on |
|---|---|---|---|
| 1 Build system, the env shim, the CMake duplicate | toolkit | 2 h | — |
| 2 Window, events, Metal layer | toolkit | 3 h | 1 |
| 3 Renderer present and shots | toolkit | 3 h | 2 |
| 4 Keyboard and mouse | toolkit | 4 h | 2 |
| 5 Gamepad and hot-plug port, its ctest | toolkit | 5 h | 1 |
| 6 Audio stream (vclock kept) | toolkit | 3 h | 1, the tracker item DSP merge |
| 7 Upstream-bound files, toolkit docs | toolkit | 2 h | 1-6 |
| 8 Toolkit Mac gates (1-6), fixes | Mac | 6 h | 1-7 |
| 9 CLI: doctor, pins, manifest, env names, fixtures, wizard fixtures, docs, tag | CLI | 5 h | — |
| 10 Deck golden, Linux-native gate (time-boxed to 2 h), sound run | Deck, Linux host, Mac | 4 h (orchestrator slots plus the user's one sound run) | 8, Open Question 1 |
| 11 Toolkit merge, public push and tag | orchestrator | 1 h | 10, review |
| 12 Games: cat, b3 (agent), ssx3, jsrf (owners), spartan pin | games | 4 h | 9, 11 |
| 13 Merge follow-through: CPU check, overlay rewording, ipados facts, TASKS, archive | orchestrator / agent | 2 h | 12 |

**Total:** about 44 h of agent time, roughly five to six working days, plus the orchestrator's Deck and push slots. Toolkit size is about 700 changed lines across ten source files and three ctests. The 2026-10-11 estimate was about 600 lines; the mouse and the hot-plug port add the rest. The CLI is about 200 lines plus fixtures, and each game is manifest and docs.

**Rollback:** `git revert` of the squash commits, and the games' pins go back to the previous tag. The Mac then needs `sdl2-compat` again (`brew install sdl2-compat`), which `doctor` says.

## Open Questions

Only the user can settle these; this spec does not decide them. Question 1 is settled (2026-10-21).

1. **Where the Linux-native gate runs. Decided (the user, 2026-10-21): option (d)** from `linux-native-vulkan` design D6. Builds happen on the Mac in the pinned Steam Runtime sniper image and run natively on the Deck, until the Linux/Proton host PC is re-provisioned with a proper Linux install; the gate then moves to that PC. No build happens on the Deck. Gate 8 runs as `linux-native-vulkan` Phase 0 (tasks 1.5-1.8), which is a prerequisite of this change's merge. Options (a) to (c) are superseded.

   The gate stays (user, 2026-10-11), and the toolkit merge waits for it.
2. **The public tag.** Recommended: ship SDL3 in the next batched public push round with its own `blinx2-v0.x` tag; the round waits for the user's go. The alternative is a push round just for this, if a game needs SDL3 sooner, for instance the overlay on a release build.

Settled:
- rename `apu_sdl2.c` to `apu_sdl.c` (D6);
- `doctor` warns, not fails (D1);
- hot-plug is in scope; now a port (D8);
- the CLI owns acquisition (D12);
- B3 is included (gates 5 and 10, slice 12);
- the Linux-native gate is kept (D17);
- this comes before the overlay's phase 3 (D16, user order 2026-10-21);
- its own upstream topic PR, timed by the post-release re-assessment (D13);
- the Windows build links no SDL;
- branch names.
