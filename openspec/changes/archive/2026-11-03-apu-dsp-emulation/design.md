## Context

### The hardware and the frame

The APU runs at 1500 frames/s, 32 samples per frame, with 32 mixbins.

- **VP:** sums the voices into the mixbins.
- **GP:** a DSP56300 at about 160 MHz. It reads the mixbins, applies
  effects and writes the outputs. Its budget is about 106k cycles per
  frame.
- **EP:** runs once every 8 frames (256 samples, 187.5 frames/s) and
  encodes AC-3.

The DSP memory windows are at MCPX +0x30000 (GP) and +0x50000 (EP). Each
DSP word is one uint32:

| Region | Offset in window |
|---|---|
| X | +0 |
| GP mixbuf (X:0x1400) | +0x5000 |
| Y | +0x6000 |
| P | +0xA000 |
| GPRST/EPRST | +0xFFFC |

### What the toolkit has today (xboxrecomp `4559bae9`)

| Piece | Where | State |
|---|---|---|
| MMIO trap | `xbox_memory_layout.c:796` (`APU_TRAP_BYTES` 0x30000) | Covers only +0..0x30000. The GP and EP windows are plain RAM on every host, so the title's image uploads and GPRST writes land in memory, and nothing sees them. The trap stops there because of the B3 `rep movsd` fault, per the comment in the same file. |
| GPRST | `apu_dsp.c:173` `mcpx_apu_dsp_gprst_write` | A shadow only, reached through the trapped register path. |
| Doorbell | `apu_dsp.c:210` `mcpx_apu_dsp_ack_poll`, from `apu_core.c:1262` | The host fakes the GP's command ack. |
| GP stage | `apu_dsp.c:324` `mcpx_apu_dsp_frame`, from `apu_core.c:1175` and `:1183` | A fixed stereo fold (`MIXDOWN_TWO_BINS`/`STAGED`/`UNITY`, `apu_dsp.c:113`). JSRF tuning notes say its 3D effects sit on bins 6–10 (`apu_dsp.c:362`). |
| EP | `ep_frame_div` (`apu_core.c`) | Divides the frame clock only. No EP program runs. |
| ISTS bit 3 | `apu_core.c:1102` `mcpx_apu_ssl_tick`, sets `NV_PAPU_ISTS_SSLINTSTS` at `:1114` | A heartbeat. See below. |

**Missing for real emulation:**

1. a DSP56300 core;
2. the GP/EP device model: DMA, the interrupt and semaphore registers,
   the GPRST bootstrap, the mixbuf mapping;
3. a way to see the title's writes to the windows, either by polling
   GPRST from the frame thread, as the probe does, or a narrow trap on
   the RST words only;
4. the real doorbell path, with the GP answering it instead of the host;
5. output from the GP's output buffers instead of the fold, and a
   surround path;
6. EP scheduling on `ep_frame_div`.

### ISTS bit 3, the "delta panic" claim

- xemu's `apu_regs.h` defines ISTS bits 0, 4, 5 and 6, and no bit 3.
- The toolkit names bit 3 `NV_PAPU_ISTS_SSLINTSTS` (`apu_regs.h:32`).
- The "delta panic" reading (the title panics when the bit never
  rises) is the toolkit's own inference, in the comment at
  `apu_core.c:1080-1101`.
- A web search found no public source.

So the claim is **unverified**. It is a host-side guess that a real GP
would make unnecessary or would confirm. Task 4 re-checks it with the
DSP on.

JSRF with the GP emulated confirms the recovery reading: the
handler resets the GP and EP and reloads them from the scratch image.
That reload loses the effect init once an effect commit has run.

**The model.** What the hardware compares against SSL cannot
be known: xemu never raises the bit and no public source names the
compare. The title code gives these facts:

- DirectSound's only response to the bit is recovery: it restarts the
  GP and EP, stalls 10 ms and reprograms the sequencer block (JSRF
  `sub_001A1F5D`, through the DPC worker `sub_001A23CD`).
