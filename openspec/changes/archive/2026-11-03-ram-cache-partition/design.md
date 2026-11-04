## Context

`kernel_file.c` has two backends: Win32 (Windows and Proton) and POSIX. Both
export the same `xbox_Nt*File` functions. The bridge and the thunk table call
them with native HANDLEs, and the bridge maps those to guest tokens.

## Decisions

### D1. One dispatcher above both backends

Each backend's functions become static `host_Nt*`. The platform-independent
part of the file defines the public `xbox_Nt*File` functions. Each one checks
`xbox_ramfs_active()`, a cached flag, then calls the store or the backend.
With the key off, that check is the only extra cost. A single hook point means
the backends cannot drift apart.

The routing rules:

- **By path:** a path goes to the store when the first rule it matches is a
  cache rule (`Z:\`, or Partition3, 4 or 5 with a path below the device). The
  title's symbolic links are resolved first, the same way the path layer
  resolves them. The helper `xbox_path_cache_rest` in `kernel_path.c` walks
  the same links and the same rules, so the two cannot disagree.
- **Bare devices:** a bare Partition3, 4 or 5 device opened as a directory is
  a free-space query, so it opens the store's root. Opened any other way, the
  device stays on its image on disk.
- **By handle:** a name relative to a store directory handle goes to the
  store.
- **Rename:** a rename between the store and disk returns
  `STATUS_NOT_SAME_DEVICE`, as a rename across two volumes does on the
  console.

### D2. Handles are real host events

A store handle is a manual-reset event created already signalled. The store
keeps it in a small table that maps it to the open file. A real host object
keeps every other path safe: a wait on the handle returns at once (I/O
completes synchronously), and `CloseHandle` frees it. A host handle value
cannot collide with a live store entry, because the store removes the entry
before it closes the event. `NtDuplicateObject` asks the store first. A
duplicate shares the file object, and so it shares the position, as in NT.

### D3. FATX semantics in memory

- **Overwrites:** an overwrite open (supersede, overwrite or overwrite-if)
  sets the size to 0 but keeps the bytes. A later end-of-file regrow brings
  them back, as FATX does: FATX has no valid-data length. The disk backends
  get the same result from a deferred truncate. Bytes that were never written
  read as zero.
- **The cap:** it counts each file's size, rounded up to 16 KB clusters,
  and refuses growth past it with `STATUS_DISK_FULL`. Space comes back when a
  file shrinks, is overwritten or is deleted. A pending overwrite keeps its
  old size charged until it settles.
- **Volume queries:** they report the cap and the free space in 16 KB
  clusters, with 512-byte sectors.
- **IoStatus Information:** opens return the NT values, as the console's
  kernel does: FILE_SUPERSEDED, FILE_OPENED, FILE_CREATED or
  FILE_OVERWRITTEN. The disk backends return 1, or 2 for FILE_CREATE.
- **Delete:** as in the POSIX backend, the name goes at once and the bytes
  go when the last handle closes. A directory is removed only when it is
  empty.
- **Append:** only an append-only handle appends. GENERIC_WRITE carries
  APPEND_DATA and WRITE_DATA, and such a handle writes at its offset. The
  POSIX backend's `O_APPEND` mapping had the same mistake and is fixed with
  it.
- **Directory listing:** a buffer smaller than the entry header gets
  `STATUS_BUFFER_TOO_SMALL` and the entry stays next. A name cut short gets
  `STATUS_BUFFER_OVERFLOW`, the bytes that fit, and uses the entry up.
- **Failures leave no trace:** a create whose handle cannot be made removes
  the name it made. A rename makes every new name, subtree included, before
  it changes any, so running out of memory leaves the tree as it was.
  `DUPLICATE_CLOSE_SOURCE` closes the source even when the duplicate fails,
  as DuplicateHandle does.
- **Seeds on overwrite:** a seeded file opened with an overwrite disposition
  is still read in, because the deferred overwrite can hand its old bytes
  back through SetEndOfFile.
- **Host memory:** a file's buffer grows by half again, so host memory can
  run past the cap by up to half of each open file. The buffer is trimmed at
  the last close. The title sees only the cap.
- **Format:** a format of the cache partition writes the partition image,
  which stays on disk. The store keeps its files, as the disk backend keeps
  its files under `<hdd>/Cache`.
- **Sharing modes:** they are not enforced, the same as in the POSIX backend.

### D4. Seeding: lazy and read-only

On first use, the store scans `<hdd>/Cache` recursively for names and sizes,
and counts the sizes against the cap. A file's bytes are read on its first
open, so a 570 MB seed costs nothing at boot. Nothing is written back. The
on-disk cache stays as it was at the start of the run, and the next run
starts from that same state. If the seed is larger than the cap, the store
loads only the files that fit and logs the rest.

### D5. Locking

One SRW lock guards the store and the handle table. Reads and writes copy
under it. The ring writer in BLiNX 1 writes 1.9 MB per second, so holding the
lock for a memcpy of that size is negligible.

### D6. The key

`RECOMP_STORAGE_RAM_CACHE` is a CONFIG row in the main `recomp_env` table, so
it exists in builds without the enhance layer. Under the enhance layer,
`storage.ram_cache` binds to it. `xbox_enhance_init` reads the key and calls
`xbox_RamCacheEnable` before the guest starts. Without the layer, the kernel
reads the variable itself on the first file call.

## Risks

- A save the player expects to keep on Z: is lost at exit. A title that keeps
  real saves on its utility drive should leave the key off. The console gives
  Z: no guarantee of keeping data, and the key's documentation says so.
- Host memory: up to 750 MB for each title that turns the key on.
