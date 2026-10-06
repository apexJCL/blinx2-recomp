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

Archived 2026-10-06 as superseded, without a spec sync (it never had spec deltas). The placeholder was never started, but its scope was delivered by other changes: `input-real-devices` (`RECOMP_SAVE_DIR`, `RECOMP_SAVE_SEED`, the `@story-hub` route that saves through SAVE GAME, LOAD GAME passing at the real-pad checklist), `kernel-memory-and-files` (FATX overwrite and rename semantics for the `Z:` cache), the toolkit's bridges for `IoDismountVolumeByName` (91) and `FscSetCacheSize` (37), and `packaging-deploy` (saves outside the program files, kept byte-identical across install, update, rollback and uninstall). The `Z:` handling is the deviation "Utility drive not mounted; Z: is a host cache directory" in `openspec/specs/deviations/spec.md`. Anything new about saves (memory units, a saves spec) starts as a new change.
