## Context

BLiNX 2's pickup, `tc_crystal_collect` `0x8BFD0` (cdecl `(item, flag)`,
player in `eax`), works on the per-team record `tc_team_record`
(`0xADCA58 + team * 0x5DC`, team = player byte 0 / 4, character
c = player `+0x41`, 0..2):

- the crystal's slot k = (type - 0x2A) % 6 maps to a control id
  (k0 PAUSE 2, k1 REC 6, k2 FF 4, k3 RETRY 1, k4 REW 5, k5 SLOW 3; the jump table at 0x8C4F8);
- `+0xC + c*6 + k`: the colour's count, 0..2;
- `+0x1E + ((c*6 + k)*4 + n)*2`: the crystals' words (item `+0xE`);
- `+0xAE + c*8 + id` held, `+0xC6 + c*8 + id` the cap, `+0xDE` stamps,
  `+0x1CE` held words, `+0x8` the last set's id.

The pickup's order: an item already taken (`+1 == 0xE`) returns; the
two-player redirect (`0xB22E3C == 2`, team mode 0 or 1); a bounce when the
player cannot take it (`+0x2F`, `+0x301`, or the unlock test `sub_00020880`
for that control in this stage); the VS/Tom Tom team redirect; then, for a
character that counts (`+7 == 0`, byte 0 < 0x10): the word goes in at the
count, the count goes up, and at 3 the control is granted when held < cap
(stamp, words copied, flash, sound) or else `tc_crystal_overflow_gold`
pays gold and the count stays 2. Last, the item is freed and the pickup
sound plays.

The record is zeroed and rebuilt at each stage start (`sub_001A4100`), a
character's part is reset by `sub_0019F9F0`, and the checkpoint copies the
whole array both ways (`sub_001A95A0`, `sub_001A90F0`).

`hud_time_controls_draw` `0x72010` draws the panel: for each control slot j
of n a slot icon through the sprite add `0x42190` (return `0x730BF`), and
for the selected slot `count[k]` pips (returns `0x736E6` and `0x737AD`).

## Goals / Non-Goals

Goals: BLiNX 1's row (four slots in pickup order; three of one colour give
that control, four give it twice; the row empties at four), in Sweepers
stages, on top of BLiNX 2's stock, caps, d-pad pick and gold payout; off by
default and stock when off; carried by checkpoints, retries and REW like
the stock counts; one HUD row.

Non-goals: BLiNX 1's freezing picker, its frozen countdown after a
control, VS and Tom Tom (they stay stock), new art.

## Decisions

### D1. Pre and post around the game's own pickup, never a skip

A skip would have to redo the item freeing, the sounds, the redirects and
the bounces, and a wrong guess there frees an item twice or leaves it on
the floor. Instead the mod's pre prepares the record so that the game's own
code grants exactly when the row says so, and its post puts the row back.

Pre (Sweepers only, `stage_team_mode` `0xB21CB4` == 0, k in 0..5, not
nested):

1. Copy `+0xC..+0xAD` of every team and character (4 x 0xA2 bytes) to a
   host buffer.
2. For each (team, c): would the row, with colour k pushed, hold three or
   four of k? Then set count[k] = 2 and put the row's earlier words of
   colour k at word slots 0 and 1, so the game grants (and checks the cap,
   pays gold when full, stamps, flashes). Else set count[k] = 0.
3. Put `~word` at the slot the game will write (`count[k]`), so the post
   can tell which (team, c) the game counted, if any.

Post: the (team, c) whose slot now holds the item's word is the one the
game counted (redirects included). Restore every copy, then push colour k
and the word into that row; at four crystals the row empties. No match
(bounced, already taken, a character that does not count): restore only.

So the mod counts exactly the crystals the game counts, as often as the
game counts them: natural play calls the pickup once per item (the taken
flag gates later touches), and a direct second call counts twice in stock
and with the mod alike (P1c, item `00B26FCC`).

### D2. The row in the count bytes

Bytes `+0xC + c*6 + i` (i 0..3) hold k + 1 of the i-th crystal, 0 when
empty; bytes 4 and 5 stay 0. The row's words sit in colour 0's word slots
(`(c*6)*4 + i`). Being in the record, the row goes through checkpoints,
retries and the stage start's clear with no code of its own. Rules (pure,
`crystals_logic.c`): the third crystal of a colour in the row grants it
once, the fourth grants it again, and the row empties when it holds four.

The game reads these bytes in only two places while the mod is on: the
pickup (prepared by D1) and the HUD pips (hidden by D3). Off, the game
would read the row as counts; so switching the mod off live (and on, which
would read stock counts as a row) empties every row in a Sweepers stage.
A set in progress is lost at that switch, nothing else.

### D3. The HUD row

