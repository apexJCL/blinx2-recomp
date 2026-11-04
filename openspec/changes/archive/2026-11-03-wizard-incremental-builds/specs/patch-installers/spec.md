## ADDED Requirements

### Requirement: A patch is chosen from a usable base manifest
`xbr package` SHALL make a patch when a base `manifest.json` is usable (same app and target, equal `data_layout`, a sha256 for every path the patch keeps, and on Windows a versioned install with a `current.txt` and an equal `stub_abi`) and the patch is under half the full bundle's size, and the full installer otherwise. The base SHALL be the target's current version, taken from `--patch-from` (a manifest, a version folder, an app, or a bundle tar), else the current version installed on this host, else one of the bundle records the CLI keeps, which `package --plan --json` lists for the wizard to offer. `--full` SHALL always make the full installer. A schema 1 manifest SHALL be a usable base.

#### Scenario: No install found
- **WHEN** no base is found for the target
- **THEN** the full installer is made, and the wizard says "no install found"

#### Scenario: A bundle tar made outside the wizard is a base
- **WHEN** `--patch-from` names a steamos bundle tar made by an earlier CLI
- **THEN** its `manifest.json` is read from the tar without extracting it and used as the base

#### Scenario: A patch that changes game files warns first
- **WHEN** a steamos or Windows patch changes, adds or deletes a game file under an equal `data_layout`
- **THEN** the wizard and the applier warn that rolling back will not undo the game data change before applying

#### Scenario: macOS rollback restores game files
- **WHEN** a macOS patch that changed a game file is rolled back
- **THEN** the app's game files equal the base version's, and no game-data warning was shown before the apply

#### Scenario: An in-place Windows install gets the full installer
- **WHEN** the Windows install found has a root `manifest.json` and no `current.txt`, or a different `stub_abi`
- **THEN** no patch is made, and the full installer (which migrates) is offered

#### Scenario: A game data layout change forces a full installer
- **WHEN** the base's `data_layout` differs from the new bundle's
- **THEN** no patch is made, and the reason is shown

### Requirement: A patch holds only what changed
A patch SHALL hold the files whose sha256 differs from the base and the files new since it, the full new `manifest.json` and `SHA256SUMS`, `patch.json` (base version, base manifest sha256, new version, and the changed, new, deleted and kept paths with their sizes and sha256s), and the target's current applier. Files are copied whole. Applying a patch to its base SHALL give a tree byte-identical to a full install of the new version, compared over the manifest's `files[]` (the versioned program files and the game files). On Windows the root tools (the stable stub and `apply.exe`) SHALL be recorded outside `files[]`; a patch SHALL never replace the stub.

#### Scenario: A code-only patch
- **WHEN** only the program binary and its pdb changed
- **THEN** the patch holds those two files, the manifest, SHA256SUMS, `patch.json` and the applier, and no game files

#### Scenario: Patch equals full
- **WHEN** a patch is applied to its base, and separately the full installer of the same version is installed fresh
- **THEN** the two installs have the same program and game-file paths and sha256s

### Requirement: Applying a patch checks its base first
Every applier SHALL check, before changing anything, that the install's current version (steamos `current`, Windows `current.txt`, the macOS app at its path) equals `base_version`, that the sha256 of that version's `manifest.json` equals `base_manifest_sha256`, and that every kept program and game file matches the base manifest. A base version that is installed but not current SHALL NOT qualify. On any mismatch it SHALL exit non-zero naming both versions (or the file) and pointing to the full installer, and SHALL leave the install unchanged.

#### Scenario: The wrong base
- **WHEN** a patch made for version A is applied to an install whose current version is B
- **THEN** the applier prints "This update is for A; this install is B. Use the full installer for <new>." and `status` is unchanged

#### Scenario: The base is installed but not current
- **WHEN** version A is kept under `versions/` but `current` is B, and a patch for A is applied
- **THEN** it refuses as for the wrong base

#### Scenario: A damaged kept file
- **WHEN** a kept game file's sha256 differs from the base manifest
- **THEN** the applier refuses naming the file, and nothing is written

### Requirement: Game files are applied by a patch-aware sync
A patch SHALL apply game files by taking the wanted set from the new manifest, writing only the new and changed files (each to a temporary name, flushed, then renamed), deleting only the paths listed as deleted, and reporting, without removing, any other file it does not expect. It SHALL NOT use the full install's sync, which removes every file absent from the bundle.

