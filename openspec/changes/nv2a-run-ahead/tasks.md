Conventions: toolkit branch `spike/run-ahead` off `posix-host/portability`
(1557104a); cat branch `spike/run-ahead`.

## 1. Run-ahead walker (toolkit)

- [x] 1.1 Checkpoint hook in `nv2a_pb_scan` (top level, every 1024 words,
      only when the walk executes).
- [x] 1.2 GET, fence tick and early ack at the checkpoint
      (`nv2a_run_ahead_may_ack`, depth N).
- [x] 1.3 `RECOMP_DEBUG=run_ahead=N`: any value but 0 is on, and a value
      that is not a number means 1.

## 2. PGRAPH notify (toolkit)

- [x] 2.1 Raise, deliver on vector 3 through the gate (`nv2a-gr`), and a
      bounded stall.
- [x] 2.2 Queue behind a pending notify, raise in order (review F2).
- [x] 2.3 Ack-thread watch on every pass, edge detection, relatch watch
      (review F1).
- [x] 2.4 `[PACING]` and `[IRQ] nv2a-gr` report lines.
- [x] 2.5 Take-down in two steps, 1 → 2 → 0, so a raise cannot be
      cleared by the poll before it (re-review F3).

## 3. Tests and gates

- [x] 3.1 `tests/gr_notify`: register helpers, the queue, the raise
      between take-down and clear, a late DPC at every rate and phase, and
      the ack rule.
- [x] 3.2 POSIX ctests; the Metal stock golden; the Deck stock and
      `run_ahead=64` goldens.
- [x] 3.3 Mac `run_ahead=64` barricade soak, 3 runs, no hang.

## 4. Docs

- [x] 4.1 `docs/env.md` row (cat).
