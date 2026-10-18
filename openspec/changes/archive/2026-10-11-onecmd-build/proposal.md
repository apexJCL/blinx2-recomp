## Why

The user asked (2026-10-11) for the public `blinx2-recomp` README's player
route to be one command that takes the path to the player's dump, disc image
or folder, and builds the release on the spot: "less friction for less savvy
people". Narrowed the same day once `./blinx2` was found to already be that
command (it sets up, lifts, builds and packages for the host with no
arguments): what is missing is the dump input and the words. Today the player
has to know how to turn a disc image into a folder (extract-xiso, xdvdfs-cli,
a Rust toolchain), copy it into `game_files/` by hand, and only then run
`./blinx2`; the CLI (`xboxrecomp-cli`, `xbr`) reads nothing but
`[data] game_files` and has no disc-image reader and no path argument
(`manifest.py`, `setup.py`, `doctor.py`, `scaffold.py`). The README's
"Install and run" says "put your dump in `game_files/` first" and leaves the
extraction to the player.

The toolkit already carries the reader this needs: upstream's
`tools/xiso/xdvdfs.py` (sp00nz, MIT, 170 lines, standard library) lists and
extracts XDVDFS images, probes the game-partition base at the five known
offsets (bare XISO, redump-style with the DVD-video partition first at
`0x18300000`, and three others) instead of guessing from the file size, walks
directory entries per sector so a padded tree link cannot silently drop a
subtree, and has a synthetic-image self-test (`test_xdvdfs.py`). It is in the
fork at the pinned `blinx2-v0.1.0`. Nothing in cat or the CLI uses it yet; the
archived `runtime-missing-files` change left "an ISO-against-extraction check
(`tools/xiso/xdvdfs.py`)" as an optional follow-up (TASKS.md).

Spec by the reviewer; the implementation and its review are
the next agent's.

## What Changes

- **The CLI accepts a dump path, folder or disc image (game-agnostic).**
  A new module `dump.py` and a vendored copy of the toolkit's XDVDFS reader
  (`xdvdfs.py`, MIT, its licence shipped under `LICENSES/` and its origin in
  `docs/origin.md`) give `xbr` an `import PATH` command, `--dump PATH` and
  `--replace` options on `package`, and a shorthand: a first argument that is
  an existing path, not a command, means `package <native target> --dump
  PATH`. So the player's whole route is `./blinx2 /path/to/BLiNX2.iso` (or a
  folder; `.\blinx2 C:\path\to\BLiNX2.iso` in PowerShell).
- **The title is verified before anything is written.** The import reads the
  XBE header out of the image or folder, checks the certificate's title ID
  against `[xbe] title_id`, and refuses another title by name
  (`this is <title> (0x...), not BLiNX 2 (0x4D530065)`) before extracting a
  byte or cloning a toolkit. Every name read from an image is checked before
  any write (no `..`, separators, Windows-reserved or case-colliding names;
  every destination resolves under the staging folder), and a source that
  sits inside the game's `game_files/` (or contains it) is refused.
  `package` keeps its own check as today.
- **ISO extracted, folder clone-copied, atomically, with a marker.** An
  image is extracted into `game_files.partial/` beside `game_files/` and
  renamed into place once every file's size matches its directory entry; a
  folder is copied with the payload copier's file mechanics (an APFS clone on
  macOS, a plain copy elsewhere), `--link` symlinks it instead for
  developers. A marker `game_files/.xbr-dump.json` records the source (an
  image: path, size, mtime, partition base; a folder: path, file count, byte
  total, the XBE's sha256), so a rerun with the same source is a quick size
  check and a no-op; a hand-placed `game_files/` whose sizes match the
  source is adopted (marker written, nothing copied); a different source or
  any other hand-placed tree is refused unless `--replace`; the bundle
  excludes the marker. Free space on the game root's volume is checked
  against the source's byte total first. An interrupted `--replace` is
  recovered on the next run from whichever of `game_files/`,
  `game_files.partial/` and `game_files.old/` is left, never by deleting the
  only copy.
- **`doctor` and the help** name the dump's origin (`imported from`,
  `linked to`), leftover `.partial`/`.old` siblings, and the path form.
- **No new `game.toml` key, no bootstrap change.** `blinx2.py` passes
  arguments through unchanged; the manifest's `[xbe]` and `[data]` tables
  already hold what the import needs (`title_id`, `sha256` for the
  known-dump warning, `path` for the XBE's name inside the dump,
  `game_files`, `game_files_exclude`).
- **`game_files.partial/` and `game_files.old/` are ignored everywhere
  `game_files/` is:** cat's `.gitignore`, the scaffold's `.gitignore`
  template and the bench sync's excludes, each with a test.
- **cat README, player half rewritten around the one command.** "What you
  need" shrinks to the dump, a build machine, and uv, git and Python
  (git named plainly as a requirement: the bootstrap clones the CLI with
  it); "Install and run" becomes "Build the game" with the clone and `cd` on
  two lines, then `./blinx2 /path/to/your/dump` (the PowerShell form beside
  it), what it does and how long it takes, the bundle's place and the
  install table as today; the by-hand `game_files/` route stays as one
  sentence and in the developer section; one sentence puts the HUD pack in
  order (build, `enhance hud`, `--hud-pack`). The same wording goes to
  `docs/packaging.md` section 1 and the "files are missing" quick fix.
