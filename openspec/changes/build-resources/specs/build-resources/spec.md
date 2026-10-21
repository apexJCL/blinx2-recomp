## ADDED Requirements

### Requirement: The CLI reads the machine's cores, memory and disk
The CLI SHALL read the usable cores, the total and available RAM, and the free disk with the Python standard library on Linux, macOS and Windows. On Linux it SHALL bound the available RAM and the cores by the process's cgroup v2 limits when they are set. On Windows the available RAM SHALL be the smaller of the free physical memory and the free commit. A value it cannot read SHALL be reported as unknown and SHALL NOT fail any command.

#### Scenario: Inside a container with a memory limit
- **WHEN** `/proc/meminfo` reports 30 GiB available and the cgroup's `memory.max` minus `memory.current` is 6 GiB
- **THEN** the available RAM used for sizing is 6 GiB

#### Scenario: Memory unknown
- **WHEN** the available RAM cannot be read
- **THEN** the build uses at most 4 jobs, and `doctor` says the memory is unknown

### Requirement: Builds size their parallelism to the available memory
`build`, `all` and `package` SHALL compile with `jobs = clamp(gen_jobs + floor((budget - gen_jobs × G) / 256 MiB), gen_jobs, cores)`, where `budget` is the available RAM less a reserve of 10% of the total RAM, at least 1 GiB and at most 2 GiB, and no other margin, `G` is the per-job estimate for the generated code, and `gen_jobs = clamp(floor(budget / G), 1, cores)`. With Ninja and CMake 3.24 or later, the targets in `[build.resources] gen_targets` (default `[build] exe`) SHALL compile in a Ninja job pool `xbr_gen` of depth `gen_jobs`, set by a CMake file the CLI injects, with no change to the game's `CMakeLists.txt`. Otherwise `jobs` SHALL equal `gen_jobs`. `G` SHALL be the larger of `[build.resources] gen_job_mib` (else 140 MiB per MB of the largest generated file, at least 512 MiB) and the last measured compile peak for the target. `--jobs N` SHALL set both counts to N and warn when N is above the computed figure. No memory limit SHALL be set on any process, and the CLI SHALL have no memory cap option.

#### Scenario: A 16 GB machine with 16 threads
- **WHEN** cat is packaged with 9 GiB available, 16 GiB total and 16 cores, and no measured peak
- **THEN** `G` is 1220 MiB from game.toml, the reserve is 1.6 GiB, the generated code compiles 6 at a time, and `cmake --build` runs with `-j 7`

#### Scenario: Override
- **WHEN** `package windows --jobs 2` runs
- **THEN** `cmake --build` runs with `-j 2`, the pool depth is 2, and the output names the override

#### Scenario: A measured peak raises the estimate
- **WHEN** an earlier build of the target measured a 1.4 GiB compile peak and game.toml gives 1220 MiB
- **THEN** `G` is 1.4 GiB, and doctor names the measurement as its source

### Requirement: Each external step reports its peak memory
The CLI SHALL measure the peak memory of the largest process of each external step it runs: through `wait4` on Linux and macOS, through an accounting-only Job Object on Windows. The HUD workers SHALL report their own peak. Peaks SHALL be kept by step and target in `.git/xbr/resources.json`, apart from the stage keys, and `xbr clean` SHALL remove the file. A failed measurement SHALL record nothing and SHALL NOT fail the step.

#### Scenario: Package records the compile peak
- **WHEN** `package windows` compiles the generated code
- **THEN** the log prints the largest compile job's peak, and `resources.json` holds it under `compile:windows`

### Requirement: The HUD upscale sizes its workers the same way
`enhance hud` without `--jobs` SHALL run `clamp(floor((budget - 512 MiB) / H), 1, min(cores, items))` workers, with `H` the larger of 128 MiB and the last measured worker peak. `--jobs N` SHALL set N. `package` SHALL pass its `--jobs` to the HUD remake.

#### Scenario: Small machine
- **WHEN** `enhance hud` runs with 1 GiB of budget
- **THEN** it starts 4 workers, not one per CPU

### Requirement: The job count never changes the output
The job counts, the pool depth and the injected CMake file SHALL NOT enter any stage key, the options digest, `manifest.json` or a bundle name. The exe and the HUD pack SHALL be the same bytes at any job count.

