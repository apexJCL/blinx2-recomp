## Context

The executor already owns surfaces, DMA resolution, the fence and the flip on both hosts (`present-frames`). The only gap between it and the title stage is that program-mode batches are dropped. The toolkit's `src/d3d/d3d8_vsh.c` parses NV2A microcode, but its back end emits HLSL for D3D11. It does not run on macOS and does not run inside the executor.

## Goals / Non-Goals

**Goals:**
- Prove that transform-unit decode is correct: program slots, constants, LOAD cursors, execution mode, viewport.
- Get one title-stage frame that matches xemu, as a BMP dump, on either host.

**Non-Goals:**
- Frame rate. The CPU path is not expected to carry a stage at 60 fps.
- Full fidelity: signed texture filtering, depth/stencil parity and the rest (`render-fidelity`).

## Decisions

### Interpreter first, backend second
The executor already owns surfaces, DMA, the fence and the flip on Proton. The interpreter proves decode correctness in about a day. The D3D11 GPU render backend (`render-gpu-backend`) is the real-time render path. Alternative considered: go straight to the GPU render backend. Rejected, because a black or wrong frame there could be a decode bug or a backend bug, and nothing would tell the two apart.

### Stopping rule
Done means: one title-stage frame (after `title_movie_1a.sfd`) matches an xemu capture of the same scene. After that, no new per-pixel feature is added to the CPU path. Work moves to `render-gpu-backend`, and the CPU path stays as the oracle for its "same frame, two paths" check. The texture stages 1-3 and the register combiners already on the branch stay, because the reference frame needs them.

### Clip space
The XDK viewport epilogue leaves oPos in surface pixels with clip w. The executor takes oPos as is, divides by w, and drops a triangle with any w <= 0. There is no near-plane clipping. That is good enough for a reference frame, and it is recorded as a known gap.

## Risks / Trade-offs

- [The ack thread gets slower, and fence timing shifts] → Reference runs are judged by dumps, not by timing. `RECOMP_PB_VSH=0` restores the old behaviour.
- [No near-plane clipping] → Triangles crossing w = 0 are dropped. That is visible as holes near the camera, and it is fixed in the GPU render backend, not here.

## Findings (macOS, toolkit 67cfdf5 + vsh branch)

- Title stage state: exec mode 0x6, no fixed-function matrices, one combiner stage (`ctl 0x11104`), final combiner = R0, stage 0 2D projective, stages 1-3 off, no fog, no alpha test, blend SRC_ALPHA with 1-SRC_ALPHA or ONE.
- `RECOMP_PB_VSH_AB=1` compares each batch against the old screen-space path in one run. Every differing batch inspected is an improvement: fade quads (oD0 = black, alpha ramp) now fade instead of drawing the texel opaque; the Sofdec/ADX logo, the title logo and "Press START" now draw where the old path drew nothing.
- Depth: the title draws its movie quad at z = 0 with LESS and depth writes on. A movie quad drawn into the other buffer without a Z clear in between is rejected (z = 0 against a stored 0). This is believed faithful to the hardware, but not yet checked against xemu.
