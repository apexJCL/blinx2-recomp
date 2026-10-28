## Context

The tracker item (spike, `spike/lod`, no code) located the LOD choice:

- `sub_0019A2C0` projects a fixed sphere (centre y+5, radius 10) and gets its
  screen radius r in 640x480 units. Two players and up: r × 0.6; mode 10
  with 3 or 4 players: r × 0.75 and a level cap.
- The loop at `0x19A460` compares `fild [0x450B08 + i*8]` with r for
  i = 0..4 (signed int32 thresholds) and takes `[0x450B0C + i*8]` from the
  first threshold above r; past i = 4 it keeps the default, 5. The
  `9999` entry is never read.
- Only `sub_0019A2C0` reads the table. Its 11 callers store
  `visible ? level : 0` into object `+0x2B4`; the draw (`sub_0018CBD0`)
  uses it for node ranges, animation snapping, the face pass and the drop
  shadow; game logic (`sub_00143F80`) only tests `== 0`.

The mod API v3 (toolkit 8fb88c79, cat 7e3910c) gives a descriptor, live
settings through `setting` and `on_setting`, `on_enable` and guest memory.

## Goals / Non-Goals

Goals: full-detail characters at 2x and 3x at the same on-screen size as at
480p; opt-in, live from the menu; stock untouched when off.

Non-goals: changing visibility or game logic (threshold 0, the multiplayer
factors, the mode-10 cap); per-level tuning; a toolkit change.

## Decisions

### D1. A descriptor mod `lod`, default off

Mod id `lod`; settings without `key`, so their keys are
`mods."lod.enable"`, `mods."lod.follow_scale"`, `mods."lod.distance"`.

| Setting | Kind | Range | Default | Live | Env |
|---|---|---|---|---|---|
| `enable` | enum off/on, `XBOX_SET_ENABLE` | | off | LIVE | `RECOMP_LOD` |
| `follow_scale` | bool | | true | LIVE | `RECOMP_LOD_FOLLOW_SCALE` |
| `distance` | float | 0.5..4 step 0.25 | 1.0 | LIVE | `RECOMP_LOD_DISTANCE` |

The env rows exist for bench and A/B runs (config tier; an env-set value is
read-only on the Mods page, as for every descriptor setting).

Left out, with the reason (mods expose every sensible setting):
- per-level thresholds: four numbers with no visible meaning to a player;
  `distance` scales them all;
- threshold 0: game logic reads level 0 (D4);
- the multiplayer factor: the game's own split-screen budget;
- controls: nothing to bind; the Mods page toggles it.

The enable setting is an enum `off`/`on` like `camera.free`, so the
`[ENHANCE] mods.lod.enable=off` line reads like the other game keys.

### D2. The render scale: polled each frame, no toolkit change

`render.scale` is a live (FLUSH) menu item, and the API has no event for it.
The mod's `on_frame` reads `nv2a_host_render_scale()` (declared in
`nv2a_backend_common.h`, which `mod.h` includes): one load per frame. A
change event in the API for a single consumer is not worth a toolkit change;
if a second mod wants it, it becomes an API v4 field.

`nv2a_host_render_scale()` is the scale asked for, not the one drawn. The
CPU rasteriser may draw at less, and D3D11 clamps the target when the scale
would pass its largest texture size (`nv2a_host_size`, MAX_DIM); then the
mod keeps detail further out than the drawn resolution needs. That costs
draws, never looks worse, and is accepted. The switch's help says it follows
the render scale setting.

### D3. When and where the table is written

All writes run on the guest's thread, from `on_frame`; the `on_enable`
callback, which the toolkit calls from the same `xbox_mod_frame`, only flips
the mod's switch. The settings are read through `setting` each frame along
with the scale, so the mod needs no `on_setting` callback. So a write never lands inside a frame's draw pass on that
thread. The four words are aligned int32 stores; even a reader on another
thread would at worst see one frame with a mix of old and new thresholds,
which only picks a neighbouring level for that frame.

The mod keeps `want` (the table its settings and the scale give) and
`have` (what it last wrote). Each frame it recomputes `want`; it writes only
when they differ, so the steady state is four compares.

### D4. Thresholds

`t_i = max(1, lround(stock_i / (s × d)))` for i = 1..4, stock
24, 48, 80, 160; `s` = render scale when `follow_scale`, else 1; `d` =
`distance`. Threshold 0 stays 8.

- 1x, d 1: stock (the mod on at 1x changes nothing).
- 2x: 12, 24, 40, 80. 3x: 8, 16, 27, 53 (the spike's values).
- The divided values stay non-decreasing, since the stock ones increase and
  share one divisor.
- When `s × d` reaches 3, `t_1` is at most 8 = `t_0`, so level 1 is never
  picked (r < 8 already gives level 0 from `t_0`). Level 1 is a tiny-model
  level that small, so it is accepted: the visible levels 2..4 still move.
- `d` < 1 raises the thresholds (detail drops nearer than stock at 1x). Kept:
  a player on a slow host may want it.

### D5. Guards

- Before the first write in a run, the mod reads the ten words at
  `0x450B08..0x450B2C`. Unless they are (8,0) (24,1) (48,2) (80,3) (160,4),
  it logs `table at 0x450B08 is not the stock one; left alone` and never
  writes (another XBE, or a `RECOMP_DEBUG=poke` run).
- Before each later write it checks thresholds 1..4 still hold `have`. If
  not (a poke, a debugger), one line and it stops writing for the run.
- Off (setting, Mods page, `mods.lod.enable = off`) writes the stock values
  back when the table holds `have`. Once stopped, the mod never writes
  again, restore included: values it did not put there are not its to undo.
- Shutdown restores stock too, best effort: it may run on the exit hook's
  thread while a mod frame is in flight, which can write its values again.
  Guest memory goes with the process, so it does not matter.
- These rules are pure C (`lod_step` in `src/lod_table.c`, over the ten
  table words), so `scripts/test_lod_scale.py` drives them on a simulated
  table; `src/lod_scale.c` only maps the guest's table and logs the result.

### D6. Logging

The toolkit prints `[ENHANCE] mods.lod.enable=off|on` at start. The mod logs
one `[MOD lod]` line per table change: `thresholds 8/12/24/40/80 (scale 2,
distance 1)`, and `stock thresholds back` when turned off. A golden run with
the mod off prints none of them.

### D7. Goldens

`game.toml` `enhance_stock` gets `"mods.lod.enable" = "off"`, so a golden
run with the mod on fails the stock check. Goldens are unchanged when off:
the init either does not run (menu off) or runs dormant and writes nothing.

## Risks / Trade-offs

- **Draw cost** on the Deck, which is draw-bound in the hub.
  Opt-in, measured and reported per the 25% rule; `distance` < 1 trims it.
- **Mixed thresholds for one frame** after a change: harmless (D3).
- **Polling the scale** reads a plain unsigned written by the menu thread:
  the same racy-but-benign read the backends do.
