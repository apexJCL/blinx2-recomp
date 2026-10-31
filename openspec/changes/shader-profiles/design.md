## Context

Grounded in the toolkit at `posix-host/portability` 878012fc:
- `src/kernel/nv2a_present_chain.{c,h}`: owns the request
  (`nv2a_present_chain_request`), the dlopened librashader, the preset path
  (`preset_path`: a bundled name maps to `shaders/<name>.slangp` beside the
  executable, else a `.slangp` path), the active parameter table (64 rows)
  and the per-preset overrides (256 rows, keyed by the preset's file stem).
- `nv2a_pb_d3d11.c` (`lrs_chain`) and `fb_present_metal.m` (`chain_get`)
  each call `nv2a_present_chain_preset`, `libra_preset_create` on that path,
  publish the table, create their filter chain, and follow the parameter
  generation with `set_param`. A failed build calls
  `nv2a_present_chain_failed(gen)` and presents stock.
- `src/enhance/enhance_menu.c`: `PAGE_SHADERS` has the *Shader* choice item
  (`present.shader`, `k_shader`), `R_PARAM` rows built from the store, and
  `R_PRESET` (*Reset to preset*). Save (`save()`) patches the user config
  with the slots' changes plus the store's dirty overrides. The page is
  hidden where no chain can run (`s_shaders_off`).
- Menu input is a closed event set (`enhance_menu.h`): Up, Down, Left,
  Right, OK (A, Enter, Space), Back (B, Esc, Backspace), Page prev/next
  (LB/RB, Q/E, PgUp/PgDn), Save (Y, F5), Clear (X, Delete). Sub-lists
  exist (the Mods page's `s_mod_sub`), and a confirm (`s_confirm`, the
  Reset row). There is no text entry.
- `recomp_cfg` reads a TOML subset: no arrays of tables, no inline tables;
  dotted tables and arrays of scalars are fine. `recomp_cfg_patch_text`
  edits a text and keeps comments.
- Bundled presets: `crt-lottes` (1 pass, viewport scale, 13 parameters),
  `crt-lottes-fast` (1 pass, viewport, 8), `crt-hyllian` (the one-pass
  fast variant, viewport, 6), `fsr` (2 passes: EASU at viewport, RCAS at
  source scale; 4). Our top-level files are `#reference` wrappers, two of
  them setting calmer curvature. Licences: public domain, MIT, Unlicense
  (`assets/shaders/README.md`). No bundled preset uses `alias` or LUT
  `textures`.

## D1. What a profile is

A profile is:
- a **name** (display text, up to 48 bytes of UTF-8) and a **slug** (its
  file stem, `[a-z0-9_-]`, derived from the name, unique in the folder);
- an ordered list of 1 to 8 **stages**; each stage is a preset reference:
  a bundled name, a `user:<stem>` name, or a `.slangp` path. The existing
  `preset_path` resolves bare and relative names against the executable's
  directory (nv2a_present_chain.c), which is right for `present.shader` but
  not for a player's own presets, so a stage resolves in its own order
  (`shader_profile_stage_path`):
  1. a bundled name (`NV2A_PRESENT_CHAIN_NAMES`) is the bundled preset;
  2. `user:<stem>` is `<root>/shaders/<stem>.slangp`;
  3. an absolute path is used as is;
  4. a relative path is tried against `<root>/shaders/` first, then the
     executable's directory (today's `present.shader` meaning).
  The Add picker writes `user:<stem>` for the files it lists from
  `<root>/shaders/`. A user preset whose stem equals a bundled name is not
  listed and is refused with `[SHADER] <root>/shaders/<stem>.slangp: name
  clashes with the bundled preset`, so `fsr` in a file always means the
  bundled one. The same preset may appear twice;
- **parameter values**: for each stage's preset key (the existing
  `nv2a_present_chain_preset_key`), the values that differ from the
  composed preset's own. Differences only, like the config.

A profile does not carry per-pass scale, filter or wrap settings: each
preset keeps its own (Out of scope; decision 2).

