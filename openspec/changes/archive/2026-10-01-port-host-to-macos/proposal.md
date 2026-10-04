## Why

The whole recompilation pipeline already runs on macOS. The 88 generated C files compile under Clang on arm64, and the toolkit's memory model reaches guest memory through an offset, which works on Apple Silicon. The one thing standing between this project and a runnable binary on the development machine is the host entry point. `src/main.c` (copied from the toolkit template) and the link list in `CMakeLists.txt` assume Windows: `<windows.h>`, `WinMain`, `MessageBoxA`, dbghelp symbolication, a vectored exception handler, and the D3D11/XInput/WinMM libraries. Porting them now lets the build → crash → fix loop (GETTING_STARTED Steps 7–8) happen locally instead of on a separate Windows machine.

## What Changes

- Make `src/main.c` build and run on macOS arm64 as well as Windows. It keeps one boot sequence; only the platform-specific edges branch.
- Replace the dialog-box error paths with messages that work on both hosts: stderr everywhere, plus the existing dialog on Windows. Startup failures exit non-zero.
- Add a POSIX crash handler (`SIGSEGV`/`SIGBUS`) that reports the same guest diagnostics as the Windows handler: fault address, guest VA, guest registers, guest return-address chain, recent ICALL targets, and the host symbol of the faulting function.
- Make host-symbol lookup work without dbghelp on macOS, so a crash names the `sub_XXXXXXXX` it happened in.
- Refuse `RECOMP_AC97_READY` on hosts where hardware-register (MMIO) trapping cannot work. It now produces a clear startup message instead of a silent fault later.
- Make `CMakeLists.txt` link Windows SDK libraries only on Windows, and build a console executable on macOS (no `WIN32` GUI subsystem flag).
- Keep the OpenSSL scoping fix already in `CMakeLists.txt`, and document why it's there.

Non-goals:
- MMIO trapping on arm64 (APU/NV2A register emulation through faults). The toolkit's decoder in `../xboxrecomp/src/platform/mmio_decode.h` decodes x86-64 host instructions only.
- An x86_64/Rosetta build.
- Making the game render or play correctly. This change gets it to boot and crash informatively; what happens after that is the Step 8 debugging loop.
- Linux. It should mostly fall out of the POSIX path, but it isn't a target or a test platform here.

## Capabilities

### New Capabilities
- `host-boot`: how the host executable starts on each supported platform. Covers the boot order, locating the game files, reporting startup failures, and refusing configurations the host can't honor.
- `host-crash-diagnostics`: what the host reports when guest code faults, on each platform. Covers the fault details, guest register and stack context, ICALL history, and host symbol names.
- `host-build`: what `CMakeLists.txt` must produce on each supported platform. Covers the executable type, platform-specific link libraries, and resolving toolkit dependencies.

### Modified Capabilities
<!-- none: no specs exist yet -->

## Impact

- **Code**: `src/main.c` (most of the change) and `CMakeLists.txt`. `src/recomp_manual.c` is already portable and isn't touched.
- **Toolkit (`../xboxrecomp`)**: no changes required. This change relies on the local patch already applied to `src/kernel/xbox_memory_layout.c` (Windows-only VEH bodies) for the toolkit to compile off Windows. That patch is upstream material and is tracked outside this change.
- **Dependencies**: Homebrew `sdl2`, `libepoxy` and `openssl` (currently `openssl@4` 4.0.3), all already installed. The macOS build needs a working toolchain: AppleClang 21 with `DEVELOPER_DIR=/Library/Developer/CommandLineTools` on this machine, which `scripts/pipeline.sh build` sets.
- **Windows**: deferred. The Windows code paths are moved, never rewritten, so behavior should stay as it is today. Checking that (diff review and an MSVC build) is the last task group, done when a Windows machine is available. macOS is the focus of this change.
- **Build time**: the first full macOS build compiles about 787 MB of generated C. Expect it to take a long time, not to fail.
