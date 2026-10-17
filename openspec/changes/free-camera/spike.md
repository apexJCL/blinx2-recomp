# Free camera and modding tools: spike (BLX-197, 2026-10-17)

Opus, research spike: this assesses the work and builds nothing. Game `cat/` at main `277e780`.
Toolkit `xboxrecomp/` is on `posix-host/portability`. The enhancements design is on
`spike/enhancements` `baeb15b`.

The evidence comes from small read-only scripts over the game files and from three short headless
Metal runs (`RECOMP_DEBUG` `mem_dump` and `vsh_const_dump` on `@stage1`). The raw runs stay
private and are not in the repo. Generated-code line numbers refer to `src/recomp/gen/` at main
`277e780`. Effort is in person-weeks (pw) of agent sessions. Every pw figure is a **guess** unless
the text says otherwise. An Opus review (2026-10-17) corrected the view-matrix reading in
section 5. This version includes those fixes.

**Headline.**

- **Model and level editors (exploration only, not for any release).** No community tool reads
  BLiNX 2 geometry. The models are not in the archives: they sit in about 33.5 MB of custom data
  sections inside `default.xbe`. pyBlinx's BLiNX 1 notes are the only head start.
  - Any editor is custom work: a parser, glTF out, glTF in, and a write-back step. Blender is the
    only part we can reuse.
  - A model editor that also writes models back is 8-14 pw. A level editor is more.
  - A read-only path is cheap and comes first: capture what the game draws and export it to glTF.
- **Free camera (worth building, post-v1).**
  - Every model's world×view passes through one 59-byte matrix-copy routine, `sub_0003F940`, on
    its way to the vertex constants. A `sub_X` wrapper there can re-base each model onto a free
    view, with no generator change.
  - First, M0 has to find the game's view matrix `V_game`.
  - About 3.5-5 pw.
- **Mod layer.** It needs a small first slice of D6, the static module table, so that the free
  camera ships as a module and not as a second one-off like `fx.glow`.
- **User decision (2026-10-17).** Textures plus the free camera are enough for now. Mesh
  replacement and both editors stay exploration only.

## 1. Format inventory

