# host-boot Specification

## Purpose
Defines how the host executable starts on each supported platform: initializing the Xbox runtime in a fixed order, finding the game files, starting the recompiled entry point, and failing loudly and early when it can't.

## Requirements

### Requirement: Supported hosts
The host executable SHALL build and start from the same source files on:
- Windows x86-64, including running under Proton/Wine on Linux
- macOS arm64

Its boot sequence SHALL be the same on all of them. Only platform-specific primitives (error reporting, crash handling, symbol lookup, entry-point signature) MAY differ.

#### Scenario: macOS arm64 boot
- **WHEN** the executable is built for macOS arm64 and launched with valid game files
- **THEN** it reaches the guest entry point and prints the same initialization banner lines it prints on Windows

#### Scenario: Windows boot
- **WHEN** the executable is built for Windows x86-64 with llvm-mingw (the tested toolchain; MSVC builds are unverified, see `host-build`)
- **THEN** it boots with the same order, outputs and failure behaviour as on macOS

#### Scenario: Proton boot
- **WHEN** the llvm-mingw Windows x86-64 build is launched under Proton with valid game files
- **THEN** it reaches the guest entry point and prints the same initialization banner lines, and those lines reach the launching terminal or the bench's log capture

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
The host SHALL load `<game_dir>/default.xbe` and use `<game_dir>` as the game data root. `<game_dir>` SHALL be the value of `RECOMP_GAME_FILES` when that is set, and otherwise `game_files/`, resolved relative to the current working directory. When `RECOMP_HDD_DIR` is set, the host SHALL pass it to the kernel as the save root (partition images, title and user data, caches). When it is unset, the host SHALL pass none, and the toolkit's default save root applies. `RECOMP_SAVE_DIR` SHALL keep overriding the UDATA/TDATA root within whichever save root is in force. With both keys unset, the boot output and every path used SHALL be identical to the behaviour before these keys existed. The host SHALL accept forward-slash paths on every host.

#### Scenario: Run from the project root
- **WHEN** the executable is launched with the project root as the working directory, `game_files/default.xbe` exists, and neither key is set
- **THEN** the XBE loads, the printed size equals the file's size in bytes, and no `[BOOT] game files:` line is printed

