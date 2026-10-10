## Why

Burnout 3 presents faster than the guest's 60 Hz vblank on every backend (BLX-49, BLX-53):

- **Steam Deck, Proton, D3D11:** the menus and the other pre-race screens run at 90 fps on the Deck's 90 Hz screen, so the audio drifts out of phase with the picture. The race runs at 60, because there it is GPU-bound.
- **Mac, Metal** (b3 `b3/macos-host` 71a0b04, `notes/b3mac/NOTES.md`, `runs/b3mac/*/flips.py`): about 2100 flips/s while the boot clears the screen, about 350 in the front end and 70-90 in the race. The vblank stays at a steady 60 Hz (600 per 10 s). The intro movies run 3 to 6 times too fast (EA 0.3 s, Criterion 0.7 s, Titles 9 s).

On the console a frame can't flip sooner than the next vblank. The toolkit has lost the two links that enforce that. Both are in the toolkit and both are backend-independent:

1. **FLIP_STALL never stalls.** The XDK's `D3DDevice_Swap` pushes these methods (B3 `sub_00350C10`, BLiNX 2 the same code in `recomp_0088.c`):
   - `NO_OPERATION` (0x100) with parameter `swap << 5 | 1`, which is software method 1. Its payload is the framebuffer address, the presentation interval in bits 0-2 and IMMEDIATE in bit 3 (encoder `sub_00350BD0`);
   - `FLIP_INCREMENT_WRITE`;
   - `NO_OPERATION 0`;
   - `FLIP_STALL`.

   On hardware the following then happens:
   - PGRAPH traps the non-zero NOP and raises its interrupt. D3D's ISR (`sub_00357000` → `sub_00357250`) queues the flip for vblank `max(last + interval, now + 1)`.
   - The vblank DPC (`sub_00356DA0` → `sub_00356CD0`) flips at that vblank. It writes `PCRTC_START` and `PGRAPH_INCREMENT` READ_3D. The READ_3D write releases the GPU from FLIP_STALL.
   - Until then the GPU consumes nothing more, and the title blocks on its next KickOff or fence.

   The toolkit raises no GPU interrupts (`NV2A_ACK` holds `PMC_INTR_0` and `PGRAPH_INTR` at zero, and only the PCRTC vblank bits are excluded from that ack), so none of this runs. The executor ends FLIP_STALL at once: `nv2a_pb_exec.c` sets `flip_read = flip_write` with the comment "there is no scanout here to wait for". The ack loop then acknowledges the next KickOff as soon as the walker is idle. The title is paced only by how fast the backend walks and presents: on Metal that is about 350/s, and under Proton/gamescope the host vsync caps it at the display's 90 Hz.

   Reviewed against toolkit 0988b9c (Fable, 2026-10-10): all three links check out in the code (`nv2a_pb_exec.c` FLIP_STALL, the `NV2A_ACK` table and its PCRTC exclusion in `xbox_memory_layout.c`, `xbox_Nv2aFrameCounterFlip` plus `frame_counters_tick`). The miniport offsets in (2) were read from the gen by the writing agent; the stand-down log line (below) confirms them at runtime.
2. **The registered frame counter counts twice.** `b3 src/game/main.c` registers `xbox_Nv2aFrameCounter(0x0035FB48, 0x1DE8)` for the XMV player. The XMV player reads that field through `D3DDevice_GetDisplayFieldStatus` (`sub_0034E0A0`). The field is the miniport's vblank count: the miniport sits at device + 0x1C28 (its first word is the register base) and its vblank count at +0x1C0, so the count lands at device + 0x1DE8. The vblank DPC increments it at +0x1C0 (`sub_00356DA0`). The registration dates from before vblank interrupts reached the title. Now that the DPC runs at 60 Hz (`[NV2A] vblank -> ISR claimed it`), `xbox_Nv2aFrameCounterFlip` still adds one more per FLIP_STALL. The movie clock therefore runs at 60 plus the flip rate, which explains the fast intros. Fixing (1) alone would still leave them at about 2x.

BLiNX 2 has the same D3D code and the same fault, but its main loop waits for its own DPC-driven vblank count (`0x00060475`, the fps-pacing change), presents at most once a vblank (every two in its 30 fps stage loop), and registers no frame counter. It therefore never ran fast. The same holds on a 90 or 120 Hz display: the guest's vblank comes from the toolkit's 60 Hz schedule, not from the host. D3D11 presents with sync interval 0 by default, and the SDL/Metal window presents on its own thread.

## What Changes

- **The walker holds after a flip until the guest's vblank allows it (toolkit, every backend).**
  - The executor decodes the swap's software-method NOP: the presentation interval, and IMMEDIATE.
  - At FLIP_STALL it still presents at once, as now, and then reports a pending flip. The hold target is `last_flip_vblank + interval`, counted on the guest vblank clock (`xbox_VblankCount`). `last_flip_vblank` is the vblank on which the previous flip was released.
  - While the vblank count is below the target, the ack loop:
    - finishes the segment it is in (so `DMA_GET` still equals the `PUT` it walked to, and no command is reported consumed before it is read);
    - leaves the next segment unwalked;
    - holds the KickOff flush ack, on both the fast-kick and the `fast_kick=0` paths. The title then waits on its next KickOff, as it waits on the stalled GPU on the console.

  Interval 0 (IMMEDIATE) never holds. A swap without the NOP counts as interval 1. A title that already takes `interval` vblanks per frame is held only where its swap interval changes (design 2). The release rule therefore caps the guest at 60 Hz (30 for interval 2) without the console's quantisation of a late frame to the next vblank. The design gives the reasons; `RECOMP_DEBUG=flip_pacing=edge` selects D3D's quantising rule for A/B runs.
