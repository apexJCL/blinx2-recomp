## Context

What the spikes settled (`entity-system-spike` design, part B on
`spike/entity` 9770730, part C on `spike/enemy-respawn` 4da65a8, both
reviewed; names in `config/symbols.toml` since the tracker item):

- **List** `ent_enemy_list` `0xAF0E88`: +0 head of {prev, next, obj} nodes,
  +0x14 count. Pool `0xADE790` in .bss, 34 slots, fixed. Objects are 0x2C0
  bytes at odd addresses (slot = used byte + object), so host reads use
  `memcpy`.
- **Object**: +0 class, +4 state, +0x10 placement*, +0x28/+0x2A hp/max
  (shorts), +0x2C id, +0x48 pos, +0x6C rot, +0x98 update, +0xAC the dead
  counter. Ids come from the serial `0x680F84` and are -1 once it reaches
  0xFF, so an id alone names nothing.
- **Spawn** `ent_enemy_spawn` `sub_0004EE20(placement*)`, EAX = list. It
  takes a slot and a node, then refuses at count > 0x21 without giving them
  back; the class init (a switch on `class & 0xFF`) links the object and
  bumps the count, so an unknown class leaks too. The object keeps the
  placement pointer and reads it again: the respawn gate reads +0x30
  (group), +0x34 (zone) and +0x54 (mode, crystal colours), and a respawn
  puts the enemy back at the placement's position.
- **Death and respawn**: a kill leaves the enemy listed in state 0xA. Mode
  0 and 1 records reset it in place after 300 or 450 frames, never while
  `stage_play_mode` `0xAE46EC` is not 0; mode 2 and up never.
- **Removal** `sub_0004ED30` runs only when an update returns nonzero or at
  teardown; a rewind can also drop an object with no remove call.
- **Rewind**: rewinding past a spawn removes the enemy (count 29 → 28); a
  spawn made during REW is undone on the next frame. Both silently.
- **Cap**: keep 34 (C3). A raise needs the pool moved, four inline limits
  patched and probably a time-record redesign (89,650 of 92,160 bytes on
  5-1, and an over-budget region is dropped silently).
- **Registry** `0xADA9B0` and checkpoints: placements load only at area
  setup; the registry's dedupe plausibly never runs (C5). C5 also said the
  checkpoint snapshot holds no enemy state; that is wrong (PC run E4, D5):
  the snapshot is a time-record frame, and it holds the list header and
  the pool.
- **Types**: no general table. `0x4AFCD8` is class 1's variant table
  (stride 0x20, hp short at +0xC; review of part B).
- **Proof**: a copy spawned from the pre hook of `sub_0004E700` and killed
  through `sub_00050800(obj, src pos*, 1.0f, dmg, 0, 0.0f, 0)` from the
  same hook works (run `live-2`).

The mod API (v5) gives hooks, `on_frame`, the descriptor, menu rows and
actions, but no way to call a guest function or to own guest memory: the
spike declared gen's `sub_*` and the `g_*` registers `extern` and saved
eight of them, missing `g_ebp`, the x87 stack beyond the top and SSE.

## Goals / Non-Goals

**Goals:** one C API for cat's mods over the enemy list (list, read,
spawn, kill, type overrides) with every guard the spikes asked for; a mod
that exposes it in the menu by the mod-settings rules; off is stock.

**Non-goals:** a raised cap; new enemy behaviour (code, a later mod);
the item and projectile pool `0xB22E68`; placement-wide respawn overrides
(part C's `ent_respawn` settings, a follow-up); BLiNX 1 (its own layouts,
a follow-up); a game-agnostic entity interface in the toolkit.

## Decisions

### D1. Toolkit: `guest_call` and `guest_alloc` in mod API v6
Both are game-agnostic and every title's entity work needs them, so they go
in the toolkit (mod-connectivity layer: the toolkit gives the generic layer,
the game the knowledge).

```c
/* v6. Guest thread only (a hook or on_frame); 0 with a line elsewhere. */
struct xbox_guest_args {
    uint32_t eax, ecx, edx;        /* register arguments */
    const uint32_t *stack;         /* pushed right to left */
    uint32_t n_stack;              /* at most 16 */
};
int (*guest_call)(uint32_t va, const struct xbox_guest_args *a, uint32_t *eax_out);
/* First call allocates; size fixed for the run, never freed. 0 on failure. */
uint32_t (*guest_alloc)(const struct xbox_mod *m, uint32_t size, uint32_t align);
```

