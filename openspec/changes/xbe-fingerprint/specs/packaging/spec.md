## MODIFIED Requirements

### Requirement: The title is verified before anything is written
Before extracting, copying, linking or running `setup`, the import SHALL read the XBE header from the source (the image's or the folder's XBE at the name `[xbe] path` gives relative to `[data] game_files`), check the certificate's title ID against `[xbe] title_id`, and refuse another title in one line that names the certificate's title and both IDs. Only after the files are in place SHALL the XBE fingerprint verdict be printed, as a warning and never a refusal, as `package` does.

#### Scenario: Wrong disc
- **WHEN** the image or folder holds another game's `default.xbe`
- **THEN** the import prints `this is "<title>" (0x<id>), not BLiNX 2 (0x4D530065)`, exits non-zero, no `game_files.partial/` exists, and no toolkit clone, toolchain download or pipeline stage ran

#### Scenario: Unknown dump
- **WHEN** the imported `default.xbe`'s sha256 is not one `game.toml` lists and one of its code sections differs from `[xbe.sections]`
- **THEN** the import completes, prints the modded-code warning once with the section names, and `package` later records the verdict `code` in `manifest.json`

## ADDED Requirements

### Requirement: The XBE is classified by its sections
The CLI SHALL classify the dump's XBE without any game constant of its own, from `game.toml`:
- `known` when its sha256 is in `[xbe] sha256`;
- `header` when every section in `[xbe.sections]` (name to sha256 of the section's raw bytes) matches and the XBE has no other section;
- `data` when only data sections differ;
- `code` when a code section differs, is added or is missing;
- `unknown` when `[xbe.sections]` is empty or the section table cannot be read.

The code sections SHALL be `.text` plus `[pipeline.disasm] extra_sections` when `text_only` is set, and every section with the executable flag otherwise. An added section SHALL count as code when its own flags are executable. `xbr fingerprint [PATH]` SHALL print the verdict for `game_files/`, a folder, a disc image or an XBE file, and `--toml` SHALL print the `[xbe.sections]` table for it.

#### Scenario: A third disc with the stock code
- **WHEN** an XBE's sha256 is not listed but every section's bytes match `[xbe.sections]`
- **THEN** the verdict is `header` and no command warns

#### Scenario: Replaced data
- **WHEN** one byte of the `.rdata` section differs
- **THEN** the verdict is `data` and the warning reads `modded data, code stock` and names `.rdata`

#### Scenario: Patched code
- **WHEN** one byte of `.text` differs
- **THEN** the verdict is `code` and the warning reads `modded code, unsupported, may crash` and names `.text`

### Requirement: A modded or unknown dump never blocks a build
`import`, `analyze`, `build`, `all`, `package` and `doctor` SHALL print the `data`, `code` or `unknown` verdict's warning and continue. No CLI command except `bench golden` SHALL refuse a dump for its XBE. `bench golden` SHALL keep refusing every XBE whose sha256 is not in `[xbe] sha256`, `header` ones included. The build wizard SHALL ask once, before the build starts, when the plan's verdict is `code`, with a dialog naming the sections and the buttons "Build anyway" and "Cancel". It SHALL show a Summary line for `data` and pass no extra flag to the CLI. `package --plan --json` SHALL report `xbe` (`sha256`, `verdict`, `sections`, `note`) for the `--dump` source's XBE when importing, else for `game_files/`'s, else `null`.

#### Scenario: Modded code in the wizard
- **WHEN** the plan reports `xbe.verdict = "code"` and the player presses Build
- **THEN** the wizard shows the confirm dialog, and the build starts only after "Build anyway"

#### Scenario: Golden on a header-only dump
- **WHEN** `bench golden` runs with an XBE whose verdict is `header`
- **THEN** it refuses before any run and names the known sha256s

### Requirement: The verdict is stamped in the manifest and the boot log
Every `manifest.json` SHALL record `xbe` as `{sha256, verdict, sections}`, where `sections` holds the differing section names, empty for `known` and `header`. For the same inputs, the manifest SHALL differ from one written before this change only by that key. When `[package] stamp_env` names a key, the staged `launch.env.default` SHALL end with a comment line and `<key>=<sha256> <verdict>`, followed by a space and the comma-joined sections when there are any. With `stamp_env` empty, no line SHALL be added.

#### Scenario: A known build
- **WHEN** a dump with sha256 0c57fd72... is packaged
- **THEN** `manifest.json` has `"xbe": {"sha256": "0c57fd72...", "verdict": "known", "sections": []}` and `launch.env.default` ends with `RECOMP_BUILD_XBE=0c57fd72... known`

### Requirement: doctor reports the asset count
When `[data] reference_files` is above 0, `doctor` SHALL print an `assets:` line with the number of files in `game_files/`, not counting the names in `game_files_exclude` or the import marker, and the reference count and the difference. It SHALL never add a problem for it.

#### Scenario: An incomplete dump
- **WHEN** `game_files/` holds 285 dump files and `reference_files = 485`
- **THEN** doctor prints `assets: 285 files (the reference dump has 485, 200 fewer)` and its exit status is unchanged
