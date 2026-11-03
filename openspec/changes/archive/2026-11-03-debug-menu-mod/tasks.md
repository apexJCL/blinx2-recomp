Worktree `wt/debug-menu-mod/cat` (`mods/debug-menu` off `main`). No toolkit
change. Runs under `xbox-recomp/runs/debug-menu-mod/`. Mac jobs under
`lockf -t 3600 ~/.recomp-mac.lock`, runs through `notes/mac-run-lock.sh`,
`SDL_AUDIODRIVER=dummy`. ## 1. Mod

- [x] 1.1 `src/debug_menu_logic.{c,h}`: addresses, PRESS START and menu
  checks, the open writes, the cursor skip, pure C.
- [x] 1.2 `src/debug_menu.{c,h}`: descriptor (enable, control open),
  the two rows, the request queue, on_frame, on_enable (D1-D5).
- [x] 1.3 `src/main.c` mod table, `CMakeLists.txt`.
- [x] 1.4 Env rows `RECOMP_DEBUG_MENU`, `RECOMP_DEBUG_MENU_KEY` (`recomp_env_game.h`, `docs/env.md`), commented
  keys in `packaging/config.default.toml`, `game.toml` `enhance_stock`.
- [x] 1.5 Input script `key` step: arrows, enter, esc, space (D6).
- [x] 1.6 `scripts/test_debug_menu.py`.

## 2. Checks

- [x] 2.1 Entry runs: each of the 15 debug rows entered headless on Metal;
  unsafe rows into `dbgm_unsafe`, each filed as a follow-up.
- [x] 2.2 Overlay run: mod on, F10, Mods page, the mod's page, the row;
  the debug menu, SELECT A STAGE and a stage load (frames).
- [x] 2.3 Mods describe dump lists the mod and its settings.
- [x] 2.4 Mod off: no `[MOD debug_menu]` write lines; nothing changes.

## 3. Gates

- [x] 3.1 Mac build; `uv run pytest scripts`; ruff.
- [x] 3.2 Metal goldens (mod off, `RECOMP_MENU=0`): attract, stage1, story
  pass on 2512a32 (`runs/debug-menu-mod/golden-metal2.log`; 93478e1 in
  `golden-metal.log`).
- [x] 3.3 Native Windows golden (PC on Windows): attract and story
  pass-with-known, stage1 pass on 2512a32, built on bench host-win
  (`runs/debug-menu-mod/win2.log`; 93478e1 in `win.log`). Proton leg
  non-blocking.