#### Scenario: One job against automatic
- **WHEN** `package windows` runs once with `--jobs 1` and once without, from the same inputs
- **THEN** the compile stage key is equal and the exe sha256s are equal

### Requirement: doctor says what the build will do
`doctor` SHALL print the total and available memory, the cores, the free disk in the build folder against the disk a `package` of this computer's target needs, and the job counts with the source of `G` (game.toml, measured, or estimated). It SHALL warn when the budget is under `G`, when the available RAM is under the largest tool step's peak plus the reserve, naming the step and its peak (`[build.resources] tool_step` and `tool_mib`, or measured), and when the free disk is under the need. These warnings SHALL NOT be problems and SHALL NOT block a build; low memory SHALL never stop a build. `doctor --json` SHALL hold a `resources` object with `cores`, `mem_total`, `mem_available`, `disk_free`, `disk_need`, `jobs`, `gen_jobs`, `gen_job_bytes`, `gen_job_source` and `warnings`, with `null` for unknown values. `package` SHALL print the same sizing when the compile starts.

#### Scenario: Low memory
- **WHEN** `doctor` runs with 2 GiB available and cat's `G` of 1.5 GiB
- **THEN** it prints `build jobs: 1`, a warning to close other programs, and a warning that disasm needs about 1.7 GB in one process, and `blocked` stays false

### Requirement: The wizard shows the machine and offers a job setting
The build wizard's Checks page SHALL show a "This computer" row from `doctor --json` `resources`: memory, cores, free disk and how many files the build will compile at a time, as a warning when `warnings` is not empty, and never blocking. The wizard SHALL keep a "Build jobs" setting (Automatic, or 1 to the cores) in its settings file and SHALL pass a number as `--jobs N` to `package` and `enhance hud`. The wizard SHALL NOT read the memory itself.

#### Scenario: Automatic
- **WHEN** the setting is Automatic
- **THEN** the Summary reads "Build jobs: Automatic (9 at a time)" from doctor, and no `--jobs` is passed

#### Scenario: A set number
- **WHEN** the player picks 2
- **THEN** `settings.json` holds `"jobs": 2`, and the wizard runs `package <target> --jobs 2 ...` and `enhance hud --jobs 2 ...`

### Requirement: A build refuses when the disk is short
`package`, `import`, `analyze`, `build`, `all` and `enhance hud` SHALL add up, per volume, the bytes the stages their plan will run write, plus 1 GiB of slack per volume, and SHALL refuse before the first stage runs when the need is over the free space on any volume. A current stage SHALL count nothing. The estimates SHALL be: setup, what it will fetch (`.venv` 256 MiB, llvm-mingw 1 GiB, the toolkit 256 MiB); import, the dump's file sizes less the `game_files/` it replaces; generate, `[build.resources] generate_mib` (default 1024); build, `[build.resources] tree_mib` per target (default 512); `enhance hud`, twice the last pack's size, else 512 MiB; package, in the output folder, `game_files/` plus 512 MiB, plus `game_files/` again when the staging tree is on another volume than the build folder. The refusal SHALL name each short volume with its need and free space, list each stage's share, give the fix (`clean` and what it can remove, or a larger drive), name `--ignore-disk-space`, and end with `refused: disk`. `--ignore-disk-space` SHALL turn the refusal into a warning. `package --plan --json` SHALL report the need per volume and stage as `disk`, and `output.kind = "none"` with the why code `disk` when space is short. The wizard SHALL show the refusal and its fix, and SHALL NOT offer `--ignore-disk-space`.

#### Scenario: Not enough room for the import
- **WHEN** `package windows --dump <iso>` runs with 2.3 GB free in the build folder and a 3.1 GB dump
- **THEN** it refuses before the import with the need of about 5.6 GB, the import, generate, build and slack lines, the fix and `refused: disk`, and nothing is written

#### Scenario: Override
- **WHEN** the same run is given `--ignore-disk-space`
- **THEN** the same text is printed as a warning and the build runs

#### Scenario: Current stages cost nothing
- **WHEN** the game files are imported and gen/ is current, and `package windows` runs
- **THEN** the need counts only the build tree, the bundle and the slack
