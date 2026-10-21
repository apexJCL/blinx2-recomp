Worktrees: `wt/<name>/xboxrecomp` (a branch off `posix-host/portability`) and `wt/<name>/cat` (off `main`).

- Raw runs go under `xbox-recomp/runs/free-cam/`, never in a worktree.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock` (game runs also through `notes/mac-run-lock.sh`), with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Proton runs on the Deck through `blinx2 bench`.
- New wrappers need `./blinx2 recomp`; never edit `src/recomp/gen/`.

## 1. M0 spike (done)

- [x] 1.1 `V_game`: the camera struct `[0x4B271C]`, the builders `sub_000292A0` and `sub_0021B1F0`, the view `0xA72380` and what reads it (`spike.md` 9.1).
- [x] 1.2 Debug keys `cam_log` and `cam_fix` (`src/recomp_manual.c`, `docs/env.md`); the stock Metal golden passes with them.
- [x] 1.3 Hook decision 1a, proven on Metal (`runs/free-cam-m0/fix-offset2`, `fix-hold2`).
- [x] 1.4 Projection `sub_00042AE0`/`sub_0029EEF2` and cull `sub_0003B180`/`sub_0003B2D0` (9.3).
- [x] 1.5 The pause state `0xAE73B4` and its menu (9.2); `.edt` is character-editor data (9.4).
- [x] 1.6 Spec deltas: `specs/free-camera/spec.md` (new) and `specs/enhancements/spec.md` (the module table, the `camera.*` keys in "Enhancements default to stock", the Hor+ cull widening). Done: `specs/free-camera/spec.md` (toggle, fly and capture, HUD hide, freeze) and `specs/enhancements/spec.md` (the `camera.*` keys stay out of goldens). The Hor+ cull widening is the tracker item's delta.

## 2. Hor+ cull widening: moved to the tracker item

This group is the scope of the tracker item (the user, 2026-10-18), designed in D6. It does not depend on the free camera.

- [x] 2.1 Wrapper `sub_0003B180` in `recomp_manual.c`: when `display.aspect` is wide and the aspect argument at `[esp+8]` is about -0.75 (the main view), scale it by `(4/3) / A` (or set `-(1/A)`). Otherwise call `_gen` with no float operation (bit-exact). The aspect comes from `nv2a_host_opts()`; it compiles and is a pass-through with `XBOXRECOMP_ENHANCE` off. Done on `fix/hor-cull` (9355a9f); prints `[HORCULL]` once when active.
- [x] 2.2 Audit the 18 callers of `sub_0003B5C0`/`sub_0003B750` for uses outside rendering (activity, AI wake-up, sound); record each and whether it may see the wider planes. With a per-site counter at 21:9 on stage 1, two sites were hit: 0x681B9 in `sub_00067E60` (visible 54% to 62%) feeds the per-frame in-view/LOD level at object +0x2B4 (table 0xCD2440, stride 0x30C): `sub_00026340` resets it each frame and the draw passes store max(old, `sub_0019A2C0`). Its readers are `sub_0018CBD0` (the character draw) and `sub_00143F80` (logic), which counts frames while the object is off-screen, then raises y (+0xF0) and advances its state. Under Hor+ an object in the side columns counts as on-screen, so that off-screen action waits until it leaves the wider frame: accepted (D6), since it agrees with the picture; 0x91853 in `sub_00091790` (45% to 55%) is a draw (instances). The update-phase callers under `sub_00062FB0` (`sub_001C2610` x2, `sub_001DF1E0`, `sub_001E0DF0`, `sub_00348590`, `sub_00348F10`) were not hit in that window. Follow-ups: identify what `sub_00143F80` drives; exercise the update-phase sites in another stage.
- [x] 2.3 Check with `cam_log` at 21:9 that only the two horizontal planes change for the main view, square targets keep theirs, and P is unchanged. Horizontal planes (±0.84195, 0, 0.53955) to (±0.66553, 0, 0.74637), half-tan 0.641 to 1.1215 (x1.75); vertical planes stay (0, ±0.90130, 0.43319); P00 1.56047 and P11 -2.08062 unchanged; square targets (argument -1) untouched.
- [x] 2.4 Metal at 16:9 and 21:9 on stage 1: the 1-1 edge objects present from the first frame they are in view (A/B frames against main at the same aspect); batches and flips/s recorded (25% rule). The wider planes are shown by `cam_log` (2.3) and the batch count; the frames cannot show them above run noise. Batches per flip, flips 900-2600: 21:9 stock Hor+ 4466 and 4548 (two runs; 4487 in the first A/B), with the fix 5007 and 5090 (two runs on the committed exe; 5093 in the first A/B): about +12%; 16:9 4463 to 4745 (+6.3%, one run each). Flips/s at 21:9: 33.8 and 33.6 stock, 33.8 with the fix (30 fps paced, no drop); the second fix run fell to 23.9 because of host load in flips 900-1500 only (other games running on the Mac, load average 19), not the fix. Pushbuffer walk at 21:9: 9.96 to 11.74 ms mean (+18%, under 1.5x). Frames (host dumps every 60 flips, 21:9): two stock runs differ from each other by about as much as stock and fix do. Over flips 1500-2640 the per-pixel MAE is 0.4-1.3 in the left column and 1.1-1.6 in the centre for every pair, and 0.3-0.6% of column pixels change by more than 24. Over flips 720-1440 the runs drift apart (MAE 13-43 everywhere, the `cam_log` camera at view build 3000 differs), so game state is not deterministic run to run. The grass that used to pop in at the left edge is visible with the fix at flip 1800, but frame A/B alone is not proof: the centre differs at run noise.
- [ ] 2.5 Gates: Mac build, `uv run pytest scripts`, ruff, the stock Metal golden, `blinx2 bench golden` (D3D11 under Proton), and a Deck 21:9 run. Mac part done (build, plus an `-DXBOXRECOMP_ENHANCE=OFF` build that compiles and links; pytest 73 passed 1 skipped, ruff clean, stock Metal golden attract/stage1/story pass on the committed exe with no `[HORCULL]` line); the D3D11 golden and the Deck 21:9 run are pending.
- [ ] 2.6 Follow-up: square reflection targets keep 4:3-width planes although the tracker item pads squares by the ratio plus w/8, so reflections near the pad edges may miss objects. Fix: scale the -1 argument by the square's padded-width factor.

## 3. Freeze: the world-update gate (D5)

- [x] 3.1 Trace what the update skips while `0xAE73B4 != 0`: from `sub_00062FB0` and `sub_000649B0`, find the branch that stops the world and timer updates but not the stage draw.
- [x] 3.2 Alternatively, find the in-game Pause time control's state (use it in stage 1 under a memory diff, as M0b did). Not needed, see Result.
- [x] 3.3 Accept a flag only if a poke freezes the world and the timer, the stage stays full-screen with no menu, and poking back resumes cleanly (Metal frames in `runs/free-cam/`).
- [ ] 3.4 If none passes, record it here and ship without freeze: drop `camera.free_freeze_key` from the keys (the user, 2026-10-18).

Result (`spike.md` 9.6): `0xAF0EF4` passes 3.3, so 3.4 does not apply and `camera.free_freeze_key` stays. 3.2 was not needed (`0xAF0EF4` comes from the 3.1 trace). The tracker item follows the 9.6 caveats:
- the entry guard (`0x449F40 == 1`, `0xAE73B4 == 0`, `0xAF0EF4 == 0`);
- a re-assert after `sub_000EEB40`/`sub_00161120` and before `0x652DC`, tracking and logging game writes;
- a restore on unfreeze;
- dropping the freeze on a stage change.

Event scripts are not frozen.

## 4. Mod-layer slice (toolkit, `spike.md` 6.3)

- [x] 4.1 `src/enhance/mod.{c,h}`: `struct xbox_mod`, the static table, `xbox_mod_api` v1 (memory, config getters, log, `on_frame`, `input_state`, `input_capture`, `batch_filter`). Done in the tracker item (toolkit `posix-host/portability`).
- [x] 4.2 `enhance_input`: capture of pad and mouse-look. Done in the tracker item (toolkit `posix-host/portability`).
- [x] 4.3 `nv2a_backend_common`: the `batch_filter` call before a draw, on both backends. Done in the tracker item (toolkit `posix-host/portability`).
- [x] 4.4 ctests: table init order; `batch_filter` with a stub backend; capture. Done in the tracker item (toolkit `posix-host/portability`).

## 5. Free camera (cat)

- [x] 5.1 Keys `camera.free`, `free_speed`, `free_look_sens`, `free_hud`, `free_toggle`, `free_hud_key`, `free_freeze_key`, `free_reset_key`: `recomp_env_game.h` rows, `docs/env.md` rows and tier counts, `packaging/config.default.toml` (stock), `report_unused`. Done; `[ENHANCE] camera.free=` is logged for the golden check and `game.toml` `enhance_stock` lists `camera.free = "off"`. The keys are read in the mod's init, inside `xbox_enhance_init`, before `enhance_cfg_report_unused`.
- [x] 5.2 Turn the M0 wrappers into the feature (D1), keeping the per-builder swap (the user, 2026-10-18): the free fields come from the camera module when it is active; `cam_fix` stays a debug key on the same path.
  - substitute only when `cam == MEM32(0x4B271C)`; log other cameras once;
  - restore a field only if it still holds the swapped-in value;
  - a depth counter so a nested build does not swap twice;
  - `cam_log` skips `cam == 0`.
- [x] 5.3 Wrapper `sub_0005C930`: `_gen`, `on_frame`, neutral pad while captured (D3).
- [x] 5.4 Fly controls and seed (D2); reset to the game camera. Bindings: left stick move, right stick and mouse look, RT/X up, LT/Y down, White fast (x4), Black slow (x0.25); `camera.free_reset_key` re-seeds.
- [x] 5.5 HUD hide through `batch_filter` (D4); list the batches it matches in this file. The filter hides the whole blended, no-depth 2D pass on the back buffer (programs `5474DB2A` and `B2913952`), not one shape: dialogue boxes and fades drawn there are hidden too while the HUD is hidden. In stage 1 (`runs/free-cam/fly1e`) that pass was one batch shape: prog `5474DB2A` prim 6 (quads) idx 4, blend 0302/0303, zwrite 0, alphatest 0, 640x480 back buffer, carrying the whole HUD, the radar included. `B2913952` never matched there.
- [x] 5.6 The radar follows the free camera (the user, 2026-10-18; no extra hook). Pin what it reads (the view global or a struct field during a build), list it and any other view-derived readers in D's risks, and check it on screen. The view `0xA72380` or a value derived from it inside a build; not the struct, not the inverse view (design, Risks).
- [x] 5.7 `scripts/test_*.py` cases for the keys and the stock default. `scripts/test_free_camera.py`: the fly maths and the freeze bookkeeping compiled from `src/free_cam_fly.c`, and the key rows, docs, `config.default.toml` and golden stock value.

## 6. Checks and gates

- [x] 6.1 Cutscenes and the `sub_0003A780` path: toggle in a story cutscene and a stage intro; record whether the view follows. Stage-1 intro and dialogue: the view follows (design, Risks: Cutscenes). Story cutscenes are movies.
- [x] 6.2 Metal and D3D11 screenshots of the same free-camera path (private, `runs/free-cam/`). On 05d4fce, script `fly1`: Metal `runs/free-cam/fly-05d4fce-metal`, D3D11 on the Deck bench-logs 20261021-121701 (frames in `runs/free-cam/deck/fly1-frames`); `runs/free-cam/fly-05d4fce-ab.png` pairs them (D3D11 left, Metal right, eight points from the toggle to after the reset). The views match, the HUD hides on both, and both logs show the same sequence (on, HUD hidden, freeze, 0 game writes, reset, off).
- [x] 6.3 Gates: Mac build, POSIX ctests, `uv run pytest scripts`, ruff, the stock Metal golden (`enhance_stock` unchanged), `blinx2 bench golden` under Proton. On 05d4fce: Mac build clean, `uv run pytest scripts` 88 passed 1 skipped, ruff clean, `openspec validate` clean. Metal goldens: attract and stage1 CLOSE; story INCOMPLETE on the first run (`runs/free-cam/golden-05d4fce`: story-hub NEWVIEW, overlay 2931 px with 0% bad, the known random fifth hub view, also seen on main) and all CLOSE on the rerun (`golden-05d4fce-r2`). On 409ef2f the same way: `golden-409ef2f` (story-hub NEWVIEW), `golden-409ef2f-r2` all CLOSE. Each log has `[ENHANCE] camera.free=off` and `(0 frame, 0 filter)`. D3D11 under Proton on the Deck (`blinx2 bench golden`, GE-Proton11-7, the Mac-built exe): attract, stage1 and story frames pass (bench-logs 20261021-121147, -121308, -121459). Its toolkit-test step did not run, because it needs a build-win configured on the host and builds stay on the Mac. No toolkit change, so no ctests. Earlier: 3581125 (`golden-3581125`) passed, and an `-DXBOXRECOMP_ENHANCE=OFF` build links.
- [x] 6.4 Docs: the README's enhancement list and `docs/env.md`.
- [ ] 6.5 Review; fixes go back to the branch's agent.
- [x] 6.7 Freeze checks (`spike.md` 9.6 caveats):
  - on the Deck with sound, whether audio and music pause or keep running during a freeze: **they keep running**. Deck run 20261021-121935 (script `fz_audio`, D3D11): the output WAV (`runs/free-cam/deck/fz_audio.wav`) holds about -31 dBFS through the freeze (game time 45.5-62.4 s), the same level as before and after. This is measured from the capture; nobody listened.
  - a stage with enemies, projectiles or time effects: **done** (Metal, `runs/free-cam/fz295/boss2`): in the Giant Mandrake fight two 5 s freezes hold the boss, a projectile and a hit flash still (0.00-0.07% change between dumps against 0.3-4.5% running), the HUD timer stops, the gate reads 1 and each freeze logs 0 game writes. Time controls stay unprobed (the pad is neutral while flying). Earlier note: What was checked: on Metal (`runs/free-cam/fz-enemy`, four freeze windows with a still camera), 0.02-0.09% of pixels change between dumps while the world runs (the sky's clouds) and 0% while frozen. The fly path never brought an enemy into view: in stage-1 play they show only in the MISSION OBJECTIVES cut-in. The time controls cannot be used while flying, because the pad is neutral.
  - an event that starts during a freeze (check the write log): **done** (`runs/free-cam/fz295/intro`): a 25 s freeze from the stage 1-1 start lets the intro event and the Operator dialogue run, as designed; the intro's per-frame writes equal the kept value and are swallowed, and the gate stays 1. Earlier note: Every run logs `0 game writes while frozen`. The event-window bookkeeping is unit-tested (`test_freeze_sees_event_writes`, `test_freeze_sees_writes_outside_the_event_window`), and the drop probes below wrote from inside the window.
  - the freeze drops on retry and on a stage change: **done**. On Metal, `drop_menu`, `drop_menu_tick`, `drop_stage_change` and `drop_stage_clear` (design D5; retry shares the menu flag's guard). On the Deck, `drop_menu` (bench-logs 20261021-122139) logs `freeze dropped: run=1 menu=1, put back 0`.
- [ ] 6.6 After merge, one Mac CPU-backend build check (the rasteriser has no HUD filter: a TASKS.md follow-up).
