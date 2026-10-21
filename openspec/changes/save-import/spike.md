# Spike: import a player's Xbox saves

Date: 2026-10-17. Agent `save-import`, branch `spike/save-import` off cat
`main` 4317f84; toolkit read at `posix-host/portability` 878d473a, CLI at
`main` f34648a. This is an assessment only: no code, no runs, and no real
saves were read.

## Verdict

**Go-limited.** I recommend a game-agnostic importer in the CLI (`xbr saves`,
reached as `<slug> saves`), driven by a new `[saves]` table in `game.toml`.

- Version 1 reads folders, zips, xemu HDD images (qcow2 or raw), xemu's
  memory-unit images and Cxbx-Reloaded's save folders, and detects xemu and
  Cxbx-Reloaded by default.
- It re-signs the files a game signs, on every import, using a recipe that
  the game declares.
- It never touches the runtime.
- The wizard gets an "Import saves" button that runs the verb, and SteamOS
  bundles get an import launcher next to `launch.sh`.

Deferred until there is a sample: Action Replay `.xsv` and non-roamable
(HDD-key-locked) saves. Out of scope by decision (the user, 2026-10-18):
export, and any use of the retail-derived key.

The verdict is limited because of signatures. My builds sign saves with a key
no retail console uses. So every game that signs its saves needs a per-game
recipe, written once its save format is known, before an imported save of that
game will load.

## 1. The recompiled side today

**A plain folder tree, not an image.**

The kernel maps the save paths to host folders:

- `\Device\Harddisk0\Partition1\UDATA` and `...\TDATA` go to
  `<user root>/UDATA` and `<user root>/TDATA` (toolkit
  `src/kernel/kernel_path.c:63-64`).
- The title maps `U:` and `T:` itself, to `E:\UDATA\<title id>` and
  `E:\TDATA\<title id>` (`kernel_path.c:54-62`).
- `E:\CACHE` goes to `TitleCache` (`:65-81`).
- The user root is `RECOMP_SAVE_DIR` when set, and the save root otherwise
  (`kernel_path.c:531-553`; the POSIX twin starts at `:726`).

`Partition0-5.img` exist only so a title can read the partition table and size
the devices (`kernel_path.c:249-300`, `:770-797`). Partition0 holds only the
table. The other images are sparse and unformatted. No FATX is involved on
this side.

Follow-up for the toolkit: its E: size, 0x465400 sectors
(`kernel_path.c:268,290`), is not the retail 0x9896B0 sectors
(0x1312D6000 bytes). The importer must not reuse it.

Where the save root is:

- It is `RECOMP_HDD_DIR` (cat `src/main.c:1067-1077`, `:1206-1207`).
- When that is unset, the default is `%LOCALAPPDATA%\xboxrecomp` on Win32
  (`kernel_path.c:451-458`). On POSIX it is `$XDG_DATA_HOME/xboxrecomp`, or
  `~/.local/share/xboxrecomp` (`:738-749`).

The packaged launchers set `RECOMP_HDD_DIR` to `<data>/hdd`:

- **Windows:** `%LOCALAPPDATA%\<app>\hdd`, or the `[data] dir_env` variable
  when it is set (CLI `package/templates/windows/launcher.c:10-15,169`).
- **SteamOS:** `Z:<root>/hdd`, where the root comes from the installed bundle
  (`steamos/launch.sh:30,151`; the default root is `~/Games/<app>`).
- **macOS:** `~/Library/Application Support/<app>/hdd` (cat
  `packaging/macos/BLiNX2.in:69`).
- These values come from `game.toml` `[package] app` and `[data]`
  (`game.toml:67-73,87-88`). They follow the deployment spec
  (`openspec/specs/deployment/spec.md:9`).

So a BLiNX 2 save lives at `<data>/hdd/UDATA/4d530065/<save id>/`. Once a
save is in that folder layout, importing it is a file copy.

Legacy case: older builds kept saves in `<game_dir>/UDATA`. The runtime still
uses that folder when the save root has none (`kernel_path.c:122-135,
556-571`). Bundles exclude `UDATA` and `TDATA` (`game.toml:69`), so in
practice this only happens in dev trees.

**Existing import paths.**

- `install.sh --import-saves DIR` copies an old save root into an empty
  `hdd/` only (CLI `package/templates/steamos/install_lib.py:868-885`). It
  runs only on SteamOS and checks neither the title nor the signatures.
