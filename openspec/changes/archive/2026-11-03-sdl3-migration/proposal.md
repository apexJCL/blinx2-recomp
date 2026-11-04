## Why

The spike `spike.md` (in this change since the tracker item; it was `openspec/changes/sdl3-spike/`) (2026-10-06, cat `spike/sdl3` 141a427) found that the project's SDL2 already runs on SDL3 on every host that links it. The Mac builds against Homebrew `sdl2-compat` (2.32.72 over `sdl3` 3.4.16 on 2026-10-21; brew stable `sdl3` is 3.4.18), and Fedora and Arch ship `sdl2` as `sdl2-compat`. The shim is one the project cannot pin or debug, its authors say not to target it for new code, and it has regressed on our stack: the February 2026 `sdl2-compat` 2.32.64 / SDL3 3.4.0 update broke controller passthrough into Proton. The toolkit's own hot-plug code already works around it, enumerating devices only on the pumping thread because sdl2-compat's device-index list is not thread-safe. The iPadOS port (cat `spike/ipados` 84799f4, self-build only) has to build an SDL from source either way, and its spec waits on this change (its task 0.1). The enhance menu's overlay phases (`enhance-menu-preview` 3A-3D, the tracker item..292) are written to wait for SDL3 too (user order, 2026-10-21: DSP the tracker item, then SDL3 the tracker item and testing, then the release). The user chose the spike's option (d): migrate every SDL-using host to SDL3.

This is the third revision. The 2026-10-11 text (cat `feat/sdl3-migration` f217dde, never merged) measured toolkit f8696da. Since then, 198 toolkit commits and 64 CLI commits have landed, and four more games pin the toolkit. This revision re-measures the surface against these bases:
- toolkit `posix-host/portability` 4559bae9;
- CLI `main` 85e24c9 (v0.9.0-8);
- cat `main` 77a01ca;
- b3 47f7fdd, ssx3 429de64, jsrf 21bc4d7, spartan f851ad0;
- upstream `origin/main` eb0aa1d5 (v0.14.0).

**What moved since 2026-10-11:**
- **Hot-plug landed on SDL2** (toolkit 8c9f875b, archive `2026-10-17-sdl2-hotplug`): a port table under a mutex, GUID-sticky ports, a flag-only event watch, rescans on the pumping thread, a 250 ms boot wait, and `tests/input_hotplug_sdl` on SDL's virtual joysticks. Hot-plug stays in scope (user, 2026-10-06), but it is now a port of a working design, not new work.
- **Keyboard and mouse grew:**
  - `mouse_sdl.c` (new): relative mouse mode, the wheel and focus;
  - `input_names.c` and `[input.bindings]`;
  - `RECOMP_MKB`;
  - `keyboard_sdl.c`, now 157 lines;
  - `tests/input_keyboard_sdl`, which tests the mouse too.
- **Audio:** the dummy driver's drain is replaced by a virtual 48 kHz device (`apu_vclock.h`). The SDL queue is now only the real-device path.
- **Upstream v0.14.0 merged** (b87b386f). Upstream is still entirely SDL2.
- **The CLI** (v0.9.0) gained:
  - the Go/Fyne build wizard, which installs Homebrew packages by parsing `doctor`'s `brew install` blocker;
  - `package/incr.py`, which calls `dylib_plan`;
  - more tests and fixtures that name `sdl2`.
- **Games:**
  - cat and b3 have macOS targets, and so do ssx3 and jsrf.
  - b3 and jsrf list `sdl2` without `sdl3`. ssx3 lists both and carries cat's `libSDL3.dylib=brew:sdl3` companion.
  - spartan has no macOS package yet. kuf is Windows-only.
  - Every game pins the **public** toolkit tag (`blinx2/portability` `blinx2-v0.5.1` 06c97d13; ssx3 `blinx2-v0.5.0` 1eee3145), not `posix-host/portability`.
- **The Deck replaced the Linux/Proton host** for Proton runs (2026-10-16). The Linux-native distrobox gate (kept by the user) needs a host restated.
- **Upstream PRs wait** for stable BLiNX 2, Burnout 3 and SSX 3 releases, then get re-assessed. The 2026-10-11 plan for a PR row after #191 is reframed to match.
- **The overlay spec** (`enhance-menu-preview`, cat 54b7eb8) says "The SDL2 backend SHALL report the host-only buttons" and has an SDL3 rename table for them.

## What Changes

- **The toolkit's POSIX host layer links SDL3** (`find_package(SDL3 3.2 CONFIG REQUIRED)`, `SDL3::SDL3`, `<SDL3/SDL.h>`) in `src/video`, `src/apu`, `src/input`, `src/d3d` and the two SDL ctests. SDL2 and `sdl2-compat` leave the build and the macOS bundles. The duplicated `fb_present_sdl.c` block in `src/video/CMakeLists.txt`, left by the v0.14.0 merge, goes.
- **Window, events and the Metal layer** (`fb_present_sdl.c`, `fb_present_metal.m/.h`):
  - SDL3's window creation;
  - the flattened `SDL_EVENT_WINDOW_*` events;
  - `SDL_GetWindowSizeInPixels` for the layer's drawable size;
  - `SDL_CreateSurface` for shots.

  The loop, the three-slot hand-off, the guest-thread inversion, the pad and mouse sync calls, and the headless path are unchanged.
