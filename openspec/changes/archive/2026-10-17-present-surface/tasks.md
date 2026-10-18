## Setup

- **Worktrees:** `wt/present/cat` off `main` (a1de09b) and `wt/present/xboxrecomp` off `posix-host/portability` (e629c35), both on `fix/present-surface`. For section 3, `wt/present/xboxrecomp-cli` off the CLI's `main` (2ad3699, v0.6.0) on the same branch name; its commits use the noreply identity (CLAUDE.md, public pushes), no tracker ids, host names or private paths.
- **Order:** one agent. Toolkit (1, 2) with its ctests, then the CLI (3) so its tag exists before cat pins it, then cat (4), then the gates (5), review (6) and the user's check (7).
- **Raw runs** go to `xbox-recomp/runs/present/`; the analysis scripts are `runs/present/tools/edges.py` and `edgesum.py`.
- **Mac:** `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`; headless runs with `SDL_AUDIODRIVER=dummy`, through `sh notes/mac-run-lock.sh`.
- **Deck (`ssh <bench-host>`, desktop mode):** only the scratch install `~/Games/BLiNX2-scratch` and its `tools/run-gs.sh NAME SECS "GSARGS" KEY=VAL...` (nested gamescope; saves the log, a `gamescopectl` screenshot and the game's environment to `runs/NAME/`). Start runs through `systemd-run --user --unit=blinx-scratch-* --collect`, since a plain `nohup` dies when ssh closes. Never touch `~/Games/BLiNX2`. The Deck's bundle comes from `blinx2 package steamos` on the branch (cat with the toolkit worktree and the CLI worktree via `XBOXRECOMP_DIR`/`XBOXRECOMP_CLI_DIR`), copied under `versions/` with the `current` symlink moved.
- Design decisions are cited as D1-D5.

## 0. Spec review

- [x] 0.1 The read-and-improve pass (this revision): D2 decided as a config-tier row set by the launcher only, D4 narrowed to unity blits with `EPS = 1/64`, file references corrected, gates completed.
- [x] 0.2 Implementation starts from this commit.

## 1. Toolkit: present.surface (D1, D2, D3)

- [x] 1.1 `src/platform/recomp_env.h`: two config-tier rows in `RECOMP_ENV_ENHANCE_KEYS`, `PRESENT_SURFACE` (`RECOMP_PRESENT_SURFACE`, "enhancements: present.surface, auto (default), window, internal") and `HOST_GAMESCOPE` (D2's help text).
- [x] 1.2 `src/enhance/enhance_cfg.c` `bind_builtins`: bind `present.surface` to `RENV_PRESENT_SURFACE`. The hint is not bound.
- [x] 1.3 `src/kernel/nv2a_backend_common.h`: `struct nv2a_host_opts` gains `int present_surface` (`NV2A_PRESENT_SURFACE_WINDOW`, `_INTERNAL`); no `NV2A_OPT_*` bit (read at init only). `src/enhance/enhance.c` `xbox_enhance_init`: read the key with `enhance_cfg_choice` (`auto|window|internal`, default `auto`), resolve `auto` with `recomp_env_on(RENV_HOST_GAMESCOPE)`, store the result, and extend the `[ENHANCE] render.scale=...` line with `present.surface=<value>(<reason>)` per D1.
- [x] 1.4 `src/d3d/nv2a_pb_d3d11.c`:
  - `init`: under `internal`, client area and swap chain at 640x480 × `nv2a_host_render_scale()`, a `WS_POPUP` at (0,0) when fullscreen and a normal window otherwise; the screen metrics are not consulted;
  - `present_resize`: returns at once under `internal` (`WM_SIZE` keeps recording the client size);
  - `d3d11_flip`: the copy condition per D1, and the first-present line gains ` (surface internal)`.
- [x] 1.5 `src/video/fb_present_metal.m`: under `internal`, keep `drawableSize` at the frame size at init and in `fbm_present`, set `contentsGravity` and the layer filters per D3, and draw the frame 1:1.
- [x] 1.6 `src/video/fb_present_sdl.c`: one `[present]` line when the key is `internal` and this presenter runs (D3). Add the TASKS.md note (section 5.5).
- [x] 1.7 ctest for the resolver (`tests/enhance_cfg`, or a new `tests/present_surface` registered like it): key × hint combinations and an invalid value, checking the resolved value and the log fragment.
- [x] 1.8 `docs/runtime/config.md`: the key in the table, a paragraph under "What the render and present keys do" (what `internal` does, that `auto` means `internal` only under the launcher's gamescope hint, that FSR needs a surface smaller than the output, so scale 1 on the Deck; a bare `.exe` under gamescope uses `internal` by hand), and the env table rows.

## 2. Toolkit: guest-rate rect sampling (D4)

- [x] 2.1 `nv2a_ps_consts_fill`: `tex_scale[n].z = N` under D4's eligibility, else 0. Reset `.z` in the render-target overrides (`nv2a_pb_d3d11.c` `setup_pixel` line 2208, `nv2a_pb_metal.m` line 2026). Comment: rect padding and the host pixels between the 1x sample points.
- [x] 2.2 The helper `nv2a_snap_uv` in HLSL and MSL (one string each, D4's rule, `EPS = 1.0/64.0`, derivatives computed before the branch). Apply it in `s_ps_src` (line 384), `d3d11_debug_ps` (line 2158), the probe's `uvof` (line 2687) and Metal `fs_basic` (line 203), always compiled in.
- [x] 2.3 `d3d8_combiners_parse.h`: `int rect_snap` beside `fog_input`. `d3d8_combiners_hlsl.c:147` and `d3d8_combiners_msl.c:133` emit the helper and its call only when it is set; the backends set it from `nv2a_host_render_scale() > 1` where they fill the state and include it in the shader cache key (`rc_hash` and Metal's). The `d3d8_hlsl_split`/`d3d8_msl_split` expected outputs stay unchanged; add one split case with `rect_snap = 1` per language.
- [x] 2.4 ctests (`tests/render_scale`): the eligibility cases and the helper's arithmetic from design.md Validation, with the C reference expression mirroring the shader text.
- [x] 2.5 `tests/posix_ctest.sh <build-dir>` (0 FAIL); `pytest tools/recomp tools/disasm` only if a tool changed.

## 3. CLI: the launcher hint

- [x] 3.1 `src/xboxrecomp_cli/package/templates/steamos/launch.sh`: D2's block before `load_env "$HERE/launch.env.default"`. Keep the notice's own `XDG_CURRENT_DESKTOP` test as it is.
- [x] 3.2 `tests/test_steamos_install.py`: extend `FAKE_UMU` to record `${RECOMP_HOST_GAMESCOPE:-unset}` (for example into `$HOME/umu.env`), then three cases through `launch()`: `XDG_CURRENT_DESKTOP=gamescope` gives `1`; `GAMESCOPE_WAYLAND_DISPLAY=gamescope-0` gives `1`; neither gives `unset`; and `RECOMP_HOST_GAMESCOPE=0` in `config/launch.env` under gamescope gives `0`. `bash -n` already covers the syntax.
- [x] 3.3 `uv run pytest tests` and `uv run ruff check . && uv run ruff format --check .`. Note the pre-existing `test_bench_cli.py::test_parity_pacing` failure if it shows.
- [x] 3.4 Release (branch side; CLI branch tip 895eed8, version 0.6.1, untagged until the merge): the orchestrator squash-merges to the CLI `main` and tags `v0.6.1` (annotated, `docs/maintainers.md`); the branch agent records the tag and commit for 4.3. Until the tag exists, cat's Deck bundle is built with `XBOXRECOMP_CLI_DIR` pointing at the CLI worktree.

## 4. cat

- [x] 4.1 `packaging/config.default.toml`: `surface = "auto"` under `[present]`, with a comment (gamescope scales the frame when the launcher says so; FSR needs scale 1; `"window"` is the old behaviour).
- [x] 4.2 `docs/env.md`: Config rows for `RECOMP_PRESENT_SURFACE` and `RECOMP_HOST_GAMESCOPE` (file:line columns), the Config count and the "Nine of them" list in the intro (`scripts/test_env_doc.py` checks the count), and the settings-files section's key list.
- [x] 4.3 (golden.json done; `game.toml` pins the CLI branch commit 895eed8 for now, the orchestrator re-pins to the v0.6.1 tag) `analysis/golden/golden.json` `env`: `"RECOMP_PRESENT_SURFACE": "window"`. `game.toml` `[cli]` to the v0.6.1 tag and commit once 3.4 is done.
- [x] 4.4 Mac build, `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`.

## 5. Verification

- [x] 5.1 Metal goldens at stock (`blinx2 golden`): same verdicts as main.
- [x] 5.2 Metal `@attract` at scales 2 and 3 with `fb_dump` every 30 flips; `edges.py` on frame 009: the last guest column and row match the interior within the golden limits. Before/after numbers against `runs/present/metal-attract-s2` go in the notes. A `RECOMP_PRESENT_SURFACE=internal` run with `present.fullscreen = true` at scale 1 shows the frame letterboxed by the layer (a window shot), and the goldens are unaffected (they pin `window`).
- [x] 5.3 Deck nested gamescope with the branch bundle (design.md Validation): the four checks, including the probe's `uv0 0.624512` at scale 2 (`RECOMP_TRACE=px=639,300,px_flips=300-302,px_max=10` in `launch.env`). Keep the logs under `runs/present/deck/after-*`.
- [x] 5.4 the Linux/Proton host, on the orchestrator's go, under the run lock: `blinx2 bench golden` at stock, then one scale-2 attract run with `RECOMP_DEBUG=d3d11_dump` checked with `edges.py`. D3D11 flips/s against main (flag a 25% drop).
- [x] 5.5 TASKS.md follow-ups: the SDL/CPU presenter ignores `present.surface`; the tracker item follow-up (a) must redefine the snap's block rule if it moves the guest-to-host mapping (design.md D4); a magnified or minified rect stretch that bleeds beyond its 1x look widens the unity test; Burnout 3 under Proton before the snap joins the upstream set.

## 6. Review

- [x] 6.1 Review of the merge; fixes go back to the branch agent. (Done: TASKS.md, "review approve after fixes"; toolkit 1b01131, cat 6ffce39.)

## 7. Game Mode check (the user)

On the Deck in Game Mode with the branch bundle installed (CLI v0.6.1 launcher):

1. In the game's Steam properties set the game resolution to **Default** (or **Native**). Leave `config/config.toml` at `[render] scale = 1`, `[present] fullscreen = true`, no `surface` line.
2. Start the game. In the Quick Access menu, Performance, set *Scaling Filter* to **FSR** (default sharpness).
3. FSR engages: the picture is pillarboxed 4:3 and sharper than with Linear, and `logs/<newest>` shows `present.surface=internal(auto: gamescope)` and `back buffer 640x480`.
4. Set `[render] scale = 2` and restart. The picture is a sharp downsample (FSR does not apply: the surface is 1280x960, taller than 800). The opening movie has no green line on the right or bottom edge.
5. Optional: `surface = "window"` under `[present]` in `config/config.toml`, restart. The log shows `back buffer 1280x800` as before, and FSR has no effect.
