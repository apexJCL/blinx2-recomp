Worktrees: `wt/spartan/cat` (branch `spec/spartan-xgasm-crash`, this spec). For implementation: a CLI worktree off `xboxrecomp-cli` `main` (a7cdc15, v0.6.7) for D1; a toolkit worktree on a new branch off `posix-host/portability` (ab8bd27) for D3, not the kicknap worktree `wt/spartan/xboxrecomp`, which is on `spartan/kicknap-base`. D1 and D3 are independent and can run in parallel. Raw runs go to `xbox-recomp/runs/spartan/`, notes to `xbox-recomp/notes/spartan-crash/`. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`, and Mac runs are headless with `SDL_AUDIODRIVER=dummy`.

## 0. Spec review

- [x] 0.1 This spec was not written by Fable, so Fable reads it and improves it, then commits the revision on the spec branch.
- [x] 0.2 Implementation starts only from Fable's revised commit. (Implemented from 1b736c3; the user's 2026-10-14 decision holds: `text_only = false` is always the default, no allowlist.)

## 1. CLI default (D1, primary)

- [x] 1.1 `src/xboxrecomp_cli/scaffold.py` `GAME_TOML`: `text_only = false` under `[pipeline.disasm]`, with the comment from design.md D1 (every code section; why; when a title sets it true and lists `extra_sections` instead). Drop the `["D3D", "DSOUND", "XPP"]` example.
- [x] 1.2 `src/xboxrecomp_cli/manifest.py`: `"text_only": (BOOL, False)`.
- [x] 1.3 `docs/manifest.md`: the `text_only` row (default `false`, why it differs from upstream's `--text-only`, when to set it true) and the `extra_sections` row (only read with `text_only = true`, or for a section the sweep would otherwise skip).
- [x] 1.4 Tests (`tests/test_manifest.py`, `tests/test_scaffold.py`, `tests/test_cli.py` as fits): the defaults assertion flips; a fresh offline scaffold's manifest has `text_only` false and `pipeline.disasm_cmds()` carries no `--text-only`; a manifest without the key does the same; the testdata games `game` (text_only true plus sections) and `game2` (false) build unchanged `disasm_cmds()`.
- [x] 1.5 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.
  - Done: `xboxrecomp-cli` branch `fix/scaffold-sweep-all` 59975db, amended after the Opus review to 901593a (author and committer the noreply address). Review fixes: F1 the test docstring's tracker id removed (`git grep 'BLX-[0-9]'` empty); F2 docs/porting.md's `extra_sections` row replaced by a `text_only` row; F3 docs/manifest.md says the PE data sections are skipped by name. Gates rerun on 901593a: pytest 543 passed, ruff clean, audit-public clean, argv hashes unchanged. 1.1 to 1.4 are in that commit; pipeline.py's disasm comment was updated to match. Tests: `test_minimal_defaults` flips; new `test_a_manifest_without_text_only_sweeps_every_section` and `test_shipped_games_disasm_flags_unchanged` (test_manifest.py); `test_offline_scaffold_loads_and_names_what_is_left` asserts the scaffold's disasm has no `--text-only` or `--extra-sections`. pytest 543 passed; ruff check and format clean; `scripts/audit-public.sh a7cdc15..HEAD` clean.
- [x] 1.6 Shipped games unchanged: `cat/src/recomp/gen.key.json` and `b3/src/game/recomp/gen.key.json` `argv` hashes are the same with the changed CLI as with v0.6.7 (run each game's `analyze` with the CLI worktree and compare the key, or compute `pipeline.stage_argv()` for both manifests).
  - Done with `stage_argv()` before (v0.6.7) and after (59975db): cat d0409a17… and b3 0fccdb19…, both equal to their committed `gen.key.json` `argv`; testdata game 53e6f53c… and game2 a39b9a08… also unchanged.

## 2. Spartan (D2)

- [x] 2.1 `spartan/tca/game.toml` `[pipeline.disasm]`: replace the `text_only = true` line and its comment with the fixed scaffold's `text_only = false` and comment. The orchestrator applies this: `spartan/tca` is not a repo and not a worktree. It does not wait for the CLI release. (Applied by the orchestrator, 2026-10-14.)
- [x] 2.2 `./tca analyze`, `./tca recomp`, `./tca build macos`. Check against design.md's `text_only = false` column: 18,083 functions, 12 unresolved stubs, DOLBY 1. A different toolkit pin may move the counts; the stub list is what must hold.
  - Done by the orchestrator (toolkit ac27175): 18,083 functions, 12 unresolved stubs, DOLBY 1 (`sub_0035E798`, 15 bytes, imm_ref_target, no callers). The new gen/ is byte-identical (`diff -rq`) to `runs/spartan/20261014-214121-text-only-false/gen`, and its twelve stub addresses equal the six-section run's.
- [x] 2.3 Record the alias drop against the new gen/ (design.md, "The alias drop"): the removed `.text` alias starts are not named anywhere in gen/ and none is a stub. Headless 120 s run with `RECOMP_STUB_LOG=1`: no `[ICALL] Failed to resolve` for 0x11485, 0x70187, 0x7048B or 0x96C9E. Not a gate for 2.1.
  - None of 0x00011485, 0x00070187, 0x0007048B, 0x00096C9E appears in any file of the new gen/, and none is among the twelve stubs. 120 s headless run with `RECOMP_STUB_LOG=1` (`runs/xgasm/20261014-220922-spartan-mac-stublog`): no `[ICALL] Failed to resolve` at all.
- [x] 2.4 Headless Mac run, then the same exe on the Deck under Proton: no `[CRASH]` and no `[STUB]`. Record the stop point.
  Done 2026-10-14: Mac runs/spartan/20261014-214958-mac-metal-textonly-false; Deck (GE-Proton11-9, d3d11, exe sha256 3465c261…) runs/spartan/20261014-223239-deck-proton. Both: no crash, no stub, one flip (clear, 0 draws), then the hang in sub_00228FA0 (BLX-132; watchdog: return 0x002292C0, PUT = GET = 0x3B44).
  - Mac done: `runs/spartan/20261014-214958-mac-metal-textonly-false` (orchestrator) and `runs/xgasm/20261014-220922-spartan-mac-stublog` (`RECOMP_STUB_LOG=1`, `SDL_AUDIODRIVER=dummy`, 120 s alarm): no `[CRASH]`, no `[STUB]`, 1 flip (a clear, 0 draws), then the hang in `sub_00228FA0` until SIGALRM (exit 142). The Deck/Proton run is still open.
- [x] 2.5 File the follow-up tracker item for the D3D pushbuffer wait in `sub_00228FA0` (proposal, "Not in this change"; `runs/spartan/20261014-212043-extra-sections/run2-sample/sample.txt`). (Filed as BLX-132.)
- [ ] 2.6 When the CLI release carrying D1 exists, move `spartan/tca/game.toml`'s `[cli]` tag and commit to it.

## 3. Toolkit disasm warning (D3)

- [x] 3.1 `tools/disasm/functions.py` `_pass_call_targets`: count call targets that fall in unswept executable non-data sections with raw data, and print the per-section warning after the pass (design.md D3 wording). No change to which candidates are added.
- [x] 3.2 `tools/disasm/test_unswept_section_warning.py`, with the negative control. Run `pytest tools/recomp tools/disasm`.
  - Done: toolkit branch `feat/unswept-section-warning` 6a894fc (off ab8bd27), amended after the Opus review to fcd3b76 (N1: a comment that the predicate mirrors `loader.get_code_sections()`; pytest rerun, 677 passed). The test sweeps `.text` of a three-section image that calls into XGRPH and into an executable `.rdata`: one XGRPH warning, none for `.rdata`, and the XGRPH target is still a candidate. The negative control sweeps XGRPH too: no warning. Without the functions.py change the warning test fails. `pytest tools/recomp tools/disasm`: 677 passed, 143 subtests passed. On Spartan's XBE (scratch, `runs/xgasm/spartan-warning`), `--text-only` prints exactly design.md's six lines (D3D 72, D3DX 1, DSOUND 28, XGRPH 9 e.g. 0x00255D64, XMV 6, XPP 8) and 17,356 functions; without it, no warning and 18,083 functions. The `--text-only` run's functions.json, labels.json and xrefs.json are byte-identical (`cmp`) to the same run with the base toolkit ab8bd27 (`runs/xgasm/spartan-warning/disasm-text-only-true-base`): the spec scenario "identical to a run without the warning code" holds as written.
- [x] 3.3 Mac build and `tests/posix_ctest.sh` (0 FAIL).
  - Done: `cmake -G Ninja -DCMAKE_BUILD_TYPE=Release` and build OK with DEVELOPER_DIR=/Library/Developer/CommandLineTools; posix_ctest 58 pass, 1 skip, 15 n/a, 0 FAIL (`runs/xgasm/toolkit-gates/`).
- [x] 3.4 BLiNX 2 regenerate against the toolkit worktree: no gen/ diff and no warning line. Then the Metal golden per the merge gates.
  - Done in a scratch copy (`runs/xgasm/blinx2-regen`, `blinx2 analyze && blinx2 recomp` with XBOXRECOMP_DIR at the toolkit worktree and XBOXRECOMP_CLI_DIR at the CLI worktree): `diff -rq` against cat's `src/recomp/gen` is empty, `gen.key.json` differs only in its `toolkit` field (argv d0409a17… unchanged), and analyze.log has no warning line. The golden was not run: gen/ is byte-identical and the branch changes only `tools/disasm`, so no runtime or generated input moves (as the orchestrator directed).

## 4. Merge and release

- [x] 4.1 Opus review of the CLI and toolkit branches.
  - Verdict MERGE AFTER FIXES. Fixes applied: CLI F1 to F3 (901593a), toolkit N1 (fcd3b76), F4 as a known limit in design.md D3, spec S1 to S4 (this commit). S2 was settled by measurement, not by softening the scenario.
- [ ] 4.2 Squash-merge each. Cut the CLI release that carries D1 (the next tag after v0.6.7); the public push waits for the next milestone round, CLI before `blinx2-recomp`.
- [ ] 4.3 `cat/TASKS.md`: replace the Spartan "Next" line with the root cause (our scaffold default), the manifest fix and the new stop point; note the CLI release and that cat's own pin can move at its next bump (cat is unaffected).
- [ ] 4.4 Offer the disasm warning upstream (sp00nznet/xboxrecomp) through `cat/analysis/upstream/pr-stack-plan.md`: add it to the stack, tested on Burnout 3 on native Windows, Proton and macOS on the exact PR head.
- [ ] 4.5 Follow-up: add a `BLX-[0-9]+` pattern to the CLI's `scripts/audit-public.sh`, so a tracker id in a commit or file fails the audit before a public push (the review found one in a test docstring on this branch, F1).
