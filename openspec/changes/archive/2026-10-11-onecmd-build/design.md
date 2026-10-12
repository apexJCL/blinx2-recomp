## Context

cat `main` ddc59a8, CLI `main` 2b95e72 (v0.5.1), toolkit
`posix-host/portability` with `tools/xiso` at 6d69551 (the same bytes as the
fork's `origin/main`). Facts below are from reading those files on
2026-10-11.

How the player's route works today. `./blinx2` (`blinx2.py`, the CLI's
`wrapper/game.py` vendored) finds uv and the CLI at the `[cli]` pin and
`execve`s `uv run --project <cli> --locked xbr --game <root> --prog blinx2
ARGS`. `main.py` splits `--game/--prog`, loads `game.toml`, and when `argv`
is empty or starts with an option rewrites it to `package <native_target()>
...` (`main.py:410`), so `./blinx2` alone packages for the host. `package`
(`package/__init__.py:197-206`) requires `G.xbe`, reads its first 64 KiB,
checks the certificate's title ID against `lib.TITLE_ID` (from `[xbe]
title_id`), and warns when the XBE's sha256 is not in `[xbe] sha256`
(`doctor.dump_state`). The payload copy (`lib.stage_game_files`,
`package/lib.py:323-348`) walks `game_files/` top level, skips
`game_file_excluded(name)` (the manifest's `game_files_exclude` plus
`.DS_Store`) and copies directories with `shutil.copytree` using
`copy_file(a, b, clone)`, where `_clonefile()` is macOS `clonefile(2)` through
ctypes and `None` on every other OS (`lib.py:299-312`). Any other command that
needs the dump (`analyze`, `ghidra`) calls `host.require(G.xbe,
pipeline.dump_hint())`, which prints "(dump the disc into game_files/)".
`doctor` prints `game files: MISSING: put your dump in game_files/`
(`doctor.py:229`), and `doctor.next_step` (`doctor.py:292`) and
`setup.host_blockers` (`setup.py:70`) say the same in their own words. The
pipeline writes `default_analysis.json` beside the XBE (`Game.analysis_json`,
unless `pipeline.analysis_json` says otherwise) and the manifest excludes it
from bundles. Every message that names the command uses `host.cli_name()`
(`./blinx2` on macOS and Linux, `blinx2` on Windows).

Where `game_files/` is kept out of things today: cat's `.gitignore`
(`game_files`), the scaffold's `GITIGNORE` template (`@GAME_FILES@/`,
`scaffold.py:150`; `*.iso` and `*.xiso` are already there, `scaffold.py:187-
188`), and the bench sync's `GAME_EXCLUDES` (`bench/sync.py`, a `None` slot
that `game_excludes()` fills with `"/" + data.game_files`; `tests/
test_bench_cli.py::test_sync_excludes_follow_gitignore` checks every
directory `tests/testdata/game/.gitignore` names is excluded). None of the
three knows `game_files.partial/` or `game_files.old/`.

The game's dump, for sizing: 486 files, 3.1 GB in `game_files/` (BLiNX 2;
`adx/`, `movie/`, `voice/`, six `lng_*` IPK pairs, `media.ipk`). A redump
image of an Xbox disc is about 7.3 GB (the DVD-video partition is ~387 MB of
that and is never read); a bare XISO is the game partition alone.

The reader. `xboxrecomp/tools/xiso/xdvdfs.py` (upstream commits 343df30,
6d69551): `Xiso(path)` opens the file, `_find_base()` seeks `base + 32 *
2048` for each of `BASE_CANDIDATES = (0x0, 0xFD90, 0x30600, 0xFD90000,
0x18300000)` and takes the first with the magic `MICROSOFT*XBOX*MEDIA`; the
descriptor's `+0x14` gives the root directory's sector and size; `_read_dir`
walks each 2048-byte sector of a directory linearly over `<HHIIBB>` entries
(left, right, sector, size, attributes, name length; 4-byte aligned; `0xFFFF
0xFFFF` or a zero name length ends the sector; names are decoded as ASCII and
a non-ASCII name ends the sector). `listdir`, `find` (case-insensitive),
`read(entry)` (the whole file, no size argument), `extract(entry, dest)` (1
MiB chunks, raises on a short read), `walk()` (yields `(dirpath, entry)` for
files only; an empty directory is never yielded). It does not validate names,
track visited sectors or bound the depth. Not implemented: writing, the
video partition, timestamps. Its test builds an image in memory from
`_entry()` records with the descriptor at sector 32, the root at 33 and data
from 34, at a chosen base. Under the CLI's ruff rules the file formats with a
few reflowed lines and lints clean but for one `E741` (`l, r, ...` in
`_read_dir`). The CLI is standard-library only at runtime (`pyproject.toml`,
`dependencies = []`), declares `license = "MIT"` with no `license-files`, and
already vendors files with a row in `docs/origin.md`.

Where the title check and the XBE header live in the CLI: `xbe.py`
(`title_id(data)`, `read_header(data)` reading the first 64 KiB; the
certificate holds the title ID at `+8` and a UTF-16LE title at `+0xC`), used
by `package` and by `scaffold` (`xbr new --xbe PATH`, which "reads a header,
never copies, moves or links a dump"). The manifest names the XBE by path
(`[xbe] path = "game_files/default.xbe"`) and the dump by folder (`[data]
game_files = "game_files"`), so the XBE's name inside a dump is the relative
path between them.

What the wrapper can and cannot do: `blinx2.py` forwards `argv` untouched
(`cmd = [uv, run, ..., "xbr", "--game", ROOT, "--prog", SLUG] + argv`), so a
new positional reaches `main.py` with no wrapper change, and
`scripts/test_game_pins.py` (cat) and `tests/test_wrapper.py` (CLI), which
compare `blinx2.py` with the template, keep passing. Without uv the wrapper
prints the uv hint and exits, as for every command. `find_cli` takes
`$XBOXRECOMP_CLI_DIR`, then `external/xboxrecomp-cli`, then
`../xboxrecomp-cli`: in a worktree under `wt/<name>/cat` the sibling
`wt/<name>/xboxrecomp-cli` is what runs.

## Goals / Non-Goals

Goals: a player with a disc image or a folder and a clone runs one command
with one argument and gets a bundle; the wrong disc is refused before any
toolkit clone, toolchain download or pipeline stage, and before anything is
written; the import never deletes what the player put in `game_files/`
without being told to, and never the only copy of the dump; a rerun costs
seconds; the reader stays the toolkit's, byte for byte in behaviour; no
network and no output outside the game root; a synthetic image in the tests,
never a dump.

Non-goals: the ones in the proposal (bootstrap, archives, the video
partition, a whole-dump hash table, a Deck build, toolkit edits), plus
`.cue` sheets, multi-track images, and extraction to anywhere but
`[data] game_files`.

## Decisions

**D1. The reader is vendored into the CLI, not called in the toolkit.**
`src/xboxrecomp_cli/xdvdfs.py` is the fork's `origin/main:tools/xiso/
xdvdfs.py` (6d69551, upstream's bytes) with one header prepended before the
module docstring, which stays untouched:
```
# Copyright (c) 2026 sp00nz, MIT, see LICENSES/xboxrecomp-MIT.txt; from
# sp00nznet/xboxrecomp tools/xiso/xdvdfs.py at 6d69551.
```
then run through the CLI's ruff format (line length 100, `py312`). Licence:
`LICENSES/xboxrecomp-MIT.txt` holds upstream's `LICENSE` verbatim (it names
no email), `pyproject.toml` gets `license-files = ["LICENSE", "LICENSES/*"]`
in `[project]`, and `[tool.ruff.lint.per-file-ignores]` gets
`"src/xboxrecomp_cli/xdvdfs.py" = ["E741"]` so the file lints as it is.
`docs/origin.md` gets a separate section, "From the toolkit", citing upstream
`main` (the existing table is blinx2-recomp's). The vendoring commit's subject
ends in `(upstream 6d69551)`, is authored and committed as the noreply
identity, and puts no upstream author email anywhere in the repo. Why
vendor: the title check has to run before `setup` clones the toolkit (a wrong
disc must not cost a clone and a 20-minute build), and the CLI's runtime is
standard library only, so a 170-line reader it already trusts is the
cheapest dependency there is. Why not import the toolkit's file after
`setup`: the toolkit a game pins may predate a reader fix, and `import` would
then behave differently per game. Why not `xdvdfs-cli` or `extract-xiso`: a
Rust toolchain or a prebuilt binary is the exact step the user wants gone,
and the reader's own docstring makes the same argument. Divergence rule: the
copy is kept identical to upstream's apart from the header and formatting
(the check in task 1.1 pipes upstream's file through the same formatter and
diffs); a bug found here is fixed in both and offered upstream as a small
PR; `tests/test_dump.py` carries the three properties the toolkit's
self-test pins (base probing, per-sector walk, loud failure on a non-image).
Name validation, loop and depth guards live in `dump.py` (D5), never in the
copy.

**D2. One module, `dump.py`, owns the import; three ways in.**
- `xbr import PATH [--replace] [--link] [--check]`: the command. `import` is
  a Python keyword, so the function is `cmd_import` and the module is
  `dump.py`; the name reads right to a player (`blinx2 import ~/BLiNX2.iso`).
- `xbr package <target> --dump PATH [--replace]`: imports, then packages.
  `--replace` is valid only with `--dump` (argparse error otherwise) so the
  shorthand can follow the advice its own refusal gives. The plan `package`
  prints gets a first step, `import <basename> (ISO, 3.1 GB, 486 files)` or
  `import (already in place)`.
- The shorthand in `main.py`: when `argv[0]` is not a registered command, not
  a tool, not `bench`, not `new`, and `os.path.exists(argv[0])`, argv
  becomes `["package", native_target(), "--dump", argv[0]] + argv[1:]`, so
  `./blinx2 PATH --replace` and `./blinx2 PATH --hud-pack` reach `package`
  with those options. A command name that also exists as a path (a folder
  called `doctor`) stays a command: the command table is checked first. A
  missing path stays an argparse error (`invalid choice`), with one added
  line: `to import a disc image or a folder, pass a path that exists`. Why
  the shorthand: the README then shows one command with one argument on
  every host.

**D3. The source is classified by content, never by extension.** The XBE's
name inside the dump is `os.path.relpath([xbe] path, [data] game_files)`
(`default.xbe` for BLiNX 2); a manifest whose XBE is not under `game_files`
(the relpath starts with `..`) is refused by `import` with the two keys
named. `dump.classify(path)` returns one of:
- `folder`: `os.path.isdir(path)` and `<path>/<xbe name>` exists. A folder
  without it is refused: `no <xbe name> in <path>: the folder must be the
  disc's root (the one that holds <xbe name>)`.
