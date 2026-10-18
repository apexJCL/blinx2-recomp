Conventions as in wizard-test-notes: **CLI** = `wt/font-link/xboxrecomp-cli`,
branch `feat/wizard-font-link`, public identity; **cat** =
`wt/font-link/cat`, branch `spec/wizard-font-link`.

## 1. CLI

- [x] 1.1 `credits.py`: `OURS`, `THIRD_PARTY`, `merged(game_entries)`
  with D3's order and the de-duplication; tests for the generic order
  (no game entries) and a game's order (blinx2-like).
- [x] 1.2 `manifest.py`: `[[wizard.credit]]` (`WIZARD_CREDIT`), its
  errors; tests.
- [x] 1.3 `wizard.py`: `credits` in the config; tests.
- [x] 1.4 docs: `docs/wizard.md` (Credits), `docs/manifest.md`
  (`[[wizard.credit]]`).

## 2. Wizard

- [x] 2.1 `gamecfg.Credit`, Validate, `FallbackCredits`, `CreditList()` (the
  field is `Credits`, so the method takes another name);
  tests (sample, refusal, fallback).
- [x] 2.2 `creditsList`; the info button and dialog; Welcome; tests:
  the button hidden on Welcome and shown elsewhere, the dialog's width
  in a wide and a narrow window and after a resize, links through
  `openLink`, both themes render.

## 3. cat

- [x] 3.1 game.toml: `[[wizard.credit]]` for apexJCL/blinx2-recomp and
  the PT Sans Narrow font of the HUD pack (its GitHub page,
  google/fonts `ofl/ptsansnarrow`, as the user asked for GitHub links
  where they exist).
- [x] 3.2 Regenerate `gamecfg/testdata/blinx2.json` from it.

## 4. Gates

- [x] 4.1 As in wizard-test-notes 4, plus `audit-public.sh` over the
  branch (public URLs only).

Results (CLI `feat/wizard-font-link` bdbacb3): CLI pytest 661 passed,
1 skipped; ruff clean; `./blinx2 wizard check --dev` passes check.sh,
race and staticcheck, and the double build gives equal sha256s for all
6 files; `audit-public.sh main..HEAD` clean, noreply address only; cat
pytest and ruff clean.

## 5. Review fixes (second review)

- [x] 5.1 `own = true` marks the game's own repo; only it goes before
  `OURS`, and the game's other entries lead the third-party section
  (D3). manifest.py, docs, the merged() tests and game.toml updated;
  the Go fallback is unaffected (it has no game entries).
- [x] 5.2 The Windows exe's static runtime checked (D11): the MinGW-w64
  runtime notices are a NOTICES.txt section, checked against the
  pinned llvm-mingw.
- [x] 5.3 REUSE-style `LICENSES/<id>.txt` folders count as licence files.
- [x] 5.4 manifest.py refuses two `[[wizard.credit]]` entries with one url.

Results (CLI c81f09a): CLI pytest 664 passed, 1 skipped; ruff clean;
`./blinx2 wizard check --dev` passes check.sh, race and staticcheck,
and the double build gives equal sha256s for all 6 files; NOTICES.txt
has 45 sections, the 44 before plus the MinGW-w64 runtime;
`audit-public.sh main..HEAD` clean, noreply address only; cat pytest
and ruff clean.
