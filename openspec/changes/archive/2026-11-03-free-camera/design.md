## Context

The spike is `spike.md` and its M0 results are section 9. The facts this design rests on:

- **Camera struct `[0x4B271C]`**: p at `+0x00`; angles at `+0x0C` (pitch), `+0x10` (yaw), `+0x14` (roll), `+0x18`, `+0x1C`; the eye at `+0x2C` (written by the first builder); a shake offset o at `+0x38`.
- **Builders**, each followed by SetTransform(view) (`sub_002E0B90` state 0) and `sub_00042AE0`:
  - `sub_000292A0` (ebx = camera; from `sub_0002DD40`, the pass setup): `V = T(-(p - o))·RotY(a1c)·RotX(-a18)·RotY(a10)·RotX(-ac)·RotZ(-a14)`; writes `+0x2C = p - o`.
  - `sub_0021B1F0` (from `sub_00216D70`, called by the stage passes): V from the eye `+0x2C` and `+0x0C/+0x10/+0x14`. It runs last, so it decides the stage image.
- **Downstream** of `0xA72380`: world×view `0xAAD3A0` (`sub_0003B5C0`), bone palettes (`sub_00038B00`), `c[112]` (`sub_0003FC40`), cull centres (`sub_0003B750`), inverse view `0xA9C220`.
- **Projection** `sub_00042AE0` → `sub_0029EEF2(0xAC1870, -atan(640/512), -(4/3), 1, [0x9FD95C])`. **Cull planes** `sub_0003B180(fov, -(h/w), zf)`, one caller (`0x42C78`); the test is `sub_0003B2D0`.
- **Pause** `0xAE73B4`: 1 in the pause menu (which draws the world as an inset), 0 in play (corrected in `spike.md` 9.6).
- The M0 debug wrappers in `src/recomp_manual.c` (keys `cam_log`, `cam_fix`) prove the substitution on Metal; the stock golden passes with them.

## Goals / Non-Goals

**Goals:** a photo-mode free camera that is off by default, returns to the game view with nothing to restore, and agrees on Metal and D3D11; the Hor+ cull widening.

**Non-Goals:** moving the audio listener; a FOV option (E10, later, through the same projection call); cutscene camera editing; a freeze built by skipping `sub_00062FB0` (it would stop rendering too).

## Decisions

### D1. Hook 1a: substitute the camera struct around both builders

The free camera is a copy of the struct's fields (`+0x00..+0x20`, `+0x2C..+0x34`, `+0x38..+0x40`). Each wrapper, when the camera is active:

1. saves the game's fields;
2. writes the free fields (o = 0, the eye = p, the angles);
3. calls `_gen`;
4. puts the game's fields back. After `sub_000292A0` the eye word gets `p - o` from the game's own fields, exactly what stock writes.

The game's own maths then produces V, the projection, the cull frustum and the inverse view, so skinning, lighting and culling follow without per-model work.

Wrapper rules (from the M0 review):

