# steamos-pinned-proton: design

Read against umu-launcher 1.4.4 (the CLI's pin), `umu/umu_run.py`,
`umu_proton.py`, `umu_runtime.py`, `umu_consts.py`.

## What umu-run does today

- `PROTONPATH` unset, `GE-Proton` or `UMU-Proton`: a GitHub API request for
  the latest release on every launch, and a download into
  `$XDG_DATA_HOME/Steam/compatibilitytools.d/` (`STEAM_COMPAT`) when it is
  newer than what is there. Offline, it falls back to the newest one
  installed.
- Any other value is a path, resolved strictly: missing means the launch
  fails. umu-run cannot download a given tag.
- The runtime (`$XDG_DATA_HOME/umu/steamrt*`) is downloaded when absent
  and otherwise updated on every launch, unless `UMU_RUNTIME_UPDATE=0`,
  which skips the update only (a missing runtime still downloads).

## D1. The pin

`pins.GE_PROTON = {"version": "GE-Proton11-7", "dir": "GE-Proton11-7-x86_64",
"url": ".../GE-Proton11-7/GE-Proton11-7-x86_64.tar.gz", "sha256": "c5448b76…"}`.
`steamos_values` writes it into `install_lib.py` and `launch.sh` as
`@PROTON_VERSION@`, `@PROTON_DIR@`, `@PROTON_URL@`, `@PROTON_SHA256@`. The
`dir` is the tarball's top directory, so Steam lists the same release by the
name umu-run would give it, and a release umu-run or ProtonUp-Qt already put
there is used as is.

The pin was GE-Proton11-9 (sha256 `b2cf4a63…`) until CLI
fix/proton-pin-11-7 (BLX-194) moved it to GE-Proton11-7. Under 11-9
winedevice crashes in hidclass.sys on the unimplemented
`win32u.dll.__wine_send_input`, so winebus never starts and the game sees no
pads, in Desktop and Game Mode alike (runs/padslot2/probe/). 11-7 is the
bench and golden Proton and has working pads on the Deck.

## D2. The installer fetches the pin

`ensure_proton(compat, fetch)` after `ensure_umu` (after the bundle is
verified, so a damaged bundle wastes no download):

- present when `<compat>/<dir>/proton` is a file: nothing is downloaded;
- otherwise: a flat check for 2 GB free (the 560 MB tarball and the
  about 1.5 GB unpacked tree), a download to `<compat>/.<dir>.tar.gz.part`, the sha256
  checked before anything is unpacked, then an unpack into
  `<compat>/.<dir>.partial/` and one rename to `<compat>/<dir>`. A failure
  removes the part file and the partial tree.
- Safe unpack: every member lies under `<dir>/`; no absolute names, no
  `..`; symlinks and hard links point inside the tree; no devices or FIFOs.
  Modes are left to Python's `filter="data"` (3.12, and the 3.8+ security
  releases) where it exists, with no masking of our own; the members are
  checked the same either way.
- A link (dangling or not) where `<dir>` goes is removed, a broken tree is
  replaced, never merged.
- Nothing in `compatibilitytools.d` is ever removed: it is shared with Steam
  and other games. An old pinned release stays until the player removes it.
- No prompt: the player chose to install a game that needs it, and the
  install prints the size first. `--no-proton` skips the step for a player
  who sets `PROTONPATH` themselves.

## D3. The launcher uses the pin

- `PROTONPATH` defaults to
  `${XDG_DATA_HOME:-$HOME/.local/share}/Steam/compatibilitytools.d/@PROTON_DIR@`,
  an absolute path, so umu-run never asks GitHub for a release.
- When it is the default and `<it>/proton` is missing, the launcher fails
  through `fail` (a notification) naming the release and `install.sh`.
- A `PROTONPATH` from the environment or from `config/launch.env` wins;
  `GE-Proton` there follows the newest release (the explicit update path).
- A `PROTONPATH` in the bundle's `launch.env.default` is ignored: a game
  shares that file with its Windows installer, and BLiNX 2's
  `PROTONPATH=GE-Proton` line there undid the pin on the Deck run (umu-run
  asked GitHub at every launch). The launcher saves the environment's value
  before loading the defaults and restores it (or unsets it) after.

## D4. Runtime updates only after an install

- `install` writes `<root>/state/runtime-update` on every install, rollback
  included (a switch of `current` is an update).
- The launcher, when `UMU_RUNTIME_UPDATE` is not set by the player: if the
  runtime is installed and that file is absent, exports
  `UMU_RUNTIME_UPDATE=0`. If the file is present, it removes the file and
  lets umu-run check once. A missing runtime downloads as before, and the
  file is removed then too: the download is the newest runtime, so the next
  launch neither checks again nor shows the notice for it.
- Why not freeze the runtime for good: a later pinned Proton may need a newer
  runtime, and the update rides on the player's install.

## D5. The notice covers every download

`setup_pending` gains a step for the post-install check, "Checking the Steam
Linux Runtime for updates ...", taken from a flag the launcher sets when it
removed `state/runtime-update`. A codename `PROTONPATH` always shows
"Checking for the newest <codename> ...": umu-run may download a newer
release whatever is installed, which no local check can tell beforehand.
The existing machinery stays: zenity
`--progress --pulsate` (or a kdialog passive popup), plus `notify-send` in
Game Mode (gamescope) or when neither is there; it closes when the game
writes its log, when umu-run ends, or after `NOTICE_MAX`. The notice text
no longer says "first launch", since an update shows it too.

## D6. Single-instance guard

- `mkdir -p <root>/state; exec 9>>"<root>/state/launch.lock"; flock -n 9`.
  On failure: `tell "@NAME@ is already starting or running."`, exit 0.
  `tell` is a notification (`notify-send`), else a zenity info window with a
  timeout, else a kdialog passive popup; always also stderr.
- Taken right after the settings load, before the log rotation and the
  log cap, which would otherwise trim the running game's logs.
- The launcher no longer `exec`s umu-run. It runs it in the background with
  `9>&-`, forwards TERM/INT/HUP and waits, so the lock lives exactly as long
  as the launch. The notice helpers also run with the descriptor closed.
  Steam tracks the launcher's process tree either way.
- No `flock` (not on any SteamOS, but a minimal distribution): no guard, and
  the launch goes on.
- A stale lock cannot happen: `flock` releases with the process.

## Tests (`tests/test_steamos_install.py`)

- `fetch_proton`: fake release tarball → installed tree, sha mismatch →
  nothing written, unsafe members (`../x`, absolute, symlink out, device)
  refused, an existing tree → no download, unpinned bundle refused.
- `install --no-proton` does no fetch; `install` writes
  `state/runtime-update`; `status` reports the Proton line.
- launch.sh: default `PROTONPATH` is the pinned path; missing pinned Proton
  fails with the install hint; a codename in `launch.env` passes through;
  `UMU_RUNTIME_UPDATE=0` exported once the runtime exists, unset (and the
  file removed) after an install, the player's value kept; a second launch
  while the first holds the lock exits 0 with the message and never starts
  umu-run; umu-run's descriptors do not include the lock.

## Not in scope

Pinning the runtime (umu-run has no way to), a shader cache (BLX-184
follow-up), the Windows and macOS launchers.
