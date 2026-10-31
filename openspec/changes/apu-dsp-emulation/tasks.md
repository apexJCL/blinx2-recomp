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

- [x] 1.1 `XBOXRECOMP_APU_DSP` CMake option, default OFF. Fetch the dsp56300 release archive per target, with sha256 pins and `CoreFoundation`/`Security` on Apple.
  - *Done (toolkit `apu-dsp/gate`): `cmake/dsp56300.cmake` pins all six v1.0.0 archives; `XBOXRECOMP_DSP56300_ARCHIVE` takes a local tarball (still sha-checked). A target without one (iPadOS, universal macOS, MSVC) warns and builds OFF; a failed download is a configure error. ctest `apu_dsp_link` runs the JIT; posix_ctest builds `template_main` with the option ON.*
- [x] 1.2 `apu_dsp` config key: the toolkit row `APU_DSP` (variable `RECOMP_APU_DSP`, 0 = stub, 1 = DSP) in `RECOMP_ENV_KEYS` (`src/platform/recomp_env.h`, parsed by `recomp_env.c`), with its `env.md` row. Check that it does not collide with `apu_dsp_ack` or `RECOMP_APU_DSP_ACK`.
  - With `apu_dsp=1`, force `apu_dsp_ack` off and ignore `apu_mixdown_all`. Log one line if the user set either (design decision 8).
  - Targets without a dsp56300 archive (iPadOS) build with the option OFF.
  - *Done: `apu_dsp_resolve` in `recomp_env.c`; ctest `apu_dsp_key` (built without the DSP, with it, and with it and its device). Until task 3 defines `XBOXRECOMP_APU_DSP_DEVICE` on `recomp_env` (PUBLIC) next to the device code, `RECOMP_APU_DSP=1` keeps the stub with a line.*
- [x] 1.3 Link check of the `x86_64-pc-windows-gnu` archive with llvm-mingw in the wizard builder. If it fails, build the static library from the pinned source tag in the builder image. *Spike: links with llvm-mingw 20260922 on the Mac given `-l:libunwind.a ws2_32 userenv ntdll bcrypt advapi32 kernel32 synchronization`; the builder image still needs the same check.*
  - *Mac half done on `apu-dsp/gate`: `tests/apu_dsp_link` cross-builds with llvm-mingw 20260922 and the cmake file's link libraries; the exe imports only system DLLs. The wizard builder-image check is still open.*
  - *Carried over into `dsp-default-on` (2026-10-30): with the DSP on by default, every Windows exe links the archive. The PC's native llvm-mingw builds (`build-all`, gate 1.10) and the release wizard's end-to-end test on wizard-built Windows exes cover the builder link.*
- [x] 1.4 Licences of the prebuilt archive. It bundles the Rust std and the crates of `dsp56300-emu`, not only dsp56300.
  - List the licences of the linked crates from `Cargo.lock` at the pinned v1.0.0 tag, with `cargo-about` (the repo ships `about.toml`) or `cargo-license`, skipping build and dev dependencies. Add the Rust std (MIT OR Apache-2.0).
  - Confirm none is GPL. *Spike: the archive's `THIRDPARTY-emu` lists only Apache-2.0 (some WITH LLVM-exception), MIT, Unicode-3.0 and Zlib; cbindgen (MPL-2.0) is build-only.*
  - Add the texts to toolkit `LICENSES/` (dsp56300 MIT, Apache-2.0, the LLVM exception, Unicode-3.0, Zlib), list the crates in `NOTICE`, and add a line to each game repo's `NOTICE`.
  - *Done: the closure of `dsp56300-emu-ffi`'s normal dependencies in `Cargo.lock` at v1.0.0 (57 crates plus std), no GPL. Toolkit `NOTICE` and `LICENSES/`; this repo's `NOTICE`. The other game repos' `NOTICE` lines follow when they turn the option on (task 7.1).*
- [x] 1.5 Write the `apu-dsp` capability spec, `specs/apu-dsp/spec.md`: the build option, the key, the default-OFF guarantee, the key interactions (design decision 8) and the stats key.
  - *Done: `specs/apu-dsp/spec.md`.*

