## 1. Measure the sampled region (D1)
- [x] 1.1 Write `wt/hudfont/tools/probe_pack.py` (local, never committed; to `notes/hudfont/` after the merge): a 4x pack holding only the font atlas's hash, with rings painted around every stock ink box in grey levels (ink box 255; 1st, 2nd and 3rd-plus guest px out to the slot 191, 127, 63), alpha 255, built on `atlas.measure`.
- [x] 1.2 Run Metal `@stage1` at `render.scale` 2 with it through `notes/mac-run-lock.sh` (`SDL_AUDIODRIVER=dummy`), capture one HUD frame with `RECOMP_DEBUG=window_shot=<flips>` (else `fb_dump`) into `runs/hudfont/probe/`, and read the margin per side, across and down, and whether it is the same for every glyph.
- [x] 1.3 Record the region `A` in NOTES.md and as a result line under D1 in design.md. Bare ink box, or no frame at all → stop and hand back with the frame and `simulate.py`'s output (gate). A margin short of the slot → `[enhance.hud] font_margin` in `game.toml` (smallest margin seen per side); the slot → no key.

## 2. CLI fit (D2-D4), in `wt/hudfont/xboxrecomp-cli`
- [x] 2.1 `enhance/atlas.py`: one proportional scale from the cap height on both axes; centred float origin on the baseline; a one-sided overrun shifted inward within the slack first; a remaining overrun shrunk uniformly about the centre and the baseline, silent within `FIT`, named beyond it; never enlarged; the 0.4-2.5x guard kept; `render()` takes the margin (default the slot); module docstring updated.
- [x] 2.2 `hud.py` reads `[enhance.hud] font_margin` and passes it; the font-wide note line and the per-glyph notes beyond `FIT` printed as now.
- [x] 2.3 Tests D5.1-D5.8 in `tests/test_enhance.py`, game-agnostic; `test_atlas_fit` replaced.
- [x] 2.4 `docs/manifest.md`: the `font_margin` row and the fit described as proportional; `__version__` 0.6.3; local tag `v0.6.3` on the commit (the public tag goes out in the next push round, the CLI's before cat's).
- [x] 2.5 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`, `bash scripts/audit-public.sh a018aea..HEAD`; public identity on every commit.
- [x] 2.6 D8: `[enhance.hud] font_stretch` and `font_full_height` in `enhance/atlas.py` and `hud.py`, with their tests in `tests/test_enhance.py` and rows in `docs/manifest.md` (CLI 6b451a3, still v0.6.3).

## 3. Verify on the owner's dump (D6)
- [x] 3.1 Font-only packs `runs/hudfont/pack-before` (CLI a018aea) and `pack-after` (branch).
- [x] 3.2 Atlas contact sheets and `runs/hudfont/stems.txt` (stem widths and capital heights, before and after).
- [x] 3.3 Metal `@stage1` at render scale 2 and 3 with each pack, frames via `window_shot`; 1:1 crops of `Stick`, `Time:` and `Press the A Button` in `runs/hudfont/crops/`. Nothing published; the README image only with the user's approval.
- [x] 3.4 Metal goldens unchanged.
- [x] 3.5 Hand the crops to the user; the merge waits for their verdict on weight, distortion, gaps and the shrunk glyphs' height. The first crops (`runs/hudfont/crops/`) were approved on 2026-10-12 ("looks amazing, now text looks more homogeneous"); the baseline fix after the review changes the descenders and brackets, so `runs/hudfont/crops2/` waits for the user's look. The crops2 review (merge on hold) found the brackets low against the caps and wide gaps around `E S O`; D8 adds `font_stretch` and `font_full_height` (CLI 6b451a3, `runs/hudfont/pack-after3`, mocks in `runs/hudfont/mock/`); `runs/hudfont/crops3/` (true stock / after2 / after3) and the `R` edge check (a render-scale filtering artefact, also in stock) are done; the merge waits for the user's look and their `font_stretch` choice. Approved by the user on 2026-10-12: `runs/hudfont/crops3/` (v3) is aligned like the original and the parentheses are faithful to the typeface; `font_stretch = 10` is kept.

## 4. Game side, in `wt/hudfont/cat`
- [x] 4.1 `game.toml`: pin CLI v0.6.3 (tag and commit); `font_margin` if 1.3 produced it; `font_stretch = 10` and `font_full_height = "()[]{}"` (D8); the comment above `[enhance.hud] font` updated with the probe's result.
- [x] 4.2 `uv run pytest scripts`, ruff check and format.
- [x] 4.3 `pt review ITEM --summary ...` with the paths and numbers.

## Follow-ups
CLI items deferred to a later CLI release (none blocks this merge):
- A command-level test that `enhance hud` passes `font_stretch` and `font_full_height` through to `render()`.
- When the fit factor reaches `f <= 0` (`enhance/atlas.py:421`), keep the stock pixels and add a note, as the 0.4-2.5x guard does.
- In the manifest's `_check_values`, warn about `font_full_height` characters that are in no `font_rows`.
