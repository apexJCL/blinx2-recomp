## ADDED Requirements

### Requirement: Language setting
The kernel SHALL answer `ExQueryNonVolatileSetting(XC_LANGUAGE)` and the `XC_MAX_OS` block's +0x30 field with the language in force: `system.language` (env `RECOMP_SYSTEM_LANGUAGE`), one of `en ja de fr es it ko zh pt` as `XC_LANGUAGE` 1..9. Unset SHALL be English (1). An unknown code, or a code outside the game's declared list, SHALL be logged once and give English.

#### Scenario: Stock
- **WHEN** a game runs with no `system.language`
- **THEN** index 7 reads 1 and the block's +0x30 reads 1, as before this change

#### Scenario: French
- **WHEN** BLiNX 2 runs with `RECOMP_SYSTEM_LANGUAGE=fr`
- **THEN** index 7 reads 4 and the title screen and menus are in French

#### Scenario: Not shipped
- **WHEN** a game declaring `en, ja, fr, es` runs with `system.language = "de"`
- **THEN** one line names the declared list and the game runs in English

### Requirement: Declared languages
A game SHALL declare the languages it ships in `game.toml` `[system] languages`; the CLI SHALL pass them to the build as `XBOXRECOMP_LANGUAGES`. The in-game menu SHALL list a `Language` choice on the Game page with only those codes, marked as applying at restart, and SHALL list none for a game with no list.

#### Scenario: Menu
- **WHEN** a player picks `fr` in BLiNX 2's menu and saves
- **THEN** `config/config.toml` gains `language = "fr"` under `[system]`, and the next start is in French