- `guest_call` finds the function with `recomp_lookup(va)`, saves the full
  register set (the `IrqRegs` save in `kernel_hal.c`, moved to a shared
  `recomp_regs.h` so the DPC path and this one stay one list), builds a
  frame 0x100 bytes below the current guest esp aligned to 16, pushes the
  arguments and a return address, runs it, reads eax and restores every
  register. The callee's pops do not matter: esp is restored. This is the
  "restore `g_ebp` around guest calls" guard, done once for every mod.
  (Implementation: the shared save is `src/kernel/recomp_regs.h`; it also
  holds `g_mxcsr`, which the old `IrqRegs` list missed, so a callee that
  changes the SSE rounding mode cannot leak it into the hooked function.)
- `guest_alloc` takes the block from the kernel's contiguous arena
  (`xbox_ContiguousAlloc`, the allocator behind
  `MmAllocateContiguousMemoryEx`, zeroed), so the guest heap never gives it
  out. One block per mod, asked from the guest thread at the first use, so
  a mod that is off never allocates and the guest's memory map is stock.
  The block's address is in the contiguous window (0x80000000, 64 MiB),
  mapped at the same offset as main RAM, so `mem + va` still reaches it but
  a bounds check against `g_xbox_total_ram` alone would refuse it; the
  cat side accepts both windows. Both calls refuse a thread without the
  kernel's guest-thread mark (`xbox_DpcIsGuestThread`), even inside a
  callback, and the first `guest_alloc` runs under a lock so two guest
  threads still get one block.
- A ctest covers both with a stub lookup: registers restored bit for bit
  (`g_ebp`, `g_seh_ebp`, `g_fp_top`, an xmm), the arguments where the
  callee reads them, refusal off the guest thread.

### D2. The API is cat's, owned by one mod
Layouts and addresses are BLiNX 2's, so the API lives in cat. The hooks need
an owner, so the `entities` mod (D8) registers them and the API is live only
while that mod is on; another cat mod calls the functions and gets
`ENT_OFF` while it is off. One owner keeps one hook per slot and one record
block.

### D3. The C surface and its threads

```c
struct ent_handle { uint32_t obj, placement; int16_t id; };
struct ent_info {                  /* a host copy, filled with memcpy */
    struct ent_handle h;
    uint32_t cls, state, flags;
    int16_t hp, hp_max;
    float pos[3], rot[3];
    uint16_t dead_frames;          /* +0xAC while dead */
    uint8_t dead, spawned;         /* state 0xA; one of the API's */
};
enum ent_status { ENT_OK, ENT_OFF, ENT_BUSY, ENT_TIMEOUT, ENT_TIME_CONTROL,
                  ENT_CAP, ENT_CLASS, ENT_RECORDS, ENT_GONE, ENT_DEAD,
                  ENT_MODE, ENT_LEAK, ENT_CALL, ENT_IGNORED };
struct ent_spawn_spec {
    struct ent_handle from;        /* copy this enemy's placement, or */
    int32_t stage, record;         /* stage table 0x4921E8[stage] record; -1 */
    float pos[3]; uint8_t has_pos; /* else the source's position */
    float rot_y;  uint8_t has_rot;
    uint8_t respawn;               /* ENT_RESPAWN_NEVER (default), _KEEP */
};
typedef void (*ent_done_fn)(enum ent_status s, struct ent_handle h, void *user);

int  ent_list(struct ent_info *out, int max);          /* guest thread */
int  ent_read(struct ent_handle h, struct ent_info *o);/* guest thread */
int  ent_count(void);                                  /* any thread, relaxed */
enum ent_status ent_spawn(const struct ent_spawn_spec *s, ent_done_fn, void *);
enum ent_status ent_kill(struct ent_handle h, ent_done_fn, void *);
enum ent_status ent_type_hp(uint32_t variant, int16_t hp); /* -1: the game's */
```

