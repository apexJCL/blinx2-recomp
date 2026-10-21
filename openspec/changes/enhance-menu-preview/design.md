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

Non-goals: see the proposal. Also: a menu that edits bindings or input
(that is `input-real-devices`), localisation, mouse input in the menu,
and a GUI on the CPU path's GDI window.

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
registers `enhance_menu_on_open(cb)` and presses its own pause from the
callback (cat does not, in this change). The 3D keeps rendering behind
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
`path.tmp` and renames, never reorders or drops a comment, never touches
another key, and refuses (one line) when the file does not parse first
or when its output does not re-parse to the original plus the changes.
Values are written in TOML spelling (`scale = 2`, `filter = "linear"`,
`enabled = true`).

Save writes to the `config.toml` the layer read (the title file when
there was one, else the data root's); when the layer read no file
(`RECOMP_CONFIG=none`, the golden pin) Save is shown dimmed as "no config
file". The environment stays on top (P1): the menu marks an env-forced
item "(env: RECOMP_...)", lets the player change it live, and Save writes
the file value only, which the variable overrides again at the next
start. `config.default.toml` is never written: it belongs to the install.

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
- SDL3 has **not** landed. The toolkit is still on SDL2, and the
  SDL3 branches in cat are unmerged. The user's standing order (TASKS,
  2026-10-11) is "SDL3 before enhance-menu phase 3". R3 is written so it
  works either way: SDL2 already has every button it needs (2.0.14+), and
  the SDL3 port is a rename table. Which comes first is open question 1.
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
| `present.fullscreen` | stored only | F on SDL and Metal; D3D11 in 3C or after a follow-up (question 4) | SDL (Metal, CPU): `SDL_SetWindowFullscreen` on the SDL main thread when the host-opts gen moves. D3D11: a `WS_POPUP` or overlapped style swap with `SetWindowPos` on the window thread, then `ResizeBuffers` at the next flip. Cost: one swap-chain resize. | Today it is read only at window creation. D3D11 is the larger half (R5 phase 3C). |
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
| `input.mouse_capture` | R | F | Grab mode (focus, always, never). A change re-grabs the window on the SDL main thread (`SDL_SetRelativeMouseMode`) or the Win32 window thread. | Window-thread work, like fullscreen. |
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
  and Metal; D3D11 per question 4), the pack toggle, `textures.font`
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

D3's choice stands: a hand-rolled CPU-rasterised RGBA8 buffer, the
public-domain `font8x8_basic`, and one alpha-blended quad per presenter.
Checked against today's presenters, it changes in four ways.

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
  draws after `SDL_RenderCopy(frame)` and before `shot_save`, so window
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

