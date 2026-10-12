# Assessment: the HUD / assets / font enhancement layer (2026-10-11)

Read on cat `main` cbde3e8, toolkit `posix-host/portability` f8696da and
the CLI `main` e2ab3a0 (v0.3.0), with read-only commands. This is the
"step 1" the user asked for before the menu and preview-tool specs; the
proposal summarises it, this file keeps the evidence.

## How the layer works today

**Three pieces, three repositories.**

1. *Toolkit, `src/enhance/`* (opt-in, `XBOXRECOMP_ENHANCE=ON`; cat builds it
   ON by default with every key at stock). `recomp_cfg.c` is a TOML-subset
   reader (read-only, ~900 lines); `enhance_cfg.c` layers env > title file
   > root file > default and records which keys were read;
   `xbox_enhance_init()` (`enhance.c`, 98 lines) reads `render.scale`,
   `present.filter`, `present.fullscreen`, `present.pacing`,
   `display.aspect` and `textures.pack` **once at startup**, stores the
   first three in `nv2a_host_opts` (a plain static struct in the kernel
   library, `nv2a_backend_common.c:583`), hands pacing to
   `xbox_PacingSetMode()` and loads the texture pack index
   (`nv2a_tex_pack_load`). It logs the `[ENHANCE] ...` lines the golden
   harness reads.
