Each slice lands in a toolkit worktree off `posix-host/portability`.

- Estimates are in agent-days.
- Stock behaviour is unchanged until task 7: the build option and the
  `apu_dsp` key default OFF.
- Mac runs use Metal and `SDL_AUDIODRIVER=dummy`, with captures under
  `runs/`.
- Deck and Windows runs need a slot from the orchestrator.
- **Gates for every slice before its merge:**
  - the Mac build with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`;
  - `tests/posix_ctest.sh <build-dir>` with 0 FAIL;
  - in cat, `uv run pytest scripts` and `uv run ruff check . && uv run ruff format --check .`;
  - a review of each merge, with its fixes going back to the slice's agent;
  - a Proton run on the Deck for every slice that touches the runtime or audio (tasks 2–6).

## 0. Spike, done

- [x] 0.1 Probe: dsp56300 1.0.0 behind the stub, `APU_DSP_PROBE` modes 1 and 2. Toolkit `spike/apu-dsp` `7fc03472`, **probe only**.
- [x] 0.2 Mac cost on JSRF in mode 1: GP 2 µs per frame and EP 22–30 µs per EP frame. flips/s unchanged.
- [x] 0.3 Found and worked around the callback invalidation crash and the EP recompile storm.
- [x] 0.4 SSX 3 WAV scan: clean after boot, so the cause is not in the APU's mix on the Mac.

## 1. Gate and build (1.5 days)

- [ ] 1.1 `XBOXRECOMP_APU_DSP` CMake option, default OFF. Fetch the dsp56300 release archive per target, with sha256 pins and `CoreFoundation`/`Security` on Apple.
- [ ] 1.2 `apu_dsp` config key: the toolkit row `APU_DSP` (variable `RECOMP_APU_DSP`, 0 = stub, 1 = DSP) in `RECOMP_ENV_KEYS` (`src/platform/recomp_env.h`, parsed by `recomp_env.c`), with its `env.md` row. Check that it does not collide with `apu_dsp_ack` or `RECOMP_APU_DSP_ACK`.
  - With `apu_dsp=1`, force `apu_dsp_ack` off and ignore `apu_mixdown_all`. Log one line if the user set either (design decision 8).
  - Targets without a dsp56300 archive (iPadOS) build with the option OFF.
- [ ] 1.3 Link check of the `x86_64-pc-windows-gnu` archive with llvm-mingw in the wizard builder. If it fails, build the static library from the pinned source tag in the builder image. *Spike: links with llvm-mingw 20260922 on the Mac given `-l:libunwind.a ws2_32 userenv ntdll bcrypt advapi32 kernel32 synchronization`; the builder image still needs the same check.*
- [ ] 1.4 Licences of the prebuilt archive. It bundles the Rust std and the crates of `dsp56300-emu`, not only dsp56300.
  - List the licences of the linked crates from `Cargo.lock` at the pinned v1.0.0 tag, with `cargo-about` (the repo ships `about.toml`) or `cargo-license`, skipping build and dev dependencies. Add the Rust std (MIT OR Apache-2.0).
  - Confirm none is GPL. *Spike: the archive's `THIRDPARTY-emu` lists only Apache-2.0 (some WITH LLVM-exception), MIT, Unicode-3.0 and Zlib; cbindgen (MPL-2.0) is build-only.*
  - Add the texts to toolkit `LICENSES/` (dsp56300 MIT, Apache-2.0, the LLVM exception, Unicode-3.0, Zlib), list the crates in `NOTICE`, and add a line to each game repo's `NOTICE`.
- [ ] 1.5 Write the `apu-dsp` capability spec, `specs/apu-dsp/spec.md`: the build option, the key, the default-OFF guarantee, the key interactions (design decision 8) and the stats key.

## 2. Device model (3 days)

- [ ] 2.1 Port `gp_ep.c` and `dsp_dma.c` (LGPL-2.1+, headers kept) into `apu_dsp_emu.c` behind `apu_dsp_emu.h`. The header exposes no dsp56300 types.
- [ ] 2.2 Bootstrap from the GPRST/EPRST poll, and map the mixbuf to X:0x1400.
- [ ] 2.3 Find the mode 2 fault: buffer 0xD, the `next_block`=0 read and the PC leaving PRAM. Use `dsp56300-disasm` on the dumped PRAM and trace the last DMA and peripheral accesses before the jump. Report any core bug upstream.
- [ ] 2.4 ctest: a tiny hand-assembled GP program DMAs a block and writes the mixbuf. Check the words and the DMA status bits.

## 3. GP output path (3–4 days)

- [ ] 3.1 With `apu_dsp=1`, skip `mcpx_apu_dsp_ack_poll`. The GP answers the doorbell.
- [ ] 3.2 Take the output from the GP's output buffers instead of the stereo fold. The EP runs on `ep_frame_div`.
- [ ] 3.3 Surround: a 6-channel output to SDL when the GP or EP produces one, and a stereo downmix otherwise. This depends on the host audio layer: do it after the SDL3 move, or defer surround and ship the stereo downmix only in this change.
- [ ] 3.4 Cap the cycles per frame, with a logged counter, a one-line stats report, and an `APU_DSP_STATS` debug-tier key (`apu_dsp_stats` in `RECOMP_DEBUG`), with its `env.md` row.
- [ ] 3.5 Pre-warm the JIT at GPRST release, or run the first frames off the APU thread. Then check on the Deck that the boot starve is gone (the spike saw one 92 ms starve from a 16.6 ms EP compile burst).

## 4. ISTS bit 3 (0.5 day)

- [ ] 4.1 With the DSP on, disable `mcpx_apu_ssl_tick`'s set of `NV_PAPU_ISTS_SSLINTSTS` (`apu_core.c:1114`) on JSRF, B3 and SSX 3. Record whether any title stalls. Keep the tick only for the stub path if the bit turns out to be needed only there.

## 5. Per-title validation (2–3 days)

- [ ] 5.1 JSRF, BLiNX 2, SSX 3 and B3, on the Mac with `apu_dsp=1`:
  - **Pass:** the WAV scans match or beat the stub (gaps, clicks, repeats) and the APU stays real time (WAV length within 0.5% of wall time).
  - Effects are audible where the title uses them.
  - B3 front-end music plays (`B3XboxFx.bin`).
- [ ] 5.2 Goldens still pass with the option ON and the key at 0, which is stock: the Metal golden on the Mac and `blinx2 bench golden` (D3D11 under Proton).
- [ ] 5.3 Key-0 identity:
  - one scripted run (JSRF) on a build with the option OFF and on a build with the option ON and `apu_dsp=0`, with the WAV tap; the two WAVs match;
  - a ctest that the DSP hooks are no-ops when the key is 0.

## 6. x86-64 cost (1 day, Deck and Windows slots; 6.3 conditional)

- [ ] 6.1 After task 3, with a real GP load: `apu_dsp=1` and no host ack, the same scripted runs on the Deck under Proton and on native Windows, with DSP stats. Include B3's front end (`B3XboxFx.bin` music). Measure the GP's frame time, cycle-cap hits, flips/s and the WAV length against wall time.
  - **Pass:** the GP's p99 is below 50% of the 0.67 ms APU frame, there are no cap hits after boot, flips/s drops less than 25%, and the WAV is within 0.5% of wall time.
  - If not, task 6.3. If that fails too, stop and ask the user before any default change.
  - *Spike, Deck, idle GP (mode 1, host ack on): GP 6 µs mean, per-second worst frame p99 328 µs, flips/s unchanged. This does not replace the run above.*
- [x] 6.2 The tracker item follow-up in the same slot: the SSX 3 WAV and queue-depth trace on the Deck with the stub. *Host queue clean; the clicks line up with 41–71 ms guest frame stalls (design.md).*

## 7. Default decision (0.5 day)

- [ ] 7.1 With the 5 and 6 results, the user decides per game whether the release build turns `XBOXRECOMP_APU_DSP` ON and whether `apu_dsp` defaults to 1.

- [ ] 6.3 Conditional, only if 6.1 fails: run the GP and EP on their own thread, fed and drained through a ring of APU frames with one frame of latency. Re-run 6.1. About 2–3 days.

Total: about 12–17 agent-days for (e), plus 2–3 if task 6.3 is needed. Options (a), (a′) and (f) are excluded by the licence decision.
