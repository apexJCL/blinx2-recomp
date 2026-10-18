## Context

After `present-scanout` (phase 1) the executor picks the surface a flip shows by size first (the largest fresh clip extent at the display address or any scanout offset, at the display pitch or twice it for fields), then the newest draw since the last flip, and publishes `{offset, w, h, pitch, format}` through `nv2a_pb_present_state()`. `w, h` is the clip extent of the entry picked. D3D11's and Metal's `present_extent()` take `min(target, pick)` and place it with `nv2a_present_rect()`; the CPU presenter (`fb_present_sdl.c` `present_copy`) and the flip dumps read `w x h` from guest memory; D3D11's `internal_resize` sizes the swap chain to it under `present.surface = internal`.

The kernel's display-mode record (`xbox_memory_layout.c`) is the resolved framebuffer address, the pitch and a generation, set by the AvSetDisplayMode bridge (`kernel_bridge.c:2376`) before `xbox_DisplayModeBump()`. `xbox_AvSetDisplayMode` (`kernel_hal.c:1470`) keeps the mode word in `g_av_display_mode` for the encoder query and decodes nothing. The CPU presenter's Win32 window (`fb_present.c`) and the framebuffer checksum probe assume 640x480.

Observed: BLiNX 2 `mode=0x0801010D format=0x12 pitch=2560 fb=0x00104000` (three sets at boot, one briefly at 0x011A8040); Burnout 3 `mode=0x080F0D12 format=0x12 pitch=2560 fb=0x005E8000`. Both widths are 640 (`2560 / 4`, format 0x12 being `D3DFMT_LIN_A8R8G8B8`); the heights are nowhere in the runtime.

## D1. Where the display height comes from

Three candidates were weighed. The mode word wins; the other two are ruled out by evidence.

**The buffer at the display address.** Its clip extent is the problem (it is what phase 1 presents). Its allocation is no better: B3 allocates both back buffers in one block (`[CONTIG] alloc 0x805E8000 2400 KB`, twice 640x480x4), so size over pitch gives 960.

**CRTC or PRAMDAC registers.** On the console the kernel's AvSetDisplayMode programs them from its own timing tables, and xemu sizes its framebuffer surface from the VGA CRTC state so programmed (`nv2a_get_framebuffer_surface`, width and height from the VGA core, the address from `PCRTC_START`); the title never writes them. Our `xbox_AvSetDisplayMode` programs nothing, so there is no register to read: whatever we would put there would come from the mode word anyway.

**The mode word, through the XDK's own table.** The XDK's D3D chooses the word from a display-mode table it carries in every title. BLiNX 2's D3D (`cat/analysis/disasm/asm/D3D.asm`) calls `AvSetDisplayMode` from `sub_002E6660` with `RegisterBase = device+0x1C28`, `Step = 0`, `Mode = device+0x1C30`, `Format = device+0x1C34`, `Pitch = device+0x1C2C`, `FrameBuffer` from the swap state; the table it filled those from sits at xbe file offset 0x2E0820..0x2E1090 in BLiNX 2 (VA 0x2F0820) and 0x34F4F8 in Burnout 3, 2160 bytes, byte-identical in both (`runs/b3jitter` has no copy; the extraction script and its output go in the notes, never in a public repo). Each 12-byte row is `(flags, (height << 16) | width, mode word)`:

- `flags`: the AV pack in bits 0-7, the video standard in 8-15 and the refresh in 22-23, which is the key the kernel's `AV_OPTION_QUERY_AVPACK` comment already describes (`kernel.h:1126`); bit 24 marks a field-rendering row, bit 25 a progressive one, bit 16 the widescreen twin.
- 180 rows, 89 distinct mode words, each word naming exactly one frame size once a field row's height is doubled: 640x480, 720x480, 1280x720, 1920x1080 for NTSC (packs HDTV, SCART, composite; standards NTSC-M and NTSC-J), plus 640x576 and 720x576 for PAL. The frame size is a function of the word's timing byte (bits 8-15): 0x01, 0x03, 0x07, 0x0D, 0x0E, 0x0F are 640x480; 0x02, 0x04, 0x08 are 720x480; 0x05 is 640x576; 0x06 is 720x576; 0x0A is 1280x720; 0x0C is 1920x1080; 0x10 is 640x576 progressive. BLiNX 2's 0x0801010D is the HDTV-pack NTSC-M 480i 4:3 row (flags 0x0060); Burnout 3's 0x080F0D12 is its 480p 4:3 row (flags 0x0260): both 640x480, which is why the runtime's HDTV capability answer gives B3 a different word and the same lines.
- The words are the kernel's vocabulary, not the title's: nxdk's `lib/hal/video.c` publishes the same words with the same sizes (its 640x480 PAL-60 composite entry is 0x44030307, our row 0x44030307 is 640x480, pack 0, PAL), and the XDK's `av.h` names them. A table of them in the toolkit is kernel knowledge, as `AV_PACK_*` and `AV_FLAGS_*` already are.

