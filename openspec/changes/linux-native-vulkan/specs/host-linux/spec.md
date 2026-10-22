## ADDED Requirements

### Requirement: Native Linux x86-64 build
The toolkit and the game SHALL build for Linux x86-64 against the Steam Linux Runtime 3.0 (sniper) ABI. The build SHALL run on the Mac, in a pinned builder image through `docker build --output` or with a pinned clang and sniper sysroot. The binary SHALL run on SteamOS and on other glibc distributions that have Steam, without Proton or Wine.

#### Scenario: Mac-built, Deck-run ctests
- **WHEN** the POSIX ctests are built on the Mac for Linux x86-64 and run natively on the Deck
- **THEN** `tests/posix_ctest.sh` reports 0 FAIL, and no build step ran on the Deck

### Requirement: Trapped MMIO on x86-64 Linux
On x86-64 Linux the POSIX fault handler SHALL decode faulting guest MMIO loads and stores with the x86-64 decoder and emulate them as the arm64 POSIX path does. The AC'97 and OHCI trap paths SHALL then be available on that host.

#### Scenario: Synthetic trap
- **WHEN** the fault-path ctest performs a load and a store to a trapped MMIO page on x86-64 Linux
- **THEN** the device model sees both accesses with the right width and value, and execution resumes after the faulting instruction

### Requirement: Case-sensitive file systems
On a case-sensitive file system, a guest file open that misses on the exact name SHALL retry once with a case-insensitive match in the same directory, and SHALL log one warning per path when the fallback is used.

#### Scenario: Wrong-case asset name
- **WHEN** the game opens a file whose on-disk name differs only in case
- **THEN** the open succeeds and the log has one case-fallback warning for that path

### Requirement: Native Linux package
The `linux` package target SHALL produce a tar with the exe, the pinned DXVK-native and vkd3d-shader shared libraries (and SDL3 when the runtime lacks it) under `lib/`, an `$ORIGIN/lib` RPATH, a launcher, and the licence notices for the bundled libraries. The `linux` package SHALL be the default on SteamOS, with the `steamos` (Proton) package offered only as an opt-in route. On SteamOS, installing it SHALL add a Steam shortcut that runs under the Steam Linux Runtime 3.0 with `DXVK_WSI_DRIVER=SDL3`.

#### Scenario: Licence check
- **WHEN** the `linux` package is built
- **THEN** it holds DXVK's own licence files, the LGPL-2.1 text with the exact vkd3d-shader source tarball link, and the zlib text for SDL3 if bundled, and a `readelf -d` check finds no bundled library that needs a GPL-only dependency

#### Scenario: Install on the Deck
- **WHEN** the `linux` package is installed on the Deck and launched from Steam
- **THEN** the game reaches the title on the D3D11 backend with no umu, Proton or Wine process running

### Requirement: SDL3 gate on native Linux
A Linux x86-64 build of the game on the CPU render path SHALL be built on the Mac and run on the Deck as SDL3's Linux gate: the POSIX ctests, a windowed `@attract` run with sound, and a virtual pad present at launch and one added after launch.

#### Scenario: Windowed attract with sound and pads
- **WHEN** the Mac-built Linux binary runs `@attract` windowed on the Deck in desktop mode for 30 s, with one `scripts/vpad.py` pad at launch and one created later
- **THEN** the log has `SDL <driver> renderer`, `[SDL3] audio initialized: driver <pipewire|pulseaudio>` and `host pad added`, and no build step ran on the Deck