| File / data | Contents | Understood | Evidence |
|---|---|---|---|
| `*.iph` + `*.ipk` | archive index + data | **fully** (read in our CLI) | `.iph`: `IPK1`, u32 align, u32 count, u32 total, then 80-byte entries (name[64], flags bit0 = LZSS, stored, offset, raw). Nested `.ipk` inside: 26 in `media`, 66 in `lng_us`. `xboxrecomp-cli/src/xboxrecomp_cli/enhance/ipk.py` |
| LZSS | entry compression | **fully** | Okumura: 4096-byte ring, start 4096-18, max match 18, a set flag bit means a literal (`ipk.py`) |
| `.dds` | textures | **fully** | 4498 in `media` + `tank_tex`: DXT1 3466, DXT3 905, DXT5 105, RGB16 13, RGB32 9; 2352 have mips. Uploaded byte-for-byte; the `textures.pack` swap is already live on Metal and D3D11 |
| `.mix` (MIXF) | XPR0 texture bundles (UI, `lng_us`) | **fully** | `xpr.py`; 84 in `media`, 2186 in `lng_us` |
| XBE sections `MDL*` (`MDLTNK` 3.1 MB, `MDLPL` 914 KB, `MDLGA`, `MDLAO`, `MDLGIM`, `MDLBT`, `MDLSR`, `MDLOB`, `MDLEN`, …) | character, enemy and object models | **partly**: layout guessed, never parsed | Mixed load flags: `MDLPL`, `MDLGA`, `MDLAO`, `MDLGIM` and `MDLEN` are preload (flags 7), the rest are flags 5. All are mapped at their VA by the toolkit's `xbox_MemoryLayoutInit` (`xboxrecomp/src/kernel/xbox_memory_layout.c:3169`); `cat/src/main.c` `load_xbe` only reads the file. Pointer-rich: about 1% of dwords are absolute self-VAs. About 40-50% of dwords are floats. Many blocks start with u16 `0x0030` + a count. Texture names are inline (`c_b2_*`, `h_b2_*`, `p_b2_*`). pyBlinx's BLiNX 1 vertex-list terminator `0xff000000` is common here (`MDLTNK` 1976, `MDLPL` 144) |
| XBE sections `MOTPL` (1.95 MB, preload), `MOTP0` | animation | **no** | no `0xff000000` runs; float-dense; layout not started |
| XBE sections `M11`…`M121` (21 sections, 20.7 MB) | per-stage geometry and probably the stage layout | **partly**: same family as `MDL*` | `M11` has 101 terminators and `M111` 20. The same node and header patterns as `MDL*` |
| XBE `G1`…`G5` (627 KB), `GIMCOM`, `DATED`, `DATADV`, `DSKERDAT`, `MSHIP`, `COMTNK` | unknown: gimmicks (stage objects), data tables | **no** | `GIMCOM` has 2 terminators; `G1` has none. The custom sections `DATED`…`MOTP0` total about 33.5 MB; `.data` (mostly BSS) is not counted |
| skinning, bone palettes | from the vertex programs | **runtime only** | every batch runs a vertex program; the bone/matrix palettes are in `c[0..47]`; world×view per model is in `c[100..103]`. Whether the palettes also carry the view is open (section 5.1) |
| `.cam` (448) | scripted camera keys per stage/area/event | **header only** | 160 bytes: `41 00 00 00 01 00 00 00 01 00 00 00 01 00 00 00` + floats. Paths come from `%smedia\cam\cam%02d%02d_%03d.cam` and `…\event\EVCAMST%02d%02d_%03d.CAM` |
| `.evb` (74) | event scripts (`event/stNNNN_000.evb`) | **header only** | `01 00 00 00`, u32 size, u32 count, `0x10` |
| `.eff` (170), `.eft` | effects | **no** | `.eft` starts with `EFT Ver.` |
| `.icb` (310), `.tga` (220) | images | **header only** | `.icb`: `00 01 01 00 00 00 01 18` |
| `bumpdata/*.bum` (17) | bump data | **no** | fixed 43008 bytes each |
| `edit_char/*.edt` (45) | most likely presets for the in-game MODEL_EDIT character editor (part and colour indices). **Unconfirmed** | **no** | `mdl_param_list_tgNNN.edt`; every file is exactly 108 bytes of small byte values plus zero padding, with no floats or geometry |
| `se/*.bin` | XSSB sound banks | **out of scope** | |
| collision, spawn and enemy tables, triggers, time-control objects | level logic | **not located** | most likely in `M*`/`G*` sections (pointer-rich, non-preload); nothing in the archives looks like them |

The engine is in-house as far as the evidence goes: no RenderWare or Criterion strings, and
nothing matches a public format.

## 2. Tools: what can be reused

| Tool | Covers | R/W | License, activity | Fit |
|---|---|---|---|---|
| our `xboxrecomp-cli` `enhance/` (`ipk`, `xpr`, `dds`, `texhash`, `pack`) | archives, textures, texture packs | R, plus pack build | ours | **already the texture path**. An `ipk` writer would be small but isn't needed, because runtime replacement beats repacking |
| pyBlinx (github.com/bakerdonkey/pyBlinx) | **BLiNX 1** XBE geometry (`MAP11`, `MDLB1`): node tree, float3+pad vertices, int16 strip "triparts" → OBJ | R | MIT, 2018, last push 2023-10 | **the only starting point**: notes and test ideas for a BLiNX 2 parser. It has no skinning, animation or UVs and gives no BLiNX 2 support |
| Blender | glTF import and export, custom properties as glTF `extras` | R/W | GPL-2.0+, active | **the editor** for any model or level path. It needs our glTF in and out with no data loss |
| Noesis | many formats → FBX/glTF | R | freeware, closed | no: a plugin would be custom work in a closed tool, with no repack |
| QuickBMS | archive scripts, reimport when sizes fit | R/(W) | GPL-2.0 | no: our `ipk.py` already does more |
| RTX Remix | mesh, texture and light replacement by geometry hash, with anchors | R/W at runtime | MIT, active | **architecture model only** (D3D9/D3D8 hook, not our renderer) for mesh replacement |
| Dolphin graphics mods, PCSX2/PPSSPP texture packs | hash-keyed runtime replacement | runtime | GPL | prior art for `textures.pack`; mesh replacement exists only in a Dolphin fork |
| xboxdevwiki XPR docs, XboxToolkit | XPR/XBE | R | wiki / MIT | already covered by `xpr.py` |
| RenderDoc (D3D11 under Proton), Xcode GPU capture (Metal) | frame inspection | R | MIT / Apple | for debugging a capture path, not as a pipeline stage |