**Built-in profiles.** `crt-lottes`, `crt-lottes-fast`, `crt-hyllian` and
`fsr` are one-stage profiles that exist without a file, one per entry of
`NV2A_PRESENT_CHAIN_NAMES`. Their parameter values live where they live
today, `[present.shader_params.<preset>]` in the user config, so the
The tracker item behaviour, its config and its docs stay true. Their chain cannot be
edited in place: the first Add, Move or Remove on a built-in makes an
unsaved user profile named "<built-in> custom" with the same values and
switches to it (D5).

## D2. File format and location

One file per profile:
`<root>/config/shader-profiles/<slug>.toml`. Per game, since `<root>` is the
game's user data root, and never in the per-title file's folder, so a game
with several titles keeps one set. `enhance_cfg_user_path` cannot name this
folder: it returns the per-title `<root>/<title>/config.toml` when one was
read (enhance_cfg.h), so a new accessor does:
`enhance_cfg_user_dir(char *out, size_t n)` returns `<root>/config`,
whatever file the layers read, and the profiles folder is
`<that>/shader-profiles/`. The `RECOMP_CONFIG` rules stay:
- `RECOMP_CONFIG=<file>`: the accessor returns the directory of that file,
  so the folder is `shader-profiles/` beside it;
- `RECOMP_CONFIG=none`: the accessor fails, and there are no profiles
  (goldens, D9).

```toml
# xboxrecomp shader profile (docs/runtime/config.md, "Shader profiles")
version = 1
name = "Soft CRT"
stages = ["fsr", "crt-lottes"]

[params.fsr]
FSR_SHARPENING = 0.2

[params.crt-lottes]
warpX = 0.0
maskDark = 0.6
```

- `version` (integer, required): 1. A file with a higher version is listed
  read-only, "(newer format)", and never written. A missing version is an
  error.
- `name` (string): the display name; the slug when absent.
- `stages` (array of strings, 1..8): the chain, first stage first.
- `[params.<preset key>]`: numbers, keyed by the preset key, not by stage
  position, so reordering touches only `stages` and a hand edit reads
  naturally. Two stages of the same preset share one table, which matches
  what librashader does with their parameters anyway (D3).
- Unknown top-level keys and unknown tables are logged once
  (`[SHADER] <file>:<line>: unknown key`) and kept: the menu writes through
  `recomp_cfg_patch_text`, which changes only the keys it sets and keeps
  comments. A file that does not parse is listed "(broken)", in red, with
  its error in the footer, and is never written.

Writes go to `<slug>.toml.tmp` and are renamed over the file, as
`recomp_cfg_patch` does. Rename moves the file (D5). Delete removes it.
The folder is created on the first save.

Why TOML in its own file, not tables inside `config.toml`:
`recomp_cfg_patch` refuses a flat key that the file holds as a `[table]`
(so a profile could not be patched as one key into `config.toml`), profiles are the thing players share, and one file per profile makes
copy, share and delete a file operation. Why not a `.slangp`: librashader
and RetroArch read only one `#reference` per preset, so a chain of presets
cannot be a wrapper, and a flattened `.slangp` loses which passes were
which preset, so the menu could not show stages again.

## D3. Composing a chain into one preset

librashader 0.12's C API builds a chain only from a file
(`libra_preset_create(path)`), so a profile of two or more stages is
composed into one `.slangp`:

1. Each stage's preset file is read by a small `.slangp` reader in
   `shader_profile.c` (the format is `key = value` lines, `#reference`
   lines and comments). A `#reference` is followed (depth 16, cycle-safe),
   and the referencing file's lines override the referenced ones, which is
   how the wrappers set `warpX = "0.01"`.
2. For each stage, the reader collects: its passes (`shaderN` and every
   `<key>N` per-pass setting, which are copied through unchanged:
   `filter_linear`, `scale_type`, `scale_type_x/y`, `scale`, `scale_x/y`,
   `wrap_mode`, `mipmap_input`, `float_framebuffer`, `srgb_framebuffer`,
   `frame_count_mod`, `alias`), its `textures` with their per-texture keys,
   its preset-level `parameters = "a;b;..."` list, and the values of the
   names in that list.
