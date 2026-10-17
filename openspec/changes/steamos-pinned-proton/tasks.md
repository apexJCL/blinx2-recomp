# steamos-pinned-proton: tasks

Worktrees: `wt/deck-launcher/xboxrecomp-cli` on `blx13/deck-launcher` off
CLI `main` 80ab034 (commits authored and committed as the noreply identity;
no tracker ids, hosts or private paths in the CLI); `wt/deck-launcher/cat`
on `blx13/deck-launcher` off cat `main` 38a409e (this spec).

Rules: builds on the Mac only; the Deck test needs the orchestrator's go
(the user removes the umu runtime and switches Game Mode / Desktop Mode);
`flock -w 3600 ~/.recomp-run.lock` on the Deck; keep 3 versions there.

## 1. Spec
- [x] 1.1 This spec (Opus, no Fable pass).

## 2. CLI (`wt/deck-launcher/xboxrecomp-cli`)
- [x] 2.1 `pins.GE_PROTON` and the `@PROTON_*@` values in `steamos_values` (D1).
- [x] 2.2 `install_lib.py`: `fetch_proton`/`ensure_proton`, `--no-proton`, `state/runtime-update` on install and rollback, the `status` line, the docstring layout (D2, D4).
- [x] 2.3 `launch.sh`: pinned `PROTONPATH` and its check, `UMU_RUNTIME_UPDATE`, the notice step and text, the lock and `tell`, umu-run in the background with the descriptor closed (D3-D6).
- [x] 2.4 `README.part`: the pin, `--no-proton`, following the newest Proton, the guard.
- [x] 2.5 Tests per the design (CLI eef02cb: 738 passed, 1 skipped; ruff clean); `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.

## 3. Deck
- [x] 3.1 Mac-built steamos bundle from cat at the CLI branch; the orchestrator's go. (`--no-build` from the golden packaging build c9a61cab/tc497da5, CLI 8881852.)
- [x] 3.2 No umu runtime, pinned Proton absent: install fetches the pin; first launch in Game Mode shows the notice; a second tap says "already starting or running". (The no-umu half passed in Desktop Mode with a scratch HOME. The user walked Game Mode on 2026-10-17 with steamrt4 and GE-Proton11-9 removed: the install fetched and checked the pin, the notice showed, and a second tap gave the message. Gap: `state/runtime-update` survives a launch that downloads the runtime, against D4; BLX-192.)
- [x] 3.3 Desktop Mode: launch, double launch, quit and relaunch at once; `umu.log` shows no GitHub release request and "updates disabled" on the second launch.
  Found and fixed there: the game's shared `launch.env.default` set `PROTONPATH=GE-Proton`, which undid the pin (CLI 8881852, cat 10d6dc6). The rerun's umu logs: runtime download on launch 1, one check on the first launch that found it, then "steamrt4 updates disabled", and no GitHub Proton check.

## 4. Hand-back
- [x] 4.1 Comment and `pt review` BLX-13; pollers stopped.
