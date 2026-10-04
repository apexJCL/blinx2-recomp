## Context

The translated XDK D3D builds NV2A command streams in contiguous memory and advances `DMA_PUT` in the zeroed register aperture. The toolkit already has three ways to consume that stream:

| Piece | File | Role |
|---|---|---|
| Survey | `src/kernel/nv2a_pb_scan.c` | Decodes the segment between the last PUT and the new one and counts `(subchannel, method)` pairs (`RECOMP_PB_SCAN`). |
| Executor | `src/kernel/nv2a_pb_exec.c` | Uses the same decode. Tracks surface state, clears, and rasterises screen-space batches, flat or textured from stage 0, into the guest framebuffer (`RECOMP_PB_EXEC`). It ranks every method it does not act on. |
| Output | `src/video/fb_present.c`, `dump_surface_bmp` | `RECOMP_FB_WINDOW` (Windows only) shows the surface finished at FLIP_STALL. `RECOMP_FB_DUMP=<prefix>` writes `<prefix>NNN.bmp`. |

The driver is the NV2A ack thread in `xbox_memory_layout.c`. When PUT moves, or every 2 s, it scans or executes from the last PUT to the new one (handling ring wrap), and only then sets `DMA_GET = PUT`. It prints a report every 10 s when any of `RECOMP_NV2A_TRACE`, `RECOMP_PB_SCAN` or `RECOMP_PB_EXEC` is set.

How the environment variables are read:

- `s_nv2a_trace` is latched once at aperture init, from `RECOMP_NV2A_TRACE || RECOMP_PB_SCAN || RECOMP_PB_EXEC`. It gates the 10 s report and the DMA_PUT/GET and PCRTC_START lines.
- The scan reads `RECOMP_PB_SCAN` on every call. `RECOMP_PB_EXEC` is latched on the first scan.
- The method inventory prints only with `RECOMP_PB_SCAN`. The unhandled ranking prints only with `RECOMP_PB_EXEC`, top 10 by default, or all with `RECOMP_PB_UNHANDLED_ALL`.
- `RECOMP_FB_DUMP` is read on every dump. A dump is written on each 10 s report and on the first `FB_DUMP_AFTER_DRAW` batches that rasterise triangles.
- Other knobs: `RECOMP_PB_EXEC_VERBOSE`, `RECOMP_PB_WRAP_TRACE`, `RECOMP_TEX_DUMP[_EVERY]`, `RECOMP_RASTER_TEST`, and the new `RECOMP_PB_SEMA_TRACE`.

## Survey (macOS arm64, 150 s, `pres-1`/`pres-3`)

The stream parses cleanly. The first 90 s gave 8,460 segments, 4,701,054 words, 0 jumps, 0 unrecognised words and 387 distinct pairs. Subchannel 0 (Kelvin, NV097) carries 371 of the pairs. Subchannels 1, 2, 3 and 5 see only SET_OBJECT and context-DMA setup, once each, so there is no 2D blit or M2MF traffic.

Draw-side methods the executor already handles: SET_BEGIN_END x8,457, INLINE_ARRAY (0x1818) x53,162, DRAW_ARRAYS x2,330, CLEAR_SURFACE x2,060, COLOR_CLEAR_VALUE x14,998, FLIP_INCREMENT_WRITE/FLIP_STALL x2,057 each. Fence-side: SET_CONTEXT_DMA_SEMAPHORE x1, SET_SEMAPHORE_OFFSET x1, BACK_END_WRITE_SEMAPHORE_RELEASE x6,462.

Unhandled methods once the executor runs (3,956,221 calls, 322 distinct), grouped by register and named from `nv2a_regs.h`:

| Calls | Slots | Register | Needed for |
|---:|---:|---|---|
| 2,511,075 | 32 | SET_TRANSFORM_PROGRAM (0x0B00) | vertex programs |
| 308,285 | 30 | texture stages 1-3 (0x1B40-0x1BFC) | multi-texture |
| 215,632 | 16 | SET_TRANSFORM_CONSTANT (0x0B80) | vertex programs |
| 154,116 | 8 | SET_COMBINER_FACTOR0 | register combiners |
| 136,984 | 8 | SET_COMBINER_FACTOR1 | register combiners |
| 68,488 each | 8 | COMBINER_ALPHA_ICW / ALPHA_OCW / COLOR_ICW / COLOR_OCW | register combiners |
| 45,610 | 1 | SET_TRANSFORM_CONSTANT_LOAD | vertex programs |
| 33,200 / 33,160 | 4 | SET_VIEWPORT_OFFSET / SCALE | viewport transform |
| 17,126 | 1 | SET_SHADER_OTHER_STAGE_INPUT | texture shader |
| 17,122 | 2 | SET_SPECULAR_FOG_FACTOR | combiners final |
| 12,823 | 2 | SET_SHADER_STAGE_PROGRAM | texture shader |
| 12,441 | 1 | SET_DEPTH_TEST_ENABLE | depth |
| 12,439 | 1 | SET_ZMIN_MAX_CONTROL | depth |
| 12,118 / 12,108 | 1 | SET_TRANSFORM_PROGRAM_LOAD / _START | vertex programs |
| 11,960 | 1 | SET_TEXTURE_CONTROL0 (stage 0) | texture enable |
| 8,561 each | 1 | SHADER_CLIP_PLANE_MODE, COMBINER_CONTROL, COMBINER_SPECULAR_FOG_CW0/1 | combiners |
| 8,300 each | 1 | SET_CLIP_MIN / MAX | depth range |
| 8,285 | 1 | SET_DEPTH_MASK | depth |

The survey's own name table had several labels wrong: TRANSFORM_PROGRAM and TRANSFORM_CONSTANT were swapped, 0x0130 was called FLIP_READ, 0x1808 was called INLINE_ARRAY, and 0x1D6C was called a zstencil clear. These are fixed in the toolkit.

## What the frames show (`pres-2`, `pres-3`, BMPs under `analysis/bringup/fb2` (local analysis, not published), `fb3`)

The surface is 640x480 X8R8G8B8, double-buffered at 0x01034000 and 0x01160000 (resolved to 0x81034000 and 0x81160000 in the contiguous window). Every batch so far is screen-space. None was skipped as needing a vertex program.

- The first 8 dumps are black: clears plus letterbox bars before the first movie frame.
- Then the intro movie draws correctly. The MPEG frame is a YUY2 (fmt 0x24) 1024x512 linear texture on a screen-space quad, with letterbox bars. Recognisable frames: the Microsoft Game Studios logo, the Artoon logo, and gameplay cuts from the intro, including a four-panel montage.
- About 90 s in, the frame turns solid white (0xFEFEFE) and stays that way. The title then stops submitting: PUT stops moving, and the segment and release counts freeze.

### The 90 s stop is not caused by this change

- It also happens with the executor off and the fence mirror on (`pres-1`), and in `hle-14`, where PUT is stuck at 0x000C1F3C.
- A thread dump at 118 s (`pres-4`) puts the main thread in D3DX `sub_002F4EBC`, called from `sub_000364D0` <- `sub_000367D0` <- `sub_00037090` <- `sub_00037010` <- `sub_00172030` <- ... <- the main loop `sub_0005F960`. It is not in the fence wait `sub_002E8110`.
- At that point the device has submitted fence 0x3141 and the executor has released 0x313F. The last release is still sitting beyond PUT, because D3D has not kicked it off. Nothing is waiting on it.

#### Root cause (found afterwards): the lifter, not the GPU

`sub_002F4EBC` is D3DXCreateTextureFromFileInMemoryEx (15 arguments, `ret 0x3c`). It was spinning in the loop at 0x2F4F1F, which counts a NULL-ended mip list linked through +0x28 and compares against ebx. ebx should be 0 and was 0xFFFFFFFF, so the walk started at NULL and ran through low memory forever. The white frame is just the last clear before submission stopped.

ebx came back wrong from `sub_002F9B7D`, which tries seven image loaders in turn. The JPEG loader, `sub_002F89C3`, returned with esp 0x90 bytes too high:
- It uses MSVC's offset frame (`push ebp; lea ebp,[esp-0x70]` ... `add ebp,0x70; leave`).
- The translator only treated `mov ebp, esp` as owning a frame, so this function never published ebp.
- libjpeg's error recovery calls setjmp, and the lifted setjmp saves `g_seh_ebp`. It therefore stored the caller's frame in the jmp_buf.
- Every texture that is not a JPEG longjmps out of this loader, so each one resumed with the wrong ebp and returned with esp moved.

Fixed in the toolkit (`translator._func_has_offset_frame`). The regen adds the ebp publish at 258 call sites in 26 functions. Upstream draft: `analysis/upstream/10-offset-frame-setjmp.md`.

#### The next stop: PGRAPH 0x400B10

