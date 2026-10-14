## Context

- **How the APU is reached today.** With `RECOMP_AC97_READY` on, `MemoryLayoutInit` makes the first 0x30000 bytes of the APU window (guest 0xFE800000-0xFE82FFFF: registers and the voice processor) `PAGE_NOACCESS` (`APU_TRAP_BYTES`, `xbox_memory_layout.c`), so every guest load or store there faults. The GP and EP DSP memories above (0xFE830000-0xFE87FFFF) stay plain RAM: the model does not implement them, and Burnout 3's DirectSound copies into them with `rep movsd`, which the lifter lowers to a host `memcpy` that cannot be resumed from a fault.
  - **Win32:** the cat VEH (`src/main.c` `veh_handler`) calls `xbox_VehMmioFault`. That routes to `apu_hook_handle_mmio`, which decodes the faulting x86-64 instruction (`mmio_emulate`, `src/platform/mmio_decode.h`), calls `apu_mmio_rd`/`apu_mmio_wr` (which call `mcpx_apu_mmio_read`/`mcpx_apu_mmio_write`), writes the destination register and steps RIP. The decoder covers `mov` both ways, `movzx`, the two-operand ALU forms, group 1 with an immediate, and `test`: a register-destination form reads the device once; a memory-destination form reads, then writes.
  - **POSIX arm64:** the same goes through `xbox_PosixMmioFault`, the A64 decoder and `apu_hook_handle_mmio_posix`.
  - **x86-64 POSIX:** audio is always off, the range is never trapped, and the window is plain RAM.
- **Measured (bench-logs 20261011-220809/-221209; `spike-results.md` 1.4):**
  - the round trip under Proton is 51.4 us per access, against 0.7 us of model work;
  - 5-1 play makes 7,500-8,000 accesses/s;
  - with the APU off, the same play is a locked 30.0 flips/s on D3D11.
- **Where the accesses come from.** All the hot ones are DirectSound's front-end PIO writes, made from constant addresses in the generated C, for example:

  ```c
  eax = MEM32(0xFE820010u);          /* PIO_FREE */
  MEM32(0xFE8202F8u) = eax;          /* SET_CURRENT_VOICE */
  MEM32(0xFE820360u) = eax;          /* SET_VOICE_TAR_VOLA */
  ```

  `grep -o 'S\?MEM[0-9]*(0xFE8[0-7][0-9A-F]\{4\}u)' src/recomp/gen/*.c` finds 93 such operands, all in `recomp_0099.c`, all `MEM32`, and all of the two shapes above: `eax = MEM32(c);` (20) or `MEM32(c) = eax;` (73). No constant APU address appears in a compare, a read-modify-write or any other form. Two of the 93 (0xFE83FF10, 0xFE85FFFC) are above the trap. Burnout 3's gen has the same two shapes (18 loads, 87 stores), 9 of them above the trap. One BLiNX 2 loop (`MEM32(ebp + 8) = 0xFE820400u`, then stores through the pointer) fills HRTF/SSL tables through a register. It runs at init, so it keeps faulting.
  - The per-offset histogram cannot tell a constant-address access from one through a register at the same offset, so "all the hot ones are constant" is an inference from the gen. Task 3.2 is the check: after the change the trapped count must stay flat during play.

## Goals / Non-Goals

**Goals**
- No fault for a constant-address `mov` inside the trapped APU range in generated code, on every host.
- The APU model sees the same calls in the same order with the same values per thread, so audio is unchanged.
- No behaviour change when the range is not trapped or the model is off.

**Non-Goals**
- Other instruction forms and accesses through a register: they keep the fault path, which stays the safety net.
- The other trapped windows. The AC'97 bus-master trap (0xFEC00100) single-steps a write to clear reset bits, and OHCI needs the guest context. BLiNX 2 has 5 constant AC'97 operands, all init-time; the 5-1 trace shows no access to either window in play. NV2A is not trapped at all (plain RAM plus the ack thread), so there is nothing to gain there.
- The `VOICE_LOCK` lock wait (task 4.3 measures it and opens the follow-up).
- x86-64 POSIX audio. It stays off. The direct path would help it, but pointer accesses would still crash there.

## Decisions

