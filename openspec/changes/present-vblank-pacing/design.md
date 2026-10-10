## Context

Pushbuffer flow today (toolkit 0988b9c):
- The title writes methods and calls `KickOff`. KickOff sets PFB 0x100410 bit 16, spins until that bit clears, then writes `DMA_PUT`.
- The `nv2a-ack` thread (`xbox_memory_layout.c`) clears the bit only when the walker has executed everything up to the last `PUT` (fast-kick path), or at the top of every tick (`fast_kick=0`). It walks `[g_scanned_put, PUT)` with `nv2a_pb_scan`, which feeds `nv2a_pb_exec_method`, and then sets `DMA_GET = PUT`.
- The kick ack is the title's only back-pressure. The KickOff comment explains why it can't be acknowledged early: with no GPU interrupts, the title's MakeSpace NOP-with-notify would wait forever.

At `FLIP_STALL` the executor:
- presents (`present_pick`, `on_flip`) on whichever backend is active (CPU, D3D11, Metal, null);
- bumps the registered frame counters (`xbox_Nv2aFrameCounterFlip`);
- carries on.

Nothing ever waits for a vblank. On the console the wait lives in the GPU (FLIP_STALL until READ_3D moves), and D3D's interrupt and DPC code decide when READ_3D moves (proposal, point 1). xemu models the same behaviour:
- a non-zero `NO_OPERATION` traps as a PGRAPH software-method interrupt, and PGRAPH waits until the ISR services it;
- `FLIP_STALL` blocks the 3D pipe until the read index set by `PGRAPH_INCREMENT` moves away from the write index;
- the guest's vblank handler writes `PGRAPH_INCREMENT` after it flips.

This change models behaviour only. No xemu code is used.

The vblank clock is the toolkit's nanosecond schedule (`kernel_vblank_tick_ns`, 60 Hz on an absolute grid, restart after 100 ms behind). `xbox_VblankCount` reads the count of vblanks raised. The count advances even while `PCRTC_INTR_EN_0` holds the ISR back.

## Goals / Non-Goals

**Goals**
- The guest never sees more than one flip per presentation interval of its 60 Hz vblank, on every backend and whatever the host refresh rate.
- Burnout 3's front end and race run at about 60 flips/s on Metal, and its intros and race run at real time.
- BLiNX 2's goldens don't move.
- The rule can be tested on its own, and the old behaviour comes back with one debug key.

**Non-Goals**
- Modelling GPU interrupts, the software-method trap or `PGRAPH_INCREMENT` for real (alternative B).
- Host-side frame pacing such as present timing or VRR. Host vsync stays as it is.
- An uncapped or unlocked mode (enhancements layer, later).
- The legacy `src/nv2a` pgraph path.

## Decisions

