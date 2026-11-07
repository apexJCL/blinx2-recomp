## Why

The game READMEs grew for developers. BLiNX 2's is 649 lines: the wizard
link sits in a tip at the top, but a player then meets an 18-row options
table, the toolchain pins and the golden harness before the bug-report
advice at the end. The other games went the other way: BLiNX 1 copies
BLiNX 2's layout, Burnout 3 has its own, and KUF and Auto Modellista still
carry the `xbr new` stub that tells a player "it will crash the first
time". None says up front which copy of the game the port needs, though
every hand-written part is keyed to one release's addresses and another
release is the most common reason a build "works" and then crashes.
Bug reports arrive without the release, the build version or the logs.

The user asked (2026-11-04) for one standard README for every game
repo: for players who are not developers, with the dense docs one link
away; the game's title, the latest release's builders, what the builder
does, a very visible disclaimer of the exact release supported, a showcase
(stills, the overlay menu, a before/after per mod), and a bug report
template that collects what triage needs.

## What Changes

- **The standard** (CLI `docs/readme.md`): the sections, their order and
  what each holds; which parts restate `game.toml` (between
  `<!-- xbr:readme:... -->` marks) and which are the game's prose; the
  image rules; a checklist that says when a README meets it.
- **The shared template** in the CLI (`templates/readme/`): a README
  skeleton and a GitHub issue form (`.github/ISSUE_TEMPLATE/bug_report.yml`,
  `config.yml`), both game-agnostic, with `@TOKEN@` slots that come from
  `game.toml`.
- **The BLiNX 2 pilot**: a new README to the template; the old README's
  player reference (building by hand, install, saves, controls, every
  option, known issues, troubleshooting, the crash checklist) moved to
  `docs/playing.md` and its developer half (architecture, build from
  source, pins, testing, environment, contributing) to
  `docs/developers.md`, nothing dropped; the issue form; a fresh set of
  screenshots in `docs/images/` replacing the old set.
- **A gap list** for the other games: what each lacks to fill the
  template.
- **The approval round** (the user, 2026-11-05; design D11): renamed
  headings, a mods table with an on/off pair or an origin note per mod, no
  config keys in the README; rolled out to BLiNX 1, Burnout 3, KUF, Auto
  Modellista, Quantum Redshift, SSX 3, JSRF and Spartan on
  `docs/readme-standard` in each repo.
- **Later (phase 2, not in this spike)**: `<slug> readme` in the CLI, which
  writes the skeleton, refreshes the marked blocks from `game.toml`, writes
  the issue form, and with `--check` runs the checklist for `doctor` and
  `public export`; `xbr new` writes both files.

## Impact

- CLI: `docs/readme.md`, `src/xboxrecomp_cli/templates/readme/` (three
  files); no code in phase 1. CHANGELOG under Unreleased.
- cat: `README.md` rewritten; new `docs/playing.md`, `docs/developers.md`,
  `.github/ISSUE_TEMPLATE/`; `docs/images/` replaced by the new set; links
  into the old README's anchors (`docs/packaging.md`, the bundles'
  `README.part`) checked.
- Public: nothing pushed. The pilot and its images wait for the user's
  approval, then go out with the next push round through `blinx2 public
  export`.
- The other game repos: the same three files and the issue form each.
- Players: no build or runtime change. No goldens (docs only).
