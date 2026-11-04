## Why

In a Windows playtest on native D3D11 (`render.scale` 3, aniso 16, 16:9, DSP on; build 20261022.0312-c47f7fdd, toolkit 3ad3663c) Burnout 3's sun glare sometimes drew bright coloured shapes, as if blending were off. The shapes are the lens-flare rings at full strength.

Burnout 3 tests the sun's visibility once a flip and rotates the test over ten report slots (0x80B97000 to 0x80B97090), reading each slot frames after its `GET_REPORT`, as the console allows. The occlusion tracker settles every report still pending at the flip (`occ-reports`): it writes the address's last count, or `NV2A_OCC_VISIBLE` (0x10000) when the address has none younger than 250 ms. A settled report's late result only refreshed the last count and was never written.

On the user's PC the D3D11 results come 8-16 ms after `GET_REPORT` (age histogram: 1644 of 3074 under 16 ms, 416 under 8), so 1592 of 3074 reports settled. Each slot's last count is ten flips old, and at the start of every sun shot none of the ten slots has one, so the first ten reports read 0x10000, hundreds of times the sun's real count (20-400): the rings flash at full strength for about a sixth of a second. When flips run slower than 25 ms (a heavy frame, a slow GPU), every report is "first". Metal at stock answers in under 1 ms and never settles, which is why the Mac never showed it; `occ_delay_us=12000` reproduces it there.

## What Changes

- **A settled report is amended** when its late result arrives: the true count replaces the settled one if the slot still holds what the settle wrote (status 0, the same count) and no later `GET_REPORT` has named the address. A slot the title has reset (EndVisibilityTest writes status 0xFFFFFFFF) or reused keeps what is there. A compare-and-swap on the count word leaves the title's stores alone.
- **A slot with no count of its own borrows from the slot beside it.** When no count at the address is younger than 250 ms, the settle writes the youngest count from an address within 0x100 bytes (`NV2A_OCC_NEAR`) before falling back to 0x10000. B3's ten slots span 0xA0 bytes, so a read that comes before the amend sees the previous flip's sun instead of a full-strength flare. Only a lone test borrows: with another report within 0x100 bytes pending in the same settle or issued in the same flip, the report settles to visible as before, so titles testing several objects side by side (JSRF, SSX 3) keep their the tracker item behaviour.
- The end-of-run `occ totals` line gains `beside N` inside the settled breakdown and `N amended`.
- **Tests:** `tests/occ_reports` changes the stale case (the late result is now written) and adds three cases: the near-slot fallback, the guards (reset slot, reused slot), and Burnout 3's ten-slot rotation read nine frames late with 12 ms results, which reads every true count and settles nine of ten from the slot beside. The review round adds a borrowed 0, tests beside each other that never borrow, and a full `retired[]` dropping an armed report.
- **Out of scope:** the 0x10000 fallback where no slot nearby has a young count (BLiNX 2's LOAD GAME needs a visible answer on a report it reads within the frame), D3D11's result latency at high scale, and readers that poll inside the frame that issued the test.

## Impact

- **Toolkit:** `src/kernel/nv2a_backend_common.{c,h}`, `tests/occ_reports/test_main.c`. Both GPU backends share the tracker, so D3D11 and Metal change together; neither backend file changes.
- **Behaviour:** none where results come within the settle budget (Metal at stock, D3D11 on a fast host). On a lagging host a title that reads after the result sees the console's count instead of a stale or visible one; one that reads before it sees what it saw before.
- **Goldens:** BLiNX 2 Metal and D3D11 goldens must pass unchanged; Burnout 3 race on Metal and native D3D11.
- **cat, b3:** nothing but this spec and TASKS.
