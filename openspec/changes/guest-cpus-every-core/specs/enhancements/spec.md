## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `display.aspect`, `display.movie`, `display.overscan`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` in every non-Windows build. BLiNX 2's Windows build is not an exception: it defaults to the stock `"spin"` (the per-build default of the requirement Frame pacing key; the user, 2026-11-05). `sleep` became the toolkit's default by the user's decision of 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL either return the stock value with every key at its default (as `nv2a_present_crop` does at `display.overscan = 0`: the whole frame, its stock UV scale and a zero offset, so the blit samples the same UVs) or be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, `display.overscan` is above 0, `display.aspect` is wider than 4:3 (a target with a non-zero `nv2a_host_pad`), a texture pack is loaded, or the frame and the output differ in size; `display.movie` acts only on a padded target. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 and pad 0 return their inputs, every Hor+ placement at pad 0 leaves the stock constants, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although `present.pacing` defaults to `sleep` in every non-Windows build, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect`, `display.overscan` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`, with no `hor+` line

#### Scenario: A plain run sleeps
- **WHEN** a non-Windows build starts with no `present.pacing` key in either settings file and no `RECOMP_PRESENT_PACING`
- **THEN** the log reads `present.pacing=sleep`, and the frames and pace match a run at `spin`

#### Scenario: A plain Windows run spins
- **WHEN** BLiNX 2's Windows build starts, natively or under Proton, with no `present.pacing` key in either settings file and no `RECOMP_PRESENT_PACING`
- **THEN** the log reads `present.pacing=spin`, the stock value

#### Scenario: Legacy pin still stock
- **WHEN** `@stage1` runs with `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_CONFIG` unset, with a `config.default.toml` beside the executable that sets `scale = 2`
- **THEN** the log has one `[ENV] RECOMP_ENHANCE_CONFIG is deprecated; use RECOMP_CONFIG` line, reads no file, and shows `render.scale=1`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 and pad-0 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_host_pad`, `nv2a_present_rect` for an exact fit, the occlusion scaling, `nv2a_aspect_map` and `nv2a_aspect_box` at pad 0) returns its input or the stock constants unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`, or `render.aniso=8`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a wide run
- **WHEN** `golden.py` evaluates a run whose log contains `display.aspect=16:9`
- **THEN** the run is marked FAIL with a reason naming `display.aspect`, and its frames are not compared

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

### Requirement: Frame pacing key
`present.pacing` (env `RECOMP_PRESENT_PACING`) SHALL select how lowered spin-wait loops wait: `"spin"` busy-waits as the console did, `"sleep"` blocks in the runtime wait (`frame-pacing`). The layer SHALL read it once at startup, before the guest starts, and SHALL report it on the `[ENHANCE]` settings line. Without the layer the mode SHALL be `spin`. With the layer the toolkit's default SHALL be `"sleep"`, set by a commit that can be reverted on its own. The default was allowed to change only once `sleep` met the acceptance rule against `spin` on the same build: the same verdict for every golden frame on the Metal goldens and on the D3D11 goldens under Proton (a frame exact in every `spin` run exact in every `sleep` run); flips/s, interval p50/p95 and the anchors' flip indices of `@stage1` and `@story-hub` within `spin`'s own run-to-run spread; no new `[AUDIO-HOST]` starves; and, on Burnout 3 under Proton, the same screens at the same flips, the race pace within spread, and no site over 5% timeout exits. The golden pins stay at `spin`.

BLiNX 2's default SHALL depend on the target build (the user, 2026-11-05; openspec `guest-cpus-every-core` D4): `"spin"` in the Windows build, which also runs under Proton, and the toolkit's `"sleep"` in every non-Windows build. The game SHALL set it as the key's code default through the toolkit's `enhance_cfg_set_code_default`, before `xbox_enhance_init`, so that every tier (the environment, `config/config.toml`, `config.default.toml`) still wins over it, a value that does not convert falls back to it, the `[ENHANCE]` settings line shows the mode in force, and the in-game menu takes it as the stock value. Its shipped `config.default.toml` SHALL leave the key out, so each build's default applies.

#### Scenario: Sleep is the default
- **WHEN** a non-Windows build runs with no `pacing` key in `config.default.toml` or `config/config.toml` and no `RECOMP_PRESENT_PACING` set
- **THEN** the `[ENHANCE]` line reads `present.pacing=sleep`, and the `pacing` trace reports `mode sleep` with wakes counted at site `0x00060475`

#### Scenario: Spin is the default in the Windows build
- **WHEN** the Windows build runs, natively or under Proton, with no `pacing` key in any file and no `RECOMP_PRESENT_PACING` set
- **THEN** the `[ENHANCE]` settings line reads `present.pacing=spin`, and the `pacing` trace reports `mode spin`

#### Scenario: The menu's stock is the build's default
- **WHEN** a player of the Windows build picks `sleep` for Frame pacing in the in-game menu and saves, then starts again, then picks `spin` and saves, or uses Reset to defaults
- **THEN** the first save writes `pacing = "sleep"` to `config/config.toml` and the next start sleeps; `spin` and Reset to defaults are the default again and drop the key; `spin` is not marked as a changed value

#### Scenario: An invalid value falls back to the build's default
- **WHEN** the Windows build runs with `RECOMP_PRESENT_PACING=fast` or `pacing = "fast"` in `config/config.toml`
- **THEN** the value is reported as ignored and the settings line reads `present.pacing=spin`

#### Scenario: Console-original timing on request
- **WHEN** the player puts `[present] pacing = "spin"` in `config/config.toml`, or sets `RECOMP_PRESENT_PACING=spin`
- **THEN** the `[ENHANCE]` line reads `present.pacing=spin`, the lowered loop busy-waits, and the `pacing` trace reports `mode spin` with no site counters

#### Scenario: Sleep on request in the Windows build
- **WHEN** the player puts `[present] pacing = "sleep"` in `config/config.toml`, or sets `RECOMP_PRESENT_PACING=sleep`, in the Windows build
- **THEN** the `[ENHANCE]` line reads `present.pacing=sleep`, the game does not change it, and the `pacing` trace reports `mode sleep`

#### Scenario: Flip reverted
- **WHEN** the default-flip commits are reverted (the toolkit's and cat's)
- **THEN** the default is `"spin"` again in the code, and the golden configuration is unchanged
