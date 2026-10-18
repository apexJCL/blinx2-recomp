## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none`, `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay even if the default of `present.pacing` changes. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 present.pacing=spin (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries, scale 4)`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

## ADDED Requirements

### Requirement: Texture pack key
`textures.pack` (env `RECOMP_TEXTURES_PACK`, a path; a relative path resolves against the directory `xbox_enhance_init` was given) SHALL name a texture pack file (toolkit `docs/formats/texture-pack.md`: `XRTP` version 1, an index of `(hash, width, height, levels, payload offset)` sorted by hash, and A8R8G8B8 texels per entry). The layer SHALL read it once at startup, before the guest starts, load the file's index, and log `[ENHANCE] textures.pack=none` when unset or `[ENHANCE] textures.pack=<path> (<n> entries, scale <s>)` when loaded. A file that is missing, has another magic or version, an entry outside the file, or an unsorted index SHALL be refused whole with one line naming the reason, and the run SHALL continue at stock.

#### Scenario: Pack loaded
- **WHEN** `enhance.toml` holds `[textures] pack = "enhance/hud.pack"` and that file beside the executable is a valid pack of 41 entries at scale 4
- **THEN** the log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries, scale 4)` and `tests/tex_pack` finds each of its hashes

#### Scenario: Bad pack refused
- **WHEN** the named file is truncated inside its index
- **THEN** the log names the file and the reason, `nv2a_tex_pack_count()` is 0, and the frames equal a stock run's

### Requirement: Texture swap at upload
With a pack loaded, the Metal and D3D11 backends SHALL look up, on every texture upload (a cache miss or a changed hash), the texel hash they compute for the guest texture (`nv2a_tex_hash` over the bytes `nv2a_tex_extent` gives, without the P8 palette fold) in the pack's index, and on a hit SHALL create the host texture at the pack entry's width, height and level count and fill it from the pack's texels instead of the decoded guest texels. Everything else (the cache key, eviction, the per-flip rehash, samplers, UV scaling) SHALL be unchanged, so a texture the game rewrites stops matching and returns to its guest bytes on the next upload. The pack's texels SHALL be read from the file on the entry's first use and kept. Without a pack the only added statement per upload SHALL be the entry-count test. The CPU rasteriser SHALL ignore the pack and log `[ENHANCE] textures.pack ignored: the CPU rasteriser samples guest memory` once.

#### Scenario: HUD texture replaced on Metal
- **WHEN** `@stage1` runs on Metal with a pack holding the Latin font atlas and the life bar at 4x, and dumps a flip where the HUD is visible
- **THEN** the log's pack hit count is at least 2, the texels of the `Time:` text in the dump have more distinct edge levels than the stock dump at the same flip (sharper), the glyphs sit where the stock glyphs sit, and no magenta texel appears

#### Scenario: Rewritten texture leaves the pack
- **WHEN** the game writes new bytes over a texture that matched a pack entry
- **THEN** the next flip's rehash misses the index and the backend uploads the guest texels at the guest size

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_TEXTURES_PACK` set to a valid pack
- **THEN** the log says once that the pack is ignored and the frames equal a stock run's within the golden limits
