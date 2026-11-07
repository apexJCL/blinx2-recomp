## Why

A player on native Windows 11 hears crackling in the boot movies and the title music. Their WAV capture (`RECOMP_DEBUG=audio_wav`, taken before XAudio2) holds the clicks, so they are in the guest's own mix, not in the host output. They are stale-lap replays: the CRI Sofdec writer falls behind the VP's cursor on the 64 KB movie ring, so the VP plays blocks still holding the previous lap. 195 clicks in 17 s, 27% of them on a 256-sample EP period boundary. The anomalous chunks match the player's own audio exactly one ring lap (17818 samples) earlier.

It reproduces on the bench PC, natively on Windows 11, with the player's version and config. It happens only with the guest threads pinned to one core, the game default `RECOMP_GUEST_CPUS=one`, together with spin pacing (`present.pacing = "spin"`):

| arm (player config, native Windows) | runs | clicking runs | clicks per run |
|---|---|---|---|
| `one` (default), spin | 6 | 5 | 2, 14, 213, 230, 282, 308 |
| core 2 (`=2`), spin | 2 | 2 | 130, 220 |
| `all`, spin | 4 | 0 | 0, 0, 1, 0 |
| `one`, sleep | 2 | 0 | 0, 0 |

On the pinned core, the guest workers that feed the ring get about a quarter of the guest-CPU turns they get on every core (755, 1022 and 29 turns against 2612, 3619 and 953 in one run each). One of them held the guest CPU for 14.1 s of wall time on 15.6 ms of its own CPU, which means it was off the core. The guest CPU lock (`RECOMP_GUEST_LOCK`, on in this game) already runs one guest thread at a time on every host. It closes the light-pool race that the pin was made for, so the pin adds only its dependence on the host scheduler. The user measured `all` equal to the pin under Proton on 2026-10-10 and kept the pin then. **On 2026-11-05 the user decided to make every core the default** ("Yes, make it the default"), reversing that, on the native Windows result.

## What Changes

- cat `src/env/recomp_env_game.h`: the game stops setting `GUEST_CPUS=one`. The toolkit's default (every core) applies. `RECOMP_GUEST_CPUS=one` stays the A/B and the way back.
- docs: the `RECOMP_GUEST_CPUS` row in `docs/env.md`, the README's one-CPU paragraph and the `src/main.c` comment.
- cat `src/main.c` (`host_enhance_init`): on `_WIN32`, `spin` is the code default of `present.pacing` (toolkit `enhance_cfg_set_code_default`), so every tier still wins and the menu's stock value is `spin`. `packaging/config.default.toml` leaves the key out (commented) so the per-build default applies. docs: the `RECOMP_PRESENT_PACING` row, README's frame pacing row, `docs/packaging.md` and `docs/frame-generation.md`.

## Capabilities

### Modified Capabilities
- `kernel-threads`: "A title's threads share one CPU" makes the pin the choice of `RECOMP_GUEST_CPUS=one` or `=<n>`, not the default.
- `enhancements`: "Frame pacing key" makes the default per target build: `spin` in the Windows build, `sleep` elsewhere; `config.default.toml` leaves the key out.

## Impact

