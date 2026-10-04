# host-boot Specification

## Purpose
Defines how the host executable starts on each supported platform: initializing the Xbox runtime in a fixed order, finding the game files, starting the recompiled entry point, and failing loudly and early when it can't.

## Requirements

### Requirement: Supported hosts
The host executable SHALL build and start on Windows x64 and on macOS arm64 from the same source files. Its boot sequence SHALL be the same on both. Only platform-specific primitives (error reporting, crash handling, symbol lookup, entry-point signature) MAY differ.

#### Scenario: macOS arm64 boot
- **WHEN** the executable is built for macOS arm64 and launched with valid game files
- **THEN** it reaches the guest entry point and prints the same initialization banner lines it prints on Windows

#### Scenario: Windows behavior preserved
- **WHEN** the executable is built for Windows with MSVC
- **THEN** it boots with the same order, outputs and failure behavior as the template-derived host before this change

### Requirement: Boot order
The host SHALL initialize the runtime in this order, and SHALL NOT enter guest code until every step has succeeded or been explicitly declared optional:
1. install crash diagnostics
2. load the XBE
3. map the Xbox memory layout
4. start the emulated APU (optional; only when requested and the host supports it, see below)
5. initialize the kernel
6. set the game and save directories
7. initialize the kernel bridge
8. set the guest stack pointer to the top of the Xbox stack
9. build the dispatch table (optional)
10. start the hang watchdog
11. call the recompiled entry point (`0x0029A1DA`)

#### Scenario: Optional dispatch table
- **WHEN** the flat dispatch table cannot be allocated
- **THEN** the host prints one line saying indirect calls will use the binary search, and continues booting

#### Scenario: Crash diagnostics armed before guest code
- **WHEN** the first guest instruction executes
- **THEN** the crash diagnostics from `host-crash-diagnostics` are already installed

### Requirement: Game file location
The host SHALL load `game_files/default.xbe` and use `game_files/` as the game data root, both resolved relative to the current working directory. It SHALL accept forward-slash paths on every host.

#### Scenario: Run from the project root
- **WHEN** the executable is launched with the project root as the working directory and `game_files/default.xbe` exists
- **THEN** the XBE loads and the printed size equals the file's size in bytes

### Requirement: Startup failures are reported and fatal
When a required startup step fails, the host SHALL write a message to stderr naming the step, the path or resource involved, and a likely fix. It SHALL then exit with a non-zero status without entering guest code. On Windows it SHALL also show the existing error dialog. On other hosts it SHALL NOT need a GUI to report the failure.

#### Scenario: Missing XBE
- **WHEN** the executable is launched from a directory with no `game_files/default.xbe`
- **THEN** stderr names the path it tried, and the process exits non-zero before memory mapping

#### Scenario: Memory layout unavailable
- **WHEN** the Xbox memory layout cannot be mapped
- **THEN** stderr says the memory layout failed to initialize, and the process exits non-zero

### Requirement: Refuse configurations the host cannot honor
The host SHALL check, before entering guest code, for configuration that needs hardware-register (MMIO) fault trapping. On a host whose fault handling cannot decode and resume the faulting instruction, it SHALL either refuse that configuration with a message that names the setting, or ignore the setting with a message saying it was ignored. It SHALL NOT arm a trap it cannot service.

#### Scenario: AC'97/APU trapping requested on macOS arm64
- **WHEN** `RECOMP_AC97_READY` is set and the host is macOS arm64
- **THEN** stderr states that `RECOMP_AC97_READY` is unsupported on this host and was ignored, the emulated APU is not started, and boot continues

#### Scenario: AC'97/APU trapping on Windows
- **WHEN** `RECOMP_AC97_READY` is set and the host is Windows x64
- **THEN** the emulated APU is started and its register faults are serviced, as before this change

### Requirement: Clean exit
When the guest entry point returns, the host SHALL shut down the kernel and memory layout, release the XBE buffer, and exit with status 0.

#### Scenario: Guest returns
- **WHEN** the recompiled entry point returns normally
- **THEN** the host prints that the game returned, runs shutdown, and exits 0