## 2. Device model (3 days)

- [x] 2.1 Port `gp_ep.c` and `dsp_dma.c` (LGPL-2.1+, headers kept) into `apu_dsp_emu.c` behind `apu_dsp_emu.h`. The header exposes no dsp56300 types.
  - *Done (toolkit `apu-dsp/device` `4114ef61`): built only with `XBOXRECOMP_APU_DSP`; `NOTICE` lists both files. A descriptor xemu would assert on (format, control bits, buffer, interleave, range) is refused: EOL set, logged with a 32-entry trace of DMA register writes and descriptors. Format 0 (8-bit) is refused too, and a chain longer than 0x800 descriptors is refused as a loop.*
  - *Review fixes (`9564d87f`): the glue to the core (peripheral decode, memory map, bootstrap) is rewritten from the hardware facts only, since xemu's `dsp.c` and `dsp_jit.c` are GPL-2.0+; the header says so. Unmapped peripheral words read 0.*
- [x] 2.2 Bootstrap from the GPRST/EPRST poll, and map the mixbuf to X:0x1400.
  - *Done (`4114ef61`, `a4f16c94`): X:0x1400–0x17FF aliases X:0xC00–0xFFF, as in xemu's map. The core starts in reset whatever the window holds, because JSRF writes GPRST=3 before the device exists.*
- [x] 2.3 Find the mode 2 fault: buffer 0xD, the `next_block`=0 read and the PC leaving PRAM. Use `dsp56300-disasm` on the dumped PRAM and trace the last DMA and peripheral accesses before the jump. Report any core bug upstream.
  - *First reading (superseded): a probe bug, not a core bug. The spike mapped X:0x1400 to a separate buffer instead of aliasing X:0xC00. On DSOUND's second command 3, the effect code it had just loaded started a chain at X:0x19F, which was all zeros without the alias. The spike then ran that chain from block 0 (the dsstdfx header read as a descriptor) and wrote 0x3EF8 words across X, Y and P, so the PC left PRAM.*
  - *A/B on JSRF mode 2 (`runs/apu-dsp/e3-m2`, `e4-noalias`). With the alias, the GP answers every doorbell, loads 7024 P words and runs about 42k cycles a frame, with no capped frames and no rejects; the title runs 5074 flips and the GP output is audible. Without it, the descriptor is refused and the title stalls at 42 flips, as in the spike. The EP sets OMR SEN (stack extension), which the core logs as unimplemented; no fault came from it.*
  - *Reopened: the A/B above is confounded. Re-runs on the same build, with `a4f16c94` and with `9564d87f` alike (`runs/apu-dsp/e8-old`), stall at 42 flips with the alias in place. What differs is DSOUND's doorbell order, which varies from run to run: in `e3-m2` the first command 3 is followed by nothing until the second; in the stalled runs (and in `e4-noalias`) a command 2 follows it (doorbell 3, 2, 0 over frames 2–4, with new parameters in X:0–0xF). By the second command 3, X:0x133–0x283 is cleared, the chain at X:0x19F is zeros, and X:6 holds a format 5 descriptor (control 0x5442), so both are refused. The alias is right on the hardware facts, but whether its absence caused the spike's fault is unproven; what the GP's command 2 handling (or the host between the commands) should leave in X is the open question, tracked in the tracker item.*
  - *Cause: neither the core nor the device. The second command 3 is DirectSound's GP/EP restart, which our ISTS bit 3 tick sets off (task 4). The GP kernel and the effect code are the same in both orders; what differs is the scratch image the restart reloads.*
    - *The effect code at P:0x171 runs its init only while bit 0 of X:0x84 (its flags word) is clear, sets the bit, and in that init builds the DMA descriptors at X:0x133–0x283. The image holds 2 there.*
    - *DirectSound's effect commit (JSRF `sub_001A2034`) reads the effect state back from the live GP (`sub_001A1B18`), ORs bit 2 (update) into the flags, writes it into the scratch image (`sub_001A1A6F`, deferred) and sends command 2 (`sub_001A1905`). The image now holds 7: init already done.*
    - *The ISTS bit 3 handler (`sub_001A2638` sets the request, the worker `sub_001A23CD` calls `sub_001A1F5D`) writes 0 to GPRST and EPRST, restores the saved command block (`sub_001A1747`) and rings command 3 against that image. The effect code skips its init, the descriptors stay zero and the chains at X:0x19F and X:0x13D are refused.*
    - *When the commit comes after the restart (`e3-m2`), the restart reloads 2 and the init runs again, so that order passes. On hardware the GP keeps pace and the restart should not happen.*
  - *Fix (toolkit `apu-dsp/cmd2` `6d379fa4`): `mcpx_apu_ssl_tick` does not fire while `gp_emulated` is set; the code that runs the GP sets it (the probe now, task 3.1 later). ctest `apu_ssl` case 6. Probe runs with the gate (`runs/apu-dsp/g1`–`g4`): see the tracker item.*