- `image`: a regular file whose `Xiso()` finds the magic at one of the bases.
  Any extension (`.iso`, `.xiso`, `.bin`, none).
- refused: a regular file with no magic. The message names the two likely
  reasons: `<path> is not an Xbox disc image (no XDVDFS descriptor at any
  known partition base) and not a folder; an archive (.zip, .7z, .rar) must
  be extracted first, and a .cue/.bin set needs its .bin`. A `.cue` is
  refused the same way (text has no magic).

**D4. Verify before any write, in this order.** (1) classify; (2) place:
refuse when `realpath(source)` equals, is inside, or contains
`realpath(game_files)` or `game_files.partial` (`the source is inside this
game's game_files/` or `contains it`: a copy would recurse, and `--replace`
would delete the source); (3) read the XBE header: for an image, `find` each
component of the XBE's name from the root and read `min(size, 64 KiB)`
from the entry's sector (the reader's `read` takes the whole file); for a
folder, the first 64 KiB of the file; (4) `xbe.read_header()`; refuse when `title_id != [xbe]
title_id` with `<source>: this is "<title>" (0x%08X), not <game.name>
(0x%08X)`, where `<title>` is the certificate's name, or `an XBE with an
empty title` when it is blank; (5) a stale `game_files.partial/` from an
interrupted run is removed now, after saying so (after the title check, so a
wrong disc costs nothing; before the space check, so its space counts as
free); (6) the listing: `walk()` (an image) or `os.walk` (a folder),
skipping nothing (the manifest's `game_files_exclude` names are excluded
only from bundles, and a folder source that holds a stray `UDATA/` is copied
as it is), with every name checked (D5 "Names") and the byte total and file
count summed; a folder the walk cannot read stops the import by name
(`os.walk(onerror=...)`, never a silent skip), and so does a link to a
missing file; (6a) a writing import (a copy or `--link`) beside a
`game_files.old/` that recovery kept is refused here (D7); (7) free space: `shutil.disk_usage(game_root).free` must
exceed the byte total plus 256 MiB; otherwise refuse with both numbers and
the volume (`needs 3.1 GB free on /Users; 1.2 GB free`). Exception: a folder
source on macOS whose `st_dev` equals the game root's is cloned and takes no
space, so only the 256 MiB margin is required; if the clone falls back to a
copy and the disk fills, the `finally` of D5 removes `.partial` and the
message names the space. For `--link` steps 5-7 are skipped. Only then does
anything under the game root change. The known-dump check (`[xbe] sha256`)
is not a refusal here either: it runs after the files are in place (the hash
needs the whole file) and prints the existing `doctor.unknown_dump_note`
warning once, as `package` does.

**D5. Placement: extract or clone-copy into `game_files.partial/`, then
rename; a symlink on request.**
- Names (image sources; `dump.py`, not the reader). Every path component
  from `walk()` must be non-empty, not `.` or `..`, hold no `/`, `\` or NUL,
  match neither `lib.BAD_CHARS` nor `lib.RESERVED`, and end in neither a dot
  nor a space (NTFS and the bundle checks refuse them); two names in one
  directory that differ only by case are refused (the target filesystems
  fold case and the second would overwrite the first); after joining,
  `os.path.realpath(dest)` must lie under `realpath(.partial)`. The walk
  keeps the set of directory sectors it has entered and refuses one it sees
  twice, and refuses a depth past 32; a directory of size 0 is empty and is
  not entered (mastering tools point several empty ones at one sector,
  which is not a loop). Each refusal names the entry and the
  rule, before any write (the walk is D4 step 6).
- Image: `game_files.partial/` beside the target (same volume, so the
  rename is atomic), `iso.extract(entry, dest)` for each `walk()` entry,
  with the path as mastered (XDVDFS stores one case; the user's existing
  extraction kept the mastered names). Every directory is made, empty ones
  included, so the tree matches the disc's. The progress and the messages
  count the dump's files (what `--check` and the marker count), not the
  `game_files_exclude` names a folder source may also hold. After
  the last file, each file's `os.path.getsize` is compared with its entry
  size (extract already raises on a short read; this catches a full disk
  that `write` reported late). Progress: one `host.say` line per 100 files
  or 256 MiB, `imported 312/486 files, 2.1 of 3.1 GB`; `--plain`/non-tty
  rules as `package`'s.
- Folder: a walk of the source that excludes nothing (not
  `lib.stage_game_files`, which skips `game_files_exclude` names and
  `.DS_Store`), reusing `lib.copy_file` with `lib._clonefile()` (an APFS
  clone on macOS when source and target share a volume, `shutil.copy2`
  otherwise and on every other OS) and the same `r-x` directory-mode fix
  (`mode | 0o700`) so the tree can be removed later. Why copy rather than
  link by default: the pipeline writes `default_analysis.json` beside the
  XBE, `package` reads the tree on every run, and a link to a USB stick or
  an external drive breaks the next `./blinx2`; a clone on APFS costs no
  space, which covers the Mac that is often near full.
- `--link`: `os.symlink(realpath(source), game_files)`; refused on Windows
  with `use a copy on Windows` (no junction is attempted). No marker is
  written: the link's identity is `os.readlink(game_files) ==
  realpath(source)`, and `doctor` shows `(linked to <source>)`. One warning
  line: `--link: the pipeline writes default_analysis.json into <source>
  unless pipeline.analysis_json points elsewhere`. Developer option; the
  README does not show it.
- Swap: when `game_files` does not exist or counts as empty (D7), `.partial`
  is renamed into place. Otherwise D7 applies.
- Cleanup: a failure that reaches the `finally` removes `game_files.partial/`
  (as `wrapper/game.py`'s `clone()` does with its `.partial`). SIGTERM,
  SIGHUP and a closed console skip `finally`, so a stale `.partial` is also
  removed at the start of the next import (D4 step 5). Removal uses
  `shutil.rmtree(path, onexc=...)` with a handler that `chmod`s and retries:
  files off a disc are read-only, which Windows refuses to unlink.

**D6. The marker, and what integrity means here.**
`game_files/.xbr-dump.json`:
```json
{"schema": 1, "format": "image", "source": "/Users/me/Downloads/BLiNX2.iso",
 "source_size": 7340032000, "source_mtime": 1760200000,
 "base": 405798912, "files": 486, "bytes": 3328000000,
 "xbe_sha256": "0c57fd72...", "cli": "0.6.0", "when": "2026-10-11T18:40:00Z"}
