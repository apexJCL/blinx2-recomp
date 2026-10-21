# Change: Game-agnostic texture upscaling in xboxrecomp-cli (whole-game packs, pluggable upscalers, a preview GUI, the wizard)

## Why

The HUD pack works: `xbr enhance hud` upscales a game's UI set with one
integer xBR kernel, re-renders the font atlas, and the runtime swaps each
texture by hash on Metal and D3D11 (`hud-pack`, `enhancements`). Three
limits were set when it was built, and all three were about size, not
correctness (`497d363`): the set is the `[enhance.hud] textures` globs
only, textures over `max_texels = 65536` are skipped (a 1024x512
background is 32 MB as RGBA8 at 4x), and textures with mip chains are
skipped. The scaler is one kernel with fixed constants, chosen for flat
UI art; it is wrong for photographic and 3D surfaces, and there is no
way to try another without a pack build and a game launch.

The user asked (2026-10-18) for a texture upscaling feature of the CLI
that is game-agnostic, user-configurable and pluggable into the build
wizard, with a GUI to pick from supported upscalers, register an
upscaler service of one's own, set the parameters and the coverage, and
preview the result for fine tuning. The same day the target was widened
to **every texture in the game**, so world assets render better too:
the HUD-only globs, the texel cap and the no-mips rule are things this
design lifts.

This change supersedes the tracker item (the parked full texture pack: it covers
that item's inventory, mip chains, DXT re-encoding, per-class scalers,
VRAM, opt-in surface and privacy) and absorbs the upscale half of
`enhance-menu-preview` (design D12-D15, tasks phase 7), whose font half
(phase 8) stays there and builds on the page this change puts up.

## What changes

- **Toolkit** (`posix-host/portability`, off by default, both GPU
  backends in the same commits):
  - pack format **v3**: a fourth entry kind `WORLD` (kind 3, refused by
    v2), a `XRTP_FLAG_BC1` payload flag beside BC3, and a header
    `classes` word; the reader takes v1, v2 and v3; BC1 uploads as
    `DXGI_FORMAT_BC1_UNORM` / `MTLPixelFormatBC1_RGBA`; entries with
    chains already load, but both samplers must follow the entry's
    chain: for a pack entry `lod_max` is shifted by `log2(entry width /
    guest width)`, `lod_min` stays 0 unless the guest set it above 0
    (then it shifts too), and a one-level guest with a pack chain gets
    mip filtering with min 0 and max at the shift, so the upscaled
    levels are sampled at magnification and the far end is no worse
    than stock;
  - a key `textures.world = on|off` (default `on`), the fourth switch
    beside `textures.font` and `textures.text`, read with or without a
    pack and live from the menu like them;
  - a **texture dump**, the debug entry `RECOMP_DEBUG=tex_dump=<dir>`
    (like `fb_dump`; no config key, no variable of its own): each first upload of a guest texture is written once
    as its decoded levels plus a sidecar with the hash, size, format,
    pitch, level count, the sampler's wrap and filter modes and a use
    count; stages that alias a render target and addresses whose hash
    keeps changing are left out and counted. This is the
    Dolphin/PCSX2 "dump then replace by hash" convention, and it is what
    makes the feature game-agnostic: no archive reader is needed to
    reach every texture the game draws;
  - a **magnification trace**, `RECOMP_TRACE=tex_mag`: per texture hash,
    the most screen pixels per texel seen in a run at its render scale
    (from the LOD the fragment shader computes on a subsample of pixels;
    exact from the vertices for 2D batches), because an upscale only
    helps where a texel is magnified, and at stock 640x480 a HUD piece
    drawn 1:1 or a distant wall gains nothing;
  - pack texels are released from host memory once the GPU texture is
    created (today they are kept for the process; a whole-game pack
    would be resident twice), and the pack log line gains the world
    count and the version.