- [x] 2.4 ctest: a tiny hand-assembled GP program DMAs a block and writes the mixbuf. Check the words and the DMA status bits.
  - *Done: ctest `apu_dsp_emu` covers a circular scratch read with writeback, FIFO 0 output, the CONTROL and EOL bits, the mixbuf alias, a host P patch, a refused buffer-0xD descriptor, a refused format 0, a self-linked descriptor refused as a chain loop, reset, and GPRST already set at create.*

## 3. GP output path (3–4 days)

- [x] 3.1 With `apu_dsp=1`, skip `mcpx_apu_dsp_ack_poll`. The GP answers the doorbell. Define `XBOXRECOMP_APU_DSP_DEVICE` on `recomp_env` (PUBLIC) next to the device code: until then `RECOMP_APU_DSP=1` keeps the stub (task 1.2), and the `apu_dsp_key` device variant tests the overrides. The GP runner sets `MCPXAPUState.gp_emulated` while the GP runs, so the ISTS bit 3 tick stays off (task 2.3).
  - *Done (toolkit `apu-dsp/output`): `src/apu/apu_dsp_run.c` runs the GP and EP on their MCPX window pages (`xbox_McpxHost()` + 0x30000 / 0x50000); `src/apu/CMakeLists.txt` builds it with the JIT and defines `XBOXRECOMP_APU_DSP_DEVICE` on `recomp_env`. `mcpx_apu_dsp_ack_poll` returns at once with the key on. GPRST/EPRST are polled from the window each frame; the probe's "start the GP at the first doorbell" fallback is gone (JSRF's GPRST reaches the window).*
