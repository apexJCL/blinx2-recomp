# Design: engine bridge assessment

## Context

What the repos have today (2026-10-30):

- **Game logic** is register-level generated C: 11,686 functions, 139 MB for BLiNX 2 (`src/recomp/gen/`), about the same for BLiNX 1. Ghidra and `func_id` name the libraries; the game's own functions are mostly `sub_XXXXXXXX`.
- **The hardware boundary** is what we understand well: the kernel, the NV2A pushbuffer executor with its D3D11 and Metal backends, the APU with the DSP JIT.
- **Game knowledge**, built for the enhancements:
  - the mod layer (`src/enhance/mod.h`): hooks on guest functions by address, guarded pokes, `on_frame`, `batch_filter` (`mod-connectivity-layer`);
  - BLiNX 2's camera struct `[0x4B271C]`, the view builders, the projection and cull functions, the world freeze flag `0xAF0EF4` (`free-camera`);
  - the HUD sprite queue, the capture JSONL and the mapping flow (`hud-anchors`);
  - draw classification (`nv2a_aspect_place`), LOD (`lod-scale`);
  - texture hashing and owner-built packs; the CLI parses `xpr`, `ipk` and `dds` (`texture-upscale`).

## Three meanings of "move to an engine"

```
  low <------------- how much of the game moves into the engine -------------> high

  [A] Engine as host        [B] Scene lift              [C] Full port
  the recompiled game       game logic stays            assets and logic
  runs inside the engine;   recompiled; the engine      rebuilt as engine
  the engine is window,     redraws the world from      scenes and scripts
  input, audio and RHI      the game's live state

  feasible, little gain     feasible, hard, big gain    not a pipeline
```

- **[A]** is a third GPU backend under "backends agree" (24-32 agent-days for a hand-written one, `linux-native-vulkan`), and it still draws the guest's pre-baked draws: no engine lighting or materials.
- **[B]** is the RTX Remix model: meshes keyed by vertex-buffer hash, materials from texture hash and combiner state, camera and lights from the located structs. Most of it is game-agnostic.
- **[C]** needs the game logic turned into engine scripts. No tool does that from register-level code; it is a matching-decompilation project of years per game. The pipeline can at most replace logic one function at a time through hooks, as `recomp_manual.c` wrappers already do.

## The glue architecture

The game repo and the CLI become the glue. Nothing game-specific ships; the engine project is generated on the owner's machine.

```
                 owner's dump (ISO)
                        |
              [1] read path                    (xbr, offline, local)
                        v
   +------- engine project (Godot, generated, never published) -------+
   |  meshes, textures, stages, materials, a HUD map, mod settings    |
   +------------------------------------------------------------------+
        ^ [3] write path                     | [2] runtime path
        | edits -> guest-format overrides    v live scene, camera, entities
        |                                     |
   +----+-------------------------------------+-----+
   | recompiled game (simulation, logic, bugfix mods) |
   | mod layer: hooks, pokes, located structs         |
   +--------------------------------------------------+
```

- **[1] Read.** Parse the dump's formats and emit glTF, textures and scenes, plus what the dump lacks: normal and roughness maps, upscaled textures, light probes. The texture-pack pipeline is half of this.
- **[2] Runtime.** The engine shows the game's live state: first as an inspector (camera, entities), later as the renderer of the world.
- **[3] Write.** The editor saves changes in the game's own formats, and the runtime overlays them at load (`xbe-section-paging`, guarded pokes). The generated code never notices.

Bugfixes and QoL already have a home in the mod layer. The engine adds an editor for them, not a second mechanism.

## Engine choice

| | Godot | Unreal | Our runtime, engine as GUI only |
|---|---|---|---|
| Fits the C11 toolkit | GDExtension is a C ABI | C++ and UBT | n/a |
| Player builds from own dump | headless import and export, one pinned download for the wizard | full editor install (tens of GB), EULA acceptance | unchanged |
| Licence | MIT | Epic EULA, royalties, redistribution limits | ours |
| macOS, Deck, Linux, Windows | all | macOS second-class | all |
| Rendering ceiling | good (Forward+, SDFGI) | best (Lumen, Nanite) | ours |

