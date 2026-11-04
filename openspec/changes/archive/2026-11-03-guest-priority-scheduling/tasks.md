Conventions: **toolkit** = branch `feat/guest-sched` rebased on
`posix-host/portability` da8f65d8 (the squash of `fix/jsrf-dj-crash`
b7e82411); **cat** = branch `spec/guest-sched` off cat `main`. Decisions
D1-D7 are in design.md.

## 1. Scheduler (toolkit)

- [x] 1.1 `GUEST_SCHED` debug row and the config gate (D1).
- [x] 1.2 Per-thread records, normalised base priority, query and set (D2).
- [x] 1.3 Priority-ordered waiter list and `sched_take` (D3).
- [x] 1.4 Preempt request and the holder's refusal at back edges, spin
      passes and yields; `refused` in the stats and report (D4).
- [x] 1.5 Soft release rule (D5).
- [x] 1.6 Guest-side suspend and resume, CreateSuspended in sched mode (D6).
- [x] 1.7 Starvation diagnostic (D7).
- [x] 1.8 Review fixes: waits poll before they block, self-suspend blocks,
      the +1 wake boost only for a thread back from a block, a gone record
      kept until its thread parts, the hang guard (valve), admissions past
      2 ms counted, the longest-wait line, a log line for a resume of an
      unknown handle (toolkit cf14a796).
- [x] 1.9 Re-review fixes: the valve's turn is reserved (the fast path
      defers to it, its waiter keeps the preempt request up); a zero
      `KeDelayExecutionThread` is a short call and a real delay blocks;
      the starvation and valve lines name the last holder when the CPU is
      free (toolkit cca61913).

## 2. Tests and docs

- [x] 2.1 ctest `tests/guest_sched` for the hand-off ordering.
- [x] 2.2 cat `docs/env.md` row for `guest_sched`.
- [x] 2.3 ctest `tests/guest_sched_bridge`: CreateSuspended and resume
      through the bridges; `tests/guest_sched` gains waits, equal levels,
      the wake boost, gone records and the valve.
- [x] 2.4 Re-review tests: the valve case drives `xbox_GuestCpuPreempt`
      and checks the turn at the first hand-off; the zero delay, a
      self-suspend that blocks, `NtSuspendThread` on another thread
      (bridge); `barge_asks` polls instead of a fixed sleep.

## 3. Mac verification

- [x] 3.1 POSIX ctests, 0 FAIL (94 pass, toolkit 7fd07f0d).
- [x] 3.2 BLiNX 2 Metal goldens, lock on, key off and on: attract, stage1
      and story pass both ways, flips/s within 1% (45.7/34.5/54.0 off,
      46.2/34.4/54.1 on).
- [x] 3.3 JSRF on Metal to attract, lock and key on: the demo plays, 11938
      flips in 200 s.
- [x] 3.4 POSIX ctests after the review fixes, 0 FAIL (95 pass, toolkit
      cf14a796); `guest_sched` 30 runs in a row, 0 failures.
- [x] 3.5 The valve fires on the Mac, key on (toolkit cf14a796): 2, 2 and
      10 times in attract, stage1 and story, with 4, 4 and 19 waits over
      1 s; all pass, flips/s 46.0/34.1/53.2 on against 46.0/34.4/54.0 off,
      0 firings off (`runs/guest-sched/blinx2-r-on`, `blinx2-r-off`).
- [x] 3.6 Deck under Proton, 8 arms (attract and story, spin and sleep
      pacing, key off and on, sound and WAV capture; toolkit cf14a796):
      0 valve firings, longest wait 450 ms under spin and about 100 ms
      under sleep; the D3D11 golden with the key on passes at
      31.6/30.5/46.9 flips/s (`runs/guest-sched/deck`).
- [x] 3.7 After the re-review fixes (toolkit cca61913): POSIX ctests 0
      FAIL (95 pass), `guest_sched` 30 runs in a row, 0 failures. Metal
      golden, key on: attract and stage1 pass, valve 2 and 1, waits over
      1 s 5 and 5, 45.5/34.4 flips/s; story NEWVIEW at a host load of 43.9
      (the hub's camera, overlay exact), then pass on a rerun at load 7.2,
      valve 13, waits over 1 s 20, 54.2 flips/s
      (`runs/guest-sched/blinx2-r2-on`). The longest wait now stops at
      the valve's 4 s.

## 4. Before a default change (later)

The key stays default OFF until every gate passes with it on:

- [ ] 4.1 (a) Decide D7: pacing parity at the lowered site (D7 b), then
      the measurement of main's blocked time and the D3D Swap waits (D7 c);
      model the cause if the console blocks there.
- [ ] 4.2 (b) Listen with sound, BLiNX 2 attract and story under `spin`
      and `sleep` pacing, key off and on (Deck, Proton, WAV capture): no ADX
      dropouts, no starvation line, the longest wait recorded per arm, 0
      valve firings.
- [ ] 4.3 (c) JSRF's DJ scene, key on: on the Mac, Proton and native
      Windows; the repro with `guest_sched=1` and `guest_priority=2`
      shows the scheduler alone fixes it.
- [ ] 4.4 (d) Every title that sets `RECOMP_GUEST_LOCK` (SSX 3, Burnout 3
      if it does) with the key on, and the `guest_cpu`/`guest_sched` ctests
      on native Windows (MSVC). Native Windows changes more than POSIX
      (Risks), so it is required.
- [ ] 4.5 (e) flips/s and frame ms against the key off on D3D11 (Deck
      golden) and Metal, within the 25% and 1.5x thresholds.
- [ ] 4.6 (f) Where the default lives: a per-game
      `RECOMP_ENV_GAME_DEFAULTS` row (as `guest_cpus` does) or promotion to
      a documented config key; decide and record it here.
