## Why

After `xdk-library-hle`, BLiNX 2 runs for 240 s on macOS arm64 with no crash. The main loop runs on the 60 Hz vblank callback, the intro MPEG streams, and the translated XDK D3D writes NV2A pushbuffers into memory that is backed but that nothing reads. Nothing is presented.

Two things were also dishonest:

- The D3D completion fence was mirrored (submitted -> completed) from the NV2A ack thread at the top of each tick, before anything had read the commands. This is the same lost-command race that the DMA_GET comment in `xbox_memory_layout.c` describes.
- `scripts/pipeline.sh` seeded the raw icall feedback database (`icall_targets.json`). The toolkit says to seed only the filtered `icall_seeds.json` (`docs/technical/indirect-calls.md`, "Seed `icall_seeds.json`, not `icall_targets.json`").

A pair review chose the toolkit's existing pushbuffer walker as the presentation path. D3D entry points are not overridden.

## What Changes

- Run the toolkit pushbuffer executor (`src/kernel/nv2a_pb_exec.c`, `RECOMP_PB_EXEC`). It is fed by DMA_PUT polling in `xbox_memory_layout.c`. It clears surfaces and rasterises screen-space batches into the guest framebuffer, and frames come out as BMPs (`RECOMP_FB_DUMP`) or in the Windows window (`RECOMP_FB_WINDOW`). That window, and since P2 the macOS SDL2 window (`fb_present_sdl.c`), is Present only: the CPU rasteriser renders.
- Toolkit: the executor implements `NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_SEMAPHORE_OFFSET` and `NV097_BACK_END_WRITE_SEMAPHORE_RELEASE`. The fence word is written when the executor consumes the release.
- Toolkit: `fence_mirrors_tick` steps aside for any mirror whose fence word is the semaphore target, once the executor has released onto it. With the executor off, the mirror still runs as the fallback.
- Toolkit: the survey's method-name table (`nv2a_pb_scan.c`) is corrected against `nv2a_regs.h`. `SET_TRANSFORM_PROGRAM` and `SET_TRANSFORM_CONSTANT` were swapped. `0x0130` is FLIP_STALL, `0x1808` is ARRAY_ELEMENT32, `0x1818` is INLINE_ARRAY, and `0x1D6C` is SET_SEMAPHORE_OFFSET.
- cat: `src/main.c` keeps `xbox_Nv2aMirrorFence` registered as the fallback, and its comment now says so.
- cat: `scripts/pipeline.sh disasm` regenerates `analysis/icall_seeds.json` from the database (`icall_feedback seeds --xbe`) and seeds that file instead of the raw database.

## Capabilities

### New Capabilities
- `present-frames`: how a translated title's NV2A pushbuffer is consumed to produce frames, and how the GPU fence tracks that consumption.

### Modified Capabilities
<!-- none -->

## Impact

- **Toolkit (`present/pb-exec`):** `src/kernel/nv2a_pb_exec.c`, `src/kernel/nv2a_pb_scan.c`, `src/kernel/xbox_memory_layout.c`. The behaviour change is gated on `RECOMP_PB_EXEC`. With it unset, the fence mirror behaves exactly as before.
- **cat (`present/pb-exec`):** `src/main.c` (comment only), `scripts/pipeline.sh` (disasm seeding).
- **Regeneration:** none for this change. The seeding fix takes effect at the next disasm, and today no icall database exists, so the next disasm output is unchanged.
- **Proton:** the executor and the semaphore are host-independent C and cross-compile with llvm-mingw. The Windows window (`RECOMP_FB_WINDOW`) and a run with `RECOMP_PB_EXEC=1` still need a bench run.
