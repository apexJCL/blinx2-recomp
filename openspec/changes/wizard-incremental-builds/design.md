## Context

cat `main` ffd3562 (this branch was cut at 277e780); `xboxrecomp-cli`
`main` 06b9bc4; b3 f7baab9; `ssx3/recomp` 3d75004; `spartan/tca` (no
git). Facts below are from reading those trees on 2026-10-17. Nothing was
built or run for this spec.

What a re-run already skips. `xbr package` runs import, setup, generate,
build, stage and wrap (`package/__init__.py` `package_plan`).

- The import is skipped when `dump.prepare` finds the same XBE sha256.
- Setup is skipped when `.venv`, llvm-mingw and the toolkit clone match
  their pins.
- Generate is skipped unless `pipeline.gen_stale_reasons()` names a reason.
  The gen key (`GEN_KEY_VERSION = 2`) holds the XBE sha256, the toolkit
  state (the tree ids of `tools/` and `templates/runtime/` plus a dirty
  hash), the sha256 of each config input (seeds, icall db, manual
  recomp, spin waits, name hooks, the Ghidra export), the sha256 of the
  stage argv and stage extras.
  - `begin_stage` deletes the key, a regen marker covers a crash in
    `recomp`, and `_write_json` is atomic (tmp + `os.replace`).
- The toolkit's recomp writes a gen file only when its bytes change
  (`write_if_changed`), so ninja recompiles only what moved.
- `build.reset_stale_toolchain` / `reset_stale_toolkit` drop the CMake
  cache when a pin moves.

What is redone every time:

- the icon (cached in the folder, but rebuilt when missing);
- `enhance hud` when `--hud-pack` is set (deterministic; 4 to 8 s
  measured in `enhancements-hud-pack`, the figure the wizard's estimate
  uses; `wizard-test-notes` said "a few minutes" and is corrected here);
- `stage_payload`, which copies everything into
  `dist/.stage-<target>/<app>-<version>-<target>/` (game files by
  clonefile);
- `write_manifest` (sha256 of every file, game files included);
- the wrap per target.

The bundle today:

- `manifest.json`: `schema 1`, `data_layout 1`, `built` (now), the
  version, `sources` (game, toolkit, cli: commit, branch, dirty,
  dirty_paths) and `files[]` (path, sha256, size), all checked by
  `private_leaks`;
- `SHA256SUMS`;
- the version is `<YYYYmmdd.HHMM of the exe mtime>-c<game7>-t<tk7>-g<gen8>
  [-dirty<8>]` (`lib.format_version`).
- **steamos:** a deterministic tar (uid/gid 0, mtimes from the exe)
  holding `install.sh` + `install_lib.py`. The install root is
  `~/Games/<App>/`:
  - `versions/<v>/` holds the program files;
  - `current` is a symlink, switched by an atomic rename;
  - `state/history` holds one line per switch;
  - `game_files/` sits at the root, unversioned, synced by checksum;
  - `install_program` builds `versions/<v>.partial` with hard links to the
    current version's unchanged files, verifies them against SHA256SUMS,
    then renames;
  - `rollback`, `--keep N` (default 3), `status`, `list` and `uninstall`.
- **windows:** a folder with `setup.exe` (NSIS, zlib, 67.5 MB, the program
  files) and `game_files/` beside it (NSIS caps an installer at 2 GB). It
  installs in place at `%LOCALAPPDATA%\Programs\<App>`, replaces
  `game_files` with `RMDir /r` + copy, writes `manifest.json` into
  `$INSTDIR`, and sets `HKCU ...\Uninstall\<App>` `DisplayVersion`. There
  is no rollback.
- **macos:** a `.app` with the payload in `Contents/Resources`, dylibs in
  `Frameworks` and relinked, every part signed ad hoc and checked with
  `codesign --verify --deep --strict`, in a UDZO DMG.

The wizard (`xboxrecomp-cli/wizard/`, Go + Fyne):

- `repo.Clone` makes a `--depth 1 --branch <tag>` clone into `.partial`,
  then renames it to `<root>/src`;
- a folder at another commit is refused, so a new wizard release means a
  new build folder;
- the settings file holds `root` and `out`;
- dev flags: `--game DIR` (no clone; the config comes from
  `<game> wizard config --json --dev`), `--config`, `--dry`, `--root`.

Measured on this Mac for BLiNX 2:

- **Time** (`cat/build-logs/timings.json`):
  - disasm 30 s, funcid 113 s, abi 12 s, recomp 615 s;
  - build macos 378 s cold, windows 0.8 s warm (a cold Windows cross
    build was 210 ninja steps in about 4.5 min, log 20261012-035643);
  - stage 3 s, tar 2.3 s, NSIS 13 s, app + DMG 75 s.
- **Size** (`du`):
  - `build-pkg-macos` 373 MB and `build-pkg-win` 409 MB;
  - `src/recomp/gen` 138 MB, `analysis/` 1.0 GB, `.venv` 216 MB;
  - `game_files` 3.1 GB.
- **The steamos bundle** is 3.53 GB: game files 3341 MB and the program
  193 MB (`cat_recomp.exe` 189.9 MB, `.pdb` 2.6 MB, the rest under 0.1 MB
  each). `--hud-pack` adds 158.8 MB.
- **The other bundles:** the DMG is 2.93 GB, and `setup.exe` is 67.5 MB
  plus game files.

Burnout 3. The Deck holds `~/Games/Burnout3Takedown` in the versions/
layout, current = `20261012.1309-c56574b4-te5d407e-g7e7298dd-dirty90bdf81c`,
installed from a CLI bundle, not the wizard. The same bundle is on this
Mac as `b3/dist/Burnout3Takedown-<that version>-steamos.tar`. Its manifest:

- schema 1, data_layout 1, 726 files;
- 715 of them game files (2418 MB);
- program 21 MB (`burnout3.exe` 18.7 MB, `.pdb` 2.1 MB).

Its `install_lib.py` predates the Proton pin.

SSX 3 and Spartan:

- `ssx3/recomp` is git (3d75004, no remote). Its `[package]` (app `Ssx3`)
  and `[wizard]` are commented out. There is no `packaging/` and no
  LICENSE, and `stock_cmake = []` (no enhancements layer).
- `spartan/tca` is not a git repo. Its `[package]` (app
  `SpartanTotalWarrior`) is commented out, and it has no `[wizard]`, no
  `packaging/`, no LICENSE and no enhancements layer.

## Goals / Non-Goals

**Goals:**

- A second wizard run for a new release redoes only the stages whose
  inputs changed, in the same build folder.
- The player gets a patch when it is smaller and a base it fits is
  installed, else the full installer. The patch result is byte-identical
  to a full install of the same version.
- Applying a patch is atomic and can be rolled back on every target.
- Incremental and clean builds give the same files, and a test proves it.
- Developers can build an unpublished game with the same wizard, hidden
  from players.

**Non-Goals:**

- Binary deltas, a shared content-addressed cache, patch hosting or
  download.
- Patching across a `data_layout` change, or across platforms.
- Making the analysis stages (funcid, recomp) themselves incremental
  inside a stage. They stay all-or-nothing, keyed as a whole.
