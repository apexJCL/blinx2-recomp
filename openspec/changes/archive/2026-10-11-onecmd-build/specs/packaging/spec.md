## ADDED Requirements

### Requirement: The dump is imported from a disc image or a folder
The CLI SHALL accept the player's dump as a path to either an Xbox disc image (XDVDFS, any file extension: a bare game partition, or a redump-style full image whose game partition follows the DVD-video partition) or a folder whose root holds the XBE named by `[xbe] path` relative to `[data] game_files`, through `blinx2 import PATH`, `blinx2 package <target> --dump PATH`, and the shorthand `blinx2 PATH` (a first argument that is an existing path and not a command name, which SHALL mean `package <native target> --dump PATH` with the remaining arguments kept). The image reader SHALL be the toolkit's `tools/xiso/xdvdfs.py`, vendored into the CLI byte for byte apart from a licence header and formatting, with its MIT licence shipped and its origin recorded, standard library only, finding the game partition by probing for the `MICROSOFT*XBOX*MEDIA` descriptor at each known base rather than from the file size. The import SHALL read the source and write only under the game root (`[data] game_files` and its `.partial`/`.old` siblings), SHALL use no network, and SHALL send nothing about the dump anywhere. Archives, `.cue` sheets and any file without the descriptor SHALL be refused with a message that says to extract the archive first. Every name read from an image SHALL be checked before any write: no empty, `.` or `..` component, no separator or NUL, no character or name Windows refuses, no trailing dot or space, no two names in one directory differing only by case, every destination resolving under the staging folder, no directory sector visited twice and a bounded depth. A source whose real path equals, lies inside or contains `game_files` or its `.partial` sibling SHALL be refused.

#### Scenario: One command from the disc image
- **WHEN** a player runs `./blinx2 /path/to/BLiNX2.iso` in a fresh clone with uv and git installed
- **THEN** the files are extracted into `game_files/`, then setup, generation, build and packaging run as `./blinx2` alone does, and the bundle appears under `dist/`

#### Scenario: Redump full image
- **WHEN** the image's XDVDFS descriptor is at the redump game-partition base (`0x18300000` plus sector 32) rather than at sector 32 of the file
- **THEN** the import finds it, extracts the same files as from a bare image, and never reads the DVD-video partition

#### Scenario: Folder source
- **WHEN** the path is a folder holding `default.xbe`
- **THEN** its whole tree is copied into `game_files/` (an APFS clone on macOS when the volume allows, a plain copy elsewhere), or symlinked with `--link`, and a folder without `default.xbe` at its root is refused naming the missing file

#### Scenario: Not an image
- **WHEN** the path is a regular file with no XDVDFS descriptor at any known base (a `.zip`, `.7z`, `.rar` or `.cue`)
- **THEN** the import refuses, names the path, and says an archive must be extracted first and a `.cue/.bin` set needs its `.bin`

#### Scenario: Unsafe name in the image
- **WHEN** an image masters an entry named `..`, a name with a separator, a Windows-reserved name, two names differing only by case in one directory, or a directory tree that loops
- **THEN** the import refuses before `game_files.partial/` exists and names the entry and the rule

#### Scenario: Source inside the game root
- **WHEN** the path is `game_files/` itself, a folder under it, or a folder that contains it
- **THEN** the import refuses and names the overlap

### Requirement: The title is verified before anything is written
Before extracting, copying, linking or running `setup`, the import SHALL read the XBE header from the source (the image's or the folder's XBE at the name `[xbe] path` gives relative to `[data] game_files`), check the certificate's title ID against `[xbe] title_id`, and refuse another title in one line that names the certificate's title and both IDs. Only after the files are in place SHALL the known-dump check (`[xbe] sha256`) run, as a warning and never a refusal, as `package` does today.

#### Scenario: Wrong disc
- **WHEN** the image or folder holds another game's `default.xbe`
- **THEN** the import prints `this is "<title>" (0x<id>), not BLiNX 2 (0x4D530065)`, exits non-zero, no `game_files.partial/` exists, and no toolkit clone, toolchain download or pipeline stage ran

#### Scenario: Unknown dump
- **WHEN** the imported `default.xbe`'s sha256 is not one `game.toml` lists
- **THEN** the import completes and prints the unknown-dump warning once, and `package` later records `"xbe": "unknown"` as today

