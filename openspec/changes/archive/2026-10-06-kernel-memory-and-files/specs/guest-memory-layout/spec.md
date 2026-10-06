## ADDED Requirements

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
