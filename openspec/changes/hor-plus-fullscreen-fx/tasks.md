## 1. Probe

- [x] 1.1 Burnout 3 race route at 16:9 on Metal with `RECOMP_TRACE=aspect` (the trace line names the target's address and pitch and the stage's pitch). The speed-blur chain and the centred composite are in the proposal table (`runs/hor-plus-fx/b3/`).
- [x] 1.2 SSX 3 race at 16:9 on Metal (`runs/hor-plus-fx/ssx3/`). No stage samples a render target; the remaining centred batches are HUD and flare sprites. Its Hor+ gaps stay with native-widescreen and a follow-up.
- [ ] 1.3 JSRF Can boost: no headless route into gameplay yet (the Mac boot waits on vblank in both the stock and fixed builds). Follow-up.

## 2. Toolkit (`fix/hor-plus-fx` off `posix-host/portability`)

- [x] 2.1 `nv2a_surf_color_bytes`, `nv2a_rt_no_alpha` and `nv2a_rt_tex_reads` in `nv2a_backend_common.h`; D3D11 uses them in place of its local copies. After review: the rule matches the colour layout and memory order against the target's surface format word, and A4R4G4B4 is dropped (no surface format has it).
- [x] 2.2 Both backends: `RenderTarget.fmt` (the surface format word). Metal: `rt_texture` takes the shared rule, and a no-alpha read sets `alpha_only = 2`, which `fs_basic` now honours as D3D11's basic shader does.
- [x] 2.3 The aspect trace line gains the target address and pitch and the stage pitch, on both backends.
- [x] 2.4 `render_scale` ctest cases for the rule: every accepted layout (0x11, 0x05, 0x1C, 0x10, 0x12, 0x06), and rejections for a mismatched layout, A4R4G4B4, an unknown surface colour, either memory-order mismatch, another pitch, DXT and P8.

## 3. Gates

- [x] 3.1 Mac build, `tests/posix_ctest.sh` 0 FAIL.
- [x] 3.2 Burnout 3 16:9 Metal race: no step at the old 4:3 edges in race frames (`edges.py`).
- [x] 3.3 Metal golden (`blinx2 golden run --backend metal`) at stock: attract, stage1, story pass (bench-logs 20261022-000025-metal-attract, -000051-metal-stage1, -000210-metal-story).
- [x] 3.4 Deck D3D11 golden (`blinx2 bench golden`, Mac-built exe): attract, stage1, story pass, 0/4675 present mismatches (bench-logs 20261022-000028, -000148, -000337).
- [x] 3.6 After review (rule on the surface format word, A4R4G4B4 dropped, `fs_basic` alpha 1): ctests 93 pass, 0 FAIL; Burnout 3 16:9 Metal race, the same render-target reads, all placed as stretch (`runs/hor-plus-fx/b3/*review-169`); Metal golden pass (bench-logs 20261022-013759-metal-attract, -013825-metal-stage1, -013944-metal-story); Deck D3D11 golden pass, 0 present mismatches (bench-logs 20261022-014857, -015101, -015435).
- [x] 3.7 `[aspect.rt-reject]` trace (once per distinct pair) on both backends; Deck D3D11 at stock, 0 rejected reads: Burnout 3 race (bench-logs 20261022-020707, rtt reads every flip), JSRF boot (20261022-022032; Mac-built exe on a fresh gen). Known gaps in the proposal.
- [ ] 3.5 Native D3D11 on the PC: Burnout 3 race at 16:9, installed build (before) against the packaged fix (after). Staged in D:\bench\hor-plus-fx-bench (README.txt); waiting on the PC lock. A no-regression check of the shared rule on D3D11; the fix itself changes only Metal's picture.
