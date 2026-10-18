## ADDED Requirements

### Requirement: Saves are listed per title from a player's own sources
`saves list` SHALL accept a folder, a zip, an HDD image or a memory-unit
image. With no source given, it SHALL use the HDD image and memory units
that xemu's configuration names, and Cxbx-Reloaded's
`EmuDisk/Partition1/UDATA/` under its data dir on Windows and inside Wine
and Steam Proton prefixes on Linux and SteamOS. Any other source SHALL be
reached with `--from`. It SHALL open every source read-only
and SHALL make no network access. Each save SHALL be listed with:
- its source;
- its title ID, taken only from the title directory's name;
- its save ID;
- its name from `SaveMeta.xbx`, and `NoCopy=1` when that is set;
- the title's `TitleMeta.xbx` `TitleName=`, with a warning when it differs
  from the game's name;
- its size;
- whether its title is one of the game's `[saves] title_ids`, matched
  case-insensitively;
- one state: `ok`, `foreign`, `no title` or `invalid`. An `ok` save also
  shows its signing state, `resign`, `none` or `unknown`.

`--json` SHALL print the same information as data.

#### Scenario: A zip with this game's save and another game's save
- **WHEN** `saves list --from shared.zip` runs on a zip holding `UDATA/4d530065/0123456789AB/` and `UDATA/4541005b/AAAAAAAAAAAA/`, for a game whose `title_ids` is `[0x4D530065]`
- **THEN** both saves are listed, the first as `ok` with its `SaveMeta.xbx` name, the second as `foreign`, and nothing is written anywhere

#### Scenario: A save folder with no title directory
- **WHEN** the source is a bare `0123456789AB/` folder holding a `SaveMeta.xbx`
- **THEN** it is listed as `no title` and is not importable

#### Scenario: Cxbx-Reloaded found by default
- **WHEN** `saves list` runs with no source and a Cxbx-Reloaded data dir holds `EmuDisk/Partition1/UDATA/4d530065/0123456789AB/`
- **THEN** that save is listed with Cxbx-Reloaded as its source

#### Scenario: xemu still running
- **WHEN** an xemu process is running (`xemu`, `xemu.exe` or the Flatpak app `app.xemu.xemu`) and the source is an image that `xemu.toml` names
- **THEN** no image is read, and the message says to close xemu

### Requirement: Import writes only this game's valid saves, after a backup
`saves import` SHALL write only `ok` saves of the game's title IDs into
`<target>/UDATA/<title id>/<save id>/`, with the title ID in lower case and
the save ID in its source case. Several saves under one title SHALL be
handled independently.

TDATA SHALL follow `[saves] tdata`: never with `ignore`, only with
`--with-tdata` with `optional` (the default), and always with `required`.

The default target SHALL be the installed data dir for this host plus
`hdd`:
- on Windows, the `[data] dir_env` variable when it is set, else the
  `[data]` default;
- on SteamOS, the root of the installed bundle; when none is found, the
  import SHALL require `--to`;
- on macOS, the `[data]` default.
`--to DIR` SHALL override it.

The import SHALL refuse to run when:
- the game, or the process of the source's emulator (xemu or
  Cxbx-Reloaded), is running, on every host including Windows;
- the target is inside an application bundle;
- the target is under `game_files/`;
- any part of `<target>/UDATA/<title id>` or `<target>/TDATA/<title id>` is
  a symlink or a junction.

Before the first write, it SHALL zip the target's existing saves for those
titles (and TDATA when TDATA is imported) to `<data>/save-backups/`, or to
`DIR/../save-backups/` with `--to DIR`, named by UTC stamp with a `-N`
suffix when the name exists. The zip SHALL pass `testzip()` before any
write.

An existing save ID, or an existing TDATA file, SHALL be skipped unless
`--replace` is given. On a case-sensitive host, an existing title or save
directory that differs only by case SHALL count as a conflict. Save IDs
SHALL never be renamed.

Each save SHALL be staged in `<target>/.save-import-tmp/`, never inside
`UDATA/<title id>/`, and renamed into place whole. With `--replace`, the
old save SHALL be renamed aside before the new one is renamed in, and
deleted only after. A staging dir left by an earlier run SHALL be removed
at the start of the next one. `--dry-run` SHALL print the plan and write
nothing.

