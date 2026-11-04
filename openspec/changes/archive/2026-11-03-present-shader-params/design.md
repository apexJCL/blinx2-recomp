## Parameters

librashader (v0.12, dlopened) reads a preset's `#pragma parameter` lines.
`libra_preset_get_runtime_params` returns name, description, initial,
minimum, maximum and step for each. A probe against the bundled library
showed the following (scratch probe, the tracker item comment):
- `initial` is the effective preset value. It includes a value that a
  `#reference` wrapper sets (`warpX = "0.01"` gives `initial = 0.01`). So
  the wrapper defaults below are what *Reset to preset* returns to, and
  the upstream value stays in the vendored file.
- `libra_preset_get_param` returns only values the preset sets explicitly,
  so it is not used.
- `libra_*_filter_chain_set_param` with a name the chain lacks returns
  `UnknownShaderParameter`; `libra_preset_set_param` does not (an earlier
  probe tried only the preset call). The backends send only the names of
  the table read off the chain's own preset, so they never hit it.

A Metal chain probe against the branch's build (review of 2026-10-29)
confirmed it end to end: for the bundled `crt-lottes.slangp`, `initial`
and the chain's `get_param` after create are both warpX 0.01 and warpY
0.02; for the vendored `crt/crt-lottes.slangp` both are 0.031 and 0.041.

The bundled presets have these parameters:

| preset | parameters |
|---|---|
| crt-lottes | hardScan, hardPix, warpX, warpY, maskDark, maskLight, scaleInLinearGamma, shadowMask, brightBoost, hardBloomPix, hardBloomScan, bloomAmount, shape |
| crt-lottes-fast | MASK, MASK_INTENSITY, SCANLINE_THINNESS, SCAN_BLUR, CURVATURE, TRINITRON_CURVE, CORNER, CRT_GAMMA |
| crt-hyllian | MASK_INTENSITY, gammas, BRIGHTBOOST, SCANLINES, SHARPER |
| fsr | FSR_SHARPENING and the film grain parameters |

The mask controls are already parameters (`shadowMask`, `maskDark`,
`maskLight`, `MASK`, `MASK_INTENSITY`). No preset has a convergence or
chromatic offset parameter, so the menu shows none.

## Store

`nv2a_present_chain` already owns the request and the library handle. It
gains, under its spin lock:
- the **active table**: up to 64 rows (name, description, initial, min,
  max, step). The backend publishes it, with the preset key and the chain
  gen, when it builds a chain. A failed build or a chain release clears it;
- the **overrides**: `{preset key, name, value}` rows, with the value last
  loaded or saved, so the menu can tell what is unsaved;
- a **parameter generation**, which every set, reset and publish bumps.

Each frame the backend compares that generation with the one it applied
last. When they differ it calls `set_param` for every active parameter with
the override or the initial. It does the same right after it creates a
chain. Setting a parameter to its initial removes the override, so the
config never holds a value equal to the preset's.

Preset key: the bundled name (`crt-lottes`), or for a path the file's stem
sanitised to `[A-Za-z0-9_-]`. The key is what the config section names.

## Config shape

```toml
[present.shader_params.crt-lottes]
warpX = 0.0
maskDark = 0.6
```

i.e. the dotted key `present.shader_params.<preset>.<param>`. At init the
enhancer reads every key with that prefix from the defaults, user and title
layers, in that order, and the later layer wins. The menu's Save writes the
current overrides of every preset as differences: a key whose override was
removed is deleted from the user file. A value is always written with a
decimal point. These keys belong in the user file. A title file may carry
them, but Save writes only to the user file.

## Menu

A new page, **Shaders**, comes after Render:
1. the Shader picker, moved from Render (the same item and key);
2. one range row for each active parameter. The label is the description,
   or the name when the description only repeats it. The value is shown at
   the step's decimals, and the footer shows `min..max`;
3. *Reset to preset*, which removes the active preset's overrides.

The parameter rows are their own row type (not item slots), built from the
store each time the page is laid out, so a new table or a new value shows on
the next redraw. The generic item save never sees them: the store saves
them. When no shader runs, or when one
is loading or has failed, an info row says so. The Save page's *Reset to
defaults* also clears every override. Parameters of other presets are kept
until they are reset or saved.

## Dump

`RECOMP_MODS_DESCRIBE=json` gains:

```json
"shaders": {
  "active": "crt-lottes",
  "presets": [
    {"name": "crt-lottes", "params": [
      {"name": "warpX", "label": "warpX", "min": 0, "max": 0.125,
       "step": 0.01, "default": 0.01, "value": 0.01,
       "key": "present.shader_params.crt-lottes.warpX"}]}]
}
```

To fill it, each bundled preset is parsed without a GPU (preset create
plus runtime params). The field is empty when the library is missing.
Schema stays 1, because a field was added and none was changed.

## Fringing

Cause (code, confirmed with shots in `runs/shader-params/`):
1. The SteamOS `launch.sh` sets `RECOMP_HOST_GAMESCOPE=1`, so
   `present.surface = auto` resolves to `internal`.
2. Under `internal`, D3D11 sizes the window and the swap chain to the frame
   (640x480 at 1x), and Metal keeps the drawable at the frame's size.
3. The chain draws into that frame-sized surface, and gamescope scales the
   result to 1280x800 (x1.667, bilinear).
4. crt-lottes draws its shadow mask per output pixel and its scanlines per
   source line, so resampling them by a non-integer factor gives colour
   fringes and moiré. On the Deck shot (`present_01100.bmp`, 640x480) the
   mask triads are 3 px wide before the scale.

Fix: while a chain is wanted and built, `internal` behaves like `window`
for the surface. Both backends gate on the built chain, so a missing
library or a broken preset never resizes the surface for the frame its
build takes to fail:
- D3D11: under gamescope or fullscreen the client area takes the monitor's
  size. Otherwise the swap chain follows the client area. `internal_resize`
  is skipped, and leaving fullscreen sizes the window as under `window`.
- Metal: the drawable follows `SDL_GetWindowSizeInPixels`.

With the chain off, the frame-sized surface comes back the next frame. Stock
(no shader) is unchanged.

`render.scale > 1` with an output smaller than the scaled frame still
aliases the scanlines. That case is documented, not changed.

## Curvature defaults

The wrappers in `assets/shaders/` set the following, and
`assets/shaders/README.md` names the upstream values:
- crt-lottes: `warpX = 0.01`, `warpY = 0.02` (upstream 0.031 and 0.041).
  Both sit on the parameters' 0.01 step grid, so the menu shows them as they
  are and steps from them evenly;
- crt-lottes-fast: `CURVATURE = 0.01` (upstream 0.02).

## Known limits

- **Title and defaults overrides come back.** An override loaded from the
  title or defaults layer counts as saved, like one from the user file.
  Moving its slider back to the preset's value, *Reset to preset* or
  *Reset to defaults* removes it for the session, and Save deletes the
  user file's key only. At the next start the title (or defaults) value
  loads again. To drop it for good, remove it from that file. The game
  ships no such keys. Flagging such rows in the menu was left out: the
  store would need each override's layer, for a case no shipped file has.
- **One key per file stem.** A path preset is keyed by its file stem, so
  `mods/foo/crt-lottes.slangp` shares overrides with the bundled
  `crt-lottes`. Rows for parameters the other preset lacks are kept and
  ignored; shared names apply to both. Keying by full path would make the
  config section unreadable and break when an install moves.
- **Override table size.** It holds 256 rows over every preset. A row
  with no value and none on disk is reused when the table is full; past
  that, a new override is refused with one log line and the slider does
  not stay off the preset's value.
