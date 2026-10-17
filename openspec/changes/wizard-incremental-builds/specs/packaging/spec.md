## MODIFIED Requirements

### Requirement: Manifest and version
Each bundle SHALL carry `manifest.json` (schema 2; readers SHALL also accept schema 1) with the schema version, product and name, the bundle version, target, build time, the sources (`cat`, `toolkit` and `cli`, each with commit, branch, dirty flag and dirty-path count), a `source` block (`{"kind": "tag", "repo", "tag", "commit"}`, `{"kind": "local", "via", "commit", "ref"}` or `{"kind": "dev", "commit"}`), a `volatile` list naming the top-level fields that may differ between two builds of the same inputs (`built` and the source branches), the gen/ digest and file count, the build type, enhancement state, generated-code options, compiler and any overrides, the bundled host libraries (macOS), on Windows the root tools (`stub_abi` and the sha256 and size of the root launcher and `apply.exe`, outside `files[]`), the data layout version, the optional `"xbe"` note when the dump is not one `xbe.sha256` lists, and every file's path, sha256 and size; plus `SHA256SUMS` in `sha256sum` format. The build time and the version's time part SHALL come from `SOURCE_DATE_EPOCH` when set, else the newest commit time of the game and the toolkit, never the clock or a file's mtime. The version SHALL be `<that time>-c<game sha7>-t<toolkit sha7>-g<gen digest 8>`, with `-o<6 hex>` (a digest of the option set, the HUD pack and the full CMake `-D` list: build type, non-stock values, debug) appended when any of them differs from stock, and `-dirty<hash>` appended when the game, the toolkit or the CLI tree has uncommitted changes, so two dirty builds of one commit with different changes get different versions. The manifest SHALL hold no absolute path, `file://` URL, home directory or host name. The bundle manifest SHALL be documented in the CLI's `docs/bundle.md`.

#### Scenario: Clean build version
- **WHEN** the game, the toolkit and the CLI trees are clean at commits A, B and C, with stock options
- **THEN** the version is `<time>-c<A7>-t<B7>-g<digest8>` with no `-o` or `-dirty`, the time is the newest of A's and B's commit times, and `sources.cli.commit` is C

#### Scenario: The same inputs give the same version
- **WHEN** one clean commit with stock options is built twice, an hour apart, in two folders
- **THEN** the two versions are equal, and the manifests differ at most in the fields listed in `volatile`

#### Scenario: Options make the version distinct
- **WHEN** one commit is built with `render.scale = 1` and again with `render.scale = 2`
- **THEN** the two versions differ in their `-o` part

#### Scenario: A non-stock CMake option makes the version distinct
- **WHEN** one commit is built stock and again with `--allow-debug`
- **THEN** the second version has an `-o` part and the first has none

#### Scenario: Two dirty builds of one commit
- **WHEN** two bundles are built from the same commit with different uncommitted changes in any of the three trees
- **THEN** their versions differ in the `-dirty<hash>` suffix

#### Scenario: No private data in the manifest
- **WHEN** a bundle is built on a machine whose home directory or host name would appear in a path, or from a local source cloned through `file://`
- **THEN** `manifest.json` contains none of them, and `package` refuses to write a manifest that does

### Requirement: Generated code is regenerated when its inputs change
The CLI SHALL record a generation key beside `src/recomp/gen/` once `recomp` succeeds, and SHALL use it as the generate stage's key in the build state, with the import stage as its only upstream. The key SHALL hold:
- the XBE's sha256;
- the tree ids of the toolkit's `tools/` and `templates/runtime/`, plus a hash of any uncommitted change under them, including untracked or ignored files there that a stage reads (the icall database today), and not the toolkit or CLI commit, so a pin move that leaves those trees unchanged keeps gen/;
- the sha256, or "absent", of every input file the pipeline stages read that the run does not itself produce;
- a hash of the argument lists the stages run;
- the extra arguments `recomp` ran with, which SHALL be empty for packaging.

Every pipeline stage command SHALL delete the key before it runs. `package` SHALL treat gen/ as stale when the key is absent or differs from the current one, when the regeneration marker is present, or when gen/'s recorded listing digest no longer matches, and SHALL name the differing field in its plan line. The key and gen/ SHALL stay out of git.

#### Scenario: Seed file edited
- **WHEN** `config/seed_functions.json` changes after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Toolkit icall database appears
- **WHEN** the toolkit's `tools/recomp/output/icall_targets.json` is created or changed after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Interrupted generation
- **WHEN** a run is interrupted between analyze and the end of recomp
- **THEN** the next run regenerates, because the key is absent

#### Scenario: A pin move outside the lifter
- **WHEN** the toolkit pin moves to a commit that changes only its runtime `src/`, and the CLI pin moves too
- **THEN** the next plan reuses generate and rebuilds the program
