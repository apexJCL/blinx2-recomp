## Why

A pad record times every step by flip. A step that a script made
after it waited on a game event can then miss in a replay: on a slower or
faster run the event comes at a different flip.

The case is `@story-hub`. It skips R0_opening with `tap A every 1 until open
tsedit`. The movie accepts A only 3-15 s after it opens, by the movie
decoder's clock. In the recording the skip took at flip 708. In the replay
the movie did not take A at flip 708. It took the next recorded A, about 730
flips later, so every later press landed hundreds of flips early and the hub
never opened (`pad-record-game-pads/design.md`, Limits).

## What changes

- Toolkit grammar (`pad_script.c`): an anchor entry,
  `f<flip>:@open:<text>[:<buttons>/<period>]`. It says that in the record a
  file whose path contains `<text>` opened at that flip. A step that starts
  after the anchor counts its flips from the flip at which that open comes
  in the replay. It does not press before the open. When the open is late
  and the anchor names a retry, the replay taps `<buttons>` every
  `<period>` flips until the open comes.
- Toolkit recorder: `RECOMP_DEBUG=pad_record=<file>,pad_anchor=<text>|...`
  writes an anchor for each successful open whose path contains one of the
  texts. The retry comes from the record itself: the last two presses
  before the open, when they press the same buttons.
- Toolkit kernel: NtCreateFile tells the pad model about each successful
  open (`usb_gamepad_file_open`), next to the existing `xbox_FileOpenHook`.
- cat: `docs/env.md` row for `pad_anchor`. No cat code changes: BLiNX 2
  replays through the toolkit tap (`usb_gamepad_game_press`), which now
  honours anchors.

Stock behaviour does not change. Without `RECOMP_PAD_SCRIPT`,
`RECOMP_PAD_LIVE` and `pad_record`, the open notice returns at once and
presses nothing. A script or record without anchors replays as before.
