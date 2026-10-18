Worktrees: `wt/khfix/cat` (branch `spec/kh-gpu-rules` off cat `main` 0860f81) and `wt/khfix/xboxrecomp` (branch `fix/kh-gpu-rules` off `posix-host/portability` 70c43712). Burnout 3: `wt/khfix/b3`, detached at b3 4c85e50, against an APFS clone of the dump. Raw runs go to `xbox-recomp/runs/khfix/`. No review pass (the user, 2026-10-15).

## 1. Toolkit

- [x] 1.1 Near clip: `clip_tri` and `clip_inside_all` per D2, and `tests/pb_clip_border` (near section), registered in `src/d3d/CMakeLists.txt` under `if(NOT WIN32)`.
- [x] 1.2 Clear rect: `nv2a_clear_box` per D1. Update `clear_surface`'s extent and write check, and the comments in the backends and `nv2a_pb_state.h`. Add the smoke-test rect case, and make the clip case set the rect to the clip.
- [x] 1.3 Border colour: decode, D3D11, Metal and CPU per D3, with the border tests in `pb_clip_border` and both backend smokes.
- [x] 1.4 One commit per fix, `area: what changed`. The bodies credit upstream #211 and #212 for the rules (not the code).

## 2. Gates

- [x] 2.1 Mac build (CommandLineTools) and `tests/posix_ctest.sh` with 0 FAIL. Each commit builds and passes its tests on its own.
- [x] 2.2 `d3d11_backend_smoke` and `d3d8_hlsl_split`, Mac-built, under Proton on the Deck.
- [x] 2.3 BLiNX 2 goldens: Metal (`blinx2 golden run`) and D3D11 (`blinx2 bench golden` on the Deck, with the Mac-built exe).
- [x] 2.4 Burnout 3 frame A/B, base against branch, on Metal and Deck D3D11. Every changed frame is explained by border sampling. Result: the frame diffs come from timing alone. A diag build shows border sampling only in the race bloom downsample chain (640x480 to 320x240 to 160x120, stages 0-3, colour 0), so the change is limited to taps past the bloom buffers' edges. Race frames are clean on both backends.
- [x] 2.5 Flips/s base against branch on Metal and D3D11, within the CLAUDE.md thresholds. Result: Metal race gate 55.1 to 53.6 race flips/s (-3%). Deck D3D11 race frame mean 17.05 to 17.09 ms.

## 3. Merge (orchestrator)

- [ ] 3.1 Review. Its fixes go back to the branch agent.
- [ ] 3.2 Squash-merge into `posix-host/portability`, then the post-merge steps from CLAUDE.md (Deck golden in place of the Linux/Proton host while it is offline).
- [ ] 3.3 TASKS follow-ups:
  - CPU mirror (mode 2), used on Burnout 3's stage 0.
  - Metal border colours other than its three presets (today: clamp plus one log line).
  - BORDER with the texture as the source (today: clamp-to-edge, since texture border texels are not decoded).
  - GPU targets sized by the clip can cut short a swizzled clear rect that reaches past the clip (grow the target to the swizzled size on a clear).
  - The CPU screen-space path clamps negative coordinates under wrap to 0 (an older issue, seen while adding border).
  - RT-sourced stages apply border/clamp at the host target's edge (rt_grow, or the self copy), not the guest texture's. Also, the forced alpha of X8R8G8B8 and R5G6B5 makes a transparent border opaque.
  - Track SET_ZMIN_MAX_CONTROL (0x1D78) ZCLAMP_EN. Then decide whether the CPU path culls at the far plane with depth off, as the GPU paths do.
  - iPadOS: check ClampToBorderColor / borderColor availability per GPU family.
