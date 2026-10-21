## Context

cat `main` 6d0aaa9, `xboxrecomp-cli` `main` a00a9c7, toolkit
`posix-host/portability` 9f1df8f0. Paths are in `xboxrecomp-cli/` unless
they start with `cat/`.

How the CLI uses the machine today:

- `build()` configures once (Ninja when the venv has it, which is
  required on Windows), then runs `cmake --build -j os.cpu_count()`
  (`src/xboxrecomp_cli/build.py:183-219`). `package` calls the same
  function on its stock trees (`package/__init__.py:436-466`).
- The compile key (`package/incr.py:221-245`) holds the stock `-D` list,
  the trees, the toolchain and the env. No job count is in it.
- `enhance hud --jobs` defaults to 0, which means one process per CPU
  (`enhance/hud.py:80-82`, `:284-296`). `package` passes `jobs=None`
  when it remakes a kept pack (`package/tweaks.py:255-265`). The pool
  returns results in item order whatever the job count.
- The pipeline's tool steps (`xbe_parser`, `disasm`, `func_id`,
  `abi_analysis`, `recomp`) are single processes run through `host.run`
  (`pipeline.py:42-50`). No toolkit tool has a worker pool.
- `host.run` uses `subprocess.run`, or `progress.run_step`'s `Popen`
  under the progress view (`host.py:121-131`, `package/progress.py:394`).
- `doctor` reports tools, the toolkit, the dump and the targets
  (`doctor.py:154-297`). `doctor --json` is what the wizard's Checks page
  reads (`doctor.py:330-367`, `wizard/internal/runner/runner.go:158-189`).
  Neither says anything about memory, cores or disk.
- The wizard checks disk itself before the clone: 15 GiB in the build
  folder (`wizard/internal/hostinfo/hostinfo.go:166-168`,
  `internal/screens/work.go:203`) and the dump plus 1 GiB in the output
  folder (`hostinfo.BundleNeed`). It has no memory check.

### Measured (Mac, 2026-10-18)

M-series Mac, 14 cores, 36 GB, Apple clang (CLT) and llvm-mingw
20260922. Each compile is the exact command from the package trees'
`build.ninja` (`cat/build-pkg-win`, `cat/build-pkg-macos`; `-O3`, the
reproducible prefix maps, `-Wno-parentheses-equality`), with the object
sent to a scratch folder. Peak is `/usr/bin/time -l` maximum RSS. The
first pass ran 8 at a time; the largest four were run again one at a
time and agreed within 15%. Raw output and scripts:
`runs/build-resources/` (`summary.txt`).

The Mac had 7.9 GB in swap during the runs. macOS RSS leaves out
compressed pages, so these are lower bounds, and D3's margin covers
that.

Compile, gen/ (51 files, 138 MB; 49 `.c`):

| | windows (llvm-mingw) | macos (Apple clang) |
|---|---|---|
| largest per-job peak | 878-927 MiB (`recomp_0009.c`, 15.8 MB) | 1063-1220 MiB (`recomp_0017.c`, 8.8 MB) |
| next three | 803-841 MiB (`_0017`, `_0018`, `_0004`) | 914-1055 MiB (`_0018`, `_0009`, `_0004`) |
| median / smallest | 200 / 63 MiB | 240 / 46 MiB |
| sum of the largest 8 / 16 / 32 | 5.1 / 7.3 / 10.5 GiB | 6.4 / 9.1 / 12.9 GiB |
| CPU time for all of gen/ | 164 s | 219 s |
| wall time at 8 jobs | 21 s | 28 s |

Peak does not follow file size: `recomp_0034.c` is 9.8 MB and peaks at
389 MiB, while `recomp_0017.c` is 8.8 MB and peaks at 1.2 GiB. The
measured ratio runs from 40 to 139 MiB per MB of source.

Everything else:

| Step | Peak | Time |
|---|---|---|
| toolkit and game sources (125 objects, windows) | at most 133 MiB (`nv2a_pb_d3d11.c`) | under 1 s each |
| link, lld (windows) / ld (macos) | 114 / 212 MiB | under 1 s |
| `disasm` | **1722 MiB** | 144 s |
| `recomp` | 669 MiB | 130 s |
| `func_id` | 277 MiB | 45 s |
| `abi_analysis` | 158 MiB | 2 s |
| `enhance hud`, the parent | 480 MiB | 17 s at 8 workers, 43 s at 1 |
| `enhance hud`, each worker | 53 MiB | |

