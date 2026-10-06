## Why

BLiNX 2 holds one host core busy just to wait, and its 30 fps frames arrive unevenly. The fps spike (`spike/fps`: `openspec/changes/fps-modes-spike/spike.md`, `mod60.md`, `v1-pacing-proposal.md`; raw runs in `xbox-recomp/runs/fpsspike/`) measured three problems:

- **A busy wait burns a core.** The main loop (`sub_0005F960`) waits for its vblank count with `while ([0xAE7388] < [0x3FD344])` at `0x00060475`. The lifted loop holds one host core at about 97% (`analysis/research/hot-threads-macos.md` §1a: 1930/1983 samples on one PC during the intro). That costs heat and battery on laptops and the Steam Deck, and it takes a core from the raster threads.
- **Flip intervals jitter.** In stock 3D on Mac/Metal (`runs/fpsspike/hold-lock30`, the last 1,399 flips), the interval is p5 26.4 ms, p50 33.3 ms, p95 41.0 ms and max 53 ms, around a 33.3 ms target. The game counts vblanks from the top of each frame, so the jitter comes from the vblank clock and from when the title's vblank DPC runs. In the same run, the toolkit's `[NV2A] vblank` lines show gaps of 11.8 to 20.8 ms, and once 1.7 to 46.4 ms, around 16.7 ms. The schedule is in whole milliseconds, the timer thread sleeps in whole milliseconds, and a DPC that finds the one-CPU gate busy waits up to 10 ms for the next pass.
- **There is no real 60 fps for this title.** Stage logic, movement and the HUD timer advance a fixed 1/30 s per frame. Every 60 fps lever the spike tried played the game at 2x speed. `fps.mode` must say so, not offer a mode that fast-forwards.

The user decided on 2026-10-05 (`spike.md`, "User decisions") that v1 is `lock30` plus smoother pacing. There is no 60 fps mod, no interpolation and no turbo.

## What Changes

- **The vblank clock is even (toolkit kernel, every title).** `kernel_vblank_tick` schedules on a nanosecond clock with the same absolute epoch. The timer thread sleeps to the vblank edge or the next kernel timer with a high-resolution sleep, not a millisecond one. A DPC drain that finds the gate busy tries again within 1 ms instead of up to 10 ms. The dpc-stall rules stay:
  - the vblank is raised only while `PCRTC_INTR_EN_0` enables it;
  - the ack thread owns the PMC and PCRTC bits;
  - the schedule restarts after a stall of more than 100 ms;
  - a DPC never waits for the gate.

  `RECOMP_DEBUG=vblank_clock=ms` brings back the old loop for A/B runs.
