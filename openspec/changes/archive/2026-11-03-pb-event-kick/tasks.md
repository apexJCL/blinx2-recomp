## 1. Toolkit (feat/pb-event-kick off posix-host/portability 8a87ec1a)

- [x] 1.1 `XboxHostWaker` (host_time.c): condvar plus a pending flag, Windows (SRW/CV) and POSIX (monotonic)
- [x] 1.2 `nv2a_kick_wake.{c,h}`: armed handshake, poke, nudge, held sleep, PUT watch, miss limit
- [x] 1.3 ack loop: watch after an ack, sleep to the tick, held sleep, miss fallback; `kick_event` env row; startup line
- [x] 1.4 `RECOMP_SPIN_WAIT` reads `g_xbox_kick_armed`; `xbox_SpinWait` pokes first; the vblank nudges
- [x] 1.5 `[PACING]   kick wait:` line (both modes, walker thread cpu)
- [x] 1.6 `tests/kick_wake` ctest: no lost wake-up (20000 kicks, one poke per store), fallback timeout, idle poke, nudge, held sleep, no latched wake, PUT watch, miss limit

## 2. Games

- [x] 2.1 BLiNX regenerate: the gen diff is only the `recomp_types.h` macro
- [x] 2.2 JSRF (skates main) regenerate and build: KickOff not lowered, so the fallback is expected
- [x] 2.3 cat `docs/env.md`: `kick_event` row

## 3. Gates and measurements

- [x] 3.1 Mac build (macOS + Windows cross), toolkit 7ef3d4de
- [x] 3.2 `tests/posix_ctest.sh`: 100 pass, 0 FAIL, 15 n/a, 3 skip (`kick_wake` pass)
- [x] 3.3 BLiNX goldens: Metal attract/stage1/story pass; D3D11 under Proton on the Deck attract/stage1/story pass
- [x] 3.4 BLiNX stage1 A/B (event vs `kick_event=0`, 100 s runs, steady windows, `runs/bench-matrix/pb-kick/blinx-{mac,deck}`):

  | | Mac (Metal) event | Mac poll | Deck (D3D11, Proton) event | Deck poll |
  |---|---|---|---|---|
  | process cpu (3 runs) | 133% | 135.5% | 166.3% | 168.1% |
  | walker cpu (3 runs) | 29.3% | 31.3% | 44.3% | 46.0% |
  | kickwait, ms per flip (flip log) | 8.5 (3 runs) | 9.8 (3 runs) | 11.5 | 12.9 |
  | frame wall (30 fps lock) | 33.3 | 33.3 | 33.3 | 33.3 |

  The saving is 2 to 4 points of a core, not the 0.2 to 0.3 core that the tracker item
  estimated: the walker's cpu is mostly its own walk, and the poll's naps were
  cheaper than estimated. The kick is acknowledged sooner (kickwait 10 to 13%
  lower). The event wait stayed on in every BLiNX run: at most 3 kicks per 600
  flips were found by the tick, never 3 in a row.
  One Mac event run with the flip log had kickwait jump from 8.5 to 24.5 ms
  per flip for its last ~250 flips, right after a 47 ms host hitch at flip
  3096. The frame rate held at 30, and two more pairs did not repeat it. 4.3
  reproduces it with injected hitches in both arms: it is the flip hold after
  a host hitch, not the event wait.
- [x] 3.5 JSRF title (skates d54c008, s1-dsp0-43, bench-matrix, `runs/bench-matrix/pb-kick/jsrf-{mac,deck}`): the KickOff spin is not lowered, so the event wait turns off within the first ~10 flips ("3 kicks in a row ... polls from now on") on both hosts.
  - Both arms are the same. Mac: process 225-227%, walker 20-24%, 59.6 fps. Deck: process 154-163%, walker 38-45%, 59.4 fps.
  - Deck event-1 scored "bad" (53 fps) at a 389 MHz GPU warm-up clock; its path is the poll's from flip 4 on, and event-2 matches the poll arms.
  - JSRF only gains once the tracker item lowers the KickOff spin (sub_001912A0).

## 4. Review fixes (review-ITEM.md; toolkit f89bcfa3)

- [x] 4.1 Fixes. `kick_event` defaults off, `kick_event=1` opts in (design 7).
  - H1: a `PUT` watch miss polls at ~50 us for the rest of the tick.
  - M1: seq_cst fence in `RECOMP_SPIN_WAIT` and `xbox_SpinWait` before the armed read.
  - M2: the held sleep rechecks the vblank count after it arms.
  - M3: a timeout that finds `PUT` moved counts as a miss.
  - M4: native Windows waits on an event plus a high-resolution waitable timer, not the 15.6 ms condvar tick.
  - L1-L4: comments, the dead `flip_poll`, the test macro copies.
- [x] 4.2 Tests.
  - `kick_wake` adds a one-pass stress in the guest's order (store, fence, armed read, poke). Over 5+ runs of 200000 passes each, the unfenced pass loses 10-68 pokes and the fenced pass loses 0. A held stress (20000 vblanks) has 0 timeouts, and there are single cases for the vblank recheck.
  - `spin_wait` adds a case with armed set.
  - `tests/posix_ctest.sh`: 100 pass, 0 FAIL, 15 n/a, 3 skip.
  - `pytest tools/recomp tools/disasm`: 1027 passed.
- [x] 4.3 Hitch runs: BLiNX stage1 on Metal, 160 s each, SIGSTOP 30-60 ms every 5 s from 40 s (24 hitches), flip log, `runs/bench-matrix/pb-kick/blinx-mac-hitch`.

  | arm | runs | runs with a slip | longest slip (flip-hold holds) |
  |---|---|---|---|
  | round-1 event (7ef3d4de) | 2 | 1 | 149 |
  | event, `kick_event=1` (f89bcfa3) | 4 | 1 | 30 |
  | poll, the default (f89bcfa3) | 4 | 2 | 147 |

  - A slip is kickwait 8.6 to 24.5 ms per flip at the same 30 fps. It starts right after a hitch frame (70-85 ms wall) and ends at a later hitch.
  - The poll arm slips as well, so the hitch itself makes the walk late. The event wait is not the cause.
  - The poll after a watch miss stays because it removes the one late-walk source that only the event wait has. Recovery belongs to the tracker item.
  - Outside slips, kickwait is 8.6-8.8 ms per flip for event and 9.8-10.1 ms for poll.
- [x] 4.4 Gates on f89bcfa3.
  - Mac build (macOS and the Windows cross build).
  - BLiNX Metal goldens attract, stage1 and story pass, both with the default and with `kick_event=1` (`runs/bench-matrix/pb-kick/blinx-golden-metal-r2-{default,event}`).
  - D3D11 under Proton on the Deck, Mac-built exe: attract, stage1 and story pass.
  - Native Windows (the M4 waker) has not been run.