### 1. Hold the walker in the toolkit, on the guest vblank count
The executor already sees the swap. It records a pending flip at FLIP_STALL. The ack loop (the walker's own thread) decides each pass whether the flip may be released, from `xbox_VblankCount()`. This puts the wait where the console has it, in the GPU's consumption of the pushbuffer, and needs no new guest-visible mechanism.

*Alternative B, rejected for now:* deliver the PGRAPH software-method interrupt to D3D's ISR, let the guest queue and flip, and release FLIP_STALL on the guest's `PGRAPH_INCREMENT` write. That is the most faithful option, but it makes the toolkit raise GPU interrupts for the first time:
- `PGRAPH_INTR` is held at zero today because of Halo's recursion;
- MakeSpace's NOP-with-notify, swap callbacks and T()NY's software-method-5 event would all start running;
- every title's interrupt path would change.

That is a much larger, riskier change, and it can come later if a title needs its swap callback (`miniport+0x18C`) or its `D3DSWAPDATA`. Rejecting it now is right: the hold gives the same guest-visible pacing for every title that waits on KickOff, fences or the vblank count, and it can be removed cleanly when B lands (B makes the hold redundant: FLIP_STALL would then wait on the guest's `PGRAPH_INCREMENT` write). B is recorded as a follow-up in TASKS and in the upstream plan under topic 4, and the upstream PR description for this change names it as the faithful successor.

### 2. The release rule: `last_flip_vblank + interval`, not D3D's `now + 1`
D3D queues a flip for `max(last + interval, now + 1)` (IMMEDIATE: `now`). That quantises a late frame to the next vblank, which is what the console does with double buffering. Here the toolkit uses:

- `target = last_flip_vblank + interval`;
- release when `(int32)(VblankCount - target) >= 0`;
- `last_flip_vblank = max(target, count at FLIP_STALL)` when the flip is released, where `count at FLIP_STALL` is `xbox_VblankCount()` sampled when the walk that reaches the FLIP_STALL began (`nv2a_pb_exec_walk_begin`, called by `nv2a_pb_scan`). The title waits in KickOff until the walker has caught up, so that walk starts within about 50 µs of the title's kick of its Swap segment: it is the vblank the title swapped in. The hold's own clock (the 100 ms bound, `held_ms`) still starts at the FLIP_STALL, before the backend's `on_flip`.

Why not D3D's rule:
- **The cap is the same.** A title faster than its interval is held to it: 60 Hz at interval 1, 30 at interval 2.
- **A title that already takes `interval` vblanks per frame is held only where its pacing and its swap interval disagree.** BLiNX 2 waits for its vblanks on the CPU before each present, so a steady frame is never held. BLiNX 2 is held, rarely and a whole vblank at a time (Mac Metal goldens, 2026-10-10, `runs/pacing/golden2`): story 25 holds in about 4200 flips (about 0.6%, 419.7 ms, so about one vblank each), stage1 5 holds (82 ms), attract none; the CPU backend's stage1 2 holds (23 ms). The holds fall where BLiNX 2 changes its swap interval: 22 of story's 25 and all of stage1's are in the trace windows that mix `iv1` (its 60 fps menus and story) with `iv2` (its 30 fps stage loop). The first interval-2 swap after an interval-1 flip at vblank V comes at V+1 and is held to V+2. D3D's own rule gives the same V+2, so the console holds that frame too. The few holds in interval-1-only windows are the same shape: the title swaps again within the vblank a held flip was released on. None changes a golden frame. Its goldens pass unchanged.
- **No quantisation cost on slow backends.** A frame that misses the vblank isn't pushed to the next one. Under `now + 1`, the Proton CPU backend (B3 menus about 14 fps) would idle the walker for up to 16.7 ms after every frame. The kick ack serialises the title behind the walker, so on hardware the CPU would overlap that wait and here it can't. That would cost up to about 15% of its frame rate for no guest-visible gain.

Recorded deviation: a title that would drop to exactly 30 fps on a console when a frame takes 17 ms runs at about 58 here. Titles that count vblanks per frame are unaffected, and that is the XDK norm. The deviation is switchable: `RECOMP_DEBUG=flip_pacing=edge` makes the rule `target = max(last + interval, count at FLIP_STALL + 1)` (interval 0 with IMMEDIATE still never holds, and a late ONE_OR_IMMEDIATE flips at once rather than waiting, as D3D does). It is one flag in the pure rule, covered by `tests/flip_hold`, and exists for fidelity A/B runs (a Burnout 3 race scene compared under both). It is not a golden mode: BLiNX 2's goldens pin the default.

Jitter holds on a self-paced title (implementation finding, 2026-10-10): the first cut sampled the count at the FLIP_STALL itself, which is walker time and includes the Swap segment's own draw time (several ms on Metal). BLiNX 2's 60 fps menu and story windows then saw a frame swapped just before a vblank counted after it, and its next frame read as a second flip in the same vblank: about 25% of flips held, about 15.5 ms each, the title's next kicks blocked, and the story golden's hub anchor arrived 13-27 flips early (NEWVIEW, `runs/pacing/golden/`). Sampling at the walk's start (above) removes that lag from the count. The trace's `iv1`/`iv2` and `holds` fields report what remains, and the goldens decide.

### 3. Where the walk pauses: at the end of the segment
The FLIP_STALL is usually the last method of a segment, because Swap kicks. When it isn't, the walker finishes the segment and holds before the next one, so `DMA_GET` always equals the `PUT` it walked to:
- Parking `GET` mid-segment would leave the submitted words unconsumed while the title keeps writing. Its MakeSpace could then take the NOP-with-notify path, which hangs here.
- Reporting `GET = PUT` over unread words is the lost-command race that the ack loop's `DMA_GET` comment describes.

Commands after a FLIP_STALL in the same segment therefore run before the vblank instead of after it. They draw into the next back buffer, and the present has already happened, so the picture is unchanged.

### 4. Back-pressure: hold the KickOff ack, even with nothing to walk
While a hold is pending, the ack loop doesn't acknowledge the kick bit. That applies on the fast path even when `PUT == g_scanned_put`, and the `NV2A_ACK` table entry skips the kick register. Otherwise the title would kick once more, get a whole segment ahead with `GET` behind, and reach MakeSpace's notify. A held title therefore waits in its next KickOff, which is where it waits on the console when the GPU is stalled.

In the fast-kick inner loop a new `PUT` no longer counts as "new work, tick now" while held. The loop naps at 50 µs to 1 ms and checks the release. The release latency is at most about 1 ms after the vblank.

### 4b. Threads and locks, and why the hold can't deadlock
- The hold runs on the `nv2a-ack` thread, which is where `nv2a_pb_scan` and the executor already run. It is a host thread: it never runs guest code, never takes the guest CPU (BLX-31 `fix/mac-one-cpu` 32cd6fd: only guest threads hold it, and the DPC drain never does), never enters the DISPATCH gate (`kernel_hal.c`) and takes no backend lock while it naps. Its nap is the existing `kick_nap_us(50)` to 1 ms fast-kick loop, or `Sleep(1)` on the `fast_kick=0` path.
- Release depends only on `xbox_VblankCount()` (bumped by the `kernel-timer` thread in `kernel_vblank_tick_ns` before the ISR or DPC run) and on host time. No guest thread is on that path, so a guest thread stuck behind the hold can't stop the release. The 100 ms bound covers a stalled timer thread.
- The held title sits in KickOff's `test [0x100410], 0x10000 / jne` loop, guest code at PASSIVE_LEVEL. It holds no gate, so the vblank ISR and D3D's vblank DPC (which bump the counter, write `PCRTC_START` and `PGRAPH_INCREMENT`) run as usual on the timer thread. The DPC waits on nothing the walker owns: its register writes land in the aperture's plain RAM.
- Under BLX-31's guest-CPU lock a raw KickOff spin would hold the guest CPU for the length of the hold. That is why the site is lowered (decision 9): `xbox_SpinWait` yields to waiting guest threads even at `present.pacing=spin`, and sleeps at `sleep`. The ack loop calls `xbox_SpinWake()` on every kick clear so the lowered site wakes within a scheduler tick, not at `SPIN_TIMEOUT_MS`.
- Fences: a semaphore release lives in a kicked segment, and the walker holds only after it has walked everything up to `PUT`. So every fence the title can be waiting on is already released, and the segment behind the held kick hasn't been submitted (the title is still in KickOff). D3D's wait-for-idle (`GET == PUT`) is satisfied for the same reason. MakeSpace's notify path is unreachable: the title can't get a segment ahead while its kick isn't acknowledged.
- BLX-2's DPC drain runs DPCs at a raise to DISPATCH on the raising thread and on the timer thread. The held title never raises, so its DPCs drain on the timer thread; that is today's behaviour whenever the title spins in KickOff behind a slow walker.
- The only new wait is therefore KickOff itself, bounded by `target` or 100 ms. Hold time is measured by the kick observer's existing `kick_wait_ns` as well as the new `held_ms`.

### 5. Decoding the swap
`NO_OPERATION` (0x0100) with `(param & 0x1F) == 1` is D3D's swap software method. In `payload = param >> 5`:
- `interval = payload & 7`: the encoder maps DEFAULT to 1, ONE to 1, TWO to 2 and THREE to 3;
- `immediate = payload & 8`.

A FLIP_STALL takes the interval of the latest swap NOP since the previous FLIP_STALL, or 1 when there was none (the triple-buffer path in `sub_00350C10`, other XDKs). Interval 0 with IMMEDIATE never holds. Interval 0 without IMMEDIATE doesn't come out of the encoder, and is treated as 1. Other software methods (`param & 0x1F` other than 1, and 0) are ignored as now.

### 6. Safety bounds
- **No hold while the vblank clock isn't running.** That covers `RECOMP_VBLANK` unset and a count that hasn't advanced for 100 ms (a stalled timer thread, or the Mac's known 100-300 ms host stalls).
- **A hold ends after 100 ms of host time** even if the count hasn't reached the target. Timeouts are counted.
- **No hold inside a pushbuffer CALL.** The walk's `in_call` state isn't kept across walks.
- **A walk that stops** (the `stop_salvage` path) clears any pending hold. Its catch-up rules are unchanged.

### 7. Frame counters: the title owns a counter it moves itself
`g_frame_counters[i]` gains `last_written`, `seeded` and `owned_by_title`. Before each bump (per flip, or by the 60 Hz fallback), the counter is read:
- the first bump always happens and seeds `last_written` with the value it wrote (a field that starts non-zero, or that D3D initialised, must not read as title-owned on the first look);
- from then on, if `(int32)(cur - last_written) > 0`, something other than the toolkit advanced it, so the title owns it: no more bumps, and one log line;
- a counter that went backwards (a device reset) stays the toolkit's.

The bump and the DPC's increment are both plain read-modify-writes of the same guest word from two host threads, as today. A lost update there delays the detection by one look at most; it never prevents it. For Burnout 3 at 350 flips/s the stand-down lands within one vblank of D3D's first DPC.

For B3 this triggers at the first vblank DPC after D3D starts. HL2 and Wreckless keep their bumps wherever only the toolkit moves the field. That is why the rule doesn't key on "the vblank ISR is live": Wreckless's counter may be one only a GPU interrupt would move.

### 8. Debug key and trace
- **`RECOMP_DEBUG=flip_pacing=0`** turns off the hold (decisions 1-6) and the ownership rule (7), for A/B runs. It is one key because the two together are what "flips paced by the vblank" means. The `recomp_env.h` row goes in the debug tier, and cat `docs/env.md` gets a row.
- **`RECOMP_TRACE=pacing`** (window line) adds `holds`, `held_ms`, `hold_timeouts`, swaps per interval (`iv0/1/2/3`, `nonop`) and `counters_owned`.

### 9. The KickOff spin as a listed spin-wait site
Both titles' KickOff spins are the same two instructions on PFB 0x100410 bit 16 (BLiNX 2 at 0x002E7F20 in `recomp_0088.c`; Burnout 3 at 0x00351BF0 in `sub_00351BD0`, the KickOff that `sub_00350C10`'s Swap calls). Neither is in `config/spin_waits.json` today, so each is a raw guest loop: it burns a core for as long as the kick waits, and under the guest-CPU lock it keeps the CPU from every other guest thread for that long. Today that wait is the walker's lag; with the hold it is up to a vblank per frame. Listing the site lowers it to `RECOMP_SPIN_WAIT`, which at `present.pacing=spin` (stock, golden-pinned) still busy-waits but yields the guest CPU to waiters (BLX-31 `kernel_pacing.c`), and at `sleep` blocks on the kernel's condition variable. The ack loop's kick clear gains an `xbox_SpinWake()`; `kick_cleared()` today only keeps statistics. The matcher (`tools/recomp/spin_waits.py`) knows `cmp` and `test`; if this site's form fails it, the matcher is extended with a test, because a listed site that fails stops the recomp stage by design.

### 10. Code placement
- **New `src/kernel/nv2a_flip_hold.{c,h}`**, pure, no globals in the rule functions:
  - `XboxFlipHold` state;
  - `xbox_FlipHoldSwap(h, param)`: NOP decode;
  - `xbox_FlipHoldStall(h, count, now_ns, clock_ok)`: arm (`clock_ok` is 0 when the vblank count is stale or the stall is inside a CALL);
  - `xbox_FlipHoldPoll(h, count, now_ns, clock_ok)`: returns 1 while still held, 0 once released;
  - `xbox_FlipHoldCancel(h, now_ns)`: a walk stop drops the hold;
  - `xbox_FrameCounterOwned(seeded, last_written, cur)`.
- **The executor** owns one `XboxFlipHold`, calls Swap and Stall, and exports `nv2a_pb_exec_flip_poll()`, `nv2a_pb_exec_flip_cancel()`, `nv2a_pb_exec_walk_begin()` (the walk-start vblank sample) and `nv2a_pb_exec_flip_report()` (the trace line). The executor and the ack loop run on the same thread, so no lock is needed.
- **`xbox_memory_layout.c`** calls Poll each pass, skips the walk and the kick ack while held, and keeps the counter ownership.
- A separate file keeps the diff away from BLX-31's `kernel_pacing.c` and `kernel_bridge.c` edits. `kernel_pacing.c` gets only the trace fields, behind a small getter.

## Risks / Trade-offs

- **A title that waits for GPU progress on something other than KickOff during a hold** (a fence on the swap's own semaphore, say) waits up to one vblank, as on the console. It can't hang, because of the 100 ms bound.
- **B3 race frames that take longer than 16.7 ms from release to FLIP_STALL** run below 60 with no hold. They are no worse than today's natural rate.
- **Kick-ack serialisation** means the title can't build the next frame while the walker is held. D3D kicks many times a frame (about 16, per the KickOff comment in `xbox_memory_layout.c`), so the title gets at most one kick's worth of work done before it blocks; on the console it would run ahead until the ring filled. For B3 on Metal (about 11-14 ms per race frame) the frame still fits in 16.7 ms. If the race lands at 30-45 flips/s, a follow-up could let the title run one segment ahead during a hold. That needs MakeSpace's notify to be modelled first, so it isn't in this change.
- **The guest-CPU lock.** With a raw KickOff spin the hold would starve the title's other guest threads for most of each frame on hosts that run the lock (the Mac after BLX-31). Decision 9 removes that; the gate on it is Burnout 3 on the Mac with the lock on, checked through the APU underrun and spin-site trace, since the Mac plays no sound without asking.
- **BLiNX 2 FMV or loading screens** that present faster than every two vblanks are now held to 60 Hz. That is console-correct, but any golden that covers them would show it. The goldens and the trace's `holds` count settle it.
- **Upstream:** this changes every title's frame timing. It is offered upstream as its own PR and tested on Burnout 3 under Proton on the exact head.

## Open Questions

- Does B3 take the swap-NOP path everywhere, or the triple-buffer path (`[device+0x1A10] >= 3`, no NOP) somewhere? The trace's `nonop` count answers it, and the default interval 1 covers it either way.
- Does B3 register a swap callback (`miniport+0x18C`, which is device + 0x1DB4) that would want `D3DSWAPDATA`? The gen code has no store to device + 0x1DB4, so probably not. Task 1.1 confirms it. If it does, alternative B becomes a follow-up.
