# Change: In-game enhancements menu and the upscale/font preview tool

## Why

The enhancements layer works (render scale, present options, pacing,
glow, the owner-made HUD pack with a PT Sans Narrow atlas; see
`assessment.md`), but every key is read once at startup and lives in a
TOML file the player edits blind. There is no way to see what a key does
without a restart, no way to see which textures a pack *missed* (the
Mission Objectives text, BLX-71, was found by eye), and no way to try an
upscale filter or a font before spending a pack build and a game launch
on it. The user asked (2026-10-11) for two things:

1. an **in-game, toggleable menu**, ideally game-agnostic, that switches
   the enhancements live (texture pack, font swap, glow, render scale,
   present filter) and will later manage mods;
2. a **preview tool** that loads the owner's extracted assets, shows
   upscale filters side by side with their parameters, extracts the
   game's font atlas and renders custom text in a choice of open-source
   typefaces with tweakable size, weight, offsets, outline and shadow,
   and saves the choices as a config that `enhance hud` consumes.

## What changes

- **Toolkit** (`posix-host/portability`; upstream-neutral, off by
  default, meant for upstream later with the enhancements layer):
  - a live-apply path for the host options: `nv2a_host_opts_request()`
    queues a change the backend applies at its next flip (scale and
    pack changes flush the render-target and texture caches there);
    `nv2a_tex_pack` gains a disabled flag, a per-entry kind, a
    generation counter and a miss trace (`RECOMP_TRACE=tex_pack`);
  - pack format **v2**: the same layout with `flags` naming the entry's
    kind (`FONT`, `TEXT`; unflagged is art) and a **BC3 payload** flag,
    so the ~2,000 baked text images BLX-71 uncovered fit (4:1 on disk and
    in VRAM; both backends upload BC3 natively); the reader accepts v1
    and v2, and each entry keeps its own size, so text can sit at 2x
    beside HUD art at 4x in one pack;
  - keys `textures.font`, `textures.text` (on/off, default on) and
    `menu.enabled`, `menu.hotkey`, `menu.chord` (default off, `F10`,
    `BACK+START`);
  - an **overlay** module in the kernel library (`nv2a_overlay.c`): a
    CPU-rasterised RGBA panel with an embedded public-domain 8x8 font,
    blitted by the three presenters as one textured quad over the frame
    (SDL renderer, CAMetalLayer pass, D3D11 present); nothing is drawn
    when the panel is hidden;
  - the **menu** in the enhancements layer (`enhance_menu.c`): pages,
    items, navigation driven from an input hook on
    `xbox_InputGetState()` (every host, every backend), game-supplied
    items through a small registration API, a pack page with hits and
    misses, and a comment-preserving TOML line patcher that saves to the
    file the layer read;
  - ctests: `overlay` (raster to a buffer), `enhance_menu` (navigation,
    hook neutralising guest input, TOML patching), `tex_pack` v2 cases,
    `host_opts_live`.
- **CLI** (`xboxrecomp-cli`, public, game-agnostic): `xbr enhance preview`,
  a local web UI (stdlib `http.server` on 127.0.0.1, opened in the
  browser) over the existing `ipk`/`dds`/`scaler`/`font`/`atlas`
  modules: an asset picker, side-by-side filters with parameters (xBR
  lv1/lv2 with its thresholds, EPX/Scale2x, nearest, fixed-point
  Lanczos as the built-in deterministic set; an external-command filter
  with presets for local open-source upscalers such as Real-ESRGAN and
  waifu2x ncnn builds the owner installs, never downloaded or run by
  the CLI itself), a font mode (installed faces, three curated OFL
  faces, the owner's own file by drag-and-drop or picker, or a Google
  Fonts family fetched from the google/fonts repository with its
  licence file kept beside it; size, weight, offsets, outline, shadow
  and overhang tweaks and a live custom-text render through the real
  fit), a runtime-log import that marks
  uploads a pack missed, and **Save** to `enhance-hud.toml`.
  `xbr enhance hud --config FILE` (default `config/enhance-hud.toml`
  when present) consumes it, writes v2 packs with the kind flags, a
  per-kind scale (text 2x by default) and BC3 for text, selects the
  owner's language set, and records the config's sha in `hud-pack.toml`.
  It builds on the BLX-71 prototype (`fix/hud-pack-text`: CLI 4ef7cd4
  `enhance/xpr.py` MIX/XPR0 reader, cat 1e5128f `lng_us` patterns),
  which merges first and is not redone here. The golden check learns
  `textures.font`, `textures.text` (stock `on`) and `menu.enabled`
  (stock `off`).
