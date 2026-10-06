## 1. Register

- [x] 1.1 Write one requirement per deviation from the xdk-library-hle and present-frames designs, `main.c` and the open-questions log.
- [ ] 1.2 Point the `main.c` comments at the deviations (devkit RAM, fence mirror, vblank, MOUNT_UTILITY_DRIVE) to this capability instead of the archived design.
  - Archive note (2026-10-06): open, moved to TASKS.md (point the `main.c` deviation comments at `openspec/specs/deviations/spec.md`).
- [x] 1.3 Archive this change, so that `deviations` becomes a main spec, and keep it current from then on.
  - Archive note: done by this archive. The stale facts (vblank clock, pacer epoch, NtFreeVirtualMemory, executor default, saves) were refreshed first.

## 2. Tripwires

- [ ] 2.1 Check that each "Detect" line has a matching log line in the toolkit or cat. Add the missing ones (for example, a one-time line naming a DMA object with a non-zero base).
  - Archive note: open, moved to TASKS.md.
