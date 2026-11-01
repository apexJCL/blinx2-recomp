## Context

The entity API (`entity-mod-api`) set the shape:
a game-level C API in cat, a pure logic file the tests compile over a fake
guest, an owner mod that is off by default, Mods-page settings with
`RECOMP_*` rows, a `[golden] enhance_stock` guard and a debug-tier proof
driver. This change follows it. It needs no toolkit change: mod API v6
(pinned `blinx2-v0.11.0`) has the hooks and guest memory it uses. It
makes no `guest_call` itself; the proof driver makes one (D9).

Addresses are the retail XBE's (`cat/game_files/default.xbe`), read from
`analysis/disasm/asm/text.asm` and the image itself
(`runs/shop-api/static/`, `runs/shop-api/scripts/xbe.py`).

## Findings (static; the live proof checks the parts marked *live*)

### The catalogue and the shop

- `menu_shop_catalogue` `0x4AACE0`: 53 records of 0x14 bytes in `.data`:
  `+0` name (a message pointer, 0 for records 50-52), `+4` a pointer the
  same for all, `+8` price (int), `+0xC` category, `+0x10` value. The
  game never writes the table.

  | records | category | value |
  |---|---|---|
  | 0 | 0 HP | hp added (10) |
  | 1 | 1 max HP | max hp added (10, capped at 100) |
  | 2-3 | 2 barrier | barrier level (3, 5) |
  | 4-5 | 3 jetpack | jetpack id (1, 2) |
  | 6-10 | 5 time control | control id (4, 3, 2, 5, 6) |
  | 11-20 | 6 space control and items | item id |
  | 21-49 | 7 weapon | weapon id (6-14 vacuums, 16-41 guns) |
  | 50-52 | 4 tank repair | repair amount (10, 20, 30) |

- `menu_shop` `sub_00210660` runs the shop for each player
  `p < [0xB22E3C]`: per-player state at `0xEB3AF0 + p*0x38` (`+0` state,
  nine states, jump table `0x210F28`; `+0x10` the cursor; `+0x18` the
  character chosen), the lineup `[0xE97F68 + (p*40 + slot)*4]` (catalogue
  indices, count `[0xEB3BF8 + p*4]`).
- A buy compares the record's price with the gold at `+0x14` of the player
  status `0xE9DA40 + p*0x2A4` (refused with sound 0x10B), applies the
  record by category (jump tables `0x210F4C`, then per character
  `0x210F6C`), then takes the price (sound 0x107). The price is read at
  the moment of the buy and each frame the shop draws it, so an override
  shows and charges at once (*live*).
- Character `k` of player `p` is `status + 0x40 + k*0x98`. A weapon buy
  (category 7) sets its `+0x50` weapon id and `+0x53` ammo (0 for a
  vacuum, `id < 0x10`; else the gun's ammo per purchase,
  `sub_00093EA0`). The weapon it replaces is refunded at its catalogue
  price *now* (`sub_00210F90`, the record of that category and id); the
  same for jetpacks and barriers.
- The status struct is not in the time record, whose regions are the
  players' objects `0xCD2440 + i*0x30C`, the enemy and item pools and the
  like. It is assumed to be what the save writes (open question 3).

### The story shop (found in the live proof)

