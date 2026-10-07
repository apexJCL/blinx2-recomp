## MODIFIED Requirements

### Requirement: One executable per supported host
Configuring and building the project SHALL produce one executable named after the CMake project (`cat_recomp`) on each supported target:
- Windows x86-64, built with an llvm-mingw toolchain, natively or cross-compiled from another host. This is the tested Windows toolchain. MSVC builds are kept possible (the `if(MSVC)` CMake block from the template) but are unverified: no Windows machine has built one.
- macOS arm64 (Clang).

On macOS the executable SHALL be a console program (no app bundle), so that its stdout and stderr reach the terminal. The build SHALL NOT hard-code host-specific toolchain paths. A cross toolchain SHALL be located through a configurable root or `PATH`.

#### Scenario: macOS build
- **WHEN** `blinx2 build` runs on macOS arm64 after a successful recomp
- **THEN** `build/cat_recomp` exists, is a Mach-O arm64 executable, and can be run from a terminal

#### Scenario: Windows build with MSVC (unverified)
- **WHEN** the project is configured and built with MSVC on Windows
- **THEN** it produces `cat_recomp.exe` with the subsystem, link options and libraries of the template's `if(MSVC)` block. No such build has been made; treat this scenario as untested

#### Scenario: llvm-mingw cross build
- **WHEN** the project is configured with the llvm-mingw toolchain file and the toolchain root is given through `LLVM_MINGW_ROOT` or `PATH`
- **THEN** it produces `cat_recomp.exe` as a PE32+ x86-64 executable, with no source or CMake edits needed between the macOS host and a Linux host