The stock pips would count the row's bytes: their pre (returns `0x736E6`,
`0x737AD`) sets their colour's alpha to 0. The row is four quads. The slot
icons' post (return `0x730BF`) records each icon; the slot loop skips
controls it does not show, so no slot index marks the last one, and the
row goes out at the first slot icon of the next frame, from the icons
the frame before drew (the live proof saw rows never drawn when it
waited for j == n - 1). Each slot is that colour's control icon, as the game drew it this
frame, scaled to 60 % and tinted with the colour (`0x3FD7C8[id]`); an
empty slot is the first icon at 25 % alpha. They sit centred above the
slots. The draws are `guest_call`s of `0x42190` with the vertices in the
mod's `guest_alloc` block and the icon's texture and sprite id as the game
used them; the mod's own hooks ignore those nested calls. The HUD layer
sees an unlisted return and treats the quads as centre, the time-control
panel's group, so they stay with the panel at any aspect.

`0x42190` is a hook slot already (the HUD mod's); the time-control panel
calls no `0x47A00` text every frame, so the row needs no new slot there.

### D4. Modes left stock

With `stage_team_mode` != 0 (Tom Tom 1, VS 3) the hooks return at once:
the pickup and the pips are stock. The row clear on a live switch skips
those modes too.

### D5. The `crystals` mod

`src/crystals_mod.c`, modelled on `entities_mod.c`: setting `enable`
(`RECOMP_CRYSTALS`, off, live), a Status row (the row of player 1, sets
completed, gold paid this run), `XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK`.
Registered before the HUD mod, so its pre sees the game's vertices and its
post runs after the HUD mod's restore. Without the hook slot it logs one
line and stays stock. `RECOMP_DEBUG=crystals_proof=<steps>` drives the
live proof (D6).

### D6. Live proof

The proof driver spawns crystals at player 1 through `ent_item_spawn`
`0x794D0` and takes them through the game's pickup (both as in the
spike's `crystal_spike.c`), makes a REW request, and logs the record each frame to a TSV under
`runs/crystal-sets/`; the d-pad presses come from the input script
(`RECOMP_INPUT_SCRIPT`), and the cap is the stage's own (stage 1 caps
PAUSE, REC and REW at 2, so the third PAUSE set pays gold). It covered: a
set of three; four of one colour giving two; a mixed row emptying with
nothing; a full control paying gold; a direct second pickup of one item
(counted twice, as stock); the d-pad selection; the row after a REW and
across a mission change; VS and Tom Tom left stock. Not covered: a
checkpoint retry or death with a partial row, and the stage-end clear (see
Risks).

## Tests

`scripts/test_crystals.py` compiles a driver over `crystals_logic.c`: the
push rules (three, four, mixed, empty at four), the prepare step for each
row and colour, the detection by the poisoned word, the clear; then checks
the env rows, the docs rows, the golden stock value, the hook slot.

## Risks

- A future gen change in `0x72010`'s frame breaks D3's reads of the
  caller's locals (slot j, n, the slot list): they are checked against the
  known return addresses only, and a value out of range skips the row.
- If REW does not rewind the record, the row survives a REW the stock
  counts would also survive; the proof records which.
- REW does not rewind the record (P1c: REW at play 1000 left the row and
  the counts as they were), so the row survives a REW the same way the
  stock counts do.
- The row lives in the record, which the game carries across a mission
  change in one stage (P2b: row `1 5 1` kept from mission 1 into 2). The
  stage start rebuilds the record (`sub_001A4100`), which is what clears
  the row; that clear is read from the code, not yet seen in a live run.
- A second collect of one item counts twice, as stock does: natural play
  calls collect once per item (P1c, P2b); only a direct double call counts
  twice, and stock counts it twice too (crystal-spike live-2).
- A control with cap 0 in a stage (SLOW in stage 1) is refused by the
  game (collect returns 1) and re-called while the player touches the
  item. The refusal bounces before the game writes the crystal's word,
  so the post finds no poisoned slot holding it and the item never enters
  the row (collect_post does not read the return value).
- The HUD slot loop skips slots (j mask `0x3E` with n 6), so the first
  or last slot index is not a usable trigger; the row is drawn at the
  next frame's first slot icon (D3).
- Turning the mod off between a checkpoint save and its load (accepted):
  the load puts the saved row bytes (k + 1 per crystal) back into the
  count area, where stock reads them as counts. The worst case stays
  inside the span: one early grant or gold payout per colour and extra
  count pips once, until the counts cycle. The reverse (on between save
  and load) gives a short wrong row that empties at four. The rows the
  toggle empties live are only the record's, not the checkpoint copies.
- Untested live: a checkpoint retry or death with a partial row (P2b
  reached a mission change instead), and the stage-end clear (the stage
  start rebuilding the record, read from the code). Both rest on the row
  living in the record like the stock counts.
- A toggle between collect's pre and post hooks (the menu thread flips
  the switch, the hooks only run while on) left the hook depth off by
  one, so the mod looked on and did nothing until restart. on_enable now
  settles it (`cry_settle`) at the frame boundary: it puts the spans back
  from the snapshot when the record was prepared and zeroes the depth.
- VS (P3b) and Tom Tom (P4b) stay stock: the hooks log nothing there.
  VS counts with BLiNX 2's own three-crystal rule (counts 1, 2, then a
  control). Tom Tom has every cap at 0.
