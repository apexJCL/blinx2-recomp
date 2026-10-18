## 0. Spec review
- [x] 0.1 The reviewer reads and improves this spec (written by the agent). Implementation starts from the revised version (this one: `mov` only, the 0x30000 trap range, the runtime gate on the trap, the follow-up made firm).

## 1. Toolkit (worktree `wt/perf/xboxrecomp`, branch `fix/perf-events` off posix-host/portability e629c35)
- [x] 1.1 `tools/recomp/lifter.py`: `APU_MMIO_TRAP_LO`/`APU_MMIO_TRAP_HI` (0xFE800000, 0xFE830000; comment names `APU_TRAP_BYTES`), `_mmio_direct_const(op)` (no base, index or `fs`; `disp` as unsigned 32-bit; `disp + size - 1` inside the range), and the two emission arms in `_lift_mov`. `_fmt_mem_read`/`_fmt_mem_write` are untouched.
- [x] 1.2 Lifter test `tools/recomp/test_lifter_mmio_direct.py`:
  - direct: `mov eax, [c]`, `mov [c], eax`, `mov [c], imm32`, `mov al, [c]`/`mov [c], al`, `mov ax, [c]`/`mov [c], ax` emit `XBOX_MMIO_R/W8/16/32`; the `al`/`ax` loads still go through the register merge;
  - still `MEMxx`: `or dword [c], 1`, `add [c], eax`, `cmp [c], 0`, `test dword [c], 0x80`, `inc dword [c]`, `xchg [c], eax`, `lock xadd [c], eax`, `movzx eax, byte [c]`, `push dword [c]`, `mov eax, [eax + c]`, `mov eax, fs:[c]`;
  - edges: 0xFE7FFFFC (out), 0xFE800000 (in), 0xFE82FFFC (in), a dword at 0xFE82FFFE (straddles the trap end: out), 0xFE830000 (out, the DSP memories), 0xFE85FFFC (out).
- [x] 1.3 `pytest tools/recomp tools/disasm` passes. After task 2.1, `grep -c RECOMP_SPIN_WAIT` on `recomp_0099.c` is the same before and after (the pass matches instructions, so this is a confirmation, not a search).
- [x] 1.4 `templates/runtime/recomp_types.h`: the `XBOX_MMIO_R8/16/32` and `XBOX_MMIO_W8/16/32` macros and the two prototypes, beside `g_xbox_mem_offset`.
- [x] 1.5 `src/kernel/xbox_memory_layout.{c,h}`: `xbox_MmioRead`/`xbox_MmioWrite`, gated on `g_apu_mmio_trapped`, `off < APU_TRAP_BYTES` and `g_apu_state`, else the plain volatile access at the given width. `src/apu/apu_mmio_hook.c`: `apu_hook_direct_rd`/`_wr` sharing `apu_mmio_rd`/`_wr`, the tallies, the first-400 listing and the `handler` timing on all hosts (factor the tally code out of the two fault handlers), with `direct=N` in `[APUMMIO-STATS]`.
- [x] 1.6 ctest `tests/mmio_direct` (standalone project, links the runtime as `tests/apu_irq` does). As landed it is arm64 POSIX only and tests against the model (x86-64 POSIX and Win32 configure-refuse and report n/a); the Win32 direct path is covered by the Proton bench runs (fails=0). Planned scope: widths 1, 2 and 4, read and write, against a model stub recording (offset, size, value), compared with what `mmio_emulate` passes for the same `mov`; offset 0x2FFFC reaches the model and 0x30000 lands in the aperture as RAM; with `g_apu_state` NULL or the range untrapped, the access is the plain one; with the trace on, `direct` counts and `reads`/`writes` include the direct accesses.

## 2. cat (worktree `wt/perf/cat`, branch `fix/perf-events`)
- [x] 2.1 Regenerate on the base toolkit first to show gen/ has no drift. Then repoint `external/xboxrecomp` to the branch and run `blinx2 analyze` then `blinx2 recomp`. Review the diff whole: only the in-range constant `mov` operands change: 300 sites at 115 addresses (47 `XBOX_MMIO_R32`, 253 `XBOX_MMIO_W32`), not 91, because the first grep looked for `0xFE8` hex and missed the operands printed as negative decimals (`MEM32(-25157620)` is 0xFE80200C); the two above the trap (0xFE83FF10, 0xFE85FFFC) and the five AC'97 operands stay `MEM32`.
- [x] 2.2 `docs/env.md`: the `RECOMP_APU_TRACE` row names the `direct=` field.

## 3. Measure (raw runs in `runs/perf/`)
- [x] 3.1 the Linux/Proton host D3D11, 5-1 idle play (`runs/perf/scripts/st5-idle.txt`, `RECOMP_SAVE_DIR=@run`), before and after: flips/s, p50 and max. Before: 23-28 flips/s, p50 36-45 ms (bench-logs 20261011-215249). Reference ceiling: 30.0 flips/s with `RECOMP_AC97_READY=0` (20261011-221209). This pair is the merge gate.
- [x] 3.2 The same with `RECOMP_APU_TRACE=1`: `direct` is about 7,500/s and the trapped count is flat after init. If it still rises in play, the `[APUMMIO-HIST]` offsets that rise name the accesses made through a register; record them as a follow-up, they are out of this change's scope.
- [ ] 3.3 (follow-up, not done in this change: neither input route works yet) PAUSE in 5-1 and the Mission 1-2 barrier: still need input routes (see `wt/perf/NOTES.md`; time controls appear to need collected crystals, and 1-2 needs a cleared 1-1: poke 0xB871B0=2 at stage init, or LOAD GAME from the seed save). Once routes exist, record before and after on the Linux/Proton host D3D11 and the Mac on Metal. Best effort before the merge; otherwise a tracker follow-up, which stay open until measured.
- [x] 3.4 Mac Metal A/B pair on 5-1 idle, with `SDL_AUDIODRIVER=dummy` under `notes/mac-run-lock.sh`: flips/s and `[APUMMIO-STATS]` (the SIGBUS round trip saved per access).

## 4. Gates
- [x] 4.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`), `tests/posix_ctest.sh` with 0 FAIL, `pytest tools/recomp tools/disasm`, cat `uv run pytest scripts`, ruff.
- [x] 4.2 Metal goldens. Then on the Linux/Proton host, `blinx2 bench golden` and `blinx2 bench tests`. (No GPU path changes, so "backends agree" is satisfied by both goldens passing.)
- [x] 4.3 Record the post-change `handler=` us/access in 5-1 (now model time alone) times accesses per frame. Open the follow-up change (shorten the APU frame thread's hold of `d->lock`, `apu_core.c` frame loop) with that number, unless it is under 1 ms per frame. Measured: 3.2 ms per frame, so the follow-up is warranted.
- [x] 4.4 Burnout 3 under Proton on the exact head, regenerated with the same toolkit: boot, race start plus 5 minutes, audio on; the 9 constant operands above the trap stay `MEM32`.
- [x] 4.5 Merge review, including decision 7 (no env key).