- **Reads** (`ent_list`, `ent_read`) run on the guest thread: the thread
  that ran the mod's first `on_frame`, recorded then; elsewhere they return
  -1. They walk at most 64 nodes and stop at a pointer outside guest
  memory, and copy each field with `memcpy`.
- **A handle** is valid while its object is listed and still holds the same
  placement pointer and id. A respawn in place keeps all three, so a handle
  survives it; a pool slot reused by another enemy fails it.
- **Requests** (`ent_spawn`, `ent_kill`) may come from any thread (the
  menu, an action, a hook). They go into a locked ring of 16 and return
  `ENT_OK` (queued) or `ENT_BUSY`/`ENT_OFF` at once (a ring found over
  full when drained answers its youngest requests `ENT_BUSY`). The pre hook of
  `sub_0004E700` takes them on the guest thread, inside the stage update,
  before any enemy runs that frame, where the spike called both. Each
  request ends with exactly one `done` call: a spawn's there, a kill's
  from `on_frame` once its hit shows (D7), or `ENT_TIMEOUT` from
  `on_frame` when no enemy update ran for 60 frames (no stage, a menu).
- **Type overrides** (`ent_type_hp`) are stored and applied at the next
  area setup (D6).

### D4. Spawn: the guards, in the order they run
In the pre hook, for each spawn request:
1. `stage_play_mode` must be 0, else `ENT_TIME_CONTROL` (D7).
2. `stage_team_mode` `0xB21CB4` must not be 3 (VS), else `ENT_MODE`: two
   players and the VS play-mode values were never tested.
3. The source: a listed enemy (handle valid) or a record inside the stage
   table's bounds, else `ENT_GONE`.
4. `class & 0xFF` must be in the allowlist, else `ENT_CLASS`. The list is
   the classes the game's own tables spawn (every `0x4921E8` entry and the
   extra sets `0x4923C8`/`0x4925A8`), built statically and checked in by
   the implementation, minus any whose init spawns again (the class whose
   init is `ent_enemy_init_spawner` `sub_00258AB0`) unless the caller
   audit (step 5) shows that nested spawn checks the count.
5. The cap: `count + 1 + reserve <= 34`, else `ENT_CAP`, checked before the
   call so the game's refusal and its leak never happen. `reserve` covers
   the game's own mid-stage spawners that do not check the count first;
   the implementation audits every caller of `sub_0004EE20` and sets it (0
   if all check, as the class 9 nest does).
6. A free record, else `ENT_RECORDS` (D5).
7. Copy the source placement (0x5C bytes) into the record, set position,
   rotation and the respawn mode (`ENT_RESPAWN_NEVER` writes 2 in the top
   nibble of +0x54 and keeps the colour bits), call `sub_0004EE20` through
   `guest_call` with EAX = the list.
8. The count must have grown by one, and the new tail object must point at
   the record; then `ENT_OK` with its handle. Otherwise `ENT_LEAK`, one
   log line, and spawns stay refused until the next area setup: something
   the guards did not foresee happened, and a second try would leak again.
   Switching the mod on again clears the refusal (the user's retry; the
   cap still guards the count). When the toolkit refuses the call itself
   (`guest_call` fails), the record is released and the answer is
   `ENT_CALL`: nothing was spawned.

### D5. Placement records: API-owned; a new area removes the old copies
The object reads its placement for as long as it exists, dead included
(respawn gate, respawn position). So the record must outlive the object,
and a rewind can bring an object back after the API thought it gone. Hence:
- one `guest_alloc` block of 128 records (128 × 0x5C = 11,776 bytes) plus
  a used byte each, all in guest memory, so a future save state
  (`save-states`) carries them with the objects that point at them;
- the used byte has four states: 0 free, 1 used, 2 marked (used before
  the last area setup), 3 retired (swept, not reused until the next stage
  start). A record is never reused within a stage;
- **a retry removes the API's copies.** After `stage_area_setup`
  `sub_000606F0` (D9: a call from its wrapper in `src/recomp_manual.c`)
  every used record is marked. Every enemy update, in the pre hook of
  `sub_0004E700` before the requests, the sweep takes every listed object
  whose record is not in use (marked, retired or free) off the list, then
  retires each marked record no listed object points at.
  The copy is gone after a retry, as after a REW past its spawn, and gone
  again the frame after a REW brings it back (run E5: the ring's oldest
  frame after a retry is the restored checkpoint, copy listed). Retiring
  instead of freeing keeps such a copy from ever pointing at a record a
  new spawn took. A mission switch (1-1 to 1-2) runs no area setup, so its
  copies carry over, as before;
