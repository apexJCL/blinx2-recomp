## Volume information

Xbox `FILE_FS_VOLUME_INFORMATION` is NT's with an `OCHAR` label, like every
other name the Xbox kernel takes:

| offset | field |
|---|---|
| 0 | `LARGE_INTEGER VolumeCreationTime` |
| 8 | `ULONG VolumeSerialNumber` |
| 12 | `ULONG VolumeLabelLength` (bytes) |
| 16 | `BOOLEAN SupportsObjects` |
| 17 | `OCHAR VolumeLabel[]` |

`sizeof` is 24. NT's I/O manager refuses a buffer under the structure size
with `STATUS_INFO_LENGTH_MISMATCH` before the file system sees it; the file
system then writes the fixed part, copies what fits of the label, sets
`Information` to the bytes written, and returns `STATUS_BUFFER_OVERFLOW` when
the label was cut. `xbox_FsVolumeInformation` does exactly that, so every
backend (Win32, POSIX, RAM cache) answers the same way.

FATX volumes carry no label, so the backends pass `""` and the reply is 17
bytes with `STATUS_SUCCESS`. That matters: XAPI tests the status with
`NT_SUCCESS`, which a `STATUS_BUFFER_OVERFLOW` warning fails. The overflow
rule is kept for completeness and covered by a direct ctest of the helper.

The serial stands for the volume. Win32 reports the volume's own; POSIX has
none, and `st_dev` names the volume the same way. The RAM cache uses a fixed
`"RAMC"`. The creation time is 0: FATX has none either.

The experiment patch returned `Information = 0x12` (an 18-byte WCHAR
offset) and accepted 18-byte buffers. The final code follows the Xbox layout
(17) and NT's length rule (24); the KUF run checks that XAPI passes the full
structure.

## Internal information

One `LARGE_INTEGER IndexNumber`. Win32 and Proton:
`GetFileInformationByHandle`'s file index; POSIX: `st_ino`, from the `fstat`
the function already makes; RAM cache: the node id, unique for the store's
life. A buffer under 8 bytes gets `STATUS_INFO_LENGTH_MISMATCH`, set in the
status block too (Information 0), as the class 1 helper does.

## Heap tail fold

The block table is in address order and the bump cursor `g_heap_next` sits
past the last block. Under reclaim, `heap_carve_free` is tried first; when it
finds nothing, every free block, the tail block included, is too small on its
own. The fold runs only when the bump from the cursor would then pass
`XBOX_HEAP_TOP`: a request that fits above the cursor bumps as before, so a
title that works today gets the same addresses (JSRF, which defaults reclaim
on, depends on which address a free hands back). When the bump would not
fit and the last non-empty block is free and ends exactly at the cursor, it
and the room above the cursor are one free run, so `heap_fold_free_tail`:

1. step back over trailing empty slots (size 0, left by merges);
2. if that block is free and ends at `g_heap_next`, set `g_heap_next` to its
   address and `g_heap_block_count` to its index (dropping it and the empty
   slots after it);
3. repeat, in case two free blocks at the tail did not merge (a merge
   refused because the table was full);
4. if the cursor moved, retry the allocation; otherwise go on to the
   quarantine drain and, failing that, out of memory.

The bump then records the new block in the slot the free block had. Why this
stays consistent:

- Address order holds: the new block starts at or above the folded block's
  start, and nothing live is above it.
- Dropped slots are free or empty; nothing (quarantine, handles) refers to a
  slot index. The quarantine holds live blocks only, so a held tail block is
  not folded; `heap_quarantine_drain` on exhaustion frees it and the retry
  folds it.
- `heap_forget_ram_names` already cleared the folded block's page names when
  it was freed and merged; a page it shares with the live block below keeps
  that block's name, which is unchanged.
- A table that filled up and bumped without recording a block leaves the
  cursor above the last recorded block, so the end test fails and nothing
  folds.
- If the retried bump still does not fit, the cursor is lower than before,
  which only makes the exhaustion report's "above the cursor" figure include
  what was the free tail; the largest-run figure is the same. The retry
  cannot loop: a second fold finds nothing and returns 0.

Reclaim off is untouched: the fold runs only under reclaim. Check 3b pins
both halves: with room above the cursor a larger request bumps past a 3 MB
free tail (every mode); with the heap filled to 1 MB short of the top, two
4 MB blocks freed at the cursor (one merged 8 MB tail) take a 9 MB request
at their address.