- **Spin waits can sleep (opt-in toolkit extension, title-agnostic).**
  - Lift time: with `--spin-waits FILE`, the generator recognises a self-loop that only reads memory and branches back. The loop at `0x00060475` is one. The generator emits `RECOMP_SPIN_WAIT(va)` on the loop's back edge. `FILE` picks the sites (all detected sites, or only the listed ones) and can exclude sites. The recomp run also writes a report of every candidate. Without the flag the generated code is byte-identical to today's.
  - Runtime: `xbox_SpinWait(va)` returns at once under `present.pacing = "spin"`, which is stock. Under `"sleep"` it blocks until the kernel signals that guest-visible state may have changed (a vblank tick, any ISR or DPC, a timer DPC, a fence write) or until 1 ms passes. A kernel signal is never lost (a generation counter under the wait's lock); a writer the kernel does not know about, such as another guest thread, costs at most 1 ms per pass and can never hang. A caller at DISPATCH level or inside the gate never sleeps.
- **New key `present.pacing`** (`"spin"` | `"sleep"`, env `RECOMP_PRESENT_PACING`), in the enhancements layer. It defaults to `"spin"`. It becomes `"sleep"` only through a separate, reversible commit, and only after `sleep` proves frame-identical on the Metal goldens, on the D3D11 goldens under Proton and on Burnout 3. Goldens stay pinned to `spin` either way.
- **`fps.mode` (cat game key, env `RECOMP_FPS_MODE`).** No fps key exists in code today; `fps.mode` appears only as an example in the toolkit's `enhance-config.md`. `lock30` is the only mode. `lock60` and `free` print one line saying they are not available for this title and why, then run `lock30`.
- **New trace `RECOMP_TRACE=pacing`.** Every 600 flips it prints one summary line: the flip-interval percentiles, the vblank gap range, process and waiting-thread CPU, and per-site wait, wake and timeout counts. `pacing=all` also prints one line per flip. A stdlib script (`scripts/pacing_stats.py`) and `bench.sh pacing` turn these lines into the A/B report.
- **BLiNX 2 lowers `0x00060475` only** (`config/spin_waits.json`, explicit list). `gen/` is regenerated (`pipeline.sh analyze`, then `recomp`). The gen key changes in its `toolkit`, `argv` and `inputs` fields.

Non-goals: `lock60`/`free` gameplay, frame interpolation, turbo, D3D11 present vsync, and retiring the BlockUntilVerticalBlank pacer. These are follow-ups or separate spikes; see design.md.

## Capabilities

### New Capabilities
- `frame-pacing`: spin-wait detection in the generator, the sleeping wait and its wake sources, the `pacing` trace, and how pacing is measured.

### Modified Capabilities
- `kernel-threads`: "Vblank runs at 60 Hz" now schedules in nanoseconds, sleeps with high resolution and retries a gate-busy DPC drain within 1 ms.
- `enhancements`: the stock-default rule covers `present.pacing`, the golden harness rejects a non-`spin` run, and `fps.mode` reports when a mode is unavailable.
- `deviations`: a new entry, "Spin waits may sleep".
- `bench-methodology`: a pacing A/B report, with the 25% flips/s and 1.5x raster-ms flags.

## Impact

- **Backends and hosts.** All three render paths (CPU, D3D11, Metal) behave the same. Pacing lives in the kernel and in generated code, and the measurement point is the executor's flip, which every backend shares. No backend file changes. Hosts: macOS (Metal, CPU) and Windows under Proton (D3D11, CPU).
- **Goldens.** All of them (`@attract`, `@stage1`, `@story`) run on Metal and D3D11 at `spin`. The regenerated `gen/` and the nanosecond clock must leave every verdict unchanged; a changed verdict blocks the merge, because the clock has no key to hide behind. The `sleep` gate re-runs them in evaluation mode.
- **Burnout 3.** The clock is unconditional, so the fork's toolkit branch also runs a Burnout 3 smoke under Proton (boot → menu → race, same pace) before it merges. The binding Burnout 3 runs for upstream are on each PR's exact head.
- **Toolkit (`posix-host/portability`).**
  - Kernel: `kernel_bridge.c` (the timer loop, the vblank schedule, wake points), a new `kernel_pacing.c`, and `kernel.h`.
  - Platform: `xbox_HostNowNs` and `xbox_HostSleepNs`.
  - Executor: a wake point at the fence write, and the flip timestamp.
  - Generator and runtime header: `tools/recomp` (matcher, `--spin-waits`, report, pytest) and `templates/runtime/recomp_types.h` (`RECOMP_SPIN_WAIT`).
  - Enhancements layer: `src/enhance` (`present.pacing`; `enhance_cfg_report_unused` moves to the title).
  - Env table: `recomp_env.h` rows.
  - Docs: `docs/runtime/enhance-config.md`.
  - Tests: ctests `vblank_schedule` and `spin_wait`.
- **Upstream.** Meant for upstream. The nanosecond clock folds into PR-08 (the vblank pacer), or follows it as PR-08b if PR-08 is already filed. Spin-wait lowering is a new opt-in extension, PR-E2, filed after PR-E1 and shaped as `pr-stack-plan.md` §3.2 says (plain `getenv`). Each is tested on Burnout 3 under Proton on the exact PR head.
- **cat.**
  - `config/spin_waits.json`, `blinx2.py` (the recomp flag, gen inputs) and `scripts/test_blinx2_cli.py`.
  - `src/env/recomp_env_game.h` and `src/main.c` (`fps.mode`, the unused-key report).
  - `scripts/golden.py` (the pacing check, `--allow-enhance`), `scripts/pacing_stats.py` with its test, `scripts/bench.sh pacing` and `analysis/golden/golden.json` (pin `RECOMP_PRESENT_PACING=spin`).
  - `docs/env.md` and `config/setup-pins.json`.
