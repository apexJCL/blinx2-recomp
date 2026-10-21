## Why

A tester reported that a build used up all of their RAM (
2026-10-18). The CLI sizes the compile by cores alone:
`cmake --build -j os.cpu_count()` (`xboxrecomp-cli`
`src/xboxrecomp_cli/build.py:219`), and the HUD upscale starts one
process per CPU (`enhance/hud.py:295`). Neither looks at memory.

Measured on the Mac for this spec (design, Context): one compile job on
a large generated file peaks at 0.8 to 1.2 GiB, against about 0.2 GiB
for a median one and at most 133 MiB for a toolkit file. With `-j` equal
to the core count, the largest files can run together: 7.3 GiB for 16
jobs on the windows target and 10.5 GiB for 32. A 16 GB machine with 16
or more threads and a browser open runs out. The single largest step is
not the compile but `disasm`, at 1.7 GiB in one process.

The user's decisions (2026-10-18), fixed for this change:

1. Measure the per-step peak memory, and the per-job compile peak on the
   largest generated files.
2. `doctor` and the wizard check free RAM and disk before a build, and
   say what they will do.
3. Parallelism adapts to the machine: jobs = min(cores, free RAM /
   per-job peak), with a Ninja job pool for the generated code, the same
   sizing for the HUD workers, a `--jobs N` override and a wizard
   setting.
4. No memory cap, now or later. Assume the workstation gives most of its
   resources to the build: a modest reserve and no other margin.
5. Low disk refuses before the first stage, so no build is left
   incomplete for lack of storage, with an explicit override. Low memory
   stays a warning.

The tester has 24 GB of RAM and reported only that the machine crashed.
That is consistent with the worst-case compile figures above at 24 to 32
threads.

## What Changes

- **CLI: a resources module.** `resources.py` reads cores, total and
  available RAM, and free disk with the Python standard library on
  Linux (with cgroup limits), macOS and Windows. It works out the job
  counts from them.
- **CLI: measured peaks.** Each external step the CLI runs reports the
  peak memory of its largest process: `os.wait4` on Linux and macOS, an
  accounting-only Job Object on Windows. The HUD workers report their
  own peak. The peaks are kept per target in the build state and shown by
  `doctor` and in the package log.
- **CLI: sized builds.** `build`, `all` and `package` compile with a
  `-j` from the formula and put the game's executable target, which holds
  the generated code, in a Ninja job pool (`xbr_gen`) with its own depth.
  The pool comes from a CMake file the CLI injects, so no game's
  `CMakeLists.txt` changes. `enhance hud` sizes its workers the same way.
  `--jobs N` overrides both. The job counts never enter a stage key, the
  options digest or a bundle.
- **CLI: doctor reports resources.** `doctor` prints memory, cores, disk
  and the job counts it would use, with a warning when memory or disk is
  low; the memory warning names `disasm`'s 1.7 GiB. `doctor --json` gains a `resources` object. `package` prints the
  same decision as it starts the compile.
- **CLI: low disk refuses.** `package`, `import`, `analyze`, `build`,
  `all` and `enhance hud` estimate what each stage they will run writes.
  When a volume is short, they refuse before the first stage with each
  stage's share and the fix (`refused: disk`). `--ignore-disk-space`
  overrides it; the wizard does not offer that.
- **game.toml: per-game numbers.** A new `[build.resources]` table holds
  the per-job peak of the game's generated code, the peak and name of its
  largest tool step, and the disk its generate and build stages write.
  cat sets measured values. Games without the table get estimates from
  the size of their gen/ files.
- **Wizard: shows and lets the player choose.** The Checks page gains a
  "This computer" row from `doctor --json`. A "Build jobs" setting
  (Automatic, or a number) is kept in the wizard's settings and passed
  as `--jobs`.

## Capabilities

### New Capabilities

- `build-resources`: measuring per-step peaks, the memory and disk
  queries, the job sizing, the pool, the override, the disk refusal, and
  what doctor and the wizard show.

### Modified Capabilities

None. `packaging` keeps its requirements; the sizing changes how fast a
build runs, never what it makes.

## Impact

- **Code** (all in `xboxrecomp-cli/`): a new `src/xboxrecomp_cli/resources.py`
  and `src/xboxrecomp_cli/cmake/xbr-jobs.cmake`; `host.py` (measured runs),
  `package/progress.py` (the same under the progress view), `build.py`,
  `main.py` (`--jobs`), `doctor.py`, `enhance/hud.py`, `package/__init__.py`,
  `package/tweaks.py`, `manifest.py` (the new table), the new-game template
  and the docs. In `wizard/`: `internal/hostinfo` (the setting),
  `internal/runner` (the `resources` object), `internal/model` (`--jobs`)
  and `internal/screens` (the row and the setting).
- **Games:** cat sets `[build.resources]` and moves the CLI pin. Burnout 3,
  SSX 3 and Spartan work with the estimates and may add their own values.
- **Outputs:** none. The exe, the HUD pack and every bundle are the same
  bytes whatever the job count (design D6).
- **Speed:** unchanged on a machine with memory to spare. On a small one
  the build is slower but finishes: the whole of gen/ is 164 s of compile
  time on the windows target, so about 80 s at two jobs.
- **Not in scope:** any memory cap (D8), changing the job
  count while a build runs, the Ghidra stage (a developer stage with its
  own JVM settings), and the tracker item (xbe classification), which ships in the
  same release round.
