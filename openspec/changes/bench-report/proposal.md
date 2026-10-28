# bench-report: a generated benchmark report, with a public summary

## Why

The report (`notes/bench-matrix/report/index.html`) answered the
user's questions, but it was built by hand from `summary.json`. The next
matrix (after the tracker item) and the next game would need the same work again,
and nothing in it can go to a public README. The user (2026-10-23) wants
reports that are generated, comparable across platforms and runs, and
partly publishable: a radar chart per platform against the target fps;
target, mean, lowest fps and p99 frame cost per platform; a best-settings
summary per platform; a hardware disclosure per platform; and an export of
the performance and settings summary, and only that, for the game's
public README. The tracker item.

## What changes

- **CLI (xboxrecomp-cli, `<game> bench-matrix report`)**: a new verb
  beside `plan`, `run`, `collect` and `analyse`. It reads a matrix result
  dir (`runs/bench-matrix/<scene>/`) and, optionally, a baseline dir
  (`--baseline`). It renders from `summary.json` and the per-run files and
  computes no frame statistics of its own.
  - The private report is one self-contained HTML file with every chart.
    It keeps the sections and adds the new ones.
  - The public export (`--public REPO`) writes per-platform radar SVGs and
    a Markdown fragment between README markers in the game repo. It writes
    through an allow-list and checks its own output for leaks.
  - Best settings are picked by a rule whose thresholds live in config,
    with defaults in the CLI that are the same for every game. The bar is
    strict: mean, hitches per minute and 1% low. A host's random slow
    mode is reported as a host caveat ("unstable") and does not decide
    the pick.
  - The figures and the pick come from one sampler group per host,
    no-sampler first.
- **Runner (`bench-matrix run`, `run-arm.ps1`)**: `hw`, `run` (sampler,
  pacing, present and window mode) and `build` blocks in each
  `run-info.json`, captured per OS from a fixed list of fields. Host names, user names, paths, serials and network addresses
  are never captured.
- **Analyser**: one new column, `steady_worst_s_fps`.
- **Game config**: `display` names on each `[[axis]]` and a `[report]`
  table in the scene TOML (the target fps,
  the scene label, axis display names and preferences, the hosts to
  publish and their public labels, threshold overrides). The JSRF title
  scene gets one.

## Out of scope

- The implementation, which is a later item that starts after the tracker item
  (`feat/bench-matrix-2`) merges.
- The tracker item's own scope: spin-share and per-CPU columns, compare mode,
  interleaved reruns, the runner's focus and quiet checks. The report
  shows whatever columns the tracker item adds and calls its `compare()`; it does
  not reimplement them. The bench rules the tracker item implements (a borderless
  fullscreen-desktop window, remote hosts first and the Mac last and
  quiet) are only recorded and stated here.
- Pushing anything. The export writes files into the game repo's working
  tree. The user approves them, and they go out in a normal public round
  (`<game> public export` and its audit).
- Frame dumps, screenshots and per-run traces in any public output.