**Godot.** Unreal fails the player-build model on size and licence. "Our own runtime with an engine as the GUI" is not an alternative to Godot. It is the first stage of using it.

## Staged delivery

```
 stage 1: Godot = editor and inspector       our exe renders; live link
 stage 2: Godot = optional renderer          scene lift; our exe = simulation
 stage 3: Godot = host                       the exe becomes a GDExtension
```

Each stage ships on its own, and stage 1 already serves level editing and QoL authoring. On 2026-10-30 the user asked for the path of least resistance first, so the spikes go from offline and static to live.

## BLiNX 1 and BLiNX 2

Checked 2026-10-30 from the two XBEs:

- **The same engine family, most likely in-house.**
  - **Sections:** both compile models and maps into the XBE: `MDLPL`, `MDLEN`, `MDLB*`, `MDLR*`, `MAP11..93` in BLiNX 1; `MDLPL`, `MDLEN`, many `MDL*`, `MOT*`, `M11..M121`, `G1..G5`, `GIMCOM` in BLiNX 2.
  - **Middleware:** both link Sofdec (`PSGSFD*` in BLiNX 1, `PSFD*` in BLiNX 2), ADX, DSOUND, XPP and DOLBY.
- **Different data layouts.** BLiNX 1's `MDLPL` (2.9 MB) starts with a table of 32-byte texture names (`z_p_bero`, `z_p_boot2`, ...), which fits the geometry format pyBlinx documents. BLiNX 2's `MDLPL` (0.9 MB) starts directly with what looks like packed float data.
- **Textures:** BLiNX 1 has 2,885 loose `.dds` files. BLiNX 2 packs them into `.ipk`, which the CLI already reads.

So BLiNX 1 is the easier read path (a public format description, loose textures), and BLiNX 2 is the better-mapped runtime (camera, HUD, LOD, cull, freeze).

### S1: one format, one parser

- **One format.** Both games store models and stages as Sega Ninja chunk models and motions as Ninja motions. Each XBE links the same chunk library, recompiled: BLiNX 2 `.text` 0x2E000-0x48000 (408 functions), BLiNX 1 0x8A000-0xA2000 (565). Two sampled pairs, `sub_0003D3C0`/`sub_00090F40` and `sub_000320F0`/`sub_0008F7F0`, are identical except for relocated data addresses and call displacements (21 of 128 and 4 of 64 bytes); the layout order differs in places (the review, 2026-10-30).
- **Two struct differences:**
  - the vertex-list header is 16 bytes in BLiNX 1 and 8 in BLiNX 2 (`add eax,0x10` at 0x8DC97, `add eax,8` at 0x2ED86, checked in both XBEs);
  - texture-name entries are 32 bytes in BLiNX 1 and 36 in BLiNX 2 (the name plus an unknown u32).
- **Data, not format:**
  - the model-tree roots;
  - textures (BLiNX 2 loads `dds\<name>.dds` from `media.ipk`);
  - motions (BLiNX 2 has `MOTPL` and `MOTP0`; BLiNX 1 mixes them into `MDLPL` and `MDLEN`).
- **The object node** (0x34 bytes, walked by BLiNX 2 `sub_000302E0`):
  - +0x00 flags;
  - +0x04 model;
  - +0x08 position;
  - +0x14 rotation (Ninja integer angles);
  - +0x20 scale;
  - +0x2C child, +0x30 sibling.
- **Functions** (BLiNX 2 / BLiNX 1):
  - model draw: `sub_0003B8D0` / `sub_0009CE20`;
  - collision against a model: `sub_0002EC20` / `sub_0008DB40`. Surface types are encoded as material colours.
- **Unknowns:**
  - the stage root tables;
  - vertex flag 0x80 and the `count*6+1` size field;
  - the extra u32 of BLiNX 2 texture names;
  - skin weights and bone binding;
  - which motions go with which models;
  - the collision colour codes;
  - which `G*`/`M*` sections are geometry.

