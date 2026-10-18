## ADDED Requirements

### Requirement: A scaffolded game builds and boots on Windows and macOS
The toolkit's `templates/new-game/` SHALL be a two-host game: one `src/main.c`
whose boot sequence is shared and whose host-specific parts (the crash
handler and its symbol lookup, the fatal-step dialog, the window, the entry
points) sit under `#if defined(_WIN32)` / `#else`, and a `CMakeLists.txt`
that configures and builds with llvm-mingw for Windows and with Apple clang
for macOS. On every host it SHALL honour `RECOMP_STDIO_LOG` before its
first line of output and SHALL print its crash report under the `[CRASH]`
tag. On POSIX it SHALL hand a trapped MMIO fault to `xbox_PosixMmioFault`
before reporting, SHALL run the guest under `xbox_HostWindowMain` unless
`RECOMP_HEADLESS` is set, and on Apple SHALL default `RECOMP_PB_BACKEND` to
`metal` when it is unset. The template SHALL carry no title constant other
than the `YOUR_GAME_*` macros `xbr new` patches. With `RECOMP_STDIO_LOG`
unset, the Windows build's boot sequence, VEH and crash report SHALL be
what they were before; the only allowed differences are the `[THREAD]`
and `[FATAL]` lines on stderr, the deprecation notes printed at boot
rather than at exit, no fatal dialog under `RECOMP_HEADLESS`, and the
guest-main thread marked for DPC delivery, which the toolkit requires.
`xbr new` SHALL write `build.targets = ["windows", "macos"]`, and SHALL
say so, rather than fail, when the toolkit it copies the template from
still has the Win32-only one.

#### Scenario: Both targets from one scaffold
- **WHEN** `xbr new d/g --xbe <dump>` runs with a toolkit at or after this change, then `./g analyze`, `./g recomp`, `./g build windows` and `./g build macos` on a Mac
- **THEN** both builds succeed with `src/main.c` and `CMakeLists.txt` as `new` wrote them

#### Scenario: Boot or a reported fault on macOS
- **WHEN** the macOS build runs with `SDL_AUDIODRIVER=dummy`, `RECOMP_HEADLESS=1` and a dump in `game_files/`
- **THEN** it presents frames on Metal, or it dies by SIGBUS or SIGSEGV after a `[CRASH]` report naming the signal, the host PC and the generated function, the guest registers, the guest return addresses and the native stack

#### Scenario: The log reaches the file under Proton
- **WHEN** the Windows build runs under Proton with `RECOMP_STDIO_LOG=<file>`
- **THEN** the boot lines, and the `[CRASH]` report if it crashes, are in `<file>`, and the bench's crash check reads them

#### Scenario: An old toolkit beside the game
- **WHEN** `xbr new` copies a template that has no `_WIN32` host section
- **THEN** the scaffold is written with both targets and the summary notes that `build macos` needs a newer toolkit pin or `macos` dropped from `build.targets`

#### Scenario: The template cannot rot unnoticed
- **WHEN** `tests/posix_ctest.sh` runs on the Mac, or the CLI's Proton standalone tests run on the Deck
- **THEN** `tests/template_main` compiles and links the template's `main.c` against the toolkit, exits 1 with `[FATAL] load XBE` when there is no XBE, and writes that line to `RECOMP_STDIO_LOG` when it is set
