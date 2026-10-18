## ADDED Requirements

### Requirement: Every render path keeps one target per surface, clears its clear box and presents the frame

A GPU backend SHALL keep one render target per guest surface (colour offset
and pitch), as large as any clip the title drew it with, keeping its contents
when it grows; a backend that seeds targets from guest memory SHALL seed the
grown margin the same way. Every render path (CPU, D3D11, Metal) SHALL bound
a colour clear by the surface clip and, once the title has sent
SET_CLEAR_RECT, by the clear rect, and SHALL leave the rest of the target as
it was. A flip SHALL present only the walker's present extent of the target,
and the walker's pick SHALL NOT change: a surface is still the colour offset
at a clip size, fresh for PRESENT_STALE_FLIPS (120) FLIP_INCREMENT_WRITEs.

#### Scenario: One back buffer, several clips

- **WHEN** a title draws its 640x480 back buffer under a 160x120 clip at
  (100, 100) and clears it there
- **THEN** Metal keeps one 640x480 target for the surface, and only the clip
  changes colour, on Metal and on the CPU path alike

#### Scenario: Clear rect

- **WHEN** a clear is sent with a clear rect of (300, 300)-(339, 339) inside a
  640x480 clip
- **THEN** only that rect changes colour, on every path

#### Scenario: Grown target keeps its contents and seeds its margin

- **WHEN** a surface drawn under a 320x240 clip is then cleared under a
  640x480 clip with a clear rect covering only (320, 240)-(639, 479)
- **THEN** Metal grows the target to 640x480; the 320x240 drawn before the
  grow, the cleared rect, and the guest bytes elsewhere all read as the CPU
  path leaves them

#### Scenario: Grown target, smaller frame

- **WHEN** a target grown to 640x480 is presented after the title draws only
  320x240 for more than 120 flips counted at FLIP_INCREMENT_WRITE
- **THEN** the flip shows 320x240, and the target is still 640x480

#### Scenario: Whole-clip clears take the stock path

- **WHEN** a title clears a surface whose clip is the whole target and has
  sent no clear rect, or one covering the clip
- **THEN** Metal clears it with the pass's load action, as before this change
