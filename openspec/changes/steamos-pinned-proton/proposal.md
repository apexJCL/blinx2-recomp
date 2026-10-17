## Why

The steamos launcher exports `PROTONPATH=${PROTONPATH:-GE-Proton}`. To
umu-run that codename means "the newest GE-Proton": every launch asks the
GitHub API for the latest release, and a new release is a 560 MB download
before the game starts, in Game Mode, with no say from the player. umu-run
also checks its Steam Linux Runtime for updates on every launch. A player's
game should change only when they install or update it.

The first launch shows a notice while umu-run downloads, but a launch that
updates the runtime or follows a new Proton shows nothing. And nothing stops
a second launch: a double tap in Game Mode starts two games on one Wine
prefix and one save root.

BLX-13 (v1-final), dispatched by the orchestrator:
1. pin the Proton release in the bundle, so a download happens only at
   install or on an explicit update;
2. show a progress dialog or notification while any umu download runs
   (zenity/kdialog, falling back to notify-send), in Game Mode and Desktop
   Mode;
3. a single-instance guard: a lock under the install root; a second launch
   says the game is already starting or running, then exits.

Opus wrote this spec with no Fable pass (CLAUDE.md, 2026-10-15).

## What changes

- `pins.py` gains `GE_PROTON`: one GE-Proton release (version, directory,
  URL, sha256), moved by a reviewed edit like `UMU_LAUNCHER`.
- `install.sh` makes sure that release is in
  `$XDG_DATA_HOME/Steam/compatibilitytools.d/` (where umu-run and Steam look):
  it downloads it, checks the sha256 and unpacks it safely, unless it is
  already there. `--no-proton` skips this for a player who manages Proton
  themselves. `status` reports it.
- The launcher defaults `PROTONPATH` to the absolute path of the pinned
  directory, and fails with a clear message (run `install.sh` again) when it
  is missing. `PROTONPATH=GE-Proton` in `config/launch.env` keeps following
  the newest release: the explicit opt-in.
- The launcher sets `UMU_RUNTIME_UPDATE=0` once the runtime is installed,
  except on the first launch after an install, which may update it. A
  missing runtime is still downloaded (umu-run has no pin for it).
- The notice covers every launch that may download: a missing runtime, a
  runtime update check, a missing Proton under a codename, a new prefix.
- A `flock` on `<root>/state/launch.lock` guards the launch. The launcher
  stays the parent of umu-run (no `exec`) and closes the lock's descriptor
  for umu-run, so a lingering wineserver never holds it.

## Impact

- `xboxrecomp-cli`: `pins.py`, `package/steamos.py`,
  `templates/steamos/{launch.sh,install_lib.py,README.part}`,
  `tests/test_steamos_install.py`. Game-agnostic; every game's steamos
  bundle gets it on its next CLI pin.
- cat: `openspec/specs/deployment` gains the requirement below once merged.
  No runtime, renderer or toolkit change; no golden affected.
- Players: an install now downloads about 560 MB once (the pin), and a
  launch never downloads Proton.
