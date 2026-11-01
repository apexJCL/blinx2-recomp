## ADDED Requirements

### Requirement: The mod namespace
`xbr mod` SHALL group the commands that change or inspect the game's behaviour: `hooks` (the pipeline stage, still run by `analyze` and `all` under the stage name `hooks`), `hud-map` (with its sub-verbs), `symbols`, `new` and `list`. They SHALL read `[mod]`, `[mod.signatures]` and `[mod.hud]` in `game.toml`, and `[pipeline] symbols`.

#### Scenario: Hooks stage
- **WHEN** `xbr analyze` runs on a game with `[mod] hook_functions`
- **THEN** the hooks stage runs as before, and its stage name in the gen key is `hooks`

### Requirement: Symbol map check
`xbr mod symbols check [--json]` SHALL load the file `[pipeline] symbols` names and report every problem (reserved names, C keywords, `sub_`/`loc_` shapes, duplicates, unknown kinds), as a list with `--json`, and exit 1 when there is any. `xbr mod symbols show ADDR|NAME [--json]` SHALL print the matching entry.

#### Scenario: Bad map
- **WHEN** the symbol map names a function `int`
- **THEN** `mod symbols check --json` lists that problem and exits 1

### Requirement: Mod scaffold
`xbr mod new NAME` SHALL write `src/NAME_mod.c` and `src/NAME_mod.h` from a template that holds nothing game-specific: a descriptor (title, summary, author, version), one menu setting, one rebindable control, `init` and `shutdown` stubs, the `XBOX_MOD_API_VERSION >= 5` guard and `NAME_mod()`. It SHALL refuse an existing file and a NAME that is not a C identifier, edit no other file, and print the `CMakeLists.txt` source line and `#include`, the registration line for `src/main.c`, and a note to grow the fixed mods array.

#### Scenario: New mod compiles
- **WHEN** `mod new speed` runs and the generated file is compiled against the toolkit headers with the enhancement keys defined
- **THEN** it builds, and `speed_mod()` returns a descriptor

### Requirement: Mod list
`xbr mod list [--json] [--exe PATH]` SHALL run the built game executable (or `PATH`) with `RECOMP_MODS_DESCRIBE=json`, read the descriptors and resolved settings it writes, and print them as a table, or as the JSON itself with `--json`. With no executable it SHALL say to build first.

#### Scenario: No build
- **WHEN** no executable is built
- **THEN** `mod list` says to build first and exits non-zero
