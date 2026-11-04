# SDL3 manifest move for cat

## Why

The toolkit and the CLI moved to SDL3 in `sdl3-migration`
(`openspec/changes/archive/2026-11-03-sdl3-migration/`), and that change was
archived on 2026-11-03 with cat's own manifest move (its task 12.1 and part
of 12.2) still open. The requirements below were synced into the live specs
at the archive. They describe cat after that move, not cat today, so they
were taken back out and wait here until the move lands:

- `game.toml` `[package] brew` still lists `sdl2`, `dylib_companions` still
  carries `libSDL3.dylib=brew:sdl3`, and there is no `[toolchain] sdl3` pin
  (so `config/setup-pins.json` has no `sdl3` entry);
- `README.md` still names SDL2 (the platform table, the tested-with table
  and the `brew install sdl2 ...` line);
- `scripts/test_launchers.py` writes and checks `SDL_AUDIODRIVER=dummy`, and
  other cat scripts (`scripts/soak.py`, `scripts/shots/run.sh`) and docs
  (`README.md`, `docs/env.md`) use the SDL2 spelling.

## What changes

- `game.toml`: `brew = ["sdl3", "openssl", "libepoxy"]`, the companion
  removed, `[toolchain] sdl3` added, and `config/setup-pins.json` refreshed
  with `xbr pins refresh`.
- `README.md`: SDL3 in the platform table, the tested `sdl3` version, and
  `brew install sdl3 openssl libepoxy`.
- `scripts/test_launchers.py`, `scripts/soak.py`, `scripts/shots/run.sh`:
  `SDL_AUDIO_DRIVER`. `docs/env.md` lists both spellings and says
  `SDL_AUDIODRIVER` is the alias.

The other games (BLiNX 1, KUF, ssx3) make the same move through their own
sessions under the tracker item; this change covers cat only.

## Impact

Packaging and docs only: no goldens. Gates are a macOS package check
(`otool -L`, `Contents/Frameworks/` holds `libSDL3.0.dylib` and no
`libSDL2`), `blinx2 doctor`, `uv run pytest scripts`, ruff, and build-all.