- **retired records go free only at a stage start** (review). The
  checkpoint frame `[0xDDD194]` keeps the copy, so every retry from it
  brings the copy back. Freeing the retired records at the retry's own
  setup let the second retry restore a copy pointing at a free record,
  which the sweep then left listed. The wrapper reads its return address:
  `0x6324D` is the stage start (`sub_00062FB0`, which takes a new
  checkpoint); `0x7533A` is the retry and `0xEB0D4`, `0x20F504` the
  teardowns before a menu, which mark but free nothing;
- **a copy of a free record goes too.** No game placement lives in the
  API's block, so a listed object pointing at a free record is always a
  copy: a restore from before the stage start that freed it. The sweep's
  cheap path does not see one (it reads only the used bytes), so
  `on_frame`'s check, which walks the list each frame for
  `ent_api_spawned`, flags it and the next sweep walks. The copy gets
  that frame's update first;
- **switched off after a spawn, the sweep goes on.** The block and its
  copies outlive the switch: the area setups keep marking (the wrapper
  runs whatever the state), and since the toolkit runs no hook of a mod
  that is off, `on_frame` runs the sweep instead, after the frame's enemy
  update. Off still takes no request, and a session that never spawned
  allocates nothing and changes nothing;
- **the sweep stays cheap.** Without a marked or retired record (no retry
  since the last spawn-free setup) it reads the 128 used bytes and
  returns. Otherwise it walks the list (at most 34 nodes) once, twice when
  it unlinked something;
- **running out.** A spawn-heavy session with retries can use every record
  in one stage: 100 spawns, a retry (100 retired), 28 more. The next
  spawn then answers `ENT_RECORDS` from guard 6 (D4), before the guest
  call, with nothing written, and the next stage start frees the retired
  ones. `ENT_RECORDS` rather than `ENT_BUSY`: busy means the request ring
  is full and a retry next frame can work, while no record frees before
  the next stage start;
- **never retire a record a listed object points at.** The sweep unlinks
  and retires only after a walk that reaches the list's count
  (`0xAF0E9C`). A short walk does nothing; a marked record a listed object
  still points at (one on another list header, which the sweep will not
  rewrite) stays used. Either way the sweep runs again next frame and logs
  one line every 300 frames while it waits. Spawns made meanwhile take
  fresh records, so the wait refuses nothing but spawns past 128;
- the sweep logs a copy of a free record once per area setup (a held REW
  restores it every frame);
- `0xADA9B0` is not written. C5 found no reader that matters, and the
  checkpoint reload does not re-run the loader (open question 4: settled,
  the loader chain is its only reader).

Why the next enemy update and not the setup's return (PC run E4, open
question 3). The retry is `sub_00075210`, from the stage state machine
`sub_00062FB0`. It runs, in order:
1. `sub_00061D60(1)`, the teardown, which removes every enemy through
   `sub_0004ED30`: unlink (`sub_0004EDC0`), `sub_00050DB0`,
   `sub_00049300(obj, -1)`, the entry in `0xE21674`, the `0xB87154`
   share, the class destructor at `obj+0xA4`, and the pool's used bytes;
2. `sub_000606F0(2, 0)`, the area setup, which loads the placements
   afresh;
3. `sub_00078350`;
4. `sub_00076030(1)`, which calls `sub_001A90F0`, the checkpoint restore.
   It copies the checkpoint's time-record frame back and applies its
   regions (`sub_001A8D80`). `sub_00074FF0` registers the list header
   `0xAF0E88` (0x58 bytes) and the pool as regions, so the restore puts
   back the list as it was at the checkpoint, copy included.

