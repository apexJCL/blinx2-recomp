## D1. Where the conversion runs: the Mac, after the pull

Remote hosts would turn their frames into PNG before the pull. They do
not, for these reasons:

- **The pulls are small.** `bench golden` pulls only `pulls.txt`'s flips
  plus each frame's plain dump, tens of MB a session over the LAN.
  Converting first would save seconds.
- **The remote frames are transient.** prune removes the host's `frames/`
  of every passing stamp. A failing run's frames stay there only until
  `bench gc`.
- **Converting remotely would compete with the lock.** Outside the run lock,
  the encode (CPU work on every core) would slow another agent's locked
  run, and its pace check would read INCONCLUSIVE. Inside the lock, it would
  lengthen every hold on a shared bench.
- **The Windows PC has no guaranteed Python.** Its bench scripts are
  PowerShell (`bench/host/windows/*.ps1`). An encoder there would be a
  second implementation that needs its own checks.
- **The Mac keeps the frames, and pays for them.** All the measured disk
  use (`runs/`, `bench-logs/`) is on the Mac.

A pre-pull conversion is a follow-up, for the day when pulls get large.

## D2. Encoder: per-row filters, standard library only

`frames.encode_png` computes all five PNG filters (None, Sub, Up, Average,
Paeth) for the whole image at once. Each row then gets the filter with the
smallest sum of |signed residual|, the libpng heuristic. The result goes
through `zlib.compress(raw, 9)`.

The filters run as SWAR on Python big integers: all the image's bytes go
in one int, and the byte-lane subtract and average are mask arithmetic.
The encoder's inputs are the original pixels, so no row depends on the
previous row's result. Paeth needs comparisons, so it runs on 16-bit lanes
with a bias bit.

Tests check each SWAR filter against the plain per-byte formula,
including the 0/127/128/255 corners.

Measured on real frames (one core, M-series Mac):

| frame | BMP | `sips` PNG | this PNG | encode | decode |
|---|---|---|---|---|---|
| D3D11 640x480, 32 bpp | 1,228,854 | 294,704 | 248,265 (0.84x sips) | 0.31 s | 0.12 s |
| Metal 854x480 host, 24 bpp | 1,230,774 | 316,857 | 282,614 (0.89x) | 0.21 s | 0.15 s |
| Metal 1120x480, 32 bpp | 2,150,454 | 982,558 | 949,694 (0.97x) | 0.20 s | 0.19 s |

The table is at zlib level 9. After review the encoder uses level 6:
on an 854x480 host frame it encodes in 0.10 s instead of 0.16 s for 0.3%
more bytes (593,726 vs 592,032); the review measured about 4x faster
for 4% more on its sample.

Conversions run in a process pool (default: the CPU count minus one, at
most 8).

## D3. The check uses an independent decoder

`frames.decode_png` is separate code from the encoder:

- Up is a SWAR byte add.
- Sub is `itertools.accumulate` on each channel.
- Average and Paeth are plain loops.

The check runs on the bytes read back from disk after the write and
fsync. The PNG then takes its name with `os.link`, which fails on an
existing name, so a PNG another writer made meanwhile is never overwritten
(a check followed by `os.replace` would leave that window). The directory
is fsynced before the BMP is removed. The tests also decode with a third, naive
reference unfilter. `golden.read_png` now uses this decoder, which is also
faster than its old per-byte loop for filtered rows.

## D4. Alpha

In the 32 bpp dumps the fourth byte is BI_RGB's reserved byte. The
dumpers write the render target's alpha there, and it is 0 in every
sampled dump. When it is 0 in every pixel, the PNG is RGB (type 2):
every reader reads RGB, and the golden hash covers the RGB pixels.
Otherwise, a constant 0xFF included, the PNG is RGBA (type 6). Either way,
no byte of pixel data is lost. `sheet.sh` and `strip.sh` pass
`-alpha off`, so an RGBA PNG draws opaque, as its BMP did.

## D5. What a conversion never does

Any failure keeps the BMP and names it on stderr:

- A mismatch keeps the BMP and leaves no PNG. Exit 1 for compact, and a
  warning line for the run hooks, whose verdict it does not change.
- A PNG of the same name with other pixels is a conflict: both are kept.
  One with the same pixels counts as "already PNG", and the BMP goes.
- An unsupported BMP (compressed, not 24 or 32 bpp, or a header other
  than the 40-byte BITMAPINFOHEADER) is kept. A V4 or V5 header carries a
  colour space, an ICC profile or a resolution the PNG would drop.
- Links are never followed, and nothing outside DIR is touched.
- A failed write leaves no temp file.

## D6. Pins

A cited dump stays BMP, so a citation keeps naming a file on disk.

`golden.json` cites the runs its references were recorded from, in prose
("reference run 20261003-005602", "D3D11 run 20261004-050144"), and
`golden reference` reads those dumps by name. golden.json and each
`--pins FILE` pin a file by:

- its base name, or its stem with `.png`;
- its path under DIR;
- the `YYYYMMDD-HHMMSS` stamp of a directory on its path.

Specs, TASKS, RESUME and the workspace notes cite dumps under `runs/` by
path too (`runs/hor-plus-fx/b3/host-after/host_07000.bmp` in
mod-connectivity-layer's tasks). compact reads the same reference text
benchdb reads, through benchdb's own reader (`benchdb.refs.read_refs`),
so the two cannot drift and the list stays in game.toml: golden.json,
TASKS.md, RESUME*.md, openspec/, the seeds and `[bench.gc] refs` (cat's
names `../notes`) less `refs_exclude`, in the main checkout and the
worktree compact runs from. From that text a file is pinned by:

- a path of two parts or more that ends in it;
- a folder path (two parts or more) naming a directory it is in. `runs/`
  and `bench-logs/` themselves, the game root and the folders above it
  are never "cited": naming the store is not citing what is in it;
- a run stamp, as above.

A bare base name in prose pins nothing, as benchdb's names do not. The
reader never refuses: a source it cannot read is named on stderr, and a
gap only converts a dump that every reader still finds, as PNG.
`--dry-run` lists each pinned file and why. `--no-pins` drops both
defaults. The run hooks apply no pins: they convert a
run that has just finished.

## D7. Opt-out

`XBR_FRAMES_BMP=1`, or `--bmp-frames`, on bench, golden run and hud-map.
The opt-out only skips the conversion; the readers take BMP as they
always did. `frames compact` itself ignores the variable: running it is an
explicit request.