Past the title screen, the Swap path (`sub_002E8110` -> `sub_002E7E80`) kicks a PFB flush and then spins. Each pass reads PGRAPH register 0x400B10 and the device's fence value (`*(device+0x30)`, re-read every pass), and the loop exits once bits 2..6 of the register equal the fence shifted left by two, masked to `0x7C`.

Against plain RAM the register stays 0, so the wait only passes when the fence happens to be a multiple of 32. The ack tick now sets bits 2..6 to `(completed fence << 2) & 0x7C`, right after it publishes GET. It is written there, after the work has been consumed, rather than ahead of it.

This is an inference from the loop. The register's name and its other bits are not confirmed, and nothing else writes it. Reading it as "the GPU's copy of the last semaphore value has reached memory" fits the flush-then-wait shape. If another title reads 0x400B10 differently, this is the place to look.

#### Not a cycle: an unresolved stub inside sub_00044900

With both fixes, the title loads `z:\media\plcom_tex` and calls SetDisplayMode again. Then the main thread overflows its native stack in `sub_00046720`, the node walk (child +0x2C, sibling +0x30, attached object +4 rendered by `sub_00044220`). The guest stack repeats with a 0x110-byte period, which looked like a scene-graph cycle.

It is not one. Objects 0x01AD9CFC and 0x01AD9F3C are static data in the XBE section MDLPL, and a RAM dump at the crash shows the runtime tree is acyclic too. A POSIX port of `RECOMP_WATCH` (toolkit, `xbox_memory_layout.c`) showed the node links are never written during the recursion. `RECOMP_ABI_CHECK` around the `sub_00044220` call showed what does change: `sub_00044900(0x01AD9CFC)` returns with esp 0x84 low and ebx/esi/edi clobbered. `sub_00044220` then returns a stack address in edi, and `sub_00046720` re-walks from that garbage node.

Root cause, in the lifter. A lone int3 at 0x00044CFA (a switch default) makes the cc_boundary pass split `sub_00044900` into [0x44900, 0x44CFB) and [0x44CFB, 0x44F3E). The halves and their aliases branch into each other's interiors (0x449B7, 0x44C20, 0x44C80, 0x44CD0, 0x44DDA, 0x44E72). No pass registered those targets: the tail-jump pass looks only at `jmp`, the orphan pass only at gaps, and "leaves its function" is tested against the primary bodies, not the alias ranges. Each branch became a tail call to an unresolved stub, which does `esp += 4; return` as if the guest had executed `ret`. The display-list interpreter came back with its frame still on the guest stack.

Fix: toolkit `FunctionDetector._pass_branch_alias_closure` (`tools/disasm/functions.py`, tests in `test_branch_alias_closure.py`). Every jmp/jcc out of a primary body or an alias range whose target is a decoded instruction strictly inside another primary body becomes an alias entry ending at that body's end. The pass iterates to a fixpoint over the new aliases. In BLiNX 2 it adds 985 aliases, and 913 of the 994 unresolved stubs become real functions. Merged at toolkit `fd76080`; see upstream draft 11 and the `disasm-branch-alias-closure` change, which records it as `recomp-coverage` requirements.

After the regen (`pres-23`, 240 s, `RECOMP_PB_EXEC=1 RECOMP_STUB_LOG=1`), no stub is hit, and the intro movie dumps as before through its end card. The title loads `plcom_tex`, sets the display mode a second time, and starts on `stg0101_tex_us`. At about 119 s, `[CONTIG] arena exhausted` appears: the contiguous window is a bump allocator, and MmFreeContiguousMemory frees through the general heap, so per-stage textures are never returned. A worker thread then exits, and the main thread spins on the kernel with PUT == GET (task 6.5). The frames after the movie are black. The 3D batches there are still skipped as not screen-space (task 6.3).

## Decisions

### The fence is written by the executor, at the release

D3D programs SET_CONTEXT_DMA_SEMAPHORE (handle 0x8) and SET_SEMAPHORE_OFFSET (0) once. After that it sends BACK_END_WRITE_SEMAPHORE_RELEASE with each fence value, odd and increasing by 2, about 3 times a frame. The executor resolves the offset with `dma_resolve`, the same rule used for surfaces and vertex arrays. That gives 0x80000000, which is exactly the word at `*(device + 0x30)` that the fence wait spins on. The executor writes the value there when it reaches the method in the stream.

