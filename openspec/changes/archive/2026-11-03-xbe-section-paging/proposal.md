## Why

BLiNX 1 never leaves its loading screen. The toolkit copies all 56
XBE sections into the flat guest map at boot, so the image ends at
`0x031DC780` (49.9 MB). With 64 MB of RAM, the stack shrinks to 1 MB and the
heap gets 12 MB. The heap runs out (`xbox_HeapAlloc: out of memory`), and
`NtReadFile` then fails on `3_plyrse.bin` with `STATUS_ACCESS_VIOLATION`
into the unmapped buffer.

On the console, only the sections flagged PRELOAD (11.6 MB for BLiNX 1) are
resident at boot. The other 40.6 MB are levels and models (`MDLPL`,
`MDLB1`..`MDLB10`, `MAP11`..`MAP93`, `$$XTIMAGE`). Each owns its VA but no
RAM until the title calls `XeLoadSection`, which reads it from disc.
`XeUnloadSection` gives the RAM back. Today both kernel calls only adjust the
reference count.

A 128 MB diagnostic (devkit RAM, local only) showed that memory is the first
blocker: the heap gets 69 MB, and the loads and DDS reads go through. The
next blocker is a different one: D3D's wait on the PGRAPH fence register
`0x400B10`.

## What changes

- New toolkit module `src/kernel/xbe_sections.c`: per-section bytes, and
  `XeLoadSection`/`XeUnloadSection` with the console's semantics:
  - a 0 -> 1 load copies the section in fresh and zeroes its BSS;
  - a 1 -> 0 unload drops it from the resident tally;
  - the head and tail shared-page counts follow both edges.
- Opt-in paging: the title calls `xbox_SetSectionPaging(1)`, or sets the new
  CONFIG key `RECOMP_XBE_PAGING`. With paging on, the loader:
  - registers every section;
  - copies only the preload sections;
  - runs the boot-time load on the preload sections (refcount 1);
  - grows the mapping so the heap above the whole image holds what RAM
    leaves after the preload sections.

  RAM stays 64 MB, as with `xbox_SetMapSize`.
- `bridge_XeSection` calls the module. With paging off it counts as before.
- A `tests/xbe_sections` ctest, and a `docs/env.md` row.

## Out of scope

- Enforcing the 64 MB budget. The resident tally is reported, not used as
  a limit.
- The NV2A fence wait that BLiNX 1 reaches next (a follow-up).
- Turning paging on for BLiNX 2, JSRF or Burnout 3. BLiNX 2 keeps 128 MB
  devkit RAM with every section loaded at boot (openspec `xdk-library-hle`).
- The thunk walk past the 121-entry table. It is a separate fix.
- The native `xbox_XeLoadSection` in `kernel_xbox.c`, whose struct layout
  only matches the guest's on a 32-bit host. The bridge is the live path.
