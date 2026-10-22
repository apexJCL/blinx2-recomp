## Why

The user asked on 2026-10-21 for a native Linux build that renders through Vulkan and does not need Proton. Today every Linux player, the Deck included, runs the Windows exe under GE-Proton through umu (the `steamos` package). That costs:
- a first launch that downloads a runtime and GE-Proton and makes a prefix, and shows nothing for minutes;
- umu's pressure-vessel failing inside the `xbr-build` distrobox, so the toolkit ctests have not run on the Deck since (TASKS);
- Wine-only behaviour in the runtime: Windows thread ids, `winebus` loading the host SDL, the `d3dcompiler_47` of whatever Proton is pinned.

Native Linux is "today absent" (`sdl3-migration` spike). The toolkit's POSIX host already builds and runs its ctests on Linux (the Linux/Proton host, 2026-10-08 and 2026-10-17). cat itself has never been built or run natively on Linux, and the POSIX host renders only on the CPU path there: the Metal backend is macOS-only and the D3D11 backend is `#ifdef _WIN32`.

This change is the spike's answer and the plan that follows from it. It measures four routes to a Vulkan renderer on Linux, lists what else native Linux needs, and records the user's decisions (2026-10-21) on the gates, Proton's role, the SteamOS default and where the Linux gate runs.

## What Changes

**Recommendation: dxvk-native.** Build the existing D3D11 backend (`src/d3d/nv2a_pb_d3d11.c`) on Linux against DXVK's native build (`libdxvk_d3d11.so`, `libdxvk_dxgi.so`; zlib). Compile its HLSL through `libvkd3d-shader` (LGPL-2.1+), the same HLSL compiler Proton already uses. It presents into the SDL3 window. Proton's D3D11 path is already DXVK on Vulkan, so the native build runs the same renderer source, the same DXVK and the same HLSL compiler on the same RADV driver. The only difference is that Wine is not in the middle.

