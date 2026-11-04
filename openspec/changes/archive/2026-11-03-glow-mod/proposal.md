## Why

The glow pass weight (`fx.glow`, `fx.glow_intensity`, archived change
`2026-10-07-glow-toggle`) was the project's first tweak, but it is two game
config keys read once at start: the menu's Mods page does not show it, a
change needs a restart, and the descriptor dump (`RECOMP_MODS_DESCRIBE=json`)
that a launcher reads does not list it. Every later tweak is a mod with a
descriptor (lod, hud, crystals); the glow should be one too (rule:
mods expose their settings).

## What Changes

- **A new cat mod, `glow`** (`src/glow_mod.c`; the weight maths stay in
  `src/glow.c`), mod API v4, with a descriptor:
  - `mods."glow.enable"`: enum `off`/`on`, default `on`, live, the mod's
    enable setting. Off means the stock glow, whatever the two below say.
  - `glow`: key `fx.glow` (the legacy spelling, kept), enum `off`/`on`,
    default `on`, live, env `RECOMP_GLOW`.
  - `intensity`: key `fx.glow_intensity` (kept), float 0..2, step 0.05,
    default 1, live, env `RECOMP_GLOW_INTENSITY`.
- **Live.** The `sub_0005B7D0` wrapper in `recomp_manual.c` scales the
  weight per call, so a change from the Mods page takes effect at the next
  frame (`on_setting`, `on_enable`).
- **Back-compat.** The keys keep their names, so a player's `[fx]` table,
  the env keys, the wizard and `config.default.toml` keep working with no
  rewrite. Precedence is the descriptor's: env, then the user file, then
  `config.default.toml`, then the default.
- **Stock stays stock.** At the defaults the wrapper never touches the
  guest, the mod reports itself idle (`api->active`) so `[ENHANCE] mods=`
  stays `none`, and the `[ENHANCE] fx.glow=on fx.glow_intensity=1` line the
  golden check reads is still printed. `game.toml`'s `enhance_stock` gains
  `mods.glow.enable = "on"`.
- A toolkit without mod API v4 keeps the old start-time read in `main.c`.

## Impact

- cat: `src/glow_mod.c`, `src/glow_mod.h` (new), `src/glow.c` (atomic
  state), `src/main.c`, `CMakeLists.txt`, `game.toml`,
  `packaging/config.default.toml`, `docs/env.md`, `CHANGELOG.md`,
  `scripts/test_glow.py`.
- No toolkit change. Goldens unchanged by construction (stock defaults).
