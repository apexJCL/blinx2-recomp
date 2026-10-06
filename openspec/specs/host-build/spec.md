# host-build Specification

## Purpose
Defines what this project's build must produce on each supported platform: a single executable that links the xboxrecomp toolkit, with only the host libraries that platform provides.

## Requirements

### Requirement: One executable per supported host
Configuring and building the project SHALL produce one executable named after the CMake project (`cat_recomp`) on each supported target:
- Windows x86-64, built with an llvm-mingw toolchain, natively or cross-compiled from another host. This is the tested Windows toolchain. MSVC builds are kept possible (the `if(MSVC)` CMake block from the template) but are unverified: no Windows machine has built one.
- macOS arm64 (Clang).

On macOS the executable SHALL be a console program (no app bundle), so that its stdout and stderr reach the terminal. The build SHALL NOT hard-code host-specific toolchain paths. A cross toolchain SHALL be located through a configurable root or `PATH`.

#### Scenario: macOS build
- **WHEN** `scripts/pipeline.sh build` runs on macOS arm64 after a successful recomp
- **THEN** `build/cat_recomp` exists, is a Mach-O arm64 executable, and can be run from a terminal

#### Scenario: Windows build with MSVC (unverified)
- **WHEN** the project is configured and built with MSVC on Windows
- **THEN** it produces `cat_recomp.exe` with the subsystem, link options and libraries of the template's `if(MSVC)` block. No such build has been made; treat this scenario as untested

#### Scenario: llvm-mingw cross build
- **WHEN** the project is configured with the llvm-mingw toolchain file and the toolchain root is given through `LLVM_MINGW_ROOT` or `PATH`
- **THEN** it produces `cat_recomp.exe` as a PE32+ x86-64 executable, with no source or CMake edits needed between the macOS host and a Linux host

### Requirement: Platform-specific host libraries
The build SHALL link Windows SDK libraries (D3D11, DXGI, DXGUID, XInput, WinMM, DbgHelp) only on Windows. On other hosts it SHALL link nothing Windows-specific, and SHALL get its graphics, input and crypto dependencies through the toolkit's targets.

#### Scenario: No Windows libraries on macOS
- **WHEN** the project is configured on macOS
- **THEN** configuring and linking succeed with no reference to any Windows SDK library

### Requirement: Toolkit dependencies resolve from the project
Configuring the project from a clean build directory SHALL succeed on every supported host without editing the toolkit. In particular, dependencies the toolkit links publicly (such as OpenSSL on non-Windows hosts) SHALL be visible to this project's executable.

#### Scenario: Clean configure on macOS
- **WHEN** `build/` is deleted and the project is configured on macOS
- **THEN** configuration completes with no "target was not found" errors

### Requirement: Host symbols available for diagnostics
On every host, the executable SHALL carry enough symbol information for `host-crash-diagnostics` to name the generated function containing a fault.
- **macOS:** the build SHALL NOT strip the executable's local symbol table (no `strip -x` and no `-Wl,-x`). It SHALL NOT need dynamic symbol export (`-export_dynamic`) for this.
- **Windows with MSVC (unverified):** the template's link options are kept unchanged.
- **Windows with llvm-mingw:** the build SHALL emit a PDB, containing at least public symbols, next to the executable.

#### Scenario: Symbols present in a Release build on macOS
- **WHEN** a Release build is produced on macOS
- **THEN** the symbol for `sub_00012000` can be resolved from its address in the running executable, and the link line contains neither `-export_dynamic` nor `-x`

#### Scenario: PDB next to a MinGW build
- **WHEN** a Release build is produced with llvm-mingw
- **THEN** `cat_recomp.pdb` exists next to `cat_recomp.exe` and contains the `sub_00012000` public symbol

### Requirement: Generated code builds for every target
The generated C SHALL compile unchanged for every supported target. Recovered function names that collide with a declaration or export of any target's C runtime or system libraries SHALL be renamed before code generation.

#### Scenario: CRT name collision
- **WHEN** a recovered function is named `fpclass`, which MinGW's `<math.h>` declares
- **THEN** the generated code names it `fpclass_<ADDR>`, and the generated sources compile for both macOS arm64 and Windows x86-64
