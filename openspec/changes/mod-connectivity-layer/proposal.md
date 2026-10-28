## Why

The user (2026-10-22): find the 16:9 mods for BLiNX 2, Burnout 3, JSRF and SSX 3, see how they work, and make the approach as game-agnostic as possible. Game-specific code goes through the mod layer. Whatever is game-agnostic is provided by a mod connectivity layer in the toolkit. The trigger is the tracker item: under Hor+, Burnout 3's crash-cam letterbox bars cover only the 4:3 centre. A second pass, the same day, widened the search to every other platform and sibling game.

The spike (`spike.md` in this change) found:
- **On Xbox:**
  - JSRF has two widescreen XBE patches in Jay's `.JMP` format (icup321 for NTSC, Esppiral for PAL). Each changes one immediate in the view builder, which is an anamorphic squeeze.
  - BLiNX 2 has only 720p patches.
  - Burnout 3 and SSX 3 have no XBE patch. koenhendriks' SSX3-recomp (GPL-2.0, Xbox PAL) is a recompilation that wraps D3DX `PerspectiveFovLH` and squeezes 2D in its vertex shader.
- **On Burnout 3:** PS2 pnach codes in every region (Aero_, PeterDelta, Arapapa's ports), and ThirteenAG's PCSX2-Fork plugin (MIT).
- **On SSX 3:**
  - a PS2 pnach by Virjoinga, with triple-screen, 21:9 and 32:9 values and no plain 16:9 entry;
  - the GameCube release's own Anamorphic option.
- **On the sibling games and other releases:**
  - Burnout Revenge and Dominator on PS2 use the same Criterion recipe as Burnout 3: the game's own 16:9 flag, then the HUD width and anchors.
  - SSX On Tour's native mode is the same value as SSX 3's Anamorphic.
  - BLiNX 1 (Xbox), Jet Set Radio (Dreamcast, Flycast's built-in cheats) and JSRF all use an anamorphic projection constant and let the TV stretch the picture.
- **On the emulators' patch systems** (Dolphin, PCSX2, Flycast, Xenia, RPCS3, `.JMP`): every one keys its patches to the exact executable, and keeps them off by default. Flycast re-applies a value only while the game's original is still in place. Dolphin's hack leaves 2D alone by a GPU flag that NV2A lacks.
- **On RenderWare:** only Burnout 3 is RenderWare (3.6). The GTA fixes hook the game's FOV and cull calls, not RenderWare itself.

All of them use one of two families of technique:
- padded Hor+, which is ours;
- anamorphic output with a 2D squeeze, where the full-screen elements are widened back.

Each family breaks down into the same few services:
- the aspect value and the pad;
- a hook on a guest function by address, for the projection and for culls;
- data pokes keyed by address, checked against the pinned XBE, guarded by an expected value, and re-asserted when the game resets them;
- a game-state probe;
- a 2D classification with rules for full-screen elements and letterbox bars;
- overrides where the rules miss;
- render-target widening;
- a present stretch.

The PS2 authors poked each bar and backdrop one by one because they had no GPU-level classifier. We have one (`nv2a_aspect_place`), so most of their per-element work becomes a generic rule.

The toolkit already has the start of this layer: `src/enhance/mod.h`, API v1, with memory, config, log, `on_frame`, input and `batch_filter`. Several pieces are planned but not landed: `poke_at`, the projection hook, `rt_dims`, `--hook-functions`, and the native-widescreen probe and overrides. Each has so far been specified for one feature at a time. This change sets them as one layer that any widescreen fix, and any later mod, builds on.

## What Changes

- **`xbox_mod_api` v2.** Fields are only added; v1 mods keep working.
  - `aspect()` returns:
    - the mode: stock, Hor+ or native;
    - the ratio;
    - the guest-unit pad for a target size, through `nv2a_host_pad`;
    - whether the game draws wide now.
  - `state_probe()` registers a named boolean, read at each flip from guest memory (address, mask, value) or from a callback. native-widescreen's `enhance_native_register()` becomes a thin wrapper over the probe named `wide`.
  - `poke()` writes guest data at an address, once or held (re-asserted at each flip). It takes an optional expected value, and writes only while the address still holds it. A poke is refused when the XBE does not match the `[xbe]` pins (the sha256, or the section hashes that `xbr fingerprint` gives). Signatures are resolved at analyze time, so there is no runtime `find()`.
  - `hook()` attaches pre and post callbacks to a guest function by VA. The callbacks get typed access to the stack arguments, ecx and edx, and the return value. The VA must be one the build generated a hook slot for.
  - `place()` lets a mod classify a batch as stretch, centre, picture, render target or no opinion. It runs after the `[aspect.*]` overrides and before the generic rules.
- **Hook slots from the CLI (free-camera D7, `--hook-functions`).**
  - `game.toml` `[mods] hook_functions` lists VAs, or `sig:` byte signatures that `xbr analyze` resolves to a VA.
  - `xbr recomp` emits a pre and post dispatch for each listed function, so a mod needs no `recomp_manual.c` wrapper.
  - The D3DX `PerspectiveFovLH`/`RH` builders get a stock signature, so a title that links them can hook its projection by name, once the signature is shown to hold across the XDK versions of our titles.
- **Generic placement rules in the layer.** The first user is the tracker item. Which rule fixes it depends on the cause the trace finds:
  - the **band** rule: a full-width 2D batch that is at most a quarter of the target high, in the top or bottom quarter, is a letterbox bar and is stretched even over a guest texture;
  - full width judged over a set of quads that tile one row band (native-widescreen D7(a)'s cover-sum), never over a whole batch, which would undo Hor+ H4;
  - a widened screen-layer test, used only for the full-width and band decisions.
- **The `[aspect.program]` and `[aspect.texture]` overrides move here** from native-widescreen (its tasks section 8 and its "Hor+ placement overrides" requirement), as the first stage of the placement order.
- **One enable gate for every mod.**
  - `struct xbox_mod` gains a `needs` mask (aspect, state, poke, hook, place) and a `follows` key.
  - A mod runs only when `[mods.<name>] enabled = true` (default false), or when its `follows` key differs from that key's default. The free camera declares `follows = "camera.free"`.
  - The layer leaves out a mod whose needs it cannot meet, with one log line.
- **Static C now; input to the Lua assessment.**
  - Mods are C files in the game repo, listed in its table.
  - This change records what the Lua assessment (free-camera spike §6.4 step 6) should weigh: the data-level work at frame rate (pokes, probes, override rows, `on_frame` logic) against the per-batch and per-call callbacks. It does not decide the assessment.
- **Goldens stay stock.**
  - With no mod enabled, every service returns its stock answer: no pokes, pass-through hooks, no placement opinion.
  - The `[ENHANCE]` line gains `mods=<names>|none`, listing the mods that passed the gate.
  - The toolkit emits the token first. Then the CLI's golden check refuses a run that is not `mods=none`, with the `golden.py` `ENHANCE_STOCK` row kept consistent with `manifest.TOOLKIT_ENHANCE_KEYS`.
- **Recommendations recorded:**
  - The tracker item: trace first, fix in the layer (rule, then override), no b3 poke mod. See the spike, section 7.
  - The tracker item belong to the layer's full-width and frame-copy rules. Neither needs a projection mod.
  - No port of the JSRF or BLiNX 1 `.JMP` patches: our Hor+ already covers both games without stretching the 2D.

## Capabilities

### Modified Capabilities

- `enhancements`:
  - the mod API v2 services (aspect, state probe, guarded poke, VA hooks, placement callback);
  - the one enable gate for every mod;
  - the generic band and full-width placement rules;
  - the `[aspect.*]` overrides, moved from native-widescreen;
  - the `mods=` token in the `[ENHANCE]` line.

## Impact

- **Toolkit** (`xboxrecomp`, a branch off `posix-host/portability`):
  - `src/enhance/mod.{h,c}`: API v2, the gate, probes at the flip;
  - `src/kernel/nv2a_backend_common.{h,c}`: the placement rules, the override tables and the `place` callback;
  - `src/recomp/` runtime: the hook dispatch table;
  - `src/enhance/enhance_native.c`: the probe;
  - ctests for each service;
  - `docs/runtime/config.md` ("Mods").
- **CLI** (`xboxrecomp-cli`):
  - the `[mods]` table in `manifest.py`;
  - signature resolution in `analyze`;
  - hook-slot emission in `recomp`;
  - the `golden.py` `mods=none` token, after the toolkit emits it;
  - pytest.
- **Games:**
  - b3: the trace and, if the rules miss, override rows in `config.default.toml`.
  - cat:
    - The `sub_0003B180` cull and `sub_00215A40` sea-fan wrappers become a `blinx2-wide-cull` mod on VA hooks. This is the API's proof. It follows `display.aspect` and never runs at 4:3. Their `[HORCULL]` logging, the `cam_log` row and the `RECOMP_DISPLAY_ASPECT` row in `docs/env.md` move with them.
    - The free camera declares `follows = "camera.free"`. `fx.glow` moves onto the mod table (free-camera §6.4 step 1).
  - ssx3: optional. An SSX 3 Hor+ projection mod is not needed while native Anamorphic exists.
  - native-widescreen: tasks section 8 and its overrides requirement are marked as moved here. Its D8 order is reconciled with D5.
- **No change** to stock behaviour, the stock goldens, or any game at 4:3 without mods.
