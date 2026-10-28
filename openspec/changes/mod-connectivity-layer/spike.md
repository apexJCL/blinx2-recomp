# Spike: widescreen mods for the four games

Date: 2026-10-22. Agent `widescreen-mods`, branch `spike/widescreen-mods`.

The question (the user, 2026-10-22): find the 16:9 mods for BLiNX 2, Burnout 3,
JSRF and SSX 3, ideally for the original Xbox releases. Retrieve them, see how
they work, and make the approach as game-agnostic as possible. Game-specific
code goes through the mod layer. Whatever is game-agnostic belongs to the
toolkit's mod connectivity layer. The trigger is the tracker item: under Hor+, Burnout
3's crash-cam letterbox bars cover only the 4:3 centre.

A second pass (the user, same day: "Probably look for mods in other platforms
as well") added every other release of the four games, their sibling games,
the emulators' own widescreen hacks and patch formats, and RenderWare
(sections 2 to 4).

The downloads were kept outside this repo and read as text; none was run.
No mod file, patch file or GPL code is copied here. This file records the
technique, the key addresses and values, the source and the licence. Where a
patch has many records, it gives the technique and the values that matter to
us, and links the file.

## 1. The four games

### 1.1 Summary

| Game | Xbox patch or mod | Other platforms | Native option on Xbox |
|---|---|---|---|
| BLiNX 2 | 720p only: Jay's Magic Patches (`.JMP`), by Silverrock and icup321 (section 1.4). No widescreen patch | none (Xbox exclusive) | none |
| Burnout 3 | none | PS2: pnach codes in every region (Aero_, PeterDelta, ports by Arapapa); the Widescreen Fixes Pack PCSX2-Fork plugin | yes: "Aspect Ratio 4:3 / 16:9", anamorphic |
| JSRF | **two widescreen `.JMP` patches**: icup321 (NTSC, matches our XBE) and Esppiral (PAL); a 720p patch by SPPV (section 1.4) | none (the 2012 JSR HD is a different game and is Hor+) | none |
| SSX 3 | koenhendriks SSX3-recomp (PAL), a recompilation, not an XBE patch | PS2: pnach (Virjoinga: triple-screen, 21:9 and 32:9 values). GameCube: the game's own Anamorphic option in Dolphin | yes: "Widescreen: Off / 16:9 / Anamorphic" |

The first pass reported no Xbox patch for any of the four. That was wrong for
JSRF: the second pass found Jay's Patch Hub, which collects Xbox XBE patches.

Searched, nothing found for these four:
- xemu and Cxbx-Reloaded have no patch system of their own (section 3).
  XPSemu (xemu on PS5) applies the same `.JMP` files.
- JSRF: a decompilation on Codeberg (about 30% per multiplayer.it), with no
  widescreen work. WSGF lists only the 2012 HD release.
- ThirteenAG's Widescreen Fixes Pack (MIT) has no SSX, JSR or BLiNX entry.
- Jay's Patch Hub lists Burnout 3 (4541005B: JPN v4, PAL v2 and v3, USA v1)
  and SSX 3 (4541003C) with no patch.

### 1.2 Burnout 3

| Mod | Source | Licence | Platform | Technique and key values | Carries over |
|---|---|---|---|---|---|
| `[Widescreen 16:9]` by Aero_ | github.com/PCSX2/pcsx2_patches, `patches/SLUS-21050_BEBF8793.pnach` at tree 8e658bc | none stated; the README credits the patches to their authors | PS2 NTSC-U | Family B (section 5): the game's own wide-camera flag, then a 3/4 squeeze of all 2D, with each full-screen element widened back. Key values: the flag byte 0x665ECD = 1; FOV 1.3333 and aspect 1.7778 (0x4E0A38, 0x4E0C70); HUD width 0.75/640. **The crash-cam borders are moved from x 0, w 640 to x -107.5, w 853.33** (0x4CA638 to 0x4CA660). The same pair is applied to the crash list backing, the full-screen borders, the loading and replay bars, and the per-player HUD render target. It also fixes the aspect of the "Globe" view (0x4E0C3C, 0x4E0A94), a second consumer of the aspect besides the race camera. The other records (HUD offsets, corner anchors, menus) follow the same scheme; see the file | technique yes; addresses no (MIPS build) |
| the same patch, ported by Arapapa | same repo: `SLKA-25206`, `SLPM-65719` | as above | PS2 Korea, Japan | Aero_'s patch at the other builds' addresses | technique |
| `[Widescreen 16:9]` by PeterDelta | same repo: `SLES-52584_75BECC18.pnach` (PAL), `SLAJ-25053` (NTSC-A) | as above | PS2 PAL, Asia | FOV only: the flag byte, then FOV 1.3333 and aspect 1.7778. The 2D layer is left alone. PAL also has a 480p patch by felixthecat1970 | technique yes |
| Burnout3.PCSX2F.WidescreenFix | github.com/ThirteenAG/WidescreenFixesPack, `source/Burnout3.PCSX2F.WidescreenFix/main.cpp` | MIT | PS2 (PCSX2-Fork plugin API) | Aero_'s layout, computed for any aspect and applied through mid-function hooks rather than code caves: `width = 480 * aspect`, `hudScale = (4/3) / aspect`, `offset = (640 - width) / 2`, `hudOrigin = 320 * (1 - hudScale)`, anchors `±(width - 640) / 1155`. It selects the native wide camera with one instruction (0x228194 `li v0, 1`). It re-applies the HUD values after the game's two HUD reset functions (pointer swaps at 0x4DD840, 0x4DD9E4). 11 sites load `width` in place of 640, and 13 store `offset` or `normalizedOrigin` into the draw call's stack frame. It validates the sites against the CRC first, and disables itself on a mismatch | technique yes |
| the game's own option | `default.xbe` | (the game) | Xbox | anamorphic: a 16:9 projection rendered into 640x480. The byte 0x4D617D (the video block 0x4D6170 + 0xD) is set from `XGetVideoFlags & 1` in `sub_0003C8A0`. `sub_0002F380` picks aspect 16/9 (0x3B18EC) with factor 1.2 (0x3B1768), against 4/3 (0x3B181C) and 1.0 (0x3B168C), and stores them at [esi+0x104] and [esi+0x100] | native-widescreen already uses it |

Notes:
- The PS2 flag byte is the same switch as the Xbox byte 0x4D617D. Every PS2
  patch starts from the game's own wide camera. The full patches fix only what
  the game left at 4:3: the 2D layer.
- On PS2 the patches write FOV 1.3333, where the game's own Xbox table has 1.2.
  A likely reading: 1.2 makes the Xbox native mode partly Vert- (about 10% less
  vertical FOV than 4:3), and 1.3333 is pure Hor+. This is not verified.
  native-widescreen task 1.3 (the b3 runtime confirmation) should check it on
  a fixed scene, and check the Globe view too.
- On PS2 the crash-cam bars are drawn at x = 0, w = 640. Moving them to
  x = -107.5, w = 853.33 cancels the 3/4 squeeze that the HUD width applies to
  every 2D element: 853.33 * 0.75 = 640, which is the whole 16:9 display.
- Xbox candidates for the same rects (static, not confirmed at run time):
  - `.data` 0x406A70 and 0x4088D0 each hold {0, 384, 640, 32};
  - 0x406B50 holds {0, 64, 640, 352}, a view band between bars at y 64 and 416;
  - the readers are `sub_000BEC10` (from `sub_000717B0`), `sub_000BFCB0`
    (from `sub_00071000`, `sub_000717B0`, `sub_00080BD0`) and `sub_000EE710`
    (from `sub_0008D790`).
  - The Xbox's 640.0 constant at 0x3B1F00 has 656 references, so the bar draw
    itself must be pinned at run time, not by grep (section 7).

### 1.3 SSX 3

| Mod | Source | Licence | Platform | Technique and key values | Carries over |
|---|---|---|---|---|---|
| "Aspect Ratio" sections by Virjoinga | pcsx2_patches `SLUS-20772_08FFF00D.pnach` | none stated | PS2 NTSC-U | Family B without the 2D fixes: two projection-scale floats, the picture stretched at present (`gsaspectratio=Stretch`). The sections are triple-screen setups ("3xStretch", "3x15:9", "3x16:10", "3x4:3"), plus 21:9 and 32:9. **There is no plain 16:9 entry.** The floats are 0x622600 (horizontal) and 0x622604 (vertical). The value is (4/3) / aspect: stock 1.0, 16:9 0.75. 0x3EAAAAAB (0.3333) is the 3x4:3 value | technique yes |
| Meridian's intro skip and Metro slowdown fix | same file; PAL `SLES-51697` has only these | none stated | PS2 | speed and skip codes | not widescreen |
| SSX3-recomp | github.com/koenhendriks/SSX3-recomp at 94e5325 (2026-10-16): `src/ssx3_overrides.c`, `src/vk/vkr.c`, `xbox.vert` | GPL-2.0 (studied, not copied) | Xbox PAL, a static recompilation (no XBE patch) | Family B in a recomp. It wraps D3DX `PerspectiveFovLH` and widens its aspect argument. It widens the render target, and squeezes 2D in the vertex shader. The wrapper is on PAL 0x0024EA13 (stdcall: out, fovy, aspect, zn, zf; called only from `sub_001EAB40`). While in game, it multiplies the aspect at [esp+12] by `target * 0.75`. "In game" is an app-state vtable test (`MEM32(0x003A930C)`, then the current state, then vtable 0x00299D7C). Menus, loading and movies stay 4:3 and are pillarboxed (`squeeze_all`). The renderer scales the target width by `aspect * 0.75`. The shader narrows each vertex with `w == 1` and `abs(ndc.x) < 0.999` by 1/f, so full-width 2D keeps its edges. `RECOMP_WIDESCREEN` is `auto` (follows the window) or `W:H`. The lens-flare test `sub_001F8760` (LensFX `sub_00152A70`) is touched for occlusion | technique yes; the PAL addresses map to our USA build below |
| the game's own option | Xbox `default.xbe`, and the GameCube release in Dolphin | (the game) | Xbox, GameCube | anamorphic into 640x480. The settings word 0x33925C, bits 20-21 (Anamorphic = 0x200000), setter `sub_0008E0D0`, menu `sub_0008F4C0` | native-widescreen |

Our SSX 3 USA build has the same projection point:
- `sub_00249633` (the D3DX section) is `D3DXMatrixPerspectiveFovLH`
  (`fsincos`, `ret 0x14`). From esp after the frame push: out +8, fovy +0xC,
  aspect +0x10, zn +0x14, zf +0x18. The only caller is `sub_001BD600` at
  0x001BD760.
- `sub_001BD600` takes the aspect from the viewport ([obj+0x13B0]+0x48/+0x4C).
  It scales fovy by [0x27DA68] when [esi+0x274] == 2, and tests
  [0x30A710] == 2 after the call.
- `sub_0024959F` looks like the RH variant and has no callers.
- So koenhendriks' PAL hook maps to `sub_00249633` (aspect at entry [esp+12])
  or to its one call site in `sub_001BD600`.

### 1.4 BLiNX 2 and JSRF

The Xbox patches are in Jay's Magic Patch format (`.JMP`), collected at
jayxbox.com's Patch Hub and in github.com/JayYardley/Xbox-Magic-Patches-by-Jay
(no licence file; the README says each patch is based on its credited
author's work). A `.JMP` file has seven header lines: system, title, region,
`version=<title id> (<code>) {<CRC32>}` for verification, author and notes.
Then come records, each under a `#` comment line, of three kinds:
- **search and replace**: a hex string to find, and its same-length
  replacement. The first match is replaced, so a record works on any build
  that contains the bytes;
- **offset**: `0x<file offset>:<hex>`;
- **append**.

| Game | Patch | Technique and key values | Carries over |
|---|---|---|---|
| JSRF | `{Widescreen} (NTSC) [icup321]`, `version=5345000A (SE-010) {3A4A7CC8}` | One search-and-replace record. It changes the immediate `mov edx, 0x3F800000` (1.0) to 0x3F400000 (0.75), in the look-at builder `sub_001BAF70` (section MMATRIX, fastcall: eye in ecx, target in edx, 31 callers). The pattern occurs twice in our XBE (file offsets 0x1A980E and 0x1A9883). Only the first match is replaced: the immediate at VA 0x001BB0B3, which one of the builder's four branches (the one at 0x001BB0AE) stores into m00. The view's x axis is scaled by 0.75 in that branch: Family B, an anamorphic squeeze in the view matrix, with the picture stretched by the TV | technique only. The value is an instruction immediate in `.text`, so a poke cannot reach it in a recomp. A post hook on `sub_001BAF70` that scales the built matrix's x column would be the equivalent, and needs ecx in the hook ABI. Our Hor+ already covers JSRF; no port is planned |
| JSRF | `{Widescreen} (PAL) [Esppiral]`, `49470018 (IG-024) {0491D477}`. Notes: "Some graphical issues" | v1: the same 1.0 to 0.75 immediate, found with a longer pattern. v2 (an alternative group, marked `[-]`): four 12-byte records that change one pointer-like word (0x8C32F9EC to 0x8CFF8198) in tables | technique; the patch itself says it is imperfect |
| JSRF | `{720p} (NTSC) [SPPV]` | about 260 offset records: the video mode table, 640x480 integers to 1280x720, and window views | no: resolution, which our render scale covers |
| BLiNX 2 | `{720p} (GLOBAL)` by Silverrock and by icup321, `4D530065 (MS-101) {8D2F7F89}` | offset records: the RAM-limit header bit, the video mode table at 0x2E0824, and 640/480 immediates to 1280/720. Silverrock's notes: "Menus/HUD elements, frustrum culling and an FOV edit would do wonders here" | no: resolution only. The notes name exactly what our Hor+ and the cull wrapper already do |
| BLiNX 2 | `{128mb D3D} (US_CANADA) [iroiry]` | search and replace on the memory-cap code and the D3D allocation constants | no: memory, not display |
| BLiNX 2 | none | Projection point `sub_00042AE0` -> `sub_0029EEF2`, aspect -(640/480). Hor+ already covers it. `cat/src/recomp_manual.c` widens the cull (`sub_0003B180`) and the far-sea fan (`sub_00215A40`) for the main view: hand-written mod-class code that already lives in the title | - |
| JSRF | (projection) | Not pinned. The only `fsincos` in `.text` is `sub_0014C910` (from `sub_0014CAA0`), which is not a projection builder. JSRF has no D3DX section. The icup321 patch points to `sub_001BAF70` as the view builder | - |

## 2. Other releases and sibling games

"Patch" means a widescreen or aspect patch; 60 fps, resolution and skip
patches are noted only where they show a pattern.

| Platform and source | Game | Found |
|---|---|---|
| PS2, pcsx2_patches (tree 8e658bc, no licence file) | Burnout 3, every region | section 1.2: NTSC-U Aero_; Korea and Japan Arapapa's ports of Aero_; PAL and NTSC-A PeterDelta, FOV only |
| | Burnout Revenge, SLUS-21242 by SuperType1/remco | Force the game's own 16:9 by a NOP at 0x1398C0, the HUD width as a `lui` immediate (0x3A9D...), and per-element HUD offsets. A separate 21:9 section; the notes say to enable only one of the two. SLES-53506/53507, SLKA-25304 and SLPM-66108 by Dread and Arapapa |
| | Burnout Dominator, SLUS-21596 by SuperType1/remco | "Force 16:9" (0x1A2798 = 0), an FOV `lui` at 0x1F60FC, the HUD width at 0x22BE50, per-element HUD offsets. SLES-54627 and SLPM-66739 too |
| | SSX 3 | section 1.3 |
| | SSX On Tour, SLES-53552 by PeterDelta | "Enable native widescreen": the word at 0x5ADF80 = 2, the same value 2 as SSX 3's Anamorphic. SLUS-21278 has only 60 fps (MelA) |
| | SSX Tricky, SSX (2000), Burnout 2 | none. The PCSX2 wiki lists SSX Tricky as natively widescreen (its own anamorphic option) |
| GameCube, Dolphin GameSettings (sha cf5cb7ef, GPL-2.0-or-later) and the Dolphin wiki | SSX 3 (GXBE69, GXBP69, GXBJ13) | no INI. The wiki says to use the game's 16:9 / Anamorphic option with aspect Auto, not the hack. Known problems: the sun shows through obstacles (fixed by turning Skip EFB Access off), and VP6 movies |
| | Burnout 2 (GB4E51, GB4P51) | the game's own 16:9 option (use Force 16:9; the wiki advises against the hack), and a "Pixel aspect" Gecko code by pneumatic (the VI width) |
| | Burnout (GBOP51), SSX Tricky (GST*) | Action Replay codes and video settings only, no widescreen |
| GBA | SSX 3 | not relevant (a different 2D game on a fixed screen) |
| PS3 | Burnout 3 | no PS2 Classics or PS3 re-release exists |
| Xbox, Jay's Patch Hub | BLiNX: The Time Sweeper (4D530013) | `{Widescreen} (Multi) [Jay]`, combining earlier patches by Esppiral and Nemesis2000: one search-and-replace of the float -1.3333 (0xBFAAAAAB) with -1.7778 (0xBFE38E38). The notes say the value occurs exactly once in every version. Family B: the projection's aspect constant, with the picture stretched by the TV. BLiNX 2 uses the same aspect, -(640/480), but the bytes occur 145 times in its XBE, so the patch does not carry over |
| | Burnout 2 (41430019) | 720p (author unknown) and Misc (Jao12345); no widescreen |
| | Burnout Revenge (45410076), SSX Tricky, SSX On Tour (45410082) | no patch (SSX Tricky has a 128 MB D3D patch) |
| Xbox 360, xenia-canary/game-patches (no licence file) | Burnout Revenge (454107DC) | bloom, blur and motion-blur switches by boma; no widescreen (the game is 16:9 on 360) |
| | SSX (2012, 4541096D) | 60 fps and resolution patches by Margen67 |
| | JSR HD, BLiNX, other Burnout and SSX | none |
| PS3, RPCS3 `patch.yml` (the rpcs3.net patch API v1.2) | Burnout Paradise (BLUS30061) | 60 fps, skip-intro and motion-blur patches; no widescreen (16:9 native) |
| | SSX (2012) | resolution patches |
| | JSR HD | none (NPUB30588 is another game) |
| Dreamcast, Flycast `core/cheats.cpp` (GPL-2.0, sha fa9d39a3) | Jet Set Radio: MK-51058 (USA), MK-5105850 (PAL), HDR-0078 (Japan, De La) | built-in widescreen cheats: two floats each, 480.0 and 0.75 (USA at 0x32E0FC and 0x32E12C; PAL 0x32F9EC and 0x32F9BC; Japan 0x327A8C and 0x327A5C). Family B: the picture is stretched |
| PC, PS3, 360 | Jet Set Radio (2012 HD) | natively 16:9 Hor+; nothing to patch |
| PSP, PPSSPP | SSX On Tour, Burnout Legends, Burnout Dominator | the PSP screen is 16:9 (480x272) and these games render to it natively; no widescreen patch exists or is needed |

What the siblings add:
- **One Criterion recipe.** Burnout 3, Revenge and Dominator on PS2 are fixed
  the same way: turn on the game's own 16:9 flag, then set the HUD width and
  move the HUD anchors. On Xbox the flag is set by the dashboard bit, which
  native-widescreen already answers. The rest is 2D placement, which our
  layer already does generically.
- **One EA flag value.** SSX On Tour's native mode is the value 2 in one word,
  the same as SSX 3's Anamorphic. A probe of the form "word == 2" fits both.
- **Family B everywhere else.** Every patch for a game without a native mode
  (BLiNX 1, JSR on Dreamcast, JSRF on Xbox, SSX 3 on PS2) widens or squeezes
  the projection and lets the TV stretch the picture. None of them fixes 2D
  or full-screen effects; the JSRF PAL patch says "some graphical issues".

## 3. Emulator widescreen hacks and patch formats

| Emulator | Mechanism | Key | What we take |
|---|---|---|---|
| Dolphin (GPL-2.0-or-later) | **Widescreen hack:** `VertexShaderManager::LoadProjectionMatrix` scales the raw projection's [0] and [1] by `fAspectRatioHackW`, for perspective projections only. The GameCube XF projection register carries a type bit (perspective or orthographic), so 2D is never touched. **Anamorphic detection** (`Widescreen.cpp`, `IsAnamorphicProjection`): per flush, the ratio of the projection's aspect to the viewport's is compared with the widescreen and standard ratios within a slop; vertex counts are kept separately for perspective and orthographic draws, and a mode change needs a threshold. The game INI's `suggested_aspect_mode` overrides it. **Gecko F6 codes** search for an instruction pattern and patch relative to the match, so one code works across regions (for example `GSO.ini`, Sonic Mega Collection, "16:9 Widescreen Region Free") | game ID, INI | NV2A vertex programs have no projection-type bit, which is why we pad the target and classify 2D instead of scaling projections. The detection heuristic is a possible generic `wide` probe for native mode (design D8, open question). F6 codes are signature patches: our `sig:` resolution at analyze time does the same |
| PCSX2 (pnach) | `patch=1,EE,<addr>,<type>,<value>` records under `[section]` headers, with `description=` and `author=` lines; one file per serial and CRC; sections are off until the player enables them | serial plus ELF CRC | the CRC key; one section per choice, with "enable only one" in the text |
| Flycast (GPL-2.0) | A built-in table, `WidescreenCheat {game_id, area_or_version, addresses[16], values[16], origValues[16]}`, about 270 entries. `apply()` runs every frame and writes a value only when the current value differs and either `origValues` is 0 or the current value equals `origValues`. Gated by `config::WidescreenGameHacks`. A separate "Widescreen" render option draws geometry outside 4:3, which is Hor+-like | disc product ID plus area or version | **the expected-original guard on held pokes** (design D4) |
| Xenia (game-patches, no licence file) | TOML: `title_name`, `title_id`, `hash` (the XEX module hash), then `[[patch]]` entries with name, desc, author, `is_enabled = false`, and typed writes (`be8`, `be16`, `be32`, `f32`, `array`) | module hash | typed values in TOML; off by default |
| RPCS3 (`patch.yml`) | YAML keyed by the executable hash (`PPU-<sha1>`), then the patch name, `Games` (serial to versions), Author, Notes, `Patch Version`, `Group` (mutually exclusive patches), `Configurable Values` (for example an aspect choice), typed writes and reusable `Anchors`. The Army of TWO "Ultrawide" notes state our own Hor+ policy: vertical FOV unchanged, HUD and videos centred, full-screen fades cover the whole screen | executable hash | `Group` and `Configurable Values` map to one `cfg_choice` key per mod |
| Jay's Magic Patcher (xemu, XPSemu, real hardware) | `.JMP`, section 1.4: search-and-replace, offset and append records; an optional CRC32 in the header; it patches the XBE file once, before boot | title ID plus CRC32 | the same signature idea; static only |
| xemu, Cxbx-Reloaded | no patch system; users patch the XBE with `.JMP` or by hand | - | - |

Lessons for the layer:
1. **Every system keys its patches to the exact executable.** PCSX2 uses the
   ELF CRC, Xenia the XEX hash, RPCS3 the PPU hash, Flycast the product ID and
   version, `.JMP` and WFP a CRC32. Our `[xbe]` sha256 and section-hash pins
   (design D4) are the same rule.
2. **Off by default.** pnach sections, Xenia's `is_enabled = false` and
   Flycast's option gate all agree with design D9.
3. **Typed values and exclusive choices.** Xenia and RPCS3 write typed values;
   RPCS3's `Group` and the "enable only one" notes in the 16:9 and 21:9 pnach
   pairs are one choice key. A mod offers them as one `cfg_choice`, not as
   separate switches.
4. **A held poke needs an expected value.** Flycast writes a held value only
   while the location still holds the game's original. That keeps a poke from
   overwriting the same address after the game reuses it for something else.
   `poke` gains an optional expected value (design D4).
5. **Signatures are resolved once.** Dolphin's F6 codes and `.JMP`
   search-and-replace find their site by bytes, so one record serves several
   builds. We resolve `sig:` entries at analyze time, against the pinned XBE,
   so the runtime needs no `find()` (design D4).
6. **Code patches do not carry over to a recomp.** Most Xbox and PS2 patches
   change an instruction (an immediate, a NOP, a branch). Our generated code
   is static C, so the equivalent is a VA hook on the function, never a poke
   into `.text` (design D3, D4).
7. **Nobody fixes 2D generically.** Dolphin's hack leaves orthographic draws
   alone; every other system leaves 2D to per-element pokes or to the
   picture stretch. Our GPU-level classifier stays the layer's main value.

## 4. RenderWare

| Game | Engine | Evidence |
|---|---|---|
| Burnout 3 | RenderWare 3.6, linked statically | `default.xbe` holds the `$Id: //RenderWare/RW36Active/rwsdk/...` strings, including `src/bacamera.c#2`, `world/pipe/p2/xbox/xblights.c` and the p2 pipeline files |
| SSX 3 | EA's own engine on D3D8 and D3DX8 | no RenderWare strings; `cXBoxGraphicsMan`, `@D3DX8` |
| JSRF | Smilebit's own, D3D8 without D3DX | no RenderWare strings |
| BLiNX 2 | Artoon's own, D3D8 and D3DX8 | no RenderWare strings |

The GTA III, Vice City and San Andreas PC fixes (ThirteenAG's
WidescreenFixesPack, MIT; `source/GTA3.WidescreenFix/` `Draw.ixx` and
`Camera.ixx`) do not patch RenderWare. They work one level up, in the game:
- an inline hook on `CDraw::SetFOV`, which the game later turns into the RW
  view window;
- mid-function hooks in `CCamera::CalculateDerivedValues` (the frustum used
  for culling) that redirect the code's float operands to variables the fix
  owns;
- every site found by a byte pattern with wildcards at load time.

So the lesson for us is not "hook `RwCameraSetViewWindow`". It is the same
split we already have: the game's FOV or aspect call (a VA hook) and the
game's cull (a VA hook), both found by signature.

For Burnout 3, `RwCameraSetViewWindow` is a candidate generic hook. It takes
the camera and a view window (the half-width and half-height of the view at
distance 1). It stores both and their reciprocals in the camera. Every RW 3.x
title calls it, and its code is the same library code across RW 3.6 titles,
so a signature for it would serve any RW title we recompile. It is not
located in b3 yet: the `$Id` strings are not referenced from code, so the
function has to be found by its shape (two stores into the camera, two
reciprocals, the frustum update call). Under Hor+ the layer does not need it,
since the game's own projection already fills the padded target. It matters
only for a Family B squeeze (design D6) or a cull fix in an RW title. It is
recorded as a later task (tasks 7.4), not built.

## 5. Two families of technique

**Family A, padded Hor+ (ours, the Flycast render option, and ThirteenAG's
usual PC fixes).**
- The render target and the viewport mapping are widened.
- The projection keeps its vertical FOV, so the horizontal FOV grows.
- The HUD stays at 4:3 in the centre (enhancements-hor-plus H6).
- Full-screen 2D (fades, post quads, bars) is stretched.
- It is done entirely in the layer, with no game knowledge, except the cull
  fixes and the classifier gaps.

**Family B, anamorphic plus a 2D squeeze (the PS2 codes, the Xbox `.JMP`
patches, the Flycast cheats, the WFP plugin, SSX3-recomp).**
- The game's projection aspect is widened: its own flag where there is one,
  otherwise an aspect constant, a view-matrix scale or a wrapper on the
  projection builder.
- The game renders into its usual 640 guest columns, and the picture is
  stretched to 16:9 at present (or by the TV).
- In the full patches, every 2D element is squeezed by 3/4 about the centre,
  or its anchors are moved out to the edges, so it keeps its shape after the
  stretch. Most patches skip this and leave the 2D stretched.
- Full-screen 2D (bars, backdrops, the crash-cam list backing) is widened
  again by 4/3 so it still reaches the edges after the squeeze. In the PS2
  codes these are the -107.5 / 853.33 pairs. SSX3-recomp does it
  generically: full-width w == 1 vertices are not squeezed.
- Menus, loading screens and movies stay 4:3 and are pillarboxed, by game
  state.

What both families need:
1. the aspect value, and the pad in guest units (107 at 16:9 on a 640 target);
2. a projection or aspect hook;
3. a 2D classifier;
4. a full-screen element rule (bars, backdrops, fades);
5. a game-state probe (in game against menus);
6. a HUD policy;
7. a present stretch (Family B) or a widened target (Family A).

## 6. Patterns, layer against mod

| Pattern | Seen in | Owner | Why |
|---|---|---|---|
| Aspect value, ratio and the pad in guest units | all | **layer** | one value per run (`display.aspect` or `display.widescreen`); every mod and rule reads the same number |
| Wrap a projection or view builder by guest VA and scale its aspect argument or result | SSX3-recomp (D3DX PerspectiveFovLH); the JSRF `.JMP` (look-at builder); the PS2 aspect floats | **layer** mechanism (a VA hook with typed access to the arguments, ecx and edx, and the return; a stock D3DX signature), **mod** data (which VA, when) | D3DX `PerspectiveFovLH` is XDK library code, so the layer can find it by signature (to be checked across XDK versions, tasks 5.5); the condition (in game only) is the game's |
| Select the game's own wide camera (a flag) | WFP (0x228194), Aero_ (0x665ECD), Revenge and Dominator "Force 16:9", SSX On Tour (word = 2), Xbox 0x4D617D | **layer** (native-widescreen's dashboard bit and probe) | the toolkit already answers `XGetVideoFlags`; the per-game part is one probe row |
| Cull and frustum widening | BLiNX 2 `sub_0003B180`, `sub_00215A40`; GTA `CalculateDerivedValues` | **mod** (game VA), with a layer helper for the factor | the cull test's shape is the game's own |
| Game-state probe: in game, menu, movie | SSX3-recomp vtable test; native-widescreen D4 | **mod** data through a **layer** API (`state probe`: address, mask, value, or a callback) | the layer only needs a boolean per flip |
| Automatic "wide" detection | Dolphin's projection-to-viewport heuristic | **layer**, later and only if a game has no probe | an open question (design) |
| 2D classification and placement | Hor+ `nv2a_aspect_place`; SSX3-recomp `w == 1` | **layer** | game-agnostic by construction |
| Full-screen element widening (bars, backdrops, list backings) | Aero_ and WFP -107.5 / 853.33; SSX3-recomp's full-width exception | **layer** generic rules (full-width 2D is never squeezed or centred), **mod** override data where the rules miss (`[aspect.program]`, `[aspect.texture]`) | the PS2 authors needed per-element pokes only because they had no GPU-level classifier |
| HUD anchors moved to the edges | Aero_ corner anchors, WFP `leftAnchor`/`rightAnchor`, Revenge and Dominator HUD offsets | **mod** (opt-in, per game) | our policy keeps the HUD at 4:3 (H6); a mod may offer edge anchoring as an option |
| HUD squeeze | Aero_ HUD width 0.75/640, WFP `hudScale` | **layer** under Family B (a placement that maps 0..640 to the centre 4:3 of the wide target, which is what Hor+ CENTRE already is) | Hor+ CENTRE and the Family B squeeze give the same pixels |
| Data pokes by address | all PS2 codes, the BLiNX 1 `.JMP`, the Flycast cheats | **layer** poke API (address, an optional expected value, checked against the pinned XBE), **mod** data | the address is fixed by the pin; a signature is resolved at analyze time |
| Code patches (immediates, NOPs, code caves) | most PS2 codes, the JSRF `.JMP` | **layer** VA hook, **mod** callback | generated code is static C; `.text` pokes change nothing |
| Re-apply after the game resets a value | WFP's HUD-reset wrappers; Flycast's per-frame apply | **layer** (a held poke with an expected-original guard) | a generic flag on a poke |
| Patch-site validation before applying | WFP (the CRC list), `.JMP` CRC32, every emulator's hash key | **layer** | our XBE sha256 and section pins |
| Exclusive choices (16:9 or 21:9) | RPCS3 `Group`, pnach "enable only one" | **mod** config: one `cfg_choice` key | no separate switches that can conflict |
| Movie scaling | Aero_ "FMVs", SSX3-recomp pillarbox | **layer** (`display.movie`) | done |
| Present stretch for anamorphic output | Virjoinga `gsaspectratio=Stretch`, SSX3-recomp, every `.JMP` (by the TV) | **layer** (native-widescreen D5) | specified, not built |
| Render-target widening for effects (blur, glare, boosts) | WFP "HUD render width 854"; SSX3-recomp's scaled target | **layer** (the padded targets and `nv2a_rt_tex_reads`, the tracker item; native-widescreen D6 frame-copy provenance) | the guest's offscreen sizes are generic |

## 7. The tracker item: the Burnout 3 crash-cam bars

What is seen (`runs/hor-plus-fx/b3/host-after/host_07000.bmp`, 854x480 on
Metal):
- the top bar (y about 16-72, "CRASHED", "IMPACT TIME") and the bottom bar
  (y about 375-465, with a translucent list backing behind the crash list)
  span x 107-747 only;
- the world shows across the full width in the top 16 rows.

The PS2 patches show that the game draws both bars as full-width 2D at
x = 0, w = 640, and the list backing as a separate full-width quad. Under
our Hor+ a full-width 2D batch is stretched when untextured or over a small
texture. A full-width batch is centred only when:
- (a) it samples a guest texture wider than a quarter of the frame, so it is
  classed a picture and follows `display.movie` (default black, centred);
- (b) its vertices' w is not one whole number from 1 to 1024, so it is
  treated as 3D and its geometry ends at the guest's 0..640;
- (c) it is drawn as several narrower quads, none full width on its own;
- (d) it samples an unpadded render target that is neither 4:3 nor square
  (`flat_rt` in `nv2a_aspect_place`), and so is centred.

The trace in the item does not list the bars among the 2D programs,
which points to (b) or to a fixed-function path.

**Recommendation, in order:**
1. Pin the cause with runs and no code change:
   - `RECOMP_TRACE=aspect` across the crash. This names the bar batch's
     program hash, its w, its texture and whether it is full width per
     triangle.
   - The candidate rects are static `.data` the game reads, so a write watch
     (`RECOMP_WATCH`) shows nothing. Test each one with `RECOMP_POKE`
     instead, the way native-widescreen task 1.3 does: set its width to 320
     and see which bar halves. If none does, trace the readers
     (`sub_000BEC10`, `sub_000BFCB0`, `sub_000EE710`).
2. Fix it in the layer, since every cause is generic:
   - (b): widen the 2D test for screen layers drawn at one fixed w, the way
     BLiNX 2's w = 2 and 3 HUD needed. Use it only to decide full width and
     band, never to make a partial batch 2D (design D5).
   - (c): judge full width over a set of quads that tile one row band.
     Union over a whole batch would undo Hor+ H4 (full width is judged per
     triangle, because BLiNX 2 draws four corner triangles in one batch).
     native-widescreen D7(a) already specifies a cover-sum for tiled
     backdrops; the bar rule reuses it.
   - (a): add a **band** rule. A full-width 2D batch whose height is at most
     a quarter of the target, and which lies in the top or bottom quarter, is
     a letterbox bar and is stretched even over a guest texture. A bar's
     texture is a vertical gradient or a flat colour, which stretching does
     not distort.
   - (d): treat a full-width batch over an unpadded flat target as a band
     when it meets the band test.
   The rule then fixes the same bars in any other title.
3. If the trace shows a case no generic rule should take, use the overrides:
   `[aspect.program]` or `[aspect.texture]` set to `stretch` in b3's
   `config.default.toml`. They move from native-widescreen to this change
   (tasks 3), so this would be their first user.
4. Not recommended: a PS2-style b3 mod that pokes the rects to x = -107,
   w = 854. Under Hor+ a poked full-width batch is stretched anyway (the poke
   changes nothing), or still centred and scissored to 4:3 (the poke is
   clipped). It only works in a Family B renderer.
5. Under `display.widescreen = native` (not built), the bars cover
   the guest's 640 columns. After the present stretch they cover the whole
   16:9 display and need no fix.
   - native-widescreen task 1.3 should still check whether b3 squeezes its
     own HUD in native mode. The PS2 build does not, which is why Aero_
     squeezes it.
   - If the Xbox build does not either, the HUD comes out 4/3 too wide under
     native. That case needs a Family B 2D squeeze in the layer: design D6.

## 8. Notes for the tracker items

**The tracker item, the SSX 3 glare.**
- Not reproduced here; it waits on the user's replay.
- The candidates are the LensFX flare sprites (our USA counterpart of PAL
  `sub_00152A70`, called from the visibility poll `sub_001F8760`) and a
  full-screen glare quad.
- If it is a full-screen quad over a padded render target, the band and
  full-width rules apply.
- If it is a flare sprite, the screen-layer test must not turn it into a 2D
  batch: flares are drawn without depth, like a HUD (design D5).
- If it is the flare's occlusion test (a small query draw sampled back), the
  layer must not filter or move that query draw. `nv2a_batch_info`'s note on
  hidden bounding draws applies.
- SSX3-recomp needed no glare fix under Family B, because its full-width
  w == 1 quads keep the edges. That supports reading the glare as a
  full-width classification gap and not a projection problem. Dolphin's
  sun-through-obstacles problem on GameCube is an EFB-access effect, not an
  aspect one.

**The tracker item, the JSRF Can boost.**
- A full-screen effect: a frame copy blurred and drawn back.
- It belongs to native-widescreen D6 (frame copies are render targets, read
  whole) and the tracker item's `nv2a_rt_tex_reads`. If the copy goes through a guest
  texture that the classifier calls a picture, it becomes a case for D6's
  provenance or for an `[aspect.texture] rt` row.
- The JSRF `.JMP` widescreen patches change only the view matrix, so they
  say nothing about the boost. No projection hook is involved.
- Agent `jsrf-boost` owns the fix. This spike only places it: layer, not mod.

## 9. Outcome

The mod connectivity layer is specified in this change. In short:
- every widescreen fix found in the wild, on every platform, becomes a layer
  service (aspect, VA hooks, guarded pokes, state probes, placement rules and
  overrides, render-target widening, the native present) plus a few lines of
  per-game data;
- the per-game data is a VA, a probe, a poke row or an override row;
- no game needs a Family B renderer to get its bars, backdrops or effects
  right under Hor+;
- the wider survey changed three things in the design: the poke's
  expected-value guard (Flycast), the removal of a runtime `find()` (every
  signature system resolves once, against a pinned executable), and the hook
  ABI's register access (the JSRF view builder is fastcall).
