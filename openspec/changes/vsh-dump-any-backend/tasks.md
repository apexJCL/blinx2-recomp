Worktrees: `wt/vsh-trigger/xboxrecomp` (`vsh-dump/any-backend` off toolkit c497da56) and `wt/vsh-trigger/cat` (`vsh-dump/trigger-doc` off cat 9a61cab). BLX-183.

Gates (orchestrator, 2026-10-17): posix_ctest plus a MinGW cross-build. Mac builds go under `lockf -t 3600 ~/.recomp-mac.lock`, and BLiNX's BLX-15 goes first. The SSX 3 Metal run that checks it is BLX-180's.

## 1. Toolkit

- [x] 1.1 `nv2a_pb_exec.c`: call `vsh_note_program()` from `draw_primitive()` on GPU backends when `vsh_dump` or the `vsh` trace is set (D1); `VSH_MAX_PROGS` 256 and the line printed once when the table is full.
- [x] 1.2 `src/kernel/nv2a_fb_ring.{c,h}`: the ring and `nv2a_fb_trigger_range` (D2); `tests/nv2a_fb_ring` ctest.
- [x] 1.3 `nv2a_pb_exec.c`: the trigger (`fb_dump_prog*`), the ring fill in `dump_at_flip`, the dynamic range in `nv2a_pb_dump_at_listed`, and the log lines (D2).
- [x] 1.4 `nv2a_pb_exec.c`: `fb_dump_at` takes 256 ranges and warns when the list is truncated (D3).
- [x] 1.5 `recomp_env.h`: rows for `FB_DUMP_PROG`, `FB_DUMP_PROG_BEFORE` and `FB_DUMP_PROG_AFTER`; `fb_dump_prog` in `s_comma_keys`; the `vsh_dump` and `fb_dump_at` help strings.
- [x] 1.6 Mac build; `tests/posix_ctest.sh` 0 FAIL; MinGW cross-build (llvm-mingw) of the toolkit and the new ctest.

## 2. Cat

- [x] 2.1 `docs/env.md`: the `vsh_dump` and `fb_dump_at` rows updated; three new rows.
- [x] 2.2 TASKS.md: the D3D11 pre-trigger ring as a follow-up.
- [x] 2.3 `uv run pytest scripts`; `uv run ruff check . && uv run ruff format --check .`.

## 3. Check

- [x] 3.1 A short SSX 3 Metal run with `vsh_dump`, `fb_dump_prog=<a program seen early>`: the `.bin` files are written and the ring and post-trigger frames come out with the right flip numbers. BLX-180 then uses it on 8F706D7F.

## Evidence

- Gates: Mac ssx3 build OK; MinGW (llvm-mingw) toolkit build and the `nv2a_fb_ring` and `recomp_env_list` ctests cross-built; `tests/posix_ctest.sh` 75 pass, 0 FAIL (`nv2a_fb_ring` included); cat pytest 61 passed, 1 skipped; ruff clean. Logs: `notes/vsh-dump/` and the session gate logs.
- Run29 (`runs/ssx3/run29/`, Metal, `fb_dump_prog=26BC08FB,8F706D7F`, 30 before, 60 after): `26BC08FB first drawn at flip 1693 (draw 586766); dumping flips 1664-1753`. 90 frames `f_flip_01664`–`01753` were written, all distinct, and they run continuously across the trigger at 1693/1694. There are 22 `vsh_*.bin` on Metal, among them `vsh_16_26BC08FB.bin` and `vsh_20_8F706D7F.bin`.