#### Scenario: Game files elsewhere
- **WHEN** `RECOMP_GAME_FILES=/data/BLiNX2/game_files` is set and the working directory is unrelated
- **THEN** the XBE loads from `/data/BLiNX2/game_files/default.xbe`, disc paths (`D:\`) resolve under that directory, and one `[BOOT] game files:` line names it

#### Scenario: Save root elsewhere
- **WHEN** `RECOMP_HDD_DIR=<dir>` is set
- **THEN** `Partition0.img`, `TitleData/`, `UserData/` and `Cache/` are created under `<dir>`, and the title's save games are written there, not under the toolkit's default save root

#### Scenario: Missing XBE with the key set
- **WHEN** `RECOMP_GAME_FILES` names a directory with no `default.xbe`
- **THEN** stderr names the full path tried and says it came from `RECOMP_GAME_FILES`, and the process exits non-zero before memory mapping

### Requirement: Startup failures are reported and fatal
When a required startup step fails, the host SHALL write a message to stderr naming the step, the path or resource involved, and a likely fix. It SHALL then exit with a non-zero status without entering guest code. On Windows it SHALL also show the existing error dialog. On other hosts it SHALL NOT need a GUI to report the failure.

#### Scenario: Missing XBE
- **WHEN** the executable is launched from a directory with no `game_files/default.xbe`
- **THEN** stderr names the path it tried, and the process exits non-zero before memory mapping

#### Scenario: Memory layout unavailable
- **WHEN** the Xbox memory layout cannot be mapped
- **THEN** stderr says the memory layout failed to initialize, and the process exits non-zero

### Requirement: Refuse configurations the host cannot honor
The host SHALL check, before entering guest code, for configuration that needs hardware-register (MMIO) fault trapping. On a host whose fault handling cannot decode and resume the faulting instruction, it SHALL either refuse that configuration with a message that names the setting, or ignore the setting with a message saying it was ignored. It SHALL NOT arm a trap it cannot service. Whether a host can service MMIO SHALL depend on the host's OS and CPU architecture, not on which compiler built it.

#### Scenario: AC'97/APU trapping requested on a host that cannot service it
- **WHEN** `RECOMP_AC97_READY` is set and the build runs on a platform with no fault decoder (none of the supported hosts; for example an unsupported native x86-64 Linux build)
- **THEN** stderr has `[ENV] RECOMP_AC97_READY: audio unsupported on this host; ignored`, the emulated APU is not started, and boot continues

#### Scenario: AC'97/APU trapping requested on macOS arm64
- **WHEN** `RECOMP_AC97_READY` is in effect and the host is macOS arm64 (Linux arm64 by construction, untested)
- **THEN** the emulated APU is started and its register faults are decoded from the signal context and serviced (`audio`)

#### Scenario: AC'97/APU trapping on Windows
- **WHEN** `RECOMP_AC97_READY` is set and the host is Windows x86-64 (llvm-mingw build), natively or under Proton
- **THEN** the emulated APU is started and its register faults are decoded from the exception record and serviced

### Requirement: Clean exit
When the guest entry point returns, the host SHALL shut down the kernel and memory layout, release the XBE buffer, and exit with status 0.

#### Scenario: Guest returns
- **WHEN** the recompiled entry point returns normally
- **THEN** the host prints that the game returned, runs shutdown, and exits 0

### Requirement: A new game's template boots with the XDK D3D defaults
The toolkit's new-game template (`templates/new-game/src/main.c`, the file `xbr new` copies into every new game) SHALL, after the Xbox memory layout is mapped and before the kernel is initialised, set `RECOMP_VBLANK` to `1` and `RECOMP_TITLE_KEVENTS` to `1` unless the environment already sets each, with a comment on each that says why (XDK D3D paces its swap, vblank wait and vblank callback on the vblank DPC; that DPC sets a KEVENT D3D built without `KeInitializeEvent`). It SHALL carry, before those two, a fence block whose last line is the commented example `/* xbox_Nv2aMirrorFence(0x00000000, 0x2C, 0x30); */` and whose comment names the device layout (`+0x2C` submitted, `+0x30` pointer to the completed word), the three known pointers (BLiNX 2 `0x2F1FB8`, Spartan `0x235528`, Burnout 3 `0x35FB48`) and where the porting doc explains how to find one. The example SHALL compile as a comment, so a scaffold the CLI could not fill builds and runs as before.

`xbr new` SHALL look for D3D's fence wait in the dump it reads the header from (the `D3D` section, or every executable section when there is none), by the instruction sequence `mov esi, [ptr]; (push edi; mov edi, eax;)? mov eax, [esi+g]; mov ecx, [eax]; mov eax, [esi+p]; mov edx, eax; sub edx, ecx`, and SHALL replace the example line with `xbox_Nv2aMirrorFence(ptr, p, g);` only when that sequence occurs exactly once; `p` and `g` SHALL come from the match. In every other case (no dump read, no match, several matches) the example line SHALL stay and the summary SHALL say which case it was and point at the porting doc. The summary SHALL name the XDK libraries and builds the dump's library table lists. Against a template without the example line, a found fence SHALL produce a note telling the porter to add the line, never an error.

#### Scenario: Fresh scaffold of an XDK 5849 title
- **WHEN** `xbr new` scaffolds Spartan: Total Warrior from its dump and the game is built with no hand edit to `src/main.c`
- **THEN** `src/main.c` carries `xbox_Nv2aMirrorFence(0x00235528, 0x2C, 0x30);`, the runtime logs `NV2A fence mirror: device at 0x00235528` and later `now written by the executor; mirror off`, and the boot reaches the same stop as the hand-edited game (the `KeDelayExecutionThread` poll under `sub_001ADCA0`) on the Mac and under Proton

#### Scenario: The fence wait is not found
- **WHEN** the dump cannot be read, has no match, or has more than one
- **THEN** the example line is left as a comment, the summary says `D3D fence: not found (<reason>)` and names `docs/porting.md`'s "The D3D fence", and the scaffold builds

#### Scenario: The defaults can be switched off
- **WHEN** `RECOMP_VBLANK=0` or `RECOMP_TITLE_KEVENTS=0` is in the environment of a scaffolded game
- **THEN** the template's default does not override it: with `RECOMP_VBLANK=0` no vblank is raised and the boot stops in D3D's vblank wait; with `RECOMP_TITLE_KEVENTS=0` the vblank DPC's `KeSetEvent` fails as before the default

#### Scenario: The template is checked by the toolkit's own test
- **WHEN** `tests/template_main` runs
- **THEN** it builds the template with the new lines, and its `defaults` test fails if either guarded `recomp_env_set` line or the example line is missing or changed