- SSL is a constant 0x800, written only in that block with XGSCNT = 0
  and 0x2010–0x2028 (`sub_001A5CD7`). The title never reads XGSCNT.
  Nothing on the CPU side moves the limit or the counter while the
  sequencer runs.

So on hardware the DSPs keep the bit down while they keep pace, and the
one thing an emulated GP can lose is pace. The toolkit therefore keeps
a GP lag:

- One APU frame is `MCPX_APU_GP_FRAME_CYCLES` (106,667) cycles of a
  160 MHz GP.
- A GP frame that takes longer adds its excess to the lag. A shorter
  frame pays the lag back with its slack, since a late GP starts the
  next frame at once.
- The bit is raised when the lag reaches SSL samples. That clears the
  lag, and so does a GP reset.
- The lag belongs to the current sequencer run. It clears while the
  counter is off or SSL is 0, and at every sequencer start. B3 and SSX 3
  switch the counter off and on in one restart, and the late frames
  before it must not fire the new run at once.
- The lag counts DSP cycles, not host time, so the JIT warm-up adds
  none.
- A frame stopped at the cycle cap adds none. A GP that never halts is
  waiting on something the model lacks, so its cycles say nothing about
  the program's pace. Counting them would raise the bit every 64 frames
  and run the title's GP restart because of a gap in the model. The cap
  hit is counted (`capped=`) and logged instead.

`gp_emulated` now only selects the model, the lag or the stub's tick.
The stub keeps its once-per-start tick, which is a concession because
nothing keeps pace there.

### The stub's re-arm

The stub's tick used to re-arm on every SECTL write with the counter off.
That turned a title's recovery into a loop. The recovery re-arms the tick,
the tick fires again once the sample count passes SSL, and the cycle
repeats. B3 and SSX 3 restarted 23 times a second.

The traces (`runs/apu-dsp/h2-b3-stock-trace`, `h4-ssx3-stock-trace`,
`runs/jsrf-mix/blx-apu`, `runs/jsrf-fps/mac-aputrace`) separate a real
start from a recovery.

DirectSound's init has the same shape in every title traced:

- SECTL 0, the sequencer stopped whole;
- program SSL and XGSCNT;
- SECTL 0x7, then 0xF.

The recovery differs by title:

- JSRF writes no SECTL at all, only IEN.
- B3, SSX 3 and BLiNX 2 go 0xF, 0x7, 0xF: only the counter mode
  changes.

So only a SECTL write of 0 re-arms the stub's tick now. Every write with
the counter off still ends the run, which is what the emulated GP's lag
counts from (`ssl_starts`). The new count is `ssl_resets`.

The reset state counts as armed, so the first interrupt comes whether or
not the init's SECTL 0 is seen. Black needs that interrupt to finish its
init, and Black was not traced. Each title now runs its recovery once per
boot.

JSRF's path does not change. BLiNX 2 has B3's shape, so its stock
behaviour changes: about 23 recoveries a second before, one per boot
after. Its goldens and audio captures are the check.

## Measurements (Mac, Apple Silicon, Metal, JSRF, 150 s, `SDL_AUDIODRIVER=dummy`)

Probe build on toolkit `spike/apu-dsp` `7fc03472`, JSRF gen regenerated
in a private worktree. Runs are under `runs/apu-dsp/` (private).

| Run | flips/s, 30–60 s | flips/s, 60–150 s | WAV length |
|---|---|---|---|
| Probe off (`s1-m0`) | 56.6 | 60.0 | 150.09 s |
| Mode 1, DSPs run and their output is discarded (`s6-m1`) | 56.1 | 60.0 | 150.03 s |

**Cost of mode 1 (host ack still on, so the GP idles):**

| DSP | Cycles per frame | Wall time per frame | Total wall time | JIT compiles | Code |
|---|---|---|---|---|---|
| GP | 303–307 | 1.7–2.1 µs | about 3 ms/s | 43, 5.8 ms in all, worst 1.1 ms | 23 KB |
| EP | about 5,985 (EP frame) | 22–30 µs (EP frame) | about 5 ms/s | 104, 8.8 ms in all; first EP frame 7.5 ms | 47 KB |