2. *Toolkit backends.* Metal (`src/d3d/nv2a_pb_metal.m`) and D3D11
   (`src/d3d/nv2a_pb_d3d11.c`) read `nv2a_host_render_scale()` when they
   create a render target (`nv2a_host_size`, three call sites each) and
   `nv2a_host_opts()->present_filter/fullscreen` at every present. The
   texture-pack hook is the same four lines in both `tex_upload`s
   (`nv2a_tex_pack_count()`, `nv2a_tex_pack_find(hash, w, h)`,
   `nv2a_tex_pack_texels`, create at the entry's size). The CPU rasteriser
   logs "ignored" once for scale and pack. The three presenters (SDL
   renderer for CPU and Metal-readback, `fb_present_metal.m` for the
   CAMetalLayer window, `present_blit`/`CopyResource` in the D3D11 flip)
   each place the frame with `nv2a_present_rect` and draw it with one
   textured triangle or `SDL_RenderCopy`.
3. *CLI, `src/xboxrecomp_cli/enhance/`* (1,872 lines, stdlib only):
   `ipk.py` (IPK1 + LZSS), `dds.py` (DXT1/3/5), `texhash.py` (the runtime's
   FNV), `scaler.py` (integer xBR lv2, 2x and 4x), `font.py` (TrueType
   reader + scanline rasteriser + host font lookup by full name),
   `atlas.py` (measure the stock atlas's ink bands, runs, glyph boxes;
   fit each glyph into its stock ink box), `pack.py` (XRTP writer +
   `hud-pack.toml`), `hud.py` (`xbr enhance hud`). `package --hud-pack`
   stages the pack and enables the key in `enhance.toml.default`. 19 tests
   in `tests/test_enhance.py` with synthetic fixtures.
4. *Game, cat.* `game.toml [enhance.hud]` holds the facts (archives,
   patterns, `scale`, `max_texels`, `font_atlas`, the ten `font_rows`, the
   face name). `src/main.c host_enhance_init` reads the game keys
   `fps.mode`, `fx.glow`, `fx.glow_intensity` after `xbox_enhance_init`;
   `fx.glow` acts through a wrapper around `sub_0005B7D0` that scales the
   guest glow weight for the call (`src/glow.c`, two statics set once by
   `glow_configure`). `docs/env.md` has one row per variable;
   `packaging/enhance.toml.default` ships every key at stock with the
   `[textures]` table commented out; `analysis/golden/golden.json` pins
   `RECOMP_ENHANCE_CONFIG=none`, scale 1, pacing spin, glow on / 1.

**What works, verified:** Metal and D3D11 goldens unchanged with the layer
on and no key set (both hosts, 2026-10-10); `@stage1` with the PT Sans pack
at 2x on both backends, every fitted glyph in place, 0 present mismatches
(`runs/hudpack/`); the pack is byte-reproducible across job counts and
hosts (sha 54fb5c0f); a bundle with `--hud-pack` runs under Proton with the
pack line in its log; the Deck build 20261011.0607 carries the pack.

## Gaps

- **Everything is startup-only.** Every key is read once in
  `xbox_enhance_init` and `host_enhance_init`; `nv2a_host_opts` is written
  once; `glow_configure` is "set once before any guest thread runs";
  `nv2a_tex_pack.h` says "not thread-safe: load at startup, use from the
  thread that uploads textures". Changing anything means editing a TOML
  file and restarting. There is no hotkey of any kind (`enhance-config.md`
  on fullscreen: "There is no hotkey yet"); the three window procedures
  only forward keys to the pad stand-in (`xbox_InputKeySet`,
  `xbox_InputSdlEvent`).
- **No overlay or text drawing exists** in the runtime. The only atlas in
  the toolkit is upstream's empty `font_atlas_data.h` placeholder for its
  Burnout 3 menu pushbuffer replay, which draws through the guest's
  pushbuffer, not on the host present path.
- **One pack, one kind.** The pack is one file with one entry per hash;
  the font atlas is just another entry, and so are the baked text images.
  Entry `flags` exist (u32, must be 0, "a v1 reader refuses any other
  value"), so the runtime cannot tell font, text and art apart without a
  format change or several packs.
- **No visibility of what did not match.** The runtime logs the entry
  count and a hit count every 600 flips; nothing lists the uploads that a
  loaded pack *missed*, nor their hashes and sizes. The CLI's `--list`
  prints the pack side (hashes of the selected archive entries) but
  nothing joins the two. **BLX-71** showed the cost: the Mission
  Objectives title, its lines and the "OR" are not font-atlas glyphs at
  all but pre-rendered DXT3 images (512x32, 512x64) inside `lng_us`
  `MIXF` (`.mix`) containers that each hold an `XPR0` resource; the pack
  builder read only `archives = ["media"]` and only `.dds` entries, so
  they never got entries, and the runtime was fine. Finding that took an
  agent a diagnosis; a "pack misses" trace (hash, size, format, count)
  plus a menu page showing hits and the first missed candidates would
  have pointed at a 512x32 DXT3 the pack did not hold in one run. The
  fix is prototyped on `fix/hud-pack-text` (CLI 4ef7cd4: `enhance/xpr.py`,
  a MIX reader; cat 1e5128f: `lng_us` patterns): 427 entries, 372 MB at
  4x. Not duplicated here; this change references it (D2b).
- **Baked text is a third kind, and it is big.** Beyond those screens
  about 2,000 more pre-rendered text images exist (`sm_*` captions,
  `mgtu` tutorials, ...), several GB of raw texels at 4x. The pack stores
  one uncompressed A8R8G8B8 texel per pixel on disk and in VRAM, has one
  informational `scale` for the whole file, and knows one kind of entry:
  "font swap off, art on" is not expressible, and neither is "text at 2x,
  HUD at 4x" as a policy (though each entry already carries its own
  size). Per-language assets (`lng_us`, ...) are a selection the builder
  does not have yet.
- **The CLI knows one scaler and one fit.** `scaler.scale` accepts only
  2 and 4 (the runtime's `render.scale` goes to 3), one kernel
  (`xbr-lv2-int`) with constants (`EQ = 300_000`, the Y/U/V/A weights)
  that are not parameters; the font fit has no user knobs (size, weight,
  offsets, outline, shadow are all fixed by "ink box = stock box x
  scale"). There is no way to try a choice without building a whole pack
  (4-8 s) and launching the game.
- **Font choice is one name in `game.toml`.** `font = "PT Sans Narrow
  Bold"` is both a game fact and a user preference. A user who prefers
  another face edits a tracked file. The CLI never downloads a font and
  the user installs it by hand (fine legally, awkward in practice).
- **`present.fullscreen` and `render.scale` have no live path.** Scale is
  baked into every render target at creation (`nv2a_host_size` at the
  three allocation sites per backend); the targets' host size is in the
  cache entry (`hw`, `hh`). D3D11 eviction loses pixels ("its pixels
  lost"); Metal writes back on eviction (`sync_guest`), and a Metal
  target created from guest bytes is expanded N×, so Metal can rebuild a
  target at a new scale from guest memory and D3D11 cannot.
- **Three windows, three input paths.** SDL main thread (POSIX; keys via
  `xbox_InputSdlEvent`, pads via `SDL_GameControllerUpdate` in the
  presenter's pump), D3D11 `wnd_proc` on the walker thread (Windows,
  `WM_KEYDOWN`, XInput pads polled by `xinput_device.c`), and the CPU
  path's GDI window `fb_wndproc`. The one place every host and backend
  passes through is `xbox_InputGetState()` (`input_core.c:75`), called by
  the guest's pad poll.

## Fragile points

- `nv2a_host_opts` is read on the walker thread (RT allocation, present)
  and would be written by a menu on another thread; today nothing writes
  it after init, so there is no locking. A live setter needs an
  "apply at the next flip" hand-off, not a direct store.
- `glow_active()`/`glow_factor()` are plain statics read on the guest
  thread each call; live changes need them atomic (or a single packed
  word) so the wrapper never sees a torn (active, factor) pair.
- The texture cache keys on `(offset, color, w, h, pitch, palette,
  levels)` and re-uploads only when the *hash* changes. Loading or
  unloading a pack at run time changes nothing for textures already
  resident: their hash is the same, so the swap never happens until the
  game rewrites them. A live pack toggle must invalidate the texture
  cache (a generation counter the `tex_bind` path compares), on both
  backends.
- `nv2a_tex_pack_texels` reads from the file on first use, on the upload
  thread; unloading while an upload is in flight is a use-after-free.
  Unload must also go through the flip boundary.
- `recomp_cfg` is read-only and drops comments; nothing writes TOML. A
  naive "serialise the table" writer would destroy the commented
  `enhance.toml.default` layout users read. Persistence needs a
  line-patching writer that keeps comments.
- The golden harness recognises stock by regexes over the `[ENHANCE]`
  lines (`ENHANCE_STOCK` in the CLI's `golden.py` plus `game.toml
  [golden] enhance_stock`). Any new key that can change frames must get
  a stock value and a pin there, or a scaled run slips through as a
  golden.
- `scaler.py` is pure Python at ~1 s per 256x256 texture at 4x per core.
  A preview that re-renders on every slider move must work on crops
  (64x64) and cache by `(filter, params, texture)`.
- The public toolkit pin in cat's `game.toml` predates the pack loader
  (TASKS follow-up (c)); a public build today has a CLI that writes packs
  the pinned runtime cannot read. Any pack-format change here widens that
  gap until the next push round re-pins.
- The SteamOS installer did not copy `enhance/` (TASKS follow-up (d),
  fixed on main cbde3e8 for the bundle's top level); a menu that saves
  `enhance.toml` must write to the *installed* config path the launcher
  made (`config/enhance.toml`), which is where the layer reads from, and
  never to the bundle's `enhance.toml.default`.

## Known open bug (not duplicated here)

BLX-71 (owned by `hud-pack-text`): root cause above, prototype fix on
`fix/hud-pack-text` (CLI 4ef7cd4, cat 1e5128f). This change builds on it:
a third entry kind (`TEXT`) with its own toggle and default scale, a
BC-compressed payload so 2,000 text images fit, per-language selection,
a pack-miss trace, the menu's Pack page with hits and misses, and the
preview tool's runtime-log import that marks seen-but-unpacked textures,
so the next such gap shows up in one run instead of a diagnosis.
