## Toolchain

The PC uses exactly the Mac's pins. These are the game's `game.toml`
`toolchain.llvm_mingw` tag and the CLI's CMake and Ninja pins, fetched by
`xbr setup` into the game tree on the PC (`third_party/`, `.venv/`). The
CLI already sha256-checks each download per platform, so the build host
needs no second pin table.

Nothing is installed system-wide. The PC needs only what it already has
(git, uv, tar, OpenSSH), and everything new lives under `D:\bench`.

`setup` exits with doctor's packaging verdict, which fails on a host with no
game files. The build host has none and needs none. `build.ps1` therefore
judges setup by what it left: `.venv\Scripts\cmake.exe`, `ninja.exe` and
`third_party\llvm-mingw-<tag>-*`.

## Source transport: git bundles, not a git remote

Options:

1. A git remote on the PC, or a fetch from the Mac. The main checkouts are
   local-only, and sub-agent worktrees are on branches that no remote has.
   The PC would need ssh back to the Mac. Rejected.
2. rsync or scp of the trees. The PC has no rsync. Copying the trees by scp
   is about 1 GB for BLiNX 2 and does not show what changed. Rejected.
3. **git bundles over scp (chosen).** The bundle carries one per-worktree,
   per-call ref, `refs/worktree/xbr-build-host/<call>`, so parallel
   worktrees and two bench commands in one worktree never collide.
   - A dirty tree goes as its `git stash create` commit. That commit is
     dated with HEAD's committer date, so the same edits give the same sha
     and are not resent.
   - Untracked files are warned about, not sent.
   - The host keeps `refs/xbr/head`. The next bundle is `^have`-relative to
     it, so a rebuild after a small commit sends kilobytes.
   - No bundle at all when the wanted commit is the host's head or an
     ancestor of it (a toolkit tip below a feature branch built before, an
     older CLI pin). git refuses an empty bundle there, and the host
     already has every object.

   gen/ is not tracked in the game repos, so it goes as a tar.gz with
   gen.key.json. It is resent only when its digest changes (sha256 over the
   gen digest and the gen.key.json bytes, kept in `gen-digest.txt` on the
   host). The tarball's own sha256 goes in the params and is checked
   before the unpack.

   The unpack uses `tar -m`, so the files get the PC's time rather than
   the controller's. One PC tree serves every controller, so a gen/ sent
   from cat main can be older than the objects another controller's gen/
   left there, and ninja would keep those objects. Each unpack also
   deletes the gen/ objects under the windows build dir
   (`CMakeFiles/*.dir/<gen rel>/`), whatever the clocks say.

Trees are checked out with `core.autocrlf false` and `core.longpaths true`,
so the PC compiles the bytes the Mac compiles.

## Layout and lock

- `BENCH_BUILD_DIR` defaults to nothing. It must be a drive path, by
  convention `D:/bench/build-bench`.
- Each game gets `<dir>/<slug>/{game,xboxrecomp,xboxrecomp-cli}`. One
  tree per game, not per worktree: a build is a checkout of an exact
  commit, so every controller (cat main, agent worktrees) shares it.
  build-all uses its own `D:/bench/build-matrix`.
- Everything that touches the shared tree runs under the lock:
  - the fetches and checkouts;
  - gen/'s unpack;
  - a digest of the gen/ the host then holds, computed by `build.ps1`
    over the files, the same way as `gen_state`;
  - the CLI command;
  - the copy of its outputs (the runtime files, the `--pull` paths) into
    the call's own `.out/<call>`.
- The state probe and the upload run before the lock, and the pull runs
  after it. They are safe because:
  - Uploads go to the call's own `.in/<call>`, which the script removes.
    Two controllers waiting for the lock never overwrite each other's
    bundles or tarballs.
  - If the probe saw one gen/ and the lock finds another (another call
    unpacked its own in between), and this call sent none, `build.ps1`
    exits 76 with `@xbr-status gen-moved`. The controller then runs the
    call once more and sends gen/ whatever the host says. If a sent
    tarball does not unpack to the digest sent, the build fails.
  - The pull reads `.out/<call>`, so a build that relinks the exe after
    the lock is released cannot reach it. The controller removes that
    dir afterwards. Dirs a dead controller left behind (`.in` and `.out`,
    over a day old) are swept under the lock.
- `BENCH_BUILD_LOCK` defaults to the `.bench-lock` beside `BENCH_BUILD_DIR`.
  That is `D:/bench/.bench-lock`, the file `run_game.ps1` takes, so a build
  and a golden on the PC never overlap.
