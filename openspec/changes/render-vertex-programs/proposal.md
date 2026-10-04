## Why

The pushbuffer executor (`present-frames`) draws clears and screen-space batches, which is enough for the Sofdec movies. Once the title stage starts, every 3D batch is skipped as "not screen-space": 86,319 skipped in run `20261001-213616`, and the frames after the movie are black. The title runs vertex programs (about 2.5 M transform-program calls in the unhandled ranking). Until they run, nothing says whether the stage geometry comes out where it should.

A CPU interpreter answers that without a GPU render backend, on both hosts, in days. It is not the renderer: 1.14 G pixels were already rasterised on the CPU in run 213616 with 3D off, on the NV2A ack thread.

Status: **in progress** in `wt/vsh` (branch `vsh/vertex-programs`).

## What Changes

- Toolkit: `nv2a_vsh_cpu`, a portable NV2A vertex-program interpreter (136 instruction slots, 192 constants, all MAC and ILU ops, decoded after xemu's `vsh.c` field table). It outputs oPos, oD0/oD1, oFog, oPts, oB0/oB1 and oT0..3.
- Toolkit: the executor captures transform-unit state from the stream and runs program-mode batches through the interpreter. It then rasterises them with the existing surface model. Fixed-function batches keep the screen-space path.
- `RECOMP_PB_VSH=0` turns the path off. `RECOMP_PB_VSH_AB` draws program-mode batches both ways, for A/B comparison.
- **Stopping rule (decision):** the CPU path is a correctness reference. Once one title-stage frame matches an xemu capture, new per-pixel and per-vertex features go to `render-gpu-backend`. The CPU path is then kept only to produce reference dumps.

## Capabilities

### New Capabilities
- `pushbuffer-executor`: how the executor decodes transform-unit state and transforms program-mode batches. It may be folded together with `present-frames` when both are archived.

### Modified Capabilities
<!-- none -->

## Impact

- Toolkit (`vsh/vertex-programs`): `src/nv2a/nv2a_vsh_cpu.c`, `src/kernel/nv2a_pb_exec.c`, `tests/nv2a_vsh`.
- cat: none, apart from bench env lines.
- Performance: worse on the ack thread, by design. Speed is not measured on this path (see `bench-methodology`).
