## Context

The pin (`openspec/changes/archive/2026-10-17-guest-one-cpu`) came before the guest CPU lock. It made the light-pool race as rare as on the console. The lock (`mac-one-cpu`) then closed the race on every host, macOS included, where no pin can act. The pin stayed as the default on Win32 and Linux, pending the Proton A/B of the pin against `=all` with the lock on (`mac-one-cpu` tasks 7.2). The user kept it (2026-10-10, `all` measured equal).

## Decisions

- **D0. The user's decision (2026-11-05):** every core is BLiNX 2's default, reversing the 2026-10-10 choice to keep the pin. Burnout 3 is not included.
- **D1. Drop the game default, not the toolkit code.** The pin stays available (`=one`, `=<n>`) as the A/B and for titles without the lock. Only BLiNX 2's default changes.
- **D2. Every host, not native Windows only.** The exe is the same under Proton, and the game cannot tell the two apart without the Wine probe the toolkit keeps for `guest_priority`. Proton measured `all` equal, so one default for both keeps one behaviour to test.
- **D3. The pin is the cause, not spin.** Sleep pacing hides the problem as well (2/2 runs clean), but spin is a player-facing option, and the cause is the pin. Every core is the fix at either pacing.
- **D4. The pacing default per target build (the user, 2026-11-05).** `spin` in the Windows exe, `sleep` in the macOS build (proposal, "Frame pacing per build"). Native Windows was the one host where sleep did worse: host `NtReadFile` stalls of up to 674 ms in 4 of 6 runs, one a 424 ms freeze in stage 1, against none at spin. The Deck runs the same exe under Proton and so gets spin, though Proton measured sleep as spin; telling Proton apart would need the toolkit's Wine probe, and one exe should behave one way.
- **D5. A code default in the game, the files untouched in their order.** `host_enhance_init` calls the toolkit's `enhance_cfg_set_code_default("present.pacing", "spin")` under `#ifdef _WIN32`, before `xbox_enhance_init`. The toolkit takes it in place of the caller's default (tier 5) in every typed lookup, so the init's settings line shows the mode in force (the CLI's `ENHANCE_RE` and `golden.py`'s stock check read that line) and an invalid value falls back to it; the in-game menu takes it as the item's stock value, so a `sleep` saved from the menu is a change that is written and kept, and `spin`, the row reset and Reset to defaults drop the key. A first cut set the mode after init when `enhance_cfg_source_of` said the code default; the menu still took `sleep` as stock, so saving `sleep` on Windows dropped the key and the next start spun (the review, 2026-11-05). A game default in `RECOMP_ENV_GAME_DEFAULTS` would not do: it fills the environment tier, which wins over the player's `config/config.toml`. `config.default.toml` is one file for every target, staged as is by `blinx2 package`, so it leaves the key out (commented, saying why). The toolkit's own default stays `sleep` for the other games.

## Mechanism (as far as measured)

At spin pacing, the main thread spends most of each frame in a lowered spin-wait. It holds the guest CPU and hands it over only at a pass that sees a waiter. With every guest thread on one host core, a worker woken by its host wait must first win the core from the spinner from the Windows scheduler before it can even queue as a waiter. The trace shows a worker holding the guest CPU for 2.4 s while getting no CPU of its own. Linux's scheduler, under Proton, hands the core over sooner, which is why the Proton A/B saw no difference. Not proven: which host thread kept the core during the 2.4 s hold.

## Risks

- The light-pool race comes back if the lock misses a path. The lock has been on since 2026-10-10 and the macOS builds have run without the pin since then. The water golden checks it.
- Windows players lose sleep's CPU saving (about 95-100 points of process CPU on the PC, 45-60 on the Deck). It stays one setting away (`pacing = "sleep"`).
