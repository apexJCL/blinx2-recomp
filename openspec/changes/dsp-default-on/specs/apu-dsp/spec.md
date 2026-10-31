## RENAMED Requirements

- FROM: `### Requirement: The APU DSP is a build option, default OFF`
- TO: `### Requirement: The APU DSP is a build option, default ON`
- FROM: `### Requirement: The apu_dsp key selects the DSP at run time, default the stub`
- TO: `### Requirement: The apu_dsp key selects the DSP at run time, default the JIT`

## MODIFIED Requirements

### Requirement: The APU DSP is a build option, default ON
The toolkit SHALL offer a CMake option `XBOXRECOMP_APU_DSP`, default ON for a target that has a dsp56300 archive and OFF for one that has none. With the option OFF the build SHALL neither fetch nor link dsp56300, and SHALL behave exactly as a build without the option. With it ON, the build SHALL take the dsp56300 1.0.0 prebuilt static library for its target from the release archive pinned by sha256 in `cmake/dsp56300.cmake`, link it into the APU library with the system libraries the Rust standard library needs (`CoreFoundation` and `Security` on Apple; `libunwind`, `ws2_32`, `userenv`, `ntdll`, `bcrypt`, `advapi32`, `kernel32` and `synchronization` under llvm-mingw), and define `XBOXRECOMP_APU_DSP` for `recomp_env`. A build tree that cached the option's former default OFF SHALL be turned ON once at its next configure, with a status line; an OFF given on the command line SHALL be kept.

#### Scenario: Default build
- **WHEN** the toolkit is configured in a fresh tree without `-DXBOXRECOMP_APU_DSP`, for a target that has an archive
- **THEN** the pinned archive is downloaded and checked, and dsp56300 is linked

#### Scenario: Tree configured before the default changed
- **WHEN** a tree whose cache holds the old option's OFF is configured again, without `-DXBOXRECOMP_APU_DSP`
- **THEN** the option becomes ON once, a status line says so, and a later `-DXBOXRECOMP_APU_DSP=OFF` is kept

#### Scenario: Stub-only build
- **WHEN** the toolkit is configured with `-DXBOXRECOMP_APU_DSP=OFF`
- **THEN** nothing is downloaded, no dsp56300 symbol is linked, and the game runs the stub

#### Scenario: Archive does not match its pin
- **WHEN** the option is ON and the downloaded or given archive's sha256 differs from the pin for its target
- **THEN** configuration fails with an error naming both hashes

#### Scenario: Target without an archive, default
- **WHEN** a target that has no dsp56300 archive (iPadOS, a universal macOS build, MSVC) is configured without `-DXBOXRECOMP_APU_DSP`
- **THEN** the option is OFF, nothing is downloaded, and no warning is printed

#### Scenario: Target without an archive, explicit ON
- **WHEN** `-DXBOXRECOMP_APU_DSP=ON` is given for a target that has no dsp56300 archive
- **THEN** each configure warns and the build goes on with the option OFF

#### Scenario: Download fails
- **WHEN** the option is ON for a target that has an archive and the download fails
- **THEN** configuration fails with an error naming `XBOXRECOMP_DSP56300_ARCHIVE` as the way to give a local copy and `-DXBOXRECOMP_APU_DSP=OFF` as the way to build without it

#### Scenario: Windows cross build
- **WHEN** the option is ON in an llvm-mingw cross build for `x86_64-pc-windows-gnu`
- **THEN** the program links, and imports only system DLLs (no `libunwind.dll`)

### Requirement: The apu_dsp key selects the DSP at run time, default the JIT
The toolkit SHALL have a config-tier `recomp_env` key `APU_DSP`, variable `RECOMP_APU_DSP`: `1` runs the APU's GP and EP on the DSP56300 JIT, while empty or `0` keeps the stub. Unset, it SHALL default to `1` in a build with `XBOXRECOMP_APU_DSP` and `XBOXRECOMP_APU_DSP_DEVICE`, and to the stub in any other build, with no line either way. A game's default for the key (`RECOMP_ENV_GAME_DEFAULTS`) SHALL win over this default, and the environment SHALL win over both. Any other value SHALL keep the stub and log one line. In a build without `XBOXRECOMP_APU_DSP`, an explicit `1` SHALL keep the stub and log one line saying the build has no APU DSP; in a build with it but without `XBOXRECOMP_APU_DSP_DEVICE`, an explicit `1` SHALL keep the stub and log one line saying the device is missing. The key SHALL NOT collide with `RECOMP_APU_DSP_ACK` or the `apu_dsp_ack` debug key: setting either of those SHALL NOT change `APU_DSP`, and `apu_dsp` SHALL NOT be accepted as a debug-list key.

#### Scenario: JIT by default
- **WHEN** `RECOMP_APU_DSP` is unset and the game sets no default for it, in a build with the DSP and its device
- **THEN** `recomp_env(RENV_APU_DSP)` reads `1`, the `apu_dsp_ack` and `apu_mixdown_all` overrides apply as for an explicit `1`, and no line is logged about the key itself

#### Scenario: Override line in the default case
- **WHEN** the key is unset, the DSP runs by default, and `RECOMP_APU_DSP_ACK` or `RECOMP_APU_MIXDOWN_ALL` is set
- **THEN** one line says the APU DSP, on by default, overrides that key, without naming `RECOMP_APU_DSP=1`

#### Scenario: Stub on request
- **WHEN** `RECOMP_APU_DSP` is empty or `0`, or the game's default is `0` and the variable is unset
- **THEN** `recomp_env(RENV_APU_DSP)` is NULL, `apu_dsp_ack` and `apu_mixdown_all` keep the values they would have had without the key, and no line is logged about it

#### Scenario: Default in a build without the DSP
- **WHEN** `RECOMP_APU_DSP` is unset in a build without `XBOXRECOMP_APU_DSP` or without its device
- **THEN** the stub runs and no line is logged about it

#### Scenario: Neighbouring names
- **WHEN** `RECOMP_APU_DSP_ACK` or `RECOMP_DEBUG=apu_dsp_ack=...` is set, and `RECOMP_APU_DSP` is `0`
- **THEN** the DSP stays off and `apu_dsp_ack` takes the given value

#### Scenario: DSP built, device not
- **WHEN** `RECOMP_APU_DSP=1` in a build with `XBOXRECOMP_APU_DSP` but without `XBOXRECOMP_APU_DSP_DEVICE`
- **THEN** the stub runs, `apu_dsp_ack` and `apu_mixdown_all` are untouched, and one line says the device is missing

#### Scenario: Build without the DSP
- **WHEN** `RECOMP_APU_DSP=1` in a build with the option OFF
- **THEN** the stub runs, `apu_dsp_ack` and `apu_mixdown_all` are untouched, and one line says the build has no APU DSP

## ADDED Requirements

### Requirement: Every game runs the JIT unless it opts out
Every game built on the toolkit SHALL run the APU DSP by default, with no game-level setting. A game whose audio breaks with the JIT SHALL default to the stub with `D(APU_DSP, "0")` in its game defaults, and SHALL have a tracker item for the fix. Each game's NOTICE SHALL name dsp56300 and the licence texts that a binary distribution carries.

#### Scenario: A game with no DSP setting
- **WHEN** a game's `game.toml` and game defaults say nothing about the APU DSP, and it is built on a toolkit with this change
- **THEN** its build links dsp56300 and its runs use the JIT unless `RECOMP_APU_DSP=0`

#### Scenario: A game that opts out
- **WHEN** a game sets `D(APU_DSP, "0")`
- **THEN** its runs use the stub unless `RECOMP_APU_DSP=1`