```
`format` is `image` or `folder` (a link has no marker, D5). Identity, what
"the same source" means in D7: an image is `source`, `source_size` and
`source_mtime` (`base` is recorded, not compared); a folder is `source`,
`files`, `bytes` and `xbe_sha256` (a folder has no size or mtime of its
own). The marker is written into `.partial` after the size check and
before the swap, so the rename that puts the tree in place is the one step
that finishes an import (D7). `lib.GAME_FILES_EXCLUDE`
adds `.xbr-dump.json` beside `.DS_Store`, so no bundle carries it; the
source path is the player's and stays on the player's machine. The size
pass: the source's listing (`walk()` or `os.walk`) against `game_files/`,
every file present with its recorded size; extra files in `game_files/`
that match `game_files_exclude` names, the marker, `.DS_Store`, `Thumbs.db`
or `desktop.ini` are ignored (`default_analysis.json` is the usual one);
about a second for 486 files. A rerun with the same source whose pass is
clean says `game_files/: already imported from <basename> on <date>;
nothing to do`; one whose pass differs names the first difference and
`--replace`. Adopt: with no marker and a passing size pass, the import
writes the marker and copies nothing (`game_files/: matches <basename>;
marker written`), so a player who extracted by hand and then passes the
image gets a clean rerun, not a refusal. Why no per-file hash table in
`game.toml`: hashes are not game data (the `[xbe] sha256` list is the
precedent and stays), but a 486-row table per game is a maintenance item
whose failure mode (a dump that differs from the maintainer's) is already
handled by the "unknown dump" warning on the XBE, by the game's own `[FILE]
missing` lines, and by `SHA256SUMS` in every bundle; redump's `.dat`
verifies the image itself before the player gets here. `--check` (D2) is
the cheaper tool for the one case that matters, a doubt about an existing
`game_files/`: it re-reads the source and compares every file's name, size
and sha256 against `game_files/` (files only; the same extras ignored),
writes nothing, prints the differences and exits non-zero on any (the
"ISO-against-extraction check" TASKS.md left open).

**D7. Never delete unasked: the `--replace` rule.** `game_files/` counts as
empty when it is missing, or holds only `.DS_Store`, `Thumbs.db`,
`desktop.ini` or `game_files_exclude` names (a dev run's `UDATA/`): such a
tree goes through the `.old` path below with no flag. With any other
non-empty `game_files/`:
- marker present, same source (D6 identity): the size pass, then no-op.
- marker present, another source: refuse: `game_files/ holds the dump
  imported from <old basename> on <date>; rerun with --replace to replace
  it, or run <cli_name> alone to build from it`.
- no marker, sizes match the source: adopt (D6).
- no marker otherwise (a hand-placed dump that differs, every clone before
  this release): refuse with `game_files/ already holds a dump that was put
  there by hand; rerun with --replace to replace it, or run <cli_name> alone
  to build from it`. `package` with `--dump` stops here too (the shorthand
  form), so a player who already copied the files and now passes the image
  by habit gets the hint, not a second copy.
- Kept names: the old tree's top-level `game_files_exclude` entries (a
  run's saves in `UDATA/` and `TDATA/`, the pipeline's
  `default_analysis.json`) are copied into `.partial` after the size check
  and before the swap, both when the old tree counts as empty and under
  `--replace`; copied, not moved, so the old tree stays whole until the
  swap. A name the source also has comes from the source, and the import
  says which names were kept and which the source replaced. They count
  toward the free-space check. `--link` over a tree holding them is refused
  without `--replace` (a link has no tree to carry them into).
- `--replace`: the new tree is built in `.partial` first (D5), the kept
  names copied in and the marker written into it; an empty `game_files` is
  `rmdir`ed; otherwise the old `game_files/` is renamed to
  `game_files.old/`, `.partial` renamed into place (the commit point), and
  `game_files.old/` removed (the same `rmtree` as D5; a failure there is a
  line saying to remove it later, which the next import also does). Each `rename` is
  retried up to five times, 0.2 s apart, on `PermissionError` (an indexer or
  antivirus holding a handle on Windows). A symlinked `game_files` is
  unlinked, never followed. Peak disk is old plus new (6.2 GB for BLiNX 2);
  D4's free-space check counts the new tree only and the message says the
  old one is removed after the swap.
- Recovery, at the start of every import, before D4: `.old` exists and
  `game_files` is missing: rename `.old` back and say so (the run died
  between the two renames). Both exist and `game_files` holds a marker or
  is a symlink (the marker, or the link, is in place before the rename that
  finishes the swap): remove `.old` (the run died after the swap). Both
  exist and `game_files` has no marker (a hand-made pair, or an older CLI
  that wrote the marker after the swap): leave both and say so. Adopt
  still runs (it renames nothing, and once it writes the marker `.old` is
  removed by the same rule), but a writing import (a copy or `--link`) is
  refused before it copies anything, since its swap needs the
  `.old` name and either tree may be the player's: `game_files.old/ is left
  from an import that stopped before it finished, beside a game_files/ with
  no marker, and either may hold your dump: remove game_files.old/ to keep
  game_files/, or remove game_files/ and the next run puts game_files.old/
  back; then run the import again`. `.old` is never deleted while
  `game_files` is absent.
- `doctor`, and `package` without `--dump`, report a leftover
  `game_files.partial/` or `game_files.old/` in one line: `left by an
  interrupted import: run '<cli_name> import PATH' again, or remove it`.
A regenerated `src/recomp/gen/` is not forced by an import: the generation
key (`gen.key.json`) already hashes the XBE, so a different dump regenerates
on the next `package` and the same bytes do not.

**D8. The CLI's words: `doctor`, the help, the plan, the errors.**
- Every message that names the command uses `host.cli_name()`; no literal
  `./blinx2` or `./<slug>` in `dump.py` or the texts it changes.
- `doctor`'s `game files:` line appends `(imported from <basename>, <date>)`
  when the marker exists or `(linked to <source>)` for a symlink, adds the
  leftover line of D7 when a sibling exists, and the MISSING line becomes
  `MISSING: run '<cli_name> import PATH' with your disc image or folder, or
  put the files in <game_files>/`; `doctor.next_step`, `setup.host_blockers`,
  `pipeline.dump_hint()` and `scaffold`'s step 1 say the same two options.
- `helptext.DOC` first command block:
  ```
  @slug@ /path/to/dump                  your disc image (.iso) or the folder
                                        with default.xbe: checks it is @name@,
                                        puts the files in game_files/, then the
                                        same as the line below
  @slug@                                package for this computer ...
  ```
  and `@slug@ import PATH [--replace]` under the player commands. `top_help`
  and `render` keep the same bytes contract with the uv-less path (the file
  stays 3.9 syntax).
- `package`'s plan: `import` as its first step when `--dump` is given (D2).
- Every refusal is one `CliError` line in the house style (what, then the
  fix), never a traceback; `XisoError` is caught at the `dump.py` boundary
  and re-raised as `CliError` with the path.

**D9. Tests: synthetic images only.** `tests/test_dump.py` ports the
toolkit's `_build_image` as a fixture builder (descriptor at sector 32, root
at 33, data from 34, a chosen base) with one extension: `default.xbe`'s
payload is `tests/test_xbe.py`'s `header()` so the title check has something
real to read; the builder takes a list of entries so a test can master a bad
name or a looped directory. Cases, one test each: bare base and the redump
base `0x18300000` (the file is written sparse with `seek`, so the test costs
no disk; it asserts `iso.base`); a subdirectory; a non-image refused with
the archive hint; a wrong title refused before `game_files.partial/` exists;
the import into an empty root, the marker's fields, the bundle exclusion
(`lib.game_file_excluded(".xbr-dump.json")`); rerun no-op; adopt of a
matching hand-placed tree; hand-placed refusal; other-source refusal;
`--replace` swap with `game_files.old` cleanup; a crash simulated after the
first rename (`.old` present, `game_files` absent) recovered on the next
run, and `.old` beside a marked `game_files` removed; a stale `.partial`
removed after the title check; the names: `..`, a separator, a NUL, a
`BAD_CHARS` character, a `RESERVED` name, a trailing dot, a trailing space,
two names differing only by case, a destination resolving outside
`.partial`, a directory sector seen twice, depth past the cap; a source
inside `game_files` and one containing it; `--check` on a changed byte and
on an ignored extra; the folder source (the copy mechanics are
`lib.copy_file`'s, already tested; the walk copies a `UDATA/` and skips
nothing) and `--link` (no marker, `readlink` identity, the one-line
warning, refused on a fake Windows); free-space refusal by monkeypatching
`shutil.disk_usage`, and the same-volume macOS folder exception by
monkeypatching `os.stat`; the `main.py` shorthand (a path argv becomes
`package <target> --dump PATH`, `--replace` and `--hud-pack` after the path
reach `package`, a folder named like a command stays a command, a missing
path gives the hint, `package --replace` without `--dump` is an argparse
error). The real dump is read by exactly one local gate (task 3.2) on the
Mac and nothing is kept from it but the verdict.

**D10. cat's README, player half.** The rows and sections (`README.md` at
ddc59a8: "What you need" 27-34, "Install and run" 54-83, the quick-fix row
205, the `#install-and-run` link 229):
- "What you need": three rows. Your own dump, "a disc image (`.iso`) or the
  extracted folder with `default.xbe`" with the legal sentence as today; a
  build machine (unchanged row); "uv, git and Python 3.9 or newer", with the
  one-line install per OS (macOS: `brew install uv`, git and Python come
  with the Command Line Tools; Linux: uv's `curl | sh` line, git and Python
  from the distribution; Windows: `winget install --id=astral-sh.uv -e`, Git
  for Windows, Python 3.9+ from python.org with the `py` launcher; the
  winget line installs uv only). Git is named plainly: `./blinx2` clones the
  toolchain with it.