- `build.ps1` uses the same create-new and dead-holder takeover logic as
  `run_game.ps1`. It waits up to an hour, then exits 75 with
  `@xbr-status lock-timeout`. The status line tells it apart from a CLI
  build that exits 75 itself. Every protocol line starts with `@xbr-`, so
  CLI output is never taken for one.
- `BENCH_LOCK_HELD=1` means the caller holds `BENCH_LOCK`, the run host's
  lock. It skips the build lock only when that is the same file: a
  Windows run host that is the build host, with `BENCH_LOCK` equal to
  `BENCH_BUILD_LOCK`. A caller that holds the Deck's flock still takes
  the PC's lock.

## CLI surface

| setting | meaning |
|---|---|
| `BENCH_BUILD_HOST` | the ssh alias of the Windows build host; empty means this machine builds |
| `BENCH_BUILD_DIR` | the drive path of its trees (required with a build host) |
| `BENCH_BUILD_LOCK` | its lock file (default: `.bench-lock` beside the dir) |
| `BENCH_BUILD_CLI` | the CLI tree to send (default: the running CLI). build-all sends the CLI under test this way |
| `BENCH_BUILD_GAME_FILES` | the host's own game files, linked in for `package` (a build needs none) |

- `BENCH_BUILD_HOST` requires `BENCH_BUILD=local`: the build host compiles,
  and this machine ships.
- The run host can be different, and usually is: the Deck, or the PC itself.
- `ship.local_exe()` returns the pulled exe, so no other command changes.
- `bench build windows` (and every command that builds before shipping)
  goes to the build host.
