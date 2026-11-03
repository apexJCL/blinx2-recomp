# Design: per-title default `<hdd>`

## Where the name comes from

The toolkit names the default root after the XBE title id. The id is read
from the certificate in `xbox_MemoryLayoutInit`, which every game calls
before `xbox_path_init` (template step 3 against step 6; cat, BLiNX 1, JSRF,
SSX 3 and Spartan follow it). `xbox_path_set_title_id` stores it, and
`xbox_path_init` uses it only when its `save_dir` argument is NULL.

Why the title id:

- It is already the save key. The Xbox keeps a title's saves in
  `UDATA/<tid>` and `TDATA/<tid>`, and the shared root on the Mac holds six
  of them. Folder names match those, and the migration can tell which saved
  data belongs to the running title without guessing.
- Every game gets the fix with the new toolkit pin and no source change,
  including a parked one (Spartan) and a new one from the template.
- Two titles never share an id. Regional builds of one game often do, and
  then they share saves, as on the console.

Alternative, not taken: each game passes its own default, for example
`xboxrecomp/<slug>` with the slug from `game.toml`, through a new
`xbox_path_set_default_name()` call or a CMake definition. The folder name
reads better (`blinx2` rather than `4d530065`), but it needs a change and a
toolkit pin move in five game repos. A game that misses the change keeps
sharing. It also needs a slug-to-title map for the migration. A later
change can add the call: a name set by the game would take the place of the
id, and the migration would stay keyed by the id.

## Migration: copy once, never move

On the first run with a per-title root (no `.legacy-saves` marker in it),
for `UDATA` and `TDATA`:

1. The source is `<base>/xboxrecomp/<NAME>/<tid>` and the destination is
   `<root>/<NAME>/<tid>`.
2. If the source is a directory and the destination does not exist or is an
   empty folder, the tree is copied to `<root>/<NAME>/<tid>.copying.<pid>`,
   each file and folder flushed and with its times kept, then renamed to the
   destination (`rename` replaces an empty folder; Win32 deletes it before
   `MoveFileExW` through a handle that shares nothing, see step 3). An empty
   destination counts as absent because BLiNX 2 makes an empty `TDATA/<tid>`
   at boot, and `UDATA/<tid>` on its first save, so after a failed copy the
   game itself would otherwise stop the retry. The times matter:
   `XFindFirstSaveGame` reports a save folder's last write as the save's date.
   A crash midway leaves only the `.copying.<pid>` tree, which a later attempt
   removes once that process is gone (or is the attempt's own: Wine reuses
   process ids). The copy's top folder must not exist after that cleanup: a
   leftover of the same name (a pid reused in another pid namespace) fails the
   copy rather than mix into it. The bare `<tid>.copying` of the first version
   of this change is removed the same way. That tree is a partial copy the
   runtime made, so removing it loses nothing. A half copy is never taken for
   the save. Stale trees are removed whether or not the destination exists.
3. Two instances started together on a new root each copy into their own
   `.copying.<pid>`; the first rename wins, and the other finds the
   destination in place and counts it as already present. A rename that loses
   to a folder with entries asks whether that folder holds the copy:
   every entry at the top of the source, with the same name and last write,
   since a copy keeps the times. Another instance's copy does, even after its
   game added a save there. A folder another instance's game made during the
   copy does not, so its save is kept and the folder fails with its note (step
   7): the old saves were not copied. Names alone would not do: a game with
   fixed slot names makes the same ones. On Win32 the empty destination is
   deleted through a `DELETE` handle that shares nothing, by marking it for
   deletion on that handle, which is the only one, not with
   `RemoveDirectoryW`. A running instance whose game made that folder and
   holds it open makes the open fail, so the copy fails and is retried next
   run. `RemoveDirectoryW` would only mark the folder for deletion, and it
   would vanish under that instance once it closed it. Only a plain empty
   folder is deleted, never a file or a junction. On POSIX `rename` replaces
   the empty folder atomically. An instance that holds the old one open keeps
   a handle on a removed folder, and its paths reach the copy.