- cat, plus one toolkit hook (toolkit branch `fix/enhance-code-default`): `enhance_cfg_set_code_default(key, value)`, a game's code default for a toolkit key, which every typed lookup and the in-game menu's stock value honour. No new key. Without the `pacing` key in `config.default.toml`, `blinx2 package` adds no pacing paragraph to README.txt and prints no note (the CLI's `pacing_sleeps` reads only the defaults file), on every target. Right for the Windows and SteamOS bundles, which spin; the macOS app's README loses its sleep paragraph until the CLI knows the per-target default: a follow-up. It changes what the game executes (thread affinity), so it takes the goldens and a Proton run. The water golden is the one to watch.
- Burnout 3 (`b3/src/env/recomp_env_game.h`) sets the same default and is not changed: the 2026-11-05 decision covers BLiNX 2 only (open question below).

## Frame pacing per build

The user also asked for `present.pacing = "sleep"` as the default if it is stable, and then (2026-11-05): "If windows is the most sensible to pacing, make it a default based on the target build instead". Sleep was already the default (cat 53449a3f, 2026-10-13, fps-pacing D9). The player had set `spin` in their own config.

Measured on this branch (cat a5bc49e5 + the change, the Windows exe built on the PC, run id 15786de87e1f, also the Deck's), golden routes story and stage1, 3 runs per arm alternating, `RECOMP_TRACE=flip,pacing=all`. Spread over the 3D flips after the checkpoint (story: the hub; stage1: the stage); paces as `golden check` measures them:

| host | scenario | arm | p50 ms | p95 ms | p99 ms | frames over 2x p50 | flips/s | paces | process CPU | longest kernel call |
|---|---|---|---|---|---|---|---|---|---|---|
| native Windows 11 | story | spin | 33.35-33.37 | 33.49-33.63 | 33.66-33.84 | 0, 0, 0 | 30.0 | tsedit 59.9-60.2, hub 30.0 | 151-162% | 32 ms |
| native Windows 11 | story | sleep | 33.23-33.41 | 33.56-33.74 | 33.70-33.82 | 0, 0, 0 | 30.0 | tsedit 59.9-60.2, hub 30.0 | 53-59% | 55, 138, 545 ms (NtReadFile) |
| native Windows 11 | stage1 | spin | 33.35 | 33.51-33.57 | 33.74-33.80 | 1, 0, 0 | 29.98-30.00 | 29.8-30.2 | 178-181% | 32-33 ms |
| native Windows 11 | stage1 | sleep | 33.34-33.39 | 33.56-33.66 | 33.70-33.79 | 1, 0, 2 | 29.85-30.00 | 29.0-30.2 | 83-85% | 33, 178, 674 ms (NtReadFile) |
| Deck, Proton (GE-Proton11-7) | story | spin | 33.33 | 33.46-33.68 | 33.54-33.96 | 0, 0, 0 | 30.0 | tsedit 60.0, hub 30.0 | 157-158% | 17-32 ms |
| Deck, Proton | story | sleep | 33.33 | 33.43-33.61 | 33.50-33.90 | 0, 0, 0 | 30.0 | tsedit 60.0, hub 30.0 | 95-97% | 26-32 ms |
| Deck, Proton | stage1 | spin | 33.33 | 33.46 | 33.53-33.55 | 0, 0, 0 | 30.0 | 30.0-30.2 | 184% | 17-18 ms |
| Deck, Proton | stage1 | sleep | 33.33 | 33.44-33.62 | 33.61-33.76 | 0, 0, 0 | 29.98-29.99 | 30.0-30.1 | 138-140% | 26-32 ms |
| Mac, Metal | story | spin | 33.33-33.34 | 33.43-33.44 | 33.47-33.95 | 0, 0, 0 | 30.0 | tsedit 59.9, hub 30.0 | 121-122% | 24-42 ms |
| Mac, Metal | story | sleep | 33.33 | 33.39 | 33.42-33.44 | 0, 0, 0 | 30.0 | tsedit 59.9, hub 30.0 | 26-28% | 32-36 ms |
| Mac, Metal | stage1 | spin | 33.33 | 33.40-33.42 | 33.46-33.47 | 0, 0, 0 | 30.0 | 30.0-30.1 | 138-143% | 24-40 ms |
| Mac, Metal | stage1 | sleep | 33.33 | 33.39-33.40 | 33.44-33.59 | 0, 0, 0 | 30.0 | 30.0-30.1 | 47-51% | 30-35 ms |

The pace checks hold in both arms on every host, and flips/s never drop past 0.5%. The frame spread is the same within a few tenths of a millisecond. Native Windows is the one host where sleep is worse: in 4 of 6 sleep runs a guest `NtReadFile` took 138-674 ms on the host (the guest CPU's "longest call taken straight back", so host time, not a wait for the CPU), against 33 ms at most in the 6 spin runs. One of them was on the main thread in the middle of stage 1 and froze the game for 424 ms (flip 870 of the third sleep run, its only frame over 100 ms after the stage start). The others were on a streaming thread or during loads. Not proven: why the host read stalls. Timer resolution is set (`timeBeginPeriod(1)`, and the process opts out of timer-resolution throttling); the likely cause is the CPU's idle states and core parking once the process stops holding a core, which spin prevents. The PC's Windows exe under Proton on the Deck does not show it: Proton does not behave like native Windows here, and the Deck gets the Windows default only because it runs the same exe.

So the default depends on the target build: `spin` in the Windows exe (native Windows and Proton), `sleep` in the macOS build. The Deck keeps spin's CPU cost (about 157% against 97% at sleep), the price of one exe for both hosts.

## Open questions

- Burnout 3: does its `GUEST_CPUS=one` default go too? It has the guest CPU lock question of its own (the tracker item's lock × guest_sched × CPUs matrix is the place to settle it).
- Native Windows: why the host read stalls at sleep pacing (CPU idle states, core parking, or a filter driver). A toolkit fix there (a power request, a timer, a thread-priority hint during I/O) would let Windows sleep too.