A copy spawned after the checkpoint therefore comes back listed, with its
object memory, links and used bytes, but not what the teardown released
outside them (`0xE21674`, `0xB87154`, the destructor's work, which no
region covers). That is the copy E4 saw frozen in state 5. The originals
work because the fresh load re-created them. The sweep unlinks such a
copy and clears its two used bytes, as `sub_0004ED30` ends, and runs
nothing else again: the teardown already ran the destructor,
`sub_00050DB0` and `sub_00049300` on it, and a second run would release
twice. None of the four steps reaches `sub_0004E700` (static call graph
from each), so the first enemy update after the setup comes after the
restore.

The other setup callers: `0xEB0CF` and `sub_0020F4F0` (both `(1, 0)`) run
the teardown first, like the retry. The stage start (`sub_00062FB0`,
`0x63248`) runs the setup without one, but it starts a stage, after the
last stage's teardown, so no copy of the API's is live then.

### D6. Type overrides before the placements load
`0x4AFCD8` is class 1's variant table and the only type data known, so the
API offers class-1 variant hp only. Before `stage_area_setup` runs
(before `sub_0004F970` and the extra set `sub_00160E70` load), the API
writes the stored hp into each variant, saving the original at the first
write; clearing an override (or the mod going off) writes the original back
at the next area setup. While the mod is off that call only gives the
saved hp back, once. Enemies already spawned keep their hp, as in the
spike. The table holds four variants (indices 1..4; index 0 and 5 on are
code pointers); a variant whose hp is not plausible (1..9999) at the first
write is left alone with one line. `hp_scale` is the owner's (set through
`ent_api_hp_scale`); an explicit `ent_type_hp` wins over it.
More fields join only once a spike names them in the symbol map.

### D7. Time control and kills
`stage_play_mode` holds the active time control and other modes (2 leaving
the hub, 0x800 skipping events). The game's own respawn gate refuses at
any nonzero value, and REW undoes a spawn made before or during it. So the
API refuses spawns at any nonzero value too; the mod reports it in the
Status row and the caller may try again.

Kills go through the game's hit path, the one the vacuum uses. A kill
during REW would be rewound, and PAUSE, SLOW, FF and REC were never tested
with an outside hit, so kills take the same guard for now (open question
1). Settled by the PC proof: PAUSE and SLOW let a kill through (its death
runs and holds after the control and after a REW); REW, FF, REC and the
other modes still refuse. A kill also refuses a dead enemy (`ENT_DEAD`) and a gone one
(`ENT_GONE`).

The game ignores a hit on a dormant enemy (state 0, PC run A4) and on an
idling one (run Q7d): `sub_00050800` returns and the hp stay as they were.
So `done` does not come at the call. The hit shows in the next frame's
enemy update, under PAUSE and SLOW as in normal play (runs Q1b-*), and
the next update's pre hook checks for it (`on_frame` too): `ENT_OK` once
the enemy is dead, below its hp at the call, or off the list;
`ENT_IGNORED` when 4 enemy updates pass without that (updates, not frames:
a frame without one cannot show the hit), `ENT_TIMEOUT` after 60 frames
with no update. 16 kills an update, each answered by its fourth, keep at
most 64 in flight; the queue holds 64 and checks for room before the
damage call (`ENT_BUSY`), so no sent kill goes unanswered.
A distinct status, not a retry: whether the enemy wakes is the game's, and
the caller may ask again. A guest call the toolkit refuses answers
`ENT_CALL`, as for a spawn.

### D8. The `entities` mod and the menu
Descriptor (mod-settings rules: info, rebindable controls, every sensible
setting):
- `enable`: enum `off`/`on`, the switch, live through `on_enable`
  (idempotent; off drops queued requests with `ENT_OFF` and clears the
  overrides, undone at the next area setup). Env `RECOMP_ENTITIES`.
- `hp_scale`: int 1..10, default 1: class-1 enemies get their hp times
  this, from the next area setup (its help says so). Env
  `RECOMP_ENTITIES_HP_SCALE`.
- Controls, ACTION, unbound: `spawn` (a copy of the enemy nearest player
  0, 40 units along x and along z from the player, from its placement record) and
  `kill` (the nearest live enemy).
  Env `RECOMP_ENTITIES_SPAWN_KEY`, `RECOMP_ENTITIES_KILL_KEY`.
- Rows on the mod's page: Status (INFO: "12 of 34 enemies, 1 spawned; last:
  refused, time control running"), "Spawn a copy of the nearest enemy",
  "Defeat the nearest enemy". The result of a press also toasts.
