## 1. Investigation

- [x] 1.1 Re-run funcid and abi after the coverage disasm (25,258 functions, 1,183 thiscall)
- [x] 1.2 Establish how the toolkit expects XDK libraries to be handled (proposal.md, "Why")
- [x] 1.3 Identify the crashing wait: `sub_002E0DB0` = D3DDevice_BlockUntilVerticalBlank on the vblank KEVENT at device + 0x1DBC

## 2. Override mechanism

- [x] 2.1 `pipeline.sh recomp` passes `--exclude-manual src/recomp_manual.c`
- [x] 2.2 `recomp_manual.c` includes `gen/recomp_types.h` (its registers are thread-local; the template's plain `extern uint32_t g_eax` named a different object)
- [x] 2.3 Override `sub_002E0DB0` as a 60 Hz pacer; compiles for macOS arm64 and llvm-mingw x86_64
- [x] 2.4 Regenerate and boot on macOS: no crash, runs to the 120 s alarm (`analysis/bringup/hle-1` (local analysis, not published))

## 3. Follow-ups found at boot

- [x] 3.1 POSIX SuspendThread parks a self-suspending thread (toolkit `hle/xdk-library`)
- [x] 3.2 Devkit RAM in main.c, documented as a deliberate deviation (design.md)
- [x] 3.3 MOUNT_UTILITY_DRIVE cleared on every host
- [x] 3.4 Boot on Proton through the bench after merge (fence mirror, vblank and seeds included). Done by Proton run 3 (`bench-logs/20261001-211249`): fence mirror registered then handed over to the executor, `RECOMP_VBLANK=1` with the ISR claiming vblank, seeded build; 240 s with no `[CRASH]` and no unresolved ICALL.
- [x] 3.5 macOS at 128 MB: the contiguous window at 0x80000000 fails to map (error 8). The POSIX span reservation is still sized for 28 mirrors, so it covers the window. Skipping the overlapping mirror doesn't help. Capping the span below 0x80000000 fixed it in a local test (hle-4). Fixed by toolkit 05718f8 (POSIX span capped below `XBOX_CONTIG_BASE`); hle-6 maps the window at 128 MB.
- [x] 3.6 Post-archive idle on macOS. There were two waits:
  - The D3D fence spin in `sub_002E8110`. Fixed by the fence mirror in main.c (hle-9).
  - The main loop waiting on the vblank-callback frame counter. Fixed by RECOMP_VBLANK on by default plus the lazy KEVENT shadow, toolkit `0e948f5` (hle-11).

  Found with a SIGUSR1 all-thread dump (`RECOMP_THREAD_DUMP=1`, main.c), because `sample` and lldb both hang on attach. The toolkit stub log (`RECOMP_STUB_LOG=1`, `e58efcf`) showed that none of the 998 unresolved stubs are reached.
- [x] 3.7 Seed the indirect-only entry points (`config/seed_functions.json`). Four came from ICALL failures: PSFD_I `0x0033A340`, PSFD_P `0x0033B040`, XPP `0x00366CBC` and `0x003674FA`. A scan of `gen/` found 20 more: code-range immediates stored to memory at addresses after int3/ret padding, among them the decoder callback `0x002D0450` (hle-13). hle-14 ran 240 s with no unresolved ICALL and no crash.
