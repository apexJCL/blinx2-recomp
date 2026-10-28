## Context

- **The spike.** `spike.md` in this change lists every 16:9 mod and patch found for the four games, their other releases and their sibling games. It compares the emulators' widescreen hacks and patch formats, checks RenderWare, and sorts the patterns into layer and mod.
- **What exists in the toolkit** (`posix-host/portability` 3b489642):
  - `src/enhance/mod.h`, API v1: `mem`, the `cfg_*` getters, `log`, `on_frame`, `input_state`, `input_capture`, `batch_filter`;
  - Hor+ (`nv2a_host_pad`, `nv2a_aspect_scan`, `nv2a_aspect_place`);
  - `display.movie`;
  - The tracker item's `nv2a_rt_tex_reads`.
- **Specified, not built:**
  - native-widescreen: D4 probe, D5 present stretch, D6 frame-copy provenance, D7 tiled backdrops, D8 `[aspect.*]` overrides;
  - free-camera spike §6.4: `poke_at`, `on_vblank`/`on_flip`, `rt_dims` plus the projection hook, `--hook-functions`, the Lua assessment, dynamic plugins.
- **Hand-written mod-class code today:** BLiNX 2's Hor+ cull and sea-fan wrappers in `cat/src/recomp_manual.c` (`sub_0003B180`, `sub_00215A40`), and `fx.glow` (`sub_0005B7D0`).

The aim is one layer that every widescreen fix in the wild maps onto. The game-specific part is then data (a VA, a signature, a probe, a poke row, an override row) or a small C mod.

## Goals / Non-Goals

**Goals:**
- Name the layer's services and their contracts: aspect, state, poke, VA hooks, placement, render-target facts.
- Say how a mod declares what it needs, and how it is enabled.
- Fix the bar, backdrop and full-screen class of bugs (and its kind) in the layer, not per game.
- Keep goldens and every 4:3 run byte-for-byte stock.

**Non-Goals:**
- A Family B renderer (anamorphic output with a 2D squeeze in the vertex stage) for Hor+. Hor+ already gives the same HUD pixels with CENTRE. A squeeze is considered only for native mode, in D6.
- Moving the HUD to the edges. H6 stands. A game mod may offer it later as its own option.
- Dynamic plugins, and any scripting engine in this change (D10).
- Fixing frustum pop-in generically. The cull test's shape is the game's own (D7).
- Porting the Xbox `.JMP` patches for JSRF or BLiNX 1. They are anamorphic squeezes that our Hor+ already beats (spike, section 1.4).

## Decisions

### D1. Two owners: the layer serves, the mod supplies data

The spike's table (section 6) is the rule:
- **Layer:**
  - the aspect value;
  - the placement rules and the overrides;
  - the present;
  - render-target sizes;
  - the poke, hook and probe mechanisms;
  - the stock D3DX signatures.
- **Mod:**
  - which VA to hook;
  - which address holds the game's flag or state;
  - which batch the rules miss;
  - the cull's arithmetic.

A mod never sets the aspect, never resizes a target, and never presents. It reads `aspect()` and asks for placements.

*Alternative considered:* a per-game Family B mod in the PS2 style, which pokes each element's width and position. Rejected. Those pokes exist on PS2 only because the emulator could not classify GPU batches. Here they would duplicate `nv2a_aspect_place`, and under Hor+ they are either redundant or clipped (spike, section 7, step 4).

### D2. `aspect()`

```c
struct xbox_mod_aspect {
    uint32_t mode;          /* XBOX_MOD_ASPECT_STOCK, _HORPLUS, _NATIVE */
    uint32_t num, den;      /* the display ratio: 4:3 at stock */
    uint32_t wide_now;      /* native: the 'wide' probe reads wide; Hor+: 1; stock: 0 */
};
void     (*aspect)(struct xbox_mod_aspect *out);       /* any thread */
uint32_t (*pad)(uint32_t w, uint32_t h);               /* nv2a_host_pad; 0 at stock */
```

