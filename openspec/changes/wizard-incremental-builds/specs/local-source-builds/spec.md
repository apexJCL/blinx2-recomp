## ADDED Requirements

### Requirement: The wizard builds from a local source only on an explicit flag
`xbr-wizard --source PATH[#REF]` SHALL clone the game into `<root>/src` from a local git checkout or a git bundle instead of a repo URL, at `REF` (default `HEAD` for a checkout, the only head for a bundle), and SHALL then run the normal pipeline. When the source checkout has uncommitted changes, it SHALL warn that they are not built. The mode SHALL NOT be reachable from the UI, the settings file or an environment key, SHALL NOT appear in the player help, and SHALL show a banner naming the source commit on every screen.

#### Scenario: A checkout without a remote
- **WHEN** a developer runs `xbr-wizard --source ssx3/recomp` and the checkout has no remote
- **THEN** the wizard clones it, reads the game's config through `wizard config --json --dev`, builds, and shows the local-source banner throughout

#### Scenario: A dirty checkout
- **WHEN** the `--source` checkout has uncommitted changes
- **THEN** the wizard says they are not built, shows it on the banner, and builds the committed `REF`

#### Scenario: A git bundle
- **WHEN** a developer runs `xbr-wizard --source tca.bundle`
- **THEN** the wizard clones the bundle's head and builds, and a later run with the same bundle reuses the build folder

#### Scenario: A player run is never local
- **WHEN** the wizard starts without `--source` after a local-source run with the same settings file
- **THEN** no local-source state is read from the settings, and the wizard uses its release repo, or explains that this game has none

### Requirement: A local build records its provenance without paths
The bundle's `manifest.json` SHALL carry `source`: `{"kind": "tag", "repo", "tag", "commit"}` for a release clone, `{"kind": "local", "via": "checkout"|"bundle", "commit", "ref"}` for a local source, and `{"kind": "dev", "commit"}` for a developer's own checkout. It SHALL be filled by the CLI from the clone's mark, and SHALL never hold a filesystem path or the clone's `file://` origin.

#### Scenario: Provenance of a local build
- **WHEN** a bundle is built through `--source` from a checkout
- **THEN** `source.kind` is `local`, `source.via` is `checkout`, `source.commit` is the built commit, no `file://` URL or path appears anywhere in the manifest, and `private_leaks` finds nothing

### Requirement: Private games can use the wizard without a repo
`[wizard]` SHALL accept `private` (bool, default `false`). `repo` MAY be absent only when `private = true`; a game with `private` false or unset and no `repo` SHALL be a config error. For a private game, `wizard config` SHALL omit the repo and update fields, the wizard SHALL skip its update check, and `xbr wizard build` and the wizard publish flow SHALL refuse the game, with or without a `repo`.

#### Scenario: A public game without a repo
- **WHEN** a game's `[wizard]` has no `repo` and no `private = true`
- **THEN** loading the manifest fails with a config error naming `[wizard] repo`

#### Scenario: A private game is never published
- **WHEN** `xbr wizard build` runs for a game with `[wizard] private = true`
- **THEN** it exits non-zero, saying a published wizard needs a public game with a repo

### Requirement: Local source works for games with a repo
`--source` SHALL also work for a game that has a `repo`: the clone comes from the local source for that run only, the update check still uses the repo, and the bundle's `source.kind` SHALL be `local`.

#### Scenario: An unpushed commit of a public game
- **WHEN** a developer runs `xbr-wizard --source cat#feature` for BLiNX 2
- **THEN** the build uses that commit, the update check runs against the game's repo, and `source.kind` is `local`
