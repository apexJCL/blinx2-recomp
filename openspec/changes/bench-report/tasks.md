# Tasks: bench-report

Implementation starts after the tracker item (`feat/bench-matrix-2`) merges, in a
CLI worktree off `main`.

## 1. Runner (D5)
- [ ] 1.1 `hw` capture for macOS and Linux/Deck from named fields; free
      text capped and character-limited
- [ ] 1.2 `run` block: sampler rate, pacing, present mode and vsync when
      logged, order; window mode, refresh and quiet read from the tracker item's
      `present_fullscreen`, `refresh_hz`, `quiet_wait_s`/`busy_during`/
      `focus_lost`; "windowed" flagged as a deviation
- [ ] 1.3 `build` from the payload manifest; `--build-version` (and
      `--game-sha`/`--toolkit-sha`) required without one; `version_public`
- [ ] 1.4 `run-arm.ps1`: the same blocks via Get-CimInstance, powercfg and
      nvidia-smi; a JSON-shape test on a recorded ps1 output (and a pwsh
      run when pwsh exists)
- [ ] 1.5 pytest with fixture outputs of each tool that hold a host name,
      serials, UUIDs, a MAC, an IP and paths: none reach `hw`

## 2. Analyser
- [ ] 2.1 `steady_worst_s_fps` (from `fps_per_s[warmup_s:]`) per run and
      per-arm medians (D2)

## 3. Report (D1-D4, D6, D7)
- [ ] 3.1 `display` on `[[axis]]`, the `[report]` table, generic defaults
      (`split = []`), schema errors (incl. `stock` required on every axis),
      `report.json`
- [ ] 3.2 sampler group per host (D2); a fixture with two prof groups
- [ ] 3.3 best settings (D4): the three checks, `min_pass` as a fraction
      (n=3 with 2 passes qualifies; 1 of 2 does not), the per-axis
      permutation test, good-runs-only judging, unstable flag with Wilson
      interval, the tied-mode case, not-judged arms, the closest arm by
      largest shortfall; the expected picks of D4 as a regression
      fixture
- [ ] 3.4 radar SVG: shared spoke order, gaps and wedge fills, min-max
      ticks, target ring, mean and 1% low series, baseline overlay,
      caption, `<title>`/`<desc>`, light and dark palettes, a contrast
      test (3:1 marks, 4.5:1 text)
- [ ] 3.5 private HTML with the D7 sections, the `report-notes.md` slot,
      `--baseline` via `compare()` in-process, `hw` variants within a host,
      the refresh-below-target note; a fixture test (all sections, figures
      match summary.json, no external URLs)
- [ ] 3.6 CLI README entry; tests and ruff

## 4. Public export (D8)
- [ ] 4.1 `--public REPO`: the SVGs, the README fragment between markers
      (best and stock rows, a stock row per split value, the no-data
      reasons, n, sampler group, single-run mark, baseline
      delta, D4 lines, hardware block), exit 1 when the markers are missing
- [ ] 4.2 allow-list model; leak check with `public.private_patterns()`
      and host keys only in identifier positions; the poisoned-fixture,
      `deck`-label and audit-private tests
- [ ] 4.3 check that the game's `public export` rules carry
      `docs/images/bench/**.svg` and the README fragment through unchanged

## 5. Game and runs
- [ ] 5.1 JSRF `config/bench/title.toml`: `display` per axis, `stock = 0`
      on the dsp axis, `[report]` with `split = ["aspect"]` and the Deck,
      Mac and PC public hosts; README markers
- [ ] 5.2 Render the private report from `runs/bench-matrix/jsrf-title/`
      (no `hw`: "not recorded") and check it against the page at
      1280px light and dark and at 400px
- [ ] 5.3 After the post-the tracker item rerun (which records `hw`): the JSRF
      private report with the runs as `--baseline`, then the public
      export for the user's approval. Nothing is pushed before that
