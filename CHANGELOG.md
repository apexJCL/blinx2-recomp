# Changelog

What changed for players in each release of the BLiNX 2 static
recompilation, newest first, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are
tagged `vYEAR.MONTH.N`, with `-rc.N` for release candidates, and each
release's section is its notes on the
[releases page](https://github.com/apexJCL/blinx2-recomp/releases).
No release contains game data: you build the game from your own disc.

## [Unreleased]

### Changed
- **The cache partition lives in memory** (`storage.ram_cache = true`, the
  toolkit's new default for every game): what the game writes to its
  scratch cache drive while it plays stays in RAM, up to the console's
  750 MB, instead of being rewritten on your disk. The game sees the same
  files. `ram_cache = false` under `[storage]` in `config/config.toml`
  puts them back on the disk.
- **The real audio DSP, on by default.** The game's own sound programs now
  run on the emulated Xbox audio DSP: the reverb, the effect sends and the
  game's own mix, instead of a plain stereo fold. Want the old sound back?
  Put `RECOMP_APU_DSP=0` in `config/launch.env`.

### For developers

- The APU DSP default moved into the toolkit: `XBOXRECOMP_APU_DSP`
  defaults ON where a dsp56300 archive exists, and the exe runs the JIT
  unless `RECOMP_APU_DSP=0`. `CMakeLists.txt` drops its own migration and
  set, keeping only the hand-over of `CAT_APU_DSP_MIGRATED`, so a tree's
  OFF stays OFF. The CLI shares one dsp56300 download per game in
  `third_party/dsp56300`.

## [2026.10.4] - 2026-10-29

**CRT shaders, an in-game menu and a lighter Steam Deck.** Everything new is
off until you turn it on, except the menu, and the menu only shows when you
open it.

- **CRT looks.** Shadow mask, scanlines and a gentle curve on the final
  picture: `crt-lottes`, `crt-lottes-fast`, `crt-hyllian`, or AMD's `fsr`
  upscaler. Metal and Direct3D 11, with nothing extra to install on
  Windows.
- **A Shaders page.** Pick a shader in the menu and tune its curvature,
  mask, scanlines and bloom live, with a Reset to preset. Save keeps only
  what you changed. The page shows only where this system can run the
  shaders.
- **An in-game menu, on by default.** F10, Guide+A or Back+L3 held for a
  moment (and an Elite's P1 on macOS) opens it over the game: change the
  options while you play, rebind the host actions, turn mods on or off. On
  a Steam Deck, SteamOS keeps Guide+A: use Back+L3, or bind R4 to F10 once
  in Steam Input.
- **A stats strip.** F3 shows fps, frame time, pacing, scale and backend in
  the corner.
- **Lighter on the Steam Deck.** A heavy frame's draw work went from about
  18.5 to 14.4 ms.
- **Render scale switches at once.** Textures stay loaded when you change
  the scale, on Metal and Direct3D 11.
- **Clean 2D at high scales.** "2D on guest grid" (`render.snap_2d`, on
  the menu's Render page) removes the seams in loading screens and HUD
  tiles at scale 2 and up.
- **Character detail mod.** On the Mods page: characters keep their
  detailed models further away, following the render scale.
- **Borderless fullscreen on macOS.** No separate Space, and Cmd-Tab away
  and back just works.
- **The far sea fills widescreen.** The distant sea now reaches the
  edges at 16:9 and wider.
- **Nintendo pads by position.** On macOS and Linux, Switch Pro and
  GameCube pads map like an Xbox pad: the right face button is B whatever
  its label says. Windows is unchanged.
- **Heads-up:** if you edited `[input.bindings]` or `[input.actions]` in
  `config/config.toml`, some names changed. See below.

### Breaking: new names for controls and keys

The game now uses upstream xboxrecomp's names in `[input.bindings]` and
`[input.actions]`. The old names are not read any more: rewrite your own
lines with the table below (`config.default.toml` is updated for you).
Until you do, each old name logs an `unknown control`, `unknown input` or
`unknown name` line, and:
- an old control name (`ltrigger = ...`) is ignored, and that control
  keeps its default;
- an old key name is skipped but the rest of the line still applies, so a
  line left with no valid entries unbinds that control
  (`start = "KPEnter"` leaves Start with no key);
- an action line such as `menu.open` keeps only its valid entries.

| Old | New |
|---|---|
| `ltrigger` `rtrigger` | `left_trigger` `right_trigger` |
| `lthumb` `rthumb` | `left_thumb` `right_thumb` |
| `lstick_up` `lstick_down` `lstick_left` `lstick_right` | `left_stick_up` `left_stick_down` `left_stick_left` `left_stick_right` |
| `rstick_up` `rstick_down` `rstick_left` `rstick_right` | `right_stick_up` `right_stick_down` `right_stick_left` `right_stick_right` |
| `back+lthumb@400` (the menu chord) | `back+left_thumb@400` |
| `KP0` .. `KP9` | `Numpad0` .. `Numpad9` |
| `KPEnter` `KPPlus` `KPMinus` | `NumpadEnter` `NumpadAdd` `NumpadSubtract` |
| `KPMultiply` `KPDivide` `KPPeriod` | `NumpadMultiply` `NumpadDivide` `NumpadDecimal` |
| `LBracket` `RBracket` | `LeftBracket` `RightBracket` |
| `MouseLeft` `MouseRight` `MouseMiddle` | `Mouse1` `Mouse2` `Mouse3` |

Every other name works as before (`Return`, `Esc`, `Mouse4`, `WheelUp`
...), and `Pause`, `CapsLock` and `Control` are new. `RECOMP_TRACE=key`
prints each key by its new name (`[KEY] down enter`). The full list is in
`docs/input.md`.

### For developers

- **Pins:** xboxrecomp-cli v0.16.0 and toolkit blinx2-v0.9.0, up from v0.10.1
  and blinx2-v0.6.0. The toolkit now carries upstream xboxrecomp v0.15.0
  and v0.16.0, and the POSIX hosts link SDL3 instead of SDL2.
- **Why the menu is on by default:** closed, it draws nothing and takes no
  input but the Guide+A and Back+L3 chords, and players should find F10
  without editing a file. A Deck A/B at stage 1 read 30.00 flips/s with it
  on and 29.99 off. `enabled = false` under `[menu]` turns it off; the
  goldens run with `RECOMP_MENU=0`. Every other new option stays off by
  default.
- **Why the rename breaks old configs:** one vocabulary with upstream
  means every game on the toolkit reads the same file the same way. An
  old name is refused and named in the log, never guessed at.
- **Shaders:** `present.shader` (`RECOMP_PRESENT_SHADER`, default `none`)
  runs a RetroArch slang preset through librashader v0.12.0 at present.
  The library is fetched at build time, pinned by sha256, and loaded at
  run time, never linked: without it the game logs one line and looks
  stock. On x86-64 Windows it is the toolkit's own D3D11-only build of the
  unmodified v0.12.0 source, which imports only system DLLs, so it runs
  on a stock Windows 11 without D3DX9 or the Visual C++ runtime. The CPU
  renderer ignores it.
- **Licences:** every package carries the full third-party notices. The
  Windows exe's MinGW-w64 and llvm-mingw runtime terms are in `LICENSES/`
  with a `NOTICE` naming what each one links; the macOS app ships each
  bundled dylib's licence in `Resources/LICENSES` with
  `BUNDLED-LIBRARIES.md`; librashader's MPL-2.0 text and crate notices sit
  in `shaders/`.
- **Shader parameters:** the Shaders page reads each preset's
  `#pragma parameter` table and sets values live on Metal and D3D11.
  Overrides live in `[present.shader_params.<preset>]` as
  `<param> = <number>`, and `RECOMP_MODS_DESCRIBE=json` lists every
  bundled preset's parameters. My wrapper presets calm the curvature
  (crt-lottes `warpX` 0.031 to 0.01, `warpY` 0.041 to 0.02; crt-lottes-fast
  `CURVATURE` 0.02 to 0.01); the vendored upstream files are untouched.
- **No fringing under gamescope:** with a shader running, the present
  surface is the output, not the 640x480 frame, so gamescope no longer
  rescales the mask and scanlines by a non-integer factor.
- **Deck draw cost:** D3D11 skips unchanged vertex constants and
  output-merger state, and the pushbuffer decode and per-batch setup are
  memoised within a flip (Metal gets the constant-upload skip too).
  `RECOMP_D3D11_MEMO=0` turns the skips off for A/B runs.
- **Audio:** the stub fix promised in v2026.10.3 ships: the stub re-arms
  its interrupt only when the sequencer is switched off, so the game's
  audio recovery runs once per boot, not about 23 times a second. The
  emulated audio DSP (MIT dsp56300 JIT) is now compiled into every build,
  but the stub stays the run-time default until the DSP shows no frame-rate
  cost; `RECOMP_APU_DSP=1` turns it on.
- **cpuid:** the game sets `RECOMP_CPUID_NO_SIMD=1` by default again. The
  v0.16 toolkit reports MMX and SSE in cpuid, and the game's MMX JPEG
  decoder has not been checked lifted yet; `RECOMP_CPUID_NO_SIMD=0`
  reports them.

## [2026.10.3] - 2026-10-21

**Updating works again.** If v2026.10.2 failed to build when you updated an
older install, run this release's wizard and choose Update.

- **Updates that build.** The wizard now moves the toolkit to this
  release's version before it builds, so an update no longer compiles
  against old code.
- **Clearer build errors.** When a build fails, the wizard shows the
  compiler's error lines first, not just the end of the log.
- **Widescreen and free camera, documented.** The README now has sections
  and screenshots for `[display] aspect` (Hor+ 16:9, 16:10, 21:9) and the
  free camera (F6), plus the new options in the settings table.

### For developers

- **Pins:** xboxrecomp-cli v0.10.1 and toolkit blinx2-v0.6.0 (unchanged),
  so the game runs the same code as v2026.10.2.
- **Why updates broke:** setup only checked that a toolkit clone existed.
  An update moved the `[toolkit]` pin but kept the clone at the first
  setup's tag. The CLI now marks the clones it makes and moves a marked
  clone to the pin (a developer's own checkout is left alone), and
  `doctor` reports a clone that is off its pin.
- **New release gate:** `scripts/release_build_check.py` builds a clone of
  the previous release, updates it in place and packages it, the path
  that broke. It reproduces the v2026.10.1 → v2026.10.2 failure, and
  `docs/packaging.md` runs it before every tag.
- **Coming next, already merged in my toolkit:**
  - **Audio stub fix.** The stub that stands in for the audio DSP re-armed
    its interrupt on every recovery, so the game ran its audio recovery
    about 23 times a second. It now runs once per boot. It ships in the
    next toolkit release.
  - **An emulated audio DSP**, opt-in at build time and at run time. The
    stub has no DSP, so games lose reverb and 3D effects, surround is
    folded to stereo, and Burnout 3's menu music is silent. The real
    programs now run on the MCPX's two DSPs through the MIT-licensed
    dsp56300 JIT. It stays opt-in until the goldens and the Deck and
    Windows numbers show it costs no frame rate. Licence rule: permissive
    or LGPL code only, no GPL, so the glue is written from hardware facts,
    not from xemu's GPL files.
  - **Groundwork for a native Linux build** (x86-64 MMIO handling). The
    plan: native by default on SteamOS with Proton as the opt-in, after
    the move to SDL3.

## [2026.10.2] - 2026-10-21

Widescreen, a free camera and a friendlier build wizard. Built with
xboxrecomp-cli v0.10.0 and the toolkit at blinx2-v0.6.0. Every new option
is off by default, so the game looks and plays as before until you turn
one on in `config.toml`.

### Added
- Hor+ widescreen on Metal and Direct3D 11: `[display] aspect = "16:9"`
  (or `"16:10"`, `"21:9"`) shows more of the world at the sides instead of
  stretching it. The HUD keeps its 4:3 layout, and `movie` chooses how
  the cutscene movies fill the wider frame (`"black"`, `"fit"`, `"fill"`).
- A free camera: `[camera] free = "on"`, then F6 starts and stops it. Fly
  with the pad or the mouse while BLiNX stands still; F8 stops and
  restarts the world, F7 shows or hides the HUD and F5 goes back to the
  game's camera. The keys and speeds are in `config.default.toml`.
- `[display] overscan` crops the edges of the picture, as a TV did, for
  games that leave a border there. 0 (the default) shows the whole frame.
- The build wizard can build for several platforms in one go, and its
  Welcome page, Fresh and Update choices and error messages are clearer.

### Fixed
- Audio under Proton (Steam Deck, Linux) has a deeper buffer, which
  removes the occasional crackle when the game is idle.
- macOS: events the game sets and resets in quick succession now wake
  every thread waiting on them, as on Windows.

## [2026.10.1] - 2026-10-17

Updates are now patches: from this release on, the build wizard
rebuilds only what changed and installs it over your current version,
instead of downloading and building the whole game again. Built with
xboxrecomp-cli v0.8.0 and the toolkit at blinx2-v0.5.1.

### Added
- Incremental builds and patch installers. Rebuilding gives the same
  files byte for byte, so an update ships only the files that differ
  from your installed version. A 2026.10.0 install can take this
  release as its first patch; on Windows, the first update moves the
  install to the new versioned layout and may be a full install once.
- `docs/frame-generation.md`: how to get a 60 fps look with outside
  frame-generation tools (Lossless Scaling, lsfg-vk) while the game
  itself runs at its stock 30 fps.

### Fixed
- Direct3D 11 and Metal: texture-shader clip planes now cut what they
  should, as the software renderer already did. No BLiNX 2 scene seen
  so far uses them, so nothing in the game is expected to look different.

### Known issues
- The game crashed once in stage 5-1 on macOS, after about 90 seconds;
  it has not happened again in later runs and is still being watched.

## [2026.10.0] - 2026-10-17

The first stable release. It builds and installs the game from your own
disc image with the build wizard for Windows, macOS and Linux (Steam Deck
included), and fixes what the release candidates left open. Built with
xboxrecomp-cli v0.7.7 and the toolkit at blinx2-v0.5.0.

### Added
- Anisotropic filtering: `aniso` under `[render]` in
  `config/config.toml` (2 to 16; 0, the stock look, by default) sharpens
  ground and walls at a distance, on Direct3D 11 and Metal.

### Fixed
- The game no longer freezes after the Tom Tom Gang rank exam.
- macOS: the game no longer crashes when started from the Finder,
  including the first boot with no saves.
- Steam Deck: controllers work again. The Proton release the bundle used
  started no controller driver, so the game saw no pads; the Deck build
  now uses GE-Proton11-7, which updating downloads once.
- Steam Deck: a second launch while the game is starting says so instead
  of starting it twice, and the "Checking the Steam Linux Runtime" notice
  shows only once.
- Controllers: a pad connected after launch on macOS and Linux is picked
  up, and a replugged pad takes its old port back. A controller on a
  second slot (Steam Deck Desktop Mode) now reaches player 1.
- The stage 1 ocean and the Boss 3 ripple draw their bump-mapped
  surfaces instead of a plain texture. The Direct3D 11 side is by
  [@hgeorgilas](https://github.com/hgeorgilas).
- The characters on the Story Mode menu no longer go missing.
- Sound: a voice the game is still updating no longer plays as a short
  burst, and a wide ADPCM block no longer overruns the decoder. Both
  fixes build on Matt Graham's ([@MattSG](https://github.com/MattSG))
  voice processor work in upstream xboxrecomp
  ([#217](https://github.com/sp00nznet/xboxrecomp/pull/217)); he
  co-authors them.
- The game's cache files no longer share a folder with the hard disk's
  cache partitions, where they could collide.

### Known issues
- The game crashed once in stage 5-1 on macOS, after about 90 seconds;
  it has not happened again in later runs and is still being watched.

## [2026.10.0-rc.2] - 2026-10-15

### Added
- The wizard's Building page lists each part of the build in order, with
  its own progress, time and log, and shows that the build is still
  working during the long, quiet recompile step.
- You choose where the finished build goes; by default it is a folder
  beside the wizard, not hidden in your user data.
- When a build fails, the wizard shows which step failed, an excerpt of
  its log and the folder with the full logs.
- Credits for this project, the tools it is built with and the
  third-party software, with their licences in `NOTICES.txt`.
- The wizard has a gamepad icon on every platform.

### Changed
- The font hint for the sharper HUD appears only when the font is
  missing, with a link to get it.
- Stopping a build asks first and says what a new run will reuse.
- Releases carry these notes, and release candidates are marked as
  pre-releases.
- Built with xboxrecomp-cli v0.7.5 and the toolkit at blinx2-v0.3.1
  (unchanged).

### Fixed
- The build wizard now builds on Windows. In rc.1 a Windows build stopped
  while packaging; the setup program's disk space estimate also left out
  the game files.

## [2026.10.0-rc.1] - 2026-10-15

The first release with downloads: a build wizard for Windows, macOS and
Linux (Steam Deck included) that builds and installs the game from your
own disc image. Built with xboxrecomp-cli v0.7.2 and the toolkit at
blinx2-v0.3.1.

### Added
- The build wizard: download the one for your system, point it at your
  disc image or dump folder, pick the options, and it fetches the tools,
  builds the game and installs it. Options: render scale (1x, the stock
  640x480, up to 4x), fullscreen, and a sharper HUD and menus redrawn
  from your own game files.
- Building by hand in one command from a disc image (`.iso`) or a dump
  folder: `./blinx2 /path/to/BLiNX2.iso`.
- Bundles for the Steam Deck and Linux (Direct3D 11 under Proton), macOS on
  Apple silicon (Metal) and Windows (Direct3D 11).
- Controllers, keyboard and mouse, with keys you can rebind in
  `config/config.toml`.
- Settings in `config/config.toml` that survive updates, over the stock
  `config.default.toml`.
- Frame pacing that sleeps between frames by default, which frees a CPU
  core; the console's busy wait is one setting away.

### Fixed
- The freezes on the results screen after mission 1 and after the
  mission 3 boss, and the freezes in stage 5-1.
- Dark ground and water on multi-core PCs, and the stutter when
  wading in stage 1.
- The frame rate on Windows, which heavy logging had slowed.
- Windows builds use the XInput that every Windows install ships.

### Known issues
- The Windows wizard's build stops while packaging (fixed in rc.2).
- Native Windows is otherwise tested under Proton only.
- Bump-environment mapping (the stage 1 ocean, the Boss 3 ripple) draws
  as a plain texture.
- A controller connected after launch is ignored on macOS: connect it
  first.
- The game crashed once in stage 5-1 on macOS, after about 90 seconds;
  this is being investigated.

[Unreleased]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.4...HEAD
[2026.10.4]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.3...v2026.10.4
[2026.10.3]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.2...v2026.10.3
[2026.10.2]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.1...v2026.10.2
[2026.10.1]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0...v2026.10.1
[2026.10.0]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.2...v2026.10.0
[2026.10.0-rc.2]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.1...v2026.10.0-rc.2
[2026.10.0-rc.1]: https://github.com/apexJCL/blinx2-recomp/releases/tag/v2026.10.0-rc.1