- CPU backend, goldens, Proton test cycles beyond the acceptance phase.

## Decisions

### D1. Per-stage stamps in one state file, not a content-addressed store

The state lives in the clone's git directory, `$(git rev-parse
--git-dir)/xbr/` (normally `<build folder>/src/.git/xbr/`):

- `build-state.json`, the stage records, written atomically with
  `_write_json` after each stage;
- `game-files.json`, the game files' cached sha256s (D2 import);
- `bundles/<target>/<manifest sha256>.json`, one per bundle made (D5).

Why the git directory and not a `.xbr/` folder in the tree: `package/lib.py`
`tree_state` runs `git status --porcelain`, which counts untracked files.
A state folder in the tree would make the second run's clone look dirty,
so the clean-clone check of D4 would refuse it, the version would gain a
`-dirty` suffix, and the compile key's dirty hash would change on every
run. Nothing under `.git/` is ever reported by `git status`, and a git
worktree gets its own git directory, so each worktree has its own state.
A game folder that is not a git checkout (only a developer's `--game` on
an untracked tree) uses `<game>/.xbr/`; there is no git status to dirty.

```json
{"schema": 1,
 "stages": {
   "import":   {"key": "<sha256>", "inputs": {"marker": "...", "listing": "..."}, "outputs": {}},
   "generate": {"key": "...", "outputs": {"src/recomp/gen/": {"tree": "<sha256 of listing>"}}},
   "compile:windows": {"key": "...", "inputs": {"generate": "...", "toolchain": "...", "...": "..."},
                       "outputs": {"build-pkg-win/cat_recomp.exe": {"sha256": "...", "size": 0, "mtime_ns": 0}}},
   "compile:macos": {}, "icon": {}, "hud": {},
   "stage:steamos": {}, "wrap:steamos": {}}}
```

Each stage stores its own input digests next to the key, so a stale
stage names its reason the way `gen_stale_reasons` does ("toolkit moved",
"render scale 2 -> 3").

The stage commands the wizard runs on their own (`import`, `enhance hud`;
`wizard/internal/model/model.go` calls them before `package`) use the
same module and write their own entries, so a stage is recorded the same
way whichever command ran it.

Why a stamp file and not a content-addressed store:

- The pipeline already has one stamp (the gen key) and its tests. Seven
  more of the same shape cost a few hundred lines, while a store needs
  its own garbage collection, locking and layout.
- The heavy outputs already live in place and are already incremental
  inside their tools (ninja, `write_if_changed`). A store would copy
  them a second time: 0.5 GB more per target, plus 3.3 GB of game files
  unless hard-linked.
- One folder belongs to one game and one player, so cross-folder
  sharing, the store's main gain, has no user.

### D2. Stage keys and how they chain

A key is `sha256` over a canonical JSON of its input digests. Every
upstream stage's key is one of the inputs, so a change anywhere
invalidates everything below it and nothing beside it. The edges are
kept as narrow as the inputs allow. In particular, generate does not
depend on setup: setup covers the CLI and toolkit pins and `uv.lock`, so
that edge would rerun the 13-minute analysis on every pin bump, which is
what the gen key's own field-by-field record exists to avoid.

| Stage | Inputs (besides upstream keys) | Upstream |
|---|---|---|
| import | the dump marker (`.xbr-dump.json`: source path digest, size, mtime) and a listing of `game_files/` (path, size, `mtime_ns`); sha256s only on doubt (below) | - |
| generate | today's gen key record (`GEN_KEY_VERSION` 2), unchanged: it already holds the XBE sha256, `toolkit_state()`, the config inputs and the argv | import |
| compile:windows | see below | generate, icon |
| compile:macos | see below | generate, icon |
| icon | XBE sha256, CLI tree | import |
| hud | each selected archive's sha256, the `[enhance.hud]` table, the font file's sha256, the CLI tree, the scale | import |
| stage:`<t>` | the option set (render scale, fullscreen, ...), the seed config, the `packaging/` tree, LICENSE/NOTICE sha, the CLI tree | compile for its build folder, icon, hud when on, import |
| wrap:`<t>` | the sha256 of the staged `manifest.json`, the kind (full or patch), the base manifest sha256 for a patch, the NSIS/hdiutil versions | stage:`<t>` |

**Compile keys follow the build folder, not the target.**
`build-pkg-win/` serves both windows and steamos, so there is one
`compile:windows` key used by both, and `compile:macos` for
`build-pkg-macos/`. The compile inputs:

- **The game:** its tree id (`git rev-parse HEAD^{tree}`) plus a hash of
  its full dirty diff, untracked files included.
- **The whole toolkit:** `HEAD^{tree}` of the toolkit checkout (or of an
  `XBOXRECOMP_DIR` dev tree) plus a hash of its full dirty diff, untracked
  files included. `toolkit_state()` hashes only `tools/` and
  `templates/runtime/`, on purpose, because that is all generate reads.
  The runtime the exe links lives in `src/`, `include/`, `cmake/` and
  `CMakeLists.txt`, so `toolkit_state()` stays the generate input only.
- **The toolchain digest,** taken directly rather than through the setup
  stage: the llvm-mingw tag and sha256 (after the `LLVM_MINGW_TAG`
  override in `fetch.py`), the sha256 of `cmake/llvm-mingw-x86_64.cmake`,
  and the cmake and ninja versions from `.venv`. For macos, also
  `clang --version`, the SDK version (`xcrun --show-sdk-version`), and
  the brew formula versions and sha256s of the dylibs that get bundled.
- **The build environment:** the variables `host.build_env` passes (`CC`,
  `CXX`, `CFLAGS`, `LDFLAGS`, `DEVELOPER_DIR`, `MACOSX_DEPLOYMENT_TARGET`),
  by value.
- **The CMake options:** the build type, `build.stock_cmake`, any
  `--allow-nonstock` values and `--allow-debug`, as the full `-D` list
  passed to CMake.
- **The icon key,** because the windows `.ico` is embedded through
  `-D<icon_var>`.

**The import key needs no hashing of 3.3 GB per run.** The import has no
manifest of its own, and `.xbr-dump.json` holds only the source's path,
size and mtime. The key is that marker plus the listing (path, size,
`mtime_ns`) of `game_files/`. `game-files.json` caches each file's
sha256 against its (size, `mtime_ns`). A file is rehashed only when those
differ or on `--verify`. `write_manifest` reads the cache, so each wrap
no longer rehashes the game files either.

Keys use git tree ids, not commit ids, so a rebase that does not change
the files keeps the build. The manifest records commits, though, and
names the source. `write_manifest` therefore always reruns (seconds,
with the cached sha256s), so a rebuilt bundle never carries the
provenance of an older commit. The wrap key holds the staged
`manifest.json`'s sha256 for the same reason: after a rebase with equal
trees, every stage up to stage is reused, but the new manifest (new
commits, new version) makes the wrap rerun, so the bundle always carries
the manifest just written. Paths inside inputs use the `$ROOT`/`$TK`
placeholders the gen key already uses, so moving the folder keeps the
keys.

### D3. When a stage runs

A stage is skipped only when all of these hold:

1. Its stored key equals the new key.
2. Every recorded output exists with the recorded size and `mtime_ns`.
3. On doubt (a size or mtime mismatch, or `--verify`), the sha256 matches.

Otherwise it runs, and every stage below it then runs. A stage starts by
deleting its own entry (as `begin_stage` does for the gen key), so a crash
mid-stage leaves no key and the next run redoes the stage. The existing
regen marker stays for `recomp`.

Failure cases:

- **Missing or unreadable state file:** every stage runs once. The tools'
  own incrementality (ninja, `write_if_changed`, the import's "same")
  still saves the work, so a lost state file costs minutes, not a clean
  build.
- **A deleted output** (the player removed `build-pkg-win/`, or `dist/`):
  that stage fails check 2 and reruns.
- **A changed output** (an edit in `src/recomp/gen/`): the generate stage
  records a listing digest of `gen/`. A mismatch reruns generate, which
  is also what `refuse_stale_gen` protects today.
- **A toolchain pin change:** the compile key changes. The stage then
  calls `start_afresh` (drop CMakeCache/CMakeFiles) before building, so
  no object made by the old compiler is linked with the new one.
- **Forced full rebuild:** `xbr package --clean` deletes the state file,
  `build-pkg-<target>/`, `dist/.stage-*` and the icon cache, then runs
  everything. It keeps the import, setup's downloads and the analysis
  cache only when their own pins match (those caches are pinned
  already). It also keeps `src/recomp/gen/` and its gen key, which live
  beside gen/ and not in the state file, so generate is decided by
  `gen_stale_reasons()` exactly as today: a matching gen key reuses gen/,
  and the 13-minute analysis does not rerun. `--clean=all` also drops
  `src/recomp/gen` and `analysis/`, so everything after import reruns,
  the analysis included.
  - The wizard's "Rebuild everything" checkbox passes `--clean`, not
    `--clean=all`: it rebuilds the program and the bundles (minutes), and
    the analysis reruns only when its own key says so. `--clean=all` is a
    CLI option for developers and is not in the wizard.

### D4. The wizard updates the build folder in place

`repo.Ensure(root, url, ref, commit)` replaces `repo.Clone`. When a clone
is reused, it writes a mark at `.git/xbr/wizard.json`: `{"origin": "repo"
| "local", "ref", "commit"}`. The mark lives in the git directory, like
D1's state, so it never dirties the tree.

- **No folder:** clone as today, and write the mark.
- **A clean clone at another commit** (`git status --porcelain` empty,
  and marked): fetch the ref; in player mode, check the fetched commit
  against the release's lock commit (local mode has no lock); then `git checkout --detach <commit>` and
  rewrite the mark. Setup then moves the toolkit and CLI pins, as
  `toolkit.checkout_pin` already does.
  - In player mode the ref is `tag <tag>`: `git fetch --depth 1 origin
    tag <tag>`.
  - In local mode (D14) it is the `REF` given: `git fetch origin <REF>`.
- **A legacy clone** (one made before this change). Today's `repo.go`
  writes no mark, so "no mark" alone cannot mean "not ours". A clone is
  accepted as the wizard's when all of these hold:
  - it is clean;
  - `origin` equals `[wizard] repo`;
  - it is shallow (`git rev-parse --is-shallow-repository`);
  - its HEAD is a tag's commit.
  The mark is then written, and it is updated as above.
- **A clone with local changes, or one that is neither marked nor
  legacy:** refused, as today, naming the folder. Developer edits are
  never thrown away.
- **Switching modes:**
  - A local-mode run sets `origin` to the source's `file://` URL.
  - The next player-mode run on a marked clone with `origin: local` sets
    `origin` back to `[wizard] repo` before fetching, and rewrites the
    mark.
