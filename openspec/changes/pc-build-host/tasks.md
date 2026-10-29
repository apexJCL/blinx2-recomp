## 1. CLI (`feat/pc-build-host` off `main` 2917b2d)

- [x] 1.1 `bench/buildhost.py`:
  - snapshot (with deterministic stash commits), bundles, gen tarball;
  - state probe, build, pull with sha256 checks, provenance
- [x] 1.2 `bench/host/windows/build.ps1`:
  - fetch and checkout, gen unpack, setup judged by its tools;
  - build under the PC lock, `file` lines
- [x] 1.3 Config: `BENCH_BUILD_HOST`, `BENCH_BUILD_DIR`, `BENCH_BUILD_LOCK`, `BENCH_BUILD_CLI`;
  help rows, doctor line
- [x] 1.4 `ship.local_exe` and `build_local` through the build host; `bench buildhost build|run --pull`
- [x] 1.5 `BENCH_BUILD_GAME_FILES` junction; `package --stale-gen-ok`, passed by `buildhost run package`
- [x] 1.6 `tests/test_bench_buildhost.py` (22 cases), a `package_plan` case in test_cli; `uv run pytest tests`, ruff check and format

## 2. cat (`feat/pc-build-host` off `main` f3afb82)

- [x] 2.1 This spec

## 3. Verify

- [x] 3.1 All six games built natively on the PC at their main heads; table in design.md
- [x] 3.2 Section comparison against the Mac cross-builds: code and data identical, debug paths differ
- [x] 3.3 BLiNX 2 patch package made on the PC and pulled (53.3 MB)
- [x] 3.4 BLiNX 2 D3D11 golden on the PC (`BENCH_HOST_OS=windows`) from the PC-built exe 5e6c4779: attract pass-with-known, stage1 pass, story pass-with-known; 34.7, 33.5 and 49.5 flips/s, all above their floors
- [ ] 3.5 Deck/Proton golden from a PC-built exe. Deck slot reserved for the user's testing; orchestrator
- [x] 3.6 Review before merge: fix first (`notes/pc-build-host/review-ITEM.md`)

## 5. Review fixes (round 2)

- [x] 5.1 H1: `tar -m`; gen/ objects dropped on each unpack
- [x] 5.2 H2: per-call `.in/<call>` and `.out/<call>`; gen/ digest computed on the host under the lock, `gen-moved` resend; tarball sha256 checked
- [x] 5.3 H3: no bundle when the commit is an ancestor of the host's head
- [x] 5.4 M1: `buildhost run package` runs the marker, stale-key and gen-changed checks
- [x] 5.5 M2: `lock_held` only for the build host's own lock
- [x] 5.6 M3: ship warns when the exe here is newer than the pulled one; M5: per-call junction
- [x] 5.7 L1 `@xbr-` protocol prefix, L2 lock status line, L3 `\` and game files in `--pull`, L4 `is_checkout`, L8 per-call ref
- [x] 5.8 Tests for each; follow-ups filed for M4, L5, L6, L7 and the L3 cleanup
- [x] 5.9 build-all: own `WIN_BUILD_DIR`; CLAUDE.md draft in `notes/claude-md-draft.md` (worktree)
- [ ] 5.10 Re-review

## 4. Orchestrator (after merge)

- [ ] 4.1 CLAUDE.md: post-merge Windows exe built on the PC; build-all's Windows leg (wording in `wt/pc-build-host/notes/claude-md-draft.md`)
- [ ] 4.2 `notes/build-all.sh`: `WIN_BUILD_HOST` leg (diff drafted in the hand-back)
- [ ] 4.3 Move the CLI pin once the CLI change lands
