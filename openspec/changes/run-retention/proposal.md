# run-retention: keep frames and runs only while pending work needs them

## Why

The Mac disk reached 100% on 2026-10-29: `runs/` holds 90 GB and
`bench-logs/` 24 GB. Two rules keep far more than any open work needs:

- A passing bench or golden run keeps most of its frame dumps. The runners
  prune only the flip dumps the check never read; the `frame_*.bmp`
  captures, the verdict images and the window's best stay.
- `benchdb plan` (design D11 of bench-results-db) pins a run when any
  reference text cites it, whatever the citing note is about. A note of an
  item accepted weeks ago pins its runs for ever. On top of that, guard 5
  keeps everything for 2 days (runs root) or 7 days (store). The
  workaround is a hand-kept `[refs] exclude` list in `benchdb.toml`, about
  forty entries long.

The user (2026-10-29): "only keep reference frames when a run fails or is
referenced and needed for PENDING work. Also allow benchdb to clean older
runs OR runs that really are no longer needed (fixed issues, wrapped up
spikes, etc)".

## What changes

- **Frames.** A passing golden run (`bench golden`, `golden run`) whose
  check exited 0 drops every image dump in its `frames/` after the verdict.
  It keeps them when it fails, when the check errors, with `--keep-frames`
  or `BENCH_KEEP_FRAMES=1`, and in record mode (a reference capture). Logs,
  metrics, `pulls.txt` and the db row always stay.
- **Pins by pending work.** With `[pending]` configured, every citation is
  judged. `golden.json` (and the audio golden) always pin. Any other
  citation pins only when the work it belongs to is still open: an open
  Plane item (not Done or Cancelled), an unarchived OpenSpec change. A
  citation whose work is all Done, Cancelled or archived no longer pins.
  When benchdb cannot map a citation to any item, the citation keeps
  pinning (fail safe), and the plan counts these citations.
- **Age.** With `[clean] guard_hours` set, an unpinned run or file in the
  store and runs roots may go once it is a few hours old, instead of after
  2 or 7 days. A run that is still live is refused whatever its age: it
  has no exit-code, its topic has a worktree, or an open item works on it.
- **Frames already stored.** `benchdb plan --frames` plans only the frame
  dirs of passing, unpinned, settled runs in the db.
- **Safety stays.** `plan` deletes nothing. `clean PLAN_ID` re-plans with
  the same arguments and journals each deletion. The 1-day floor of
  `--older-than` and `--force-young` / `--force-dirty` are unchanged.

## Impact

- `xboxrecomp-cli`: `benchdb/{pending,clean,config,refs,retain,cli}.py`,
  `golden.py`, `golden_run.py`, `bench/golden.py`, `bench/__init__.py`, and
  tests.
- `benchdb.toml` (workspace, not in a repo): `[pending]` and `[clean]`
  sections, and most of `[refs] exclude` can go. The diff is proposed in
  the agent's notes and applied by the orchestrator.
- Without `[pending]` and `[clean]` the plan behaves exactly as before.