- **A tagged CLI release (`v0.6.0`) that cat pins** (`[cli] tag` and
  `commit`), as every CLI change does. The release notes go in the annotated
  tag (the CLI has no changelog).

Non-goals: a no-git `curl | sh` or PowerShell bootstrap (dropped from scope
by the user, 2026-10-11; `./blinx2` from a clone is the route); reading
archives (`.zip`, `.7z`, `.rar`) or `.cue/.bin` sets, which are refused with
"extract the archive first"; the DVD-video partition, timestamps or writing
XDVDFS (the reader's own non-goals); a per-file hash table of the whole dump
in `game.toml` (design D6); changing where the pipeline writes
`default_analysis.json`; Burnout 3's manifest (b3 gets the feature for free
once it pins the release; its README is its own change); the Steam Deck as
a build machine (stock SteamOS has no compiler and a read-only root; the
README keeps steering to a PC or Mac); any toolkit change (the toolkit's
`tools/xiso` stays upstream's; a fix found in the vendored copy is offered
upstream separately and noted in `docs/origin.md`).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `packaging`: a dump import from a disc image or folder, with the title
  verified before any write, atomic placement, a rerun marker and a
  `--replace` rule with crash recovery; the one-command path accepts the
  dump's path; the bundle excludes the marker; the help shows the path form
  first.

## Impact

- **Render backends, hosts and goldens.** None of the renderer, runtime,
  audio or kernel changes; no golden moves. The CLI change runs on every
  build host (macOS, Linux, Windows). The only run against the real dump is a
  local check that the vendored reader's extraction of the user's image
  matches the existing `game_files/` byte for byte (names and sizes, then
  sha256), which never leaves the Mac.
- **Toolkit.** Untouched; not upstream-bound. The vendored reader is
  upstream's file, so a bug fixed in the copy is sent upstream as its own
  small PR under the usual rules.
- **CLI** (branch `feat/dump-import` off `main` 2b95e72, v0.5.1, in a fresh
  CLI worktree): `src/xboxrecomp_cli/xdvdfs.py` (vendored),
  `LICENSES/xboxrecomp-MIT.txt` (upstream's LICENSE), `pyproject.toml`
  (`license-files`, a ruff per-file ignore), `dump.py` (new), `main.py` (the
  `import` command, `package --dump`/`--replace`, the path shorthand),
  `helptext.py`, `doctor.py` (origin and leftover lines, `next_step`),
  `setup.py` (`host_blockers`), `pipeline.py` (`dump_hint`),
  `package/__init__.py` (`--dump`, `--replace`, the leftover line),
  `package/lib.py` (`GAME_FILES_EXCLUDE` gains the marker), `bench/sync.py`
  (the two siblings in the excludes), `scaffold.py` (`.gitignore` template,
  the closing lines), `docs/origin.md` ("From the toolkit"),
  `docs/manifest.md` (a paragraph under `[data]`), `docs/commands.md` (two
  player sections), `README.md` (the quick start's dump comment, the Commands
  table), `tests/test_dump.py` (new, synthetic images only),
  `tests/test_cli.py`, `tests/test_scaffold.py`, `tests/test_bench_cli.py`,
  `tests/testdata/game/.gitignore`; version 0.6.0 and its tag. About 900
  lines including tests.
- **cat** (`wt/onecmd/cat`, branch `feat/dump-import` off `main` ddc59a8 or
  later, after this spec merges): `README.md` (the player half, about 80
  lines), `docs/packaging.md` (about 20 lines), `.gitignore` (two lines) and
  `scripts/test_gitignore.py` (new), `game.toml` (two pin lines),
  `TASKS.md`. No other code: `blinx2.py` is the CLI's template and does not
  change (`scripts/test_game_pins.py` keeps passing).
- **Public pushes.** The CLI's round goes before cat's so the pinned tag
  exists publicly; the noreply identity and `scripts/audit-public.sh` apply
  as always. No tracker ids, host names or private paths in the CLI repo.
  Nothing in this change sends anything about the dump anywhere: the import
  reads the source and writes under the game root only.

## Status

Proposed 2026-10-11 against cat `main` 2b552e3, CLI `main` 13f4091 (v0.4.0),
toolkit `posix-host/portability` (tools/xiso at 6d69551, unchanged since the
reader landed). Scope narrowed by the user the same day: no
bootstrap; ISO/XISO input and the README's player top only.

Revised 2026-10-11 after the review, against cat `main` ddc59a8 and CLI
`main` 2b95e72 (v0.5.1; v0.5.0 and v0.5.1 shipped meanwhile, so the release
is v0.6.0). Operator decisions the same day (design "Decisions (operator,
2026-10-11)"): folder sources are clone-copied and `--link` is for
developers; no per-file hash table in `game.toml`; the command is `xbr
import` and the shorthand stays; git stays a player requirement, said
plainly in the README.