- **Where the title waits, and on which thread the hold runs.** The hold runs on the `nv2a-ack` thread (the walker's and executor's host thread). It holds nothing while it waits: no guest CPU, no DISPATCH gate, no DPC lock, no backend lock. The title waits in KickOff's spin on PFB 0x100410, guest code at PASSIVE_LEVEL. On the console that spin lasts microseconds (the flush) and a stalled GPU is felt later, in MakeSpace or a fence; here the kick ack is the only back-pressure the toolkit has, so the wait moves there. The design records the cost (the title can't overlap the next frame's CPU work with the hold).
- **The KickOff spin becomes a listed spin-wait site in both titles** (`config/spin_waits.json`: BLiNX 2 the `test [eax+0x100410], 0x10000 / jne` loop at 0x002E7F20, Burnout 3 the same loop at 0x00351BF0 in `sub_00351BD0`, the KickOff `sub_00350C10`'s Swap calls). The hold makes that spin last up to a vblank per frame. Lowered, the site yields the guest CPU to other guest threads under BLX-31's guest-CPU scheduler and sleeps under `present.pacing=sleep`; raw, it would hold the guest CPU for most of every frame and starve the title's other threads (Burnout 3's audio and loader threads). The ack loop calls `xbox_SpinWake()` whenever it clears the kick bit, so a sleeping site wakes at once.
- **Safety bounds.** No hold while the vblank clock isn't running (no `RECOMP_VBLANK`, or no advance for 100 ms). No hold is longer than 100 ms of host time. No hold inside a pushbuffer CALL. A hold that times out is counted. The legacy `src/nv2a` path (no `RECOMP_PB_EXEC`) is unchanged.
- **Frame counters stand down once the title moves them itself.** `xbox_Nv2aFrameCounter` remembers each counter's last written value. If the counter has moved forward by itself before the next bump, the title's own code (here the vblank DPC) owns it. The toolkit then stops both the per-flip bump and the 60 Hz fallback for that counter, and says so once. The first bump of a counter always happens and seeds `last_written` (a field that starts non-zero must not read as title-owned); the comparison starts with the second. A title whose counter only the toolkit moves keeps today's behaviour.
- `RECOMP_DEBUG=flip_pacing=0` restores both old behaviours, for A/B runs; `flip_pacing=edge` keeps them on with D3D's `max(last + interval, now + 1)` release. One row in cat `docs/env.md`. The fix itself is stock behaviour, because the console does it. It isn't an enhancement, so it is on by default.
- `RECOMP_TRACE=pacing` adds to its window line: holds, held ms, hold timeouts, swaps by interval, and frame counters stood down. `hold_timeouts` is expected to stay 0 in every gate run; a non-zero count means the 100 ms bound fired and is investigated, not accepted.
- New ctest `tests/flip_hold` for the pure hold rule and the counter-ownership rule.
- The enhancements layer (`present.pacing`, BLiNX 2's `fps.mode`) is untouched. A future uncapped mode would turn the hold off through it.

## Capabilities

### Modified Capabilities
- `pushbuffer-executor`: a flip holds the walker and the KickOff ack until the guest vblank reaches the swap's presentation interval; frame counters the title moves itself are left to the title.

## Impact

- **toolkit:**
  - `src/kernel/nv2a_pb_exec.c`: `NO_OPERATION` swap decode; FLIP_STALL reports the pending flip.
  - `src/kernel/xbox_memory_layout.c`: the hold in the ack loop (deferred walk, kick ack held), and frame-counter ownership.
  - new `src/kernel/nv2a_flip_hold.{c,h}`: the pure rule.
  - `src/kernel/kernel_pacing.c`: trace fields only.
  - `src/platform/recomp_env.h`: the `flip_pacing` row.
  - `tests/flip_hold`.

  This changes when every title's frames go out, so it is upstream-relevant and gated on Burnout 3 under Proton. It belongs to topic PR 4 (interrupts, DPCs and pacing) of `analysis/upstream/pr-stack-plan.md`, where BLX-49 is already named; the executor's swap-NOP decode and FLIP_STALL arm travel with the walker (G2) if that series is split out first, and `nv2a_flip_hold.{c,h}` with its test goes with topic 4.
- **BLiNX 2:** expected unchanged, because it paces itself on two DPC vblanks per frame and has no frame counter. It is still held now and then, a whole vblank at a time, where it switches from interval 1 to interval 2 (about 0.6% of story flips; design 2). D3D holds the same frames on the console, and no golden frame changes. The goldens prove it, and the trace shows the hold count and the interval BLiNX 2 swaps with (`iv1` or `iv2`).
- **cat and b3 config:** `config/spin_waits.json` lists the KickOff spin in each title; gen is regenerated with `blinx2 analyze` then `blinx2 recomp` (b3 through its own pipeline, in a b3 worktree on its own branch; the orchestrator merges it). If the spin-wait matcher rejects the `test [mem], imm / jne` form, the matcher is extended in the toolkit (`tools/recomp/spin_waits.py`, with a `test_spin_waits.py` case), not the site skipped.
- **Burnout 3:** about 60 flips/s in the front end and the race, intros at their real length, and race logic at real time. A race that ran 1.2-1.5x fast on the Mac now runs at console speed: that is a correction, not a regression.
- **cat:** `docs/env.md` row; TASKS cross-references to BLX-49/BLX-53.
- **b3:** no change needed. The `xbox_Nv2aFrameCounter` registration can stay: it is now a fallback that steps aside. A later b3 change may drop it.
