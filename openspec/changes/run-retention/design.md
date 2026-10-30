# Design

## R1. Frames after the verdict

`golden.prune_frames(d, keep)` removes only the flip dumps the
check did not read. It stays for `golden prune`. A new
`golden.drop_frames(d)` removes every `*.bmp` / `*.png` / `*.ppm` under
`<run>/frames/` and keeps the rest (`pulls.txt`, any text). The runners call
it where they called `prune_frames`:

| Runner | Drops when | Keeps when |
|---|---|---|
| `bench golden` (`bench/golden.py prune`) | verdict `pass`, check rc 0, run clean | any other verdict, `--keep-frames`, `BENCH_KEEP_FRAMES=1`, a trace run |
| `golden run` (`golden_run.py check_and_prune`) | verdict `pass`, check rc 0, the present check clean | any other verdict, `--keep-frames`, a present mismatch (its verdict does not weigh it) |

`pass-with-known` keeps its frames: a known difference is still a
difference someone may need to look at. The host's own `frames/` is
removed as before (`host.prune`, `prune_frames.sh`).

## R2. Pending pins

### Sources

`[pending]` in `benchdb.toml`:

```toml
[pending]
states = ["uv", "run", "-q", "--project", "...", "python", "notes/tracker_states.py"]
# or: states_file = "path/to/states.json"
prefixes = ["BLX"]
cache_minutes = 10
```

The command prints `{"fetched": ISO, "items": {"ITEM": {"state": "Done",
"group": "completed", "labels": ["agent:x"]}}}`. benchdb runs it once per plan, with
a timeout, from the config's dir, and caches the output in
`<store>/tracker-states.json` (one of the store's own files) for
`cache_minutes`, so a plan and its clean cost one fetch. `plan --states FILE`
reads a file instead. When the fetch fails, or the doc (file or cache) has
no items or was fetched over an hour ago, every item is unknown, so every
citation that maps to an item keeps pinning, guard_hours is dropped, and
the plan warns. A stale doc would release the runs of an item reopened
since.

An item is closed when its state group is `completed` or `cancelled` (Done,
Cancelled); every other state, Backlog included, is open.

OpenSpec: a change name is open when some game's main checkout has
`openspec/changes/<name>/`, closed when one has
`openspec/changes/archive/YYYY-MM-DD-<name>/` (matched exactly, so
`fps-pacing` is not `pacing`) and none has it open, and unknown when
none has it at all (a change only on a branch, which is open work).

### The judge

Each citation (a stamp, its HHMMSS token, a path or a build sha in a
reference file) is judged on its own:

1. A golden json or golden audio file of a game: always live.
2. A file under `openspec/changes/archive/`: released. A file under
   `openspec/changes/<name>/`: that change's state.
3. Otherwise the union of the work refs of:
   1. the enclosing block: the table row, or the top-level list item with
      its continuation lines, or the paragraph;
   2. the enclosing markdown headings (not for a table row: an index
      table's heading names the index, not each row's owner; a `#` line
      inside a code fence is no heading);
   3. the file's path: a `blxNNN` in it (BLiNX 1's slug prefix names
      the game, not the tracker item), or a notes folder whose name is an `agent:<name>` label of
      some item.

   Work refs are `BLX-n` and `openspec/changes/<name>` mentions. The union
   (review): a closed ref in a block must not hide an open one in its
   heading, e.g. "baseline: the tracker item's run" under an open the tracker item.
4. The citation is live when any of its refs is open or unknown, released
   when all are closed. With no refs, the refs anywhere in the file can
   only keep it: it stays live, as fail safe, whether those refs are open,
   closed or absent. An unknown ref also counts as fail safe.

A path pinned by several citations stays when any one is live. The refusal
names the live citation: `pinned: cat/TASKS.md:1810 cites 20261004-045825
(pending: the tracker item Backlog)`. The plan's `pins` field counts citations by
verdict and source file, and lists the paths that are no longer pinned
because their citations were all released.

Without `[pending]` (and without `--states`) the judge is off: every
citation pins, as in D11.

## R3. Age and live runs

`[clean] guard_hours = 6` (or `plan --guard-hours H`, at least 1) sets the
age of the store root that has no `days` of its own, in place of 7 days,
for a run whose verdicts are all `pass` or that has none. A run with any
other verdict (REGRESSION, INCOMPLETE, FAIL-RUN, ...) is a failure's
evidence and keeps the games' `[bench.gc] days`. The runs root gets
guard_hours but at least 24 hours, in place of 2 days: a topic's name is
written by hand and matches its worktree or item only loosely
(`runs/kuf-mac-build` for the tracker item beside `wt/kuf-macos`). `--older-than`
still wins. It is also D10's young rule for the store's retention, with
the same exception for failing runs. Host roots and worktrees keep their
days.

A runs-root topic is live, whatever its age, when:

- `wt/<topic>` exists (an agent's worktree);
- an item Ready, In Progress, Blocked or In Review carries `agent:<topic>`
  (Ready: dispatched, its agent may already write there);
- the topic holds `blxNNN` and BLX-NNN is in one of those states.

A run without an exit-code is refused as before.

## R4. `plan --frames`

Plans only the `frames` artifacts of runs in the db whose verdicts are all
`pass` (at least one) and whose exit code was parsed, not pinned, older
than the guard and not live. The exit code itself is not judged: a golden
run is stopped (124, -2 or -9 in the db, 739 passing runs) and a crash is
already FAIL-RUN. Store and runs roots only. The flag is saved in the plan's
args, so `clean` re-plans the same way.

## Decisions

- The judge is opt-in by config, so the existing D11 tests and any game
  without a tracker keep their behaviour.
- Backlog counts as open: a parked item may come back to its evidence.
- The seeds' `source` and analysis notes name runs without an item: they
  stay pinned (fail safe) and are counted, not guessed.
