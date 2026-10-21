Worktrees: `wt/ssx3-edge/xboxrecomp` (branch `feat/display-overscan` off `posix-host/portability` 485f82ac), `wt/ssx3-edge/xboxrecomp-cli` (branch `feat/display-overscan` off `main`) and `wt/ssx3-edge/cat` (branch `display-overscan/spec`, this change).

- Raw runs go under `xbox-recomp/runs/display-overscan/`.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock`, with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Proton runs on the Deck through the title's `bench`, after the orchestrator gives the go.

## 1. Shared helper (toolkit)

- [x] 1.1 `nv2a_backend_common`:
  - the `overscan` field of `nv2a_host_opts` (guest px a side, 0 = stock);
  - `struct nv2a_crop` and `nv2a_present_crop` (design D3).
- [x] 1.2 `tests/present_crop/` (new standalone CMake project, `project(present_crop_test C)`, picked up by `tests/posix_ctest.sh`), modelled on `tests/render_scale`. Cases:
  - `ov 0` returns the whole frame: rect `(0, 0, fw, fh)`, UV scale `fw/tw, fh/th`, offset 0 and fit `fw x fh`, compared exactly;
  - 640x480, scale 1, ov 9, `nearest` and `linear`: rect `(9, 6.75, 622, 466.5)`, `u_off 9/640`, `v_off 6.75/480`, fit `640 x 480` (uncropped, design D3);
  - the review's seam case: that fit in a 640x480 back buffer gives `nv2a_present_rect` `(0, 0, 640, 480)`, no bar;
  - the same at scale 2 and 4 (every value times the scale; UV unchanged);
  - a texture larger than the frame (`tw > fw`, the D3D11 case): offsets and scales divided by `tw` and `th`, not by `fw` and `fh`;
  - `pad > 0` (Hor+) returns the whole frame;
  - a frame no wider than `2 * ov` guest px returns the whole frame;
  - `integer`, ov 9: the vertical cut rounded to 7 host rows (scale 1) and 13.5 → 14 (scale 2), rect `(9, 7, 622, 466)`, fit `622 x 466`; in a 1920x1080 window `nv2a_present_rect` gives the real multiple `2 x (622 x 466)` = `1244 x 932`, centred;
  - `nearest` with fit `fw x fh` in a 2560x1440 window gives the same 4:3 letterbox as the uncropped frame.
- [x] 1.3 `enhance.c`:
  - read `display.overscan` with `enhance_cfg_int` (0..64; above 64 clamps to 64 and below 0 to 0, each with a warning);
  - apply the Hor+ refusal on the parsed `o.aspect_w` after the aspect parse (design D2);
  - add ` display.overscan=N` to the summary line only when non-zero (D7).

  `enhance_cfg.c`: bind `RENV_DISPLAY_OVERSCAN`. `recomp_env.h`: `X(DISPLAY_OVERSCAN, CONFIG, "RECOMP_DISPLAY_OVERSCAN", NULL, "enhancements: display.overscan, guest px cropped from each side edge")`.
- [x] 1.4 `tests/enhance_cfg`: the key from the file and from `RECOMP_DISPLAY_OVERSCAN`, the clamp at 65 and at -1, a non-number, the Hor+ refusal with `display.aspect = "16:9"`, and an invalid aspect (`"16:9x"`, falls back to 4:3) that still crops.

## 2. Backends (toolkit)

- [x] 2.1 D3D11:
  - the blit shader's `uv_scale.zw` offset, named in the cbuffer comment;
  - `present_blit` fills it from `nv2a_present_crop` and passes `fit_w x fit_h` to `nv2a_present_rect`;
  - `d3d11_flip` forces the blit when `overscan > 0` (the `stock` test, the `same` shortcut and the `internal` `CopyResource`);
  - under `internal` with `integer`, the point sampler (matches Metal, design D3).
- [x] 2.1a `tests/d3d11_backend_smoke`: a crop case. A frame whose columns 0..8 and 9 have distinct colours is flipped at ov 9 into a back buffer the frame's size; `nv2a_pb_d3d11_back_pixel(0, y)` reads column 9's colour, and at ov 0 column 0's. It runs under Proton (D3D11 has no `window_shot`). There is no Metal present smoke (`nv2a_backend_smoke` runs headless with no presenter), so Metal is checked by `window_shot` in 5.2.
- [x] 2.2 Metal:
  - `struct fb_slot` gains `n` and `pad`; `xbox_FramebufferWindowBackTexture(w, h, n, pad)` from `metal_flip` (the drawn target's scale and pad); `fbm_upload` sets `n = 1`, `pad = 0`; `fbm_present` takes them;
  - a second pipeline with vertex function `vs_crop` and its `crop` uniform through `setVertexBytes`, used only when `overscan > 0` (at 0 the present is unchanged);
  - `fbm_present` passes `fit_w x fit_h` to `nv2a_present_rect`;
  - under `internal`, `nearest` is forced at 0 and under `integer` only.
- [x] 2.3 CPU rasteriser: one `display.overscan=N ignored by the CPU rasteriser` line (`nv2a_pb_exec.c`).
- [x] 2.4 `docs/runtime/config.md`: the key in the keys table, a per-key bullet (unit, the proportional vertical cut, the Hor+ refusal, the `linear` suggestion, captures unaffected except `window_shot`), and the env table row.

## 3. CLI (`xboxrecomp-cli`)

- [x] 3.1 `golden.py`: `ENHANCE_OVERSCAN_RE` and the `ENHANCE_STOCK` row with stock `"0"`; `manifest.py`: `display.overscan` in `TOOLKIT_ENHANCE_KEYS`.
- [x] 3.2 Tests: a log with `display.overscan=9` is not stock; a log without the key is stock; `--allow-enhance display.overscan=9` passes with a note.

## 4. cat

- [x] 4.1 `docs/env.md`: a `RECOMP_DISPLAY_OVERSCAN` row after `RECOMP_DISPLAY_MOVIE`, and in the "Config" line the count 50 → 51 (after main's `RECOMP_FILE_APC_DEFER`) and the enhancements list Twelve → Thirteen.
- [x] 4.2 `TASKS.md`: "CPU rasteriser: `display.overscan` (an SDL `srcrect` in `fb_present_sdl.c` present_pixels)".
- [ ] 4.3 This change's delta merged into `openspec/specs/enhancements/spec.md` on archive.

## 5. Gates and checks

- [x] 5.1 Gates:
  - `tests/posix_ctest.sh` with 0 FAIL, including `present_crop` and `enhance_cfg`;
  - the CLI's `uv run pytest tests` and ruff;
  - cat's `uv run pytest scripts` and ruff;
  - the Mac build with `XBOXRECOMP_ENHANCE` ON and OFF;
  - the Metal goldens and `blinx2 bench golden` on D3D11 under Proton, at stock, with the same verdicts as the base (the change touches the presenters);
  - `d3d11_backend_smoke` with the crop case under Proton (a Deck slot from the orchestrator first).
- [x] 5.2 SSX 3 on the Mac (Metal), title screen, `window_shot`:
  - at 0 identical to the base;
  - at 9 with no dark columns, and the art's left edge at window x 0 within one host pixel;
  - at 9 under `present.surface = internal`, the same;
  - at 9 with `RECOMP_DISPLAY_ASPECT=16:9` (once Hor+ reaches SSX 3's pin), the refusal line, and the border hidden in the pillarbox (D2).
- [x] 5.3 Proton (D3D11) on the Deck, SSX 3 title and race at 0 and 9, after the orchestrator's go:
  - the smoke case of 2.1a passes (D3D11 has no `window_shot`);
  - flips/s at 9 within 5% of 0 at scale 1 with `nearest`.
- [ ] 5.4 Review before merge.
- [ ] 5.5 Follow-up in the SSX 3 repo (separate change): `packaging/config.default.toml` gets `# overscan = 0` under `[display]`, with a comment that 9 hides the title screen's border and trims the same 9 columns a side from race frames.
