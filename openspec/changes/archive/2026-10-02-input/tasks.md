## 1. Scripted pad

- [x] 1.1 Identify the XInput entry points in `XPP` from their bodies and their callers (`sub_0021C190` init, `sub_0021C290` per-frame poll, `sub_0021C710` rumble).
- [x] 1.2 Override them in `src/recomp_manual.c`, and regenerate: recomp reports 8 functions excluded.
- [x] 1.3 Add `src/pad_input.c`: script parser, `[INPUT]` log, packet numbers, presets `@skip-intro` and `@new-game`.
- [x] 1.4 Verify on macOS (`analysis/bringup/input/` (local analysis, not published), toolkit 5187d75): without a script title_movie_1a.sfd opens at 83.7 s and the attract demo loads stg0101 at 120.3 s (`base1`); with `@skip-intro` they happen at 11.2 s and 48.7 s (`skip1`).
- [x] 1.5 Verify the first, timed `@new-game`: R0_opening.sfd at 26.0 s, Time Sweeper editor (tsedit_tex_us.ipk) at 37.7 s (`newg1`). Both stg0101 and tsedit then stop flipping: a loader worker exits (`PsTerminateSystemThread`) and the main thread polls `ObReferenceObjectByHandle`/`ObfDereferenceObject` (ordinals 246/250) about 17M times a second. That is a thread-object bug, not input.

## 2. Event-driven script

- [x] 2.1 Toolkit `xbox_FileOpenHook` after every `NtCreateFile`; cat installs it in `cat_pad_early_init()` before the entry point (logo_mgs.sfd opens before the first pad poll).
- [x] 2.2 Steps `wait open`, `wait SECS`, `wait polls`, `tap ... until open`, action lists; the timed form kept.
- [x] 2.3 Presets on events: `@skip-intro`, `@attract`, `@new-game`.
- [x] 2.4 Verify on macOS (toolkit e0ca280 + hook; smoke-tested again on 7502e04 + 6ec0099), normal and with 18 busy loops on 14 cores: title_movie_1a 7.3 s / 10.0 s, stg0101 32.0 s / 55.6 s, R0_opening 16.1 s / 25.9 s, tsedit 23.2 s / 38.1 s, every preset at its target (`ev-*`, `slow-*`; `RECOMP_PB_EXEC=0` runs `pb0-*` are not slower).

## 3. Host pad

- [x] 3.1 Merge the toolkit's `xbox_input` state (XInput on Windows, SDL2 elsewhere behind `RECOMP_HOST_PAD=1`).
- [x] 3.2 Verify on Proton with a real controller: START on the title advances to the menu. (Moved to `input-real-devices` 1.4; tick when archiving.)
- [x] 3.3 Verify SDL2 GameController on macOS (`RECOMP_HOST_PAD=1`), including that initialising it off the main thread is safe. (Moved to `input-real-devices` 9.1/9.2; tick when archiving.)