The first price run (`price_pct=50`, the debug menu's SHOP entry) showed
the catalogue written (53 words) and the shop still at retail prices: the
story shop does not read the catalogue. `menu_shop` above is the
per-player shop (`p < [0xB22E3C]`), most likely the versus one.

- The story shop's prices come from four lists in `.data`, records of
  0x4C with the price at `+0x30` and the record's own index at `+0x34`:

  | list | VA | records | holds |
  |---|---|---|---|
  | 0 | `0x4938D0` | 43 | guns: record 1 the TS-2000 (400), 2 the TS-2100 (600) |
  | 1 | `0x494598` | 22 | not named (prices 0..1000) |
  | 2 | `0x494C20` | 23 | not named (prices 0..2500) |
  | 3 | `0x4952F8` | 38 | not named (prices 10..1000) |

  The game never writes them.
- `menu_story_shop_build` (`sub_001BFB10`, called from the scene
  dispatcher `sub_00062FB0` on entering the shop) copies each record a
  status unlock byte (`+0x74 + i`) allows into the stock at `0xE42600`
  (list `l` record `i` at `(l*0x46 + i)*0x4C`), caps the gold at 99999
  and stores a pointer to it at `0xE4257C`. The shop draws and charges
  from the stock; a sale pays half the price (`sub_001B15C0`). So a list
  price written before the shop opens shows on that visit; one written
  while it is open shows from the next.
- The story wallet is not the per-player status `0xE9DA40 + 0x14` (set to
  5000 in the run, the shop still showed 0); the pointer at `0xE4257C` is
  the lead (open question 4).

### The weapon stats

| stat | where | per |
|---|---|---|
| capacity | gun table `0x402860` `+4` | gun |
| ammo per purchase or pickup | gun table `+0xC` | gun |
| power | shot table `0x4022E0` `+0xC` | shot type |
| shot speed | inline in `sub_001A0260` (default 8.0) | gun |
| shot life (range = speed × life) | inline in `sub_001A0260`, the slot's `+0x12` | gun |
| fire interval | inline in the caller `0x19FFB7` (3, 10, 13 or 29 frames) | gun |

- **Gun table** `0x402860` (`.data`): records of 0x10, `{id, capacity,
  kind 0-3, ammo per purchase}`, ended by id -1; 20 guns. A gun not listed
  falls back to the code's default. `sub_00093EA0` reads `+0xC`; the
  player's capacity `+0x20A` is copied from `+4` when a gun is taken
  (`0x211FA`, `0x2133B`).
- **Shot table** `0x4022E0` (`.data`): 30 records of 0x24, indexed by shot
  type. `+0xC` is power: the hit code (`sub_000835F0` at `0x84190`)
  divides it by 10 for the damage it passes to `sub_00050800`, at least 1
  when it is 1..9. `+0x18` (a float, 8 to 40) is probably the hit radius
  and `+0x1C` the blast flag; not part of the API.
- **The fire function** `sub_001A0260(player*)` (6554 bytes), called from
  the player's fire gate (`0x1A005E` for guns, `0x1A012D` for vacuums):
  - takes one ammo (`+0x209`);
  - a switch on the gun id (tables `0x1A1C18`/`0x1A1C5C`) picks the shot
    type (the gun → shot map below), the speed (8.0, 4.0 for 22, 23 and
    32, 12.0 for vacuums, a charge for 25) and the count (3 for 27);
  - spawns each shot into the item pool `0xB22E68` (256 slots of 0x6C,
    `+0` used) through `ent_item_spawn` `sub_000794D0`, item type 0x25 (0x24
    for 32), with velocity `+0x2C..+0x34` = direction × speed and life
    `+0x12` (frames; 60 for most shots).
  - Gun → shot type: 16→8, 19→4, 21→6, 22→0xA, 23→0xB, 24→0xC, 25→0xD,
    26→6, 27→6, 28→7, 29→0xE, 32→0, 36→0x14, 37→0x18, 38→0x19, 41→0x1C,
    the rest 5. Guns 21, 26 and 27 share type 6: a power change on one is
    a change on all three.
- **Fire interval**: the player's float `+0x178` counts frames from the
  press (`+= 1.0` a frame, `0x19FF94`). A gun fires when it crosses the
  start (0.0; 18.0 for 19, the charge) and is busy until it reaches the
  gun's threshold (switch at `0x19FFB7`, tables `0x1A0228`/`0x1A0238`):
  3.0 for 21, 25, 26, 27, 29; 29.0 for 19; 13.0 for 16, 20, 22, 23, 24,
  28, 32, 35-38, 41; 10.0 otherwise.

## Goals / Non-Goals

Goals: read and override the catalogue; read and change the four weapon
stats; read and set owned weapons; a mod that shows each on the Mods page;
stock when off.

Non-goals: new catalogue records or a longer lineup (the lineup is built
elsewhere; not mapped); the vacuums' stats; the shot table's other fields;
the shop's text; anything in VS.

## Decisions

### D1. Overrides are host state, written to the guest on the guest thread

Every table change is an override held on the host: per catalogue record
a price and a value, per gun a capacity and an ammo per purchase, per
shot type a power, each -1 for none. Calls from any thread store it
(relaxed atomics, as `ent_type_hp`). The API's `on_frame` (the guest
thread, between two game frames) writes what changed: the effective value
is the override, else the game's own, times the mod's percent for that
stat (D7). The game reads the tables only on the guest thread, so it
never sees half an update, and a frame's latency is invisible in a menu.

The game's values are read once, at the first `on_frame` while on, after
a check that the three tables look as expected (catalogue record 0 price
50 and category 0, the gun table's first id 16 and its terminator at
record 20, shot type 5's power 10, each story list's last record holding
its own index, list 0 record 1's price 400 and list 3 record 0's 10).
A failed check turns the API off with
one line: another XBE or a moved table is never written.

### D2. Off gives every value back

