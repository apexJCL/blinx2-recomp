## ADDED Requirements

### Requirement: Constant-address APU moves do not fault
Generated code SHALL reach the APU register model by a direct call for every `mov` whose memory operand is a constant address, with no base, index or segment register, lying wholly inside the trapped APU range (guest 0xFE800000-0xFE82FFFF). The model SHALL receive the same call with the same offset, width and value, at the same point in the thread, as the trapped-fault path would deliver. When the range is not trapped or the APU model is not initialised, the access SHALL be the plain guest-memory access that generated code made before this change, at the same width. Every other access to the APU window (any other instruction form, any access through a register, any constant address at or above 0xFE830000) SHALL be emitted as before and keep the trapped-fault path or its plain-RAM behaviour.

#### Scenario: DirectSound voice update without a fault
- **WHEN** the title writes `SET_CURRENT_VOICE`, `VOICE_LOCK` and the voice volume and pitch methods and polls `PIO_FREE` during 5-1 play with the APU model up
- **THEN** `[APUMMIO-STATS]` counts those accesses as `direct`, the trapped count stays at the init-time level, and the audio matches the pre-change build

#### Scenario: Model off
- **WHEN** the game runs with `RECOMP_AC97_READY=0`, or on a host where the range is never trapped
- **THEN** every constant-address APU `mov` reads or writes the aperture as plain RAM, exactly as before this change

#### Scenario: DSP memories stay RAM
- **WHEN** generated code moves to or from a constant address in 0xFE830000-0xFE87FFFF (the GP and EP DSP memories, which the trap leaves as RAM)
- **THEN** the lifter emits the plain `MEMxx` access and the value is kept in the aperture, with no model call

#### Scenario: Standalone test
- **WHEN** `tests/mmio_direct` drives `xbox_MmioRead`/`xbox_MmioWrite` at widths 1, 2 and 4 against a model stub, and the lifter test lifts constant-address `mov` forms at every width, plus ALU read-modify-write, `cmp`, `test`, `inc`, `xchg`, `lock xadd`, `movzx`, a register-based form and addresses just outside the range
- **THEN** the model stub sees the offsets, widths and values the fault decoder passes for the same `mov`; offset 0x2FFFC reaches the model and 0x30000 lands in RAM; the in-range `mov` forms emit `XBOX_MMIO_*`; every other form emits `MEMxx` as before

#### Scenario: Proton frame rate
- **WHEN** 5-1 is played under Proton on D3D11 with the APU on
- **THEN** idle play holds 30 flips/s as the `RECOMP_AC97_READY=0` run does, or the post-change `handler=` figure accounts for the shortfall and the `VOICE_LOCK` follow-up is opened with it; PAUSE no longer costs about 51 us per voice update
