## MODIFIED Requirements

### Requirement: Platform-specific host libraries
The build SHALL link Windows SDK libraries (D3D11, DXGI, DXGUID, XInput, WinMM, DbgHelp) only on Windows. On other hosts it SHALL link nothing Windows-specific, and SHALL get its graphics, input and crypto dependencies through the toolkit's targets, whose POSIX window, input and audio-device library is SDL3 (version 3.2 or newer, found with `find_package(SDL3 CONFIG)`); SDL2 and `sdl2-compat` SHALL NOT be linked or required.

#### Scenario: No Windows libraries on macOS
- **WHEN** the project is configured on macOS
- **THEN** configuring and linking succeed with no reference to any Windows SDK library

#### Scenario: SDL3 only
- **WHEN** the project is configured on macOS or Linux
- **THEN** the CMake cache holds `SDL3_DIR` and no `SDL2_DIR`, and the linked executable depends on `libSDL3` and not on `libSDL2`
