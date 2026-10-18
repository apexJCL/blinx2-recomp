Conventions: **CLI** = branch `feat/dump-import` off `main` 2b95e72 (v0.5.1)
in a fresh CLI worktree the orchestrator names (`wt/onecmd/xboxrecomp-cli`
sits on an old docs branch and is not reused), commits authored and committed
as the noreply identity, no tracker ids, host names or private paths; **cat**
= branch `feat/dump-import` off `main` (ddc59a8 or later) in `wt/onecmd/cat`.
One agent, CLI first (phases 1-2), then cat (3-4), then the gates and the
merge (5-6). The toolkit is not touched. No run uses sound, the Linux/Proton host or the
Deck; the one run against the real dump (3.2) is local to the Mac and keeps
nothing. Design decisions are cited as D1-D12. Tasks marked **needs-user**
need the user's disc image, which is not in the workspace.

Phase map:

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 1 Reader, import module, tests | CLI | M | - |
| 2 Commands, help, doctor, docs, release | CLI | S | 1 |
| 3 cat: pin, README, packaging doc, ignores | cat | S | 2 committed |
| 4 Real-dump check and the end-to-end run | cat (Mac) | XS | 3 |
| 5 Review and merge | main session | S | 4 |
| 6 Follow-through | main session | XS | 5 |

## 1. CLI: the reader, the import module and its tests

- [x] 1.1 Vendor the reader (D1): `git -C ../../../xboxrecomp show
  origin/main:tools/xiso/xdvdfs.py > src/xboxrecomp_cli/xdvdfs.py` (the
  fork's `origin/main` mirrors upstream; the bytes equal
  `posix-host/portability`'s); prepend the two header comment lines, leave
  the docstring untouched, `uv run ruff format` it. `LICENSES/
  xboxrecomp-MIT.txt` = upstream's `LICENSE` verbatim; `pyproject.toml`:
  `license-files = ["LICENSE", "LICENSES/*"]` under `[project]` and
  `"src/xboxrecomp_cli/xdvdfs.py" = ["E741"]` under per-file-ignores.
  `docs/origin.md`: a "From the toolkit" section citing upstream `main`, the
  licence file and the divergence rule (fix in both, offer upstream). Commit
  subject ends in `(upstream 6d69551)`; no upstream author email in the
  repo. Verify:
  `git -C ../../../xboxrecomp show origin/main:tools/xiso/xdvdfs.py | uv run ruff format --stdin-filename src/xboxrecomp_cli/xdvdfs.py - | diff - src/xboxrecomp_cli/xdvdfs.py`
  shows only the header (fix the relative path if the layout differs);
  `uv run ruff check .` is clean.
- [x] 1.2 `tests/test_dump.py`, the image builder (D9): port `_build_image`
  with the XBE payload from `tests/test_xbe.py`'s `header()` (title and
  title ID as arguments), entries as a list so a test can master a bad name
  or a looped directory, and a sparse write for a large base. Port the
  toolkit's three pinned properties as the first three tests: base found at
  `0x0` and at `0x18300000` (`iso.base` asserted), per-sector walk reaches a
  subdirectory's files, a non-image raises `XisoError`. Verify:
  `uv run pytest tests/test_dump.py -k reader`.