### Requirement: Import is atomic, repeatable and never deletes unasked
The import SHALL check the free space on the game root's volume against the source's byte total plus a margin before writing and refuse with both numbers when it is short; a folder source on the same volume on macOS, which is cloned, SHALL need only the margin. It SHALL build the new tree in `game_files.partial/` beside the target (every file and directory, empty ones included), verify each file's size against its directory entry, carry in the old tree's top-level `game_files_exclude` entries, write the marker `.xbr-dump.json` into it, and rename it into place, that rename being the one step that finishes the import; the marker's identity is the path, size and mtime of an image, or the path, file count, byte total and XBE sha256 of a folder, with the format, partition base, CLI version and time; a failure that reaches cleanup SHALL remove `.partial` and leave the previous `game_files/` as it was, and a stale `.partial` SHALL be removed at the start of the next import after the title check. A rerun with the same source SHALL compare every source file's size with `game_files/`, ignoring extras under `game_files_exclude` names, and do nothing else when they match. A `game_files/` with no marker whose sizes match the source SHALL be adopted: the marker written, nothing copied. A `game_files/` holding only `.DS_Store`, `Thumbs.db`, `desktop.ini` or `game_files_exclude` names SHALL count as empty. Any other non-empty `game_files/` with another marker or no marker SHALL be refused unless `--replace`, with a message naming the two ways on (`--replace`, or the command alone to build from what is there); `--replace` SHALL be accepted by `import` and by `package` with `--dump`, SHALL complete the new tree with its marker first, rename the old one to `game_files.old/`, swap, then remove the old one (a failure to remove it SHALL be reported, not fail the import), and SHALL unlink rather than follow a symlinked `game_files`. The old tree's top-level `game_files_exclude` entries (saves, the pipeline's files) SHALL be copied into the new tree before the swap, with or without `--replace`; a name the source also has SHALL come from the source, and the import SHALL say which names it kept and which the source replaced; `--link` over a tree holding such entries SHALL be refused without `--replace`. A folder that cannot be read, in the source or in `game_files/`, or a link to a missing file SHALL stop the import or the check with its name, never be skipped. At the start of every import, a `game_files.old/` beside a missing `game_files/` SHALL be renamed back, a `game_files.old/` beside a `game_files/` holding a marker or being a symlink SHALL be removed, a writing import (a copy or `--link`) beside a `game_files.old/` that recovery kept SHALL be refused before it copies anything with a message naming which tree to remove, and `game_files.old/` SHALL never be deleted while `game_files/` is absent. A source refused because the marker names another SHALL be told which of the identity's parts differ. `--link` SHALL write no marker; its identity SHALL be the link's target. `import --check` SHALL compare the source with `game_files/` by name, size and sha256, files only, and write nothing. The bundle payload SHALL exclude the marker. `doctor` SHALL name the import's source and date when the marker exists, the link's target for a symlink, and any leftover `.partial` or `.old` sibling, as SHALL `package` without `--dump`; the help SHALL show the path form among the player commands. Every message SHALL name the command through the host's name for it, never a literal.

#### Scenario: Rerun
- **WHEN** `./blinx2 /path/to/BLiNX2.iso` runs again with the same image
- **THEN** the import prints that `game_files/` already holds that import and the plan lists only build and package

#### Scenario: Hand-placed dump
- **WHEN** `game_files/` holds files but no marker, they differ from the source, and a path is passed
- **THEN** the import refuses, says the files were put there by hand, and names `--replace` and the no-argument run

#### Scenario: Adopted hand-placed dump
- **WHEN** `game_files/` holds files but no marker and every source file is present with its size
- **THEN** the import writes the marker, copies nothing, and says so

#### Scenario: Replace
- **WHEN** `./blinx2 import /path/to/other.iso --replace` (or `./blinx2 /path/to/other.iso --replace`) runs over an existing import
- **THEN** the new tree is complete before the old one moves, `game_files.old/` is gone at the end, and the marker names the new source

#### Scenario: Interrupted import
- **WHEN** an extraction is killed or the disk fills midway
- **THEN** `game_files/` is as it was, `game_files.partial/` is removed (by cleanup, or at the start of the next import with a line saying so), and no marker was written

#### Scenario: Crash between the renames
- **WHEN** a `--replace` died after `game_files/` became `game_files.old/` and before `.partial` took its place
- **THEN** the next import renames `game_files.old/` back before anything else and says so, and `doctor` meanwhile names the leftover

