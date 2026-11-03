## Why

Frame dumps take most of the disk the project's runs use. The toolkit's
dumpers (`write_bmp32` in `nv2a_pb_d3d11.c`, the Metal dumper) write
uncompressed BMP: 1.2 MB a frame at 640x480 (32 bpp), 2.2 MB at 1120x480.
A golden that keeps a pass-with-known story run still holds about 110 MB,
and the Mac's `runs/` trees from HUD and Auto Modellista work hold thousands
of BMPs each. The same pixels as PNG take a quarter of that or less, and
lose nothing.

## What changes

- The dumpers stay BMP. A BMP is a copy in the render path and costs the
  game no time; a PNG encoder there would.
- The CLI converts the frames a command keeps into PNG once the run is
  over, on the machine that keeps them:
  - `bench golden`, after its pull, check and prune;
  - `golden run`, after the Mac run lock is released;
  - `hud-map capture` and `hud-map check` (the check now writes its sheets
    after the conversion, outside the lock);
  - cat's `scripts/shots/run.sh`, before its contact sheet.
- Each conversion is lossless and checked: the PNG is read back from disk
  by a decoder of its own and compared with the BMP's pixels, and only an
  exact match removes the BMP. The base name stays (`flip_01139.bmp` ->
  `flip_01139.png`), and the PNG takes the BMP's mtime.
- Opt-out: `--bmp-frames` (bench, golden run, hud-map) or `XBR_FRAMES_BMP=1`
  (the environment, or `scripts/bench.env` for bench).
- Every frame reader takes either format, the PNG first: golden's dump
  lookup, window and prune (`flip_NNNNN.{bmp,png}`), hud-map's capture
  frames and sheets, cat's `sheet.sh` and `strip.sh`. The golden compare
  reads the same pixels either way, so its metrics are the same.
- A new verb, `<game> frames compact [--dry-run] [--jobs N] [--pins FILE]
  [--no-pins] DIR...` (also `xbr frames compact` outside a game), for frames
  already on disk. It touches nothing outside the DIRs and follows no link.
  It leaves alone the files that `golden.json` cites by name, path, or run
  stamp, and those the game's reference text (benchdb's sources: TASKS,
  RESUME, openspec, notes) cites by path, folder or run stamp.
  `--dry-run` prints the bytes it would save and the files it leaves.

## Not in scope

- Running `frames compact` over the real `runs/` and `bench-logs/`. That is
  the user's call, once this lands.
- PNG in the toolkit's dumpers.
- Converting on the PC or the Deck before the pull (see design D1).
