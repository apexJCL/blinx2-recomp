## Context

`sub_0005B7D0` (post mode 3) draws the glow layer with the weight word
`0xADC744` as the quad's colour. `recomp_manual.c` wraps it and, when
`glow_active()`, scales the word by `cbrt(k)` for the call only
(`glow.c`). Until now `main.c` called `glow_configure(off, k)` once from
`fx.glow` and `fx.glow_intensity`.

## Decisions

- **D1: the glow's on/off is a setting, not the enable switch.** The mod's
  enable (`mods."glow.enable"`, default on, as `hud`) means "apply the glow
  settings"; off, or a mod never inited, is the stock glow. Making
  `fx.glow` the enable setting would invert the rule that a mod off is
  stock, and a mod left out at start (enable off with the menu off) would
  then draw the glow a player turned off.
- **D2: legacy key spellings.** The descriptor's `key` keeps `fx.glow` and
  `fx.glow_intensity` (as `camera.free_speed`), not aliases under
  `mods."glow.*"`: no player file is rewritten on Save, the wizard and the
  golden's `enhance_stock` keep their keys, and docs stay in one place.
- **D3: live through glow.c's state.** `on_setting` and `on_enable` run on
  the guest thread from `xbox_mod_frame` and call `glow_configure`; the
  wrapper reads the state with relaxed atomics (the factor as its bits), so
  a change lands at the next glow call. The pair can tear for one call at
  worst, which only draws one frame with the old value.
- **D4: step 0.05.** The descriptor snaps numbers to its step. Old values
  between grid points move by at most 0.025 (a weight-byte change of one at
  most), and the toolkit logs the snap; the menu moves in useful steps.
- **D5: idle in stock.** The mod calls `api->active(mod, glow_active())`,
  so `[ENHANCE] mods=` lists `glow` only while it changes the frame, and
  stock goldens keep `mods=none`.
- **D6: the [ENHANCE] line.** `main.c` prints
  `[ENHANCE] fx.glow=<on|off> fx.glow_intensity=<k>` after
  `xbox_enhance_init` from `glow.c`'s state, i.e. what the run uses (stock
  when the mod is held off), as the golden check expects.

## Risks

- A player value like 1.33 now runs as 1.35 (D4). Invisible in practice.
