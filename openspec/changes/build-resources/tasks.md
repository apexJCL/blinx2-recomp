Conventions: **CLI** = a branch off `xboxrecomp-cli` `main` (a00a9c7 or
later) in its own worktree, commits authored and committed as the noreply
identity, no tracker ids, host names or private paths. **cat** = a branch
in its own worktree for `[build.resources]`, the CLI pin and docs. Design
decisions are cited as D1-D9. No toolkit change. Builds run on the Mac
only, under the Mac bench lock, at most `-j8` while measuring. Goldens are
skipped: the exe bytes do not change (D6), which task 8.3 checks.

Phase map:

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 1 Queries and measured runs | CLI | M | - |
| 2 Sizing, `--jobs` and the pool | CLI | M | 1 |
| 3 HUD workers | CLI | S | 1, 2 |
| 4 doctor and the package log | CLI | S | 2 |
| 4b Disk refusal | CLI | S | 4 |
| 5 game.toml table and cat's values | CLI, cat | S | 2 |
| 6 Wizard | CLI `wizard/` | M | 4 |
| 7 Docs | CLI, cat | S | 1-6 |
| 8 Gates | Mac; Deck and Windows only with the user's OK | S | 7 |
| 9 Review and merge | orchestrator | XS | 8 |

## 1. Queries and measured runs (CLI)

- [x] 1.1 `resources.py`: `cores()`, `mem_total()`, `mem_available()`,
      `disk_free(path)` per D2, each returning `None` when unknown. Linux
      reads `/proc/meminfo` and the cgroup v2 files; macOS runs `sysctl`
      and `vm_stat`; Windows calls `GlobalMemoryStatusEx` through `ctypes`.
      The file paths and the commands are parameters, for the tests.
- [x] 1.2 `host.run` and `progress.run_step` return the peak of the
      largest process (D1): `os.wait4` on POSIX (KiB on Linux, bytes on
      macOS), an accounting-only Job Object on Windows. Any failure gives
      `None` and never fails the step.
- [x] 1.3 `.git/xbr/resources.json`: record the peaks by step and target
      (`compile:<target>`, `tool:<module>` for disasm, func_id, abi and
      recomp, `hud:worker`, each keeping the max) with the job count, the date and the CLI version.
      `xbr clean` removes it.

## 2. Sizing, `--jobs` and the pool (CLI)

- [x] 2.1 `resources.plan(target, jobs=None)`: the D3 formula, giving
      `jobs`, `gen_jobs`, `G`, its source and the warnings. The reserve is
      10% of total RAM clamped to 1-2 GiB, with no other margin. `G` is the
      larger of the game.toml value (else the size estimate) and the
      measured peak.
- [x] 2.2 `cmake/xbr-jobs.cmake` as in D4, shipped as package data.
      `build()` passes `-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES`,
      `-DXBR_GEN_JOBS` and `-DXBR_GEN_TARGETS` when the generator is Ninja
      and CMake is 3.24 or later, else `jobs = gen_jobs`. The dev tree
      reconfigures only when the cached `XBR_GEN_JOBS` differs.
- [x] 2.3 `cmake --build -j <jobs>` in place of `os.cpu_count()`
      (`build.py:219`). `--jobs N` on `build`, `all` and `package`, passed
      through `compile_stage`.
- [x] 2.4 Keep the job values out of `incr.compile_inputs`, the options
      digest and the manifest (D6).
