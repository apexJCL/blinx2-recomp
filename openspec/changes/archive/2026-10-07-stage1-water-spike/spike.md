# Spike: stage 1 water stutter and horizon split

Branches: `spike/stage1-water` in cat and in the toolkit. Raw runs, scripts and logs are in `xbox-recomp/runs/stage1-water/`. Everything ran headless on the Mac (`SDL_AUDIODRIVER=dummy`).

## Probes added (debug tier, off by default)

- `RECOMP_DEBUG=pad_peek=VA:N[:x],...` (game, `pad_input.c`) prints N guest dwords on every scripted pad poll, as floats, or as hex with `:x`. The game's frame is locked to the pad poll, so this gives a per-frame trace with no host timing in it.
- Input-script step `memdump LABEL`, with `mem_dump_every=0` to dump only at script steps (game, `main.c`).
- `RECOMP_TRACE=zminmax` (toolkit) logs SET_ZMIN_MAX_CONTROL writes.
- `RECOMP_DEBUG=watch_delay=s` (toolkit) arms a plain `watch` s seconds after boot. Armed at init, the trap on `0xCD24A0` never fired: the title's own section and heap setup remaps the page read-write. Armed late, it caught the writer at once.
- The CPU `[CPU-PX]` probe also prints the fog colour, the fog gen mode, the fog params and constants c41 and c137.

Warp recipe: write the player position into both `0xCD252C` and `0xCD2538` (current and previous; the player object is at `0xCD2440`, pointer at `0xB9D310`). Then tap A through the operator's dialogue. The scripts are in `runs/stage1-water/scripts/`:
- `warp7p.txt`: the water room, ground spot (467.54, -70.1, -1066.43), then wading in 5 directions;
- `warp_lhp.txt`: the lighthouse sea view (427.04, -70.02, -1055.43).

## Bug 1: wading stutter (cause found)

Per-frame trace while wading (Metal, `warp7p.txt`, polls 2634+):
- `[+0x84]`, the walk-ramp counter, cycles 0, 1, 2, 0;
- `[+0xAC]`, the previous stick value, cycles 0, 1, 1, 0;
- the speed `[+0x140]` cycles 0.52, 0.66, 0.84, 0.69;
- the hit-stun byte `[+0x60]` is 1 on every 4th frame, standing or moving.

The trace is identical with `metal_occ=sync`, so occlusion timing is ruled out. `sub_00176150` zeroes the stick while `[+0x60] > 0` (it sets the input-lock local `esp+0x44`), so the walk state restarts every 4 frames.

The watchpoint shows the writer is `sub_000F1C20(2)` ("freeze all players n frames"). It is called from `sub_000F7C50`, by way of `sub_000F6D20`, `sub_000EEB40` and the object loop. `sub_000F7C50` is a sign/talk-zone state machine at `0xB8BD70`. Its states 2 and 3 share `loc_000F7F7C: je`. One predecessor sets the flags with `cmp eax, 0` and the other with `test esi, 0x100`. The recompiler could not merge the two, so the `je` became `if (_flags ...)`, which is never true. The machine therefore cycles 1→2→3→4→1 every 4 frames, and each pass through state 1 freezes the players. That explains both conditions in the report: the zone object is gone once the puzzle is solved, and it does not run while time is stopped.

The fix and its spec are in `openspec/changes/recomp-test-flag-join/`.

Not done: an A/B run with the one branch corrected by hand in a scratch copy of `recomp_0028.c`. The tooling refused the edit of a generated file. The causal chain above rests on the watchpoint stack and the lifted C.

## Bug 2: horizon split (narrowed)

**Cause found later (spike/horizon-occlusion):** the occlusion lead below was wrong. The cyan layer is a 4592-index quad list, and the walker's 4096-index cap dropped its farthest rows. See `openspec/changes/pb-index-batch-cap/`.

The same view on both runs:
- **Attract demo:** flips ~3000-3100, deterministic on Metal.
- **Lighthouse warp:** flips 2300-2600, still.

The xemu reference shows cyan sea all the way to the horizon. Ours shows a cyan near band that ends in a hard horizontal edge (at x=40, between y=179 and 182), with dark green sea above it.

Facts:
- **The near band and the far sea are separate draws.** On the CPU backend at flip 2490 (`runs/stage1-water/lh-cpu-p/log.txt`), the near patch is a 7-vertex strip and the far sea a 191-vertex strip. Both use program 1, the same combiner (6 stages) and the same final combiner: `fcw 130C0300/00001C80`, which decodes to `fog.a*r0 + (1-fog.a)*fog.rgb` with alpha from r0. Fog is enabled with mode 0x800 (EXP). Their stage-0 textures differ, and so do their stage-3 textures.
- **Backend-independent.** The CPU backend shows the same split as Metal, and the user sees it on D3D11. So the cause is in shared guest-visible state (vertex-program fog output, fog params, occlusion results), not in one backend's shader.
- **The game gates it on occlusion queries.** With `metal_occ=fixed` (every query visible), the attract frame draws extra cyan patches and sun-shaft quads. That mode changes gameplay too, so it is not a fix, but it shows that the patches are culled by the game's own GET_REPORT results.
- **Ruled out: ZCLAMP.** The game writes 0x1D78 once, with 0x1 (CULL_NEAR_FAR, no clamp). All three backends clip at the far plane per pixel.
- **The fog does not make the cyan.** In the CPU fog probe (`runs/stage1-water/lh-cpu-fog/log.txt`, flip 2490), every sea draw has:
  - fog colour 0x00847064, a brown-grey;
  - gen mode 2, EXP;
  - params 1.5 and -0.0541;
  - c41 (0.136, 0.242, 0.466, 51.8) and c137 (1/1360, -0.0735, 0, 1).

  Fogging toward that colour cannot turn the far sea cyan. The cyan in xemu therefore comes from the patches' own textures and passes. That makes the missing distance fade unlikely, and the occlusion gating the leading candidate: the game draws a cyan water patch only when its GET_REPORT query says the patch is visible, and ours report the far patches as hidden.

Next step: log every GET_REPORT in the lighthouse view with its zpass count and the bounds of the query's proxy draw (`zpass` trace, lifting its 64-line cap), and compare with xemu's counts at the same view. Look first at far proxies near depth 1.0, where a depth test or a far-plane clip can reject proxies that real hardware counts.
