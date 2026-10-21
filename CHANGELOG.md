# Changelog

What changed for players in each release of the BLiNX 2 static
recompilation, newest first, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are
tagged `vYEAR.MONTH.N`, with `-rc.N` for release candidates, and each
release's section is its notes on the
[releases page](https://github.com/apexJCL/blinx2-recomp/releases).
No release contains game data: you build the game from your own disc.

## [Unreleased]

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

[Unreleased]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.2...HEAD
[2026.10.2]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.1...v2026.10.2
[2026.10.1]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0...v2026.10.1
[2026.10.0]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.2...v2026.10.0
[2026.10.0-rc.2]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.1...v2026.10.0-rc.2
[2026.10.0-rc.1]: https://github.com/apexJCL/blinx2-recomp/releases/tag/v2026.10.0-rc.1