4. The parent (`UDATA`, `TDATA`) is created only for the copy, and removed
   again when the copy fails and leaves it empty. An empty `UDATA` in the
   root would hide saves still in the game dir (`s_user_in_game`) until the
   next run.
5. A link to a regular file is copied as the file. A link to a folder, a
   junction or reparse point, a dangling link or a special file fails the
   copy, so a save is never adopted with a part silently missing.
6. When both folders are in place (copied now, or already there) or there
   was nothing to copy, the marker `<root>/.legacy-saves` is written. It
   names the source root, what was copied and what was already present.
   With the marker present, the copy does not run again. This means a
   player who deletes the new copy of a save does not get the old one back.
7. Any failure is logged as a warning naming both paths (including a path
   too long for the copy or the marker), the marker is not written, and a
   failed folder leaves `<root>/.legacy-saves-failed-<NAME>`. The next run
   tries again while the destination is missing or empty. Every failure
   writes the note: a parent that cannot be made, a path too long (the
   note's path is built first) and a save made during the copy. The note
   says in words what to do. A note that cannot be written is logged:
   without it, a later save would make the folder count as present, and
   the marker would leave the old saves behind unreported. A note whose
   folder is gone from the shared root is removed, unless the shared
   root's whole `<NAME>` is missing (a root unmounted for now): then the
   note is kept and the marker is not written, so a run with the root back
   looks again. A note
   next to a folder that holds the copy (step 3) is removed and the folder
   counts as present: an earlier run lost the rename to another instance's
   copy, or the player copied by hand with the times. If the player
   has saved into it in between, it is not overwritten: the marker stays
   unwritten and each run logs that the old folder waits in the shared root
   for a copy by hand, after which deleting the note ends the check (the
   folder then counts as already present). A successful copy removes the
   note. The source is never written, moved or deleted. The title then
   starts with no save in the new root, and the old one is still in the
   shared root.
8. Before the marker is written the root is flushed, so the folders' names
   are on the disk before the marker that says they are there. On macOS the
   flushes use `F_FULLFSYNC` (`fsync` leaves the data in the drive's cache);
   that is cheap here, a handful of files once per title. A file system that
   refuses the times (`futimens`, `utimensat`) logs a warning and the copy
   goes on: the times date the save, and a folder without them does not
   read as a copy in step 3.

Limits:

- The warnings are only in the log and in the note file in the root. The
  game shows nothing, so a player who never reads either keeps the old
  saves only in the shared root, which is intact.
- The copy test in step 3 assumes the copy keeps its entries' times. On
  a file system that refuses them (logged), or once the winner's game has
  rewritten a top-level file or replaced a save folder's entries, the
  loser reads the winner's copy as not a copy. This can happen at any
  point during the loser's whole copy, which with a flush per file can
  take a second or more. The loser then fails with a note. The note is
  misleading: the old saves are already in place, and copying the shared
  root's folder over by hand could put an older save over a newer one. Its
  text says to check first. A later run removes the note once the folder
  holds the copy again; until then it blocks the marker on every run,
  even after the winner's marker, until the player deletes it.
- On Win32, between the delete and `MoveFileExW`, another instance can
  briefly find the folder missing, or make it again. In the second case
  the move fails and the copy is retried next run.
- A handle opened with no data access, only attributes, does not conflict
  with the share-nothing open, so a folder held that way is still
  replaced.
- Any other process that holds the empty Win32 destination open blocks the
  share-nothing open just as a running instance does: an Explorer window
  on an empty `TDATA/<tid>`, the search indexer or a virus scanner. The
  copy fails for that run with its note, the log says the folder is open
  elsewhere, and the next run tries again.
- A source folder that cannot be read for a moment (access denied on
  Win32) looks gone, so its note is removed. If the other folder failed,
  a save made in the new root before the source comes back makes the
  folder count as present, and the old saves are left behind unreported,
  not lost. A missing `<NAME>` in the shared root keeps the note and
  leaves the marker unwritten, so each run looks again until the root is
  back or the player deletes the note.
- A new root on a file system with coarser times than the shared root's
  (exFAT or FAT32 on removable media, HFS+ against APFS) never reads as a
  copy in step 3. Every lost race there leaves a note, and such a note is
  not removed on its own. It fails safe: the saves are kept.
- Only names and times are compared. A link in the source matches on
  POSIX (`stat` follows it) and does not on Win32 (the link's own time is
  read). A `.DS_Store`, `desktop.ini` or `Thumbs.db` that a file browser
  rewrote in the shared root's folder after the copy also makes it read as
  not a copy. Both fail safe, with a note left in place.

What is not copied:

- `Cache/`, `TitleCache/`, the partition images, `SystemData/` and the
  shader cache. They are scratch. Copying `Cache/` would carry the other
  games' pages along, which is the bug this change fixes.
- `TitleData/` and `UserData/` (the bare `T:\` and `U:\` rules). They are
  not keyed by title. Titles reach their saves through
  `XapiMapLetterToDirectory`, which goes to `UDATA/<tid>` and `TDATA/<tid>`.
  These two folders are empty on the Mac.

Why not a fallback that keeps reading the shared root: the saves would stay
in the shared root next to the shared `Cache/`, and every path rule would
need a second root. A one-time copy keeps one root per title and leaves the
old one untouched, so nothing can be lost.

The migration also runs when the saves are in the game dir
(`s_user_in_game`). The check for that runs after the copy, against the new
root. It behaves as before: a copied `UDATA` in the root wins over one in
the game dir, as the shared root's did.

## Windows

The Win32 backend does the same with `%LOCALAPPDATA%\xboxrecomp\<tid>`,
using `CreateDirectoryW`, `CopyFileW` (which follows a link to a file and
keeps the last write), `FlushFileBuffers`, `SetFileTime` for folders and
`MoveFileExW`. `CopyFileW` keeps a read-only attribute, which refuses the
write handle the flush needs, so the flush lifts it and puts it back, and
opens with full sharing; removing a stale tree lifts it before
`DeleteFileW`. `%LOCALAPPDATA%` is read from the environment when it holds
an absolute path, so a test or a scripted run can point it at scratch, and
from the known folder otherwise. Under Proton that is inside the prefix, as
before, and launchers set `RECOMP_HDD_DIR` anyway. A base too long for the
root falls back to `SaveData` in the current folder with a warning
(`_snwprintf_s` with `_TRUNCATE`; `swprintf_s` would abort). A
`RECOMP_SAVE_DIR` too long for the rules is dropped with a warning, and the
copy then runs as if it were unset, as on POSIX, where it is never dropped.
Win32 does not flush folder entries (no directory fsync there).

## Test

`tests/kernel_path` (cross-platform) calls `xbox_path_adopt_legacy_saves`
with explicit roots. On both backends it covers the copy, the marker and
its text, an existing destination left alone, stale `.copying` and
`.copying.<pid>` trees (also beside a destination already in place), a
failed copy (an unreadable file: a `chmod 0` on POSIX, a file held open
with no sharing on Win32) that leaves no marker and no empty `UDATA` and is
retried, the game between two attempts (empty `UDATA/<tid>` and
`TDATA/<tid>` made after a failed copy are copied over; a folder saved into
after a failed copy is kept, gets no marker, and counts as present once the
note is deleted), a note on every failure path (a parent that cannot be
made, a root that is not there, where the failed note write is checked in
the log, a copy name too long, a note whose folder is gone, one kept with no
marker while the shared root's whole `UDATA` is missing), a note removed
once its folder holds the copy or its source is empty, and kept while it
does not, two racing threads (a save made
in the new root during the copy fails with the note; another instance's
copy with a save added counts as present; each tries up to five times and
fails when the racer never reaches the copy), file and folder times kept,
and the full default root with the data folder (`XDG_DATA_HOME`,
`%LOCALAPPDATA%`) in its temp dir: two title
ids get two roots and two `Cache` dirs, a zero id keeps the shared root,
and the copy happens on the first init and not on the second. On POSIX it
also covers links (to a file, to a folder, dangling) and four forked
instances racing on one new root, and on Win32 a read-only save file
(copied, still read-only), a stale tree holding one (removed) and an
empty destination another handle holds open (left, retried). The Win32
cases run natively on Windows (the PC); a run under Proton is still owed,
since Wine's share and delete semantics differ from NTFS.
