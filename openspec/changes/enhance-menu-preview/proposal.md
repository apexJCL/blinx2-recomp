# Change: In-game enhancements menu and the upscale/font preview tool

## Why

The enhancements layer works (render scale, present options, pacing,
glow, the owner-made HUD pack with a PT Sans Narrow atlas; see
`assessment.md`), but every key is read once at startup and lives in a
TOML file the player edits blind. There is no way to see what a key does
without a restart, no way to see which textures a pack *missed* (the
Mission Objectives text, was found by eye), and no way to try an
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
    so the ~2,000 baked text images the tracker item uncovered fit (4:1 on disk and
    in VRAM; both backends upload BC3 natively); the reader accepts v1
    and v2, and each entry keeps its own size, so text can sit at 2x
    beside HUD art at 4x in one pack;
  - keys `textures.font`, `textures.text` (on/off, default on) and
    `menu.enabled` (default off), with the menu opened by the
    `menu.open` action (default `F10` and Guide + A, plus a per-game
    fallback chord; R3 and R10 of the design, 2026-10-22);
  - an **overlay** module in the kernel library (`nv2a_overlay.c`):
    vendored microui (MIT) builds each layer's UI, a converter turns it
    into one draw list of textured triangles, and each presenter draws
    that list with one small renderer (CAMetalLayer pass, D3D11 present,
    SDL3 renderer). Text uses vendored stb_truetype and an embedded OFL
    face (Atkinson Hyperlegible, the user, 2026-10-22). A CPU reference rasteriser of the same list
    backs the ctests. Nothing is drawn when every layer is hidden;
  - **mouse in the menu**: the capture is released while it is open, an
    overlay cursor is drawn (a toolkit default, or a per-game style),
    and hover, click, wheel and right-click work on every page. cat
    ships capture on click (`input.mouse_capture = "click"`, with Esc
    as a free key) and idle cursor hiding;
  - the **menu** in the enhancements layer (`enhance_menu.c`): pages,
    items, navigation driven from an input hook on
    `xbox_InputGetState()` (every host, every backend), game-supplied
    items through a small registration API, a pack page with hits and
    misses, and a comment-preserving TOML line patcher that saves to the
    file the layer read;
  - ctests: `overlay` (draw lists and the CPU reference raster),
    `input_actions`, `enhance_menu` (navigation, mouse, hook
    neutralising guest input, TOML patching), `tex_pack` v2 cases,
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
  It builds on the prototype (`fix/hud-pack-text`: CLI 4ef7cd4
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

## Revision 2026-10-21

The user asked for three more things on 2026-10-21: live switching where
possible, an overlay that shows more than the menu, and bindings for host
features (the free camera first) on chords and on the extra buttons of
the Deck and modern pads. The design adds R1 to R6:

- **R1, live-switch audit.** Every toolkit, game and mod key is
  classified as live, live with a flush, at a later game point, or
  restart only, with the mechanism and the blocker. Of 26 rows, 21
  switch without a restart after this change (13 live, 8 with a flush),
  up from 4 today. `camera.free_hud` applies at the next activation.
  `display.aspect` and the pack path become live in follow-ups.
  `present.surface` and `fps.mode` stay restart-only.
- **R2, the overlay.** It has three layers (menu, a stats strip, toasts)
  with one writer each. Presenters draw them after the frame and never
  into dumps, at the cost of one atomic load when nothing is shown.
- **R3, host actions.** cat bypasses `xbox_InputGetState`, so the seam
  is a title-glue filter (`xbox_enhance_pad_filter`). Both the
  toolkit's input path and cat's pad glue call it. Named actions (`menu.open`, `overlay.stats`,
  `camera.free.toggle`, ...) are bound in `[input.actions]` to keys,
  pad chords with a hold time, and host-only buttons (guide, misc1,
  paddles, touchpad). The rules mean a binding never steals a button the
  game sees. Mods register actions through mod API v2. On the Deck under
  Proton, Steam Input maps the back grips to keys.
- **R4, pages.** Mods (list, toggle, per-mod items), Stats, Controls
  (rebind any action) and Debug join Render, Pack and Game.
- **R5, phases.** Phase 3 splits into 3A actions, 3B overlay and stats,
  3C live switching (all three in parallel) and 3D menu. 5B moves the
  free camera onto actions after the tracker item. The merges go in the order
  3A, 3B, 3C, 3D, each with its own D3D11 golden on the Deck. About 11
  agent-days through phase 6.
- **R6, follow-ups** outside the change.

## Revision 2026-10-22

The user decided on 2026-10-22: a richer UI toolkit with a proper font,
the mouse in v1, Guide + A by default, no pause, SDL3 names (has
landed), and a Save states page. The design adds R7 to R10 and revises
R3 to R6:

- **R7, toolkit and font.** microui (MIT, about 1,500 lines) is picked
  over Nuklear (about 30k lines), Clay (a global context, layout only),
  Dear ImGui (C++) and LVGL (far too large). It has an explicit
  context, which fits the per-thread layer writers, and it emits a
  flat command stream. That stream becomes one draw list, drawn by one
  small renderer per backend and checked by ctests on a CPU raster of
  the same list. Text uses stb_truetype with an atlas baked off the poll
  thread, in an embedded OFL face, with Latin-1, Latin Extended-A and a
  few symbols.
- **R8, the look.** Theme tokens (colours, spacing, radius, font sizes
  at 1080 lines) are scaled by the output height and the player's
  `overlay.ui_scale`, never by `render.scale`. The design sets the
  layouts of the menu panel, the stats strip and the toasts. A game may
  set its own theme in `config.default.toml`.
- **R9, mouse and cursor.** Open releases the capture and relative mode,
  and close restores them. The OS cursor is hidden while the menu is
  open and on idle. An overlay cursor is drawn (arrow, dot, or an owner
  PNG that is never distributed). The window threads hand the menu an
  atomic snapshot. Mouse-look is suppressed only while the menu is open.
- **R10, Guide + A.** It is a modifier chord (R3 rule 7): Guide first,
  then A, with A masked from the game until it is released. The design
  has a per-host table of where Guide is seen, with F10 and a per-game
  chord as the fallbacks (Steam takes Guide on the Deck).
- **Save states page.** The UI half of `save-states` phase 5:
  list, rearrange, delete, export, import.
- **Phases.** 3B is rewritten. New phases are 3E (font and theme), 3F
  (mouse and cursor) and 3G (Save states). The total is about 17
  agent-days through phase 6, up from 11.5.

## Revision 2026-10-22, round 2

The review of `14f041d` (F1 to F13) and the user's answers the
same day:

- **Decided:** the Atkinson Hyperlegible face, committed under OFL
  with README licence rows and an audit allow-list for its TTFs; idle
  cursor hiding on by default; D3D11 live fullscreen in v1; Deck grips
  documented only; `guide+y` for the free camera; exports in
  `<save dir>/exports/<game>/` with an Open folder row; capture on
  click, with a new `input.mouse_free_keys` (Esc in cat's file).
- **Accepted for v1:** on D3D11 the cursor, F10 and clicks arrive at
  guest flips (F-9 and F-11 stay follow-ups; "OK for v1, fix later").
- **Fixed:** the flip tick makes its own host read; the mouse drops
  button edges across a close; the D3D11 overlay clears an uncopied
  back buffer; the SDL renderer uses premultiplied blending; every new
  key has its env and doc rows; the save-states change hands its menu
  half to 3G.
- **Estimate:** 3B is 4.25 days, 3A 2.5 and 3F 2. The total is about
  19 agent-days through phase 6 (19.5 with phase 9), up from 17.

## Backends, hosts and goldens

- Metal and D3D11 get the same live-apply hand-off and the same overlay
  draw list (one renderer each, R7), on the same branch, in the same
  commits. Metal is verified on
  the Mac; D3D11 under Proton on the Linux/Proton host when the orchestrator sends
  "go". The CPU rasteriser gets the SDL-renderer overlay for free (same
  presenter) but still ignores scale and pack, and says so on the
  menu's own line; its Win32 GDI window gets no overlay (recorded). On
  D3D11 the overlay and the cursor refresh at guest flips (accepted for
  v1 by the user, 2026-10-22; F-9 and F-11 are follow-ups).
- Goldens are unaffected: `menu.enabled` defaults to off in code, the
  golden configuration pins `RECOMP_ENHANCE_CONFIG=none`, and the
  harness fails a run whose log shows `menu.enabled=on` or
  `textures.font=off` unless `--allow-enhance` names it. Nothing in a
  backend or presenter runs for the overlay unless a panel is visible,
  and nothing runs for live-apply unless a request is pending.
- Hosts: macOS (Metal, CPU), Windows under Proton (D3D11, CPU), the Deck,
  and native Windows for the Guide check when the user boots it.

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
game follow the README rule (fresh, few, approved). The vendored
microui and stb files are MIT (stb dual-licensed with public domain) and
the embedded UI face, Atkinson Hyperlegible, is SIL OFL 1.1, each with
its licence file, a NOTICE entry and a row in the toolkit README's
License table. The face's TTFs are the only binaries the change adds;
the toolkit's public-round audit allow-lists that one directory. A cursor or theme asset cut from a game's textures is
owner-generated, kept in the owner's config directory, and never
committed, packaged or distributed.

## Non-goals

- A 60 fps mode, Hor+, or any new rendering enhancement: the menu
  exposes keys that exist.
- A general mod loader (Lua, code patches). The menu's pack page is
  shaped so a `mods/` list can be added later (design D11); the loader
  is its own change.
- Pausing the guest while the menu is open (D7; the user, 2026-10-22:
  no pause and no pause hook. Input is neutralised instead).
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
- Redoing the tracker item's MIX reader and `lng_us` patterns: they merge from
  `fix/hud-pack-text` first.
