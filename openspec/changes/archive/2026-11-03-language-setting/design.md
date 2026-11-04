## Context

`xbox_ExQueryNonVolatileSetting` (toolkit `src/kernel/kernel_xbox.c`) answers `XC_LANGUAGE` with a literal 1 and writes 1 at +0x30 of the `XC_MAX_OS` block. XAPI's `XGetLanguage` reads index 7 (BLiNX 1 also reads region 0x104 inside it); some titles read the whole block. The menu (`src/enhance/enhance_menu.c`) has a `RESTART` liveness for keys that only take effect at the next start.

## Decisions

**D1. One code table in the kernel.** `kernel_language.c` holds the nine codes in `XC_LANGUAGE` order (en 1, ja 2, de 3, fr 4, es 5, it 6, ko 7, zh 8, pt 9) and the language in force, `xbox_Language()`. Both answers in `kernel_xbox.c` read it, so the block and the single query cannot disagree (the `kernel_eeprom_settings` ctest checks that already).

**D2. Set before the guest, read lazily otherwise.** `xbox_SetLanguage(code)` is called by `xbox_enhance_init` from `system.language`, like `xbox_RamCacheEnable`. Without a call, the first query reads `RECOMP_SYSTEM_LANGUAGE`. Unset or empty is English; an unknown code, or one outside the game's list, logs one `[XBOX] system.language` line and stays English. Matching ignores case.

**D3. The list is the game's, at build time.** `game.toml` `[system] languages` is the one place a game says what it ships: the CLI already reads it for every command, and the list does not change at run time. The CLI passes it as the CMake cache variable `XBOXRECOMP_LANGUAGES` (comma list) on the first configure and whenever the cached value differs, the way it keeps the job pool in step, so a developer tree and a packaging tree agree. The toolkit puts it on `kernel_language.c` alone (a source property), so changing it recompiles one file. A toolkit older than this change ignores the variable (CMake's unused-variable warning); a CLI older than this change refuses the `[system]` table, so the game's `game.toml` gains it only once its CLI pin, or `XBOXRECOMP_CLI_DIR`, carries the key (native-widescreen's `[display]` table has the same order: CLI first).

Rejected: the list in `config.default.toml` (the player's layer; a list there could be "fixed" into a language the disc lacks), and a call from the game's `main.c` (a second place beside `game.toml`, and a C change per game for data).

**D4. Codes, not names, in the config.** `system.language = "fr"` is short, matches the CLI list and is what the menu's choice values are. The menu row shows the code with the help line naming the languages ("en English, fr French, ..."), since the overlay font is not sure to carry every native name.

**D5. Restart.** The item is `ENHANCE_LIVE_RESTART` with no setter: the menu stores the value, Save writes it, the next start applies it. Changing the answer under a running game would only confuse a title that cached it at boot.

## Risks

- A game that reads the language more than once would see the new value only after restart anyway (D5), so nothing differs.
- A non-English language changes text textures and so frames: goldens stay at the default, and `golden` runs must not set the key (it is not an enhancement key, so stock runs are unaffected by construction; a `system.language` set in a tester's `config.toml` would show in the run's config dump).
