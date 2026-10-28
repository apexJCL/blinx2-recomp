# Design: enhance-menu-preview

## Context

Written by the reviewer on 2026-10-11 against cat `main` cbde3e8,
toolkit `posix-host/portability` f8696da and the CLI `main` e2ab3a0, from
the assessment in `assessment.md`. No separate review is needed.

Facts the design rests on:

- Every enhancement value is read once at startup and stored in
  `nv2a_host_opts` (kernel library, read by the backends on the walker
  thread), `xbox_PacingSetMode` (a global the lowered loops read each
  pass), `glow_configure` (two statics read on the guest thread) and the
  pack index (`nv2a_tex_pack`, used on the upload thread).
- The one code path every host and backend shares for input is
  `xbox_InputGetState()` (`src/input/input_core.c`): the guest's pad poll
  on its own thread. Keyboard keys reach `keyboard.c`'s table from three
  window procedures and are read there (`xbox_FramebufferKeyDown(vk)`).
- The three presenters each draw the frame as one textured quad and
  nothing else: `SDL_RenderCopy` (CPU, Metal readback), one triangle in
  `fbm_present` (CAMetalLayer), `present_blit` or `CopyResource` in the
  D3D11 flip (walker thread). Each has the frame's placement rectangle
  from `nv2a_present_rect`.
- The texture cache re-uploads only when a texture's hash changes; the
  render-target cache bakes the host size in at creation. Metal writes a
  target back to guest memory on eviction and expands guest bytes N× when
  it creates one; D3D11 loses an evicted target's pixels.
- The toolkit is C11 (`LANGUAGES C`, Objective-C for the two Metal
  files), with upstream's rule of no external dependencies; the CLI is
  standard-library Python 3.12+; the uv Python ships `tkinter` on the Mac
  but the CLI's own rule is stdlib-and-portable, and a browser is on
  every host.
- The pack format has a `flags` field per entry that a v1 reader refuses
  when non-zero, a `version` field, one informational `scale` for the
  file, and each entry's own width and height (so entries at different
  scales already coexist). Texels are A8R8G8B8 on disk and uploaded as
  BGRA8; both backends also support BC3 textures natively
  (`DXGI_FORMAT_BC3_UNORM`, `MTLPixelFormatBC3_RGBA` on macOS).
- The tracker item (coordinator, 2026-10-11): the Mission Objectives title, lines
  and "OR" are pre-rendered DXT3 images (512x32, 512x64) in `lng_us`
  `MIXF` containers holding `XPR0` resources, not glyphs; the builder read
  only `media` and `.dds`. The prototype fix on `fix/hud-pack-text` (CLI
  4ef7cd4 `enhance/xpr.py`, cat 1e5128f) takes the pack from 268 to 427
  entries and 145 to 372 MB at 4x. About 2,000 more baked text images
  (`sm_*` captions, `mgtu` tutorials, ...) would be several GB raw at 4x.

## Goals / Non-Goals

Goals: switch every existing enhancement live from a game-agnostic
overlay menu on every backend, persist the choice to the file the layer
read, show what a pack missed, keep stock and goldens byte-identical,
and let the owner choose filters and fonts by eye before building a
pack, reproducibly.

Non-goals: see the proposal. Also: a menu that remaps the guest pad
(that is `input-real-devices`; the Controls page binds host actions
only), localisation, and a GUI on the CPU path's GDI window. Mouse input
in the menu was a non-goal until 2026-10-22 and is now in v1 (R9).

## Decisions

### D1. Live values: a request queue applied at the flip (toolkit)

`nv2a_host_opts` stays the struct the backends read, and it stays
written on the walker thread only. The layer never stores into it after
init; it calls

```c
/* Queue a change; the backend applies it at its next flip and bumps
 * nv2a_host_opts_gen(). Any thread. */
void nv2a_host_opts_request(const struct nv2a_host_opts *o, unsigned mask);
/* At the flip, on the walker thread: apply pending requests. Returns the
 * mask of fields that changed. */
unsigned nv2a_host_opts_apply(void);
```

`mask` names the fields (`NV2A_OPT_SCALE`, `_FILTER`, `_FULLSCREEN`,
`_PACK`). The queue is one pending struct plus mask under a mutex; the
backends call `nv2a_host_opts_apply()` first thing in `on_flip`
(`metal_on_flip`, the D3D11 flip) and, when the returned mask has
`SCALE`, drop every render target (Metal: with the existing eviction
write-back so the next creation expands guest bytes at the new scale;
D3D11: `rt_release` each, the pixels lost as on any eviction) and every
texture (render-to-texture inputs are sized by scale). The null and CPU
backends call `apply` too, so a request never stays pending, and log the
"ignored" line again when scale changes.

Why at the flip: that is the one point where no target is bound, no
upload is in flight and the thread that owns every GPU object is
running. Why a queue and not a lock around every read: the backends read
the options in dozens of places; a torn read between scale and a target
size would be a hard-to-find bug, and at stock the cost must stay one
load (the pending flag).

Cost at stock: one atomic load of the pending flag per flip.

**Live render scale is in scope on both backends**, through this flush.
The visible cost is one frame whose render-to-texture inputs (the glow
chain, the hub's reflection) are rebuilt from scratch: Metal has the
guest copy, D3D11 draws them again on the next frame anyway (the game
redraws its post chain every frame). If the Proton check (tasks 6.x)
shows a persistent target that the game does not redraw, scale on D3D11
falls back to "applies at restart" on its menu line; that is a recorded
difference, not a blocker.

### D2. Texture pack: disable, kinds, generation and misses (toolkit)

`nv2a_tex_pack` gains:

- `nv2a_tex_pack_set_enabled(int)`, `nv2a_tex_pack_set_kind_enabled(kind,
  int)` (kind: `ART`, `FONT`, `TEXT`), both plain stores read by
  `nv2a_tex_pack_find` through one `unsigned` mask; `find` returns NULL
  when the pack or the entry's kind is off. Toggling goes through
  `nv2a_host_opts_request(..., NV2A_OPT_PACK)` so the flip bumps the
  **texture-cache generation** (`nv2a_tex_pack_gen()`): each `TexEntry`
  stores the generation it was uploaded under, and `tex_bind` treats a
  stale generation like a changed hash (re-upload). That is the only
  backend change for live pack toggling, identical in both files.
- `nv2a_tex_pack_load` reads v1 (flags must be 0) and **v2**: flags bits
  0-1 are the kind (`0` art, `1` `XRTP_KIND_FONT`, `2` `XRTP_KIND_TEXT`),
  bit 4 is `XRTP_FLAG_BC3` (D2b); any other bit is refused.
  `docs/formats/texture-pack.md` gets the v2 section; the CLI writes v2
  (D13). Why three kinds and not two: the baked text images the tracker item found
  are neither glyphs the font swap draws nor art the xBR kernel shapes
  well (anti-aliased text is better served by a smoother kernel or by
  staying at 2x), and a player may want sharp HUD art with the game's
  own text; the kind is the unit of both the toggle and the build policy.
- **Why kinds in the pack and not three packs:** one `fopen`, one index,
  one key, and the CLI already has every entry's provenance (`.dds` from
  `media` is art or the atlas; `.mix`/`XPR0` from `lng_*` is text). The
  runtime never guesses a kind from an image.
- Unload at run time is **not** offered (the texel buffers may be in use
  on the upload thread); "pack off" keeps the index and stops matching.
  Loading a different pack file at run time is also out: the menu lists
  the one configured pack and its state. (A mod manager that swaps packs
  loads them all at startup, D11.)
- **Misses.** When a pack is loaded, `tex_upload` reports every upload the
  pack did *not* match through `nv2a_tex_pack_miss(hash, w, h, color,
  levels)`: a 64-entry ring of distinct `(hash, w, h, format)` with a
  count each, kept in the kernel library; swizzled/DXT textures without
  mips are flagged "candidate" (what a pack could hold), the rest
  "linear/mip" (what it cannot). `RECOMP_TRACE=tex_pack` prints the ring
  every 600 flips (`[TEXPACK] miss 7A3F... 256x256 DXT5 x412 candidate`),
  and the menu's pack page shows the top of it (D6). No pack, no call.

Why misses in the kernel library and not the layer: the backends never
link the layer (the `nv2a_host_opts` pattern). Why a ring, not a map:
bounded memory, no allocation on the upload path.

### D2b. Pack size: per-kind scale and a BC3 payload (toolkit, CLI)

The prototype's 427 entries are 372 MB at 4x; the remaining
~2,000 text images would be several GB raw. Two levers, both in the pack
format and both already half there:

1. **Per-kind scale.** The header's `scale` is informational and every
   entry carries its own size, so a v2 pack holds text at 2x and HUD art
   at 4x with no reader change. The CLI's config gives each kind a scale
   (`[text] scale = 2` by default, D13); `scale` in the header becomes
   the art scale and the log line reads `scale 4 (text 2)`. A 512x32 DXT3
   caption at 2x is 128 KB of texels instead of 512 KB.