- **Throughput:** the JIT runs about 240M DSP cycles/s on one Mac core.
- **Projection for a real GP effects load:** 50–106k cycles per frame
  costs 0.2–0.45 ms per APU frame, which is 30–65% of one core on the APU
  thread. The render thread is unaffected, but the APU thread must
  still keep real time. This is a projection. Mode 2 never produced a
  real GP load (see below).
- **x86-64:** measured on the Deck, see the next section. Native
  Windows was out of scope for this slot.
- **flips/s:** the 25% rule is not tripped, because flips are capped at
  60 and the DSP runs on the APU frame thread. The real risk is APU
  real time (the WAV length), not flips/s.

**Problems the probe found, and what they mean for the slices:**

- **Invalidating from a callback crashes.** Calling
  `dsp56300_invalidate_cache` inside a peripheral callback during
  `dsp56300_run` frees the running block (SIGSEGV). Invalidations wait
  until `run` returns.
- **Whole-cache invalidation is too slow.** Dropping the cache on every
  EP overlay DMA into P (about 137 words per EP frame) recompiled the EP
  every frame:
  - about 82 compiles per EP frame, 7.8 ms per EP frame;
  - code grew about 750 KB/s;
  - the APU fell to 68% of real time (a 102.5 s WAV after 150 s).

  Writing P per word with `dsp56300_write_memory` fixed it. Compiles hold
  at 104.
- **Mode 2 runs away.** With the host ack off, the GP takes real
  commands, then DMA buffer 0xD shows up (unhandled in xemu too),
  followed by a descriptor read with `next_block`=0. The PC then leaves
  PRAM (0x1445ae, 0x32ca2e, …) until the 2M-cycle cap, about 35 ms a
  frame. The probe's DMA register map and block walk match xemu's
  `dsp_dma.c`, so the fault lies elsewhere:
  - an unimplemented opcode (dsp56300 1.0.0 lacks SA/SC/DM and SEN);
  - a peripheral read;
  - or buffer 0xD itself.

  Task 2 owns this.

## Measurements (Steam Deck, GE-Proton11-7, D3D11, on-screen with sound)

The same probe build, cross-built on the Mac with llvm-mingw 20260922
against the `x86_64-pc-windows-gnu` dsp56300 1.0.0 archive (task 1.3:
it links as is with `-l:libunwind.a` plus `ws2_32 userenv ntdll bcrypt
advapi32 kernel32 synchronization`, and the exe imports only system
DLLs). The probe uses SRWLOCK and QueryPerformanceCounter on `_WIN32`.
Same JSRF pad script; each run lasted about 263 s, because
`RECOMP_WINDOW_QUIT_AFTER` is SDL-only and the D3D11 window ignores it,
so the outer timeout ended them. Runs are under `runs/apu-dsp/deck-*`
(private).

| Run | flips/s, 30–60 s | flips/s, 60–263 s | WAV length vs flip clock | Host queue |
|---|---|---|---|---|
| Probe off (`deck-jsrf-m0`) | 42.0 | 59.9–60.0 | 262.7 s / 262.6 s | 0 starves, 0 underruns |
| Mode 1 (`deck-jsrf-m1`) | 54.6 | 60.0 | 263.6 s / 263.8 s | 1 starve (92 ms, at boot), 2 underruns |

The 30–60 s window is the boot and intro, which differs run to run.

| DSP | Mean per frame | Per-second worst frame, after boot: median / p99 / max | Total | JIT |
|---|---|---|---|---|
| GP (1,500 frames/s) | 6.0 µs (Mac 1.9) | 39 / 328 / 586 µs | about 9 ms/s | 43 compiles, 32 ms, worst 3.9 ms |
| EP (187 EP frames/s) | 80.7 µs (Mac 24.8) | 165 / 635 / 661 µs | about 15 ms/s | 104 compiles, 113 ms, worst 16.6 ms |

- **Cost:** about 24 ms/s, 2.4% of one Deck core, about 3× the Mac per
  frame. Frames over 1 ms occur only in the first second (JIT
  compiles). That second is also where the one 92 ms starve sits.