#### Scenario: Conflict without --replace
- **WHEN** the target already holds `UDATA/4d530065/0123456789AB/` and the source holds the same save ID
- **THEN** that save is skipped and reported as a conflict, the target's files are byte-identical afterwards, and other saves still import

#### Scenario: Replace keeps a backup
- **WHEN** the same import runs with `--replace`
- **THEN** a zip under `save-backups/` that passes `testzip()` holds the previous save byte-identical, and the target holds the imported save

#### Scenario: Interrupted replace
- **WHEN** a `--replace` import stops after the old save was renamed aside and before the new one was renamed in
- **THEN** the next run restores or keeps a whole save, removes the stale staging dir, and no half-written save is left in `UDATA/4d530065/`

#### Scenario: Dry run
- **WHEN** `saves import --dry-run` runs
- **THEN** the plan lists each save with its action (import, skip, replace or reject) and the reason, and no file or directory is created or changed

#### Scenario: TDATA required by the game
- **WHEN** a game declares `tdata = "required"` and the source holds `TDATA/<title id>/` files, one of which already exists in the target
- **THEN** the TDATA files are imported with the saves without `--with-tdata`, the existing file is skipped unless `--replace` is given, and the backup holds the target's previous `TDATA/<title id>`

### Requirement: Source names and sizes are checked before anything is written
The importer SHALL apply one rule set to folder, zip and FATX sources. It
SHALL reject a name that:
- is longer than 42 bytes;
- is `.` or `..`;
- contains `/ \ : * ? " < > |`, NUL or a control character;
- ends in a dot or a space;
- is a Windows reserved name;
- differs only by case from another name in the same directory.

Zip entries SHALL also be rejected for absolute names, drive letters and
symlinks. Folder sources SHALL NOT follow symlinks or junctions and SHALL
reject them with a reason. Caps on file size, save size, entry count and
directory depth SHALL apply to every source. A save that breaks a rule SHALL
be rejected with the reason while the other saves still import, and nothing
SHALL be written outside the target.

#### Scenario: Unsafe archive
- **WHEN** a zip entry has an absolute name, a drive letter, a `..` component or a symlink, or the archive exceeds the size cap
- **THEN** the affected save is rejected with that reason and nothing is written outside the target

#### Scenario: Unsafe FATX dirent
- **WHEN** a FATX image holds a save whose directory contains an entry named `..` or `a/b`
- **THEN** that save is rejected with the reason, other saves still import, and nothing is written outside the target

#### Scenario: Symlink in a folder source
- **WHEN** a folder source's save contains a symlink to a file outside the source
- **THEN** the link is not followed, and the save is rejected with the reason

### Requirement: Declared signed files are re-signed with the build's key
When a game declares `[saves] signing = "resign"`, each file matching a
`[[saves.signed]]` recipe SHALL have the declared size, or its save SHALL be
rejected as `invalid`. On import, the digest at each recipe's `digest` SHALL
be replaced with the HMAC-SHA1 of `[data[0], data[1])` under the build's
`XboxSignatureKey` (16 zero bytes, as the toolkit exports it). A glob MAY
carry several recipes, one per signed block. No other byte SHALL change. A
game that declares `signing = "none"` SHALL import without re-signing.

#### Scenario: A retail-signed BLiNX 2 save
- **WHEN** a synthetic `blinx2data.bin` of the declared size carrying any other digest at 33972 is imported for BLiNX 2
- **THEN** bytes 33972-33991 of the imported copy equal `HMAC-SHA1(16 zero bytes, file[0:33972])`, every other byte equals the source, and the source file is unchanged

#### Scenario: Wrong size
- **WHEN** a matching file is not the declared size
- **THEN** its save is rejected as `invalid` with the expected and actual size

### Requirement: Game constants come from game.toml
The importer SHALL take every game-specific value from the game's
`game.toml`: the title IDs (defaulting to `[xbe].title_id`), the signing
mode, the TDATA mode, the recipes, `[data]` and `[package] app`. The CLI
SHALL contain no game's title ID or save layout. The manifest SHALL refuse a
recipe whose range or digest does not fit its `size`, whose digest overlaps
a data range of the same glob, or whose glob is absolute or contains `..`.

#### Scenario: A game without a [saves] table
- **WHEN** a game has no `[saves]` table and a save of its title is imported
- **THEN** the copy goes ahead with the signing state `unknown`, and the plan and the output warn that its saves may need re-signing and may not load