### S2: a BLiNX 1 stage in Godot

- **The stage.** MAP11 (the clock-tower town) goes from the XBE and `media/*.dds` to glTF through a stdlib-only extractor of about 980 lines. Godot 4.7.2 imports it headless with no errors or warnings: 310 meshes, 51,146 triangles, 64 materials, 32 images, the same counts in Blender. These come through right:
  - geometry and UVs;
  - tiling, clamp and flip;
  - double-sided faces and cut-out alpha;
  - the axes: Y up, right-handed, 1:1, no conversion.
- **Characters do not.** Blinx (`MDLPL` 0x0AE2CFC) parses in full (6,193 triangles, right textures), but the skinned glTF comes out with the body parts scattered, whatever the rotation order. Characters share one weighted vertex buffer and draw their polygon lists later (cache, then draw), so a per-node export is wrong. The space the vertices are authored in is still unknown.
- **Lost or not found:**
  - the white plaza surfaces: an environment map at run time, no UVs in the data;
  - lighting and fog: they are in game code;
  - placements of props, enemies, items and the player;
  - collision (tree A);
  - specular, the other blend modes, and material type 24;
  - motions.
- **Pitfalls:**
  - pyBlinx's offsets are for another XBE build, and it misreads angles (as radians), the child and sibling offsets, and UVs (divided by 255). It was read, never run (MIT), and used only for orientation.
  - The vertex chunk `size` field is not the stride.
  - Normals are Xbox packed.
  - Tables must be found by structure, never by another tool's fixed addresses.
- **Estimate for `xbr extract` on BLiNX 1:**
  - static textured stages: about 1 week;
  - a stage that looks played (reflections, props, collision, skinned and animated characters, lighting, fog): 3-4 weeks.
- **Tools:** Godot 4.7.2 is pinned in `xbox-recomp/toolchains/godot-4.7.2/` (`SHA256SUMS`, URL; the official SHA512 matched).

### What S1 and S2 change

- The read path is real for stages in both games. One Ninja chunk parser with two per-game struct switches serves both, and BLiNX 2's textures come through the existing `.ipk` reader. For BLiNX 2, add 3-5 agent-days to S2's parser for static stages, plus 3-5 for skinning and motions.
- The first pitfall is skinned characters, and it hits both games. The game's own draw routine (`sub_0009CE20` / `sub_0003B8D0`) shows how vertices and bones are bound. The running game shows the answer as ground truth (S4 read it at the draw). So characters move to the live spikes, and the static route stays the cheap one for stages.
- Placements, lighting, fog and environment maps are in game code or in tables not found yet. The live link (S4) reads them from the running game instead of parsing them, which is what makes stage 1 the right first stage.

## S4: BLiNX 2 live link into Godot

- **It works, and guest timing does not move.** A throwaway mod wraps the Ninja model draw `sub_0003B8D0` and sends, once per guest frame over non-blocking loopback UDP, the camera and every model draw (about 680 a frame in stage 1 gameplay) to a Godot 4.7.2 viewport. At the same flip the Godot camera and markers match the game frame. The `stage1` Metal golden passes with the link on and Godot live (2 of 2). Spike tip `a263411` on `spike/engine-live-link`, not for merge; files under `runs/engine-bridge/s4/`.
- **Frame times** (Mac, Metal, golden `stage1` env, flips 900-2600, 3 interleaved runs per arm):

  | arm | pacing | flips/s | mean ms | p99 ms | process CPU |
  |---|---|---|---|---|---|
  | off | spin (golden) | 29.97 | 33.36 | 35.09 | n/a |
  | on | spin (golden) | 30.00 | 33.33 | 34.59 | n/a |
  | off | sleep | 30.00 | 33.33 | 34.54 | 38.7% |
  | on | sleep | 30.00 | 33.33 | 34.24 | 39.3% |

  One frame's `publish()` takes 78-86 µs on average (worst 355 µs), about 0.25% of a frame; 2,877-2,893 of about 2,895 frames arrived per run. The A/B finds no cost at its resolution, which is coarse:
  - at the 30 fps lock, flips/s and mean ms only show a cost larger than the frame's headroom;
  - CPU is integer % per 600-flip window (36-42% in both arms), so a difference under about 3 points is invisible;
  - the per-draw `pre_draw` cost (about 680 hooks a frame, each with a 64-byte `memcmp`) was not measured;
  - the "off" arm ran on the hooked build, so the hook slot's cost against stock main is unmeasured, and the golden ran only with the link on.
