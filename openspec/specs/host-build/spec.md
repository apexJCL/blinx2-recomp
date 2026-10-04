# host-build Specification

## Purpose
Defines what this project's build must produce on each supported platform: a single executable that links the xboxrecomp toolkit, with only the host libraries that platform provides.

## Requirements

### Requirement: One executable per supported host
Configuring and building the project SHALL produce one executable named after the CMake project (`cat_recomp`) on Windows x64 (MSVC) and on macOS arm64 (Clang). On macOS the executable SHALL be a console program (no app bundle), so that its stdout and stderr reach the terminal.

#### Scenario: macOS build
- **WHEN** `scripts/pipeline.sh build` runs on macOS arm64 after a successful recomp
- **THEN** `build/cat_recomp` exists, is a Mach-O arm64 executable, and can be run from a terminal

#### Scenario: Windows build
- **WHEN** the project is configured and built with MSVC on Windows
- **THEN** it produces `cat_recomp.exe` with the same subsystem, link options and libraries as before this change

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
On every host, the executable SHALL carry enough symbol information for `host-crash-diagnostics` to name the generated function containing a fault. On macOS the build SHALL NOT strip the executable's local symbol table (no `strip -x` and no `-Wl,-x`). It SHALL NOT need dynamic symbol export (`-export_dynamic`) for this. On Windows the existing link options are kept unchanged.

#### Scenario: Symbols present in a Release build on macOS
- **WHEN** a Release build is produced on macOS
- **THEN** the symbol for `sub_00012000` can be resolved from its address in the running executable, and the link line contains neither `-export_dynamic` nor `-x`
