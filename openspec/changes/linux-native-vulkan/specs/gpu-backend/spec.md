## ADDED Requirements

### Requirement: D3D11 backend on Linux through dxvk-native
On Linux x86-64, `RECOMP_PB_BACKEND=d3d11` SHALL select the same D3D11 backend source (`nv2a_pb_d3d11.c`) built against DXVK-native, with HLSL compiled to DXBC by vkd3d-shader and the swap chain bound to the SDL3 window. Window, input and shader-compiler access SHALL go through a host seam, so the renderer logic is shared by Windows, Proton and native Linux and no separate Linux renderer exists. The native Linux run SHALL be held to the same D3D11 golden references as the Proton run.

#### Scenario: Native golden on the Deck
- **WHEN** the D3D11 golden scenarios run natively on the Deck with the `linux` package
- **THEN** every frame passes against `analysis/golden/golden.json` within its D3D11 limits, and flips/s is recorded beside the native Windows run of the same build

#### Scenario: Win32 seam unchanged
- **WHEN** the host seam is introduced and the Windows build runs the D3D11 golden on native Windows
- **THEN** each frame's verdict and the flips/s match the build before the seam within the performance tolerance

### Requirement: The native Linux renderer is opt-in at build time
The CMake option `XBOXRECOMP_DXVK_NATIVE` SHALL default OFF, so a plain POSIX Linux build, the POSIX ctests and `install_deps.sh` need neither DXVK nor vkd3d-shader. The CLI's `linux` build target SHALL turn it ON. On Linux, `RECOMP_PB_BACKEND` SHALL default to `d3d11` in a build with the option ON and to `cpu` otherwise.

#### Scenario: Plain POSIX Linux build
- **WHEN** the toolkit is configured on Linux x86-64 without `XBOXRECOMP_DXVK_NATIVE`
- **THEN** it builds and runs `tests/posix_ctest.sh` with 0 FAIL, with no DXVK or vkd3d-shader present, and the game defaults to the CPU render path

#### Scenario: Shipped Linux package
- **WHEN** the `linux` package built by the CLI runs with `RECOMP_PB_BACKEND` unset
- **THEN** the log shows the D3D11 backend on DXVK-native

### Requirement: Native Linux is not a third backend
Native Linux SHALL use the D3D11 backend's renderer source, so a renderer change made for D3D11 covers it. A visible change in the D3D11 backend's SDL host (window, overlay, sizing, input) SHALL be mirrored in the Metal backend's SDL presenter where it applies, or recorded in TASKS.md. A workaround needed only under DXVK-native SHALL be recorded in TASKS.md.

#### Scenario: Overlay change in the SDL host
- **WHEN** a change alters how the enhance-menu overlay is drawn by `d3d11_host_sdl.c`
- **THEN** the same change lands in the Metal presenter in the same merge, or a TASKS.md follow-up names it