- **A newer clone than the wizard's release** (a downgrade): allowed, the
  same way. The keys make the old outputs stale where they differ.

Why fetch and not reclone: the clone is small, but the folder around it
(`analysis/`, `build-pkg-*`, `.venv`, game files) is 5 GB and is the
point of keeping it.

### D5. Full or patch: the base manifest

A patch needs a base: the `manifest.json` of the version the target has
**current**. Where it comes from, in order:

1. **`--patch-from FILE|DIR|TAR`.** A `manifest.json`, an installed
   version folder, or a bundle tar (the manifest is read from the tar
   without extracting). This is the developer route, and how the
   acceptance test uses B3's existing Deck install. `xbr package` takes
   it, and the wizard passes it through from a hidden dev flag of the
   same name (D14's rules: flag only, banner shown).
2. **The installed copy on this host,** when the target is the host's
   own platform:
   - steamos: `<data root>/versions/<current>/manifest.json`, `<data
     root>` from `[data]`;
   - macos: `/Applications/<App>.app/Contents/Resources/manifest.json`,
     else `~/Applications/...`;
   - windows: the `InstallLocation` from the uninstall key, then
     `versions\<current.txt>\manifest.json` (D8). An old in-place install
     (a `manifest.json` at the root and no `current.txt`) is not a base:
     `apply.exe` works only on the versioned layout, so that player gets
     the full installer, which migrates (D8).
3. **The bundles this folder made.** Each wrap records a copy of the
   manifest (about 100 KB) as `.git/xbr/bundles/<target>/<manifest
   sha256>.json`. The records are keyed by content, not version, since
   two builds of one commit with different options share a version
   unless D12's options digest differs. This covers the player who builds
   on the Mac for the Deck.
   - The CLI lists them, newest first, in `package --plan --json`
     (`bases: [{version, made, sha256, size of the patch}]`).
   - The wizard only shows that list; it never reads the records
     itself. It asks which one the Deck has and defaults to the newest.

A base is usable when:

- its `app` and `target` match;
- its `data_layout` equals the new one;
- every file the patch keeps is listed in it with a sha256;
- windows only: it comes from the versioned layout (`current.txt`
  exists) and its `stub_abi` equals the new one (D8).

`schema 1` manifests (B3's current install, every bundle made before
this change) qualify, because they already list every file with its
sha256.

The patch is chosen by default when a usable base exists and the patch is
under half the full bundle's size. Otherwise the full installer is made,
and the wizard says why ("no install found", "game data layout changed").
The player can always pick the full installer.

### D6. What a patch holds

A patch is computed from the new staged payload (the full tree,
`dist/.stage-<target>/`, always built) against the base:

- **changed:** paths in both with a different sha256;
- **new:** paths only in the new tree;
- **deleted:** paths only in the base;
- **kept:** the rest. It is listed in `patch.json` with each file's size
  and sha256, but not shipped.

The patch carries:

- the changed and new files;
- the full new `manifest.json` and `SHA256SUMS`;
- `patch.json`: `{"schema": 1, "base_version", "base_manifest_sha256",
  "version", "changed": [...], "new": [...], "deleted": [...], "kept":
  [...]}`;
- the target's applier (D7 to D9). It is always the new applier, so a
  base installed by an older `install.sh` (B3's) is patched by the new
  code.

Whole-file copies, not binary deltas:

- The program is one 190 MB exe (19 MB for B3) that changes throughout
  on any code change: the gen files move code addresses, so a delta
  would be large and need bsdiff-class memory (several times the file
  size) on the Deck.
- The saving over a whole exe is about 100 MB at most, while the
  saving over the full bundle is already about 3.3 GB.
- A delta format adds a decoder per platform: C on Windows, Python on
  the Deck, sh on the Mac.

This can be revisited if game-file patches become common (D10).

Names:

- `<App>-<version>-<target>-patch-from-<base version short>.tar` on
  steamos;
- `...-patch-from-<short>/` (folder with `apply.exe`) on windows;
- `...-patch-from-<short>.dmg` on macos.

`<base version short>` is the base version's `c<game7>-g<gen8>` part.

**The base check is the same on every target.**

- The applier reads the installed version that is **current** (steamos
  `current`, windows `current.txt`, macos the app at its path).
- It refuses unless that version equals `base_version` and the sha256 of
  its `manifest.json` equals `base_manifest_sha256`.
- An older version that is merely still kept under `versions/` is not a
  base. Patching a non-current version would make the switch also roll
  the program back or forward past what the player has.

**Game files in a patch.** On every target, game files are applied by a
patch-aware sync, never by the full install's sync.
`install_lib.sync_game_files` builds its `want` set from the files
present in the bundle and deletes everything else, so on a patch, which
holds only the changed files, it would delete every kept game file. The
patch-aware sync:

1. Takes `want` from the new manifest's game-file entries.
2. Before changing anything, verifies each kept game file under the
   install's `game_files/` by size, then sha256. Any mismatch refuses
   the whole apply (D10), and nothing is changed.
3. Writes the new and changed game files to `<name>.partial` beside the
   target, flushes them, then renames over.
4. Deletes only the paths in `deleted`.
5. Never touches a game file that is not in `want` and not in `deleted`.
   Such a file is reported, not removed.

### D7. SteamOS: `install.sh patch`

The patch tar holds `install.sh`, `install_lib.py`, `patch.json`, the new
manifest and SHA256SUMS, and the changed and new files. `./install.sh`
detects `patch.json`, or the player runs `install.sh patch`.

`cmd_patch` is `cmd_install` with two steps swapped, so a patched install
ends in exactly the state a full install would leave. B3's base predates
the Proton pin, so a patch that skipped `ensure_proton` would install
and then fail to launch.

The steps, in `cmd_install`'s own order (`install_lib.py` `cmd_install`
at CLI 06b9bc4):

1. **The same pre-steps as `cmd_install`:** `check_host`,
   `check_not_dev_tree`, `check_ours`, `check_layout`, and the free-space
   check (sized for the patch's new files plus the game files it writes,
   not the bundle).
2. **New for both paths: the launch lock.** `cmd_install` takes no lock
   today; `launch.lock` is only held by the launcher while the game runs.
   Both `install` and `patch` now take it non-blocking for their whole
   run and refuse while the game holds it.
3. **The base check** (D6): `current` resolves to
   `versions/<base_version>`, and the sha256 of its `manifest.json` equals
   `base_manifest_sha256`. Then every kept program file under
   `versions/<base>` and every kept game file is checked against the base
   manifest (size, then sha256). If any fails, see D10.
4. **The bundle verify and the runtime steps, as `cmd_install` runs
   them:** the patch's own files against its SHA256SUMS, then
   `ensure_umu`, `ensure_proton` (already in `cmd_install`), `state/layout`,
   `record_umu`, `mark_runtime_update`, the `config/` folder and
   `seed_config`. These run before the program step in `cmd_install`, and
   stay there.
5. **Program step** (replaces `install_program`):
   - If `versions/<new>` already exists and is complete against the new
     SHA256SUMS (the check `install_program` already makes), it is
     reused. This is the rerun after a crash between the rename and the
     switch.
   - Otherwise build `versions/<new>.partial`: hard-link the kept files
     from `versions/<base>`, copy the changed and new files from the tar,
     write the manifest and SHA256SUMS, verify the whole tree, `fsync`
     every written file and then `.partial` itself. Rename it to
     `versions/<new>` and `fsync` `versions/`.
   - A patch never takes the reinstall path (rename the old
     `versions/<new>` to `.old`, then `.partial` over it): `<new>` is
     never current during a patch, so a stale incomplete `versions/<new>`
     is removed before `.partial` is renamed.
6. **Game-file step** (replaces `sync_game_files`): the patch-aware sync
   of D6, with an `fsync` of each written file and of its directory.
7. **The switch and the post-steps, as `cmd_install`:**
   - `switch`: write the new symlink, `fsync` the root, `os.replace` it
     over `current`, then `fsync` the root again; append to
     `state/history` and `fsync` it;
   - then `write_stable_launcher`, `write_desktop`, `prune` to `--keep`
     (default 3, never `current` or the previous version),
     `import_saves` when `--saves-from`, and `add_to_steam` when
     `--steam`.

`install_lib` has no `fsync` today. The same `fsync` calls go into
`install_program` and `switch` for full installs, so both paths are
power-loss safe. The full install's reinstall path (the current version
reinstalled: `final` to `.old`, `.partial` to `final`) leaves `current`
dangling between the two renames. It is replaced by
`renameat2(RENAME_EXCHANGE)` of `.partial` and `final` (Linux 3.15+,
through `ctypes` on `libc`; SteamOS's kernel and filesystems have it),
then the removal of `.partial`, which now holds the old tree. Where the
call fails with `EINVAL` (a filesystem without it), the two renames stay,
with an `fsync` of `versions/` after each, and the next run repairs a
missing `versions/<current>` by finishing the rename from `.old`.

Rollback is unchanged (`install.sh rollback` switches to the previous
entry in `state/history`). Power loss or a crash at any step:

- before step 7's `os.replace`, `current` still names the base. The
  next run deletes any `.partial` and reuses a complete `versions/<new>`
  (step 5);
- after it, the new version is complete on disk.

The only window is in step 6: a changed game file is replaced while
`current` is still the base. D10's warning covers it, and rerunning the
patch completes it: step 3 still passes for the program (current is
still the base), the kept files were not touched, and
step 6 is idempotent (a changed or new game file already at its new
sha256 is skipped).

### D8. Windows: a versioned layout, and an `apply.exe` helper

The in-place NSIS install has no rollback, and swapping a running
install's files in place is not atomic. The layout moves to the
SteamOS shape:

```
%LOCALAPPDATA%\Programs\<App>\
  current.txt            # one line: the version folder name
  versions\<v>\...       # program files, the per-version launcher, manifest.json, SHA256SUMS
  game_files\            # unversioned, as today
  <App>.exe              # the root stub: reads current.txt, runs versions\<v>\<App>.exe
  apply.exe              # the applier: patch, rollback, migrate, switch
  state\history.txt      # one line per switch, as state/history on steamos
  uninstall.exe
```

- **The root stub is stable.** It only reads `current.txt` and starts
  `versions\<v>\<App>.exe` with the same arguments; everything that can
  change between versions is in the per-version launcher (`launcher.c`
  today): the environment, `RECOMP_GAME_FILES`, and the backend.
  - The stub carries a contract number, `stub_abi = 1`.
  - The root tools (the stub and `apply.exe`) are not in `files[]`,
    which lists only what lands under `versions\<v>\` and `game_files\`.
    The manifest records them apart, as `"root": {"stub_abi", "stub":
    {"sha256", "size"}, "apply": {"sha256", "size"}}`, so "Patch equals
    full" compares the versioned trees and is not broken by a rebuilt
    stub.
  - A patch never replaces the stub, and is made only when its
    `stub_abi` equals the base's (D5). A new `stub_abi` means a full
    installer. So the stub always stays compatible with every kept
    version.
- **The rollback tools are installed, not left in the patch folder.**
  The full installer writes `apply.exe` and `state\history.txt` at the
  root, and every patch replaces the root `apply.exe` with its own (the
  patch runs its copy from the patch folder, so the root one is not in
  use) by a flushed `.tmp` and `MoveFileExW`, after the switch. So
  `apply.exe rollback` works after the player deletes the patch folder
  (D11).
- **The per-version launcher** points `RECOMP_GAME_FILES` at the root
  `game_files\` (`..\..\game_files` from its own folder, resolved to an
  absolute path), not at a folder inside the version.
- **The switch:** `current.txt` is replaced by `MoveFileExW(tmp,
  current.txt, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)`,
  which is atomic on NTFS.
- **Kept files** are hard-linked (`CreateHardLinkW`) from the base
  version.
- **Power loss:** every copied file, and `current.txt.tmp`, gets
  `FlushFileBuffers` before `current.txt` changes. A power loss before
  the move leaves the base current; after it, the new version is
  complete.
- **A running game** is detected by a named mutex,
  `Local\<App>-running`, which the per-version launcher holds while the
  game runs. `apply.exe` and the NSIS installer refuse while it exists.
- **The full NSIS installer** writes the same layout. NSIS cannot
  hard-link, flush or call `MoveFileExW` with `MOVEFILE_WRITE_THROUGH`
  without the System plugin, so the installer embeds `apply.exe`,
  extracts it to the root first, and calls `apply.exe migrate` and
  `apply.exe switch <v>` for every link, flush and `current.txt` change.
  NSIS itself only extracts files into `versions\<v>.partial\` and
  copies `game_files\`.
- **The uninstaller** removes `versions\`, `current.txt`, the stub,
  `apply.exe`, `state\`, `game_files\` and its own registry key. It
  removes a `game_files` junction inside a version (below) with
  `RemoveDirectory` on the junction itself, never by a recursive delete
  through it, and so does `apply.exe` when it prunes. As before, it never
  touches the data folder.
- **The one-time migration** (`apply.exe migrate`) runs in the full
  installer over an old in-place install. The old launcher (`launcher.c`
  today) needs `<exe dir>\game_files\default.xbe` and sets
  `RECOMP_GAME_FILES` to that folder, so the migrated version needs a
  `game_files` beside its exe. Its order is safe at every step:
  1. hard-link (or copy, if links fail) the old program files into
     `versions\<old DisplayVersion>\`, verified against the old
     `manifest.json` (its game-file entries are verified at the root
     `game_files\`);
  2. create the junction `versions\<old>\game_files` pointing at
     `<root>\game_files` (a directory junction needs no elevation, unlike
     a symbolic link);
  3. write `current.txt` naming it, flushed;
  4. replace the root `<App>.exe` with the stub;
  5. delete the old top-level program files.
  A crash before step 4 leaves the old launcher working, since its files
  are still in place; after step 4, the stub runs the migrated version
  through its junction. Rerunning the installer resumes from whichever
  step is missing. Versions made by the new installer need no junction:
  their launcher reads the root `game_files\` directly.
- **`apply.exe`** is small C, built with llvm-mingw like the launcher,
  with `-Wl,--no-insert-timestamp` (the mingw driver's flag; `/Brepro`
  is lld-link's and is not accepted by `x86_64-w64-mingw32-clang`), using
  BCrypt for SHA-256 because NSIS has no sha256.
  - `apply.exe [patch]` runs D7's steps 2 to 7 with Windows calls: the
    mutex for the lock, the patch's own SHA256SUMS verify without the
    umu and Proton steps, the base check against `current.txt`, the patch-aware
    game-file sync of D6, then `DisplayVersion` updated after the switch,
    then pruning to `--keep` (default 3). A complete `versions\<new>` from
    an interrupted run is reused, as on steamos.
  - `apply.exe rollback` rewrites `current.txt` to the previous entry in
    `state\history.txt`.
  - `apply.exe migrate` and `apply.exe switch <v>` serve the installer.
  - The patch folder holds `apply.exe`, `patch.json`, the manifest,
    SHA256SUMS and the files. NSIS is not used for patches.

The alternative, a journalled in-place swap (rename each changed file to
`.old`, copy the new one, delete `.old` at the end, replay the journal on
the next start), keeps the current layout but makes a crash mid-swap a
half-old install until the next start, and has no rollback after the end.
It was rejected for that reason. The user chose the versioned layout,
the one-time migration and the `apply.exe` helper (2026-10-17).

### D9. macOS: clone, overlay, swap

The patch is a DMG with `apply.command` (sh), a small helper `xbr-swap`
(C, built and signed ad hoc with the bundle), and the patch payload,
paths relative to `<App>.app/Contents/`. The steps:

1. Find the installed app (D5.2). Check the base as in D6: its version
   and the sha256 of `Contents/Resources/manifest.json`. Refuse while the
   game runs (`pgrep -f` on the app's executable path).
2. Run the game-file part of D6's check: verify the kept game files
   inside `Contents/Resources/game_files/` by size, then sha256.
3. `cp -c -R <App>.app <dir>/.<App>.app.partial` (an APFS clone: no data
   copied).
4. Overlay the changed and new files and delete the deleted ones. The new
   `_CodeSignature/` and the re-signed Mach-Os are among the changed
   files, since the build signs before staging. Game files sit inside
   the app here, so the overlay is also their patch-aware sync.
5. Verify with `shasum -a 256 -c` against the new SHA256SUMS, and run
   `codesign --verify --deep --strict`.
6. `xbr-swap` flushes the `.partial` tree (`fcntl(F_FULLFSYNC)` on each
   file and on the directory), then exchanges `.partial` and `<App>.app`
   in one call, `renamex_np(RENAME_SWAP)`. There is never a moment with
   no app at the path, which two renames would leave.
7. The old app, now at `.<App>.app.partial`, is renamed to
   `<dir>/.<App>.previous.app`, beside the installed app, replacing the
   one there. `apply.command` and `xbr-swap` are copied to
   `<dir>/.<App>.previous.tools/`, so rollback works after the patch DMG
   is ejected or deleted.
   - Everything stays in `<dir>` (`/Applications` or `~/Applications`):
     the same volume, so `RENAME_SWAP` and the rename always work and
     there is no cross-volume copy. The data folder
     (`~/Library/Application Support/<App>/`) is never written, as the
     deployment spec's "Replace the app (macOS)" requires.
   - The steps are journalled in `<dir>/.<App>.apply.json`, so rerunning
     `apply.command` after a crash finishes them.
   - The dot names keep the previous app out of Finder and Launchpad.

`apply.command rollback` (from the DMG or the copy beside the previous
app) swaps `.<App>.previous.app` and `<App>.app` back the same way. One
previous app is kept (the user, 2026-10-17): macOS has no `current` link
to point at, and an APFS clone of the previous app costs only its changed
blocks. The wizard's "Install now" button runs the script on the host.
Since the patch is unsigned like the DMG today, Gatekeeper's first-launch
prompt is the same as for a full install.

**`xbr-swap`.** About 100 lines of C, built by the CLI's macOS package
step with the Command Line Tools' `clang` (`DEVELOPER_DIR` as the build
uses), as a universal binary (`-arch arm64 -arch x86_64`) with
`-mmacosx-version-min` equal to the game's deployment target, and signed
ad hoc. Its source sits in `templates/macos/`, so its sha256 is a wrap
input. It lives outside the app (in the DMG, then beside the previous
app), so it is outside D12's equality check of the app.

**Refusals at the swap (TCC and permissions).** On macOS 13 and later,
replacing a bundle in `/Applications` may need the App Management
permission for the Terminal or the wizard; step 6 then fails with
`EPERM`. A non-admin user who cannot write `/Applications` gets `EACCES`,
earlier, at step 3 (creating `.partial` in `<dir>`). In both cases the
applier:

- stops before changing the app (the swap is the first write to the
  app's path; a `.partial` made at step 3 is removed);
- says why: how to grant App Management (System Settings > Privacy &
  Security > App Management), or that `/Applications` is not writable
  by this user;
- offers to install into `~/Applications` instead.

Task 4.4 tests both cases.

### D10. Base mismatch and what a patch may change

- **No usable base, or the hash is wrong:** the applier refuses before it
  touches anything:

  > This update is for <base version>; this install is <found version>.
  > Use the full installer for <version>.

  It exits non-zero, and the wizard offers to make the full installer.
  It never patches a near match.
- **A kept file that does not match the base manifest** (program or game
  file) is the same refusal, naming the file.
- **A patch may change program files freely.**
- **A patch may change game files when `data_layout` is equal** (the
  user, 2026-10-17).
  - On steamos and Windows, game files are unversioned (one
    `game_files/` at the root) and are kept that way: versioning 2.4 to
    3.3 GB per version is what the keep-3 rule exists to avoid. So the
    wizard and the applier warn before applying ("this update also
    changes game data; rolling back will not undo that").
  - On macOS the game files live inside the app, so the previous app
    holds the old ones (as APFS clones, sharing unchanged blocks) and
    rollback restores them. No warning is shown there.
- **A different `data_layout` means a full installer.**

### D11. Disk use and cleanup

The kept folder for BLiNX 2 holds:

- `src/` with `analysis/` (1.0 GB) and `gen/` (0.14 GB);
- `.venv` (0.2 GB);
- `build-pkg-<t>` (0.4 GB per build folder);
- game files (3.1 GB);
- `dist/`, which grows by one bundle per run (3.5 GB each).

Rules:

- **The staging tree is reused,** not recreated per version. It stays at
  `dist/.stage-<target>/` and is updated in place by the stage step: copy
  only the files whose sha256 changed, and game files by clonefile where
  the filesystem has it, hard links where it does not.
  - The wrap reads from it and writes the versioned bundle beside it
    (the tar, the DMG, or the windows folder by clonefile or hard
    links).
  - It is never renamed, so the next run finds it.
  - This is also what keeps the stage step at seconds.
- **Bundles:** the CLI keeps the newest 2 bundles per target in `dist/`,
  and the manifest records of all of them (`.git/xbr/bundles/`, small).
  Older bundles are deleted after a successful wrap. `--keep-bundles N`
  changes it. The wizard only shows the result.
- **Patches** are not kept after the player installs them (the wizard
  asks). Deleting one never costs the rollback: the tools it needs are
  installed (D8 on Windows, D9 on macOS; steamos copies `install.sh` into
  every version already).
- **`xbr clean [--bundles|--build|--all]`** prints what it would free and
  deletes on `--yes`. The wizard's settings show "Build folder: 9.8 GB,
  [Free space]", which runs `clean --bundles --build` (keeping the import
  and analysis, the costly parts).
  - `xbr clean --all` never deletes `.git/xbr/wizard.json`, the mark of
    D4: without it the next wizard run would fall back to the legacy-clone
    check, and refuse a clone that is no longer at a tag commit. It
    removes the rest of `.git/xbr/` (state, game-file cache, bundle
    records).

Without bundles, the folder is about 5.5 GB for one build folder and 6 GB
for two.

### D12. Reproducible output

An incremental build is only trustworthy if it equals a clean one. Today
it cannot, for three reasons:

- the PE and pdb carry link timestamps and GUIDs (lld writes them unless
  told not to);
- macOS binaries carry an LC_UUID from the build, and debug paths carry
  the build folder;
- the manifest's `built` is now(), and the version is the exe mtime.

The fixes:

- **Windows (lld through the mingw driver, `x86_64-w64-mingw32-clang`):**
  - `-Wl,--no-insert-timestamp` (a zero timestamp; lld then derives the
    PDB GUID from the content). `/Brepro` is the lld-link spelling of the
    same thing and is used only if a target links with `lld-link`
    directly;
  - `-ffile-prefix-map` for each root that can appear in debug and
    `__FILE__` paths: the game (`<root>=.`), the toolkit (`$TK=tk`), the
    llvm-mingw root and the `.venv`.
  - All are set in the toolkit's runtime CMake, for all games.
  - The ctest of task 3.1 also checks that the PDB GUID is stable across
    two links under `--no-insert-timestamp`, since lld derives it from
    the content only when told to.
- **macOS:** the same prefix maps, `ZERO_AR_DATE=1` for archives, and
  ld64 computes LC_UUID from the content when no timestamp input differs.
  Verify it, and add `-Wl,-reproducible` when the linker has it.
- **Manifest:**
  - `built` and the version's time part come from `SOURCE_DATE_EPOCH`
    when set, else the newest commit time of the game and the toolkit,
    not now().
  - The manifest gains `"volatile": [...]`, naming the top-level fields
    that may differ between two builds of the same inputs: `built`, and
    `sources.*.branch`.
  - Equality is defined over `files[]` (path, sha256, size) only. The
    `volatile` list documents what else may differ, and every other
    top-level field must be equal.
- **Version uniqueness:** with the time part fixed, two builds of one
  commit with different options (render scale, HUD pack) would share a
  version, and so collide in `versions/<v>` and in the bundle records.
  - The version gains `-o<6 hex>`, a digest of the option set, the HUD
    pack's sha256 and the full CMake `-D` list (the build type,
    `--allow-nonstock` values, `--allow-debug`), whenever any of these
    differs from stock.
  - A stock build keeps today's format.
  - The bundle records are keyed by manifest sha256 anyway (D5).
- **The tar and DMG:** the tar is already deterministic. The DMG
  (`hdiutil` UDZO) is not, so equality is checked on the staged tree and
  on the app inside the DMG, not on the DMG's own bytes.

The equality test (task 7.3) builds a game fixture twice in two
temporary folders: clean, and incremental from the previous commit
followed by one code change. It compares the staged trees' manifests
`files[]` as equal, and the remaining top-level fields as equal outside
`volatile`.

- It is the game-bundle analogue of the wizard binary's double build
  with equal sha256s, which `xbr wizard check` runs after `wizard/check.sh`
  and which is unaffected.
- It runs in the CLI's pytest on a small fixture game, once on BLiNX 2
  by hand (task 7.3), and on Burnout 3 in the acceptance run (task 9.5).

Ad hoc signing on macOS is deterministic for identical input, so an equal
Mach-O gives an equal signature.

### D13. Wizard UX

- **The start screen** detects the build folder from the settings file's
  `root`. When `src/` holds a clean clone, it says "Build folder found:
  BLiNX 2 20261012 (c1a2b3c). This release will reuse it." In local
  source mode it names the source's commit instead.
- **The options screen** is unchanged. A changed option is fine: its
  stages rerun.
- **The output choice** shows one line per target, preselected: "Update
  (190 MB) for the installed 20261012" or "Full installer (3.5 GB):
  no install found". The other is reachable through "Change...". Also
  there: "Rebuild everything" (off), and for a cross-target patch, "The
  Deck has: [newest bundle made here v]". The picker's entries are the
  `bases` list from the CLI's `package --plan --json` (D5.3); the wizard
  never reads the bundle records itself.
- **The plan** lists stages as "reuse" or "run (toolkit moved)", from the
  CLI's `package --plan --json`, with estimates from the folder's own
  `build-logs/timings.json`.
- **The end screen** says what was made, where, and how to apply it: "Copy
  the folder to the Deck and run `./install.sh`" (the same command for a
  patch), "Double-click apply.exe", "Open the DMG and run Apply". On the
  host's own target it also shows an "Install now" button.

Players never see keys, manifests or the word "base".

### D14. Local source mode (developers only)

`xbr-wizard --source PATH[#REF]`:

- **`PATH`** is a git checkout or a `.bundle` file (`git bundle create`).
- **`REF`** defaults to `HEAD` for a checkout, and for a bundle to the
  bundle's only head, else it must be given.

The wizard clones from it into `<root>/src` with `git clone --no-local`
(a checkout) or `git clone <bundle>` (a bundle). Then it:

- sets `origin` to a `file://` URL in the clone only, so D4's fetch of
  `REF` works on later runs from the same source (a player-mode run
  resets it, D4);
- writes the mark with `"origin": "local"` and the ref;
- warns when the source checkout has uncommitted changes: only commits
  are built, so "uncommitted changes in PATH are not built" is printed and
  shown on the banner;
- reads the game's config with `<game> wizard config --json --dev`, as
  `--game` does.

Everything after the clone is the normal pipeline, so the stage keys and
patches work unchanged.

**Why a flag, and not an environment key or hidden config:**

- A flag is visible and explicit per run, and gone with the process.
- An environment key would leak into every child (the CLI, uv, the
  game's build) and persist in a developer's shell, where it would
  silently change what a later player-facing test does.
- A hidden config entry persists in the settings file, which players
  share in bug reports, and would turn a player's wizard into a dev
  build without a trace on screen.
- The flag also shows a banner on every screen ("Local source: 3d75004,
  not a release; nothing is published") so screenshots cannot mistake it
  for a release.

It does not appear in `--help`'s player section, in the UI or in
settings. It is documented in the CLI's `docs/wizard.md` developer
section.

**What changes in the CLI and the games:**

- **`[wizard] private`** (bool, default `false`), a new key. `repo`
  may be left out only when `private = true` (the user, 2026-10-17); a
  game with `private = false` (or unset) and no `repo` stays a config
  error, as today, so a public game cannot lose its repo by accident. A
  private game's `wizard config` omits the repo and update fields, and the
  wizard skips the update check. `xbr wizard build` (the release builder
  of wizard binaries) and the publish flow refuse a private game, since a
  published wizard must clone from somewhere public. `private = true` with
  a `repo` is allowed and means the same refusal to publish.
- **`--source` works for every game,** private or not. For a game with a
  `repo` it replaces the clone URL for that run only: the update check
  still runs against the repo, and the build's provenance is `local`, not
  `tag`. This is how a developer tests an unpushed commit of cat or b3
  through the real wizard.
- **Provenance:** the manifest gains `source`, filled by the CLI from the
  clone, never by the wizard:
  - a release clone records `{"kind": "tag", "repo": "<url>", "tag":
    "<tag>", "commit": "<sha>"}`;
  - a local one records `{"kind": "local", "via": "checkout"|"bundle",
    "commit": "<sha>", "ref": "<ref>"}`;
  - a developer's own checkout (no mark) records `{"kind": "dev",
    "commit": "<sha>"}`.
  - Paths are never recorded, and neither is the clone's `file://`
    origin: a local source gets `via` and the commit only. The
    `private_leaks` check already refuses paths, and the test covers the
    new field.
- `sources.game` is unchanged, and the version string gains nothing, so a
  local build's version reads like any other.
- **Publishing:** the wizard publishes nothing in any mode (it only
  builds bundles on the player's disk). `xbr wizard publish` and the
  `<slug>-wizard-*` release flow refuse a game with `private = true`.

### D15. SSX 3 and Spartan packaging

This is done by the games' own sessions (ssx3-ec for `ssx3/recomp`,
xb-windows for `spartan/tca`). This spec reads those trees and does not
edit them. Per game:

- **`[package]`:** `app` (`Ssx3` and `SpartanTotalWarrior`, as already
  drafted), the targets `windows`, `steamos` and `macos` where the game
  builds on the Mac (SSX 3 declares macos; Spartan to be confirmed).
- **`packaging/`:**
  - `launch.env.default.windows` and `launch.env.default.macos` (the
    stock keys only);
  - `windows/README.part` and `macos/README.part` (steamos uses the
    CLI's);
  - no `config.default.toml`, since neither has an enhancements layer.
- **A `LICENSE`** on the same terms as cat's and b3's (the
  orchestrator, 2026-10-17; each owning session adds it): the CLI always
  copies one and refuses without it.
- **`[wizard]`:** `private = true` and no `repo` until the game has a
  public repo (D14), an icon when one exists, and options:
  none for config keys (no `reads_config`), so only flag options such as
  the target. The wizard's options screen then shows only the target and
  the folders.
- **`[data]`:** the defaults from `docs/manifest.md` (`~/Games/<app>`
  etc.).
- **Spartan only:** `git init` and a first commit of `spartan/tca`
  (excluding the dump, build trees and `tca-old/`). Local source mode
  needs a commit, and the stage keys need a tree id.

## Implementation notes (deviations, 2026-10-17)

Where the implementation (CLI `feat/wizard-incremental-builds`, toolkit
`feat/wizard-incremental-builds`, cat `feat/wizard-incr-pin`) differs from
the decisions above, and why.

Stage keys and reuse (D1 to D3, D11):

- The stage key includes the version string, since README.txt carries it.
- generate and icon have no import edge: the gen key already holds the
  XBE sha (and gen/'s listing digest, so a hand recomp reruns compile),
  and icon.key holds the XBE sha.
- The Homebrew dylib shas sit in wrap:macos's inputs, not compile's: they
  are copied into the app at wrap time, not linked differently.
- wrap's key has no upstream stage key: the manifest sha covers the
  payload. On macOS the .app is relinked (clonefile) every run; only
  hdiutil is skipped.
- `--keep-stage` is a no-op: the stage is always kept.
- The plan is read-only. After an import, generate and icon read "run"
  (they are checked after the import). wrap is predicted from a recorded
  basis; the run decides on the manifest sha.
- `clean --all` never deletes game_files/, .venv, the Ghidra export or
  the wizard's mark. Bundles are pruned only when `--out` is inside the
  game folder. `--clean` keeps game-files.json. Patches are recorded and
  pruned apart from full bundles.

Reproducible output (D12):

- The build time and version time (SOURCE_DATE_EPOCH or the commit
  times) landed in phase 1, because wrap reuse needs them. The `-o`
  digest goes after `-g<8>`, before `-dirty`, and is empty for a stock
  build.
- lld records its command line, cwd and PDB path in the PDB, so the
  toolkit cannot neutralise a game's absolute `--pdb`: cat passes
  `--pdb=` (cat 1be3106). `/pdbaltpath` and `/pdbsourcepath` go beyond
  the spec's flag list. The PDB still holds the llvm-mingw path: equal
  binaries need the same toolchain path, which the wizard's layout
  gives. There is no separate .venv map, since the .venv sits inside the
  game folder under the root map. macOS `-g` builds (OSO paths) are not
  covered; package builds Release.

Patches (D5 to D10):

- macOS patches ship the app's signed parts whole, and the half-size rule
  does not count them.
- A bundle record is a base only when `--patch-from` names it; the
  default base is the version installed on this host.
- A patch that changes game data needs `--yes` when nothing can ask.
- A change to game files alone keeps the version.
- The history's `what` for a patch is "patch".
- Windows: apply.exe reads `patch.lst`, not patch.json, and takes the
  `Local\<App>-apply` lock. The switch has a short rename window. It
  pauses when double-clicked. `migrate` checks only the program files.
- A v1 installer run over a migrated install (found in 7.5) puts v1's
  root files and launcher back. The game then runs v1 from the root and
  ignores `current.txt`, and the uninstall entry names v1 again. Running
  the current full installer again repairs it completely: the root is
  clean, the stub is back and the entry is right. Installers already
  shipped cannot be changed, so there is no code change; the full
  installer is the documented repair.

Wizard (D4, D13, D14):

- A bundle source records its plain path as origin (git opens a bundle
  only by path). A checkout's clone uses a `file://` URL, not
  `--no-local`.
- The clean checks ignore untracked files: byproducts a .gitignore misses
  would otherwise block every run.
- In local mode the config comes from a throwaway clone at the commit
  being built, and the update check compares the release the binary
  embeds.
- The Welcome line comes from the mark alone. Whether the clone is clean
  is checked at Checks, after the tools are fetched.
- The output line ("Makes:") and its Change… dialog are on the Summary.
  The plan's `output` is a prediction made against the newest bundle
  record; the run decides again on the real manifest.
- The disk line and Free space are on the Done page, since they need the
  runner that Checks sets up.
- Install now for a steamos patch runs `./install.sh` in the unpacked
  folder, without `--steam`.

Gates:

- The Deck's Proton toolkit tests were not run for 3.4: they compile in
  the Deck's distrobox, and builds stay on the Mac. The toolkit change
  is CMake link flags, covered by the POSIX ctest `reproducible_link`.

## Risks / Trade-offs

- **[A wrong skip ships stale code]:** the key misses an input.
  → The equality test (D12) runs incremental against clean on the
  fixture for each input class, and `--verify` / "Rebuild everything"
  are always one click away.
- **[The Windows layout migration breaks existing installs]:** players
  of BLiNX 2 v1 have the in-place layout.
  → The new installer migrates once and keeps the old files as a
  version, with a `game_files` junction so its launcher still starts
  (D8). It is tested from a v1 install on the PC (task 7.5).
- **[Hard links share inodes across versions]:** an in-place write to a
  kept file would change every version.
  → The game never writes into its program folder (data lives in the
  data folder), and the appliers only create new files and never open
  kept ones for writing.
- **[Determinism flags change the binary]:** `--no-insert-timestamp`
  and prefix maps change the timestamp and the debug info only.
  → The goldens run on the first build with the flags (task 3.4); the
  pdb still resolves symbols for crash reports.
- **[A cross-host base is guessed wrong]:** the player picks the wrong
  "the Deck has" entry.
  → The applier's sha check refuses (D10), and the wizard can then make
  the full installer.
- **[macOS App Management blocks the swap]:** replacing an app in
  `/Applications` may need the permission on macOS 13 and later.
  → The swap is the first write to the app's path, so a refusal changes
  nothing. The applier explains the permission and offers
  `~/Applications` (D9), and task 4.4 tests both cases.
- **[Power loss during an apply]:** every applier flushes before its one
  atomic switch (D7 to D9). The game-file step is the only window, and
  rerunning the patch completes it.
- **[Disk]:** a kept folder is 6 GB plus bundles.
  → Two bundles are kept, the space is shown in the UI, and one button
  frees it.

## Migration Plan

- The state file is new. A folder without one runs every stage once (D3)
  and is then incremental.
- `manifest.json` goes to `schema 2` (`source`, `volatile`, the Windows `root` block, `patch` in
  patches). Every reader accepts 1 and 2. A schema 1 base is a valid patch
  base.
- The Windows layout migrates on the first full install of the new
  installer (D8).
- The CLI's pin moves in cat and b3 when it ships. No game change is
  needed for them.

## Resolved Questions

Answered by the user on 2026-10-17 (1 to 4) and by the orchestrator
(5 to 7):

1. **Windows layout:** `versions\` + `current.txt` with rollback, the
   one-time migration of in-place installs, and the C `apply.exe` (D8).
2. **macOS:** one previous app kept for rollback (D9).
3. **Game files:** a patch may change them, with the warning that
   rollback will not undo them on steamos and Windows; on macOS rollback
   does restore them (D10).
4. **`[wizard] repo`:** optional only with `[wizard] private = true`; a
   public game without a repo is a config error. `--source` works for
   games with a repo too (D14).
5. **The flag:** `--source`.
6. **SSX 3 and Spartan:** a LICENSE on cat's and b3's terms, added by the
   owning sessions in phase 8 (D15).
7. **HUD pack time:** the estimate uses the measured 4 to 8 s;
   `wizard-test-notes` is corrected.

## Open Questions

None.
