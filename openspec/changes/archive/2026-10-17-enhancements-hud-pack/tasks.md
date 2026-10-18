Worktrees: `wt/hudpack/{cat,xboxrecomp,xboxrecomp-cli}`, all on `feat/hud-pack` (rebased 2026-10-10: cat onto `main` ad53076, toolkit onto `posix-host/portability` c20a671, CLI onto `main` 10e5078). Packs and frame dumps go to `xbox-recomp/runs/hudpack/`, never inside a worktree. Mac builds with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`; runs under `notes/mac-run-lock.sh` with `SDL_AUDIODRIVER=dummy`.

## 1. Toolkit: pack reader and key (D1-D3)

- [x] 1.1 `src/kernel/nv2a_tex_pack.{c,h}`: `nv2a_tex_pack_load(path)` (header, index, bounds and sort checks, one-line refusal), `nv2a_tex_pack_count/scale`, `nv2a_tex_pack_find(hash)`, `nv2a_tex_pack_texels(entry)` (lazy, cached), `nv2a_tex_pack_hits()`. Added to `KERNEL_SOURCES`.
- [x] 1.2 `recomp_env.h`: `TEXTURES_PACK` row in `RECOMP_ENV_ENHANCE_KEYS`; `enhance_cfg.c` binds `textures.pack`; `enhance.c` reads it, resolves a relative path against the root, loads the pack and logs `[ENHANCE] textures.pack=none|<path> (<n> entries, scale <s>)`.
- [x] 1.3 Metal `tex_bind`: hash before upload on a miss; `tex_upload(t, hash)` takes the pack entry when one matches (size, levels, texels from the pack). Same change in D3D11 `tex_upload(e, t, hash)`.
- [x] 1.4 CPU rasteriser: `[ENHANCE] textures.pack ignored: ...` once, beside the `render.scale` line.
- [x] 1.5 ctest `tests/tex_pack` (standalone CMake, POSIX and Windows): a synthetic pack written by the test; load, find hit and miss, texels, a second entry, bad magic, bad version, out-of-bounds entry, unsorted index, truncated file, a path that does not exist; the hash of a fixed byte pattern equals the value the CLI's Python test checks (shared vector).
- [x] 1.6 Docs: `docs/runtime/enhance-config.md` (key row, env row, a "Texture packs" section), `docs/formats/texture-pack.md` (the format).
- [x] 1.7 Mac build of the toolkit tests: `tests/tex_pack`, `tests/enhance_cfg`, `tests/render_scale`, `tests/pb_tex_cache` (in the game build) pass. (2026-10-10, after the rebase: the full sweep `runs/hudpack/mac-ctest-branch.txt` matches the same sweep on `posix-host/portability` c20a671 line for line, plus `tex_pack` passing; the configure and build failures (d3d11/d3d8/nv2a smokes, input_*, kernel_directory/events/object_paths, mmio_decode, mmx_integer, xaudio2, pb_tex_cache standalone) are the base's. `guest_cpu` failed once on the base and passed on its rerun. `pb_tex_cache` from the game build: all checks pass.)

## 2. CLI: reading the game's assets (D6, synthetic tests)

- [x] 2.1 `src/xboxrecomp_cli/enhance/ipk.py`: the `IPK1` index, LZSS decode, `read_entry` (read-only). Test: an archive the test writes with a stored and an LZSS entry (encoder in the test).
- [x] 2.2 `enhance/dds.py`: DDS header (DXT1/3/5 FourCC, size, mip count), DXT1/3/5 block decode to RGBA rows. Test: hand-built blocks with known colours and alphas.
- [x] 2.3 `enhance/texhash.py`: `nv2a_tex_hash` in Python; the shared vector of 1.5.
- [x] 2.4 `manifest.py`: optional `[enhance.hud]` table (`archives`, `textures`, `scale`, `max_texels`, `font_atlas`, `font_rows`) with validation; `docs/manifest.md` section. Tests in `test_manifest.py`.

## 3. CLI: the scaler and the font (D4, D5)

- [x] 3.1 `enhance/scaler.py`: integer xBR 2x and 4x with alpha. Tests: a flat image is flat; a 2x2 checker gains the expected diagonal fill at the colour boundaries; output is identical across two runs and job counts; the kernel never emits a colour outside the input's range on a two-colour image.
- [x] 3.2 `enhance/font.py`: TrueType reader (head, hhea, hmtx, maxp, loca, glyf, cmap 4 and 12, composites) and the scanline rasteriser. Test: a minimal TTF the test writes (a square and a triangle), rasterised at a known size, coverage checked inside, outside and on edges.
- [x] 3.3 `enhance/atlas.py`: the stock layout measurement (ink bands, column runs, the run grouping against the font's widths, per-glyph ink boxes, per-band baseline and cap height) and the fitted rendering of each glyph to its stock ink box at scale; a missing glyph, a U+FFFD one and a run the fit cannot match keep the xBR pixels. Test: a synthetic atlas of bands with rectangles at known boxes and the test font; the rendered glyphs' ink boxes land on the stock boxes times 4, and a row-count mismatch is refused.

## 4. CLI: the commands (D6, D7)

- [x] 4.1 `enhance/pack.py`: the `XRTP` writer and `hud-pack.toml`. Test: write, then parse back with a reader in the test; the index is sorted; the bytes of a known texel are A8R8G8B8 little-endian.
- [x] 4.2 `enhance/hud.py` and `main.py`: `xbr enhance hud` with `--scale`, `--out`, `--font`, `--jobs`, `--only`, `--list`; help entry in `helptext.py`. Test: an end-to-end run on a synthetic game tree (archive with two DDS entries, one matching the patterns) writes a pack with one entry whose hash is the entry's data-block hash.
- [x] 4.3 `package --hud-pack [DIR]`: copies the pack to `enhance/hud.pack`, appends the `[textures]` key to the staged `enhance.toml.default` (macOS path variant), records it in the manifest. Test: `write_common` on a scratch payload with and without the flag.
- [x] 4.4 `golden.py`: `textures.pack` in `ENHANCE_STOCK` (stock `none`); `manifest.TOOLKIT_ENHANCE_KEYS` gains it. Tests: a log with a pack fails, with `--allow-enhance` passes with a note, `none` passes.
- [x] 4.5 `scripts/audit-public.sh`: `pack` in `DATA_EXT`. `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`, `scripts/audit-public.sh main..HEAD` clean.

## 5. Game (cat)

- [x] 5.1 `game.toml` `[enhance.hud]`: `archives = ["media"]`, the texture patterns (fonts, `b2_gamen_*`, `b2icon_*`, `pause_*`, `com_*`, `radar*`, `hub_*`, `slc_*`, `equip_*`, `sav_*`, `vs_*`, `tcrmes*`, `res_*`, `tankchip*`, `h_title*`, `icon_*`), `scale = 4`, `max_texels = 65536`, `font_atlas = "dds/font_arialnarrow_bold.dds"`, `font_rows` (the ten rows read off the dump; `^` and the box glyph as U+FFFD).
- [x] 5.2 `docs/env.md`: the `RECOMP_TEXTURES_PACK` row (Config count and the intro sentence), `docs/packaging.md`: `--hud-pack` and where the pack goes per target.
- [x] 5.3 `packaging/enhance.toml.default`: a commented `[textures]` section. `.gitignore`: `*.pack`, `enhance/`.
- [x] 5.4 `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`.

## 6. Mac verification (Metal)

- [x] 6.1 Build cat against the branch toolkit (`XBOXRECOMP_CLI_DIR=wt/hudpack/xboxrecomp-cli`, `../xboxrecomp` is the worktree's toolkit).
- [x] 6.2 `xbr enhance hud --out runs/hudpack/pack --font <LiberationSansNarrow-Bold.ttf>`: the entry count, the time taken, and that two runs give byte-identical packs. (268 entries, 145 MB, 8 s with 4 jobs; `--jobs 1` gives the same sha256 fde2eafd; `runs/hudpack/pack` and `pack-j1`. That pack predates the last CLI commit of the first round: the committed CLI, before and after the rebase, gives 37ea2fd8 with any job count. Redone with PT Sans in 9.3.)
- [x] 6.3 Metal `@stage1` with `RECOMP_TEXTURES_PACK=<pack>` and `RECOMP_RENDER_SCALE=2`: frame dumps into `runs/hudpack/`, read locally; the log line shows the entry count and hits; the HUD text, life bar and radar are sharper than the stock dump at the same flip; no magenta, no misplaced glyphs. (`runs/hudpack/metal-pack`: `textures.pack=... (268 entries, scale 4)`, 16 hits by the stage HUD; flips 841, 1321, 1900, 2200, 2500, 3000 read: name plate, `Time:`, the objectives text and `Press the A Button` in the fitted font, every glyph in place. The fb_dump of a 2x run is box-downscaled to 640x480, so the dumps understate the gain; the in-window frame is the test.)
- [x] 6.4 Stock Metal goldens (`blinx2 golden`) on the branch build with no key set: unchanged verdicts; the log shows `textures.pack=none`. (2026-10-10, `blinx2 golden run --backend metal`, `runs/hudpack/golden-metal`: attract pass, stage1 pass, story NEWVIEW on story-hub (tsedit and menu CLOSE), the state TASKS.md records for Metal story on main; every log has `[ENHANCE] textures.pack=none`.)
- [x] 6.5 dropped (user 2026-10-10: CPU backend not gated routinely; the CPU path's 'ignored' log line was checked by reading the code)
  (`nv2a_pb_exec.c`: the line prints once, beside the `render.scale` one, when a pack is loaded and the backend is the CPU or null one; `nv2a_tex_pack_find` and `nv2a_tex_pack_texels` are called only from the Metal and D3D11 `tex_upload`, so the CPU frame is the stock frame by construction.)

## 9. HUD font: PT Sans Narrow Bold

- [x] 9.1 Spec, design D5 and docs name PT Sans Narrow Bold (OFL 1.1) in place of Liberation Sans Narrow; `game.toml` `[enhance.hud] font = "PT Sans Narrow Bold"`; `docs/packaging.md` says where to get it (macOS ships it; ParaType or Google Fonts elsewhere). The font stays user-supplied, never vendored.
- [x] 9.2 CLI: TTC collections and the face's full name (name ID 4); `font` in `[enhance.hud]`, looked up by name in the host's font folders; `--font` takes a file or a name; the hint names the font; the manifest records `font_face`. The atlas grouping makes skipping a glyph cost more than any glyph, so PT Sans's narrow `[` is no longer swallowed by `\`; a glyph with no run is reported. Tests for all of it (423 pass).
- [x] 9.3 Pack with PT Sans (found at `/System/Library/Fonts/Supplemental/PTSans.ttc`, face 2 of 8): 268 entries, 4 s; `--jobs 1` gives the same sha256 54fb5c0f (`runs/hudpack/pack-pt`, `pack-pt-j1`). The fit's 150 glyph boxes equal Liberation's; 147 glyphs drawn (the stock `\` is a 4x17 stroke the font's 10x21 does not match: its xBR pixels stay, as designed).
- [x] 9.4 Metal `@stage1` with the PT Sans pack at scale 2 (`runs/hudpack/metal-pack-pt`): `textures.pack=... (268 entries, scale 4)`, 16 hits; flips 841, 1321, 1900, 2200, 2500, 3000 read, the objectives text, `Stick`, `Time:` and the counters in PT Sans, every glyph in place, no magenta. The pack's atlas (`atlas-pt.png`) read glyph by glyph, accents included.

## 7. Proton (D3D11)

Run 2026-10-10 in a Linux/Proton scratch tree (`~/xbox-recomp-hudpack`, its own prefix) at cat cee4219, toolkit 816794a, CLI dfc1e56; 7.4 at CLI 66696f1. Results in `runs/hudpack/`.

- [x] 7.1 Sync and build the branch on the Linux/Proton host; `tests/tex_pack` under `tests/proton_run.sh`. `bench build` OK; tex_pack 1/1 pass under Proton, the wrap cases included (`bench host-tex_pack.txt`).
- [x] 7.2 `blinx2 bench golden` on D3D11 with no key: unchanged. Attract, stage1 and story pass (runs 20261010-215810/215930/220122), all three logs `textures.pack=none`, the 12 Proton ctests pass (`bench host-golden-d3d11.txt`, `golden-d3d11/`).
- [x] 7.3 D3D11 `@stage1` with the pack (`RECOMP_TEXTURES_PACK`, scale 2): dumps compared with the Metal dumps of 6.3 at the same flips; the HUD alpha edges checked (D8 risk). Run 20261010-220630 (`d3d11-pack-pt/`): the pack loads (268 entries, scale 4), 8 hits by flip 4017 (Metal: 16; the hits count uploads, so cache residency differs); 0/4017 present mismatches. Flips 1321 (objectives text) and 2500 (HUD) show the same PT Sans Narrow glyphs as Metal, and the HUD panel, bar and text edges have no dark fringe. D3D11 dumps at the render size (1280x960), Metal's fb_dump at the guest size, and the timer differs by the run's timing, so the comparison is by eye, not by pixel.
- [x] 7.4 A Windows bundle made with `--hud-pack` launches under Proton with the pack line in its log. This first failed at the installer step: `nsis_lists` refused any payload subdirectory (`enhance/`). Fixed in the CLI (66696f1: each subdirectory gets its own SetOutPath; the uninstaller deletes its files and RMDirs it). The bundle (built on the Mac) installed silently into the scratch prefix, and the game log reads `textures.pack=enhance/hud.pack (268 entries, scale 4)` on D3D11 (`bundle-run/`).

## 8. Review and merge

- [x] 8.1 Merge review of the three branches (the reviewer out of quota): merge after fixes. A fuzz test under ASan/UBSan found the loader sound.
- [x] 8.1a Review fixes. Toolkit d9786b8: refuse more levels than `1 + floor(log2(max(w, h)))`, non-zero reserved bytes or entry flags; take an entry only at the guest texture's aspect; on a refused pack-size texture upload the guest texels (D3D11 makes the new texture before releasing the old one; both backends move the hash only after a successful upload); the hit line every 600 flips as the doc says; tex_pack refusal cases and enhance_cfg cases pinning the `textures.pack=` lines golden reads. CLI ddcf8cc: one pack entry per hash (equal texels kept once and said, different ones refused), `stage_hud_pack` takes an existing `enhance/`. Cat: `.gitignore` drops the unanchored `enhance/` (dist/ covers the default output) for `hud-pack.toml`; `export-public.sh` refuses `*.pack` and `hud-pack.toml`; packaging.md and enhance.toml.default say the pack turns on only on a first install, with the macOS path. Mac gates: ctests tex_pack, enhance_cfg (222 checks), render_scale under ASan/UBSan; CLI `pytest tests` 424 pass plus the known test_parity_pacing failure, ruff and audit clean; cat `pytest scripts` 27 pass, ruff clean; Metal @stage1 with the PT pack at 2x (`runs/hudpack/metal-pack-pt-fix`): 268 entries, 16 hits as before, six hit lines instead of 3914, every glyph drawn, frames match `metal-pack-pt` but for game-timer drift; stock Metal golden (`runs/hudpack/golden-metal-fix`): attract, stage1, story pass, `textures.pack=none`.
- [x] 8.1b D3D11 recheck on the Linux/Proton host (scratch tree `~/xbox-recomp-hudpack`): the first compile of the D3D11 `tex_upload` change builds clean. tex_pack passes under Proton; enhance_cfg's new cases failed there on the CRT's "\r\n" stderr, fixed in toolkit a8a88b8, then pass (`bench host-tex_pack-fix.txt`). D3D11 `@stage1` with the PT pack at 2x (run 20261010-223437, `d3d11-pack-pt-fix/`): 268 entries, 8 hits as in 7.3, the hit line every 600 flips, 0/4013 present mismatches; flips 1321 and 2500 draw every PT Sans Narrow glyph and match `metal-pack-pt-fix` but for the timer. Stock D3D11 golden (`bench host-golden-d3d11-fix.txt`, `golden-d3d11-fix/`, runs 20261010-224041/224201/224352): tests pass; attract, stage1, story pass, all `textures.pack=none`.
- [ ] 8.2 After the merge: copy the agent's notes to `notes/hudpack/`, copy the runs referenced here to `runs/`, remove the worktrees, keep the branches, sync and rebuild the Linux/Proton host, run golden, update `TASKS.md`.

## State (2026-10-10, ready to merge)

Heads: toolkit a8a88b8, CLI ddcf8cc, cat (this commit), all `feat/hud-pack`. Review fixes, the Mac gates (8.1a) and the D3D11 recheck (8.1b) are done. At the merge, re-pin `game.toml` to the merged CLI sha.
