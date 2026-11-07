# Known gaps (pending, not urgent)

These are paths we know about but have not tested, or questions the code
reading could not settle. None of them blocks anything today. Check this
list when a new bug comes in: if the report matches a symptom here, the
entry says where to start.

Each entry says what the gap is, why it is open, what a bug report would
show, and where to look. Addresses are guest virtual addresses; function
names are the generated ones (`src/recomp/gen/`) or the wrappers in
`src/recomp_manual.c`.

## Free camera

The free camera (`camera.free`, [env.md](env.md)) swaps its own eye and
angles into the game camera `[0x4B271C]` around the view builds and the
render passes that read the camera. The verdict for each reader is in
openspec change `free-camera-screen-projection`, design D3 and D4. Task 3.6
lists the paths no flight has reached.

### The split-screen sky dome

- **What.** The stage pass `sub_000E58D0` (`gfx_stage_pass_e58d0`) can
  move the sky dome to the eye: (eye.x, -3000, eye.z), scaled by
  `cam_far`, at 0xE5A06. It does so only when the view count `[0xAF0EE0]`
  is not 1 and the stage `[0xB87168]` is 0, 3, 5, 0xF, 0x11, 0x12 or 0x28.
  The stage pass is swapped, so this dome should follow the free camera.
- **Why it is open.** `sub_000606F0` sets the view count to 1 for one
  player (0x6190D) and to the player count for split screen (0x618B4). So
  the path runs only in split screen. Every flight so far was single
  player (stages 0, 5, 0xA, 0xF and 0x14) and never reached 0xE5A06.
- **What a bug would show.** In split screen with the free camera on, the
  sky stays around the game camera instead of the free one: its edge or
  the clear colour shows as the free camera flies away, or a view's sky
  jumps when the free camera starts or stops.
- **Where to start.** The `sub_000E58D0` wrapper in `src/recomp_manual.c`;
  the translate at 0xE5A06 and the `sub_002D4CB0` call that returns to
  0xE5A27; `[0xAF0EE0]` and the `cam_views` entries `sub_000606F0` builds,
  one per player. The swap acts only when the camera is `[0x4B271C]`, so
  check which camera each view's pass reads. Single-player stages draw a
  world-fixed dome instead (design D4); that is the game's own behaviour.

### The camera pitch stored by the sprite draw on stage 0x1C

- **What.** `sub_000DAEC0` turns a sprite to face the camera. At 0xDB13A
  it also stores the camera pitch (+0x0C) into the drawn entity's +0x44,
  for the 16-bit types 0x6B, 0x16B and 0x26B. Only `sub_000DAE80` passes
  those types: it runs when `[0xB87168]` is 0x1C, loops over the player
  table 0xB22BA4 and matches the type's low byte, 0x6B. (`sub_000DAE50`
  passes 0x36B, 0x46B and 0x56B, which skip the store.) With the free
  camera flying, that field takes the free camera's pitch.
- **Why it is open.** +0x44 is written by `ent_player_update` and many
  other functions, and read by `sub_000C0670`, `C2E20`, `C5CF0`, `D0B50`,
  `D9350`, `DB3C0`, `104C20`, `126B20`, `13C670` and `13F740`. No read of
  the value stored here was confirmed, and stage 0x1C was never flown. It
  is an open risk, not a case shown to be safe.
- **What a bug would show.** On stage 0x1C, with the free camera on, an
  entity of that type tilts, aims or moves differently when the free
  camera looks up or down, while the same scene with the free camera off
  is fine.
- **Where to start.** The `sub_000DAEC0` wrapper in `src/recomp_manual.c`;
  the store at 0xDB13A and the type tests at 0xDB03E..0xDB055; the caller
  `sub_000DAE80`; the +0x44 readers above. Fly stage 0x1C with the free
  camera's pitch well away from the game's and watch which reader picks
  up the value.

### Draw callbacks called through pointers

- **What.** The Ninja model draws call two hooks through pointers,
  `[0xA71754]` and `[0xADA0A4]`. `sub_00038840`, which the stage pass
  calls for its stage models, walks a node tree on the Ninja matrix stack
  (`nj_matrix_stack`), calls `nj_draw_model`, and calls the hooks at
  0x3885C and 0x38A4E. `sub_0003C220`, `sub_0003C520`, `sub_0003E140`,
  `sub_0003E550` and `sub_0003E900` call through both slots too.
- **Who sets them.** 62 functions store into `[0xADA0A4]`. Most set a
  fixed target around a model draw, then put the old value back from a
  register. Examples: `sub_000A9AA0` (0xA9DF0, around its
  `sub_00038840` call that returns to 0xA9D4A), `ent_item_draw` (0x79480),
  `ent_character_draw` (0x192E70, 0x193BC0) and `sub_000A0950` (0x9FB30,
  0xA0020). `sub_000DAEC0`, the swapped sprite draw, sets 0xDB210 itself,
  so that hook runs under the swap; `sub_000D9BF0` stores 0. This slot has
  57 fixed targets. Seven functions store into `[0xA71754]`:
  `sub_0022C800` and `sub_0022D150` set 0x230C10, `sub_0026E940` and
  `sub_0026ED1A` set 0x26E8C0, and `sub_00034490`, `sub_002194F0` and
  `sub_002538F0` store a register.
- **Why it is open.** Design D3 lists the camera readers found by reading
  the generated code and following direct calls. A hook target is only
  known where a function stores a constant; a target stored from a
  register cannot be followed that way. Of the 59 fixed targets of the
  two slots, none reads `[0x4B271C]` in its own body, but their callees
  were not checked, and the register-stored targets were not checked at
  all. A callback run
  inside a swapped pass sees the free camera; one run from a draw outside
  any swap sees the game camera.
- **What a bug would show.** With the free camera flying, one model part,
  sprite or effect stays placed or turned for the game camera while the
  rest of the scene follows the free camera.
- **Where to start.** Find the model draw that the wrong object goes
  through, and the function that set the hook around it: the writers of
  `[0xADA0A4]` and `[0xA71754]` (search the generated code for
  `MEM32(0xADA0A4) =`). If the target is a constant, read it and its
  callees for reads of `[0x4B271C]` (the angles at +0x0C..+0x1C, the eye
  at +0x2C..+0x34). If it comes from a register, log the target at run
  time on the stage where the bug shows. Also check whether the draw runs
  under a swap at all: a camera reader outside every wrapped pass needs
  the same `cam_build(..., NULL, ...)` wrapper as the others (design D1,
  D3).
