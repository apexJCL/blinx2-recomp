## Context

A visibility test is three methods. `CLEAR_REPORT_VALUE` and `SET_ZPASS_PIXEL_COUNT_ENABLE(1)` open it, `ENABLE(0)` and `GET_REPORT(1 << 24 | offset)` close it; the GPU then writes 16 bytes at that offset in the report DMA object, `{timestamp (8), count (4), status (4)}`. The XDK's `EndVisibilityTest` writes 0xFFFFFFFF to the status before it pushes `GET_REPORT`, and `GetVisibilityTestResult` returns `D3DERR_TESTINCOMPLETE` while it reads that. The walker (`get_report()`, `nv2a_pb_exec.c`) resolves the address and hands it to the backend's `on_report`; the CPU path writes its own fragment count at once, the null backend and `zpass_fixed` write a constant, and the GPU backends return 1 and complete it later through the shared tracker `struct nv2a_occ` (`nv2a_backend_common.c`, 65b25c5): each counting stretch is one host query (`D3D11_QUERY_OCCLUSION`; on Metal a list of visibility-result slots, one per render pass the stretch spans), a report sums the stretches since the clear, goes on `pend[]` with its push time, and `nv2a_report_set_pending()` writes the 0xFFFFFFFF again. `nv2a_occ_poll(o, flush)` completes what is ready (count then status 0 through `nv2a_report_write()`, a release store), answers an overflowing report or one older than `NV2A_OCC_LATE_US` (250 ms) as `NV2A_OCC_VISIBLE` (0x10000), and a `GET_REPORT` at an address with a report still pending supersedes it unread. `d3d11_occ` / `metal_occ` `=sync` wait at `GET_REPORT` instead; `=fixed` leaves reports to the walker.

Who polls, and when. D3D11: `nv2a_occ_poll(o, 0)` at every batch and at the top of `d3d11_flip()` before `present_target` and `Present` (`GetData` with `DONOTFLUSH`); `d3d11_on_poll()` on the ack thread's idle tick with a flush. Metal: `metal_on_report()` commits the open command buffer when the report counted in it, so the count can land within the frame (render-gpu-backend M3: the attract cliff's light shafts take their brightness from the count and were 17% bad when it landed a frame late); `metal_flip()` ends with `flush(1)`, which waits for the frame's command buffer, then `occ_after_wait()` frees retired slots and polls without a flush; `metal_on_poll()` flushes on the idle tick. The render-scale change path in both backends polls with a flush and then sets the new scale.

