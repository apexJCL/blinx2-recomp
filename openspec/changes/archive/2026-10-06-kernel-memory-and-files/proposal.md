## Why

Three kernel bridges were wrong in ways that only showed up at the stage 1-1 load.

- NtFreeVirtualMemory treated its guest pointer arguments as host pointers. Every call failed: 55,891 `NtFreeVirtualMemory failed` lines in 240 s, and 5.5 MB of kernel log.
- The contiguous arena was a bump allocator, and MmFreeContiguousMemory handed contig addresses to the general heap. Stage textures were never returned, and the 64 MB arena ran out while `stg0101_tex_us` loaded (`present-frames` 6.5).
- ObReferenceObjectByHandle returned NULL for thread handles. XAPI GetExitCodeThread therefore read STILL_ACTIVE forever, and BLiNX 2 spun at 105.8 s waiting for its stage loader to exit.
- Vblank fired every 20 ms (50 Hz), because it used `now + 16` on a 10 ms timer tick.
- On POSIX, an overwrite open truncated at once, so the z: cache files were zeros.
- NtSetInformationFile had no FileRenameInformation. BLiNX 2 writes each z: cache file as `.tmp` and renames it to `.ipk`, so the cache never formed.

Status: **implemented** on toolkit `kmem/kernel-memory` (`93ab30b`, `96c0be1`, `a598ad5`, test `a4a346f`; thread objects `edf04c4`; vblank `7183207`, vblank ack `6d39c11`; duplicate tokens `3be5b39`, token lock `c1ce7c6`, logs `ebd63ad`, FATX overwrite `ea3d2f7` and `8773d89`; heap lock `55ab7d8`; thread TLS `56a5062`). Verified in 240 s runs: `analysis/bringup/kmem-fix.err` (local analysis, not published) against the baseline `kmem-base.err`, then `kmem-thobj.err` and `kmem-final.err`. Timer profile: `kmem-timer-prof-before.txt` and `kmem-timer-prof-after.txt`.

## What Changes

- NtFreeVirtualMemory reads and writes BaseAddress and FreeSize through guest pointers. It validates the type, and its logging is rate-limited.
- The contiguous arena is a locked first-fit page allocator. It honours the low/high/alignment arguments of MmAllocateContiguousMemoryEx. MmFreeContiguousMemory frees into it, and MmQueryAllocationSize answers for it.
- Thread handles lead to guest thread objects, which are signalled with their exit status when the thread ends.
- Vblank runs on an absolute 60 Hz schedule.
- FileRenameInformation renames the open file. It supports ReplaceIfExists and RootDirectory, and resolves the target through the guest path table.
- An overwrite open keeps the bytes that a following end-of-file set exposes, as FATX does (POSIX only for now).
- Handle tokens are unique for each handle (NtDuplicateObject included), and the token table is locked.
- PsCreateSystemThreadEx honours TlsDataSize. Each thread's TLS block sits under its own fs:[4], and fs:[0x28]+0x28 names it, as on the Xbox. The guest heap is locked.

## Capabilities

### New Capabilities
- `kernel-file-io`: renaming an open file.
- `kernel-threads`: thread objects, per-thread TLS, and the vblank clock.

### Modified Capabilities
- `guest-memory-layout`: the contiguous arena is reclaimed, and NtFreeVirtualMemory works in guest terms.

## Impact

- Toolkit:
  - `src/kernel/kernel_bridge.c`, `xbox_memory_layout.{c,h}`, `kernel_file.c`, `kernel.h`, `src/platform/win32_compat.{c,h}`
  - `tests/kernel_memory_bridge_posix` (24 checks)
- cat: no source change.
- Behaviour change: the z: cache (`$XDG_DATA_HOME/xboxrecomp/Cache`) now keeps finished `.ipk` files between runs, so later runs skip the rebuild.
- Not covered: NtProtectVirtualMemory and MmSetAddressProtect pass guest 4 KB ranges to the host VirtualProtect, which is a risk on 16 KB host pages. The Win32 rename path is untested. The Win32 backend still zero-fills an overwrite (task 1.14).