- [x] 1.3 `src/xboxrecomp_cli/dump.py` (D2-D7): `xbe_name(game)` (the
  relpath, refused outside `game_files`), `classify(path)`,
  `read_xbe(source)`, `verify_title(source, game)` (the message with the
  certificate's title), `check_source_place(source, game)` (D4 step 2),
  `listing(source)` with the name, loop and depth checks (D5 "Names"),
  `plan(source, game)` (count, bytes, free space with the same-volume macOS
  exception, the marker's verdict: `fresh`, `same`, `adopt`, `other`,
  `by-hand`), `recover(game)` (D7's `.old`/`.partial` rules, run first),
  `run_import(path, replace=False, link=False, check=False)`: `.partial`
  extraction or clone copy (a walk that excludes nothing, `lib.copy_file`,
  `lib._clonefile`, the mode fix), size pass, swap with `rmdir`/`.old`/
  retried `rename`, marker, the unknown-dump warning; `--check`; `--link`
  with no marker and the one-line warning; `rmtree` with the `onexc` chmod
  handler; every refusal a `CliError`; every command name through
  `host.cli_name()`. Marker schema and identities per D6, written into `.partial` before the swap.
  Verify: the D9 cases, one test each (wrong title with no `.partial` left;
  empty root and marker fields; rerun no-op; adopt; by-hand and
  other-source refusals; `--replace` swap and `.old` gone; crash after the
  first rename recovered, `.old` beside a marked tree removed; stale
  `.partial` removed after the title check; the eleven name, loop and depth
  refusals; source inside and containing `game_files`; `--check` on a
  changed byte and an ignored extra; folder copy with `UDATA/` kept and
  `--link`'s identity, warning and Windows refusal; free-space refusal and
  the same-volume exception; folder without the XBE refused; non-image
  hint).
- [x] 1.4 `package/lib.py`: `GAME_FILES_EXCLUDE` gains `.xbr-dump.json`
  beside `.DS_Store` (both in the default tuple and in `configure`).
  Verify: `tests/test_package_lib.py` asserts `game_file_excluded(
  ".xbr-dump.json")` and that a staged payload from a tree with the marker
  has none.
- [x] 1.5 `bench/sync.py` (D12): two `None` slots in `GAME_EXCLUDES` filled
  by `game_excludes()` with `"/" + data.game_files + ".partial"` and
  `".old"`; `tests/testdata/game/.gitignore` gains `game_files.partial/` and
  `game_files.old/` after `game_files`. Verify: `tests/test_second_game.py`
  asserts both excludes for cat's manifest;
  `tests/test_bench_cli.py::test_sync_excludes_follow_gitignore` passes.

## 2. CLI: commands, help, doctor, docs and the release

- [x] 2.1 `main.py` (D2): `command("import", ..., _cfg_import)(cmd_import)`
  with `PATH`, `--replace`, `--link`, `--check`, listed with the player
  commands; `package` gains `--dump PATH` and `--replace` (`_cfg_package`;
  `--replace` without `--dump` is an argparse error) and
  `package.cmd_package` runs `dump.run_import` first and shows it in the
  plan, and reports a leftover sibling (D7) when `--dump` is absent; the
  shorthand before `parse_known_args`: a first argument that is not a
  command, a tool, `bench` or `new`, and exists, becomes `package
  <native_target()> --dump PATH` with the rest of argv kept; a non-existent
  non-command adds the one hint line to argparse's error. Verify:
  `tests/test_cli.py` cases: a path argv is rewritten; `PATH --replace` and
  `PATH --hud-pack` reach `package` with those options; a folder named
  `doctor` runs doctor; a missing path shows `invalid choice` plus the hint;
  `package --replace` alone is refused; `package --dump` with a differing
  hand-placed `game_files/` refuses with D7's message.
- [x] 2.2 `helptext.py` (D8): the `@slug@ /path/to/dump` block first and
  `@slug@ import PATH [--replace]` under the player commands; 3.9 syntax
  kept. `doctor.py`: `(imported from <basename>, <date>)`, `(linked to
  <source>)`, the leftover line, the new MISSING line and `next_step`
  (`doctor.py:292`); `setup.host_blockers` (`setup.py:70`),
  `pipeline.dump_hint()` and `scaffold`'s step 1 say "run '<cli_name> import
  PATH' ... or put the files in <game_files>/". Verify: `python3
  src/xboxrecomp_cli/helptext.py tests/testdata/game blinx2` prints the
  block; `tests/test_cli.py`'s help, `doctor` and `setup` tests updated;
  `git grep -n '\./blinx2\|\./@slug@' src` finds no new literal.
- [x] 2.3 `scaffold.py` (D12): `@GAME_FILES@.partial/` and `@GAME_FILES@.old/`
  after `@GAME_FILES@/` in the `.gitignore` template (`*.iso` and `*.xiso`
  are there already); `xbr new`'s closing lines name `import`. Verify:
  `tests/test_scaffold.py::test_gitignore_and_attributes` wants both lines.
- [x] 2.4 Docs: `README.md`'s quick start comment (line 50: `./mygame import
  /path/to/game.iso`, or the folder, or put the files in `game_files/`) and
  the Commands table (lines 75-87: `mygame PATH`, `mygame import PATH`,
  `package --dump`); `docs/commands.md`: `### mygame PATH` and `### mygame
  import PATH` under "Player commands" in the existing style;
  `docs/manifest.md` `[data]` paragraph on the marker, the siblings and the
  exclusion. No changelog exists: the release notes are drafted for the tag
  message (2.5). No tracker id, host or private path anywhere. Verify:
  `git grep -n -i 'blx-\|bench host' -- README.md docs src tests` is empty
  except the OS-name sense already present (per the audit rules).
- [x] 2.5 Release (D11): `__version__ = "0.6.0"`. Gates: `PYTHON_COLORS=0
  NO_COLOR=1 uv run pytest tests`; `uv run ruff check . && uv run ruff format
  --check .`; `bash scripts/audit-public.sh main..HEAD`. The orchestrator
  squashes to `main` and tags `v0.6.0` (annotated, the release notes as its
  message) on the squash commit; the public push waits for the next round.

## 3. cat: pin, README, the packaging doc and the ignores

- [x] 3.1 `game.toml`: `[cli] tag = "v0.6.0"` with its commit (the branch tip
  during the work; the orchestrator moves it to the squash sha, as
  `cli-tag-pins` 2.1 did). In the worktree `find_cli` picks
  `../xboxrecomp-cli`, the sibling of `wt/onecmd/cat`, so every `./blinx2`
  run here sets `XBOXRECOMP_CLI_DIR` to the CLI worktree of phase 1.
  Verify: `./blinx2 doctor` runs that CLI and prints the new `game files:`
  line; `uv run pytest scripts` (the pin and wrapper tests).
- [x] 3.2 Run on a real BLiNX 2 image (2026-10-11, CLI v0.6.0 2ad3699,
  cat main, runs/onecmd/08-blinx2-image-check.log): the operator's
  `blinx2.xiso.iso` (285 files) against `game_files/` (485 files) found 201
  differences and exited 1, with nothing written. The image is a different
  dump: its XBE is the old known one (aa186954, the goldens' dump; 2048
  bytes shorter than 0c57fd72 in game_files), and it lacks 200 files
  (fr/ge/it/jp/sp language packs, 181 voice/*.adx, 9 adx/song_*). The check
  did its job; the image is not imported over game_files.
  Run on a real Burnout 3 image (2026-10-11, CLI d8734ed, b3
  scratch clone): the operator's XISO (base 0, 715 files, 2.5 GB, the
  known XBE) matched the folder import of their extraction by name, size and
  sha256 both ways round (`--check`), with no case differences; the image
  imported into an empty tree and a rerun was a no-op; BLiNX 2 refused it by
  title. The BLiNX 2 image check stays **needs-user** until the operator
  provides one. Real-dump check on the Mac, local only (D5, D9):
  `./blinx2 import <the user's image> --check` against the existing
  `game_files/`, in the worktree with `game_files` as a symlink to the main
  checkout's, or from a scratch root under `runs/onecmd/` holding a fresh
  import; compare names (case included), sizes and sha256; record the
  verdict and the image's partition base in `TASKS.md` (no paths, no hashes
  beyond the XBE's, which `game.toml` already lists). A case or byte
  difference is a finding for the design's Risks, not a change to the
  reader. Clean up through `notes/cleanup-derived.py`.
- [x] 3.3 `README.md` (D10): "What you need" to three rows with git named
  plainly and Python from python.org on Windows; "Install and run" to
  "Build the game" with the clone and `cd` on two lines, `./blinx2
  /path/to/your/BLiNX2.iso` and the PowerShell form, the what-happens
  paragraph, the by-hand sentence, `package <target>` and `doctor`, the
  install table as it is, the `#install-and-run` link (line 229) updated;
  the "files are missing" quick fix; the HUD pack order sentence; the
  developer "Build from source" comment. The platform table, options, known
  issues, screenshots and help sections are otherwise untouched. Verify:
  `uv run ruff check . && uv run ruff format --check .`; `uv run pytest
  scripts`; a read-through for a player who has never used git (every
  command shown once per shell; no `&&`; no dangling anchor).
- [x] 3.4 `docs/packaging.md` section 1 (the dump sentence, line 53) and
  section 7 (the missing-files entries, lines 357-365) say the import
  command and the by-hand route. `TASKS.md`: the `runtime-missing-files`
  follow-up "ISO-against-extraction check" is marked done by `import
  --check`.
- [x] 3.5 `.gitignore` (D12): `game_files.partial/` and `game_files.old/`
  after `game_files`; `scripts/test_gitignore.py` runs `git check-ignore -q`
  on `game_files/x`, `game_files.partial/x` and `game_files.old/x`. Verify:
  `uv run pytest scripts/test_gitignore.py`.

## 4. Gates

- [x] 4.1 CLI: the gates of 2.5 on the final tip.
- [x] 4.2 cat: `uv run pytest scripts`; `uv run ruff check . && uv run ruff
  format --check .`; `openspec validate onecmd-build --strict`.
- [x] 4.3 (folder route done 2026-10-11; the image route stays needs-user) **needs-user** for the image; falls back to a folder source. Mac
  end to end, headless, no sound: from a scratch clone of the cat branch
  under `runs/onecmd/` with `XBOXRECOMP_CLI_DIR` at the CLI worktree,
  `./blinx2 import <image>` (or `./blinx2 import <the main checkout's
  game_files>`, a folder source, when the image is not at hand) then
  `./blinx2 package macos` with
  `DEVELOPER_DIR=/Library/Developer/CommandLineTools`; the bundle's
  `manifest.json` lists no `.xbr-dump.json`, `game_files/default.xbe` in the
  payload is byte-identical to the import's, and a second `./blinx2
  <source>` prints the no-op line and only build and package in the plan.
  The Metal golden is not affected (no runtime change) and is not rerun for
  this change; the scratch clone is removed through
  `notes/cleanup-derived.py`.
- [x] 4.4 No Proton run: nothing under `src/`, the toolkit, the renderer,
  audio or kernel changes. If the review disagrees, `blinx2 bench golden`
  on the Linux/Proton host under the run lock is the one run to add.

## 4R. Review fixes (merge after fixes, no blockers)

- [x] 4R.1 The marker goes into `.partial` before the swap, so the rename
  finishes the import; a copy or `--link` beside an unmarked
  `game_files.old/` is refused before anything is copied; a symlinked
  `game_files` counts as a finished swap (D6, D7). Tests: a crash right
  after the swap; the refusal and the adopt that clears it.
- [x] 4R.2 An unreadable folder, in the source or `game_files/`, and a
  link to a missing file stop the import and `--check` by name (D4 step 6).
- [x] 4R.3 The old tree's `game_files_exclude` entries carry into the new
  tree, with or without `--replace`, the source winning a shared name and
  said; `--link` over them refused without `--replace` (D7 "Kept names").
- [x] 4R.4 Nits: size-0 directories not taken for loops and empty
  directories made; the title check reads 64 KiB; a failed `.old` removal
  is a line; the disk hint only for a full disk; one file count for the
  import, the plan and `--check`; a refused marked source says which
  identity parts differ.
- Follow-ups, not in this change: adopting the marker for a moved or
  re-downloaded image (refused, now with what differs); non-ASCII names in
  the reader (an upstream fix).

## 5. Review and merge (main session)

- [x] 5.1 Review of both branches (the CLI's reader copy against
  upstream's file, the refusal paths, the name checks, the `--replace` swap
  and its recovery, the README as a first-time player). Fixes go back to
  the branch's agent.
- [x] 5.2 CLI: squash to `main` as `dump: import a disc image or folder into
  game_files; 0.6.0`, noreply author and committer, tag `v0.6.0`
  (annotated, release notes in the message); cat: move `[cli] commit` to
  the squash sha, then squash to `main` as `docs: one command from the disc
  image; pin CLI v0.6.0`, body naming the branch and tip sha. `openspec
  archive onecmd-build` after both land.

## 6. Follow-through (main session)

- [ ] 6.1 Copy untracked notes to `notes/onecmd/`; remove both worktrees
  (`git worktree remove --force` and `rm -rf wt/onecmd`), keep the branches;
  move any run under `runs/onecmd/` through `notes/cleanup-derived.py`.
- [ ] 6.2 the Linux/Proton host: sync and rebuild `~/xbox-recomp` under the run lock and
  run `blinx2 bench integrate --golden` as every integration merge does (the
  pin changed; the game did not).
- [ ] 6.3 `TASKS.md`: the tracker item done with the shas; b3 follow-up noted (pin the
  CLI release, its README's dump sentence); the public push round queued
  (CLI first, then cat; audits and the noreply identity as the rules say).
