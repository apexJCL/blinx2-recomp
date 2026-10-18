Implemented with wizard-test-notes on the same branches (see its
tasks.md for the conventions).

## 1. Model

- [x] 1.1 `runner/checklist.go`: parts, states, plan replacement, inserts,
  skips, per-part lines, `Fraction`; table tests (plan, no plan, a stage
  added at run time, a jump, failure, cancel, prerequisites).

## 2. Building page

- [x] 2.1 Tabler glyphs per kind and state, recoloured; tests that each
  renders in both themes.
- [x] 2.2 Rows: icon, name, state, status, the running row's bar, the
  in-place log; the overall line; Details unchanged.
- [x] 2.3 Coalesced refreshes and the 1 s clock through `fyne.Do`; race
  test clean.
- [x] 2.4 The failed row opens with the excerpt; the Done page shows the
  read-only checklist; tests (TestBuildClock, TestDoneFailure,
  TestDoneCanceled updated; a narrow-window layout test).

## 3. Docs

- [x] 3.1 `docs/wizard.md` Build and Done.

## 4. Gates

- [x] 4.1 As in wizard-test-notes 4.

## 5. Review fixes (review, 2026-10-15)

- [x] 5.1 D2's sentence on lines before any part matches the code (they
  are in no row).
- [x] 5.2 An open placeholder log stays open on the stage that replaces
  it; test.
- [x] 5.3 A closed row's log is filled when it opens, not on every
  refresh; the failure excerpt is taken for a failed part only, also
  when it fails with no new line; tests.
- [x] 5.4 The placeholder reads "Build the game"; with stage lines but no
  plan line it becomes the first stage; tests.