### Requirement: HDD and memory-unit images are read without new dependencies
The importer SHALL read the following with the Python standard library only:
- qcow2 images, versions 2 and 3, including compressed clusters and backing
  files;
- raw full-disk images, with E: at byte 0xABE80000 and the retail size
  0x1312D6000;
- memory-unit images: FATX at offset 0, sized by the file.

It SHALL read FATX volumes with the FAT at partition + 0x1000, FAT16 when
the partition's cluster count plus one is below 0xFFF0 and FAT32 otherwise,
and the data area after the FAT rounded up to 4 KiB.

It SHALL refuse a qcow2 image that:
- sets an incompatible-feature bit it does not know;
- is encrypted, uses an external data file or extended L2, or uses zstd;
- has `cluster_bits` outside 9..21;
- has an `l1_size` beyond what its virtual size needs or a memory cap;
- has an L1 or L2 table that is misaligned or outside the file;
- has its dirty or corrupt bit set, with a message to run
  `qemu-img check -r all` or to boot and close the image in xemu.

Compressed clusters SHALL inflate to at most one cluster. Backing files SHALL
be resolved relative to the image's directory, SHALL be regular local files
(never `json:` specs, URLs or device nodes), SHALL form a chain at most 8
deep with no cycles, and SHALL be named in the plan output.

It SHALL reject a FATX chain that loops, leaves the volume, or is shorter
than the file's size.

#### Scenario: A compressed cluster over a backing file
- **WHEN** a synthetic qcow2 v3 image with one compressed cluster and a raw backing file holds a FATX E: with one save
- **THEN** `saves list` lists that save and names the backing file, and its imported files are byte-identical to those written into the fixture

#### Scenario: Dirty image
- **WHEN** no xemu process runs and the qcow2 image has its dirty bit set
- **THEN** the image is not read, and the message says to run `qemu-img check -r all` or boot and close it in xemu

#### Scenario: Unsafe backing file
- **WHEN** a qcow2 image's backing name is a `json:` spec, a URL, a device node, or forms a cycle or a chain deeper than 8
- **THEN** the image is refused with that reason and no backing file is opened beyond the check

#### Scenario: FAT width at the threshold
- **WHEN** synthetic FATX volumes are sized so that the cluster count plus one is 0xFFEF and 0xFFF0
- **THEN** the first is read as FAT16 and the second as FAT32

### Requirement: Imports never use a retail key
Every import SHALL re-sign declared files under the build's key. The
importer SHALL have no option or configuration that reads, derives or
stores a retail signature key, and SHALL NOT offer export.

#### Scenario: No retail-key option
- **WHEN** `saves import --help` runs
- **THEN** no option names a retail key or a key file, and no `saves export` verb exists

### Requirement: SteamOS bundles carry the importer
A SteamOS bundle SHALL carry the `saves` module and an `import-saves.sh`
launcher next to `launch.sh`. The launcher SHALL find Python as `install.sh`
does, SHALL run the bundled `saves` verb with the bundle's own `<root>/hdd`
as the target, and SHALL pass every other argument through. With no
`--from`, it SHALL use the default detection, including xemu's Flatpak
configuration and Cxbx-Reloaded's Proton prefixes. Installing, updating or
removing the bundle SHALL still never write `hdd/`.

#### Scenario: Import on a Deck
- **WHEN** the player runs `import-saves.sh --from saves.zip` in an installed bundle
- **THEN** the zip's saves for this game are imported into that bundle's `<root>/hdd/UDATA/`, after a backup to `<root>/save-backups/`, with no CLI checkout present

#### Scenario: Install does not import
- **WHEN** the bundle is installed or updated
- **THEN** `hdd/` is untouched and the importer does not run

### Requirement: The wizard imports through the CLI
The build wizard's import screen SHALL get its list from `saves list --json`
and SHALL import only by running `saves import --json`. It SHALL parse no
save or image format itself. Foreign, `no title` and invalid saves SHALL be
shown and SHALL NOT be selectable.

#### Scenario: Import from the wizard
- **WHEN** the player picks a zip, keeps the ticked saves and presses Import
- **THEN** the wizard runs `saves import --json` with those save IDs and shows the backup path and each save's result from its output
