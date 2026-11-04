## Why

The toolkit kernel answers `XC_LANGUAGE` (EEPROM index 7) and the `XC_MAX_OS` block's +0x30 field with 1, English, on every game (GitHub #6). Games pick their text from that value, so a player cannot get the German, French or Japanese text the disc already carries. BLiNX 2 ships en, ja, de, fr, es and it, and reads the value once at boot in `sub_0005F960` (every write to its language global 0xAE738C is there). BLiNX 1 NA plays in en, ja, fr and es; its code sends de and it to English although the assets exist (a separate, optional fix).

## What Changes

- **`system.language`** (env `RECOMP_SYSTEM_LANGUAGE`, a row of the toolkit's main table): a language code, `en` (the default, stock), `ja`, `de`, `fr`, `es`, `it`, `ko`, `zh`, `pt`, the dashboard's nine (`XC_LANGUAGE` 1..9). The kernel answers index 7 and the `XC_MAX_OS` +0x30 field with it. The enhancements layer reads the config key before the guest starts; a build without the layer reads the variable, the same way, as `storage.ram_cache` does.
- **The game's languages**, declared in `game.toml`: `[system] languages = ["en", "ja", ...]`. The CLI checks the codes and passes the list to every configure as `-DXBOXRECOMP_LANGUAGES=en,ja,...`; the toolkit compiles it into the kernel. When a game declares a list, a code outside it is logged and English is used, so a player never lands in a language the disc does not carry. A game with no list takes any of the nine (spikes) and gets no menu item.
- **Menu**: a `Language` choice on the Game page, listing only the declared codes, marked "applies at restart" (`ENHANCE_LIVE_RESTART`): every game known here reads the setting once at boot. Save writes `system.language` to `config/config.toml`.
- **BLiNX 2**: `[system] languages = ["en", "ja", "de", "fr", "es", "it"]` in `game.toml`, `[system] language = "en"` in `config.default.toml` (as the CLI's new-game template now carries it), the env row in `docs/env.md`.

Default stays English, so every golden and every stock run is unchanged.

## Out of scope

- BLiNX 1's de/it fallback in its own code, and its `game.toml` list (en, ja, fr, es): a separate change in the blinx project once the CLI pin there carries the key.
- The wizard: no language option yet (a later `choice` option can write `system.language`).
- `ExSaveNonVolatileSetting` stays a no-op: a game that writes its language back changes nothing.
