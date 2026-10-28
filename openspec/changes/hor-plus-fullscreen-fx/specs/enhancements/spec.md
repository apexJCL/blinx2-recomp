## ADDED Requirements

### Requirement: Render-target reads agree across GPU backends
A texture stage whose address is a live render target's (low 27 bits) SHALL sample that target in place, on D3D11 and on Metal alike, when it reads the bytes the target's surface holds: R5G6B5 (linear or swizzled) for an R5G6B5 surface, A1R5G5B5 or X1R5G5B5 for an X1R5G5B5 surface, any 32-bit format for a 32-bit surface; swizzled for a swizzled surface, and linear at the target's pitch for a linear one; never DXT. Any other read at that address SHALL decode guest memory. A target sampled as a format with no alpha (R5G6B5, X1R5G5B5, X8R8G8B8) SHALL read alpha 1, in every shader path.

#### Scenario: Burnout 3 speed blur at 16:9
- **WHEN** the race-gate route runs at `display.aspect = "16:9"` on Metal or D3D11
- **THEN** the speed-blur chain's 320x240 and 160x120 R5G6B5 targets are sampled as render targets, the full-width composite `C8AF571F` is placed as a stretch, and the host frame shows no step at the old 4:3 edges beyond the scene's own

#### Scenario: A read the target cannot serve
- **WHEN** a target's address is sampled in another colour layout (a 32-bit target as 16-bit, R5G6B5 as X1R5G5B5, any target as A4R4G4B4), in the other memory order, or as a linear texture at another pitch
- **THEN** the stage decodes guest memory on both backends. On Metal a 16-bit read decoded memory before too; on D3D11 this is stricter than before, when a matching texel size (and pitch, if linear) was enough, and since D3D11 writes no target back such a read shows black. Under `RECOMP_TRACE=aspect` each rejected (surface format, pitch, texture format, pitch) is logged once as `[aspect.rt-reject]`