- **The renderer present** (the CPU path's window and Metal's readback fallback) moves to SDL3's renderer API with the stock nearest letterbox made explicit, because SDL3's default scale mode is linear. Window shots read back through the surface-returning `SDL_RenderReadPixels`.
- **Audio** (`apu_sdl2.c`, renamed `apu_sdl.c`):
  - The push queue becomes an `SDL_AudioStream` opened with `SDL_OpenAudioDeviceStream`.
  - `RECOMP_AUDIO_BUF_SAMPLES` maps onto `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES`, and the granted size is logged and used.
  - On the dummy driver, the virtual device (`apu_vclock`) stays the queue.
  - The pacer, the WAV tap and the XAudio2 backend do not change. The log prefix becomes `[SDL3]`.
- **Gamepad and hot-plug** (`xinput_device.c`, `input_map.h/.c`): the `SDL_Gamepad` API with positional button names. The values are unchanged, so the mapping table and `tests/input_map` keep their meaning. The design ports one-for-one:
  - the slot table, the GUID stickiness and the boot wait;
  - `SDL_EVENT_GAMEPAD_ADDED/REMOVED` raising the rescan flag;
  - `SDL_GetGamepads` in the rescan;
  - SDL3's virtual-joystick API in the ctest.
- **Keyboard and mouse** (`keyboard_sdl.c`, `mouse_sdl.c`, `tests/input_keyboard_sdl`):
  - SDL3's key and mouse event fields;
  - `SDL_SetWindowRelativeMouseMode`;
  - float mouse deltas, accumulated to the same integer counts;
  - the wheel's `direction`;
  - per-window text input.

  The rules and the ctest cases stay the same.
- **SDL's own environment variables:** SDL3 reads `SDL_AUDIO_DRIVER` and `SDL_VIDEO_DRIVER`. The host layer copies the SDL2 spellings into them when unset, so every script, launch env and bench recipe keeps working. Live documentation moves to the SDL3 names. The CLI sets both spellings, because the games pin different toolkit tags.
- **Acquisition and packaging, in the CLI:**
  - `xbr doctor` keeps reading `[package] brew` from `game.toml`; each game with a macOS target sets `sdl3`, `openssl` and `libepoxy` (no `sdl2`).
  - A new `[toolchain] sdl3` version makes `xbr pins refresh` record one SDL3 source release in `config/setup-pins.json`, and `doctor` warns, never fails, when the installed SDL3 is older.
  - The macOS app bundles `libSDL3.0.dylib` as an ordinary `otool -L` dependency, so cat's and ssx3's companion entries go.
  - The wizard needs no code change (it installs what `doctor` names); its fixtures move to `sdl3`.
  - The steamos and windows bundles carry no SDL and do not change.
- **Games:**
  - cat, b3, ssx3 and jsrf move their `brew` lists to SDL3 and their docs and scripts to the SDL3 variable names.
  - cat and ssx3 drop the companion.
  - Each game moves its toolkit pin to the first public tag that carries SDL3.
  - No game's C changes; they have no SDL calls of their own.
- **The overlay spec** (`enhance-menu-preview`) is reworded from "SDL2 backend" to "SDL backend" when this change merges, or when its phase 3A starts if that comes first.
- **Upstream:** the upstream-bound files get the smallest mechanical diff and are listed for the post-release upstream re-assessment. No upstream PR is opened by this change.
- **`ipados-port`** consumes the result: the merge shas, the pinned version and the hot-plug port. Nothing in `spike/ipados` is edited.

Non-goals:
- sticky slots across launches, rebinding and input selection (`spike/input-selection`);
- touch and pen;
- `SDL_MAIN_USE_CALLBACKS` on desktop;
- the properties API beyond what the window needs;
- any change to the Windows build, XInput, XAudio2, the GDI window or the D3D11 window;
- a native Linux package;
- the overlay itself (phase 3 of `enhance-menu-preview`), which is written on SDL3 after this lands.

## Capabilities

### New Capabilities
- `host-sdl`: the SDL3 host layer on POSIX hosts:
  - which hosts link it;
  - the version floor and the pin;
  - headless drivers and the accepted environment variables;
  - that the Windows build never links SDL.

### Modified Capabilities
- `gpu-backend`: the CPU path's present and the Metal window name SDL3; the stock nearest filter is explicit; window shots are unchanged.
- `input`: the host pad on POSIX is SDL3's gamepad API behind the same mapping table; hot-plug's ctest uses SDL3 virtual gamepads.
- `audio`: the POSIX device backend is SDL3's audio stream behind the same `xa2_*` contract and pacing. Log lines read `[SDL3]`. `SDL_AUDIO_DRIVER` is honoured, with `SDL_AUDIODRIVER` accepted.
- `deployment`: the test-only settings example uses the SDL3 variable name.
- `packaging`:
  - the Homebrew list is `game.toml`'s and names `sdl3`;
  - `doctor` checks the installed SDL3 against the `sdl3` pin;
  - the macOS app bundles `libSDL3` and nothing of `sdl2-compat`.
