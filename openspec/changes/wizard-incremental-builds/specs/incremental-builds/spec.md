## ADDED Requirements

### Requirement: Stages run only when their inputs change
`xbr package` SHALL record, per stage (import, generate, `compile:windows` for `build-pkg-win/` used by both windows and steamos, `compile:macos`, icon, hud, `stage:<target>`, `wrap:<target>`), a key hashed from the stage's input digests and the keys of the stages it reads, and each output's sha256, size and mtime, in `build-state.json` under the clone's git directory (`$(git rev-parse --git-dir)/xbr/`), written atomically, so that the state never makes the tree dirty. A stage SHALL be skipped only when its key is unchanged and every recorded output passes its check; otherwise it and every stage below it SHALL run. A stage SHALL drop its entry before it starts. Generate SHALL depend only on import and the existing generation key, not on the CLI, toolkit or `uv.lock` pins as such. Compile SHALL be keyed on the whole toolkit tree and its uncommitted changes, the toolchain digest, the build environment, the full CMake option list and the icon. The `import` and `enhance hud` commands SHALL record their stages the same way when run on their own. `write_manifest` SHALL always rerun, and the wrap key SHALL include the sha256 of the staged `manifest.json`, so a bundle always carries the manifest written by its own run.

#### Scenario: A code-only change rebuilds only the program
- **WHEN** a package run follows a finished one in the same folder, and only a runtime source file in the game changed
- **THEN** the plan shows import, generate, icon and hud as reused and `compile`, `stage` and `wrap` for the target as run, naming the game tree as the reason

#### Scenario: The state does not dirty the clone
- **WHEN** a package run finishes in a clean wizard clone
- **THEN** `git status --porcelain` in the clone is empty, and the next run's version has no `-dirty` suffix

#### Scenario: A pin bump does not rerun the analysis
- **WHEN** the CLI pin moves to a release whose `tools/` and `templates/runtime/` trees are unchanged
- **THEN** generate is reused

#### Scenario: A toolkit runtime change rebuilds the program
- **WHEN** only a file under the toolkit's `src/` changed, committed or not
- **THEN** `compile:windows` reruns and generate is reused

#### Scenario: A toolchain pin change starts the compile afresh
- **WHEN** the llvm-mingw pin in `config/setup-pins.json` changes between runs
- **THEN** `compile:windows` reruns after its CMake cache is dropped, and generate is reused

#### Scenario: One build folder, two targets
- **WHEN** steamos is packaged after windows with no change in between
- **THEN** the steamos run reuses `compile:windows` and runs only `stage:steamos` and `wrap:steamos`

#### Scenario: A lost state file costs one full pass
- **WHEN** `build-state.json` is deleted or is not valid JSON
- **THEN** every stage runs once, and the next run with no change reuses them all

#### Scenario: A deleted output reruns its stage
- **WHEN** the player deletes `build-pkg-win/` between runs
- **THEN** `compile:windows` and the stages below it rerun, and the stages above it are reused

#### Scenario: A crash mid-stage is not taken for a finished stage
- **WHEN** a run is killed during `compile:windows`
- **THEN** the next run has no entry for `compile:windows` and reruns it

#### Scenario: A rebase with equal trees rewraps with the new manifest
- **WHEN** the game is rebased so that its tree is unchanged but its commit differs, and the package runs again
- **THEN** compile and stage are reused, the wrap reruns, and the new bundle's manifest names the new commit and version

#### Scenario: Game files are not rehashed every run
- **WHEN** a package run follows a finished one and no game file's size or mtime changed
- **THEN** no game file is read for hashing, and the manifest's game-file sha256s come from the cache

### Requirement: A forced full rebuild is always available
`xbr package --clean` SHALL delete the state file, the per-build-folder trees, the staging trees and the icon cache before running, and SHALL keep the generated sources and their generation key, so generate reruns only when that key is stale; `--clean=all` SHALL also delete the generated sources and the analysis cache, so every stage after import reruns. The wizard SHALL offer `--clean` as "Rebuild everything", off by default, and SHALL NOT offer `--clean=all`. `xbr clean --all` SHALL NOT delete the wizard's mark in the state directory.

#### Scenario: Rebuild everything ignores the state
- **WHEN** the player ticks "Rebuild everything" with an up-to-date folder
- **THEN** compile, icon, hud, stage and wrap run, generate is reused because its generation key matches, and the staged `files[]` equal the previous build's

#### Scenario: A full clean reruns the analysis
- **WHEN** `xbr package --clean=all` runs with an up-to-date folder
- **THEN** every stage after import runs, the analysis included

#### Scenario: Cleaning keeps the wizard's mark
- **WHEN** `xbr clean --all --yes` runs in a wizard build folder
- **THEN** `.git/xbr/wizard.json` is still there, and the next wizard run updates the folder in place

### Requirement: The wizard keeps its build folder across releases
When `<root>/src` holds a clean clone that is the wizard's, the wizard SHALL fetch the release tag (or, in local source mode, the given ref), check the commit against the release's lock in player mode, and check it out, keeping the rest of the folder. A clone is the wizard's when it carries the mark in its git directory, or, for a clone made before the mark existed, when it is clean, its `origin` equals `[wizard] repo`, it is shallow and its HEAD is a tag's commit; such a legacy clone SHALL then be marked. A player-mode run on a clone last used in local source mode SHALL reset `origin` to `[wizard] repo`. The wizard SHALL refuse a clone with local changes, or one that is neither marked nor legacy, naming the folder.

#### Scenario: A new release reuses the folder
- **WHEN** a player who built release A runs the wizard of release B with the same build folder
- **THEN** the clone moves to B's commit, and the stages whose inputs did not change are reused

#### Scenario: A folder from today's wizard
- **WHEN** the build folder was made by a wizard release from before this change, and is clean
- **THEN** the new wizard accepts it, writes the mark, and updates it in place

#### Scenario: Local edits are never discarded
- **WHEN** `<root>/src` has uncommitted changes
- **THEN** the wizard stops before any git command that changes the checkout and names the folder

### Requirement: Incremental output equals clean output
An incremental build SHALL produce a staged tree whose manifest `files[]` (path, sha256, size) equals a clean build's of the same commit and options, and whose other top-level manifest fields are equal except those the manifest lists under `volatile` (`built` and the source branches). The program build SHALL be deterministic: no link timestamps, a content-derived PDB GUID, and no build-folder, toolkit, toolchain or venv paths in the binaries.

#### Scenario: Two folders, one result
- **WHEN** the same commit is built clean in one folder and incrementally from the previous commit in another
- **THEN** the two staged manifests' `files[]` are equal, and every other top-level field not in `volatile` is equal

### Requirement: The kept folder's size is bounded
The CLI SHALL keep the staging tree of each target in place across runs, keep the newest 2 bundles per target in `dist/` (changeable with `--keep-bundles`) and a manifest record of every bundle, keyed by the manifest's sha256, under its state directory's `bundles/<target>/`. `xbr clean` SHALL print what it would free and delete only with `--yes`, and only inside the game folder.

#### Scenario: A third bundle evicts the first
- **WHEN** a third steamos bundle is wrapped
- **THEN** the oldest steamos bundle is deleted from `dist/`, its manifest record stays, and it is still offered as a patch base
