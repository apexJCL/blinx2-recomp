## 1. Manifest

- [ ] 1.1 `game.toml` `[package]`: `brew = ["sdl3", "openssl", "libepoxy"]` and no `dylib_companions` SDL entry. Verify: `blinx2 doctor` names `sdl3` and never `sdl2`.
- [ ] 1.2 `game.toml` `[toolchain] sdl3` at the version the toolkit is tested with, then `xbr pins refresh` writes the `sdl3` entry into `config/setup-pins.json`. Verify: `blinx2 doctor` prints the `sdl3:` line against the pin.

## 2. Docs and scripts

- [ ] 2.1 `README.md`: SDL3 in the macOS platform row, `sdl3 <ver>` in the tested-with table, and `brew install sdl3 openssl libepoxy`.
- [ ] 2.2 `scripts/test_launchers.py` writes and checks `SDL_AUDIO_DRIVER=dummy`. `scripts/soak.py` and `scripts/shots/run.sh` use `SDL_AUDIO_DRIVER`. Verify: `uv run pytest scripts`.
- [ ] 2.3 `docs/env.md` lists `SDL_AUDIO_DRIVER` and `SDL_AUDIODRIVER`, the second as the alias, and `README.md`'s `RECOMP_HEADLESS` and no-sound rows use the SDL3 name.

## 3. Gates and archive

- [ ] 3.1 `blinx2 package macos`: `otool -L` of the app shows `libSDL3.0.dylib` under `Contents/Frameworks/` and nothing named `libSDL2`; the DMG launches with `RECOMP_WINDOW_QUIT_AFTER=10`. Then `sh notes/build-all.sh`.
- [ ] 3.2 Archive with `openspec archive sdl3-cat-manifest`. Verify: `openspec validate --specs`.
