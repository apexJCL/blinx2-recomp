## Context

Both GPU presenters end in one textured draw of the frame into
`nv2a_present_rect`'s rectangle on the window's back buffer:
- Metal: `fbm_present` (`src/video/fb_present_metal.m`) draws the slot
  texture (exactly the frame size) with `s_pso`/`s_pso_crop`, then the
  overlay in the same encoder.
- D3D11: `d3d11_flip` calls `present_blit` (`src/d3d/nv2a_pb_d3d11.c`) when
  the back buffer is not the frame size; otherwise it is a `CopyResource`.
  The overlay (`ovl_present`) draws after the frame dump, before `Present`.

The frame at that point is the render-scale frame (render.scale x 640x480,
with Hor+ width), which is what the tracker item asked the shader to read.

## Library

librashader v0.12.0 (C ABI 2, API 5), the upstream prebuilt release zips:

| Zip | sha256 |
|---|---|
| librashader-aarch64-macos-v0.12.0-optimized.zip | 49808004a4904f6a99e0231092dcfdfe52b7b61f68430a4c9f1e165749c4c90e |
| librashader-x86_64-windows-v0.12.0-optimized.zip | 521fe0f364bfa705883f9e99fb1733a3a24f0f403bcc5591b6b78f6cff289183 |

(v0.12.1 is tagged but has no release assets.) The D3D backends do not
build with MinGW (upstream issue #220), so our MinGW exe loads the MSVC dll
at run time and calls it through plain C and COM pointers; the Metal dylib
is loaded the same way, which keeps one code path and no link dependency.

**MPL-2.0 terms.** The library is MPL-2.0. Distributing it unmodified in
executable form (section 3.2) needs: the Source Code Form available to the
recipients, and a notice telling them how to get it. A dlopen'd library is a
separate file inside a Larger Work (section 3.3), so the game and toolkit
licences are not affected. The release zips carry no licence file, so the
toolkit keeps the licence text as `LICENSES/MPL-2.0-librashader.txt` and the
build stages it as `shaders/LICENSE-librashader.txt`, beside
`shaders/README.md` with the source URL
`https://github.com/SnowflakePowered/librashader/tree/librashader-v0.12.0`;
the toolkit NOTICE names it too.
The vendored `librashader.h` is MIT (Copyright 2022 chyyran), which keeps its
header comment.

**No VC++ runtime shipped**. The dll imports VCRUNTIME140(_1) and
the UCRT; Proton has them, a clean Windows 11 may not. When LoadLibrary
fails, the loader checks for `vcruntime140.dll` and logs one line naming the
Microsoft Visual C++ Redistributable.

## Presets (libretro/slang-shaders 2b0530bac0e8083d9d643c194929dc0a6b69bd35)

| Name | Files | Licence | Verdict |
|---|---|---|---|
| crt-lottes | crt/crt-lottes.slangp, crt/shaders/crt-lottes.slang | public domain (Timothy Lottes) | bundled |
| crt-lottes-fast | crt/crt-lottes-fast.slangp, crt/shaders/crt-lottes-fast.slang | public domain ([CRTS]) | bundled; the light one for the Deck |
| crt-hyllian | crt/crt-hyllian-fast.slangp, crt/shaders/hyllian/crt-hyllian-fast.slang | MIT (Hyllian 2011-2015) | bundled under the name crt-hyllian |
| fsr | edge-smoothing/fsr/fsr.slangp, shaders/fsr-pass0/1.slang, ffx_a.h, ffx_fsr1.h | Unlicense; ffx headers MIT (AMD) | bundled (an upscaler, not a CRT) |
| full crt-hyllian (5 passes) | crt/crt-hyllian.slangp | support passes (multiLUT, glow) have no licence header; the Sony Wega LUT PNGs have none | **not bundled**; a player can point `present.shader` at their own copy |

The files keep their directory layout under `assets/shaders/` so the
presets' relative paths resolve unchanged, and each preset sits at the top
as `<name>.slangp`, a one-line `#reference` to the upstream preset. On
macOS the loader also looks in `<exe_dir>/../Resources/shaders` and the
library in `<exe_dir>/../Frameworks`, for the app bundle.

## Keys

- `present.shader`: `none` (default, the stock present), a bundled name
  (`crt-lottes`, `crt-lottes-fast`, `crt-hyllian`, `fsr`), or a path to a
  `.slangp` (relative to the exe directory, or absolute). A bare name looks
  for `<exe_dir>/shaders/<name>.slangp`.
- `present.shader_lib`: empty (default): `librashader.dylib` / `.dll`
  beside the exe; otherwise that path.
- Env: `RECOMP_PRESENT_SHADER`, `RECOMP_PRESENT_SHADER_LIB` (CONFIG tier).

## Runtime

- The loader is lazy: nothing loads while `present.shader` is `none`, so
  the stock path runs no new code beyond one flag check per present.
- A generation counter: the menu (or the config at start) sets the request;
  the backend compares the generation each present and rebuilds its chain
  on a change (the old chain is freed after the GPU is done with it). A
  failed preset logs one line, keeps the stock present and does not retry
  until the request changes.
- Both backends resolve every librashader call they use (preset create
  and free, chain create, frame and free) when they build the chain; a
  library without one fails that generation with one line, never a black
  frame.
- Metal: the chain is built on the presenter's command queue and runs in
  the present command buffer: clear the drawable, run the chain into it
  with the present rect as viewport, then the overlay with a load action.
  The slot texture is already the frame's size, so it is the chain's input
  as is. `display.overscan` is ignored while a shader runs (one log line):
  the chain samples the whole source, and a crop would need a scratch copy
  for a setting the CRT look replaces anyway.
- D3D11: with a shader on, the flip skips `present_blit` and calls the
  chain with an SRV of the frame and the back buffer's RTV, the present
  rect as viewport, after a clear. A target grown past the frame (render
  scale, pads) is copied into a scratch texture of the frame's extent
  first; the scratch is released with the chain (a switch to `none` or a
  failure). Overscan is ignored as on Metal. `s_sc_init = 0` afterwards,
  as the blit does, because librashader changes pipeline state.
- frame_count counts presents since the chain was built; a rebuild makes a
  fresh chain, so there is no history to clear. frames_per_second is the
  measured present rate (`nv2a_present_chain_rate`, a moving average of
  the intervals; BLiNX 2's lock30 says 30), not a fixed 60, for presets
  that animate by time.
- Evidence: the Metal window shot (`RECOMP_WINDOW_SHOT`) shows the drawable.
  On D3D11 the blit path dumps the render target, not the back buffer, so
  with a shader on the flip also writes the back buffer as
  `present_<n>.bmp` next to the frame dumps. Goldens run with `none` and
  are unchanged.
- The CPU rasteriser and SDL presenter: unsupported, one log line.

## Packaging

The pins live in the toolkit, not the CLI: `cmake/librashader.cmake` holds
the sha256 of each release zip (macOS arm64/x86-64, Windows x86-64/arm64),
downloads the one for the target into `<build>/_deps/librashader` (or takes
`XBOXRECOMP_LIBRASHADER_ARCHIVE`), checks it (a wrong sha256 stops the
configure; a failed download only warns and builds without the library,
since the feature is opt-in and the runtime then says the library is
missing), extracts only the library and
copies it, `assets/shaders` and the licence beside the exe after each build
(`xboxrecomp_present_shaders(<target>)`, which a game calls; BLiNX 2 does).
So `blinx2 build` on any host, the PC build host included, gives an exe dir
that runs the shaders as is.

The CLI's package step carries what the build put there: `shaders/` at the
payload top (the exe dir on Windows and SteamOS, `Contents/Resources` on
macOS, where the runtime also looks), `librashader.dll` beside the exe, and
`librashader.dylib` as a Frameworks companion. Both feed the incremental
stage inputs, so a changed preset or library restages.

Follow-ups: `bench` ships `*.dll` beside the exe but not `shaders/`, so a
bench run that wants a preset names an absolute `.slangp` path (as the
phase 1 Deck run did); the wizard's preset fetch stays out of scope.
