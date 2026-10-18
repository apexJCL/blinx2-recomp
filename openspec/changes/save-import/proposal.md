# Change: Import a player's Xbox saves (`saves list` / `saves import`)

## Why

Players who own the game often have saves from xemu, from a softmodded
console, or from save-sharing sites. Today the only way to bring one in is
to copy folders by hand into the right `hdd/` folder. Even then, BLiNX 2
reports a retail-signed save as damaged. The build's kernel exports a zero
`XboxSignatureKey`, so the save has to be re-signed first (the 2026-10-03
seed needed a local re-sign helper). The spike (`spike.md`) found
that everything a player would bring is readable with stdlib Python. That
covers dashboard folders, zips, xemu's qcow2 or raw HDD with FATX inside,
and memory-unit images. Its verdict is go-limited.

## What changes

- **CLI (`xboxrecomp-cli`):** a new verb `xbr saves` with `list` and
  `import`, reached as `<slug> saves`.
  - Sources: folders, zips, xemu HDD images (qcow2 with backing files, or
    raw), xemu MU images, and Cxbx-Reloaded save folders. Default detection
    finds both emulators.
  - Imports take only the game's title IDs. Before writing, the verb backs
    up the existing saves and checks the backup. It supports a dry run,
    skips conflicts unless told to replace, stages every write, and refuses
    while the game or the source's emulator is running.
  - One name and size rule set covers folder, zip and FATX sources. Links
    are never followed.
  - It re-signs the files the game declares, with the build's key, on
    every import. A game with no `[saves]` table still imports, with a
    warning that its saves may need re-signing and may not load.
  - All reads are read-only and nothing touches the network.
- **`game.toml` `[saves]`:**
  - The title IDs (default `[xbe].title_id`).
  - `signing` (`resign`, `none`).
  - `tdata` (`ignore`, `optional`, `required`).
  - `[[saves.signed]]` recipes: a glob, the data range, the digest offset and
    the expected size. A glob may carry several recipes.
  - cat declares BLiNX 2's recipe: `blinx2data.bin`, HMAC-SHA1 over
    `[0, 33972)` at 33972. The size, 81920 bytes, is provisional until
    phase 0 confirms it and checks for a second signed block.
- **Wizard:** an "Import saves" screen over `saves list --json` and
  `saves import`.
- **SteamOS bundle:** the importer ships in the bundle, with an
  `import-saves.sh` launcher next to `launch.sh` that runs the bundled verb
  against the bundle's own data root.
- **No toolkit change.** The zero key stays the stock behaviour, and the
  runtime is not touched. The toolkit's E: size, which differs from retail,
  is recorded as a toolkit follow-up.
- **Release:** a CLI CHANGELOG entry and version bump, and cat's `game.toml`
  CLI pin moved to that release.

Deferred until there is a sample:
- Action Replay `.xsv` (no public format).
- Non-roamable (HDD-key) saves.

Out of scope (the user, 2026-10-18):
- Export.
- Any use of the retail-derived key, in the importer or the kernel.

## Capabilities

### New Capabilities
- `save-import`: detecting, validating and importing a player's own Xbox
  saves into a recompiled game's save root.

## Impact

- `xboxrecomp-cli`: `src/xboxrecomp_cli/saves/` (sources, FATX, qcow2,
  import, process checks), `main.py`, `manifest.py`, `docs/manifest.md`,
  `README.md`, `CHANGELOG.md`, tests. The SteamOS templates gain
  `import-saves.sh` and carry the `saves` module. The wizard gets a new
  screen in `wizard/internal/screens`.
- cat: the `game.toml` `[saves]` table and CLI pin, and a README "Bring your
  saves" section. b3 adds its table after phase 0 finds out whether it signs.
- The deployment rule that installers never write `hdd/`
  (`openspec/specs/deployment/spec.md:9`) still holds: the importer is a
  verb the player runs, not an installer.
- Privacy: saves are never committed, published or sent anywhere, and the
  test fixtures are synthetic.

## Status

Draft from the spike, 2026-10-17, revised after the review and
the user's answers of 2026-10-18 (recorded in `design.md`, "Decisions from
the user"). Nothing is implemented.
