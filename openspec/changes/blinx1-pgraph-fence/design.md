## Context

PGRAPH `0x400B10` is not modelled as hardware. The toolkit treats it as "the GPU's copy of the last fence" and writes bits 2..6 from the completed fence word (deviations, *Inferred register semantics*). That fits XDK 5849. BLiNX 1 is the first title on XDK 5558, and its wait-for-idle compares bits 0..4 (proposal).

## Decisions

### D1. Learn the field's place from D3D's own fence methods

Each fence D3D inserts is `0x0004A310, word` then `0x00041D70, value` (subchannel 5 method `0x0310`, then subchannel 0 `BACK_END_WRITE_SEMAPHORE_RELEASE`), in both XDKs. The word carries `value & 0x1F` at the place the XDK's wait-for-idle will read it. The executor sees both methods in order, so it can read the shift off the pair:

- only a pair counts: the `0x0310` must be the method right before the release, tracked by a flag the next method clears (not the `[PB-PERF]` method counter, which resets at each printed flip). A walk that stops out of step clears it too: `stop_salvage` then runs a release that is not the word's partner, often with a later fence;
- subchannel 0's `0x0310` (`SET_DITHER_ENABLE`) never counts;
- shifts 0..7 are tried; exactly one must fit. The fence values are odd, so a 5558 word fits only at 0 (bits 5 and 6 are the pushbuffer address's low bits, 0). A 5849 word can fit at 0 as well as 2 for some values (for example word low bits `0x55`, value `0x15`); such a pair is skipped;
- the first unambiguous pair sets the shift, because a 5558 title's first wait-for-idle needs it. After that a different shift takes three unambiguous pairs in a row; a pair at the current shift ends the run. Real D3D pairs never disagree, so this costs nothing, while one foreign pair (a runtime-built pushbuffer that puts some other `0x0310` before a release) would otherwise move the field and hang the next wait for good. Changes and outvoted pairs are logged, at most six lines.

Alternatives considered:

- *A per-game setting* (the title tells the toolkit its XDK). Works, but the porter would have to find it, and the XBE's library versions are the same information the pushbuffer already states, one fence later.
- *XDK version from the XBE's library table.* Needs a version-to-layout table, filled one title at a time; the pushbuffer needs none.
- *Write the whole `0x0310` word to the register.* See D2.

### D2. Only the fence field is written, at a learned shift

The register keeps its other bits, except that a field that moves clears its old place (5558's D3D reads `reg >> 5` as how far the GPU has read, and the default shift's bits 5..6 would stay there).

Considered and not taken (review, 2026-10-27): latch the `0x0310` word's bits 0..6 at each paired release, which needs no shift. It holds for both layouts when the register only ever follows paired releases, but the tick also places values that came with no `0x0310`: a walk stop's salvaged release (`stop_salvage`), and a fence mirror's word while the mirror is still on. Placing those needs the layout, so the shift stays. In today's titles (BLiNX 1, BLiNX 2, Burnout 3) the mirror turns off once the executor writes the fence word, so both designs would give the same register in steady state.

Writing the whole word would be closer to the console (the 5849 D3D reads the upper bits at `0x002E7E32`, `(dev[0x40] - reg) >> 5`, as how far the GPU has read), but it changes what BLiNX 2 and Burnout 3 see today, which this fix must not. Follow-up: model `0x400B10` as the latched `0x0310` word, with goldens, once a title is shown to need the upper bits.

### D3. Default shift 2

Before the first pair, and with `RECOMP_PB_EXEC` off (nothing learns), the tick writes bits 2..6 as before. A 5558 title with the executor off would still spin; the executor is on in every game's default, and `docs/env.md` says 5558 titles need it. Moving the detection into the scan's shared decode (which also runs for the survey) was not done: the survey path is a diagnostic, and the executor already decodes every method in order.

### D4. Threads

The shift, the pending word and the tick's last mask live on the walker thread: the executor runs there, and the tick is called only from the ack loop on the same thread (`xbox_memory_layout.h`). No locks or atomics.

## Risks

- **A title whose fence word is not built this way** (another XDK, or a different method) learns nothing and keeps bits 2..6, the old behaviour. Detect: no `fence field` line in the log while a wait-for-idle spins.
- **A non-fence `0x0310` right before a release** whose word happens to fit at exactly one wrong shift. Before the first real pair it would set the wrong shift (a real pair then needs three in a row to win back); after it, it is outvoted. D3D always emits its own `0x0310` right before the release, so another title would have to do the same with a different object. The log line shows the word and value.
- **SSX 3's wait-for-idle override** (proposal Impact) reads bits 2..6 and spins once SSX 3 pins this toolkit with the override in place.

## Verification

- `tests/pgraph_fence_5558` (eleven checks; negative controls run: without the walk-stop forget check 2 fails, with one-pair changes check 7 fails, without clearing the old field check 8 fails); `tests/pgraph_fence` unchanged.
- BLiNX 1 on Metal with the 128 MB diagnostic: the `bits 0..4` line, past the loading screen.
- BLiNX 2, Burnout 3 and JSRF Metal goldens: verdicts as before; BLiNX 2's log shows `bits 2..6`, JSRF's none.
