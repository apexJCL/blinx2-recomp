## Context

The `crystals` mod (archived change `2026-11-03-crystal-sets`, its design
D1 to D6) keeps BLiNX 1's row in the team record's count bytes and wraps
the game's pickup `tc_crystal_collect` `0x8BFD0` in a pre and a post. Its
rules hold; this change renames what players see, fixes the heart
crystal's empty slot and reorganises the code. The archived design stays
the reference for the record layout, the HUD hooks and the modes left
stock.

## Goals / Non-Goals

- Goals: a name that says what the mod does; heart crystals visible in the
  row; the same behaviour from simpler code; live runs of the death and
  retry and the stage-end clear.
- Non-goals: new rules (BLiNX 1's freezing picker stays out), a new hook
  slot, new keys, or changes with the mod off.

## Decisions

### D1. The name: "BLiNX 1 crystals"

The Mods page lists mods by name, beside "Bloom", "Free camera" and the
HUD. "BLiNX 1 crystals" says the one thing a player needs: crystals work as
they did in BLiNX 1. Players who know BLiNX 1 recognise the row from that
alone; the summary line ("Collect crystals the BLiNX 1 way: a row of four")
tells the rest. Names weighed and left:

- "Crystal row" and "Crystal sets" describe the mechanic but not where it
  comes from, so a player cannot guess it is the BLiNX 1 rule;
- "Classic crystals" is vaguer: classic to whom;
- "BLiNX 1 crystal rule" or "BLiNX 1-style crystal collection" say the same
  at twice the length, and the Mods page row is narrow.

The id `crystals`, `mods."crystals.enable"`, `RECOMP_CRYSTALS` and
`crystals_proof` stay. The Bloom rename (cat c5f51d40) set the pattern:
players' settings, the goldens' `[golden] enhance_stock` and the input
scripts keep working with no migration.

### D2. One pickup step over every team

The first version split one pickup into `cry_prepare` (per character),
`cry_counted` (per character) and `cry_settle` (hook depth repair), and the
mod looped over teams and characters around them. The rewrite has one
struct, `cry_pickup`, in `crystals_logic.c`:

- `cry_pickup_begin` snapshots all four teams' spans and prepares every
  character's counts and poisoned word slot (archived D1);
- `cry_pickup_end` finds the one slot that now holds the crystal's word,
  puts every span back and pushes the crystal into that character's row,
  returning nobody, counted or counted with a set;
- `cry_pickup_undo` puts every span back, for a post that never runs.

The mod keeps one `cry_pickup`, a call depth and an active flag.
collect_pre begins at the outermost call only, so a pickup the game makes
from inside another one sees the prepared record, as before; collect_post
ends it there.
on_enable, at the frame boundary, undoes an active pickup whose post never
ran (the mod switched off in between) and zeroes the depth: the job
`cry_settle` did, with no second copy of the state.

The mod tells a set from gold by the held count: the post compares the
character's held control with a snapshot taken in the pre.

### D3. The heart crystal's icon

The row draws each crystal with its control's icon as the panel drew it
this frame (archived D3): `TAB_SPRITE[id]` picks a frame of the panel's
texture. The time-control panel shows PAUSE, REC, FF, REW and SLOW; retries
are the heart gauge, so RETRY (id 1) has no slot and no icon of its own in
that texture, and its slot came out empty.

`sub_0006B1F0` draws a heart above the heart gauge for each heart crystal
of a partial set (its loop `0x6D920` to `0x6DB3C`, over the count byte at
record `+0xF + c*6`). The heart is one sprite-add call at `0x6DB17`: the
texture pointer `[0xA723C8]` set to `0x418848`, frame 3, colour white, its
four corners covering the whole texture (u 0 at the left, v 0 at the top).
The row uses that heart for k3:

- the texture pointer becomes `0x418848` for that quad and goes back
  after the row;
- `cry_quad(tpl, out, x, y, scale, own_uv = 1)` gives the slot's corners
  the whole texture; slot icons keep their template UVs (`own_uv = 0`);
- `0x418848` is a static descriptor `{frames, count}`; `sub_00037090`
  loads frame i's handle into `frames + i*0x24 + 0x20`, the word the sprite
  add reads. The heart is drawn only when the count is above 3 and frame
  3's handle is set; before the stage's HUD textures load, the slot shows
  the faint empty icon, never a frame of the panel's texture (which has no
  RETRY icon). `cry_icon(k, heart_loaded)` makes that choice, so it is
  tested with the rest of the logic.

The stock lit hearts above the gauge read c's RETRY count byte, record
`+0xF + c*6` (`0x6D8F6` and `0x6DB27`). The row lives in the first three
count bytes and never uses the fourth, so before this change the lit
hearts stayed dark with the mod on. Now each push writes the row's heart
count, at most two, into that byte: the lit hearts show the hearts in the
row as the stock game shows a partial set. Three hearts in the row have
granted a retry and still light two; the row emptying at four clears the
byte with the rest. The pickup's snapshot and undo cover the byte, since
it is inside the span.

