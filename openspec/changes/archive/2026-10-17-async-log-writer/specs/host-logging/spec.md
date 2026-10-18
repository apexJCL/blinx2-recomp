## ADDED Requirements

### Requirement: A default run prints little, and every line whole
With no trace key set, the runtime SHALL print under five lines a second in steady play and bursts only at boot, in loads and at exit; each line that remains SHALL be written by one call. stdout and stderr SHALL stay unbuffered, so the crash report, the `[UNIMPL]` line before an `abort()` and the watchdog's report reach the file as they do today, and a tool that tails a running log sees a line when it is printed.

#### Scenario: Ten minutes of mission 1-2 on native Windows
- **WHEN** the game plays mission 1-2 for ten minutes with `RECOMP_TRACE=pacing` and no other key
- **THEN** the log is under 5 MB, and the 1-2 flip p95 is within 1-1's band

#### Scenario: Untranslated-instruction trap
- **WHEN** the game boots with `RECOMP_DEBUG=unimpl_trap`
- **THEN** the log's last line is the `[UNIMPL] ... REACHED` line printed before the `abort()`

### Requirement: Per-call file records are a trace
The kernel bridge's `[READ]` and `[WRITE]` records (one per `NtReadFile` with an event or APC, one per `NtWriteFile` of 4 KB or more) SHALL print only under `RECOMP_TRACE=file`. The `[PATH]` and `[FILE]` open lines are unchanged.

#### Scenario: A level load by default
- **WHEN** a level loads with no trace key set
- **THEN** the log has its `[PATH]` and `[FILE]` lines and no `[READ]` or `[WRITE]` line

### Requirement: The kernel call summary is printed where it answers a question
The `[KERNEL] summary` block (cumulative kernel calls, the ordinal of the call that produced it, esp, and the six most-called ordinals) SHALL be printed once when the process ends through an exit path the host controls (`exit`, a window's `ExitProcess`, `HalReturnToFirmware`) and in the watchdog's hang report. The periodic form, every 2 s, SHALL print only under `RECOMP_TRACE=kernel_summary`.

#### Scenario: Normal quit
- **WHEN** the title quits through `HalReturnToFirmware` on any host
- **THEN** the log holds exactly one `[KERNEL] summary` block, near its end, and none during play

#### Scenario: Hang
- **WHEN** the watchdog fires on a run that stopped making progress
- **THEN** its report includes the `[KERNEL] summary` block after the ICALL ring

### Requirement: The async log writer is a recorded follow-up
The runtime MAY later carry stdout and stderr through a pipe and one writer thread, as design.md D4 of `async-log-writer` describes. That work SHALL start only on evidence: a default-run profile with 5% or more of a game thread's samples in the log's write path or a frame-time spike aligned with a log burst, or a high-rate trace on Windows or Proton whose writes perturb its own measurement.

#### Scenario: No evidence
- **WHEN** default-run profiles show the log off every game thread's critical path
- **THEN** stdio stays unbuffered and synchronous, and no writer thread exists
