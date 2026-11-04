## ADDED Requirements

### Requirement: One pinned SDL3 release, documented
`config/setup-pins.json` SHALL hold one SDL3 source release (version, URL, sha256, size) under `sdl3`, written by `xbr pins refresh` from the version in `game.toml` `[toolchain] sdl3`. Desktop builds SHALL use the package manager's SDL3 at or above the floor; `xbr doctor` (`blinx2 doctor`) SHALL print the installed version against the pin and warn, never fail, when its major.minor is older. Each game's `README.md` SHALL name the pinned version as the tested one.

#### Scenario: Doctor on an older Homebrew
- **WHEN** `blinx2 doctor` runs where `sdl3` is 3.2.x and the pin is 3.4.x
- **THEN** it reports macos as packageable and prints a warning naming both versions

#### Scenario: No pin
- **WHEN** a game's `game.toml` has no `[toolchain] sdl3`
- **THEN** `pins refresh` writes no `sdl3` entry and `doctor` prints the installed SDL3 version with no warning

## MODIFIED Requirements

### Requirement: SDL's environment variables keep their SDL2 spellings as aliases
The host layer SHALL read `SDL_AUDIO_DRIVER` and `SDL_VIDEO_DRIVER` (SDL3's names) and, before SDL is initialised, SHALL copy `SDL_AUDIODRIVER` and `SDL_VIDEODRIVER` into them when the SDL3 name is unset, through SDL's own environment API and never libc `getenv`. Headless runs (`RECOMP_HEADLESS=1`) SHALL set `SDL_AUDIO_DRIVER=dummy` unless either spelling already names a driver. Live documentation and scripts SHALL use the SDL3 names; `docs/env.md` SHALL list both and say which is the alias. The CLI's golden runner SHALL set both spellings, so one CLI release serves a game pinned to an SDL2 toolkit and one pinned to an SDL3 toolkit without playing sound on either.

#### Scenario: Old script
- **WHEN** a run is started with `SDL_AUDIODRIVER=dummy` and nothing else
- **THEN** the audio backend logs `driver dummy` and nothing is played

#### Scenario: SDL3 name wins
- **WHEN** both `SDL_AUDIODRIVER=coreaudio` and `SDL_AUDIO_DRIVER=dummy` are set
- **THEN** the dummy driver is used

#### Scenario: Unit test
- **WHEN** the toolkit's `sdl_env` ctest runs
- **THEN** it passes on macOS and Linux and fails if the alias copy is removed

#### Scenario: Golden runner on either toolkit
- **WHEN** `blinx2 golden run` builds a run's environment
- **THEN** it holds `SDL_AUDIODRIVER=dummy` and `SDL_AUDIO_DRIVER=dummy`
