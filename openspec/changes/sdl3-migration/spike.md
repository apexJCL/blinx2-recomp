# SDL3 migration spike

Date: 2026-10-06. Static analysis and documentation only; no game was run, nothing was
implemented. Toolkit at `posix-host/portability` 4e9a2f2, cat at `main` 25ec32c.

**Question.** The iPadOS port (`ipados-port`) is about to pin SDL2 2.30.x as a from-source iOS
dependency. Is it worth moving every host of the project to SDL3 instead, and when?

**Answer in one paragraph.** Yes, and before the iPad build step: option (d), effort **M**.
Three facts decide it. First, the project already runs on SDL3 at runtime on both hosts that
link SDL: the Mac builds against Homebrew `sdl2-compat` (README "Tested with": 2.32.72), and
The Linux/Proton host is Fedora 43/44-based, where the `SDL2` package *is* `sdl2-compat` over `SDL3`. So the
"risk of SDL3's new audio and video behaviour" has already been taken, through a shim that adds
its own bugs and that its authors say not to target for new code. Second, the Windows build,
which is the Proton, SteamOS and golden-on-the Linux/Proton host path, links no SDL at all (XInput, XAudio2,
GDI/D3D11), so the migration cannot touch the D3D11 goldens or the Steam Deck package. Third,
the iPad port has to build an SDL from source anyway, and its own work (the lifecycle pause gate
in the presenter's event loop, the audio category and pause, the UIKit Metal view) lands in
exactly the files the migration rewrites; done in the SDL2 order it is written twice. The
surface is ~400 `SDL_` references in 9 toolkit files (2 of them upstream's), with the seams
already in place (`xa2_*`, `xbox_FramebufferWindow*`, `XBOX_HOST_SDL_GAMEPAD`, `keyboard.c`).
The trigger that flips the answer: the iPad port is dropped or parked for more than a quarter.
Then stay on the SDL2 API over `sdl2-compat` (option (c), the status quo) and migrate when
something else forces a rewrite of `fb_present_sdl.c` or `apu_sdl2.c`.

## 1. Every SDL touchpoint today

### 1.1 Where SDL is linked

| Host / path | Links SDL? | Which SDL at runtime | Gated by |
|---|---|---|---|
| macOS, Metal (`RECOMP_PB_BACKEND=metal`) and CPU present | yes | Homebrew `sdl2-compat` 2.32.7x on `sdl3` 3.4.x (README "Tested with") | Metal goldens, `audio_check.py`, keyboard ctests, `test_package_lib.py` |
| Linux native (CPU render, SDL present, GL `d3d8_gl.c`) | yes | distro `SDL2` = `sdl2-compat` on Fedora 42+ and Arch; real SDL2 on Debian/Ubuntu | nothing today: the README tests only macOS and Linux (Proton); "Linux PC gates 7.x" are open in TASKS |
| Windows x86-64, Proton on the Linux/Proton host, the SteamOS package (`packaging/steamos/launch.sh` runs the Windows build under umu-run) | **no** | none in our process; Proton's `winebus.sys` dlopens the *host's* `libSDL2-2.0.so.0` for controllers, which on the Linux/Proton host is `sdl2-compat` | D3D11 goldens (`bench.sh golden`) |
| iPadOS (specced, not built) | yes | SDL2 2.30.x static, from source (`ipados-port` proposal) | - |

Consequence: a migration changes the Mac build and the dev-only native Linux build. The
Proton and SteamOS paths cannot regress from it, and Proton's own controller stack is already
SDL3 underneath on the Linux/Proton host.

### 1.2 Files and counts (toolkit `posix-host/portability`)

`git grep -o 'SDL_[A-Za-z0-9_]*'` finds 394 references, ~170 distinct names. By file:

| File | LOC | `SDL_` refs | Area | Upstream has it? |
|---|---|---|---|---|
| `src/video/fb_present_sdl.c` | 844 | 84 | window, event loop, `SDL_Renderer` present, window shots, vsync, custom events, quit | no (fork) |
| `src/video/fb_present_metal.m` + `.h` | 385 | 19 | `SDL_Metal_CreateView/GetLayer/GetDrawableSize`, BMP shot surface | no (fork) |
| `src/apu/apu_sdl2.c` | 231 | 26 | audio device, push queue, pacing by queue depth, `SDL_AUDIODRIVER=dummy` for headless | no (fork) |
| `src/apu/apu_shim.h` | - | 21 | **stubs of the SDL3 audio API** (`SDL_AudioStream`, `SDL_OpenAudioDeviceStream`, `SDL_PutAudioStreamData`, `SDL_GetAudioStreamQueued`) for xemu's monitor output; never linked | yes, identical (xemu itself is on SDL3) |
| `src/input/xinput_device.c` | 171 | 29 | `SDL_GameController` open/poll/rumble, `SDL_NumJoysticks`, main-pump flag | yes, but the fork's version is 402 lines diverged |
| `src/input/input_map.h` / `.c` | 360 | 46 | the SDL button/axis enum values as `XBOX_SDL_*`, header-free; the README table column "SDL2" | no (fork) |
| `src/input/keyboard_sdl.c` / `.h` | 137 | 13 | keycode to VK, `SDL_StopTextInput`, key and focus events | no (fork) |
| `src/d3d/d3d8_gl.c` | 1074 | 24 | SDL window + GL 3.3 context, `SDL_PollEvent` in Present | yes, 3-line diff |
| `src/platform/win32_compat.c` | - | 1 | comment only | yes |
| `tests/input_keyboard_sdl/test_main.c` + CMake | 154 | 34 | synthetic `SDL_Event`s (`key.keysym.sym`, `key.state`, `window.event`), `SDL_VIDEODRIVER=dummy` | no (fork) |
| CMake: `src/{apu,input,d3d,video}/CMakeLists.txt`, `tests/input_keyboard_sdl` | - | 5x `find_package(SDL2 REQUIRED)`, `SDL2::SDL2` | build | 3 of 5 upstream |

cat (`main`) has no SDL calls in C. It has: `src/pad_input.c` and `src/main.c` comments;
`scripts/package_lib.py` bundling `libSDL2-2.0.0.dylib` plus a `--companion` for sdl2-compat's
`libSDL3` (its test fixture in `scripts/test_package_lib.py:210-235`); `packaging/launch.env.default.macos`
and the three `README.part`s naming SDL pads; and **43 mentions of `SDL_AUDIODRIVER` /
`SDL_VIDEODRIVER`** across `docs/env.md`, `openspec/`, `scripts/shots/run.sh`,
`scripts/test_launchers.py`, `README.md`, `RESUME.md` and `TASKS.md`. SDL3 renamed those
variables (`SDL_AUDIO_DRIVER`, `SDL_VIDEO_DRIVER`); `sdl2-compat` translates them today.

### 1.3 Each touchpoint against SDL3's API

SDL3 changes, from the migration guide (fetched 2026-10-06), mapped to our call sites:

| Area (file:line) | SDL2 today | SDL3 | Change size |
|---|---|---|---|
| Init, errors (every file) | `SDL_Init() != 0`, `SDL_InitSubSystem`, int returns | `bool` returns on every function; `SDL_INIT_GAMECONTROLLER` -> `SDL_INIT_GAMEPAD` | mechanical, ~30 sites |
| Window (`fb_present_sdl.c:545-575`, `d3d8_gl.c:996`) | `SDL_CreateWindow(title, x, y, w, h, flags)`, `SDL_WINDOWPOS_CENTERED`, `SDL_WINDOW_ALLOW_HIGHDPI`, `SDL_WINDOW_FULLSCREEN_DESKTOP`, `SDL_WINDOW_SHOWN` | `SDL_CreateWindow(title, w, h, flags)` (position via properties), `SDL_WINDOW_HIGH_PIXEL_DENSITY`, `SDL_WINDOW_FULLSCREEN` with a NULL fullscreen mode = borderless desktop, `SHOWN` gone (windows show by default) | S |
| Event loop (`fb_present_sdl.c:633-648`, `keyboard_sdl.c:72-100`, `d3d8_gl.c:555`) | `SDL_WINDOWEVENT` + `ev.window.event == SDL_WINDOWEVENT_*`, `SDL_QUIT`, `SDL_KEYDOWN/UP` | window events are top-level `SDL_EVENT_WINDOW_EXPOSED/RESIZED/FOCUS_LOST/HIDDEN/MINIMIZED`; `SDL_EVENT_QUIT`; `SDL_EVENT_KEY_DOWN/UP` | S |
| Keyboard (`keyboard_sdl.c`, the ctest) | `ev.key.keysym.sym`, `.mod`, `KMOD_GUI`, `SDLK_a..z`, `SDL_StopTextInput()`, `SDL_IsTextInputActive()` | `ev.key.key`, `ev.key.mod`, `SDL_KMOD_GUI`, `SDLK_A..Z` (same values, 'a'..'z'; the `_Static_assert`s at `:20-23` keep holding), `.repeat` stays, `SDL_StopTextInput(window)`, `SDL_TextInputActive(window)`. SDL3 does not start text input by itself, so `xbox_InputSdlInit` becomes a no-op guard | S |
| Gamepad (`xinput_device.c:94-157`, `input_map.h` enums) | `SDL_GameController*`, `SDL_NumJoysticks`/`SDL_IsGameController(i)`, `SDL_GameControllerUpdate/GetButton/GetAxis/Rumble`, `SDL_CONTROLLER_BUTTON_A` | `SDL_Gamepad*`, `SDL_GetJoysticks(&n)` array of ids + `SDL_IsGamepad(id)`, `SDL_UpdateGamepads/GetGamepadButton/GetGamepadAxis/RumbleGamepad` (bool), `SDL_GAMEPAD_BUTTON_SOUTH/EAST/WEST/NORTH`. **Numeric values are unchanged** (SOUTH=0 .. DPAD_RIGHT=14; axes 0..5), so `XBOX_HOST_SDL_GAMEPAD` and `input_map.c`'s rows keep their meaning; only the four `_Static_assert`s and the README column name change. Hotplug arrives as `SDL_EVENT_GAMEPAD_ADDED/REMOVED` in the loop we already own | S |
| Audio (`apu_sdl2.c`) | `SDL_OpenAudioDevice(NULL, 0, &want{samples=512}, &have, 0)`, `SDL_QueueAudio`, `SDL_GetQueuedAudioSize`, `SDL_ClearQueuedAudio`, `SDL_PauseAudioDevice(dev, 0/1)`, `SDL_setenv("SDL_AUDIODRIVER", "dummy", 0)` | `SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec{48000, S16, 2}, NULL, NULL)` (opens paused), `SDL_PutAudioStreamData`, `SDL_GetAudioStreamQueued` (bytes), `SDL_ClearAudioStream`, `SDL_ResumeAudioDevice`/`SDL_PauseAudioDevice(dev)`, `SDL_setenv_unsafe("SDL_AUDIO_DRIVER", ...)`. `SDL_AudioSpec.samples` is gone: the device buffer (our `RECOMP_AUDIO_BUF_SAMPLES`) becomes `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES`, set before open, and "many platforms won't honor this request"; `SDL_GetAudioDeviceFormat(dev, &spec, &frames)` reports what was granted. The names are the ones `apu_shim.h` already stubs | S code, M verification (section 4.2) |
| Renderer present (`fb_present_sdl.c:574-752`) | `SDL_CreateRenderer(win, -1, ACCELERATED\|PRESENTVSYNC)`, `SDL_GetRendererInfo`, `SDL_HINT_RENDER_SCALE_QUALITY=nearest`, `SDL_RenderSetLogicalSize`, `SDL_SetTextureScaleMode(SDL_ScaleModeLinear)`, `SDL_RenderCopy`, `SDL_GetRendererOutputSize` | `SDL_CreateRenderer(win, NULL)` + `SDL_SetRenderVSync(r, 1)`, `SDL_GetRendererName`, the quality hint is gone and **the default scale mode is linear**, so the stock nearest letterbox must be set per texture (`SDL_SCALEMODE_NEAREST`), `SDL_SetRenderLogicalPresentation(r, w, h, SDL_LOGICAL_PRESENTATION_LETTERBOX)`, `SDL_RenderTexture` with `SDL_FRect`, `SDL_GetCurrentRenderOutputSize` | M (the largest single block) |
| Window shots (`fb_present_sdl.c:469-488`, `fb_present_metal.m` `save_shot`) | `SDL_CreateRGBSurfaceWithFormat`, `SDL_RenderReadPixels(ren, NULL, fmt, px, pitch)`, `SDL_SaveBMP`, `SDL_FreeSurface` | `SDL_RenderReadPixels(ren, NULL)` returns an `SDL_Surface*`; `SDL_CreateSurface(w, h, fmt)`, `SDL_DestroySurface`; `SDL_SaveBMP` keeps its shape (bool) | S |
| Metal layer (`fb_present_metal.m:130-160`, `:300`) | `SDL_WINDOW_METAL`, `SDL_Metal_CreateView`, `SDL_Metal_GetLayer`, `SDL_Metal_DestroyView`, `SDL_Metal_GetDrawableSize` | the first four exist unchanged in SDL3 (since 3.2.0; main thread only); `SDL_Metal_GetDrawableSize` -> `SDL_GetWindowSizeInPixels` | S |
| Custom events, wake-ups (`fb_present_sdl.c:225-228, 336-339, 600, 772`) | `SDL_RegisterEvents(2)` (-1 on failure), `SDL_PushEvent`, `SDL_WaitEventTimeout(&ev, 100)` | `SDL_RegisterEvents` returns 0 on failure; `SDL_PushEvent` returns bool; `SDL_WaitEventTimeout` unchanged | trivial |
| Hints (`fb_present_sdl.c:531`, `apu_sdl2.c`, `xinput_device.c:122`, `d3d8_gl.c:981`) | `SDL_HINT_NO_SIGNAL_HANDLERS` | same | none |
| GL (`d3d8_gl.c:989-1012`) | `SDL_GL_SetAttribute`, `SDL_GL_CreateContext`, `SDL_GL_MakeCurrent`, `SDL_GL_SetSwapInterval`, `SDL_GL_SwapWindow` | same names, bool returns | trivial |
| Vsync | `SDL_RENDERER_PRESENTVSYNC`; the layer sets `displaySyncEnabled` itself | `SDL_SetRenderVSync`; the layer path is untouched | trivial |
| Threads, timers | none: the fork uses pthreads and `clock_gettime`; `xbox_HostWindowMain` starts the guest on its own pthread | n/a | none |
| Properties API | not used | optional; only `SDL_CreateWindowWithProperties` if we want the centred position back (SDL3 centres by default) | none required |
| Headers, CMake, packaging | `<SDL.h>`, `find_package(SDL2)`, `SDL2::SDL2`; the Mac bundle carries `libSDL2-2.0.0.dylib` + companion `libSDL3.dylib` | `<SDL3/SDL.h>`, `find_package(SDL3 CONFIG)`, `SDL3::SDL3`; the bundle carries `libSDL3.0.dylib` only, the `--companion` path and its fixture go | S |
| `sdl2-compat` | what the Mac and the Linux/Proton host run today | not involved after the move; a binary-compatible layer, "not for new code" (its README) | - |

Nothing in the list is a redesign. The event loop, the three-slot hand-off, the guest thread
inversion and the pacing marks are untouched; the renderer block and the audio open are the two
places where behaviour, not just spelling, must be re-checked.

## 2. What SDL3 buys

### 2.1 Real for this project

- **One SDL on every host, and the one the host actually runs.** Today the Mac binary links an
  SDL2 shim over SDL3; after the move it links SDL3. The `sdl2-compat` layer has had its own
  regressions on exactly our stack (the 2.32.62->2.32.64 / SDL3 3.4.0 update of February 2026
  broke controller passthrough into Proton, per the CachyOS report), and we cannot debug or pin
  what Homebrew and Fedora ship. The iPad build must compile its SDL from source either way;
  with SDL3 that source is the maintained line (3.4.18 on Homebrew and Fedora 43/44/45 as of
  2026-10-06) instead of SDL2's maintenance line (2.32.10, 2025-09-01).
- **The iPad lifecycle in the loop we own.** SDL3 keeps the classic main loop on iOS (the
  main-callbacks README: the callbacks "work on every platform" and are faked with a loop where
  the platform does not need them; iOS "prefers" them, Emscripten requires them). So the
  `ipados-port` pause gate in `xbox_HostWindowMain` works unchanged, and
  `SDL_MAIN_USE_CALLBACKS` (`SDL_AppInit/Iterate/Event/Quit`) stays an option for the iOS entry
  file if the "OS may not give you any processing time after the events are delivered" rule bites
  at `SDL_EVENT_WILL_ENTER_BACKGROUND`. SDL3's iOS build is documented for CMake
  (`-DCMAKE_SYSTEM_NAME=iOS`, `SDL_FRAMEWORK`), which is the configure `ipados-port` already
  plans; SDL2's iOS CMake path works too, so this is parity, not a gain.
- **Audio written against the real device model.** `apu_sdl2.c` paces the APU by queue depth
  with the assumption "the device thread pulls one device buffer per callback". Under
  `sdl2-compat` that is SDL3's stream being emulated as SDL2's queue; writing to
  `SDL_AudioStream` directly lets `RECOMP_AUDIO_BUF_SAMPLES` map onto
  `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES` explicitly and lets us log the granted
  `sample_frames` from `SDL_GetAudioDeviceFormat`, which today we only infer. SDL3 also migrates
  the stream when the default output device changes (headphones), which SDL2 did not.
- **Hotplug and the input-selection spike.** `spike/input-selection` plans "SDL hot-plug with
  sticky slots". SDL3's `SDL_EVENT_GAMEPAD_ADDED/REMOVED` land in the presenter's one event loop;
  SDL2 has the same events, so this is parity in API but the spike's code would be written once.
- **Touch and pen for an on-screen overlay** (iPad v2, after input-selection). SDL2 has finger
  events; the pen API (`SDL_EVENT_PEN_*`, pressure, tilt, proximity) is SDL3-only. A game overlay
  needs fingers, not pens, so this is a small plus, not a reason.
- **Packaging gets simpler.** One dylib instead of a shim plus its companion; the `--companion`
  code path in `package_lib.py` and its fixture go away.

### 2.2 Generic, not a reason here

- Gamepad database and Steam Input: SDL2 2.32 and SDL3 share the mapping database, and our
  Proton path never sees our SDL. On the Deck the SteamOS package runs Proton, whose SDL is
  Valve's problem (the SteamOS README: "Link against SDL as normal, and expect it to be
  available"); the Steam Linux Runtime now ships `sdl2-compat` on SDL3.
- HiDPI and fullscreen on macOS: SDL3 always runs high-DPI and separates pixel size from point
  size (`SDL_GetWindowSizeInPixels`, `SDL_GetWindowPixelDensity`). We already pass
  `SDL_WINDOW_ALLOW_HIGHDPI` and size the layer from `SDL_Metal_GetDrawableSize`; borderless
  fullscreen exists in both. No visible change.
- Audio latency: SDL3 picks the device buffer itself and may ignore the hint. Our 512x4 marks
  were tuned on SDL2 semantics and already run through `sdl2-compat`; expect the same numbers,
  not better ones.
- The properties API, 64-bit ticks, the camera and GPU APIs: unused.
- Proton's SDL: not ours to choose; Proton's `winebus` loads the host's `libSDL2-2.0.so.0`,
  which on the Linux/Proton host and the new Steam Runtime is already `sdl2-compat` over SDL3.

## 3. Costs and risks

### 3.1 Effort per area

| Area | Work | Size |
|---|---|---|
| `fb_present_sdl.c` window, loop, renderer, shots | ~40 call sites; the renderer block is re-expressed (`SetRenderLogicalPresentation`, `RenderTexture`, per-texture nearest, `ReadPixels` surface); the loop's event names | M |
| `fb_present_metal.m/.h` | 1 function rename, 1 surface API, header path | S |
| `apu_sdl2.c` | stream open, put, queued-bytes, clear, resume; the hint for the buffer size; `SDL_AUDIO_DRIVER` for headless while still honouring `SDL_AUDIODRIVER` from our scripts; the `[SDL2]` log prefix becomes `[SDL3]` and `docs/env.md` follows | S |
| `xinput_device.c`, `input_map.h/.c`, README table | renames, `SDL_GetJoysticks`, 4 asserts, the "SDL2" column header; optional hotplug | S |
| `keyboard_sdl.c/.h`, `tests/input_keyboard_sdl` | field and constant renames, per-window text input, flattened window events, `SDL_VIDEO_DRIVER=dummy` in the ctest env | S |
| `d3d8_gl.c` (upstream file) | 1 create-window call, 1 event name, header | S |
| CMake (5 places), `apu_shim.h` guard so the real header wins | `find_package(SDL3 CONFIG)`; make the stubs `#ifndef SDL_h_`-guarded or drop them | S |
| cat: `package_lib.py` + fixture, `test_launchers.py`, `scripts/shots/run.sh`, `docs/env.md`, READMEs, specs: the 43 `SDL_AUDIODRIVER`/`SDL_VIDEODRIVER` mentions, the "SDL2" wording | S-M (mostly search and replace, but it is documentation the user reads and types) |
| Gates: Mac build, POSIX ctests, Metal goldens, `audio_check.py` with real sound (asks the user), keyboard hands-on, packaged app re-check (pad, sound, bundle contents) | M |
| `ipados-port` edits: the SDL pin becomes SDL3 3.4.x; event names in the pause gate; `SDL_HINT_AUDIO_CATEGORY` is unchanged | S, if done before M1 |

Total **M**: on the order of a working week for one agent including gates, in one toolkit
branch off `posix-host/portability` plus one cat branch for packaging and docs. It becomes
**L** only if we also stand up a native Linux build gate on the Linux/Proton host (today absent, and
`sdl2-compat` vs real SDL2 on Debian-family already makes that path unverified).

### 3.2 Golden and audio regression surface

- **D3D11 goldens: none.** The Windows build has no SDL.
- **Metal and CPU goldens on the Mac: pacing only.** `golden.py` compares `fb_dump_at`/`d3d11_dump`
  frames and flip pace; the SDL window's pixels are never compared. The present path can move
  pace if the renderer's vsync wait or the main loop's wake-up changes; `SDL_WaitEventTimeout`
  and the custom frame event are unchanged, and the layer path (the default on Metal) does not
  use `SDL_Renderer` at all. Risk: low; the gate catches it.
- **Window shots** (`RECOMP_WINDOW_SHOT`, used by `scripts/shots`): the renderer's default scale
  mode flips to linear in SDL3; forgetting `SDL_SCALEMODE_NEAREST` would blur the stock
  letterbox. Not a golden, but a visible stock-behaviour change, so it is a review item.
- **Audio: the real risk, and it is verification, not design.** Queue-depth pacing
  (`xa2_queued_samples` -> `mcpx_apu_pace_step`) depends on the granted device buffer. SDL3 may
  not honour the sample-frames hint; CoreAudio generally does, but the first run with real sound
  on the Mac must be listened to, and TASKS already records that Mac audio has only been checked
  with `SDL_AUDIODRIVER=dummy` since the real-time timer thread change (task 8.10). That check is
  needed with or without SDL3; do them together, and **ask the user before any Mac run with
  sound** (workspace rule).
- **Upstream (Burnout 3) under Proton:** unaffected; no SDL in that binary.

### 3.3 Packaging and licensing

- SDL3 is zlib, as SDL2 and `sdl2-compat` are (Homebrew formula pages). `NOTICE` keeps one SDL
  entry with the version bumped. No new third-party code enters the tree.
- macOS bundle: `dylib_plan` walks `otool -L`; SDL3 appears as a plain dependency
  (`@rpath/libSDL3.0.dylib`), so the `--companion` mechanism becomes unused. Keep it or delete
  it with its test.
- Windows and SteamOS bundles: unchanged.
- iOS: SDL3 built static from source with the same pin mechanism `ipados-port` plans for SDL2
  (`config/setup-pins.json`).

### 3.4 Availability of packages

| Host | SDL3 | Notes |
|---|---|---|
| macOS Homebrew | `sdl3` 3.4.18 (zlib); `sdl2-compat` 2.32.74 depends on it and is "also known as `sdl2`" | the Mac already has `sdl3` installed as a dependency; `brew install sdl3` adds headers and the CMake config |
| Fedora 43/44/45 (the Linux/Proton host base; the Fedora 42 build container) | `SDL3` 3.4.16 stable, 3.4.18 testing; `SDL3-devel` | Fedora's own `SDL2` is `sdl2-compat` since F42 |
| Arch / SteamOS 3.7 | `sdl2` replaced by `sdl2-compat`; `sdl3` in extra | the SteamOS package does not link SDL anyway |
| Debian / Ubuntu | `libsdl3-dev` in testing and recent Ubuntu; LTS 22.04 has none | affects only a from-source Linux build; `install_deps.sh` is upstream's and lists per-distro packages |
| iOS | from source (CMake, `-DCMAKE_SYSTEM_NAME=iOS`) | same as the SDL2 plan |

### 3.5 Upstream adherence

Upstream `sp00nznet/xboxrecomp` is SDL2 on POSIX: `d3d8_gl.c` (SDL window + GL),
`xinput_device.c` (SDL GameController), three `find_package(SDL2)` lines,
`tools/linux/install_deps.sh` ("sdl2 resolves to sdl2-compat on current Arch", upstream's own
comment), `tools/macos/setup.sh` (`brew install sdl2 libepoxy`) and `docs/GETTING_STARTED.md`.
Its README positions Linux and macOS as secondary hosts of a Windows-first toolkit. The fork's
SDL files that matter (`fb_present_sdl.c`, `fb_present_metal.m`, `apu_sdl2.c`,
`keyboard_sdl.c`, `input_map.c`) are not upstream's at all, so for them there is nothing to
adhere to beyond the README's "C11, match the surrounding code" rules.

The two shared files are the cost. SDL2 and SDL3 cannot both be linked into one process (same
`SDL_*` symbol names), so the move is all-or-nothing per binary, and the upstream give-back
of `d3d8_gl.c` and `xinput_device.c` then carries an SDL3 dependency. Two ways to keep that
cheap:

1. Keep the upstream-file diffs minimal and mechanical (the create-window call, the event
   names, the gamepad renames), and offer them upstream as one small "SDL3" PR in the stack,
   with the Arch/Fedora `sdl2-compat` situation as the motivation upstream already acknowledges.
   `xinput_device.c` is already 402 lines away from upstream, so its give-back is a rewrite
   either way.
2. The `pr-stack-plan.md` has no SDL item; add one in the lowest tier and state in each PR that
   it was tested under Proton only (the Windows build never links SDL, which makes that true and
   harmless).

If the user's priority were to land the current 26-PR stack first, the migration should wait
until that round is out, which keeps the SDL3 PR a clean one-commit diff on top.

## 4. The options

| | Option | Now | Later | Verdict |
|---|---|---|---|---|
| (a) | Stay on SDL2: pin SDL2 for iOS, keep `sdl2-compat` on desktop | 0 | the iPad lifecycle and audio work is written against SDL2; a frozen 2.32 line on iOS; every SDL bug on the Mac is debugged through a shim we do not control; a migration later costs the same M plus a second pass over the iPad code | cheapest today, most expensive over the year |
| (b) | SDL2 now, SDL3 later behind an isolated shim | S-M to build a shim over ~170 symbols | the shim is more code than the migration (the seams that matter already exist: `xa2_*`, `xbox_FramebufferWindow*`, `XBOX_HOST_SDL_GAMEPAD`, `keyboard.c`); it would be a third API nobody else documents | reject |
| (c) | `sdl2-compat` as the bridge | 0 (it is the status quo on the Mac and on the Linux/Proton host) | no path to iOS (its README does not cover iOS and says not to target it for new code); shim regressions land on us (Feb 2026); the `--companion` bundling stays | fine as a holding pattern, not a destination |
| (d) | Migrate now, before the iPad build step | **M** | iPad built once on SDL3; one SDL on every host; audio and hotplug written against the real API; simpler bundle; one small upstream PR | **recommended** |

**Recommendation: (d), effort M**, sequenced as its own toolkit branch after the in-flight
upstream-merge follow-ups and before `ipados-port` M1 ("boot to attract in the Simulator").
Spec: `openspec/changes/sdl3/` (proposal, design, tasks) with these gates: Mac build, POSIX
ctests (`input_keyboard_sdl` on the dummy driver), Metal and CPU goldens on the Mac,
`audio_check.py` with sound on the Mac (user asked first), the packaged app re-checked (bundle
contents, pad, keyboard, sound), `pytest scripts/` for the launcher and bundling tests, and
one `bench.sh golden` on the Linux/Proton host to prove the D3D11 path did not move (it should be byte
identical: no SDL in that build). Review on merge, as every merge.

**Trigger that changes the answer.** If the iPad port is dropped or parked beyond a quarter,
stay on (c): keep the SDL2 API, keep `sdl2-compat` on desktop, and migrate only when
`fb_present_sdl.c` or `apu_sdl2.c` needs a rewrite for another reason (hotplug with sticky
slots from the input-selection spike would be that moment). A second trigger in the other
direction: if Homebrew or Fedora drop `sdl2-compat` as the `sdl2` provider, the Mac build stops
configuring and (d) becomes urgent rather than planned.

## 5. Questions for the user

1. Ordering: SDL3 before `ipados-port` M1 (recommended), or after the iPad Simulator boot so the
   port is not blocked on this? Doing it after means the pause gate and audio pause are written
   twice.
2. The audio gate needs one Mac run with real sound (`audio_check.py`, coreaudio). May the
   migration agent ask for that at the end of its branch, together with the pending task 8.10
   check?
3. If (a) or (c) is chosen instead: pin SDL2 **2.32.x** for iOS rather than 2.30.x; 2.32 is
   SDL2's maintenance line (2.32.10, 2025-09-01) and what `sdl2-compat` emulates.

## Sources (fetched 2026-10-06)

- SDL3 migration guide, `docs/README-migration.md` at `libsdl-org/SDL` main:
  <https://raw.githubusercontent.com/libsdl-org/SDL/main/docs/README-migration.md>
  (bool returns, `SDL_CreateWindow`, window and key events, `SDL_Gamepad` renames,
  `SDL_AudioStream` and `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES`, renderer renames and the linear
  default, `SDL_RenderReadPixels` returning a surface, `SDL_Metal_GetDrawableSize` ->
  `SDL_GetWindowSizeInPixels`, `SDL_setenv_unsafe`, `SDL_AUDIO_DRIVER`/`SDL_VIDEO_DRIVER`,
  `SDLK_a` -> `SDLK_A`, `KMOD_*` -> `SDL_KMOD_*`, `SDL_WINDOW_FULLSCREEN_DESKTOP` removed,
  high DPI always on).
- `SDL_GamepadButton` values: <https://wiki.libsdl.org/SDL3/SDL_GamepadButton>.
- `SDL_Metal_CreateView` in SDL3 (since 3.2.0, main thread only):
  <https://wiki.libsdl.org/SDL3/SDL_Metal_CreateView>.
- SDL3 audio model: <https://wiki.libsdl.org/SDL3/CategoryAudio>;
  the sample-frames hint: <https://wiki.libsdl.org/SDL3/SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES>.
- SDL3 main callbacks: <https://wiki.libsdl.org/SDL3/README-main-functions>.
- SDL3 on iOS (lifecycle events, `SDL_SetiOSAnimationCallback`, deployment targets):
  <https://wiki.libsdl.org/SDL3/README-ios>.
- SDL3 CMake consumption and iOS/tvOS builds: <https://wiki.libsdl.org/SDL3/README-cmake>.
- SDL3 pen API: <https://wiki.libsdl.org/SDL3/CategoryPen>.
- SDL on Steam/SteamOS: <https://wiki.libsdl.org/SDL3/README-steamos>.
- `sdl2-compat` README ("not for new code", `SDL2COMPAT_*`, syswm caveats):
  <https://github.com/libsdl-org/sdl2-compat> and
  <https://raw.githubusercontent.com/libsdl-org/sdl2-compat/main/README.md>.
- Homebrew: `sdl3` 3.4.18, zlib: <https://formulae.brew.sh/formula/sdl3>;
  `sdl2-compat` 2.32.74 on `sdl3` 3.4.18, "also known as sdl2", zlib:
  <https://formulae.brew.sh/formula/sdl2-compat> (the `sdl2` formula page returns 404).
- Fedora: `SDL3` 3.4.16/3.4.18 on F43-F45: <https://packages.fedoraproject.org/pkgs/SDL3/SDL3/>;
  the F42 change replacing SDL2 with `sdl2-compat`:
  <https://www.fedoraproject.org/wiki/Changes/SDL2onSDL3>; `sdl2-compat` on F43:
  <https://packages.fedoraproject.org/pkgs/sdl2-compat/sdl2-compat>.
- The Linux/Proton host 43.x releases (Fedora 43 base): <https://newreleases.io/project/github/ublue-os/bench host/release/43.20260210>.
- Arch `sdl2-compat` 2.32.70 replacing `sdl2`: <https://www.archlinux.org/packages/extra/x86_64/sdl2-compat>.
- Proton's `winebus` loading the host `libSDL2-2.0.so.0` (now `sdl2-compat`), and the
  February 2026 controller breakage:
  <https://discuss.cachyos.org/t/possible-regression-with-latest-proton-cachyos-native-when-using-an-xbox-compatible-controller/22696>.
- SDL2 maintenance line (2.32.0 2025-02-08 .. 2.32.10 2025-09-01):
  <https://lore.ptxdist.org/ptxdist/20250307094946.4096888-1-m.olbrich@pengutronix.de/t>
  and <https://gitlab.com/recalbox/packages/sdl2/-/tags>.
- SDL3 release cadence (3.4.0 2026-01-01 .. 3.4.12 2026-07-02; Fedora and Homebrew at 3.4.18):
  <https://discourse.libsdl.org/c/sdl-announcements/5>.

Project facts cited from the main checkouts: toolkit `posix-host/portability` 4e9a2f2
(`src/video/fb_present_sdl.c`, `src/video/fb_present_metal.m`, `src/apu/apu_sdl2.c`,
`src/apu/apu_shim.h`, `src/input/xinput_device.c`, `src/input/input_map.h`,
`src/input/keyboard_sdl.c`, `src/d3d/d3d8_gl.c`, `tests/input_keyboard_sdl/test_main.c`, the
four `CMakeLists.txt`), upstream `origin/main` (`src/apu/CMakeLists.txt`,
`tools/linux/install_deps.sh`, `tools/macos/setup.sh`, `docs/GETTING_STARTED.md`), cat `main`
25ec32c (`README.md` "Tested with", `scripts/package_lib.py`, `scripts/test_package_lib.py`,
`scripts/golden.py`, `packaging/steamos/launch.sh`, `TASKS.md`), and
`wt/ipados/cat` (`openspec/changes/ipados-spike/spike.md`, `openspec/changes/ipados-port/proposal.md`).
