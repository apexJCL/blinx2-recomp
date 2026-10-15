## ADDED Requirements

### Requirement: R8B8 textures decode on every texel path
The shared texel decode SHALL decode NV097 texture format 0x29 (`SZ_R8B8`, swizzled) and its linear twin 0x16 (`LIN_R8B8`) as two bytes per texel, unsigned. The low byte is B and the high byte is R. Expanded to A8R8G8B8, R and A SHALL take the high byte and G and B the low byte, matching xemu's `GL_RG8` (G, R, R, G) table entry (GL and Vulkan) and Cxbx-Reloaded's `____R8B8ToARGBRow_C` (B, G, R, A = byte 0, byte 0, byte 1, byte 1). The Metal and D3D11 backends and the CPU sampler SHALL all decode it through this one table, so the three paths produce the same texels. The `SET_TEXTURE_FILTER` SIGNED bits are not applied, as for every other format today.

#### Scenario: Known texels
- **WHEN** a linear R8B8 texel holds the bytes `AB 12`
- **THEN** it decodes to `0x1212ABAB`, while G8B8 on the same bytes decodes to `0x12AB12AB`

#### Scenario: Swizzled level
- **WHEN** a 2x2 swizzled R8B8 level holds `01 10 02 20 03 30 04 40`
- **THEN** it decodes, row-major, to `0x10100101, 0x20200202, 0x30300303, 0x40400404` and occupies 8 bytes

#### Scenario: Spartan's lookup table is no longer magenta
- **WHEN** Spartan: Total Warrior binds its 256x256 R8B8 texture at 0x80720E00 during boot, on Metal or D3D11
- **THEN** no `texture format 0x29 ... not decoded: drawn magenta` line is logged and the texture is uploaded from guest memory

#### Scenario: Titles without the format are unchanged
- **WHEN** BLiNX 2 or Burnout 3 runs with the change
- **THEN** no texel it samples differs from main's, because neither title binds 0x29 or 0x16 (their main runs log no `not decoded` format at all) and every other decode case is untouched