- "Install and run" becomes "Build the game" (the link at line 229 becomes
  `#build-the-game`): the clone and the `cd` on two lines (PowerShell 5.1
  has no `&&`), then `./blinx2 /path/to/your/BLiNX2.iso`, with the
  PowerShell form beside it (`.\blinx2 C:\path\to\BLiNX2.iso`; `blinx2 ...`
  in cmd), one paragraph on what happens (checks the disc is BLiNX 2, puts
  the files in `game_files/`, fetches the toolchain, lifts and builds; 20-40
  minutes the first time; where `dist/` is), the by-hand sentence ("or copy
  the disc's files into `game_files/` yourself and run `./blinx2` alone"),
  the `package <target>` and `doctor` lines, then the install table
  unchanged. Windows keeps the short checkout path and `core.longpaths`
  advice.
- Quick fixes: the "files are missing" row's fix becomes `./blinx2 import
  /path/to/BLiNX2.iso --replace`, then rebuild.
- HUD texture pack: one sentence on the order, build first (`./blinx2
  PATH`), then `./blinx2 enhance hud`, then `./blinx2 package <target>
  --hud-pack`.
- The developer section keeps the by-hand route and gains `./blinx2 import`
  in the "Build from source" block's comment.
- `docs/packaging.md` section 1 (line 53) and section 7 (the missing-files
  entries, lines 357-365) get the same two sentences. `TODO(link)` comments
  stay.
Wording rule: no git or shell knowledge is assumed beyond pasting the lines;
every command is shown for both shells once.

**D11. Release and pins.** CLI `v0.6.0` (annotated tag on `main`, the squash
commit; the release notes are the tag message, the CLI has no changelog),
`__version__ = "0.6.0"`; cat `[cli] tag = "v0.6.0"` with the commit;
`config/setup-pins.json` and `uv.lock` unchanged (no new download, no new
Python dependency). b3 is out of scope and keeps its pin.

**D12. The siblings are ignored wherever `game_files/` is.**
`game_files.partial/` and `game_files.old/` hold the dump too. cat's
`.gitignore` gains the two lines after `game_files`; the scaffold `GITIGNORE`
template gains `@GAME_FILES@.partial/` and `@GAME_FILES@.old/` after
`@GAME_FILES@/`; `bench/sync.py` `GAME_EXCLUDES` gains two `None` slots that
`game_excludes()` fills with `"/" + data.game_files + ".partial"` and
`".old"`, and `tests/testdata/game/.gitignore` mirrors cat's so
`test_sync_excludes_follow_gitignore` enforces it. Tests: cat
`scripts/test_gitignore.py` (`git check-ignore -q` on a file under each
sibling), `tests/test_scaffold.py::test_gitignore_and_attributes` (the two
lines), `tests/test_second_game.py` (the two anchored excludes from
`game_excludes`).

## Decisions (operator, 2026-10-11)

1. Folder sources are clone-copied (D5); `--link` is for developers only
   and the README does not show it.
2. No per-file hash table in `game.toml` (D6); `import --check` covers the
   doubt case.
3. The command is `xbr import`; the shorthand `./blinx2 PATH` stays (D2).
4. git stays a player requirement (the bootstrap clones the CLI with it;
   the no-git bootstrap is out of scope), and the README says so plainly
   (D10).

## Risks / Trade-offs

- **Two copies of the reader** (toolkit, CLI). Mitigated by D1's divergence
  rule and the origin section; the file has not changed upstream since
  2025, and the three pinned properties are in both test suites.
- **A 7 GB read on a slow drive** (USB 2, a network share) takes minutes;
  the progress line and the plan's size make the wait legible. A clone copy
  on APFS is instant; a cross-volume copy is a real 3 GB write.
- **Peak disk with `--replace`** is old plus new. Said in the message; the
  alternative (delete first) breaks the "never lose the player's files"
  rule.
- **A kill that skips `finally`** (SIGTERM, SIGHUP, a closed console) leaves
  `.partial` or a half-swapped pair; D4 step 5 and D7's recovery clean up or
  restore on the next run, and `doctor` names what is left.
- **The shorthand's ambiguity** (a path that is also a command name) is
  resolved toward the command and tested; a player's path is almost always
  absolute or has a slash.
- **Case of extracted names.** Kept as mastered. If the user's existing
  `game_files/` differs in case from the image (task 3.2 will show), the
  game still finds its files: APFS folds case by default, NTFS does, and
  Wine does under Proton. (`kernel-file-io`'s case-insensitive comparison is
  the missing-file dedup, not a lookup rule.) Recorded, not changed.

## Migration Plan

Nothing migrates. Existing clones keep their hand-placed `game_files/`
(D7's rules only speak when a path is passed, and a matching tree is
adopted). cat pins the new CLI; a player on the old pin sees the old help.
Rollback is the pin.
