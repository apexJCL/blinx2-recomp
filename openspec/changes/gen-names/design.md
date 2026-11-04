## Context

The pipeline names functions in one place: the `name` field of
`analysis/disasm/functions.json`. `disasm` writes `sub_XXXXXXXX` (or a name
it knows, such as `xbe_entry_point`); the `names` stage runs the toolkit's
`merge_names.py --apply`, which overwrites that field with Ghidra's library
names, then the game's `names_hooks` (cat's `host_reserved_names.py`
suffixes names that would shadow a host libc symbol). `recomp` reads the
field and uses it for the definition, the declaration in
`recomp_funcs.h`, every call site, the dispatch table and the doc block
above the definition (`lifter._func_ident`, which also suffixes the
toolkit's own reserved identifiers). About 60 gen functions already carry
Ghidra names this way (`nh_malloc`, `atexit_002D5678`).

What else knows gen's names:

- `src/recomp_manual.c` defines, wraps and calls gen functions by `sub_`
  name (45 distinct `sub_` names at r2, 36 of them mapped gen functions:
  27 plain references that recomp pins back to `sub_`, its "27 pinned to
  sub_ names", and 9 wrapped as `sub_X_gen`, inside its "23 wrapped";
  counted as the distinct `sub_XXXXXXXX` in the file, comments included,
  whose VA is a map function with gen code). recomp's `--exclude-manual` scan
  (`tools/recomp/manual_scan.py`) collects every `\bsub_XXXXXXXX\b` in that
  file, comments included, and forces the function database name back to
  `sub_XXXXXXXX` for each (`__main__.py`, "pinned to sub_ names"), and
  names a wrapped body `sub_X_gen` with `sub_X` kept for its callers.
- `gen/recomp_hook_slots.c` (CLI, `hooks.slots_c`) defines `sub_X` around
  `sub_X_gen` for each `[mods] hook_functions` VA; the scan file the CLI
  hands recomp (`hooks.scan_text`) declares those wraps, so recomp pins them
  the same way.
- The mods (`hud_mod.c`, `entities_mod.c`, `debug_menu.c`, ...), `main.c`,
  `glow.c`, `free_camera.c`, `ent_api*.c`, `lod_*`, `pad_input.c` name
  `sub_` functions only in comments (audited with comments and strings
  stripped: no code reference outside `recomp_manual.c`). They reach gen
  through hooks and `guest_call` by VA.
- The toolkit's runtime prints `[ABI] sub_%08X` from the address, and
  every table (`RECOMP_ABI_CALL`, dispatch, icall feedback, spin waits,
  seeds, hook slots) is keyed by VA.
- The CLI's `hudmap` shows a function's functions.json name when it has
  one (a proposal label only). The golden tooling and cat's scripts match
  no `sub_` text in gen or in logs.

## Goals / Non-Goals

**Goals:** the map's function names as gen identifiers; its notes as
comments above the definitions; globals, fields and labels as comments; a
format any game can use; nothing keyed by `sub_` text breaks; a no-op regen
stays a no-op build.

**Non-Goals:** typed globals or struct fields in gen (a `#define` or a
typed view would change tokens the lifter emits, and the map does not know
widths); naming functions in the toolkit (no toolkit change); renaming
functions that already have a name.

## Decisions

### D1. Names go through functions.json, the path Ghidra's names take

The `names` stage applies the map after `merge_names.py` and the
`names_hooks`, in process (`symbols.apply_names`). recomp then emits the
name wherever it emits a function's name, with its own reserved-word
mangling, exactly as for Ghidra's names. The alternative, a post-recomp
rewrite of `sub_` tokens in gen, would rewrite every file after recomp's
write-if-changed compare and duplicate work recomp already does
consistently across declaration, definition, calls and dispatch.

Only an entry still named `sub_<its own address>` is renamed. A function
that disasm or Ghidra already named (`xbe_entry_point`, `atexit_002D5678`,
both `in_gen = false` in cat's map) keeps it: those names may be what other
code links against, and the map's `in_gen = false` is honoured as "leave
gen's name alone" too. The CLI refuses (fails the stage) a map whose
name is not a C identifier, is reserved or equals another function's name
in functions.json. Reserved: a C keyword, an x86 register name (the lifted
code's locals and globals), a name under `_` (the lifter's locals: `_t`,
`_i`, `_flags`, ...), `g_` or `recomp_` (the runtime's static inline
helpers in `recomp_types.h`), or a generated shape (`sub_`, `loc_`). A
clash with the game's own sources is the game test's job (D6).

`recomp` applies the map to functions.json before it runs, as `names`
does, so a map edit followed by `recomp` alone keeps the identifiers and
the comments in step.

The stage marks each renamed entry (`"symbol_name": <name>`) so a rerun of
`names` alone (no `disasm`) first puts `sub_` back where its own name still
stands, then applies the current map: a name removed from the map leaves
gen.

### D2. Linkage names: the map's names, with `sub_` kept where code needs it

Options weighed:

1. **Map names as the linkage names** (chosen). The object files define
   `menu_title_main`; crash symbolization and debuggers show it, which is
   the point of naming.
2. `sub_` linkage with a `#define name sub_XXXXXXXX` layer. Nothing in
   recomp's output can include a game header before `recomp_funcs.h`
   declares the names, so this needs either a toolkit change or a
   force-included header in every game's CMake, and the macros would leak
   into every game source that includes `recomp_funcs.h`. It would also
   hide the names from crash reports.

Option 1 is safe because every hand-written reference to a gen function
already goes through the mechanism that pins it: recomp's
`--exclude-manual` scan resets the name of every `sub_` the manual file
mentions, and the CLI's hook slots are declared in that same scan. A map
name for such a function (`stage_area_setup` at 0x606F0, wrapped by the
free camera and the entity API; the hooked HUD sprite helpers) is simply
not used as an identifier; its note still lands in the doc block, which is
keyed by address. cat's `scripts/test_symbols.py` guards the one way this
could break later: code outside `src/recomp_manual.c` that names a mapped
function as `sub_XXXXXXXX` fails the test, because nothing pins it (move
the reference into the manual file, or call by VA).

### D3. Comments after recomp, with the mtime kept for unchanged files

recomp has no field for a note, so the CLI writes the comments after recomp
(and after the hook slot file), from the map and the gen text:

- a function's doc block, found by its ` * Original: 0x%08X - ` line, gets
  ` * <name> (sub_XXXXXXXX): <note>` after its first line, wrapped at 79
  columns; a function the map names without a note gets the line without
  the colon part;
- a code line (not a comment line, no string literal, no open block comment
  at its end, no line continuation) with a hex literal, outside recomp's
  own `/* */` comments, whose value is a global's or a field's `addr` gets
  ` /* <name>[, <name>...] */`;
- a line that starts `loc_XXXXXXXX:` at a `label` address gets
  ` /* <name> */`.

Heap fields (no `addr`) have no fixed place in gen and get no comment.

The pass is idempotent: a doc line or trailing comment that is already the
map's is left alone, so annotated gen run through it again is unchanged.

recomp's `write_if_changed` keeps an unchanged chunk's mtime so a regen
rebuilds only what changed; the annotation rewrites every annotated file
after it. So the CLI notes each gen `.c` file's bytes and mtime before
recomp, and after annotating restores the old mtime of any file whose bytes
are back to what they were. A no-op `analyze && recomp` therefore still
rebuilds nothing.

### D4. Gen key

The map file joins `gen_inputs` and a `("cli", "symbols", [<map>,
<annotation version>])` entry joins the hashed stage commands, both only
when `[pipeline] symbols` is set, so another game's gen.key.json does not
change. The annotation version is a constant in `symbols.py`, bumped when
the comment format changes.

### D5. The format

`docs/symbols.md` in the CLI: one `[[symbol]]` table per address; `addr`
(integer VA), `name` (a C identifier, unique), `kind` (`function`,
`global`, `field`, `label`), `note` (one line, optional), `in_gen = false`
(optional, functions only); `struct` and `offset` mark a heap field; other
keys are the game's own (cat keeps `source`, `conflict`, `ghidra_only`).
The CLI checks only what it needs; naming rules (cat's subsystem
prefixes, sorting, sources) stay in the game's own test. TOML is read with
`tomllib`; cat keeps its narrower subset for the Ghidra import script.

### D6. Collision checks in cat

`scripts/test_symbols.py` gains:

- every name: not a C or C++ keyword, not a libc, POSIX or Windows CRT
  name (the sets in `scripts/host_reserved_names.py` and the ISO C list
  `merge_names.py` reserves, read from the toolkit when present);
- every function name: not an identifier in cat's sources outside gen
  (comments and strings stripped), not a function name in the toolkit's
  `src/` or runtime templates (skipped when no toolkit is checked out, as
  in the public repo's CI), not another function's name in
  `analysis/disasm/functions.json` (skipped when absent);
- no code outside `src/recomp_manual.c` names a mapped function as
  `sub_XXXXXXXX` (D2).

Consequences:

- `test_no_clash_with_cat_sources` rejects a map name used anywhere in
  cat's sources outside gen, so a mod cannot call a gen function by its new
  name either: it reaches one by VA (the hook and dispatch tables) or
  through `src/recomp_manual.c`, which keeps the `sub_` name pinned.
- `test_no_clash_with_toolkit` skips when no toolkit sits next to cat
  (`external/xboxrecomp` or `../xboxrecomp`), as in an agent worktree
  without its toolkit pair or the public CI. The r2 run of
  `uv run pytest scripts` (340 passed, 25 skipped) skipped it; run against
  toolkit 11e099c2, `scripts/test_symbols.py` gives 11 passed.

## Risks / Trade-offs

- [The first build after the merge recompiles all of gen] -> once; later
  regens keep mtimes (D3).
- [A future mod calls a gen function by its `sub_` symbol] -> the D6 test
  fails before the link does, naming the file.
- [A crash-log tool that greps `sub_` misses a named frame] -> none in the
  CLI, cat or the toolkit's pipeline today (audited); the toolkit's
  address prints are unchanged.
- [A player's build without Ghidra] -> the map applies with or without
  Ghidra; only Ghidra's own names differ, as today.
- [Comment noise on hot globals] -> trailing comments only, one per line,
  names only (notes stay in the map).
