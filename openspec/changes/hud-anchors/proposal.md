## Why

Under Hor+ the world fills the wide frame and the HUD stays in the 4:3 centre (enhancements-hor-plus H6). The user (2026-10-29) asked for the next level: move the game's own HUD elements to the edges of the wide frame through hooks, keep the owner-built HUD pack for sharpness, and make it work across games and ratios (16:10, 16:9, 21:9, and a HUD narrower than the world).

H6 dropped the old edges mode because the pushbuffer carries triangles, not elements: every guess at grouping split some element. A hook on the game's own code does not guess. It runs where the game still knows which element it is drawing.

Two research items feed this change:
- **The tracker item** (`notes/hud-hooks/assessment.md`) proposed the layer: anchor kinds, the offset rule from the pad, `display.hud_aspect` and `display.hud_margin`, and a mark carried to the render thread by pushbuffer position.
- **The tracker item** (`notes/hud-hooks/locate.md`) located BLiNX 2's HUD and changed the design:
  - BLiNX 2 adds every HUD sprite to a queue (`sub_00042190`, 249 callers, plus three thin helpers), and one routine draws the whole queue later. Element identity exists only when a sprite is added; at draw time every element has the same return address.
  - Sprite positions are centre-relative, in 640x480 units. Beyond ±320 means parked off-screen.
  - Anchors go per call site, not per function: `sub_0006B1F0` draws elements anchored left, centre and right.
  - Text needs a second level of caller: `sub_00048600` draws each string 5 times for the outline, through a helper.
  - The push pointer (`g_Device+0`, `0x2F1FC0`) is confirmed, but `nv2a_batch_info` carries no guest address.
  - There is no dialogue flag. `0xAE73B4` is the pause flag.

So the anchor is applied in guest memory, where the sprite is added, and the render thread needs no element identity at all. What it still needs is a way to let moved sprites into the pads without letting parked ones show there.

