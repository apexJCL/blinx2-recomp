# Design: overlay-saves

## Context

- Guest saves live under `\Device\Harddisk0\Partition1\UDATA\<tid>\` and
  `...\TDATA\<tid>\`. `kernel_path.c` maps both to `<user dir>/UDATA` and
  `<user dir>/TDATA`. The user dir is the save dir, or `RECOMP_SAVE_DIR`
  when set. Legacy installs can keep them in the game dir
  (`s_user_in_game[]`). The RAM cache (`kernel_ramfs`) covers only the
  Cache partitions, never these trees.
- The Files page owns a file browser (`file_browser.h`), name
  entry, an atomic write (`fb_write_atomic`) and the exports folder
  `<user config dir>/exports`.
- The menu does not pause the guest. The game keeps its save data in RAM
  and may write it again at any time.
- The toolkit has no zip or zlib library.

## Decisions

### D1 Portability: no re-signing between our installs

Every input a save signature can depend on is a constant in the kernel:

- `XboxSignatureKey`, `XboxHDKey`, `XboxLANKey`, `XboxEEPROMKey` and
  `XboxAlternateSignatureKeys` are 16 zero bytes (`kernel_bridge.c`,
  `kernel_xbox.c`);
- the HAL disk serial is the constant `XR0000000000`;
- the EEPROM settings are fixed defaults (only the time zone follows the
  host, and saves don't sign it).

So a roamable save (signed with the title's signature key, derived from
`XboxSignatureKey`) and a non-roamable one (keyed by `XboxHDKey`) verify on
every install of the same game. The zip carries no re-sign data. The
manifest's `keys` field records a fingerprint: `"zero"` while both keys are
zero, otherwise 16 hex digits of SHA-1("xbr-saves-keys" + HDKey +
SignatureKey); a fingerprint, not a secret, so a plain hash does. Import
refuses a zip whose fingerprint differs from the running build's, with
"These saves were made with different console keys". A future per-install
key would need save-import's re-sign recipes (`save-import` D4); out of
scope.

### D2 Zip format

- PKZIP, method 0 (stored) only, no zip64, no encryption, general flag bit
  11 (UTF-8 names), DOS time plus the extended timestamp extra (0x5455) for
  mtime, unix mode in the external attributes (version made by 3).
- Entries, in order:
  1. `xbr-saves.toml`, the manifest:
     ```toml
     format = 1
     kind = "saves"
     title_id = "4c410015"   # lower hex, the running title
     title = "BLiNX 2"       # from the XBE certificate
     created = "2026-11-03T12:00:00Z"
     keys = "zero"
     files = 12
     bytes = 40960
     toolkit = "<build id>"
     ```
  2. `hdd/UDATA/<tid>/...` and `hdd/TDATA/<tid>/...`, directories first
     (as `name/` entries), then files.
- The `hdd/` prefix is the layout of the host save dir, so the CLI's
  `xbr saves import --from <zip>` reads the same zip (D9).
- Deflate is out of scope: the reader refuses any other method with
  "This zip is compressed; export it again from the menu". Follow-up:
  a small inflate.

### D3 Validation

One violation refuses the whole zip; nothing is written before validation
passes.

- Caps: the zip at most 64 MiB, at most 4096 entries, 16 MiB per file,
  64 MiB uncompressed in all, path depth at most 8.
- Structure: the end-of-central-directory record found within the last
  64 KiB + 22 bytes; central and local headers agree on name, method,
  sizes and CRC; every entry lies inside the file and entries don't
  overlap; CRC32 checked for every file.
- Names (shared rule set with `save-import` D6): UTF-8; `/` only as the
  separator; no `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, NUL or control
  characters; no empty, `.` or `..` component; no leading `/` or drive
  letter; no trailing dot or space; no Windows reserved names (`CON`,
  `NUL`, `COM1`...); each component at most 42 bytes (the FATX limit); no
  two names equal ignoring ASCII case.
- Types: no symlinks or other special files (unix mode type bits must be
  regular or directory).
- Content: the manifest is required and parses; `kind = "saves"`,
  `format = 1`; `title_id` equals the running title id; every other entry
  is under `hdd/UDATA/<tid>/` or `hdd/TDATA/<tid>/` of that id; the
  manifest's `files` and `bytes` match the entries.
- Messages name the first problem in player words ("This zip is for
  another game (title 4d530004)", "This zip is damaged (bad checksum in
  UDATA/.../SaveImage.xbx)").

### D4 Busy guard

- `kernel_file.c` keeps a table of the guest's open handles (256 slots,
  an atomic_flag spinlock) whose path resolves under a title's UDATA or
  TDATA (`xbox_path_is_save`, which follows the same rules as the path
  resolver; the CACHE to TitleCache rule is not a save), in the shared
  `xbox_NtCreateFile` and `xbox_NtClose` dispatch. A relative open under a
  tracked directory handle is tracked too. Create, write, set-information,
  rename, delete and close stamp the tick there; only file (not
  directory) handles count as open.
- `int xbox_saves_busy(void)` returns non-zero while a handle is open or
  within 2000 ms of the last stamp.
- Export and the import apply both check it, and the apply checks it
  again right before the swap. Busy shows "The game is saving; try again
  in a moment".
- The game is not paused while the page copies, so one check could pass
  just before a save starts. Every stamp also moves a generation,
  `unsigned xbox_saves_gen(void)`. The page reads it before the export
  (or the backup), again after it, and in the busy check just before the
  import's first rename, and drops the copy when it moved.
