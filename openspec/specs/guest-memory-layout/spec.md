# guest-memory-layout Specification

## Purpose
Defines where the toolkit places its guest-visible structures (kernel data, stacks, heap) relative to the loaded XBE image, so that large titles such as BLiNX 2 boot without the toolkit overwriting their sections.

## Requirements

### Requirement: Toolkit structures never overlap the title image
The toolkit SHALL place its guest-visible structures (scratch region with kernel data exports and fake TIB/TLS data, main stack, heap) at or above the first 64 KB boundary past the end of the highest loaded XBE section, and never below guest VA 0x00700000.

#### Scenario: Large image
- **WHEN** a title whose sections end at 0x0303AC20 boots
- **THEN** the scratch region starts at 0x03040000, the main stack and heap lie above it, and no heap allocation, thread stack or toolkit structure overlaps a loaded section

#### Scenario: Small image keeps today's addresses
- **WHEN** a title whose sections end below 0x00700000 boots
- **THEN** kernel data is at 0x00740000, the main stack is 8 MB at 0x00780000, and the heap starts at 0x00F80000, exactly as before

### Requirement: Every XBE section is loaded
The loader SHALL copy every section listed in the XBE header that lies within guest RAM, whatever the section count.

#### Scenario: More than 64 sections
- **WHEN** an XBE with 73 sections boots
- **THEN** the boot log reports 73 sections loaded

### Requirement: Layout that does not fit fails at boot
When the title image leaves too little RAM for at least a 1 MB main stack and a 1 MB heap, memory layout initialization SHALL fail with an error naming the image end and the RAM size, instead of starting the title.

#### Scenario: Image too large
- **WHEN** the image ends within 2 MB of the end of mapped RAM
- **THEN** the host reports a fatal memory-layout error and exits non-zero without running guest code

### Requirement: Contiguous memory is reclaimed
The contiguous arena at guest VA 0x80000000 SHALL be a page allocator with free. MmFreeContiguousMemory SHALL return the block to that arena, MmAllocateContiguousMemoryEx SHALL honour its physical lowest/highest range and alignment, and MmQueryAllocationSize SHALL answer for contiguous blocks.

#### Scenario: Texture churn during stage load
- **WHEN** BLiNX 2 runs 240 s with `RECOMP_PB_EXEC=1` and loads stage 1-1 textures
- **THEN** `[CONTIG]` usage rises and falls, and no `[CONTIG] arena exhausted` line is logged

### Requirement: NtFreeVirtualMemory is answered in guest terms
The NtFreeVirtualMemory bridge SHALL read BaseAddress and FreeSize as guest pointers to 32-bit guest values. MEM_DECOMMIT SHALL zero the page-rounded range, MEM_RELEASE SHALL return the heap block, and both SHALL write the rounded base and size back. Addresses below the dynamic heap SHALL be refused.

#### Scenario: Heap decommit storm
- **WHEN** BLiNX 2 runs 240 s
- **THEN** `xbox_kernel.log` has no `NtFreeVirtualMemory failed` line (55,891 before the fix)

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
