# Audio spike results (tasks 1.1-1.4)

Host: the Linux/Proton host, GE-Proton 11-7 (umu-run), tree `~/recomp-audio`, built from cat `audio/spec` 3c6c51c + toolkit `audio/main` d38e873 (both as dirty trees at build time; d38e873 is the committed form of the toolkit change). Every build and run held `~/.recomp-run.lock` (through `scripts/bench.sh` with `BENCH_DIR=~/recomp-audio`), each run with a fresh `XDG_DATA_HOME` (symlinks to the host's `Steam/` and `umu/` inside it so umu finds GE-Proton). Logs stay in `bench-logs/` (gitignored); only log lines and numbers are quoted here.

| Run | Stamp | Env (besides `RECOMP_AC97_READY=1 RECOMP_APU_TRACE=1 RECOMP_FLIP_LOG=1`) | Outcome |
|---|---|---|---|
| A | 20261002-205910 | `RECOMP_WATCHDOG_SECS=90 RECOMP_APU_FAULT_BENCH=100000` | killed by a decoder gap during DSOUND init |
| B | 20261002-210058 | same, with the decoder gap fixed | DSOUND init hangs on the GP doorbell; watchdog at 90 s |
| C | 20261002-210423 | `RECOMP_WATCHDOG_SECS=140 RECOMP_APU_DSP_ACK=0x80A1C810` (probe, not the fix) | boot proceeds past DSOUND init to the first logo movie; stopped by hand after ~10 s to free the run lock for a live test on the host |
| D | 20261003-010629 | `RECOMP_WATCHDOG_SECS=140 RECOMP_APU_DSP_ACK=0x80A1C810`, 150 s limit; build with the 3.3 override (cat 29b1e6c, toolkit 85c38af) | 1.4 steady state: boots through the four movies to the title; watchdog exit at 140 s as configured |
| E | 20261003-011746 | `RECOMP_WATCHDOG_SECS=90`, **no** `RECOMP_APU_DSP_ACK`, 100 s limit; cat 591c303 + toolkit 10b61a5 | 3.3 check: the override alone gets DSOUND init past the doorbell; boot reaches the title; watchdog exit at 90 s as configured |

## Toolkit changes the spike needed (`audio/main` d38e873)

- `RECOMP_APU_TRACE` statistics. The stock trace stops after 400 lines and the hook's counters were never printed, so the 1.2 counts and the 1.4 rate could not be read from a log. Now every access is tallied per offset, `[APUMMIO-STATS]` prints every 10 s and `[APUMMIO-HIST]` (per-offset r/w counts and last value written) every 30 s, from a reporter thread. `getenv` is read once instead of per access.
- `apu_hook_fault_bench` / `RECOMP_APU_FAULT_BENCH=<n>` (one call in cat `src/main.c` after `[BOOT] emulated APU up`): times n trapped reads of `PIO_FREE` through the real fault, VEH and decoder path.
- Decoder forms: `TEST r/m, imm` (F6/F7 /0), group 1 `ADD/OR/AND/SUB/XOR/CMP r/m, imm` (80/81/83), `op r, r/m` (02/03, 0A/0B, 22/23, 2A/2B, 32/33, 3A/3B), `ADD/SUB/XOR r/m, r` (00/01, 28/29, 30/31). Without them run A died (below). This front-loads the code half of task 2.5; its ctest cases are still to do.

## 1.1 Boot lines (run B)

```
  APU: 0xFE800000..0xFE880000 trapped for MMIO
  AC97: codec reported ready at 0xFEC00130 (DirectSound will initialise)
[APU] MCPX APU initialized (standalone)
[BOOT] emulated APU up
```

All four are present. Two differences from the task text: the trap line prints the end exclusively (`0xFE880000`, not `0xFE87FFFF`), and the codec line has a suffix (`(DirectSound will initialise)`). Both are the same facts.

## 1.2 Register traffic

### Decode failures

Run A, during DSOUND init:

```
[APU] MMIO decode fail at RIP=00006FFFF4671257 offset=0x2000: F7 84 06 F0 1F FE
[CRASH] Access violation at RIP=0x6FFFF4671257, fault addr=0x2467D2000 (read)
```

`F7 84 06 <disp32> <imm32>` is `test dword [rsi+rax+disp32], imm32` on `0xFE802000` (offset 0x2000), in `sub_00338939` (called from `sub_00338A31`; guest stack `0x00338A3B <- 0x00338AB7 <- 0x00334DDC`). Fixed in d38e873 (assigned to task 2.5 for its test case). Runs B and C: `fails=0`.

### Counts (run B)

```
[APUMMIO-STATS] t=10.0s reads=74 (+7/s) writes=270 (+27/s) fails=0 handler=0.72us/access
[APUMMIO-STATS] t=80.1s reads=74 (+0/s) writes=270 (+0/s) fails=0 handler=0.72us/access
```

All 344 accesses happen in the first 10 s (DSOUND init), then none: the main thread is in the doorbell spin (1.3), which touches guest RAM, not the APU. Reads: 58 of `PIO_FREE` (0x20010, always 0x80), 4 of 0x1100 (FECTL), 4 of 0x2000, 2 of 0x1004 (IEN), 2 of 0x1510, 1 each of 0x3024/0x3034/0x3044/0x3054.

### Write classes (run B, `[APUMMIO-HIST]`)

- Global/front end (0x1xxx): ISTS 0x1000 (FFFFFFFF, the clear), **IEN 0x1004 (0x00, 0xD8, then 0xD9)**, FECTL 0x1100 (last 0x100F), 0x1104-0x115C (FE limits, voice-list bases), SECTL 0x1500 group (0x1500-0x1510).
- Setup (0x2xxx): 0x2000 (0x0F), 0x2008-0x2074 (scratch/FIFO bases and limits: GPSADDR 0x2040 = 0x00A28000, GPFADDR 0x2044 = 0x00A10000, EPSADDR 0x2048 = 0x00A40000, EPFADDR 0x204C = 0x00A14000, 0x2054-0x2074 = 0xFFFF), 0x20D4 (x4, last 0x71), 0x20D8, 0x20DC, 0x20E0.
- GP/EP output FIFOs (0x3xxx, 0x4xxx): 0x3024-0x305C, 0x4024-0x403C.
- PIO methods (0x2xxxx): 0x20120-0x20140, 0x20200-0x202C0 (one write each), voice setup 0x202F8 (SET_CURRENT_VOICE, x12), 0x202FC-0x203DC, 0x20804/0x20808, 0x21000/0x21004, 0x21800/0x21808.
- **GP (0x3xxxx):** 0x3FF00, 0x3FF04, 0x3FF10 (0x03E5F605), 0x3FF14 (0xFF), 0x3FFFC GPRST (0, 1, 3).
- **EP (0x5xxxx):** 0x5FF00, 0x5FF04, 0x5FF10 (1), 0x5FF14 (0xFFFFFFFF), 0x5FF5C, 0x5FFFC EPRST (1, 1, 3).
- No access at all to GP/EP memory windows (0x30000-0x3FEFF, 0x50000-0x5FEFF). The `0xFE836000` constant in `sub_003341BE` is added to DMA descriptors the title writes to guest RAM, not an access.
- **No GP/EP register is ever read.** Nothing polls GPRST/EPRST or a GP/EP FIFO cursor.

### `[APU] started by the title`

```
[APU] started by the title (SECTL=0000000F FECTL=0000100F)
```

Present in runs B and C.

## 1.3 Decision: option 3 (cat override, user-approved)

After `started by the title`, run B stops flipping. The rendering never starts: no D3D11 flip in 90 s, `NV2A USER PUT=00001280 GET=00001280`. The watchdog names the spin:

```
[WATCHDOG] no exit after 90s; guest esp=0x038BFD24
  regs: eax=00000003 ecx=00000000 edx=AA153FE0 ebx=80A1C810 esi=80A1FB3C edi=80A297EC
```

The guest stack (`tools/stackwalk.py` over `analysis/disasm/functions.json`), innermost first: `sub_0033439F+0x7A` (return 0x00334419) <- `sub_003321FC` <- `sub_0033230E` <- `sub_00332DBD` <- `sub_0021C850` <- `sub_0021C8B0` <- `sub_00333BD1` (DirectSoundCreate path) <- ... <- title main. esp is exactly `sub_003341BE`'s frame (0x1C locals + 3 saves + ebp), so the thread is in `sub_003341BE`'s own body, at its tail:

```
MEM32(ebx) = eax;                         /* ebx = <DSP block> + 0x810, eax = 3 */
loc_00334325: if (MEM32(ebx) != 0) goto loc_00334325;
```

- **Function:** `sub_003341BE` (DSOUND, called from `sub_0033439F`). It builds a DMA descriptor list for the GP (the `+ 0xFE836000` and `- 0x17C6818` relocations), copies a command block, writes command 3 to the doorbell and spins until the GP program writes 0.
- **Address polled:** guest RAM `0x80A1C810` (contiguous memory, `ebx` in the dump; the same address in runs B and C). It lies in none of GPSADDR/GPFADDR/EPSADDR/EPFADDR (0xA28000, 0xA10000, 0xA40000, 0xA14000). It is a DSOUND allocation the GP program reads by DMA.
- **Why not option 1:** the title waits on the GP.
- **Why not option 2:** no GP/EP register is read (above). The thing waited on is a word the GP *program* writes to system RAM, so modelling a register cannot answer it. Only a DSP56300 port running the XDK's GP image, or an acknowledgement, can.
- **Probe:** with `RECOMP_APU_DSP_ACK=0x80A1C810` (run C), the line `[APU] DSP doorbell 0x80A1C810: command 0x00000003 acknowledged` appears. DSOUND init then completes: PIO programming continues past the 400-line trace cap, worker threads spawn, and the first logo movie (`movie\logo_mgs.sfd`) opens and streams. The doorbell is therefore the only gate in DSOUND init. `RECOMP_APU_DSP_ACK` stays a probe (design Decision 2); the fix is 3.3.
- **Shape of 3.3:** the wait is inline at the end of `sub_003341BE`, so there is no separate wait function to stub. The override replaces `sub_003341BE` by guest address in `src/recomp_manual.c`: the generated body, with the spin at `loc_00334325` replaced by "command completed" (the word cleared, `eax = 0`). It is recorded as the deviation "DSOUND GP command wait short-circuited". Wreckless's doorbell (documented in `apu_dsp.c`) is also at `+0x810` in its DSOUND block. That suggests the protocol belongs to XDK DSOUND, not to this title, which keeps a general toolkit acknowledgement open for later. It does not change this decision.
- **Other tight waits in DSOUND**, for the next runs to watch:
  - `test [eax], 0x100000` spins in `sub_00336EBE`, `sub_00336F07`, `sub_00336F6E` (shared `loc_00336F99`) and `sub_0033765A` (`loc_0033768E`);
  - a byte spin in `sub_00338E0D` (`loc_00338E43`).
  None of them was hit in runs B or C.

## 1.4 Fault cost

- **Per access, fault round trip:** `[APU] fault bench: 100000 trapped reads of PIO_FREE, 51.39 us each` (run B), and 53.29 us in run A. The handler itself (decode + model) is **0.72 us** of that (`handler=0.72us/access`), so about 98.6 % of the cost is the exception dispatch through Wine/Proton, not the decoder.
- **DSOUND init:** 344 accesses before the doorbell is ~18 ms; run C's longer init (>400 accesses) is under 25 ms. Not an issue.
- **Steady state (run D, 20261003-010629, cat 29b1e6c + toolkit 85c38af, env `RECOMP_AC97_READY=1 RECOMP_APU_TRACE=1 RECOMP_FLIP_LOG=1 RECOMP_APU_DSP_ACK=0x80A1C810 RECOMP_WATCHDOG_SECS=140`, 150 s limit; the watchdog ended it at 140 s, exit 3, as configured).** This build already has the 3.3 override (`[DSOUND] GP command 0x3 at doorbell 0x80A1C810 completed without a GP (short-circuited, #1)`), so the probe had nothing left to do. The boot plays `logo_mgs.sfd`, `logo_artoon.sfd`, `blinx2_opening.sfd`, then `title_movie_1a.sfd` (the title), and no input is given. `fails=0` throughout, and no `[XA2] underrun`.

  ```
  [APUMMIO-STATS] t=50.1s reads=1528 (+30/s) writes=4610 (+90/s) fails=0 handler=2.16us/access
  [APUMMIO-STATS] t=60.1s reads=1620 (+9/s) writes=4875 (+26/s) fails=0 handler=2.10us/access
  [APUMMIO-STATS] t=80.1s reads=3265 (+107/s) writes=10464 (+371/s) fails=0 handler=1.48us/access
  [APUMMIO-STATS] t=100.2s reads=5370 (+109/s) writes=17094 (+337/s) fails=0 handler=1.30us/access
  [APUMMIO-STATS] t=130.2s reads=8703 (+111/s) writes=27633 (+353/s) fails=0 handler=1.15us/access
  ```

  - Movies (10-60 s): about 120 accesses/s.
  - Plateau from 80 s to the end, after the title opened: **about 460 accesses/s** (110 reads + 350 writes). That is below the 500/s that would call for a `RECOMP_TRACE_PROFILE` run, so none was made.
  - **Cost:** 460/s x 51.4 us (run B's fault round trip; the handler's share here is 1.15 us) = **about 24 ms per second, 0.40 ms per 60 Hz video frame. That is under 1 ms, so task 4.5 is not required.**
  - Headroom: 1 ms per frame is reached at about 1150 accesses/s, 2.5 times the plateau. Gameplay (`@stage1`, with more voices and SFX) has not been measured. The phase 4 runs keep `RECOMP_APU_TRACE=1` to watch for it.
  - The run had no D3D11 flips to log, because `RECOMP_PB_BACKEND` and `RECOMP_PB_EXEC` were not in the env. NV2A vblank lines and `NV2A USER PUT=GET` advancing (`000ECC50`) show the main loop running. The `[APU] voice N pos=` lines (2.6) appear, four voices at a time.

## 3.3 check (run E)

With the `sub_003341BE` override and without `RECOMP_APU_DSP_ACK` (no `doorbell ack` line in the log):

```
[APU] started by the title (SECTL=0000000F FECTL=0000100F)
[DSOUND] GP command 0x3 at doorbell 0x80A1C810 completed without a GP (short-circuited, #1)
[APUMMIO-STATS] t=80.1s reads=3261 (+108/s) writes=10452 (+376/s) fails=0 handler=1.53us/access
  NV2A USER  PUT=0009F9E8 GET=0009F9E8
```

- `logo_mgs.sfd`, `logo_artoon.sfd`, `blinx2_opening.sfd` and `title_movie_1a.sfd` open in turn.
- vblank lines continue to the end of the run (`vblank 5400: last 600 in 10004 ms`).
- The pushbuffer advances: run B was stuck at `PUT=GET=0x1280`.
- There was only one GP command in 90 s (and in run D's 140 s).
- No `[XA2] underrun` and no decode failures.

## Limitations of this evidence

- `RECOMP_THREAD_DUMP` exists only on macOS arm64 (SIGUSR1 handler in `src/main.c`). Under Proton the only hang evidence is `RECOMP_WATCHDOG_SECS`: it reports the main guest thread's registers, guest stack and the last 16 indirect-call targets, then exits. A spin on another guest thread would not show up there. This spin was on the main thread.
- The `[APUMMIO-HIST]` value is the last value written, not a history. Values written to PIO methods are taken from the decoder, not read back.

## What changes in the plan

- **The design says DSOUND "never writes IEN". It does:** IEN = 0xD8, then 0xD9. No APU interrupt is delivered. Boot went through without one, but notification/position paths may wait on the APU DPC later. Phase 4 runs should watch for it.
- **Task 2.5:** the decoder forms are in (d38e873). What remains is their `tests/mmio_decode` cases.
- **Task 4.5 targets the wrong cost.** Caching the decode per RIP saves at most 0.72 of ~52 us. Run D puts the steady state at 0.40 ms per frame, so 4.5 is not required (1.4).
- **Phase 3:** 3.1 and 3.2 are not needed, and 3.3 is the path (above).
