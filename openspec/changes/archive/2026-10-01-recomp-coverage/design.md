## Context

The toolkit's disassembler picks sections in one of two ways. `--text-only` sweeps `.text` alone. Without it, the disassembler sweeps every executable-flagged section except the conventional PE data names. The Xbox linker marks nearly every section executable. In BLiNX 2 that includes about 60 model and motion data sections (DOLBY through MOTP0, ~30 MB), so dropping `--text-only` would turn data into phantom functions. `--extra-sections` adds named sections on top of `--text-only`.

Byte checks on this XBE:
- **Code:** the 12 library sections each start with x86 prologues, or contain the unresolved targets.
- **Data:** DOLBY, DATADV, G3, DSKERDAT and COMTNK.

## Decisions

1. **`--text-only` plus an explicit `--extra-sections` list**, kept in `pipeline.sh` as a game setting. An explicit list is predictable and easy to review, where a code-likeness heuristic is not. A future title with different library sections edits one variable.
2. **The seed list lives at `config/seed_functions.json`**, not under `analysis/`. It's hand-maintained source: the bench syncs it, and it survives `analysis/` being regenerated. Every entry records where it was measured.
3. **Seeding `0x002D702E` deliberately clamps `sub_002D7024`.** The toolkit warns that seeds inside a function clamp its end. Here that's the right result: the `int3` after the non-returning call is the real end.
4. **Growing coverage uses the toolkit's `icall_feedback` loop** (`RECOMP_ICALL_FEEDBACK`). Its database, `tools/recomp/output/icall_targets.json`, is passed as a second `--seed-functions` file once it exists, and is never merged into the hand list.

## Risks

- **New code paths.** Library sections translated for the first time may expose lifter gaps, such as unusual instructions in D3D or DSOUND code.
- **Function ends.** The non-returning-call merge may happen elsewhere and go unnoticed. The feedback loop is how those get found.

## Result (task 2.2, 2026-10-01)

- **Disasm/recomp.** 25,258 functions detected (.text 21,160; library sections 4,098; none in DOLBY or later). Recomp translated 25,283 bodies with 0 failures into 102 files. The build is clean.
- **Boot** (`analysis/bringup/coverage-1.{out,err}` (local analysis, not published)). All 23 original targets resolve. Two new unresolved ICALL targets remain, both in XPP: `0x003674FA` and `0x00366CBC`. They are candidates for the next seed or feedback round.
- **Exit 139** on guest worker thread 4: `[CRASH] Access violation ... fault addr=0x2F3D84`. The stack is `WaitForSingleObject ← xbox_KeWaitForSingleObject ← bridge_KeWaitForSingleObject ← sub_002E0DB0 (D3D) ← sub_002A1BA0 ← sub_002D702E`. The newly translated D3D code waits on a KEVENT at `0x002F3D7C` that lives in guest memory and never went through the bridged `KeInitializeEvent` or `KeInitializeSemaphore`. As a result, `ke_shadow_lookup` misses, and the fallback hands a guest pointer to the Win32 wait shim as a HANDLE.
- **Side effect.** 482 `.text` `tail_jump_alias` entries disappeared once the extra sections were added (seeds alone lose none). 476 now fall inside another function. No direct jump targets them, but 43 are referenced as immediates from library code, so they could be icall targets.
- **Not re-run.** `funcid` and `abi` still describe the pre-coverage function set. ABI only feeds comments, and with no category filter every function is translated, so the impact should be small. Re-run both before the next recomp anyway.

## Next blocker

Guest-resident dispatcher objects in the Ke* wait bridges. There are two candidate fixes:
- **(a) Toolkit change** in `src/kernel/kernel_bridge.c`. On a shadow miss, read the guest `DISPATCHER_HEADER` (Type, SignalState) and create a shadow on first use.
- **(b) Replace the XDK D3D library code** (D3D section) with the toolkit's d3d8 layer instead of translating it. This is unverified: it needs a check of how the toolkit expects D3D to be hooked.
