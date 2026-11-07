## Why

A port's hand-written side is keyed by the reference dump's addresses:
`recomp_manual.c` wraps `sub_0009AD80` and reads `MEMF(0x3AE6A0)`, the seeds
list `0x000F9860`, `main.c` registers the D3D fence at `0x00143B58` with
the device offsets `0x2C`/`0x30`. On another release of the game (another
region or version) those addresses are other code, so the build stops at
the "another release" guard or, worse, links and writes into the
wrong memory.

The spike showed that a game-agnostic matcher places every one of
BLiNX 1's hand-written items in the PAL release (14/14, checked by hand)
across a different XDK and a recompile. Its write-up
(`notes/release-matcher/release-matcher.md`) recommends a go, with the
names resolved through a per-release match map and the unsure entries
flagged. This change is that phase 2.

## What Changes

- **Port names** (`[pipeline] names = "config/names.toml"`): one row per
  address or value the hand-written side uses, with its name, kind
  (`function`, `global`, `site`, `value`) and the reference release's
  address or value. It is separate from the gen symbol map
  (`symbols.toml`): it renames nothing in gen.
- **Release maps** (`[pipeline] releases = "config/releases"`): one
  `<release>.toml` per other release, listing its dumps' sha256 and, per
  name, the address in that release with the matcher's verdict (`sure`,
  `unsure`, `reviewed`) or nothing (unplaced). Values that are not
  addresses (struct offsets, timing) are kept there by hand.
- **`xbr match PATH [--release ID]`**: analyses another dump (parse,
  disasm) into `analysis/releases/<id>/`, runs the spike's matcher against
  the reference analysis and writes `config/releases/<id>.toml`, flagging
  unsure and unplaced names. The release ID defaults to the certificate's
  region and version (`pal-v3`).
- **Release selection**: before any stage, the CLI picks the names for the
  dump in `game_files` by its fingerprint: the reference (its sha256 is
  listed, or the sections match), or the release file that lists its
  sha256. Another release with no file stops with the command to run
  (`blinx1 match game_files`). Unsure names are listed as a warning on
  every analyze and recomp until marked `reviewed`.
- **The C form**: the CLI writes `gen/recomp_names.h` for the selected
  release. Hand-written code says `XBR_FN(name)`, `XBR_GEN(name)` (the
  wrapped body), `XBR_VA(name)`, `XBR_VAL(name)` and `#if XBR_HAVE(name)`.
  The address form (`sub_0009AD80`, `0x3AE6A0`) stays valid, so a game
  migrates one table at a time.
- **A name the release lacks** disables the code under `#if
  XBR_HAVE(name)`; any other use stops the build by name before recomp,
  never at link.
- **Toolkit, recomp `--names FILE`**: the manual scan resolves the name
  forms to addresses before its regexes, so wraps, skips and pinned
  `sub_` names are found as before, and drops `#if XBR_HAVE(name)` blocks
  whose name the file lacks.
- **Seeds by name**: a seed row may say `"name"` instead of `"start"`; the
  CLI writes the resolved list to `analysis/` and hands that to disasm and
  recomp.
- **BLiNX 1** (the first user): `config/names.toml` for its wraps, globals,
  seeds and fence; `recomp_manual.c`, `far_cull.h` and `main.c` in the name
  form; `config/releases/pal-v3.toml` from `match`, reviewed by hand.

## Impact

- CLI: new `names.py` and the `match` verb (around the spike's
  `match.py`); `manifest.py`, `pipeline.py`, `main.py`, `helptext.py`;
  docs (`names.md`, `manifest.md`, `commands.md`), CHANGELOG.
- Toolkit: `tools/recomp/manual_scan.py`, `tools/recomp/__main__.py`
  (`--names`), tests.
- blinx: `game.toml` `[pipeline] names`, `config/names.toml`,
  `config/releases/pal-v3.toml`, `config/seed_functions.json`, the three C
  files, a `scripts/test_names.py`. Its `[cli]` and `[toolkit]` pins move
  at the next push round; until then it builds with `XBOXRECOMP_CLI_DIR`
  and `XBOXRECOMP_DIR` (held commit, as for the release gate).
- Generated code: a regen of the NTSC-U v6 dump is byte-identical in every
  gen file; `gen/recomp_names.h` is the one new file. BLiNX 2 (no `names`
  key) generates exactly as before.
- Players: the stock NTSC build is unchanged. A PAL dump of BLiNX 1
  builds and boots instead of stopping at the guard.
