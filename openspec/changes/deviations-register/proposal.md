## Why

The port deviates from hardware on purpose in several places, and each deviation is recorded only in prose: in `main.c` comments, in three `design.md` files (one of them now archived) and in the project's open-questions log. Nothing says which deviations are temporary, what retail does instead, what would show that a deviation is causing a bug, or what evidence would retire it. Some of them are inferences from one data point (PGRAPH `0x400B10`, DMA base 0), and each one has a log line that would show a violation. The next agent who sees that line won't know it is a tripwire unless it is written down in one place.

## What Changes

- Add one capability, `deviations`, with one requirement per deliberate deviation. Each one states what we do, why, the risk, how to detect that it matters, and the exit criterion that retires it.
- The initial entries:
  - devkit 128 MB RAM;
  - `RECOMP_VBLANK` forced on;
  - the 60 Hz BlockUntilVerticalBlank pacer override;
  - the fence-mirror fallback;
  - lazy KEVENT shadowing;
  - the MOUNT_UTILITY_DRIVE handling (Z: is a host cache directory);
  - the inferred PGRAPH `0x400B10` bits and DMA base 0;
  - the POSIX span capped below the contiguous window.
- From here on, adding or retiring a deviation means editing this spec, through a change, in the same commit as the code.

## Capabilities

### New Capabilities
- `deviations`: the register of deliberate deviations from hardware, each with its reason, risk, detection and exit criterion.

### Modified Capabilities
<!-- none -->

## Impact

- No code changes. `src/main.c` comments that describe a deviation will point here.
- Sources: `openspec/changes/archive/2026-10-01-xdk-library-hle/design.md` (Decisions, Risks), `present-frames/design.md` (fence handover, `0x400B10`), the open-questions log (devkit RAM watch, fence mirror, Proton running with `RECOMP_VBLANK=1`), and the 2026-10-01 design review of the presentation path.
