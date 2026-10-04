## 1. Interpreter (toolkit, `vsh/vertex-programs`)

- [x] 1.1 `nv2a_vsh_cpu`: 136 slots, 192 constants, MAC and ILU ops, decoded after xemu's `vsh.c` field table. Tests in `tests/nv2a_vsh` (viewport epilogue, ARL-relative reads, negate, swizzle). Commit `b9a48d2`, not merged.
- [x] 1.2 Executor: capture transform-unit state, run program-mode batches, texture stages 0-3, register combiners. `RECOMP_PB_VSH=0` and `RECOMP_PB_VSH_AB` switches. Commit `df3a7d7`, not merged.
- [x] 1.3 Blending: every GL factor pair with ADD (the loading screen's additive glows were black squares). Commit `5187d75`, not merged. Debug aids: `RECOMP_VSH_TRACE`, `RECOMP_VSH_DUMP`, `RECOMP_VSH_ZLOG`, `RECOMP_PB_VSH_AB_DUMP`.

## 2. Reference frame

- [x] 2.1 Boot to the title stage on macOS with `RECOMP_PB_EXEC=1 RECOMP_FB_DUMP=...`. Check that the report shows no program-mode batch skipped as "not screen-space". Done on toolkit 67cfdf5: title screen (logo, copyright, "Press START") and the "Now loading..." screen render; every program-mode batch goes through the interpreter. Only 2D programs run before 240 s on macOS: two XDK pretransformed passthroughs (5474DB2A, B2913952) and two 1-batch runs of a 94-slot lit program on a full-screen quad. No real 3D is reachable locally yet (stage load stalls).
- [ ] 2.2 Capture the same scene in xemu and compare. Record the frame, the differences and their causes in design.md.
- [ ] 2.3 Repeat on Proton through `scripts/bench.sh`.

## 3. Close

- [ ] 3.1 Merge `vsh/vertex-programs` into the integration toolkit and regenerate if needed.
- [ ] 3.2 Apply the stopping rule: move any open per-pixel work to `render-gpu-backend` or `render-fidelity`, and close `present-frames` task 6.3.
