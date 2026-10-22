## ADDED Requirements

### Requirement: The APU DSP is a build option, default OFF
The toolkit SHALL offer a CMake option `XBOXRECOMP_APU_DSP`, default OFF. With the option OFF the build SHALL neither fetch nor link dsp56300, and SHALL behave exactly as a build without the option. With it ON, the build SHALL take the dsp56300 1.0.0 prebuilt static library for its target from the release archive pinned by sha256 in `cmake/dsp56300.cmake`, link it into the APU library with the system libraries the Rust standard library needs (`CoreFoundation` and `Security` on Apple; `libunwind`, `ws2_32`, `userenv`, `ntdll`, `bcrypt`, `advapi32`, `kernel32` and `synchronization` under llvm-mingw), and define `XBOXRECOMP_APU_DSP` for `recomp_env`.

#### Scenario: Default build
- **WHEN** the toolkit is configured without `-DXBOXRECOMP_APU_DSP`
- **THEN** nothing is downloaded, no dsp56300 symbol is linked, and the game runs as before

#### Scenario: Archive does not match its pin
- **WHEN** the option is ON and the downloaded or given archive's sha256 differs from the pin for its target
- **THEN** configuration fails with an error naming both hashes

#### Scenario: Target without an archive
- **WHEN** the option is ON for a target that has no dsp56300 archive (iPadOS, a universal macOS build, MSVC)
- **THEN** configuration warns once and the build goes on with the option OFF

#### Scenario: Download fails
- **WHEN** the option is ON for a target that has an archive and the download fails
- **THEN** configuration fails with an error naming `XBOXRECOMP_DSP56300_ARCHIVE` as the way to give a local copy

#### Scenario: Windows cross build
- **WHEN** the option is ON in an llvm-mingw cross build for `x86_64-pc-windows-gnu`
- **THEN** the program links, and imports only system DLLs (no `libunwind.dll`)

### Requirement: The apu_dsp key selects the DSP at run time, default the stub
The toolkit SHALL have a config-tier `recomp_env` key `APU_DSP`, variable `RECOMP_APU_DSP`: `1` runs the APU's GP and EP on the DSP56300 JIT, while unset, empty or `0` keeps the stub. Any other value SHALL keep the stub and log one line. In a build without `XBOXRECOMP_APU_DSP`, `1` SHALL keep the stub and log one line saying the build has no APU DSP. Until the device model is built in (task 3, which defines `XBOXRECOMP_APU_DSP_DEVICE` on `recomp_env`), `1` SHALL keep the stub and log one line saying the device is not wired yet, because with the host ack off nothing would answer the GP doorbell. The key SHALL NOT collide with `RECOMP_APU_DSP_ACK` or the `apu_dsp_ack` debug key: setting either of those SHALL leave `APU_DSP` unset, and `apu_dsp` SHALL NOT be accepted as a debug-list key.

#### Scenario: Stub by default
- **WHEN** `RECOMP_APU_DSP` is unset, empty or `0`
- **THEN** `recomp_env(RENV_APU_DSP)` is NULL, `apu_dsp_ack` and `apu_mixdown_all` keep the values they would have had without the key, and no line is logged about it

#### Scenario: Neighbouring names
- **WHEN** `RECOMP_APU_DSP_ACK` or `RECOMP_DEBUG=apu_dsp_ack=...` is set, and `RECOMP_APU_DSP` is not
- **THEN** the DSP stays off and `apu_dsp_ack` takes the given value

#### Scenario: DSP built, device not yet
- **WHEN** `RECOMP_APU_DSP=1` in a build with `XBOXRECOMP_APU_DSP` but without `XBOXRECOMP_APU_DSP_DEVICE`
- **THEN** the stub runs, `apu_dsp_ack` and `apu_mixdown_all` are untouched, and one line says the device is not wired yet

#### Scenario: Build without the DSP
- **WHEN** `RECOMP_APU_DSP=1` in a build with the option OFF
- **THEN** the stub runs, `apu_dsp_ack` and `apu_mixdown_all` are untouched, and one line says the build has no APU DSP

### Requirement: With the DSP on, the stub's keys are overridden
With `APU_DSP` at `1` in a build with the DSP and its device, `apu_dsp_ack` SHALL be forced to `0`, because the GP answers its own doorbell, and `apu_mixdown_all` SHALL be ignored, because the output comes from the GP and not from the stub's fold. If the user set either key, by its list key or its old variable, one line SHALL be logged at startup naming the keys overridden. With `APU_DSP` off both keys SHALL keep their current behaviour.

#### Scenario: Quiet override
- **WHEN** `RECOMP_APU_DSP=1` and neither key is set
- **THEN** `apu_dsp_ack` reads `0`, `apu_mixdown_all` reads unset, and no line is logged

#### Scenario: User set both
- **WHEN** `RECOMP_APU_DSP=1` and `RECOMP_DEBUG=apu_dsp_ack=auto,apu_mixdown_all=2`
- **THEN** both are overridden and exactly one line names both

### Requirement: The DSP reports its cycle budget through a debug key
The DSP SHALL cap the cycles it runs per frame and count the frames that hit the cap. A debug-tier key `APU_DSP_STATS` (`apu_dsp_stats` in `RECOMP_DEBUG`) SHALL print a one-line stats report of the DSP's frame time, cycles and cap hits, and the key SHALL have an `env.md` row. A cap hit SHALL never be silent.

#### Scenario: Stats on
- **WHEN** the DSP runs with `RECOMP_DEBUG=apu_dsp_stats`
- **THEN** a one-line `[APU DSP]` stats report is printed, including the count of cap hits
