## Why

`config/symbols.toml` names 453 BLiNX 2 addresses (250 functions, 142
globals, 58 fields, 3 labels; the tracker items; counts at the r2 rework), but the generated code in
`src/recomp/gen/` still calls every function by address: the lift of the
title state machine is `sub_000133E0`, and nothing in gen/ says so. The
user asked that the reverse-engineering work leave named, documented
functions behind. The CLI's `names` stage already writes Ghidra's
library names into the function database that `recomp` reads; it does not
read the game's own map.

## What Changes

- **CLI, `[pipeline] symbols`** (new, default `""`): the path of a game's
  symbol map, a TOML file of `[[symbol]]` tables (`addr`, `name`, `kind`,
  `note`; other keys ignored). The format is game-agnostic and documented
  in the CLI's `docs/symbols.md`.
- **CLI, `names` stage**: after Ghidra's names (when there is an export),
  every `kind = "function"` entry whose address is a function start still
  called `sub_XXXXXXXX` gets the map's name in `functions.json`. `recomp`
  then uses it everywhere a function name becomes a C token (definition,
  declaration, calls, dispatch table), as it already does for Ghidra's
  names. The stage runs whenever a map is configured, Ghidra or not, so a
  player's build (no Ghidra) gets the same names.
- **CLI, after `recomp`**: comments only, never code:
  - a function in the map gets ` * <name> (sub_XXXXXXXX): <note>` in the
    doc block above its definition, whether `recomp` used the name or
    kept `sub_` (see design D2);
  - a line of code with a hex literal equal to a global's or field's
    address gets a trailing `/* <name> */`;
  - a `loc_XXXXXXXX:` label at a `kind = "label"` address gets one too.
  Files whose bytes come out the same keep their mtime, so a no-op regen
  rebuilds nothing.
- **Gen key**: the map file is an input, and the map's step joins the
  hashed stage commands, only for a game that sets the key: every other
  game's gen/ stays fresh.
- **cat**: `game.toml` sets `symbols = "config/symbols.toml"`;
  `scripts/test_symbols.py` rejects names that would collide in C (keywords,
  libc and host CRT names, identifiers in cat's sources, the toolkit's and
  gen/'s other function names) and code outside `src/recomp_manual.c` that
  names a mapped function by its `sub_` symbol.

## Unchanged

- Hooks, `config/seed_functions.json`, `config/hook_functions.json`,
  `[mods] hook_functions`, spin waits and every runtime table stay keyed by
  address.
- `recomp_manual.c` keeps calling `sub_XXXXXXXX` and `sub_XXXXXXXX_gen`:
  recomp's `--exclude-manual` scan already pins every `sub_` name the
  manual file mentions back to `sub_` (D2).
- The lifted code: the generated C differs from a stock regen only in
  identifiers and comments (task 3.3 checks it).
- No toolkit change.

## Impact

- CLI: `manifest.py`, `pipeline.py`, new `symbols.py`, `docs/manifest.md`,
  new `docs/symbols.md`, tests.
- cat's `game.toml` key needs that CLI: the CLI refuses unknown keys, so
  cat's side merges once its `[cli]` pin reaches a release that has it
  (v0.19.0 first; cat main pins v0.20.0).
- cat: `game.toml`, `scripts/test_symbols.py`, this change.
- Every gen file is rewritten once (new names and comments), so the first
  build after the merge recompiles all of gen/.

