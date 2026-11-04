## 1. Mod

- [x] 1.1 `src/glow_mod.c`/`.h`: descriptor (enable, glow, intensity), init,
      `on_setting`, `on_enable`, `active`.
- [x] 1.2 `src/glow.c`: atomic state for the live path.
- [x] 1.3 `src/main.c`: register the mod; legacy read only without it; the
      `[ENHANCE] fx.glow=` line from glow.c's state.

## 2. Keys and docs

- [x] 2.1 `game.toml` `enhance_stock`: `mods.glow.enable = "on"`.
- [x] 2.2 `docs/env.md`, `packaging/config.default.toml`, `CHANGELOG.md`.
- [x] 2.3 `scripts/test_glow.py`: env rows, docs, descriptor, golden stock.

## 3. Gates

- [x] 3.1 pytest, ruff; Mac build; PC D3D11 golden.
- [x] 3.2 D3D11 dump A/B at a glow scene: glow off, intensity 2, mod off.
