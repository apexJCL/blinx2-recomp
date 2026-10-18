## Why

The tracker item (SSX 3: the rider vanishes, leaving the board and a square shadow) is tied to the first draw of vertex program 8F706D7F. In runs 24 and 25 the rider disappears in the flip where that program first draws. In runs 26 and 27 the program never draws and the rider stays visible. Two debug tools fall short for the next step:

- **`vsh_dump` writes nothing on Metal or D3D11.** The `.bin` writer sits in `vsh_note_program()`, and the only caller is `raster_batch_vsh_one()`, the CPU rasteriser (toolkit `nv2a_pb_exec.c`). Run28 on Metal (`runs/ssx3/run28`) ran 9480 flips and wrote no programs, so the microcode of 8F706D7F and 26BC08FB is still unknown.
- **The onset can't be targeted by flip number.** SSX 3 races don't replay the same way from one run to the next, even with the same save and pad script (runs 25–27 finished 3rd, 4th and 6th), so the first draw of 8F706D7F lands at a different flip each time. `fb_dump_at` needs the flips in advance, and `fb_dump_flips` samples too sparsely. Its 64-range limit is also silent: run25's list was cut short without a message.

## What Changes

- **`vsh_dump` on every backend** (design D1). The executor tracks the program for every backend, so `vsh_note_program()` is also called from `draw_primitive()`, beside `vsh_const_dump_draw()`, for a program batch on a GPU backend. It runs only when `vsh_dump` or the `vsh` trace is set, so a stock run on D3D11 or Metal still never hashes the program per draw. The CPU path keeps its call where it is. The program table grows from 64 to 256 entries and prints a line once when it fills.
- **A frame-dump trigger on a program's first draw** (D2). The new key `RECOMP_DEBUG=fb_dump_prog=HASH[,HASH]` (hex, comma list) arms a trigger.
  - It fires once, at the first draw by any listed program.
  - From then on, the next `fb_dump_prog_after` flips (default 60) are dumped as `<fb_dump prefix>flip_NNNNN.bmp`, the same names `fb_dump_at` uses.
  - The `fb_dump_prog_before` flips before the trigger (default 30, at most 240) are kept in a memory ring of presented frames and written when it fires.
  - The ring works on the CPU path and on write-back backends (Metal).
  - D3D11 dumps from its own back buffer. It gets the post-trigger flips through the existing `nv2a_pb_dump_at_listed()` hook but no ring; that gap is a TASKS.md follow-up.
  - A log line names the program, the flip, the draw and the range dumped.
- **The `fb_dump_at` limit is raised and reported** (D3): 256 ranges instead of 64, and a warning when the list is truncated.

All three are default-off debug keys. Stock behaviour, goldens and speed are unchanged.

## Impact

- **Toolkit:**
  - `src/kernel/nv2a_pb_exec.c`: the `vsh_note_program()` call site, `VSH_MAX_PROGS`, the trigger, the ring and the dump_at limit.
  - `src/kernel/nv2a_fb_ring.{c,h}`: the ring and the trigger range, free of executor state so a ctest can drive them.
  - `src/platform/recomp_env.{h,c}`: three DEBUG rows; `fb_dump_prog` on the comma-key list.
  - `tests/nv2a_fb_ring/`: a new ctest. `tests/recomp_env_list` already checks every comma key.
- **Cat:**
  - `docs/env.md`: the `vsh_dump` row (every backend), the `fb_dump_at` row (256 ranges, the warning) and three new rows.
  - TASKS.md: the D3D11 ring follow-up.
- **Backends:** the program note and the post-trigger frames go through the shared walker, so CPU, Metal and D3D11 agree. D3D11 has no pre-trigger ring yet.
- **Upstream:** not planned; these are bring-up debug tools.

Worktrees:
- `wt/vsh-trigger/xboxrecomp` (`vsh-dump/any-backend`, off c497da56)
- `wt/vsh-trigger/cat` (`vsh-dump/trigger-doc`, off 9a61cab)
