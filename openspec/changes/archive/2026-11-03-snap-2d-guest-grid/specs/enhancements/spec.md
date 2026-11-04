## ADDED Requirements

### Requirement: 2D textures on the guest grid
`render.snap_2d` (env `RECOMP_RENDER_SNAP_2D`, default `false`, live) SHALL do the following above `render.scale` 1 on Metal and D3D11. A bilinear texture stage on a 2D batch SHALL sample at its guest pixel's 1x sample point, with gradients equal to the 1x ones.

A batch is 2D when either:
- it is pre-transformed; or
- it is a program batch whose scanned vertices share one whole `oPos.w` and one `oPos.z`.

In addition, the batch must be on an unpadded target or centred on a padded one. The stage's mapping must be axis-aligned, with u along x and v along y.

The snap SHALL leave alone render-target stages, 3D batches, STRETCH and COVER placements, and 90-degree mappings.

While it is on, the walker SHALL NOT merge back-to-back batches.

With the key off, the backends SHALL compile the same basic and combiner shader texts as before the key existed. They SHALL write the same constants and do no 2D scan beyond the one Hor+ runs.

#### Scenario: Stock run unchanged
- **WHEN** JSRF runs the dogenzaka golden on D3D11 on the Deck with `render.snap_2d` off
- **THEN** every checked frame is EXACT, as on the toolkit before the key

#### Scenario: Seams gone at scale 2
- **WHEN** BLiNX 2 shows its loading screen at `render.scale` 2 with `RECOMP_RENDER_SNAP_2D=1`
- **THEN** no light line shows between the loading-screen tiles, and the snap shader variants build with no `FAILED` line