- **Matrices.** During the scene walk the current Ninja matrix lives in `xmm4..7`; the memory stack slot is stale at the draw (661 of 679 draws differ), so the hook reads registers. Row vectors, translation in row 3, a Y-down right-handed world. Into Godot: `diag(1,-1,-1)` on world and view, a 51.34° vertical FOV, consistent with S2.
- **Skinning is on the CPU in BLiNX 2**, not in vertex programs. The node ordinal at `0x8E4E80` indexes the bone palette at `0xA001D0`. The palette writers `sub_00038B00` and `sub_00039100` are called from the draw, so the hook sees each drawn bone's world matrix and slot. They are also called from `sub_00044220` (0x443BF) and `sub_000BAC40` (0xBAD1C), outside the hooked draw, so "every bone is a drawn node" is not proven (Risk 2). A Godot `Skeleton3D` can be driven from it, given the exported mesh and weights and a key that groups draws per object. This answers S2's open problem from the live side.
- **Pitfalls:**
  - the mod hook API cannot read entry registers (`eax`, `xmm`); the spike read the runtime's internals;
  - the hook needs a regen and a CLI newer than cat's `v0.16.0` pin (main `f38bb96`);
  - sprites, particles and the HUD do not go through the Ninja draw;
  - stage chunks have bounding radii up to about 2000 and need filtering in a view;
  - model pointers identify a model only within one stage load, so mapping draws to exported assets needs a load-time table;
  - open UDP on loopback; a feature wants a shared-memory ring or an authenticated socket;
  - `live_link.c` is compiled out on `_WIN32`, so nothing ran on the primary gate host; Winsock, Proton loopback (a Wine game to a native Godot) and the no-receiver case are untested.
- **Estimate for a real stage-1 link:**

  | piece | estimate |
  |---|---|
  | mod API exposing entry registers, with a ctest | 1-2 days |
  | toolkit transport, versioned schema, `recomp_env` row, ctest | 3-4 days |
  | per-game descriptor | 1-2 days per game |
  | Winsock port, Windows receiver, Proton loopback | 2-3 days |
  | Godot receiver with mesh mapping and skeletons | 1-2 weeks |

## Recommendation

Stage 1, in three slices, each its own change and shippable alone:

| slice | what the owner gets | games | estimate |
|---|---|---|---|
| 1a `xbr extract` | the game's stages as a Godot project generated from their dump: one Ninja chunk parser (S1, S2), textures from `.dds` and `.ipk`, glTF out, `godot --headless --import` from the pinned Godot | BLiNX 1, then BLiNX 2 | about 1 week, plus 3-5 agent-days for BLiNX 2 |
| 1b live link | the running game shows its camera and every model in that project live | BLiNX 2, then BLiNX 1 | about 1.5-2 weeks, Windows included |
| 1c live meshes | 1b draws the exported meshes, with characters posed through the bone palette | BLiNX 2 | about 3 weeks: 2 for the receiver, plus BLiNX 2 skinning and motions from the static parse (3-5 agent-days) and the load-time model-pointer table |

- **1a first:** it is offline, touches neither the toolkit nor what the game executes (no goldens), and every later slice and the write path need its parser and the asset keys.
  - **Order of games:** BLiNX 1 then BLiNX 2 departs from the decision "BLiNX 2 first" below. BLiNX 1 has the public format notes, loose `.dds` and S2's working extractor; BLiNX 2 follows in the same change. The go on 1a asks the user about this.
  - **Where the code goes:** the Ninja parser is game-agnostic CLI code; the per-game switches (vertex header 16 or 8, texture entry 32 or 36), the section names and the roots go in each `game.toml`.
  - **Gates:** the CLI's pytest and ruff. The wizard gets Godot in `pins.json` with its sha256 and download size only if it offers the project.