The probe (design "Evidence"; files in `xbox-recomp/runs/linux-vulkan/`) built and ran this chain in C on Fedora 42 x86-64 against DXVK 3.1.1 native, `libvkd3d-shader` 1.14 and SDL3, on lavapipe (Mesa's CPU Vulkan) under Xvfb:
- the toolkit's `COBJMACROS` style compiles;
- HLSL compiles to DXBC;
- an SDL3 window serves as the swap chain's `HWND`;
- `CreatePixelShader` succeeds and an occlusion query is created (not yet issued or read back).

The routes, in agent-days (one agent-day is about 8 h of agent time):

| Route | Effort | Parity risk | Upkeep under "backends agree" |
|---|---|---|---|
| **dxvk-native (recommended)** | 15-20, everything native Linux needs included | low: same code, DXVK and compiler as the Proton golden | none added: still two GPU backends (D3D11, Metal) |
| Hand-written Vulkan backend | 24-32 | medium: a new backend re-earns every golden | a third backend: every renderer fix lands three times |
| SDL_GPU, one backend over Vulkan, Metal and D3D12 | 30-40 to replace both | high: no occlusion queries; both proven backends re-earn their goldens | lowest in the end, but only after the replacement |
| Status quo (Proton only) | 0 | none | none; Linux stays a Windows exe |

The work this change plans:
- **Toolkit (`posix-host/portability`):**
  - `nv2a_pb_d3d11.c` builds on Linux behind `XBOXRECOMP_DXVK_NATIVE` (default OFF; the CLI's `linux` target turns it ON), with its Win32 window, sizing, title, clock, message pump, overlay and `LoadLibrary("d3dcompiler_47")` split into a host seam. A Win32 seam keeps today's code; an SDL3 seam adopts the presenter's window and compiles HLSL through `vkd3d_shader_compile`.
  - Input on Linux comes from the SDL host layer, as it does on macOS.
  - An x86-64 POSIX fault path for trapped MMIO: the existing x86-64 decoder under `sigaction`. Today only arm64 POSIX traps, so on x86-64 Linux the OHCI pad model is off and the AC'97 trap spins.
  - The first full Linux build of the root library (task 1.1; the probe ran only the ctests) and a case-insensitive fallback for guest file opens.
- **cat:** a Linux target in `game.toml`, a Mac-built Linux binary on the CPU path for SDL3's gate 8, a `NOTICE` section for the Linux package's LGPL vkd3d-shader, and docs.
- **CLI (`xboxrecomp-cli`):**
  - a `linux` build target, built on the Mac in a pinned Steam Runtime 3 (sniper) image through `docker build --output`, or by the pinned clang against a pinned sniper sysroot (design D4);
  - a `linux` package target: a tar that installs as a Steam shortcut running under the Steam Linux Runtime, with the DXVK and vkd3d-shader libraries beside the exe;
  - `doctor` checks and `golden` and `bench` recipes for native runs on the Deck;
  - licence files and `credits.py` entries for DXVK, vkd3d-shader and SDL3 (if bundled), and a `readelf`/`ldd` check against GPL dependencies;
  - the wizard offers the native target on Linux hosts with Docker. The last, optional task is one wizard build-and-test on the Deck as a low-resource host (design D10): a one-off exception to the no-builds-on-the-Deck rule that gates no merge.
- **Gates:** native Linux adds a gate: the native D3D11 golden against the same `golden.json` references, on the Deck until the Linux/Proton host PC is re-provisioned with Linux, then on the PC. Native Windows stays a required gate; Proton is only a stop-gap when no Windows host is up (design D7).
- **SteamOS:** the native `linux` package is the default; the `steamos` (Proton) package stays as an opt-in route (design D7).

Non-goals:
- a hand-written Vulkan backend or an SDL_GPU backend (design D2, D3; SDL_GPU is revisited only on the conditions in D3);
- Flatpak and Flathub;
- Linux arm64 (it would need Linux ucontext macros for the A64 decoder; recorded as a follow-up);
- dropping the Windows build or the opt-in `steamos` (Proton) package;
- the CPU backend as a Linux gate.

## Capabilities

### New Capabilities
- `host-linux`: the native Linux x86-64 host: its build, its renderer (D3D11 through dxvk-native), its fault path, its package and its gate.

### Modified Capabilities
- `gpu-backend`: the D3D11 backend also builds on Linux through dxvk-native and is held to the same D3D11 golden references there.

## Impact

- **Ordering.** This change lands after the tracker item (SDL3), not inside it. The user's order is DSP (spike the tracker item), then SDL3, then the release. dxvk-native's WSI should take the SDL3 window, not an SDL2 one that then replaces. The tracker item's Linux-native gate (its task 10.2) runs as this change's Phase 0 (design D6). Phase 0 of this change (root Linux build, x86-64 fault path, case fallback, sniper image, SDL3-in-sniper check, CPU-path Linux cat) touches no SDL code and can run before the tracker item when a worker is free. Phase 0 carries the tracker item's gate 8 and is a prerequisite of the tracker item's merge. Priority (the user, 2026-10-21): right after SDL3, with Phase 0 free to start early on a free worker.
- **SDL3 OQ1:** decided as option (d) (design D6). Build on the Mac, run on the Deck, until the Linux/Proton host PC is re-provisioned with Linux; the gate then moves there. No build happens on the Deck, so no exception is needed.
- **Hosts:** the Mac (builds); the Deck (native Linux runs and goldens) until the re-provisioned PC takes over Linux and Proton runs; native Windows on the PC (the required Windows gate, the user switches the boot).
- **Goldens:** D3D11 references, a new `native` run mode on the Deck. Metal is untouched, but Phase 0 changes shared POSIX and kernel code, so those tasks gate on the Metal and Windows goldens.
- **"Backends agree":** native Linux is the D3D11 path, not a third backend; design D9 proposes the CLAUDE.md wording for the orchestrator to apply.
- **Licences:** DXVK (zlib, its licence files copied in) and vkd3d-shader (LGPL-2.1+, built unmodified from a pinned upstream tarball, shipped as its own replaceable `.so` with a notice and the exact source link). The toolkit already carries `LICENSES/LGPL-2.1.txt`. SDL3 comes from the Steam runtime, or is bundled (zlib) if task 1.6 finds it missing.
- **Tracker:** The tracker item (this spike, accepted). The orchestrator files one implementation item per phase. The optional Deck wizard test (design D10) is its own last item and gates nothing.
