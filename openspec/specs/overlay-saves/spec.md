# overlay-saves Specification

## Purpose
TBD - created by archiving change overlay-saves. Update Purpose after archive.

## Requirements

### Requirement: The menu has a Saves section
The in-game menu SHALL have a Saves page, separate from Files, that lists
the running title's saves (name, size, date), shows the folder they are
in, and offers Export and Import.

#### Scenario: Saves listed
- **WHEN** the player opens Saves while `UDATA/<tid>/` holds two saves
- **THEN** both are listed by their `SaveMeta.xbx` name, with size and date

### Requirement: Export writes the title's save trees as a zip
Export SHALL write one stored zip holding `xbr-saves.toml` and the files
under `hdd/UDATA/<tid>/` and `hdd/TDATA/<tid>/` of the running title, and
nothing else, through the Files browser's temp-then-rename write.

#### Scenario: Export
- **WHEN** the player exports to Exports with the default name
- **THEN** `<game>-saves-<date>.zip` appears there and holds the manifest and both trees

### Requirement: Import validates the whole zip before writing
Import SHALL refuse, with a message naming the problem and with no change
to the current saves, any zip that breaks the size, entry, name, type,
checksum, method or manifest rules of design D3, or whose title id is not
the running title's.

#### Scenario: Another game's zip
- **WHEN** the player imports a zip whose manifest names another title id
- **THEN** it is refused as being for another game and the saves are unchanged

#### Scenario: Zip-slip
- **WHEN** an entry is named `hdd/UDATA/<tid>/../../x` or `/etc/x`
- **THEN** the zip is refused and nothing is written

#### Scenario: Damaged zip
- **WHEN** a file's CRC32 does not match
- **THEN** the zip is refused as damaged

### Requirement: Import backs up, swaps atomically and quits
A valid import SHALL first back up the current saves to a zip of the same
format, then stage and swap each carried tree with renames, rolling back
on failure, and then quit the game.

#### Scenario: Import on another host
- **WHEN** a zip exported on one host is imported on another
- **THEN** a backup zip exists, the trees match the zip, the game quits, and the next start loads the imported progress

### Requirement: No export or import during a save
Export and import SHALL refuse while the guest has a file open under
`UDATA` or `TDATA`, or within 2 s of its last change there.

#### Scenario: Game saving
- **WHEN** the guest holds a save file open and the player picks Export
- **THEN** the menu says the game is saving and writes nothing
