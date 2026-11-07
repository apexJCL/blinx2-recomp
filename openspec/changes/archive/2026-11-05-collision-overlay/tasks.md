## 1. Toolkit

- [x] 1.1 `src/kernel/nv2a_dbg_draw.{c,h}`: segments, clip transform, pull, triple buffer (D3, D4).
- [x] 1.2 Mod API v8 in `mod.h`/`mod.c`: `draw3d_begin`, `draw3d_tris`, `draw3d_lines`, `draw3d_end`.
- [x] 1.3 D3D11 draw at the flip (D2).
- [x] 1.4 Metal draw at the flip (D2).
- [x] 1.5 ctest `tests/dbg_draw`: transform, segments, flags, hand-off, the API through `enhance_mod`.
- [x] 1.6 Docs: `docs/runtime/config.md` or the mod API notes.

## 2. cat

- [x] 2.1 `src/collision_logic.{c,h}`: flatness, sliver, crease edges, octree walk on bytes (pure, tested).
- [x] 2.2 `src/collision_mod.c`: descriptor, controls, draw, contact (D7–D10).
- [x] 2.3 Glue: `sub_0021B1F0` and `sub_000292A0` (game camera) wrappers, mods table, CMake, env row, `docs/env.md`, `game.toml` stock value.
- [x] 2.4 `scripts/test_collision_overlay.py`.
- [x] 2.5 TASKS.md: the CPU gap, the one-frame lag.

## 3. Gates and verification

- [x] 3.1 Mac build, posix ctest, cat pytest and ruff.
- [x] 3.2 build-all with the toolkit worktree: 6/6 pass (BLiNX 2, BLiNX 1, KUF; macOS and
  Windows on the PC) on toolkit a58aed4f, again after the rebase on toolkit 69b4bbd0 (cat main c6d10b52).
- [x] 3.3 Goldens with the mod off: Metal (Mac) attract, stage1, story pass; D3D11 (PC
  native) attract pass-with-known, stage1 pass, story pass-with-known. The same verdicts after the rebase (cat 6ed1fc8a, toolkit 69b4bbd0).
- [x] 3.4 Stage 2-1 (M23) with the mod on, Metal and D3D11: the funnel by the hole, framed
  with the free camera (flatness opaque, flatness with edges see-through, x-ray; the
  contact sphere in the funnel). The two backends match. The shots are listed. After the rebase, flatness with edges matches again on both backends, and under Hor+ (16:9) on Metal the overlay stays on the geometry.