- `host-build`: the toolkit's POSIX graphics, input and audio dependency is SDL3.

## Impact

- **Hosts.** macOS (cat, b3, ssx3, jsrf: Metal present, the readback fallback, audio, pad, keyboard, mouse) and a native Linux build change. Windows, Proton, the Steam Deck and the steamos bundles do not link SDL and must come out with unchanged behaviour; the Deck's D3D11 golden shows that. No render path changes: the change is Present, input and audio output only.
- **Goldens:**
  - Metal goldens on the Mac. Pace is the only thing that can move, because frames are never read through SDL.
  - D3D11 goldens on the Deck via `blinx2 bench golden`, expected identical.
  - No CPU goldens: the SDL renderer block is verified through Metal's readback mode and the dummy-video fallback, and one Mac CPU check follows the merge.
- **Audio.** `audio_check.py` runs on the Mac headless. One run with real sound needs the user's go-ahead; it also gives the tracker item its first number on the stream API.
- **toolkit** (`wt/sdl3/xboxrecomp`, `feat/sdl3-migration` off `posix-host/portability` 4559bae9 or later):
  - `src/video`: `fb_present_sdl.c`, `fb_present_metal.m/.h`, `CMakeLists.txt`;
  - `src/apu`: `apu_sdl2.c` → `apu_sdl.c`; `apu_xaudio2.h` (`XA2_BACKEND_NAME`, which `apu_core.c:576` prints as `[APU] Using SDL2 audio backend`, and the comments at :11 and :106); the comments in `apu_xaudio2.c` (:17-18, :280) and `apu_core.c:794`; `CMakeLists.txt`;
  - `src/input`: `xinput_device.c`, `input_map.h/.c`, `keyboard_sdl.c/.h`, `mouse_sdl.c/.h`, the comments in `input_backend.h:3` and `xinput_xbox.h:87`, `README.md`, `CMakeLists.txt`;
  - `src/d3d`: `d3d8_gl.c`, `CMakeLists.txt`;
  - `src/platform/sdl_env.h` (new);
  - tests: `input_keyboard_sdl`, `input_hotplug_sdl`, `sdl_env` (new), `posix_ctest.sh`;
  - scripts and docs: `tools/linux/install_deps.sh`, `tools/macos/setup.sh`, `docs/GETTING_STARTED.md`, `docs/runtime/config.md`, `README.md`, `CHANGELOG-blinx2.md`;
  - the comment-only mentions in `win32_compat.c/.h`, `recomp_env.h` descriptions and `templates/new-game/CMakeLists.txt:117`.

  Then a public `blinx2/portability` push and tag (memory *public-push-authorized*).
- **CLI** (`wt/sdl3/xboxrecomp-cli`, `feat/sdl3-migration` off `main` 85e24c9 or later):
  - code: `doctor.py`, `setup.py` (host blockers), `pins.py`, `fetch.py` (tolerates the new entry), `manifest.py`, `golden_run.py`, the `package/lib.py` docstring;
  - docs: `docs/manifest.md`, `docs/porting.md`, `docs/wizard.md`;
  - tests: Python tests and fixtures;
  - wizard (Go): fixtures only, gated by `wizard/check.sh`.

  A tagged release follows, because games pin the CLI by tag.
- **Games** (one branch per repo, after the toolkit tag and the CLI tag):
  - cat: `game.toml`, `config/setup-pins.json`, docs, scripts, comments, TASKS;
  - b3: `game.toml`, docs, packaging, `scripts/race_gate.py`;
  - ssx3 and jsrf: `game.toml` and docs. ssx3 drops its companion; it also moves from `blinx2-v0.5.0`;
  - ssx3, jsrf and spartan: the `(SDL2,` comment at `CMakeLists.txt:123`, copied from the toolkit's template.
- **Other changes:**
  - `ipados-port` 0.1 records the merge;
  - `audio` (open): this change's `audio` delta modifies the requirement its delta adds, so this change archives after it;
  - `enhance-menu-preview`: its SDL2 wording in spec, design, tasks and `assessment.md` follows (task 13.4); phase 3A starts after this;
  - `fps-pacing` 8.10 shares the sound run.

## Status

- **2026-10-06:** proposed, then parked the same day before any code.
- **2026-10-11:** re-scoped against toolkit f8696da (cat `feat/sdl3-migration` f217dde).
- **2026-10-21:** refreshed against the bases above, with no code.

Spike: `spike.md` in this change (moved from `openspec/changes/sdl3-spike/`). Implementation the tracker item (Backlog; it absorbed the tracker item, which is done). The overlay items the tracker item..292 are blocked by it.