- **1b next:** a toolkit enhancement under `XBOXRECOMP_ENHANCE`, default off, fork-only. It reads guest state and draws nothing, so D3D11 and Metal need no mirroring.
  - **It still changes what the game executes:** `hook_functions` regenerates gen for every build, link on or off.
  - **Gates:**
    - the full golden matrix (Metal, D3D11 under Proton, native Windows), link off and on;
    - a slot-only perf A/B against stock main;
    - a per-draw hook-cost counter, with runs on the Deck and Windows;
    - the CLI pin move past `f38bb96`, with `notes/build-all.sh`.
- **1c entry tasks:**
  - hook `sub_00044220` and `sub_000BAC40` too, or prove they do not run in gameplay;
  - an early go/no-go: do static meshes placed at live transforms agree with the game frame?
- **Not yet:** stage 2 (Godot as the renderer) and the write path. Lighting, fog, environment maps, placements and collision come after 1c, from the live side first.
- **S3 is dropped.** Its questions were static versus run-time agreement and posed characters. S4 answered most of the second (CPU skinning, a visible palette; the two other palette callers stay open) and 1c's go/no-go answers the first.

## Risks

1. **BLiNX 2 format reverse-engineering** decides how much of [1] and [3] works. The live hook mitigates it: the transforms, model pointers and bone matrices it reads are ground truth for a static parse, checked by 1c's go/no-go.
2. **Skinning and motion (`MOT*`).** BLiNX 2 skins on the CPU (S4), so the live path reads the bone palette. Its writers are also called from `sub_00044220` and `sub_000BAC40`, outside the hooked draw, so some skinned draws may bypass the hook. The static path still needs a bind pose, the weights and the motion-to-model binding.
3. **Write-back safety.** Edited stages must keep the game's invariants: collision, the time-control record buffers, the stage scripts in `M*`/`G*`. They need a validator and goldens on edited stages.
4. **Materials.** NV2A register combiners map to engine materials by heuristics, per game.
5. **The live link's cost.** It must not perturb guest timing. It runs code on every model draw (about 680 a frame) and sends once a frame, never blocking the guest; S4 measured the send, not the per-draw hook.
6. **Legal.** The generated project, its `.godot/imported` cache and any Godot export (`.pck`) are bundles of game assets. The generator never runs an export. Shareable edits (mods, levels) are deltas against the dump, never copies of extracted assets. An inbound channel for the write path needs authentication before it exists.

## Spikes, by least resistance

| Spike | Path | Game | Needs | Tracker |
|---|---|---|---|---|
| S2 stage to glTF, opened in Godot | read | BLiNX 1 | pyBlinx format, the dump, Godot headless | The tracker item |
| S1 format lineage | read, write | both | the XBEs, Ghidra, generated code | The tracker item |
| S4 live link: camera and drawn models into a Godot viewport | runtime (stage 1) | BLiNX 2 | a throwaway mod build in a worktree | The tracker item |
| S3 captured frame to glTF | runtime (stage 2) | BLiNX 2 | a draw capture on the Metal path | dropped (Recommendation) |

S1 and S2 were offline and read-only and ran in parallel. S4 needed a build and a game run, so it came after.

## Decisions

- Godot, staged as above (the user, 2026-10-30: "path of least resistance first").
- The engine project is generated locally from the owner's dump by a bootstrap; the project is the glue (the user, 2026-10-30).
- BLiNX 2 first, BLiNX 1 alongside (the user, 2026-10-30). For slice 1a, BLiNX 1 then BLiNX 2 in the same change (the user, 2026-10-30, after the review).
- Stage 1 starts with slice 1a, `xbr extract` (the user, 2026-10-30).
- Settings for a later stage go through `recomp_env` with `docs/env.md` rows and default off. A later renderer stage must say how D3D11 and Metal stay in agreement. This assessment adds neither.
