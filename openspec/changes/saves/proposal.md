## Why

Placeholder: nothing has started. The path layer works: `U:\13C9177716xx\SaveMeta.xbx` maps to `game_files/UDATA/4d530065/...`, and 8 slots are probed. The probes fail with `err=3` because the directories don't exist on the bench. Directory creation through `NtCreateFile(FILE_DIRECTORY_FILE)`, the `XCreateSaveGame` writes (`SaveMeta.xbx`, `SaveImage.xbx`) and the game's own cache writes to `Z:` are all untested.

## What Changes

- UDATA/TDATA directory creation, SaveMeta/SaveImage writes, and 8-slot enumeration that succeeds.
- Cache-partition writes and dismount. `Z:` is `<save_dir>/Cache`, not a raw partition (see the MOUNT_UTILITY_DRIVE entry in `deviations`). `IoDismountVolumeByName` (ordinal 91) and `FscSetCacheSize` (ordinal 37) are unresolved imports today.
- Acceptance: a bench run with a controller saves, quits, and loads the save on the next boot.

## Capabilities

### New Capabilities
- `saves`: save games and the cache partition (requirements to be written when the work starts).

## Status

Placeholder (proposal only). `.openspec.yaml` sets `skip_specs: true` so it validates. Remove that, and add design, spec deltas and tasks, when the work starts.