#### Scenario: Crash right after the swap
- **WHEN** an import died after `.partial` became `game_files/` and before `game_files.old/` was removed
- **THEN** `game_files/` holds the marker, the next import removes `game_files.old/` and says so, and a rerun with the same source is a no-op

#### Scenario: Leftover beside an unmarked tree
- **WHEN** `game_files.old/` and a `game_files/` with no marker both exist and a copy or `--link` import runs
- **THEN** it refuses before reading the source's files, says which tree to remove to keep the other, and changes nothing

#### Scenario: Saves survive an import
- **WHEN** `game_files/` holds `UDATA/` (and nothing else, or a dump under `--replace`) and an import runs
- **THEN** the new `game_files/` holds the same `UDATA/` and the import names it as kept, unless the source has its own `UDATA/`, which wins and is named as replaced

#### Scenario: Linked folder
- **WHEN** `./blinx2 import /path/to/folder --link` runs on macOS or Linux
- **THEN** `game_files` is a symlink to the folder's real path, no marker is written, a rerun with the same folder is a no-op, and `doctor` shows `(linked to /path/to/folder)`

#### Scenario: Marker never ships
- **WHEN** `blinx2 package` stages the payload from an imported `game_files/`
- **THEN** `.xbr-dump.json` is not in the payload, `SHA256SUMS` or `manifest.json`

## MODIFIED Requirements

### Requirement: One command packages for this host
Running `blinx2` with no arguments SHALL package for the host's native target: `macos` on macOS, `steamos` on Linux, `windows` on Windows. `blinx2.cmd` with no arguments SHALL do the same. Running `blinx2 PATH`, where `PATH` is an existing disc image or folder and not a command name, SHALL import the dump first (the dump-import requirements) and then do the same, with any further arguments (`--replace`, `--hud-pack`) passed to `package`. `blinx2 package <target>` SHALL:
- import the dump first when `--dump PATH` is given, replacing an existing one only with `--replace`, which is valid only with `--dump`;
- run `setup` when the toolchain or toolkit that target needs is missing;
- regenerate `src/recomp/gen/` (analyze, then recomp) only when it is missing or stale;
- then build and package.

Before running anything, it SHALL print a plan naming each step it will run and why, the import among them with the source's name, format, size and file count. When a prerequisite that `setup` cannot install is missing, it SHALL stop and print the one-line fix; when the dump is missing it SHALL name both ways to supply it (`import PATH`, or the files in `game_files/`).

#### Scenario: Fresh clone to bundle
- **WHEN** a user runs `./blinx2` in a fresh clone on macOS, with only the game files in place
- **THEN** setup, generate, build and package run in order, and a DMG appears under `dist/`

#### Scenario: Fresh clone to bundle from the image
- **WHEN** a user runs `./blinx2 /path/to/BLiNX2.iso` in a fresh clone on macOS with an empty `game_files/`
- **THEN** the plan lists import, setup, generate, build and package, they run in that order, and a DMG appears under `dist/`

#### Scenario: Nothing changed
- **WHEN** `./blinx2` runs again with no input changed
- **THEN** the plan lists only build and package, and no stage of the pipeline runs

#### Scenario: Path that is also a command name
- **WHEN** a folder named `doctor` exists in the working directory and the user runs `./blinx2 doctor`
- **THEN** the `doctor` command runs; the shorthand applies only to arguments that are not command names

### Requirement: Help shows player commands first
`blinx2 --help` SHALL list the player commands first: the path form (`blinx2 /path/to/dump`, the disc image or folder), no arguments, `package`, `doctor`, `import`, `enhance hud` and `setup`. It SHALL list the pipeline stages, `build`, `pins`, `new` and `bench` under a separate "Developer commands" heading, with `bench` as one line that points at `blinx2 bench --help`. Every developer command SHALL keep its current behaviour. The help SHALL print the same bytes with or without uv on the host.

#### Scenario: Help
- **WHEN** a user runs `./blinx2 --help`
- **THEN** the first command line shows the path form with the disc image, `import` is among the player commands, and `analyze`, `recomp`, `build` and `bench` appear only under "Developer commands"

#### Scenario: Bench help
- **WHEN** a developer runs `./blinx2 bench --help`
- **THEN** it lists the bench commands, their options, the `BENCH_*` configuration table, the host layout and the rule that the command takes the run lock itself and is never wrapped in an outer `flock`