- **Only the game camera.** `sub_000292A0` takes its camera in ebx and may be passed another struct. The feature substitutes only when `cam == MEM32(0x4B271C)`; any other camera runs `_gen` untouched and is logged once (under `cam_log`) so the cases are known.
- **Restore only what is still ours.** After `_gen`, a field is put back only if it still holds the value the wrapper swapped in; a field the build or a callee changed keeps the new value (the `fx.glow` wrapper's rule).
- **Depth counter.** A nested build (a builder reached from inside another) sees the struct already swapped; a depth counter makes only the outermost wrapper swap and restore, so an offset is never applied twice.
- `cam_log` skips a call with `cam == 0`.

*Alternatives.* Writing `0xA72380` after the builders: it works for V, but the cull planes, the inverse view and `c[]` built inside `sub_00042AE0` would be from the game view. Hook 1b (correct each ring store): per-model maths, and it misses the palettes and `c[112]`. Swapping once per frame around the render pass: fewer swaps, but the pass boundary is less clear than the two builders and any game logic inside it would see the free camera. The user chose the per-builder swap (2026-10-18).

### D2. Seed and fly

On toggle on, the free fields are copied from the game's (with the eye as the position), so the camera starts where the game's is. Fly in camera space from the yaw and pitch: the left stick moves, the right stick looks, the triggers move down and up (the world is Y-down), a shoulder speeds up; WASD/QE and mouse look through `enhance_input`. Roll and the two extra angles stay 0.

### D3. Input capture on `sub_0005C930`

A new wrapper on the once-per-frame input poll calls `_gen`, runs `on_frame`, and while the camera is active zeroes the game's pad state after the poll. Capture also swallows mouse-look, which feeds the pad.

### D4. HUD hide is a backend batch filter

`batch_filter` in `nv2a_backend_common` matches program hashes `5474DB2A`, `B2913952` plus state (back-buffer target, no depth test, blending on): the whole blended, no-depth 2D pass on the back buffer. The matches seen are recorded in the tasks (5.5). Dialogue boxes and fades are drawn in that pass, so they hide with the HUD.

### D5. Freeze needs its own gate

Setting `0xAE73B4 = 1` opens the pause menu, so it is not a freeze. The freeze task traces what the update path skips while `0xAE73B4 != 0` (in `sub_000649B0`, called from the stage frame `sub_00064850`), or the in-game Pause time control's state, and keeps the render running. Accepted only if a poke of the found flag freezes the world and the timer with the stage drawn full-screen and no menu, and toggling back resumes. If no flag passes, `camera.free_freeze_key` is not shipped.

**Outcome (`spike.md` 9.6):** `0xAF0EF4`, the event world-stop flag, passes. The freeze key ships. It is allowed only while `0x449F40 == 1`, `0xAE73B4 == 0` and `0xAF0EF4 == 0`. While frozen, the event system (`sub_000EEB40`) runs on the game's own value of the flag and what it leaves is kept as the value to restore, so an event that stops the world during a freeze still holds after unfreeze; a value other than 1 found before the event system (a game write since the last re-assert, such as `sub_00076030`'s snapshot restore at `0x761B4`) is kept the same way; the flag is 1 again after it and after `sub_00161120`, before the gate at `0x652DC`. Unfreeze, and a dropped freeze (the pause menu, leaving the run state, a stage start), put the kept value back. Event scripts are not frozen.