**Amended 2026-10-30.** The user settled the open questions and widened the scope:
- The HUD stays anchored while paused; no pause gate. "HUD width" leaves the menu; `display.hud_aspect` follows the display. After the review of this amendment the user approved the HUD mod defaulting on, an exception to default-off like the in-game menu: any wide aspect anchors the HUD, and the Mods page turns it off. The world markers are `world` rows, confirmed by the scenario run. BLiNX 1 and BLiNX 2 are the first targets; JSRF and Burnout 3 come later.
- 640x480 is BLiNX 2's canvas, not a rule. Each game describes its canvas, and the layer reads it at run time.
- Whole-screen layers that slide (BLiNX 2's loading bands) and the cinematic top and bottom bars must cover the wide frame: a `stretch` kind, and sprites that belong together need one transform (groups).
- Mapping a HUD took a spike for one game. A game-agnostic mapping flow in the CLI turns that into capture, propose, review, emit and check, so BLiNX 1 and every later title cost a review instead.

## What Changes

- **A game-agnostic HUD anchor service in the enhancements layer** (toolkit), used by a game's mod, acting only through one active flag (mod on, table registered, pad above 0):
  - **Game canvas.** The mod's table describes the canvas: size, origin (centre or top-left), y direction, the view it covers in the target, and where its size comes from at run time (fixed, guest memory read once per guest frame, or the target's own size), with the declared values as the fallback. The layer maps canvas units to guest pixels, then to the pad. Never a hardcoded 640x480.
  - **Element table as data.** A mod registers its game's table as TOML text embedded at build time (`config/hud.toml` in the game repo): the canvas, the 2D vertex layout, the wrappers, the groups and the sites. A site row maps a call site (the return address of the call that names the element) to an element and a group; the group carries the kind: `left`, `right`, `centre`, `proportional`, `world` or `stretch`.
  - **Call chain.** The table's wrappers (BLiNX 2's sprite helpers and its font routine) are hooked, and the layer keeps a small per-thread chain of call sites, so the sprite add sees the element's site through one or more wrappers.
  - **Per-element shift and clip in guest memory.** From a hook on the call that takes the vertices, the layer finds the element, shifts each primitive's x by its group's offset, clips axis-aligned primitives to the group's window (the target's 4:3 columns, moved by the offset), moves primitives wholly outside that window past the wide frame's edge, and restores the caller's vertices after the call. Every primitive of a group moves by the same amount, so elements keep their shape; a uniform scale of positions would split them apart.
  - **Stretch.** A `stretch` group is mapped by `cx + (x - cx) × W/w` about the target's centre, the map H5 applies to full-width batches, so a band that slides in stays consistent with its stretched rest position. A rule in the backends keeps H5 from stretching it again. The cinematic bars are a `stretch` group unless they stay within 8 guest pixels of the 4:3 columns, where H5 already covers them.
  - **Groups.** Sprites that belong together (the dialogue box, face, text and button; the top-left panel; a bar and its caps) share one transform; `proportional` takes one reference x per group.
  - **The offset rule.** `pad_hud = max(0, min(pad, pad_at(display.hud_aspect)) - display.hud_margin)`, from the target's Hor+ pad (H1). Left is `-pad_hud`, right `+pad_hud`, centre and world 0, proportional `cx / (w/2) * pad_hud`. Offsets are whole guest pixels.
  - **The clip lift.** While the active flag is set, `nv2a_aspect_box` lets centred 2D that is neither full width nor a near layer reach the target's edges on padded 4:3 targets of the canvas's target size, as it does for 3D. The mod's in-game clip replaces the backend's 4:3 scissor for what the game adds through the hooked call. One shared helper, so Metal and D3D11 agree.
  - **Keys:** `display.hud_aspect` (`RECOMP_DISPLAY_HUD_ASPECT`, default `display`: the configured aspect; a file key) and `display.hud_margin` (`RECOMP_DISPLAY_HUD_MARGIN`, guest pixels, default 0; also a live "HUD margin" menu item). Both are inert while the active flag is clear.
  - **Trace:** `RECOMP_TRACE=hud` lists each site with its element, group, kind and offset, unlisted sites whose sprites cross or lie outside the 4:3 window, primitives that cross it but cannot be clipped exactly, calls left unclipped (`[hud.skip]`), the canvas and the lift state.
  - **ctests** over synthetic sprites, canvases (including a top-left canvas in a smaller view, Burnout 3's shape) and boxes.
- **A HUD mapping framework**, game-agnostic:
  - toolkit: a DEBUG key `hud_capture` that records, at 4:3 and without changing anything, each sprite's call chain, bounding box in canvas units, texture hash, queue and guest frame as JSONL, with its own frame dump per captured guest frame; level 0 records at a game's D3D draw entries for a title located from scratch; `hud_capture_table` loads the table file itself, so locating a title needs no mod;
  - CLI: `<game> hud-map capture | propose | review | emit | check`, a developer command group beside `bench` and `public` (apart from the player's `enhance hud`), standard library only. `propose` groups sprites into elements by call site and chain and suggests kinds by position; `review` writes a static HTML contact sheet at 4:3 and at a wide ratio; `emit` writes and validates the game's `config/hud.toml`; `check` runs the per-ratio scenarios;
  - captures and sheets stay in `runs/` (or a gitignored `dist/`) and are never published. The CLI holds no game constants; `game.toml` only names the table and the scenarios.
- **BLiNX 2's `hud` mod** (cat), the first table built with the framework:
  - `game.toml` `[mods] hook_functions` gains the sprite add `sub_00042190`, its helpers `sub_000177F0`, `sub_000178C0`, `sub_00047A00`, and the font routine `sub_00048600`. `blinx2 analyze` then `blinx2 recomp` generate the slots.
  - `config/hud.toml`, emitted by the framework and checked against the tracker item's element table: the top-left panel and the radar left; the item counter and the TS label right; the time-control slots, the yellow arc, the round banner and the dialogue centre; the world markers `world`; the loading bands, the cinematic bars where they overhang the band, and the backdrops the review keeps, `stretch`.
  - `src/mods/hud.c`: a descriptor mod with an `XBOX_SET_ENABLE` setting that defaults on (the user, 2026-10-30). At 4:3 the pad is 0, the active flag is clear, each hooked call costs one branch, and `hud` is absent from `mods=`, so stock and the goldens are byte-identical.
  - No state gate: menus, the pause panel and movies are not in the table, so they keep the stock 4:3 layout and clip; the stage HUD stays anchored behind the pause panel.
  - Mission complete, which the tracker item could not reach, is located with the framework and added.
- **BLiNX 1's `hud` mod** (blinx), the first game the framework locates from scratch, once its Hor+ is finished (`hor-cull` tasks 4.1 and 4.2, the seam): a level-0 capture, the same copy, cull, argument and canvas checks, its table, its mod and its ratio check; with no BLiNX 1 goldens, its stock check is an A/B frame comparison on Metal and D3D11.
- **The wizard (later, per game).** Each game adds an aspect option (`display.aspect`) after its HUD ratio check. The mod is on by default, so the wizard writes nothing else and the CLI's manifest gains no field.
- **Not in this change:**
  - Moving menus, scaling single elements, or a separate HUD render target (assessment ranks 5 and 6).
  - A mark carried to the render thread. It is kept in the design as the route for a title that draws its HUD from vertex buffers it fills ahead of the draw, where a shift for the call's duration cannot work.
  - A pause gate.
  - The HUD pack import path (owner PNGs, dumps by hash): the tracker item.
  - JSRF and Burnout 3 tables and mods: later items, one per game, on this layer and framework.

## Capabilities

### Modified Capabilities

- `enhancements`:
  - the HUD anchor service (game canvas, TOML table, call chain, groups, per-element shift and clip, `stretch`, offset rule);
  - the clip lift for centred 2D while a HUD mod runs, with the already-wide rule;
  - the `display.hud_aspect` and `display.hud_margin` keys;
  - the `hud` trace and the `hud_capture` debug key;
  - the HUD mapping framework in the CLI;
  - BLiNX 2's and BLiNX 1's `hud` mods, on by default and active only at a wide aspect, with stock goldens unchanged;
  - Hor+ in a game's wizard anchoring its HUD.

## Impact

- **Depends on** mod-connectivity-layer tasks 4.1 (`needs`, so a missing hook slot refuses the mod), and 4.9 (the `mods=` token, with an addition: a mod may report an active state and is listed only while it is set, so `hud` appears only at a wide aspect), and tasks 5.1 to 5.4 and 5.6 (generated hook slots); 5.5 for the goldens' token. BLiNX 1 needs the same hook-slot work in its repo, through its CLI pin. It does not need:
  - 4.2 (the gate): the `hud` mod's switch is its descriptor's `XBOX_SET_ENABLE` setting, default on, and its active flag keeps stock unchanged;
  - 4.3 (`aspect()`/`pad()`): the layer calls `nv2a_host_pad` directly;
  - 4.4 (probes): no state gate; the canvas's memory source is a plain read in `xbox_mod_frame`;
  - 4.5 to 4.7 (pokes, `place`, `rt_dims`): the layer reads the target's guest size itself.
- **API version:** the toolkit's `mod.h` is at version 3. mod-connectivity-layer's services land as version 4; the HUD fields are version 5, or the same bump if both land in one merge.
- **First checks** (tasks 0.3 and 0.4, before each game's mod): whether the sprite add copies the vertices, whether anything culls sprites by x, where the vertex pointer and count live, and where the canvas size and origin live. A pointer kept until the drain stops that game's mod in favour of the mark route.
- **Toolkit** (`xboxrecomp`, a branch off `posix-host/portability`):
  - `src/enhance/mod.{h,c}`: the HUD fields of the mod API, appended after mod-connectivity-layer's;
  - a new `src/enhance/hud_anchor.{h,c}`: the canvas, the table parser over the existing TOML reader, the offset rule, the site lookup, groups, the call chain, the shift, clip and stretch, the active flag;
  - a `hud_capture` writer beside it;
  - `src/kernel/nv2a_backend_common.{h,c}` and `nv2a_aspect.c`: the lift helper, the bounded variant of `nv2a_aspect_full_tris` (the already-wide rule) and the `lift` input of `nv2a_aspect_box`; `src/d3d/nv2a_pb_metal.m` and `nv2a_pb_d3d11.c` call both with the same inputs;
  - `src/enhance/enhance.c`, `enhance_cfg.c`, `enhance_menu.c`: the two keys, their summary line and the "HUD margin" Display item, shown once a HUD mod registers a table;
  - `src/platform/recomp_env.h`: two CONFIG rows, the `hud` trace row and the `hud_capture` DEBUG rows (`hud_capture`, `hud_capture_at`, `hud_capture_table`);
  - `docs/runtime/config.md`: the keys, the service and the table schema;
  - ctests.
- **CLI** (`xboxrecomp-cli`): the `hud-map` command group in a `hudmap/` package (capture, propose, review, emit, check), the optional `[hud]` table in `game.toml` with its schema entry in `manifest.py` and a section in `docs/manifest.md`, pytest cases over synthetic captures. Then a CLI release and cat's `[cli]` pin, with `sh notes/build-all.sh`.
- **cat:**
  - `game.toml` `[mods] hook_functions` (five VAs) and `[hud]`, then `blinx2 analyze` and `blinx2 recomp`;
  - `config/hud.toml`, `src/mods/hud.c`, the mod table entry and the build step that embeds the table;
  - `packaging/config.default.toml`: `[display]` lists the two keys, `[mods]` lists `"hud.enabled" = true`;
  - `docs/env.md` rows for the two keys, the trace and the capture key, landing with the toolkit pin bump that brings them;
  - a `scripts/test_*` case checking the table against the analysis xrefs.
- **blinx (BLiNX 1):** the same set, after its Hor+ seam fix and its locate.
- **No change** to stock behaviour (4:3, where the mod is on but inactive), the goldens, H6 as the default, or any run with the mod off. Players who already set a wide aspect see the HUD move to the edges after the update; that is the intent, and the release notes point at the Mods page.
