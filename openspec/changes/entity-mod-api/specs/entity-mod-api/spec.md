## ADDED Requirements

### Requirement: Guest calls and guest memory for mods
The toolkit's mod API v6 SHALL offer `guest_call`, which runs a lifted
guest function by VA from the guest thread and restores every guest
register afterwards (`g_ebp`, `g_seh_ebp`, x87 and SSE state included), and
`guest_alloc`, which gives a mod one block of guest memory the guest heap
never hands out. Both SHALL refuse, with one log line, off the guest thread.

#### Scenario: Registers restored
- **WHEN** a hook's pre calls a guest function through `guest_call`
- **THEN** after the call every guest register holds its value from before

### Requirement: Enemy list reads
With the `entities` mod on, `ent_list` and `ent_read` SHALL return host
copies of the listed enemies (handle, class, state, hp, position, rotation,
dead state), copying each field with `memcpy`, on the guest thread only.
A handle SHALL stay valid while its object is listed with the same
placement pointer and id, across a respawn in place.

#### Scenario: Slot reused
- **WHEN** an enemy's pool slot is taken by another enemy
- **THEN** `ent_read` on the old handle answers gone

### Requirement: Guarded spawns
`ent_spawn` SHALL be carried out on the guest thread in the pre hook of
`sub_0004E700`, from a placement record in API-owned guest memory that is
not reused before the next stage start. It SHALL be refused, without calling
the game's spawn, while `0xAE46EC` is not 0, in VS, for a class outside the
allowlist, when `count + 1 + reserve > 34`, or when no record is free.

#### Scenario: Spawn during a rewind
- **WHEN** a spawn is asked while REW runs
- **THEN** it answers `ENT_TIME_CONTROL` and the list count is unchanged

#### Scenario: Cap
- **WHEN** spawns are asked until the list is full
- **THEN** the last answers `ENT_CAP` and no pool slot is leaked

### Requirement: A new area removes the API's copies
After an area setup the API SHALL take every listed enemy it spawned
before that setup off the list, at the next enemy update (after a retry's
checkpoint restore), and retire its record. It SHALL take such a copy
off the list again at any later enemy update a retry or a rewind brings
it back, and SHALL NOT free a retired record before the next stage start
(the stage state machine's call of the setup, not a retry's). A listed
object pointing at a free record SHALL be taken off the list too. It
SHALL retire a record only after a walk that reaches the list's count,
and never while a listed object points at it; a held record SHALL be
retried the next frame. With every record used or retired, a spawn SHALL
answer `ENT_RECORDS` and write nothing. A mission switch without an area
setup SHALL leave the copies listed. Switched off after a spawn, the API
SHALL keep marking and sweeping, and take no request.

#### Scenario: Retry after a death
- **WHEN** a copy is spawned after the checkpoint and the player dies and
  retries
- **THEN** the copy is no longer listed, its record is retired, and no
  stale-record line is logged

#### Scenario: Rewind after a retry
- **WHEN** the player rewinds right after that retry
- **THEN** the copy is off the list again from the next enemy update on,
  and no stale-record line is logged

#### Scenario: A second retry from the same checkpoint
- **WHEN** the player dies and retries again, and rewinds after it
- **THEN** the copy is off the list after each retry and through the
  rewind, and no stale-record line is logged

#### Scenario: Switched off after a spawn
- **WHEN** the mod is switched off after a spawn and the player retries
- **THEN** the copy is off the list from the next frame on

### Requirement: Kills and type overrides
`ent_kill` SHALL damage a listed live enemy by its hp through `sub_00050800`
on the guest thread, under the same time-control guard except that PAUSE
and SLOW let a kill through. Its done SHALL answer `ENT_OK` only once
the enemy died, lost hp or left the list, `ENT_IGNORED` when it had not
4 enemy updates after the hit (a dormant or idling enemy), and
`ENT_TIMEOUT` after 60 frames with no enemy update. Every kill SHALL get
exactly one answer. Class-1 hp
overrides SHALL be written before the area's placements load and the
originals written back at the area setup after they are cleared.

#### Scenario: hp scale
- **WHEN** `mods."entities.hp_scale" = 3` and a stage loads
- **THEN** class-1 enemies spawn with three times their hp

### Requirement: Off is stock
With `mods."entities.enable" = "off"` (the default) the mod SHALL read and
write no guest memory and allocate none; stock runs log
`[ENHANCE] mods=none`, and `game.toml` `[golden] enhance_stock` SHALL list
`"mods.entities.enable" = "off"`. The mod, its settings and its controls
SHALL appear on the menu's Mods page and in the descriptor dump.

#### Scenario: Golden run
- **WHEN** a golden runs with the stock config
- **THEN** the log shows `[ENHANCE] mods=none` and no `[MOD entities]` line
  writes guest memory
