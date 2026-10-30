# Tasks

## 1. Frames in the runners
- [x] 1.1 `golden.drop_frames(d)`: remove every image dump under `frames/`,
      keep text files (`pulls.txt`).
- [x] 1.2 `bench golden` and `golden run` call it for a passing run whose
      check exited 0, unless `--keep-frames` / `BENCH_KEEP_FRAMES=1`;
      `bench golden --record` never drops; `golden run`, whose verdict does
      not weigh the present check, keeps them on a present mismatch.
- [x] 1.3 Tests in `tests/test_golden_prune.py`.

## 2. Pending pins
- [x] 2.1 `benchdb/pending.py`: the tracker states (command or file, cached
      in the store), the OpenSpec state of each change, and the judge.
- [x] 2.2 `[pending]` in `config.py`; `--states FILE` on `plan`.
- [x] 2.3 `refs.golden`: the golden json realpaths.
- [x] 2.4 `clean.Pins` judges each citation when pending is on; the plan
      reports pins by source, released citations and fail-safe counts.
- [x] 2.5 Tests for each mapping level, golden, archived specs, an
      unknown item, an unreachable tracker.

## 3. Age
- [x] 3.1 `[clean] guard_hours` and `plan --guard-hours`: the store and
      runs roots' default age, also passed to D10's young rule.
- [x] 3.2 Live topics: a worktree of the same name, an open started item
      labelled `agent:<topic>`, or naming the topic's `blxNNN`.
- [x] 3.3 Tests.

## 4. Frames in the store
- [x] 4.1 `benchdb plan --frames`.
- [x] 4.2 Tests.

## 5. Validation
- [x] 5.1 Dry plans over the workspace with the agent's branch; numbers in
      the comment. No `clean`.
- [x] 5.2 Proposed `benchdb.toml` diff in the agent's notes.

## 5. Review fixes
- [x] 5.1 guard_hours only for pass or unjudged runs: a failing run keeps
      the games' gc days in the store guard and the retention.
- [x] 5.2 Archived changes matched as `YYYY-MM-DD-<name>` exactly.
- [x] 5.3 Block, heading and path refs taken together; fenced `#` lines are
      no headings; the whole file only keeps.
- [x] 5.4 Ready counts as live; the runs root's guard is at least 24 h.
- [x] 5.5 BLiNX 1's slug paths name no item; an empty or hour-old states doc (or
      cache) is refused.
- [x] 5.6 `golden run` keeps a pass's frames on a present mismatch.
- [x] 5.7 A test for each.