1. **The lifter decides, in `_lift_mov`, at the operand.**
   - A helper `_mmio_direct_const(op)` returns the address when the operand is a memory operand with no base, index or `fs` segment and `disp` (taken as unsigned 32-bit) through `disp + size - 1` lies inside [0xFE800000, 0xFE830000). `_lift_mov` then emits `XBOX_MMIO_R<bits>(0x...u)` for a load and `XBOX_MMIO_W<bits>(0x...u, src);` for a store instead of calling `_fmt_mem_read`/`_fmt_mem_write`. The register write still goes through `_fmt_set_reg`, so `al`/`ax` destinations keep their merge.
   - The range is a lifter constant, `APU_MMIO_TRAP_LO`/`APU_MMIO_TRAP_HI`, with a comment naming `APU_TRAP_BYTES` in `xbox_memory_layout.c`. It is Xbox hardware and the toolkit's own trap size, not game data, so nothing goes in `game.toml`. The two have to agree, which the ctest pins (decision 3) and the lifter test's edge cases pin from the other side.
   - Alternatives considered:
     - (a) A textual post-pass over the emitted C: fragile against the lifter's many statement shapes.
     - (b) A range test inside `MEM32` for every access: it costs every guest load and store.
     - (c) Overriding the DirectSound functions by hand: game-specific, and it is code to maintain.
     - (d) The check in the shared `_fmt_mem_read`/`_fmt_mem_write` formatters, so every form benefits. Rejected: see decision 2.
     - The lifter is the one place that knows the address is a constant, and `mov` is the one form where one formatter call is one access.
2. **`mov` only. No read-modify-write, compare or exchange.**
   - The shared formatters are called more than once per instruction by the other forms. `_lift_alu_binop` reads the destination for the result, again for CF on `add`/`sub`, and again *after the write* in `_result_snapshot` (`_fa = MEM32(a) & mask`), so `or dword [c], 1` would become read, write, read against the model, and the flags would come from a read-back of a register that may not return what was written. `_lift_inc_dec` and `_lift_neg` re-read the same way, and `_lift_xchg` and `_lift_cmp`/`_lift_test` also go through these formatters. The decoder does one read and, for a memory destination, one write, with flags from the computed result. Routing those forms direct would change what the model sees.
   - They could be rewritten to read once into a temporary, but no title examined has such a form at a constant APU address, and the fault path stays correct for them. So the scope is `mov`, and the lifter test (task 1.2) asserts every other form at a constant APU address still emits the plain `MEMxx`. Widening the set later is a change of its own, with the read-once rewrite as its design.
3. **Runtime entry.** In `xbox_memory_layout.c` (prototypes in `xbox_memory_layout.h`, next to `xbox_VehMmioFault`, and in `recomp_types.h`, because generated code includes only that header):

   ```c
   uint32_t xbox_MmioRead(uint32_t va, int size);
   void     xbox_MmioWrite(uint32_t va, uint32_t value, int size);
   ```

   - Model path when `g_apu_mmio_trapped` is set, the offset is below `APU_TRAP_BYTES`, and `g_apu_state` is set: exactly the conditions under which the same access faults and is serviced today. It calls a new `apu_hook_direct_rd(off, size)` / `apu_hook_direct_wr(off, v, size)` in `apu_mmio_hook.c`, which wrap the existing static `apu_mmio_rd`/`apu_mmio_wr`, so the size splitting, `s_last_wval`, the `RECOMP_APU_TRACE` tallies (`s_tot_r`/`s_tot_w`, the histogram, the first-400 `[APUMMIO]` listing) and the `handler` timing are shared; the tally code is factored out of the two fault handlers rather than copied. A new counter `s_direct` reports as `direct=N` in `[APUMMIO-STATS]`. `handler=` keeps its meaning, time inside decoder and model per access, and so stays comparable before and after; after the change it is model time alone, which is what task 4.3 wants.
   - The wrappers are built on Win32 and POSIX alike: the model code is not Win32-only, only its fault half is. On x86-64 POSIX they are never reached (the range is never trapped) but they still compile.
   - Otherwise the functions do the plain volatile access through `XBOX_PTR` at the exact width the generated code would have used. When the range is trapped and the model is not up yet, that faults into the VEH, which returns 0 as it does today, and the crash report names the access; when the range is RAM (`RECOMP_AC97_READY=0`, x86-64 POSIX), the value lands in or comes from the aperture as before.
   - `g_apu_state` can go NULL at shutdown while a guest thread is mid-access. The fault path has the same window; neither closes it, and the behaviour is the same (the access falls to the plain path).
