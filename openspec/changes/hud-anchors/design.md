## Context

- **Sources.**
  - `notes/hud-hooks/assessment.md`: the idea assessment. It proposed a mark that a guest hook sets per element and that reaches the render thread keyed by pushbuffer position, with the backends shifting each marked batch and its scissor.
  - `notes/hud-hooks/locate.md` (cat `spike/hud-locate` adc8034): BLiNX 2's element table, D3D entries and probes. Where it differs from the assessment, it wins.
  - The tracker comments.
  - The user's answers of 2026-10-30 and the new scope: the pause, `display.hud_aspect`, the wizard, the world markers, the cinematic black bars, BLiNX 1 and BLiNX 2 as the first targets, the game canvas, the `stretch` kind, groups and the HUD mapping framework. The same day the user approved the HUD mod defaulting on, as an exception to default-off (A16).
  - The review of the amendment (2026-10-30).
  - Code read at toolkit `posix-host/portability` 878012fc, cat `main` e26ce6d, BLiNX 1 (`blinx/`) `main` 0da7372 and xboxrecomp-cli `main` 5ae107c.
- **What exists.**
  - Hor+ (enhancements-hor-plus): `nv2a_host_pad` (H1), `nv2a_aspect_map` (H2), the 2D scan (H3), full width per triangle (H4), `nv2a_aspect_place` and `nv2a_aspect_box` (H5). H6 keeps every 2D batch that is not full width centred and scissored to the guest's 4:3 columns, so parked pieces never show in the pads.
  - The mod API in `src/enhance/mod.h` is at version 3 (mod-settings: actions, menu items, descriptors). mod-connectivity-layer's "v2" services (`aspect`, `state_probe`, `poke`, `hook`, `place`, `rt_dims`, the `needs` mask) are specified but not built (its tasks 4 and 5). The version numbers diverged. hud-anchors amended mod-connectivity-layer task 4.1 (cat 771d62e) to land its services as version 4; this change's fields come after them as version 5. If both land in one toolkit merge, they share one bump to 4.
  - Today's gate: `mods."<id>"` (bool, default true) leaves a mod out at start, and a descriptor's `XBOX_SET_ENABLE` setting is the mod's switch. With the menu on, a mod whose switch is off still runs its init as *dormant*, so the menu can switch it on live (`on_enable`).
  - The texture pack swaps by texel hash at upload, wherever the texture is drawn (`docs/formats/texture-pack.md`).
  - `pb_merge` is off under `display.aspect` (cat `docs/env.md`), so every guest batch is its own backend draw under Hor+.
  - The CLI already has `<game> enhance hud`, the player command that builds the HUD texture pack from the dump. It has nested verbs (`wizard`, `public`, `bench`), is standard library only at run time, and its wizard writes each `[[wizard.option]]` as one `config` key or one `package` flag.
  - Neither BLiNX game's wizard offers Hor+ today: cat's options are render scale, fullscreen and the HUD pack; BLiNX 1's are render scale and fullscreen. BLiNX 1's `config.default.toml` notes that wider ratios are untested there. Its `hor-cull` change (side planes widened to `display.aspect`) is on blinx `main` (769b8b5); its tasks 4.1 (that note) and 4.2 (a faint seam at the old 4:3 edges) are open. BLiNX 1 has no golden suite (`golden.json`) yet.
