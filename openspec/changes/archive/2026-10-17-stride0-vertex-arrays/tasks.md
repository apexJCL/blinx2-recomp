Worktrees: `wt/stride0/xboxrecomp` (`stride0/arrays` off posix-host/portability 9ccd8e84) and `wt/stride0/cat` (`stride0/spec` off a392a86). The tracker item.

Gates (orchestrator, 2026-10-17): posix_ctest and a MinGW build; BLiNX 2 goldens on Metal and on D3D11 (Deck, through the orchestrator); SSX 3 on Metal and D3D11. Any BLiNX 2 golden change stops the merge and is reported. Burnout 3 is a follow-up.

## 1. Toolkit

- [x] 1.1 `nv2a_pb_exec.c`: `vsh_inputs()` and `fetch_attr()` take size > 0 as an array, stride 0 included (D3).
- [x] 1.2 `nv2a_pb_metal.m`: `on = a->size != 0`.
- [x] 1.3 `nv2a_pb_d3d11.c`: the stride-0 float4 takes the fetched element; the `trace_batch` dumps follow.
- [x] 1.4 `tests/pb_stride0`: the CPU-path ctest; it fails 5 checks under the old rule.
- [x] 1.5 Mac build; `tests/posix_ctest.sh` 0 FAIL; MinGW cross-build.

## 2. Cat

- [x] 2.1 TASKS.md: the xemu inline-value update and Burnout 3 as follow-ups (D4).
- [x] 2.2 `uv run pytest scripts`; `uv run ruff check . && uv run ruff format --check .`.

## 3. Check

- [x] 3.1 BLiNX 2 goldens on Metal.
- [x] 3.2 BLiNX 2 goldens on D3D11 under Proton (Deck, through the orchestrator).
- [x] 3.3 SSX 3 on Metal: the body draws through the race.
- [x] 3.4 SSX 3 on D3D11 under Proton.
- [x] 3.5 Review: no bugs; the nits are fixed on the branch or recorded as follow-ups (D4).
- [x] 3.6 A before/after pair of the snow for the user (D2): `runs/ssx3/snow-ab-ITEM.jpg`, run42 (old rule) against run41 (fix).

## Evidence

- Gates: Mac BLiNX 2 and SSX 3 builds OK; MinGW (llvm-mingw) toolkit build and the BLiNX 2 and SSX 3 cross-builds OK; `tests/posix_ctest.sh` 76 pass, 0 FAIL (`pb_stride0` included); cat pytest 61 passed, 1 skipped; ruff clean.
- BLiNX 2 Metal goldens: attract, stage1 and story pass, every check CLOSE (`bench-logs/20261017-001451-metal-attract`, `-001518-metal-stage1`, `-001637-metal-story`). The verdicts match the 20261016-0757 baseline; story-menu's mae 1.255/0.995/0.849 is one of its two usual values.
- SSX 3 Metal run41 (`runs/ssx3/run41/`, toolkit 371f5100, flips 4600–7000 every 100): the body draws in all 25 frames and the shadows look right. Run42 (old rule, the same frames): the body is off screen throughout.
- BLiNX 2 D3D11 goldens under Proton (Deck, exe sha256 4c96dffe…, toolkit 371f5100): attract, stage1 and story pass, every check CLOSE; story-hub pace 30.0 fps against 29.6/29.9. The Proton toolkit ctests that `bench golden` runs first all failed with "proton_run: no exit code", for a host reason unrelated to this change: inside the `xbr-build` distrobox, bwrap cannot bind-mount `/etc/resolv.conf`, since the box's copy is a bind of the host file that was replaced on 2026-10-16 (link count 0). `umu-run` on the host itself runs fine. Restarting the box should clear it; the tests need a rerun after that.
- SSX 3 D3D11 under Proton (`runs/ssx3/s0d1/`, the Deck, run24 save and pad script, `RECOMP_PB_BACKEND=d3d11`): the body draws in every race frame from 1:08 to 3:00 (`sheet.jpg`), with a proper shadow and no square; no crash.
