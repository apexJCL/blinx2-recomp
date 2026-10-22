## Context

- **Toolkit** `posix-host/portability` 4559bae9. **cat** main dd2f1c1. **CLI** main 85e24c9.
- **GPU backends today:**
  - D3D11 (`nv2a_pb_d3d11.c`, 4317 lines, `#ifdef _WIN32`). On the Deck it runs through Proton's DXVK.
  - Metal (`nv2a_pb_metal.m`, 3458 lines, macOS only).
  - Both plug into `struct nv2a_pb_backend` (`src/kernel/nv2a_pb_state.h`). Its hooks:
    - `on_clear`, `on_zclear`, `on_draw`, `on_flip`;
    - `on_zpass`, `on_zpass_clear`, `on_report` (visibility tests / GET_REPORT), `on_poll`;
    - `sync_guest`, plus a `writes_back` flag.
  - Shaders come from emitters: HLSL in `d3d8_vsh_hlsl.c` and `d3d8_combiners_hlsl.c`; MSL in the Metal pair.
- **What ties the D3D11 backend to Windows.** All of it is host glue, none of it renderer logic:
  - it creates its own Win32 window (`RegisterClassA`, `CreateWindowW`, `GetModuleHandleA` :483), and a `wnd_proc` feeds keyboard and mouse;
  - it sizes and titles it (`GetSystemMetrics`/`AdjustWindowRect` :501/:514, `SetWindowPos` :3791, `SetWindowTextW` :3909);
  - it times frames with `QueryPerformanceCounter`/`QueryPerformanceFrequency` (:4132);
  - it draws the enhance-menu overlay in its own present, as each presenter does;
  - it loads `d3dcompiler_47.dll` with `LoadLibraryA` for `D3DCompile`;
  - it creates an `IDXGISwapChain` on that HWND and calls `MakeWindowAssociation`.
  - The rest is the D3D11 API through C COM macros: occlusion queries, `ClearView`, and stream output for the trace only.