Threads. "Everything here runs on the NV2A ack thread" (`nv2a_pb_state.h`; both backend headers say the same): the walker, every hook, `on_poll`, the flip and the present inside it (D3D11 presents and pumps its window on that thread; Metal's layer-mode copy is a command buffer the presenter in `fb_present_metal.m` reads on the GPU, and the presenter never touches the tracker). The only other party is the title, reading the report words from its own threads; that edge is the release store in `nv2a_report_write()`.

Readers. BLiNX 2: the player code (`sub_00022DB0`) reads a test issued the frame before and skips the draw on a low count or an incomplete status (this bug); the flare and glow code (`sub_00040AB8`) scales sprites by `count / area`. Burnout 3 issues 15-20 tests a flip in a race and none in the menus. The d3d11 smoke test (`tests/d3d11_backend_smoke`) issues four tests a frame and spins on them with `on_poll` as a title would.

## D1. What a pending report reads as: the last completed count for its address, settled at the flip

Four answers were on the table for a report the title polls before its result is in. What each costs and breaks:

| Answer | Hardware and emulators | Cost on D3D11 and Metal | Failure modes |
|---|---|---|---|
| **Block until ready (bounded)** | The NV2A never blocks the CPU; the report appears when the pipeline reaches `GET_REPORT`. xemu's GL renderer does block: it reads every zpass query with `glGetQueryObjectuiv(GL_QUERY_RESULT)` inside the method and writes the report before the next method runs, so its titles never see TESTINCOMPLETE after the method; its Vulkan renderer queues the report and writes it when the queries' command buffer completes (to confirm against the source at implementation time; `~/Documents/xemu` holds only firmware and a disk image). | This is `=sync`: 120-150 us a report on a trivial scene (377f04a), a pipeline drain per report on a loaded GPU, 20 of them a flip in a B3 race. The stall lands exactly on the host where the GPU already lags, the one being fixed. | Frame rate collapses where the GPU is behind; titles that spin are served, at the price of every other title. |
| **Visible (a nonzero count)** | The 250 ms and overflow fallbacks already say this; the hardware never does. | None. | Popping: the object draws through whatever hid it. Flares and glows at full strength (`metal_occ=fixed` was the extra cyan on the stage1 water, pb-index-batch-cap; the late Metal count was the 17% bad attract cliff). Wrong culling in the direction that changes game logic (the player test). |
| **Incomplete (today)** | The hardware state before the GPU reaches the method; on the console it lasts as long as the GPU lags, which the swap throttle bounds at about a frame. | None. | This bug: a title that treats incomplete as hidden drops the draw. A title with a brightness fallback pops. Titles that spin until complete are fine (`on_poll` exists for them) and stay fine under every option here. |
| **Last completed count for the address** | What a title that reads last frame's test gets on the console whenever the GPU is a frame behind: the previous frame's answer. | None by default (D2); the retired list is bookkeeping. | At most one frame stale while the GPU lags: an object crossing a visibility edge appears or lingers one frame late, a flare's brightness lags one frame, a camera cut shows one frame of the pre-cut answer. All below what 60 Hz shows, and all what the console shows a title that reads last frame's test. The first test at an address has no history and reads visible, once. |

The last count wins: it is the only answer that is both free and the console's own in the lagging case. "Visible" is kept only as the first-time value, where it is already the tracker's fallback and the frame is one.

Why the answer is settled at the flip and not given at `GET_REPORT`: the result usually arrives in time (every Mac flip and all but three Deck flips a run have nothing pending), and an exact count beats a stale one whenever it is there. The settle is the deadline the title can observe, not the answer. Until it, a report pending reads incomplete as today, which is also what the in-frame readers see on the console.

## D2. Where the decision runs: the flip, after submission, in shared code

**The flip.** `FLIP_STALL` in the executor is the title's swap, the point after which it may read the frame's results; the executor calls the backend's `on_flip` there, for every backend. D3D11: the settle goes after `IDXGISwapChain_Present` (the flush that submits the frame's queries; before it, a `GetData` with a flush would be the first submission) and before `flip_log()`, so the line shows it. Metal: `occ_after_wait()`, after `flush(1)` has waited for the frame's command buffer; every slot's command buffer is then complete and the poll is exact, so at stock nothing is pending there and the settle is a no-op. In both the call is `nv2a_occ_flip(&s_occ)`; the policy lives once, in `nv2a_backend_common.c`, and the backends differ only in `result(flush)` and `now_us`, as they do today.

`nv2a_occ_flip(o)`:

1. `nv2a_occ_poll(o, 1)`: take every result that is in, with a flush.
2. While something is pending and less than `o->settle_us` has passed since step 1: poll again with a flush (a spin on `GetData`, as `sync` mode spins per report; here once per flip, for every report at once).
3. Settle each report still pending: `nv2a_report_write(mem, va, last_count(va))`, or `NV2A_OCC_VISIBLE` when the address has no last count; move it from `pend[]` to `retired[]` with its queries; count it as `settled`, and as `stale` or `first`.
4. Poll `retired[]` as `pend[]` is polled, here and in every later `nv2a_occ_poll`: a result updates `last_count(va)` and returns the queries to the pool; nothing is written to guest memory. A retired report older than `NV2A_OCC_LATE_US` is dropped unread; `retired[]` holds `NV2A_OCC_PENDING` entries and drops its oldest unread when full. Returning an in-flight query to the pool is safe on both backends (D3D11 `Begin` restarts it; Metal's `occ_put` retires the slot until the flip's wait).

`last_count` is a table of `NV2A_OCC_LAST = 64` entries `{va, count}` keyed by the report address, the oldest replaced when full. The XDK recycles a fixed set of report slots per device, so the addresses a title uses are few and stable (BLiNX 2: two on this screen; B3: about twenty); the table is a bound, not a model. The count stored is the guest-size count, after the render-scale division, so a scale change needs no rescaling of history. The scale-change path, which today polls with a flush and then sets the scale, calls `nv2a_occ_flip()` first and drops `retired[]` unread: a retired result read at the new scale would be off by N², and the one count it would have refreshed is a frame old anyway.

