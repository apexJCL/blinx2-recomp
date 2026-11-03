# Change: a Saves section in the in-game menu (export and import as a zip)

## Why

Players want to move their saves to another PC or device (public issue
blinx2-recomp #6). Today that means finding the `hdd` folder by
hand, which differs per host (`%LOCALAPPDATA%`, Application Support, the
bundle on the Deck) and which a SteamOS player in Game Mode cannot reach
at all. The menu's Files page (overlay-revamp phase G) already
exports and imports settings and shader profiles through its own file
browser. The same machinery can carry the game's saves as one zip.

## What changes

- **A Saves section** in the in-game menu, its own toolbar entry next to
  Files (the operator, 2026-11-03: saves get their own section, not rows
  on Files). It lists the running title's saves (name, size, date),
  says where they are on disk, and has Export and Import.
- **Export** writes `<game>-saves-<yyyymmdd-hhmm>.zip` through the Files
  browser and name entry, with the temp-then-rename write it already
  has. The zip holds a small manifest (`xbr-saves.toml`) and the title's
  part of the `hdd` folder: `hdd/UDATA/<title id>/` and
  `hdd/TDATA/<title id>/`, nothing else of `hdd`.
- **Import** picks a zip in the browser and validates all of it before
  anything is touched: a size cap, entry caps, zip-slip and name checks,
  CRCs, the running title's id only, and the manifest a build of this
  toolkit writes. A preview shows what it brings and what it replaces.
  Apply backs up the current saves to a zip of the same format first,
  stages the new trees beside the live ones, swaps them in with renames,
  and quits the game so it rereads them at the next start.
- **No re-signing between our installs.** Every key a save signature can
  depend on is a constant in the toolkit kernel (16 zero bytes for
  `XboxSignatureKey`, `XboxHDKey`, the LAN and alternate keys; a fixed
  disk serial; fixed EEPROM settings). A save one install writes loads in
  any other build of the same game. The manifest still records a
  fingerprint of those keys, so a future build with other keys refuses
  the zip instead of loading saves that fail their check (design D1).
- **A guard against a save in progress.** The kernel counts the guest's
  open file handles under `UDATA`/`TDATA` and the time of the last change
  there. Export and import refuse, with a message, while a save file is
  open or within two seconds of the last write.
- Game-agnostic toolkit feature: every game built with
  `XBOXRECOMP_ENHANCE=ON` gets it, with no per-game data.

## Out of scope

- Original Xbox, xemu or Cxbx-Reloaded saves and re-signing them: that is
  `save-import` (the CLI's `xbr saves`). Design D9 says how
  the two relate; the zip this change writes is a valid `zip` source for
  that importer.
- Deflate-compressed zips (a zip re-packed by a desktop tool). Our export
  stores the files uncompressed, so import reads only stored entries; a
  compressed one is refused with a clear message (follow-up in tasks).
- Per-save selection (import one save of several). The zip is restored
  whole, as a snapshot.
- Save-state slots (`save-states` D9): they have their own export.

## Capabilities

### New Capabilities
- `overlay-saves`: exporting and importing the running title's saves as a
  validated zip from the in-game menu.

## Impact

- Toolkit (`xboxrecomp`, branch off `posix-host/portability`):
  - `src/enhance/saves_zip.{c,h}`: the pure zip writer, reader and
    validator, and the manifest (ctest `tests/saves_zip`);
  - `src/enhance/saves_store.{c,h}`: collecting the trees, the backup,
    the staging and the swap (ctest on a temp dir);
  - `src/kernel/kernel_file.c`, `kernel_path.c`, `kernel.h`: the busy
    guard, the save-tree paths, the title id and name, the key
    fingerprint;
  - `src/enhance/enhance_menu.c`: the Saves page, the browser shared with
    Files;
  - `docs/runtime/config.md`: the Saves section.
- cat: this spec, a README "Move your saves" line, `docs/env.md` only if
  a key is added (none planned).
- Privacy: saves are never committed, published or attached; the ctests
  build synthetic trees.

## Status

Spec, 2026-11-03.