- [x] 3.2 Take the output from the GP's output buffers instead of the stereo fold. The EP runs on `ep_frame_div`.
  - *Done: each frame writes the 32 mixbins to X:0x1400 as 24-bit words, runs the GP, and takes left/right from X:0x1400/X:0x1420 (xemu's monitor point GP). Frames before the title starts the GP are silent. The EP runs when `ep_frame_div % 8 == 0`; an EPRST change sets `ep_frame_div` to 0; its FIFO 0 period is sunk, as xemu does.*
- [x] 3.3 Surround: a 6-channel output to SDL when the GP or EP produces one, and a stereo downmix otherwise. This depends on the host audio layer: do it after the SDL3 move, or defer surround and ship the stereo downmix only in this change.
  - *Decided (orchestrator, 2026-10-21): stereo only in this change; 6-channel output waits for the SDL3 move: the tracker item (under the tracker item, blocked by the tracker item).*
- [x] 3.4 Cap the cycles per frame, with a logged counter, a one-line stats report, and an `APU_DSP_STATS` debug-tier key (`apu_dsp_stats` in `RECOMP_DEBUG`), with its `env.md` row.
  - *Done: GP cap 2 × 106,667 cycles (two frames of a 160 MHz GP), EP cap 16 × that. `apu_dsp_stats` prints one `[APU DSP]` line a second (frames, cycles avg/max, host us avg/max, cap hits, DMA blocks and refusals, and the warm-up's skipped and late frames as totals, see 3.5). Whatever the key, new cap hits or skipped or late warm-up frames get a summary line at most every 10 s, besides the core's first four per-hit lines.*
- [x] 3.5 Pre-warm the JIT at GPRST release, or run the first frames off the APU thread. Then check on the Deck that the boot starve is gone (the spike saw one 92 ms starve from a 16.6 ms EP compile burst).
  - *First pass (`afadaf33`): the library has no precompile call, so for 188 EP periods (about 1 s) after each EP bootstrap the EP ran on a worker thread; a period that found it busy was skipped and counted (its output is not heard yet). The GP was left inline, on the spike's worst GP compile of 3.9 ms; the Deck check below showed its first frame takes 522 ms, so the GP now gets the same warm-up (the third bullet).*
  - *Deck check (2026-10-21, toolkit `afadaf33`, runs/apu-dsp/deck304): the EP warm-up works (max 65 ms on the worker, 15 periods skipped, none heard), but the starve is still there. The first GP frame took 522 ms inline, the GP program's first JIT compile, and caused one 516 ms starve at boot; the stock run of the same exe has none. Nothing after boot: GP max 1.8 ms, EP max 0.5 ms, no cap hits. The silence before 30 s, the gaps near 50 s and the clicks after 100 s are in the stock WAV too (Deck and Mac), so they are the game's. Still open: the GP's first frames need the same treatment as the EP's.*
  - *Done (toolkit `7582d4a3`): the GP gets the same warm-up, 1500 frames on its worker after each bootstrap, and the APU thread now waits for each worker frame (GP and EP) at most 3 ms. A GP frame that misses the wait, and those that find the worker still compiling, are silent and counted (`skipped`/`late`). Without the wait the first re-check (`b882dafa`) had no starve but lost 7 GP frames in 8 for about 7 s, because the APU thread makes its frames in bursts. ctest `apu_dsp_warm` checks the schedule with a fake worker and clock.*
  - *Deck re-check (2026-10-21, exe `81abf6a9`, runs/apu-dsp/deck304b d5-on/d4-stock): 0 starves and 0 underruns with the DSP on, as stock. 991 GP frames skipped during the 549 ms first compile and 6 late, 1500 frames a second from t=2 s. On the Mac (o5/o4, back to back) ON and stock both show 9 underruns and 2–3 starves; the earlier 21 (o1) ran during another agent's Docker ctests, and a stock run under load (o2) had 744, so they are host load on the dummy driver, not the device.*
- [x] 3.6 Mirror the window's GPMIXBUF page (+0x5000) from X:0xC00–0xFFF, so a title or the host that reads the mixbuf through the window sees what the GP wrote.
  - *Done: after each GP frame `apu_dsp_emu_run_frame` copies X:0xC00–0xFFF to window +0x5000; ctest `apu_dsp_emu` checks the page after two frames.*
- [x] 3.7 Skip the DMA trace entry for a descriptor that repeats the one before it. A chain-loop reject now dumps 32 identical "block" lines, which push out the register writes that set `next_block`.
  - *Done: an entry equal to the one before it (same frame) adds to that entry's repeat count, printed as `(xN more)`; ctest `apu_dsp_emu` checks a looping chain (0x801 walks) takes one entry.*

## 4. ISTS bit 3 (0.5 day)

- [x] 4.1 With the DSP on, replace `mcpx_apu_ssl_tick`'s set of `NV_PAPU_ISTS_SSLINTSTS` with a model of when the hardware raises it, and run JSRF, Black, B3 and SSX 3 with it. Record whether any title stalls. The stub path keeps its tick.
  - *JSRF done: with the GP emulated the tick must stay off, and the title runs without it (task 2.3). Black, B3 and SSX 3 remain. Black needs the first interrupt to finish its DirectSound init on the stub, so it must be run with the GP on.*
  - *the tracker item: the stand-in is replaced by the GP lag model (design.md, "ISTS bit 3"). The bit rises when the emulated GP falls SSL samples behind its 106,667-cycle frames; the stub keeps its once-per-start tick. Ctest `apu_ssl` cases 6–7d cover it, including lag built while the counter is off or before a restart (7c, 7d). Frames stopped at the cycle cap add no lag.*
  - *Runs (Mac, Metal, dummy audio, WAV tap; `runs/apu-dsp/h1`–`h7`), with `RECOMP_APU_DSP=1`:*

    | Title | Run | Sequencer starts | `ssl` raised | Result |
    |---|---|---|---|---|
    | B3 | h1, 330 s | 1 (h3 trace, 90 s) | 0, lag 0 | 19,801 flips (60/s), no stall, real time |
    | SSX 3 | h6, 150 s | 1 (h5 trace, 90 s) | 0, lag 0 | 7,132 flips into the race, no stall |
    | JSRF | h7, 120 s | 1 (no trace: its only restart is the bit 3 path, `sub_001A1F5D`, and the bit never rose) | 0, lag 0 | 7,048 flips, no stall, so no regression |
    | Black | — | — | — | not run: no Black dump on the Mac or the Linux/Proton host. It was tested upstream (5e40efb1). |

    *GP cycles per frame stay well under the frame: B3 44k, SSX 3 8.3k, JSRF 42k, and none hit the cap. On the stub, B3 and SSX 3 restart the sequencer 23 times a second (h2 and h4 traces: 2,111 and 2,108 starts in 90 s). Their restart writes SECTL 0x7, which has XCNTMODE off, so the once-per-start tick re-arms on every restart. Stock behaviour is unchanged here. Black: the tracker item.*
- [x] 4.2 On the stub (stock), start the sequencer a bounded number of times per boot. Only a SECTL write of 0 re-arms the stub's tick. A counter-only toggle (0xF, 0x7, 0xF), which is how B3, SSX 3 and BLiNX 2 recover, does not. JSRF's and Black's first interrupt must still come, and JSRF's starts and audio must not change. This changes stock BLiNX 2 (design.md, "The stub's re-arm").
  - [x] 4.2.1 Ctest `apu_ssl` case 2c covers B3-style restarts, which give no fire. Case 3 covers the init shape (SECTL 0), which fires, and a B3 recovery after the ack, which does not. Case 7d now restarts with the B3 shape (SECTL 0x7, then 0xF): it shows that the emulated GP's lag still restarts on a counter-only write, which never re-arms the stub.
  - [x] 4.2.2 BLiNX 2 and JSRF on the Mac: sequencer starts before and after, and the WAV taps compared. Then BLiNX 2's Metal golden and its D3D11 golden on the Linux/Proton host.
    - *Done (`runs/apu-stub`, removed 2026-10-21 after the merge; 90 s, Metal, dummy audio with the WAV tap). BLiNX 2: 2087 SSL writes and 2086 ISTS acks of 0x9 before, 2 and 1 after; 50.2 flips/s both; WAV rms 1049 against 1048, the same 4 silent gaps, no clicks. JSRF: 2 starts both, 58.4 flips/s both, the WAVs identical. Metal golden: attract, stage1 and story pass. The Linux/Proton host D3D11: attract and stage1 pass; story is INCONCLUSIVE ("cpu stall ~8.5%") on the before exe too, so that is the host's baseline.*
  - [x] 4.2.3 On the Deck, before and after: SSX 3 frame stalls, and B3 and BLiNX 2 flips/s.
    - *Done (300 s each, GE-Proton11-7, D3D11, on screen with sound). B3: 60.0 flips/s in every 30 s window both ways, one flip gap over 100 ms both. BLiNX 2: the same windows (59.8, 30, 30, 30, 40), 7 against 6 gaps over 100 ms. SSX 3: 8 flip gaps over 50 ms after against 10 before (max 443 against 490 ms). No audio starves or underruns in any run, and the WAVs have the same gaps. The restarts were cheap on the Deck: removing them neither fixes nor worsens the tracker item.*

## 5. Per-title validation (2–3 days)

- [x] 5.1 JSRF, BLiNX 2, SSX 3 and B3, on the Mac with `apu_dsp=1`:
  - **Pass:** the WAV scans match or beat the stub (gaps, clicks, repeats) and the APU stays real time (WAV length within 0.5% of wall time).
  - Effects are audible where the title uses them.
  - B3 front-end music plays (`B3XboxFx.bin`).
  - *Carried over into `dsp-default-on` (2026-10-30): each game's PC smoke and `audio_check` paired with a stub run, the Metal pair on the Mac, and the user's listen (its D6 and tasks 3.x). B3's front-end music is part of its task 3.5.*
- [x] 5.2 Goldens still pass with the option ON and the key at 0, which is stock: the Metal golden on the Mac and `blinx2 bench golden` (D3D11 under Proton).
  - *Superseded by `dsp-default-on` (2026-10-30): key 0 is no longer stock, and the user dropped goldens for the DSP change.*
- [x] 5.3 Key-0 identity:
  - one scripted run (JSRF) on a build with the option OFF and on a build with the option ON and `apu_dsp=0`, with the WAV tap; the two WAVs match;
  - a ctest that the DSP hooks are no-ops when the key is 0.
  - *Partly carried over, partly dropped (2026-10-30). The ctest half goes to `dsp-default-on` tasks 1.4 and 1.5: `apu_dsp_key` cases for `0`, and the stub tests run with `RECOMP_APU_DSP=0` in a DSP build. The WAV identity run is dropped: the stub is no longer the stock path, so key-0 identity with an OFF build no longer guards stock behaviour.*

## 6. x86-64 cost (1 day, Deck and Windows slots; 6.3 conditional)

- [x] 6.1 After task 3, with a real GP load: `apu_dsp=1` and no host ack, the same scripted runs on the Deck under Proton and on native Windows, with DSP stats. Include B3's front end (`B3XboxFx.bin` music). Measure the GP's frame time, cycle-cap hits, flips/s and the WAV length against wall time.
  - **Pass:** the GP's p99 is below 50% of the 0.67 ms APU frame, there are no cap hits after boot, flips/s drops less than 25%, and the WAV is within 0.5% of wall time.
  - If not, task 6.3. If that fails too, stop and ask the user before any default change.
  - *Spike, Deck, idle GP (mode 1, host ack on): GP 6 µs mean, per-second worst frame p99 328 µs, flips/s unchanged. This does not replace the run above.*
  - *Done in part by the tracker item: KUF with a real GP load on the Deck under Proton and on native Windows, with GP+EP well under 1 ms per APU frame, no cap hits and no added dropouts. The per-game measurements are carried over into `dsp-default-on` D6: flips/s and GP/EP average and maximum per game on the PC and the Mac, plus a non-blocking Deck pair.*
- [x] 6.2 The tracker item follow-up in the same slot: the SSX 3 WAV and queue-depth trace on the Deck with the stub. *Host queue clean; the clicks line up with 41–71 ms guest frame stalls (design.md).*
- [x] 6.3 Conditional, only if 6.1 fails: run the GP and EP on their own thread, fed and drained through a ring of APU frames with one frame of latency. Re-run 6.1. About 2–3 days.
  - *Superseded (not needed): the tracker item found no cap hits, and the JIT costs at most about 4% of one Deck core. A game that fails the `dsp-default-on` check falls back to the stub (its D6) instead.*

## 7. Default decision (0.5 day)

- [x] 7.1 With the 5 and 6 results, the user decides per game whether the release build turns `XBOXRECOMP_APU_DSP` ON and whether `apu_dsp` defaults to 1.
  - *Answered by the user on 2026-10-30: ON at build time and on at run time for every game, now and for new games. Implemented by `dsp-default-on`.*

Total: about 12–17 agent-days for (e), plus 2–3 if task 6.3 is needed. Options (a), (a′) and (f) are excluded by the licence decision.