2. **BC3 payload** (`XRTP_FLAG_BC3`, per entry). The entry's texels are
   BC3 blocks (the DXT5 layout the source images already use), 1 byte
   per pixel instead of 4, on disk and in VRAM: both backends create the
   texture in the BC3 format and upload the blocks as they are, which is
   also cheaper than today's decode path. The CLI encodes with its own
   deterministic DXT5 encoder (range-fit over the block's colour
   extremes, the alpha endpoints from the block's min and max, integer
   only; ~150 lines) so two hosts give one pack. BC3 is lossy but the
   sources are DXT3/DXT5 already, and anti-aliased text survives it; the
   preview tool shows the BC3 result beside the raw one so the owner can
   leave it off for an entry (`[override] bc3 = false`). Default: BC3 on
   for `TEXT`, off for `ART` and `FONT` (the atlas's fine alpha edges and
   the small HUD pieces are not where the bytes are).

   Why BC3 and not deflate: deflate shrinks the file but not VRAM, needs
   an inflater in the C runtime (upstream's no-dependency rule; ~400
   lines to write or vendor), and is slower at first use; BC3 needs no
   new code in the runtime beyond the format enum and the block
   `bytesPerRow`, and `nv2a_tex_pack_texels` already reads a byte range.
   Why not BC1/BC7: BC1 has one-bit alpha (wrong for text), BC7 has no
   deterministic encoder small enough to write in Python.

   Estimate: 2,000 captions at 2x in BC3 come to about 250 MB on disk,
   read lazily per entry (the resident set is what a screen shows).
   The user confirmed the policy (text 2x + BC3, every pre-rendered text
   texture, the owner's languages only) on 2026-10-11.

3. **Per-language selection** (confirmed by the user, 2026-10-11: "the
   user chooses which language(s) to support and only those get
   built"). `game.toml [enhance.hud] languages = { us = ["lng_us"], jp =
   ["lng_jp"], ... }` names the archives per language (cat fills what
   the dump has; the prototype's `lng_us` patterns move under it); the
   config picks `[text] languages = ["us"]` and the preview tool offers
   the list with the size readout per language, so the owner builds only
   the sets they play in. Entries from an unselected language are simply
   not in the pack and miss at run time, as any unpacked texture does.

4. **Game-agnostic rule** (the user, 2026-10-11): any texture that is
   pre-rendered text is the `TEXT` kind and is built at 2x with BC3 by
   default, whatever game and wherever it lives. The CLI assigns the
   kind from provenance (`MIXF`/`XPR0` containers) and from the game's
   `[enhance.hud] text` patterns; it never guesses from pixels in this
   change (D16 assesses detection).

Everything here is additive to the branches: `xpr.py` and the
`lng_us` patterns land first; this change gives their entries a kind, a
scale and a payload format.

### D3. The overlay: a CPU-rasterised panel, one blit per presenter (toolkit)

*Revised 2026-10-21: layers, the presenter details and the stats strip are in R2.*
*Superseded 2026-10-22 (the user): the hand-rolled panel and the 8x8 font give way to microui with a TrueType font, one draw list and one renderer per backend (R7). The table below is kept as the first weighing; R7 re-weighs it.*

Options weighed against C11, no external dependencies, three presenters
on two threads:

| Option | Fit |
|---|---|
| Dear ImGui (+cimgui) | C++, enabling CXX in a C project, ~30k lines vendored, a renderer per backend, a font baker. Rejected. |
| Nuklear (single header C89, MIT/PD) | C fits, but ~25k lines, a vertex-buffer renderer per backend (Metal, D3D11, SDL), stb_truetype inside. Far more than a list menu needs. Rejected. |
| microui (rxi, MIT, ~1,100 lines C) | Small and C, but still a command stream (rect, text, clip, icon) to execute per backend and a font to supply. Would be the pick if we needed widgets beyond lists and sliders. Held in reserve. |
| **Hand-rolled CPU panel** | One rasteriser in the kernel library writes an RGBA8 buffer (rects, 8x8 bitmap glyphs scaled 2-3x, a highlight bar); each presenter uploads it as one small texture and draws one alpha-blended quad in the placement rectangle it already has. No per-backend drawing code beyond the blit; ctestable by reading the buffer. **Chosen.** |

This is the `recomp_cfg` precedent (own 900-line reader over tomlc17):
the feature needs a list, a slider, a toggle and a line of text, and
backends must agree by construction. The font is a public-domain 8x8
ASCII bitmap (`font8x8_basic`, Daniel Hepper, public domain) as a 1,024-
byte static array in `nv2a_overlay_font.h`, drawn at an integer scale
chosen from the panel height (2x at 480-line output, 3x from 960) so it
is legible at every `render.scale` and window size.

API (`src/kernel/nv2a_overlay.h`):

```c
struct nv2a_overlay_frame { const uint32_t *px; uint32_t w, h; uint64_t gen; };
/* The visible panel, or NULL when hidden: presenters call it at every
 * present and blit when non-NULL. Reading is lock-free: the writer
 * builds into a back buffer and publishes with one atomic swap. */
const struct nv2a_overlay_frame *nv2a_overlay_frame(void);
/* Writer side (the menu): begin a frame of w x h, draw, publish. */
void nv2a_overlay_begin(uint32_t w, uint32_t h);
void nv2a_overlay_rect(int x, int y, int w, int h, uint32_t argb);
void nv2a_overlay_text(int x, int y, int scale, uint32_t argb, const char *s);
void nv2a_overlay_publish(void);
void nv2a_overlay_hide(void);
```

Presenters, when `nv2a_overlay_frame()` is non-NULL:

- **SDL renderer** (CPU, Metal readback): one streaming `SDL_Texture`
  (ABGR8888) re-uploaded when `gen` changes, `SDL_RenderCopy` into the
  frame's rectangle with `SDL_BLENDMODE_BLEND`.
- **CAMetalLayer** (`fbm_present`): a second pipeline state with alpha
  blending, a shared `MTLTexture` refreshed when `gen` changes, drawn
  after the frame triangle with the same viewport.
- **D3D11** (flip, walker thread): the same, after `present_blit` or the
  copy; a blend state and a dynamic texture. When the stock path copied
  the frame straight into the back buffer, the overlay draw still runs
  (it is the only draw into the back buffer) and `s_sc_init = 0` as
  `present_blit` does.

The panel is sized to the *frame's* placement rectangle, not the window,
so it scales with `present.filter` and is the same picture on every
backend. The panel occupies the left 40% of the frame at most, so the
game stays visible behind it. Dumps and goldens never see it: the SDL and
D3D11 dump paths read the frame or the render target, never the back
buffer after the overlay (the D3D11 dump reads the back buffer only on
the stock copy path, and the overlay is drawn after `dump_frame()` there;
stated in the spec and checked by a `RECOMP_WINDOW_SHOT` plus `fb_dump`
pair in 6.x).

### D4. Input: a hook on `xbox_InputGetState`, the chord and the hotkey (toolkit)

*Revised 2026-10-21: the hook on `xbox_InputGetState` is replaced by the title-glue filter `xbox_enhance_pad_filter`, because cat never calls `xbox_InputGetState`. The chord and the hotkey become bindings of the `menu.open` action (R3). The neutral pad while open and the scripted-pad rule stand.*

`input_core.c` gains one hook pointer, NULL without the layer:

```c
typedef int (*xbox_input_hook)(DWORD port, XBOX_INPUT_STATE *st, DWORD rc);
void xbox_InputSetHook(xbox_input_hook h);
```

Called at the end of `xbox_InputGetState` with the merged state; the hook
may rewrite `*st` and the return. The menu's hook (D5) sees every port
on every host and backend, on the guest's poll thread, at the game's own
poll rate. That is deliberately not the window thread: the three window
procedures stay as they are, and the hook needs no SDL or Win32 code.

- **Pad chord**: `menu.chord`, default `"back+start"`, held for 400 ms on
  port 0 (either button alone passes to the game as usual; the chord is
  consumed when it triggers, and the two buttons are reported released
  until both are physically released, so the game never sees the pause
  press that opened the menu). BLiNX 2 uses START for pause and BACK
  alone in menus; both at once is unused. The chord is configurable per
  game because a title may use BACK+START (`game.toml` can set the
  default through its `config.default.toml`).
- **Keyboard hotkey**: `menu.hotkey`, default `"F10"`, read by the hook
  through `xbox_FramebufferKeyDown(vk)`; the key table of
  `RECOMP_KEYBOARD` binds no F-key, so there is no clash. `F10` is also
  outside Alt+F4, F11 (fullscreen on many hosts) and the F-keys the Deck
  maps.
- **While open**, the hook returns a neutral pad to the guest (buttons
  and triggers 0, sticks 0, packet number frozen so the title's edge
  detector sees "no change") and reads the physical state itself:
  D-pad/left stick for navigation, A/Enter to toggle or enter, B/Esc
  back, left/right to step a value, Y to save, BACK+START or the hotkey
  to close. Repeat at 150 ms then 60 ms on held directions.
- A scripted pad (`RECOMP_INPUT_SCRIPT`) never opens the menu: the hook
  reads only the host backend's state, so goldens cannot trip it even
  if a script pressed BACK+START.

### D5. The menu: pages, items, a registration API (toolkit layer)

*Extended 2026-10-21: the Mods, Stats, Controls and Debug pages are in R4.*

`src/enhance/enhance_menu.c` holds the state machine. Pure functions over
a `struct enhance_menu` take an input event and return the redraw
request, so the ctest drives them without a window. Items are a flat
table the layer fills from its own keys and a title adds to:

```c
enum enhance_item_kind { ENHANCE_ITEM_TOGGLE, ENHANCE_ITEM_CHOICE,
                         ENHANCE_ITEM_RANGE, ENHANCE_ITEM_INFO, ENHANCE_ITEM_ACTION };
struct enhance_item {
    const char *key;       /* "fx.glow": the config.toml key it persists to */
    const char *label;     /* "Glow" */
    const char *page;      /* "Game", "Render", "Pack", ... */
    enum enhance_item_kind kind;
    const char *const *choices;          /* CHOICE */
    double lo, hi, step;                 /* RANGE */
    const char *note;                    /* "applies at restart", shown dimmed */
    /* Called on the poll thread when the value changes; the item does
     * what it must (store an atomic, queue a request). */
    void (*set)(const struct enhance_item *, const char *value);
    const char *(*get)(const struct enhance_item *, char *buf, size_t n);
};
int enhance_menu_add(const struct enhance_item *it);   /* a title's items */
```

Pages and the toolkit's own items:

- **Render**: `render.scale` (1..4, live via D1; the note says "flushes
  the frame once"), `present.filter`, `present.fullscreen` (live:
  SDL_SetWindowFullscreen is queued to the SDL main thread through the
  existing frame event; the D3D11 window style change runs on the walker
  thread at the flip, where `present_resize` already lives),
  `present.pacing` (live: `xbox_PacingSetMode` is a store the loops read).
- **Pack**: `textures.pack` on/off (D2), `textures.font` and
  `textures.text` on/off (D2; each shown only when the loaded pack has
  an entry of that kind, else "none in this pack"), INFO lines: entries
  per kind, scales, BC3 count, hits, misses (candidates / other), the
  first four missed candidate hashes with size and format (the tracker item
  view: a `512x32 DXT3` row would have named the Mission Objectives
  title), "CPU path: pack ignored" on the CPU backend.
- **Game**: the title's items (cat: D9).
- **Stats** (INFO): flips/s, frame ms, backend, scale in force.
- **Controls** (late phase, user 2026-10-11): `menu.chord` and
  `menu.hotkey` as CHOICE items over the supported chords and F-keys,
  plus a "Capture" ACTION that reads the next chord held 400 ms (two
  pad buttons, any pair the title does not use is allowed; a single
  button is refused) or the next F-key and writes it to the item. The
  new binding is live at once and persists through Save like any key;
  the file is the override, the menu is the editor.
- **Save** (ACTION, also `Y`): D8. **Reset to stock** (ACTION).

Rendering: at most 12 rows, title, a highlight bar, the value right-
aligned, a dimmed note line, and a footer with the key hints. The state
machine is redrawn only on a change (the overlay `gen` moves), so an
open idle menu costs one blit per present and no raster.

### D6. Keys and logging

*Revised 2026-10-21: `menu.hotkey` and `menu.chord` are replaced by `[input.actions] "menu.open"` (R3); `overlay.stats` is added (R2). The `[ENHANCE] menu.enabled=...` line stays and names the `menu.open` bindings.*

| Key | Where | Values | Default | Env |
|---|---|---|---|---|
| `menu.enabled` | toolkit layer | bool | `false` in code; the bundle's `config.default.toml` sets `true` | `RECOMP_MENU` |
| `menu.hotkey` | toolkit layer | `"F10"`, `"F1"`..`"F12"`, `"none"` | `"F10"` | `RECOMP_MENU_HOTKEY` |
| `menu.chord` | toolkit layer | `"back+start"`, `"lthumb+rthumb"`, `"none"` | `"back+start"` | `RECOMP_MENU_CHORD` |
| `textures.font` | toolkit layer | `"on"`, `"off"`: the pack's FONT entries | `"on"` | `RECOMP_TEXTURES_FONT` |
| `textures.text` | toolkit layer | `"on"`, `"off"`: the pack's TEXT entries | `"on"` | `RECOMP_TEXTURES_TEXT` |

All config tier, `RECOMP_ENV_ENHANCE_KEYS`, naming rule `RECOMP_` + key.
The settings line gains nothing (every parser depends on it); the pack
line gains the kinds when a pack is loaded, and a new line follows it:

```
[ENHANCE] textures.pack=enhance/hud.pack (427 entries: 268 art, 1 font, 158 text; scale 4, text 2; 158 bc3) textures.font=on textures.text=on
[ENHANCE] menu.enabled=off
[ENHANCE] menu.enabled=on hotkey=F10 chord=back+start
```

(`golden.py`'s `ENHANCE_PACK_RE` matches `textures.pack=<value>` up to
the first space, so the longer line still reads `none` or the path.)
The golden harness (`ENHANCE_STOCK`) learns `menu.enabled` (stock `off`),
`textures.font` and `textures.text` (stock `on`). `golden.json` pins `RECOMP_MENU=off`
beside the other pins, so a Mac developer's `config.toml` with the menu
on cannot leak into a golden even if `RECOMP_ENHANCE_CONFIG=none` were
dropped by mistake.

**Off in code, on in the shipped file (decided by the user,
2026-10-11).** The rule is that a build with every key at its default
executes the stock code; a hook that inspects every pad poll and a
presenter branch that tests a pointer are not stock, so they must be
reachable only when a key says so. The bundle's `config.default.toml`
sets `[menu] enabled = true`, so the menu is there on first launch. The chord and hotkey are overridable in the
file (`menu.chord`, `menu.hotkey`) from the first phase and from the
menu's Controls page in a late one (D5).

### D7. The guest keeps running

The menu does not pause the guest: there is no game-agnostic pause, and
stopping the walker or the guest threads from the poll thread would
deadlock the one-CPU gate. While the menu is open the title sees a
neutral pad (D4), so the character stands still and a pause screen the
player opened before the menu stays. A title that wants a real pause
could have registered a callback to press its own pause; the user
decided on 2026-10-22 that the menu does not pause at all, so no such
callback is added (R4). The 3D keeps rendering behind
the panel, which is also what makes live preview of scale, glow and the
pack useful.

### D8. Persistence: differences-only writes to `config.toml` (toolkit layer)

Save targets **`config.toml`** (P1): the user's file is the set of keys
whose value differs from `config.default.toml`, so Save writes exactly the
changed keys and Reset deletes them. `recomp_cfg_patch(path, keys[],
values[], n, err)` in `recomp_cfg.c` reads the file as lines and, per
`table.key`, replaces the value on the existing `key =` line under its
`[table]` header (or dotted form), keeping any comment after it; appends
a missing key under its header and a missing header at the end; and
removes a key whose value is NULL (and its header once empty). It writes
`path.tmp`, flushes it to the disk and renames it (a symlinked
`config.toml` is written at its target), never reorders a comment, never
touches another key, and refuses (one line) when the file does not parse
first or when its output does not re-parse to the original plus the
changes. An array that keeps its item count is edited item by item, so
the comments between a binding list's items stay; one that grows or
shrinks is written on one line and loses them, and a comment line above
a removed key stays (as built, the tracker item review S2).
Values are written in TOML spelling (`scale = 2`, `filter = "linear"`,
`enabled = true`).

Save writes to the `config.toml` the layer read (the title file when
there was one, else the data root's); when the layer read no file
(`RECOMP_CONFIG=none`, the golden pin) the Save row reads "off
(RECOMP_CONFIG=none)". The environment stays on top (P1): the menu shows
an env-forced item's value with "(environment)" and keeps it read only,
refusing a change with "Set by the environment". A live change there
would be overridden at the next start, and Save would write a value the
player never saw take effect (as built in 3D, accepted by the tracker item
review S5; the first draft let the item change live and saved the file
value). `config.default.toml` is never written: it belongs to the install.

Unsaved live changes are lost at exit, by design (the menu shows
"unsaved" in the footer when any item differs from the files).

### D9. cat: game items and live-safe glow

`host_enhance_init` registers after `xbox_enhance_init`:

- `fx.glow` TOGGLE and `fx.glow_intensity` RANGE 0..2 step 0.1 on the
  Game page; `set` calls `glow_configure`, which becomes one atomic
  64-bit word (active flag and factor bits) that `glow_active`/
  `glow_factor` read together, so the wrapper never pairs a new flag
  with an old factor.
- `fps.mode` INFO: "lock30 (the only mode for this title)".

The chord stays the default (BACK+START is not a BLiNX 2 input), the
hotkey too. `config.default.toml` gets `[menu] enabled = true`,
`hotkey = "F10"`, `chord = "back+start"` and `font = "on"` under
`[textures]` (commented with the pack line). `docs/env.md` gets the four
rows; `scripts/test_glow.py` gains the atomic-word cases.

### D10. Backends agree

Both GPU backends take the same four changes (apply at flip, texture
generation, overlay blit, miss report) on one branch in one commit per
change; Metal verified on the Mac, D3D11 under Proton. The CPU rasteriser
builds, draws the overlay through the shared SDL presenter, applies
nothing for scale or pack and says so on the menu's Pack page; its GDI
window on Windows gets no overlay (recorded in TASKS as a gap, like its
present keys). The null backend applies requests so none stays pending.

### D11. The mod-manager shape (not built here)

The Pack page is one instance of a "source" page: name, on/off, kind
toggles, hits/misses. A later change adds `mods/<name>/mod.toml` (a pack
path, kind defaults, a description) loaded at startup into a list the
same page type shows one row per mod, with `textures.pack` becoming the
first mod. `nv2a_tex_pack` would then hold several indexes searched in
order. Nothing in this change prevents that; the menu API takes pages by
name and the pack module's `set_enabled` is per pack already in its
signature (`nv2a_tex_pack_set_enabled(int)` is written as `(pack 0)`).

### D12. The preview tool: `xbr enhance preview`, a local web UI (CLI)

Where it lives was weighed three ways:

| Option | Fit |
|---|---|
| CLI flags only (`enhance hud --filter --font ...` and look at the pack in the game) | Reproducible but blind: the ask is to *see* side by side. Rejected as the only path; the flags exist anyway (D13). |
| SDL/C app in the toolkit | Needs a font rasteriser, image decoders and a GUI in C; duplicates the Python `atlas`/`font`/`scaler` the pack is actually built with, so what you preview is not what you get. Rejected. |
| tkinter | Stdlib, but Tk is missing from some distro Pythons and on the Deck's system Python; image display through PhotoImage is slow and awkward; one more GUI toolkit to look at. Rejected. |
| **Local web UI from the CLI** | `http.server` on `127.0.0.1:<random port>`, one HTML page with a little JS, PNGs encoded with `zlib` from the *same* Python modules that build the pack, so the preview is byte-for-byte what `enhance hud` writes. Works on every host with a browser, no dependency, no network. **Chosen.** |

`xbr enhance preview [--config FILE] [--port N] [--no-browser]`:

- **Assets.** The picker lists the `[enhance.hud] textures` set from the
  dump (`hud.select` + `load_items`, cached; `.dds` and, through the
  the tracker item branch's `xpr.py`, the `MIXF`/`XPR0` images), grouped by kind
  (art, font, text) and language, with a few curated defaults pinned at
  the top from `game.toml [enhance.hud] preview = [...]` (cat: the font
  atlas, the life bar, the radar, a menu piece, the Mission Objectives
  title). A size readout per kind and language (entries, raw MB at the
  chosen scales, MB with BC3) shows what the build will cost before it
  runs. The owner can also drop a `RECOMP_TRACE=tex_pack` log on the
  page: its missed candidate hashes are joined against the dump's hashes
  and listed as "seen at runtime, not in the pack" (named when the dump
  has them, hash-only when it does not: the composed-at-runtime case).
  That is the class made visible: a `512x32 DXT3` miss named
  `lng_us:...` would have said where the title came from.
- **Upscale mode.** Side by side at the chosen scale (2, 3, 4), on a crop
  the owner drags (default 64x64) so a re-render is well under a second:
  `nearest`, `xbr` (lv1/lv2, `eq` threshold, the Y/U/V/A weights, alpha
  as an edge on/off), `epx` (Scale2x; 2x, 4x as 2x twice, 3x as
  Scale3x), `lanczos` (fixed-point, 3 lobes, integer kernel table so the
  pack stays reproducible), and `external` (D14). Each panel shows its
  time per texture, so the owner sees the cost of a full build. A
  per-texture override (`[override."dds/radar*"] filter = "nearest"`)
  is set from the panel. Every kernel stays integer: two hosts give one
  pack.
- **Font mode.** The stock atlas is decoded and its bands measured
  (`atlas.measure`); the page shows the stock row, the fitted row for
  the chosen face, and a free-text line ("Time: 00:42", the owner's own
  string) rendered through the real fit onto the stock glyph boxes, so
  what the game will draw is what the page shows. The selector offers
  (user, 2026-10-11):
  - the **installed faces** (`font.font_dirs` scanned for `name` ID 4);
  - **three curated OFL faces** (`fonts.toml` in the CLI: PT Sans Narrow
    Bold, Roboto Condensed Bold, Fira Sans Condensed Bold), each an
    entry of the google/fonts repository below with its sha256;
  - **the owner's own file**, dropped on the page or chosen with a file
    picker: the browser posts the `.ttf`/`.ttc`/`.otf` to the local
    server, which stores it in the cache under its sha256 and the face
    name it reads (CFF-outline `.otf` is refused with a line: the
    rasteriser reads `glyf` only), and the config records the file's
    name and sha so the build refuses a different file;
  - **a Google Fonts family**, by URL (`https://fonts.google.com/
    specimen/Roboto+Condensed`) or name. Of the ways to fetch a Google
    font, the one that needs no key, is documented as the source of
    truth and keeps the licence beside the file is the
    **github.com/google/fonts repository**: each family lives in
    `ofl/<slug>/` (or `apache/`, `ufl/`) with its TTFs, a `METADATA.pb`
    naming every file, style and weight, and the licence text
    (`OFL.txt`, `LICENSE.txt`, `UFL.txt`). The tool maps the family to
    its slug (lower case, no spaces), reads `METADATA.pb` over
    `raw.githubusercontent.com/google/fonts/main/`, picks the static
    file of the requested weight (a `static/` instance when the family
    is variable; otherwise the variable file's default instance, which
    is a plain `glyf` outline the rasteriser reads, said on the page),
    and downloads the TTF **and the licence file** into
    `~/.cache/xbr/fonts/<slug>/` (`XDG_CACHE_HOME`, `%LOCALAPPDATA%`),
    recording the family, file, commit-pinned URL, licence file name and
    both sha256s in the config. Rejected: the CSS2 API (returns `woff2`
    for a modern User-Agent and TTF only through an unofficial UA trick;
    no licence file; `woff2` needs brotli, not stdlib), the Developer
    API (needs an API key), the `fonts.google.com/download` zip
    (undocumented). Only the three licence directories are accepted, so
    every fetched face is OFL, Apache 2.0 or UFL and its licence text
    travels with it; the build copies nothing into the tree, and the
    config holds names, URLs and hashes only.
  Knobs: `size` (cap-height factor 0.8-1.2 within the
  box), `weight` (synthetic stroke -1..+2 px at the pack scale; a bold
  face is preferred and listed first), `dx`/`dy` offsets, `outline` px
  and colour, `shadow` dx/dy/alpha, `overhang` px the ink may leave its
  stock box by (default 0; the atlas has 1-3 px gaps, so 1 is safe for
  most rows and the page shows a red mark where two glyphs would touch).
  Tracking/kerning are not offered and the page says why: the game lays
  text out from its own table, so the atlas can only change what a glyph
  looks like inside its box.
- **Save** writes `enhance-hud.toml` (D13) and shows the `enhance hud`
  command that consumes it. **Build** is not in the tool: the pack build
  stays the CLI command, so the two never disagree.

The server is single-process, serves only `127.0.0.1`, random port
printed and opened with `webbrowser`, and exits when the page sends
`/quit` or on Ctrl-C. The page is one static HTML file in the package
with no external resources (no CDN, no fonts fetched by the browser: the
browser never renders a game font itself; every glyph image is a PNG from
Python, so the browser's font stack cannot alter what is shown).

### D13. The config `enhance hud` consumes

`enhance-hud.toml` (default `config/enhance-hud.toml` in the game tree,
tracked: it names fonts, filters and numbers, never game bytes):

```toml
schema = 1
[upscale]                   # art: the .dds HUD pieces
scale = 4
filter = "xbr"              # nearest | xbr | epx | lanczos | external
bc3 = false
[upscale.xbr]
level = 2
eq = 300000
weights = [48, 7, 6, 48]
[text]                      # baked text images (lng_*, sm_*, mgtu ...)
scale = 2
filter = "lanczos"
bc3 = true
languages = ["us"]          # keys of game.toml [enhance.hud] languages
[override."dds/radar*"]     # fnmatch over entry names, any kind
filter = "nearest"
bc3 = false
[font]
face = "PT Sans Narrow Bold"   # full name; found installed or in the cache
source = "https://.../PTSans-NarrowBold.ttf"   # optional: the curated entry
sha256 = "..."                 # of the file used; the build refuses another
size = 1.0
weight = 0
dx = 0
dy = 0
outline = 0
shadow = [0, 0, 0.0]
overhang = 0
```

`xbr enhance hud --config FILE` reads it (default the file above when
present; `--scale`, `--font` still override the art and font values),
applies per kind the scale, filter and BC3 choice, then the overrides
per entry, the font knobs in `atlas.render`, writes **v2** packs with the
kind flags (`FONT` on the atlas entry, `TEXT` on every `MIXF`/`XPR0`
image and on entries the game's `[enhance.hud] text` patterns name) and
`XRTP_FLAG_BC3` where chosen, and records the config's path and sha256
in `hud-pack.toml` with per-kind counts and sizes. Without a config the
command does what it does today for art and the atlas (xbr lv2, the
game's font, no knobs, no BC3), so existing packs rebuild with the same
texels (the test asserts the entry payloads are byte-identical; the
header version and kind flags differ by design); text entries without a
config take the `[text]` defaults above. `scaler` gains 3x for
xbr (the lv2 kernel's lines at 3x, exact rationals as now) and the
`epx`/`lanczos` kernels in their own modules; the package `--hud-pack`
copy is unchanged.

### D14. External upscalers, and what the 2026-10-06 rule meant

The user clarified on 2026-10-11 that the 2026-10-06 "never a CNN" rule
was about cost: nothing bundled or default may call an API or a service
that can incur a charge. Any upscaler is allowed; **open-source, locally
run ones come first**, and a paid or third-party service is the owner's
own opt-in, used at their own responsibility. The design is therefore:

- The CLI's built-in filters stay deterministic and integer (xBR, EPX,
  Lanczos): they are the defaults, they need nothing installed, and two
  hosts give one pack.
- `filter = "external"` with `[upscale.external] command = "realesrgan-
  ncnn-vulkan -i {in} -o {out} -s {scale}"` runs the owner's own program
  per texture on PNG files in a temp dir. The preview tool's filter list
  shows a **curated set of local open-source upscalers** as presets
  (Real-ESRGAN ncnn-vulkan, waifu2x ncnn-vulkan, Upscayl's CLI; each
  with its licence and a "found on PATH / not found" state) that fill
  the command template; it never downloads or runs one by itself, and
  nothing in the CLI or its defaults contacts a network service. An
  owner who wants a remote or paid service writes that command
  themselves; the page says so in one line beside the field.
- The manifest records `kernel = "external:<basename>"` with the tool's
  sha256 and the note "not reproducible across hosts"; `hud-pack.toml`
  keeps the command. The golden check is unaffected (a pack is non-stock
  whatever made it).
- Phase order follows the rule: built-in filters first (phase 7), the
  external presets in the same phase behind the template, and no CNN is
  ever vendored.

### D15. Legal boundaries in code

- The preview server binds `127.0.0.1` only and never writes a decoded
  image to disk; PNGs live in memory for the response. `enhance-hud.toml`
  is the only file Save writes, and `audit-public.sh` already flags
  `*.pack`; it gains nothing new because the config holds no game data.
- Fonts: the curated list is OFL 1.1 only, each entry with its licence
  URL; the download goes to the per-user cache with its sha checked;
  nothing is vendored; `NOTICE` is unchanged.
- Tests build their own archives, DDS blocks, a synthetic TrueType font
  and packs as today; the preview tests drive the HTTP handlers in
  process with `http.client` against a synthetic game tree.

### D16. Re-rendering baked text in the chosen face (assessed; a late phase)

The user asked (2026-10-11) that typography stay consistent across all
assets: find pre-rendered text in textures and re-render it in the
selected font, fine-tunable like the atlas. Assessment:

- **What exists.** `atlas.measure` already segments an image into ink
  bands and column runs, groups runs into glyphs given the string, and
  fits a face's glyph into each stock ink box at scale; `atlas.render`
  draws it with the knobs of D12. A baked caption is the same problem
  with three unknowns: *which images are text*, *what the string is*,
  and *what style* (fill, outline, glow, gradient, shadow) the game
  baked in.
- **Finding text.** Provenance first (`MIXF`/`XPR0` containers and the
  game's `text` patterns, D2b.4) covers the known sets with no guess. A
  pixel heuristic for the rest (one or two ink bands of glyph-sized runs
  on a flat or transparent background, consistent cap height) tags
  candidates for the owner to confirm in the preview tool; it never
  decides alone. OCR is not needed to find text.
- **Recovering the string.** Three sources in order: a per-language
  table the owner fills in the preview tool (`config/text-strings.toml`:
  entry name, string, language; shareable, no game bytes); an optional
  local OCR (Tesseract, Apache 2.0, if installed; the same external-
  command pattern as D14) that drafts the strings for the owner to
  correct; and the game's own string tables where a later analysis finds
  them (BLiNX 2's `lng_*` archives likely hold the text the images were
  rendered from, which would make this exact; not investigated here). A
  string that does not explain the runs (the grouping cost of
  `group_runs` is the test) keeps the upscaled pixels and is listed.
- **Matching the style.** Measure from the stock image: fill colour or
  vertical gradient (per-row median of the glyph interior), outline
  width and colour (the ring between the fill mask and the alpha
  extent), glow (alpha falloff beyond the outline, fitted to a Gaussian
  radius), shadow (an offset copy in the alpha). Re-synthesise from the
  re-rendered glyph coverage with the D12 knobs (`outline`, `shadow`)
  plus `glow` and `gradient`. The MISSION OBJECTIVES title (white fill,
  dark outline, soft glow) is the shape this targets; a title with a
  texture fill or a hand-drawn logo is refused and kept as pixels.
- **Layout.** Each baked glyph keeps its stock ink box times the scale
  (as the atlas does), so the game's placement is untouched; `overhang`
  allows the chosen face to breathe into the gaps.
- **Feasibility: medium-high effort, no blocker.** The fit machinery
  exists; the work is the string source, the style measurement and the
  owner's review loop in the preview tool. The risk is volume (2,000
  images) and taste (a glow that does not match); both are bounded by
  making it per-entry opt-in with the upscaled image as the fallback.
- **Placement.** A spike first (one screen: the Mission Objectives title
  and lines), then phase 10 behind `[text] rerender = true` and per-entry
  overrides; never on by default.

### P1. Configuration layering: `config.default.toml` + `config.toml` (decided 2026-10-11)

The user settled the first draft's open proposal the same day, and its
four sub-questions too. `enhance.toml` becomes a generic **`config.toml`**
over a shipped **`config.default.toml`**; Save writes only `config.toml`,
as differences; the environment stays on top. The rename is its own
change and **lands before the menu** (phase 2), so Save (D8) is built
against `config.toml` from the start and no menu code ever targets the
old file.

**Today.** `enhance.toml.default` is a *template*: the launcher copies it to
`config/enhance.toml` on first launch, refreshes `config/enhance.toml.default`
every launch for comparison, and points the runtime at the copy with
`RECOMP_ENHANCE_CONFIG` (SteamOS `launch.sh:72-104`, Windows
`launcher.c:189-198`). The runtime reads one file (or title + root), never
the `.default`.

**Layering** (lowest to highest):

1. code defaults (every key's stock value, as now);
2. `<exe dir>/config.default.toml`, shipped with the bundle and refreshed on
   every install: *read by the runtime*, not copied;
3. `<root>/<title>/config.toml` then `<data>/config/config.toml`, the user's
   files, created as a comment header on first launch; Save writes the one
   the layer read, and only keys whose value differs from layer 2 (Reset
   deletes the key);
4. **the environment, on top** (the user, verbatim): "an environment
   variable can and will override whatever's on config.toml - this helps in
   automated testing on active environments. For example, if I'm doing a
   playthrough of a game and find a bug, you can change the env variable
   and peek into what's happening without messing up my settings." Save
   never writes an env value; the menu marks an env-forced item
   "(env: RECOMP_...)", shows the forced value, and lets the player change
   it live but says the variable wins again at the next start (D8 holds).

**Scope: enhancements only** (the user, verbatim): "it will only adjust
enhancements that are not available in the base game. Remember this menu
is meant for more like a modding experience, just the mere fact of
rendering at 2x is a mod on itself." So:

- `config.toml` and the menu hold the enhancement and mod keys only:
  `[render]`, `[display]`, `[present]`, `[textures]`, `[menu]` and the game's
  own enhancement tables (`[fps]`, `[fx]` in cat), later the mods list (D11).
- **No `launch.env` row moves.** `RECOMP_PB_BACKEND`, `RECOMP_WINDOW_SCALE`,
  `RECOMP_PRESENT_VSYNC`, `RECOMP_HEADLESS`, `RECOMP_HOST_PAD`, `RECOMP_RUMBLE`
  and `RECOMP_KEYBOARD` are how the host runs the game, not changes to it;
  they stay environment settings in `config/launch.env` and off the menu.
  The first draft's `[video]` and `[input]` tables are withdrawn.
- Every planned menu item checked against the rule: `render.scale`,
  `present.filter`, `present.fullscreen` and `present.pacing` are the layer's
  E1 and pacing enhancement keys (the console had no window, filter or
  host core to free, so each is a change to how the game is shown or run
  that the base game does not offer; they stay); `textures.pack`,
  `textures.font`, `textures.text` and the pack page are mods; `fx.glow`
  and `fx.glow_intensity` are the game's enhancement keys; `fps.mode` is an
  INFO line for the layer's own key; `menu.chord` and `menu.hotkey` are the
  menu's keys; Stats is read-only. Nothing on the menu edits a base-game
  option (the game's own settings screen stays the place for its sound,
  vibration and the like) or a `launch.env` host setting.

**Migration: automatic, no notice** (the user: no existing user base).

- Runtime: `enhance_cfg_init` reads `config.default.toml` then the
  `config.toml` files. If no `config.toml` exists and an `enhance.toml`
  does at the same place, it is renamed to `config.toml` (the keys are the
  same; a key equal to the default is harmless under differences-only and
  is dropped at the next Save) and one line says so. No compatibility
  window: the next release reads `config.toml` only.
- `RECOMP_CONFIG` replaces `RECOMP_ENHANCE_CONFIG`; the old name stays as
  a `LEGACY` entry in the env table row, which is what the table already
  does for renamed variables at no cost, so it is kept. `none` keeps its
  meaning for goldens.
- Launchers (SteamOS `launch.sh`, Windows `launcher.c`, the macOS app):
  stop copying the template; keep `config.default.toml` beside the
  executable (refreshed by the install itself); rename an existing
  `config/enhance.toml` to `config/config.toml` on the first launch after
  the upgrade; delete `config/enhance.toml.default`; set `RECOMP_CONFIG`.
  The uninstaller's file list follows.
- SteamOS installer: `config.default.toml` is a top-level bundle file (the
  `enhance/` subdirectory fix, TASKS (d), is unrelated and stays).
- `blinx2 package`: stages `config.default.toml`; `--hud-pack` writes the
  `[textures]` table into it, which now *applies* on an upgrade too (the
  "copy the line yourself" step in `packaging.md` §Enhancements goes away).
- Docs: `packaging.md` §6, the README `Configuration` section, the
  toolkit's `enhance-config.md` (renamed `config.md`, with the layering
  table), `docs/env.md` (`RECOMP_CONFIG` row with the legacy name).

**Golden harness and pins: unchanged.** Env on top keeps every pin
working as today: the golden configuration pins `RECOMP_CONFIG=none`
(`RECOMP_ENHANCE_CONFIG=none` still accepted through the legacy name)
plus the per-key pins; `game.toml [golden] enhance_stock` and the CLI's
`ENHANCE_STOCK` table need no change beyond the variable's name.

**Also decided** (the user, 2026-10-11):

3. `config.toml` holds **differences only** from `config.default.toml`:
   Save writes a key, Reset deletes it, the default file carries the
   comments the player reads.
4. **The per-title file stays** in the layering (`<root>/<title>/config.toml`
   over the data root's): already implemented, cheap, and a multi-title
   data root may want it.
5. A developer tree reads **`config/config.toml` in the repository**
   (gitignored), like the bundle, with `config.default.toml` from the
   build directory.
6. The rename is **its own openspec change, landed before the overlay and
   menu** (phase 2). It follows the live plumbing (phase 1) rather than
   preceding it because the two touch disjoint code (phase 1 the backends
   and the pack module, phase 2 the layer's reader, the launchers and
   packaging), phase 1 adds the `textures.font`/`textures.text` keys that
   the first `config.default.toml` should already carry, and phase 1 is
   what gives the entries a kind and a smaller pack right away;
   ordering the reader change second costs nothing since the menu, the
   only consumer of Save, comes after both.

## Revision 2026-10-21: live switching, the overlay, host actions

The user asked on 2026-10-21 for three things on top of this change:

- which enhancements can switch on the fly;
- an in-game overlay for more than the menu (mods, frame stats, debug);
- bindings for host features (the free camera of the tracker item first), with
  chords on the original pad and the extra buttons of the Deck and
  modern pads.

R1 to R6 below record the answers, checked against the toolkit at
`posix-host/portability` 30fbb38e and cat `main`. They supersede the parts
of D3, D4, D5, D6 and the Migration Plan that they name. Everything else
in this design stands.

Facts that changed since the 2026-10-11 draft:

- Phase 2 (P1) landed as its own change (`archive/2026-10-17-config-layering`).
- The mod API v1 landed (`src/enhance/mod.h`).
- The free camera (cat `free-camera/feature`) is the first mod.
- Hor+ landed, so `display.aspect` is owned by the merged code.
- SDL3 had not landed on 2026-10-21. **It has since landed**
  (Done; toolkit 3b0a4540 "sdl3: the POSIX host on SDL3 instead
  of SDL2", sysroot SDL 3.4.16), so phase 3 is written against SDL3
  names from the start (the user, 2026-10-22; R3's backend table).
- **cat does not call `xbox_InputGetState`.** It replaces the XDK XInput
  entry points (`recomp_manual.c` ~183-240, the `sub_00368457` wrapper),
  and `pad_input.c` `cat_pad_get_state` merges the pad, the script and
  the keyboard and mouse itself. b3, ssx3, jsrf and spartan reach
  `xbox_InputGetState` through `usb_gamepad.c`. D4's hook on
  `xbox_InputGetState` would therefore never run in BLiNX 2. R3 replaces
  it with a title-glue entry that both paths call.

### R1. Live-switch audit

Classes:

- **L** live at the next flip;
- **F** live with a cache, target or swap-chain flush (one frame or a
  few rebuilt);
- **S** at a later game point (next stage, scene or activation);
- **R** restart only.

"Today" is the code as merged. "After" is the code once this change's
phases land. Every key is off or stock by default, and nothing below
changes a stock run.

#### Toolkit keys (every game)

| Key | Today | After | Mechanism, cost | What blocks more |
|---|---|---|---|---|
| `render.scale` | F | F | `NV2A_OPT_SCALE` at the flip. `scale_drop()` drops targets, depth and textures. Metal writes back first. A few frames are rebuilt. | D3D11 scale needs a confirmation on Proton (6.x). If any target keeps stale pixels, D3D11 falls back to R. |
| `render.aniso` | R | L | `nv2a_stage_aniso()` already reads `s_host_opts.aniso` at every draw, and samplers are keyed on it. It only needs a new `NV2A_OPT_ANISO` mask bit. Cost: one new sampler-cache entry per state. | The mask bit. |
| `present.filter` | L on D3D11; stored only on SDL and Metal | L | D3D11 already reads `nv2a_host_opts()` at each present. The SDL loop caches `filter` once at start (`fb_present_sdl.c` ~544) and passes it to `fbm_present`, so it must read the option at each present and call `SDL_SetTextureScaleMode` when it changes. Cost: none. | The cached local. |
| `present.fullscreen` | stored only | F on SDL and Metal; D3D11 in 3C (the user, 2026-10-22: in v1 scope) | SDL (Metal, CPU): `SDL_SetWindowFullscreen` on the SDL main thread when the host-opts gen moves. D3D11: a `WS_POPUP` or overlapped style swap with `SetWindowPos` on the window thread, then `ResizeBuffers` at the next flip. Cost: one swap-chain resize. | Today it is read only at window creation. D3D11 is the larger half (R5 phase 3C). |
| `present.pacing` | R (read at init) | L | `xbox_PacingSetMode` is a plain store that the loops read. The menu calls it. Cost: none. | Nothing beyond the menu item. Goldens fail a `sleep` run, as today. |
| `present.surface` | R | R | Picks the presenter (layer or renderer; internal or window size) at window creation. | It would need the presenter torn down and rebuilt. Not worth it: the menu says "applies at restart". |
| `display.aspect` | R | R in this change; F after F-5 | Targets are padded at creation, the shader key carries it (`key[36]`), and the window takes its shape. It needs a `scale_drop`-style flush plus a window resize, through a new `NV2A_OPT_ASPECT` bit. | Hor+ is merged. F-5 adds the flush. A per-game projection patch made at stage load (cat's cull-plane wrapper) would make it S for that game. F-5 decides. |
| `display.movie` | R | L | Read at each movie draw. It needs an `NV2A_OPT_MOVIE` bit. | The mask bit. |
| `display.overscan` | R | L | Read at each present on D3D11 and Metal, and by the SDL renderer's placement. It needs an `NV2A_OPT_OVERSCAN` bit and is refused with a wide aspect, as at start. | The mask bit. |
| `textures.pack` on or off | F | F | `NV2A_OPT_PACK` bumps `nv2a_tex_pack_gen()`, and resident textures re-upload at their next bind. | None. |
| `textures.pack` path | R | R in this change; F after F-1 | Load the new file on a worker, then swap the pack pointer at the flip and bump the gen. The old pack is freed one flip later. | Uploads hold entry pointers inside a flip, so it can only swap at the flip. Low value. Follow-up, not in R5. |
| `textures.font`, `textures.text` | F | F | Kind mask plus the gen (phase 1). | None. |
| `input.keyboard`, `input.mouse` | R | L | Flags read at each poll. A setter is enough. | The setter. |
| `input.mouse_release_key` | R | L | Read at each poll. | The setter. |
| `input.mouse_look`, `mouse_sensitivity`, `mouse_invert_x`, `mouse_invert_y`, `mouse_min_deflection`, `wheel_pulse_ms`, `stick_ramp_ms`, `walk_scale` | R | L | `enhance_input.c` reads them once into the mouse and ramp config. A setter publishes a new config struct that the poll reads. Cost: none. | The setter. |
| `input.walk_key` | R | F | A key in the effective key map. It is rebuilt with `[input.bindings]` (pointer swap) and re-checked for clashes. | The table swap. |
| `input.mouse_capture` | R | L | Grab mode (`focus`, `click`, `never`; the shipped default becomes `click`, R9). A change re-grabs the window on the SDL main thread (`SDL_SetRelativeMouseMode`) or the Win32 window thread, so it is live (as built in 3D, the tracker item review N4; the first draft had it at the next flip). | Window-thread work, like fullscreen. |
| `[input.bindings]` | R | F | Rebuild the VK table, then swap it on the poll thread (one pointer, RCU-style; the old table freed at the next poll). | Today `enhance_input_init` writes the live table in place, which is unsafe during a poll. |
| `menu.*`, `[input.actions]` (new) | n/a | F | Same swap as the bindings (R3). | None. |
| `overlay.stats` (new) | n/a | L | Visibility bit of the stats layer (R2). | None. |

#### Game and mod keys

| Game | Key | Today | After | Mechanism, cost | What blocks more |
|---|---|---|---|---|---|
| cat | `fx.glow`, `fx.glow_intensity` | R (statics set once) | L | `src/glow.c` statics `s_active` and `s_factor`. The `sub_0005B7D0` wrapper reads them every frame. Pack them in one atomic word (D9). | Two plain statics written in two stores. |
| cat | `fps.mode` | R | R | Only `lock30` exists, so the key is informational. | No other mode is implemented (60 fps is the tracker item). |
| cat | `camera.free` on or off | R | L | `free_camera.c` init returns before registering `on_frame` and `batch_filter` when the key is off. Fix: always register them when the mod is built in, and gate both on an atomic. Turning it off runs the toggle-off path, which restores the camera, drops freeze and shows the HUD. Cost: one atomic load per frame and per batch. | Registration is init-only in API v1 (max 16 frame callbacks, max 8 filters). |
| cat | `camera.free_speed`, `camera.free_look_sens` | R | L | Statics read every frame. Make them relaxed atomics. | Nothing beyond the setter. |
| cat | `camera.free_hud` | S | S | Read when the camera turns on. A change applies at the next activation. | It is a choice made at entry, so S is the right class. |
| cat | `camera.free_toggle`, `free_hud_key`, `free_freeze_key`, `free_reset_key` | R | L, as actions | Polled with `xbox_FramebufferKeyDown` and rising-edge detection. They move to R3 actions (rebindable live). The old keys stay as aliases. | R3. |
| b3, ssx3, jsrf, spartan, kuf | (none) | | | Their `config.default.toml` holds render, display and present only (b3 also a commented `[textures]`). kuf (`kuf/project`) has no game keys either. No game keys, mods or hotkeys. | Nothing to do. The overlay and actions reach them through the toolkit. |

Counts over the 26 classified rows (20 toolkit, 6 game; the row for the
other games holds no key). A row that holds several keys counts once.

| Class | Today | After this change | After F-1 and F-5 |
|---|---|---|---|
| L | 1 (`present.filter` on D3D11 only) | 13 | 13 |
| F | 3 | 8 | 10 |
| S | 1 | 1 | 1 |
| R | 21 | 4 | 2 |

- **L after this change (13):**
  - toolkit: `render.aniso`, `present.filter`, `present.pacing`,
    `display.movie`, `display.overscan`, `input.keyboard` and
    `input.mouse`, `input.mouse_release_key`, the eight mouse and
    stick-feel keys (one row), `overlay.stats`;
  - game: `fx.glow` with its intensity, `camera.free` on or off, its
    speed and sensitivity, its four keys as actions.
- **F after this change (8):** `render.scale`, `present.fullscreen` (SDL
  and Metal; D3D11 in 3C), the pack toggle, `textures.font`
  and `text`, `[input.bindings]`, `input.walk_key`,
  `input.mouse_capture`, `menu.*` and `[input.actions]`.
- **S (1):** `camera.free_hud`.
- **R after this change (4):** `present.surface` and `fps.mode`, which
  stay restart-only, plus `display.aspect` (until F-5) and the pack path
  (until F-1).

Notable blockers:

- missing `NV2A_OPT_*` mask bits (aniso, movie, overscan, aspect);
- the SDL loop's cached filter;
- fullscreen applied only at window creation (D3D11 hardest);
- in-place rewrites of the input binding table;
- mod API v1 allowing callback registration only in `init`;
- `display.aspect` waiting on the Hor+ change.

The menu marks every item with its class: a dot for L or F, "next stage"
for S, "applies at restart" for R.

### R2. The overlay, revised (supersedes D3's single panel)

*Revised 2026-10-22 (the user): what a layer holds changes. The layers,
their writers, the triple buffer, the `visible` mask, where each
presenter draws and the dump rules below all stand. A layer's slot now
holds a draw list (vertices, indices, draw commands) built with microui
and a TrueType atlas, instead of an RGBA8 raster with `font8x8`, and each
presenter runs one small geometry renderer instead of one quad blit
(R7). A fourth layer, `CURSOR`, is added (R9). The API block below is the
2026-10-21 shape; R7 gives the new one.*

D3's choice stood on 2026-10-21: a hand-rolled CPU-rasterised RGBA8
buffer, the public-domain `font8x8_basic`, and one alpha-blended quad per
presenter. Checked against today's presenters, it changes in four ways.

**Layers, not one panel.** The overlay module keeps three layers. Each has
its own double buffer, `gen` and writer thread:

| Layer | Writer | Content | Input |
|---|---|---|---|
| `MENU` | poll thread (the R3 hook) | the menu pages (R4) | captures the pad (neutral to the guest) |
| `STATS` | the presenting thread, at 2 Hz (composed there) | one small strip in a corner: fps, frame ms (average and worst of the last second), flips/s, pacing, scale, backend | none |
| `TOAST` | the presenting thread, from a line queue any thread may push to | a short line for 2 s ("Free camera on", "Saved", "Scale 2x") | none |

Each layer has exactly one writer thread, and the reader is the
presenting thread. A layer is a **triple buffer**: the writer draws into
its own back slot, then publishes by swapping it with the "ready" slot
in one atomic exchange of a packed index word (with a fresh bit). The
reader takes "ready" by swapping it with its "front" slot when the fresh
bit is set. Neither side ever waits, and a slot is never written while
it is read.

The STATS and TOAST layers are composed by the presenting thread itself.
`nv2a_overlay_toast` from any thread only pushes a line into a small
lock-free ring (8 lines, the oldest dropped), which the presenting
thread drains at 2 Hz or when the ring's count moves. Only the MENU layer
has a writer (the poll thread) other than the reader.

Drawing calls take the canvas they draw on, so no global "current layer"
can race between two writers. The presenter reads one atomic `visible`
mask. When it is 0 the present runs as today (one load and one branch),
which is the zero-cost-closed rule. When it is non-zero the presenter
draws the visible layers in a fixed order (STATS, TOAST, MENU), at most
three quads, re-uploading a layer's texture only when its `gen` moved.

The overlay, `nv2a_stats` and the R3 filter compile only under
`XBOXRECOMP_ENHANCE`. A build without it has none of their call sites.

```c
enum nv2a_overlay_layer { NV2A_OVL_STATS, NV2A_OVL_TOAST, NV2A_OVL_MENU, NV2A_OVL_COUNT };
struct nv2a_overlay_frame { const uint32_t *px; uint32_t w, h; int x, y; uint64_t gen; };
struct nv2a_overlay_canvas;                                 /* one writer's back slot */
uint32_t nv2a_overlay_visible(void);                       /* one atomic load */
/* Reader side (the presenting thread): the newest published frame, or NULL. */
const struct nv2a_overlay_frame *nv2a_overlay_acquire(enum nv2a_overlay_layer l);
/* Writer side (the layer's one writer thread). */
struct nv2a_overlay_canvas *nv2a_overlay_begin(enum nv2a_overlay_layer l,
                                               uint32_t w, uint32_t h, int x, int y);
void nv2a_overlay_rect(struct nv2a_overlay_canvas *c, int x, int y, int w, int h, uint32_t argb);
void nv2a_overlay_text(struct nv2a_overlay_canvas *c, int x, int y, int scale,
                       uint32_t argb, const char *s);
void nv2a_overlay_publish(struct nv2a_overlay_canvas *c);
void nv2a_overlay_hide(enum nv2a_overlay_layer l);
void nv2a_overlay_toast(const char *fmt, ...);             /* any thread: queues a line */
```

`x` and `y` place the layer in frame-rectangle units (0..1000), so the
same numbers land in the same place on every backend.

**Per presenter, against today's code:**

- **SDL renderer** (`src/video/fb_present_sdl.c`, the SDL main thread; CPU and the
  Metal readback): the loop wakes on a frame event or every 100 ms. A
  layer whose `gen` moved sets `dirty` and posts the frame event, so a
  menu edit shows while the guest is in a loading pause. The overlay
  draws after `SDL_RenderTexture(frame)` (SDL3) and before `shot_save`, so window
  shots include it (wanted for README shots). `fb_dump` reads the guest
  frame, not the renderer, so it never sees the overlay.
- **CAMetalLayer** (`src/video/fb_present_metal.m`, `fbm_present`): a second
  blended pipeline state and one `MTLTexture` per layer, drawn in the
  same render pass after the frame triangle. `fbm_present` gains a
  `const struct nv2a_overlay_frame *const *layers` argument (NULL when
  `visible == 0`), so the SDL loop stays the only reader of the overlay
  state. `RECOMP_WINDOW_SHOT` reads the drawable and includes it, while
  the Metal frame dump reads the render target and does not.
- **D3D11** (`src/d3d/nv2a_pb_d3d11.c`, the walker thread at the flip): draw after
  `present_blit` or the stock copy **and after `dump_frame()`**, then
  `IDXGISwapChain_Present`. On the stock copy path the overlay draw is
  the only draw into the back buffer, so it sets the viewport and render
  target itself and leaves `s_sc_init = 0`, as `present_blit` does. The
  D3D11 present is on the walker thread, so a menu edit shows at the next
  guest flip. That is fine while the guest flips. During a hang the menu
  is frozen anyway. **Gap (backends agree):** on SDL and Metal a menu
  edit shows within 100 ms even when the guest does not flip, but on
  D3D11 only at the next guest flip. It is recorded in TASKS. A
  present-only path on the walker when no flip came for 100 ms is a
  follow-up (F-9).
- **CPU GDI window** (`src/video/fb_present.c`, Windows CPU only): no overlay. This
  is recorded in TASKS and follows the CLAUDE.md rule for the CPU path.

**Goldens and dumps.** `RECOMP_FB_DUMP`, `fb_dump_at`, `d3d11_dump` and
the Metal dump never contain a layer (above). `RECOMP_WINDOW_SHOT` has
no D3D11 implementation today, so the D3D11 window checks use a host
screenshot. **Gap:** this is recorded in TASKS under backends-agree, and
a D3D11 back-buffer shot after the overlay draw is F-10. The golden pins
`RECOMP_CONFIG=none`, so `menu.enabled`, `overlay.stats` and every
`[input.actions]` default are off in code. `golden.py ENHANCE_STOCK`
learns `menu.enabled=off`, `overlay.stats=off` and `actions hook=off`. A run whose log shows
any of them on fails unless `--allow-enhance` names it. Window shots include
the overlay, which is wanted for README shots and the 3.x checks.

**Text.** *Superseded 2026-10-22 by R7 (a TrueType face through
stb_truetype, UTF-8 labels within a fixed range).* The 2026-10-21 text
was: `font8x8_basic` at integer scale, ASCII only, with microui held back
until the pages outgrew the list.

### R3. Host actions (new; supersedes D4's hook seam, chord and hotkey and D6's `menu.hotkey` and `menu.chord`)

A game-agnostic layer in `src/enhance/enhance_actions.{c,h}` that turns
host input into named **actions**. Actions are not guest buttons and
never remap the pad the title sees. That job stays with
`[input.bindings]` (keyboard to pad) and the parked cat
`spike/input-selection` (`pad<N>.<control>` remaps, per-port source,
GUID pins). Both of those feed the merged guest state. Actions read the
host state beside it and only ever *remove* presses from it (a consumed
chord).

**Registry.** The toolkit registers its own actions. Mods register theirs
through the mod API (below).

| Action | Owner | Default bindings | Kind |
|---|---|---|---|
| `menu.open` | toolkit | `F10`, `guide+a` (R10; the user, 2026-10-22), plus a per-game fallback chord from `config.default.toml` | press (toggle) |
| `overlay.stats` | toolkit | none (reached from the Stats page; F12 is Steam's screenshot key under Proton) | press (toggle) |
| `shot.window` | toolkit | none | press: writes a window shot to the run dir |
| `camera.free.toggle` | cat mod `camera.free` | `F6`, `guide+y` (the user, 2026-10-22; a modifier chord under rule 7, Guide first) | press |
| `camera.free.hud` | cat mod | `F7` | press |
| `camera.free.freeze` | cat mod | `End` (orchestrator, 2026-10-22, follows from the user's F8 choice; the user may override; was `F8`, now the mouse release) | press, only while flying |
| `camera.free.reset` | cat mod | `Home` (the user, 2026-10-22; was `F5`, now the quick save) | press, only while flying |

The user, 2026-10-22: "Save states keep F5/F9". Quick save stays on F5
and quick load on F9. The mouse release moves to F8 and the free-camera
reset to Home. Both ship today on F9 and F5. Save-states task 4.0 rebinds
them, with its docs rows and ctests, ahead of the hotkeys.

Names are `<owner>.<verb>` in lowercase ASCII. A mod's actions start with
its mod name. Duplicate names are refused at registration with a log line.

**Config.** `[input.actions]` maps an action to a list of bindings. An
empty list unbinds it:

```toml
[input.actions]
"menu.open"          = ["F10", "guide+a", "back+lthumb@400", "paddle1"]
"camera.free.toggle" = ["F6"]
"overlay.stats"      = []
```

A binding is one of:

- **a key:** a name from `input_names.c`'s VK vocabulary (`F1`..`F24`,
  letters, `ctrl+F6`). Modifiers are allowed only on a key, and only a
  modifier that is absent from the effective key map (rule 2).
- **a pad chord:** `+`-joined names from the guest-pad vocabulary (`a b x
  y white black ltrigger rtrigger start back lthumb rthumb dpad_*`) plus
  the host-only names `guide`, `misc1`, `paddle1`..`paddle4` and
  `touchpad`, with an optional hold `@<ms>` (default 0, at most 2000).
  The chord is read on port 0 unless prefixed `pad2:` to `pad4:`. A
  chord whose first member is host-only (`guide+a`) is a **modifier
  chord** with its own rule (7, below).
- **a single host-only button:** `paddle1`, `guide` and so on. It is
  always allowed because the title can never see it.

Rules, so a binding never steals what the game uses:

1. A single guest button (`a`, `start`, `dpad_up`) as an action binding
   is **refused** with a warning. Guest buttons are allowed only in a
   chord of two or more, and only with a hold of at least 200 ms.
2. A key the guest already receives is **refused** for an action with a
   warning, and the guest keeps the key. The check is against the
   **effective key map**: the compiled-in `xbox_key_map` defaults, then
   `[input.bindings]`, `input.walk_key` and `input.mouse_release_key`
   (F8 by default from save-states task 4.0; F9 before it). Modifiers count as keys. Ctrl and Shift are guest keys
   in the default map, and cat's bindings take LShift and LAlt, so
   `ctrl+F6` is refused there unless the player unbinds Ctrl. F10 has no
   other meaning today and is `menu.open`'s default. F11 is free: the
   toolkit names it in `input_names.c` and warns when it is bound, but no
   fullscreen hotkey exists.
3. A chord is **consumed**. From the moment every button of the chord is
   down, those buttons are reported released to the guest until each is
   physically released. If the chord is let go before its hold time,
   nothing fires. The guest still sees the press of the chord's first
   button, and masking then adds a release the player did not make. With
   `back+start`, pressing START first pauses BLiNX 2 and the mask then
   releases START, so it is a poor default. The hold time does not help
   here, because it only guards against firing the action by accident.
   The design therefore:
   - prefers defaults whose members the title ignores on a lone press:
     host-only buttons, or a guest button with no use plus one used only
     in menus (`back+lthumb` for BLiNX 2: lthumb has no use, BACK only
     acts in menus);
   - offers `[input] chord_delay_ms` (default 0, at most 100). It holds a
     chord member back from the guest for that long after its press, so
     a chord completed inside the window never reaches the guest. The
     cost is that much latency on those buttons only, which is opt-in
     because it changes how the game feels;
   - documents the first-button effect in `config.md`.
4. Defaults use only F-keys, two-button chords with a hold, host-only
   buttons and modifier chords (rule 7). A game's `config.default.toml` may override them
   when a default chord collides with the title (b3, ssx3, jsrf and
   spartan get the toolkit defaults and a TASKS line to check them in
   play).
5. A scripted pad (`RECOMP_INPUT_SCRIPT`) never fires an action. Chords
   and host-only buttons read the host backend's pad, which the script
   never touches. Keyboard actions are different: kbm scripts
   (`kbm_script.c` ~222) inject into the same key table that real keys
   use (`xbox_InputKeyEvent`), so a scripted key **does** fire a
   key-bound action. That is intended, because cat's `key` script step
   is how unattended runs drive the free camera. Goldens stay safe
   through rule 6, not through the source of the key.
6. **Stock stays stock.** The filter is armed only by **feature keys**:
   `menu.enabled`, `overlay.stats`, or a mod's own enable key
   (`camera.free`). Registering an action never arms it. A golden run
   (`RECOMP_CONFIG=none`, every feature key off) leaves it disarmed, so
   it returns at its first test. At startup the layer logs
   `[ENHANCE] actions hook=off`, or `[ENHANCE] actions hook=on (menu.enabled, camera.free)`
   naming the keys that armed it. The golden harness fails a run whose
   log says `on` unless `--allow-enhance` names one of those keys. Every
   fire also logs `[ACTION] <name> via <binding>` unconditionally,
   limited to 10 lines a second, so a run that fired anything shows it
   without a trace channel.
7. **Modifier chords** (added 2026-10-22 for `guide+a`, R10). A chord
   written `<host-only>+<guest>...` fires only when the host-only member
   is pressed first. While that member is held, each guest member of
   any modifier chord bound on that port is masked from the guest from
   its own press until it is physically released, even if the host-only
   member is let go first. So the guest never sees the A of `guide+a`,
   and no hold is needed (`@0` is allowed here, unlike rule 1). A guest
   member pressed *before* the modifier goes to the guest as usual and
   does not complete the chord. A button that closes the menu (A on
   "Resume", B at the top page, A of `guide+a`) stays masked after the
   close until it is released, so the game never sees the tail of the
   press. When the backend cannot see the modifier (Steam took Guide),
   the chord never completes and the guest member passes unchanged.

**Where it runs: a title-glue filter, not a hook on `xbox_InputGetState`.**
cat never calls `xbox_InputGetState` (see the facts above), so D4's
hook would never run there. The seam is one function in `mod.h`'s glue
section, beside `xbox_mod_input_captured`:

```c
/* Host state of one port, before any script or keyboard merge. */
struct xbox_host_pad {
    XBOX_INPUT_STATE pad;   /* the host backend's guest-shaped state, 0 if none */
    uint32_t extra;         /* XBOX_HOST_GUIDE | MISC1 | PADDLE1..4 | TOUCHPAD */
    int      connected;
};
/* Evaluate actions and the menu for this poll; may rewrite *st (consumed
 * chords, neutral pad while the menu is open). Returns at its first test
 * when disarmed (rule 6). Poll thread. */
void xbox_enhance_pad_filter(DWORD port, const struct xbox_host_pad *host,
                             XBOX_INPUT_STATE *st);
```

There are two callers, and both call it after their own merge:

- **The toolkit's `xbox_InputGetState`** (b3, ssx3, jsrf, spartan and
  kuf, through `usb_gamepad.c`) fills `host` from the backend read it
  already makes, before the keyboard merge and the script.
- **cat's `cat_pad_get_state`** (`src/pad_input.c`) fills `host` from its
  own backend read, before it merges `RECOMP_INPUT_SCRIPT` and the
  keyboard and mouse. It calls the filter on the merged 18-byte gamepad
  converted to `XBOX_INPUT_STATE`, then writes it back. This is a
  ~20-line glue task in 3A and lives in cat, not the toolkit.

Keyboard bindings are read through `xbox_FramebufferKeyDown(vk)`. The
host state is kept apart from the script, which is what rule 5 needs.
While the menu is open the filter also neutralises the pad (D4).

The guest may not poll for a while (loading, a hang), so the flip also
calls `enhance_actions_tick()` when the last poll is older than 100 ms.
That covers keyboard, host-only buttons and modifier chords (rule 7),
never plain guest-button chords, so `menu.open` from F10, a paddle or
`guide+a` works on a loading screen. A modifier chord the tick fires
marks its guest member consumed, so the next poll masks it until
release.
**The tick's own host read** (review F1). The tick runs exactly when no
poll has refreshed anything for 100 ms, so it never relies on state a
poll left behind. When the filter is armed it makes its own host read
through a backend entry that is safe off the poll thread,
`xbox_input_backend_read_host(port, &host)`, and publishes the result to
the backend's atomic snapshot (guest buttons and `host_extra`):

- **XInput:** `XInputGetStateEx` (or `XInputGetState`), which is thread
  safe and may be called from the walker.
- **SDL3:** `SDL_GetGamepadButton` on the open gamepad, which takes
  SDL's joystick lock. The SDL main thread keeps pumping events in the
  present loop, so the state it returns is current even when the guest
  does not poll.
- **No pad open:** the snapshot is cleared, so a held modifier cannot
  stay held on old data.

A poll after the tick reads the pad itself as before, and rule 7's
masks carry across the two readers through the shared chord state,
which only the holder of the menu-step lock writes.

**Extra buttons: the backend seam.** `input_backend.h` grows
`uint32_t host_extra` beside the guest state. Each backend fills it, and
it reaches the filter as `xbox_host_pad.extra`:

| Backend | Buttons | How |
|---|---|---|
| SDL3 gamepad (macOS, Linux native; landed with the tracker item) | `guide`, `misc1`, `paddle1-4`, `touchpad` | `SDL_GAMEPAD_BUTTON_GUIDE` is already in the button table (`input_map.h`, `XBOX_SDL_BUTTON_GUIDE`, index 5) but maps to no guest button, so it only needs routing to `extra`. The new reads are `SDL_GAMEPAD_BUTTON_MISC1` (15), `RIGHT_PADDLE1` (16), `LEFT_PADDLE1` (17), `RIGHT_PADDLE2` (18), `LEFT_PADDLE2` (19) and `TOUCHPAD` (20) through `SDL_GetGamepadButton` in a second loop; `paddle1..4` name them in that order (R1, L1, R2, L2). `XBOX_SDL_BUTTON_COUNT` stays 15 for the guest map. |
| XInput (Windows native, Proton) | `guide` | `XInputGetStateEx` (xinput1_4 ordinal 100; Wine implements it), resolved with `GetProcAddress` by ordinal. Nothing else exists in XInput. Windows.Gaming.Input does not report the Guide button to apps, so it is not used. |
| Keyboard | none | Keys are already the key path. |

F-3 (the SDL3 rename of this table) is gone: the table is SDL3 now.

**Steam Input and the Deck.** Under Proton, Steam Input is on by default
and presents a virtual XInput pad. The back grips (L4, L5, R4, R5) are
not visible to XInput, and the guide button opens Steam. So on the Deck
the documented way is to bind a grip **in Steam Input** to a keyboard key
(`F10` for the menu, `F6` for the free camera) or to the pad chord. The
key path then fires the action unchanged.

Caveats, all for `config.md`:

- **Guide under Proton** reaches `XInputGetStateEx` only with Steam
  Input off for the title. Otherwise Steam takes the button.
- **Native Deck paddles** (Linux build, Steam Input off) need SDL3's
  HIDAPI Steam Deck driver (`SDL_HINT_JOYSTICK_HIDAPI_STEAMDECK`, on by
  default in 3.4). Through Steam's virtual pad the grips are not seen.
- **Elite and DualSense Edge paddles** are reported as `PADDLE1-4` only
  where the firmware mode and SDL's HIDAPI driver expose them. On some
  firmware they mirror face buttons instead, and those are guest buttons.

`docs/runtime/config.md` gets a short Deck paragraph with the Steam Input
steps. A shipped Steam Input layout for the Deck is a follow-up (R6,
F-6), not part of this change.

**Mod API v2** (fields appended; `XBOX_MOD_API_VERSION 2`; a v1 mod still
loads):

```c
/* Register a named action with its default bindings ("F6,back+lthumb@400").
 * init only. Returns an id >= 0, or -1 on a duplicate or a full table (64). */
int  (*action_register)(const char *name, const char *label, const char *defaults);
/* Presses since the last call (edge, consumed). Any thread. */
int  (*action_pressed)(int id);
/* 1 while held (a chord past its hold time). Any thread. */
int  (*action_down)(int id);
/* A menu item on the mod's own page (R4). init only. */
int  (*menu_add)(const struct enhance_item *it);
/* Called with 0 or 1 when the Mods page turns the mod off or on. NULL means
 * "applies at restart". init only. The toolkit records the request and calls
 * fn from the next xbox_mod_frame, on the guest thread, so the mod changes
 * guest memory and its own state from the thread its on_frame uses. */
int  (*on_enable)(void (*fn)(int on, void *user), void *user);
void (*toast)(const char *fmt, ...);
```

*As built in 3A (toolkit `src/enhance/mod.h`; the review,
L5), where it differs from the block above:*

- `action_register` takes its defaults as a NULL-ended string array
  (`const char *const *defaults`), one binding each, not one comma list.
- `toast` takes the mod first, `void (*toast)(const struct xbox_mod *m,
  const char *fmt, ...)`, so the line names its mod. It is a
  `[MOD <name>] toast:` log line until 3B's overlay.
- `menu_add` and `on_enable` are `void *` placeholders, NULL until 3D
  types them. 3D replaces them in place: same offset, same size.
- One more field, `int (*actions_arm)(const char *key)`, comes after
  `toast`. From init, it arms the hook when the mod's enable key is true
  (rule 6). A mod whose init fails takes its key with it.
- Action keys may be quoted: `"menu.open" = [...]` and `menu.open = [...]`
  are the same entry under `[input.actions]`, so 5.3's
  `config.default.toml` form is valid. An action name may not be another
  name plus a part (`menu.open` beside `menu.open.all`), because bare
  TOML cannot express that pair.

The free camera then polls `api->action_pressed(id_toggle)` in its
`on_frame` instead of its own rising-edge detection on
`xbox_FramebufferKeyDown`. Its `camera.free_toggle`, `free_hud_key`,
`free_freeze_key` and `free_reset_key` keys stay readable as aliases: when
set and `[input.actions]` does not name the action, they replace the
key binding. One log line notes the alias. This is a small follow-up
after the tracker item merges (R5 phase 5B). The free camera registers `on_frame`
and `batch_filter` only when `camera.free` or `menu.enabled` is on, so a
stock run keeps today's never-taken branch and no callback. With the menu
on and the camera off, the callbacks are registered and gated on an
atomic, which is what makes the Mods-page toggle live. Its actions arm
the filter only through rule 6, which means when `camera.free` is on.

**Overlap with `spike/input-selection`** (cat e09b325, parked):

- **Shared:** the host-button vocabulary. Both use `input_names.c` and
  the extra-button names added here.
- **Not shared:** actions never remap the guest pad, choose a source or
  pin a GUID. When the spike is revived its remaps feed the merged state
  *before* the hook. Its `input.ini` is superseded by `config.toml`
  (`[input.pad1]`), not by `[input.actions]`.

**Coexistence with `[input.bindings]`:**

- `[input.bindings]` is keyboard to guest pad, read into the VK table.
- `[input.actions]` is host input to action.
- A key is in one or the other, never both (rule 2).
- Both tables rebuild live with a pointer swap on the poll thread (R1).

### R4. Overlay pages (extends D5)

*Revised 2026-10-22: a Save states page (5), mouse use on every page
(R9), and the pause question closed.*

The menu keeps D5's item table, `enhance_menu_add` and the pure state
machine. Pages, in order:

1. **Render:** `render.scale`, `render.aniso`, `present.filter`,
   `present.fullscreen`, `present.pacing`, `display.aspect`,
   `display.overscan`, `display.movie`, `present.surface` (R).
2. **Pack:** as D5, with the miss list read from the snapshot (3.11).
3. **Game:** the title's items.
4. **Mods:** one row per registered mod (name, `on`, `off`, `failed` or
   `restart`). A toggle calls `on_enable` when the mod gave one, or
   records the change for the next start. Entering a row opens the
   items the mod added with `menu_add`. The toolkit keeps the mod
   table, the init result and the enable state. `mods.<name>` (bool,
   default on when built in) is the persisted key, so Save writes
   `[mods] "camera.free" = false`.
5. **Save states** (the user, 2026-10-22): the UI half of phase 5 of
   `openspec/changes/save-states/` (its tasks 5.1 and 5.2),
   over that change's D9 slot store. Shown only when the save-states
   layer is built and armed; otherwise the page is absent, not greyed.
   - **List:** one row per slot in `slots.json` order: the 160x120 PNG
     thumbnail from the slot header (decoded once per open into an
     overlay image, R7), the label, the date and time, and a `quick`
     tag on the quick slot. A row with a bad header shows "unreadable"
     and offers only delete.
   - **Rearrange:** pad: hold X on a row and move it with up and down,
     release to drop. Mouse: drag the row by its handle, or the up and
     down buttons on the row. The new order is written to `slots.json`
     (temporary file and rename, as D9 does).
   - **Delete:** a confirm row ("Delete 'Stage 1-2'? A: delete, B:
     keep"); delete removes the file and its entry, as D9 says.
   - **Export:** copies the slot to the export folder,
     `[states] export_dir`, default `<save dir>/exports/<game>/` (the
     user, 2026-10-22: "Folder next to saves"; `<save dir>` is the save
     root, `RECOMP_SAVE_DIR`, and `<game>` the title id, as in D9's
     `states/<title_id>/`), with the name
     `<title>-<label>-<yyyymmdd-hhmm>.xbrslot`, and toasts the full path.
     An **Open folder** row opens that folder in the host's file
     manager (`SDL_OpenURL` on a `file://` URL; absent in Deck game mode,
     where the row says so). Where SDL3's file dialog works (macOS, Linux desktop) an
     "Export to..." row opens `SDL_ShowSaveFileDialog`; its callback
     posts the path to the menu thread. In Deck game mode and on the
     Win32 D3D11 window there is no dialog, so only the folder applies.
     This is how the menu meets D9's "a path the player picks" (the
     user, 2026-10-22).
   - **Import:** lists the `.xbrslot` files in the export folder; picking
     one runs D9's header check. A refusal (another XBE, newer chunk
     versions) shows the reason on the row and a toast. An accepted file
     gets a new id and is appended.
   - **Load** and **Save to a new slot** rows call the save-states API
     (`xbox_StateRequest`) and close the menu, so the request is served
     at the next safe point the save-states change defines.
   It needs the mouse and list widgets of R7 and R9 (a scrolled list
   with image rows, drag, a confirm row), which is why it lands in
   phase 3G, after 3F and after save-states phase 4 and its task 5.2 (the
   store operations, with no UI).
6. **Stats:** a full-page version of the STATS layer with a 120-frame
   frame-ms graph drawn as bars, the pacing mode, and per-second flips,
   presents, draws and texture uploads. It also has the toggle for the
   corner strip (`overlay.stats`).
7. **Controls:** every registered action with its bindings, plus capture
   (the next key, two-button chord held 400 ms, modifier chord such as
   `guide+a`, or host-only button; refused under the R3 rules) and
   clear. A click on a binding starts the capture too; mouse buttons are
   never bindable, so a click cannot be captured by mistake. A **Mouse**
   group at the end shows the capture mode (`input.mouse_capture`:
   `click`, `focus`, `never`, a choice item applied on the window thread
   per R1), the release key (`F8`) and the free keys
   (`input.mouse_free_keys`, R9) as info rows, and the current capture
   state ("captured", "free: click to capture", "free: F8"). This
   replaces phase 9's two menu items.
8. **Debug:** backend and presenter, host-opts gen, texture-cache and
   target counts, the pack miss ring, the input sources with the extra
   buttons seen this second (to test a paddle binding), "write a window
   shot" (`shot.window`), and the trace channels the `recomp_env` table
   flags as live (a new `LIVE` flag in the X-macro rows; none is live
   today, so the page lists them read-only until a row opts in). On
   D3D11 "write a window shot" is disabled until F-10.
9. **Save** and **Reset to stock.**

**Stats source.** `nv2a_stats.{c,h}` in the kernel library: relaxed
atomics bumped where the work already happens (the flip, the present,
draw submit, texture upload, pack hit or miss) and a 128-entry frame-ms
ring written at the flip. `xbox_title_format` and `RENV_TITLE_STATS`
already compute fps once a second, and they read the same counters, so
the title bar and the strip agree. **Cost when off:** each counter site
tests one relaxed-loaded flag, `nv2a_stats_on`, which is set while the
STATS layer, the Stats page or `RECOMP_TITLE_STATS` is shown. With the
flag clear the site does nothing more. That is the same one-load,
one-branch rule as the overlay, and the "Enhancements default to stock"
requirement allows it.

**The guest keeps running** (D7 stands; the user, 2026-10-22: no pause).
The menu never pauses the guest, and no `enhance_menu_on_open` pause
callback is added. A player who wants the game paused opens the game's
own pause screen first; the neutral pad keeps it there.

### R5. Phases from 3 on (supersedes the Migration Plan's 3, 4, 5, 6 and 9)

*Revised 2026-10-22: microui, the TrueType font, the mouse and
cursor, Guide+A and the Save states page (R7 to R10) re-split phase 3.
SDL3 has landed, so nothing waits for the tracker item and F-3 is gone.*

Each phase has its own worktree and agent and merges on its own. Estimates
are agent-days including gates. Toolkit phases branch off
`posix-host/portability`.

| Phase | Content | Estimate | Depends on |
|---|---|---|---|
| **3A. Host actions** (toolkit, plus cat glue) | `xbox_enhance_pad_filter` in the toolkit, called from `xbox_InputGetState`, plus the cat glue in `cat_pad_get_state`; `enhance_actions` (registry, `[input.actions]` parser with the R3 rules 1 to 7, chords with a hold, consumption, modifier chords and the mask-until-release of rule 7, `chord_delay_ms`, the flip tick with its own host read through `xbox_input_backend_read_host` (review F1), the `actions hook=` line, the rate-limited `[ACTION]` line); `host_extra` in the SDL3 and XInput backends (`XInputGetStateEx`); `menu.open` defaults `F10` and `guide+a`, firing only a log line until 3D; mod API v2 `action_*` and `toast` (a log line until 3B); `[input.bindings]` and actions rebuilt live by pointer swap; the input setters of R1. ctests `input_actions` (rule 7 cases included, and a modifier chord fired by the tick with no poll at all). Docs: `config.md`, the input README, the Deck paragraph, the Guide table of R10. | 2.5 | none |
| **3B. Overlay core, renderers and stats** (toolkit) | Vendored microui and stb_truetype with their licence files; the embedded UI font (R7); `nv2a_overlay` with four triple-buffered layers holding draw lists; the microui-to-draw-list converter (rounded rects, AA feather, scissor, images); the code-default theme tokens and `ui_scale` (R8); the three renderers (Metal pipeline, D3D11 shaders through `D3DCompile`, SDL3 `SDL_RenderGeometryRaw`) with the SDL dirty wake, the `fbm_present` layers argument and D3D11 after `dump_frame`; the CPU reference rasteriser; `nv2a_stats` (gated on `nv2a_stats_on`), the STATS strip and the TOAST layer; the `overlay.stats` key and env row. ctests `overlay` (draw-list checksums, layout, reference raster). Mac Metal and SDL window shots compared with the reference raster, plus an `fb_dump` of the same flip without the overlay; flips/s with the strip on within 5% and with it off unchanged. The D3D11 renderer is written and compiled here and checked under Proton in this phase's Deck gate. | 4.25 | none (parallel with 3A) |
| **3C. Live-switch completion** (toolkit) | Mask bits `ANISO`, `MOVIE`, `OVERSCAN`; the SDL loop reads the filter each present; SDL fullscreen on the main thread; D3D11 fullscreen style swap and `ResizeBuffers` (in v1 scope, the user, 2026-10-22); pacing and input setters. `ASPECT` is left to the Hor+ change, and its row is written there. ctest `host_opts_live` cases for the new bits. | 1.5 | none (parallel) |
| **3D. Menu** (toolkit) | `enhance_menu` on microui: the D5 state machine drives a microui frame per redraw (rows, toggles, choices, sliders, info rows, a confirm row, a scrolled list); the R4 pages Render, Pack, Game, Mods, Stats, Controls, Debug, Save, Reset; the R8 layout of the menu panel; the miss-ring snapshot (3.11); `recomp_cfg_patch` and Save; mod API v2 `menu_add` and `on_enable`; `menu.enabled` key. Pad and keyboard only here; the mouse is 3F. ctests `enhance_menu` (navigation, the command stream of a page against a checked-in checksum) and `recomp_cfg_patch`. Mac checks of the old 3.9 and 3.10. | 3 | 3A, 3B, 3C |
| **3E. Font and theme** (toolkit) | The atlas worker and rebakes on a size step (R7); the Regular and Bold weights; the Unicode range and the box glyph; tabular digits for the stats; `[overlay.theme]` and `[overlay] ui_scale` read and live (R8); a per-game theme from the game's `config.default.toml`, including an optional font file; the R8 layouts of the stats strip and toasts at every output height. ctests: atlas bake, missing glyphs, theme parse and refusals, layout at 480, 720, 1080 and 2160 lines. | 1.5 | 3B (merges after 3D) |
| **3F. Mouse and cursor** (toolkit) | The menu mouse snapshot written by the SDL3 and Win32 window threads, the coordinate mapping to output pixels, the capture release and restore through `xbox_InputMouseSuspend`, OS cursor hide and idle hide, the `CURSOR` layer, the built-in cursor styles and an owner PNG through vendored stb_image (PNG only), the menu's hover, click, wheel and right-click, the pad-press cursor hide, the mouse close mask in `mouse.c` (review F7), and the capture-on-click changes: `input.mouse_free_keys`, `click` mode left free after the menu, the shipped `mouse_capture = "click"` (R9). ctests: snapshot hand-off, hit tests, the click and wheel mapping, cursor image refusals, and the `tests/input_keyboard` mouse cases for the close mask, the free keys and click mode after the menu. Mac checks with a trackpad and a mouse, Metal and the SDL renderer. | 2 | 3D, 3E |
| **3G. Save states page** (toolkit) | The R4 page over the save-states slot store and API: list with thumbnails, rearrange, delete with confirm, export to `<save dir>/exports/<game>/` with an Open folder row (and the SDL3 dialog where it works), import with the header refusals, load and save to a new slot. ctest over a temporary slot directory (order, delete, import refusals). This is the UI half of save-states phase 5 (its tasks 5.1 and 5.2, marked moved in that change's `tasks.md` on this branch); that change's phase 5 then holds the CLI verbs (5.3) and the manual pass (5.4), both blocked on 3G. | 0.75 | 3F, save-states phase 4 and 5.2 |
| **4. CLI golden** | `ENHANCE_STOCK`: `menu.enabled`, `overlay.stats` (stock `off`), `textures.font` and `textures.text` (stock `on`); a check that a golden log carries no `[ACTION]` fire line and no `[OVERLAY]` atlas line. | 0.5 | 3A, 3B, 3D (the log lines) |
| **5A. cat items** | Atomic glow (D9), Game items, `[menu]`, `[overlay]` and `[input.actions]` in `config.default.toml` (BLiNX 2 adds the fallback `back+lthumb@400` to `menu.open`, and sets `input.mouse_capture = "click"`, `mouse_free_keys = ["Escape"]` and `cursor_hide = "idle"`), env rows, docs. | 1 | 3D, 3F, 4 |
| **5B. Free camera onto actions** (cat) | Register the four actions through API v2; drop the private edge detector; old keys become aliases; `camera.free` live through `on_enable`; speed and sensitivity atomic; a Mods-page entry with its items; the pad default `guide+y` (the user, 2026-10-22). | 0.5 | The tracker item merged, 3A (3D for the Mods page) |
| **6. Proton, the Deck and Windows** (D3D11) | The old 6.x (on the Deck, not the Linux/Proton host) plus: the D3D11 renderer after `dump_frame`, D3D11 fullscreen live, `XInputGetStateEx` guide and `guide+a` on Proton (Steam Input off for the title), a Deck grip bound in Steam Input to F10 opening the menu, the mouse and cursor on the Win32 window (the cursor moves at the guest flip rate, R9), capture on click under Proton, the Save states page on the Deck. A native Windows pass of Guide (Game Bar setting) only when the user boots Windows. | 1.5 | 3A-5B |
| **9. Controls** | Folded into 3D's Controls page. Only the real-pad capture checks on both hosts stay as 9.x, now including a `guide+a` capture. | 0.5 | 6 |
| **7, 8, 10** | Unchanged. | | |

**Gates per phase.** 3A to 3G each change the runtime, the renderer or
input, so each merge gets its own gates under CLAUDE.md:

- the Mac build, the POSIX ctests and the Metal goldens;
- `blinx2 bench golden` on D3D11 under Proton on the Deck;
- a Deck smoke run of the installed build;
- the review.

The overlay phases add three checks of their own. 3B, 3E and 3F compare
a Metal and an SDL-renderer window shot with the CPU reference raster of
the same draw list (a small tolerance for the GPUs' AA). They check a
D3D11 host screenshot on the Deck by eye, since D3D11 has no window shot
until F-10. And they show that the goldens and dumps are free of the
overlay: the golden runs leave every layer hidden, and an `fb_dump` taken
with the menu open equals one taken closed. Each phase's estimate
includes about 0.25 day for the gates. 3B's estimate assumes the
D3D11 renderer can be verified in the Deck gate. If it cannot, it splits
into 3B2 (0.75 day, verified in phase 6) with no change to the total.
Phase 6 then holds only the
feature checks on D3D11 and the Deck that need the whole set.

**Parallel work, ordered merges.** 3A, 3B and 3C can be developed at the
same time in separate toolkit worktrees, and 3E can start once 3B has
merged. They touch shared files: `enhance.c` (key reads and log lines),
`recomp_env.h` (rows), `mod.h` (the v2 fields), `fb_present_sdl.c` (3B's
renderer and 3C's filter and fullscreen), `nv2a_pb_d3d11.c` (3B's
renderer and 3C's fullscreen), the window procedures (3F) and the
`fbm_present` signature (3B's layers, 3C's filter). The merge order is
fixed:

1. **3A first.** It owns the `mod.h` v2 block. It appends the
   `action_*` and `toast` fields and reserves `menu_add` and `on_enable`
   as later fields.
2. **3B rebases on 3A.** It owns the `fbm_present` signature change and
   the vendored code.
3. **3C rebases on 3B.** Its presenter edits land in the new signature.
4. **3D** on 3C.
5. **3E** on 3D. Until then 3D uses 3B's code-default theme.
6. **3F** on 3E.
7. **3G last**, once save-states phase 4 and its 5.2 have merged.

`recomp_env.h` rows and `enhance.c` log lines are append-only, so those
conflicts are textual. **Total** for 3A to 6 with the per-phase gates is
about 19 agent-days, and 19.5 with the phase 9 checks (17 at `14f041d`,
11.5 on 2026-10-21). Against 11.5, the rise is microui and the three
geometry renderers with their reference raster (+2.25, of which +1.25
is the review's F13 re-estimate of 3B), the menu on microui (+0.5), the
font and theme (+1.5), the mouse and cursor (+2, of which +0.5 is
capture on click and the close mask), the Save states page (+0.75),
modifier chords and the tick's own host read (+0.5) and the wider
phase 6 (+0.5).

**What changes in tasks.md.** 3A.x gain the modifier-chord rule, the
Guide defaults and the per-host Guide table. 3B.x are rewritten (vendoring,
draw lists, renderers, reference raster). 3D.x move the pages onto
microui, gain the Mouse group on Controls (3D.3) and lose the mouse suspend item to 3F. New sections 3E (font and
theme), 3F (mouse and cursor) and 3G (Save states page). Phase 6 gains
the cursor, Guide and Save states checks, 9.1 a `guide+a` capture. The
pause hook is gone from every task. Round 2 (the review and the
user's answers, 2026-10-22) adds: the tick's host read (3A.3), the
Atkinson Hyperlegible files and the README licence rows (3B.1), the env
rows per phase (3B, 3E, 3F, 3G), the pad-press hide, the close mask and
capture on click (3F), the export folder (3G), and the save-states
`tasks.md` edit.

### R6. Follow-ups outside this change

| ID | Title | Estimate | Depends on |
|---|---|---|---|
| F-1 | Toolkit: live `textures.pack` path swap at the flip | 0.5 | 3D |
| F-2 | Toolkit: overlay on the CPU GDI window (Windows CPU backend): one more consumer of the draw list, through the reference rasteriser | 0.5 | 3B |
| F-3 | *Dropped 2026-10-22: SDL3 landed and R3's table is written in SDL3 names.* | | |
| F-4 | b3, ssx3, jsrf, spartan, kuf: check the default action chords in play (`guide+a` included) and add `[input.actions]`, `[menu]` and `[overlay]` to their `config.default.toml` | 0.5 | 5A |
| F-5 | Hor+: `display.aspect` live with an `NV2A_OPT_ASPECT` flush, or recorded as S per game | 0.5 | `enhancements-hor-plus`, 3C |
| F-6 | Shipped Steam Input layout for the Deck (grips to F10 and F6), if the user wants one | 0.5 | 6 |
| F-7 | `recomp_env` `LIVE` flag for trace channels that can toggle at run time, shown on the Debug page | 0.5 | 3D |
| F-8 | Revive `spike/input-selection` on top of the filter (pad remaps before actions) | later | 3A |
| F-9 | D3D11: present the overlay without a guest flip (walker present-only path after 100 ms); also lifts the cursor above the guest flip rate. The present-only path must also pump the Win32 messages (`pump()`, `xbox_InputMouseWin32Sync`), since on D3D11 F10 and mouse clicks also arrive only at guest flips today (review F8); Guide already works through the tick. The user, 2026-10-22: the flip-rate cursor is "OK for v1, fix later". | 0.5 | 3B |
| F-10 | D3D11: `RECOMP_WINDOW_SHOT` (back buffer after the overlay draw), for the Debug page and README shots | 0.5 | 3B |
| F-11 | Hardware cursor mode (`overlay.cursor.mode = "hardware"`): the same cursor image as an OS cursor (`SDL_CreateColorCursor`, Win32 `CreateIconIndirect`), moving at the OS rate on every backend; the answer to the D3D11 cursor rate if F-9 is not enough | 0.5 | 3F |
| F-12 | CLI: `xbr enhance cursor`, which builds an owner cursor PNG from the owner's dump (a crop of a game texture the owner names), kept in the owner's config directory and never distributed | 0.5 | 3F |
| F-13 | CJK and other scripts: a per-game font file plus wider atlas ranges, with localisation | later | 3E |

## Revision 2026-10-22: UI toolkit, font, mouse, Guide+A, save states

The user decided on 2026-10-22:

- a richer UI toolkit with a proper font, replacing the 8x8 bitmap panel
  of D3 and R2;
- the mouse in v1, with a game-styled cursor;
- Guide + A as the default pad binding for the menu;
- no pause (D7 stands);
- SDL3 has landed (Done), so phase 3 uses the SDL3 names;
- a Save states page for phase 5 of `save-states`.

R7 to R10 below record the design for those decisions, checked against
the toolkit at `posix-host/portability` cae8c90e. They supersede D3, the
content half of R2 (what a layer holds and how text is drawn), and the
parts of R3, R4, R5 and R6 that are marked "2026-10-22". R1 and the rest
of R2 and R3 stand.

### R7. UI toolkit, draw list and font (supersedes D3; replaces R2's raster and text)

**What it must do.** It needs:

- the menu pages of R4 with a scrolled list, image rows (save
  thumbnails), sliders, toggles, a confirm row and drag;
- hit tests for the mouse;
- proportional text with a real face at every output size;
- one picture on Metal, D3D11 and the SDL renderer.

It must also follow these constraints:

- C11, small and vendorable under the toolkit's licence rules;
- the R2 threading: one writer per layer, triple buffers, a presenter
  that never waits;
- zero cost while closed;
- nothing in a dump or a golden.

**Options, re-weighed:**

| Option | Licence, size | Renderer work per presenter | Font and text | Threading | Verdict |
|---|---|---|---|---|---|
| **microui** (rxi, v2.x) | MIT; about 1,200 lines of C and 300 of header | None of its own. It emits a command list of rect, text, clip and icon, which we convert to triangles once on the CPU. | Bring your own: two callbacks (text width, text height). stb_truetype fits. | One explicit `mu_Context`, fixed-size stacks, no mutable globals: one context per writer is safe. | **Chosen.** |
| Nuklear (single header) | MIT or public domain; about 30k lines with its bundled stb_truetype and stb_rect_pack | Its vertex converter, plus one renderer per backend | Its own font baker | One `nk_context` per writer, fine | Rejected. About 25 times the code, most of it unused (charts, property editors, its own allocator and AA path), and the extra code has to be reviewed. |
| Clay (nicbarker) | zlib; about 4k lines, C99 | A render-command list, like microui | Bring your own measure callback | A process-global current-context pointer (`Clay_SetCurrentContext`) shared by the MENU writer and the presenting thread, which composes STATS and TOAST | Rejected. It is layout only (no widgets or input), the 0.x API changes between releases, and the global context races with two writers. |
| Dear ImGui (or cimgui) | MIT; about 30k lines of C++ | Its backends exist for Metal, D3D11 and SDL3 | Its own baker | One global context per thread unless rebuilt | Rejected as before: C++ in a C11 toolkit. |
| LVGL | MIT; over 100k lines | Its own software renderer, or a draw-unit per GPU | Its own font engine | A single global instance and lock | Rejected: an embedded GUI framework, far too large. |
| Hand-rolled panel (D3) with a TrueType face | ours | One quad per layer | stb_truetype into the raster | As R2 | Rejected now. Mouse hit tests, scrolling, drag and image rows would grow it into a worse microui. |

**Why microui.**

- It is the smallest option that has widgets, input and clipping.
- Its whole state is in a context we own, which fits R2's per-thread
  writers. Each writer thread that builds UI has its own context.
- Its output is a flat command list, so every backend renders the same
  triangles and the backends agree by construction.
- Custom commands (`mu_push_command`) carry what it lacks: rounded
  rects, images (thumbnails, the cursor) and a two-weight font id.

microui has no gamepad focus model. It does not need one here: D5's pure
state machine keeps the selected row. A redraw marks that row as
microui's hover and focus, and a mouse hover writes the hovered row back
into D5's selection (R9). The pad and the mouse drive one selection.

**Vendoring.**

- `third_party/microui/` (MIT): `microui.c` and `microui.h` unmodified,
  with the version in a `VERSION` file. Our size macros
  (`MU_COMMANDLIST_SIZE` and the others) are set by the build.
- `third_party/stb/` (public domain or MIT, the dual licence):
  `stb_truetype.h` and `stb_image.h`. stb_image is built with
  `STBI_ONLY_PNG` and `STBI_NO_STDIO`, and it decodes only the owner
  cursor and the save-state thumbnails (R9, R4).
- `LICENSES/MIT-microui.txt`, `LICENSES/MIT-stb.txt` and
  `LICENSES/OFL-1.1-atkinson-hyperlegible.txt` (the font, below), NOTICE
  entries, and a `LICENSES/README.md` row each, as `dsp56300` set the
  precedent. The toolkit `README.md` "License" table gains three rows:
  `third_party/microui/` (MIT, rxi), `third_party/stb/` (MIT or public
  domain, Sean Barrett) and `third_party/fonts/atkinson-hyperlegible/`
  (SIL OFL 1.1, Braille Institute of America). Upstream's "no other
  external dependencies" line still holds, since all three are vendored
  (review F12).
- They compile only under `XBOXRECOMP_ENHANCE`, in one translation unit
  each, with warnings relaxed for those files only.

**One command stream, one draw list.** `src/kernel/nv2a_overlay_ui.c`
converts a finished microui frame into a **draw list**:

```c
struct nv2a_ovl_vtx { float x, y, u, v; uint32_t rgba; };   /* output pixels */
struct nv2a_ovl_cmd { uint32_t first, count;                /* indices */
                      int16_t clip[4];                       /* x, y, w, h in output px */
                      uint16_t tex; };                       /* 0 = atlas, 1.. = images */
struct nv2a_ovl_list {
    const struct nv2a_ovl_vtx *vtx; const uint16_t *idx; const struct nv2a_ovl_cmd *cmd;
    uint32_t nvtx, nidx, ncmd;
    uint32_t out_w, out_h;      /* the placement the list was built for */
    uint64_t gen, atlas_gen;
};
```

- A rect becomes two triangles that sample the atlas's white texel.
- A rounded rect becomes a fan with a 1-pixel alpha feather, 4 to 8
  segments per corner by radius.
- Text becomes one quad per glyph from the atlas.
- An image is one quad on its texture slot.
- A clip change starts a new command.

Each layer's triple-buffer slot (R2) now holds one `nv2a_ovl_list` in
fixed arrays allocated at arm time:

| Layer | Vertices | Commands |
|---|---|---|
| `MENU` | 16k | 256 |
| `STATS` | 2k | 16 |
| `TOAST` | 2k | 16 |
| `CURSOR` | 64 | 2 |

Indices are 16-bit. Nothing is allocated after init. A frame that would
overflow is cut at a command boundary and logs once. Publishing and
acquiring are R2's single atomic exchange, unchanged.

**Threads.** R2's writers stand, with one refinement for the menu. The
menu step (`enhance_menu_step`: input, then the microui frame, then the
conversion, then the publish) runs under an atomic try-lock. The poll
thread takes it at each poll. The flip tick takes it when the last poll
is older than 100 ms (R3's loading-screen case). So the MENU layer has
exactly one writer at a time, and the lock's acquire and release order
the context and the back slot between the two threads. A step that finds
the lock taken is skipped, and the next one catches up. STATS and TOAST
have their own microui contexts on the presenting thread. CURSOR is
composed by the presenting thread from R9's atomic position.

**One renderer per backend.** Each renderer draws textured, coloured
triangles with a scissor and premultiplied alpha blending. It uploads
the atlas when `atlas_gen` moves and a list's buffers when `gen` moves.

| Presenter | Renderer | Size |
|---|---|---|
| CAMetalLayer (`fb_present_metal.m`) | A second `MTLRenderPipelineState` from MSL source, compiled like `s_blit_msl`. One vertex and one index `MTLBuffer` per layer (shared storage, refreshed on `gen`). `setScissorRect` per command, drawn in the frame's render pass after the frame triangle. | about 150 lines |
| D3D11 (`nv2a_pb_d3d11.c`, the walker at the flip) | A vertex and pixel shader pair compiled once through the `D3DCompile` path the backend already uses. Dynamic vertex and index buffers (`MAP_WRITE_DISCARD` on `gen`). A blend state and a rasteriser state with `ScissorEnable`, and `RSSetScissorRects` per command. Drawn after `dump_frame()` and before `Present`, saving and restoring the state it touches. When no frame was copied or blitted this present (`s_drawn` NULL, or no back buffer bound yet), it clears the back buffer to black first, so the overlay never draws over undefined contents (review F9). | about 150 lines |
| SDL renderer (`fb_present_sdl.c`, SDL3) | `SDL_RenderGeometryRaw` per command, with `SDL_SetRenderClipRect`, the atlas and images as `SDL_Texture`s with `SDL_BLENDMODE_BLEND_PREMULTIPLIED`, which every SDL3 renderer supports (review F10). SDL3 takes float colours, so the list's `rgba` is expanded once per `gen` into a cached `SDL_FColor` array. Drawn after `SDL_RenderTexture(frame)` and before `shot_save`. | about 60 lines |
| CPU GDI window | None (R2's gap; F-2 would draw the list through the reference rasteriser). | |

The vertex positions are in output pixels of the placement rect the
presenter publishes (an atomic `{x, y, w, h}` word pair written at each
present). When the placement changes, the presenter scales the old list
by the ratio for that frame, and the writer rebuilds at the new size on
its next step, so a window resize never shows a stale-size panel for more
than one step.

**The CPU reference rasteriser** (`nv2a_overlay_ref.c`, built for the
ctests and for F-2) draws a draw list into an RGBA8 buffer:

- fixed-point edges with the top-left fill rule;
- bilinear atlas sampling;
- premultiplied blending;
- the same scissor.

The `overlay` ctest builds known pages through the real microui and
converter, then checks:

- the draw list (a checksum of vertices, indices and commands);
- layout facts (a row's rect, the panel's width at 720 and 2160 lines,
  text clipped at the panel edge);
- the reference raster's checksum.

The GPU renderers are checked against that raster through Metal and SDL
window shots (R5 gates). The ctests prove the shared stream, and the
renderers are thin enough to check by shot.

**Font.** stb_truetype bakes a coverage atlas (one 8-bit channel,
expanded to premultiplied white on upload):

- **When:** at arm time on the init thread for the first output size,
  then on a lazily created worker thread when the size step changes
  (R8). The new atlas is published by an atomic pointer and
  `atlas_gen`. Until it is ready the old atlas is drawn, scaled. No bake
  ever runs on the poll thread or a presenter.
- **Sizes:** the token sizes of R8 at the current `ui_scale`, in Regular
  and Bold, with 2x horizontal oversampling. That gives a
  1024x1024 atlas at 1080 lines and 2048x2048 at 2160, built in about
  10 to 30 ms on the worker.
- **Unicode scope (v1):**
  - U+0020 to U+007E and U+00A0 to U+017F (Latin-1 and Latin Extended-A,
    which covers the European languages the games ship);
  - U+2010 to U+2026 (dashes, quotes, the ellipsis) and U+2022;
  - U+2190 to U+2195 (arrows) and U+00D7.

  Labels are UTF-8. A code point outside the range draws a box (the
  font's `.notdef`), and the Debug page counts them. CJK and other
  scripts need a per-game font file and wider ranges (F-13), outside v1.
- **Digits:** stb_truetype applies no OpenType features, so the stats
  strip gets tabular digits from our layout. Each digit is advanced by
  the widest digit's advance.
- **The face:** **Atkinson Hyperlegible** (the user, 2026-10-22,
  replacing the Inter proposal). It is the Braille Institute's face,
  under SIL OFL 1.1, drawn for legibility at small sizes, which suits a
  TV and the Deck's 7-inch screen. The static Regular and Bold TTFs go
  in `third_party/fonts/atkinson-hyperlegible/` unmodified, with its
  `OFL.txt`. Being unmodified keeps any reserved font name respected.
  The face has no SemiBold, so R8's title and selected-row sizes use
  Bold. The build turns the files into a C array (a CMake step, no new
  tool). The two files are about 0.2 MB, under `XBOXRECOMP_ENHANCE`
  only. The 0.7 MB cap stays as a gate in 3B.1. Its Latin coverage is
  checked against R7's range in 3E, and a gap draws the box glyph and
  shows in the Debug page's count.
- **Committed TTFs and the public audits** (the user, 2026-10-22: the
  TTF is committed, OFL). The files are open-licensed binaries and not
  game data. Three audits are affected:
  - **Toolkit fork pushes** (`notes/public-toolkit-map/round.py` and
    its `README-rounds.txt` audit step): the tree-delta binary check
    gains an allow-list entry for
    `third_party/fonts/atkinson-hyperlegible/*.ttf`, which is recorded
    in `README-rounds.txt`. The orchestrator makes this change, since
    it lives in `notes/`.
  - **cat's public export** is unchanged, because the TTFs live in the
    toolkit, not in cat.
  - **The CLI's `scripts/audit-public.sh`** is not touched. The TTFs
    never enter `xboxrecomp-cli`, so no allow-list entry is added
    there.
- **A per-game face:** `[overlay.theme] font` names a TTF or OTF file
  shipped with the game build or owned by the player, with
  `font_bold` optional (R8). BLiNX 2 could match its HUD pack's PT
  Sans Narrow (OFL) this way. Nothing from a game dump is ever used as
  the UI font.

**Zero cost while closed, goldens and dumps.** These are unchanged from
R2:

- The presenters test one relaxed load of `visible` and draw nothing
  when it is 0.
- The UI code runs only from the menu step, the STATS and TOAST
  composition, and the atlas worker, and each is reached only when its
  layer is visible or armed.
- A golden run (`RECOMP_CONFIG=none`) never arms the overlay. So it
  never creates a context, never bakes an atlas (the atlas line
  `[OVERLAY] atlas ...` is absent, which phase 4 checks), and never
  allocates the arrays.
- The draws come after `dump_frame()` on D3D11 and after the frame in
  the SDL and Metal passes. They never touch the render targets that
  `RECOMP_FB_DUMP`, `fb_dump_at`, `d3d11_dump` or the Metal dump read.

**API** (`src/kernel/nv2a_overlay.h`; it replaces R2's canvas calls):

```c
enum nv2a_overlay_layer { NV2A_OVL_STATS, NV2A_OVL_TOAST, NV2A_OVL_MENU,
                          NV2A_OVL_CURSOR, NV2A_OVL_COUNT };
uint32_t nv2a_overlay_visible(void);                         /* one atomic load */
/* Reader side (the presenting thread). */
const struct nv2a_ovl_list *nv2a_overlay_acquire(enum nv2a_overlay_layer l);
const struct nv2a_ovl_atlas *nv2a_overlay_atlas(void);        /* pixels, w, h, gen */
const struct nv2a_ovl_image *nv2a_overlay_image(uint16_t tex);/* pixels, w, h, gen */
void nv2a_overlay_set_placement(int x, int y, int w, int h);  /* at each present */
/* Writer side (the layer's one writer at a time). */
mu_Context *nv2a_overlay_ui_begin(enum nv2a_overlay_layer l); /* sizes from the placement */
void nv2a_overlay_ui_publish(enum nv2a_overlay_layer l);      /* convert, then publish */
void nv2a_overlay_hide(enum nv2a_overlay_layer l);
int  nv2a_overlay_image_set(uint16_t tex, const uint32_t *rgba, int w, int h); /* thumbnails, cursor */
void nv2a_overlay_toast(const char *fmt, ...);                /* any thread: queues a line */
```

### R8. The look: theme tokens, layout and scaling

**Scale.** All sizes are tokens defined at 1080 output lines:

```
ui_scale = clamp(out_h / 1080, 0.5, 3.0) * overlay.ui_scale
```

- `out_h` is the placement rect's height in output pixels, so HiDPI
  windows (Retina, a 4K TV) get crisp text.
- `overlay.ui_scale` is the player's factor (float, default 1.0, 0.75 to
  2.0, live).
- The scale is independent of `render.scale`: the overlay is drawn at
  output resolution after the frame. A 2x or 3x guest render changes
  nothing in the overlay.
- Sizes are rounded to whole pixels after scaling.
- The atlas rebakes (R7) when the rounded body size changes, which
  happens on a window resize, a fullscreen toggle or a change of
  `ui_scale`.

**Tokens** (code defaults; every one can be overridden in
`[overlay.theme]`):

| Token | Default | Use |
|---|---|---|
| `bg` | `#101418` at 0.86 alpha | panel background |
| `bg_row` | `#1A2027` at 0.9 | alternate rows, inputs |
| `bg_hover` | `#2A3440` | hover and the pad selection |
| `accent` | `#4FB3FF` | the selection bar, toggles on, slider fill, focus ring |
| `text` | `#E8EDF2` | body text |
| `text_dim` | `#9AA7B4` | hints, units, read-only values |
| `warn` | `#FFB84F` | "restart", refusals |
| `bad` | `#FF6B6B` | delete confirm, failed mods |
| `good` | `#7BD88F` | "saved", toggles on in the stats strip |
| `radius` | 10 px | panel; rows use `radius / 2` |
| `pad` | 16 px | panel padding |
| `gap` | 8 px | between rows |
| `row_h` | 44 px | a menu row (a comfortable pad and mouse target) |
| `font_title` | 30 px Bold | page title |
| `font_body` | 22 px Regular | rows |
| `font_small` | 17 px Regular | hints, the stats strip, toasts |
| `shadow` | 0.35 alpha, 12 px | the panel's soft shadow (a feathered rounded rect) |

Colours are written `"#RRGGBB"` or `"#RRGGBBAA"`. A bad value is refused
with one warning, and the default is kept.

**The menu panel.**

- A rounded panel on the left of the frame, `min(40% of the width,
  720 px * ui_scale)` wide, full height minus `2 * pad`. The game stays
  visible on the right. In portrait or under 640 output pixels wide it
  takes the full width.
- Top: a tab strip with the page names, scrolled horizontally when they
  do not fit. LB and RB, or Q and E, switch pages, and a click selects
  a tab.
- Body: a vertical list of `row_h` rows, with the label left and the
  value right. Toggles are pills, choices show `<  value  >`, and ranges
  are sliders with the number. The selected row has the `bg_hover`
  fill and a 3-pixel `accent` bar on its left. The list scrolls so the
  selection stays in view, with a thin scroll bar when it overflows.
- Bottom: a hint line in `font_small` with the inputs of the current
  host (pad glyph names such as "A select · B back · LB/RB page", or the
  keys and mouse when the last input was the keyboard or mouse), and
  the R1 apply tag of the selected row ("live", "at restart").

**The stats strip.** A rounded strip in the top-right corner, one line
in `font_small` with tabular digits: `60.0 fps · 16.7 ms (max 18.2) ·
pacing vsync · 2x · Metal`. On a frame-ms spike the max turns `warn`.
The corner can be set with `overlay.stats_corner` (`tr`, `tl`, `br`,
`bl`; default `tr`).

**Toasts.** Bottom centre. A stack of at most three rounded pills in
`font_body`, each shown for 2 s and faded over the last 300 ms. The
fade is drawn by the presenting thread, which recomposes TOAST at 30 Hz
only while a toast is fading.

**Cursor.** See R9. Its size is `24 px * ui_scale`.

**Window size and backends.** Every size is computed from the
placement rect, never the window, so letterboxing, overscan and
`present.filter` keep the overlay on the picture. The same tokens at the
same `out_h` give the same draw list on every backend, and so the same
picture.

**Per-game theme.** A game's `config.default.toml` may set any
`[overlay.theme]` token, plus `font` and `font_bold` (paths relative
to the game's install directory) and `[overlay.cursor]` (R9). The
player's `config.toml` overrides it as usual. The keys apply live, and a
font change rebakes on the worker. A game theme is plain values and
open-licensed fonts. It never holds bytes from the dump. Owner-made
assets, such as a cursor cut from the owner's own dump (F-12), live in
the owner's config directory and are referenced by path, never shipped.

### R9. Mouse and cursor in the menu (new in v1; the user, 2026-10-22)

**Interpretation of "undo mouse capture"** (review F2). The user wrote
"probably we can undo mouse capture ... the only thing we need is that
the cursor hides unless necessary". The design reads it as follows:

1. Relative mode stays, because `mouse_look = "right_stick"` needs it
   for unbounded look.
2. Capture is fully released while the menu is open.
3. Outside the game window, or with the mouse unused, idle hide covers
   "hides unless necessary".

The capture itself was then decided: **"Capture on click"** (the user,
2026-10-22), below.

**Capture on click** (the user, 2026-10-22). The shipped default
becomes `input.mouse_capture = "click"`. The cursor stays free until a
click in the window. Then it is captured for mouse-look. Esc or the
menu releases it. What exists today, and what is new:

- **Exists** (`mouse.c`, `enhance_input.c`): `focus` (the code
  default), `click` and `never`. In `click` mode the first press in the
  focused window grabs and is consumed, F9 (`mouse_release_key`; F8 after save-states task 4.0)
  toggles, and focus loss clears the grab, so the next click is needed
  again.
- **New, `input.mouse_free_keys`:** a list of key names, code default
  `[]`, shipped `["Escape"]`. A press of a listed key while captured
  frees the cursor. The key is not consumed: Escape still reaches the
  game through `[input.bindings]` (START in BLiNX 2, so the game pauses
  as the cursor comes free). It never grabs. A listed key is not a
  clash under rule 2 or the reserved-key warning, because it adds a
  release and takes nothing from the binding. `xbox_InputMouseKey`
  returns 0 for it, and 1 for the release key as today.
- **New, `click` after the menu:** in `click` mode, opening the menu
  clears the grab (`s_clicked`), so after closing the cursor stays free
  until the next click, as the user asked. In `focus` mode, closing
  restores the capture as today. The click that closes the menu (on
  "Resume") is seen while capture is suspended, so it never grabs.
- **Code defaults stay stock:** `focus` and no free keys. Only the
  shipped `config.default.toml` sets `click` and `["Escape"]` (5.3).
- **Env:** none. This follows the input-knob precedent, where only
  `input.keyboard` and `input.mouse` have variables. `cat/docs/env.md`
  gets a row with "none" in the Env column, and the toolkit
  `docs/runtime/config.md` input table gets the same row. There is no
  `recomp_env.h` row, because the key has no variable.
- **Phase and test:** 3F. The `tests/input_keyboard` mouse cases cover
  the free key and click mode after the menu, and `tests/enhance_cfg`
  covers the list parse and the no-clash rule.

**Open and close.**

- On open, the menu calls `xbox_InputMouseSuspend(1)`. That already
  frees the cursor: the window threads see `xbox_InputMouseCaptured()`
  fall to 0 and turn off SDL relative mode (`SDL_SetWindowRelativeMouseMode`)
  or release `ClipCursor` and raw input on Win32.
- The menu also hides the OS cursor (`SDL_HideCursor`, or Win32
  `WM_SETCURSOR` in the client area answered with `SetCursor(NULL)`),
  because the overlay draws its own.
- The pointer is warped to the panel's centre on the first open of a
  session, so it is in view.
- On close, `xbox_InputMouseSuspend(0)` restores the previous capture
  state in `focus` mode, and with it relative mode and the clip. In
  `click` mode (shipped) the cursor stays free until the next click
  (above). The OS cursor returns to the idle-hide rule.
- **The close mask for mouse buttons** (review F7). While capture is
  suspended, `mouse.c` drops button and wheel edges. After a resume,
  it keeps dropping a button's edges until that button has been
  released once. Without this, a left click on "Resume" that is still
  held at close would reach the guest as a held mouse-bound button.
  This mirrors rule 7's close mask for pad buttons. A
  `tests/input_keyboard` case covers it.

**Mouse-look.** Mouse-look is unaffected while the menu is closed. While
it is open, mouse-look is suppressed: suspend stops the motion feed into
the guest-pad mouse path, as `mouse.c` already does for the
"menu" reason, and the neutral pad (D4) covers the rest. Motion,
buttons and the wheel go to the menu only.

**OS cursor idle hide** (the user, 2026-10-22: "Idle-hide on by
default"). When the mouse is not captured and the menu is closed
(`input.mouse` off, before the first click in `click` mode, or
released with F8 or Esc), the OS cursor shows on motion and hides after
`input.cursor_idle_ms` without motion.

- `input.cursor_hide` takes `never`, `idle` or `always`.
- The code default is `never`, so stock is unchanged.
- The shipped `config.default.toml` sets `idle` with 2000 ms.
- The window thread runs the timer from its own event loop (SDL) or a
  `WM_TIMER` (Win32).

**Hand-off from the window threads to the menu thread.** The window
threads already receive every mouse event. They are the SDL main loop
through `xbox_InputSdlMouseEvent`, and the Win32 `wnd_proc` (the walker
on D3D11, the GDI thread on CPU) through `xbox_InputMouseWin32Msg`.
While the MENU layer is visible (one atomic load), they also write a
**menu mouse snapshot**, before the `xbox_InputMouseOn()` gate, so the
menu works even with `input.mouse` off:

```c
struct xbox_menu_mouse {           /* every field atomic, relaxed except seq */
    _Atomic int32_t  x, y;         /* output pixels in the placement rect; -1 when outside */
    _Atomic uint32_t buttons;      /* held: left, right, middle */
    _Atomic uint32_t press[3];     /* press counters per button */
    _Atomic int32_t  wheel;        /* accumulated notches, the natural-scroll sign fixed as today */
    _Atomic uint32_t seq;          /* bumped last with release order */
};
```

- **Coordinates:** SDL3 gives window points, so the window thread
  multiplies by `SDL_GetWindowPixelDensity` and subtracts the placement
  origin. Win32 client coordinates are pixels when the
  process is DPI aware, and are scaled by `GetDpiForWindow` otherwise.
- **Reading:** the menu step (R7) reads `seq` with acquire. When it
  moved, it takes the fields, turns press-counter deltas into clicks
  and takes the wheel delta. So a click between two polls is never lost
  and never doubled.
- **Waking:** on SDL a motion event while the menu is visible also posts
  the overlay frame event, so the cursor redraws without waiting 100 ms.
- **The cursor position** feeds the CURSOR layer directly. The
  presenting thread reads `x` and `y` at each present and composes a
  small list. So on SDL and Metal the cursor moves at the present rate,
  apart from the menu step's own rate.

**Menu interactions.**

- **Hover** moves D5's selection to the row under the pointer and shows
  the `bg_hover` fill. The pad then continues from there.
- **Left click** on a row acts like A: it toggles a toggle, enters a
  page or a mod, and starts a capture on Controls. A click on `<` or `>`
  of a choice steps it. Dragging a slider sets the value, and so does a
  click on its track.
- **Wheel** over a choice or range row steps the value (one step per
  notch, ten with Shift). Over the list elsewhere it scrolls.
- **Right click** is Back, like B: it leaves a page or cancels a capture
  or a confirm. A right click at the top page closes the menu.
- **Middle click** does nothing.
- **Drag** reorders rows on the Save states page (R4).
- **A click outside the panel** does nothing, and the game never gets
  it.
- The hint line switches to mouse and keyboard hints when the last
  input was the mouse.
- **A pad or key press hides the overlay cursor** until the mouse moves
  again (review F4). The selection then follows the pad from the row
  the pointer last hovered, and a resting pointer cannot hover a row
  away from under the pad.
- Mouse buttons are never bindable to actions, so a click can never be
  captured as a binding.

**The cursor in the overlay.** The CURSOR layer is drawn last, above
MENU, only while the menu is open and the pointer is inside the
placement rect. `[overlay.cursor]`:

- `style`: `arrow` (default), `dot` or `image`.
  - `arrow` is a toolkit-drawn arrow: a rounded triangle with a 1.5-pixel
    dark outline and the `accent` fill. It is built from triangles in
    the converter, so it needs no asset.
  - `dot` is a filled circle with an outline.
- `image`: a PNG path (RGBA, at most 128x128), decoded with stb_image
  into an overlay image slot. A missing or bad file falls back to
  `arrow` with one warning.
- `hotspot = [x, y]` in image pixels (default `[0, 0]`).
- `size` in px at 1080 lines (default 24).

A per-game style comes from the game's `config.default.toml` (colours
and the style, or an image the game's own build ships under an open
licence). An image cut from the game's own textures is owner-generated:
the owner makes it locally from their dump (F-12 would add a CLI step)
and points `image` at it, in the owner's config directory. It is never
committed, packaged or distributed.

**Per backend.**

- **Metal and the SDL renderer:** the cursor moves at the present rate
  (the SDL loop wakes on motion).
- **D3D11:** the Win32 window is pumped on the walker at the guest flip,
  so the snapshot is written and the cursor is drawn only at guest flips.
  At BLiNX 2's 30 or 60 flips a second that is usable. During a loading
  pause without flips it freezes, like the rest of the D3D11 overlay
  (R2 gap, F-9). This difference is recorded in TASKS under
  backends-agree. The user, 2026-10-22: "OK for v1, fix later". F-9 (a
  present-only walker path, which must also pump messages, since F10
  and clicks arrive only at flips too; review F8) and F-11 (a hardware
  cursor) stay follow-ups.
- **CPU GDI window:** no overlay, so the OS cursor stays visible while
  the menu is open (R2's gap).

### R10. Guide + A by default (the user, 2026-10-22)

**Bindings.** `menu.open` defaults to `["F10", "guide+a"]` in the
toolkit, in `[input.actions]` and on the Controls page, where the player
can rebind or clear it. F10 stays the keyboard default. A game's
`config.default.toml` adds a fallback pad chord for hosts where Guide is
not seen. BLiNX 2 adds `back+lthumb@400` (R3 rule 3's reasoning).

**How it fits R3.**

- `guide` is host-only, and the original Xbox pad has no Guide, so the
  guest never sees it.
- `a` is a guest button. A single `a` would be refused (rule 1), and a
  plain chord with a guest button needs a 200 ms hold. `guide+a` is a
  modifier chord instead (rule 7).
- **The hold:** none. It fires on A's press while Guide is held, because
  masking makes an accidental fire harmless to the game.
- **Consumption:** A is masked from its own press until its physical
  release, so the game never sees that A. Closing the menu with
  `guide+a`, or with A on "Resume", keeps A masked until release, so
  the game does not see the tail of the press either.
- **Order:** A pressed before Guide goes to the guest and does not open
  the menu.
- **The flip tick** (loading screens) makes its own host read (R3,
  review F1), so it sees `guide+a` with no poll. It fires and marks A
  consumed for the next poll.
- **`guide+y`** for `camera.free.toggle` (the user, 2026-10-22) is
  the same modifier rule: Guide first, Y masked until release.

**Guide per host, with the fallback:**

| Host | Backend | Guide seen? | Fallback |
|---|---|---|---|
| macOS | SDL3 gamepad (GameController framework or HIDAPI) | Usually. macOS may take the Home button itself (System Settings > Game Controllers can give it back to apps for a controller). 3A.9 checks an Xbox and a DualSense pad. | F10; the game's fallback chord |
| Linux desktop, native | SDL3 gamepad (evdev or HIDAPI) | Yes, unless Steam is running with Steam Input on for the pad, which takes Guide for its overlay | F10; the fallback chord; Steam Input off for the title |
| Steam Deck (Proton today; native later) | XInput through Steam's virtual pad (Proton), or SDL3 | No. SteamOS always takes the Steam button, and the grips are not visible through the virtual pad | A grip bound to F10 in Steam Input (documented, R3); the fallback chord; F-6 for a shipped layout |
| Windows, native | XInput (`XInputGetStateEx`, ordinal 100) | Yes, unless the Xbox Game Bar takes the Xbox button (Settings > Gaming > Game Bar, "open with this button"). Windows.Gaming.Input never reports Guide and is not used. | F10; the fallback chord; the Game Bar setting in `config.md` |
| Windows apps under Proton (desktop Linux) | XInput through Wine | Only with Steam Input off for the title | F10; the fallback chord |

The Debug page lists the host-only buttons seen this second (R4). So a
player can check whether Guide reaches the game on their host, and the
hint line on the first open names the fallback when Guide has not been
seen since start.

## Risks / Trade-offs

*Added 2026-10-22 (R7 to R10):*

- **Vendored code.** microui, stb_truetype and stb_image are third-party
  C in the kernel library. They are small, frozen at a version, built
  only under `XBOXRECOMP_ENHANCE` and fed only our own strings, the
  embedded font, a player-named font file and player-named PNGs.
  stb_truetype and stb_image are not hardened against hostile files, so
  a per-game or player font and a cursor PNG are size-capped (8 MB and
  128x128) and parsed on the atlas worker or at arm time, never on the
  poll thread. Detection: the ctests feed a truncated TTF and PNG.
- **Three renderers.** Rounded corners, the AA feather and premultiplied
  blending can differ by a level between Metal, D3D11 and SDL. The
  reference raster and the window-shot comparison (with a small
  tolerance) catch real drift. A D3D11 difference is checked by eye
  until F-10.
- **The D3D11 cursor rate** follows the guest flips (R9), accepted for
  v1 (the user, 2026-10-22). F10 and clicks also wait for a flip there
  (review F8). Mitigation: F-9, which also pumps messages, or F-11.
- **Atlas memory and bake time.** 2048x2048 at 2160 lines is 4 MB, plus
  the upload. A bake runs only on the worker. A window drag through
  many sizes coalesces to the last size.
- **macOS taking Home.** If macOS keeps Guide on the user's pads,
  `guide+a` is dead there. The fallback chord and F10 cover it, and the
  Debug page shows it.

- **The hook runs on the guest's poll thread.** Menu logic must stay
  allocation-free and short (a few hundred instructions per poll); the
  raster runs only on a change. Detection: `RECOMP_TRACE=pacing` flips/s
  with the menu open vs closed (25% rule).
- **Live scale on D3D11 loses target pixels for one frame.** Expected
  invisible (the post chain is redrawn each frame); if a persistent
  target shows garbage under Proton, D3D11 scale becomes "at restart".
- **Fullscreen toggling touches window code on two threads.** Both paths
  exist already (SDL on its main thread, D3D11 `present_resize` on the
  walker); the risk is a resize race with the present extent, covered by
  the existing `present_resize` ordering. If it misbehaves, fullscreen
  stays "at restart".
- **TOML patching.** A file the reader accepts but the patcher misreads
  (a key set twice across a dotted and a table form is already refused by
  the reader) must not be damaged: the patcher re-parses its output and
  refuses to rename over the original when the parse differs in any key
  but the ones it changed. ctest cases include comments after values,
  quoted keys, dotted keys, CRLF.
- **BC3 is lossy.** Range-fit DXT5 can band a gradient and nick a thin
  anti-aliased stroke. Text sources are DXT3/DXT5 already (so the game's
  own quality bar is a block format), BC3 is off by default for art and
  the atlas, and the preview page shows raw beside BC3 per entry with an
  override. Detection: the owner's eye in the preview and a Metal
  `@stage1` dump of the Mission Objectives screen; mitigation: the
  override, or `[text] bc3 = false` at the cost of disk.
- **A several-hundred-MB pack.** Lazy per-entry reads keep the resident
  set to what a screen shows, but a slow disk shows a one-frame stall at
  first use of a big caption. Detection: the `tex_pack` trace's upload
  times; mitigation: `[text] languages` and patterns narrow the set, and
  a later prefetch of a screen's entries is a follow-up if measured.
- **Pack v2 and the public pin.** The runtime pin in the public build
  still predates the pack loader (TASKS (c)); v2 widens that until the
  next push round re-pins. The CLI could write v1 when no entry is
  flagged, but one format is simpler: v2 always, and the push round
  carries both.
- **Pure-Python preview speed.** xBR on a 64x64 crop at 4x is ~60 ms; a
  full 256x256 is ~1 s. The page renders crops live and full textures on
  demand, and shows the build-time estimate.
- **Browser availability.** The Deck in game mode has none; the tool is a
  desktop step on the owner's machine, like `enhance hud`.
- **Overlay in dumps.** The D3D11 stock path copies the frame into the
  back buffer, then the overlay is drawn there; `dump_frame` runs before
  the overlay draw and reads the back buffer only on that path. The
  spec states it and 6.x checks a dump taken with the menu open equals
  one taken closed.

## Migration Plan

*Phases 3, 4, 5, 6 and 9 are re-split in R5 (2026-10-21). The text below is the 2026-10-11 plan, kept for the other phases.*

Phases, each mergeable alone (one worktree and agent at a time):

0. **The tracker item merges first** (`fix/hud-pack-text`, its own review): the
   MIX/XPR0 reader and the `lng_us` patterns. This change rebases on it.
1. **Toolkit live plumbing** (no UI): `nv2a_host_opts_request/apply` in
   both backends and the null/CPU ones, texture generation, pack
   `set_enabled`/kinds, v2 reader with kinds and the BC3 upload path in
   both backends, miss ring and `tex_pack` trace, the `textures.font`
   and `textures.text` keys. ctests `host_opts_live`, `tex_pack` v2.
   Goldens unchanged on Metal; Proton for D3D11. The CLI's v2 writer with
   kind flags, per-kind scale, BC3 encoder and `languages` ships in the
   same phase (small, and the toolkit's `tex_pack` test vector for BC3
   is shared with the CLI's test), so the owner's pack is v2 from here.
2. **Configuration layering** (P1, its own openspec change):
   `config.default.toml` read by the runtime, `config.toml` as
   differences with env on top, `RECOMP_CONFIG` (legacy name kept in the
   row), the automatic rename, the launchers, `blinx2 package`, docs and
   the golden pin. Before the menu, so Save never targets `enhance.toml`;
   after phase 1 for the reasons in P1.6.
3. **Overlay + menu**: `nv2a_overlay`, the three presenter blits, the
   input hook, `enhance_menu` with the toolkit pages, `menu.*` keys,
   the `[ENHANCE] menu...` line, the differences-only patcher and Save.
   ctests `overlay`, `enhance_menu`, `recomp_cfg_patch`. Metal
   verification with a window shot; Proton for D3D11.
4. **CLI golden harness**: `menu.enabled`, `textures.font`,
   `textures.text` in `ENHANCE_STOCK`.
5. **cat**: game items, atomic glow, `config.default.toml`, env rows,
   README; the Mac runs with the menu open over `@stage1`.
6. **Proton** (D3D11) checks of phases 1-5 on "go".
7. **CLI preview, upscale mode**: the server, the page, the picker,
   filters and parameters (xbr 3x, epx, lanczos, external with the local
   open-source presets), the log import, Save; `enhance hud --config`.
   pytest on synthetic trees.
8. **CLI preview, font mode**: the three curated faces and the cache,
   the owner's file by upload, the Google Fonts fetch with its licence
   file, the fit knobs in `atlas.render`, the text line. The owner
   rebuilds the PT Sans pack from a saved config and compares shas.
9. **Menu Controls page**: chord and hotkey as items, the capture
   action, persistence (D5). After phase 6 so the capture is tested on
   a real pad on both hosts.
10. **Baked-text re-render**: the spike (D16; one screen, go/no-go in
    TASKS), then, on go, `[text] rerender = true` with per-entry opt-in,
    the owner's string table in the preview tool and optional local OCR
    drafts.
11. **Follow-ups** (own changes): the mods list (D11), D3D11 scale or
    fullscreen "at restart" if phase 6 says so, the GDI-window overlay.

Rollback: every key defaults to stock; a build without `XBOXRECOMP_ENHANCE`
has no hook, no overlay call site reached and no menu. Removing
`[menu] enabled = true` from a config returns the player to today.

## Phase 1 as built (deviations and choices)

Toolkit `feat/enhmenu-p1` 2fc5d3c, CLI `feat/enhmenu-p1` 5c54e35. Where
the text above left a detail open or did not fit the code, the smallest
sound choice was made:

1. **Spinlock, not a mutex** (D1). `nv2a_backend_common.c` has no OS
   headers (the CPU, Metal and D3D11 libraries and the ctests all link
   it), so the pending struct and mask sit under a C11 `atomic_flag`
   spinlock; the flip reads one `atomic_uint` pending flag first, so a
   flip with nothing queued takes no lock. `apply` returns the mask of
   fields whose value changed (scale 0 and 1 are the same value) and
   bumps `nv2a_host_opts_gen()` once per apply that changed something.
2. **One place bumps the texture generation** (1.2). `nv2a_tex_pack_set_enabled`
   and `set_kind_enabled` bump `nv2a_tex_pack_gen()` themselves when what
   matches changes, and `nv2a_host_opts_set`/`apply` call them through the
   `pack_off` bits (`NV2A_PACK_OFF_ALL/FONT/TEXT/ART`), so the backends do
   not bump it on `NV2A_OPT_PACK`; a setter called anywhere else (a test,
   a later menu path) cannot forget it. `nv2a_backend_common` now links
   `nv2a_tex_pack.c`; the `nv2a_tex`, `rt_alias` and `render_scale`
   ctests list it.
3. **v2 header field for the text scale** (D2b). Offset 24 is a u32 text
   scale (0 means the header scale) and 28 a reserved u32 that must be 0;
   v1 keeps its u64 reserved at 24. Informational, like the scale.
4. **BC3 entries are whole blocks**. A BC3 entry's width and height must be
   multiples of 4 (refused otherwise, "BC3 entry not a multiple of 4"), so
   every level the backends create is whole blocks on both APIs. The CLI
   keeps an entry that is not raw A8R8G8B8 with a note. Every BC3 entry
   in this game's set passes.
5. **TEXT is a language archive entry or a `text` pattern** (D2b, review
   note). MIXF/XPR0 provenance alone does not make an entry TEXT: the
   kind comes from the picked language's archives and from
   `[enhance.hud] text` patterns; the atlas (no sub) is FONT; everything
   else is art.
6. **Text is built at 2x with xbr, BC3** (`TEXT_SCALE = 2`). Lanczos, the
   per-kind filters and `--config` are phase 7; the art payloads are byte
   for byte what they were (a CLI test pins it).
7. **`--language` defaults to the first language listed** in
   `[enhance.hud] languages`, not a hard-coded `us`, so the CLI stays
   game-agnostic; an unknown language is an error. Language archives are
   read only when picked, whether or not `archives` lists them, and each
   unpicked language prints one line. cat lists only `us` for now: the
   `lng_us/...` patterns select nothing in another language's archive, and
   the other languages' patterns come with phase 5's `text` patterns.
8. **BC3 decode tolerance**. The CLI encoder and both GPUs expand 5:6:5
   endpoints by bit replication; the toolkit's `d3d8_dxt_decode_texel`
   uses `v * 255 / max`. The shared vector is exact for alpha and allows
   1 on colour in `tests/tex_pack`.
9. **The miss ring is not thread-safe**. It is written from the upload
   path of the one render thread; phase 3's menu reader must read it at
   the flip (or the ring gains a lock then).
10. **D3D11 is compiled, not run, on the Mac**: the toolkit and a full cat
    Windows build go through llvm-mingw (`third_party/llvm-mingw-*`) with no
    new warnings. BC3 upload with block-row pitch, `pack_gen`, the miss call
    and `scale_drop` (which also clears `s_cur` and `s_stage_rt[]`, both
    pointers into the released targets) were also read by eye. Phase 6
    runs it.
11. **Live `present.filter` and `present.fullscreen`** update only the
    stored value in phase 1; the presenters act on them in phase 3.

12. **1.9 evidence (Metal, `@stage1`, render scale 2)**. The v2 pack from the
    the tracker item set is 158.8 MB: 427 entries, 267 art (140.4 MB), 1 font (4.2 MB),
    159 text (14.2 MB, all BC3 at 2x). The five Mission Objectives textures
    (three `mis_r01s01_01` lines, `demo_font01obj`, `demo_or_mis`) hit from
    the pack and show no misses; with `RECOMP_TEXTURES_TEXT=off` the same five
    miss as DXT3 candidates and the hit count drops from 21 to 16. The final
    miss ring (64 entries, 36 candidates) is in `runs/enhmenu/misses-metal.txt`.
    The stock goldens (attract, stage1, story) pass with `textures.pack=none`.
13. **Review fixes (phase 1)**. Both GPU backends now present first and
    apply live options after (`d3d11_on_flip`, `metal_on_flip`): applied
    before, the present sized a frame drawn at 2x by the new 1x scale and
    showed its top-left quarter for one flip. `scale_drop` drains the pending
    occlusion queries (`nv2a_occ_poll(&s_occ, 1)`) before the new scale, so
    none is divided by the wrong factor. A miss of a texture the pack holds is
    tagged with why: ` (text off)` / ` (font off)` / ` (art off)`,
    ` (pack off)`, or ` (entry refused)` when the backend could not use the
    entry; both backends now count a refused entry as a miss, and Metal
    checks `supportsBCTextureCompression` (an older iPad) and says once that
    BC3 entries go up from the guest. Rerun with text off: the five
    objective hashes carry ` (text off)` (`runs/enhmenu/stage1-textoff-fix`).

## Phase 3B as built (deviations and choices)

Toolkit `feat/overlay-3b` e505511a, squashed as 8a87ec1a.

1. **Arming** (review H1). STATS and TOAST are armed in
   `xbox_enhance_init` on the init thread, hidden, right after
   `enhance_actions_start`, whenever the actions hook is armed (a feature
   key is on, rule 6). We chose this over arming at the presenter's first
   poll: it keeps all arming on one thread, and its only cost is the font
   bake (the `[OVERLAY] atlas` line prints its ms; 1.9 ms on the Mac,
   9.2 ms on the Deck) and the lists of two layers. Stock leaves the hook
   and the overlay disarmed, so a golden has no atlas line (4.1). A toast
   sent from a mod's init, which runs before the arming, is only its log
   line.
2. **One font weight** (review L5). Atkinson Hyperlegible Bold and
   `stb_image.h` are dropped until a theme token or image loader needs
   them (3C/3D/3E); only Regular is embedded.
3. **Title FPS** (review M5). `xbox_title_format`'s FPS reads
   `NV2A_STAT_FLIPS` in ENHANCE builds: `RECOMP_TITLE_STATS` sets
   `nv2a_stats_use(NV2A_STATS_TITLE, 1)` on both the SDL and the
   Metal/D3D11 title paths, so the title and the strip agree. Stock
   builds keep their own counter.
4. **Buffers.** Metal keeps three buffer sets per layer, refilled only
   when the list changes; D3D11 refills on every present (review2 L-f:
   revisit only if 3C's menu shows a cost on the Deck).

## Phase 3C as built (deviations and choices)

Toolkit `feat/overlay-3c` 032959df and 3ba941cc, review fixes
a64cbb4a.

1. **One queue, applied at the flip.** `nv2a_host_opts_request` may be
   called from any thread; the request lands at the next flip on the
   walker thread, which bumps the options gen with release. The SDL
   presenter reads the gen with acquire and reacts to filter and
   fullscreen changes. New mask bits: ANISO 0x10, MOVIE 0x20,
   OVERSCAN 0x40.
2. **Clamps and refusals.** aniso clamps to 0 or 2..16; a movie mode
   past `fill` and an overscan with a wide aspect are refused with one
   line each. The CPU and null backends accept the bits and log scale
   and overscan as ignored, naming the backend (3C.1).
3. **D3D11 fullscreen stays live.** `fullscreen_switch` runs in on_flip
   on the walker thread and `present_resize` follows at the next flip.
   The Linux/Proton smoke (GE-Proton11-7, four toggles, 0/2277 mismatched
   presents, 32.5 flips/s) showed no resize race, so the "applies at
   restart" fallback was not needed.
4. **macOS fullscreen without Spaces, only when live.** A Spaces
   fullscreen does nothing for an app that is not frontmost while SDL
   reports success, so a live switch from a background run never took
   effect. The presenter sets `SDL_HINT_VIDEO_MAC_FULLSCREEN_SPACES` to 0
   before `SDL_Init` only when a live switch is armed: fullscreen
   configured, the overlay armed, or `opts_at` set. A stock run keeps
   Spaces (Ctrl-Cmd-F still enters a Space). The env var still wins.
   `SDL_RaiseWindow` instead was rejected: macOS decides whether a
   background app may come forward (it may only bounce the Dock icon),
   and a menu switch should not steal focus. The policy for the enhanced
   case is not decided yet; `MAC_SPACES_OFF_LIVE` in `fb_present_sdl.c`
   flips it (0 keeps Spaces everywhere).
5. **Pacing** goes through `xbox_enhance_set_pacing` (appended to
   `enhance.c` and `.h`), which wraps `xbox_PacingSetMode`.
6. **Test hook.** `RECOMP_DEBUG=opts_at` (debug tier, comma list of
   `flip:key=value`) makes live requests at given flips and logs each
   one; the pacing branch logs the mode it read back. The parser is its
   own unit, `nv2a_opts_at.{c,h}` (32 entries at most, a bad entry is
   skipped with one line), with the `opts_at` ctest. The Mac evidence is
   under `runs/overlay-3c/live/` and `live-r/`.
7. **Review fixes (a64cbb4a).** A failed `SDL_SetWindowFullscreen` is
   logged and the state kept, so the next gen change retries. D3D11
   saves the windowed placement with `GetWindowPlacement` and restores
   it with `SetWindowPlacement`, so a maximised window comes back
   maximised. `enhance.c` uses `NV2A_OVERSCAN_MAX`.

## Phase 3D as built (deviations and choices)

Toolkit `feat/overlay-3d` 97423edb (`recomp_cfg_patch`), bb104b9e (the
menu, mod API v2) and 0cf4bddf (a mod switched off keeps its keys
quiet).

1. **Pages.** Eight tabs: Render, Pack, Game, Mods, Stats, Controls,
   Debug, Save. Reset is a confirm row on the Save page ("Reset
   everything? A / Enter: yes"), not a ninth page. Save is F5 or Y from
   any page, as well as the Save row.
2. **Live classes.** Each row shows its class (a dot for live and at the
   flip, "next stage", "applies at restart") and the footer names the
   selected row's. `input.mouse_capture` is live (window thread). There
   is no environment flag to force a class.
3. **Environment wins.** An item whose key the environment sets shows
   "(environment)" and does not change, because the next start would
   undo the change.
4. **Values in force.** A row's value is the value in force (`get`); the
   menu steps from its own current value, so two presses before a flip
   land as two steps.
5. **Neutral pad.** While open, the title sees a neutral pad with the
   packet number frozen at the value at open plus one, and the closing
   poll is neutral too: the filter took that poll's mask before the
   release marks the held buttons, so A leaked one poll without it.
6. **Texture pack toggle is session only** (`ENHANCE_ITEM_NOSAVE`): the
   pack's own key names a folder, and a toggle that wrote `false` would
   lose it.
7. **Controls.** A capture writes source names (`"P"`, `"guide+a"`) and
   refuses a key the guest's `[input.bindings]` uses, with a toast
   (`K refused: 'K' is bound to the guest's right_stick_down`). The Mouse
   group shows the configured release key (F9 today; save-states 4.0
   moves it to F8) and "Free keys: none (3F)".
8. **Debug.** No cache or target counts (the backends export none yet);
   the pack miss total and the top three of the miss ring, read from a
   snapshot the flip writes under a spin flag (a reader in the middle of
   a copy makes the writer skip that flip). Missing glyphs is "n/a (3E)"
   and the window shot row reads "RECOMP_WINDOW_SHOT only" (the menu
   action waits for F-10 on D3D11 and a shot helper on Metal).
9. **Mods.** `mods.<name>` (bool, default true) under `[mods]`, quoted
   when the name has a dot (`"camera.free" = false`). A mod off by its
   key is not inited, and its keys (those starting with its name) count
   as read, so no "unused key" lines. cat's `camera.free` gives no
   `on_enable`, so its row says "applies at restart". A mod whose
   settings sit under `[mods.<name>]` would clash with the bool; no mod
   does that today.
10. **Mac checks** (`runs/overlay-3d/live/`): L1 open with F10, scale
    1→2→3→1, filter, the pack toggle, camera.free off, a refused capture,
    F5 (2 keys written), with window shots and `fb_dump` of the same flips
    (panel in the shot, not in the dump); L2 restart: the filter and the
    mod state came back, P captured for `overlay.stats` and saved; L3
    restart: P toggles the stats strip, the file unchanged; P0/P1 menu
    closed vs open 15-40 s: 60.0 vs 60.0 flips/s, walk 1.31 vs 1.31 ms,
    present 0.62 vs 0.62 ms; L4 Controls and Debug pages. Stock Metal
    goldens pass with `menu.enabled=off` (`runs/overlay-3d/metal-golden-234427`).

## Fix 2026-10-27: one input, one action

On the Deck the Controls capture saved plain `F10` for `overlay.stats`
(`runs/overlay-3d/deck-handson-287/game-20261027-054627.log`, lines
2555-2606). R4 is a Steam Input mapping that sends F10, the capture's key
loop took it before the pad chord with the triggers could form, and
`capture_finish` checked only the R3 rules and the same action's
duplicates. Dispatch fired every binding that matched, so each F10 then
opened the menu and toggled the strip. Nothing quieted the bindings during
a capture either: the menu only ignored its own `menu.open` request.

Toolkit `fix/chord-conflict` (`enhance_actions.c` rules 8-10):

1. **One input fires one action.** At table build, of two bindings on the
   same input (a key and its modifiers, side for side as `key_cond` reads
   them, or the same pad bits and port, any hold) `menu.open`'s keeps it;
   of any other two a written one beats a default, and otherwise the
   first registered wins (the toolkit's before the mods'). `menu.open`
   never gives way because the menu is the one in-game place to repair a
   binding, and on the Deck under Proton its other defaults are out of
   reach (`guide+a` is Steam's recording, XInput has no `paddle1`), so a
   written `overlay.stats = "F10"` would lock the player out. That keeps
   "F10 SHALL stay bound by default on every host". Written beats default
   so a player's binding still takes a mod's default (`camera.toggle =
   "F6"` over another mod's default F6), which mod-settings relies on. A
   binding is judged against every kept one before it takes any input,
   so the log never says a binding won that is then refused. The claim
   is an int (`claim()`: menu 2, written 1, default 0) so mod-settings'
   env tier fits beside it. The loser gets one line.
2. **Capture refuses an owned binding**, through `enhance_action_owner`:
   `F10 refused: Open the menu has it (F10); clear it there first`, as
   status and toast.
3. **Longest match.** A pad binding whose bits are a strict subset of a
   longer one's on the same port is shadowed: it fires on release after
   its hold, and only when no longer binding was held whole while it was
   held. A longer binding held whole spends the shorter ones even when it
   is let go before its own hold and fires nothing: one press, one action
   (back+start@400, then left_thumb for 200 ms, fires neither). Captured
   guest chords all get `@400`, so this is the shape players make, and
   mod-settings B.8 reuses the rule. The
   step runs in passes so the result does not depend on table order. The
   cost is release latency, and only where a longer binding exists
   (`paddle1` beside `paddle1+b@300`).
4. **Quiet capture.** `enhance_actions_quiet` is on while the capture
   phase is not off; inputs held then are spent until released. Turning
   it off drains through port 0's next step (keys step there; the pad
   hands the menu the same held its step saw, so other ports need no
   drain and do not wait for port 0): the menu reads keys after the
   step, so a key that went down in between ends the capture before any
   step saw it, and would otherwise fire its owner (`menu.open`, closing
   the menu) on the next step.
5. **Mods.** `mod.h`'s `action_down` says a binding inside a longer one
   never reads as down. No build line for a shadowed binding: rule 9 is
   documented, and a line per shadowed default would print on every start
   once a player binds a chord over one.

Not covered: a key and a pad source are never one binding, so on the Deck
R4 (F10 through Steam Input) plus the triggers cannot be captured as a
chord; the capture refuses the F10. A saved `overlay.stats = "F10"` is
refused at build with a line and R4 opens the menu again, so the Deck
config needs no edit; the dead binding stays in the file until the
player clears it in the menu.

## Decided (the user, 2026-10-11)

The seven open questions of the first draft, answered the same day:

1. **Menu on by default** in the shipped `config.default.toml`; the code
   default stays off and goldens pin `RECOMP_MENU=off` (D6).
2. **Upscalers:** the 2026-10-06 rule meant no bundled or default call to
   a service that can cost money. Any upscaler is allowed; open-source,
   locally run ones come first; a paid or remote one is the owner's own
   command and their responsibility (D14).
3. **BACK+START** and **F10**, overridable in the file from phase 3 and
   from the menu's Controls page (capture a chord or key) in phase 9
   (D5).
4. **Env overrides and Save** (settled later the same day, P1): env stays
   on top of `config.toml`; `enhance.toml` becomes `config.toml` over a
   shipped `config.default.toml` with automatic migration and no notice;
   the file and the menu cover enhancement and mod keys only, so no
   `launch.env` host setting moves. Sub-questions 3-6 decided too:
   differences-only user file, the per-title file kept, `config/` in the
   repository, and the rename landed before the menu (phase 2).
5. **Fonts:** three curated faces; the owner's own file by drag-and-drop
   or picker; a Google Fonts family through the google/fonts repository
   with its licence file kept beside the font (D12).
6. The tuning config lives in **`config/`** in the game tree (D13).
7. **Game-agnostic text policy:** any pre-rendered text texture is the
   `TEXT` kind at 2x with BC3; the owner selects the languages to build
   (D2b). Re-rendering baked text in the chosen face is assessed in D16
   and placed late.

## Decided (the user, 2026-10-22)

The 2026-10-21 questions 1 and 3, part of 2, and three new requests:

1. **A richer UI toolkit with a proper font**, replacing the 8x8 bitmap
   panel (D3, R2). The design picks microui with stb_truetype and an
   embedded OFL face, one draw list and one renderer per backend (R7),
   and defines the look (R8).
2. **Mouse in v1** (removed from the non-goals): capture and relative
   mode released while open and restored on close, the OS cursor hidden
   unless needed, a game-styled overlay cursor, hover, click, wheel and
   right-click back, mouse-look suppressed only while open (R9).
3. **Guide + A by default** for `menu.open`, configurable in
   `[input.actions]` and on the Controls page; F10 stays the keyboard
   default (R10, R3 rule 7). This answers the `menu.open` half of the
   old question 2.
4. **No pause.** D7 stands, and no pause callback is added (old
   question 3).
5. **SDL3 has landed** (Done). Phase 3 uses the SDL3 names, and
   F-3 is dropped (old question 1).
6. **A Save states page** for phase 5 of `save-states`: list,
   rearrange, delete, export, import (R4, phase 3G).

Round 2, after the review (the user, 2026-10-22, quoted):

7. **The UI face:** "Atkinson Hyperlegible", replacing the Inter
   proposal. The Regular and Bold TTFs are committed to the toolkit
   unmodified with `OFL.txt` (R7). The toolkit round audit gets the
   allow-list entry, and the README licence table gets its rows (R7,
   3B.1). Old question 7.
8. **The D3D11 cursor rate:** "OK for v1, fix later". F-9 and F-11 stay
   follow-ups, and F-9 also pumps messages (review F8). Old question 8.
9. **Idle hide:** "Idle-hide on by default". The shipped default is
   `input.cursor_hide = "idle"` (2 s), and the code default stays
   `never`. Old question 9, and review F6.
10. **D3D11 fullscreen live and the Deck layout:** "Accept both". D3D11
    live fullscreen is in v1 scope (3C). The Deck grips are documented
    in `config.md` only, and F-6 waits for a request. Old questions 4
    and 5.
11. **Free camera pad default:** "Yes, Guide + Y". `camera.free.toggle`
    gets `guide+y` under rule 7, Guide first (5B.1). Old question 2.
    `overlay.stats` stays unbound, reachable from the Stats page.
12. **Save-state export path:** "Folder next to saves", that is
    `<save dir>/exports/<game>/`, with an Open folder row, plus the
    SDL3 save dialog where it works (R4, 3G). Old question 6.
13. **Mouse capture:** "Capture on click". The shipped default is
    `mouse_capture = "click"`, and Esc (`input.mouse_free_keys`) or the
    menu releases the cursor (R9, 3F). This answers review F2.
14. **Hotkey clash:** "Save states keep F5/F9". The mouse release moves
    from F9 to F8, and the free-camera reset from F5 to Home, active only
    in free-cam (R3 actions table). Both ship today on the old keys.
    Save-states task 4.0 rebinds them, with the docs rows and ctests,
    before its hotkeys land.
15. **The free-camera freeze key:** `End` (orchestrator, 2026-10-22,
    follows from the user's F8 choice; the user may override). cat
    shipped `camera.free_freeze_key = "F8"`, which is now the mouse
    release, and the mouse is captured while flying, so F8 would both
    freeze the world and free the cursor. `End` sits beside Home's
    reset, is in no default key map, and acts only while flying.
    Save-states task 4.0 moves it in the same merge as the release.

## Still open (2026-10-22)

None. Every question of 2026-10-21 and 2026-10-22 is decided above.
