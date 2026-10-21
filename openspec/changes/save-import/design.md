## Context

Findings and citations are in `spike.md`. In short:

- A save root is a plain host folder tree:
  `<data>/hdd/UDATA/<title id>/<save id>/` (toolkit
  `src/kernel/kernel_path.c:63-64`). The launchers set it with
  `RECOMP_HDD_DIR`.
- The kernel's `XboxSignatureKey` is 16 zero bytes
  (`src/kernel/kernel_bridge.c:330`).
- BLiNX 2 signs `blinx2data.bin` with a roamable HMAC-SHA1 under that key.
  Retail and xemu saves use the retail-derived key, so they fail until they
  are re-signed. The file's size, 81920 bytes, and its single signed block
  are known from one sample and are provisional until task 0.1.

## Goals / Non-goals

Goals:
- One game-agnostic importer, with no game constants outside `game.toml`.
- Stdlib-only Python.
- Read-only sources, a checked backup before any write, and staged writes.
- The wizard as a thin front end.
- The same importer on SteamOS, run from the bundle.

Non-goals:
- Runtime or kernel changes.
- Any retail key. Imports always re-sign under the build's key; there is no
  retail-key option or config, and the key is never stored anywhere.
- Export. A zip of the save root would carry zero-key digests that do not
  load in xemu or on a console, so it is not low-hanging.
- `.xsv` and non-roamable saves, until there is a sample.

## Decisions

### D1. The CLI owns the importer

It lives in `xboxrecomp_cli/saves/` and has five parts:
- `sources.py`: the source kinds, how they are detected, and the name and
  size rules (D4).
- `fatx.py`: a read-only FATX reader.
- `qcow2.py`: a read-only qcow2 reader that presents a seekable file.
- `procs.py`: process checks for the game, xemu and Cxbx-Reloaded on every
  host, including
  a Windows lister (`tasklist /FO CSV`, or toolhelp through `ctypes`),
  since `running_game.py` lists nothing on Windows today.
- `importer.py`: the plan, backup, staging, re-sign and copy steps.

The verb is `xbr saves {list,import}`. The wizard runs it through the
game's bootstrap, as it runs `package` today. Rejected alternatives:
- Toolkit import at boot: the import would run on every launch, it would
  change runtime behaviour, and it would put C code into the format parsing.
- Wizard-only: it would be a second pipeline, against the wizard rules.

The deployment rule that no installer writes `hdd/`
(`deployment/spec.md:9`) still holds, because the importer only runs when
the player runs the verb.

### D2. Sources

| Kind | Detected by | Root of saves |
|---|---|---|
| `folder` | a directory | any of: one that holds `UDATA/`; a `UDATA` dir; an `E`/`e` dir holding `UDATA/`; a dir named like a title ID (8 hex digits) |
| `zip` | `zipfile.is_zipfile` | the same rules, applied inside the archive |
| `xemu` | `xemu.toml` found (the SDL pref path per OS, the portable exe dir, Flatpak), or `--xemu-config` | `[sys.files] hdd_path` → disk; each `peripheral_param_*` that is a file → MU |
| `disk` | qcow2 magic `QFI\xfb`, or "FATX" at 0xABE80000 in a raw file | E: at 0xABE80000, size 0x1312D6000, `UDATA/` |
| `mu` | "FATX" at offset 0 | the root, sized by the file; its title dirs sit directly under it |
| `cxbxr` | a Cxbx-Reloaded data dir found by default detection, or `--from` a dir holding `EmuDisk/` | `EmuDisk/Partition1/UDATA/` |