- **What the tracker item found in BLiNX 2.**
  - Nearly all 2D goes through a sprite queue. `sub_00042190` adds a sprite (cdecl; the vertices are 16 bytes each, x, y, u, v as floats; records are 0x34 bytes; queue 0's write pointer is `[0xA043DC]`). `sub_00035140` draws queue 0 later, so every element has the same D3D return address at draw time.
  - Three thin helpers call the add for most callers: `sub_000177F0` (747 callers), `sub_000178C0` (466), `sub_00047A00` (394). The element is the helper's caller.
  - The font routine `sub_00048600` draws a string as 5 offset passes (the outline) through `sub_00047A00`. The element is the font routine's caller, two wrappers above the add.
  - Coordinates are centre-relative in 640x480 units (screen x = x + 320). Values beyond ±320 are parked sprites, slid off-screen.
  - `sub_0006B1F0` draws the lives dots, Time, the gauge bracket, the yellow arc, the TS label and "/ 5": left, centre and right elements from one function.
  - Non-queue 2D: full-screen fades (`sub_00042380`), the movie and stills quad (`sub_0015B470`), and the glow passes. All are full width, so H5 stretches them or applies `display.movie`.
  - The cinematic black bars (top and bottom, in cutscenes) are not in the tracker item's table. The Hor+ analysis (`analysis/enhancements/hor-plus.md`) lists "letterbox bars in cutscenes" among the full-width untextured batches H5 stretches; their call site is not located. The cutscene dim (`sub_000550C0`, `0x55210`) is the nearest candidate.
  - The `S` rows of the element table: the loading bands in `sub_0005EB30` (49 sites, parked at ±1280), the cutscene dim (`0x55210`), the fades, the pause backdrops (`0x171CA2`, `0x171D08`, `0x171FAF`) and the title backdrop (`0x1845C`). The full-width zero-height quads of `sub_00216D70` (`0x21703A`) are drawn every frame and must never move.
  - No dialogue flag exists. `0xAE73B4` is the pause flag. `0x449F40` means "not paused".

## Goals / Non-Goals

**Goals:**
- A mod can move each HUD element to an anchor (left edge, right edge, centre, proportional) or stretch it over the wide frame, at any wide ratio, with the kind named per element and the element named by call site.
- Coordinates come from a game canvas the mod describes and the layer reads at run time, never from a hardcoded 640x480.
- Sprites that belong together share one transform (groups).
- The layer part is game-agnostic. A game supplies data: hook VAs, its canvas, its 2D vertex layout and an element table.
- Mapping a game's HUD is a repeatable, game-agnostic flow in the CLI (capture, propose, review, emit, check), so each new title costs a review, not a reverse-engineering spike.
- BLiNX 2 and BLiNX 1 are the first targets. BLiNX 2's table is the first one the framework builds; BLiNX 1 is the first game the framework locates from scratch.
- Elements moved into the pads show there; parked pieces stay hidden; menus, dialogue and movies keep their stock 4:3 layout unless their rows say otherwise.
- The owner-built HUD pack keeps working on moved elements.
- The HUD mod is on by default (the user, 2026-10-30), but stock is unchanged: at 4:3, under `mods=none` and with the mod switched off, nothing moves and the goldens stay byte-identical. H6 stays what a game without a HUD mod shows.
- The cinematic black bars cover the wide frame, with no bare pads and no double stretch.
- Small: no walker change, no new backend state per batch, both backends through one shared helper.

**Non-Goals:**
- Moving menus or scaling elements. Scaling needs a separate HUD render target (assessment rank 5). The `stretch` kind scales whole-screen layers by the frame's own map, which H5 already does for full-width batches; it is not a per-element scale.
- Redrawing the HUD in the overlay (assessment rank 6).
- A mark carried to the render thread in this change (A1 keeps it as the route for a later title).
- The HUD pack import path for owner-made images and dumps by hash.
- JSRF and Burnout 3 element tables (A8). Burnout 3 shapes the canvas design (A11) as its stress case.
- A pause gate (A4).

## Decisions

### A1. The anchor is applied where the game hands over its vertices

The hook on the call that takes the element's vertices shifts their x in guest memory by the anchor's offset. For BLiNX 2 that call is the sprite add, `sub_00042190`. The layer then draws them where the game would have, plus the offset; the render thread needs no element identity.

- **Why here.** The tracker item showed element identity exists only at the add. At draw time the queue's drain has one return address for every element. A shift at the add costs a table lookup and a few float adds per sprite, on the guest thread, and changes nothing in the walker or the backends.
- **The shift must land on data drawn this frame, never on game state.** What the call does with the vertices decides the case:
  - **It copies them during the call** (into the queue's vertex pool, or into the pushbuffer as `DrawVerticesUP` and RenderWare's `RwIm2D*` do). The pre callback shifts the caller's vertices, the body copies the shifted ones, and the post callback restores the caller's. The caller's buffer, which the game may keep across frames, is unchanged when the call returns. This is the only case this change builds.
  - **It keeps the pointer until the drain** and reads the caller's vertices there. A restore at post would undo the shift before the draw, and no restore would let it accumulate across frames. This change stops: the game needs the mark route below.
  - **It neither copies nor keeps them** in a form the hook can see (the add builds the draw some other way). This change stops too, and the inventory is redone.
  - BLiNX 2 is checked first, before any toolkit work (tasks 0.3). A copy is likely: the tracker item found the vertices on the helpers' stack frames, which are gone by the drain, and the drain draws `DrawVertices(6, start, 4)` from a pool, so the add must copy into that pool. The 0x34-byte record is too small to hold four 16-byte vertices, which fits a record that points into the pool. BLiNX 1 gets the same check once its sprite path is found (tasks 0.4).
- **Two more facts from the same check** (tasks 0.3):
  - **A cull by x.** If the add or either drain (`sub_00035140` for queue 0, `sub_000348A0` for queue 1) drops sprites whose x lies past ±320 as parked, moved elements vanish: at 21:9 the radar lands at -526..-394 and the top-left panel at -512..-364. A cull at the add runs on the shifted vertices and has to be handled by shifting after it (a post-call shift of the pool copy) or ruled out; a cull in a drain needs its bound patched by a hook or a poke.
  - **Where the arguments live.** `hud_apply` needs the vertex pointer and the count. The tracker item reads ecx as the vertex pointer and n on the stack; `xbox_mod_call` gives `ecx` and `esp` at entry, but no entry `eax` (its `eax` is the return value). The sprite id in eax is not needed. If either argument turns out to be in eax, the hook slot needs an entry-eax field first.
- **Generic shape for a title that draws directly** (JSRF's `Draw*` calls if it uses them, Burnout 3's `RwIm2DRenderPrimitive`): the hook is on the draw call, which copies the vertices into the pushbuffer during the call. Same pre-shift, post-restore. The element is the draw call's caller, or a wrapper's caller (A5).
- **What it cannot do.** A title that draws its HUD from a vertex buffer it filled ahead of the call (`DrawVertices` over a static buffer) gives the GPU a pointer that the walker reads up to a frame later. A shift restored at post would race the walker, and an unrestored shift accumulates. Such a title needs the mark below.

*Alternative: a mark carried to the render thread* (assessment section 3.3(a)). The hook pushes `{start, end, anchor}` keyed by the push pointer (`g_Device+0`), the walker compares each batch's guest address against the ring, and the backends shift the batch through `nv2a_aspect_map` and `nv2a_aspect_box`. Not built now:
- for BLiNX 2 the mark would have to be set at the drain, per queue record, from a side table keyed by record address, since the add runs long before the draw;
- `nv2a_batch_info` has no guest address, so the walker must first record the push range per batch on both backends;
- a desynchronised mark shifts or clips the wrong batch, and the failure is a HUD element that vanishes or jumps for a frame.
It stays the documented route for the static-buffer case, sized M in the assessment, and would use the same table and offset rule. Nothing in this change blocks it.

*Alternative: pokes on a layout table* (assessment rank 2). The tracker item found no layout table in BLiNX 2; positions are computed per call. Not applicable.

### A2. The scissor: lift the backend's 4:3 clip and clip in the game

H5 scissors centred 2D to the guest's 4:3 columns, so an element shifted into the pads would be cut off. The scissor has to let moved sprites through and keep parked ones hidden.

**Chosen: lift the clip while a HUD mod runs, and clip in guest memory at the add.**
- **Layer, render thread.** `nv2a_aspect_box` gains a `lift` input. With `lift` set, a batch placed CENTRE, 2D and not full width, on a padded 4:3 target, gets the same box as centred 3D: an edge of the guest clip box at 0 or at w is pushed out to the target's edge. A narrower clip the game set itself keeps its edges. Squares, STRETCH and COVER are unchanged. Full-width batches keep their box, so a movie or still under `display.movie = black` keeps its pillarbox.
- **`lift` is set** while the layer's active flag is set by a mod (A10: the mod on, its table registered, the pad above 0). It is one relaxed atomic read per 2D batch. It is 0 under `mods=none`, with the mod off, at 4:3, before any table is registered, and during a capture alone (A15).
- **Who gets the lift.** `nv2a_aspect_box(place, two_d)` cannot tell a full-width batch or a near layer from other 2D today, and Metal passes `two_d || flat`. So the backends do not pass the lift flag raw: one shared helper, `nv2a_aspect_hud_lift(rt_w, rt_h, two_d, flat, full_w, x_lo, x_hi)`, returns the effective lift, and `nv2a_aspect_box` gains a `lift` input fed from it. Metal (`nv2a_pb_metal.m`, the `nv2a_aspect_box` call near line 2450) and D3D11 (`nv2a_pb_d3d11.c`, near line 3422) call it with the same inputs: `two_d` from the 2D scan, `flat` from `nv2a_aspect_flat`, `full_w` as both backends compute it for the placement (below), and `x_lo`, `x_hi` from the batch's guest x bounds, which H4's fallback already has. The x range is used only by the lift decision: a batch wholly inside `[0, w]` needs no lift and keeps its H5 box, so its trace line reads as at H6. The lift is set only when:
  - the batch is 2D (pretransformed), not a near layer (`flat` is never lifted: that is the rule that keeps Burnout 3's front-end menus, drawn at rhw 10, out of the pads);
  - the batch is not full width, so fades, backings and movies keep their H5 box;
  - the target's guest size equals the canvas's target (A11; 640x480 for BLiNX 2), so 2D drawn into squares and other targets keeps its clip.
- **Already wide (added 2026-10-30, for `stretch`, A13).** Full width is decided per triangle today: `full_w` is the batch's `nv2a_aspect_full_width` test AND `nv2a_aspect_full_tris` (`src/kernel/nv2a_aspect.c`), which is true when any one triangle spans `[2, w - 2]`. The rule lives in a bounded variant of `nv2a_aspect_full_tris`, used by both backends for the placement while the layer's active flag is set on the canvas's target: a triangle counts only if it spans `[2, w - 2]` **and** lies within `[-8, w + 8]` guest pixels. The layer's stretch map puts its sprites past that band on purpose, so H5 never stretches them a second time; they are CENTRE, lifted, and drawn where the layer put them. A batch that mixes a fade triangle at 0..w with a piece outside the band stays full width through the fade triangle, as it does today. With the flag clear the unbounded test runs, unchanged.
- **Game side, at the add.** For each primitive (four vertices for BLiNX 2's quads), with `dx` its element's offset (0 for an unlisted site), all in guest pixels of the canvas's target (A11):
  - the primitive is shifted by `dx`;
  - its window is the target's 4:3 columns, `[0, w]` in guest pixels, moved by `dx`. Pretransformed 2D is not clipped by the viewport, and H6 clipped it to the guest clip box, which is the 4:3 columns; so the canvas's view (A11) only maps units, it never narrows the window;
  - wholly inside: nothing more;
  - wholly outside (a parked piece): moved past the wide frame's edge on its side, so it stays hidden whatever it is anchored to;
  - crossing the window and axis-aligned (every vertex at the primitive's min or max x, u a function of x alone): clamped to the window, with u interpolated at the new x, which is exact for an affine quad;
  - crossing and not axis-aligned (rotated or skewed): left as it is and counted by the trace (A7);
  - full width (its own span reaches both 4:3 edges, within 2 guest pixels): not shifted and not clipped, as H4 leaves a fade or backing alone. This holds for every kind except `stretch`;
  - `world` rows: not shifted and not clipped. With the lift they show in the pads where the game projected them (BLiNX 2's world markers, A5). A `world` site that also parks its sprites (a marker slid to -400 to hide it) would show the parked one in a 16:9 pad; the group's optional `park` bound (canvas units from the centre) moves a primitive wholly beyond it past the frame's edge. The capture decides whether BLiNX 2's markers need one (tasks 3.3);
  - `stretch` rows: mapped by A13, full width included; no window and no in-game clip. The lift's box, the target's edges, clips them to the wide frame.
- So an unlisted sprite looks as it does under H6: centred, clipped to the 4:3 columns. A left element slides in from the HUD's left edge, as the game animates it at stock from the 4:3 edge. This is the assessment's "clipped at the new left edge" rule, done in the game.

*Alternative: a mark per queued sprite or batch*, with the backend shifting the box by `dx` per marked batch and keeping the 4:3 clip for the rest.
- Cost: all of A1's mark route (the push range per batch on both backends, a ring, a drain-time side table keyed by record), for the scissor alone, since the shift is already done at the add.
- Failure: a missed or late mark clips a moved element away, so the HUD element vanishes. A wrong mark lets a parked piece show.
- Benefit: draws outside the hooked call stay clipped by the backend.

*Lift costs and failures.*
- Cost: two inputs to the shared helper, one input to `nv2a_aspect_box`, the in-game clip (a few compares per primitive), and ctests. No walker or per-batch state.
- Failure: centred 2D that is not full width, drawn while the lift is on but **not** through the hooked call, is no longer clipped to 4:3. If it is partly off-screen it shows in the pad. In BLiNX 2 every such draw goes through the queue (the title, menus, pause, loading bands and dialogue all have queue sites); the other draws are full width. The trace's `[aspect.program]` lines already print each 2D batch's x range, so a run lists any batch reaching past 0..w with the lift on (tasks 3.7).
- Failure: a full-width batch the game draws itself that reaches more than 8 guest pixels past the 4:3 columns loses H5's stretch while the lift is on. The `[aspect.program]` lines show it (`lift` with a full-width x range past the band); the scenario runs compare fades and backdrops in the pads against the mod-off frames.
- Failure: a rotated primitive crossing the window shows its outside part in the pad. Counted by the trace, and left for a table row if one is ever seen.
- Failure: a call the layer leaves untouched is not clipped either, and under the lift a parked piece in it shows in the pad. Two cases: a vertex count that is not a multiple of the layout's vertices per primitive, and a call over the 1024-vertex restore cap. The first is a table error (a wrong `prim`) and the second has not been seen in BLiNX 2 (its sprites are quads and its strings are drawn per glyph). Each logs one `[hud.skip]` line per site, and `hud-map check` lists them; a site that shows one is fixed in the table or gets a larger cap before its game's check passes.
- Failure: the mod is toggled from the menu while a frame is in flight. For that one frame, shifted sprites may be clipped, or unshifted ones unclipped. Harmless.

### A3. The offset rule and the keys

- **The pad.** `pad = nv2a_host_pad(w, h)` for the canvas's target (A11; 640x480 for BLiNX 2). It is 0 at stock, at 4:3 and on targets Hor+ does not pad, and then every offset is 0.
- **The HUD's pad.** `pad_at(aw:ah) = roundf((h * aw/ah - w) / 2)` is H1's formula (`roundf`: halves away from zero). The layer calls `nv2a_host_pad` directly for `pad`, so it does not need mod-connectivity-layer's `aspect()`/`pad()` (task 4.3). `pad_hud = max(0, min(pad, pad_at(display.hud_aspect)) - display.hud_margin)`. At 640x480: 64 at 16:10, 107 at 16:9, 240 at 21:9. A 16:9 HUD on a 21:9 world gets 107 while the world fills 240.
- **Per kind**, in guest pixels of the canvas's target:
  - `left`: `-pad_hud`;
  - `right`: `+pad_hud`;
  - `centre`, `world`: 0;
  - `proportional`: `roundf(cx / (w/2) * pad_hud)`, clamped to `±pad_hud`, with `cx` the reference x from the target's centre: the primitive's own x centre, or its group's reference (A14). A piece a third of the way from the centre lands a third of the way into the wide frame, and a piece sliding from the edge to the centre moves continuously. Without a group it is per primitive, and an element built of several primitives would spread apart; a group gives them one `cx`.
  - `proportional` has no BLiNX 2 row yet. It is kept, not deferred: it is three lines and two ctests, and Mission complete (tasks 5.1) may slide in from the edges, where an edge anchor would jump.
  - `stretch`: no offset; the map of A13, from the frame's full `pad`. It ignores `display.hud_aspect` and `display.hud_margin`, because a stretched layer covers what the world covers, as H5's STRETCH does.
  - The element keeps its own distance from the 4:3 edge: BLiNX 2's top-left panel, 48 pixels in from the 4:3 edge, sits 48 pixels in from the HUD's edge.
- **Whole pixels.** `dx` is rounded with `roundf` to a whole guest pixel, so `render.snap_2d` and the 1x grid of `nv2a_snap_flat2d` stay valid on moved sprites. It is then converted to canvas units (A11); BLiNX 2's canvas units are guest pixels.
- **Keys** (layer keys, read at start whether or not a HUD mod runs, so they are never reported unused):

  | key | env | default | values |
  |---|---|---|---|
  | `display.hud_aspect` | `RECOMP_DISPLAY_HUD_ASPECT` | `display` | `display` (the configured `display.aspect`: the HUD reaches the frame's edges), or `W:H` from 4:3 up. Narrower than 4:3 is logged and read as 4:3; wider than `display.aspect` is capped by `min(pad, ...)` |
  | `display.hud_margin` | `RECOMP_DISPLAY_HUD_MARGIN` | `0` | guest pixels pulled in from the HUD's edge, 0..64; out of range is clamped with a line |

  - Env rows in toolkit `recomp_env.h` (CONFIG tier) and in cat `docs/env.md`. `packaging/config.default.toml` `[display]` lists both at their defaults.
  - **One menu item (changed 2026-10-30).** The Display page gets "HUD margin" (0..64), live: the offset is computed per sprite from the current value. It is shown only once a HUD mod has registered a table, so games without one never list it. There is no "HUD width" item: `display.hud_aspect` follows the configured aspect by default, and a narrower HUD stays a file-only choice (the user, 2026-10-30).
  - With a wide aspect and a HUD mod running, the `[ENHANCE]` aspect line adds `display.hud_aspect=... display.hud_margin=... hud_pad=N`.
- **Menus and movies stay 4:3.** Menus are not in the table, so they are unlisted: no shift, the 4:3 clip in the game (A2). Movies and stills are full-width batches outside the queue and keep `display.movie`. H6 places everything else as before.

*Alternative: per-ratio offsets in the table* (the PS2 pnach style). Rejected: one rule from the pad covers every ratio, as H1 does for the world.

### A4. No state gate for BLiNX 2 (pause decided 2026-10-30)

- The gate's job in the assessment was "menus and movies stay 4:3" where a function draws both gameplay HUD and menu pieces. The tracker item found no such sharing in BLiNX 2:
  - **Dialogue** is drawn by its own functions (`sub_000F1FD0` family, objectives `sub_000F2630`), centred as one group (A14). Its group is `centre`, so it stays centred and 4:3-clipped. The gameplay HUD stays at the edges beside it. No dialogue flag is needed.
  - **Pause** is one composed 4:3 panel from its own functions. Its widest piece reaches x 330, which the in-game clip cuts at 320 as the backend did.
  - **Loading bands, title and menus** have their own sites. The bands and the backdrops are `stretch` candidates (A13); the rest stays unlisted.
- **The HUD stays anchored while paused** (the user, 2026-10-30). The stage HUD behind the pause panel keeps its edge positions. An element the game animates (a slide-out when the pause opens, a blink) follows its animation, because the shift is applied as each sprite is added, on whatever position the game computed for that frame. No pause gate is needed, and no probe is registered.
- The pause flag `0xAE73B4` is no longer planned for this change. It stays recorded in `locate.md` for other uses.
- A later title whose element functions also draw in menus (a shared status panel) can still need a state gate. The table then names a probe (mod-connectivity-layer D8, task 4.4); the service is built with the first title that needs it, not here.

### A5. Declaring elements as data (revised 2026-10-30)

```c
/* Version 5 of struct xbox_mod_api, appended after mod-connectivity-layer's
 * version 4 fields. Init only unless said. */
enum { XBOX_HUD_CENTRE = 0, XBOX_HUD_LEFT, XBOX_HUD_RIGHT,
       XBOX_HUD_PROPORTIONAL, XBOX_HUD_WORLD, XBOX_HUD_STRETCH };

/* Parse and register the game's HUD table (TOML text the mod embeds; the
 * schema is A15's): the canvas, the vertex layout, the wrappers, the groups
 * and the sites. Every wrapper must be a hook slot; the layer hooks it.
 * A duplicate site, an unknown group or kind, a wrapper with no slot or a
 * bad canvas fails the call with one line and returns < 0, and the mod
 * fails. Returns the number of sites. */
int (*hud_table)(const char *toml, size_t len);

struct xbox_hud_call {      /* one call that hands over vertices */
    uint32_t vtx_va;        /* guest address of the first vertex */
    uint32_t n;             /* vertex count */
    uint32_t flags;         /* XBOX_HUD_RESTORE */
    uint32_t queue;         /* the game's queue or layer, for capture; 0 */
    uint64_t tex;           /* the pack's texel hash of its texture, or 0 */
};
/* From a hook's pre callback on the call that takes the vertices: resolve
 * the element, then shift, clip or map the vertices (A2, A13). With
 * XBOX_HUD_RESTORE the layer saves them and puts them back at that hook's
 * post (A1, the copying shape). Returns the kind applied. Guest thread. */
int (*hud_apply)(const struct xbox_mod_call *c, const struct xbox_hud_call *d);
void (*hud_restore)(const struct xbox_mod_call *c);
```

- **The active flag.** The layer keeps one atomic flag: set while a mod is on with a table registered and the pad above 0, or while a capture runs (A15). The wrappers' pre and post and `hud_apply` return at their first test while it is clear, so the default config at 4:3 costs one predictable branch per call. Shifts, clips, the lift and the already-wide rule need the mod part (a capture alone records). The flag is recomputed in `xbox_mod_frame` and when the mod's switch or the aspect changes.

- A site whose `ret_va` lies inside a listed wrapper's body is an error, caught by the row test (the layer does not know function extents): such a site is reached from every caller of the wrapper, menus included, and would shift them all. Time's font calls (`0x48691..0x48743`) are inside the font routine; Time's rows are its callers in `sub_0006B1F0`.
- **Rows are per call site, not per function** (`sub_0006B1F0` holds left, centre and right sites). `ret_va` is the guest return address after the call: what `[esp]` holds at the callee's entry. Each row names its element and its group (A14); the group carries the kind.
- **The call chain.** Each wrapper in the table is hooked (it must be in `hook_functions`, mod-connectivity-layer D3). Its pre pushes `[esp]` on a per-guest-thread chain and its post pops it. `hud_apply` resolves the element by trying the chain from the outermost entry inwards, then the hooked call's own `[esp]`, and takes the first row that matches. For BLiNX 2:
  - a sprite added directly: the add's `[esp]` is the element's site;
  - through a helper: the helper's caller is on the chain;
  - through the font: the chain holds the font routine's caller, then the call inside the font routine; the outermost, the font's caller, names the element. This is the tracker item's second level, with no stack offsets (`esp+0x58`, `esp+0x204C`) to maintain.
  - No match: unlisted, treated as centre with the 4:3 clip.
- The chain is at most 8 deep; a deeper push is dropped with one trace line and the element resolves from what is kept.
- **Unbalanced wrappers** (a longjmp out of a wrapper) must not leak an entry into later frames. Each chain is thread-local and only its own thread touches it. The epoch is bumped in `xbox_mod_frame`: once per guest frame, on the guest thread, outside any wrapper, never on the render thread's flip (which runs 10 to 28 frames off the guest's Swaps and could land mid-chain). Each entry records the epoch of its push, and a push first drops the entries pushed 2 or more epochs ago, so a wrapper still open across one frame boundary (a loading loop that calls `xbox_mod_frame` inside a wrapper) keeps its entry. A pop on an empty chain does nothing. No thread ever writes another thread's chain.
- **The arguments.** The mod fills `struct xbox_hud_call` from the hook's `ecx` and stack (`XBOX_MOD_ARG32`); tasks 0.3 confirms where they live. `queue` and `tex` are optional and feed only the capture (A15): BLiNX 2's queue flag is a stack argument, and its texture is named by the record the add writes. A call whose `n` is not a multiple of the layout's vertices per primitive is skipped unchanged, with one trace line per site.
- The lookup is a binary search over the sites, sorted at registration. A duplicate `ret_va` fails registration with a line.

**Where the table lives (revised): a TOML file in the game repo, embedded in the build.** The tracker item chose a C table in the game's mod. With a tool writing the table (A15), that choice is reopened:
- **Chosen: `config/hud.toml` in the game repo**, the one source of the table. `<game> hud-map emit` writes it and a person reviews its diff. The game's build embeds its text into the mod (a CMake `file(READ)` into a header in the build tree, not into `src/recomp/gen/`), and the mod passes it to `hud_table` at init. The toolkit's TOML reader already takes arrays of tables, so the layer adds no parser.
  - A tool writes the table, and a person corrects it. A C table would need emit to rewrite C source that people also edit, or a generated `.c` file under the never-hand-edit rule. TOML gives one readable diff, comments for review notes, and no code generator.
  - The rows still name call sites of one pinned XBE. They change only when the build changes, and they ship inside the executable, so players never edit VAs and a bad row cannot come from a player's file.
  - The format is the same one a later per-element override would use (tasks 6.4), so a launcher's file can be read by the same parser.
- **The row test stays.** `<game> hud-map emit --check` validates a table against the analysis without writing (A15), and the game keeps a `scripts/test_*` case that reads `config/hud.toml` and checks each `ret_va` follows a call to a hooked function or a listed wrapper in the analysis xrefs.

*Alternative: keep the C table*. Rejected now that a tool writes it, for the reasons above. A game may still register a table built in C by passing TOML text it composes; nothing in the layer depends on where the text came from.

*Alternative: JSON.* Equivalent for the tool, but the repo's config files are TOML, the toolkit already reads TOML, and JSON has no comments for review notes. Rejected.

*Alternative: rows in `config.default.toml`* (`[mods.hud] sites = [...]`). It ships as an editable file to players, and a row there can name a site with no hook. Rejected; tasks 6.4 keeps a per-element override for a launcher, on top of the embedded table.

*Alternative: `game.toml`.* It is the CLI's file; the CLI carries no runtime data (CLAUDE.md). Rejected. `game.toml` only names the table's path for the CLI (`[hud] table`, A15).

**BLiNX 2's rows** come from the tracker item's element table (`locate.md` section 4), rebuilt with the framework (tasks 3.3) and checked against it:
- groups `left`: the top-left panel (frame, portrait, health bar, the "Stick" name, the lives dots, Time and the gauge bracket) and the radar;
- groups `right`: the TS label with its dashes, and the item counter (the big digit and "/ 5");
- groups `centre`: the time-control slots, the yellow arc, the round banner (listed so the trace names them), and the dialogue (box, face, text, A button, short label) and the objectives;
- group `world`: the world markers at `0x412A8`;
- groups `stretch`: the `S` rows the review keeps (A13): the loading bands of `sub_0005EB30`, and the cutscene dim, the pause backdrops and the title backdrop if their frames confirm it.
- The rows for Time and "/ 5" are the font routine's callers in `sub_0006B1F0` (`0x6B671`, `0x6B819`, `0x6BA9B`, `0x6BFE1`, `0x6C059`); which is which is checked in tasks 3.3.
- The full-width zero-height quads (`sub_00216D70`, `0x21703A`) are never listed and never move.

### A6. Text and the HUD pack

- **Text.** A string's five outline passes share one element through the call chain (A5), so they move together. The font routine needs no hook beyond being a wrapper. Corner text and centred text from the same routine take their callers' kinds.
- **The pack** swaps by texel hash at upload and does not depend on where a sprite lands, so moved elements keep their hi-res art, fonts (`textures.font`) and baked text images (`textures.text`). Whole-pixel offsets (A3) keep the pack's texels on the same host grid as at stock. A stretched sprite (A13) is magnified by the frame's map, as H5's STRETCH magnifies a fade.
- **The in-game clip changes u** on a crossing primitive. The pack's sampler reads the same normalised u, so a clipped hi-res sprite shows the same part of its art as the backend scissor would have.
- **The import path** for owner-made images and for dumps named by hash is a separate item, the tracker item. This change does not depend on it.
- **Per-element texture substitution** (assessment section 4.5) needs the mark route (A1) to reach the backend. Not in this change.

### A7. Trace

`RECOMP_TRACE=hud` (TRACE tier row in `recomp_env.h`, cat `docs/env.md` row):
- `[hud.site] 0xRET element group kind dx N`: once per distinct site seen, and again when `dx` changes (a key changed live, or the canvas changed);
- `[hud.unlisted] 0xRET x LO..HI`: once per distinct unlisted site whose primitives cross or lie outside the 4:3 window. These are the candidates for new rows (Mission complete, a slide-in nobody listed);
- `[hud.skew] 0xRET`: once per site with a crossing primitive that is not axis-aligned (A2);
- `[hud.canvas] WxH origin O view X,Y,W,H target TWxTH source S`: at registration and whenever a run-time read changes it (A11); a read that falls back adds `fallback` and the reason;
- `[hud.skip] 0xRET reason`: once per site whose call is left untouched and unclipped (a vertex count not a multiple of `prim`, or over the restore cap; A2);
- `[hud] lift on|off pad P hud_pad H`: at start and when it changes.

With `RECOMP_TRACE=aspect` also on, the `[aspect.program]` lines show the lift (`lift` after the placement), and `wide` when the already-wide rule (A2) cleared a batch's full width, so a 2D batch reaching past 0..w under the lift is visible next to its program and texture.

The capture for the mapping framework is a separate DEBUG key, `hud_capture` (A15): it writes files, so it is not a trace.

### A8. Other games (later items)

Each is its own ticket after this layer and the framework land. The framework (A15) does the inventory; a title-specific spike is needed only where its capture cannot see the HUD.
- **Burnout 3** (RenderWare 3.6): the HUD's natural hook is `RwIm2DRenderPrimitive` and `RwIm2DRenderIndexedPrimitive`, which copy their vertex arrays into the pushbuffer during the call (A1's copying shape), by `sig:` row. Elements by return address or by wrapper. It is the canvas's stress case (A11): it draws into a viewport smaller than its target, so its canvas declares a view inside the target, and the view maps its units while the window, the offsets and the stretch come from the target's columns and pad, not from 640x480. The race HUD (speed, boost, position, timer) gets edge kinds; the front end is unhooked and stays 4:3. Its menus are near layers (rhw 10, `nv2a_aspect_flat`), which the lift never opens (A2), so they stay clipped even with a HUD mod on. If Burnout 3's race HUD is itself drawn as a near layer, the lift's `flat` exclusion has to become per-site, and that needs the mark route. The crash-cam bars stay with the band rule (mod-connectivity-layer D5). Split-screen may compose a per-player HUD into its own target, or draw each player's HUD into its own view; a view that changes within a frame needs the canvas read per call rather than per guest frame (A11), and a separate target needs the mark route.
- **JSRF**: an older XDK. Whether its HUD goes through the `Draw*` entries, `BeginPush` or vertex buffers is unknown. Entries with user-pointer vertices fit this change; vertex buffers or `BeginPush` need the mark route (A1). Its level-0 capture (A15) answers this.
- **SSX 3** fits the same shape if its HUD calls draw through user-pointer vertices; native Anamorphic needs nothing from this change.

### A9. Where it sits against mod-connectivity-layer

| mod-connectivity-layer item | used here |
|---|---|
| D3 hook slots (tasks 5.1 to 5.4, 5.6) | yes: five slots in BLiNX 2, and BLiNX 1's add and wrappers once found; the table's wrappers and the mod's add hook use `hook()`. The level-0 capture (A15) hooks a game's D3D draw entries the same way, by VA or `sig:` row |
| `needs` (task 4.1) | yes: the mod declares `XBOX_MOD_NEED_HOOK`, so it is refused with a line when a hook slot is missing. `needs` does not turn a mod off at 4:3; the pad-0 no-op (A10) does |
| the gate (task 4.2, D9) | no: the `hud` mod's switch is its v3 descriptor's `XBOX_SET_ENABLE` setting, `mods."hud.enabled"`, which already exists, defaults to true (A16) and is not D9's `[mods.<name>] enabled` or a `follows` key. Nothing here needs D9's gate |
| `mods=` token (task 4.9, CLI 5.5) | yes, with one addition this change makes to 4.9: a mod may report an active state, and such a mod is listed only while it is set. `hud` reports the layer's active flag (A5), so at 4:3 and in the goldens (`mods=none`, 4:3) the token stays `none` |
| `aspect()`/`pad()` (task 4.3) | no: the layer calls `nv2a_host_pad` itself |
| D8 probes (task 4.4) | no: no pause gate (A4). The canvas's memory source (A11) is a plain read in `xbox_mod_frame`, where the layer already bumps its epoch, not a probe |
| D4 pokes, D5 `place`, D7 `rt_dims` (tasks 4.5 to 4.7) | no: the canvas's target source reads the frame's guest size inside the toolkit, the same value `rt_dims` would report to a mod |
| API version | mod-connectivity-layer's services are version 4 (task 4.1, amended by hud-anchors); the HUD fields are version 5, or the same bump if both land in one merge |
| D5 placement order | unchanged: the lift changes the box of a CENTRE batch, and the already-wide rule (A2) changes only H4's full-width input on the canvas's target while the active flag is set. There is no new step 0 |

The assessment proposed a new D5 step 0 for the mark. With A1 and A2 there is no mark, so D5 stays as specified. The amendment of 2026-10-30 adds no dependency on mod-connectivity-layer: the framework's capture needs the same hook slots as the mod.

### A10. Stock and goldens

- With the active flag clear (no HUD mod, the mod switched off, or the aspect 4:3, where the pad is 0): the wrappers and `hud_apply` return at their first test, no vertex is touched, `lift` is 0, the already-wide rule is off, and `nv2a_aspect_box` gives the H5 box.
- The hook slots for the five functions exist in every BLiNX 2 build after tasks 3.2. Stock goldens of that build prove the empty branch changes nothing (mod-connectivity-layer D12).
- Goldens run with `mods=none` and `display.aspect=4:3`, which the golden harness already pins. Either pin alone keeps the flag clear, so the mod being on by default changes nothing there, and the token prints `mods=none`. The two new keys need no pin of their own.
- The `hud_capture` key (A15) is DEBUG tier, unset by default, and records without changing anything.
- The mod is on by default, an exception the user approved (A16). Hor+ stays opt-in (`display.aspect` ships as 4:3), so a player who never picks a wide aspect sees stock. A player who does gets the HUD at the edges, and the Mods page turns it off.

### A11. The game canvas (added 2026-10-30)

The tracker item assumed 640x480 centre-relative coordinates. That is BLiNX 2's canvas, not a rule. The mod describes the game's canvas, and the layer reads its size at run time.

- **The descriptor** (the table's `[canvas]`, A15):
  - `w`, `h`: the canvas size in canvas units (BLiNX 2: 640, 480);
  - `origin`: `centre` (x 0 at the canvas centre, BLiNX 2) or `top-left` (x 0 at the left edge, Burnout 3's screen pixels);
  - `y`: `down` or `up`. The x rules never use it; capture and review need it to draw boxes on the frame;
  - `view`: the rectangle of the target, in guest pixels, that the canvas's units map onto. Default: the whole target. It maps units only; it never clips (A2). Burnout 3 may declare a smaller one;
  - `target`: the guest size of the frame the HUD lands on: `frame` (default: the back buffer's guest size, the surface H1 pads, read in `xbox_mod_frame` with the canvas) or a fixed `[w, h]`;
  - `source`: where `w`, `h` and `view` come from at run time: `fixed` (the declared values), `memory` (guest addresses with a type, `f32` or `u32`, read once per guest frame in `xbox_mod_frame`) or `target` (the canvas is the target: `w`, `h` and `view` equal the target's guest size). The declared values are the fallback.
- **Units.** Canvas units map to guest pixels by `s = view_w / w`: `gx = view_x + (x - x0) * s`, with `x0 = -w/2` for `centre` and 0 for `top-left`. Every rule in A2, A3 and A13 runs in guest pixels of the target, and the result is converted back by `1/s` before it is written. `dx` is rounded to a whole guest pixel first, so a canvas whose units are not pixels still lands its sprites on the pixel grid.
- **The window** of A2 is the target's 4:3 columns moved by `dx`, whatever the view: pretransformed 2D is not viewport-clipped, and H6 clips it to the guest clip box. The full-width test and the stretch map use the target's columns and centre too, because they have to agree with H4 and H5, which see the target.
- **The pad** comes from the target (`nv2a_host_pad(target)`), not from the canvas: a HUD drawn into a smaller view still moves to the wide frame's edges, and the view's own gap to the target's edge stays as the game's margin.
- **Reading it.** A `memory` source and the target's size are read at the same point, in `xbox_mod_frame` where the chain epoch is bumped (A5): on the guest thread, once per guest frame. The target size is the last back-buffer guest size the render side published. Both go into one snapshot that `hud_apply` reads. A value that is not finite, not positive or over 4096 is not used: the layer keeps the declared fallback and logs one `[hud.canvas] ... fallback` line per change. A view that changes within a frame (a split-screen per player) would need a read per call; that is added with the first title that needs it (A8).
- **The lift** compares a batch's target to the canvas's target size, so 2D drawn into other targets keeps its H5 clip.
- **BLiNX 2** is expected to be `fixed`: centre origin, y down, 640x480, the whole 640x480 target. The drain adds +320 and +240 to reach screen pixels. Tasks 0.3 finds where it holds those numbers: immediates in the drain (then `fixed` is right, and the row test checks the immediates in the analysis), or variables (then `memory`, with their addresses).
- **BLiNX 1** answers the same question once its sprite path is found (tasks 0.4).
- **Burnout 3** is the stress case for the descriptor: a top-left origin in screen pixels, and a view smaller than the target if its HUD units map onto part of it. The descriptor has to express it without layer changes; its ctest uses a synthetic smaller view, where the view moves the units and the window stays the target's columns (tasks 1.9).

*Alternative: hardcode 640x480 and convert per game in the mod.* Every game's mod would repeat the conversion, the trace and the capture would print game units nobody can compare across titles, and Burnout 3's view would need its own window logic. Rejected.

*Alternative: derive the canvas from the projection or the viewport registers on the render thread.* The shift runs on the guest thread at the add, long before the batch reaches the walker, so the render thread's view of the viewport arrives too late. The target's guest size is the only render-side fact the layer uses, and it changes only on a mode change.

### A12. Per-element shift stays the rule (added 2026-10-30)

A uniform map of the whole HUD, `x × W/w`, looks simpler: one transform, no table. It splits elements apart. It scales positions but not sprite sizes, so a panel built of a frame, a portrait and a bar spreads out: each piece's centre moves by a different amount while each piece keeps its width, and the gaps between them grow by up to a third at 16:9. Text built of one quad per glyph spreads the same way.

So the rule stays per element: every primitive of an element moves by the same `dx`, and the element keeps its shape. `proportional` is the one kind computed from a position, and a group (A14) gives all its members one reference x, so it does not split them either.

The uniform map that scales positions *and* widths is `stretch` (A13). It keeps shapes consistent with each other but distorts them, so it is right only for layers meant to cover the screen.

### A13. The `stretch` kind (added 2026-10-30)

- **The map.** `x' = cx + (x - cx) × W/w`, about the target's centre `cx`, with `W = w + 2·pad` the wide frame's width in guest pixels. It is the map H5's STRETCH applies to a full-width batch, done in guest memory. Every vertex gets the same linear map, so positions and widths scale together and slide animations stay consistent: two bands that met at the 4:3 edge now meet at the wide edge, and a band parked at ±1280 is parked further out, still off the frame.
- **No window, no in-game clip.** A stretched sprite is clipped by the wide frame itself: the lift (A2) gives it the target's edges as its box.
- **Applied once.** H5 would stretch a full-width batch again. Two rules keep the map single:
  - every primitive of a `stretch` element is mapped, full width included, so the element never jumps between the guest map and H5's at the end of a slide or between a sprite H5 places by `display.movie` (a guest picture texture) and one it stretches;
  - the backends' already-wide rule (A2): with the active flag set, a triangle that reaches more than 8 guest pixels past the 4:3 columns is not full width, so H5 places it CENTRE and the lift opens its box. A mapped primitive that covers the 4:3 columns but would reach less than 8 pixels past them (only when the original spans about the middle `w × w/W` of the frame, or the pad is under 8) has its outer x pushed out to 9 pixels past the columns. Its u is kept, not extrapolated: the texture stretches by at most 9 guest pixels over the primitive's width, and no texel outside the sprite's own u range is sampled, whatever the texture's wrap or clamp mode, for a few frames of a slide.
- **Which sprites.** `stretch` is for 2D that samples guest textures or no texture. A pass that samples a padded render target stays with H5, which reads the whole padded target for it; the trace's `[aspect.program]` line shows the source, and the review (A15) keeps such a site unlisted.
- **What H5 already covers in BLiNX 2.** The fades (`sub_00042380`, outside the queue) and the cutscene dim (`0x55210`, untextured or a small texture, full width) are already stretched by H5 when they are full width; a row for them changes nothing but makes them consistent if they ever slide. The pause backdrops (`0x171CA2`, `0x171D08`, `0x171FAF`) and the title backdrop (`0x1845C`) are full-width pictures, which H5 places by `display.movie` (pillarboxed under the default `black`); a `stretch` row fills the frame with them instead. The loading bands of `sub_0005EB30` are the case H5 cannot cover: while they slide they are not full width, so H6 clips them to the 4:3 columns and they snap to the wide frame only at rest. The review decides each one with the wide preview (A15); the bands are the expected rows.
- **The cinematic black bars** (the user's requirement, 2026-10-30) must cover the wide frame in cutscenes. Their site is not located (Context); tasks 3.3 finds it with a cutscene capture: the cutscene dim `0x55210` or another site in the cutscene code (`sub_00054860`, `sub_000550C0`). They are `stretch` rows, grouped as one `bars` group, unless the capture shows every bar triangle spans `[2, w - 2]` and lies within `[-8, w + 8]`. Then H5 already stretches them (a full-width untextured batch, as the Hor+ analysis lists), the already-wide rule keeps them full width, and no row is needed. The case that needs a row: a bar the game over-draws, say at -16..656, is more than 8 pixels past the band, so with the lift on it loses H5's stretch, is placed CENTRE and drawn at -16..656, and the pads beside it are bare. As a `stretch` row it maps to about -128..768 at 16:9 and covers them. A bar that slides in from off the canvas needs the row too, for the bands' reason.
- **The zero-height quads** of `sub_00216D70` stay unlisted. They are full width and have no area, and H4 leaves them alone.
- **At 4:3**, `W = w` and the map is the identity.

*Alternative: let H5 handle every `S` row.* It already does at rest, but a band that slides in from ±1280 is not full width until its last frame, so H6 keeps it in the 4:3 columns while it moves, and it pops to the full frame when it stops. Rejected for the bands, the case the user named.

*Alternative: a backend STRETCH placement for marked batches.* Needs the mark route (A1). Rejected for the same reasons as A2's alternative.

### A14. Groups (added 2026-10-30)

- **A group is a set of sprites that share one transform.** Each site row names its group; the group carries the kind. An element's sprites always share a group, and siblings that must move together share one too: BLiNX 2's dialogue (box, face, text, A button), the top-left panel (frame, portrait, health bar, name, lives, Time, gauge bracket), and a bar with its end caps.
- **The table's `[[group]]`** has a name, a kind, an optional `ref_x` in canvas units and, for `world`, an optional `park` bound (A2). A site with no group is its own group, named after its element.
- **The reference.** Edge kinds, `centre`, `world` and `stretch` give every member the same transform by construction. `proportional` needs one `cx` for the whole group: the group's `ref_x` when declared, else the x centre of the first primitive of the group's first member added in this guest frame (the epoch the chain uses, bumped in `xbox_mod_frame`). Each group stores its (epoch, reference) as one 64-bit atomic, set by compare-and-swap: the first thread to add a member in a new epoch sets it, and every other thread, in the same frame, reads that value, so threads agree on the first member. A group whose first member is not drawn in a frame takes its reference from whichever member comes first.
- **The window** of A2 is per group: all members are clipped to the same view moved by the same `dx`.
- **For the framework**, groups are what `propose` suggests and what the review edits: sites become elements, elements become groups (A15).

*Alternative: a kind per row, as the tracker item had.* Rows of one panel could get different kinds by mistake, and `proportional` had no shared reference. Rejected; a group of one is still one row's choice.

### A15. The HUD mapping framework (added 2026-10-30)

Each game needs its own element table, built by hand from traces (took a spike for one game). The framework makes that a repeatable flow, game-agnostic in the CLI and the toolkit, with the game's data in the game's repo.

**Commands.** A developer command, `<game> hud-map <verb>`, beside `bench`, `public` and `wizard`, in a CLI package `hudmap/`. The name keeps it apart from `enhance hud`, the player's HUD texture pack built from the dump (`enhance/hud.py`), which stays as it is. The help lists `hud-map` with the developer commands. `game.toml` gains an optional `[hud]` table with paths only: `table` (default `config/hud.toml`) and `scenarios` (the game's scenario names for capture and check). The CLI's `manifest.py` rejects unknown tables, so `[hud]` gets a schema entry there and a section in `docs/manifest.md`. The CLI holds no game constants.

1. **capture** (`<game> hud-map capture SCENARIO [--level 0|1] [--frames FROM:COUNT] [--out DIR]`): runs a scenario at stock aspect with `RECOMP_DEBUG=hud_capture=<dir>` and writes `capture.jsonl` plus one guest-size frame (BMP) per captured frame.
   - The runtime side is a toolkit DEBUG key, `hud_capture=<dir>`, with `hud_capture_at=<from>:<count>` in guest frames. It sets the layer's active flag for recording only (A5): it records and changes nothing, whatever the mod's switch. Capture runs at 4:3, so the boxes are in the stock layout.
   - **The table without a mod.** `hud_capture_table=<path>` makes the capture load a table file itself, with the layer's parser, and hook its wrappers and `[capture] draws` through the same hook service a mod uses. Locating a new title then needs no mod, only the hook slots (`[mods] hook_functions`, then `analyze` and `recomp`). `hud-map capture` passes the game's `[hud] table`. When a mod has registered a table too, the mod's wins and the file is ignored with one line. Chosen over a registration-only mod per game, because the step is the same for every title and belongs in the toolkit.
   - One JSONL line per sprite: the guest frame, the queue, the call chain (outermost first), the resolved site and group if the table lists it, `n`, the bounding box in canvas units, the primitive count, and the texture hash when given. One line per frame: the frame and the canvas snapshot (A11).
   - The capture dumps the picture of each captured guest frame itself, at the flip that presents it. It does not reuse `fb_dump_at`, which counts host flips, and the tracker item saw the guest's Swaps run 10 to 28 behind them.
   - **Level 1** records at `hud_apply`, called by the game's mod from its hook on the add (for BLiNX 2, the skeleton mod of tasks 3.4a), with the chain of the table's wrappers. **Level 0** is for a title located from scratch: it records at the D3D draw entries the table lists under `[capture] draws` (by VA or `sig:` row, as hook slots), with a scan of the stack for return addresses inside the code sections, as BLiNX 2's `hud_calls` key does (cat `spike/hud-locate` adc8034, the starting point for the runtime side). A draw row may name where its vertex pointer, count and stride live (`ecx`, `edx`, `stack:<offset>`); with them level 0 records boxes, without them only call sites and counts. Level 0 answers whether the title draws directly or through a queue; a queue then means naming its add and wrappers in the table, writing the mod's add hook, and capturing again at level 1.
   - `--out` defaults to `dist/hud-map/<scenario>/` (gitignored, like `dist/enhance/`). In this workspace captures go under `xbox-recomp/runs/hud-map/<game>/`. Captures hold game frames and are never published or committed.
2. **propose** (`<game> hud-map propose CAPTURE... [--out FILE]`): groups the captured sprites into elements by call site and chain, and elements into group candidates by their function (from the analysis) and touching boxes, and suggests a kind from where each element is when it is on the canvas:
   - in the left third: `left`; in the right third: `right`; in the middle third: `centre`;
   - spanning the canvas: `stretch`;
   - beyond the edges and moving between frames independently of any slide (its centre changes in both x and y, not monotonically): `world`, with a `park` bound proposed when some of its sprites sit far beyond the rest;
   - parked off the canvas in some frames and inside it in others (a slide-in): the kind of its on-canvas frames, so it follows its element;
   - zero-area primitives (BLiNX 2's zero-height quads): never proposed.
   It writes a proposal file (the table's schema, every row marked `proposed`, with the evidence: frames seen, boxes, the rule that chose the kind) next to the capture. It never writes the game's table.
3. **review** (`<game> hud-map review PROPOSAL [--ratio 16:9]`): writes a static contact sheet (one HTML file, SVG boxes over the captured BMP frames, no server, standard library only) next to the capture. Each frame is shown twice: at 4:3 with element boxes coloured by kind and labelled with element, group and site, and at the wide ratio as a preview, the frame placed in grey pads with each element's crop moved or stretched by its kind's rule. A person corrects kinds, groups and names in the proposal file and runs review again.
4. **emit** (`<game> hud-map emit PROPOSAL [--check]`): validates the proposal against the analysis and writes the game's table (`[hud] table`, by default `config/hud.toml`). Rows already in the table are kept unless the proposal changes them; rows still marked `proposed` are refused unless `--accept-proposed`. The checks are the row test's: each `ret_va` follows a call to the hooked add or a listed wrapper; none lies inside a wrapper's body; no duplicates; every wrapper and draw is in `[mods] hook_functions`; every kind and group is known; the canvas parses. `--check` validates the existing table and writes nothing (exit 1 on a bad row).
5. **check** (`<game> hud-map check [SCENARIO...] [--ratios 16:9,16:10,21:9]`): runs each scenario with the mod on at each ratio, with `RECOMP_TRACE=hud,aspect` and frame dumps, plus the mod-off frames at the same ratio, and writes a per-ratio sheet (the same HTML form): mod off beside mod on, the `[hud.unlisted]`, `[hud.skew]` and `[hud.skip]` sites, and any lifted batch reaching past the columns that no row explains. It compares nothing against goldens; goldens stay stock (A10).

**The table schema** (`config/hud.toml`): `version`, `[canvas]` (A11), `[layout]` (`stride`, `x_off`, `u_off`, `prim`: vertices per primitive), `[[wrapper]]` (`va`, `name`), `[capture] draws` (level 0 only), `[[group]]` (`name`, `kind`, `ref_x`, `park`), `[[site]]` (`ret_va`, `element`, `group`, an optional `note`). The layer refuses a version it does not know.

**Where the pieces live.**
- The toolkit: the `hud_capture` keys and their writer, beside the layer (A5), standard C, writing on the guest thread into a buffer flushed in `xbox_mod_frame`.
- The CLI: the `hudmap/` package for the five verbs, standard library only; the contact sheet is plain HTML and SVG over the dumped BMPs; the proposal rules are pure functions with pytest cases over synthetic captures.
- The game repo: `config/hud.toml`, the mod, the `[hud]` paths in `game.toml`, the row test.

**Frames-only rule.** Captures, sheets and frames stay under `runs/` (or a gitignored `dist/`). They are never committed, published or attached to the tracker. The table and the proposal hold VAs, names, kinds and boxes in canvas units, no game data, and the table is committed.

**Scope kept** (the review asked whether to defer the `memory` canvas source, `view` and the wide preview). All three stay: the user asked for a canvas read at run time from game variables and for a contact sheet at a wide ratio, and `view` is how Burnout 3's units are expressed. Each is small; the `memory` source is only built into a game's table if tasks 0.3 or 0.4 finds variables.

*Alternative: keep mapping a manual spike per game* (the tracker item's way). It took a full spike for one game and left the result as a markdown table that had to be retyped as rows. Rejected: every title in the plan needs it.

*Alternative: put the framework in the game repo* (cat's scripts). Every game would copy it. Rejected; the CLI is the shared home for game-agnostic tooling.

*Alternative: capture at the render thread from the pushbuffer.* It sees only the drain's draws and no call sites. Rejected; the capture runs where the shift runs.

### A16. The HUD mod is on by default; the wizard only offers Hor+ (revised 2026-10-30)

- **The user's decisions.** No separate wizard item for the HUD: picking Hor+ turns on the HUD at the edges. Then, after the review of this amendment, the user approved the HUD mod defaulting **on**, as an exception to the default-off rule, like the in-game menu (on by default since 2026-10-27).
- **What that means.** `mods."hud.enabled"` defaults to true in each game's descriptor and in its `config.default.toml`. Any wide aspect, set in the wizard, the menu or the file, anchors the HUD at the edges; the Mods page turns it off. A player who stays at 4:3 sees stock.
- **Stock stays byte-identical.** The mod acts only through the layer's active flag (A5): mod on, table registered, pad above 0. At 4:3 the pad is 0 and the flag is clear, so the wrappers and `hud_apply` cost one branch and the frames do not change. `hud` appears in the `mods=` token only while the flag is set (A9), so stock and the goldens (4:3, `mods=none`) print `mods=none`. Hor+ itself stays opt-in: `display.aspect` ships as 4:3.
- **The wizard** needs no new manifest field. Each game adds one `choice` option, `config = "display.aspect"`, values 4:3, 16:10, 16:9 and 21:9, default 4:3, after its HUD ratio check (tasks 6.5). The mod's default does the rest.
- **Updates.** A player who already plays at a wide aspect sees the HUD move to the edges after the update that ships the mod. That is the intent: it is what the user asked Hor+ to look like. The release notes say it and point at the Mods page.

*Alternative: default off, with the wizard writing `mods."hud.enabled" = true` beside the aspect through a new `[[wizard.option]] also` field* (this amendment's first version). It kept the default-off rule but needed a CLI manifest change, covered only fresh installs through the wizard, and left a player who set the aspect in the menu with a centred HUD. Replaced by the user's decision.

*Alternative: a separate "HUD at the edges" wizard item.* The user chose not to have one.

### A17. BLiNX 1 (added 2026-10-30)

- **BLiNX 1 is an initial target with BLiNX 2.** Its HUD has not been located. It is the first game the framework locates from scratch, and the test of whether A15 replaces a spike.
- **Prerequisite: its Hor+ is finished.** `hor-cull` is on blinx `main` (769b8b5). What remains is its task 4.1, lifting the "untested" note in `config.default.toml`, and its task 4.2, the faint vertical seam at the old 4:3 edges. Both close before BLiNX 1's HUD work, so the mod never ships on a Hor+ with a visible seam.
- **Order.** Then: the hook slots for its D3D draw entries (from its D3D section, by `sig:` rows as in `locate.md` section 1) in `blinx/game.toml`, `blinx1 analyze` and `blinx1 recomp`; a skeleton `config/hud.toml` with `[capture] draws`; the level-0 capture through `hud_capture_table` (A15), with no mod yet; the copy, cull, argument and canvas checks of tasks 0.4 on whatever path that finds; its mod's add hook; a level-1 capture; propose, review, emit; its mod; its ratio check.
- **What carries over.** BLiNX 1 and BLiNX 2 share a developer, so the sprite-queue shape may repeat. That is a guess for the capture to confirm, not a plan: the level-0 capture runs first either way, and BLiNX 2's VAs are never reused.
- **Its mod** is the same shape as BLiNX 2's: a descriptor mod with `XBOX_SET_ENABLE` (default on, A16), an embedded `config/hud.toml`, the hook list in `blinx/game.toml` `[mods] hook_functions`, and its own row test. Its tracker items carry the `game:blinx-1` label.
- **Stock check without goldens.** BLiNX 1 has no golden suite. Building one is its own item, larger than this change, so the stock gate for BLiNX 1 is an A/B frame comparison instead: the default config at 4:3 (mod on, flag clear) against the build without the HUD slots, over the same scripted scenarios, on Metal and on D3D11, with equal frame dumps required. If BLiNX 1's goldens land first, they replace the A/B.
- If BLiNX 1's HUD draws from vertex buffers filled ahead of the draw, it needs the mark route (A1), and its section stops at the locate with that finding.

## Risks / Trade-offs

- **The mod is on by default** (A16). A bug in the layer reaches every player at a wide aspect, not only those who opted in. Mitigation: the per-ratio checks (`hud-map check`) and speed checks gate each game's mod; the Mods page turns it off live; stock (4:3) is unaffected by construction and by the goldens.
- **A centred 2D draw outside the hooked call can leak into the pads under the lift** (A2). Mitigation: the tracker item found none in BLiNX 2; the scenario runs check the `[aspect.program]` x ranges with the lift on; the trace names unlisted sites. A title where this happens needs the mark route or a narrower lift.
- **Skipped calls are not clipped** (A2): a wrong `prim` or a call over the restore cap. Logged as `[hud.skip]`; a game's check does not pass with one.
- **The already-wide rule can take H5's stretch from a game's own full-width triangle** that overhangs the 4:3 columns by more than 8 guest pixels, while the active flag is set (A2, A13); the cinematic bars are the known case and get a row. Mitigation: only on the canvas's target with a HUD mod active; `[aspect.program]` marks it `wide`; `hud-map check` compares fades, bars and backdrops in the pads against the mod-off frames.
- **The stretch nudge** moves a mapped edge by up to 9 guest pixels for a few frames of a slide, with the texture stretched over the primitive (A13). Accepted.
- **Rotated primitives crossing the window are not clipped.** Counted by `[hud.skew]`. A table row can mark the element `world` or move it away from the edge.
- **Parked world markers** show in the pads unless their group has a `park` bound (A2). The capture shows whether a `world` site parks.
- **The shift on the caller's buffer assumes the call copies.** Checked per game before any toolkit work (tasks 0.3, 0.4). A wrong guess either undoes the shift (pointer kept, restored) or accumulates it (no restore); both show at once on the first scenario run.
- **Hook slots on hot functions.** `sub_000177F0` has 747 callers. With the flag clear the cost is one predictable branch per call; with it set, a chain push and pop and a binary search per sprite. Measured on the Deck and on Metal with `RECOMP_TRACE=pacing` (tasks 3.8, 4.8) in two pairs: the build with slots at 4:3 against the build without slots, and the mod on against the mod off at 16:9.
- **Near layers are never lifted** (A2). A title whose HUD is drawn as a near layer gets no pads from this change; Burnout 3's front end, the case the `flat` rule was written for, stays clipped.
- **No CPU path.** The CPU rasteriser gets no lift and no already-wide rule; the guest-side shift still runs there, so moved elements are clipped by its 4:3 scissor. Recorded as a TASKS follow-up (tasks 7.3), as CLAUDE.md asks for a CPU gap.
- **A wrong canvas read moves everything.** A memory source that reads garbage falls back to the declared values with a line (A11); the declared values are what the row test checks.
- **Proposals are heuristics.** `propose` will misjudge some elements (a centred element that sits in the left third, a world marker that never leaves the canvas). The review is the guard: nothing reaches the table while it is marked `proposed`, and `hud-map check` shows the result at every ratio.
- **Capture and frame alignment.** A box drawn on the wrong frame misleads the review. The capture dumps its own frames by guest frame (A15) for that reason.
- **A frame in flight during a toggle** may show one frame of mismatched shift and clip. Accepted.

## Migration Plan

1. mod-connectivity-layer tasks 4.1, 4.9 (with the active-state addition) and 5.1 to 5.4, 5.6 land; 5.5 for the goldens' token. 4.2 is not needed (A9).
2. The layer (tasks section 1): canvas, table, chain, groups, kinds including `stretch`, the API with the active flag, the lift and the already-wide rule, the margin key and item, trace, ctests. Stock goldens. The toolkit pin moves in each game with `sh notes/build-all.sh`.
3. The framework (tasks section 2): the toolkit's `hud_capture`, then the CLI's `hud-map` verbs. Capture and propose need the canvas, the table, the chain and the API (tasks 1.1, 1.2, 1.5), so they can merge before the rest of section 1. A CLI release, then cat's `[cli]` pin, with `sh notes/build-all.sh`.
4. BLiNX 2's mod (tasks section 3): the copy and canvas check, the hook list, the skeleton mod, the table built with the framework, the full mod, the scenario runs, goldens.
5. BLiNX 1's mod (tasks section 4): its Hor+ finished, its locate from scratch with the framework, its table, its mod, its ratio check, its A/B stock check.
6. Mission complete (tasks section 5).
7. Later items (tasks section 6): JSRF and Burnout 3, the mark route if a title needs it, the games' aspect options in the wizard, per-element overrides, the tracker item.

Each step merges on its own after a review.

## Open Questions

1. **Does `sub_00042190` copy the vertices, and does anything cull by x?** A copy is likely (A1). A pointer kept until the drain, or no copy, stops this change in favour of the mark route. Tasks 0.3; answerable from Ghidra.
2. *Closed 2026-10-30.* **The world markers** are `world` rows and show in the pads where the game projected them. If the game culls them to its 4:3 view they pop in at the old edge, and the cull is widened before the check passes (tasks 3.7a); a marker the game parks off-screen gets a `park` bound (A2).
3. *Closed 2026-10-30.* **The paused HUD** stays anchored; animated elements follow their animation (A4). No pause gate.
4. *Closed 2026-10-30.* **"HUD width" in the menu** is dropped. `display.hud_aspect` defaults to the configured aspect and stays a file key; "HUD margin" stays in the menu (A3).
5. **Where BLiNX 2 and BLiNX 1 hold their canvas** (A11). Tasks 0.3 and 0.4. Immediates mean a `fixed` canvas; variables mean a `memory` one.
6. **Does BLiNX 1 draw its HUD through user-pointer vertices or a copying queue?** Its level-0 capture answers it (A17). Vertex buffers filled ahead of the draw would move it to the mark route.
7. **Where BLiNX 2 draws the cinematic black bars, and how wide** (A13). A cutscene capture in tasks 3.3 answers it: inside `[-8, w + 8]`, H5 covers them; past it, or sliding, they are a `stretch` group.
