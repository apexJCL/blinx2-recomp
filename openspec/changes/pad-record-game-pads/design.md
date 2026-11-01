## Decisions

**D1. A toolkit tap, not a second recorder in cat.** The recorder
(`pad_recorder_feed`), the script grammar and the flip clock are already in
the toolkit. A copy in cat would drift from them, and its record would no
longer be the format `RECOMP_PAD_SCRIPT=@file` reads. The tap converts the
game's `XBOX_GAMEPAD` to the 20-byte report and back, then runs the same
`pad_script_apply` and `pad_record` that the USB report runs.

**D2. Press before `camera.free`, record after it.** On the USB path the
script presses on top of the source's state, and the recorder writes the
report that goes to the title. In cat, the script's presses join the game's
own sources (cat script, host pad, keyboard) after the mod pad filter. So
`camera.free` treats them like any other pad, and a scripted press does not
fire a host action. The record is taken after `camera.free`, on what the
title reads. A replay pressed at the same point then gives the title the
same state.

**D3. The script's ports are connected.** A replay with only
`RECOMP_PAD_SCRIPT` set has no cat script, no keyboard on a scripted run
and no host pad on the Mac. Without this, port 0 would read empty and the
title would ignore the presses. The USB model does the same through
`usb_gamepad_present`.

**D4. Record every poll, connected or not.** A port that drops out
mid-hold reads zeros, and the record must see that release, or a replay
holds the button until the next recorded change. A port that is never
pressed feeds only zeros, and the recorder writes nothing for it. The
record is taken under the flip its poll's press used (`usb_gamepad.c`).
The walker can count a flip between the two calls, and a record taken a
flip late lengthens the hold.

## Limits

- The flip count is the walker's, not the title's frame counter. On a
  steady screen a replay lands within 1-2 flips. Across loading screens and
  movies the number of flips varies per host and per run (pad_script.h).
- A press that only lands because a script waited on an event can miss in
  the replay. The record keeps the press at its flip, not the event it
  waited for. Measured on the Mac (Metal, 2026-10-30, runs/pad-record/):
  - `@story-hub` skips R0_opening with `tap A every 1 until open tsedit`.
    The movie accepts A only a few seconds after it opens, by the movie
    decoder's clock. In the recording (run A) the first A it took came
    3.2 s in. `story-slack.txt` allows 3-9 s for that. Run A recorded the
    skip at flip 708. The replay (run B) pressed A at flip 708 too, but the
    movie did not take it yet. The skip came at the next recorded A, at
    flip 1435 (+727). The later anchors came late in B: tsedit by +476
    flips and the slot list by +516. So every tap after the skip landed
    hundreds of flips early, and the hub never opened. Host load is a
    confound: A started at load 89.9, and B's golden warned of load 39.2.
  - A route that does not race the decoder replays. `story-slack.txt`
    (beside this file) lets R0_opening play out (94 s), waits 10 s on
    tsedit and taps A twice after the save. Its record (34 steps) replayed
    twice. The hub opened at flip 9311, 9311 and 9312, and every movie,
    music and save open landed within 3 flips of the recording.
  So a record replays a run whose presses have slack around wall-clock
  events. A game-event-timed record (by file open or memory state) would
  remove the limit.
- The connected ports differ between a run and its replay. On replay, the
  script makes every pad it names connected from boot (D3). A pad that was
  connected but never pressed is not in the record, so on replay it is
  absent. A title that counts pads, a 2P menu, or a run that plugs a pad in
  mid-way can then branch differently. A pad that disconnects mid-hold is
  recorded as a release (D4). On replay the port stays connected (D3) and
  reads released, where the title saw "not connected". This matters only
  for a title that pauses when a pad is pulled.
- `RECOMP_INPUT_SCRIPT` steps that do not press the pad (`poke`, `key`,
  `memdump`) are not in the record. They are not pad input.