#### Scenario: A code-only patch keeps the game files
- **WHEN** a patch with no game-file changes is applied to an install with 715 game files
- **THEN** all 715 game files are still present and byte-identical afterwards

### Requirement: Applying a patch is atomic and can be rolled back
On steamos, the patch command SHALL run the same pre-steps and post-steps as a full install (host, ownership, layout and free-space checks, the launch lock, the runtime and Proton steps, the seed config, the stable launcher, the desktop entry, the Steam entry when asked, the runtime marks, pruning), and replace only the program step (build `versions/<new>.partial` from hard links to the base's kept files plus the patch's files, verify, flush, rename) and the game-file step. It SHALL switch `current` by an atomic rename with the files and directories flushed before it and the root flushed after it, keep 3 versions by default, and leave `rollback` working. On Windows (the versioned layout), it SHALL do the same with `versions\<new>`, `FlushFileBuffers` on every written file, and `current.txt` replaced by `MoveFileExW`, refusing while the game's mutex exists. On macOS it SHALL clone the installed app with `cp -c`, overlay and delete, verify with `shasum` and `codesign --verify --deep --strict`, flush with `F_FULLFSYNC`, and exchange the clone and the installed app in one `renamex_np(RENAME_SWAP)`, keeping the previous app beside the installed one (same folder, never in the data folder) for `rollback` and journalling the rest there so a rerun completes it. Every target SHALL install the tools its rollback needs: steamos's `install.sh` in each version, Windows' `apply.exe` and `state\history.txt` at the install root, macOS's `apply.command` and `xbr-swap` beside the previous app; so rollback SHALL work after the patch is deleted. No applier SHALL run while the game runs.

#### Scenario: Power loss during a steamos apply
- **WHEN** the Deck loses power at any step of `install.sh patch`
- **THEN** after the restart either the base version is current and launches, or the new version is current and complete, and rerunning the patch finishes any game-file step left undone

#### Scenario: Power loss during a Windows apply
- **WHEN** the PC loses power at any step of `apply.exe`
- **THEN** after the restart `current.txt` names either the base or the complete new version, that version starts, and rerunning `apply.exe` completes the apply

#### Scenario: Power loss during a macOS apply
- **WHEN** the Mac loses power at any step of `apply.command`
- **THEN** after the restart an app is at the install path and launches (the base, or the complete new version), and rerunning `apply.command` completes the apply

#### Scenario: A patch over an older installer's base
- **WHEN** a steamos patch is applied to a version installed by an `install.sh` that predates the pinned Proton
- **THEN** the patch installs the pinned Proton, the stable launcher and the desktop entry exactly as a full install would, and the game launches

#### Scenario: Rollback after a patch
- **WHEN** `install.sh rollback` runs after a patch was applied
- **THEN** `current` points at the base version again, and the game launches

#### Scenario: Rollback after the patch is deleted
- **WHEN** the patch folder, tar or DMG is deleted after the apply, and rollback is run from the install (`install.sh rollback`, the root `apply.exe rollback`, or the `apply.command` beside the previous app)
- **THEN** the base version is current again and launches

#### Scenario: Keep 3
- **WHEN** a patch makes the fourth version on steamos with the default keep
- **THEN** the oldest version that is neither current nor previous is removed, and three remain

#### Scenario: macOS App Management refuses the swap
- **WHEN** replacing the app in `/Applications` is refused with `EPERM`
- **THEN** the installed app is unchanged, and the applier explains the App Management permission and offers to install into `~/Applications`

#### Scenario: A non-admin user cannot write /Applications
- **WHEN** creating the clone beside the app in `/Applications` fails with `EACCES`
- **THEN** the installed app is unchanged, nothing is left in `/Applications`, and the applier says the folder is not writable and offers `~/Applications`

#### Scenario: The macOS data folder is untouched
- **WHEN** a macOS patch is applied and rolled back
- **THEN** `~/Library/Application Support/<App>/` is byte-identical before and after

### Requirement: Patches stay on the player's machines
Patches SHALL be built only from the player's own build folder and SHALL NOT be uploaded, published or fetched by any CLI or wizard command. A patch holding owner-generated assets (such as the HUD pack) SHALL be treated as those assets are.

#### Scenario: No network for patches
- **WHEN** a patch is made and applied
- **THEN** no command sends or downloads any patch content
