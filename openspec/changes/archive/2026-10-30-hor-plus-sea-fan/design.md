## Cause

Probes on Metal at 16:9 (`runs/blinx-sea/`) ruled out the renderer:

- The square read mapping, the scissor, depth, CLIPPLANE kills and the
  stage samplers do not set the cut. With magenta textures and depth
  off, the water program's (0xBCAF4F3A) fragments still stop on the same
  lines.
- The wave grid (`sub_002171C0`, `sub_002177E0`) does not set it either.
  Scaling its rectangle x3 leaves the coverage the same.
- The water batch's own vertices do. The batch has 1218 vertices, 42 rows
  of 29, with y 0, z from -0.13 to 258.6 and x from -199 to 199. Each row
  spans `0.78 + 0.767 z`. That projects to NDC x of about +/-1.21 against
  the frame's +/-1.33.

A write watch on the buffer (guest 0x80C9D000) names the builder:
`sub_00215A40` (eax is the sea object), called once per stage from
`sub_00215EA0`. It:

- creates a vertex buffer of 0x3918 bytes (`+0x4C`);
- derives each row's depth and half-width from the object's view angle
  (`+0x58`, 1.0472) and its aspect (`+0x5C`, 4/3);
- writes rows of 29 xyz floats;
- stores the vertex count at `+0x50`.

## Fix

A wrapper, written like the cull wrapper (`sub_0003B180`), that
shares its `cull_init` and `s_cull_scale`:

- It calls the generated body first.
- If the build succeeded (eax is not negative and `+0x4C` is set), it
  divides each vertex's x by `s_cull_scale`. That is a multiply by
  A/(4/3).
- It finds the vertices through the buffer's `Data` field (`+4`,
  physical, ORed with 0x80000000).

Why scale x and not the angle: the half-width is linear in z, so
scaling x opens the fan's tangent by exactly the frame's factor and
keeps the stock margin. Scaling `+0x5C` would also do it, but that field
feeds the row spacing through `fptan`, so the result is less direct to
check.

The texture coordinates follow on their own: the vertex program builds
oT0 from the world position, and oT1, oT2 and oT3 from the screen
position and the eye vector.

## Backends

The change is game-side and changes vertex data only, so D3D11, Metal
and the CPU rasteriser all see it.