- **Task 6.1 gate:** pass on the Deck. Even the p99 of the per-second
  worst GP frame (328 µs) is under 50% of the 0.67 ms frame, and
  flips/s does not drop. The isolated 0.6 ms worst frames are host
  preemption, not DSP work (cycles per frame are fixed at 303).
- **Projection:** a real GP effects load (50–106k cycles per frame) at
  the Deck's rate is about 0.6–1.3 ms per frame, which is at or above
  the 0.67 ms budget. Mode 1 does not measure that load (the GP idles
  with the host ack on). Task 6.1 re-runs with a real GP load after
  task 3. The cycle cap (task 3.4) bounds the damage, and a DSP thread
  (task 6.3) is the planned answer if a title misses real time on the
  Deck.
- **Compile stall at boot:** the first EP compile burst (16.6 ms)
  starved the host queue once. Task 3.5 pre-warms the JIT at GPRST
  release or runs the first frames off the APU thread.

### The tracker item: SSX 3 choppy audio

One Mac run of SSX 3 (`x0-stock`: ssx3 build of Oct 17, bench pad
script, 150 s, Metal, dummy audio driver), scanned with
`runs/apu-dsp/wavscan.py`:

| Window | Gaps (≥2 ms of zeros) | Clicks | Repeated 256-sample periods |
|---|---|---|---|
| 0–20 s (boot, menus) | 14, 517 ms in all | 0 | 0 |
| 20–150 s (front end and race) | 0 | 0 | 0 |

The run held 60 flips/s.

- **Result:** the mixer's output on the Mac is clean. The WAV tap sits
  before the SDL queue, so the choppiness reported on the Deck is not
  in the APU's mix on the Mac.
- **Deck run (task 6.2):** the installed SSX 3 build (20261019.1052,
  stub, no probe), the same pad script, GE-Proton11-7, D3D11, on-screen
  with sound, `RECOMP_TRACE=flip,audio_host` (`deck-ssx3-stock`).

  | | Mac `x0-stock` | Deck `deck-ssx3-stock` |
  |---|---|---|
  | Length | 150 s | 263 s |
  | flips/s after 30 s | 60.0 | 58.0 (30–60 s), then 60.0 |
  | Gaps | 14, 517 ms, all in 0–20 s | 15, 505 ms: 14 in 0–20 s, one of 3 ms at 140 s |
  | Clicks (splices in the mix) | 0 | 9 events (19 samples) |
  | Host queue | n/a (dummy driver) | 0 starves, 0 underruns, 0 refused, q_min 1,280 frames |
  | APU real time | 149.95 s WAV | 262.70 s WAV vs 263.79 s flip clock |

- **Result:** the host queue under Proton is not the cause. It never
  ran dry, and the APU kept real time. The 9 clicks are in the WAV,
  which is what the device is given, so they come before the queue.
  Six of them (47.2, 50.1, 61.6, 105.8, 222.9 and 244.9 s) land on
  game-side frame stalls of 41–71 ms, at 47.3, 50.3, 61.8, 105.9,
  223.1 and 245.1 s on the flip clock. The Mac run has no such
  stalls. The choppiness on the Deck is the guest stalling, not the
  host queue and not a missing DSP. The likely causes are a DXVK
  pipeline compile or streaming I/O. A stalled frame leaves the
  game's stream voices short, and the mixer splices.
- **Next step:** find what the 41–71 ms stalls are, using
  the `[PB-PERF]` and DXVK logs around those flips. Neither the DSP
  nor an SDL3 move addresses them.

## Options

All licences below come from the files themselves, read on 2026-10-21:

- **xemu `hw/xbox/mcpx/apu/dsp/`:**
  - `dsp.c`, `dsp_c.c` and `interp/*` (`dsp_cpu.c`) say GPL v2 "or (at your option)
    any later version", "Adapted from Hatari DSP M56001 emulation (C)
    2001-2008 ARAnyM developer team, Adaption to Hatari (C) 2008 by
    Thomas Huth".
  - `dsp_jit.c` is GPL-2-or-later (Matt Borgerson, 2026).
  - `gp_ep.c` and `dsp_dma.c` say Lesser GPL version 2 "or (at your
    option) any later version" (espes, Jannik Vogel, Matt Borgerson).
