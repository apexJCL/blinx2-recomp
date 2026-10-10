## Why

A game pins the toolkit and the CLI by exact sha today: `game.toml` has
`[cli] commit` and `[toolkit] branch` + `commit`. Releases are now tagged
(2026-10-10, all annotated): xboxrecomp-cli `v0.1.0` (dde49a6), the fork's
`blinx2-v0.1.0` (35ed68f, the tip of `blinx2/portability`), blinx2-recomp
`v0.1.0` (e9ef392). The user prefers tags as the anchor: "the better/ideal"
one; sha stability itself does not matter. A tag says which release a game
is on, `pins refresh` can say which newer release exists, and a player
reading `game.toml` sees a version, not a hash.

The CLI cannot read a tag today. `manifest.py` requires both `commit`s and
refuses any unknown key (so `tag = "..."` is an error), the bootstrap
(`wrapper/game.py`, vendored as `blinx2.py`) clones and checks out the
commit only, and `pins refresh` compares the pins with branch heads.

Tracker: BLX-64. No Fable spec pass: Fable is out of quota (the quota
wind-down rule); the orchestrator's brief carries the recommended design,
and the review at merge is Opus.

## What Changes

- **game.toml**: `[cli]` and `[toolkit]` accept `tag = "..."`.
  - A tag alone is a complete pin.
  - A tag with a `commit` makes the commit a lock: the tag must resolve to it, or
    every command that fetches refuses with an error naming both.
  - Without a tag, the pins work as before (`[cli] commit`; `[toolkit]`
    `branch` and `commit`).
  - `[toolkit] branch` stays allowed, but a tag pin doesn't need it.
- **Fetching by tag** (the toolkit clone in `setup`, the CLI's own marked
  clone, and the bootstrap's clone). An annotated tag is peeled to its commit
  (`^{commit}`). The lookup checks the clone's own tags first, then fetches
  that one tag from `origin`. A cached clone already at the lock (or at the
  tag, when there is no lock) needs no network.
- **`pins refresh`** reports, for a tag pin, the newest tag on the remote with
  the pinned tag's prefix (`v*` for the CLI, `blinx2-v*` for the fork). It
  also says whether the pinned tag still resolves to the lock. A commit-only
  pin keeps the branch-head report.
- **`doctor`** shows the tag next to the commit on the `cli:` and `toolkit:`
  rows. It warns when a checkout's local copy of the tag disagrees with the
  lock. It stays offline.
- **`xbr new`** writes `[cli] tag` + `commit` when the CLI it runs from is at
  a release tag (or, from the remote, the newest `v*` tag). Otherwise it
  writes the commit alone, as before.
- **The bootstrap** (`wrapper/game.py`, so `blinx2.py`) reads `tag` and
  resolves it with git alone, under the same rules. It stays standard-library
  Python 3.9+. The `blinx2` shell file only `exec`s it, so nothing there
  changes.
- The docs (`docs/manifest.md`, README "Releases and pins", "How a game
  finds the CLI", troubleshooting) describe tag pins.
- **cat**:
  - `game.toml` moves to `[cli] tag = "v0.2.0"` + `commit`, and to
    `[toolkit] tag = "blinx2-v0.1.0"` + `commit` (the branch is kept for
    `bench`'s readers).
  - `blinx2.py` takes the new template.
  - cat now needs the new CLI, because v0.1.0 refuses the `tag` key, so the
    next CLI release is `v0.2.0`.

## Impact

- CLI: `manifest.py`, a new `gitpin.py`, `toolkit.py`, `cli_dir.py`,
  `pins.py`, `doctor.py`, `scaffold.py`, `wrapper/game.py`, the docs and the
  tests. Version 0.2.0.
- cat: `game.toml`, `blinx2.py`, README and `docs/packaging.md` wording.
- An older bootstrap still works with a tag + commit `game.toml`, because it
  reads the commit and ignores the tag line. A tag-only `game.toml` needs the
  new bootstrap.
- No runtime, renderer or toolkit change: no Linux/Proton host run, no golden.