- [x] 2.5 Before `analyze` and `package` run the tool steps, warn when the
      available RAM is under `tool_mib` (or the measured tool peak) plus
      the reserve, naming `tool_step` and its peak ("disasm needs about
      1.7 GB"). Warn only: low memory never stops a build.

## 3. HUD workers (CLI)

- [x] 3.1 `enhance hud --jobs` default 0 now means "sized" (D3's
      `hud_jobs`), not one per CPU. `--jobs N` keeps its meaning.
- [x] 3.2 `_scale_task` returns its peak (D1). `upscale_all` records the
      largest as `hud:worker`.
- [x] 3.3 `package/tweaks.py` passes the run's `--jobs` to the HUD remake
      in place of `jobs=None`.

## 4. doctor and the package log (CLI)

- [x] 4.1 `doctor` lines `memory`, `cores`, `disk` and `build jobs`, plus
      the low-memory and low-disk warnings (D5). Warnings never add to
      `problems`.
- [x] 4.2 `doctor --json` gains `resources` (D5), with `null` for unknown
      values.
- [x] 4.3 `package` prints its sizing at the compile and the measured peak
      after it, in the progress view and in the plain log.

## 4b. Disk refusal (CLI)

- [x] 4b.1 `resources.disk_need(plan)`: the per-stage estimates of D9,
      summed per volume (`st_dev`) with 1 GiB of slack each.
- [x] 4b.2 `package`, `analyze`, `build`, `all` and `enhance hud`
      refuse before the first stage (`import` keeps `check_space`) with D9's text and `Refusal(...,
      "disk")`. `--ignore-disk-space` prints it as a warning instead.
- [x] 4b.3 `package --plan --json`: the `disk` list, and `output.kind =
      "none"` with the why code `disk`.
- [x] 4b.4 Wizard: the `disk` refusal shows the CLI's text and a Retry;
      no `--ignore-disk-space` anywhere in the wizard.

## 5. game.toml table and cat's values (CLI, cat)

- [x] 5.1 `manifest.py`: `[build.resources]` with `gen_job_mib` (INT),
      `tool_mib` (INT), `tool_step` (STR), `generate_mib` (INT, default
      1024), `tree_mib` (INT, default 512) and `gen_targets` (STRS,
      default `[build] exe`). The new-game template has the table
      commented out with the estimate's rule.
- [ ] 5.2 cat: `gen_job_mib = 1220`, `tool_mib = 1722`,
      `tool_step = "disasm"`, and the CLI pin
      moved to the merged sha.

## 6. Wizard (CLI `wizard/`)

- [x] 6.1 `runner`: parse `resources` into `Doctor.Resources` (pointers or
      a `Known` flag, so `null` stays unknown).
- [x] 6.2 `screens/checks.go`: the "This computer" row (D5), shown as a
      warning when `warnings` is not empty, and never blocking. The
      pre-clone disk check uses the larger of `NeedBytes` and `disk_need`
      once doctor has run.
- [x] 6.3 `hostinfo.Settings.Jobs` (`json:"jobs,omitempty"`). A "Build jobs"
      select on the Summary page: Automatic (with doctor's figure), then 1
      to `cores`.
- [x] 6.4 `model`: a non-zero `Jobs` adds `--jobs N` to `package` and to
      `enhance hud`.

## 7. Docs (CLI, cat)

- [x] 7.1 CLI README and `docs/`: `--jobs`, the doctor lines, the
      `[build.resources]` keys and how to measure them (the `build jobs`
      line after one build).
- [x] 7.2 cat `docs/`: the build page says what the wizard and doctor
      show on a small machine.

## 8. Gates

- [x] 8.1 CLI: `uv run pytest tests`, `uv run ruff check .` and
      `uv run ruff format --check .`. New tests:
      - `test_resources.py`: `/proc/meminfo` and cgroup fixtures (with and
        without `memory.max`, and `cpu.max`), `vm_stat` and `sysctl` text,
        a Windows-only `ctypes` case under `skipif`, and the D3 table as
        cases, including unknown memory and `--jobs` over the formula;
      - a measured run of a child that allocates 200 MB and reports at
        least that (POSIX), and one whose measurement fails and still
        runs;
      - the build argv: `-j`, the three `-D` values with Ninja, none
        without Ninja or with CMake under 3.24, and no reconfigure when the
        cached depth is equal;
      - `compile_inputs` equal for `--jobs 1` and `--jobs 8`;
      - `upscale_all` giving equal results at 1 and 3 workers;
      - `doctor --json` with `resources`, the warnings (the disasm one
        among them), and no new `problems`;
      - the disk need per stage and volume from plan fixtures, the
        refusal text and `refused: disk`, `--ignore-disk-space` as a
        warning, a current stage counting nothing, and the plan's
        `disk` field;
      - the `[build.resources]` keys and their defaults in `manifest.py`.
- [x] 8.2 Wizard: `wizard/check.sh` (gofmt, vet, test, staticcheck, the
      double build). New tests: the `disk` refusal page and Retry,
      `ParseDoctor` with and without
      `resources` (testdata `doctor-lowmem.json`), `checkRows` ok and
      warn, the model's args with and without `--jobs`, the settings round
      trip with `jobs`, and the select's choices.
- [x] 8.3 Mac, under the bench lock: `package windows` and `package macos`
      at `--jobs 1` and with automatic jobs give equal exe sha256s (D6);
      `doctor` and the package log show the sizing and a measured peak
      within 25% of the Context table; cat's `uv run pytest scripts` and
      ruff pass.
      Results (2026-10-18): at --jobs 8 (the rule's cap; automatic picks
      9-10 here) and at --clean --jobs 1, the exes and manifest.json are
      equal on both targets. The comparison was --jobs 8 against --jobs 1,
      not automatic jobs. The setup.exe and .dmg containers differ;
      the program inside does not. Measured peaks: compile:macos 1250 MiB
      (Context: 1220) and disasm 1711 MiB (1722). Logs are in
      runs/build-resources/gate-summary.txt.
- [x] 8.4 At implementation time (the user, 2026-10-18), `xbr doctor`
      only, no build, checking the memory, cores and disk lines against
      the host's own tools:
      - the Deck: read-only, under `flock -w 3600 ~/.recomp-run.lock`,
        against `free -b`, `nproc` and `df`;
      - the Windows workbench (`ssh <bench-host>-win`), taking
        `D:\bench\.bench-lock` as `notes/benches.md` describes, and only
        while the PC is already booted into Windows (never switch the
        boot), against `Get-CimInstance Win32_OperatingSystem` and
        `Get-PSDrive`.
      Message the orchestrator before each.
      Results (2026-10-18, CLI 0f2e844, no mismatch on either host):
      - Deck: doctor said 15.5 GB total and 12.2 GB available, 8 cores,
        and 245.7 GB free. `free -b` gave 15523667968 total and
        12190171136 available, `nproc` gave 8, and `df` gave
        245666250752 free. The cgroup memory.max is `max`. It sized
        8 jobs (8 generated, 1.3 GB each, from game.toml).
      - Windows: doctor said 34.3 GB total and 28.2 GB available,
        16 cores, and 5936.4 GB free on D:. Win32_OperatingSystem gave
        33469400 KiB total and 27574016 KiB free, there are 16 logical
        processors, and Get-PSDrive D gave 5936397361152 free. It sized
        16 jobs.
      - A doctor finding from before this change: on Windows the
        makensis hint reads `sudo apt install nsis`, a Linux command.
        It belongs to a follow-up, not to this change.

## 9. Review and merge (orchestrator)

- [ ] 9.1 Review of the CLI branch and the cat branch; fixes go to
      the branch's agent. The first review's fixes (2026-10-18):
      - [x] `package` counts the stages its plan runs and the plan's
            output: a current stage counts nothing, and a patch counts
            its payload, not the game files. The plan and the run check
            the same needs (test_package_disk_counts_what_runs).
      - [x] The wizard's plan passes `--out`, so the Summary judges the
            disk the bundle goes to.
      - [x] Saved build jobs above this computer's cores fall back to
            Automatic, shown and passed.
      - [x] Doctor counts the import before the first one, from the new
            `[build.resources] game_files_mib` (cat: 3187, the measured
            `game_files/`).
      - [x] D9's import row: the full dump, as the code counts it.
- [ ] 9.2 Squash-merge the CLI branch, then cat with the new pin.
      Packaging-only: no goldens and no Deck sync (CLAUDE.md, 2026-10-17).