4. **The macros.** `templates/runtime/recomp_types.h` defines `XBOX_MMIO_R8/R16/R32` and `XBOX_MMIO_W8/W16/W32` as calls to the two functions, with casts to the operand width (`(uint8_t)xbox_MmioRead(a, 1)`; a store casts its value likewise).
   - A store macro expands to one statement, so it can stand where `MEM32(a) = v;` stood.
   - The signed loads (`SMEM*`, `movsx`) and `movzx` do not go through `_lift_mov`, so they keep the trap. None of the 93 operands is one.
5. **Spin-wait detection.** `spin_waits.py` matches on the basic block's instructions (loads and compares, back edge to the block start) and lowers by finding the `goto` in the lifted statements, so it never sees `MEM32` versus `XBOX_MMIO_R32` and the marker set cannot move. A `PIO_FREE` poll keeps its `RECOMP_SPIN_WAIT` call; the model returns 0x80 and the loop exits on the first pass as before. Task 1.3 confirms by counting `RECOMP_SPIN_WAIT` in `recomp_0099.c` before and after the regenerate.
6. **Ordering, locking and interrupts.** The fault path runs the model on the faulting guest thread, synchronously, at the instruction. The direct call does the same, on the same thread, at the same point. The model takes `d->lock` where it needs it (`voice_lock`), in both paths. Posted IRQs run only at explicit safe points (`xbox_IrqSafePoint`, kernel calls), never at a fault return, so interrupt delivery does not change. Under `guest_cpus=one` nothing changes about who holds the gate. The direct call runs in ordinary code rather than inside an exception handler, which removes constraints (Wine's exception dispatch, the Win32 rule against taking locks in a VEH) rather than adding any.
7. **No env key.** CLAUDE.md's opt-in rule exists so a feature cannot change stock behaviour unasked. This change does not alter behaviour: the model receives identical input and the generated code's effect on guest memory is identical, so there is no stock behaviour to preserve behind a flag. A runtime switch would need a second code path in generated code for no purpose. The A/B is the previous `gen/` built against the same runtime, and `RECOMP_AC97_READY=0` remains the ceiling reference. The merge review confirms this reading; if it disagrees, a lifter flag (`--no-mmio-direct`, emitting today's code) is the cheap escape, not a runtime key.
8. **Upstream.** The lifter change is title-agnostic and the hook code sits on top of what upstream #193 (APU) and #195 (APU diagnostics, the tallies) carry. It lands here first on `posix-host/portability`, gated on Burnout 3 under Proton (task 4.4), and is offered upstream as a follow-on PR after #193/#195 land, per the upstream-PR-round rule.

## Risks / Trade-offs

- **A missed width or sign:** a byte or word store to a 32-bit model register goes in with `size` 1 or 2, exactly as the decoder passes it today. The ctest pins all six widths and directions against the fault path's outputs.
- **Lifter range versus runtime trap size:** if one changes without the other, a `mov` either traps (slow, correct) or reaches the model for an address that is RAM today (wrong). The runtime functions gate on `APU_TRAP_BYTES` themselves, so the second case cannot happen: a direct call outside the trapped range falls to the plain access. The ctest pins 0x2FFFC as model and 0x30000 as RAM.
- **Generated-code churn:** only the in-range constant `mov` operands should change (300 sites as landed, not the first grep's 91, which missed the negative-decimal operands), and any other diff in the regenerate is a red flag for the review. Regenerating also picks up any unrelated drift between the pinned toolkit and gen/, so task 2.1 first regenerates on the base toolkit to show it is a no-op.
- **Upstream:** the lifter change touches every title, and Burnout 3's DirectSound is the same XDK library. Gate it under Proton on Burnout 3 (race start plus 5 minutes, audio on) before it goes into an upstream PR.
- **What is left:** the direct call removes the dispatch, not the model's own time. If 5-1 does not reach 30 flips/s after the change, the post-change `handler=` figure says how much of the frame the `VOICE_LOCK` wait still takes, and the follow-up starts from that number rather than from today's mixed figure.

## Measurements to record (tasks 3-4)

Before and after on the same host, script and save. The Linux/Proton host D3D11 first, then the Mac on Metal, as A/B pairs:
- 5-1 idle play: flips/s, p50 and max ms. This pair is the merge gate: it reproduces the mechanism (7,500-8,000 accesses/s) and the loss (23-28 against 30.0).
- `[APUMMIO-STATS]` reads, writes, `direct`, the trapped count and `handler` us; the trapped count must be flat after init.
- 5-1 with PAUSE, and the Mission 1-2 barrier, once their input routes exist (task 3.3). These are the tickets' symptoms and are recorded when reachable; they do not hold the merge, and BLX-77/BLX-100 stay open until they are measured.
