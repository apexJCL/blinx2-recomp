## ADDED Requirements

### Requirement: Gen carries the game's symbol map names
A game MAY set `[pipeline] symbols` to a symbol map, a TOML file of `[[symbol]]` tables (`addr`, `name`, `kind`, `note`) in the format the CLI's `docs/symbols.md` documents. With a map set, `analyze` SHALL give every `kind = "function"` entry whose address is a function start its map name in `functions.json`, so `recomp` uses it as the C identifier, except where the game's manual file or a hook slot needs the `sub_XXXXXXXX` name, which `recomp` pins back. After `recomp`, the map's notes SHALL go into comments only: a doc block line above each mapped function, a trailing comment on lines whose literal is a mapped global, field or label. The lifted code SHALL differ from a regen without the map only in identifiers and comments. Hooks, seeds and runtime tables SHALL stay keyed by address. A game without the key SHALL get the gen it got before. The game's tests SHALL reject a map name that is a C keyword, a libc or host CRT name, an identifier in the game's sources or the toolkit's, or another function's name.

#### Scenario: BLiNX 2 regen with the map
- **WHEN** cat sets `symbols = "config/symbols.toml"` and runs `analyze` then `recomp`
- **THEN** gen defines the mapped functions under their map names except those `recomp_manual.c` or the hook slots name, and mapping the names back to `sub_` and stripping the added comments gives the stock regen byte for byte

#### Scenario: Unchanged regen keeps mtimes
- **WHEN** `analyze` and `recomp` run again with no input changed
- **THEN** no gen file is rewritten and no file's mtime moves

#### Scenario: Name clash
- **WHEN** a map function name equals an identifier in cat's `src/` outside gen
- **THEN** `scripts/test_symbols.py` fails naming the name and the file