3. The composite numbers passes in stage order (`shaders = total`), writes
   every shader and texture path absolute (each was relative to the file
   that named it), merges the textures list, and writes the preset-level
   parameters: the `parameters` lists are merged in stage order with
   duplicates dropped (the first stage keeps its place), and each name's
   value comes from the earlier stage that sets it. `fsr.slangp` carries
   such a list (`FSR_SHARPENING;FSR_FILMGRAIN;...`); dropping it would lose
   its preset defaults, so it is kept, and a ctest checks `fsr` +
   `crt-lottes` and `fsr` twice.
   Every path is written quoted, with forward slashes, as UTF-8
   (`shader3 = "C:/Program Files/BLiNX 2/shaders/crt/crt-lottes.slang"`):
   librashader accepts forward slashes on Windows, and the quotes keep
   spaces and non-ASCII names whole. A ctest composes from a folder with a
   space and a non-ASCII name and, on the POSIX host, from a `C:\`-style
   path string, and checks the written lines.
4. It goes to `<cache root>/slangp/<slug>.slangp`, through a temporary and
   a rename. It is rewritten at every compose, never read back as a
   source, and the file name is the slug so a stale one is overwritten. An
   unsaved profile composes to `~unsaved.slangp`.
   `<cache root>` is today only a D3D11 detail: nv2a_pb_d3d11.c builds
   `xbox_path_hdd_root()` + `"\\ShaderCache\\dxbc"` with a backslash. A
   host-neutral accessor, `xbox_path_shader_cache(char *out, size_t n)`
   in the path module, returns `<save root>/ShaderCache` with forward
   slashes on every host; the composer uses it on Metal and D3D11 alike,
   and the D3D11 dxbc cache moves onto it (same folder, so no cache is
   lost; its env override stays).
5. The request handed to `nv2a_present_chain_request` is that path, so
   `preset_path`, both backends and the failure path need no change. A
   one-stage profile skips 1 to 4 and requests the stage's preset as is,
   so a built-in profile is exactly today's `present.shader`.

**Clashes.**
- *Parameter names.* librashader keys runtime parameters by name across the
  whole chain: two passes that declare `MASK_INTENSITY` read one value
  (crt-lottes-fast declares it 0..1 step 0.05, crt-hyllian 0..1 step 0.1).
  v1 keeps that rule: one value per name, its range, step and default as
  `libra_preset_get_runtime_params` reports them for the composed preset (a
  probe in task 1.1 records which declaration wins; the menu shows what the
  library says). The value is saved under the preset key of its *owner*,
  the first stage that declares the name. A reorder can change the owner,
  so on load a shared value is accepted from any stage's table: the
  owner's table first, else the first other stage's table that sets it in
  stage order, with one line when two tables disagree. Save writes it under
  the current owner and removes it from the other stages' tables, so the
  file never holds two values for one name. This also keeps the default
  baseline right: "differs from the preset" is measured against the value
  librashader reports for the composed chain, not against one stage's
  declaration. The menu marks the row "shared with stage N".
- *Aliases and textures.* Two stages that declare the same `alias` or
  texture name cannot be composed without rewriting shader sources (the
  shaders sample them by name). The compose fails with
  `[SHADER] profile <slug>: stage 2 (<preset>) reuses alias "<name>" from
  stage 1`, and the menu refuses the Add with that message in the footer.
  None of the bundled presets declares either.
- *Pass-indexed semantics.* `PassOutputN`, `PassOutputSizeN`,
  `PassFeedbackN` and `PassFeedbackSizeN` name a pass by its index in the
  chain, and renumbering shifts every later stage's passes. The reader
  scans each pass's `.slang` source (with its `#include`s) for those names;
  a stage after the first that uses one fails the compose like an alias
  clash (`stage 2 (<preset>) uses PassOutput1, which renumbering breaks`),
  and the menu refuses the Add. A first stage keeps its indices, so it may
  use them. Rewriting the indices in the sources is out of scope. None of
  the bundled presets uses them.
- *Original.* `Original` and `OriginalSize` are the chain's input, the game
  frame, in every pass, so in a later stage they are not that stage's
  input. crt-hyllian(-fast) sets `InputSize` from `OriginalSize`: after
  `fsr` it computes its scanlines from the game frame's height while it
  samples the scaled picture. This is how RetroArch behaves with appended
  presets and it is allowed; the reader flags a later stage whose source
  uses `Original` and the menu adds the dim note "reads the game frame"
  next to "sees the scaled picture". Probe 1.1 records how crt-hyllian
  after `fsr` looks on both backends.
