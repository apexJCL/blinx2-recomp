# Changelog

What changed for players in each release of the BLiNX 2 static
recompilation, newest first, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are
tagged `vYEAR.MONTH.N`, with `-rc.N` for release candidates, and each
release's section is its notes on the
[releases page](https://github.com/apexJCL/blinx2-recomp/releases).
No release contains game data: you build the game from your own disc.

## [Unreleased]

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

[Unreleased]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.2...HEAD
[2026.10.0-rc.2]: https://github.com/apexJCL/blinx2-recomp/compare/v2026.10.0-rc.1...v2026.10.0-rc.2
[2026.10.0-rc.1]: https://github.com/apexJCL/blinx2-recomp/releases/tag/v2026.10.0-rc.1
