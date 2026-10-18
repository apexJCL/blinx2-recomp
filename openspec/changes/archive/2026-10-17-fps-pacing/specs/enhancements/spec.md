## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`

#### Scenario: A plain run sleeps
- **WHEN** the game starts with no `present.pacing` key in either settings file and no `RECOMP_PRESENT_PACING`
- **THEN** the log reads `present.pacing=sleep`, and the frames and pace match a run at `spin`

#### Scenario: Legacy pin still stock
- **WHEN** `@stage1` runs with `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_CONFIG` unset, with a `config.default.toml` beside the executable that sets `scale = 2`
- **THEN** the log has one `[ENV] RECOMP_ENHANCE_CONFIG is deprecated; use RECOMP_CONFIG` line, reads no file, and shows `render.scale=1`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`, or `render.aniso=8`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

## ADDED Requirements

### Requirement: Frame pacing key
`present.pacing` (env `RECOMP_PRESENT_PACING`) SHALL select how lowered spin-wait loops wait: `"spin"` busy-waits as the console did, `"sleep"` blocks in the runtime wait (`frame-pacing`). The layer SHALL read it once at startup, before the guest starts, and SHALL report it on the `[ENHANCE]` settings line. Without the layer the mode SHALL be `spin`. With the layer the default SHALL be `"sleep"`, set by a commit that can be reverted on its own, and the game's shipped `config.default.toml` SHALL state the key (`pacing = "sleep"`) so that a bundle's default is the file's, not the toolkit's. The default was allowed to change only once `sleep` met the acceptance rule against `spin` on the same build: the same verdict for every golden frame on the Metal goldens and on the D3D11 goldens under Proton (a frame exact in every `spin` run exact in every `sleep` run); flips/s, interval p50/p95 and the anchors' flip indices of `@stage1` and `@story-hub` within `spin`'s own run-to-run spread; no new `[AUDIO-HOST]` starves; and, on Burnout 3 under Proton, the same screens at the same flips, the race pace within spread, and no site over 5% timeout exits. The golden pins stay at `spin`.

#### Scenario: Sleep is the default
- **WHEN** the shipped `config.default.toml` has `[present] pacing = "sleep"`, the player's `config/config.toml` has no `pacing` key and no `RECOMP_PRESENT_PACING` is set
- **THEN** the `[ENHANCE]` line reads `present.pacing=sleep`, and the `pacing` trace reports `mode sleep` with wakes counted at site `0x00060475`

#### Scenario: Console-original timing on request
- **WHEN** the player puts `[present] pacing = "spin"` in `config/config.toml`, or sets `RECOMP_PRESENT_PACING=spin`
- **THEN** the `[ENHANCE]` line reads `present.pacing=spin`, the lowered loop busy-waits, and the `pacing` trace reports `mode spin` with no site counters

#### Scenario: Flip reverted
- **WHEN** the default-flip commits are reverted (the toolkit's and cat's)
- **THEN** the default is `"spin"` again in the code and in `config.default.toml`, and the golden configuration is unchanged

### Requirement: Packaged bundles say how to get the console-original pacing
When the game's `config.default.toml` staged into a bundle sets `[present] pacing = "sleep"`, `package` SHALL add one paragraph to the bundle's README.txt, after the paragraph on the two settings files, and SHALL print one note after the `bundle:` line. Both SHALL say that frame pacing defaults to `sleep` (the frame wait sleeps until the next vblank, which saves CPU and battery), that `spin` is the console-original timing (the wait holds a CPU core as on the Xbox), and how to select it: `pacing = "spin"` under `[present]` in `config/config.toml`, or `RECOMP_PRESENT_PACING=spin` in `config/launch.env`. When the file sets `"spin"` or has no `pacing` key, neither SHALL appear. A defaults file the CLI cannot parse SHALL produce one `WARNING:` line naming the error and no note. The note SHALL NOT be shown by a launcher or on game start. The CLI SHALL hold no game name or toolkit default for this: the text is game-agnostic and the condition is the game's own file.

#### Scenario: BLiNX 2 bundle
- **WHEN** `blinx2 package` runs with `packaging/config.default.toml` at `pacing = "sleep"`
- **THEN** the bundle's README.txt holds the frame-pacing paragraph with `pacing = "spin"` and `RECOMP_PRESENT_PACING=spin`, and the command prints the note once under `bundle:`

#### Scenario: A game that ships spin
- **WHEN** a game's `config.default.toml` has `pacing = "spin"`, or no `[present] pacing` key
- **THEN** README.txt has no frame-pacing paragraph, no placeholder is left in it, and nothing is printed about pacing

### Requirement: Frame-rate mode reports what is available
The title SHALL read `fps.mode` (env `RECOMP_FPS_MODE`, choices `lock30`, `lock60`, `free`, default `lock30`) before the layer reports unused keys. `lock30` SHALL run the game's own pacing and log `[ENHANCE] fps.mode=lock30`. `lock60` and `free` SHALL each log exactly one line saying the mode is not available for this title and why, and then run `lock30`, writing nothing to guest memory. A value outside the choices SHALL be reported once by the layer and treated as the default.

#### Scenario: lock60 asked for
- **WHEN** BLiNX 2 starts with `RECOMP_FPS_MODE=lock60`
- **THEN** the log has one line `[ENHANCE] fps.mode=lock60 not available for this title (...); using lock30`, the game runs at its stock 30 fps in 3D, and frames match a `lock30` run

#### Scenario: Key in the file is not reported unused
- **WHEN** `enhance.toml` sets `[fps] mode = "lock30"`
- **THEN** the unused-key report does not list `fps.mode`
