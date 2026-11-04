## Why

The `crystals` mod (openspec change crystal-sets) gives BLiNX 2
BLiNX 1's crystal row. Two things came back from play (the user,
2026-11-03):

- Its name says nothing about what it does. On the Mods page it reads
  "crystals", which could be any crystal tweak.
- A heart crystal (the RETRY colour) leaves an empty slot in the row. The
  row draws each crystal with its control's icon from the time-control
  panel, and the panel has no RETRY slot: retries live in the heart gauge.

The user also asked for a rewrite: the first version grew through its
live proof, and its pickup step, hook depth bookkeeping, toggle settling
and proof driver sit in one 700-line file.

## What Changes

- **Player-facing name "BLiNX 1 crystals".** The mod's name on the Mods
  page, its enable row's label and its summary ("Collect crystals the
  BLiNX 1 way: a row of four"). The reason is in design D1. The mod id
  `crystals`, the key `mods."crystals.enable"` and the env keys
  `RECOMP_CRYSTALS` and `crystals_proof` stay, as the Bloom rename kept
  `glow` (cat c5f51d40), so settings files and scripts keep working.
- **Heart crystals show in the row**, drawn with the heart the game draws
  above the heart gauge (texture `0x418848`, frame 3), at the slot's size.
- **Rewrite, same behaviour:**
  - one pickup step (`struct cry_pickup`: begin, end, undo) over every
    team's span replaces the prepare, counted and settle helpers;
  - one quad helper (`cry_quad`) for the row's slot icons and the heart;
  - the live proof moves to `src/crystals_proof.c`, so `crystals_mod.c`
    holds only the mod; the shared bits are in `src/crystals_internal.h`;
  - the proof gains `kill:f` (player 1's hp to 0) for the death and retry
    case the first version left untested.
- **Tests:** `scripts/test_crystals.py` drives the new pickup step on four
  teams, the redirect to another character, the undo, the quad's UVs for
  slot icons and for the heart, and checks the name and the heart icon.
- **Live runs** of the cases the first version left open: a heart crystal
  in the row, a death with a partial row, and the stage-end clear.

## Capabilities

### Modified Capabilities
- `crystal-sets`: the row shows heart crystals; the mod is shown as
  "BLiNX 1 crystals".

## Impact

- Off by default; with it off nothing changes and no golden moves.
- No new hook slot, no gen change, no new config key.
- With the mod on, the stock lit hearts above the heart gauge light for
  the row's heart crystals, up to two, as they do in the stock game for a
  partial set (design D3). Before this change they stayed dark.