**Field rendering is not in the word.** The 640x480 row and the 640x240 field row of a timing share the word (0x0801010D appears with flags 0x0060 at 640x480 and 0x0140 at 640x240). D3D marks fields to the kernel in one way only: `sub_002E6660` tests the device's mode flags for 0x01000000 (the row's field bit) and, when set, halves the pitch it passes to `AvSetDisplayMode` (`shr ebx, 1` at 0x002E6697). So a field title's buffers are at twice the display pitch, which is exactly how the present code has detected fields since `3ff3d6a` (N3). The record therefore carries no field flag; the present rule reads it from the surface pitch, as now.

**What the kernel adds.** `xbox_SetDisplayMode(fb_va, pitch, mode, format)` replaces `xbox_SetDisplayFramebuffer(fb_va, pitch)` in the bridge and stores, beside the address and pitch, the frame size `xbox_AvModeSize(mode, &w, &h)` gives (`kernel_hal.c`, beside the AV constants: the timing-byte table above, 0 for a byte it does not know) and the format. `xbox_GetDisplayMode(&pitch, &w, &h)` reads it; `xbox_GetDisplayFramebuffer` stays for the address. Width is cross-checked once per mode set against `pitch / bpp(format)` for the linear formats D3D passes (0x12, 0x1E four bytes; 0x11, 0x1C, 0x10 two; the AV format codes `sub_002E95B0` maps D3DFORMAT to); a pitch of half the width is no disagreement (D3D halves the pitch it passes for a field mode, whose buffers are at twice it); a disagreement or an unknown word logs one `[AV]` line and records no size, since presenting the table's width at that pitch would give a pixel size no format has. The record is read on the executor's thread, so a sequence count keeps each read whole. The record is written before `xbox_DisplayModeBump()`, as the address is today, so a walker that sees the new generation sees the new size. The checksum probe's `s_fb_height` and `fb_present.c`'s 640x480 read the record.

## D2. Modes other than 640x480, and titles that change mode

The table covers 720x480 (titles that render 720 wide), 1280x720 and 1920x1080 (our capability answer advertises 480p and 720p, so a title with an HD option may set 0x880B0A02), and the PAL sizes. A title that changes mode mid-run (BLiNX 2 sets its mode three times at boot, twice with a different address; a title with an in-game 480p or 720p toggle) gets a new record, generation and scanout set at each set; buffers of the old mode are at the old pitch or stale and cannot be picked, as phase 1 and `3ff3d6a` S2 arranged. A 1080i title renders 1920x540 field buffers at twice the pitch of a 1920-wide line, and D3's field rule shows 540 rows.

Nothing here reads the word's widescreen bit (0x10000000, the `1801010D` twin of `0801010D`): `display.aspect` stays the enhancements layer's; feeding `auto` from the record is a note in TASKS, not part of this change.

## D3. The present rule

Phase 1 decides *which* entry the flip shows and nothing in that changes: the scanout set, size-first, newest draw, staleness, the field pitch latch and the generation reset. This change decides the extent the pick publishes:

1. With a display mode whose size is known, and the picked entry at the display pitch: `w, h = display width, display height`.
2. With the entry at twice the display pitch (the field case `s_pitch_seen` admits): `w, h = display width, display height / 2`. One field at its own height, as today; never 480 rows from a 240-row buffer.
3. Otherwise (no display mode, an unknown word, or an entry at some other pitch): the entry's clip extent, as phase 1.