- **Game** (`cat`): registers its items (`fx.glow`, `fx.glow_intensity`;
  `fps.mode` read-only) with the menu through the API, makes
  `glow_configure` live-safe, adds the `[menu]` and `textures.font`
  rows to `docs/env.md` and `config.default.toml` (menu on in the
  shipped default file, off in code), the `config/enhance-hud.toml`
  the preview tool writes (tracked: fonts and parameters only),
  `docs/packaging.md` and the README.

## Backends, hosts and goldens

- Metal and D3D11 get the same live-apply hand-off and the same overlay
  blit, on the same branch, in the same commits. Metal is verified on
  the Mac; D3D11 under Proton on the Linux/Proton host when the orchestrator sends
  "go". The CPU rasteriser gets the SDL-renderer overlay for free (same
  presenter) but still ignores scale and pack, and says so on the
  menu's own line; its Win32 GDI window gets no overlay (recorded).
- Goldens are unaffected: `menu.enabled` defaults to off in code, the
  golden configuration pins `RECOMP_ENHANCE_CONFIG=none`, and the
  harness fails a run whose log shows `menu.enabled=on` or
  `textures.font=off` unless `--allow-enhance` names it. Nothing in a
  backend or presenter runs for the overlay unless a panel is visible,
  and nothing runs for live-apply unless a request is pending.
- Hosts: macOS (Metal, CPU), Windows under Proton (D3D11, CPU), the Deck.

## Legal

Packs, decoded textures, atlas crops and frames never enter a
repository; the preview tool renders them in a browser on
`127.0.0.1` from the owner's own dump and writes nothing but
`enhance-hud.toml` (filter names, parameters, font names, URLs and
sha256s: no game bytes). Downloaded fonts go to a per-user cache, never
the tree, each with its licence file (OFL, Apache 2.0 or UFL from the
google/fonts repository's own directories); an owner's uploaded font
stays in that cache under the owner's responsibility. The CLI never
calls a network service that can incur a cost and ships no model; an
external upscaler is the owner's own program, local open-source ones
offered as presets, a remote or paid one the owner's own command and
responsibility (the user, 2026-10-11). Screenshots of the menu over the
game follow the README rule (fresh, few, approved).

## Non-goals

- A 60 fps mode, Hor+, or any new rendering enhancement: the menu
  exposes keys that exist.
- A general mod loader (Lua, code patches). The menu's pack page is
  shaped so a `mods/` list can be added later (design D11); the loader
  is its own change.
- Pausing the guest while the menu is open (D7: input is neutralised
  instead; a game may hook `on_open` to pause itself).
- A native GUI for the preview tool, or any CNN scaler shipped in the
  CLI (the external-command filter runs the user's own tool).
- The `config.toml` / `config.default.toml` rename itself (design P1):
  decided here, written as its own change and landed before the menu
  (phase 2), so Save is built against `config.toml` from the start.
- Re-rendering baked text in the chosen face is assessed (design D16)
  and phased late behind a spike; it is not part of the first merges.
- World textures and mip chains in packs (as before). BC3 is in scope
  only as the pack payload for text; the guest's own textures still
  decode to BGRA8.
- Redoing BLX-71's MIX reader and `lng_us` patterns: they merge from
  `fix/hud-pack-text` first.
