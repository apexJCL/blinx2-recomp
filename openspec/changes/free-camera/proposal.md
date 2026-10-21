## Why

The user decided on 2026-10-17 that textures plus a free camera are the post-v1 enhancements to build (spike the tracker item, `spike.md` section 7). The free camera is a photo mode: fly away from the game camera, look at the stage, and come back to the game view unchanged.

M0 (`spike.md` section 9) found what the spike left open:

- The game builds its view in two places, `sub_000292A0` and `sub_0021B1F0`, from one camera struct at `[0x4B271C]`, into the D3D view global `0xA72380`. Everything downstream (each model's world×view, the bone palettes `c[0..47]`, the `c[112]` light, the cull centres, the inverse view) is derived from it.
- Substituting the camera struct around both builders moves the whole picture on Metal and leaves the game's camera state stock (`runs/free-cam-m0/fix-offset2`, `fix-hold2`). That is hook 1a. The per-model correction (1b) is not needed.
- The projection is `sub_00042AE0` → `sub_0029EEF2` (fov from 640/512, aspect 4/3). The side cull planes come from one function, `sub_0003B180`. This is also where the Hor+ edge pop-in can be fixed: widen the horizontal cull planes to the display aspect while leaving the projection alone.
- The pause flag `0xAE73B4` exists, but setting it opens the pause menu with the world as an inset. The world-update gate behind it is `0xAF0EF4`, the event world-stop flag (`spike.md` 9.6). Setting it to 1 freezes the world and the timer with the stage full-screen and no menu.

## What Changes

- **The mod-layer first slice** (`spike.md` 6.3): toolkit `src/enhance/mod.{c,h}` with a static module table and `xbox_mod_api` v1 (guest memory, config getters, log, `on_frame`, `input_state`, `input_capture`, `batch_filter`). `camera.free` is its first module.
- **`camera.free = off | on`** (default `off`): `on` enables a toggle hotkey. While active:
  - wrappers on `sub_000292A0` and `sub_0021B1F0` swap the free camera's fields into the struct for the build and put the game's back after it (the M0 debug hook, made a feature);
  - a new wrapper on `sub_0005C930` (the once-per-frame input poll) runs `on_frame`, drives the fly controls, and gives the game a neutral pad while the camera has the input;
  - toggling off stops the swap; the next build is the game's.
- **Keys**: `camera.free`, `camera.free_speed`, `camera.free_look_sens`, `camera.free_hud = keep | hide`, and the hotkeys `camera.free_toggle` (F6), `camera.free_hud_key` (F7), `camera.free_freeze_key` (F8), `camera.free_reset_key`. Each has a `RECOMP_*` row in `recomp_env_game.h`, a row in `docs/env.md` and a line in `packaging/config.default.toml`.
- **HUD hide** in `nv2a_backend_common` through `batch_filter`, keyed on the program hash plus state, so Metal and D3D11 agree.
- **Freeze** through `0xAF0EF4` (found in the tracker item, `spike.md` 9.6), allowed only while `0x449F40 == 1`, `0xAE73B4 == 0` and `0xAF0EF4 == 0`. It saves the flag, re-asserts it each frame after the event system, and restores it on unfreeze.
- **Radar** follows the free camera (the user, 2026-10-18); no extra hook.
- **Hor+ cull fix** (for the tracker item; now its own item): a wrapper on `sub_0003B180` widens the main view's horizontal cull planes to the display aspect when `display.aspect` is wide, so objects past the 4:3 edge are no longer culled. Other targets and stock (4:3) go through `_gen` untouched.
- **Debug keys** (landed with M0): `RECOMP_DEBUG=cam_log=n` and `cam_fix=dx:dy:dz:dyaw:dpitch | hold[:n]`.

## Capabilities

### New Capabilities
- `free-camera`: the toggle, the fly controls, input capture, HUD hide, the optional freeze, and the return to the game camera.

### Modified Capabilities
- `enhancements`: the module table and `xbox_mod_api` v1; "Enhancements default to stock" gains the `camera.*` keys; Hor+ gains the cull widening.

## Impact

- **Toolkit** (fork-only, under `XBOXRECOMP_ENHANCE`): `src/enhance/mod.{c,h}`, `enhance_input` (capture), `nv2a_backend_common` (`batch_filter`), ctests for the table and the filter.
- **cat**: `src/recomp_manual.c` (wrappers on `sub_000292A0`, `sub_0021B1F0`, `sub_0005C930`; `sub_0003B180` under the tracker item), a camera module source, `src/env/recomp_env_game.h`, `docs/env.md`, `packaging/config.default.toml`, `scripts/test_*.py`, `TASKS.md`. One recomp for the new wrappers (no gen edits).
- **Goldens**: none change. Every key defaults to stock, and the cull wrapper is a pass-through at 4:3. The Hor+ cull fix changes the Hor+ evaluation runs, which are not goldens.
- **Upstream**: none. All of it sits on the fork's enhancements layer.
