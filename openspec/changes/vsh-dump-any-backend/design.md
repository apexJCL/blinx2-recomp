## D1. The program note on every backend

`vsh_note_program()` hashes the program (`nv2a_vsh_program_hash`), counts batches per `(hash, start)` and, the first time it sees a pair, prints the `vsh` trace and writes the `vsh_dump` file. The file holds the start, the program memory, the constants and the inline attributes. All of that state (`s_vsh`) is kept by the executor for every backend; `vsh_const_dump` relies on the same state on Metal.

`draw_primitive()` gains the call next to `vsh_const_dump_draw()`, when:
- the batch runs a program (`vsh_batch_active()`);
- the backend isn't the CPU rasteriser, which already calls it from `raster_batch_vsh_one()` and uses the returned length;
- `vsh_dump` or the `vsh` trace is set. The answer is cached the first time. The hash walks every program slot, so a stock GPU run must not pay for it per draw.

The end-of-run `[VSH]   program ...` lines then also appear on GPU backends when one of those keys is set. `VSH_MAX_PROGS` goes from 64 to 256, because a whole race can use more than 64 `(hash, start)` pairs. When the table is full, one line says that programs after the 256th are neither counted nor dumped.

## D2. The first-draw trigger and the ring

There are three keys, all DEBUG tier. They need `fb_dump` for the prefix, like `fb_dump_at`.

| key | value | default |
|---|---|---|
| `fb_dump_prog` | hex program hashes, comma list, up to 16; parsed with `nv2a_vsh_cdump_parse` | unset: off |
| `fb_dump_prog_before` | flips kept before the trigger, 0–240 | 30 |
| `fb_dump_prog_after` | flips dumped from the trigger on | 60 |

**Flip numbering:** a draw happens while `s_gpu.flips == k`, and its frame is presented by the flip that makes the count k+1. This is also the number `dump_at_flip` and the D3D11 `s_presents` use. When the trigger fires at a draw with flips == k:
- flips k+1 through k+after are added to the dump_at test as one dynamic range, so `nv2a_pb_dump_at_listed()` covers them for D3D11 and for the walker-side dump;
- the ring then holds the frames of flips k-before+1 through k, which were presented before the trigger. They're written as `flip_NNNNN.bmp` at the next flip, from the walker thread, before that flip's own dump.

**The ring** (`nv2a_fb_ring.c`):
- It has `before` slots, each holding a flip number, w, h, pitch, bpp and a byte buffer that is grown, never shrunk.
- While armed, `dump_at_flip()` copies the presented surface into the next slot, after `sync_guest`, the same readback `write_present_bmp` does.
- Writing walks the slots from oldest to newest and calls `write_bmp_at` on each; then the ring is freed.
- At 640×480×4 bytes, 30 slots take 37 MB, and 240 slots take 295 MB. The cap is there so a typo can't exhaust memory.
- The per-flip readback costs Metal a GPU sync, only while the trigger is armed. Before is 0 skips the ring and its cost.

**Logging:**
- When the trigger is armed: `[GPU] fb_dump_prog: armed for N program(s), B flips before, A after`.
- When it fires: `[GPU] fb_dump_prog: HASH first drawn at flip k (draw d); dumping flips a-b`.
- A malformed value prints one line, and the trigger stays off.

**D3D11:** the post-trigger frames come through `nv2a_pb_dump_at_listed` with the `d3d11_dump` prefix, as `fb_dump_at` does today. The pre-trigger ring would need a back-buffer copy per present inside the backend. It is left out and recorded as a TASKS.md follow-up, which the "backends agree" rule allows for debug tooling.

**The pure parts are tested standalone** (`tests/nv2a_fb_ring`): the ring's order across wrap-around, a shorter fill than its size, size 0, the slot grow on a size change, and the trigger range arithmetic (`nv2a_fb_trigger_range`: k, before, after → the ring's first flip and the dump range, with no wrap at flip 0).

## D3. fb_dump_at's limit

`s_dump_at_lo/hi` grow to 256 entries. `dump_at_parse` keeps parsing past the limit only to count what it dropped, and prints `[GPU] fb_dump_at: N ranges past the first 256 ignored`. The run25 list of 81 single flips was silently cut to 64.

## Non-goals

- A pre-trigger ring on D3D11 (a follow-up).
- Triggers on anything other than a program hash.
- More than one firing per run.