- *Scale.* A stage whose last pass scales to the viewport hands the next
  stage an output-sized picture. CRT presets draw scanlines per source line,
  so one after `fsr`, or after another CRT, draws them per output line.
  This is allowed (RetroArch allows it), and the menu says so on the later
  stage: a dim note "sees the scaled picture". The check is the earlier
  stage's last-pass `scale_type`.

Why compose ourselves rather than ask librashader: 0.12 has no API to
append presets or passes, and the preset file is its documented input. The
reader is small and tested against the bundled presets and hand-written
cases (D10).

## D4. The store and the request

`nv2a_present_chain` keeps one request; it gains a kind:
- `present.shader` requests (a name or a path) stay as they are;
- a profile request carries the slug, the composed path, and the stage
  list: each stage's preset key and the names of the parameters it
  declares.

The stage of a row cannot come from the library: the published table is
filled from `libra_preset_get_runtime_params` (`params_read` in
nv2a_present_chain.c), which returns name, description, initial, min, max
and step, with no pass index. So at compose time, before the request is
made, `nv2a_present_chain_describe` (the GPU-free parse the descriptor dump
already uses) runs on each stage's own preset, and the request keeps each
stage's parameter names. `nv2a_present_chain_params_publish` then tags each
row of the composed chain by name: its stage is the first stage whose list
holds the name, and it is shared when a later stage's list holds it too. A
name that no stage lists (not expected) gets stage 0 and no flag. Describe
costs one preset parse per stage, at most 8, on the thread that composes;
without librashader there is no chain, so nothing to tag.

The active table grows from 64 to 128 rows (`NV2A_PRESENT_PARAMS_MAX`):
crt-lottes plus fsr is 17, and eight stages of large presets would pass 64.
Each row gains its stage index and a shared flag. A preset past 128
parameters gets its first 128, with one line.

**Profile error.** Parse and compose failures happen before any request,
so no generation exists to fail. The store keeps a profile error string
(`nv2a_present_chain_profile_error_set/get`, 160 bytes, cleared by the next
successful request): the profile module sets it on a parse error, a
missing stage, a clash or a limit, and the request falls back to stock.
A chain that composes but fails to build keeps today's path,
`nv2a_present_chain_failed(gen)`, and sets the same string from the
backend's message. The menu reads only that string for the red Chain
header, so both kinds show the same way (D9).

Values for a profile come from the profile, not the per-preset overrides:
the store's override rows gain a scope, `preset` (today's, keyed by preset
key, saved to the config) or `profile` (keyed by the slug and the name,
saved to the profile file). `nv2a_present_chain_param_set` writes the scope
of the active request. Override capacity stays 256 over every scope; the
reuse rule of the tracker item stays.