Default detection (the user, 2026-10-18) covers:
- xemu: the HDD image and every MU image that `xemu.toml` names;
- Cxbx-Reloaded: `EmuDisk/Partition1/UDATA/` under its data dir:
  - Windows: `%APPDATA%\Cxbx-Reloaded\`, the portable executable's
    directory when `--cxbxr-dir` names it, and the custom location in its
    `settings.ini`;
  - Linux and SteamOS: the same tree inside the default Wine prefix
    (`~/.wine`) and inside Steam's `compatdata/*/pfx` prefixes, at
    the prefix's `%APPDATA%\Cxbx-Reloaded\`;
  - macOS: none (Cxbx-Reloaded runs only under Wine-based tools there), so
    `--from`.
  Task 0.3 confirms every path and the process names against Cxbx-Reloaded's
  source. Detection reads only folders that exist and never scans a whole
  disk.

Any other source is reached with `--from`.

**Emulator running.** Before reading any image xemu names, the importer
checks for a running xemu process by name (`xemu`, `xemu.exe`, or the
Flatpak app `app.xemu.xemu`). If one runs, no image is read and the message
says to close xemu. A Cxbx-Reloaded source is read only while no
Cxbx-Reloaded process runs (`cxbx.exe`, `cxbxr-ldr.exe`, to confirm in task
0.3), so a half-written save is never copied. The qcow2 dirty bit is not used for this: xemu sets it
only with `lazy_refcounts`, so it says nothing reliable about a live
process.

**qcow2 support:**
- Versions 2 and 3.
- L1/L2 lookup and zero clusters.
- Compressed clusters. The descriptor's offset takes the low
  x = 62 − (cluster_bits − 8) bits, and the sector count the bits above
  them. The data is raw deflate (`zlib.decompressobj(-15)`), with the output
  capped at one cluster.
- Backing files, raw or qcow2:
  - resolved relative to the image's own directory;
  - depth at most 8, and no cycles (compared by resolved path);
  - regular local files only, never `json:` specs, URLs or device nodes;
  - the plan output names each backing path.

The reader refuses:
- any incompatible-feature bit it does not know;
- encryption, external data files, extended L2 and zstd compression;
- `cluster_bits` outside 9..21;
- an `l1_size` larger than the virtual size needs, or above a memory cap;
- an L1 or L2 table offset that is not cluster-aligned or lies outside the
  file;
- the `corrupt` bit;
- the `dirty` bit, because the refcounts may be stale. The message says to
  "run `qemu-img check -r all` or boot and close it in xemu".

Internal snapshots are ignored, and the active L1 is what gets read.

**FATX geometry** (as in mborgerson's `fatx`):
- The 4 KiB superblock at the partition's start: magic "FATX", sectors per
  cluster, root cluster.
- The FAT starts at partition + 0x1000.
- Its entry count is the partition size over the cluster size, plus one
  reserved entry. FAT16 when that count is below 0xFFF0, FAT32 otherwise.
  The review suggested 65525 as the bound; I pin mborgerson's 0xFFF0 and a
  test on both sides of it settles any doubt.
- The FAT's size is the entry count × 2 (or × 4), rounded up to 4 KiB. The
  data area follows it, and cluster 1 is the root directory.
- The partition size is the retail E: size, 0x1312D6000, for a disk, and
  the file size for an MU. The toolkit's E: size (0x465400 sectors) is not
  reused; that mismatch is a toolkit follow-up.
- The root cluster must be below the entry count.
- 64-byte dirents. 0xE5 marks a deleted entry; 0x00 and 0xFF end a
  directory.
- Chain walks are bounded by the entry count, so a loop is an error. A
  file's size must fit its chain, and every cluster must lie in the volume.

### D3. `[saves]` in `game.toml`

```toml
[saves]
# Title IDs whose UDATA/TDATA the game reads; default [xbe].title_id.
title_ids = [0x4D530065]
# "resign": the [[saves.signed]] recipes are recomputed on every import.
# "none": the game signs nothing. Absent: import, with a warning that the
# saves may need re-signing and may not load.
signing = "resign"
# "ignore": TDATA never imports. "optional": only with --with-tdata.
# "required": always imported with the saves. Default "optional".
tdata = "optional"

[[saves.signed]]
glob = "*/blinx2data.bin"     # under UDATA/<title id>/
size = 81920                  # provisional until task 0.1
data = [0, 33972]             # HMAC-SHA1 input, [start, end)
digest = 33972                # 20-byte digest offset
key = "roamable"              # the only kind in v1
```

A glob may have several `[[saves.signed]]` entries, one per signed block,
in case task 0.1 finds a second block in 33992..81920. They must share the
glob's `size` and must not overlap one another's digest.

The manifest validates the table:
- Ranges must fit `size`.
- A digest must not overlap any data range of the same glob.
- The glob must be relative, with no `..`.

The re-sign key for `roamable` is the build's `XboxSignatureKey`, 16 zero
bytes. A CLI pytest pins the constant, citing the toolkit line. If the
toolkit ever gains another key mode, the recipe gains a matching `key`
value; nothing switches implicitly.

### D4. Import plan

1. **Resolve the source.** Enumerate `UDATA/<tid>/`, and `TDATA/<tid>/`
   when `[saves] tdata` and `--with-tdata` call for it.
   - The title directory's name is the only title ID. `TitleMeta.xbx`
     `TitleName=` is shown, with a warning when it differs from the game's
     name, but it never decides the title.
   - Title IDs match case-insensitively and are written lower case, as XAPI
     writes them. Save IDs keep their case.
   - A save directory with no title directory above it (a bare save folder)
     is reported as "no title" and is not imported.
   - Several saves under one title are independent: each is classified,
     skipped, replaced or rejected on its own.
2. **Classify each save.** A save in a title not in `title_ids` is
   `foreign`: listed, never imported. A save without a `SaveMeta.xbx` is
   `invalid`. A file that matches a recipe and has the wrong size is
   `invalid`. A save that breaks the name and size rules is `invalid`.
   Otherwise the save is `ok`, carrying the signing state `resign`, `none`
   or `unknown`. The save name comes from `SaveMeta.xbx` (`Name=`,
   UTF-16LE), and `NoCopy=1` is shown when present.
3. **Pick the target.** By default, the installed data dir for this host,
   plus `hdd`:
   - Windows: `[data] dir_env` when that variable is set, else
     `%LOCALAPPDATA%\<app>`, as the launcher does;
   - SteamOS: the root of the installed bundle (as `launch.sh` derives it);
     when no bundle is found, `--to` is required;
   - macOS: `~/Library/Application Support/<app>`.
   `--to DIR` overrides it.
4. **Refuse unsafe conditions:**
   - the game's process, or the process of the source's emulator, is
     running (`procs.py`);
   - the target is inside a bundle (`.app`) or under `game_files/`;
   - any part of `<target>/UDATA/<tid>` (or `TDATA/<tid>`) is a symlink or
     a junction.
   Warn when `<game_dir>/UDATA` exists and the target has no `UDATA`,
   because the runtime would keep reading the legacy folder.
5. **Back up.** Zip the target's `UDATA/<tid>` (and `TDATA/<tid>` when
   TDATA is imported) before the first write:
   - to `<data>/save-backups/<UTC yyyymmdd-hhmmss>.zip`, or to
     `DIR/../save-backups/` with `--to DIR`;
   - a stamp that already exists gets a `-N` suffix;
   - the zip must pass `testzip()` before anything is written;
   - no backup when nothing exists yet; backups are never pruned.
6. **Handle conflicts.**
   - Per save ID: an existing ID is skipped; `--replace` replaces it. IDs
     are never renamed. On a case-sensitive host, an existing title or save
     directory that differs from the source only by case is a conflict.
   - Per TDATA file: an existing file is skipped unless `--replace`.
   - Title-level files (`TitleMeta.xbx`, `TitleImage.xbx`) are written only
     when absent.
7. **Write.**
   - Each save is staged in `<target>/.save-import-tmp/`, on the same
     filesystem as the target and never inside `UDATA/<tid>/`. The recipes
     are re-signed there.
   - A new save is renamed into place.
   - With `--replace`, the old save is renamed aside within the staging
     dir, the new one is renamed in, and only then is the old one deleted.
   - A failure leaves no half-written save. A staging dir left by an
     interrupted run is removed at the start of the next one.
8. **`--dry-run`** prints steps 1-7 and writes nothing. `--json` gives the
   wizard the same plan as data.

**Name and size safety** (one rule set for folder, zip and FATX sources):
- Names are rejected when they:
  - are longer than 42 bytes (the FATX limit);
  - are `.` or `..`;
  - contain `/ \ : * ? " < > |`, NUL or a control character;
  - end in a dot or a space;
  - are a Windows reserved name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`,
    `LPT1`-`LPT9`, with or without an extension);
  - differ only by case from another name in the same directory.
- Zips also reject absolute names and drive letters.
- Folder sources never follow symlinks or junctions; a link is rejected
  with a reason. Zip entries that are symlinks are rejected too.
- Caps apply to every source: a per-file size, a per-save total, an entry
  count and a directory depth (a total of 64 MiB uncompressed by default;
  Xbox saves are small).
- A save that breaks a rule is rejected with the reason; the others still
  import, and nothing is ever written outside the target.

### D5. Wizard

A screen reached from the finish page and the start page:
- A source picker: "From xemu" (auto-detected), "From a folder or zip", "From
  an image".
- The list from `saves list --json`, with this game's saves ticked and
  foreign, "no title" and invalid saves greyed out.
- An Import button that runs `saves import --json` with the ticked IDs, then
  shows the backup path and the result.

The screen parses no formats.

### D6. SteamOS bundle

The bundle carries the importer, so a player on a Deck needs no CLI
checkout:
- `steamos.py` copies the CLI's `saves` package (stdlib only) into the
  bundle next to `install_lib.py`.
- A new template, `import-saves.sh`, sits next to `launch.sh`. It finds
  Python as `install.sh` does and runs the bundled verb with `--to` set to
  the bundle's own `<root>/hdd`, as `launch.sh` derives the root. It passes
  every other argument through, so `--from`, `--dry-run` and `--replace`
  work as in the CLI.
- With no `--from`, it uses the default detection: xemu's Flatpak
  `xemu.toml` and Cxbx-Reloaded's Proton prefixes.
- `install.sh` changes nothing: it still never writes `hdd/`, and its
  `--import-saves` copy of an old save root stays as it is.
- The bundle's README part gains a "Bring your saves" line.

### D7. Privacy

- Sources are opened read-only.
- Writes go only to the target, its staging dir and the backup.
- No network.
- Logs carry paths, IDs and names, not bytes.
- The repos' existing game-data refusals cover saves.
- Fixtures are generated by test code.

## Risks

- **Re-signing hides corruption.** Without the retail key the importer
  cannot verify the retail digest, so a corrupt save gets a valid digest and
  may crash the game or load wrong data. The user accepted this
  (2026-10-18). Mitigation: the size and structure checks, and the backup.
- **A self-consistent bug in the FATX and qcow2 code.** If the reader and the
  fixture writer share a misreading, the tests still pass. Mitigation: the
  fixture writers follow the published layouts independently, plus optional
  local oracle runs (`qemu-img`, mborgerson's `fatx`).
- **A provisional recipe.** If `blinx2data.bin` has a second signed block,
  a one-block recipe leaves it with the retail digest. Task 0.1 settles it
  before the table ships.
- **Burnout 3 and later games.** Their save formats are unknown, so they
  import with a warning until their tables exist.

## Decisions from the user (2026-10-18)

The five open questions are answered and closed:
1. **Retail key: no.** Every import re-signs under the build's key; there is
   no retail-key option or config (non-goal above).
2. **A game with no `[saves]` table** still imports. The plan and the
   output warn that its saves may need re-signing and may not load.
3. **Export: not now** (non-goal above).
4. **SteamOS: yes** (D6).
5. **Sources:** xemu (HDD and MU images) and Cxbx-Reloaded are both in v1's
   default detection (D2).