The HUD pack had the same sha256 at 1 and 8 workers.

Disk, from the main cat checkout: dump 3.1 GB, `game_files/` 3.1 GB
(the imported copy), the two package build trees 146 and 141 MB, gen/
138 MB, `analysis/` about 140 MB, `third_party/` 762 MB, `.venv` 216 MB,
the HUD pack 159 MB, each bundle about 3.5 GB.

The tester's report: 24 GB of RAM, and the machine crashed
during a build. They named no step and no thread count.

What this means:

- At `-j` equal to the cores, a machine with 16 threads can need 7 to
  9 GiB for the compile alone, 24 threads 9 to 11 GiB, and 32 threads
  10.5 to 12.9 GiB. These are lower bounds, and Windows counts commit,
  which is larger than RSS. On a 24 GB machine with a desktop and a
  browser open, that is consistent with the tester's crash.
- The toolkit's files, the link and the HUD workers are small. Only
  gen/ needs a limit, and only on the target that holds it.
- `disasm` is the largest single process. It cannot be split, so it gets
  a check and a warning, not a job count. The warning names its 1.7 GiB.

## Goals / Non-Goals

**Goals:** a build that fits the memory it finds, says what it will do
before it starts, keeps the full speed where memory allows, and makes
the same bytes at any job count. It works on Linux, macOS and Windows
with the standard library only.

**Non-Goals:** any memory cap, now or later (D8); changing the job count while a
build runs (Ninja fixes the pool depth when it loads `build.ninja`);
limiting the Python steps, which are single processes; the Ghidra stage.

## Decisions

### D1: Each step reports the peak of its largest process

`host.run` and `progress.run_step` start the child with `Popen` and
measure it:

- **Linux and macOS:** `os.wait4(pid, 0)` in place of `wait()`. Its
  `ru_maxrss` is the largest of the child and the descendants it waited
  for, so for `cmake --build` it is the largest compile job. Linux gives
  KiB and macOS bytes. A check on this Mac: `bash -c 'python3 ...'`
  holding 600 MB gave 590 MiB through `wait4` on the bash.
- **Windows:** a Job Object with no limit flags, created per step through
  `ctypes`. The child is assigned right after `Popen`. After it exits,
  `QueryInformationJobObject(JobObjectExtendedLimitInformation)` gives
  `PeakProcessMemoryUsed`, the largest committed memory of any process
  in the tree. Descendants join the job by themselves. The only process
  that can escape is one spawned before the assign, and cmake reads its
  cache before it starts Ninja.
- **HUD workers:** `_scale_task` returns its own peak with its result
  (`resource.getrusage(RUSAGE_SELF)` on POSIX, `GetProcessMemoryInfo`'s
  `PeakWorkingSetSize` through `ctypes` on Windows).

The peaks go to `.git/xbr/resources.json`, by step and target:
`{"compile:windows": {"peak": bytes, "jobs": 6, "at": "...", "cli": "0.9.0"}, "tool:disasm": {...}, "hud:worker": {...}}`.
A tool step's key is `tool:<module>`. A record keeps the larger of the
stored and the new peak, so one light run (a partial rebuild) never
lowers the figure the next sizing uses.
This file is kept apart from `build-state.json`, so a peak never moves a
stage key. `xbr clean` removes it. A failed measurement (no `wait4`, a
`ctypes` error) records nothing and never fails the step.

### D2: Queries, standard library only

`resources.py`, one function per quantity. Each returns `None` when it
cannot tell, and the result then says "unknown":

