## ADDED Requirements

### Requirement: steamos launches download nothing unasked
The steamos bundle SHALL carry one GE-Proton release pinned by the CLI (version, top directory, URL, sha256). `install.sh install` SHALL make sure that release is unpacked in `$XDG_DATA_HOME/Steam/compatibilitytools.d/<dir>`, downloading it only when absent, checking its sha256 before unpacking, refusing archive members outside `<dir>/`, and never removing anything else there; `--no-proton` SHALL skip the step. The launcher SHALL default `PROTONPATH` to that directory's absolute path and SHALL fail with a message naming `install.sh` when it is missing; a `PROTONPATH` from the environment or from `config/launch.env` SHALL win, and one in the bundle's `launch.env.default` SHALL be ignored. Once the runtime is installed the launcher SHALL set `UMU_RUNTIME_UPDATE=0`, except on the first launch after an install or rollback, unless the player set it.

#### Scenario: Install fetches the pinned Proton once
- **WHEN** `install.sh` runs on a host without `compatibilitytools.d/<dir>`, and then again
- **THEN** the first run downloads the pinned tarball, checks its sha256 and unpacks `<dir>/proton`; the second downloads nothing

#### Scenario: A tampered download installs nothing
- **WHEN** the downloaded tarball's sha256 differs from the pin
- **THEN** the install exits non-zero naming both hashes, and neither `<dir>` nor a partial tree nor the tarball remains

#### Scenario: The launch never asks for the newest Proton
- **WHEN** the installed game is launched with no `PROTONPATH` in `config/launch.env`
- **THEN** umu-run gets `PROTONPATH=<data>/Steam/compatibilitytools.d/<dir>`, and with the runtime installed and no install since the last launch, `UMU_RUNTIME_UPDATE=0`

#### Scenario: The bundle defaults do not undo the pin
- **WHEN** the bundle's `launch.env.default` holds `PROTONPATH=GE-Proton`, and the game is launched first with nothing else set, then with `PROTONPATH=/opt/my-proton` in the environment, then with `PROTONPATH=GE-Proton` in `config/launch.env`
- **THEN** umu-run gets the pinned directory, then `/opt/my-proton`, then `GE-Proton`

#### Scenario: Pinned Proton removed
- **WHEN** `compatibilitytools.d/<dir>` is deleted and the game is launched
- **THEN** the launcher exits non-zero before starting umu-run, telling the player to run `install.sh` again

#### Scenario: A first launch that downloads the runtime uses up the update check
- **WHEN** the first launch after an install finds no runtime and umu-run downloads it
- **THEN** `state/runtime-update` is removed, and the next launch sets `UMU_RUNTIME_UPDATE=0` and shows no notice

### Requirement: steamos launches show their downloads
While a launch may download (no runtime yet, the runtime check after an install, a codename `PROTONPATH`, or a new Wine prefix), the launcher SHALL show a zenity progress window or a kdialog popup, and a `notify-send` notification in Game Mode or when neither tool exists, closed when the game writes its log, when umu-run ends, or after `NOTICE_MAX` seconds. `LAUNCH_NOTICE=0` SHALL turn it off.

#### Scenario: First launch on a Deck with no runtime
- **WHEN** the game is launched in Game Mode or Desktop Mode on a Deck without `~/.local/share/umu/steamrt*`
- **THEN** a notice is visible until the game's window is up

### Requirement: One steamos launch at a time
The launcher SHALL hold an exclusive `flock` on `<root>/state/launch.lock` for the whole launch, taken before it rotates or trims logs, and SHALL NOT pass that lock's descriptor to umu-run. A launch that cannot take it SHALL tell the player the game is already starting or running and exit 0 without starting umu-run.

#### Scenario: Double launch
- **WHEN** the game is launched while an earlier launch of it is starting or running
- **THEN** the second launch shows "already starting or running", exits 0, and the first launch's logs and processes are untouched

#### Scenario: Relaunch after quitting
- **WHEN** the game quits and is launched again at once
- **THEN** the new launch takes the lock and starts, even if a wineserver from the first is still alive
