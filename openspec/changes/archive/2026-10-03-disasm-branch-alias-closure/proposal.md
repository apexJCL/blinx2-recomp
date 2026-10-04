## Why

A lone `int3` splits a function, and branches between the halves, or out of their alias ranges, landed on unresolved stubs. A stub does `esp += 4; return`, as if the guest had executed a `ret` it never ran. That corrupts esp and the callee-saved registers. In BLiNX 2 the int3 at `0x00044CFA` (a switch default) split `sub_00044900`. The display-list walk then came back with its frame still on the guest stack, and the main thread overflowed its native stack in `sub_00046720`. That overflow was first read as a scene-graph cycle (`present-frames` task 6.2).

Status: **implemented.** Merged at toolkit `fd76080` (`FunctionDetector._pass_branch_alias_closure`), regenerated, and verified in `pres-23`. Upstream draft 11.

## What Changes

- Toolkit disasm: every direct jmp/jcc out of a primary body or an alias range, whose target is a decoded instruction strictly inside another detected function, becomes an alias entry ending at that function's end. The pass iterates to a fixpoint. Targets in gaps are left to the orphan pass.
- The unresolved-stub count is a measured number in the recomp report. `RECOMP_STUB_LOG=1` logs the first run-time hit of each stub.
- BLiNX 2: 985 new aliases. The unresolved stubs drop from 994 to 81.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `recomp-coverage`: adds the branch-alias closure rule and the stub measurement rule.

## Impact

- Toolkit: `tools/disasm/functions.py`, `tests/test_branch_alias_closure.py` (`fd76080`).
- cat: a regeneration of `src/recomp/gen/`. No hand-written source changed.
- The 81 remaining stubs are not covered here. Upstream draft 08 (make every out-of-function jump target an alias at disasm time) is the general fix.