*Proof of the drops (Metal):* `runs/free-cam/drop_menu` (the pause menu by poke, the `on_frame` guard), `drop_menu_tick` (the menu flag written from the event window by a scratch probe, the `sub_00161120` guard), `drop_stage_change` and `drop_stage_clear` (the game's stage end `sub_00062550` called from the event window by a scratch probe, args 0 and 1; the drop at `sub_000606F0`). Each logs `freeze dropped ... put back 0`, and the world runs afterwards (`0xAF5C94 = 0`; the next stage, or the results scene, plays). Retry was not run on its own: it opens through the same menu flag `0xAE73B4`, so `drop_menu` and `drop_menu_tick` cover its guard.

### D6. Hor+ cull widening (now the tracker item)

The Hor+ cull fix is its own item, the tracker item; this decision is its starting design. A wrapper on `sub_0003B180` widens the horizontal cull planes when `display.aspect` is wide. Only the horizontal planes widen (half-tan 0.641 at 4:3 to 0.641·A/(4/3)); the projection, which `sub_0029EEF2` built before the call, is unchanged.

- **Main view only.** `sub_00042AE0` runs after all 17 view builds, which likely include square targets (the 512 or 256 reflection textures, h/w = 1). The factor `(4/3)/A` applies only when the aspect argument (`[esp+8]`, `-(h/w)`) is about -0.75 (the 640x480 main view); equivalently the argument is set to `-(1/A)` for that view only. Other targets keep their own aspect.
- **Bit-exact when not wide.** When `display.aspect` is not wide (or the argument is not the main view's), the wrapper calls `_gen` with no float operation, so stock is bit for bit unchanged and goldens stay put.
- **Builds with `XBOXRECOMP_ENHANCE` off.** The aspect is read from `nv2a_host_opts()`; without the layer it is 0:0 and the wrapper is a pass-through, so the file compiles and behaves as stock either way.
- **Effects outside rendering.** The cull planes are also read by `sub_0003B750`, whose results feed the 18 callers of `sub_0003B5C0`/`sub_0003B750`. Some may gate activity, AI or sound on "in view"; those callers are audited before the fix ships, and any non-render use is either left on the 4:3 planes or accepted with a note.

*Alternatives.* Widen the projection itself: that is a FOV change, not Hor+. Disable the cull: more draws at every aspect, and distant geometry the game never meant to draw.

## Risks / Trade-offs

- **Other culls.** Distance and activity checks (AI wake-up, LOD) still use the game's 4:3 view and its camera. Under the free camera objects far from the game camera may be asleep or at low LOD; acceptable for photo mode. Under Hor+, enemies past the 4:3 edge may be drawn but idle.
- **Radar.** The radar's view cone turns with the free camera (M0, `fix-offset2`; the tracker item `runs/free-cam/radar_base`). The user wants it to follow the free camera (2026-10-18), so there is no extra hook. What it reads, by elimination (task 5.6): the struct holds the game's fields outside the builds (D1 restores them), and holding the inverse view `0xA9C220` at its pre-toggle value after every swapped build (a scratch probe, `runs/free-cam/radar_vinv2`) left the cone turning as in the plain run. So the radar reads the view `0xA72380` or a value derived from it inside a build (world×view `0xAAD3A0`, `c[]`), not the struct and not the inverse view. Other view-derived readers: 68 functions reference `0xA72380` and 6 reference `0xA9C220` (`sub_000425B0`, `sub_00042AE0`, `sub_00048880`, `sub_00048A90`, `sub_001A47C0`, `sub_001D4160`); any of them that feeds game logic sees the free view while flying. None showed a game-state effect in the runs (no write to the camera struct, the character stands still).
- **Cutscenes.** The stage-1 intro fly-over and the Operator's dialogue close-ups go through the same builders: the free camera seeds from the scripted camera and the view follows it (`runs/free-cam/intro1`); the script keeps running underneath, and toggling off shows it where it has got to. The pad is neutral while flying, so dialogue does not advance. Story cutscenes are movies (`R0_opening`), where the camera does nothing; the `sub_0003A780` path (`[0x67EF6C] != 0`) was not seen in these runs.
- **Pause while flying.** START reaches the game through port 0, which is neutral while flying, so the pause menu cannot open; the player toggles off first (accepted by the user, 2026-10-21).
- **Gamepad bindings:** via the host-action layer. The four actions are one function each (`free_cam_action_*`), which the keyboard path calls now and that layer will call.
- **Seeding ignores roll and the extra angles.** The seed copies the eye, pitch and yaw only; roll (+0x14) and the angles at +0x18 and +0x1C stay 0 while flying, so a scripted camera that rolls or uses them starts level, and toggling off returns to the game's own values.
- **A 1 written outside the event window.** Before the event system the flag holds the freeze's own 1, so a 1 the game writes there cannot be told apart from it; only other values are taken as game writes. `sub_00062BF0` writes `0xAE73B4 = 1` and `0xAF0EF4 = 1` together (`0x62D48`): the menu flag drops the freeze, which puts back the kept value (0), where stock keeps 1 until `sub_00062FB0` clears both. The menu flag alone stops the world through the gate (`0xAF5C94 = 0xAE73B4 || 0xAF0EF4`, computed by `sub_000649B0` at `0x652DC`; `spike.md`, the gate chain) meanwhile, and both clear together, so this is probably harmless; no effect was seen in the drop runs.
- **A stage change while flying.** A freeze is dropped at a stage start, but the free camera keeps flying into the next stage (or the results scene) from the same position until it is toggled off or the stage frees its camera.
- **Speed at 21:9.** More batches past the old edge. Measure flips/s on Metal and D3D11 against the 25% rule.
- **Cutscenes** (`.cam`, `EVCAMST`, `sub_0003A780`): the builders may be bypassed. Tested, not assumed.
- **The game's camera logic.** Code that reads the struct between builds sees the game's values, since the swap restores them after each build. Code that reads the view-derived globals (`0xA72380`, the inverse view, the cull planes), or runs inside a build, sees the free camera; the radar is one such reader. Task 5.6 lists the readers found.

## Open Questions

- Does any cutscene build its view outside the two builders?
- ~~Is there a clean world-update gate (D5)?~~ Answered: yes, `0xAF0EF4` (`spike.md` 9.6).
