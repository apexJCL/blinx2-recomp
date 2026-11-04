Worktrees `wt/language/{xboxrecomp,xboxrecomp-cli,cat}`, branches `feat/language-setting` (toolkit off `posix-host/portability` 2a27f0dc, CLI off `main` 7b6bfa6, cat off `main` 0017bd8a). The tracker item.

## 1. Toolkit

- [x] 1.1 `src/kernel/kernel_language.{c,h}`: the code table, `xbox_SetLanguage`, `xbox_Language`, `xbox_LanguagesShipped`, the lazy `RECOMP_SYSTEM_LANGUAGE` read; `XBOXRECOMP_LANGUAGES` cache variable, checked at configure.
- [x] 1.2 `kernel_xbox.c`: index 7 and `XC_MAX_OS` +0x30 from `xbox_Language()`.
- [x] 1.3 `recomp_env.h` row `SYSTEM_LANGUAGE`; `enhance_cfg.c` binds `system.language`; `enhance.c` calls `xbox_SetLanguage`.
- [x] 1.4 Menu: `Language` on the Game page when the list is not empty, `ENHANCE_LIVE_RESTART`.
- [x] 1.5 ctest `kernel_language`: the lazy env read (case), a code, unknown and outside-the-list codes, unset, the block field; `enhance_menu` `test_language_row`; `xbox_SetLanguage` stubs in the tests that link enhance.c without the kernel.
- [x] 1.6 `docs/runtime/config.md`.

## 2. CLI

- [x] 2.1 `manifest.py` `[system] languages` (codes checked), `docs/manifest.md`.
- [x] 2.2 `build.py`: `-DXBOXRECOMP_LANGUAGES` on configure and when the cache differs; package's input digest includes it; the new-game `config.default.toml` template gains `[system] language = "en"` (test_config_defaults reads the toolkit beside).
- [x] 2.3 pytest.

## 3. BLiNX 2

- [x] 3.1 `game.toml` `[system] languages`, `config.default.toml` `language = "en"`, `docs/env.md` row.
- [x] 3.2 Gates: Mac build, POSIX ctests, `uv run pytest scripts`, ruff; Windows build on the PC; French boot with the key, English without; `blinx2 bench golden` at the default.
