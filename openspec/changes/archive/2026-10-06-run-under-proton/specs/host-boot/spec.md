## MODIFIED Requirements

### Requirement: Supported hosts
The host executable SHALL build and start from the same source files on:
- Windows x86-64, including running under Proton/Wine on Linux
- macOS arm64

Its boot sequence SHALL be the same on all of them. Only platform-specific primitives (error reporting, crash handling, symbol lookup, entry-point signature) MAY differ.

#### Scenario: macOS arm64 boot
- **WHEN** the executable is built for macOS arm64 and launched with valid game files
- **THEN** it reaches the guest entry point and prints the same initialization banner lines it prints on Windows

#### Scenario: Windows behavior preserved
- **WHEN** the executable is built for Windows with MSVC
- **THEN** it boots with the same order, outputs and failure behavior as the template-derived host before this change

#### Scenario: Proton boot
- **WHEN** the llvm-mingw Windows x86-64 build is launched under Proton with valid game files
- **THEN** it reaches the guest entry point and prints the same initialization banner lines, and those lines reach the launching terminal or the bench's log capture

### Requirement: Refuse configurations the host cannot honor
The host SHALL check, before entering guest code, for configuration that needs hardware-register (MMIO) fault trapping. On a host whose fault handling cannot decode and resume the faulting instruction, it SHALL either refuse that configuration with a message that names the setting, or ignore the setting with a message saying it was ignored. It SHALL NOT arm a trap it cannot service. Whether a host can service MMIO SHALL depend on the host's OS and CPU architecture, not on which compiler built it.

#### Scenario: AC'97/APU trapping requested on a host that cannot service it
- **WHEN** `RECOMP_AC97_READY` is set and the host has no fault decoder (for example x86-64 Linux)
- **THEN** stderr has `[ENV] RECOMP_AC97_READY: audio unsupported on this host; ignored`, the emulated APU is not started, and boot continues

#### Scenario: AC'97/APU trapping requested on macOS arm64
- **WHEN** `RECOMP_AC97_READY` is in effect and the host is macOS arm64 (Linux arm64 by construction, untested)
- **THEN** the emulated APU is started and its register faults are decoded from the signal context and serviced (`audio`)

#### Scenario: AC'97/APU trapping on Windows
- **WHEN** `RECOMP_AC97_READY` is set and the host is Windows x86-64, built with MSVC or llvm-mingw, natively or under Proton
- **THEN** the emulated APU is started and its register faults are serviced, as before this change
