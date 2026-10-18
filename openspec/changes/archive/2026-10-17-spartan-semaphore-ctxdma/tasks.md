Worktrees:
- cat `wt/ITEM/cat`, branch `spec/spartan-semaphore-ctxdma` (this spec);
- toolkit `wt/ITEM/xboxrecomp`, branch `fix/semaphore-ctxdma-base` off `posix-host/portability` 3d37629, prototype 7e705d4;
- Spartan scratch clone `wt/ITEM/tca`. It has a fresh build dir `build-ITEM` pointed at the toolkit worktree, and its `src/main.c` carries the D2 mirror line as a probe.

Raw runs are in `xbox-recomp/runs/ITEM/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`, perl `alarm`). Proton runs are on the Deck with a Mac-built exe copied over (memory note *deck-proton-bench*; never build on the Deck).

## 0. Spec review

- [x] 0.1 This spec was not written by the reviewer, so the reviewer reads it and improves it, then commits the revision on the spec branch.
- [x] 0.2 Implementation starts only from the revised commit, including the call on design D3 (decided: no fallback in this change).
  Done: implemented from 31540fb.

## 1. Toolkit: context DMA base for the semaphore and report objects (D1)

- [x] 1.1 Prototype 7e705d4: `sema_ctxdma_base()` in `nv2a_pb_exec.c`, looked up at the first release after `SET_CONTEXT_DMA_SEMAPHORE`; `xbox_Nv2aAperture()` in `xbox_memory_layout.c`/`.h`; ctest `tests/pb_semaphore` (base, adjust, offset, missing handle), added to `src/d3d/CMakeLists.txt` beside `pb_tex_cache` (not WIN32); Mac build and `tests/posix_ctest.sh runs/ITEM/toolkit-ctest`: 59 pass, 1 skip, 15 n/a, 0 FAIL.
- [x] 1.2 Bring the branch to the revised D1:
  - the helper is generic (`ctxdma_lookup(handle, &base, &limit)` or similar) and returns found/not found, base and limit;
  - the lookup runs when the bind method runs: `SET_CONTEXT_DMA_SEMAPHORE` and `SET_CONTEXT_DMA_REPORT` store handle, base, limit and a found flag in a per-purpose `struct ctxdma_bind` static (`s_sema_bind`, `s_report_bind`); `sema_base_valid` and the release-time lookup go;
  - the release writes at `dma_resolve(s_sema_bind.base + sema_offset)` (through `ctxdma_place`); `get_report()` at `dma_resolve(s_report_bind.base + (param & 0x00FFFFFF))`;
  - a release or report whose end is past `limit + 1` of a found object is refused with one log line; an object not found has no limit (base 0, today's behaviour);
  - logging as design D1 (per bind when the result changes, capped; `report` lines as well as `semaphore`);
  - the helper's comment says RAMHT is 4 to 32 KB (the prototype says 64 KB), and the header comment on `xbox_Nv2aAperture()` names RAMHT and the DMA objects as the readers.
  Done: toolkit 3c2386a (`ctxdma_lookup`/`ctxdma_bind`/`ctxdma_place`, `s_sema_bind`/`s_report_bind` as the single source; the unread `sema_base`/`sema_limit`/`sema_bound` copies in `nv2a_pb_state.h` were dropped after the review, F3).
- [x] 1.3 Extend `tests/pb_semaphore`: a re-bind to a handle whose object was rewritten picks up the new base (bind, rewrite PRAMIN, re-bind, release); a release at an offset past the limit is refused and the word is untouched; a `GET_REPORT` after `SET_CONTEXT_DMA_REPORT` of an object with a non-zero base lands at base plus offset on the CPU backend; the existing four checks stay. Negative control: with the writes back on the bare offset, the base, adjust and report checks fail.
  Done: 10 checks pass (`runs/ITEM/toolkit-ctest2/pb_semaphore.ctest.log`); negative control (`*phys = offset`): base, adjust, offset, rebind, limit and report fail (`runs/ITEM/pb_semaphore-negative-control.txt`).
- [x] 1.4 Gates on the branch: Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`); `tests/posix_ctest.sh <build-dir>` 0 FAIL. `tools/recomp` and `tools/disasm` are untouched, so no pytest run is needed; say so in the gate record if that holds at the end.
  Done: Mac build ok; `tests/posix_ctest.sh runs/ITEM/toolkit-ctest2`: 59 pass, 1 skip (mmx_integer), 0 FAIL. `tools/recomp` and `tools/disasm` untouched, no pytest needed. The Proton ctests were not run (the bench builds them on the host, and nothing is built on the Deck); pb_semaphore is host-independent logic.
- [x] 1.5 Review of the branch; fixes go back to the branch's agent.
  Done: verdict MERGE AFTER FIXES on 3c2386a; fixes in toolkit 14d0a56. F1: pb_semaphore case on handle 9 (limit 0x1F, the XDK shape) where offset 0x1C lands and 0x1D is refused, plus a report at limit - 15 (lands) and limit - 14 (refused). F2: a release with no re-bind after a PRAMIN rewrite keeps the cached base 0x2000, then the re-bind moves it to 0x4000. F3: the unread `sema_base`/`sema_limit`/`sema_bound` fields are gone, and D1 and 1.2 now name the `ctxdma_bind` statics. F4: the refused-write latch is per `ctxdma_bind` (`refused_said`). F5: the `fence_mirrors_tick` comment now names the two mismatch causes. Nits taken: N1 (a bad instance pointer skips the RAMHT entry, `continue`), N2 (design says xemu reads the object words at use, `nv_dma_map`, and why we cache at bind), N4 (`src/main.c`). N3 is left for the squash message. Gates: Mac build and `tests/posix_ctest.sh runs/ITEM/toolkit-ctest3` 59 pass, 1 skip, 0 FAIL; pb_semaphore 17 checks pass. Negative controls in `runs/ITEM/pb_semaphore-negative-control-r2.txt`: bare offset fails 12 checks; exclusive limit fails 3 (0x1C on limit 0x1F, report at 0xFF0); a limit one byte loose fails the 0x1D checks and dies with SIGBUS at the 0xFF1 report; lookup at use fails `cached`. No new goldens or Proton runs (the fixes touch only the test, dead fields, a log latch and comments).
- [x] 1.6 BLiNX 2 with the branch: `blinx2 golden` on Metal, and the D3D11 golden under Proton on the Deck (`blinx2 build windows` on the Mac, copy, `blinx2 bench golden`). Expected in both logs: `semaphore context DMA 0x00000008: base 0x00001000` (or `0x00000000` if the fence page is physical 0 in that build), the first release at 0x80001000 (or 0x80000000), and `NV2A fence mirror: ... now written by the executor; mirror off`. Verdicts match main. Record flips/s and frame ms against main on both backends; the CLAUDE.md thresholds (25% fewer flips/s, 1.5x frame ms) are flags, and any `fence caught up` or `catch-up missed` lines go in the record. A drop is reported to the user as a finding, not absorbed.
  Done (toolkit 3c2386a; cat built from main 156e424's gen with `--stale-gen-ok`, the change being runtime-only). Both backends log `semaphore context DMA 0x00000008: base 0x00001000 limit 0x00000020`, the first release `0x00000005 -> 0x80001000`, `fence word 0x80001000 now written by the executor; mirror off`, and `report context DMA 0x0000000C: base 0x00000000 limit 0x10000000`; no `fence caught up`, `catch-up missed` or `REFUSING` line. Main's build logs `mirror stays on (semaphore releases land at 0x80000000)`.
  - Metal, A/B against main's toolkit 3d37629 (same gen, same session): attract, stage1, story pass on both. Under host load 41-65: flips/s 43.0/46.7, 33.3/33.4, 54.3/54.1 (fix/main), mean frame ms 23.3/21.4, 30.0/30.0, 18.4/18.5. The attract gap and its one 492 ms gap did not repeat on a quiet host (load 2-3, runs alternated fix, main, fix, main): 45.8 and 46.3 against 46.1 and 46.5 flips/s, mean 21.8 and 21.6 against 21.7 and 21.5 ms. Runs `runs/ITEM/metal-{fix,base}{,-quiet}/`, `runs/ITEM/flip-ms-blinx.txt`.
  - D3D11 on the Deck (Mac-built exe sha256 9c7e6a9c..., `runs/ITEM/provenance-win-fix.txt`): `bench golden` attract, stage1, story pass (bench-logs 20261014-232021/-232140/-232331). Against the last main-equivalent session (toolkit 90279d7, bench-logs 20261014-211848/-212007/-212159): flips 2373/2372, 3210/3210, 4691/4685; mean frame ms 28.7/28.8, 30.7/30.7, 19.5/19.5. No flag.
- [x] 1.7 Burnout 3 with the branch: boot on the Mac (Metal) and the Proton race gate on the Deck. Expected: `base 0x003E6000` (or wherever its fence page is), the first release there, "mirror off", no change in its boot, and the race gate's flips/s against the last main figure (57.0 flips/s on 2026-10-14) under the same thresholds. If Burnout 3 binds a report object, its `report context DMA` line is recorded too.
  Done (b3 d6eab90 = main, Mac-built, `--stale-gen-ok`). Both backends log `semaphore context DMA 0x00000008: base 0x003E6000 limit 0x00000020`, the first release `0x00000005 -> 0x803E6000`, `fence word 0x803E6000 now written by the executor; mirror off`, and `report context DMA 0x0000000C: base 0x00000000 limit 0x10000000`; no `REFUSING` line. Boot unchanged (the race gate's route runs as on main).
  - Metal race gate, fast mode, A/B against main's toolkit 3d37629: both PASS; race 53.7 flips/s (max gap 77 ms) against 52.6 (264 ms). `runs/ITEM/b3-mac/20261014-234000-fix`, `-234205-base`.
  - Deck Proton race gate (D3D11, Mac-built exes, `runs/ITEM/provenance-b3-win-{fix,base}.txt`): both PASS, 0 present mismatches; race 57.5 flips/s (gap 69 ms) against 56.6 (67 ms) for main's toolkit built the same way, and 57.0 on 2026-10-14. Mean frame ms 17.06 against 17.19. Runs `runs/ITEM/b3-deck/20261014-233956` (fix) and `-234827` (main); `runs/ITEM/flip-ms-b3.txt`. No flag.
- [x] 1.8 Backend parity: no backend code changes; confirm the Metal and D3D11 `on_report` paths receive the corrected address by reading the branch, and note it in the review request.
  Done: `get_report()` hands the base-plus-offset va to `metal_on_report(va)` (`nv2a_pb_metal.m:2720`) and `d3d11_on_report(va)` (`nv2a_pb_d3d11.c:3888`); no backend change.

## 2. Spartan (D2, orchestrator: `spartan/tca` is not a repo)

- [x] 2.1 `spartan/tca/src/main.c`: `xbox_Nv2aMirrorFence(0x235528, 0x2C, 0x30)` after `xbox_MemoryLayoutInit`; `RECOMP_TITLE_KEVENTS` and `RECOMP_VBLANK` default to `"1"` when unset. Use the comments from design D2.
  Done 2026-10-15 (backup notes/ITEM/spartan-main.c.before; diff runs/spartan/20261015-001139-ITEM-mac/main.c.diff).
- [x] 2.2 Rebuild Spartan against the merged toolkit, in a **fresh** build dir (the CLI ignores a changed `XBOXRECOMP_DIR` once a build dir is configured). Run it headless on the Mac. Expect the `base 0x00002000 limit 0x00000020` line, releases at 0x80002000, "mirror off", no `[CRASH]`, and boot past device creation to the `KeDelayExecutionThread` poll under `sub_001ADCA0` (as `runs/ITEM/r10-proto-mirror`).
  Done: build-ITEM against toolkit b958798; base 0x2000, release 0x80002000, mirror off, no crash, 4 flips, stop under sub_001ADCA0 (runs/spartan/20261015-001139-ITEM-mac).
- [x] 2.3 The same build on the Deck under Proton (d3d11): Windows exe built on the Mac, copied over; the same stop point.
  Done: same lines and stop under Proton d3d11 (runs/spartan/20261015-001343-ITEM-deck).
- [x] 2.4 File the next stop as a tracker item: the `KeDelayExecutionThread` poll under `sub_001ADCA0` ← `sub_000DC6E0` ← `sub_00182880`, after the render targets are created (`runs/ITEM/r10-proto-mirror/sample.txt`).
  Filed the tracker item.
- [x] 2.5 File the scaffold follow-up as a tracker item (CLI, next push round): `templates/new-game/src/main.c` defaults `RECOMP_TITLE_KEVENTS` and `RECOMP_VBLANK` to on as `cat/src/main.c` does, carries the mirror line as a commented example with the three offsets, and `porting.md` points at both; plus design D3's 0x400B10 fallback in the shape D3 fixes, with its own ctest and three-title runs.
  Filed the tracker item.

## 3. After the merge

- [x] 3.1 Notes to `notes/ITEM/`; the evidence runs (r3, r4, r5, r6, r10) stay in `runs/ITEM/`.
  Done.
- [ ] 3.2 Comments (cat's done on this branch: `src/main.c` now says the semaphore DMA object's base is physical 0x1000 and the release lands at 0x80001000) that now state the old rule: `cat/src/main.c` near the mirror line (the release "lands at 0x80000000"), `b3/src/game/main.c` near its mirror line ("the runtime advances the fence as an honest acknowledgement of everything submitted"), and the `get_report()` comment in the toolkit. cat's goes on this spec's branch; b3's is the orchestrator's; the toolkit's is part of 1.2.
  cat and toolkit done; b3's comment waits for b3's next toolkit pin bump (recorded in TASKS.md).
- [x] 3.3 Remove `wt/ITEM` (the scratch `tca` clone is about 3 GB) through `notes/cleanup-derived.py`. Keep the branches.
  Done (wt/ITEM and wt/postmerge removed via cleanup-derived.py).
- [x] 3.4 Post-merge Deck golden with the Mac-built exe (`bench golden`), and update `cat/TASKS.md`: the merge, the gate figures from 1.6 and 1.7, the two tracker items from 2.4 and 2.5.
  Done: Deck D3D11 attract/stage1/story pass (bench-logs 20261015-002717/-002836/-003028), Metal pass; flips/s and frame ms level (runs/ITEM/postmerge).