- `bench buildhost run package windows --pull dist` makes test-install
  zips. `--pull` refuses:
  - absolute paths, drive paths and `..`, in either `/` or `\` form;
  - the game files folder.
- With a build host set, `ship` warns when the exe built on this machine
  is newer than the pulled one, because the pulled one is what ships.
- The CLI that is sent must be a git checkout (`cli_dir.is_checkout`).
  Under uvx, set `BENCH_BUILD_CLI`.

### Packages for test installs

`bench buildhost run package windows [--patch-from BASE] --pull 'dist/*'`
packages on the PC. Two things make this work:

- A package holds the game files, and the build host gets none from here.
  `BENCH_BUILD_GAME_FILES` names the PC's own copy (for BLiNX 2,
  `D:/bench/BLiNX2/game_files`). `build.ps1` links it into the tree as a
  junction: a link, not a copy, and ignored by git. The junction exists
  only for that call, so the tree never holds it between calls:
  - The `finally` block removes it non-recursively
    (`[IO.Directory]::Delete`). Windows PowerShell's recursive
    `Remove-Item` follows a junction into its target, so it is never
    used here.
  - A link left from an earlier call is replaced, even when it is
    dangling or points at another target.
  - A real folder at that path is refused.
  - A build gets no junction, because it needs no game files.
- `package` regenerates a gen/ whose key is stale. On the PC the key's
  inputs (the analysis cache, the Ghidra export) are missing. The first
  real run regenerated gen/ there, and was stopped at its recomp. The fix:
  - `package --stale-gen-ok` keeps gen/ as sent;
  - `buildhost run package` passes it, but only after the checks a local
    package makes, which it runs here first: it refuses a
    `.gen-regenerating` marker and a stale key (the caller's own
    `--stale-gen-ok` skips the key check). It also refuses a gen/ that
    changed here while it was being sent;
  - any non-build run drops `gen-digest.txt`, so the next build sends gen/
    again in case the command changed it.

  The pinned CLI (33390f64) predates the flag. Until the pin moves, set
  `BENCH_BUILD_CLI` to this branch's CLI for package runs.

That stopped run also left `.gen-regenerating` beside gen/, and the CLI
then refused the complete gen/ that came next. `build.ps1` now removes the
marker whenever it unpacks a gen/ that was sent.

Measured: `buildhost run package windows --pull 'dist/*-patch-from-*'` for
BLiNX 2 (f3afb82) made a 53.3 MB patch over the PC's installed
20261024.0426-c41815bf, against a 3.4 GB full bundle. It took 91 s, with
the packaging compile in `build-pkg-win`, and an unchanged rerun took
14 s. The patch folder (apply.exe, files/, patch.json) came back to
`build-win/build-host/pulled/`. Every get is recursive, because a patch
is a folder.

Test installs ship as patches over the install. A patch needs a versioned
base on the PC: either a full bundle made there, or the manifest of the
install it updates. The PC's old BLiNX 2 bundles (2026-10-17) are an
in-place install with no manifest, and are refused as bases.

### How the exe reaches the Deck

The PC does not ship to the Deck itself. The flow is:

1. The controller (the Mac) pulls the exe and checks its sha256.
2. The existing ship step sends it to the Deck's
   `~/xbr-bench/<game>/runs/<sha12>/`.
3. The ship step checks the Deck's copy against the same sha.

This keeps the one ship path, so it needs no ssh trust between the PC and
the Deck. The exe is a few MB, so the extra hop costs seconds.

## Reproducibility against the Mac

The PC and Mac exes are **not sha256-equal**. Their machine code is equal.
All six games were compared section by section (`pecmp.py`, a PE parser):

- **Byte-identical:** `.text`, `.rdata`, `.data`, `.pdata`, `.tls`,
  `.reloc`, `.debug_abbrev`, `.debug_loc`, `.debug_ranges` and the trailing
  data.
- **Different:** `.debug_info`, `.debug_line`, `.debug_str` and
  `.debug_aranges`; `.buildid` (the RSDS/PDB GUID, a hash of the image); and
  3 to 6 header bytes (the PE timestamp and checksum, both derived from that
  hash).

Every differing DWARF string is a mingw-w64 CRT source path baked into the
llvm-mingw release packages. The macos-universal package has the macOS
CI runner's `runner/work/llvm-mingw/...` paths. The ucrt-x86_64 Windows
package was cross-built on Linux, so it has the Linux runner's. There
are 71 occurrences. None of our own paths are embedded:

- The Mac build is path-independent. A build in a fresh worktree equals
  build-all's sha (skates ce98b532 both ways).
- The game sha is not embedded: cat 24f2e30 and f3afb82 give identical
  exes.

What this means:

- **Behaviour and goldens:** the same machine code and data run, so they are
  the same.
- **Symbol addresses:** the same, so crash dumps and the symbolizer agree.
- **Run ids differ:** the run directory id is the exe's sha12, so PC and Mac
  builds of one commit get different run dirs on the Deck. That costs one
  extra exe copy per run, and nothing else.
- **No sha-equality cross-check:** "the PC's exe equals the Mac's" cannot be
  tested by sha256.

Possible follow-up (not in this change): a code digest over the non-debug
sections, recorded in the provenance, that would compare the two hosts
directly.

Making the shas equal would mean patching the packages' DWARF or stripping
debug info, and the symbolizer needs that debug info. Not worth it.

## Measured (2026-10-28)

The PC builds each game's exe at its main head, with toolkit 20606840, CLI
33390f64 and llvm-mingw 20260922. PC times include sending the trees, setup
and the pull. Mac times are build-all's Windows leg at 8 jobs.

| game | head | PC | PC time | PC sha256 | Mac sha256 | Mac time |
|---|---|---|---|---|---|---|
| blinx1 | 81d461b | pass | 89 s (with first setup) | e3611201 | a119db81 | 241 s |
| burnout3 | bd4646a | pass | 69 s | 4b6e07ab | 3761bad3 | 142 s |
| ssx3 | e1c9c6d | pass | 54 s | 64a2270a | 464c85f2 | 113 s |
| spartan | ee86cac | pass | 56 s | 48211edd | 87808c47 | 72 s |
| skates | 0961a49 | pass | 7 s (26 s with setup) | 0d04176c | ce98b532 | 11 s |
| blinx2 | f3afb82 | pass | 91 s | 5e6c4779 | 8d8966a7 (24f2e30) | 968 s |

For all six games, the code and data sections are identical. The shas
differ only in the CRT DWARF paths, the build id and the header bytes, as
described above.

## build-all's Windows leg

`notes/build-all.sh` gets a `WIN_BUILD_HOST` leg. It runs `bench buildhost
build` per game with `BENCH_BUILD_CLI` and `XBOXRECOMP_DIR` set to the trees
under test. It runs outside the Mac lock and takes the PC's lock. Its trees
are its own (`WIN_BUILD_DIR`, default `D:/bench/build-matrix`), never the
benches' `D:/bench/build-bench`. The Mac cross-build leg remains when
`WIN_BUILD_HOST` is unset. This is drafted for the orchestrator, because
the file is shared.

## Open follow-ups

Filed from the review rather than fixed here:

- **No benchdb build record for a PC build**. `integrate
  --golden` prints no regression lines for it.
- **setup is judged by the CMake and Ninja files existing,** not by
  their pins.
- **`BENCH_BUILD_JOBS`:** `BENCH_JOBS` from the Mac caps the PC's cores.
  
- **Generic paths in the public help and error text** (`D:/bench`), and
  **`pulled/` and the PC's `dist/` are never cleared**.