- **`mborgerson/dsp56300`:** "MIT License, Copyright (c) 2026 Matt
  Borgerson".
- **gearmulator** and its DSP core **`dsp56300/dsp56300`
  (dsp56kEmu):** `LICENSE.md` is GNU GPL version 3. The core's `.cpp`
  files have no per-file headers.

**What each licence means for us.** The toolkit and the game repos are
MIT, apart from the LGPL APU files named in `NOTICE`.

**Decision:** this change allows MIT (and other permissive licences,
such as Apache-2.0, Zlib and Unicode-3.0) plus LGPL-2.1+ only. Code
under any GPL would put the shipped executables and the wizard's
downloads under GPL terms, so it is excluded unless the user decides
again. The table records the effect of each licence for that decision.

| Licence | Effect on the public repos and the wizard builds |
|---|---|
| MIT (e) | Credit only: `NOTICE` plus `LICENSES/MIT-dsp56300.txt`. No change to the binaries' terms. |
| LGPL-2.1+ (device model from xemu `gp_ep.c`/`dsp_dma.c`) | Already the precedent. The static link is covered by the public source of every repo and the existing `NOTICE` text on relinking. |
| GPL-2+ (xemu's interpreter or JIT), **excluded** | Every distributed binary becomes GPL (2 or later). The game repos' own source can stay MIT, because MIT is compatible, but the shipped executables and the wizard's downloads carry GPL terms. The source is already public, so this is satisfied. `NOTICE` and `LICENSES/GPL-2.0.txt` are needed. |
| GPL-3 (gearmulator), **excluded** | As GPL-2+, but GPL-3. `LICENSES/GPL-3.0.txt` and `NOTICE` are needed, and the toolkit's LGPL-2.1+ files are used under their "or later" clause, as GPL-3 requires. |

MIT and LGPL-2.1+ are allowed. The device model port follows the
existing `NOTICE` precedent for the xemu APU files. The two GPL rows
are excluded and need a new user decision.

**Glue that only GPL files hold.** dsp56300 emulates only the chip
(instructions, memory, the JIT); it knows nothing of the MCPX. xemu
keeps the rest of the Xbox glue in its GPL files, not in the LGPL
`gp_ep.c`/`dsp_dma.c`: the peripheral register decode in `dsp.c`, and
the GP/EP boot and the memory map (the X:0x1400 → X:0xC00 mixbuf alias)
in `dsp_jit.c`. We write that glue in our own structure from the
hardware facts alone: addresses, bit meanings, aliases and reset
behaviour. We never port or adapt code from those files, and their
debug conventions (such as the `0xababa` read of an unmapped
register) stay out. Facts are not copyrightable, but code is. The
The tracker item review found a first draft that tracked `dsp.c` and
`dsp_jit.c` too closely, and it was rewritten. A reviewer of later
slices checks new device code against those two files.

The prebuilt dsp56300 archive also bundles the Rust std (MIT OR
Apache-2.0) and the crates of `dsp56300-emu`. The archive's
`THIRDPARTY-emu` file, made by cargo-about from `Cargo.lock` at v1.0.0
with only permissive licences accepted, lists Apache-2.0 (cranelift,
regalloc2, gimli, hashbrown, libc, windows-sys and others; some WITH
LLVM-exception), MIT (dsp56300-core, dsp56300-emu, region, libm,
strsim), Unicode-3.0 (unicode-ident) and Zlib (foldhash). None is GPL.
cbindgen (MPL-2.0) is a build dependency only and is not linked.
Task 1.4 re-checks this and carries the texts.

### The options compared

| Option | Accuracy | Speed | Effort (agent-days) | Risk |
|---|---|---|---|---|
| (a) xemu interpreter port (GPL-2+). **Excluded by the licence decision; needs a new user decision.** | High. It is what xemu ships. | Low. An interpreter at about 160M cycles/s of guest work costs several times the JIT, and is unlikely to keep real time at a full GP load on the Deck. | 6–8 (C, glib removed) | Speed on the Deck. |
| (a′) xemu `dsp_jit.c` (GPL-2+). **Excluded by the licence decision; needs a new user decision.** | High | Unknown. New in 2026, tied to xemu's tree. | 8–12 | Young, needs extraction from QEMU. |
| (b) static recompile of the DSP images | Exact for known images | Best | 15–25, and per title | Images arrive by DMA and overlay at run time (the EP loads overlays into P every frame). Self-modifying flows and title-custom images (`B3XboxFx.bin`) need a fallback anyway. |
| (c) HLE: effects written in C | Approximate | Good | 10+ per effect family, per title | No custom images. Reverb and I3DL2 parameters are guessed. |
| (d) stub plus targeted fixes | Low, per symptom | Free | 1–2 per symptom | Never yields effects or surround. Today's path. |
| **(e) `mborgerson/dsp56300` JIT, MIT, Rust with a C FFI** | Good. Written for the MCPX by xemu's maintainer. Gaps: SA/SC/DM, SEN. | **Measured at an idle GP:** about 240M cycles/s on the Mac; on the Deck GP 6 µs per frame and EP 81 µs per EP frame. | **12–17 in all** (tasks) | The cost of a real GP load is open (task 6.1). The `windows-gnu` archive links with llvm-mingw. The mode 2 fault is not yet understood. |
| (f) gearmulator `dsp56300/dsp56300`, GPL-3, C++17 with asmjit. **Excluded by the licence decision; needs a new user decision.** | Very high for the 56362/56303 synths it targets | Fast JIT on x64 and aarch64, also an interpreter | 15–21: (e)'s slices plus 3–4 for an MCPX peripheral class and a C header shim | The peripherals (ESAI, ESSI, HDI08, DMA) don't match the MCPX, so we write our own. About 64k lines of C++ plus asmjit (zlib) in every build. Upstream moves fast (last commit 2026-10-20) and has no MCPX users. |

#### gearmulator in detail (coordinator request)

- **Licence:** GPL-3 (`LICENSE.md`), as above, so excluded under the
  licence decision. The assessment below stays on record for a future
  decision.
- **Separation:** the DSP core is its own repository and CMake target,
  `dsp56300/dsp56300`. It builds as a static library without the synth
  or plugin code.
- **Peripherals:** written for the Motorola 56362 and 56303 (ESAI,
  ESSI, HDI08, the 56300 DMA). The MCPX's DMA engine, its scratch
  buffers and its GPRST bootstrap are not covered. We would subclass the
  peripheral interface with an MCPX model, which is the same device
  model as in (e), written in C++.
- **JIT:** asmjit back ends for x86-64 and aarch64 (the Mac, the Deck
  and Windows), plus an interpreter.
- **Footprint:** about 64k lines of C++17, plus asmjit. The toolchains
  in the wizard builds (llvm-mingw, Apple clang) handle C++17. Per the
  language spike, a C++ core behind a C header is acceptable as a leaf.
- **Maintenance:** active and mature; it is the engine behind several
  shipping synth emulators.
- **Against (e):** comparable or better maturity and a proven JIT. It
  costs more integration (a peripheral class in C++, a large C++
  dependency compiled into every build) and has no MCPX-specific
  testing. (e) was written for exactly this chip, with xemu's
  semantics, and has a C ABI already. Prefer (e). If (e)
  fails task 2 (a core bug we cannot fix upstream) or task 6 (too slow
  on x86-64 even with a DSP thread), stop and ask the user.

## Decisions

1. **The engine is (e)**, behind a C interface (`apu_dsp_emu.h`) that
   does not leak dsp56300 types, so the engine can be swapped if the
   user ever decides on another one.
2. **The device model is ported from xemu's LGPL `gp_ep.c` and
   `dsp_dma.c`**, as the probe already does. It keeps their LGPL-2.1+
   headers and is listed in `NOTICE`, following the precedent of the
   xemu APU files already there.
3. **The gate:**
   - a CMake option `XBOXRECOMP_APU_DSP` (default OFF; whether a game
     repo turns it on is the user's decision in task 7.1);
   - and at run time a config-tier `recomp_env` key, `apu_dsp`
     (default `0`, the stub). It is a toolkit row (`APU_DSP`, variable
     `RECOMP_APU_DSP`) in `RECOMP_ENV_KEYS` in `src/platform/recomp_env.h`,
     parsed by `recomp_env.c`, not a game key. The parser matches names
     by exact length, so `RECOMP_APU_DSP` does not collide with
     `RECOMP_APU_DSP_ACK` or with the `apu_dsp_ack` debug key.

   Stock audio is byte-identical with the key at 0 (task 5.3 tests it).
   The key gets an `env.md` row.
4. **Linking:** the dsp56300 release archives are fetched per target and
   pinned by sha256, as `wizard/pins.json` does. Building from Rust
   source is not a wizard dependency. v1.0.0 has archives for
   `aarch64-apple-darwin`, `x86_64-apple-darwin`,
   `x86_64-pc-windows-gnu`, `aarch64-pc-windows-gnullvm`,
   `x86_64-unknown-linux-gnu` and `aarch64-unknown-linux-gnu`. A
   target without one, such as iPadOS, builds with the option OFF.
5. **Window visibility:** the frame thread polls GPRST/EPRST in the
   untrapped windows, as the probe does. The trap stays at
   `APU_TRAP_BYTES`, because widening it brings back the B3 `rep movsd`
   fault.
6. **JIT hygiene:**
   - write P one word at a time through `dsp56300_write_memory`;
   - never invalidate inside a callback;
   - budget the cycles per frame with a cap that is logged, never
     silent.
7. **Threading:** the DSPs run on the existing APU frame thread, in
   order (VP, GP, then EP every eighth frame), as on hardware. The
   Deck numbers so far are at an idle GP; the real load is open. A
   separate DSP thread is task 6.3, done only if 6.1 fails.
8. **Existing keys.** With `apu_dsp=1`:
   - `apu_dsp_ack` (default `auto`) is forced off, because the GP answers the doorbell itself;
   - `apu_mixdown_all` is ignored, because the output comes from the
     GP and no longer from the stub's fold.

   If the user also set either key, one line is logged at startup
   saying it is overridden. With `apu_dsp=0` both keep their current
   behaviour.
9. **Renderer-agnostic.** Nothing here touches D3D11 or Metal, so the
   backend parity rule does not apply. The golden gate still runs on
   both, because the change touches the runtime's audio.

## Risks

- **The x86-64 cost may exceed the APU budget at a full GP load.** The
  cost was measured at an idle GP only (Deck: 2.4% of a core); the
  real load is open. Task 6.1 measures it after task 3, before any
  default changes. The fallbacks are a DSP thread (task 6.3) or keeping
  the gate OFF on that host. Any other engine needs the user to decide.
- **dsp56300 1.0.0 gaps** (SA/SC/DM, SEN) may matter for some title
  images. Fix them upstream (MIT) or carry a patch.
- **The first EP frame compiles for about 7.5 ms (Mac) to 16.6 ms
  (Deck)**, a one-off stall on the APU thread. On the Deck it starved
  the host queue once (92 ms). Task 3.5 handles it.
- **Per-title regressions.** JSRF's bins 6–10 tuning in the stub
  mixdown is replaced by the title's own GP mix. Goldens and the WAV
  scans decide.

## Open questions

- Is the GP output stereo plus a 6-channel EP input, or does the GP
  write 6 channels? This decides the surround path (task 3). xemu
  reads the GP's output buffers, so we start there.
- Does the title need ISTS bit 3 once a real GP runs (task 4)?
  *No for JSRF, B3 and SSX 3: with the GP on, each starts the
  sequencer once and never sees the bit. Black is unchecked (no dump
  here).*
- What is DMA buffer 0xD (task 2)?
