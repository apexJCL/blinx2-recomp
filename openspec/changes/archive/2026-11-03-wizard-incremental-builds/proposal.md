## Why

The user asked (2026-10-17) for incremental updates in the
wizard: keep the build folder between runs, track what each stage was
built from by hashing its inputs, and end with either a full installer
or a patch installer that copies only the files that changed.

Today a new release costs a full rebuild. The wizard clones the game at
its release tag into `<root>/src` and refuses a folder that holds another
commit (`wizard/internal/repo/repo.go`: "holds a clone at X, not this
wizard's release"), so the player starts from a fresh folder: about 13
min of analysis and lifting plus 4 to 6 min of compiling on the Mac for
BLiNX 2 (`build-logs/timings.json`), 20 to 40 min on a slower PC
(`docs/wizard.md`). The CLI under it already skips much on a re-run in
the same folder (the import when the dump hash matches, setup, the gen
key in `pipeline.py`, ninja's objects), but nothing records the later
stages (the HUD pack, staging, the installer), and every run ships the
whole bundle: 3.5 GB for the Steam Deck, of which 3.3 GB is the
player's game files and 190 MB is the program. A code-only release
changes about 5% of the bundle.

Two additions from the user (2026-10-17, same item):

- **A developer-only local source mode.** SSX 3 (`ssx3/recomp`) and
  Spartan (`spartan/tca`) have no public repo, so the wizard must also
  build from a local checkout or a git bundle, hidden from players and
  publishing nothing, with the provenance recorded in the bundle's
  manifest as a tag is.
- **An acceptance plan on the Steam Deck:** wizard-built installers made
  on the Mac, installed on a fresh Deck layout. Burnout 3 tests the
  incremental build and the patch over its existing install; SSX 3 and
  Spartan test the full builder through local source mode.

## What Changes

- **Per-stage build state.** `build-state.json` in the clone's git
  directory (`src/.git/xbr/`, so it never makes the tree look dirty)
  records each stage's key and its outputs' sha256s and sizes. The
  stages are import, generate, compile per build folder, icon, HUD pack,
  stage and wrap. A key is hashed from the stage's inputs and the keys of
  the stages it reads.
  - A stage runs only when its key changed or an output fails its check.
  - The existing gen key becomes the generate stage's key, with no setup
    edge, so a pin bump does not rerun the analysis.
  - Compile is keyed on the whole toolkit tree and the toolchain.
  - `package --clean` and the wizard's "Rebuild everything" force a full
    build.
- **The wizard updates its build folder in place.** A clean clone at an
  older tag is fetched to the new tag and checked out instead of refused,
  and folders made by today's wizard are recognised and accepted. A
  clone with local changes is still refused.
- **Patch installers.** `package --patch-from BASE` diffs the new staged
  payload against a base `manifest.json` (the installed version's, one
  the build folder made earlier, or a file the developer gives) and wraps
  only the changed and new files, the list of deletions, and the full new
  manifest. Applying a patch gives a tree byte-identical to the full
  install. SteamOS applies it into a new `versions/<v>` with hard links;
  macOS clones the app, overlays and swaps, keeping one previous app for
  rollback; Windows moves to a versioned layout (`versions\` +
  `current.txt`, a one-time migration of in-place installs, a small C
  `apply.exe`) so a patch can be applied and rolled back the same way.
  A patch may change game files. On SteamOS and Windows that comes with
  a warning that rollback will not undo them; on macOS the game files
  live in the app, so rollback restores them.
- **Reproducible output.** The program build becomes deterministic (no
  link timestamps, fixed path prefixes) and the manifest's volatile
  fields are declared, so an incremental build is checked equal to a
  clean one.
- **Local source mode.** `xbr-wizard --source PATH[#REF]` (a checkout or a
  `.bundle`) clones from that instead of a repo URL. It is a flag only:
  not in the UI, not in the settings file, no environment key.
  `[wizard] repo` may be left out only when the new `[wizard] private =
  true` is set; `--source` also works for games with a repo. The
  manifest's new `source` block
  records `{"kind": "local", "via": "checkout"|"bundle", "commit": ...}`
  next to `{"kind": "tag", "repo": ..., "tag": ...}`, never a path.
- **Packaging for SSX 3 and Spartan**, done by their own sessions:
  `[package]`, `[wizard]` with `private = true`, `packaging/` templates
  and a LICENSE on cat's and b3's terms.

## Capabilities

### New Capabilities

- `incremental-builds`: per-stage keys and outputs in the kept build
  folder, invalidation, forced rebuilds, in-place updates of the build
  folder, and the equality of incremental and clean output.
- `patch-installers`: choosing a full or patch installer from a base
  manifest, the patch format per target, the base check, atomic apply and
  rollback.
- `local-source-builds`: the developer-only `--source` mode and its
  provenance.

### Modified Capabilities

- `packaging`:
  - "Manifest and version": schema 2 with `source` and `volatile`, the
    time from commits rather than the clock, and the `-o` options
    digest. This builds on the `cli-extraction` change's text of the same
    requirement, so it is archived after `cli-extraction` (task 10.3).
  - "Generated code is regenerated when its inputs change": the gen key
    as the generate stage's key, keyed on the toolkit's lifter trees
    rather than its commit.
- `deployment`:
  - "steamos versioned install with an atomic switch": flushes, and
    `install.sh patch`.
  - "Windows installer": the versioned layout, the migration and
    `apply.exe`, replacing "overwrite in place".
- The bundle manifest has no document today (`docs/manifest.md` in the
  CLI documents `game.toml`). A new `docs/bundle.md` in the CLI documents
  `manifest.json`, `patch.json` and the per-target layouts.

## Impact

- **Code** (all in `xboxrecomp-cli/`): `pipeline.py` (state file, keys),
  `package/__init__.py` and `package/{lib,steamos,windows,macos}.py`
  (stages, patch wrap), `templates/steamos/{install.sh,install_lib.py}`
  (patch apply), `templates/windows/` (versioned layout, apply helper,
  launcher), `templates/macos/` (apply script), `wizard/internal/{repo,
  model,screens,runner}` (update in place, the full/patch choice,
  `--source`). The toolkit and the games get link flags for determinism
  (`templates/runtime/` CMake, game `CMakeLists.txt`).
- **Games:** cat and b3 need no change beyond the CLI pin. SSX 3 and
  Spartan get `[package]`, `[wizard]` and `packaging/` from sessions
  the SSX 3 session and the Spartan session; Spartan first needs a git history.
- **Disk:** the kept folder grows by the old bundles the player keeps; a
  cap and a cleanup command bound it (design D11).
- **Legal:** patches hold the player's own derived files (the program and
  any owner-generated HUD pack). They are built and applied on the
  player's own machines, exactly as full bundles are, and never
  published.
- **Not in scope:** binary deltas, a content-addressed store, hosting or
  downloading patches, patches across a game-data layout change.