- **CLI** (`xboxrecomp-cli`, public, game-agnostic, stdlib-first):
  - `xbr enhance textures inventory | estimate | build` over an
    **inventory** fed by two sources joined on the texel hash: the
    game's archives (the readers the CLI has, loose `.dds`/`.xpr`
    files, and a reader hook a game repo supplies) and the runtime dump.
    Every entry gets a **class** (`font`, `text`, `ui`, `world`) from
    `game.toml` patterns and from facts the dump and the format give,
    and the exact-size facts each with its rule: render targets and
    `volatile` (CPU-written, movie) textures are never packable;
    `linear` (rect) textures are skipped by default though the shader
    normalises their coordinates by the guest size, so a rule may include
    one; `palette` (P8) entries are packable from the dump, one per
    palette variant; `data` (ramps, lookups) and `normal` (bump/env
    maps) are skipped unless opted in with renormalisation; `grid`
    atlases are upscaled cell by cell. Coverage runs from the game's
    presets (HUD-only to everything) to **`traced`**, where the trace
    proposes skip, 2x or 4x per texture for the render scale the owner
    plays at and the owner tunes the table;
  - a **pluggable upscaler interface**: built-in deterministic integer
    filters (`nearest`, `xbr` 2/3/4 with parameters, `epx`, `lanczos`,
    `box`), a **command** backend (a template over PNG files in a
    temporary directory, per texture or per batch, with presets for
    local open-source tools the owner installs: Real-ESRGAN
    ncnn-vulkan, waifu2x ncnn-vulkan, Upscayl's CLI, chaiNNer's `run`),
    and an **HTTP service** backend with a small documented contract
    (hardened: allowlisted model and scale, size caps, no bearer token
    over plain http off loopback) plus adapters for the AUTOMATIC1111
    and ComfyUI APIs; a Python/PyTorch backend is recorded as a later
    option (the user, 2026-10-18: command and service only). Alpha is
    split from colour before a model
    sees it, texture edges are padded by the sampler's wrap mode the
    dump recorded, mip chains are regenerated from the upscaled base,
    and the result is re-encoded raw, BC1 or BC3 per class;
  - the config `config/enhance-textures.toml` (tracked: coverage preset,
    per-class and per-rule scale, upscaler, parameters, alpha, edges,
    mips, encode, size limits, budgets, the `[font]` table of
    enhance-menu-preview D13 unchanged) with an untracked
    `enhance-textures.local.toml` for the owner's program paths and
    service URLs, both consumed by `build` and written by the GUI; the build
    is reproducible when every upscaler is built-in, and says so in
    `textures-pack.toml` otherwise;
  - `xbr enhance hud` stays as the `hud` coverage preset of `build`;
    `package --texture-pack [DIR]` stages the pack and `--texture-preset
    NAME` builds it, with `--keep-texture-pack` and `--clear-texture-pack`
    beside them; `--hud-pack` and its keep and clear flags stay as they
    are for the HUD-only pack (`hud.pack`), and a bundle carries one
    pack, so the two are refused together;
  - the GUI: the planned **`xbr enhance preview` local web UI** (a
    stdlib `http.server` on `127.0.0.1`, no external resource, a
    per-session token on every route, Host and Origin checks, JSON-only
    POSTs) gets its Textures page here: the upscaler list with found/not-found and
    licence per preset, service registration (URL, test, capabilities),
    parameters, coverage presets and per-class/per-rule rules, a
    side-by-side **and** a slider (wipe) comparison on crops of real
    textures from the dump or the archives, an **on-screen view** that
    shows the result at the footprint it has at the chosen render scale
    (through the recorded filter and mip level, beside the stock
    texture's own) rather than only zoomed in isolation, a per-upscaler
    time per texture, the pack size, VRAM and build-time estimates per
    preset,
    the runtime-log import of misses, and Save. The font page of
    enhance-menu-preview phase 8 joins the same server later.
- **Wizard** (Go/Fyne, a front end over the CLI): a `choice` option may
  carry `flag` (`--texture-preset`), so a game offers its coverage
  presets as radio buttons with the estimate of each from
  `package --plan --json`; a `Configure…` button, enabled once Checks
  passed and the dump is known, runs `<game> enhance preview` in the
  clone and opens the URL it prints; the saved config in the clone's
  `config/` is what the build reads. No upscaler runs in the wizard
  process and nothing new is linked.
- **Games** (`cat`, then `b3`): `game.toml [enhance.textures]` (sources,
  class patterns, excludes, presets, preview picks), the env rows, the
  `config.default.toml` comment, docs; the owner's whole-game pack built
  and checked on Metal and under Proton.

## Backends, hosts and goldens

- Metal and D3D11 get v3, BC1, the world switch and the dump in the same
  commits; the CPU rasteriser ignores the pack and the dump with its one
  line each.
- Goldens are unaffected: every new key defaults to stock
  (`textures.world=on` is stock with no pack; `RECOMP_DEBUG=tex_dump` and
  `RECOMP_TRACE=tex_mag` never change a frame), the golden configuration pins
  `RECOMP_CONFIG=none`, and the harness fails a run whose log shows a
  pack or `textures.world=off` without `--allow-enhance`.
- Upscalers run where the pack is built: the Mac (built-in filters on
  the CPU; ncnn tools through MoltenVK), a Windows or Linux PC (a Vulkan
  GPU, or whatever the owner's installed tool uses, with the tools' CPU
  fallbacks), or a service on another machine. The Deck installs packs
  and never builds them.

## Legal

Packs, dumps, inventories with texels, decoded textures and frames never
enter a repository: `*.pack`, `enhance/` and the dump directory are
gitignored, the audit flags them, and the inventory file the CLI keeps
holds names, hashes, sizes and classes only. The CLI ships no model
weights and downloads none; a command preset is a template the owner's
own installed program fills, with the tool's licence shown beside it; a
service is the owner's own URL, and the owner's program paths and
service URLs live in an untracked local file. Every pack is
owner-generated, for the owner's own build, and the docs say so where
the command is described.

## Non-goals

- Shipping, vendoring or downloading any CNN or model (the 2026-10-11
  rule: nothing bundled or default may call a service that can cost
  money; open-source local tools first; a paid service is the owner's
  own command).
- Mesh, model or level replacement, or a mod loader: textures only
  (textures plus the free camera are the modding scope).
- A native GUI, or a second pipeline in the wizard.
- Re-rendering baked text (enhance-menu-preview D16, phase 10) and the
  font page (phase 8): they stay in that change.
- Changing how the runtime keys textures (the hash, the aspect check,
  the cache) or sampling linear (rect) textures from a pack.
- BC7 or ASTC payloads (a follow-up once an encoder worth its cost
  exists; recorded in design).
