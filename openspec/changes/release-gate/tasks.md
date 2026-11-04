- Worktrees `wt/release-gate/{xboxrecomp-cli,xboxrecomp,cat,blinx}` on
  `feat/release-gate` (CLI off main d777966, toolkit off
  `posix-host/portability` 01511963, cat off main 94836ca6, blinx off main
  d54c71e); scratch `xbox-recomp/runs/release-gate/`.

## 1. CLI

- [x] 1.1 `xbe.py`: `cert_release`, `region_text`, `release_text`.
- [x] 1.2 `manifest.py`: `[xbe] region`, `version`, `title`,
  `alt_title_ids` with range checks (D1).
- [x] 1.3 `fingerprint.py`: release fields on `Verdict`, precedence (D2),
  note, doctor text, plan record, stamp (D4), `--toml` keys, `title_match`.
- [x] 1.4 `dump.py`, `package`: import with a warning on a title match (D3).
- [x] 1.5 Docs (`manifest.md`, `commands.md`), README, CHANGELOG.
- [x] 1.6 Tests: cert parsing, region words, each precedence case, title
  match, key validation, doctor and fingerprint output, import warning.

## 2. Wizard

- [x] 2.1 `runner`: plan xbe fields, `XbeRisk` (D5); fixture.
- [x] 2.2 `screens`: Summary line, dialog for unknown, truncated and other
  release; strings in `copy.go`.
- [x] 2.3 Go tests; `wizard/check.sh`.

## 3. Toolkit

- [x] 3.1 `recomp`: fail on a wrap with no body (D6); warn on unknown code
  references (D7).
- [x] 3.2 `test_manual_wraps.py`.

## 4. Games

- [x] 4.1 blinx: sha256 and `[xbe.sections]` (mergeable now).
- [x] 4.2 blinx, cat: release keys, held for the `[cli]` pin move (D8).
- [x] 4.3 KUF: reported, not edited (no sha256, no sections).

## 4b. Review (2026-11-04)

- [x] Another title ID is another release (D2), unknown with the check off.
- [x] Truncated claims no release in any output (D2).
- [x] Alternate-ID rules need one publisher; `--toml` comments the IDs and
  the sha256 (D1, D3).
- [x] recomp's error leads with the player's sentence; the CLI adds the
  note and the command (D6); uses of unknown functions are fatal (D7).
- [x] package: a cut head is a CliError; `ModdedCode()` dropped; one
  release string; docs on sections and v0.20.0.
- [x] Follow-ups filed: the tracker item (B3 sections), the tracker item (KUF sha256 and
  sections), the tracker item (per-title-ID save root).

## 5. Gates

- [x] 5.1 CLI ruff clean; pytest 2374 passed, 2 skipped, 2 failed, both
  fixed and passing (a later rerun failed 52 tests on the Mac's full disk:
  every one the CLI's own disk-space refusal in its tmp build);
  `wizard/check.sh` ok (staticcheck not installed).
- [x] 5.2 Toolkit: `tests/posix_ctest.sh` on the Mac
  (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`): 152 pass, 4 skip,
  18 n/a, 0 FAIL; `pytest tools/recomp tools/disasm` 1088 passed, 1 skipped.
- [x] 5.3 cat 364 passed, 1 skipped; blinx 32 passed; ruff clean on both.
- [ ] 5.4 Byte-identical gen/: BLiNX 2 done (`diff -r` of the base
  toolkit 01511963 + CLI d777966 regen against the branch's: identical;
  no new ERROR or WARN). BLiNX 1 not run: its analyze refused, disk full.
- [x] 5.5 BLiNX 2 Metal goldens: push round 20 (cat 961599c7, toolkit
  blinx2-v0.14.0 7a97fcd0, CLI v0.21.0 c0ae467): attract, stage1, story
  pass (44.7, 34.5, 54.1 flips/s).
- [x] 5.6 `TOOLKIT=<wt toolkit> sh notes/build-all.sh`: push round 20,
  GAMES=all on the round's toolkit and CLI, Windows natively on the PC
  (the round's scope, 2026-11-04): all seven games pass.
- [x] 5.7 Negative tests (`runs/release-gate/neg/`): a BLiNX 1 XBE copy
  patched to PAL, version 2 with one `.text` byte flipped reads `code`,
  "another release: PAL, version 2, where this port was made from NTSC-U,
  version 6"; cat's scan file plus a wrap at 0x000133E1 stops recomp with
  the D6 error, rc 1, no gen written.
