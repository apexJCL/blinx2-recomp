## Why

BLiNX 2's movies are CRI Sofdec (MWSFD/XBOX 3.03, CRI SFD 1.887), not Bink: 64 `.sfd` files (MPEG-1, 640x448 or 640x480, 59.94 fps) plus ADX/AIX audio, interleaved or as sidecar files (`analysis/research/blinx2-internals-and-fmv.md`). The translated CRI code already decodes them on the CPU, converts to YUV 4:2:2 and writes a linear YUY2 (0x24) or UYVY (0x25) texture. The executor draws that texture with BT.601 conversion, and the intro plays on both hosts.

This change is mostly a decision record, so that nobody replaces a decoder that works, and so that movie frames do not pollute performance numbers.

## What Changes

- **Decision:** movies stay guest-decoded by the translated Sofdec code. This matches what UnleashedRecomp does with CRI on the Xbox 360.
- **Later optimisation:** do the YUY2/UYVY to RGB conversion on the GPU (in `render-gpu-backend`) instead of on the CPU at texture upload.
- **Fallback only:** HLE `mwPly*` with ffmpeg (`mpeg1video` + `adpcm_adx`), if guest decode turns out too slow or A/V sync misbehaves once audio exists.
- The runtime tags movie windows, so that `bench-methodology` can exclude them.
- A cheap check that the PVIDEO overlay is not used (no MMIO writes to `0xFD008000`-`0xFD008FFF` during a movie).

## Capabilities

### New Capabilities
- `fmv-playback`: how movies are decoded and presented, and how movie windows are marked for measurement.

### Modified Capabilities
<!-- none -->

## Impact

- Toolkit: the file I/O layer (movie-window tagging), `src/kernel/nv2a_pb_exec.c` (unchanged YUV sampler).
- No change to the decoder or to generated code.
- A/V sync depends on `audio`: Sofdec uses audio as the master clock (xemu #1118 is the failure mode).