No tool for BLiNX 2 exists: no QuickBMS script, Noesis plugin or Blender add-on. No public `.ipk`
spec exists either. Ubisoft UbiArt and opkg `.ipk` are unrelated formats. Models Resource and the
Xentax archives could not be checked (HTTP 403, offline).

## 3. Model editor paths (exploration only)

The write-back rules apply to every path:

- Owner-generated files are made from the owner's own dump and never distributed.
- Replacement is opt-in under `XBOXRECOMP_ENHANCE`, off by default.
- Goldens run stock.

That rules out shipping a patched `default.xbe` or archives. It favours runtime replacement keyed
on content, the way `textures.pack` already works.

| Path | What | Effort (guess) | Custom vs reused | Risks |
|---|---|---|---|---|
| **A. Runtime capture → glTF** (read only) | The backend dumps one frame's draws to glTF: the vertex and index buffers as fetched, the matching texture (already DDS), and `c[]` per draw. Rigid meshes come out in world space through `c[100..103]` and `V⁻¹`. Skinned meshes come out posed, with bone palettes as extras | 2-3 pw | custom capture in shared backend code; reuses the existing vertex fetch and texture decode, plus Blender | Vertex programs carry the transforms, so un-skinning needs the per-program attribute layout. Output is posed, one frame, not a rest pose |
| **B. Mesh replacement by hash** (RTX Remix style) | Key = hash of the vertex and index ranges + program hash. A `meshes.pack` built by the CLI from glTF; the backend swaps the buffers at draw time on Metal and D3D11 | 4-8 pw on top of A | custom on both backends + CLI; reuses the `textures.pack` design | Skinned meshes must keep the bone indices and weights layout. Animated or CPU-written buffers have unstable hashes. Culling uses the old bounds |
| **C. Offline XBE section parser → glTF → Blender → back** | Parse `MDL*`/`M*` node trees (pyBlinx-derived), export glTF with skeleton and UVs, re-import, then write back. Write-back is either a **runtime section overlay** (the toolkit's section mapping maps an owner-built section image when the stock section's sha matches) or an in-place patch of a *copy* of `default.xbe` within the section size | 8-14 pw, plus 3-6 for `MOT*` animation | all custom except Blender; pyBlinx for hints | The format is unknown beyond the patterns above. Growing a section needs every self-pointer relocated, which the overlay can do since the runtime owns the VA layout. Skinning and animation formats are untouched so far |
| D. Noesis plugin | read-only view | 2-4 pw | custom in a closed tool | no write-back, so a dead end |

The write-back choice is **the runtime overlay over an on-disk patch**. It leaves the dump alone, it
is a no-op when off, and it fits the owner-generated-assets rule. `XeLoadSection` is only refcount
bookkeeping (`xboxrecomp/src/kernel/kernel_bridge.c:4540`). Every section is mapped once at boot by
`xbox_MemoryLayoutInit` (`xboxrecomp/src/kernel/xbox_memory_layout.c:3169`), so there is one choke
point for overlays. That makes the overlay a generic toolkit hook under `XBOXRECOMP_ENHANCE`, not
cat code.

## 4. Level editor (exploration only)

- **What is known.**
  - Stage data is in the `M11`…`M121` sections (21 sections, about 1 MB each).
  - Scripted cameras are in `.cam`, events in `.evb` and effects in `.eff`.
- **What is not located.** Object placement, spawn and enemy tables, collision, triggers and
  time-control objects. They are probably pointer tables in `M*`/`G*`/`GIMCOM`, found by tracing
  the stage loader.
- **Reuse.** Blender through glTF, with nodes for placed objects and `extras` for type, parameters
  and trigger links. Collision would come in as a separate hidden mesh.
- **Custom work.** Everything else: the loader trace, the parsers, a validator and the write-back
  overlay.
- **In-game editor.** An overlay on the mod layer that moves objects in guest memory live. It is
  cheaper to prototype than offline write-back, but nothing persists without the parser anyway.
- **Effort (guess).**
  - Tracing and documenting the stage formats: 3-6 pw. This is the precondition.
  - A placement-only Blender round trip: about 6 more pw.
  - Adding collision and triggers: 10-16+ pw in total.

## 5. Free camera (post-v1, depth)

### 5.1 What the render path does with matrices (found in this spike, corrected by review)

