# new-game-portable-host: tasks

Worktrees: `wt/porthost/xboxrecomp` on `feat/new-game-portable-host` off
`posix-host/portability` 38717b2; `wt/porthost/xboxrecomp-cli` on
`feat/new-game-portable-host` off `main` 9e400eb (CLI commits authored and
committed as the noreply identity, no tracker ids, hosts or private paths in
the CLI); `wt/porthost/cat` on `spec/new-game-portable-host` (this spec, off
cat `main` 127572f). cat and b3 themselves do not change.

The scratch game: `runs/porthost/tca/`, made by `xbr new` from the CLI
worktree with `XBOXRECOMP_DIR` at the toolkit worktree and `--xbe
spartan/tca/game_files/default.xbe` (read in place), its `game_files/` a
symlink to `spartan/tca/game_files`. `spartan/tca` is never written.
Dumps and logs under `runs/porthost/`, notes in `notes/porthost/NOTES.md`.

Rules: Mac builds with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`;
Mac runs with `SDL_AUDIODRIVER=dummy` and `RECOMP_HEADLESS=1`, kill by PID
only. The Proton host is the Deck (`ssh <bench-host>`, `flock -w 3600
~/.recomp-run.lock`, BLiNX first); native Windows is `bench host-win` and the
user is asked before the PC is booted into it. Proton and Windows runs never
overlap.

## 1. Spec and worktrees
- [x] 1.1 This spec on `spec/new-game-portable-host` (no separate spec pass).
- [x] 1.2 Toolkit and CLI worktrees and branches as above; the scratch game directory.

## 2. Toolkit (`wt/porthost/xboxrecomp`)
- [x] 2.1 `templates/new-game/src/main.c` per D1-D6: `host_main`, the host sections, `host_stdio_setup`, `host_install_crash_handler` (VEH unchanged; POSIX sigaction, `xbox_PosixMmioFault` first, `crash_printf`, `dladdr`, the arm64 frame walk), `host_report_fatal`, `xbox_HostWindowMain` from POSIX `main`, the Metal default on Apple, the `recomp_dispatch_init` declaration. The `YOUR_GAME_*` lines and the comment marks keep their exact text.
- [x] 2.2 `templates/new-game/CMakeLists.txt` per D7: the OpenSSL hoist, `if(WIN32)` around the import libraries, `-Wno-parentheses-equality` on the generated sources under Clang.
- [x] 2.3 `tests/template_main/` per D10: the standalone project, `stubs.c`, the two ctests; added to the CLI's Proton standalone list (`bench/host/tests.sh` 36) in 3.2.
  Done (b9dc8c5): the ctests run through `run.cmake`, which takes the
  cross emulator, so the same checks run under Proton. Deviation: the
  Windows `host_report_fatal` skips `MessageBoxA` when `RECOMP_HEADLESS` is
  set (D5 said always), since the dialog would block the unattended
  Proton ctest; a run without the key still gets the dialog.
- [x] 2.4 Mac gate: toolkit build with `DEVELOPER_DIR` set; `tests/posix_ctest.sh <build-dir>` 0 FAIL, `template_main` among the passes. `pytest tools/recomp tools/disasm` not needed (no tool changed).
- [x] 2.5 cat and b3 still build against the toolkit worktree (`XBOXRECOMP_DIR`): `blinx2 build macos` in the main cat checkout's build dir is not touched; use a scratch build dir under `runs/porthost/` for each. No golden: the runtime libraries did not change, and the build is the evidence.
  Done: `runs/porthost/build/{cat,b3}-macos` (Ninja, Release,
  `XBOXRECOMP_ENHANCE=ON`, `XBOXRECOMP_DIR` at b9dc8c5) both built, rc 0;
  the main checkouts' `git status` unchanged.

## 3. CLI (`wt/porthost/xboxrecomp-cli`) and the scratch game
- [x] 3.1 `scaffold.py` per D9: `GAME_TOML` targets and comment, the host-dependent `summary()` step 3, the README template, the Win32-only-template note in `patch_template`.
- [x] 3.2 Tests per D9 in `tests/test_scaffold.py`; `bench/host/tests.sh` learns `template_main`. `uv run pytest tests` with `XBOXRECOMP_DIR` at the toolkit worktree (so `test_real_template_patches_match` runs) and `uv run ruff check . && uv run ruff format --check .`.
  Done (CLI be11951): `template_main` went into `tests.sh`'s `optional`
  list, not `standalone`: cat's and b3's pinned toolkits lack the dir, and
  `standalone` stops with "toolkit too old?" on a missing one. The bench's
  step header and `tests/testdata/bench_parity.json` follow. CLI suite: 540
  passed, `test_real_template_patches_match` ran (and fails against the
  Win32-only template at 38717b2, as it should); ruff clean.
- [x] 3.3 The scratch game: `xbr new runs/porthost/tca --xbe spartan/tca/game_files/default.xbe --offline --toolkit-commit <toolkit worktree HEAD> --cli-commit <CLI worktree HEAD>`, then `./tca setup --no-toolkit` with `XBOXRECOMP_DIR` at the toolkit worktree (main.py 114), the `game_files` symlink, `analyze`, `recomp`. `./tca build windows` and `./tca build macos` both succeed with the copied `main.c` and `CMakeLists.txt` unedited. Note the warning count of the Windows build before and after 2.2 for the record.
  Done: analyze 31 s (17356 functions), recomp 42 s; both builds OK,
  `main.c` and `CMakeLists.txt` md5 unchanged. `--offline` needed
  `config/setup-pins.json` and `uv.lock` copied from `spartan/tca` (read
  only) and its llvm-mingw cloned into `third_party/`. Windows build
  warnings: 1006 before 2.2 (886 `-Wparentheses-equality`), 120 after (0);
  macOS 86.
- [x] 3.4 Mac boot, headless Metal, 120 s watchdog, `RECOMP_FB_DUMP` under `runs/porthost/<stamp>/`, `RECOMP_TRACE=flip`: first frames dumped, or a complete `[CRASH]` report (signal, host PC and generated function, guest registers, guest return addresses, native stack) and death by the original signal. Record which, the flips/s if any, and whether `RECOMP_TITLE_KEVENTS=1` changes the outcome (D6) as a note for the Spartan port, not a change here.
  Done: a complete `[CRASH]` report, no frames, no flips
  (`runs/porthost/20261014-165058-mac-metal/`): SIGSEGV in
  sub_001B807B+0x56C (a heap free of the garbage pointer 0x89CF8B41 under
  the CRT initialisers sub_001B5E10 -> sub_001F2440), guest registers and
  VA, guest return addresses, native stack down to `host_main`; exit 139
  (killed by SIGSEGV). `RECOMP_TITLE_KEVENTS=1` changes nothing
  (`...-165207-mac-metal-kevents/`): the crash comes before any title
  KEVENT. With the tracker item's POP32 macro (7ca1aa4) applied in scratch copies
  only (`runs/porthost/tk-pop32`, `runs/porthost/tca-pop32`, whose
  `gen/recomp_types.h` is the one `recomp` would copy; not on this branch)
  the run gets past static init to the known second crash
  (`...-165320-mac-metal-pop32/`): SIGSEGV reading 0xFFFFFFFF in
  sub_0025A92C+0x70, guest stack from 0x001B16A3, exit 139.
- [x] 3.5 Proton on the Deck, the `build windows` exe rsynced into a scratch dir there, run through umu with `RECOMP_STDIO_LOG=<file>` (what `run_game.sh` 24 does): the boot lines and, when it crashes, the `[CRASH]` report are in the file. A second run with the variable unset to confirm nothing else changed in the console log. The `template_main` ctest under Proton (the CLI's standalone list).
  Done (`runs/porthost/20261014-170001-deck-proton/`, GE-Proton11-9,
  a scratch prefix): with `RECOMP_STDIO_LOG` the file has the boot lines
  and the VEH `[CRASH]` report (Access violation, the same guest state and
  return addresses as the Mac run); umu exit 5 both runs. Without it the
  console log equals the first run's apart from the prefix-creation line
  (umu-run drops the program's stdout and stderr either way, so the D4
  `[THREAD]` lines are not visible there). `template_main` under Proton,
  cross-built on the Deck in `xbr-build`: 2/2 passed. Found: the VEH's
  native stack is empty and no function name prints, because llvm-mingw
  links DYNAMIC_BASE + HIGH_ENTROPY_VA (the exe ran at 0x6FFFF...) and the
  walk keeps only 0x140000000-0x150000000, and dbghelp cannot read the
  DWARF symbols. The VEH is unchanged here (D3); a follow-up.
- [x] 3.6 Native Windows (`bench host-win`), if the user agrees to boot it: the same exe once, with and without `RECOMP_STDIO_LOG`. Otherwise the Proton run is the Windows evidence and this line says so.
  Not run: the Proton run (3.5) is the Windows evidence. Native Windows
  was not booted (the Deck is the Proton bench and no request was made).
- [x] 3.7 Docs per D9: `README.md` "macOS", `docs/porting.md` "macOS as a target" (incl. the D6 note and the old-pin case).

## 4. Review and merge (orchestrator)
- [x] 4.1 Review of both branches; fixes go back to this change's agent.
  Review fixes (agent, `runs/porthost/REVIEW.md`): toolkit 24eac0a (F1 hint
  names `YOUR_GAME_DIR`, F3 kill-sent SIGSEGV/SIGBUS re-raised, F11
  stdio-log open checked, F5 `RECOMP_HEADLESS` description); CLI 4bc2676
  (F6 Homebrew line in porting.md, F10 step 3 on a Mac with a Win32-only
  template); this spec F2 (D2 and the requirement list the allowed Windows
  differences, the guest-main DPC marking among them) and F5 (D5,
  `docs/env.md`). Re-run: posix ctest 56 pass / 0 FAIL; template_main
  cross-built clean and 2/2 under Proton; CLI 541 passed, ruff clean.
  F4, F7, F8, F9 are TASKS follow-ups.
  Merged 2026-10-14: toolkit 51aa402 (squash of 24eac0a), CLI 4ef60a4
  (squash of 4bc2676, noreply), this spec on cat main.
- [x] 4.2 Merge: toolkit `git merge --squash` onto `posix-host/portability` (`templates: new-game main.c boots on Windows and macOS`, the body naming the branch and tip sha); CLI `--squash` onto `main` with `--author` and `GIT_COMMITTER_*` set to the noreply identity; this spec `--ff-only` or squash onto cat `main`.
- [ ] 4.3 After the merge: `notes/porthost/` from the agent's notes; the referenced dumps with `cp -c` into `runs/porthost/`; worktrees removed, branches kept; `cat/TASKS.md` updated (the Linux-target and `RECOMP_GAME_FILES`-in-template follow-ups; the D6 KEVENT observation for Spartan; the upstream PR 5 note; the `xinput1_4` coordination). The Deck's post-merge `blinx2 bench integrate --golden` is not required by this change (no runtime library changed) and is left to the next merge that needs it.
- [x] 4.4 `spartan/tca` re-made with a fresh `xbr new` (the user, 2026-10-14: "fresh scaffold"), from the released CLI with the dump read in place, after the toolkit and CLI push rounds (6.1); not hand-patched, and not from an agent worktree (D11).
  Done 2026-10-14: `xbr new spartan/tca --xbe spartan/spartan.xiso.iso
  --cli-tag v0.6.7 --toolkit-commit ac27175` from the CLI main checkout at
  v0.6.7; the old tree kept as `spartan/tca-old` (its two main.c edits, the
  stdio-log stopgap and the dispatch declaration, are both in the new
  template), its extracted `game_files/` and llvm-mingw moved over. analyze
  (17,356 functions), recomp, `build macos` and `build windows` pass with
  the scaffold unedited. Mac headless Metal boot
  (`runs/spartan/20261014-210324-mac-metal-pinned/`): exit 139, the known
  read of 0xFFFFFFFF in sub_0025A92C+0x70, no frames.

## 5. Tracker and hand-back
- [x] 5.1 The tracker item updated with the commit shas, the acceptance outcome (3.4, 3.5) and the open questions below.
  Done: the acceptance comment and `pt review` (In Review), with the Windows
  VEH native-stack gap added to the open questions.

## 6. Public push (a later round, noted here for the order)
- [x] 6.1 The toolkit fork's round (`blinx2/portability`, a new `blinx2-v0.3.x` tag) goes out before the CLI release that writes both targets, so a public `xbr new` resolves a branch head whose template is two-host (D9's note covers the window in between). The CLI's `scripts/audit-public.sh` and the noreply-only check as usual.
  Done 2026-10-14 (push round 7): toolkit `blinx2/portability` ac27175, tag
  `blinx2-v0.3.1`; CLI v0.6.7 (a7cdc15). The CLI went out about three
  minutes before the toolkit, against this order; no `xbr new` ran in that
  window.

## Decided by the user (2026-10-14)
- Metal is the template's Apple backend default when `RECOMP_PB_BACKEND` is unset ("yes Metal default on the Mac"; D4).
- `spartan/tca` is re-made with a fresh `xbr new` after the merge, not hand-patched ("fresh scaffold"; D11, task 4.4).
- The template CMake's `xinput` link is the tracker item's (Mac-built exes import `XINPUT1_3.dll`, which stock Windows lacks; the fix is `xinput1_4`). This change only moves the line under `if(WIN32)` (D7).