- `[ENHANCE] mods=` lists the mod while it is on (no `active` call).

A debug-tier row `RECOMP_DEBUG=entities_proof=<steps>` (`spawn:f`,
`fill:f`, `kill:f`, `rew:f`, `spawnrew:f`, `out:<file>`; f a play frame as
in the spike: the frames from the first checkpoint of a stage with
enemies; `spawnrew:f` is a REW request at f and a spawn 30 frames later)
drives the API itself for the live proof and logs the list each frame. It calls only the public API, so the proof tests what mods use.

### D9. Hook slots and their gen impact
`game.toml` `[mods] hook_functions` gains, permanently:

| slot | name | use |
|---|---|---|
| `0x0004E700` | `ent_enemy_update_all` | pre: take the requests (D3, D4) |

`stage_area_setup` `sub_000606F0` cannot be a slot: `src/recomp_manual.c`
defines it by hand (the free camera's wrapper), and `blinx2 recomp` refuses
a hook on a function it does not emit. The wrapper calls
`ent_api_area_setup(0, stage_start)` before its gen call (type overrides,
D6) and `ent_api_area_setup(1, stage_start)` after it (mark the records
for the sweep, and at a stage start free the retired ones, D5);
`stage_start` is its return address at `[esp]` being `0x6324D`. Both
return at once until the mod has attached. `sub_0004E700`'s callers (0x673A4, 0x673BB) pop
its argument and read no float, but the x87 walk cannot settle its depth,
so `game.toml` `[mods] no_st0` lists it. It runs twice in a frame when
`[0xB2A740]` is 4; the requests drain at the first.

No hook on `sub_0004EE20`, `sub_0004ED30` or `sub_00050800`: the API calls
the first and last, and removal is seen by the liveness check, which also
catches a rewind's removal that no hook would. Both functions return no
float; `no_st0` lists them only if the x87 walk cannot settle it. Gen
changes in `sub_0004E700`'s wrapper and in `config/hook_functions.json`:
`blinx2 analyze`, then `blinx2 recomp`, and the goldens. Gen is not
tracked; `config/hook_functions.json` is committed.

### D10. Failure modes
| failure | result |
|---|---|
| toolkit below v6 | the mod fails its init with one line; nothing else changes |
| a hook slot missing | same |
| `guest_alloc` fails | spawns answer `ENT_RECORDS`; kills and reads still work |
| a spawn leaks (D4.8) | one line, spawns refused until the next area setup |
| a restore brings back a copy of a free record (D5) | unlinked at the next enemy update after `on_frame` sees it; one line per area |
| a retry or rewind brings back a swept copy (D5) | unlinked at the next enemy update; one line per 300 such frames (a held REW restores it every frame) |
| the mod switched off after a spawn (D5) | no requests; the area setups still mark and `on_frame` sweeps |
| every record used or retired (D5) | spawns answer `ENT_RECORDS` until the next stage start |
| the area sweep's walk short, or a marked record still referenced (D5) | records held, retried each frame, one line per 300 frames |
| a kill's hit ignored (D7) | `ENT_IGNORED` after 4 enemy updates (`ENT_TIMEOUT` after 60 frames with none) |
| kills in flight | at most 64 (16 an update, answered by the fourth); a 65th would answer `ENT_BUSY` before its damage call |
| the list walk hits a bad pointer | the walk stops there; the read reports what it had |

## Tests

- **ctest (toolkit)**: `guest_call` and `guest_alloc` (D1).
- **`scripts/test_entities.py`** compiles a driver against
  `src/ent_api_logic.c` over a fake guest memory: the guard order and each
  status, the cap with reserve, the allowlist, record allocation and the
  area-setup free (referenced records kept), the respawn nibble, handle
  validity across a respawn and a slot reuse, the list walk on odd
  addresses and a broken chain, override apply and restore. It also checks
  the keys: env rows, `docs/env.md` rows, the descriptor names,
  `enhance_stock`.
- **Live proof, Metal (Mac) and native Windows (PC)**, `@stage1`, mod on,
  `entities_proof`, frames dumped:
  1. list each frame; `hp_scale=3` gives class 1 3/3;
  2. spawn beside the player: it moves and hits the player (frames);
  3. kill it: hp 0, state 0xA;
  4. a spawn asked during REW answers `ENT_TIME_CONTROL`, count unchanged;
  5. rewind past a spawn: the handle reads gone, the record stays used,
     no stale-record line;
  6. `fill`: spawns until `ENT_CAP`; the pool's used bytes and the count
     show no leak;
  7. stage change (`@stage1` then the next area): records retired;
  8. a retry after a death (run E4's flow), then REW 30 frames later: the
     copy off the list after the retry and again after the REW, its
     record retired, no stale-record line.
- **Off**: the mod off logs `[ENHANCE] mods=none`, no `[MOD entities]`
  write lines, and no allocation.

## Open questions (with how the implementation settles them)

1. **Kills under PAUSE, SLOW, FF and REC.** Refused for now. Live: kill a
   spawned enemy under each; allow those that stick after the control ends
   and after a rewind past it. REW stays refused.
   Settled (PC runs Q1b-*, Q1orig): a kill under PAUSE or SLOW dies and
   holds after the control and after a REW, as the unpaused baseline does,
   so both are allowed. A REW after a kill does not undo it, the same as
   for an original enemy the API kills (class 0x210, run Q1orig; that
   class dies into state 3, not 0xA): the game's own behaviour. REC's playback runs the death a second time and a
   later REW reverses it, so REC stays refused. FF stays refused untested:
   a 0x400 request never changed the mode on 1-1. A kill on a dormant
   enemy (state 0, run A4) reports done but leaves its hp alone; the game
   ignores hits until the enemy wakes.
2. **Spawns under the non-time-control play modes.** Refused (any
   nonzero value). Relaxed only if a mod needs it, with a run.
3. **Can a rewind reach back past an area setup?** Assumed not. The
   per-frame stale-record check (D5) logs it; the proof's step 7 runs REW
   right after an area change.
   Open, and the assumption fails (PC run E4): a mission switch (1-1 to
   1-2, run E) runs no area setup and the copy carries over. The retry
   after a death on 1-2 does run `stage_area_setup`; the hook then freed
   the copy's record (`1 placement records freed`), yet the copy stayed
   listed (n 31 before and after) and the next frame logged `enemy …
   points at a freed placement record`, before any REW. The copy then sat
   in state 5 at one spot for the rest of the run. Either the walk at the
   hook missed the copy (a list mid-rebuild) or the retry restores the
   list after the setup; both break the "free after area setup" rule and
   need a design decision (D5).
   Cause: the retry restores the checkpoint after the setup, list and pool
   included (D5). Decided: a retry removes the copies, swept at the next
   enemy update; records are freed only on a full walk and never while
   referenced (D5).
   Rerun (PC run E5, cat f1ac875): the sweep works. At the first frame
   after the retry the copy is off the list (n 31 to 30) with one line,
   `1 copies off the list, 1 placement records freed`. But the REW the
   proof asks 30 frames later brings it back (n 30 to 31 at 35 frames
   into the REW, state 5, frozen), pointing at the freed record, and the
   stale-record line fires. The restore writes the checkpoint frame into
   the ring's current frame (`sub_001A90F0`), so the ring's oldest frame
   after a retry is the restored state, copy listed, recorded before the
   sweep ran. Decided: option (a) (D5): the sweep runs every frame and
   unlinks any listed copy of a marked or retired record; retired records
   are not reused until the next area setup. Rerun (PC runs E6, E7, cat
   1af329f): the copy is off the list after the retry and stays off
   through the REW (n 30 in every sample), with no stale-record line. A
   held REW sits at the ring's oldest frame and restores the copy every
   frame; the sweep removes it each time, logging one line per 300.
   Settled.
   Review: a second retry from the same checkpoint broke it.
   Its setup freed the records the first retry's sweep retired, and the
   restore brought back a copy pointing at a free record, which the sweep
   left listed. Now retired records go free only at a stage start, a copy
   of a free record is unlinked too (no game placement points into the
   block), and the mod switched off after a spawn keeps sweeping (D5).
   Proof on the PC (cat ce63aae, exe 45f9a3f6723f, run E8b): spawn, die,
   retry, die, retry, REW 30 frames later. Each retry re-lists the copy
   (n 31) and the next frame unlinks it (n 30); the second setup retires
   nothing new (the record is still retired, not freed), the REW's restore
   is swept the same way, and n stays 30 for the 8906 samples after the
   second retry, with no freed-record line. E7 again (E7b) as before.
4. **Does anything read `0xADA9B0` for enemies?** Callers of
   `sub_0004F910`, statically; record the spawn only if one matters.
   Settled: its only caller is `stage_enemy_placements_load`; nothing
   outside the loader chain reads `0xADA9B0`, and the API does not write
   it.
5. **The cap reserve.** Every caller of `sub_0004EE20` audited for a count
   check before it calls; `reserve` set from that, 2 until then.
   Settled: 0. The loader runs on a list just reset at area setup, the
   class 9 nest checks count < 0x22 before its spawn, and the spawner
   (class 0x14), which does not, is off the allowlist.
6. **The allowlist.** Classes from every stage table, statically; the
   spawner class kept only if its nested spawn checks the count.
   Settled: 01 02 04-0A 0D 0E 10 12 81-86 (class & 0xFF). 0x14 is out (its
   nested spawn checks no count) and 0x21 (the extra sets) is out: the
   switch sends it to its default, which runs no init and leaks.
7. **Tom Tom (`stage_team_mode` 1) and 2P.** Allowed, untested; one proof
   run on a Tom Tom stage (debug stage select, index % 5 == 2) checks the
   spawn. VS stays refused.
   Settled (PC run Q7d, Tom Tom 2-3, team mode 1): the spawn works (4 to
   5 listed, the copy idles 0-1-2-5-6 at its offset). Tom Tom 1-3 lists no enemies (runs Q7b, Q7c), so it
   has nothing to copy. The kill at play 301 hit the idling copy and left
   its hp alone, as for a dormant enemy (open question 1).
8. **Cap raise.** Not here (C3). A follow-up only if the user asks;
   it needs the time-record budget measured per stage first.

## Risks

- **A REW right after a retry restores a swept copy** (open question 3,
  run E5). Applied: (a), the sweep runs every frame and unlinks any listed
  copy of a marked or retired record, and retired records are not reused
  until the next area setup, so a restored copy never points at a new
  spawn's record. Not taken: (b) removing the copy from the time-record
  frames (the checkpoint frame at `[0xDDD194]` and the ring), which needs
  the frame layout; (c) refusing spawns until the stage's checkpoint is
  taken after them. What (a) leaves:
  - the copy is listed for the frame the REW restored it, until the next
    enemy update; the game updates nothing on it in between;
  - a restore from before the stage start that freed a record brings back
    a copy pointing at a free record. It is a copy for sure (no game
    placement lives in the block) and goes at the next enemy update after
    `on_frame` sees it, one frame later than a retired record's copy. If a
    spawn takes that record first, the copy points at a used record and
    stays listed, as a copy of the new spawn's record;
  - records retired at a retry stay unusable until the next stage start,
    so a spawn-heavy session with retries runs out sooner: `ENT_RECORDS`
    until then (D5).

- **A class init with side effects outside the object** (registrations
  through `sub_001A9830`, aggro slots) might misbehave in a copy made away
  from its home. The allowlist starts from what the game itself spawns,
  and the proof covers class 1; other classes are tried in the proof's
  `fill` step, which spawns copies of every listed class.
- **Time-record budget.** Whether the pool is recorded as one region is not
  known (C3), and a class whose init registers its object (0x110 does)
  adds a region per spawn; an over-budget region is dropped silently, and
  its state then stops rewinding. The proof's `fill` step logs the frame
  size on 5-1 with a full list; a class that pushes it past the budget
  leaves the allowlist. Measured (PC run D): 89,650 of 92,160 bytes in 9
  regions at 28 enemies and still at 34 after `fill` added six, so the
  pool is recorded as one fixed region and spawns cost nothing more. No
  class leaves the allowlist.
- **Guest stack depth.** `guest_call` runs below the hooked call's frame;
  the spawn's depth is that of the game's own loader call, which runs from
  a shallower frame. Fine on the spike's runs; the ctest checks alignment.
