# Hor+ 16:9 widescreen for BLiNX 2: spike

Spike, 2026-10-07, on the Mac only (Metal), against cat `main` 885d62f and
toolkit `posix-host/portability` a0b9a55. Branches `spike/hor-plus` in both
(worktrees `wt/horplus/{cat,xboxrecomp}`). Raw runs under
`xbox-recomp/runs/horplus/`. The binding decisions are the enhancements
layer's (`spike/enhancements` baeb15b, design.md § User Decisions): generic
Hor+, check FOV for edge pop-in without going deep into game-specific code,
goldens at stock, every key opt-in and OFF by default.

The question from TASKS.md: where the projection or FOV is set, which HUD,
menu and 2D pieces need `[aspect.program.<hash>]` fixes, cutscenes and
movies, the effort, and the Burnout 3 outlook.

## 1. Where the projection is set, and why it does not matter for the generic mode

**Every vertex the game draws reaches the backends in surface pixels.** The
walker tracks two paths and the Metal/D3D11 backends map both the same way:

- Vertex programs: the XDK's shader epilogue multiplies by `c[58]` (the
  viewport scale) and adds `c[59]` (the viewport offset) after the
  perspective divide (`rcc`), so `oPos.xy` leaves the program in pixels of the
  640x480 surface with the clip `w` in `oPos.w`. The backends' generated MSL
  and HLSL (`d3d8_vsh_msl.c:343-347`, `d3d8_vsh_hlsl.c:452-461`, both built
  with the `SCREEN_SPACE` flag) map pixels back to NDC:
  `o.pos = ((oPos.xy * vp_scale.xy + vp_off.xy) * w, oPos.z * vp_scale.z * w, w)`.
- The fixed-function / pass-through path (`program == 0`, pre-transformed
  XYZRHW vertices: the HUD, menus, the movie quad, post passes): attribute 0
  is already in pixels, and `vs_pass` applies the same two constants
  (`nv2a_pb_metal.m:172-180`).

`vp_scale` and `vp_off` come from one shared function,
`nv2a_vp_consts_fill(v, format, rt->w, rt->h, &vc)` in
`nv2a_backend_common.c:357`: `c[0] = 2/w, c[1] = -2/h, c[4] = -1, c[5] = 1`.
Both GPU backends call it per batch with the target's guest size (Metal
`:1889`, D3D11 `:2870`). Render scale already rides on this: the host target
is `N` times larger, the viewport covers it, the constants stay on the guest
size.

`c[58]`/`c[59]` are written by the XDK's `D3DDevice_SetViewport` through the
NV097 viewport methods, which the walker folds into the constant file
(`nv2a_pb_exec.c:1996-2013`). In every BLiNX 2 run on record the viewport is
the full surface: `offset 320.53 240.53, scale 320 -240` (791 `[VSH]
viewport` summary lines in bench-logs, all the same values; Burnout 3 is the
one that uses `320 -224`, a 640x448 viewport, and `64 -64`).

**The projection itself is in the game's composite matrix.** Programs do
`m4x4` against constant rows the game fills per batch (world x view x
projection, then the viewport epilogue); the walker never sees a projection
matrix on its own, and the game's matrix-build functions carry no `4/3` or
`0.75` immediate (`0x3FAAAAAB` does not occur in `.text`; the `0x3F400000`
hits are clamps and colours, e.g. `0x0001A101`). Finding the game's
`fovy`/aspect site is a disassembly task of its own (the writers of the
constant rows the 3D programs read), and the layer design asked not to go
deep: the generic Hor+ below does not need it, and § 5 says what it would buy.

