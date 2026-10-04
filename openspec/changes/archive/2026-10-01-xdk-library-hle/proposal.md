## Why

After `recomp-coverage`, BLiNX 2 crashes on a guest worker thread in `bridge_KeWaitForSingleObject`. The call chain is `sub_002D702E` → `sub_002A1BA0` → `sub_002A1870` → `sub_002E0DB0` (D3D). The wait object is guest `0x002F3D7C`: the vertical-blank KEVENT inside D3D's static device (in D3D's `.bss`, at `MEM32(0x002F1FB8) + 0x1DBC`). The bridge has never seen this object, so it passes the raw guest pointer to the host as a handle. On macOS the shim dereferences it, which is an access violation. On Windows the wait would fail outright.

That raised the question of whether translating the statically linked XDK libraries (D3D8, DSOUND, XGRAPHC, ...) is the intended path at all.

It is. The toolkit's evidence:

- `tools/recomp --all` translates every category, XDK included.
- `translator.py` (`translate_batch_split`) says the manual set "is how a game replaces a recompiled XDK routine (a D3D8 entry point, say) with one that drives the host runtime instead of the hardware".
- `kernel_bridge.c`, in its KeConnectInterrupt note, says: "Code that *waits* on the ISR rather than polling will hang here, and the fix for that is to bridge the D3D8 entry point that owns the wait, not to synthesise NV2A interrupts."
- `docs/technical/d3d8ltcg-device-context.md` shows Burnout 3 running recompiled D3D8LTCG code, with device-context fixups and a few overridden entry points.
- `src/d3d` (D3D8 → D3D11) is a COM-vtable API layer for a project to call from its overrides. Nothing maps guest VAs to it automatically.

## What Changes

- The XDK libraries stay translated. Individual entry points that depend on hardware the host doesn't have are replaced by hand in `src/recomp_manual.c`, using the toolkit's existing mechanism.
- `scripts/pipeline.sh recomp` passes `--exclude-manual src/recomp_manual.c`. A `void sub_XXXXXXXX(void)` defined there is declared in `gen/` but not emitted, and direct callers route through `recomp_lookup_manual` and the dispatch table to the hand-written body.
- First override: `sub_002E0DB0`, `D3DDevice_BlockUntilVerticalBlank`, becomes a 60 Hz pacer.
- `src/main.c` runs with devkit RAM (128 MB). This deliberately deviates from retail; see design.md.
- `src/main.c` clears the MOUNT_UTILITY_DRIVE init flag on every host, Windows included.
- Toolkit (`hle/xdk-library`): the POSIX `SuspendThread` shim parks a thread that suspends itself instead of returning at once.

## Capabilities

### New Capabilities
- `xdk-library-hle`: how XDK library code that depends on hardware is replaced at the level of individual entry points.

### Modified Capabilities
<!-- none: recomp-coverage's section list is unchanged -->

## Impact

- **cat files:** `src/recomp_manual.c`, `scripts/pipeline.sh` (recomp stage), `src/main.c`.
- **Toolkit:** `src/platform/win32_compat.c`. This is POSIX-only code, so the Windows build is unaffected.
- **Regeneration:** a recomp is needed whenever an override is added or removed. Disasm, funcid and abi are not affected.
- **Proton:** same `gen/` tree and the same overrides. The SuspendThread fix doesn't apply there, because Windows already has real suspension.
