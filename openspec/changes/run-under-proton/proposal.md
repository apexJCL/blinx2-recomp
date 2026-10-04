## Why

The user's top priority is now running BLiNX 2 properly under Proton, on a Linux x86-64 host. The host is a remote compile/test bench, driven from the Mac over `ssh <bench-host>`. Running the Windows build under Proton turns the x86-64 MMIO path back on. That path is the toolkit's only working audio route (`RECOMP_AC97_READY` → emulated APU), and it can't work on macOS arm64.

This change also takes over the postponed `verify-windows-host` change. The checks it held (that the Windows code was only moved, not rewritten, during the macOS port) now matter for Proton.

macOS arm64 support stays as it is. That work continues in its own changes.

## What Changes

- Add a Windows x86-64 build made with **llvm-mingw** (clang + lld + mingw-w64, UCRT). It can be cross-compiled on the macOS dev machine, or built on the Linux/Proton host inside a distrobox, using a toolchain file at `cmake/llvm-mingw-x86_64.cmake`. The toolchain is found through `LLVM_MINGW_ROOT` or `PATH`; CMake contains no host-specific paths.
- MSVC and clang-cl stay supported as the fallback (MSVC ABI), using the same `CMakeLists.txt`.
- `HOST_CAN_SERVICE_MMIO` is now true for any Windows x86-64 compiler (`_M_X64` or `__x86_64__`), not just MSVC.
- A MinGW-only CMake block:
  - GCC's assembler gets big-object output for the generated sources.
  - With lld, the build writes a PDB of public symbols, so the crash handler's `SymFromAddr` can name the guest function.
- Recovered function names that clash with the Windows CRT are reserved, as macOS libc names already were. The generated C is shared by every host.
- Placeholder tasks for the Proton run, carried out on the bench through `scripts/bench.sh`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `host-build`: Windows x86-64 can be built with llvm-mingw (cross or native) as well as MSVC, and needs a symbol source for diagnostics.
- `host-boot`: the supported hosts include Windows x86-64 under Proton/Wine, and MMIO trapping is available on Windows x86-64 whatever the compiler.

## Impact

- **Code**:
  - `CMakeLists.txt`: the MinGW block.
  - `cmake/llvm-mingw-x86_64.cmake`: new.
  - `src/main.c`: the MMIO gate.
  - `scripts/host_reserved_names.py`: Windows-target names.
  - `.gitignore`: `build-*/`, `third_party/`, `bench-logs/`.
- **Toolkit**: no changes needed so far. All of it compiles with llvm-mingw unchanged. Its `_MSC_VER` gates select MSVC intrinsics versus GNU builtins, which is correct for both llvm-mingw and clang-cl.
- **Generated code**: 10 functions are renamed (`fpclass` → `fpclass_002D50C6`, and so on), which forces a full rebuild on every host.
- **Dependencies**: llvm-mingw 20260922 (UCRT), unpacked under `third_party/` (gitignored) for local checks. On Windows the toolkit needs no SDL2, libepoxy or OpenSSL: it uses D3D11, XInput, XAudio2, Media Foundation and bcrypt. Render under Proton is the D3D11 GPU render backend (`RECOMP_PB_BACKEND=d3d11`, through Wine to DXVK/Vulkan) or the CPU rasteriser; Present is the D3D11 swap chain, or the Win32 GDI window (`RECOMP_FB_WINDOW`) for the CPU path. SDL2 is never Render; on POSIX it handles Present and controller input.
- **Shared blocker**: the toolkit's fixed stack/heap layout overlaps BLiNX 2's image on every host. That's fixed separately on toolkit branch `posix-host/portability`. Until then the Windows build is expected to crash the same way the macOS build does.
