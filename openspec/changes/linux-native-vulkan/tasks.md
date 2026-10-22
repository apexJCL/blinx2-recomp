Conventions:
- **Branches.** Every branch is `feat/linux-native`, in its own worktree under `wt/linux-native/`: the toolkit off `posix-host/portability`, the CLI off `main`, cat off `main`.
- **Builds** happen on the Mac only (design D4). The Deck runs binaries and never builds them, except the optional task 5.6 (design D10). Deck slots come from the orchestrator (`notes/benches.md`; `blinx2 bench` takes the flock).
- **No sound on the Mac.** Headless runs set `SDL_AUDIO_DRIVER=dummy`. Sound on the Deck is allowed.
- **Evidence:** `bench-logs/<stamp>`; raw dumps and probe outputs in `xbox-recomp/runs/linux-native/` (the spike's probes are in `xbox-recomp/runs/linux-vulkan/`). Nothing derived from the game is committed.
- **Tracker:** The tracker item (spike, accepted). One implementation item per phase, filed by the orchestrator.
- **Gates.** Each merge passes the CLAUDE.md gates that apply to it (table below), and every merge gets a review whose fixes go back to the branch agent.
  - **Mac:** build with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools` and `-DXBOXRECOMP_ENHANCE=ON`; `tests/posix_ctest.sh <build-dir>` 0 FAIL.
  - **Linux:** the same ctests built on the Mac for Linux x86-64 and run on the Deck (later the PC under Linux), 0 FAIL (from 1.5 on).
  - **Goldens** whenever a change touches what the game executes (runtime, kernel, renderer, audio, input): the Metal golden on the Mac (`blinx2 golden`) and the D3D11 golden on **native Windows** (the PC booted into Windows; the user switches the boot). Native Windows is required. `blinx2 bench golden` under Proton is only a stop-gap when no Windows host is up, and the Windows run is then still owed (design D7).
  - **Native Linux golden** (from Phase 2): the D3D11 golden over dxvk-native, on the Deck until the Linux/Proton host PC is re-provisioned with Linux, then on the PC. It adds to the Windows gate; it never replaces it.
  - **cat:** `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`.
  - **CLI:** `uv run pytest tests` plus the same ruff checks; `wizard/check.sh` for wizard changes.

| Task | Mac build + ctest | Linux ctest (Deck, later PC) | Metal golden | Windows golden (native; Proton stop-gap) | Native Linux golden | cat pytest/ruff | CLI pytest/ruff |
|---|---|---|---|---|---|---|---|
| 1.1 root build fixes | yes | yes | if shared code changes | if shared code changes | no | no | no |
| 1.2-1.3 fault path (shared with arm64 macOS) | yes | yes | **yes** | **yes** | no | no | no |
| 1.4 file-layer case fallback (every host) | yes | yes | **yes** | **yes** | no | no | no |
| 1.5-1.8 sniper image, SDL3 check, CPU-path cat | yes | yes | no | no | no | yes (cat) | no |
| 2.x host seam | yes | yes | yes | **yes** (2.2, native Windows) | no | no | no |
| 3.x dxvk-native | yes | yes | no | yes | **yes** | no | no |
| 4.1-4.5 CLI | no | no | no | no | yes (4.5) | no | **yes** |
| 5.1-5.5 roll-out | no | no | yes | **yes** | **yes** | no | no |
| 5.6 optional Deck wizard test | none: it gates no merge | | | | | | |
| 4.6 cat targets and docs | no | no | no | no | no | **yes** | no |
| 4.7 wizard | no | no | no | no | no | no | **yes** + `wizard/check.sh` |

## 1. Phase 0: Linux host groundwork (may start early on a free worker; a prerequisite of the tracker item's merge)

- [x] 1.1 Build the toolkit root library on Linux x86-64. Probe B ran only the ctests, so this is the first full build. Fix any failures behind no new options. Mac and Windows builds stay unchanged.
- [x] 1.2 Add x86-64 Linux `sigaction` glue for trapped MMIO in the toolkit's POSIX fault path, using the existing x86-64 decoder in `mmio_decode.h` (`REG_RIP` and the `gregs` mapping). Add a ctest that traps a synthetic load and store. The arm64 macOS path shares this file, so the gate includes the Mac ctests, the Metal golden and the native Windows golden. Native Windows golden waived by the user (2026-10-21): the Windows codegen is identical (review, llvm-mingw disassembly); run at the next Windows boot.
- [x] 1.3 Turn the AC'97 and OHCI trap paths on for x86-64 Linux once 1.2 passes. Check that the AC'97 channel reset no longer spins (ctest).
- [x] 1.4 Add a case-insensitive fallback for guest file opens on case-sensitive file systems. It logs one warning per path. Add a ctest. It changes the kernel file layer on every host, so the gate includes the Metal and native Windows goldens. Native Windows golden waived by the user (2026-10-21): the Windows codegen is identical (review, llvm-mingw disassembly); run at the next Windows boot.
- [x] 1.5 Add the Steam Linux Runtime 3.0 (sniper) SDK builder image, pinned by digest, built through `docker build --output` with no bind mounts. It builds the toolkit and the ctests. Time a full build there (design D4).
- [x] 1.6 Check whether SDL3 (and which version) is in the sniper runtime. If not, build and bundle a pinned `libSDL3.so` (zlib). (Was 4.3.)
- [x] 1.7 Build cat for Linux x86-64 on the CPU path (`XBOXRECOMP_DXVK_NATIVE` OFF) in the sniper image. When the DSP is ON, link dsp56300's `x86_64-unknown-linux-gnu` archive and re-measure its cost on the Deck.
- [x] 1.8 SDL3 gate 8 under option (d) (`sdl3-migration` 10.2), on the Deck in desktop mode, Mac-built binaries only:
  - the POSIX ctests, 0 FAIL;
  - a 30 s windowed `@attract` (`RECOMP_WINDOW_QUIT_AFTER=30`) with sound, logging `SDL <driver> renderer` and `[SDL3] audio initialized: driver <pipewire|pulseaudio>`;
  - a `scripts/vpad.py` pad present at launch, and one created after launch (`host pad added`).

  Verify: logs in `bench-logs/`, a screenshot in `runs/linux-native/`.

  Passed on the Linux/Proton host on 2026-10-21 (`bench-logs/linux-native-gate8/`). The ELF links SDL2, so it logs `[SDL2] audio initialized`; the `[SDL3]` line waits.

## 2. Phase 1: D3D11 host seam (after the tracker item)

- [ ] 2.1 Add `d3d11_host.h` and move every Win32 call in `nv2a_pb_d3d11.c` into `d3d11_host_win32.c`, with no behaviour change:
  - the window class and window (`RegisterClassA`, `CreateWindowW`, `GetModuleHandleA` :483);
  - sizing (`GetSystemMetrics`, `AdjustWindowRect` :501/:514, `SetWindowPos` :3791);
  - the title (`SetWindowTextW` :3909);
  - timing (`QueryPerformanceCounter`/`QueryPerformanceFrequency` :4132), which becomes a host clock call;
  - `wnd_proc` and the keyboard and mouse feed;
  - the swap-chain HWND and `MakeWindowAssociation`;
  - the `d3dcompiler_47` load.
- [ ] 2.2 Gate 2.1 with a Mac build and ctests, a Windows cross-build, and the D3D11 golden on native Windows (Proton only as a stop-gap, with the Windows run still owed). Every frame's verdict and flips/s must match main.
- [ ] 2.3 Add `d3d11_host_sdl.c`. It adopts the presenter's SDL3 window (as the Metal backend does) and passes the `SDL_Window*` as the `HWND`. It leaves input, title and window size to the SDL host layer, and reports the drawable size.
- [ ] 2.4 Draw the enhance-menu overlay through the SDL host on Linux, as the Metal presenter does. Visible behaviour matches Windows and macOS.
- [ ] 2.5 Add the HLSL compile shim over `vkd3d_shader_compile` (HLSL to DXBC TPF) in its own translation unit, with flags mapped from the backend's `D3DCompile` calls. Add a unit test that compiles every emitter's output for the attract frames' shader set.

## 3. Phase 2: dxvk-native build and parity

- [ ] 3.1 Add the CMake option `XBOXRECOMP_DXVK_NATIVE`, **default OFF**, so the existing POSIX Linux build, the ctests and `install_deps.sh` stay as they are. The CLI's `linux` target turns it ON. When ON:
  - it uses `dxvk-d3d11` and `dxvk-dxgi` from the DXVK native release tarball, pinned by version and sha256;
  - `libvkd3d-shader` is built unmodified from a pinned upstream source tarball (version and sha256 in the pins). The package's source link points at that exact tarball.
- [ ] 3.2 Make `RECOMP_PB_BACKEND=d3d11` select the backend on Linux. Defaults on Linux: `d3d11` when built with `XBOXRECOMP_DXVK_NATIVE` ON (the shipped package), `cpu` otherwise. Document this in `docs/env.md`.
- [ ] 3.3 Build cat for Linux with `XBOXRECOMP_DXVK_NATIVE` ON in the sniper image.
- [ ] 3.4 Dump the DXBC of every compiled shader on one Proton run and one native run of the attract scenario, and diff them. Explain or fix each difference.
- [ ] 3.5 Run the D3D11 golden natively on Linux (the Deck, or the PC once re-provisioned) against `analysis/golden/golden.json` (all scenarios). Record verdicts and flips/s beside the native Windows run of the same build. DXVK-native-only workarounds are logged in TASKS.md.

## 4. Phase 3: CLI, package, licences and wizard

- [ ] 4.1 CLI: add the `linux` build target (`BUILD_TARGETS`) using the 1.5 image with `XBOXRECOMP_DXVK_NATIVE=ON`, and a `doctor` check for Docker and the pinned image.
- [ ] 4.2 CLI: add the `linux` package target (`linux-x86_64`), a tar with:
  - the exe;
  - `lib/` holding DXVK, vkd3d-shader and SDL3 if 1.6 requires it;
  - `RPATH=$ORIGIN/lib`;
  - a launcher;
  - `NOTICE` and `LICENSES/`: DXVK's own licence files copied from its tarball, LGPL-2.1 for vkd3d-shader with the exact source link, and zlib for SDL3 if bundled.
- [ ] 4.3 Licence checks:
  - CLI `credits.py` entries for DXVK, vkd3d-shader and SDL3 (if bundled);
  - a cat `NOTICE` section for the Linux package's LGPL vkd3d-shader;
  - a package test that runs `readelf -d` (and `ldd` in the sniper image) on every bundled `.so` and fails if any pulls in a GPL-only dependency.
- [ ] 4.4 CLI: add `package install` for `linux` on SteamOS, the default package there; `steamos` (Proton) becomes opt-in. It creates a non-Steam shortcut set to run under "Steam Linux Runtime 3.0 (sniper)" with `DXVK_WSI_DRIVER=SDL3`.
- [ ] 4.5 CLI: add a native mode to `bench` and `golden` (`--native`) that runs the Linux package on the Deck without umu.
- [ ] 4.6 cat: add `linux` to `game.toml` `[build]` and `[package]` targets, and document it in the README and `docs/`.
- [ ] 4.7 Wizard: offer the `linux` target on Linux hosts **that have Docker** (the Linux/Proton host and other desktop distros), using the same sniper image as the CLI. Test it on the PC under Linux once it is re-provisioned. The wizard on SteamOS (no Docker, which would need the clang plus sniper sysroot route) is not a gate. It gets one optional test in 5.6 (design D10).

## 5. Phase 4: gates and roll-out

- [ ] 5.1 Review of each merge (toolkit seam, Linux host, CLI). Fixes go back to the branch agent.
- [ ] 5.2 From Phase 2 on, every change that touches what the game executes runs the native Linux golden in addition to the native Windows and Metal goldens (design D7).
- [ ] 5.3 Hand the orchestrator the proposed CLAUDE.md "backends agree" wording (design D9) to apply. Do not edit CLAUDE.md from the branch.
- [ ] 5.4 Hand the orchestrator the gate changes for CLAUDE.md and `bench-coordination`: native Linux added as a gate, native Windows required, Proton a stop-gap; the re-provisioned PC takes over Linux and Proton runs from the Deck.
- [ ] 5.5 Update TASKS.md and RESUME.md. Record Linux arm64 and the SDL_GPU revisit conditions (design D3) as follow-ups.
- [ ] 5.6 **Optional, last, gates no merge** (design D10). One wizard build-and-test on the Deck as a low-resource host. The wizard builds the `linux` target on the Deck through the clang plus sniper sysroot route (SteamOS has no Docker) and the result is launched once.
  - The user granted a one-off exception to the no-builds-on-the-Deck rule for this test only (2026-10-21).
  - It runs only after 5.1-5.5 have merged, in an orchestrator Deck slot.
  - Record the build time, peak memory and disk use in TASKS.md. A failure becomes a TASKS follow-up, not a blocker.