**Text.** `font8x8_basic` at integer scale: 1x for the stats strip at
480 lines and 2x from 960, 2x or 3x for the menu as in D3. ASCII only.
Item labels and mod names are ASCII by rule (a non-ASCII byte draws as
`?`). A proportional face (the game's own PT Sans atlas) is not worth a
font rasteriser in the kernel library. It can come back with microui if
the pages outgrow the list.

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
| `menu.open` | toolkit | `F10`, plus a pad chord (question 2) | press (toggle) |
| `overlay.stats` | toolkit | `F12`? (question 2) | press (toggle) |
| `shot.window` | toolkit | none | press: writes a window shot to the run dir |
| `camera.free.toggle` | cat mod `camera.free` | `F6`, plus a pad chord (question 2) | press |
| `camera.free.hud` | cat mod | `F7` | press |
| `camera.free.freeze` | cat mod | `F8` | press |
| `camera.free.reset` | cat mod | `F5` | press |

Names are `<owner>.<verb>` in lowercase ASCII. A mod's actions start with
its mod name. Duplicate names are refused at registration with a log line.

**Config.** `[input.actions]` maps an action to a list of bindings. An
empty list unbinds it:

```toml
[input.actions]
"menu.open"          = ["F10", "back+lthumb@400", "paddle1"]
"camera.free.toggle" = ["F6", "back+lthumb@400"]
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
  The chord is read on port 0 unless prefixed `pad2:` to `pad4:`.
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
   (F9 by default). Modifiers count as keys. Ctrl and Shift are guest keys
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
4. Defaults use only F-keys, two-button chords with a hold, and
   host-only buttons. A game's `config.default.toml` may override them
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
That covers keyboard and host-only buttons only, never guest-button
chords, so `menu.open` from F10 or a paddle works on a loading screen.
The flip tick reads the host-only state through a backend call that is
safe off the poll thread (an atomic snapshot the backend refreshes at
each read), and only when the filter is armed.

**Extra buttons: the backend seam.** `input_backend.h` grows
`uint32_t host_extra` beside the guest state. Each backend fills it, and
it reaches the filter as `xbox_host_pad.extra`:

| Backend | Buttons | How |
|---|---|---|
| SDL2 GameController (macOS, Linux native, Windows non-XInput) | `guide`, `misc1`, `paddle1-4`, `touchpad` | GUIDE is already in the SDL button table (`input_map.h` ~67, index 5) but maps to no guest button, so it only needs routing to `extra`. The new reads are 15..20 (`MISC1`, `PADDLE1-4`, `TOUCHPAD`; SDL 2.0.14+) through `SDL_GameControllerGetButton` in a second loop. `XBOX_SDL_BUTTON_COUNT` stays 15 for the guest map. |
| XInput (Windows, Proton) | `guide` | `XInputGetStateEx` (xinput1_4 ordinal 100; Wine implements it), resolved with `GetProcAddress` by ordinal. Nothing else exists in XInput. |
| Keyboard | none | Keys are already the key path. |
| SDL3 (when the tracker item lands) | the same names | `SDL_GAMEPAD_BUTTON_GUIDE`, `MISC1`, `RIGHT_PADDLE1` and so on. A rename table only. |

**Steam Input and the Deck.** Under Proton, Steam Input is on by default
and presents a virtual XInput pad. The back grips (L4, L5, R4, R5) are
not visible to XInput, and the guide button opens Steam. So on the Deck
the documented way is to bind a grip **in Steam Input** to a keyboard key
(`F10` for the menu, `F6` for the free camera) or to the pad chord. The
key path then fires the action unchanged.

Caveats, all for `config.md`:

- **Guide under Proton** reaches `XInputGetStateEx` only with Steam
  Input off for the title. Otherwise Steam takes the button.
- **Native Deck paddles** (Linux build, Steam Input off) need SDL2 2.26 or
  later with the HIDAPI Steam Deck driver. Older SDL sees the Deck as a
  plain pad without paddles.
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
5. **Stats:** a full-page version of the STATS layer with a 120-frame
   frame-ms graph drawn as bars, the pacing mode, and per-second flips,
   presents, draws and texture uploads. It also has the toggle for the
   corner strip (`overlay.stats`).
6. **Controls:** every registered action with its bindings, plus capture
   (the next key, two-button chord held 400 ms, or host-only button;
   refused under the R3 rules) and clear. This replaces phase 9's two
   menu items.
7. **Debug:** backend and presenter, host-opts gen, texture-cache and
   target counts, the pack miss ring, the input sources with the extra
   buttons seen this second (to test a paddle binding), "write a window
   shot" (`shot.window`), and the trace channels the `recomp_env` table
   flags as live (a new `LIVE` flag in the X-macro rows; none is live
   today, so the page lists them read-only until a row opts in). On
   D3D11 "write a window shot" is disabled until F-10.
8. **Save** and **Reset to stock.**

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

**The guest keeps running** (D7 stands). The question for the user is
whether the menu should also pause the guest, through a title callback
(`enhance_menu_on_open`), when a title supplies one. cat does not in this
change.

### R5. Phases from 3 on (supersedes the Migration Plan's 3, 4, 5, 6 and 9)

Each phase has its own worktree and agent and merges on its own. Estimates
are agent-days including gates. Toolkit phases branch off
`posix-host/portability`.

| Phase | Content | Estimate | Depends on |
|---|---|---|---|
| **3A. Host actions** (toolkit, plus cat glue) | `xbox_enhance_pad_filter` in the toolkit, called from `xbox_InputGetState`, plus the cat glue in `cat_pad_get_state`; `enhance_actions` (registry, `[input.actions]` parser with the R3 rules, chords with a hold, consumption, `chord_delay_ms`, the flip tick, the `actions hook=` line, the rate-limited `[ACTION]` line); `host_extra` in the SDL2 and XInput backends (`XInputGetStateEx`); `menu.open` firing only a log line until 3D; mod API v2 `action_*` and `toast` (a log line until 3B); `[input.bindings]` and actions rebuilt live by pointer swap; the input setters of R1. ctests `input_actions`. Docs: `config.md`, the input README, the Deck paragraph. | 2 | none |
| **3B. Overlay core and stats** (toolkit) | `nv2a_overlay` with triple-buffered layers and canvas handles, `font8x8`, the three presenter blits (SDL with the dirty wake, `fbm_present` layers argument, D3D11 after `dump_frame`); `nv2a_stats` (gated on `nv2a_stats_on`) and the STATS strip; `overlay.stats` key and env row; the TOAST layer. ctests `overlay`. Mac Metal and SDL-renderer window shots, plus an `fb_dump` of the same flip without the overlay; flips/s with the strip on within 5%. | 2 | none (parallel with 3A) |
| **3C. Live-switch completion** (toolkit) | Mask bits `ANISO`, `MOVIE`, `OVERSCAN`; the SDL loop reads the filter each present; SDL fullscreen on the main thread; D3D11 fullscreen style swap and `ResizeBuffers`; pacing and input setters. `ASPECT` is left to the Hor+ change, and its row is written there. ctest `host_opts_live` cases for the new bits. | 1.5 | none (parallel) |
| **3D. Menu** (toolkit) | `enhance_menu` (D5 and R4 pages: Render, Pack, Game, Mods, Stats, Controls, Debug, Save, Reset); the miss-ring snapshot (3.11); `recomp_cfg_patch` and Save; the mouse suspend (3.12); mod API v2 `menu_add` and `on_enable`; `menu.enabled` key. ctests `enhance_menu` and `recomp_cfg_patch`. Mac checks of the old 3.9 and 3.10. | 2.5 | 3A, 3B, 3C |
| **4. CLI golden** | `ENHANCE_STOCK`: `menu.enabled`, `overlay.stats` (stock `off`), `textures.font` and `textures.text` (stock `on`); a check that a golden log carries no `[ACTION]` fire line. | 0.5 | 3A, 3B, 3D (the log lines) |
| **5A. cat items** | Atomic glow (D9), Game items, `[menu]` and `[input.actions]` in `config.default.toml`, env rows, docs. | 1 | 3D, 4 |
| **5B. Free camera onto actions** (cat) | Register the four actions through API v2; drop the private edge detector; old keys become aliases; `camera.free` live through `on_enable`; speed and sensitivity atomic; a Mods-page entry with its items; the default pad chord (question 2). | 0.5 | The tracker item merged, 3A (3D for the Mods page) |
| **6. Proton and the Deck** (D3D11) | The old 6.x (on the Deck, not the Linux/Proton host) plus: the overlay after `dump_frame`, D3D11 fullscreen live, `XInputGetStateEx` guide on Proton (Steam Input off for the title), a Deck grip bound in Steam Input to F10 opening the menu. | 1 | 3A-5B |
| **9. Controls** | Folded into 3D's Controls page. Only the real-pad capture checks on both hosts stay as 9.x. | 0.5 | 6 |
| **7, 8, 10** | Unchanged. | | |

**Gates per phase.** 3A, 3B, 3C and 3D each change the runtime, the
renderer or input, so each merge gets its own gates under CLAUDE.md:

- the Mac build, ctests and Metal goldens;
- `blinx2 bench golden` on D3D11 under Proton on the Deck;
- a Deck smoke run of the installed build;
- the review.

Each of those phases' estimates includes about 0.25 day for this. Phase 6
then holds only the feature checks on D3D11 and the Deck that need the
whole set.

**Parallel work, ordered merges.** 3A, 3B and 3C can be developed at the
same time in separate toolkit worktrees, but they touch shared files:
`enhance.c` (key reads and log lines), `recomp_env.h` (rows), `mod.h`
(the v2 fields), `fb_present_sdl.c` (3B's layers and 3C's filter and
fullscreen), `nv2a_pb_d3d11.c` (3B's draw and 3C's fullscreen) and the
`fbm_present` signature (3B's layers, 3C's filter). The merge order is
fixed:

1. **3A first.** It owns the `mod.h` v2 block. It appends the
   `action_*` and `toast` fields and reserves `menu_add` and `on_enable`
   as later fields.
2. **3B rebases on 3A.** It owns the `fbm_present` signature change.
3. **3C rebases on 3B.** Its presenter edits land in the new signature.
4. **3D last.**

`recomp_env.h` rows and `enhance.c` log lines are append-only, so those
conflicts are textual. Total for 3A to 6 with the per-phase gates is about 11
agent-days, and 11.5 with the phase 9 checks.

### R6. Follow-ups outside this change

| ID | Title | Estimate | Depends on |
|---|---|---|---|
| F-1 | Toolkit: live `textures.pack` path swap at the flip | 0.5 | 3D |
| F-2 | Toolkit: overlay on the CPU GDI window (Windows CPU backend) | 0.5 | 3B |
| F-3 | SDL3 port of `host_extra` (rename table) | 0.25 | The tracker item, 3A |
| F-4 | b3, ssx3, jsrf, spartan, kuf: check the default action chords in play and add `[input.actions]` and `[menu]` to their `config.default.toml` | 0.5 | 5A |
| F-5 | Hor+: `display.aspect` live with an `NV2A_OPT_ASPECT` flush, or recorded as S per game | 0.5 | `enhancements-hor-plus`, 3C |
| F-6 | Shipped Steam Input layout for the Deck (grips to F10 and F6), if the user wants one | 0.5 | 6 |
| F-7 | `recomp_env` `LIVE` flag for trace channels that can toggle at run time, shown on the Debug page | 0.5 | 3D |
| F-8 | Revive `spike/input-selection` on top of the filter (pad remaps before actions) | later | 3A |
| F-9 | D3D11: present the overlay without a guest flip (walker present-only path after 100 ms) | 0.5 | 3B |
| F-10 | D3D11: `RECOMP_WINDOW_SHOT` (back buffer after the overlay draw), for the Debug page and README shots | 0.5 | 3B |

## Risks / Trade-offs

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

## Still open (2026-10-21, for the user)

1. **SDL3 first, or SDL2 now?** The tracker item has not landed.
   - **Standing default:** the user's order of 2026-10-11 (TASKS, round
     order) is "SDL3 before enhance-menu phase 3". 3A to 3D
     would then wait for the tracker item and use the SDL3 names from the start.
   - **Alternative:** start 3A on SDL2 now. The cost is F-3 (about 0.25
     day, a rename table for the extra buttons). There is also a likely
     rebase of the SDL backend and `fb_present_sdl.c` edits against the
     SDL3 migration, perhaps 0.5 day across 3A to 3C. The order of
     2026-10-11 would need a decision to override it.
2. **Default pad chords.** `back+start` is a poor default: pressing START
   first pauses BLiNX 2 (R3 rule 3). Candidates for BLiNX 2:
   - `back+lthumb@400`, since lthumb has no use and BACK acts only in
     menus;
   - `lthumb+rthumb@400`, although rthumb drives the camera;
   - no pad default (F-keys plus user bindings and paddles).

   Only one action can take `back+lthumb`. Which should get it,
   `menu.open` (proposed) or `camera.free.toggle`? Should the other get
   no pad default? Should `overlay.stats` default to F12 or stay
   unbound?
3. **Pause while open.** Keep D7 (the guest runs and sees a neutral pad),
   or let a title pause through `enhance_menu_on_open`? Pausing BLiNX 2
   would need its own pause press.
4. **D3D11 fullscreen live** (3C). Is it in scope now, or is
   `present.fullscreen` "applies at restart" on D3D11 while SDL and
   Metal get it live? The latter goes in TASKS under the backends-agree
   rule.
5. **Deck layout.** Document Steam Input grip bindings only (proposed),
   or also ship a Steam Input layout (F-6)?