- **Constants.** Vertex constants per batch:
  - `c[100..103]` = world×view for the model being drawn;
  - `c[0..47]` = bone and other per-batch matrix palettes;
  - `c[112]` = a view-space light/up vector;
  - `c[58]`/`c[59]` = viewport scale and offset (`320,-240,16777215` / `320.53,240.53`).

  Projection is folded into the programs and the viewport. The world is Y-down.
- **`0xAAF450` is a per-model matrix ring, not a set of views.** It holds `0x80` bytes per slot:
  - `+0x00`: xmm4-7, stored by `sub_002D4C10`;
  - `+0x40`: a copy of the current transform `0xAAD3A0` (world×view for that model).
- **The slot index `[0xAD7BBC]` is a running counter.**
  - `sub_000359F0` resets it to 1 once per frame through `sub_000348A0` (gen
    `recomp_0001.c:3332`).
  - `sub_00039100` and `sub_0003A780` each increment it on every call (`recomp_0001.c:13005`,
    `:15520`).
  - The dumps agree: slots 1-63 hold 63 different matrices. The "slot 2 = main view" reading in the
    first draft was one model whose world matrix is about the identity.
- **The two writers.** Both are called from `sub_0003B8D0`, which has about 100 call sites in the
  enemy, object and stage draws:
  - `sub_00039100` (`0x39100`-`0x3A44D`) is the normal path.
  - `sub_0003A780` is taken when `[0x67EF6C] != 0` (the branch at `0x3BBDF`); it writes a slot
    from `0x3A982`.

  `sub_000BAC40` also calls `sub_00039100`. Each writer then runs
  `ecx = (slot<<7) + 0xAAF490; eax = 0xAAD3A0; call sub_0003F940`.
- **`sub_0003F940`** (59 bytes, 22 call sites) copies a matrix from `eax` to `ecx`. When `eax == 0`
  it stores xmm4-7 to `ecx` (`sub_002D4C10`). When `ecx == 0` it loads `eax` into xmm4-7
  (`sub_002D4BD0`).
- **The current transform.** `0xAAD3A0` is the transform being composed. `sub_00038B00` *stores* it
  into the node matrices at `0xA001D0 + idx*64`. A matrix stack lives at
  `0x885E20 + [0xAD8030]*64`.
- **Not found: `V_game`, the view matrix itself.** The view is already folded into every stored
  matrix. The derived eye (344.8, 25.9, 349.5) is not stored as a float triple anywhere in the
  64 MB of guest memory. So the game camera is probably angles plus a distance around a target, and
  the view is built from that and pushed into the composition (`0xAAD3A0` or the bottom of the
  stack) once per pass. **A free camera needs `V_game`**, either to undo it per model or to replace
  it where it is composed. M0 finds it.
- **The projection builder is not identified.** These read 4/3 at `0x3DFA30`:
  - `sub_00293B30` (called from `sub_002865E0` and `sub_00295320`);
  - `sub_0035E600` (SRCADV).

  0.75 constants sit near `0x3DEE14`. A free camera keeps the game's FOV. A FOV option (E10)
  needs the builder.

### 5.2 Hook options

| Option | How | Verdict |
|---|---|---|
| **1a. Inject `V_free` where the view is composed** | A `sub_X` wrapper on the function that first puts `V_game` into `0xAAD3A0` or the matrix stack (found in M0). When the camera is active, it substitutes `V_free`. Every product downstream inherits it: the ring slots, the bone palettes, and `c[112]` if that is derived from the same matrix | **preferred if M0 finds a single composition point**. One write per pass and no per-model maths. Needs one override (a 9-minute recomp) |
| **1b. Correct every ring store in `sub_0003F940`** | Wrap `sub_0003F940` and run `_gen`. When the destination is in the ring (`0xAAF490 + n*0x80`), the camera is active and the caller is `sub_00039100` or `sub_0003A780` (return address), rewrite the slot as `M' = M·V_game⁻¹·V_free` | **fallback**. It covers both writers. It needs `V_game` per frame and costs one 4×4 multiply per model. Bone palettes and `c[112]` are *not* covered unless they also go through this copy, which M0 checks |
| 2. Per-frame guest-memory poke | write into the ring or `0xAAD3A0` each frame (`RECOMP_DEBUG=poke` style or `on_frame`) | **rejected**: the ring is rewritten for every model, so a poke races the draws and moves one model at most |
| 3. Backend view-constant override | rewrite `c[100..103]` in the backend with `V_game⁻¹·V_free` | **rejected**: `c[]` mixes world×view, bone palettes and view-space vectors per program. It needs per-program knowledge mirrored in both backends, and `V_game` is still needed |