| | Linux | macOS | Windows |
|---|---|---|---|
| cores | `os.process_cpu_count()` (3.13+), else `len(os.sched_getaffinity(0))`, then the cgroup v2 `cpu.max` quota, rounded up | `os.process_cpu_count()`, else `os.cpu_count()` | `os.process_cpu_count()`, else `os.cpu_count()` |
| total RAM | `/proc/meminfo` `MemTotal` | `sysctl -n hw.memsize` | `GlobalMemoryStatusEx().ullTotalPhys` |
| available RAM | `MemAvailable`, and at most `memory.max - memory.current` of the process's cgroup v2 (from `/proc/self/cgroup`) when that is not `max` | `vm_stat`: (free + inactive + speculative + purgeable) × page size | `min(ullAvailPhys, ullAvailPageFile)`: Windows does not overcommit, so the commit headroom limits too |
| free disk | `shutil.disk_usage(path).free` | same | same |

On macOS the formula leaves out what the compressor could free, so it is
lower than Activity Monitor's figure. That is the safe side: on this Mac
it gave 13.7 GB while `memory_pressure` reported 65% free.

The cgroup rule covers containers, distrobox and Flatpak hosts, where
`MemAvailable` reports the whole machine.

### D3: The sizing formula

The user's rule (2026-10-18): the workstation gives most of its
resources to the build. So the reserve is small and fixed, and nothing
else adds a margin. With a per-job peak `G` for the gen/ target,
`O` = 256 MiB for any other compile job (measured at most 133 MiB), and
the cores `C`:

```
reserve  = clamp(10% of total RAM, 1 GiB, 2 GiB)
budget   = max(0, available - reserve)
gen_jobs = clamp(floor(budget / G), 1, C)
jobs     = clamp(gen_jobs + floor((budget - gen_jobs * G) / O), gen_jobs, C)
```

- The reserve leaves room for the desktop and the CLI itself. The 2 GiB
  ceiling keeps it modest on a large machine: 10% of 64 GiB would hold
  back 6.4 GiB for no reason.
- `jobs` is `cmake --build -j`. `gen_jobs` is the depth of the `xbr_gen`
  pool (D4).
- Without the pool (no Ninja, or CMake older than 3.24 with
  `--system-tools`), `jobs = gen_jobs`.
- `G` is the larger of two values:
  - `[build.resources] gen_job_mib` from game.toml, else 140 MiB per MB
    of the largest gen/ file (the worst measured ratio), at least
    512 MiB;
  - the last measured `compile:<target>` peak (D1).

  A measurement can raise `G` and never lower it, since an incremental
  build that recompiles only small files measures little.
- cat sets `gen_job_mib = 1220`, the largest peak measured on either
  target. One value covers both targets.
- Unknown available RAM: `gen_jobs = jobs = min(C, 4)`, with a note.
- `--jobs N` sets `jobs = gen_jobs = N`. It warns when N is over the
  formula's figure. It is the player's choice.

`enhance hud` uses the same budget:
`hud_jobs = clamp(floor((budget - 512 MiB) / H), 1, min(C, items))`, with
`H` the larger of 128 MiB and the last measured worker peak. The 512 MiB
is the parent's measured 480 MiB, not a margin. `--jobs N` sets the
count to N.

With cat's `G` of 1220 MiB:

| Machine | Available | Reserve | Budget | gen_jobs | jobs |
|---|---|---|---|---|---|
| this Mac: 14 cores, 36 GiB, during these runs | 12.8 GiB | 2 GiB | 10.8 GiB | 9 | 9 |
| 24 threads, 24 GiB (the tester's RAM) | 16 GiB | 2 GiB | 14 GiB | 11 | 14 |
| 8 threads, 16 GiB | 11 GiB | 1.6 GiB | 9.4 GiB | 7 | 8 |
| 16 threads, 16 GiB, browser open | 9 GiB | 1.6 GiB | 7.4 GiB | 6 | 7 |
| 8 threads, 8 GiB | 4.5 GiB | 1 GiB | 3.5 GiB | 2 | 6 |
| 32 threads, 32 GiB | 24 GiB | 2 GiB | 22 GiB | 18 | 20 |
| 8 GiB, nearly full | 2 GiB | 1 GiB | 1 GiB | 1 (warn) | 1 |

At one job all of gen/ takes about 164 s of compile on the windows
target. That is the slowest case.

The tool steps get no job count. Before `analyze` or `package` runs
them, the CLI compares the available RAM with the larger of
`[build.resources] tool_mib` and the measured tool peaks. For cat that is
1722 MiB, `disasm`'s measured peak, with `tool_step = "disasm"` naming
it. When `tool_mib + reserve` is over the available RAM, the CLI warns
(D5) and goes on.

### D4: A Ninja pool for the generated code, with no change to a game's CMake

The CLI ships `src/xboxrecomp_cli/cmake/xbr-jobs.cmake` and passes
`-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=<that file> -DXBR_GEN_JOBS=<gen_jobs> -DXBR_GEN_TARGETS=<targets>`
at configure. CMake runs the file at the game's first `project()`:

```cmake
include_guard(GLOBAL)
if(XBR_GEN_JOBS)
  set_property(GLOBAL APPEND PROPERTY JOB_POOLS xbr_gen=${XBR_GEN_JOBS})
  cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL _xbr_gen_pool)
endif()
function(_xbr_gen_pool)
  foreach(t IN LISTS XBR_GEN_TARGETS)
    if(TARGET ${t})
      set_property(TARGET ${t} PROPERTY JOB_POOL_COMPILE xbr_gen)
    else()
      message(WARNING "xbr: no target ${t} for the generated-code pool")
    endif()
  endforeach()
endfunction()
```

- The deferred call runs after the top-level `CMakeLists.txt`, when the
  target exists.
- `XBR_GEN_TARGETS` is `[build.resources] gen_targets`, by default
  `[build] exe`. In cat that target holds gen/ and six small game files.
  The toolkit's libraries are other targets and keep the full `-j`.
- CMake has a per-target `JOB_POOL_COMPILE` but no per-source one. That
  is why the pool is per target.
- The stock trees configure on every run, so they always get the current
  depth. The dev tree (`build()` without `stock`) reruns
  `cmake -B <dir> -DXBR_GEN_JOBS=N` only when the cached value differs.
  This regenerates `build.ninja`, and Ninja rebuilds nothing, because no
  compile command changes.
- `CMAKE_PROJECT_TOP_LEVEL_INCLUDES` needs CMake 3.24. The venv's CMake is
  4.4.4. With an older `--system-tools` CMake, the CLI passes no pool and
  uses `jobs = gen_jobs`.

### D5: What doctor, package and the wizard show

`doctor` adds these lines after `llvm-mingw`:

```
memory:     16.0 GB, 9.0 GB available now
cores:      16
disk:       212 GB free in ~/blinx2 (a build needs about 6.1 GB, D9)
build jobs: 7 (generated code 6 at a time, about 1.2 GB each: game.toml)
```

- The source after the colon is one of `game.toml`, `measured
  2026-10-18`, or `estimated from gen/` (D3).
- Low memory adds a warning when `budget < G`:
  `warning:    memory is low (2.0 GB available): the build will compile
  one file at a time and may use swap; close other programs first`.
- It adds another when the available RAM is under the tool peak plus the
  reserve. For cat:
  `warning:    disasm needs about 1.7 GB in one process and 2.0 GB is
  available; close other programs first`.
- Low memory is a warning only, never one of `problems`. The build still
  runs, at one job.
- Low disk adds `warning:    disk: 2.3 GB free, a build needs about
  6.1 GB: package will refuse (D9)`. Doctor's figure is D9's need for a
  `package` of this computer's target, from the same plan. In doctor it
  is a warning, since doctor builds nothing. `package` refuses (D9).

`doctor --json` adds:

```json
"resources": {
  "cores": 16, "mem_total": 17179869184, "mem_available": 9663676416,
  "disk_free": 227633266688, "disk_need": 6549825126,
  "jobs": 7, "gen_jobs": 6, "gen_job_bytes": 1279262720,
  "gen_job_source": "game", "warnings": ["..."]
}
```

A value that is unknown is `null`.

`package` prints its decision as the compile starts, through the
progress view:
`build: 7 jobs, generated code 6 at a time (9.0 GB available, about 1.2 GB per job)`.
After the step it prints the measured peak:
`build: largest compile job 1.1 GB`.

The wizard (Go):

- **Checks** gets a "This computer" row from `resources`, for example
  "16 GB memory (9 GB free now), 16 cores, 212 GB free. The build will
  compile 7 files at a time." It shows as a warning when `warnings` is
  not empty, with the CLI's warning in a player's words. It never blocks.
- The wizard keeps its own disk check before the clone, which runs when
  no CLI exists yet. After `doctor`, it uses the larger of `NeedBytes`
  and `disk_need`.
- A `disk` refusal from `package` (D9) is shown like the other refusals,
  through its `refused: disk` code. The page shows the CLI's message and
  the fix, and offers a Retry once space is freed.
- **Settings:** `Settings.Jobs int` (`json:"jobs,omitempty"`, 0 means
  Automatic). The Summary page shows it as "Build jobs: Automatic
  (7 at a time)", with the choices 1 to `cores`. A non-zero value adds
  `--jobs N` to `package` and to its `enhance hud` run.
- The wizard never offers `--ignore-disk-space`.
- The wizard never queries memory itself. `doctor --json` is the one
  source, as for the targets.

### D6: The job count never changes the output

- `-j`, `XBR_GEN_JOBS`, `XBR_GEN_TARGETS` and the injected include are not
  in `compile_inputs`' `-D` list. They are not in the options digest, the
  manifest or any bundle name. A test asserts that the compile key is the
  same for jobs 1 and 8.
- A job pool changes only the order Ninja runs the commands in. The
  compile and link command lines are the same. The toolkit's reproducible
  flags and `-Wl,--pdb=` already make the exe independent of the build
  folder.
- `upscale_all` keeps its results in item order. The HUD stage key
  (`hud_record`) has no job count. Measured: the same pack sha256 at 1
  and 8 workers.
- The release gate (tasks 8.3) builds the windows and macos exes at
  `--jobs 1` and with automatic jobs, and compares the sha256s.

### D7: Names

| What | Name |
|---|---|
| CLI flags | `--jobs N` on `build`, `all`, `package` and `enhance hud`. On `enhance hud` it already exists, and only its default changes. `--ignore-disk-space` on `analyze`, `build`, `all`, `package` and `enhance hud` (D9; `import` keeps its own check). |
| game.toml | `[build.resources]`: `gen_job_mib` (int, MiB), `tool_mib` (int, MiB), `tool_step` (string), `generate_mib` (int, MiB, default 1024), `tree_mib` (int, MiB, default 512), `gen_targets` (strings, default `[build] exe`) |
| CMake | `XBR_GEN_JOBS`, `XBR_GEN_TARGETS`, pool `xbr_gen`, `cmake/xbr-jobs.cmake` |
| state | `.git/xbr/resources.json` |
| doctor JSON | `resources` |
| plan JSON | `disk` (D9), refusal code `disk` |
| wizard setting | `jobs` in `settings.json` |

No environment variable: `--jobs` is enough, and `CMAKE_BUILD_PARALLEL_LEVEL`
does nothing because the CLI always passes `-j`.

### D8: No memory cap

No memory cap, now or as a later change (the user, 2026-10-18). A cap
ends the build when it is reached, and the player still has no build.
Sizing (D3) is the only control. This change sets no limit flag on the
Job Object of D1 and starts no cgroup.

### D9: Low disk refuses before the first stage

A build that fills the disk stops halfway and leaves a tree that is not
complete. So `package`, `import`, `analyze`, `build`, `all` and `enhance
hud` add up what the stages they will run write. When that need is over
the free space on any volume, they refuse before the first stage runs.
`import` on its own keeps the check it already had (`dump.py`'s
`check_space`, the dump's size against the free space) and takes no
`--ignore-disk-space`; `package` counts its import stage with the rest.

The need per stage, counted only for the stages the run's plan will run
(a current stage writes nothing):

| Stage | Folder | Estimate | Measured (cat) |
|---|---|---|---|
| setup | build | what is missing: `.venv` 256 MiB, llvm-mingw 1 GiB, the toolkit 256 MiB | 216 MB, 762 MB, about 100 MB |
| import | build | the dump's file sizes in full: the new files are written before the old `game_files/` is removed. Before the first import (doctor), `[build.resources] game_files_mib` | 3.1 GB |
| generate | build | `[build.resources] generate_mib`, default 1024 | `analysis/` plus gen/, about 0.3 GB (1.0 GB in a dev tree) |
| build | build | `[build.resources] tree_mib` per target, default 512 | 141 and 146 MB |
| enhance hud | build | twice the last pack's size (`dist/enhance/hud` plus the pack store), else 512 MiB | 159 MB, linked into the store |
| package | out | when the files are staged again: 512 MiB, plus `game_files/` when the staging tree is on another volume than the build folder (no clone or hard link there); when the bundle is wrapped again: `game_files/` for a full one, the patch payload for a patch | bundle 3.5 GB |

- The real run counts the stages its own `--plan` would run, and the
  output the plan expects (a full bundle or a patch). When that plan
  cannot be made, it counts every stage it names.
- Each volume (`os.stat().st_dev`) needs the sum of the stages that write
  to it, plus 1 GiB of slack. The 1 GiB matches the wizard's
  `BundleNeed`, and it is the only extra amount. Stage outputs that a
  rerun replaces in place (the trees, gen/) are counted in full. That
  costs at most about 1.5 GiB of overestimate.
- A first cat run on one volume, after setup, needs 3.1 (import) + 1.0 +
  0.5 + 3.6 (package) + 1 (slack) = about 9.2 GB. With the game files
  already imported, it needs about 6.1 GB. Setup adds up to 1.5 GiB.
- `package --plan --json` gains
  `"disk": [{"path", "free", "need", "stages": {"import": bytes, ...}}]`.
  When the space is short, `output.kind` is `"none"` with the why code
  `disk`.

The refusal names the volume, the shortfall, each stage's share and the
fix:

```
disk: this build needs 5.6 GB in ~/blinx2 and 2.3 GB is free
  import    3.1 GB  game files from the dump
  generate  1.0 GB  analysis and generated code
  build     0.5 GB  build-pkg-win
  slack     1.0 GB
  (and 4.6 GB in ~/out for the bundle, which has 40 GB free)
free 3.3 GB in ~/blinx2: `blinx2 clean` shows what it can remove (old bundles in
dist/, the other targets' build trees), or move the build folder to a
larger drive; --ignore-disk-space builds anyway, and the build stops if the
disk fills
refused: disk
```

**Override:** `--ignore-disk-space` turns the refusal into the same text
as a warning. The estimate can be wrong where the filesystem compresses
or deduplicates (btrfs on SteamOS and the Linux/Proton host, APFS clones), and a
developer may know the space is there. The wizard does not offer it
(D5). `xbr clean`'s dry run already lists the space it would free, so
the fix points to it, and not to a new command.

## Risks / Trade-offs

- **Available memory changes during the build.** Sizing happens once, at
  the start, against the reserve alone. The rule is that the workstation
  is given to the build. A player who opens a game during the build can
  still swap.
- **The measured peaks are lower bounds.** The Mac was swapping, and macOS
  RSS leaves out compressed pages. With no margin on `G`, a host whose
  peak is higher swaps a little until its first build records its own
  peak (D1), which then raises `G`.
- **RSS is not commit.** On Windows, `PeakProcessMemoryUsed` is committed
  memory, which is larger than RSS. A Windows measurement can therefore
  raise `G` above the Mac figure. That is the safe side.
- **Native Windows and Linux clang were not measured here.** They run the
  same LLVM, so they should land close to the llvm-mingw numbers.
- **Slower small machines.** On 8 GB the generated code compiles 2 at a
  time. That is about 80 s more than today on the windows target, against
  a build that today may not finish.
- **The memory size estimate is crude** (40 to 139 MiB per MB measured).
  It is only a fallback, and each game should set `gen_job_mib`.
- **The disk refusal can be wrong** on a filesystem that compresses or
  deduplicates. `--ignore-disk-space` covers that, and the estimate
  errs high.

## Open Questions

None. The user answered the four questions of the first draft
(2026-10-18):

- The tester has 24 GB of RAM and only reported a crash (Context).
- There is no memory cap (D8).
- The doctor checks on the Deck and on Windows run at implementation
  time (tasks 8.4).
- Low disk refuses (D9).
