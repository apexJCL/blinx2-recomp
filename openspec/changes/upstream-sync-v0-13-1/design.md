# Design: upstream v0.13.1 sync decisions

Toolkit shas on `sync/upstream-v0.13.1`: merge 36761e6, env edda927, KEVENT 8a37a94,
wrapped routing 6be0db5, flag joins 62bd535. cat: b5facff (main.c, env.md).

## Same problem, fixed twice

| problem | kept | why | evidence |
|---|---|---|---|
| KEVENTs a title builds without KeInitializeEvent (BLiNX 2's D3D8 vblank event) | upstream `ke_guest_event` (opt-in `RECOMP_TITLE_KEVENTS`); ours `ke_event_shadow` removed (8a37a94). cat main.c turns the switch on. | Upstream also keeps SignalState in guest memory, which XDK code resets by writing 0; ours read the header once. KeSetEventBoostPriority and KeWaitForMultipleObjects, which upstream did not cover, now use `ke_guest_event` too. | Metal goldens 8/8 CLOSE with it; every run logs `event 0x002F3D7C built by the title: host event created (notification)` and no `shadowed on first use`. |
| Contiguous memory never given back | ours: first-fit page arena, always on | Ours honours MmAllocateContiguousMemoryEx's physical range and keeps the last MB below 16 MB for range-limited requests. XDK D3D's EndVisibilityTest asks for report pages below 16 MB (0..0xFFFFFF); upstream's arena (bump, first-fit only under `RECOMP_HEAP_RECLAIM`) ignores the range, so those pages could land where the GPU's 24-bit offset cannot reach them. That failed 700-1,900 times a run in BLiNX 2 stage 1-1 (78aa03e). Ours also answers MmQueryAllocationSize for interior addresses. | 96c0be1: arena peaks at 24.9 MB with 223 frees (was exhausted at 64 MB). Goldens: no `arena exhausted`. memory_regressions ctest updated: contiguous reuse holds in every mode. |
| Guest heap unserialised | upstream SRW lock | Same fix; upstream's lock allows shared reads. Our `RECOMP_HEAP_TRACE` now wraps upstream's locked functions. | ctests memory_layout_posix, memory_regressions pass. |
| NtFreeVirtualMemory reading guest pointers as host pointers | both, in order: upstream's `guest_vmem` and `RECOMP_HEAP_RECLAIM` paths first, ours as the fallback | Upstream's fallback (switch off) still hands the guest slots to the host VirtualFree, which fails every call: 55,891 failures in 240 s of BLiNX 2 (93ab30b). Ours answers in guest terms with the switch off, so BLiNX does not need `RECOMP_HEAP_RECLAIM` (which would also move every heap address). | memory_regressions `default` mode passes the decommit check (zeroed page, neighbours kept); goldens: 0 `NtFreeVirtualMemory failed`. |
| Calls to a wrapped function (sub_X / sub_X_gen) | upstream #175 (`wrapper_name` in func_db); ours (a10f6d8, 604a77d) removed (6be0db5) | Upstream also keeps the wrapped body in the batch whatever the filters say. | Our tail-jump, guarded-icall-arm and conditional-tail tests pass unchanged on upstream's mechanism (now driven by `wrapper_name`). |
| Joins whose predecessors set flags differently | upstream per-edge evaluation + float families; our `cmp_mixed` removed (62bd535) | Per-edge also answers js/jo across compares of different widths, which cmp_mixed could not. | BLiNX 2 flag-fallback report identical with both mechanisms and with upstream alone: 1936 unique sites, 2 at joins (main: 1967 and 23). New test: mixed widths join per edge, js included. |
| Guest threads running at once (BLX-1 light-pool race) | ours: one-core pin (`guest_cpus`); upstream `RECOMP_GUEST_LOCK` stays, off | The pin makes the race as rare as on the console (a preemption between the lifted load, add and store), it does not remove it. Upstream's lock holds the CPU across guest code and drops it only in kernel calls; its own note says a guest spin-wait with no kernel call deadlocks. On BLiNX it costs speed. Ours has the Proton A/B. | Mac attract with `RECOMP_GUEST_LOCK=1`: attract-title paced at 23.1 fps vs 58.3 reference (INCOMPLETE). BLX-1: pinned 20/20 good, unpinned 3/14 bad under Proton. `RECOMP_GUEST_LOCK=1` is otherwise untested on BLiNX 2. macOS has no affinity (BLX-31); the guest lock is not a drop-in fix there. |
| XBOX_THREAD_LOCAL under MinGW | upstream's comment | Same code on both sides; only the comment differed. | n/a |

## KEVENT gate check (Fable review item 1)
Upstream's `ke_guest_event` accepts a header only when Type is 0/1 and Size is 4;
`ke_event_shadow` did not check Size. In all four Mac runs (attract, stage1, story,
attract with the guest lock) the only title-built event is 0x002F3D7C, accepted:
`event 0x002F3D7C built by the title: host event created (notification)`. Neither
0x0035F45C nor 0x00FFFDE0 appears in any log, and main's runs on the same routes
shadowed only 0x002F3D7C. No real event was refused on these routes, so the gate is
unchanged. A refused event would fall to `XBOX_TO_NATIVE` and fault on POSIX; watch the
operator's play-through and the Proton runs for that.

## Unions (both kept)
- Pseudo-handles: one helper for the by-value and PHANDLE accessors, upstream's
  `>= 0xFFFFFFF0` range.
- NtClose: our overwrite settle, then upstream's directory-context drop; the bridge goes
  through `xbox_NtClose`, so it gets both.
- Jump tables: upstream's displacement sites plus our byte tables.
- Path hook (`g_xbox_path_hook`) plus our path classifier (`xbox_path_tree`).
- pushad/popad: upstream's flag-preserving entries added beside our `cpuid`.
- `recomp_env`: upstream's four raw `getenv` switches go through the table (edda927).

## Fixes the merged tree needed
- guest_vmem's free-run scan spun forever on the POSIX shim, whose VirtualQuery reported
  free memory with RegionSize 0 (the ext-vma ctest hung on the Mac). The merge guarded the
  scan; 4e901fb fixes the shim instead (RegionSize runs to the next registered view) with
  a kernel_memory_posix check, and guest_vmem.c matches upstream again.
- Test fixtures: fake disasm sections gain `raw_size`; the flag-fallback report tests use
  a join per-edge evaluation cannot answer (a mul edge).

## RECOMP_EXT_VMA in the fork (review fix)
Upstream's opt-in tracker reserves guest [top of the mirrors, 0x7FFE0000) itself, with a
plain fixed-address reservation, only where the host reports the range free. Here it was
not free: on Windows/Proton our 4 GB placeholder window (819c96e) covers it, and on Linux
the range above the span is usually taken (mappings go top-down).
`memory_regressions_ext_vma` failed 1 of 4 under Proton and natively on Linux.
- e550a12: just before guest_vmem_init the layout releases that range: a split-off piece
  of the placeholder on Windows, the span's tail on POSIX.
- 32a2e80: on POSIX, growing the span only to 0x7FFE0000 put its end against the
  neighbouring mapping, and the contiguous window at 0x80000000 failed (error 8). With
  the switch on, the span now holds the whole 4 GB window, as the Windows placeholder
  does, and `layout_map_view`/`layout_commit_at` release each fixed window's slice.
- With the switch off nothing changes: every step is behind `ext_vma_span()` (0 unless
  `RECOMP_EXT_VMA` is set) or `g_span_whole_window` (set only there). Checked on the
  Mac: memory_regressions' default and heap-reclaim modes print the same layout lines
  as before the fix (host addresses masked; only a thread-start line moves).
- The ext-vma ctest now checks that the tracker is on and that a contiguous block is
  writable beside it. Native Linux: memory_regressions 4/4, kernel_memory_posix,
  memory_layout_posix, kernel_memory_bridge_posix pass. Proton (the Linux/Proton host, scratch tree
  ~/xbox-recomp-syncfix, toolkit 32a2e80): `blinx2 bench tests` pass (17); run by hand
  with the same toolchain and emulator, memory_regressions 4/4 (the tracker reserves
  guest 0x74000000..0x7FFE0000 at host 0x1B4B80000), kernel_events 2/2,
  kernel_regressions 1/1. Logs: runs/upstream-sync/syncfix/. Rerun at ce55bf0: the same
  (native Linux memory_regressions 4/4 and memory_layout_posix; bench tests pass; Proton
  memory_regressions 4/4, kernel_events 2/2, kernel_regressions 1/1).
- ce55bf0 (Fable review): the mirror loop no longer frees its slice when the span holds
  the whole window, so each slice is released once (by `layout_map_view`).
- The carve-outs give up the hold for a moment, so they are not atomic. On POSIX the slice is
  unmapped, then mapped with MAP_FIXED_NOREPLACE. On Windows the EXT_VMA range is
  released, and guest_vmem's plain VirtualAlloc reserves it. Another thread could take
  the gap. That would be visible: the window's map fails, or the tracker stays off. It
  would not corrupt anything. Making it atomic needs a MAP_FIXED path in the shim's
  MapViewOfFileEx (Linux) or a MEM_REPLACE_PLACEHOLDER hook in guest_vmem (Windows);
  not done, since the switch is opt-in and this is init time.
- Shutdown's span release munmaps the whole 4 GB when the span holds the window, so it
  also tears down anything guest_vmem left mapped inside (guest_vmem_shutdown runs
  first and releases its own range in any case).
- Not ours: at 128 MB (ext-vma-128) the contiguous window still fails on Linux. The
  tracker is off there (the mirrors reach past user space), so that is the stock 128 MB
  layout on Linux, unchanged by this fix.

## Gates (Mac)
- `pytest tools/recomp tools/disasm`: 656 passed.
- POSIX ctests: 34 dirs pass (memory_regressions 4/4 after the fixes above). Windows-only dirs (kernel_events,
  kernel_regressions, kernel_directory, kernel_object_paths, kernel_dispatch, mmio_decode,
  xaudio2, the d3d and input smokes) are owed under Proton.
- BLiNX regenerated (`blinx2 analyze`, `blinx2 recomp`: 26182/26190 functions, 0 failed,
  53 unresolved stubs) and built.
- cat `uv run pytest scripts` 27 passed; ruff check and format clean.
- Windows build (llvm-mingw, `blinx2 build windows`): rc 0 (kernel_path.c's
  `wcscpy_s` compiles under MinGW).
- Metal goldens 8/8 CLOSE (runs/upstream-sync/golden/r-*). The first stage1 run anchored at
  flip 752 and fell outside the default dump window (INCOMPLETE); rerun with a wider window,
  anchored at 765: CLOSE.