Rules 1 and 2 apply only to a pick sized from the display address or the scanout set (phase 1's pass 0); a pass-1 pick, the largest fresh surface anywhere, keeps its clip (rule 3) and does not join the scanout set, since nothing says the mode's frame is at its offset (the review's probe: a 320x240 offscreen at the display pitch was shown, and on Metal grown, at 640x480).

The pick's `pitch` and `format` are the entry's, as before. Width comes from the record, not the clip, so a title that clips narrower than its frame (Burnout 3's 250-pixel option windows, `surface_bpp`'s comment) also presents the whole line, as the CRTC does; the pitch cross-check in D1 is what guards the width.

The size-first scan still ranks candidates by clip area within the scanout set. That is deliberate: it is the tie-break that tells a back buffer from a same-offset oddity (the 640x480 clip with a 320x240 pitch the present comment describes), and it is tested; the extent override happens after it. The `[PRESENT]` trace prints the display size and which rule (1-3) set the extent on each traced flip.

Interleaving fields is a follow-up with a clear shape: on the console the even field's buffer at `base` and the odd field's at `base + display pitch`, both at twice the pitch, are one 480-line frame at the display pitch, so the CPU presenter could show the frame whole from guest memory and the GPU backends would need a two-target interleave. No title we run uses fields (no bench log has ever printed the field warning), so it waits for one that does.

## D4. The crop rule: narrowed, with its reason kept

`metal-present-mirror` (mirroring D3D11's 4bfee1c) made the present show the walker's extent rather than the whole target, because a target grown in place for a larger clip "can be bigger than the frame; the rest of it, and its black grow margin, is not the frame" (`present_extent`'s comment; design D4/D6 of that change). The walker's extent was the largest fresh clip at the display address, so a title whose clip shrinks shows the smaller frame once the larger entries age out, and the smoke's `crop` case pins that: 122 flips of a 320x240 clip on a 640x480 target, then `nv2a_pb_metal_shown` reports target 640x480, shown 320x240, and the CPU state 320x240.

The reason was the grow margin, not the CRTC. This change keeps the reason and changes the measure: with a display mode the frame is the display's size, which is never larger than the frame the title set up, so a target grown past it still hides its margin; without a display mode there is no better measure than the fresh clip, and rule 3 keeps it. The `crop` case runs without a display mode (the smoke sets one only in phase 1's scanout cases, which restore it), so it is unchanged and still pins rule 3. A new case pins rule 1 beside it: the same stream with a 640x480 mode set shows 640x480 on both paths (D6).

What a user would see differently: a title that renders a 320x240 clip into a 640x480-mode back buffer now shows the whole 640x480 frame, with the rest of the buffer as the console would show it, instead of a 320x240 frame scaled to the window. That is the hardware behaviour and the point of the change; no title we run does it.

## D5. Backends: grow instead of clamp

`present_extent()` in both backends takes `min(target, pick)`. Under rule 1 a pick can exceed a target only when the title never drew the buffer at the display size (the 320x240-clip title above); then clamping would show 320x240 on the GPU backends and 640x480 on the CPU path, a disagreement. So both backends grow the target to the pick with their existing `rt_grow` (D3D11 `nv2a_pb_d3d11.c:675`, Metal `nv2a_pb_metal.m:729`) before the present, then show the pick. The two backends' grow margins already differ (D3D11 starts black, Metal seeds from guest bytes; `metal-present-mirror` accepted that) and the difference is already in TASKS; this change does not widen it. For BLiNX 2 and Burnout 3 the grow never runs: their back-buffer targets are made at 640x480 by the first full clear (`[metal] surface 0x005E8000: 640x480 render target` at flip 1) and every later present is at or below it. D3D11's `internal_resize` and `s_shown_w/h`, Metal's `s_shown_w/h` and the layer blit, all follow the extent as now, so under `present.surface = internal` the swap chain holds one size for the whole run.

The CPU path needs nothing: `present_copy` and `write_present_bmp` already read `w x h` at the pick's pitch from guest memory.

## D6. Tests

**`tests/kernel_display_mode` (standalone ctest, kernel only):** `xbox_AvModeSize` gives 640x480 for 0x0801010D and 0x080F0D12, 720x480 for 0x0802020E, 1280x720 for 0x880B0A02, 1920x1080 for 0x880E0C03, 640x576 for 0x48050516 and 0 for a word with an unknown timing byte; `xbox_SetDisplayMode` then `xbox_GetDisplayMode` returns what was set and the generation is bumped after the size is visible; a pitch that disagrees with the format's width logs once and records no size. The table check is also run by the notes' extraction script against the 89 words of both titles' tables (private).

**`nv2a_backend_smoke`, CPU path and Metal where it builds, after phase 1's cases:**
1. Rule 1 beside the crop: the crop case's stream with a 640x480 mode set at BUF0 (pitch 2560): CPU present state 640x480; Metal `nv2a_pb_metal_shown` target 640x480, shown 640x480. The existing crop case (no mode) stays as it is.
2. Grow at present: a mode set at a fresh buffer only ever drawn with a 320x240 clip; the flip shows 640x480 on the CPU path, and on Metal the target is grown to 640x480 and shown whole; the 320x240 content is at the top left on both.
3. Field title: mode set with pitch 2560; every frame draws a 640x232 clip into A at pitch 5120, then flips; the extent is 640x240 at pitch 5120 (the mode's half height, not the clip) and the field warning prints once. Then a surface at pitch 2560 is drawn and flipped: 640x480.
4. Mode change: after case 1, a mode set with word 0x880B0A02, pitch 5120, at a new address; a frame at 1280x720 and a flip: 1280x720; then back to 0x0801010D at 2560: 640x480. The old mode's buffers are never picked in between.
5. Unknown word: a mode set with timing byte 0x7F records no size; the pick's extent is the clip's, as phase 1.
6. B3's pattern: one buffer pair, 20 frames at clip 640x464 then 20 at 640x480 and 640x463 (phase 1's card frame): every flip from the first presents 640x480, zero size changes across the transition.
7. A pass-1 pick (added by the review): the mode set at a buffer nothing draws, and only a 320x240 offscreen at the display pitch drawn for 122 flips; the CPU path presents 320x240 and Metal's target stays 320x240.

**`d3d11_backend_smoke`, under Proton (added by the review):** the crop stream with a 640x480 mode set shows the 640x480 target whole, and a buffer drawn only at 320x240 has its target grown to 640x480 and shown whole.

Cases 1, 2 and 6 fail on `fix/present-scanout` and pass on the branch; both outputs go in the notes.

## D7. Stock, byte for byte

- **BLiNX 2:** the pick is 640x480 from the display address on every flip (phase 1's D4 proof, the `RECOMP_FLIP_LOG` sequences), and 640x480 is the mode's size, so rule 1 publishes the same extent and the copy path's input is unchanged. Proof as in phase 1: identical per-flip `(offset, w, h)` columns against main for attract, stage1 and story, goldens passing unchanged on Metal and D3D11, the `[d3d11] first present` line reading `copy`. No re-record.
- **Burnout 3:** the menus move from 640x464 to 640x480 at stock: D3D11 takes `CopyResource` instead of the overlap copy, and rows 464-479 come from the guest buffer (black bars, or the lit row 464 of TASKS follow-up (a)), which the console shows too. B3 has no golden; the race gate judges race reached, FPS, stalls, audio and stock `[ENHANCE]` lines, never a frame's size, so nothing is re-recorded. The race gate's frame dumps change height, which is the intended effect.
- **Everything else:** the Win32 window and the probe read 640x480 from the record for both titles, as they assumed.

## D8. Branch, stacking and overlap

Toolkit branch `fix/present-mode-height` cut from `fix/present-scanout`'s tip (2a142d7 at the time of writing) in `wt/present-mode-height/xboxrecomp`, so it builds on phase 1's `s_scanout`, `present_scanout()`, `present_victim()` and smoke cases. Phase 1 lands first by `git merge --squash`; this branch is then rebased with `git rebase --onto posix-host/portability fix/present-scanout` (its own commits only) and lands by squash after its own gates re-run on the rebased tip. Cat branch `spec/present-mode-height` off `spec/present-scanout` carries this spec and the env.md rows.

Files: `kernel_hal.c` (table), `kernel_bridge.c` and `xbox_memory_layout.{c,h}` (record), `nv2a_pb_exec.c` (present block), `nv2a_pb_d3d11.c` and `nv2a_pb_metal.m` (`present_extent` only), `fb_present.c`, tests. `feat/fork-prs-aniso-bumpenv` touches the two backends in their sampler and shader setup and the executor at `vsh_method`; none of these regions. `git merge-tree` against it should be clean.

## Validation

- `tests/posix_ctest.sh`: 0 FAIL, with `kernel_display_mode` and the six smoke cases; cases 1, 2 and 6 shown failing on `fix/present-scanout`.
- BLiNX 2 goldens on Metal and D3D11 unchanged, the sequence diff empty.
- Burnout 3: Metal race gate on the Mac; the Deck fullscreen `--pad-script` run with `RECOMP_FLIP_LOG=1` showing zero `WxH` changes from the `[AV] SetDisplayMode` line to the end of the drive, title screen, menus and race included.
- Review before the merge.
