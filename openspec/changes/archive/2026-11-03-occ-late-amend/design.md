## Context

`nv2a_occ` (`src/kernel/nv2a_backend_common.c`) settles every report still pending at the end of a walk, before a semaphore release after a report, and at the flip (design of `occ-reports`, archived 2026-10-17). The settled report's queries stay on `retired[]`; their result used to update the address's last count only.

## Decisions

**D1. Amend, guarded.** When a retired report's result comes in, `occ_amend` writes the count over the settled one with a compare-and-swap on the count word, after an acquire load of the status word reads 0. The settle records the count it wrote (`settled`) and arms the report (`amend = 1`). A `GET_REPORT` at the same address disarms every retired report there before anything is polled, so the new test's count is never overwritten, even when it equals the settled one. Equal counts skip the write.

Why not drop the 0x10000 fallback: BLiNX 2's LOAD GAME reads its tests 4-12 ms after `GET_REPORT` in the same frame and skips the characters when a test reads hidden, so a visible first answer is what keeps them. The amend fixes titles that read late without touching titles that read early.

Why not widen the history window: it only moves the cliff (ten slots at 25 ms a flip already exceed 250 ms).

**D2. The accepted window.** A title that reads between the settle and the amend reads the settled value, as before. A title that has read the settled value and reads again after the amend sees the true count; on the console it would have read the true count both times.

**D3. Thread safety.** Everything runs on the NV2A ack thread, as before; the guest reads through memory. The title's own store to the status word races only with the acquire load, and a store landing between the load and the compare-and-swap leaves a status of 0xFFFFFFFF over a count the title ignores until its next report writes both.

**D4. The slot beside, only with no count of its own.** The amend cannot help a read that comes before the result. A title rotating one test over several slots leaves each slot's own count ten flips old or missing, but the slot beside it was answered a flip ago. So when no count at the address is younger than `NV2A_OCC_LATE_US`, the settle takes the youngest such count from an address within `NV2A_OCC_NEAR` (0x100) bytes, and only then falls back to visible. The address's own count still wins when there is one: a title testing several objects a frame keeps per-object counts, and a neighbour is only borrowed where the alternative is 0x10000. The window keeps BLiNX 2's LOAD GAME case: its reused slot and the slots around it were last answered at boot, seconds before, so nothing nearby is young and the answer stays visible. The BLiNX 2 goldens check it. The borrow is for one test rotating only: when another report within `NV2A_OCC_NEAR` is pending in the same settle, or was issued in the same flip (each report and last count carries the flip it was issued in), the slots hold several objects at once, as JSRF's lights and SSX 3's flares do, a neighbour's count says nothing about this one, and the report settles to visible as before. B3 issues one sun test a flip, so it still borrows. The borrow carries most of the fix: B3 reads some slots before the late result lands, and with the delay the amend alone left 148 flare frames, the borrow 3. Counted as `beside` (not `near`, a macro in the Windows headers).

## Verification

- `tests/occ_reports`: 18 cases, six new: the guards, the rotation, the slot beside, a borrowed 0, no borrow among tests beside each other, and a full `retired[]` dropping an armed report; the scale case also checks that a dropped report is not amended.
- Metal, B3 race with `occ_delay_us=12000`: unfixed, amend only, and amend plus beside builds, frames every flip in a race-wide window, against the fixed build with no delay.
- Native D3D11 on the PC at the user's settings, and the BLiNX 2 goldens on Metal and the Deck.
