## Context

`port-host-to-macos` (archived at `openspec/changes/archive/2026-10-01-port-host-to-macos/`) gave `src/main.c` shared code with per-host edges. The Windows edge is a vectored exception handler (VEH), dbghelp, `WinMain` and the APU MMIO dispatch, and it has never been built since the port. The target is now Proton: Valve's Wine build, run through `umu-run` with GE-Proton on a Linux x86-64 host. Bench host access, syncing, launching and log retrieval are done by main-session sub-agents over `ssh <bench-host>`, through `scripts/bench.sh` (`sync|build|run|logs`; logs land in `bench-logs/`). This change owns the source and build side.

## Decisions

### 1. llvm-mingw, not GCC MinGW
GCC on mingw implements `__thread` through emutls, a function call per access. The `RECOMP_TLS` guest registers are touched by nearly every lifted instruction, so that cost lands everywhere. Clang emits native TLS. llvm-mingw also ships lld, which can write a PDB. The MSVC-ABI fallback is clang-cl plus xwin. `CMakeLists.txt` keeps its `if(MSVC)` branch for that, and its `if(MINGW)` branch for this.

### 2. Toolchain file located by variable, not path
`cmake/llvm-mingw-x86_64.cmake` finds `x86_64-w64-mingw32-clang` from `LLVM_MINGW_ROOT` (a cache or environment variable), and falls back to `PATH`. The same file works for a cross build on macOS and inside the Linux/Proton distrobox, so CMake contains no host-specific paths. The root is passed to `try_compile` projects through `CMAKE_TRY_COMPILE_PLATFORM_VARIABLES`.

### 3. Symbols through an lld PDB
The VEH resolves the faulting RIP with `SymFromAddr`. A MinGW build has no PDB by default, and Wine's dbghelp reads PDBs, so the link passes `-Wl,--pdb=<exe dir>/cat_recomp.pdb`. lld writes public symbols even without `-g`, which is enough to name every `sub_XXXXXXXX`, and cheap compared with full debug info over ~800 MB of generated C. The PDB has to travel next to the exe to the bench.

### 4. MMIO gate by architecture, not compiler
`HOST_CAN_SERVICE_MMIO` checks `_WIN32 && (_M_X64 || __x86_64__)`. Under MinGW `_M_X64` isn't defined, and the old gate silently disabled the APU path.

### 5. Reserved names cover every target; the generated C is shared
The generated C is produced on the macOS dev machine and rsynced to the bench, so one copy must compile for every host. `scripts/host_reserved_names.py` (run by `pipeline.sh names`) now reserves the union of:
- the host libc's exports
- a POSIX baseline
- a Windows CRT baseline
- the exports of llvm-mingw's CRT and system import libraries, when a toolchain is found

The first MinGW compile failed on `fpclass` (it conflicts with `<math.h>`). Ten names in all were renamed to `<name>_<ADDR>`.

### 6. Subsystem stays GUI
`add_executable(... WIN32 ...)` keeps the template's GUI subsystem. Wine passes the Unix stdout/stderr to the process when it's launched from a terminal, which is how `umu-run` is used on the bench. If logs don't come through, a console-subsystem build option is the fallback (open question).

### 7. Windows reserves the whole 4 GB guest window
The toolkit maps every guest window at `g_memory_offset + VA`. On Windows it used to reserve only RAM and its mirrors, at a base the OS chose. Proton run 2 put that base at host `0x7FFF0000`, and the contiguous window at host `0xFFFF0000` collided with something at `0x100000000` (error 487). The kernel page went with it, and the title faulted at guest `0x8000FFF0`.

The fix (toolkit `proton/win-layout`) reserves max(4 GB, RAM + mirrors) as one `VirtualAlloc2` placeholder, then carves each window out of it with `MEM_REPLACE_PLACEHOLDER`. So every guest VA the layout uses is ours before anything is mapped. The span code it replaces on Windows released slices with `VirtualFree(MEM_RELEASE)` and a non-zero size. That call fails on Windows and on Wine (`kernelbase` `VirtualFreeEx`), so the span never worked there and its 1.8 GB reservation leaked. If `VirtualAlloc2`/`MapViewOfFile3` are missing, a racy probe-and-map of a free 4 GB hole is the fallback. POSIX keeps its span, which works there because `munmap` can release part of a mapping. After init, the leftover placeholders are turned into plain reservations, so fixed-address `MEM_COMMIT` calls (the NV2A VRAM fault hook) still work.

## Risks / Trade-offs

- **The layout overlap crashes Windows too.** The fixed stack/heap bases are host-independent, so a Proton run before the toolkit fix lands on `posix-host/portability` will reproduce the heap-corruption crash.
- **Wine's VEH and dbghelp behavior** may differ from Windows in its details: the `ExceptionInformation[0]` values, and PDB public-symbol lookup from an lld PDB. Proton tasks 3.x check both.
- **Utility drive.** The game-side `MOUNT_UTILITY_DRIVE` workaround in `main.c` applies only off Windows, because the toolkit's Windows path backend has Partition0 support. Under Proton that backend writes `Partition0.img` through Wine's filesystem, which should work but hasn't been tried.

## Open Questions

- Do stdout/stderr come through `umu-run` for a GUI-subsystem exe, or does the bench need a console build or a log file?
- Does `SymFromAddr` resolve symbols from the lld PDB under Proton's dbghelp?

## Windows build dependencies (for the bench `setup`)

- **Build time:** only the llvm-mingw toolchain (release 20260922, UCRT variant, `x86_64-w64-mingw32-clang`), plus CMake ≥ 3.20 and Ninja. The bench installs the Linux x86-64 llvm-mingw release on the host and passes `-DLLVM_MINGW_ROOT`. `third_party/` holds only the macOS copy used for local cross-checks, and no build step depends on it. No SDL2, libepoxy or OpenSSL is needed: on `WIN32` the toolkit uses D3D11, XInput, XAudio2, Media Foundation and bcrypt, which come from the mingw-w64 import libraries bundled with llvm-mingw.
- **Run time (imports of `cat_recomp.exe`):** UCRT `api-ms-win-crt-*`, kernel32, user32, gdi32, shell32, ole32, winmm, dbghelp, d3d11, `D3DCOMPILER_47.dll`, `XAudio2_8.dll`, `MFPlat.DLL`, `MFReadWrite.dll`. Proton ships all of these as builtins: d3d11 via DXVK, d3dcompiler_47 via vkd3d-shader, XAudio2 via FAudio, and MF via GE-Proton's media stack. No MinGW runtime DLLs are needed. Ship `cat_recomp.pdb` next to the exe for crash symbols.
