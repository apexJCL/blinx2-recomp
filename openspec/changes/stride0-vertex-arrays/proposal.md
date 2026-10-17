## Why

BLX-180: in SSX 3 the rider's body stops drawing partway through a race. Only the hands stay, and when the rider jumps a square sometimes stands in for the shadow. BLX-190 is the toolkit side.

The body's program, D94C1234, adds v4.xyz to the position before the bone palette (`add R2.xyz, R2.xyzz, v4.xyzz`). The game passes that v4 as a float3 vertex array with **stride 0** and a different offset per mesh (0x81001C60, …). The toolkit treats an attribute as an array only when it has both a size and a stride. So a stride-0 array fell back to the inline value, SET_VERTEX_DATA4F(4), which SSX 3 writes only for program 8F706D7F (`add R3.xyz, R9.xyzz, v4.xyzz`). Once 8F706D7F first draws, the body inherits its v4 and is thrown off screen. The planar shadow (BC25EF09) and the other skinned program (5726458F) read v4 the same way.

On the NV2A, an attribute with a size is an array whatever its stride. Stride 0 means every vertex reads the one element at the offset. Only size 0 disables the array and leaves the SET_VERTEX_DATA value. xemu follows this rule (design D1).

## What Changes

- **The CPU executor:** `vsh_inputs()` fetches any attribute with a size. `fetch_attr()` no longer refuses stride 0; at stride 0 every index reads the element at the offset.
- **Metal:** the per-input float4 expansion takes `size != 0` as on.
- **D3D11:**
  - Inputs that are neither native nor per-vertex go as one float4 at stride 0. That float4 is now the array's element when the attribute has a size, and the SET_VERTEX_DATA value only when it is disabled.
  - The `trace_batch` debug dumps follow the same rule.
- **Test:** the new `tests/pb_stride0` ctest drives a DRAW_ARRAYS quad through the CPU path with v4 as a float3 stride-0 array. It checks that every pixel takes the element, never the inline value or the next element, and that size 0 takes the inline value. It fails 5 checks under the old rule.

This is a hardware-accuracy fix and is on by default. It changes what any title draws when it uses stride-0 arrays, which is why the BLiNX 2 goldens gate it.

## Impact

- **Toolkit:** `src/kernel/nv2a_pb_exec.c`, `src/d3d/nv2a_pb_metal.m`, `src/d3d/nv2a_pb_d3d11.c`, `src/d3d/CMakeLists.txt`, `tests/pb_stride0/`.
- **Backends:** CPU, Metal and D3D11 all follow the same rule.
- **SSX 3:** the rider's body draws through the whole race (runs 39 and 40).
  - Program 86AE0156 also changes: its v7 and v8–v15 are stride-0 arrays and now read their elements, as in xemu. The pink snow tint seen in these runs is there on the old rule too, so it is not caused by this change (design D2). A before/after pair goes to the user.
- **BLiNX 2:** unknown until the goldens run. Any change stops the merge and is reported.
- **Burnout 3:** not checked now; a TASKS.md follow-up.

Worktrees:
- `wt/stride0/xboxrecomp` (`stride0/arrays`, off posix-host/portability 9ccd8e84)
- `wt/stride0/cat` (`stride0/spec`, off a392a86)
