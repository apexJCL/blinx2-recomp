## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay even if the default of `present.pacing` changes or a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 present.pacing=spin (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`

#### Scenario: Legacy pin still stock
- **WHEN** `@stage1` runs with `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_CONFIG` unset, with a `config.default.toml` beside the executable that sets `scale = 2`
- **THEN** the log has one `[ENV] RECOMP_ENHANCE_CONFIG is deprecated; use RECOMP_CONFIG` line, reads no file, and shows `render.scale=1`

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
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

### Requirement: Configuration file beside the executable
The enhancements layer SHALL read two files under the environment. The **defaults file** `config.default.toml` SHALL be read from the directory of the running executable (`recomp_exe_dir()`, resolved portably with a working-directory fallback; on Apple platforms, when absent there, from `<exe dir>/../Resources/`, the app bundle's layout), SHALL never be written by the layer or the game, and SHALL ship with every build and bundle so that a new version's keys apply to an existing install. The **user file** `config.toml` SHALL be read from `<root>/<title>/config.toml` (when a title is given) and then `<root>/config/config.toml`, where `root` is the user data root `xbox_enhance_init` was given; `RECOMP_CONFIG=<path>` SHALL replace both user locations with that one file and keep the defaults file; `RECOMP_CONFIG=none` SHALL read no file at all. The precedence SHALL be env > title file > user file > defaults file > the caller's default. `RECOMP_ENHANCE_CONFIG` SHALL be the row's legacy name, honoured when `RECOMP_CONFIG` is unset with the table's one deprecation line. The layer SHALL log one `[ENHANCE] config:` line naming every file it read with that file's key count (or `none (RECOMP_CONFIG)`), SHALL report an unparseable file with its line and skip it whole (the defaults file included), and SHALL list unread keys of every file through `enhance_cfg_report_unused`, a key a higher file overrides counting as read. A relative `textures.pack` SHALL resolve against the executable's directory, the root the defaults file is read from.

#### Scenario: File next to the binary
- **WHEN** `config.default.toml` beside the executable holds `[render] scale = 2`, no user file exists, the game is started from another working directory and no `RECOMP_*` enhancement variable is set
- **THEN** the log names that file with its key count, `enhance_cfg_source_of("render.scale")` is `ENHANCE_SRC_DEFAULTS`, and the backends render at 2×

#### Scenario: User file over defaults, environment over both
- **WHEN** the defaults file holds `scale = 2`, `config/config.toml` under the root holds `scale = 3`, and the game starts from another working directory with `RECOMP_CONFIG` pointing at that user file
- **THEN** the log names both files, `render.scale=3` is read from the user file; with `RECOMP_RENDER_SCALE=1` set as well the log adds `render.scale = 1 from RECOMP_RENDER_SCALE` and the backends render at 1×

#### Scenario: Bench reads no file
- **WHEN** a golden run starts with `RECOMP_CONFIG=none` while a defaults file and a user file exist
- **THEN** neither is read, the log reads `[ENHANCE] config: none (RECOMP_CONFIG)` and every key is at its code default

#### Scenario: Broken defaults file
- **WHEN** `config.default.toml` has a duplicate key
- **THEN** the log reports the file and line with `(file ignored)`, the user file and the environment still apply, and the run otherwise proceeds

#### Scenario: Pack path from the executable
- **WHEN** the user root is the working directory and `config.default.toml` beside the executable holds `[textures] pack = "enhance/hud.pack"`
- **THEN** the pack is opened at `<exe dir>/enhance/hud.pack` and the log's `textures.pack=` line names `enhance/hud.pack`

## ADDED Requirements

### Requirement: The user file holds differences only
`config.toml` SHALL hold only the keys whose value differs from `config.default.toml`: a writer (the in-game menu's Save, a later change) writes a key whose value differs from the defaults file's (or, when the key is absent there, from the code default) and deletes a key returned to that value; `config.default.toml` SHALL never be written. The layer SHALL expose what a writer needs: `enhance_cfg_user_path()` SHALL return the file Save writes (the title file when one was read or created, else the user root file or the `RECOMP_CONFIG` file; NULL under `none`), and `enhance_cfg_defaults()` SHALL return the parsed defaults file or NULL. When the user file the layer would read is absent and its directory exists, `enhance_cfg_init` SHALL create it as a comment header (no key) that names `config.default.toml` beside the executable and says that only changed keys live here and that the environment overrides it; the layer SHALL never create a directory, SHALL create nothing under `RECOMP_CONFIG=none`, and SHALL say once and go on when the write fails. A key present in the user file with the defaults file's value SHALL be read as any other (the layer does not judge equality on read).

#### Scenario: Header created on first launch
- **WHEN** the game starts with `RECOMP_CONFIG=<data>/config/config.toml`, `<data>/config/` exists and holds neither `config.toml` nor `enhance.toml`
- **THEN** `config.toml` is created holding only comment lines, parses to 0 keys, the log names it with `(0 keys)`, and `enhance_cfg_user_path()` returns its path

#### Scenario: No directory, no file
- **WHEN** the user root has no `config/` directory and `RECOMP_CONFIG` is unset
- **THEN** no file or directory is created, the log names the defaults file alone, and `enhance_cfg_user_path()` returns the path the file would have had

#### Scenario: Save path under none
- **WHEN** the run started with `RECOMP_CONFIG=none`
- **THEN** `enhance_cfg_user_path()` is NULL and `enhance_cfg_defaults()` is NULL

#### Scenario: A writer's comparison
- **WHEN** the defaults file holds `[render] scale = 1` and `[present] filter = "nearest"` and a writer is given `render.scale = 2` and `present.filter = "nearest"`
- **THEN** `enhance_cfg_defaults()` answers `1` and `"nearest"`, so the writer writes `scale = 2` and deletes any `filter` key the user file holds

### Requirement: One-time migration of enhance.toml
Before loading a user location whose basename is `config.toml` (the `RECOMP_CONFIG` file, `<root>/<title>/config.toml`, `<root>/config/config.toml`), when that file is absent and `enhance.toml` exists in the same directory, `enhance_cfg_init` SHALL rename `enhance.toml` to `config.toml` and log one line `[ENHANCE] config: renamed <dir>/enhance.toml to config.toml (one-time migration)`; a failed rename SHALL be said once and the run SHALL go on without that file. The layer SHALL NOT migrate `<root>/enhance.toml` (the pre-change root location), a `RECOMP_CONFIG` file with another basename, or anything under `RECOMP_CONFIG=none`, and SHALL NOT delete any file. The launchers SHALL stop copying any template, SHALL remove the `config/enhance.toml.default` copy they wrote in earlier versions, and SHALL set `RECOMP_CONFIG`. There is no compatibility window: the next release reads `config.toml` only.

#### Scenario: Renamed once
- **WHEN** `<data>/config/enhance.toml` holds `[render] scale = 2`, no `config.toml` exists there, and the game starts with `RECOMP_CONFIG=<data>/config/config.toml`
- **THEN** the file is now `config.toml` with the same bytes, the log has the rename line and reads `render.scale=2`; a second start shows no rename line

#### Scenario: Not a candidate
- **WHEN** `RECOMP_CONFIG=ecfg_init.toml` names a file that does not exist while `enhance.toml` sits beside it, or `<root>/enhance.toml` exists with `RECOMP_CONFIG` unset
- **THEN** nothing is renamed and no rename line is printed

#### Scenario: Developer build reads the repository's user file
- **WHEN** `./build/cat_recomp` starts from the repository root with `config/config.toml` holding `[render] scale = 2` and the build directory's `config.default.toml` at stock
- **THEN** the log names `build/config.default.toml` and `config/config.toml`, and `render.scale=2` is in force; `git status` shows `config/config.toml` neither untracked nor staged
