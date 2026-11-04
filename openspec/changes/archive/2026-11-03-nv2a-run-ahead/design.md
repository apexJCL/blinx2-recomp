## Context

The pushbuffer is walked on the ack thread (`nv2a_ack_thread`, the only
caller of `nv2a_pb_scan`). The title's KickOff sets the flush bit, spins
until it clears, then stores PUT.

## Decisions

**D1. Checkpoints, not a second thread.** The walker reports progress from
inside the walk, every 1024 words at a top-level method header (never
inside a CALL target). At each checkpoint it does three things in order:
- settles the walk's reports;
- stores GET (with a release fence);
- ticks the fence mirror.

This is the same order as at the end of a walk. 4 KB is under the 8 KB at
which BlockOnTime sleeps. 1 KB cost about 0.5 ms more walk per heavy
frame, with no fewer notifies.

**D2. The ack rule** (`nv2a_run_ahead_may_ack`) is
`kick_set && !flip_held && acks_this_walk < depth`:
- each ack lets the title submit one segment past the walk in progress;
- the depth bounds that count, so N=1 overlaps one segment;
- a held flip blocks the ack, so the flip hold still gives the title its
  FLIP_STALL.

**D3. The notify, and how it differs from hardware.**
- Only method 5 is trapped: BlockOnTime's event, numbered as in XDK
  5849's D3D8.
- The swap (method 1) stays the flip hold's.
- The other non-zero parameters pass as before, where PGRAPH traps them
  all. The channel field is 0, and PGRAPH_INTR_EN is not consulted.
- PFIFO waits for a trap indefinitely. The walk here waits 50 ms at most,
  so a DPC stuck behind the gate cannot hang the walk.
- A notify that finds another still pending is queued, in order, 16
  deep. Past that it is dropped, counted and logged. Each far-path
  BlockOnTime waits on its own notify, so a dropped one is a lost wakeup.

**D4. Ending the trap on plain RAM.** The registers are RAM, so the
handler's write-1-to-clear of PGRAPH_INTR is a plain store. The bits stay
set, and its DPC calls ServiceGrInterrupt again for as long as the re-read
is non-zero. Service is inferred from PGRAPH_FIFO:
- the handler writes 0 there on entry and 1 on exit;
- the raise leaves 2 there, which the handler never writes.

Sampling that level can miss every exit of a looping handler. The first
version had no sampler at all once the walk gave up, and the Mac hung.
So:
- the ack thread polls on every pass, walking or not;
- it reads service as an edge: over a pass in flight (FIFO 0) it leaves a
  mark (3) that only the handler's own writes erase, so a 0 or 1 seen
  after its mark is an exit;
- after service, a pass whose write-back put the bits back up is watched
  over many passes and cleared, instead of relying on the ack table's
  once-a-pass clear.

The timer thread polls the plain level as well. The title never reads
PGRAPH_FIFO.

**D5. Taking a notify down.** Either thread may find a notify serviced, so
`pending` goes 1, then 2 (being cleared), and only after the status bits
are cleared to 0. A raise waits for 0, so it cannot land between the take
and the clear and have its own bits cleared, which would leave it pending
with nothing for the ISR to find (review F3). The timer does not deliver
while the line reads 2.

## Risks

- Every BlockOnTime far path costs a notify round trip, about 2 ms a frame
  on the Deck.
- The vblank gap widens once the title is no longer held at each kick.
  
- Another title's D3D build may number its software methods differently.
  The mask is a constant (`NV2A_GR_NOTIFY_DEFAULT_MASK`), and the header
  names the XDK it was checked against.