- `NtDuplicateObject` with `DUPLICATE_CLOSE_SOURCE` closes its source
  without an `NtClose`; `xbox_saves_duplicated` drops the source from the
  table there, and tracks the copy as the source was.
- The guard is shared with `save-states`, which needs the same
  rule before it snapshots the trees.

### D5 Export

1. Busy check.
2. Collect `UDATA/<tid>` and `TDATA/<tid>` (either may be missing) with
   `lstat`, skipping links and special files, within the D3 caps.
3. Build the zip in memory and hand it to the Files browser:
   `fb_export_begin` with root Exports, filter `.zip`, default name
   `fb_default_name("<slug>-saves", ...)`. The slug comes from the title
   name through `shader_profile_slug`; with no title it is
   `saves-<tid>`.
4. The browser writes it with its temp-then-rename write.

An empty save tree exports nothing: "No saves yet".

### D6 Import

1. Pick a `.zip` in the browser; read it with `fb_import_entry`, cap
   64 MiB; validate (D3).
2. Preview: the manifest's title and date, the save names (from each
   save's `SaveMeta.xbx` `Name=` line, UTF-16LE), file count and size,
   and what it replaces (the current saves). Actions: "Import and quit",
   Cancel.
3. Apply:
   - busy check;
   - back up the current trees to
     `<exports>/save-backups/<slug>-saves-backup-<stamp>.zip`, same format,
     so a backup imports like an export; a failed backup stops the import;
   - write each tree the zip carries to a new folder
     `.saves-import-<stamp>-<pid>-<n>-<TREE>` beside its live root (the
     same volume, so the swap is renames), with the mtimes. The folder is
     made exclusively (`n` counts up past one that is there), so a retry
     in the same second never reuses, and then deletes, a folder an
     earlier failed undo kept;
   - busy check again, then for each tree: rename the live `<tree>/<tid>`
     aside, rename the staged one in; on any failure, put back every tree
     already swapped and report. If a put-back fails too, the report says
     the undo failed, names the tree and the stage folder that keeps its
     old saves, and leaves that folder. On Windows a folder with an open
     handle under it does not move: the report then says the game may
     have the folder open, to quit to the title menu and try again;
   - remove the old trees;
   - `recomp_quit_post("saves_import")`, so the game cannot overwrite the
     imported saves from RAM. With no poster (GDI), the status says
     "Saves imported. Quit the game now without saving".
- A tree the zip doesn't carry stays as it is.
- The stage folders sit in the hdd folder, which the title can list.
  Above it a rename could cross volumes (an hdd folder linked to another
  disk), and the import quits the title before it could look, so they
  stay there; only a kept stage folder outlives the import.

### D7 The Saves page

- A new `PAGE_SAVES` ("Saves") before Files. Rows: a header with the
  title, the save list (name, size, date; up to 12, then "and N more"),
  the folder path, Export, Import, and on desktop builds
  "Open exports folder". The list is read when the page opens and after
  each job.
- The Files browser takes its host page from `s_fb_page`, so Saves and
  Files share one browser and name entry.
- Icon: Lucide `save` when the glyph subset can be rebuilt; else
  `DOWNLOAD`. Follow-up if it stays `DOWNLOAD`.
- The enhance_menu tests change their page count (9 to 10) and the order
  check that reaches Files.

### D8 Where the files are

- Exports and backups are under the user config dir: `%LOCALAPPDATA%` on
  Windows, Application Support on macOS, `~/.local/share` or the bundle's
  data dir on Linux and SteamOS.
- SteamOS Game Mode has no file manager, so the page shows the full path,
  and the browser's Home root (`Z:` under Proton) reaches a USB stick or
  `~/Downloads`. Desktop Mode reaches the same path.

### D9 Relation to save-import and save-states

- `save-import` (CLI): imports original Xbox, xemu and
  Cxbx-Reloaded saves, re-signing with the zero key. Its `zip` source
  takes any zip holding `UDATA/` under some prefix, so our export works
  as its input. Both share the D3 name rules and the zero-key fact (D1).
  Neither imports through the other.
- `save-states`: its SAVE chunk covers the same two trees and
  will use the D4 guard. Its slots under `states/` are not in our zip.

### D10 Backend parity

No draw changes: the page is rows like every other page and draws the
same on Metal and D3D11. The quit poster exists on SDL/Metal and D3D11.
The GDI backend has none (D6 fallback text; follow-up).

### D11 Tests

- `tests/saves_zip` (ctest, pure): write then read round trip; each
  refusal (caps, zip-slip, `..`, backslash, drive letter, absolute path,
  reserved name, case duplicate, symlink mode, bad CRC, header mismatch,
  truncated file, deflate, encrypted, missing or bad manifest, wrong
  title, entry outside the title, count mismatch, key mismatch).
- The same ctest, on a temp dir: collect, export, stage and swap; the
  rollback, with renames failed on purpose through
  `saves_store_rename_hook` (each of the four renames, and a failed
  put-back, which must say so and keep its stage folder); a retry that
  must not reuse a kept stage folder; a zip of more saves than the list
  holds, each counted once (saves_store has no separate ctest).
- `tests/kernel_directory_posix`: the busy table (open, close, the 2 s
  window, a relative open, a directory handle, CACHE not counted), the
  generation, and a handle closed by its duplicate.
- `tests/enhance_menu`: the Saves page exists and its rows build; the
  updated page count and order.

## Risks

- A guest that keeps a save handle open for the whole session blocks
  export. The busy message says so; none of our games do this as far as
  traces show.
- A player who ignores "quit without saving" on GDI can overwrite the
  import. Only GDI lacks the poster.