- `RECOMP_SAVE_SEED` is a bench tool that copies a tree before boot (cat
  `src/save_seed.c:1-13`).

**Signatures.**

The kernel's keys:

- The kernel exports `XboxSignatureKey` (ordinal 325) and `XboxHDKey` (323)
  as 16 zero bytes (toolkit `src/kernel/kernel_bridge.c:326-336`; the host
  copies are at `kernel_xbox.c:51-57` and `kernel_thunks.c:326-330`).
- `XcHMAC` is a real HMAC-SHA1 (`kernel_crypto.c:257-311`).

On a retail console, at launch, `XboxSignatureKey` is set to a per-title key:
HMAC-SHA1 of a retail kernel constant and the XBE certificate's 16-byte
signature key at certificate +0xC0, cut to 16 bytes. This matches the public
re-signer [PMStanley/xbox-save-sig](https://github.com/PMStanley/xbox-save-sig).
XAPI's `XCalculateSignature*` uses that key directly for roamable signatures.
For non-roamable ones it mixes in the HDD key.

**BLiNX 2 checks its signature.**

- The check is an HMAC-SHA1 over `blinx2data.bin[0, 33972)`, with the digest
  stored at 33972.
- A community (retail-signed) save reads as damaged until a local re-sign
  helper writes the zero-key digest
  (`openspec/changes/archive/2026-10-13-input-real-devices/design.md:78`).
- Under this kernel, a non-roamable key would be HMAC(zero HDKey, zero key),
  which is not zero. The zero key works, so BLiNX 2 uses roamable signatures.
  A save from any console or any xemu install therefore imports after a
  re-sign, and no HDD key is needed.
- The file size of 81920 bytes and the single signed block are known from one
  sample only. That is provisional until phase 0 confirms it. 81920 is
  2 × 40960, so 33992..81920 could hold a second signed block.

**Burnout 3: unknown.** Nothing in `b3/` records a save format or a check.
Phase 0 answers it from a save the game writes under this build.

## 2. Sources

| Source | Format | Readable how (stdlib) | Signature status | Priority |
|---|---|---|---|---|
| Copied `UDATA` folder (FTP from a softmod, a FATXplorer extract, a USB copy) | dashboard tree `UDATA/<tid>/<save id>/` | `os.scandir` without following links; root normalisation (`E/`, `UDATA/`, `<tid>/`) | retail key; roamable saves need a re-sign | P1 |
| Save zip (GameFAQs and similar) | zip of `UDATA/<tid>/...` (community BLiNX 2 saves are plain zips, not `.xsv`) | `zipfile`, with the name and size rules | same | P1 |
| xemu HDD, qcow2 | qcow2 v2/v3: L1/L2 cluster map, optional zlib clusters, optional backing file. Internal snapshots (save states) do not affect the active image | ~300 lines with the hardening in design D2 | retail key (xemu runs a real BIOS); roamable saves need a re-sign | P1 |
| xemu HDD, raw (`dd` of a real drive) | full-disk image with the retail partition layout | E: at 0xABE80000, size 0x1312D6000 | same | P1 |
| FATX (inside both) | superblock "FATX"; FAT at +0x1000; FAT16 or FAT32; 64-byte dirents | ~250 lines, read-only (design D2) | n/a | P1 |
| Memory unit image (xemu `peripheral_param` `.bin`, an MU dump) | raw FATX at offset 0, sized by the file; title dirs at the root | same FATX reader | roamable only, by design | P1 |
| Cxbx-Reloaded | host folders `EmuDisk/Partition1/UDATA/<tid>/` under its data dir (to confirm in task 0.3 against its source) | folder reader, found by default detection | unknown; re-signed like every import | P1 |
| Action Replay `.xsv` | not publicly documented (searched) | needs a real sample | unknown | defer |
| Xenia | Xbox 360 STFS, not an original Xbox format | n/a | n/a | out of scope |

Where xemu keeps things:

- `xemu.toml` is in SDL's pref path, `SDL_GetPrefPath("xemu","xemu")` (xemu
  `ui/xemu-settings.cc`), or next to the executable in portable mode:
  - Windows: `%APPDATA%\xemu\xemu\`
  - macOS: `~/Library/Application Support/xemu/xemu/`
  - Linux: `~/.local/share/xemu/xemu/`
  - Flatpak, the usual Steam Deck install:
    `~/.var/app/app.xemu.xemu/data/xemu/xemu/`
- The image path is `[sys.files] hdd_path`.
- MU images are `[input.peripherals.portN] peripheral_param_*` (xemu
  `config_spec.yml`).
- The detector reads `xemu.toml` and never guesses file names.
- The xemu FAQ warns that saves may be tied to the HDD key in its EEPROM.
  That is the non-roamable case below.

Where Cxbx-Reloaded keeps things (a Windows program; task 0.3 confirms each
path against its source):

- The data dir is `%APPDATA%\Cxbx-Reloaded\` by default, the executable's
  directory in portable mode, or the custom location in its `settings.ini`.
  Saves are under `EmuDisk\Partition1\UDATA\` there.
- On Linux and SteamOS it runs under Wine or Proton, so the same tree sits in
  a prefix, at the prefix's `%APPDATA%\Cxbx-Reloaded\`.
  The detector looks in the default Wine prefix and in Steam's
  `compatdata/*/pfx` prefixes, and reads only the folders that exist.
- On macOS it runs only under Wine-based tools, so it is reached with
  `--from`.

In version 1 (the user, 2026-10-18), default detection covers xemu (its HDD
image and the MU images `xemu.toml` names) and Cxbx-Reloaded's folders. Any
other source is reached with `--from`.

Every format I read can be covered with synthetic fixtures. A real xemu image
would confirm the quirks of xemu's prebuilt drive, but it would not change the
verdict. A real `.xsv` would change the `.xsv` row. I fetched neither.

## 3. Signatures

**Roamable saves, the common case.** The game's own XAPI code compares an
HMAC-SHA1 under `XboxSignatureKey`. So an imported retail save fails unless one
of two things is done:

- (a) re-sign it with the build's zero key on import;
- (b) have the kernel export the retail-derived per-title key.

Option (b) needs a Microsoft key constant. It would also invalidate every
save these builds have written, and it would change stock behaviour.

**Decided: (a)** (the user, 2026-10-18). Every import re-signs under the
build's key. There is no retail-key option and no retail-key config, and the
key is never stored anywhere.

- Each game describes its signed files in `game.toml`: a file glob, the data
  range, the digest offset and the expected size.
- The importer recomputes those digests with the build's key.
- Games that sign nothing declare `signing = "none"`.
- A game without a table still imports, and the plan and the output warn
  that its saves may need re-signing and may not load (the user, 2026-10-18).

**Verification.** Without the retail key, a corrupt save cannot be told from a
good one, so the importer checks structure only (title, names, sizes, the
recipe's size). That is accepted: the backup is the safety net.

**Non-roamable saves.** Verifying or re-signing them needs the source console's
HDD key, from xemu's encrypted `eeprom.bin` or a console EEPROM. Out of scope:
they import as unverified, and they may read as damaged.

**Disabling the check.** I rejected this:

- patching a game's comparison is per game and happens in generated code,
  which is never hand-edited;
- an `XCalculateSignature` HLE hook would change stock behaviour.

## 4. Ownership

- **The CLI owns the logic.** It is stdlib Python, so `zipfile`, `zlib`,
  `hmac` and `hashlib` come for free. It already reads XBE headers, disc
  images and `game.toml`, and it knows each target's data dir.
- **New verb** `xbr saves {list,import}`. All game constants come from
  `game.toml`; the CLI holds none.
- **The wizard (Go) is a front end only:** pick a source, show
  `saves list --json`, tick saves, run `saves import`.
- **SteamOS bundles (the user, 2026-10-18: yes).** Stdlib Python is on
  SteamOS, so the `saves` module ships in the bundle next to
  `install_lib.py`. An `import-saves.sh` launcher sits next to `launch.sh`.
  It finds Python as `install.sh` does and runs the bundled verb with the
  bundle's own root as the target, so a player on a Deck needs no CLI
  checkout. Steam Deck sources come from the same default detection
  (xemu's Flatpak config and Cxbx-Reloaded's Proton prefixes) or `--from`.
- **The toolkit is unchanged in v1.** The CLI's re-sign key must match the
  toolkit's zero key (`kernel_bridge.c:330`), and a pytest pins it.
- **Opt-in, and the backends agree trivially.** Nothing in the renderer,
  audio or runtime changes, and nothing runs unless the player runs the verb.
- **Deployment rule.** The deployment rule that no installer, update,
  rollback or uninstaller writes `hdd/` (`deployment/spec.md:9`) still holds.
  The importer is a verb the player runs, not an installer.

## 5. User experience and safety

**Detect.** `saves list [--from PATH]` lists saves per title ID. It marks this
game's titles and shows, for each save:

- the save's name (`SaveMeta.xbx` `Name=`), and `NoCopy=1` when it is set;
- the title name (`TitleMeta.xbx` `TitleName=`), with a warning when it
  differs from the game's name;
- the source, size and modified time;
- the signing state.

`--json` feeds the wizard.

**Choose.**

- By default the importer takes every valid save of this game's title IDs.
  `--save ID` picks single saves.
- Saves from other titles are listed as foreign and never imported.
- TDATA follows the game's `[saves] tdata` setting.

**Target.**

- The target is the installed data dir. On Windows that honours
  `[data] dir_env`; on SteamOS the root comes from the installed bundle or
  `--to`.
- The importer refuses to run while the game, or the emulator the source
  comes from (xemu or Cxbx-Reloaded), is running.
- It refuses a target whose path contains a link.
- It warns when the legacy `<game_dir>/UDATA` would win.

**Back up.**

- Before the first write, the importer zips the existing saves. The zip goes
  to `<data>/save-backups/`, or to `DIR/../save-backups` with `--to`, and is
  checked with `testzip()` first.
- The backups are never pruned.
- `--dry-run` writes nothing.

**Conflict.** An existing save ID, or a TDATA file, is skipped unless
`--replace` is given. IDs are never renamed. A name that differs only in case
counts as the same save.

**Reject.** Each save is rejected on its own, with a reason, and the rest still
import. The importer rejects:

- unsafe names (design D4: one rule set for folders, zips and FATX);
- links;
- oversize files;
- the wrong title;
- a missing `SaveMeta.xbx`;
- a recipe size mismatch;
- a qcow2 or FATX image that fails the D2 checks.

**Privacy.**

- No network access.
- Sources are read-only.
- Writes go only to the target, its staging dir and the backup.
- Logs carry paths and names, never contents.
- Fixtures are synthetic.

**Per OS, the target is:**

- Windows: `%LOCALAPPDATA%\<app>\hdd`.
- SteamOS: `<root>/hdd`. These are Linux paths, never a Wine prefix path.
- macOS: `~/Library/Application Support/<app>/hdd`, never inside the `.app`.

## 6. Plan, sizes and tests

| Phase | What | Size |
|---|---|---|
| 0 | Facts: BLiNX 2's recipe and file size; Burnout 3's save name, sizes, roamability and check; TDATA use per game; the Cxbx-R layout | S-M |
| 1 | CLI: `[saves]`, folder and zip sources, `list`/`import` with backup, dry run, conflicts, staging, process checks (including a Windows lister), re-sign; BLiNX 2's table | M (~700 lines + tests) |
| 2 | CLI: read-only FATX, hardened qcow2, raw-disk and MU readers; xemu.toml discovery | M (~650 lines + tests) |
| 2 | (adds) Cxbx-Reloaded discovery on Windows and in Wine and Proton prefixes | S |
| 3 | Wizard import screen | S-M |
| 4 | SteamOS bundle: the `saves` module and `import-saves.sh` | S |
| 5 | Release: CLI CHANGELOG and version, cat's CLI pin | S |
| later | `.xsv` and non-roamable saves, each once there is a sample | decide per item |

Tests run on synthetic data:

- a FATX writer: FAT16 and FAT32 on both sides of the threshold, deleted
  entries, multi-cluster files, unsafe names;
- qcow2 wrappers: v2 and v3, a compressed cluster, raw and qcow2 backing files,
  every refusal;
- zips and folders with unsafe names, links and oversize files;
- a recipe HMAC vector;
- backup, conflict and staging cases.

An optional local oracle (`qemu-img check`, mborgerson's `fatx`) guards
against the reader and the writer sharing the same misreading.

## Decisions (the user, 2026-10-18)

1. **Retail key: no.** Every import re-signs under the build's key. There is
   no retail-key option or config.
2. **A game with no `[saves]` table** still imports, with a warning in the
   plan and the output that its saves may need re-signing and may not load.
3. **Export: not now.** It is not low-hanging. A zip of the save root is
   easy, but its saves carry the build's zero-key digests, so they would not
   load in xemu or on a console without the retail key, which is out of
   scope. Export stays a non-goal.
4. **SteamOS: yes.** The bundle ships the importer and an `import-saves.sh`
   launcher next to `launch.sh`.
5. **Sources:** xemu (HDD and MU images) and Cxbx-Reloaded are both in v1's
   default detection.