Other code that touches the byte, from the generated code:

- `sub_000649B0`, where a retry is used (it decrements the held RETRY at
  `0xADCB07`): it copies characters 0 and 1's RETRY count bytes and held
  RETRY into `0xAE740C`, `0xAE7410`, `0xAE73CC` and `0xAE73D0`. Nothing in
  the generated code reads those back by address; with the mod on they
  hold the row's heart count, a value the stock byte can hold too (0..2).
- `sub_00152D80`, the stage goal's sequence (state `0xB8BD54`), writes the
  byte (a count mod 3) and the held RETRY at `+0xAF + c*8`. With the mod on
  that can light hearts the row does not hold, until the next pickup
  writes the row's count again.
- `tc_crystal_collect` reads the counts; the mod prepares them around it
  (D2), so its count of a heart crystal is the mod's, as for every colour.

No code found decides anything on the byte outside the pickup, so the
change is safe.

### D4. The proof in its own file

The live proof (archived D6) moves to `src/crystals_proof.c`; the mod calls
`cry_proof_init` when `RECOMP_DEBUG=crystals_proof` is set and
`cry_proof_frame` once a frame. `src/crystals_internal.h` holds what both
share: the API pointer, the guest block, the stats and the addresses.
`crystals_mod.c` holds only the mod. The proof gains:

- `kill:f`: player 1's hp (int16 at player `+0x6C`) to 0 at play frame f,
  so the game's own death and retry run over a row in progress;
- `hp` and `hearts` (heart quads drawn) in each log line.

### D5. Live runs

On the PC D3D11 bench (exe `c20bf613814e`), the mod on, frames dumped;
logs and frames in `runs/crystals-rewrite/`:

- **Heart:** heart crystals are counted into the row (`4 4` then `4 4 4`),
  the third grants a RETRY (held id1 1 to 2), and the row draws the gauge's
  heart in each heart slot (`heart-frames/crop_0030.png`, `crop_0040.png`).
  A REC spawn at cap 0 is refused, as in the stock game. After the review
  fixes (exe `f21e3d78610f`) the RETRY count byte reads 1, 2, 2 over the
  three hearts and the lit hearts above the gauge show them: two lit with
  two hearts in the row, two lit after the third grants (`heart2-*`,
  `heart2-frames/crop_0030_gauge.png`, `crop_0040_gauge.png`; before,
  `heart-frames/crop_0030_gauge_before.png`, none lit).
- **Death and retry:** a row of `1 5` carried from mission 1 past the 1-2
  checkpoint, then the barricade's monsters take Stick to hp 0 (play
  1260). After the retry prompt hp is back to 30 (play 1824) and the row is
  `1 5` (`die3-*`). A second run picks a third crystal after the
  checkpoint (`1 5 1`, mission 2), then dies the same way: after the retry
  the row is still `1 5 1` and the held RETRY count stays 1 (`die4-*`). The
  game's retry leaves the team record alone, so the row is kept as it was
  at the death, not rolled back to the checkpoint.
- **Stage end:** the input script's goal pokes (`evt_goal_state`
  `0xB8BD50`) did not end the stage, so the run reloads stg0101 through the
  stage loader's scene switch, the path a stage end takes. A `1 5` row is
  empty after the reload (play 403) and play goes on with an empty row: the
  stage start's rebuild (`sub_001A4100`) clears it (`stageend2-*`). The
  older run also shows a row carried into mission 2 (`1 5 1`) and a fourth
  crystal completing a PAUSE set among four, which empties the row.

## Tests

`scripts/test_crystals.py` compiles a driver over `crystals_logic.c` with a
model of the game's count, grant and gold over four teams: three, four,
mixed, after emptying, heart crystals, gold at the cap, every team and
character, a bounce (nobody counted, every span unchanged), a redirect to
another character or team, an undo, a toggle in the middle of a pickup
(`cry_settle`, also for an off and on in one frame), the row's hearts in
the RETRY count byte; `cry_icon` with the empty fallback; `cry_quad`
keeps or replaces the UVs
and scales about the centre; the name, the heart's texture and frame, the
env and doc rows, the descriptor, the golden stock value and the hook slot.

## Risks

- The heart's texture `0x418848` is the gauge's; a stage that never loads
  it leaves frame 3's handle 0, and the row then shows the empty slot (the
  check in D3), not a wrong texture.
- The goal-reached stage end itself was not reproduced on the bench (D5);
  the clear runs on the stage start, which both paths reach.
- The stage goal's sequence (`sub_00152D80`) writes the RETRY count byte
  itself; with the mod on, the lit hearts can then show a count the row
  does not hold until the next pickup (D3). Not seen on the bench.
- The row survives a death and retry as it stood at the death (D5), as
  the stock counts do; the delta spec says so. A checkpoint load
  (`sub_001A90F0`) restores the saved copy, which is not tested live. If
  BLiNX 1 rolled the row back on a retry, that is a follow-up.
- The archived Risks stand for the record, the toggle between a checkpoint
  and its retry, and the HUD slot loop.
