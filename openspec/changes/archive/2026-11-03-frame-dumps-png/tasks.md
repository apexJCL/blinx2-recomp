## 1. CLI (`xboxrecomp-cli` `feat/frames-png`)

- [x] 1.1 `frames.py`: BMP reader (24/32 bpp, both row orders, alpha), SWAR per-row-filter encoder, independent decoder, checked convert, compact, after-run hook, `XBR_FRAMES_BMP`
- [x] 1.2 `frames compact` verb in `main.py` (game-free; golden.json default pins); helptext, README, `docs/commands.md`
- [x] 1.3 Readers: golden (`frame_path`, `flip_path`, `dump_image_path`, window, prune names, `read_png` via the new decoder); hud-map (capture frames, sheet frames, capture cleanup)
- [x] 1.4 Hooks: `bench golden` (after check and prune), `golden run` (after the lock), `hud-map capture` and `check` (check's sheets after the conversion); `--bmp-frames`
- [x] 1.5 `tests/test_frames.py`: SWAR filters vs per-byte, PNG round trip vs a naive decoder, BMP orders and alpha, mismatch and conflict keep the BMP, compact dry-run, pins, links, opt-out, reader fallback, golden check output unchanged after compact
- [x] 1.6 Gates: `uv run pytest tests`, ruff check and format

## 2. cat (`feat/frames-png`)

- [x] 2.1 This spec
- [x] 2.2 `scripts/shots/sheet.sh`, `strip.sh`: PNG else BMP; `run.sh`: `blinx2 frames compact` before the sheet (`XBR_FRAMES_BMP=1` skips it)
- [x] 2.3 `scripts/test_shots.py`; gates: `uv run pytest scripts`, ruff

## 3. Verify

- [x] 3.1 Encoder size vs `sips` on real frames (D2 table: 0.84-0.97x)
- [x] 3.2 A `cp -c` copy of a real run (bench-logs 20261101-072943, story, PC D3D11): `golden check` output identical before and after compact; 114.3 MB -> 24.4 MB
- [x] 3.3 One PC D3D11 golden through this CLI (CLI 6acce1d, exe 122818b3d686): attract pass-with-known, stage1 pass, story pass-with-known (only); attract 14 and story 100 PNGs landed (17.2 -> 4.5 MB, 122.9 -> 25.7 MB); a re-check of the PNGs matches each run's golden.txt
- [x] 3.4 Review before merge: mergeable, with the fixes in 4

## 4. Review fixes

- [x] 4.1 Alpha: dropped only when 0 in every pixel (a constant 0xFF is RGBA); `-alpha off` in `sheet.sh` and `strip.sh`; tests
- [x] 4.2 Only the 40-byte BMP header is taken (V4/V5 left as BMP); test
- [x] 4.3 Pins from benchdb's reference text (game.toml sources): cited paths, folders and stamps stay BMP; the dry run lists them; tests, and a dry run on a `cp -c` copy of `runs/hor-plus-fx/b3` (78 of 78 pinned)
- [x] 4.4 `os.link` into place (no clobber), directory fsync before the BMP goes; test
- [x] 4.5 zlib level 6
- [x] 4.6 `bench golden` and `golden run` warn when a worktree's `bench-logs/` is a folder, not the store's link; test
- [x] 4.7 Rebased on cat main 4c3a5b54; gates