**No native widescreen mode.** The toolkit's EEPROM answer already reports
`XC_VIDEO_FLAGS_WIDESCREEN | HDTV` (`kernel_xbox.c`, `XC_VIDEO`), and the game
reads the video flags once in its init (`sub_0005F972` at `0x0005F99F`,
through the XDK's `XGetVideoFlags`, `sub_00298AA3`); it masks only the PAL-60
bit (`shr eax, 6; and eax, edi` into `0xEC4BF4`). Nothing in the game reacts
to the widescreen bit, which matches the stock 4:3 frames at every anchor:
BLiNX 2 has no anamorphic 16:9 option to switch on. (Burnout 3 has one; § 7.)

## 2. The generic Hor+: shift the pixel-to-NDC mapping, widen the target

This is the layer design's D3, made concrete against today's code. One rule,
no per-title knowledge:

For a colour target whose guest shape is 4:3 within 1% (640x480 and 320x240
in BLiNX 2; not 256x256 or 512x512, which are shadow/environment/post
buffers and keep their shape), add `pad` guest pixels on each side:
`pad = round((h * aw/ah - w) / 2)`; 16:9 gives 107 for 640x480 (host width
854) and 53 for 320x240. The host texture is `(w + 2*pad) * N` by `h * N`, the
viewport covers it, the depth target follows its colour target. The mapping
constants become `vp_scale.x = 2 / (w + 2*pad)`, `vp_off.x = -w / (w + 2*pad)`:
guest pixel 0 lands at host column `pad*N`, guest pixel 640 at
`(640 + pad)*N`. Everything the game positioned in its 640 columns stays
where it was, centred; a perspective batch whose projected geometry falls
outside 0..640 is no longer clipped at the 4:3 edge (the host clips at NDC
+-1, which is now the padded width), so it fills the new columns with the
game's own vertical FOV. That is Hor+ in the literal sense: the same vertical
view, 33% more horizontal view, at the same pixel scale.

Three classes of batch need the *other* mapping, the stock `2/w, -1`, which on
a padded target stretches 0..640 over the whole host width:

| Class | Examples in BLiNX 2 | Rule |
|---|---|---|
| full-width 2D batches that sample a render target | the glow and post downsample/blur/composite quads, the time-control blur, the pause blur | stretch, and sample the source target whole (`tex_scale.x = 1/w` on a padded source is exactly that) |
| full-width untextured 2D batches | fades, the time-control tint, letterbox bars in cutscenes | stretch x |
| full-width 2D batches sampling a guest texture | the movie quad, the title's cloud movie, loading and still backgrounds | **centred** (a 4:3 picture stays 4:3, pillarboxed); per-hash override to stretch |

Everything else 2D (HUD, text, menus, radar, markers, the CPU-projected
sprites) is centred by default. Classification is per batch, from data the
backend has in hand: the first vertices' output positions (pass-through:
attribute 0 as is; a program: the program's `oPos` for the first <= 8
vertices through `nv2a_vsh_run`, cached per program hash as "2D" when
`oPos.w == 1`) and whether stage 0 is bound to a render target
(`rt_texture()` non-NULL) or a decoded guest texture. "Full-width" means the x
range covers `[0 - 2px, w + 2px]`. Overrides go in `enhance.toml`:
`[aspect.program] <hash> = "center" | "stretch"` and
`[aspect.texture] <hash> = "center" | "stretch"`, with `RECOMP_TRACE=enhance`
listing each hash's decision once.

What else moves with the pad (the render-scale table, with one more term):

