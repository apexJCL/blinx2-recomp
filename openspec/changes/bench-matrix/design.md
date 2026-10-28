# Design: bench-matrix

## D1. Scene start from the batch count, not a clock

The title starts after about 41 s of intro cards and movies, but load time
differs per host. The scene starts at the first flip with at least
`start.min_batches` draw batches (the intro is 0-1 batch per flip, the 3D
title 360-580), held for `start.hold` flips; the window is the next
`duration_s` seconds. A fixed `start.offset_s` is the fallback for a game
without such an edge. Both are game config. The run lasts `run_s`
(`RECOMP_WINDOW_QUIT_AFTER`), long enough for the slowest host.

## D2. Frame times from `RECOMP_TRACE=pacing=all`

`[PACING] flip N t_us T batches B` is printed on every flip by every backend
(kernel_pacing.c), in microseconds, with the batch count D1 needs. `flip`
(the `[GPU]`/`[METAL]`/`[D3D11]` lines) is millisecond-resolution and three
lines a flip, so it is not used. A frame time is the interval between two
flips inside the measured window; the interval into the window's first
flip (from the intro's last flip, often a load) is reported apart as
`load_gap_ms` and is not a frame. Over the window, and again over its
warm-up and steady parts (a frame belongs to the part its end flip falls
in):
- avg fps = flips / window seconds; max/min fps = the highest and lowest
  whole 1-second buckets the flips reach (no short last bucket);
- p1/p50/p99 frame time by nearest rank (`ceil(p/100 * n)`);
  1% low fps = 1000 / mean of the slowest 1% of the part's frame times;
- hitches = frame times over 1.5x the median (a missed vblank at 60 Hz),
  stutters = over 2.5x; slow share = the share of frames under the
  scene's `slow_fps` (50);
- warm-up = the window's first 20 s, the steady state the rest, since the
  Deck's first seconds run with the GPU still at its idle clock.
  The steady figures lead the tables.
- repeats of an arm (`--rep N`, `-rN` run dirs) are grouped by host, arm
  and profiler setting into n, median, min, max and MAD; a scene's
  `[verdict]` table (Deck: good when the warm-up is at least 50 fps) labels
  each run, and an arm counts its good and bad runs. A run another process
  disturbed (`busy_during`) is kept as a row but left out of the arm
  figures unless `analyse --include-disturbed`.

## D3. Hot paths: one in-process sampler on all three hosts

Mac has `sample`/`xctrace`, the Deck has `perf`, native Windows has ETW but
no reader a script can use without installing WPA/PerfView. Three tools
give three kinds of report. The toolkit samples itself (`RECOMP_TRACE=prof`,
host_prof.c): every thread's pc HZ times a second, written at exit as module
offsets; `collect` symbolises the exe's offsets with `nm`/`llvm-nm` on the
Mac, where every exe is built. Under Wine the thread cycle counter does not
move, so every thread is sampled and waits land in ntdll; the analyser
shows the system modules as their own rows and ranks the game exe's
functions apart. The sampler runs from `profile.delay_s` (the title's
start) at `profile.hz` (250), in the measured run; its overhead is checked
once per host on one arm against a run without it.

Under Wine the all-threads mode is not free: each round suspends, reads
and resumes about 28 threads (a wineserver round trip each), some 7000 a
second at 250 Hz. Within one performance mode (good runs against good
runs) the Deck measured a 1.1 to 1.3% fps cost at 250 Hz and 0.3 to 0.5%
at 100 Hz. Whether 250 Hz also tips runs into the slow mode is open: its
runs all ran in one block. Until 4.3
picks the threads that moved with `GetThreadTimes` (Wine updates it from
/proc) and suspends only those, the Deck host samples at 100 Hz (the
host's `profile` in title.toml), and fps figures come from runs without
the sampler only.

## D4. GPU clock and busy level

The Deck samples `pp_dpm_sclk` (the active level) and `gpu_busy_percent`
every 250 ms during the run (a shell loop beside the game); Windows samples
`nvidia-smi --query-gpu=clocks.gr,utilization.gpu -lms 250` when it
exists. The Mac has no unprivileged equivalent (`powermetrics` needs root):
none. Samples are timed from the game's launch and land in `run.json`.

## D5. Arms and hosts

The matrix TOML names axes (each value a set of env keys and config keys)
and hosts (each with a backend and an optional axis filter, e.g. the Deck
skips scale 4). An arm id is the axis values joined, `s2-dsp1-169`. The
arms run leg by leg: one arm on every host, then the next. Native Windows
gets `run-arm.ps1` plus the rendered plan; its results are copied back into
the same tree and collected on the Mac.

## D6. One build per host, one toolkit sha

Every host runs exes built on the Mac from the same game and toolkit shas
with the DSP compiled in (`-DXBOXRECOMP_APU_DSP=ON`); `RECOMP_APU_DSP`
picks the arm. The PC gets them as a patch over its installed version.

The matrix ran at toolkit `feat/prof-sampler` 4ec1a736 and JSRF
`feat/bench-matrix` 5d8e7b0. Deck leg 1 at the first sha (d9934717) found
two D3D11 gaps the bench needs, fixed in 4ec1a736: D3D11 had no
`RECOMP_WINDOW_QUIT_AFTER`, so the runner killed the game and the exit
hooks (the profile report) never ran; and the `[PACING] flip` batch count
only counted write-back backends, so it read 0 on D3D11 and the start
detection fell back to its fixed time.
