## 1. Decision record

- [x] 1.1 Identify the middleware: Sofdec MWSFD/XBOX 3.03 and ADX, no Bink or XMV (`analysis/research/blinx2-internals-and-fmv.md`).
- [x] 1.2 Movie frames draw through the executor's YUV sampler (BT.601) on macOS and Proton (`present-frames`, Proton run 3).

## 2. Measurement support

- [ ] 2.1 Log the open and close of `movie\*.sfd` with timestamps (one line each).
  - Filed with `audio` 6.x as the tracker item (2026-11-03).
- [ ] 2.2 Log MMIO writes to `0xFD008000`-`0xFD008FFF` during a movie, and record the result.
  - Dropped: movies draw correctly through the texture path on every backend, so the check has no open question to answer.

## 3. Later

- [ ] 3.1 With `render-gpu-backend`: convert YUY2/UYVY on the GPU instead of at upload.
  - Dropped: no measured cost of the upload conversion; reopen as an item if a profile shows one.
- [ ] 3.2 With `audio`: compare the ADX position with the video frame index, and look for the xemu #1118 symptom (video frozen, audio looping).
  - Filed as part.
- [ ] 3.3 Only if guest decode is too slow or A/V sync fails: propose the ffmpeg fallback as its own change.
  - Dropped: conditional on 3.2 failing; the tracker item records it if it does.