- It is read-only, and the values are fixed for the run (the aspect does not change in-flight today). `wide_now` is the last flip's sample.
- `pad` is in guest pixels, so a mod that moves a guest coordinate (BLiNX 2's sea fan) needs no host scale.
- Under native, `pad` returns 0: targets are stock-sized (native-widescreen D2).

### D3. VA hooks: generated slots, mod callbacks

- **Mechanism (free-camera D7).** `game.toml` gains:

  ```toml
  [mods]
  hook_functions = ["0x0003B180", "0x00215A40", "sig:d3dx_perspective_fov_lh"]
  ```

  - `xbr analyze` resolves each `sig:` entry against the XBE, from the toolkit's stock signature table or from a `[mods.signatures]` row. It fails on any count other than exactly one match in the expected section. The result goes to `config/hook_functions.json`, next to the seeds, with the VA and the signature name.
  - `analyze` also fails when a listed VA has a hand-written override in `recomp_manual.c` (the manual-function list the CLI already reads). One function has one owner.
  - `xbr recomp` wraps each listed `sub_X` with a dispatch:
    - `recomp_hook_pre[idx]`, then the body (or a skip), then `recomp_hook_post[idx]`;
    - one predictable branch when nothing is attached.
  - With an empty list, the generated code is byte-identical to a build without `[mods]` (tasks 5.3).
  - This replaces hand-written `sub_X` wrappers for mod use. `recomp_manual.c` keeps the wrappers that fix the game itself.
- **API.**

  ```c
  struct xbox_mod_call {
      uint32_t esp;          /* the guest esp at entry: [esp] is the return address */
      uint32_t ecx, edx;     /* entry values: thiscall and fastcall arguments */
      uint32_t eax, edx_ret; /* post: the return value (edx_ret for 64-bit returns) */
      float    st0;          /* post: a float return; may be changed */
      int      st0_valid;    /* post: the function returns on the x87 stack */
      int      skip;         /* pre: replace the body */
  };
  typedef void (*xbox_mod_hook_fn)(struct xbox_mod_call *c, void *user);
  #define XBOX_MOD_HOOK_MAY_SKIP 1u
  int (*hook)(uint32_t va, xbox_mod_hook_fn pre, xbox_mod_hook_fn post,
              uint32_t flags, void *user);
  #define XBOX_MOD_ARG32(api, c, n) XBOX_MOD_MEM32(api, (c)->esp + 4 + 4 * (n))
  #define XBOX_MOD_ARGF(api, c, n)  XBOX_MOD_MEMF(api, (c)->esp + 4 + 4 * (n))
  ```

  - `hook` is init-only. It fails, with a log line and returning 0, when the VA has no generated slot.
  - Callbacks run on the guest thread that called the function, inside the call. They must not block.
  - Several mods may hook one VA. The pre callbacks run in table order, and the posts run in reverse order.
  - Post callbacks see the same entry `esp`, so `XBOX_MOD_ARG32` reads the same arguments as in pre.
  - **Skip.** Only a hook registered with `XBOX_MOD_HOOK_MAY_SKIP` may set `skip`. At most one such hook per VA is accepted; a second is refused at init. A skip from a hook without the flag is ignored and logged once.
    - On a skip, the slot does what the body's `ret` would: it pops the return address and the callee-cleaned argument bytes. Their count, `ret_pop`, is recorded per VA by `analyze` from the function's `ret imm16` (the 0x14 of `ret 0x14`), and is 0 for cdecl.
    - The callback sets `eax` (and `edx_ret`), or `st0` with `st0_valid` for a float return, which the slot pushes on the x87 stack. `analyze` records whether the function returns on the x87 stack (its `ret` paths leave st0 loaded), and `st0_valid` is preset from that.
    - The post callbacks still run after a skip.
- **Stock projection signatures.**
  - The XDK's D3DX `D3DXMatrixPerspectiveFovLH`/`RH` are library code linked into every title that uses D3DX: SSX 3 USA `sub_00249633` (`ret 0x14`, `fsincos`) is the one sample so far.
  - The toolkit ships their byte signatures, with wildcards for relocations. The identity across XDK versions is a check that can fail (tasks 5.5): if BLiNX 2's or another title's D3DX differs, the table gains one row per XDK version, or the mod names the VA.
  - A mod hooks the projection by name, with no game address. BLiNX 2 builds its projection in game code (`sub_0029EEF2`), and JSRF links no D3DX section. For them the mod names the VA.
- **Why not the free-camera spike's `poke_at(hook, ...)` alone:** pokes reach data, but the projection's aspect argument lives on the stack for one call (SSX3-recomp scales `[esp+12]`), and the JSRF `.JMP` patch changes an immediate in a fastcall view builder. Only a call hook reaches them.
- **RenderWare.** Burnout 3 links RenderWare 3.6. `RwCameraSetViewWindow` is a candidate stock signature for RW titles, like D3DX for D3DX titles. It is not located yet, and nothing needs it under Hor+ (spike, section 4, tasks 7.4).

### D4. `poke()`

```c
#define XBOX_MOD_POKE_HOLD   1u   /* re-assert at each flip */
#define XBOX_MOD_POKE_EXPECT 2u   /* write only while the address holds 'expect' */
int (*poke)(uint32_t va, const void *bytes, const void *expect, uint32_t len, uint32_t flags);
```

- **Data only.** The generated code is static C, so a byte poked into `.text` changes nothing. `poke` refuses any address inside an executable section. A PS2-style code cave, or an `.JMP` immediate patch, becomes a VA hook (D3).
- **Pinned XBE.** Pokes are valid only for the pinned XBE:
  - the layer checks the loaded XBE against `game.toml` `[xbe] sha256`, and then against `[xbe.sections]` (the `xbr fingerprint` hashes). A header-only change is still known, the same as for builds;
  - the build passes those hashes to the runtime;
  - when the section holding a poke's address differs, the layer disables every mod that declared `XBOX_MOD_NEED_POKE`, with one log line.
  - This plays the role of WFP's CRC-checked runtime, the `.JMP` CRC32, and every emulator's executable-hash key (spike, section 3).
- **No runtime `find()`.** Signatures are resolved once, by `analyze`, against the pinned XBE (D3), as Dolphin's F6 codes and `.JMP` search records resolve theirs once. A poke row that needs a signature names a `sig:` entry, and `analyze` writes its VA beside the hook list.
- **Expected value.** With `XBOX_MOD_POKE_EXPECT`, the layer writes the bytes only while the address holds `expect` (the game's original) or already holds the poked bytes. Otherwise it skips that write and logs once. This is Flycast's `origValues` guard. It keeps a held poke from overwriting the address after the game reuses it for something else.
- **HOLD.** HOLD covers WFP's reset wrappers, where the game rewrites its HUD values on each menu change. At each flip the layer compares the `len` bytes with the poked bytes and, if they differ (and the expected-value guard passes), writes them again. The cost is one compare of `len` bytes per held poke per flip.
- **The free-camera spike's E7 poke file** becomes a built-in mod, `pokes`, reading `[mods.pokes] entries = [{va, bytes, expect, hold}]`. The data then lives in TOML and needs no C.

### D5. Placement: overrides, callback, rules

The order, first answer wins:
1. **`[aspect.program]` and `[aspect.texture]` overrides** (specified in native-widescreen D8, moved here):
   - rows in the game's shipped `config.default.toml`, read only when the aspect is wide;
   - each row names a class: `stretch`, `centre`, `picture` or `rt`;
   - an override is the maintainer's last word, so it wins over the rules. A generic fix makes the override row unnecessary, and the row is then removed.
2. **Mod `place` callbacks**, in table order:

   ```c
   enum { XBOX_MOD_PLACE_NONE = 0, XBOX_MOD_PLACE_STRETCH, XBOX_MOD_PLACE_CENTRE,
          XBOX_MOD_PLACE_PICTURE, XBOX_MOD_PLACE_RT };
   typedef int (*xbox_mod_place_fn)(const struct nv2a_batch_info *b,
                                    float lo_x, float hi_x, float lo_y, float hi_y, void *user);
   int (*place)(xbox_mod_place_fn fn, void *user);    /* init only */
   ```

   - A callback runs on the render thread only for a batch that the scan already called 2D.
   - It reads game state through probes (D8), never by polling memory per batch.
3. **The generic rules in `nv2a_aspect_place`**, extended:
   - **Row cover.** A set of quads that tile one row band without gaps (two or more quads sharing y extents, with one texture and one program) is full width when their cover sums to the guest width. This is native-widescreen D7(a)'s cover-sum for tiled backdrops, applied to bars drawn as several pieces. It never judges a whole batch by its bounding box: that would undo Hor+ H4, where full width is judged per triangle because BLiNX 2 draws four corner triangles in one batch, and their union spans the width.
   - **Band.** A full-width 2D batch is a letterbox band, and is stretched over any texture or over an unpadded flat render target (the `flat_rt` case), when both hold:
     - its height is at most a quarter of the target;
     - it lies wholly within the top or the bottom quarter.
     A bar's texture is flat or a vertical gradient, so stretching it does not distort. A titled banner with text baked into a full-width texture is the risk. It is caught by the BLiNX 2 Hor+ scenario runs (tasks 2.4), and an override row turns the rule off for it.
   - **Screen layer.** If the trace shows the bars at a fractional w with every vertex sharing it, the layer test (`nv2a_aspect_layer_w`) gains a second form: every vertex of a quad batch at one w, and the batch drawn with depth test off. This form is used only to decide full width and band. It never makes a batch 2D for any other placement: lens-flare and particle sprites are also drawn without depth (SSX 3), and must keep their 3D placement.
   - Only the rule that the trace shows to be needed is built (tasks 2.2). The others stay in this design as the ready answers.
   - **Built: the band piece.** The trace (tasks 2.1) answered the question.
     - b3's crash cam draws each of these from the HUD program `1B73FAD1`, as quads at one fractional w (24.37) with the depth test off:
       - its two bars;
       - their thin edge lines, each as two half-width quads drawn as separate batches;
       - the list backing, over a 32x32 texture, with its raised right end at y 349.
     - The rule built is the screen-layer form joined to a band test (`nv2a_aspect_band`):
       - the batch is a quad at one positive w (`nv2a_aspect_screen_quad`), drawn with depth off;
       - it samples no guest picture and no unpadded target;
       - it keeps within the frame's width and height, and reaches its left or right edge;
       - it lies wholly in the top or bottom **third**;
       - that third holds a **bar**: a full-width screen quad stretched on the same target in this flip or the last (`nv2a_aspect_bar_mark`, `nv2a_aspect_bars`).
       Such a piece is stretched.
     - Why it differs from the D5 sketches:
       - **Third, not quarter:** the raised end starts at y 349, above the bottom quarter.
       - **Bar required (review of 7db09a69):** without it the rule also took Burnout 3's front-end menu frame (header strips and bottom rule at one w, without depth, touching an edge), which then broke away into the pads. The crash-cam bars already pass the screen-quad rule; the menu has no such bar. Without a stamp the interpreter is not run for band candidates, so normal frames pay nothing.
       - **Edge, not cover sum:** the line halves are separate batches, so their cover cannot be summed when the first one draws. A stretch is one affine map about the centre, so every piece that reaches an edge stays joined to its neighbours.
     - What keeps its place:
       - text and icons inside the band, which reach neither edge, or sample a guest picture wider than a quarter of the frame (`nv2a_aspect_picture`);
       - the front-end menu frame, which has no bar;
       - a mid-screen flare;
       - BLiNX 2's corner triangles, a batch that spans both thirds.
     - **Not built:** the row cover, and the band over a guest picture or a flat target. No trace has needed them yet.

### D6. Native mode and the 2D squeeze (deferred)

- If native-widescreen task 1.3 shows that b3 or SSX 3 does not squeeze its own HUD in native mode, the HUD comes out 4/3 too wide after the present stretch.
- The answer would be a layer placement `SQUEEZE`, used only under native while the probe reads wide:
  - 2D that is not full width is narrowed by `(4/3) / ratio` about the centre;
  - full-width 2D is kept, which is SSX3-recomp's rule and the PS2 codes' -107.5 / 853.33.
- This is specified here and built only on that evidence. Today the PS2 build needs it (Aero_ squeezes the HUD), and the Xbox build is unknown.

### D7. Render-target facts and culls stay game code

- `rt_dims(offset, &w, &h, &pad)` reports a guest surface's stock size and its Hor+ pad. A mod that computes a screen-space value (a cull, a sea fan, a lens-flare test position) can then scale it.
- The cull's arithmetic is the game's:
  - BLiNX 2 scales the cull aspect by (4/3)/A for the main view only (aspect argument about -0.75);
  - the sea fan scales vertex x by A/(4/3).
- These become the `blinx2-wide-cull` mod on two VA hooks. It is the API's proof, and it removes two hand-written wrappers from `recomp_manual.c`.
- The GTA PC fixes do the same in their game: they hook the FOV call and the frustum calculation, not the engine (spike, section 4).

### D8. State probes

```c
int (*state_probe)(const char *name, uint32_t va, uint32_t mask, uint32_t value);
int (*state_probe_fn)(const char *name, int (*fn)(const struct xbox_mod_api *, void *), void *user);
int (*state)(const char *name);       /* the last flip's value; -1 when unknown */
```

- The layer samples every probe at each flip, which the toolkit owns in every title (free-camera §6.4 `on_flip`). It does not depend on `xbox_mod_frame`, which only cat calls: b3 and SSX 3 have no frame glue, and native-widescreen D4 samples per flip.
- Held pokes are re-asserted at the same point, after the probes.
- The render thread reads the last sample.
- `wide` is native-widescreen D4's probe. `enhance_native_register()` registers it.
- `in_game` is a convention for the SSX3-recomp kind of test (the app-state vtable). A projection hook uses it to keep menus 4:3.
- Under Hor+, the layer pillarboxes nothing. A mod that wants menus at 4:3 under Hor+ is outside H6 and needs its own proposal.
- **Open: an automatic `wide` probe.** Dolphin detects anamorphic output by comparing the projection's aspect with the viewport's, counted per flush (spike, section 3). On NV2A this would mean reading the projection out of vertex-program constants, which have no fixed slot. A registered probe stays the primary path. The heuristic is worth a look only if a game with a native mode has no probe.

### D9. Declaration and enabling

```c
struct xbox_mod {
    const char *name;
    int (*init)(const struct xbox_mod_api *api);
    void (*shutdown)(void);
    /* v2: zero-initialised in v1 tables */
    uint32_t needs;       /* XBOX_MOD_NEED_ASPECT | _STATE | _POKE | _HOOK | _PLACE */
    const char *follows;  /* NULL, or a config key that enables it */
};
```

- **One gate for every mod.** The layer calls a mod's `init` only when one of these holds:
  - `[mods.<name>] enabled = true`, which defaults to false;
  - its `follows` key holds a value different from that key's default. For example `blinx2-wide-cull` follows `display.aspect` (default `4:3`), and the free camera follows `camera.free` (default `off`).
  - The free camera's own early return when `camera.free=off` (`src/free_camera.c`) then never runs, and can stay as a guard.
- **No `api_min`.** Mods are linked statically into the title they were written for, so a version refusal could never fire. It is added with dynamic plugins, if they come.
- **Refusal.** The layer leaves out a mod with one line, `[MOD name] needs hook: not available`, when a need is missing: no slot for its VA, a poke on a mismatched XBE, or the layer built without the backend.
- **The `mods=` token** lists the mods whose `init` ran and returned success (D12).
- **Exclusive choices.** A mod offering several aspects or variants (the pnach 16:9 and 21:9 pairs, RPCS3's `Group`) exposes one `cfg_choice` key, not separate switches.
- **The CLI's view.** `game.toml` `[mods] hook_functions` and `[mods.signatures]` are what the CLI sees. The wizard and README options for a mod come from its `[mods.<name>]` keys in `config.default.toml`, like any other key.

### D10. Static C now; input to the Lua assessment

- **Now:** C mods in the game repo (`src/mods/*.c`) in the title's table. This keeps the user's 2026-10-04 decision.
- **The Lua assessment** (free-camera spike §6.4 step 6) is the user's decision to make, once three real mods exist: `blinx2-wide-cull`, `pokes`, and the free camera. This change only gives it input:
  - the data-level work at frame rate: poke tables, probes, override rows, `on_frame` logic such as toggles or a debug overlay's state. None of these is on a hot path;
  - the hot paths: hook callbacks run per guest call (the BLiNX 2 cull runs hundreds of times per frame), and `place` runs per batch on the render thread.
  - The survey found no emulator that scripts its widescreen fixes: they are typed data (Flycast, Xenia, RPCS3, pnach, `.JMP`) or native code (Dolphin, WFP).

### D11. Relation to the display keys and to native-widescreen

| Item | Owner after this change |
|---|---|
| `display.aspect` (Hor+) | unchanged; it feeds `aspect()` and the `follows` gate |
| `display.widescreen = native` | unchanged (native-widescreen D1 to D5); its probe becomes `state_probe("wide", ...)` |
| `[aspect.program]` and `[aspect.texture]` | moved here from native-widescreen (its D8, tasks section 8 and the "Hor+ placement overrides" requirement); the first stage of D5 |
| native-widescreen D6 (frame copies are render targets) | unchanged and generic; the tracker item's likely home |
| native-widescreen D7 (tiled backdrops) | its cover-sum is reused by D5's row cover |
| `display.movie` | unchanged |

### D12. Stock and goldens

- With every mod disabled:
  - `aspect()` reports stock;
  - no poke is written;
  - hook slots take the empty branch;
  - no `place` callback runs;
  - the rules in D5 run only when the aspect is wide, which is never at stock.
- The `[ENHANCE]` line gains `mods=none` or `mods=a,b`, the mods that passed the gate (D9). At stock it is `mods=none`, including in cat, where the free camera's gate fails while `camera.free` is off.
- Order of landing: the toolkit emits the token first. Then the CLI's `golden.py` adds `("mods", ..., "none")` to `ENHANCE_STOCK`, and `manifest.TOOLKIT_ENHANCE_KEYS` gains the same key (the CLI's `tests/test_manifest.py` checks the two agree). A golden run with a mod enabled then fails the stock check.
- The generated hook slots exist in every build that lists `hook_functions`. A stock golden of that build proves the empty branch changes nothing.

## Risks / Trade-offs

- **The band rule can stretch a titled full-width banner.** Mitigations: an override row, and BLiNX 2's Hor+ scenario runs in tasks.
- **The screen-layer test can catch sprites.** Mitigation: it only feeds the full-width and band decisions (D5), with a flare-sprite negative case in the ctest.
- **Hook slots change generated code.** The CLI's gen key includes `hook_functions`, so changing the list regenerates. Stock goldens gate it (D12), and an empty list is byte-identical.
- **Signatures can match twice, or differ by XDK version.** `analyze` fails on any count other than exactly one match in the expected section, and tasks 5.5 checks each stock signature against every title that links it.
- **API v2 is a struct growth.** `size` already guards it. Only fields are appended.
- **Moving the cull wrappers into a mod loses `[HORCULL]` at 4:3.** A mod that follows `display.aspect` never runs at 4:3, so the cull's aspect logging there is gone. Tasks 6.3 keeps that logging in the game or accepts the loss explicitly.

## Migration Plan

Land in this order, which the tasks follow:
1. the trace and the one rule it needs;
2. the overrides;
3. API v2 with the gate, probes and pokes;
4. hook slots in the CLI, with the D3DX signature check;
5. `blinx2-wide-cull` replacing its two hand-written wrappers.

Each step merges on its own, after a review, with stock goldens unchanged.

## Open Questions

1. The cause ((a) to (d) in the spike, section 7). It picks the D5 rule.
2. Whether b3 and SSX 3 squeeze their HUD in native mode (native-widescreen 1.3). It decides D6.
3. Whether JSRF's projection is worth pinning. No mod or bug needs it today; the `.JMP` patch points at `sub_001BAF70`.
4. Whether an automatic `wide` probe (D8) is ever needed.
5. Where `RwCameraSetViewWindow` is in b3, if an RW-generic hook is ever wanted (D3).
