## Why

Six small CLI and export problems are left from the 2026-10-06 disk audit and the 2026-10-07 merges. Each one costs disk, hides data, lets a bad build through, or makes the public tree read badly.

1. **The bench-logs store only grows.** The disk audit (`xbox-recomp/notes/disk-audit-2026-10-06.md`) found about 21 GB of unreferenced runs in the Mac store and 32 GB on the Linux/Proton host whose runs are all in the Mac store as well. Root causes 2 and 3 there say why: `bench logs` pulls and leaves the host copy, and nothing removes a run that no doc names. The audit's reference scan is the prototype for a tool. `benchlog-retention` exists, but it does not see the host or live worktrees' notes, does not keep runs per scenario, and does not know which game a run in the shared store belongs to (the store holds BLiNX 2 and Burnout 3 runs). Since the audit, the user ran its Mac tier-1 line: the store now holds 340 stamp runs, of which 116 are referenced, 208 are the audit's tier 2 (2026-10-05..06) and 16 are newer.
2. **`bench golden` keeps every frame dump.** Root cause 3: 471 Mac runs carry frames (19 GB), and each host run keeps its whole `fb_dump_at` window plus a dump every 60 presents (150-230 MB a scenario). A passing check reads only the frames it compares.
3. **`blinx2 recomp` never passes `--seeds`.** The toolkit's `recomp` takes `--seeds JSON` (toolkit b0eb653) so that its flag-fallback report lists the sites inside seeds marked `"observed": true`. The CLI's `recomp_cmds` does not pass it, so under the CLI that list is always empty.
4. **The golden engine hardcodes a game key.** `ENHANCE_STOCK` in `xboxrecomp_cli/golden.py` holds `fps.mode`, a BLiNX 2 key, and lacks `fx.glow` and `fx.glow_intensity` (glow-toggle archive, task 7.4). So a glow-off run is not caught as non-stock, and `--allow-enhance fx.glow=off` is refused.
5. **The public export reads badly in places.** `scripts/export-public.sh`'s catch-all rules put a second "the" before "Linux/Proton host" in "the Linux/Proton copy" and "every Linux/Proton run", and after "allowed" in "the next allowed Linux/Proton session" (TASKS.md line 47).
6. **A stale gen/ reaches the linker.** gen/ is untracked, and `gen.key.json` already records what it was generated from (toolkit commit, the hash of uncommitted `tools/` edits, the sha of `recomp_manual.c`), but only `package` reads `gen_stale_reasons()`. `build.build()` requires only `recomp_funcs.h`, and `bench integrate` checks only that gen/ is non-empty and that the host's digest matches the local one. The 2026-10-07 integrate linked a duplicate `sub_0005B7D0` because main's gen/ predated the wrap fix (Fable review `notes/fable-reviews/2026-10-07.md`, section 2, should-fix). The key also keys its committed half on the toolkit's `HEAD`, so a runtime-only toolkit merge would report "toolkit changed" against the docstring's own intent.

## What Changes

- **New `<game> bench gc`** (dry run by default, `--apply` removes). It lists stamp-named runs in the local store and, with `--host`, in the bench host's store, with their allocated sizes. It removes only runs that every protection rule leaves unprotected (design D1). Protected runs:
  - runs of another game (their run-info names another exe), and runs of no known game (no run-info, or none naming an exe);
  - runs named in golden.json, audio.json, TASKS.md, RESUME*.md, OPEN_QUESTIONS.md and openspec/, in every worktree of the game repo, and in the extra reference paths game.toml lists (cat lists `timeline`, `../notes`, `analysis`, `docs`, `README.md`);
  - runs still being written or half pulled;
  - runs younger than D days;
  - the newest N runs per scenario and run kind;
  - on the host, any run the local store has not got in full.
  On the host it runs under the exclusive run lock. It refuses to run at all when a reference source is missing from the main checkout, or when the worktree list cannot be read.