- **The POSIX host, by architecture:**
  - Its trapped-MMIO path (APU, AC'97, OHCI) decodes A64 with Darwin ucontext macros, so it works on arm64 macOS only.
  - On x86-64 Linux, `mmio_decode.h` already holds an x86-64 decoder, but no `sigaction` glue calls it. Constant-address APU accesses still reach the device, through the lifter's direct `XBOX_MMIO_R/W` calls.
  - The gaps that leaves:
    - AC'97's channel reset spins;
    - OHCI is off, which BLiNX 2 does not need (it uses its XInput override) but Burnout 3 may.
- **What Linux has run so far.** The toolkit's POSIX ctests ran natively on the Linux/Proton host. cat has never been built for Linux: its "Linux build" gate was a cross-build of the Windows exe. TASKS once rejected native Linux for SteamOS because it "has no GPU renderer target". cat's CMake already treats every non-WIN32 host as POSIX.
- **Proton's D3D11 path:**
  - DXVK on Vulkan (RADV on the Deck);
  - HLSL compiled by Proton's `d3dcompiler_47`, which is `vkd3d-shader`. The Deck log shows `D3DCompile2VKD3D Ignoring flags 0x8000` (`bench-logs/20261017-194113/steam-default.log`).
- **Goldens:** D3D11 references captured under Proton (`analysis/golden/golden.json`). A frame passes on an exact hash or within its tolerances.
- **Constraints:**
  - The CLAUDE.md "backends agree" rule: every behaviour change on one GPU path lands on the other or is logged.
  - Builds happen on the Mac, never on the Deck.
  - Docker only through `docker build --output`.
  - Order: DSP, then SDL3.

## Evidence

The probes' Dockerfiles, sources and outputs are in `xbox-recomp/runs/linux-vulkan/` (`dxvkprobe/`: `Dockerfile`, `probe.c`, `hlsl.c`, `out/`, `docker.log`; `linuxprobe/`: `Dockerfile`, `out/`, `docker.log`).

**Probe A, dxvk-native** (`runs/linux-vulkan/dxvkprobe/`). Docker on the Mac, `linux/amd64`, Fedora 42.
- **Inputs:**
  - DXVK v3.1.1 `dxvk-native-3.1.1-steamrt-sniper.tar.gz` (sha256 `506fa1ea…91b7`);
  - `libvkd3d-shader` 1.14;
  - SDL3;
  - Mesa lavapipe under Xvfb.
- **The C test program** in the toolkit's `COBJMACROS` style. It:
  - compiled HLSL with `vkd3d_shader_compile` (HLSL to DXBC TPF), which returned 0 and 432 bytes;
  - created a headless D3D11 device (`hr=0`, feature level 11_0);
  - created a pixel shader from that DXBC (`hr=0`);
  - created a `D3D11_QUERY_OCCLUSION` query (created only: no `Begin`/`End` or `GetData` was issued, so query results are untested);
  - created a device and swap chain whose `HWND` is an `SDL_Window*` (`DXVK_WSI_DRIVER=SDL3`, `hr=0`).
- **The tarball** ships:
  - `libdxvk_d3d11.so`, `libdxvk_dxgi.so`;
  - pkg-config files;
  - flat headers (`d3d11.h`, `d3dcompiler.h`, a `windows.h` shim).
- **Limits:** everything ran on lavapipe (Mesa's CPU Vulkan) under Xvfb, not on RADV or a real GPU, and nothing was drawn or presented. The probe proves the build, link, compile and device-creation chain only.
- **One trap:** calling `D3DCompile` through DXVK's `d3dcompiler.h` against `libvkd3d-utils` crashed with garbage flags, a header ABI mismatch. The native `vkd3d_shader_compile` API, in its own translation unit that does not see the DXVK headers, works. D1 builds on that.

**Probe B, the toolkit's POSIX host on Linux** (`runs/linux-vulkan/linuxprobe/`).
- Setup: Fedora 42 x86-64, SDL2 and SDL3, libepoxy, `-DXBOXRECOMP_ENHANCE=ON`, then `tests/posix_ctest.sh`.
- Result: see "Probe B result" at the end. The ctests pass; the root library build was not run, so task 1.1 starts there.

## Goals / Non-Goals

**Goals:**
- A native Linux x86-64 BLiNX 2 that renders the 3D on the GPU through Vulkan, with Proton out of the path.
- Golden parity with the Proton D3D11 references.
- No third renderer to keep in step.
- Built on the Mac, run and gated on the Deck.
- Shipped as a package that SteamOS runs from Steam.

**Non-Goals:**
- a new renderer;
- SDL_GPU now;
- Flatpak;
- Linux arm64;
- removing the Proton package;
- CPU-backend gating.

## Decisions

### D1. Route: the D3D11 backend over dxvk-native

`nv2a_pb_d3d11.c` gets a host seam, `d3d11_host.h`, covering every Win32 call listed in Context:
- create a window or adopt one (module handle, class, window);
- size, reposition and title it;
- give the swap-chain target;
- pump input;
- a host clock (today `QueryPerformanceCounter`/`Frequency`);
- draw the enhance-menu overlay (on Linux through the SDL host, as the Metal presenter does);
- compile HLSL;
- report the drawable size.

There are two implementations:
- **`d3d11_host_win32.c`:** today's Win32 window, `wnd_proc` and `d3dcompiler_47`, moved as they are.
- **`d3d11_host_sdl.c`, Linux:**
  - It adopts the presenter's SDL window, as the Metal backend does, and passes the `SDL_Window*` as the `HWND`. DXVK's SDL3 WSI takes it.
  - Input stays with the SDL host layer's event pump, as on macOS.
  - HLSL compiles through `vkd3d_shader_compile` to DXBC, in its own translation unit so the vkd3d and DXVK headers never meet.

Build:
- CMake gains `XBOXRECOMP_DXVK_NATIVE`, **default OFF**, so the existing POSIX Linux build, the ctests and `install_deps.sh` keep working unchanged. The CLI's `linux` target turns it ON. It then uses the pinned DXVK native tarball and a `libvkd3d-shader` built unmodified from a pinned upstream source tarball.
- `RECOMP_PB_BACKEND=d3d11` selects the backend on Linux as it does on Windows. The default on Linux is `d3d11` in a build with `XBOXRECOMP_DXVK_NATIVE` ON (the shipped package) and `cpu` otherwise.
- With the DSP on, the Linux target links dsp56300's `x86_64-unknown-linux-gnu` archive; its cost is re-measured on the Deck (task 1.7).

Why it works:
- **Parity.** Under Proton this backend already runs DXVK over Vulkan with HLSL from vkd3d-shader. Native Linux keeps all three and drops Wine. The DXVK version and the vkd3d-shader version are pinned to the ones the Proton golden used, or the golden records the pair.
- **"Backends agree."** One source file serves Windows, Proton and Linux, so a renderer fix lands once for all three. No third backend.
- **Licences:**
  - DXVK is zlib. The toolkit is MIT.
  - vkd3d-shader is LGPL-2.1+. It ships as its own `.so`, built unmodified from a pinned upstream source tarball and replaceable, with `LICENSES/LGPL-2.1.txt` (already in the toolkit) and a link to that exact source tarball in the notice. This follows the toolkit's existing LGPL precedent (the xemu APU sources). Accepted by the user on 2026-10-21.
  - DXVK's own licence files are copied from its tarball into the package.
  - CLI `credits.py`, cat `NOTICE` and the wizard's credits list DXVK, vkd3d-shader and SDL3 (if bundled).
  - A package test runs `readelf -d`/`ldd` on every bundled `.so` and fails on any GPL-only dependency.
  - No static linking.

**Effort: 15-20 agent-days.**

| Item | Days |
|---|---|
| Host seam and Win32 move: window, sizing, title, clock, input, compiler (no behaviour change; the native Windows golden proves it) | 3-4 |
| SDL3 host side, enhance-menu overlay on Linux, vkd3d compile shim | 2-3 |
| CMake option, pinned DXVK, vkd3d-shader from pinned source | 1-1.5 |
| x86-64 POSIX fault glue and ctest | 1-2 |
| Root Linux build (task 1.1) and the case-sensitive path check | 1 |
| Phase 0 CPU-path cat build, SDL3-in-sniper check, gate 8 on the Deck | 1-1.5 |
| CLI build target (sniper image), package target, licence checks, doctor and bench/golden native mode | 3.5-4.5 |
| Wizard Linux target (Docker hosts) | 1 |
| Deck golden bring-up and fixes | 1-2 |

**Risks:**
- DXVK-native differs from DXVK-in-Proton in its WSI layer and in no-Wine details (thread naming, `GetModuleHandle` stubs). It is a supported build, used by shipped Linux games (for example, the Source ports).
- `vkd3d_shader_compile` flags must match what Proton's `D3DCompile` passes. Pin and compare the DXBC of every emitted shader on one Proton run and one native run (task 3.4).

### D2. Hand-written Vulkan backend: rejected for now

A third backend beside D3D11 and Metal.
- The shaders could reuse the HLSL emitters through `vkd3d-shader` to SPIR-V, or get a GLSL emitter compiled by glslang (BSD/Apache).
- Memory through VMA (MIT); loading through volk (MIT).
- Occlusion queries, clears, render-target and depth management, texture swizzle and upload, and present are written from scratch.

**Effort: 24-32 agent-days.** The Metal backend is the gauge: M1 to M2 on 2026-10-03, goldens green within days, then 48 commits through 2026-10-18 to keep it in step.

**Upkeep:** under "backends agree", every renderer fix lands three times. **Parity:** a new backend re-earns every golden.

**Revisit** only if DXVK-native blocks something D3D11 cannot express, which has not happened.

### D3. SDL_GPU: rejected for now, and never as a fourth backend

SDL3's GPU API covers Vulkan, Metal and D3D12, with SPIR-V, MSL and DXIL/DXBC shaders.

What it lacks for this executor:
- **occlusion or visibility queries**, which the NV2A zpass/GET_REPORT hooks need: the Metal backend's M3 visibility tests and the D3D11 queries;
- geometry shaders and stream output (trace only);
- rectangle clears (they would become draws).

As a replacement for both backends:
- 30-40 agent-days;
- high parity risk: D3D12 on Windows instead of D3D11, and both proven backends re-earn their goldens;
- in exchange, one backend in the end. Licence zlib.

**Revisit after the tracker item** only if:
- SDL_GPU gains occlusion queries, or the game is shown not to need them; and
- the user wants to replace both D3D11 and Metal.

It is never a third or fourth backend. The tracker item makes SDL3 available, which keeps this door open at no cost.

### D4. Building Linux binaries on the Mac

The Linux build must target the Steam Linux Runtime 3.0 (sniper) ABI, Debian 11 based, glibc 2.31. Then the binary runs on SteamOS, the Linux/Proton host and any distro with Steam.

**Primary:** `docker build --output` from the pinned sniper SDK image (`registry.gitlab.steamos.cloud/steamrt/sniper/sdk`, digest pinned in the CLI's pins).
- The image builds cat and the toolkit for `linux/amd64` and exports the binary and its `.so` files.
- On Apple Silicon this runs under emulation. Probe B took 700 s for configure plus the ctest projects on Fedora; a full cat build (generated code included) is larger.
- No bind mounts. The source goes in as the build context.
- This follows the wizard's builder-image pattern.

**Alternative:** the pinned llvm-mingw clang with `--target=x86_64-linux-gnu`, against a pinned sniper sysroot extracted once from the SDK image.
- No emulation, so faster.
- It needs lld and a matching libstdc++ or compiler-rt.
- The CLI picks it if the emulated build costs more than about 10 minutes per full build.

Probe B does not settle this: it ran on Fedora, not sniper, and built only the ctests. Its 700 s is already over the threshold for a smaller job, so the clang route is likely. Task 1.5 times a full cat build in the sniper image and decides.

### D5. Packaging and what the player runs

Target `linux-x86_64` (a new `[package]` target `linux`), a tar holding:
- the exe;
- `lib/libdxvk_d3d11.so`, `libdxvk_dxgi.so`, `libvkd3d-shader.so` (pinned) and `libSDL3.so` (if sniper lacks SDL3; task 1.6 checks);
- `RPATH=$ORIGIN/lib`;
- a launcher script;
- `NOTICE` and `LICENSES/`.

Install:
- `xbr package install` adds a non-Steam shortcut set to run under "Steam Linux Runtime 3.0 (sniper)". The shortcut sets `DXVK_WSI_DRIVER=SDL3`.
- Outside Steam, the launcher runs it directly.

Formats:
- **AppImage:** optional later; it adds nothing on SteamOS.
- **Flatpak: rejected for now.** It needs a manifest, a runtime choice and sandbox holes for the dump path and controllers. Flathub cannot host a build that needs the player's dump.
- The `steamos` Proton package stays as an opt-in route for players who want it; native `linux` is the SteamOS default (D7).

### D6. Where the Linux gate runs (answers SDL3 OQ1)

**Decided (the user, 2026-10-21): option (d).** Build on the Mac (D4) and run on the Deck as a native process, until the Linux/Proton host PC is re-provisioned with a proper Linux install. The Linux-native gate then moves to that PC, which also takes over the Proton runs from the Deck. Builds stay on the Mac either way.
- (d) keeps the rule "builds on the Mac, never on the Deck", so no exception is needed.
- Runs on the Deck are already routine, under its flock.
- A native run needs no umu and no pressure-vessel. That also sidesteps the `xbr-build` bwrap failure that blocked ctests there. The ctest binaries are Mac-built too and copied over.

Compared with the SDL3 design's options:
- **(a) PC in a Linux/Proton Fedora distrobox:** superseded by the re-provisioned PC above, which becomes the Linux gate host once it exists.
- **(b) Deck `xbr-build` builds:** breaks the build rule.
- **(c) A Mac VM:** a second Linux to maintain. Its GPU is virtual, so goldens are impossible there.

For the tracker item: its gate 8 (`sdl3-migration` 10.2) needs a native cat build on the CPU path, the POSIX ctests, a 30 s windowed `@attract` with the SDL3 audio driver logged, and a vpad at launch and after hot-plug. Under (d) these are Phase 0 tasks 1.5-1.8: the sniper image, the SDL3-in-sniper check, a Mac-built Linux cat on the CPU path, and a Deck desktop-mode windowed run with sound and vpad. **Phase 0 is a prerequisite of the tracker item's merge.**

### D7. Gates and Proton's role after native Linux

**Decided (the user, 2026-10-21).** Native Linux adds a gate; it never replaces the Windows gate, and Proton is not the Windows gate.
- **Native Windows stays a required gate** for every change that touches what the game executes. Things have worked under Proton and broken on native Windows before. It runs on the PC booted into Windows (the user switches the boot).
- **Proton is a stop-gap only,** used when no Windows host is up. The PC dual-boots, and its Linux side serves Linux and Proton first, relieving the Deck of those runs.
- **The native Linux golden** (D3D11 over dxvk-native) runs against the same D3D11 references, on the Deck until the PC is re-provisioned with Linux, then on the PC. It covers renderer, runtime, audio, kernel and input changes on Linux.
- **SteamOS packages:** native `linux` is the default. The `steamos` (Proton) package is offered only as an opt-in route for players who want it.

### D8. Ordering

- **Decided (the user, 2026-10-21):** right after SDL3, which follows the DSP (spike the tracker item). Phase 0 may start early on a free worker.
- After the DSP and the tracker item (SDL3). Not folded into the tracker item: that change is already about 44 h and is about the SDL API, not a renderer host.
- **Phase 0 can go before the tracker item** when a worker is free and does not collide with SDL3's files:
  - the root Linux build (task 1.1; probe B found no failures because it never built the root library);
  - x86-64 fault glue;
  - the case-sensitive path check;
  - the sniper builder image, the SDL3-in-sniper check, the CPU-path Linux cat and gate 8 (tasks 1.5-1.8).

  Phase 0 must finish before the tracker item merges (D6).
- **Phases 1-4 wait for the tracker item**, because the D3D11 host seam on Linux adopts the SDL3 window:
  - seam;
  - SDL host;
  - CLI target;
  - Deck golden.

### D9. "Backends agree" for native Linux (proposed CLAUDE.md wording)

The orchestrator applies this to CLAUDE.md; the branch does not edit it:

> Native Linux is the D3D11 path (`nv2a_pb_d3d11.c` over dxvk-native), not a third backend: renderer changes made for D3D11 cover it. Visible changes in its SDL host (`d3d11_host_sdl.c`: window, overlay, sizing, input) are mirrored in Metal's SDL presenter where they apply, or recorded in TASKS.md. Workarounds needed only under DXVK-native are logged in TASKS.md.

### D10. Wizard on SteamOS: one optional low-resource test, last

**Decided (the user, 2026-10-21):** "We can test one just for low-resource hosts testing, but leave optional and last".
- **What the wizard ships.** Its `linux` target covers Linux hosts with Docker (the Linux/Proton host and other desktop distros), tested on the PC under Linux. Players on the Deck install the Mac-built package.
- **The optional test.** The last task of the change (5.6) is one wizard build-and-test on the Deck, which stands in for a low-resource host. It uses the clang plus sniper sysroot route, since SteamOS has no Docker.
- **Exception to the build rule.** This is a one-off exception to "builds on the Mac, never on the Deck", granted by the user for this test only.
- **It gates nothing.** It does not gate any merge. It runs only after everything else in the change has merged, and a failure becomes a TASKS follow-up.

## Risks / Trade-offs

- **DXVK-native or vkd3d-shader differ from the pair Proton bundles, and a golden drifts.** Pin the versions to the ones in the Proton used for the references, record them in `golden.json`, and keep the native Windows gate as the arbiter. Compare the DXBC of every emitted shader on both paths (task 3.4).
- **SDL3 is not in the sniper runtime.** Bundle a pinned `libSDL3.so` (zlib). Task 1.6 checks.
- **Emulated amd64 builds on the Mac are slow.** Fall back to clang plus the sniper sysroot (D4).
- **The x86-64 fault glue is new low-level code.** Use the existing decoder, add a ctest that traps a synthetic MMIO load and store, and test on the Deck.
- **Case-sensitive file systems.** A wrong-case read on Linux returns "missing", where Windows and macOS would find the file. Add a one-time case-insensitive fallback with a warning in the file layer, tested in a ctest.
- **Another target to keep green.** It is the same renderer, so the cost is host glue and packaging, not shaders.

## Open Questions

None open. All were resolved by the user on 2026-10-21 (recorded verbatim):
- Proton's role and the Windows gate: D7.
- The SteamOS default: D7.
- SDL3 OQ1: D6.
- The licences: D1, where LGPL vkd3d-shader and zlib DXVK are accepted.
- Priority: D8.
- The wizard on SteamOS: D10.

## Probe B result

Toolkit 4559bae9 on Fedora 42 x86-64 (`linux/amd64` under emulation on the Mac, `docker build --output`):
- **Configure:** the root CMake configure passed with `-DXBOXRECOMP_ENHANCE=ON`.
- **POSIX ctests** (`tests/posix_ctest.sh`, which builds each test project itself): **82 pass, 0 fail**. Three were skipped:
  - `mmio_decode_a64`: arm64 only;
  - `reproducible_link`;
  - `usb_ohci_posix`: OHCI is off on x86-64 POSIX, as the Context section says.

  17 were n/a: Windows or Proton harnesses such as `xaudio2`.
- **Evidence:** `runs/linux-vulkan/linuxprobe/out/` (`status.txt`, `ctest.txt`, `root.cfg.log`, `pkgs.txt`, `ctest/`) and `docker.log`.
- **Not measured:** the root build of the library itself. The probe passed `-k 0` to `cmake --build` instead of after `--`, so that step never ran. Task 1.1 starts with this build. No Linux build failures are known yet.
- **Time:** the whole configure-and-ctest step took 700 s under amd64 emulation on the Mac. It does not settle D4 (Fedora, not sniper; ctests, not the full cat build). Task 1.5 re-times a full build in the sniper image and decides between the image and the clang plus sysroot route.