Both 1a and 1b keep the game's own camera state untouched, so returning to the game camera is
free. The precedent is `fx.glow`'s `sub_0005B7D0` wrapper in `recomp_manual.c`.

**Known drawback.** The game culls and picks LOD with its own frustum, so objects outside the real
camera's view are missing or pop. That is acceptable for photo mode. A later fix is to widen or
disable the cull test once its function is found.

### 5.3 Controls and behaviour

- **Config** (cat `enhance` keys, defaults keep stock):
  - `camera.free = off|on`. `on` only enables the toggle; the camera still starts on the game view.
  - `camera.free_speed`, `camera.free_look_sens`.
  - `camera.free_hud = keep|hide`.
  - Hotkeys `camera.free_toggle` (default F6), `camera.free_hud_key` (F7),
    `camera.free_freeze_key` (F8) and `camera.free_reset_key`. Their names go through
    `input_names` and are read through `enhance_cfg`, so `report_unused` sees them. They cannot go
    under `[input.bindings]`, which accepts only the Duke's controls
    (`xbox_InputControlFromName`, `enhance_input.c:288`) and warns "unknown control" for anything
    else.
  - Defaults go in `packaging/config.default.toml`. Each key gets a `RENV_*` row in
    `cat/src/env/recomp_env_game.h` and a row in `cat/docs/env.md`.
- **Fly.**
  - On toggle, seed `V_free` from `V_game`, so the camera starts where the game camera is.
  - Pad: left stick moves, right stick looks, triggers go down and up (Y-down world), a shoulder
    button speeds up.
  - Keyboard and mouse: WASD/QE plus mouse look through `enhance_input`.
- **Input capture.** While flying, the game must see a neutral pad.
  - No glue exists for this yet. The XInput overrides in `recomp_manual.c` run per port and per
    poll.
  - Add a new wrapper on `sub_0005C930`, the once-per-frame input poll named in the enhancements
    design. It carries `on_frame`, and it zeroes the game's pad state after the poll while capture
    is on.
  - Capture must also swallow KBM mouse-look, because `input.mouse_look` feeds the pad.
  - The wrapper can share one recomp with the camera override.
- **Freeze.** The game has a combined update+render (`sub_00062FB0`), so pausing the world needs
  the game's own pause or time-stop flag; skipping the call would also stop rendering. Find the flag
  in M0, from the pause-menu path or the in-game Pause time control. If no clean flag exists, ship
  without freeze.
- **HUD hide.** Skip HUD batches in shared backend code (`nv2a_backend_common`), so Metal and D3D11
  agree by construction. The CPU rasteriser only has to build, so its gap goes in TASKS.
  - The program hash alone is too coarse: the XDK pass-through `B2913952` also draws the Sofdec
    movie quad (`openspec/changes/present-surface/design.md:16`), and the pass-through programs
    probably draw the fades too.
  - Filter on the hash (`5474DB2A`, `B2913952`) **plus state**: the render target is the back
    buffer, the depth test is off and blending is on.
  - **Risk:** fades or effects that match the same state disappear too. Collect a list of the
    matches in M2.
- **Return.** Toggling off stops the substitution. The game view comes back on the next pass with
  nothing to restore.
- **Off-path cost.** When `camera.free=off`, each wrapper is a single branch, and `enhance_stock`
  and every golden are unchanged.

### 5.4 Plan, ready for an openspec proposal

