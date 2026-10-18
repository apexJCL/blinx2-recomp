## ADDED Requirements

### Requirement: PGRAPH 0x400B10 follows the executor when no fence mirror is registered
When no fence mirror is registered (`g_fence_mirror_count == 0`) and the executor has run at least one `BACK_END_WRITE_SEMAPHORE_RELEASE`, the ack loop SHALL set PGRAPH `0x400B10` bits 2..6 from the executor's last released value, exactly as it sets them from a mirror's completed word, and SHALL log once that the register follows the executor's releases. It SHALL NOT do so while any mirror is registered, whether or not that mirror's device is readable yet, and it SHALL NOT write the register before the first release. The tick that writes the register SHALL be callable outside the ack loop (`xbox_Nv2aPgraphFenceTick`) so a ctest can drive it. `RECOMP_VBLANK` SHALL be read as a switch (`recomp_env_on`): `=0` turns vblanks off.

#### Scenario: A title with no mirror passes D3D's wait-for-idle
- **WHEN** a scaffolded title registers no fence mirror, the executor is on, and D3D's wait-for-idle polls `0x400B10` against its fence word
- **THEN** after the executor's first release the register's bits 2..6 equal the released value's low five bits shifted by 2, the wait ends, and the log holds one `NV2A PGRAPH fence: no fence mirror registered` line

#### Scenario: A registered mirror is never overridden
- **WHEN** a mirror is registered whose device pointer is still 0 and the executor releases value 9
- **THEN** the register keeps its previous bits; once the device exists and its completed word reads 3, the register shows 3

#### Scenario: Before the first release
- **WHEN** no mirror is registered and the executor has released nothing
- **THEN** a tick leaves the register unchanged, bits outside 2..6 included

#### Scenario: The gate titles are unaffected
- **WHEN** BLiNX 2 or Burnout 3 runs with its mirror registered
- **THEN** no `PGRAPH fence` line appears, the mirror lines read as before, and the goldens and flips/s match main

#### Scenario: Vblanks switched off
- **WHEN** `RECOMP_VBLANK=0` is in the environment
- **THEN** the kernel timer raises no vblank and `xbox_VblankCount()` stays 0