`ent_api`'s rule: the owner's switch is the API's. Switching off (the
owner's `on_enable(0)`, on the guest thread) writes the game's values
back over every value the API changed, drops every override and every
percent's effect, and answers later calls `SHOP_OFF`. The fire hook is
dormant while off (the toolkit's rule), so no shot is scaled. Owned
weapons set while on stay: they are the player's state (D6).

### D3. Inline stats: a post hook on the fire function

Speed, life and the fire interval are immediates in code. A pre hook on
`sub_001A0260` notes which pool slots are free (256 bytes); its post hook
finds the slots that call took (free before, used after, item type 0x24
or 0x25) and scales their velocity and life by the gun's percents, life
at least 1 frame and at most 0x7FFF. The post hook then moves the fire
timer: for a gun (`+0x3E >= 0x10`) with an interval percent below 100,
`timer = threshold − (threshold − timer) × pct / 100` from the
thresholds above, so a 50 % interval leaves half the busy frames.
The timer only moves forward. The gate keeps the timer before the frame's
step at `[esp+8]` (`0x19FE2B`) and fires when that value is below the
start and the timer after the step is not (`0x1A0039..0x1A0053`); at the
threshold it clamps the timer and sets the state `+0x35 = 4`. A timer
moved back under the start would fire the gun again, so a percent above
100 (a slower gun) has no effect: the API accepts it (10..1000, as every
percent) and the mod offers 25..100. The
gate reads the timer right after the call returns (`0x1A00D8`), so a
timer at the threshold frees the gun that frame. Vacuum fires (the call
at `0x1A012D`, `+0x3E < 0x10`) are left alone.

Why a pool diff and not a hook on `ent_item_spawn`: that function has 85
callers; the fire function is the one place a player's shot is made, and
it runs on the guest thread inside the stage update, as the spawns do.

The hook is per gun id: `shop_gun_scale(id, speed, life, interval)`.
The mod's `speed_pct` and `interval_pct` apply to every gun on top
(multiplied). The mod leaves life alone: range is speed × life, so it
follows speed. API callers may set life alone. Guns 37 and 38 keep their
interval: their gate takes another path (`0x19FFFB`, a lock-on test
and a fixed timer of 2.0).

### D4. Threads and statuses

```c
enum shop_status { SHOP_OK, SHOP_OFF, SHOP_RANGE, SHOP_GONE, SHOP_BUSY };
```

- Reads (`shop_item_get`, `shop_gun_get`, `shop_owned_get`) run on the
  guest thread (an `on_frame` or a hook) and return `SHOP_BUSY` elsewhere,
  as `ent_list`. `shop_item_count` and the stat tables' static facts
  (`shop_gun_shot`, the gun → shot map; `shop_gun_count`) are any thread.
- Overrides (`shop_item_set`, `shop_gun_set`, `shop_shot_power_set`,
  `shop_gun_scale`) are any thread: `SHOP_OK` (written at the next
  `on_frame`), `SHOP_OFF`, `SHOP_RANGE` (out of range: a price outside
  0..999999, a value that names no item of its category, a capacity
  outside 1..99, an ammo per purchase above the capacity, a power outside
  0..999, a percent outside 10..1000), `SHOP_GONE` (no such record, gun or
  shot type). Each call sets every value it takes; a negative one gives
  the game's back (clears that override).
- Every set answers `SHOP_OFF` until the first `on_frame` after the
  switch: the checks need the game's values, which that frame reads
  (D1).
- `shop_owned_set` (guest thread only) writes a character's weapon and
  ammo as a buy does; `SHOP_RANGE` for a weapon id the catalogue does not
  sell or ammo above its capacity (the gun table's value now, percents
  included; 0 for a vacuum). Guns 17 and 18 are sold but not in the gun
  table (the code's default), so they take 0..99.

### D5. Rewind and checkpoints

The tables (and the story lists, D10) are `.data`, outside the time record: a rewind or a
retry leaves the current overrides in place and never brings an old
value back. Shots are scaled inside the fire call, before the frame's
time-record step copies the pool, so a rewound shot comes back already
scaled and is never scaled twice (the hook acts only on slots the call
itself took). The fire timer is in the player's object, also recorded,
so a rewind restores the timer the hook wrote. Nothing to undo.

### D6. Saves

The save holds the player's progress (gold, owned weapons, items; assumed
to be the status struct, open question 3), never the `.data` tables. So:

- prices and stats are never saved: a save made with the mod on loads
  with stock prices when the mod is off;
- gold spent at an overridden price, a weapon bought, and a weapon set
  through `shop_owned_set` are the player's, as any purchase, and stay
  after the mod turns off. The Mods page says so;
- a refund (buying over a weapon, jetpack or barrier) pays the old item's
  price at the time of the refund, the game's rule: a price changed
  between the buy and the refund gains or loses the difference. Kept: the
  API does not track purchases.

### D7. The `shop` mod

Settings (`mods.shop.*`, live):

| name | env | range | effect |
|---|---|---|---|
| `enable` | `RECOMP_SHOP` | off/on | the API and the rows |
| `price_pct` | `RECOMP_SHOP_PRICE_PCT` | 10..500 % (100) | every price |
| `ammo_pct` | `RECOMP_SHOP_AMMO_PCT` | 50..500 % (100) | capacity and ammo per purchase, clamped to 1..99 |
| `power_pct` | `RECOMP_SHOP_POWER_PCT` | 50..500 % (100) | every gun's shot power |
| `speed_pct` | `RECOMP_SHOP_SPEED_PCT` | 50..300 % (100) | gun shot speed (and range) |
| `interval_pct` | `RECOMP_SHOP_INTERVAL_PCT` | 25..100 % (100) | gun busy frames (only shorter, D3) |

A Status row ("on: prices 50 %, …", or why it is off). No controls.
Rounding: prices to the nearest 10 like the game's, at least 10;
everything else to the nearest integer, at least 1 (power at least 0).

### D8. Hook slot

`0x001A0260` joins `[mods] hook_functions`. The function returns nothing
in `st0` (its gate pops the FPU stack before the call); `no_st0` names it
if the analysis cannot settle it. It changes gen: goldens run.

### D10. The story shop's price lists

The story shop charges from its own lists (Findings), so the API covers
them as it does the catalogue: per list record a price override (-1 for
none), read once with the rest, written by `on_frame` with the mod's
`price_pct` on top (same rounding, a free record stays free), given back
when off. `shop_list_count`, `shop_list_price_get` (guest thread: now
and the game's) and `shop_list_price_set` (any thread; `SHOP_RANGE`
above 999999, `SHOP_GONE` for no such list or record). The stock at
`0xE42600` is not written: the game rebuilds it from the lists on every
visit, so a change shows from the next one, and after off the visit in
progress keeps the prices it opened with. The lists are `.data`, so D5
and D6 hold as for the catalogue. Naming lists 1-3 is open question 5.

### D9. The live proof (`RECOMP_DEBUG=shop_proof=<steps>`)

A debug-tier driver in the mod, steps joined by `+`:

- `log:1` writes a per-frame line (`out:file`, default `shop_proof.tsv`)
  of the shop state, player 0's gold, the lineup's first records and
  their prices, and player 0's weapon, ammo and fire timer, plus one line
  per scaled shot;
- `gun:<id>+fire:<f>+every:<n>+shots:<k>`: from frame f of play (first
  checkpoint, as `entities_proof`), give player 0's object gun `id` and
  ammo, and call the fire function on it every n frames, k times
  (`guest_call` on the guest thread), so the run fires without a pad
  binding for the gun;
- `gold:<n>+goldat:<f>`: player 0's gold set to n at frame f of the run
  (counted from the first frame, not the checkpoint), so a buy in the
  shop can be afforded.

Proof plan (PC D3D11):
1. Price: the debug menu's SHOP entry (title state 1, cursor 10) with
   `price_pct=50`: the Arms page shows the TS-2000 at 200 and the
   TS-2100 at 300 (D10; the log's `arms` field gives both list words), and a buy takes the
   halved price from the gold (log). With the mod off, the same route
   shows the stock prices.
2. Stat: `@stage1` with `gun:16` fires: at `speed_pct=200` the shots'
   speed is twice the stock run's, at `power_pct` the shot type's power
   in the table is doubled (log). Frames under `runs/shop-api/` only.

## Risks / Trade-offs

- Shared shot types: power is per shot type, not per gun (21, 26, 27).
  `shop_gun_get` names the type; the mod scales all guns alike.
- The lineup is out of scope, so an override cannot add an item to the
  shop. A value override can turn a record into another item of its
  category.
- `shop_owned_set` during a stage writes the status the next stage start
  copies into the player; whether a running stage reads it again is not
  mapped (open question 1).

## Open questions

1. When does the stage copy a character's weapon from the status into the
   player object? Assumed: at a stage start. The API documents
   `shop_owned_set` as "from the next stage".
2. Does any code outside the shop and `sub_00093EA0` read the gun table's
   `+0xC` (pickups)? Then `ammo_pct` changes pickups too, which the mod's
   help says.
3. Which memory the save writes (`blinx2data.bin`). Not mapped; the
   live proof checks the part D6 relies on: a save made with the mod on
   loads stock prices with the mod off.
4. Where the story shop's wallet lives: the status the pointer at
   `0xE4257C` names (`menu_story_shop_build` sets it). Not needed by the
   API; a gold call for the story mode would need it.
5. What story lists 1-3 sell (items, costumes, and the like). The API
   indexes them by list and record; names can follow without a change.