| Step | Work | Gate | pw (guess) |
|---|---|---|---|
| M0a | **Find `V_game`.** Trace back from `sub_0003B8D0`/`sub_000348A0` to where the view first enters `0xAAD3A0` or the `0x885E20` stack: a debug-only `RECOMP_DEBUG` log of the matrix at the stack bottom per frame, checked against the derived eye. Decide between 1a and 1b. Check whether `c[0..47]` and `c[112]` carry the view. Prove it with a fixed `V_free` and Metal screenshots (on the Mac, under the run lock) | screenshots, kept private | 1-1.5 |
| M0b | Find the pause or time-stop flag | a flag that freezes the update but keeps the render | (in M0a) |
| M0c | **`.edt` presets** (about half a day): find the reader of `edit_char/*.edt` (search the `mdl_param_list_tg` string's xrefs) and map the 108 bytes to MODEL_EDIT parts and colours | a byte map in this change | 0.1 |
| M1 | The mod-layer slice (section 6.3) with `camera.free` as its first module; the `sub_0005C930` wrapper with `on_frame` and input capture; fly controls | `enhance_stock` golden unchanged; a `scripts/test_*.py` case for the keys | 1.5-2 |
| M2 | HUD hide in `nv2a_backend_common` (hash + state), a ctest for the filter, a list of the batches it matches | Metal golden + `blinx2 bench golden` under Proton | 0.5-1 |
| M3 | Freeze (if the flag exists), reset, the cutscene check, docs, an Opus review | full gates | 0.5-1 |

Total: **3.5-5 pw (guess)**.

Risks:

- `V_game` may not have a single composition point. Then 1b's per-model correction is required,
  and any palette or vector that skips `sub_0003F940` stays on the game camera: skinned characters
  or lighting would drift.
- Culling pop (section 5.2).
- The audio listener stays with the game camera. That is fine for photo mode.
- Cutscenes (`.cam`/`EVCAMST`) and the `sub_0003A780` path may compose the view differently. They
  are tested in M3, not assumed to work.

## 6. Mod layer: revival

### 6.1 What has landed

- **Toolkit `src/enhance/`, option `XBOXRECOMP_ENHANCE`** (off in the toolkit, on in cat's CMake
  and `stock_cmake`):
  - `xbox_enhance_init(root, title)`.
  - `enhance_cfg`: TOML through `recomp_cfg.c` with `config.toml` over `config.default.toml`, env
    binding, typed getters and `report_unused`.
  - `enhance_input`: `[input]` / `[input.bindings]`, keyboard and mouse.
  - Keys `render.scale` 1-4, `render.aniso`, `present.filter`, `present.fullscreen`,
    `present.pacing`, `present.surface`, `display.aspect` (4:3 only), `textures.pack`,
    `textures.font`, `textures.text` and the `input.*` keys.
- **Cat:** `fps.mode` (lock30 only) and `fx.glow` (`src/glow.c` + the `sub_0005B7D0` wrapper in
  `recomp_manual.c`; golden `enhance_stock`).
- **Not landed** (spike/enhancements design):
  - **D6:** `struct xbox_mod` / `xbox_mod_api`, the static table and the hooks `rt_dims`,
    `batch_classify`, `on_present`, `on_vblank`, `on_flip`, `on_frame` and `poke_at`.
  - **D7:** `--hook-functions`.
  - **D8:** dynamic plugins.
  - E7 (cheat/poke file), E10 (FOV), lock60/free fps and Hor+.
- **The user's decisions (2026-10-04) still stand:** TOML, static modules now, a Lua-style
  scripting assessment later based on real mods, upstream as an opt-in extension, easiest extras
  first, goldens stock.

### 6.2 What each feature needs

| Feature | Needs from the mod layer |
|---|---|
| free camera | function hooks on the view composition point or `sub_0003F940`, and on `sub_0005C930` (today: `sub_X` wrappers); typed guest-memory access; config; input query + **input capture** (pad and mouse-look); HUD batch filter; optional pause-flag poke |
| `fx.glow` (exists) | function hook on `sub_0005B7D0`; config. Moving it onto the module table proves the API |
| E7 cheats/pokes | `poke_at(hook, va, value)` on a frame hook; a file format (TOML) |
| E10 FOV | function hook on the projection builder (not found yet); config |
| lock60 / free fps | vblank/flip hooks (`on_vblank`, `on_flip`); the timing variables `[0x3FD33C]`/`[0x3FD340]` |
| Hor+ | `rt_dims` + projection hook |
| `.edt` preset editor | none at runtime: an offline tool writes presets inside the 108-byte format; loading them needs a file overlay or the game's own reader |
| model capture (path A) | backend draw hook (shared code), a capture hotkey through input |
| mesh replacement (path B) | backend draw-time buffer swap, pack loader |
| section overlay (path C, level edits) | a section-mapping hook in `xbox_MemoryLayoutInit` (toolkit) |
| in-game level editor | everything above, plus an overlay UI (ImGui-class), which is not in scope |

### 6.3 Minimal first slice (ships with the free camera)

- **Module table.** Toolkit `src/enhance/mod.h` + `mod.c`, under `XBOXRECOMP_ENHANCE`:
  - `struct xbox_mod { name; init(api); shutdown(); }` and a static table that the game registers
    (`XBOX_MOD_REGISTER` or a game `enhance_table.c`), as in D6.
  - `xbox_enhance_init` calls each `init`.
- **`xbox_mod_api` v1**, no more than this:
  - guest memory base + the `MEM32`/`MEMF` helpers;
  - `enhance_cfg_*` getters;
  - log;
  - `on_frame(fn)`, from D6. The game glue calls it once per guest frame: in cat, the new
    `sub_0005C930` wrapper on the guest thread, not the ack thread.
  - **additions to D6:**
    - `input_state()` (from `enhance_input`) and `input_capture(bool)`, which the game's pad
      glue honours (pad and mouse-look);
    - `batch_filter(fn)`: a predicate over (program hash, draw state), called from
      `nv2a_backend_common` before a draw, so both backends agree. It is a narrower form of D6's
      `batch_classify`.
- **Function hooks stay per-title `sub_X` wrappers (D7 today).** The module exposes a C function,
  and the wrapper in `recomp_manual.c` calls it. Nothing changes in the generator.
- **Tests.**
  - A ctest for table init order and for `batch_filter` with a stub backend.
  - A cat `scripts/test_*` case for the keys.
  - `enhance_stock` golden unchanged.
- **Effort:** 1-1.5 pw, counted inside the free-camera total (M1).

### 6.4 What follows, in order

1. Move `fx.glow` onto the table. This is cheap and proves the API on a second module.
2. `poke_at` + E7 poke file.
3. `on_vblank`/`on_flip` for lock60 and free fps.
4. `rt_dims` + projection hook for Hor+ and E10 (needs the projection builder).
5. D7 `--hook-functions FILE`: generated `recomp_hook_pre/post[idx]` + `recomp_hook_set(va, …)`,
   so modules hook by VA without a `recomp_manual.c` edit. Add `all` for mod-development builds.
   This becomes worth it at about three or more wrapped functions; the free camera alone brings two.
6. The scripting assessment (Lua-class), using the modules above as test cases.
7. D8 dynamic plugins, last, only if someone outside the repo writes mods.

## 7. Recommendation and order

The user decided on 2026-10-17 that textures plus the free camera are enough for now.

1. **Mod-layer slice + free camera: post-v1, the one thing to build.** 3.5-5 pw (guess). Start with
   M0 (section 5.4), 1-1.5 pw, which finds `V_game`, picks hook 1a or 1b, and finds the pause flag.
2. **`.edt` preset mapping (M0c): half a day, then decide.** If the bytes map cleanly, a preset
   editor is a cheap remix route, though it is limited to the parts the game ships.
3. **Model capture to glTF (path A): exploration only.** 2-3 pw. It gives owners a read-only look at
   the models in Blender and supplies data for any later parser work.
4. **Mesh replacement by hash (B) and the section overlay (C): exploration only**, per the user's
   decision. Choose B for "swap a model" and C for real editing, if this is ever reopened.
5. **Model and level editors: exploration only, not for any release.** Custom parsers seeded by
   pyBlinx: 8-14 pw for models and 10-16+ pw for levels (guess). The precondition is a stage
   loader trace (3-6 pw).

## 8. Open questions

1. Where is `V_game` composed into `0xAAD3A0` or the `0x885E20` stack? Is it one point per pass
   (hook 1a) or not (hook 1b)? Do the bone palettes `c[0..47]` and `c[112]` carry it? (M0a)
2. Where is the game's pause or time-stop flag, and is it safe to toggle from a hook? (M0b)
3. Which function builds the projection (`sub_00293B30`, `sub_0035E600` or another)? This blocks
   E10 and Hor+.
4. Where does the cull/LOD test read the frustum? It decides whether free-camera pop can be fixed.
5. Do cutscene cameras and the `sub_0003A780` path (`[0x67EF6C] != 0`) compose the view the same
   way as the normal path? (M3)
6. Does the BLiNX 1 node-tree layout (pyBlinx) hold for the `MDL*`/`M*` sections, and where are
   the UVs, bone indices and weights?
7. Where are the stage object, spawn, collision and trigger tables? Is `GIMCOM`/`G*` the gimmick
   (time-control object) data?
8. Which code reads `edit_char/*.edt`, and what do its 108 bytes mean? (M0c)