At start, `xbox_enhance_init` resolves the request (D7). It reads one
profile file, the one `present.profile` names, and only when that key is
set; with `none` it opens nothing under `shader-profiles/` (D6). The list
of profiles (the folder's `*.toml`, at most 64, sorted by name) is read
lazily, each time the menu opens the Shaders page, so a stock start reads
no profile file and a file dropped in while the game runs shows up.

## D5. Menu

The Shaders page, top to bottom:

1. **Profile**: a choice row, `< Soft CRT >`. Choices: `Off`, the four
   built-ins, then the user's profiles by name; a broken or newer-format
   one is shown in red and skipped by Left/Right. Changing it is live (the
   next present builds the new chain) and is saved as `present.profile`
   (a built-in saves as `present.shader = "<name>"` with `present.profile`
   removed, so a config that only uses built-ins reads exactly as today).
   Off saves `present.profile` and `present.shader` both removed (stock).
   Save writes the user config only, and a key removed there can still be
   set by a lower layer (`<root>/config/config.toml` under a per-title file,
   or `config.default.toml`), which by D7 would then win. So where a lower
   layer sets a key that the choice needs gone, Save writes it as `"none"`
   instead of removing it: `present.profile = "none"` for a built-in or
   Off, and `present.shader = "none"` for Off. The ctest covers both.
2. When a profile is active, a **Chain** header and one row per stage:
   `1  fsr`, `2  crt-lottes`, with notes ("sees the scaled picture",
   "missing" in red). On a stage row:
   - OK opens the **stage sub-list** (as a mod's sub-page: Back returns to
     the stage row);
   - Left / Right move the stage one place earlier / later (the footer
     says so); at an end it does nothing;
   - Clear (X, Delete) removes it, after the Reset row's confirm
     ("Remove fsr? A / Enter: yes"). The last stage cannot be removed:
     the footer says to pick Off instead.
3. **Add shader**: OK opens a picker sub-list: the bundled presets, then
   the `.slangp` files in `<root>/shaders/` (one level, sorted; a folder the
   player fills, created by nothing). OK on one appends it as the last stage
   and returns; the new stage is selected. A preset that does not parse
   (`libra_preset_create` without a GPU, as the descriptor dump does) or
   that clashes (D3) is refused with the reason in the footer. At 8 stages
   or 16 passes the row is dimmed with the limit in the footer.
4. Profile actions, as action rows:
   - **Save as new**: copies the active chain and values into a new user
     profile named "Profile N" (the first free N), selects it, and writes
     its file at the next Save. No typing needed on a pad.
   - **Rename** (user profiles only): a text-entry row (below).
   - **Duplicate**: as Save as new, named "<name> copy".
   - **Delete** (user profiles only): confirm, then, at once and not at
     Save, the file is removed and, when `present.profile` names it, the
     key is removed from the user config in the same step (a
     `recomp_cfg_patch` of that one key), so the config never points at a
     deleted file. The picker moves to Off.
5. **Reset to preset** on the page resets the active profile's values for
   every stage (today's row, widened).

The **stage sub-list**: the stage's preset name and path (info), its
parameters as `R_PARAM` range rows (as today; a shared one carries the
note "shared with stage 1"), *Move up*, *Move down*, *Remove*, *Reset this
stage* (removes the overrides of the names this stage owns).

**Text entry** (Rename), a new row type `R_NAME`: OK starts editing; the
row shows the name with a cursor. Editing is a modal state, as binding
capture is: `input_step` calls a `name_step(held, now)` right after
`capture_step`, and while an edit is on it consumes the pad and key input,
latches `s_kprev` and returns before any `ENHANCE_EV_*` is mapped, because
Space, Enter, Backspace, Q, E, Y, F5 and Delete all map to menu events
today (OK, Back, page change, Save, Clear) and would otherwise fire while
typing. The mapped events resume when the edit confirms or cancels;
closing the menu by any other route cancels the edit.
- Keyboard: letters, digits, space, `-`, `_`, `.` and `(` `)` are typed
  (with Shift for capitals), Backspace deletes, Left/Right move the cursor,
  Enter confirms, Esc cancels. Read from the same key polling the menu
  already does (`xbox_FramebufferKeyDown`, edge against `s_kprev`), with no
  new input path. Only ASCII in v1, and the key-to-character table is the
  US layout: on another layout a key types its US character (an AZERTY A
  types `q`). A layout-aware path (SDL text input) is a later change.
- Pad: Up/Down cycle the character under the cursor through
  `A-Z a-z 0-9 space - _`, Left/Right move the cursor, X deletes, A
  confirms, B cancels.
- Confirm checks the name: empty, or a slug another profile has, is
  refused in the footer. The file is renamed at the next Save; the old slug
  in `present.profile` is restaged.

**Dirty state and Save.** Chain edits and parameter changes are live and
unsaved, like every other row. The page title shows a dot while the active
profile differs from its file. Save (Y, F5, the Save page) writes, with
"Save keeps only what you changed":
- the config keys (`present.profile` or `present.shader`, and the
  built-ins' `present.shader_params`), as today;
- each user profile that has changes: `stages`, `name`, and the `params`
  values that differ from the composed preset's, removing keys equal to it.
  Profiles with no change are not touched (their mtime stays).
The Save page's *Reset to defaults* sets the picker to Off and clears the
built-ins' overrides, as today; it never deletes profile files. Leaving an
edited profile for another one keeps its edits in memory until Save or
exit; the menu's unsaved count includes them.

The descriptor dump (`RECOMP_MODS_DESCRIBE=json`) adds under `"shaders"`:
`"active_profile"` and `"profiles": [{"name", "slug", "file", "stages":
[...], "builtin": bool, "state": "ok"|"broken"|"newer"}]`. Schema stays 1.

## D6. Defaults and opt-in

`present.profile` defaults to `"none"`; no profile file exists until the
player saves one; nothing under `config/shader-profiles/` is read while the
key is `none` until the menu opens the Shaders page (D4), and no file is
composed,
so the stock present stays one atomic load. The enhancements layer gates it
all (`XBOXRECOMP_ENHANCE`). Games ship no profile files: the user's or
`config.default.toml` would be the only source, and the shipped one sets
none.

## D7. Migration and precedence

No file is rewritten at start. The request is resolved in this order:
1. `RECOMP_PRESENT_SHADER` set: that preset, as today (debug and bench
   use), logged with "present.profile ignored" when one is also set;
2. `RECOMP_PRESENT_PROFILE` set (not `none`): that profile;
3. otherwise the config layers (the per-title file, then
   `<root>/config/config.toml`, then `config.default.toml`), taken as one
   pair: the highest layer that sets either `present.profile` or
   `present.shader` decides, and the keys of lower layers are not
   consulted. In that layer a `present.profile` other than `none` wins
   (the profile); else its `present.shader` other than `none` (as today,
   shown in the picker as its built-in; a path shows as "<stem> (config)",
   a one-stage profile with no file); else stock. So a per-title
   `present.shader = "fsr"` is not overridden by a profile set in the
   shared `config/config.toml`, and an explicit `"none"` in a layer stops
   a lower layer's choice (D5's Save relies on this). The layers are read
   one by one through the existing `enhance_cfg_file(i)`, not through the
   merged `enhance_cfg_string`;
4. stock.

A chosen profile that is missing or broken logs one line and presents
stock: it never falls through to `present.shader`, so a typo cannot
silently pick an older look.

A player with `present.shader = "crt-lottes"` and tuned
`[present.shader_params.crt-lottes]` sees the built-in *crt-lottes* active
with those values, with nothing to do. Making a chain from it (Add) or
*Save as new* copies the tuned values into the new file; the
`present.shader_params` table stays, still used by the built-in.
`present.shader` is not deprecated: it is the short form of a one-stage
profile and the env knob the benches and docs use.

## D8. Backends

Both backends already take a path from `nv2a_present_chain_preset` and
publish the table from the preset they parsed; a composed file is a preset
like any other. Changes on each, mirrored:
- the published table carries the stage index and the shared flag
  (computed in `nv2a_present_chain_params_publish` by name, from the
  request's per-stage parameter names (D4), not in the backend);
- the D3D11 dxbc cache directory comes from `xbox_path_shader_cache` (D3),
  the same folder as today;
- nothing else. The surface rule of the tracker item (`internal` draws at the
  output while a chain runs) applies to any chain.

CPU rasteriser and SDL presenter: no chain, the page is hidden, the key is
logged and ignored, as `present.shader` is today. Linux-native Vulkan
(when it lands) uses the same path.

## D9. Limits, cost and failure

- 8 stages, 16 passes in a composed preset, 128 parameters in the table,
  64 profiles listed, 48-byte names. Each limit refuses the edit with a
  footer message; a file past one loads its first 8 stages with one line.
- GPU cost is the sum of the passes; viewport-scaled passes cost per
  output pixel. The page's footer on the Chain header shows
  "N passes", and the Stats page's present time (when the present-ms stat
  exists) is the measure. No automatic downgrade.
- Compile time: a chain is built on the present thread, as now; a long
  chain stalls one present the first time (librashader caches compiled
  shaders across runs). The menu shows "building" while the generation is
  pending.
- Failure: a parse error, a missing stage, a compose clash or a limit
  happens before any request, so it sets the store's profile error (D4)
  and requests stock; a chain creation failure calls
  `nv2a_present_chain_failed(gen)` as today and sets the same error. Either
  way: stock present, one `[SHADER]` line naming the profile and the
  stage, and the Chain header in red with the error string ("stage 2
  (crt-hyllian) failed: see the log"). The profile
  stays selected so the player can remove the stage; no retry until the
  next change. When librashader does not say which pass failed, the line
  says so and names the composed file.

## D10. Tests

- `tests/shader_profile` (new ctest, no GPU, no library):
  - parse: the example above; version missing, higher, wrong type; empty
    `stages`; 9 stages; unknown keys kept; a `[params.x]` value that is not
    a number; names and slugs (unicode name, slug clash);
  - serialize: differences only; a round trip keeps comments and unknown
    keys; reorder changes only `stages`;
  - compose: each bundled preset alone (pass settings copied), `fsr` +
    `crt-lottes` (3 passes, absolute paths, the wrapper's `warpX` kept),
    the same preset twice, `#reference` depth and cycles, an alias clash and
    a texture clash refused, 17 passes refused; the preset-level
    `parameters` lists merged without duplicates (`fsr` + `crt-lottes`,
    `fsr` twice); a later stage using `PassOutput1` or `PassFeedback0`
    refused, a first stage allowed; a later stage using `OriginalSize`
    flagged; paths quoted with forward slashes from a folder with a space
    and a non-ASCII name and from a `C:\`-style string;
  - stage refs: a bundled name, `user:<stem>`, a relative name found in
    `<root>/shaders/` before the executable's directory, a user stem that
    clashes with a bundled name refused;
  - shared values: a value under a non-owner's table is read, and Save
    re-homes it under the owner and removes the other copy;
  - migration: `present.shader` only, `present.profile` only, both, env
    over config, a missing profile gives stock; the highest layer setting
    either key wins (a per-title `present.shader` over a shared
    `present.profile`); Save writes `"none"` over a lower layer's key;
    `enhance_cfg_user_dir` with a per-title file, `RECOMP_CONFIG=<file>`
    and `RECOMP_CONFIG=none`.
- `tests/present_chain`: profile requests, the 128-row table, stage index
  and shared flag tagged by name from the per-stage name lists, the profile
  error string (set by a compose failure, cleared by the next request),
  override scopes, with `fake_lrs.c` grown to report parameters for a
  composed file.
- `tests/present_chain_lrs` (new ctest against the real library, no GPU):
  skips (ctest skip code) when librashader is not found; else composes
  `fsr` + `crt-lottes` from the bundled presets, runs
  `nv2a_present_chain_describe` on the composed file and expects 17
  parameters, and on each stage alone expects 4 and 13.
- `tests/enhance_menu`: the Profile picker (built-ins, user, broken skip),
  Add, Move by Left/Right and by the sub-list, Remove with confirm, last
  stage kept, Rename on keyboard and pad (Q, E, Y, F5, Space and Delete
  typed or swallowed, never firing their menu events), Save as new, Delete
  (file and `present.profile` removed at once), the list read only when
  the page opens, the unsaved
  count, Save writing only changed profiles, Reset to defaults leaving
  files.
- A librashader probe (scratch, as the tracker item's) records what
  `get_runtime_params` reports for a composed preset with a shared name,
  and how crt-hyllian after `fsr` looks (its `InputSize` is the game
  frame's `OriginalSize`), on macOS and Windows.
- Harness: `blinx2 golden` keeps `present.profile = "none"` in its stock
  key list; a `scripts/test_*.py` case checks the key is listed. The
  release wizard is untouched.

## D11. Public safety

Profiles hold preset names, paths and numbers: no game data. Example
profiles in the docs use only the bundled presets. The composed file is a
cache, never committed. Bundled licences are unchanged (no new shader is
vendored); a user preset under `<root>/shaders/` is the player's own.

## Decisions on the open questions (2026-10-30)

The user decided 1, 2, 3 and 5. The orchestrator set 4 and 6 to the
recommended defaults, and the user may revisit them.

1. **Shared parameters (the user):** one value per parameter name across
   the chain, with the "shared with stage N" marker (D3, D5). Renaming
   clashing parameters in shader sources is not planned.
2. **Per-pass scale and filter (the user):** not in v1. The composed
   passes keep each preset's own settings. A later `[pass.<preset key>.<n>]`
   table stays possible.
3. **Pad text entry (the user):** Rename works on the pad through the
   character spinner, and keyboard typing works too (D5).
4. **User presets (orchestrator default):** they go in `<root>/shaders/`
   and the Add picker lists them. Presets shipped by mods come later, as a
   follow-up item.
5. **Built-ins' parameters (the user):** the built-ins keep their tuning in
   `[present.shader_params.*]` (D1, D7). `present.shader_params` is not
   retired.
6. **Limits (orchestrator default):** 8 stages and 16 passes for now (D9).
   A lower pass cap for the Deck is reconsidered after the tracker item
   measurements.
