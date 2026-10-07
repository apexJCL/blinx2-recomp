## ADDED Requirements

### Requirement: A batch keeps every index the title sends
The executor SHALL collect at least `0x80000` (524,288) indices per BEGIN/END batch from `ARRAY_ELEMENT16`, `ARRAY_ELEMENT32` and `DRAW_ARRAYS`, and every backend SHALL draw the whole list. The NV2A accepts batches of at least `0x0FFFFF` elements and retail titles are known to send at least `0x410FA` in one draw, so a smaller cap cuts real geometry. Indices SHALL stay 16-bit: the hardware faults on a `DRAW_ARRAYS` start above `0xFFFF`, so no title references more than 65536 vertices in one batch. When a batch would pass the executor's limit, the executor SHALL print one `[GPU] index batch over N indices` warning per run and SHALL count the dropped words and runs. It SHALL NOT drop indices silently.

#### Scenario: The stage 1 water grid reaches the horizon
- **WHEN** BLiNX 2 draws its stage 1 water grid as one 4592-index quad list (the lighthouse warp, `runs/stage1-water/scripts/warp_lhp.txt`, flip 2490)
- **THEN** all 1148 quads are drawn on the CPU path, Metal and D3D11, and the cyan water reaches the horizon with no hard edge, as in xemu

#### Scenario: A quad past index 4096
- **WHEN** a backend smoke test sends an indexed quad list of more than 4096 indices as `ARRAY_ELEMENT16`, with a distinct colour on the quads from index 4096 on
- **THEN** a pixel inside a quad past index 4096 has that colour on the CPU path and on the GPU backend under test, and the two frames match

#### Scenario: Overflow is visible
- **WHEN** a batch sends more indices than the executor holds
- **THEN** the run log has one `[GPU] index batch over` line, and the overflow count on the periodic `[GPU]` summary line is non-zero

### Requirement: The odd index of an indexed draw is kept
The executor SHALL decode `NV097_ARRAY_ELEMENT32` (0x1808) as one index per word, appended to the open batch under the same limit and warning as `ARRAY_ELEMENT16`. The XDK sends the last index of an odd-count `DrawIndexedVertices` this way; dropping it loses the batch's last primitive.

#### Scenario: A triangle list whose last index is a 32-bit element
- **WHEN** a backend smoke test sends a triangle list as `ARRAY_ELEMENT16` words followed by one `ARRAY_ELEMENT32` word
- **THEN** a pixel inside the last triangle is drawn on the CPU path and on the GPU backend under test, and `0x1808` does not appear in the unhandled-method ranking

### Requirement: The summary says how big batches get
The executor's periodic `[GPU]` summary SHALL print the largest index count of any batch so far and the number of overflowed batches (`index batches: max M, N overflowed`), and SHALL print the count of `DRAW_ARRAYS` runs that reached past index `0xFFFF` when it is non-zero. A run log then shows whether a title ever needed more than an earlier cap, and whether the walker decoded a start the hardware would have rejected.

#### Scenario: Reading a title's largest batch from its log
- **WHEN** a golden or Burnout 3 run finishes with the NV2A trace on
- **THEN** its log's last `[GPU]` summary carries `index batches: max M, N overflowed`, with N = 0 for every scenario of BLiNX 2 and Burnout 3 at the new cap

### Requirement: A backend draws any batch the executor accepts
A GPU backend's index ring SHALL hold the expanded list of a batch of `NV_MAX_INDICES` indices (three list indices per input index, 32-bit each), and its per-index scratch SHALL grow with the batch rather than be sized statically to the cap. The CPU program path's transformed-vertex scratch SHALL do the same. A batch the executor collects whole is then never dropped for its size downstream.

#### Scenario: Scratch costs what the run uses
- **WHEN** BLiNX 2 runs its stage 1 golden
- **THEN** the per-index scratch on each backend is sized to the run's largest batch (4592 indices), not to the cap