**The other two places, and why not.** At the title's read: `GetVisibilityTestResult` is recompiled title code (`sub_002E0D20` in BLiNX 2, RenderWare's own in B3) reading guest memory; there is no HLE to hook, and a guard page per report would turn every read into a fault. At a fence: the visibility API uses no fence or semaphore of its own, and the executor's semaphore releases are the title's frame fences, which come at the flip or later; the flip is the fence the title has.

**The bound, `occ_settle_us`, default 0 (superseded by D9: 8000 µs a frame).** The investigation proposed a 2-4 ms wait at the flip. It is kept as a knob and not as the default, for three reasons. The settle write must land before the title's read in the next frame, and every microsecond waited is a microsecond in which the title can still read incomplete; with no wait the write lands with the flip. Where the GPU is more than the bound behind, the wait is a stall on the ack thread for nothing, and that is the host being fixed, where the executor's time is scarcest (1509 batches at scale 4). And exactness over one-frame staleness has no visible beneficiary we know of (D1's last row). The knob makes the Windows A/B a rebuild-free comparison (D6); if the stale answer ever shows, that run is where a nonzero default would earn its place.

**Thread safety.** `struct nv2a_occ` is touched only on the ack thread: the hooks, `on_poll`, the flip and now `nv2a_occ_flip()`; `retired[]` and the last-count table are plain fields with the same owner, so no lock is added. The title's reads see each report through `nv2a_report_write()`'s count-then-status release store, the same writer the settle uses. One window is accepted: a title that has already reset a slot for frame N+1's test when frame N's report at that slot settles reads frame N's count where the console would have read incomplete; the next `GET_REPORT` sets the slot pending again, and the count is the previous frame's for the same object.

**What does not change.** The supersede rule (a `GET_REPORT` at an address with a report pending drops the old one unread) now applies within a frame only, since nothing stays pending across a flip; it is kept for titles that push one address twice a frame (the smoke's report 2). The 250 ms fallback is kept for titles that never flip while spinning. Overflow, `sync` and `fixed` modes, the CPU and null paths, `nv2a_occ_scale_count` and the walker's `get_report()` are untouched. The hook comment in `nv2a_pb_state.h` says the backend writes a deferred report "now or later, and no later than its `on_flip` returns".

## D3. Debug keys, trace and the flip log

Two rows in `recomp_env.h`, debug tier, no old name, beside `d3d11_occ` and `metal_occ`:

- `occ_delay_us`: `=us: hold every visibility result back this long (test hook)`. In `occ_ready()`: a report's result is not taken before `now - t0 >= delay`, on both backends and in `sync` mode. It is the diag's `LOADCAT_OCC_DELAY_US` moved into the table. The diag's `LOADCAT_OCC=0` (every test invisible) is not kept: `zpass_fixed=0` does it already.
- `occ_settle_us`: `=us: per-frame wait for pending visibility results before settling them at a walk end, semaphore release or flip (8000; 0 none)` (D9; the first text, `wait this long at the flip ... (0)`, is superseded).

Both are read once by each backend and handed to the tracker with `nv2a_occ_set_delay()` / `nv2a_occ_set_settle()`, so `nv2a_backend_common.c` keeps no `recomp_env` dependency and the ctest sets the fields directly, as `render_scale` sets the scale. Rows in cat's `docs/env.md` (Debug 91 to 93; `scripts/test_env_doc.py` checks the count).

`RECOMP_TRACE=flip`: both backends' flip lines gain `settled N (stale M, first K)` after `superseded`, and the end-of-run summary the totals. `RECOMP_TRACE=zpass` prints the first 64 settles with the flip number, address, the count written and the report's age, which is what the Windows run reads. The diag's `[OCCAGE]` histogram is folded into the summary under `zpass`: eight buckets of result age, so a run states its GPU latency without a patch.

## D4. Tests

**`tests/occ_reports`**, a standalone ctest like `tests/render_scale` (`project()`, builds `nv2a_backend_common.c` and `nv2a_tex_pack.c`, found by `tests/posix_ctest.sh` on its own). Fake ops: a query whose result becomes available at a fake time set per query, a fake clock the test advances, a pool that counts gets and puts. Guest memory is an array; the report words are read back directly. Cases, each one `[occ_reports] name: PASS|FAIL` line:

1. **Ready at the flip:** a test at A with its result in; `nv2a_occ_flip` writes the real count, status 0, `settled` 0; the last count for A is that count.
2. **Pending at the flip, with history:** A tested again, result not in; the flip writes A's last count, status 0, `stale` 1. The result then arrives (clock advanced, poll): the report words are unchanged, and after the title resets the status to 0xFFFFFFFF (as the next `EndVisibilityTest` would) a poll still leaves it; the last count for A is now the late result. A third test at A pending at the next flip reads that late count: one frame stale.
3. **Pending, no history:** a first test at B pending at the flip reads `NV2A_OCC_VISIBLE`, `first` 1.
4. **Superseded within a frame:** two tests at C before a flip, the first still pending: the first is never written and its queries are back in the pool before the flip (the rule as it is).
5. **Overflow and late:** a report with nine stretches reads visible at the next poll; with no flip at all a pending report reads visible after 250 ms of fake time, as today.
6. **Injected delay:** `delay_us` 16000 under a 16.7 ms fake frame: every flip settles stale with the previous frame's real count, the first with visible; the `settled` count equals the reports.
7. **The bound:** `settle_us` 2000 and a result that lands at 1 ms of fake time is exact, one at 3 ms is stale; with `settle_us` 0 both are stale.
8. **Scale change:** a retired result pending across `nv2a_occ_flip` plus a scale change is dropped and the last count keeps its old value.
9. **Accounting:** after every case gets equal puts (no leak through `retired[]`), and `retired[]` full drops its oldest unread with the puts to match.

**`tests/d3d11_backend_smoke`** (Windows and Proton): the cross-frame reuse case (report 3, pushed open and not waited for, found still pending at the top of the next frame and superseded) cannot run live any more: the flip settles report 3 first. The case becomes: at the top of frame f > 0, report 3 is complete (status 0) with count 100, or with the previous frame's 100 when it was settled stale, or `NV2A_OCC_VISIBLE` on the first frame; the run counts exact, stale and first, and `s_cross_live` and its "never ran live" failure go. The in-frame supersede (report 2, two tests in one frame) and the counts 0 and 100 stand. This test is not in the Mac gate; it runs on the Deck in the CLI's Proton ctest list.

## D5. The harness case

- **Preset `@story-idle`** in `src/pad_input.c` and `game.toml`'s `presets`, the script of `runs/loadcat/bin/loadgame-idle.txt`: the intro skip, `wait mem 0x5eb5f4 == 0x5eb620`, `wait mem 0x5eb620 == 0`, `tap START every 1 until mem 0x5eb620 == 0xd`, then idle. Run with the save the investigation used (`RECOMP_SAVE_SEED`), so the screen shows the characters. A README row beside `@story-load`.
- **`scripts/occ_flips.py LOG [--min-batches 1400]`** (stdlib): reads the `[METAL]` / `[D3D11] flip N batches B ... occ ...` lines, takes the first flip with at least `min-batches` as the screen being up, and prints the histogram of batch counts after it, the number of flips below the floor, and the `occ` totals (reports, settled, stale, first). Exit 1 when any flip after the first is below the floor, 2 when the log has no flip lines. `scripts/test_occ_flips.py`: the idle pattern passes, the delay pattern (1509 then 157s) fails naming the count, a log without flip lines exits 2, the floor is honoured. The floor is 1400 and not 1509 so a cursor blink does not fail the case; the idle run shows 1509 on every one of its 7864 flips.
- **The case:** `@story-idle`, 60 s, `RECOMP_TRACE=flip`, `RECOMP_DEBUG=occ_delay_us=16000`, stock otherwise. On `posix-host/portability` the checker fails with thousands of 157-batch flips (the Mac delay run: 3644); on the branch it passes with 0 below the floor and `stale` equal to the reports after the first flip. A second run without the delay must match the base run's histogram (all 1509) with `settled` 0 on Metal. Mac Metal headless and the Deck D3D11 from a Mac-built exe, under the run lock.

## D6. Stock proof and gates

The settle changes a report only when it is pending at the flip. The proof is therefore on that count, then on the frames:

1. **Metal, Mac:** attract, stage1 and story headless with `RECOMP_TRACE=flip`: the `settled` totals recorded (D9: the bounded wait settles some at stock where the first design's unbounded wait settled none), goldens pass with main's verdicts, no re-record; flips/s and mean frame ms against main's last runs (45.8 / 33.4 / 54.0 flips/s for attract / stage1 / story, as the present-scanout gate recorded), flagged at a 25% drop or 1.5x rise.
2. **D3D11, Deck:** `blinx2 bench golden` from a Mac-built exe: goldens pass with the verdicts of 20261015-154907 / -155027 / -155217; the per-scenario `settled` total from the flip log (D9: with the walk-end settle and 2 ms a frame, expected near 0 at stock; the first estimate, one to three flips, counted the flip only); speed against the same runs. If a reference frame differs at one of those flips, that flip is examined on its own before anything else moves: the only candidate is the first-time value (D1).
3. **Burnout 3:** `b3/scripts/race_gate.py` on the Mac (Metal) from a b3 build against the branch, and the `--pad-script` variant on the Deck under the run lock: pass, with the `settled` totals recorded; a race issues 15-20 tests a flip, so this is the gate that exercises the retired list at volume.
4. **The harness case** (D5) on the Mac and the Deck, base and branch.
5. **Native Windows, the user's PC** (the user's go first; drive D): a BLiNX 2 Windows build of the base and of the branch, `@story-idle` (or `RECOMP_INPUT_SCRIPT=runs/loadcat/bin/loadgame-idle.txt` until the preset is built) at `render.scale` 4, `RECOMP_TRACE=flip,zpass`, 60 s each, no injected delay. Recorded per run: the count of flips below 1400 batches after the screen is up (`scripts/occ_flips.py`), the `settled` / `stale` / `first` totals, the age histogram and flips/s. Expected: the base shows the 157-batch flips the user sees (this is the first measurement of the fault on its host; if it shows none, the run is repeated with the user playing the screen as they did) and the branch shows none, at a flips/s within the 25% rule. Then branch runs with `occ_settle_us` 0, 2000 and 8000 for the A/B on the default (D9 made 8000 the default). The user's own look at the screen is the acceptance for the eye.
6. **Toolkit:** Mac build with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`, `tests/posix_ctest.sh <dir>` 0 FAIL with `occ_reports` in the list; `pytest tools/recomp tools/disasm` unaffected. cat: `uv run pytest scripts` (the new checker test, `test_env_doc`), `uv run ruff check . && uv run ruff format --check .`. The CPU rasteriser builds; no CPU golden.

## D7. Branch and overlap

Toolkit branch `fix/occ-reports` off `posix-host/portability` in `wt/occ-reports/xboxrecomp`: `occ: settle pending visibility reports at the flip with the address's last count`, the ctest, the smoke rewrite, the keys; landing by `git merge --squash`. Cat branch `spec/occ-reports` (`wt/occ-reports/cat`) carries this spec, the `docs/env.md` rows, the preset and the checker; TASKS is the main session's.

The three in-flight branches touch the same files elsewhere:

- `feat/fork-prs-aniso-bumpenv` (`wt/hgpr`, likely first): `nv2a_backend_common.c` at `nv2a_stage_decode`, `nv2a_ps_consts_fill`, `nv2a_host_render_scale` and `nv2a_downscale_box32` (hunks at lines 6-800), the header at `struct nv2a_stage`, `nv2a_ps_consts` and the host options (516-1079); this change edits the occ block (`occ_begin` to `nv2a_occ_report`, 453-610) and its header section (960-1025). `nv2a_pb_d3d11.c` at the sampler and `setup_pixel` (177-2327) against this change's `d3d11_flip` (3590-3748), `flip_log` (3325-3375) and the occ section (3759-3915); `nv2a_pb_metal.m` at `address_mode`, `fnv` and `metal_on_draw` (128-2096) against this change's occ section (2486-2760) and `metal_flip` (2839-3043). `recomp_env.h` rows at 61 and 114 (config and trace tiers) against two debug rows near 202-209. No shared hunk; `git merge-tree` should be clean.
- `fix/present-scanout`: `nv2a_pb_exec.c`'s present block and `tests/nv2a_backend_smoke`, neither touched here.
- `fix/present-mode-height`: `nv2a_pb_d3d11.c` at 3299-3320 (the `s_occ` declaration and `flip_log`'s statics) and `present_target` (3509); this change adds counters to `flip_log` at 3325-3375, adjacent to the first hunk, so a trivial textual conflict is possible and whichever lands second rebases it. `nv2a_pb_metal.m` at 2100-2136 (`present_extent`), clear of this change. `tests/d3d11_backend_smoke/smoke.c` at 19, 47, 103, 578 and 1180 against this change's visibility case (116-140, 728-760, 880-930 and the summary near 1165-1175): the summary lines are near its last hunk; same remedy.

On the cat side all three and this change edit `docs/env.md` in different rows, and only this change touches `pad_input.c`, `game.toml`'s presets and `scripts/`.

## D8. Amendment during implementation: settle after every walk, not only at the flip

The flip alone (D2) does not fix the case. On the Mac with `occ_delay_us=16000` the first branch (toolkit f583895, settle at the flip only) lost the cat on 2787 of 3050 flips, as the base did (2839 of 3104; `runs/occ-reports/mac/branch-d16000-164144`, `base-d16000-164034`): reports were pending at the flip on only 365 of them. BLiNX 2 reads the LOAD GAME tests inside the frame that issued them, before the walker reaches that frame's `FLIP_STALL`, so D1's "read after the swap" was wrong. Three probes placed the read:

- Releasing the swap (`flip_read`, the frame counters) after `on_flip` instead of before: still lost (2680 of 3075, `expB-d16000-164553`). The title does not wait on the swap before it reads.
- `metal_occ=sync` with the delay, which holds the walk at each `GET_REPORT` until the result is in: never lost (0 of 1292, `branch-sync-d16000-164724`). The title reads only after the walk that carried the report has been acknowledged.
- Settling from `on_poll`, the ack thread's pass after each walk: never lost.

So the settle runs at the last point before the title can read, the pass after the walk, as well as at the flip: `nv2a_occ_settle(o)` is steps 1-4 of D2, and `nv2a_occ_flip(o)` counts the flip and calls it. Both backends call `nv2a_occ_settle` from `on_poll` in place of the flushing poll. Metal first waits for the command buffers of the reports still pending (committed at `GET_REPORT`), so at stock every result is in and nothing settles (no-delay run: settled 0, results <1 ms 4881, <2 261, <4 554, <8 31). On D3D11 a report whose `GetData` is not done after the walk now settles with the last count where it used to stay incomplete; the Deck runs measure how often at stock.

The flip's settle stays in Metal's flip after `flush(1)`, not in `occ_after_wait()` (2.2), which also runs at the waits inside a walk (a full ring, a readback).

A last count older than `NV2A_OCC_LATE_US` counts as no history (visible): with the delay the first settle on the LOAD GAME screen otherwise took the count 0 its slot had at boot, 470 flips before, and dropped the cat for one flip.

Mac results with this design (`runs/occ-reports/mac/walk-*`, 60 s, LOAD GAME idle): delay 16 ms, 0 flips below 1400 batches (1509 x2996), settled 6116 (stale 6113, first 3); delay 8 ms, 0 below (1509 x3093); no delay, 0 below, settled 0. Base with the diagnostic delay: 16 ms, 2914 below (157 x2839); 8 ms, 31 below (157 x15).

## D9. Amendment after review: settle before the title can read, 2 ms a frame by default

The review of toolkit d6ae77e found the walk's settle too late and the two backends unequal:

- **Where.** `on_poll` ran after GET was stored, so the title, which polls GET and its semaphores, could already read. The executor now owes a poll after any `on_report` that returned 1 (`s_report_owed`) and pays it in `reports_settle()`, called before `BACK_END_WRITE_SEMAPHORE_RELEASE` writes its semaphore and from `nv2a_pb_exec_walk_end()`, which `nv2a_pb_scan.c` calls right after the walk, before the stop salvage and before GET is stored. The `on_report` contract in `nv2a_pb_state.h` now reads "no later than the next `on_poll`".
- **How long.** Metal's settle first waited for every pending report's command buffer, unbounded; D3D11 waited `occ_settle_us`, default 0. Both now run the one bounded loop in `nv2a_occ_settle`, with `NV2A_OCC_SETTLE_US` as the common default (0 keeps the no-wait behaviour): 2000 µs in 797bbc9, 8000 µs since 7181ea4 (the A/B below). The budget is per frame (`frame_wait_us`, reset by `nv2a_occ_flip` after its settle), so a frame with many walks waits at most that in all. On Metal `occ_result(flush=1)` commits a query still in the open command buffer before the wait (review F4).
- **Polling.** Settled reports in `retired[]` are polled without a flush; an `on_poll` with nothing pending does only `nv2a_occ_poll(o, 0)`. The scale-change path uses the same settle on both backends.
- **Tests.** `tests/occ_reports` gains the per-frame budget and a late result that must not replace a newer report's count (12 cases). The smoke's first-time check allows a visible fallback after any gap over 250 ms.

Mac results (toolkit 797bbc9, `runs/occ-reports/mac/rev-*`, 60 s, LOAD GAME idle):

| Delay | Flips below 1400 | Settled | Settle wait |
|---|---|---|---|
| 16 ms | 0 | 6022 of 6022 (stale 6019, first 3) | 2 ms a frame |
| 8 ms | 0 | 6228 of 6236 | |
| none | 0 | 76 of 6232 | 756 ms in 60 s |

The cost of the bound: Metal at stock now settles some reports stale where the unbounded wait settled none (stage1 golden: 7548 of 33341 under a host load of 40-50; attract 13 of 67; story 35 of 2792). The goldens still pass (D6.1). A stale count here is the previous frame's count for the same object, the D1 answer.

Stage1 A/B on Metal at a host load of 8-13 (`runs/occ-reports/golden-metal-stage1-*`; 78 s each, all pass, the pace is the game's):

| `occ_settle_us` | Flips/s | Settled | Settle wait |
|---|---|---|---|
| 0 | 34.1 | 29228 of 29376 | 0 |
| 2000 | 34.0 | 8948 of 31125 | 3.1 s |
| 8000 (default) | 33.6 (load 12 to 6; 30.2 at load 26) | 9 of 30097 (59 of 31754 at load 26) | 4.5 s |
| 20000 | 34.0 | 0 of 30928 | 4.4 s |

Metal's results come in within a frame, but a fifth of stage1's come in more than 2 ms after the walk. The 8000 row is the sanity golden on the default (toolkit 7181ea4, `golden-metal-stage1-8000default`, pass); its first run, at a host load of 26, read 30.2 flips/s.

Deck D3D11 on 797bbc9 (bench-logs 20261015-191403 / -191523 / -191715): the goldens pass with the same verdicts, at 29.9 / 29.95 / 30.0 flips/s, p50 33 ms and p95 34 ms on all three, the same as d6ae77e (pacing-stats: no flags). Settled at stock dropped from 9172 of 20360 / 15133 of 43379 / 998 of 3551 (d6ae77e, no wait) to 130 / 60 / 6. Stage1 A/B on the Deck (`bench run`, 105 s, no frame dumps; frame ms from `[PB-PERF]` after flip 800):

| `occ_settle_us` | Settled | Settle wait | Wall ms mean / p99 | Walk ms mean / p95 |
|---|---|---|---|---|
| 0 | 19894 of 47165 | 0 | 33.33 / 33.92 | 12.03 / 15.19 |
| 2000 | 40 of 45132 | 1.05 s | 33.33 / 34.07 | 12.46 / 15.59 |
| 8000 | 27 of 46247 | 1.09 s | 33.34 / 34.07 | 12.44 / 15.62 |
| 20000 | 0 of 47892 | 1.07 s | 33.35 / 33.95 | 12.33 / 15.61 |

On D3D11 the results come in within 2 ms of the walk almost always, and any bound costs about 0.4 ms of walk a frame (in the locked 33.3 ms frame). So the default is 8000: it costs D3D11 what 2000 does and leaves Metal almost nothing to settle, and a host whose GPU is further behind pays at most 8 ms a frame. The 6.6 A/B (0, 2000 and 8000 passed explicitly) can still move it before the merge.

## Validation

- `tests/posix_ctest.sh`: 0 FAIL, `occ_reports` with its ten cases; the d3d11 smoke on the Deck with the rewritten case.
- BLiNX 2 goldens, Metal and D3D11, unchanged verdicts and speed within the limits; `settled` 0 on Metal and the per-scenario totals on D3D11 recorded.
- The harness case: base fails, branch passes, on Metal and D3D11; without the delay the branch matches the base.
- B3 race gate on Metal and the Deck, pass.
- Native Windows before and after, with the user's go; the `occ_settle_us` 0 / 2000 / 8000 A/B.
- Review before the merge; fixes go back to the branch's agent.