| Site | Change |
|---|---|
| allocation (`surface`, `rt_grow`, `depth_target`) | host size `(w + 2pad)*N x h*N`; `RenderTarget` carries `pad` and `n` (today's `hw / w` is no longer the factor) |
| clears | a clear covering the whole clip clears the whole host target (pads included); a partial clear is offset by `pad*N` |
| seed from guest bytes (`rt_seed`) | the guest frame into the centre, pads black |
| write-back (`write_back`, `write_back_scaled`, `rt_sync`) | the centre `w x h` region, so `RECOMP_FB_DUMP`, `fb_dump_at` and the title keep 640x480 guest frames (goldens stay stock-shaped by construction) |
| present | the whole host target (`hcw = (cw + 2pad)*N`); the presenter already places a frame by its own aspect (`nv2a_present_rect`), so a 16:9 frame letterboxes in a 4:3 window and fills a 16:9 one |
| RTT sampling by a centred batch | `tex_scale.x = 1/(w + 2pad)`, plus an offset `pad/(w + 2pad)` (the `tex_scale` constant's unused `zw` lanes; one line in each combiner emitter) |
| self copy | host size, as today |
| `read_pixel`, `px_probe` (D3D11 debug) | `x -> (x + pad)*N` |
| visibility counts | unchanged (the title's tests count its own geometry; a wider view counts a little more, which only makes "visible" more visible) |

CPU backend: it rasterises into guest memory at the guest pitch; the key is
ignored with one log line, as `render.scale` is.

## 3. What breaks, by area

From the first 16:9 attract run (`runs/horplus/wide-attract-v2-noscissor`,
1136 flips, host frames `fb/host_NNNNN.bmp`, sheets in `runs/horplus/sheets/`):

| Area | Seen | Rule / fix |
|---|---|---|
| 3D | works as designed: the cliff scene shows 107 more columns a side with the game's vertical FOV, continuous geometry across the old 4:3 edge (`sheets/edges.png`: crops of the pads at flips 1000 and 1100, no seam at column 107, nothing missing at the border); no pop-in observed in the demo's camera path (a hub drill is still owed) | the mapping shift (§ 2) |
| post chain (glow) | the 5 full-width 2D batches a frame (downsample, blur, composite) are stretched; the glow halos continue into the pads | stretch class |
| title screen | the cloud movie quad (guest YUV texture) stays 4:3, pillarboxed black, the 3D crystal and the logo centred (`sheets/pair-a.png`, top) | centred class; `[aspect.texture]` could stretch it |
| HUD parked off-screen | **the biggest 2D problem:** the demo's HUD elements that the game slides out of view (two radar/gauge circles at x < 0 and x > 640) appear in the pads (`sheets/pair-a.png`, bottom right) | centred 2D batches are scissored to the game's 640 columns (prototype v3, unverified: the run was queued when the session wound down) |
| full-width HUD batch | the blue corner triangles (one batch spanning x 0..640 and y 0..480) are classified full-width and stretched to the new edges, 33% wider | needs an override (`[aspect.program.<hash>] = "center"`) or a finer rule (a single primitive spanning the width, not a bounding box); the hash is logged by the v3 trace |
| classifier cost | one interpreter run per batch halved the flip rate (2519 → 1136 flips in 75 s) | v3 gates it per program hash (16 batches, then every 256th; 2D programs always) |
| menus, in-engine cutscenes, stage HUD, story hub | not reached: the stage1 and story runs were queued behind the Mac lock when the session wound down | next session, same chain (`scratchpad/wide-chain.sh` logic: `probe.sh NAME SCRIPT SECS 20 RECOMP_DISPLAY_ASPECT=16:9 RECOMP_VSH_TRACE=1 RECOMP_DEBUG=...metal_host_dump=`) |
| FMV (Sofdec movies) | the movie quad samples a guest texture: centred by the rule (not run) | centred; override to stretch |
| write-back / goldens | guest frames stay 640x480 (`fb/NNN.bmp` of the wide run are the centre); the stock golden passes on the prototype binary | by construction |

## 3b. Resume here (2026-10-07, wound down on quota)

Done:
- Analysis §§ 1, 2, 5, 7, 8 and the findings above; the Metal prototype on
  toolkit `spike/hor-plus` (v3: padded targets, mapping, program-based 2D
  classification through `nv2a_vsh_run` with per-hash gating, scissor for
  centred 2D batches, stretch for full-width RT/untextured passes,
  `metal_host_dump`); `tests/render_scale` pad cases pass; stock golden
  `@attract` passes on the prototype binary (`runs/horplus/golden-attract`).
- OpenSpec change `enhancements-hor-plus` (proposal, design, spec delta,
  tasks), `openspec validate --strict` clean, marked WIP: design H3 still
  describes the pass-through classifier; it must become the program-based
  one (§ 4) with the scissor rule and the per-hash gating, and the tasks'
  § 1 and § 4 follow.
- v3 of the prototype is compiled as an object but **not linked or run**:
  `ninja -C build cat_recomp` in `wt/horplus/cat` (under the Mac lock), then
  the chain (`wide-attract`, `wide-stage1`, `wide-story`).

Next:
1. Link v3, run the three 16:9 scenarios with `RECOMP_VSH_TRACE=1`; read the
   `[METAL] hor+: program <hash> 2D batch ... -> full width|centred` lines
   (the `[aspect.program]` inventory TASKS asked for), check the scissor
   hides the parked HUD, measure flips/s against the stock 2519.
2. Decide the corner-triangle batch: override by hash, or the "single
   primitive spans the width" refinement.
3. Fold § 4's program classification, the scissor and the gating into
   design H3/H4 and the spec delta; drop the "every 2D batch is
   pass-through" claims; then the spec pass.
4. Story-hub drill for pop-in; perf; the D3D11 mirror stays as written.

Open questions for the user:
- Full-width HUD batches that touch both edges (the corner triangles): stretch
  (edge-anchored but distorted), centre (as stock), or an `aspect.hud =
  edges` mode later? Proposed: centre by default via the override, and keep
  edge anchoring as a follow-up.
- Movies and stills: 4:3 pillarboxed by default (proposed) or stretched.

## 4. Prototype and probe runs (Metal)

The prototype on toolkit `spike/hor-plus` implements § 2 for Metal:
`nv2a_host_pad`, `aspect_w/h` in `nv2a_host_opts`, the pad term in
`nv2a_vp_consts_fill`, `display.aspect` parsing in `enhance.c`, the
`tex_scale.zw` sampling offset in the MSL combiner, `pad`/`n` on the Metal
targets with the allocation, seed, clear, write-back and present sites, an
in-draw classifier, and `RECOMP_DEBUG=metal_host_dump=<prefix>` for host-size
frames (the guest dumps stay 640x480 by design). `tests/render_scale` gained
the pad and mapping cases. All runs are headless Metal under the Mac run
lock, 16:9 = `RECOMP_DISPLAY_ASPECT=16:9`; raw output in
`xbox-recomp/runs/horplus/<run>/` (`log.txt`, `fb/NNN.bmp` guest frames every
20 flips, `fb/host_NNNNN.bmp` host frames).

**Stock identity** (`golden-attract`): the prototype binary with no key set,
`@attract` 75 s, `fb_dump_at` at the golden flips, `blinx2 golden check`:
`attract-title` CLOSE (mae 1.940/1.319/1.295, bad 0.0000%, limits 6.0/0.20%)
and `attract-cliff` CLOSE (mae 0.192/0.209/0.226, bad 0.0042%, limits
0.5/0.50%), `golden: pass`; the log shows `(display.aspect=4:3)` and no
`hor+` line. The same verdicts as the integration runs of these frames.

**Stock probe** (`stock-attract`, `@attract` 75 s, 2519 flips): the
reference frames for the comparison below, and one fact that changed the
classifier: on Metal every batch of every frame is a program batch (`[METAL]
flip 1000 batches 3153 prog 3153`; the title menus and HUD included). BLiNX 2
never uses the pass-through path: the XDK's fixed-function pipeline is a
vertex program too. So "pass-through = 2D" (the layer design's D3 and the
first prototype) classifies nothing here; the prototype's second version
asks the program: one vertex of the batch through the toolkit's interpreter
(`nv2a_vsh_run`, with the batch's constants), `oPos.w == 1` after the XDK
epilogue means an orthographic (2D) batch, and for those the x range of up
to 33 sampled vertices decides full-width. Cost: one interpreter run per
batch (about 3000 a frame in the demo), plus a few for the 2D ones.

## 5. FOV and edge pop-in

The game culls on the CPU against its own 4:3 frustum: an object whose bounds
leave the 4:3 view is not drawn, so in the new side columns it appears late
(pop-in) and disappears early. The generic mode cannot change that; the fix
is per game: patch the game's projection build to the wide ratio (then the
3D class switches to the stretch mapping, since the game's own projection is
wide, and the CPU-side culling, LOD and "is on screen" logic agree with the
picture). It needs the site § 1 did not look for. Effort once found: S-M (a
`recomp_manual.c` wrapper that rewrites the matrix rows, like the glow
wrapper). The generic Hor+ is playable before it, with pop-in at the edges
the documented limit.

## 6. Per-backend work

| Backend | Work |
|---|---|
| Metal | the table in § 2 (prototype in this spike covers the mapping, allocation, clear, seed, write-back, present and RTT offset; the classifier and overrides are the implementation's) |
| D3D11 | the same table on `nv2a_pb_d3d11.c`: allocation (`rt_grow`, `depth_target`), viewport, clear rect, `read_pixel`/`px_probe`, present blit extent, `dump_frame` at host size; the HLSL combiner's `tex_scale.zw` offset. Proton-only verification |
| CPU | ignore with a log line; `RECOMP_PB_FAST_AB` untouched |
| presenter (SDL, CAMetalLayer, D3D11 window) | nothing: frames carry their own aspect |
| shared | `nv2a_host_opts.aspect`, `nv2a_host_pad()`, the classifier and its per-hash overrides in `nv2a_backend_common`, ctests |

## 7. Burnout 3 outlook

From the Proton bench logs of the B3 menu script (`bench-logs/20261006-194527`,
D3D11): targets 640x480 (the frame, 20388 lines), a 640x464 clip of the same
surface (1157), 320x240 and 160x120 (post downsamples), 128x128 and 64x32
(bloom), and viewports of 640x448 (`scale 320 -224`, the race view with
bars), 640x480 and 128x128. Under the rule of § 2:

- the frame and its 320x240/160x120 downsamples are padded; the 640x464 clip
  is a clip of the padded 640x480 target (one target per surface, grown), so
  nothing special; the 128x128 and 64x32 bloom buffers are not 4:3 and keep
  their shape, and the full-width quads that fill them sample their padded
  sources whole (the classifier runs on any target while the aspect is set),
  so the bloom covers the pads;
- the 640x448 viewport is a `c[58]`/`c[59]` matter the game owns; the mapping
  shift does not care about it;
- Burnout 3 is the second data point for the classifier: a different HUD
  and menu set. Whether it draws them with programs is not known (a
  `RECOMP_VSH_TRACE` menu run on the Linux/Proton host tells); if it does, the
  `nv2a_vsh_run` 2D-program classification named as a follow-up is needed
  there, with centred-by-default as the safe fallback;
- Burnout 3 has its own anamorphic 16:9 option (the Xbox release supports
  480p and 16:9). With it on, the game projects a 16:9 picture into the 4:3
  frame; the right enhancement there is a present-stage stretch
  (`aspect.mode = anamorphic`: the whole 640x480 frame shown at 16:9, HUD
  included, as the game designed it), not Hor+. That is a small presenter key
  (S) and is the recommended B3 path; the generic Hor+ with the option off
  works too and gets the classifier's second data point. Both are Proton-only
  verification (TASKS § 7 of the change).

## 8. Effort

| Piece | Size | Notes |
|---|---|---|
| Shared: `nv2a_host_pad`, mapping, classifier, overrides, two ctests | S | pad and mapping exist on `spike/hor-plus`; the classifier moves out of the Metal draw into `nv2a_backend_common` with the override table |
| Metal: H4 sites, host dump | S | prototyped on `spike/hor-plus`; the classifier swap and the CPU log line remain |
| D3D11 mirror | M | the same table on `nv2a_pb_d3d11.c` plus the HLSL `tex_scale.zw` term at three sampling sites; built with llvm-mingw, verified under Proton |
| cat wiring, docs, golden pin, TASKS | S | |
| Mac verification (goldens at stock, three 16:9 scenarios, 16:9 x 2, present shots, perf) | S-M | about four hours of queued runs under the Mac lock |
| Proton verification (goldens, 16:9 runs, Burnout 3) | M | one Linux/Proton session |
| Per-game projection patch (pop-in) | not sized here | needs the projection build; a follow-up |

Total: about two agent-sessions for the implementation and the Mac
verification, plus one Linux/Proton session; the enhancements layer's spike put
Hor+ at "M, ~80% generic", which holds.
