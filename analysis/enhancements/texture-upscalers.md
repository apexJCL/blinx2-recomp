# Texture upscalers: re-assessment and measurements

Spike of 2026-11-01 for the `texture-upscale` change. It covers five
things:

- what still holds in the spec, and what does not;
- the upscalers a builder can plug in (built-in, ncnn command tools and,
  since the user's decision of 2026-11-01, a PyTorch backend);
- what each one costs on this Mac (Apple M4 Max);
- the shape of a CLI preview step that puts their outputs side by side;
- an in-game A/B of three upscalers on the PC (section 8).

This document holds names, hashes, sizes, timings and licences only. The
comparison grids and every decoded texture stay in a local runs
directory and are never committed, attached or published.

The spike code lives on the CLI branch `spike/texture-upscalers`, under
`spike/`:

| Script | What it does |
|---|---|
| `inventory.py` | the archive feeder, without the texel cap and the mip rule |
| `summarize.py` | the class rules |
| `packsize.py` | the pack-size estimate |
| `extract.py` | the 16 samples |
| `grid.py` | the harness: padding, alpha split, 3x crop, two runs per upscaler, timings |
| `mkgrid.py` | the per-class PNG grids and `index.html` |

## 1. Re-assessment of the spec

### What holds

- **D1, joined on the hash.** The archive half works as designed. A
  recursive IPK1 walk (nested `.ipk` with an inline index, two levels
  deep) reaches every DDS and MIX in `media`, `lng_us` and `tank_tex`:
  22,931 entries.
- **D2, the classes.** Each one has a different best upscaler (section
  4), so the per-class table is the right shape.
- **D7, the pluggable interface.** It covers every tool tried here:
  - the command template with `{in_dir}`/`{out_dir}` fits
    realesrgan-, waifu2x-, realcugan-ncnn-vulkan and upscayl-bin as they
    are;
  - split alpha with colour extended under transparent texels works for
    every RGB-only model. No halos appeared on the cutouts.
- **The wrap pad of 8 texels.** It gave no seam on the tiled world
  samples.
- **D9, the GUI.** It stays the place where an owner edits rules. The
  preview step of section 5 is a smaller, earlier piece that feeds it.

### What is stale or was never checked

- **"Decided" item 3 is reversed.** The user, 2026-11-01: "Let's allow
  PyTorch backend". D7.4 and D16's last row change with it (section 6).
- **D16, Apple Silicon.** The ncnn tools run on Apple Silicon through
  MoltenVK. This is now verified for:
  - realesrgan-ncnn-vulkan 20220424;
  - waifu2x 20250915;
  - realcugan 20220728;
  - upscayl-bin 20251207.

  All are universal macOS builds and run on the M4 Max.
- **D6's build-time figures** ("~1 s per 256x256 at 4x per core in pure
  Python; ncnn 0.1-1 s") are replaced by the measured table in section 3.
- **Phase 0 never ran.** This spike does 0.2 (the archive feeder) and
  most of 0.3 (the calibration of the external upscalers and the CLI's
  `xbr`; the BC1/BC3 encoders and the pure-Python `lanczos`, `epx`,
  pad, split and down-to-scale are still to be timed, in 3.4 and 3.1).
  - 0.1, the toolkit dump and trace, is still open. VRAM per scene and
    the dump-only formats need it.
  - The parts of 0.4 that come from the archives are in section 2.
- **3x is missing from the spec.** D2's defaults are 2x and 4x, but
  render scale 3 is a common choice. What 3x needs:
  - **The built-ins:**
    - `xbr` 3x is the CLI's own kernel with its `(2, 4)` guard widened to
      `(2, 3, 4)`. `_tables(s)` is already generic, and the output looks
      correct.
    - `lanczos` and `epx` do 3x natively.
  - **CNNs:** most are 4x (some 2x), so 3x is "4x, then a premultiplied
    lanczos down to 3x".
  - **Native 3x models:** realesr-animevideov3 x3, Real-CUGAN se/pro 3x,
    and upscayl-bin `-s 3`, which runs a 2x model and resamples.
  - **D4's sampler shift** is `log2(entry_w / guest_w)`. At 3x that is
    1.585, so the LOD clamps and the sampler key need a fractional shift.
    Both APIs take float LOD clamps; the key carries the entry's integer
    scale, which quantises the shift (design.md D4, task 1.2).
  - **The default scale** follows the render scale `R`: `clamp(R, 2, 4)`
    for ui, and for world once a CNN is picked; world `lanczos` stays
    2x, text 2x, font 4x (design.md D2). A 4x entry drawn at `R = 3`
    spends 7/16 (about 44%) of its texels on minification.
  - **The CLI's 2/4-only checks** also widen: `scaler.py`'s guard,
    `manifest.py`'s `enhance.hud.scale` and `hud.py`'s `--scale`
    choices (task 3.1).
  - **BC blocks.** A 3x side is a multiple of 4 only when the source side
    is. Sources with a side of 1 or 2 are already `data` (skipped), so no
    entry is lost.
  - **The runtime.** Its lookup checks the aspect ratio only
    (`nv2a_tex_pack.c` `lookup`), so 3x entries load today.

### Gaps against "upscale all assets"

| Gap | Size | What closes it |
|---|---|---|
| Non-DXT archive entries the feeder cannot hash (TGA8 829, RGB16A 25, RGB32A 19, TGA32 1) | 874 entries | the dump (0.1/1.5); TGA8 is palette data, which D2 already routes through the dump |
| Mipped world textures | 2,959 of 5,481 unique world hashes | D4's sampler shift (1.2), fractional at 3x |
| Textures above the HUD cap (64K texels) | 151 world, 36 text, 28 ui unique | the cap is a `hud` preset rule; the other presets lift it |
| `text` is the largest class | 161 M unique texels, 3,048 hashes (mostly 512x128 language images) | a scale of its own (2x default kept); the class is an upper bound, since everything in `lng_us` outside the `_tex/_tg/_ts` stage archives counts as text |
| Render targets, volatile and dynamic textures | unknown until the dump | the dump (D1) |
| In-game frames | none taken | section 7 |

## 2. Inventory (archives only)

Totals: 22,931 entries: 22,056 decodable DXT, 874 non-DXT and one
skipped archive; 8,926 unique DXT hashes; 565.1 M DXT texels with
duplicates (577.6 M with the non-DXT entries).

The Entries column counts every entry of the class, non-DXT included
(world holds the 829 TGA8); the other columns are DXT only.

| Class | Entries | Unique hashes | Unique M texels | Mipped (unique) | Over 64K texels (unique) | Formats (unique) |
|---|---|---|---|---|---|---|
| world | 17,481 | 5,481 | 158.47 | 2,959 | 151 | DXT1 4,101, DXT3 1,302, DXT5 78 |
| text (upper bound) | 4,888 | 3,048 | 161.38 | 12 | 36 | DXT3 2,508, DXT5 494, DXT1 46 |
| ui | 294 | 294 | 13.66 | 0 | 28 | DXT3 215, DXT1 43, DXT5 36 |
| font | 2 | 2 | 0.13 | 0 | 0 | DXT5 2 |
| effect (name heuristic) | 265 | 101 | 0.82 | 16 | 1 | DXT3 72, DXT1 21, DXT5 8 |

- The ui class is cat's `[enhance.hud] textures` globs, `dds/font_*` is
  font, and effects are a name regex (`eff|fx|smoke|fire|spark|light|glow|kira|hit`).
- World entries are duplicated about 3.2 times across stage archives, so
  the hash join matters: per-stage builds would triple the work.

**Pack size, GPU-ready.** The encoding is BC1 for DXT1 sources and BC3
otherwise; mipped sources get a full chain (4/3). The figures are MiB:

| Class | 2x | 3x | 4x | raw RGBA at 3x |
|---|---|---|---|---|
| world | 456 | 1,026 | 1,824 | 6,262 |
| text | 613 | 1,379 | 2,452 | 5,544 |
| ui | 34 | 76 | 135 | 469 |
| font | 0.3 | 1 | 2 | 4 |
| effect | 3 | 7 | 13 | 30 |
| **all** | **1,107** | **2,490** | **4,426** | **12,310** |

What this means for D6:

- `ui` and `font` can stay raw.
- `world` and `text` must be BC; raw world at 3x is 6 GB.
- A 3x `all` pack is about 2.5 GB; `ui` plus `world` is about 1.1 GB.
- `[budget] pack_mb` needs these numbers. VRAM per scene waits for the
  dump.

## 3. Candidates and measurements

**The samples.** Sixteen textures in five classes (ui 5, font 1, text 2,
world 4, fx 4), decoded from level 0
(0.8253 M source texels in all):

| Class | Name | Size | Format | Hash |
|---|---|---|---|---|
| ui | `pause_mission` | 256x64 | DXT3 | `d02c345f1b06a971` |
| ui | `b2icon_car1a` | 64x64 | DXT3 | `f21622810a8a83df` |
| ui | `com_cursor` | 64x64 | DXT5 | `14c5b2bba4c90c9f` |
| ui | `equip_sboard_swe` | 256x128 | DXT3 | `ed020bf68dd80fa7` |
| ui | `com_bg_tom` | 1024x256 | DXT3 | `723e087185559e7c` |
| font | `font_arialnarrow_bold` | 256x256 | DXT5 | `3c09cf61a829ea46` |
| text | `mis_failed_us` | 256x64 | DXT5 | `117893ccdd3b8f36` |
| text | `demo_font01_tom_us` | 512x32 | DXT3 | `98588670461b33e3` |
| world | `i_b2_kabe11` | 128x128, 8 levels | DXT1 | `1062c05328a49354` |
| world | `p_b2_ntoge_all1` | 512x512, 10 levels | DXT1 | `652ef27dbf3e0795` |
| world | `i_b2_hekiga12` | 128x64, 8 levels | DXT1 | `1916608f3fae7746` |
| world | `h_medal_05a` | 128x128 | DXT1 | `182d4bff4fa66787` |
| fx | `a_b2_fire1red01` | 64x64 | DXT3 | `b23a270cddc8115b` |
| fx | `t_b2_hit002` | 256x256, 9 levels | DXT3 | `7a2abf284e980e51` |
| fx | `m_kemuri1a` | 256x128 | DXT3 | `b00861a539dbe0a0` |
| fx | `p_b2_r04leaf01` | 32x64, 1-bit alpha | DXT1 | `4a3d887d86a23ba8` |

**The pipeline**, D7's:

1. Pad 8 texels: wrap for world, edge otherwise.
2. Built-ins take RGBA. Every other upscaler gets split alpha: colour
   extended under alpha < 16, and alpha as a grey image.
3. Upscale.
4. Bring a 4x (or 2x) result to 3x with a premultiplied lanczos.
5. Crop the padding.

Each upscaler ran twice; "det" means the two output sha256s were equal.
Times are wall seconds for the whole set, the faster of the two runs.
They time the upscaler call only, over the padded inputs and, for split
upscalers, the alpha images too (1.534 M input pixels); the padding,
the split and the down-to-scale ran in numpy/Pillow outside the timed
call. So:

- `nearest`, `lanczos` and `scale3x` are numpy/Pillow stand-ins, for
  this spike only. The CLI's integer versions are pure Python, of the
  order of `xbr`'s seconds per megatexel, and are still to be timed
  (task 3.1).
- Every CNN figure is optimistic by the down-to-scale over its 4x
  output (16x the source texels), also still to be timed.
- The ncnn tools include their start-up (one process per batch, per
  file for Real-CUGAN). The torch rows do not: the harness kept the
  model in its own process. A cold plugin process adds about 0.85 s for
  the torch and spandrel import, 0.01-0.06 s for a Compact model's load
  and 0.02-0.4 s for the first inference (MPS warm-up), measured
  separately. The real `compare` step times the plugin as a subprocess.

Small textures favour the built-ins: the GPU tools pay start-up and
per-dispatch costs.

| id | Upscaler | Native | Runs (s) | s per source M texel | det | Est. world pass (158 M texels) |
|---|---|---|---|---|---|---|
| `nearest` | built-in (numpy here) | 3 | 0.007 | 0.01 | yes | 2 s |
| `lanczos` | built-in (Pillow here, spike only; the CLI's will be integer, pure Python) | 3 | 0.22 | 0.27 | yes | 43 s |
| `scale3x` | built-in EPX/AdvMAME3x (numpy here) | 3 | 0.011 | 0.01 | yes | 2 s |
| `xbr3` | CLI xBR lv2, pure Python | 3 | 6.74 | 8.17 | yes | 22 min per job |
| `xbr4` | CLI xBR, 4x then 3x | 4 | 7.08 | 8.58 | yes | 23 min per job |
| `esr-x4plus` | realesrgan-ncnn-vulkan `realesrgan-x4plus` | 4 | 9.69 | 11.74 | yes | 31 min |
| `esr-anime` | realesrgan-ncnn-vulkan `realesrgan-x4plus-anime` | 4 | 3.36 | 4.07 | yes | 11 min |
| `esr-av3x3` | realesrgan-ncnn-vulkan `realesr-animevideov3` | 3 | 0.88 | 1.07 | yes | 2.8 min |
| `waifu2x` | waifu2x-ncnn-vulkan cunet, noise 1 | 4 | 2.15 | 2.61 | yes | 6.9 min |
| `cugan3` | realcugan-ncnn-vulkan models-se, conservative | 3 | 7.93 | 9.61 (one process per file) | yes | 25 min |
| `ups-hdcube2` | upscayl-bin with 2xHDCube Compact ncnn, `-s 3` | 2 | 0.85 | 1.03 | yes | 2.7 min |
| `t-esr-x4plus` | spandrel ESRGAN `RealESRGAN_x4plus`, MPS | 4 | 6.84 | 8.29 | yes | 22 min |
| `t-esr-general` | spandrel RealESRGAN Compact `realesr-general-x4v3`, MPS | 4 | 0.47 | 0.57 | yes | 90 s |
| `t-hdcube4` | spandrel Compact `4xHDCube4Compact`, MPS | 4 | 0.28 | 0.34 | yes | 54 s |
| `t-hdcube2` | spandrel Compact `2xHDCube_Compact`, MPS | 2 | 0.23 | 0.28 | yes | 44 s |
| `t-pbrify-span` | spandrel SPAN `4x-PBRify_UpscalerSPANV4`, MPS | 4 | 0.42 | 0.51 | yes | 81 s |
| `t-pbrify-rplksr` | spandrel PLKSR `4x-PBRify_RPLKSRd_V3`, MPS | 4 | 2.95 | 3.57 | yes | 9.4 min |
| `t-esr-x4plus-cpu` | same, CPU | 4 | 75.2 | 91.1 | yes | 4.0 h |
| `t-esr-general-cpu` | same, CPU | 4 | 3.42 | 4.14 | yes | 11 min |
| `t-hdcube4-cpu` | same, CPU | 4 | 1.81 | 2.20 | yes | 5.8 min |
| `t-pbrify-span-cpu` | same, CPU | 4 | 2.71 | 3.29 | yes | 8.7 min |

**One 1024x1024 image** (a mosaic of the samples), to see the speed
without per-image overhead:

| Upscaler | Time |
|---|---|
| spandrel `4xHDCube4Compact`, MPS | 0.16 s |
| spandrel `4x-PBRify_UpscalerSPANV4`, MPS | 0.15 s |
| spandrel `RealESRGAN_x4plus`, MPS | 5.6 s |
| ncnn `realesr-animevideov3` x3 | 2.0 s |
| ncnn `realesrgan-x4plus` | 9.1 s |

Tiling at 256 changed nothing measurable on MPS.

**Determinism:**

- Every upscaler gave identical bytes on two runs on the same Mac.
- MPS against the CPU differs by at most 1 in 255 on a small fraction of
  texels, in all four models compared.
- So a GPU result is reproducible on the same host and setup, but not
  across hosts.

**Tool quirks:**

- **Real-CUGAN's macOS build** segfaults (rc 139) on some wide, thin
  inputs at every tile size:
  - 512x48, 512x64 and 528x64 crash;
  - 512x96 and 256x32 run.

  In directory mode the crash stops the batch. The harness runs it one
  file per process and pads inputs to at least 128 a side, then crops.
  The preset must do the same.
- **upscayl-bin** needs the model's input blob named `data`. Venomalia's
  2xHDCube Compact ncnn param names it `input`, so a renamed copy of the
  `.param` was needed.

### Platforms, tools and licences

| Tool | Licence | macOS arm64 | Windows | Linux / SteamOS | CPU fallback | Alpha |
|---|---|---|---|---|---|---|
| built-ins (`nearest`, `lanczos`, `xbr`, `epx`) | the CLI's | yes | yes | yes | they are CPU | RGBA |
| realesrgan-ncnn-vulkan 20220424 | MIT | yes (MoltenVK, verified) | yes | yes | `-g -1` (ncnn) | RGB (split) |
| waifu2x-ncnn-vulkan 20250915 | MIT | yes (verified) | yes | yes | `-g -1` | RGB (split) |
| realcugan-ncnn-vulkan 20220728 | MIT | yes, with the thin-image crash | yes | yes | `-g -1` | RGB (split) |
| upscayl-bin 20251207 | AGPL-3.0 (invoked, never linked) | yes (verified) | yes | yes | `-g -1` | RGB (split) |
| chaiNNer `run` | GPL-3.0 (invoked) | yes | yes | yes | per backend | per chain |
| spandrel 0.4.2 + PyTorch 2.15.0 | MIT / BSD-3 | MPS (verified) | CUDA (the PC; not run here) | CUDA / ROCm / CPU | CPU (measured above) | RGB (split); 4xHDcube-Alpha is an alpha-only model, not tried |

Handhelds do not build, so the Linux column is for owners only.

**Releases**, from the official GitHub releases, with their sha256:

| File | sha256 |
|---|---|
| `realesrgan-ncnn-vulkan-20220424-macos.zip` (Real-ESRGAN v0.2.5.0) | `e0ad05580abfeb25f8d8fb55aaf7bedf552c375b5b4d9bd3c8d59764d2cc333a` |
| `waifu2x-ncnn-vulkan-20250915-macos.zip` | `a5b58b239eb3aa030db5464f6759637fe412d8c07891a4346ea57f708b514d42` |
| `realcugan-ncnn-vulkan-20220728-macos.zip` | `0df908cbb98b480f85897221b96d37b0bdb70f82d81b2c7037fe950dd5c0fa33` |
| `upscayl-bin-20251207-174704-macos.zip` | `277419791281a56eae0c739c70120b974d7267cf7c2de8e86dc09798d4b314db` |

### Models

| Model | Source | Arch (spandrel) | Size | Licence | sha256 |
|---|---|---|---|---|---|
| `RealESRGAN_x4plus.pth` | xinntao/Real-ESRGAN release | ESRGAN | 67.0 MB | BSD-3 | `4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1` |
| `RealESRGAN_x4plus_anime_6B.pth` | xinntao/Real-ESRGAN release | ESRGAN | 17.9 MB | BSD-3 | `f872d837d3c90ed2e05227bed711af5671a6fd1c9f7d7e91c911a61f155e99da` |
| `realesr-general-x4v3.pth` | xinntao/Real-ESRGAN release | RealESRGAN Compact | 4.9 MB | BSD-3 | `8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292` |
| `realesr-animevideov3.pth` | xinntao/Real-ESRGAN release | RealESRGAN Compact | 2.5 MB | BSD-3 | `b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d` |
| `4x-PBRify_UpscalerSPANV4.pth` | Kim2091/PBRify_Remix | SPAN | 9.0 MB | CC0-1.0 | `d1f1fa1af7a5ab23fcf143e75aac4951e6c52d56bf77d9ccd4d004a4831d0461` |
| `4x-PBRify_RPLKSRd_V3.pth` | Kim2091/Kim2091-Models release | PLKSR | 29.7 MB | CC0-1.0 | `1325a08842ebfc18aea90e71594aa9b9e82b9c7e16321dccf5b757884a22daf1` |
| `4xHDCube4Compact.pth` | Venomalia/HDcube release 4.0 (`4xHDcube4Compact.zip` `7893007b…`) | RealESRGAN Compact | 5.0 MB | HDcube licence, **flagged** | `f841188a346581b0e851f6306b69d50da0f5ac668498bb46a32c7c1c03589e58` |
| `4xHDcube-Alpha.pth` | same zip | RealESRGAN Compact | 2.5 MB | HDcube licence, **flagged** | `1781430c1613a037aed1f4eb7493118bff030e0fd5a2bbff641d9bf23f990d88` |
| `2xHDCube_Compact.pth` | Venomalia/HDcube release | RealESRGAN Compact | 4.8 MB | HDcube licence, **flagged** | `67f296d868de757b4f3daca3e35f16b61ab1ae88703776727dab212004203e57` |
| `2xHDCube_Compact_fp32-ncnn.zip` | same release | ncnn | | HDcube licence, **flagged** | `9de4c0505d59b65888e58b111f3948b0ba1c91be27267f768377cc8b13929992` |
| ncnn and waifu2x/Real-CUGAN models | bundled with the tools | ncnn | | MIT (waifu2x; Real-CUGAN, whose `bilibili/ailab` `Real-CUGAN/LICENSE` is MIT and states no separate terms for the weights), BSD-3 (Real-ESRGAN) | in the release zips |

**Why HDcube is flagged.** Its repo licence (Venomalia, 2023) is custom:

- the output is unclaimed and use is allowed;
- renting, selling or redistributing the model is not.

OpenModelDB disagrees per version:

- `2x-HDCube-Compact`: CC-BY-4.0;
- `4x-HDCube`: CC0;
- `4x-HDCube2` and `4x-HDCube3`: CC-BY-NC-SA-4.0.

Packs are never distributed and the CLI never ships a model, so an owner
may use it, but the preset must show the flag.

**OpenModelDB** has 671 models. Licence counts:

| Licence | Models |
|---|---|
| CC-BY-NC-SA-4.0 | 227 |
| CC-BY-4.0 | 123 |
| WTFPL | 73 |
| CC-BY-NC-4.0 | 53 |
| Apache-2.0 | 51 |
| CC0 | 44 |
| GPL-3.0 | 27 |
| MIT | 22 |
| none | 27 |

- **Permissive game-texture models worth a preset:**
  - `1x-DEDXT` (WTFPL, removes DXT block artefacts before an upscale);
  - `4x-PBRify-UpscalerV4` (DAT, CC0, 140 MB);
  - `4x-Textures-GTAV-rgt-s` (CC-BY-4.0);
  - `4x-TextureDAT2-otf` (CC-BY-4.0);
  - `2x-AoMR-mosr` (CC-BY-4.0).
- **Non-commercial, flagged:**
  - `4x-UltraSharp` (CC-BY-NC-SA-4.0; MEGA only);
  - `2x-AniScale-2` (CC-BY-NC);
  - `2x-GameUpV2-TSCUNet` (CC-BY-NC-SA).
- `4x-PixelPerfectV4` (WTFPL) is on Google Drive only and was skipped.

## 4. Verdicts per class, from the 3x grids

The grids are `out/grid_<class>.png` in the local runs directory, with
`index.html` beside them. Each cell is the 64x64 source window with the
most detail, at 3x over a checkerboard.

| Class | Verdict | Default to ship | Best CNN choice |
|---|---|---|---|
| world | CNNs win here. HDCube4, realesr-general and PBRify RPLKSR add detail and keep the look. x4plus and x4plus-anime repaint: carved stone turns into new carvings, and the medal goes flat. waifu2x and xbr add little over lanczos. | `lanczos` (nothing to install, reproducible), 2x by default for size; a CNN at the render scale | `realesr-general-x4v3` (BSD-3; spandrel, 0.57 s/Mtexel on MPS) or `realesr-animevideov3` x3 (BSD-3; ncnn, native 3x, 1.07). `4xHDCube4Compact` looks best, but its licence is flagged. |
| ui | `xbr` 3x is clean, with no halos. CNNs over-sharpen, and `esr-x4plus` and `realesr-general` invent a grid from the DXT blocks of the semi-transparent panel (`equip_sboard_swe`). | `xbr` 3x | none needed. Real-CUGAN and HDCube are sharper on the icons if the owner wants it. |
| text | `xbr` keeps the strokes. CNNs add white halos inside the red lettering of `demo_font01_tom_us` (anime, cugan, realesr-general). | `xbr` (2x default kept for size; 3x where the budget allows) | none |
| font | Alpha decides it. CNNs give crisper alpha edges (x4plus, cugan3), but D2's atlas fit stays better for a named font. | atlas fit, else `xbr` | none |
| fx | Soft gradients. CNNs flatten the glow core (`t_b2_hit002` with HDCube4 and PBRify SPAN) and invent veins on the leaf (x4plus). | `lanczos` | none. A 1-bit cutout (DXT1 leaf) needs alpha `binary`. |

`4x-PBRify_UpscalerSPANV4` shifted the green medal texture towards a
lighter, noisier green. It is not recommended for colour-critical
diffuse.

## 5. The preview step (CLI first, then D9)

The spec's D9 GUI is a hardened local server for editing rules. A
builder first needs to answer one question: "which upscaler for each
class?". That fits a one-shot command that writes files:

```
xbr enhance textures compare [--class C ...] [--upscaler NAME ...]
    [--scale 3] [--samples 4] [--pick NAME ...] [--crop 64]
    [--repeat 2] [--out DIR]
```

- **Samples.** Per class, the game's `[enhance.textures] preview` picks
  first, then the busiest texture of each size band. Selection is
  deterministic by hash, so two runs compare the same texels. `--pick`
  adds named entries.
- **Upscalers.** Every one registered: built-ins, the presets found on
  PATH, and the local file's `command`, `http` and `torch` entries. It
  runs them through the same alpha, edge and down-to-scale code that
  `build` uses (3.3), so the preview is the pack's bytes.
- **Output** goes to `dist/enhance/compare/<stamp>/`:
  - `grid_<class>.png`: rows are samples, columns upscalers, cells the
    busiest crop over a checkerboard;
  - full-size outputs per upscaler;
  - a static `index.html` (no server, no script, no external resource);
  - `compare.json`: per upscaler, the identity (tool sha256, model
    sha256, licence and its flag), seconds per megatexel, and whether it
    is deterministic. `--repeat 2` adds the determinism check.

  The timings feed `build-logs/timings.json`, the calibration cache of
  D6.
- **Picking.** `xbr enhance textures pick CLASS UPSCALER [--scale S]`
  writes the class row of `enhance-textures.toml`, the same writer the
  GUI's Save uses.
- **Relation to D9.** The renderer, `compare.render(sample, upscaler,
  crop)`, is the function D9's Compare panel calls later. The CLI step
  ships in phase 3, without the server, so it needs none of D9's
  hardening. D9 adds the interactive crop, the wipe slider, the on-screen
  view (D15) and rule editing on top.
- **Privacy.** The grids hold game texels, so they live under `dist/`.
  `layout.py` already refuses a top-level `dist/` and every `.png`
  outside `docs/images/` (where only curated README screenshots go,
  checked for text chunks), so nothing new is needed.
- **Prototype.** `spike/grid.py` and `spike/mkgrid.py` show the shape:
  about 400 lines with numpy and Pillow. The real step uses the stdlib
  PNG module (3.1) and the registry.

## 6. The PyTorch backend (the user, 2026-11-01)

**Shape.** A separate optional package, `xbr-upscale-torch`, kept in the
CLI repo under `plugins/torch/` with its own `pyproject.toml`:

- It is never a dependency or an extra of the CLI. An extra would land
  in the per-tag `.venv`, which every re-pin replaces, and would pull in
  torch for every user: 0.7 GB on the Mac (this spike's venv is 708 MB),
  a few GB with CUDA wheels.
- The owner installs it once into user space with `uv tool install`.
  `xbr enhance textures backend install torch` only prints the line:
  - the package is not on PyPI, so the source is the CLI repository at
    the CLI's tag with `#subdirectory=plugins/torch`, or a local clone;
  - PyPI's torch is CPU-only on Windows, so a CUDA or ROCm host gets the
    PyTorch index for its platform;
  - `uv tool install` ignores the plugin's lockfile, so its
    `pyproject.toml` pins torch and spandrel exactly.
- The plugin outlives CLI re-pins, so it reports a contract version and
  the CLI refuses a different major.
- It is a **command backend** (D7.2) with a fixed CLI:
  `xbr-upscale-torch upscale --model PATH --scale S --in-dir --out-dir
  --device auto|mps|cuda|cpu --tile N --dtype fp32`.
- **The torch preset** in `presets.toml` registers it with
  `alpha = "rgb"` (split) and `batch = true`.
- **No torch import in the CLI.** The CLI's process never imports
  torch, so the stdlib-first default stays dependency-free.
- **No server of its own.** A Mac reaches the PC's CUDA through
  `xbr enhance serve --backend torch`, which keeps one plugin process in
  a stdio `worker` mode. The hardening of D7.3 then lives in one place.
  Start-up (about 1.3 s per cold process) is paid once per batch in a
  local build, and once per server with the worker; a process per
  request would cost about 2 h over a world pass.

**Models** are the owner's files:

- `--model` takes `.safetensors` (preferred), `.pth` or `.ckpt`, loaded
  only through `spandrel.ModelLoader`, never a raw `torch.load`. Its
  pickle path uses spandrel's `RestrictedUnpickle` (checked in 0.4.2),
  which refuses a forbidden global. Core architectures only:
  `spandrel_extra_arches` is never installed, because its licences
  include non-commercial ones.
- A model preset's expected sha256 is checked before loading; a
  mismatch is refused unless the owner overrides it.
- The plugin prints the architecture, the native scale and the sha256 of
  the model file.
- `presets.toml` names models with their homepage and licence. It never
  holds a URL that the tool fetches.

**Devices:**

| Device | Measured |
|---|---|
| MPS on the Mac | section 3 |
| CPU fallback | 6.5 to 7.3 times slower on the compact models, 11 times on ESRGAN x4plus |
| CUDA on the PC | not run in this spike |

`--device auto` picks CUDA, then MPS, then the CPU, and the record says
which.

**Determinism and the pack record:**

- Every torch model gave identical bytes run to run on MPS and on the
  CPU. MPS and the CPU differ by 1 LSB on a few texels.
- `textures-pack.toml` records per class:
  - `backend = "torch"`, `model_sha256`, `arch`, the native scale;
  - the torch and spandrel versions;
  - `device`, `dtype`, `tile`;
  - `reproducible = false`, since equal bytes are expected only on the
    same device, versions and tile.
- `--device cpu` with `torch.use_deterministic_algorithms(True)` adds
  `reproducible_scope = "host"`; `reproducible` stays a boolean.
- The goldens never load packs, so none of this touches the gates.

## 7. Why v2 can carry only unmipped world

The current runtime pack (v2) cannot show the world classes at 3x yet:

1. **The build path.** The CLI has none for world:
   - `enhance hud` globs the ui patterns only;
   - it skips mip chains and anything over the 64K-texel cap;
   - it has no BC1.
2. **What v2 can carry.** The runtime's lookup is by hash and aspect
   ratio, so a hand-made v2 pack can hold an *unmipped* world or fx
   texture as a kind-0 (`art`) entry. That is 2,522 of the 5,481 unique
   world hashes. A v2 3x ui-only pack works today.
3. **What v2 cannot carry.** Mipped world textures need D4's sampler LOD
   shift (task 1.2), fractional at 3x, or the chain is sampled at the
   wrong level.
4. **Taking frames needs a game build** with a hand-made pack, which
   was out of this spike's scope.

Section 8 has that A/B.

## 8. In-game A/B

`@stage1` on the PC (D3D11 native), render scale 3, `RECOMP_MENU=0`, one
run stock and one per pack, frames dumped from the render target
(1920x1440). The packs are hand-made v2: the 2,607 unmipped world (2,522)
and fx (85) hashes as kind-0 entries, raw BGRA (no BC, so no encoder
artefacts in the comparison), one level, at 3x, 3.15 GB each. They are
built with the 0.3 pipeline (pad 8, wrap for world, edge for fx; `lanczos`
premultiplied; the CNN with split alpha, 4x then Lanczos down to 3x;
`xbr` at 3x with the CLI's xBR scaler patched to accept 3x (its scale guard
is `(2, 4)` on main)). Mipped textures stay stock,
with no sampler shift (D4 is not in this run). Crops, contact sheets and full frames are
kept locally, never in the repo.

| Pack | Build (Mac, 2,607 textures, 87 M source texels) | Deterministic |
|---|---|---|
| `lanczos` | 4 s compute, 13 processes; 150 s with the stream to the PC | yes (same sha twice) |
| `xbr` 3x | 56 s compute, 13 processes; 200 s with the stream | yes |
| `realesr-general-x4v3` | 448 s on MPS (compute-bound; the stream overlaps) | not checked |

End to end, the CNN pack build ran about 5 s per source megatexel (448 s
over 87 M texels), against 0.57 s for the model call alone (section 3).
Padding, the alpha split, the down-scale and the stream make up the rest.

**In the frame.**
- Each pack run loaded all 2,607 entries.
- 105 entries were hit in the run, with about 81 MB resident.
- The misses are the mipped chains and render targets, as designed.
- Each run took 3,406 to 3,481 flips in 105 s each, 32 to 33 per
  second, with no
  change against stock and 0 presents mismatched.

What the pack reaches in `@stage1`:
- alpha-cut plants, grass, ferns and vines;
- the ground glyph decal (fx);
- props such as the boulder by the brick wall;
- the radar disc, which is classed world by name.

The large surfaces stay stock because they are mipped: the rock walls,
the dirt ground and the brick.

**Per upscaler.**
- `lanczos`:
  - Props come out a little sharper than stock and stay soft.
  - Premultiplied alpha leaves no halos.
  - Thin alpha-tested strands get thinner: one hanging vine almost
    disappears. This may come from premultiplied RGBA rather than from
    lanczos itself: the built-ins ran premultiplied, the CNN split alpha.
    This run does not separate the two.
  - Against `xbr`, it is cleaner and cheaper; the CNN is sharper.
- `realesr-general-x4v3`:
  - It gives the clearest gain. The boulder's surface is crisp and
    denoised instead of blotchy.
  - Vines and fern fronds keep their width and get clean edges.
  - No halos (colour extended under alpha, alpha upscaled apart).
  - The cost is about 110 times `lanczos` compute.
- `xbr`:
  - Props come out smoothed and posterised, with flat painterly patches
    on the boulder.
  - Thin strands keep their width but stair-step.
  - This is no better than `lanczos` for world art.
- No pack shows seams or tiling breaks. The decal is edge-padded, and the
  boulder wraps cleanly. The tiled floors and walls are mipped, so this
  pack does not test them.

**Mipped beside unmipped.** With no sampler shift, a mipped surface stays
at the guest's texels. An upscaled unmipped surface next to it gains
detail the mipped one lacks. In wide gameplay views the gap is hard to
see, because the mipped ground and walls are minified there. In close-ups
it is easy to see: the CNN-sharpened boulder and fern sit against the soft
stock rock wall and brick, so the mixed sharpness shows. A world pack
therefore wants the mipped chains too (D4, task 1.2) before the CNN's
sharpness pays off. On its own, an unmipped-only pack improves props and
foliage, and the difference is visible mainly up close.

### Native 4x and render scale 4

This checks whether the 4x-to-3x Lanczos step after `realesr-general-x4v3`
softens its gain. The same 2,607 hashes were packed at the model's native
4x with no down-to-scale step: 5.59 GB (the 3x pack is 3.15 GB), about
145 MB resident (81 MB for 3x), and 105 hits as before. Runs were on the
PC, D3D11, `@stage1`:
- render scale 3: stock, 3x and 4x;
- render scale 4: stock, a stock repeat, 3x and 4x.

**Native 4x against 4x-to-3x: no visible gain.** In the frames the two
match by eye. In the boulder, high-frequency energy (the Laplacian's
standard deviation) rises 1 to 3% from 3x to 4x at render scale 3 and
1 to 4% at render scale 4, where 3x itself rises 5 to 20% over stock at
render scale 3. The whole-frame mean absolute luma difference between 3x
and 4x is 0.41 8-bit levels at render scale 3 and 0.27 at render scale 4.
Two stock runs at render scale 4 differ by 0.13 levels. Inferred, not
measured (D14's trace will measure it): on-screen magnification stays
under about 3 pixels per source texel, so the GPU minifies the 4x entry.
The entries are single-level, so that minification aliases rather than
averages, and the extra texels add almost nothing.

**Render scale 4.** At render scale 4 the 4x pack still adds no visible
texture detail over 3x (1 to 4% detail energy). By eye, render scale 4
shows finer geometry edges and thinner grass stems than render scale 3,
the usual render-scale gain. The detail metric is per screen pixel, so it
gives no stock render scale 4 against 3 figure for texture detail.

Flips per second over a 105 s run:
- render scale 3: 32.4 for stock, 32.8 for 3x, 33.1 for 4x;
- render scale 4: 29.6 for stock, 29.2 for its repeat, 29.5 for 3x, 31.4
  for 4x.

The ±1.5 is the full range of all runs at one render scale (32.4 to 33.2
at render scale 3 with every pack, 29.2 to 31.4 at render scale 4), not a
measured noise model. The two stock runs at render scale 4 differ by 0.4.
The 4x pack's 31.4 at render scale 4 is noise, not a gain: the packs cost
no speed.

The 4x build took 926 s on MPS against 448 s for 3x. The two are not
comparable: other jobs loaded the Mac during the 4x build.
