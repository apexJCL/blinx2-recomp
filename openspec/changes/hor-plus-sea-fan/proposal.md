## Why

The tracker item: under Hor+ (`display.aspect` wider than 4:3) the far sea in
stage 1-1 loses its reflection and colour near the frame's sides. The
cut follows two slanted, slightly curved lines at about guest x -72 and
708 (host 35 and 815 of 854 at 16:9). Outside them only the flat, dark
base sea remains. Seen on native D3D11 (Windows playtest) and on Metal.

## What changes

- The game builds the far sea as a fan of vertices in the camera's yaw
  frame (`sub_00215A40`). The fan is sized to the 4:3 view plus a small
  margin. A wrapper in `src/recomp_manual.c` scales every vertex's x by
  A/(4/3) after the build, so the fan covers the wide frame.
- Stock (4:3, or no enhancements layer) is unchanged: the wrapper calls
  the generated body and returns.
- No renderer or toolkit change.

## Impact

- cat `src/recomp_manual.c` (a new wrapper; `blinx2 analyze` and `blinx2 recomp` rename the body to `sub_00215A40_gen`).
- Goldens run at stock, where the wrapper does nothing. They still run
  because the change touches recompiled code.