The DMA object's own base is not read, because nothing walks RAMHT or PRAMIN yet. For XDK D3D it covers physical memory from 0, so the first release is logged with its handle and offset. If a title breaks that assumption, the log line will show it. A release that would land on the loaded image is refused.

### The mirror becomes a fallback, decided per word

`fence_mirrors_tick` skips a mirror only when both hold:

- `RECOMP_PB_EXEC` is set and the executor has released at least once.
- The release landed on the same word the mirror follows: `get_ptr`, or its contiguous-window alias.

It says which case applies, once. So:

- With the executor off, nothing changes.
- Before the first release, which is a few fences at boot, the mirror still unblocks D3D init.
- If a title's semaphore points elsewhere, the mirror stays on and the log says why. This avoids a silent hang.

The cat-side `xbox_Nv2aMirrorFence(0x2F1FB8, 0x2C, 0x30)` stays registered for exactly this fallback. `pres-3` shows the handover, `fence word 0x80000000 now written by the executor; mirror off`, followed by 6,518 releases. In `pres-4`, the thread dump's `*(device + 0x30)` = 0x313F equals the executor's last release, so the fence advances only through the executor.

Alternative considered: unregister the mirror whenever `RECOMP_PB_EXEC` is set. This was rejected because it hangs D3D init if the executor ever falls behind the first fence wait, and it does nothing for a title whose semaphore is not where `dma_resolve` puts it.

### Seed the filtered icall file

`pipeline.sh disasm` used to pass the raw `icall_targets.json` straight to `--seed-functions`. Now, when the database exists, it runs `tools.recomp.icall_feedback seeds --xbe game_files/default.xbe --out analysis/icall_seeds.json`. The `--xbe` decode check supersedes the 16-byte alignment filter. disasm then seeds that output. The database path can be overridden with `ICALL_DB`. The toolkit module docstring (step 3) still shows seeding the raw database. That is worth an upstream note, together with the corrected survey names.

## 3D: scope, not built here

The intro needs none of this. Gameplay will. The survey says the title runs vertex programs (TRANSFORM_PROGRAM/CONSTANT/LOAD/START), register combiners (FACTOR0/1, ICW/OCW, CONTROL, SPECULAR_FOG), up to four texture stages (texture shader STAGE_PROGRAM/OTHER_STAGE_INPUT) and depth. The order to wire it in the executor:

1. **Vertex programs.** Capture TRANSFORM_PROGRAM words into a 136-slot microcode store at the LOAD cursor and constants into 192 vec4s at CONSTANT_LOAD. Run the program per vertex on the CPU. The parser in `src/d3d/d3d8_vsh.c` (`d3d8_vsh_parse`, which builds `NV2AVshInstruction` structs) is host-independent and can drive a small interpreter. Its HLSL emitter and D3DCompile path are Windows/D3D11 only. Apply VIEWPORT_SCALE/OFFSET and the w divide, then reuse the existing screen-space rasteriser. `batch_is_screen_space` stays as the fast path.
2. **Combiners.** `src/d3d/d3d8_combiners.c` decodes ICW/OCW into an evaluable form. Start with stage 0 plus the final combiner, per pixel, in the existing `put_pixel` path.
3. **Textures.** Stages 1-3 reuse the stage-0 sampler. Swizzled and DXT formats go through `src/d3d/d3d8_swizzle.h`, which the executor already includes.
4. **Depth.** A zeta surface from SET_SURFACE_ZETA_OFFSET, DEPTH_TEST/MASK/FUNC, and CLIP_MIN/MAX.

This work has moved out of this change. Step 1 is `render-vertex-programs` (a CPU interpreter kept as a correctness reference, with a stopping rule). Real-time rendering is `render-gpu-backend` (pgraph to D3D11, DXVK under Proton; `src/d3d/nv2a_pb_d3d11.c`). On macOS the CPU rasteriser renders and the SDL2 window presents the frame (P2, with BMP dumps); a Metal GPU render backend is `render-gpu-backend` tasks §4.

## Risks

- **The executor is CPU-bound and runs on the ack thread.** At 640x480 with full-screen movie quads it keeps up, at about 710 M pixels in 90 s. 3D will not keep up without the D3D11 path.
- **The fence is now only as fast as the executor.** If the walk ever drops a segment (for example a ring wrap guessed wrong before the bounds are learned), the fence for that segment is never written and D3D waits. Before this change the mirror would have hidden that.
- **The DMA-object base is assumed to be 0** (see above). The first-release log line is the check.