- **`bench golden` prunes a passing scenario's frames.** When a scenario passes (its run ended cleanly, it presented no foreign surface, its frames were EXACT or CLOSE, and the toolkit tests passed), the run keeps the images the verdict read and the plain dumps a later re-record reads; the other flip dumps go, and so does the run's `frames/` on the host. `BENCH_KEEP_FRAMES=1` or `--keep-frames` keeps everything. It never prunes on `--record`, FAIL, INCOMPLETE (NEWVIEW included) or INCONCLUSIVE. Pruning is on by default, as the audit recommends; CLOSE counts as a pass (design D2 says why).
- **`recomp --seeds`**: `recomp_cmds` passes each `pipeline.seeds` file as `--seeds`, when the toolkit's `recomp` defines the flag.
- **`[golden] enhance_stock` in game.toml**: a table of game enhancement keys and their stock values. The engine checks those keys, plus the toolkit's own keys, which stay built in (`render.scale`, `display.aspect`, `present.pacing`). cat's game.toml gets `fps.mode = "lock30"`, `fx.glow = "on"` and `fx.glow_intensity = "1"`.
- **export-public REWRITE**: determiner-aware rules, so "every Linux/Proton run" reads as "every Linux/Proton run". The "no bench host left" check stays and a "the the" check joins it. `scripts/test_export_public.py` gets cases.
- **Stale gen/ refused** (design D6): `build.build()` and `bench integrate` call `pipeline.gen_stale_reasons()` and refuse with the reasons and the `<game> analyze && <game> recomp` hint; `--stale-gen-ok` overrides. The key's committed half becomes the tree ids of `tools/` and `templates/runtime/`, so a runtime-only toolkit merge does not stale gen/ and a lifter or template change does.
- **cat pins the new CLI** in `game.toml` (`[cli] commit`), with the `enhance_stock` and `bench.gc` entries in the same commit (unknown keys are manifest errors, so they cannot land earlier).

Non-goals:
- removing agents' extra host trees (`BENCH_DIR=~/<name>`, audit root cause 4) or B3 gate trees; gc touches only the configured host store;
- compressing runs (that is `benchlog-retention`; it stays as it is);
- loose files and non-stamp-named entries in the store (gc lists their total and never touches them);
- automatic pruning of Mac (Metal) golden runs: they are made by hand (the game run with the scenario's dump env, then `blinx2 golden check`). The engine's new `prune` subcommand (design D2) can be run on them by hand, as a user `!` line; nothing calls it for them;
- `bench logs` removing the host copy after a pull (audit root cause 2): a follow-up, once gc has been used for a round;
- a stale check in `bench sync` or `bench build`: a dev loop may ship a deliberately stale gen/ to the host; `integrate` is the gate.

## Capabilities

### New Capabilities
- `bench-gc`: listing and removing unreferenced bench runs, locally and on the bench host.

### Modified Capabilities
- `bench-methodology`: golden runs keep only the compared and recordable frames of a passing scenario; the game's enhancement keys come from game.toml; the integration build refuses a stale gen/.

## Impact

- **Repos:** xboxrecomp-cli (gc, frame pruning, seeds, enhance_stock, stale-gen refusal, manifest keys, docs/manifest.md, README/help); cat (game.toml pin and keys, export-public.sh, test_export_public.py, docs/env.md, TASKS.md). The toolkit is not touched, so nothing here is meant for upstream. b3 needs no change: it has no enhancements layer, its seeds pass through on its own pin, and the new `bench.gc` keys have defaults. Its pin moves when b3 next bumps.
- **Backends, hosts and goldens:** no renderer, runtime, audio or kernel change. CPU, D3D11 and Metal output is unchanged. The D3D11 goldens run through the changed `bench golden`, so one `blinx2 bench golden` on the Linux/Proton host checks the pruning end to end (the orchestrator queues it). The Metal goldens are unaffected. With `enhance_stock` from game.toml, the engine's stock check covers the same keys as today, plus the two glow keys.
- **One regenerate after the pin bump.** `--seeds` changes the gen key's `argv` hash and D6 changes its `toolkit` field (key version 2), so the first `blinx2 build`, `package` or `bench integrate` on the new pin reports gen/ stale until `blinx2 analyze && blinx2 recomp` has run once. gen/ comes out byte-identical (task 3.3 checks). The orchestrator regenerates main's gen/ right after the merge, before the Linux/Proton integrate.
- **Disk:** the audit's remaining Mac runs (tier 2) and the Linux/Proton tier lists become one `gc --apply` (Mac) and one `gc --host --apply`, each built from a reviewed dry run. The user runs these as `!` commands; no agent runs `--apply` on a real store.
- **Public CLI repo:** every fixture is synthetic (no real run-info.txt: the real ones carry the Mac host name and home paths; no committed `.bmp`/`.png`: `audit-public.sh` blocks them). Host scripts and help text name no host.
