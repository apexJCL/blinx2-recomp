# Change: Compile the game's shaders before the frame that needs them

Revised after the review of 6f82a98
(`runs/shaderpc/REVIEW-spec.md`). Both GPU backends build a shader on the
render (ack) thread the first time a vertex program or combiner state is
seen, so the first frame that needs a new one waits for the compiler. This
change gives the toolkit a game-agnostic shader record and key, a trace
that names every shader a run used, a background preload of a record list
at boot adopted inside the caches' own miss paths, and a per-player index
of what was used that becomes the next launch's list; the CLI harvests the
game's list from golden and replay logs and cat ships it privately.

## Why

- **The hitch is measured, on both backends, at the same place.** In every
  BLiNX 2 Proton golden run of 2026-10-13 the first 3D frame of stage 1-1
  (the fly-over, flip 774 of `@stage1`, flip 902 of `@attract`) took **875
  and 890 ms** against the 33 ms around it, with **27 vertex programs**
  compiled inside that one frame (`[d3d11] compiled` lines between the two
  `[GPU] flip` lines) and the combiner count going from 2 to 10 in the same
  window: about **30 ms per vertex shader** through Wine's `d3dcompiler_47`
  and DXVK. Later single compiles cost 50-83 ms frames. The story scenario
  shows the same at the hub (242 ms with 8 compiles). Burnout 3 pays it too
  (251 and 274 ms frames with 7 and 8 compiles, `bench-logs/20261013-133515`).
  On the Mac the operator felt the slowdown at the 1-1 response event,
  where the fragment count went from 14 to 20 (`game-20261013-185821.log`),
  and not on the second launch, which macOS's per-binary shader cache
  served. A timing build (design § Measurements, `runs/shaderpc/`) put
  numbers on it: with that cache cold, a vertex program compiles in **9 ms**
  and a combiner shader in **120 ms** (M4 Max), the stage-start frame took
  **1182-1353 ms** with 1.1-1.3 s of compiles, stage 1-1's set is 1.5 s in
  all, and the pipeline-state build is 0.1-0.2 ms even with a cold
  per-binary cache (`coldbin-1`); on the next launch every compile is 0 ms
  and the frame 79 ms. Compiling ahead of the frame is what helps;
  caching compiler output is not what the Mac needs.
- **Nothing compiles ahead, and nothing survives the process.** Metal keeps
  `s_vs`, `s_fs` and `s_pso` for the life of the process
  (`nv2a_pb_metal.m`, `compile_fn` and `pipeline()`); D3D11 keeps `s_vs`
  and `s_rc` (`nv2a_pb_d3d11.c`, `vertex_shader` and `combiner_ps`). Each
  compile runs where the draw runs. The only cross-launch help is the host's
  own: macOS's shader cache, and under Proton the Mesa disk cache for the
  driver half; DXVK 2.4 and later keep no state cache, so the HLSL half
  (`D3DCompile`) is paid on every launch.
- **The inputs are already small and backend-neutral.** A vertex shader is a
  function of the program dwords from the start slot to FINAL
  (`nv2a_vsh_program_hash`, `d3d8_vsh_parse`), a fragment shader of 36
  register and mode dwords plus a render-scale class (the backends' own
  `key[37]` in `fs_select` and `setup_pixel`). The same record generates the
  HLSL and the MSL, so one list serves both backends. The review checked the
  generators: no other state reaches the text today, and the design adds a
  check at adoption for the day one does.
- **The data is game-derived.** The records embed the title's vertex-program
  microcode. Under CLAUDE.md's legal rules that is derived game data: it can
  be harvested and used on the owner's machines and never published, like
  `src/recomp/gen/` and the golden frames.

## What Changes

- **Toolkit (game-agnostic):** one record format (`vs`, `fs` lines; `pso`
  reserved), a `RECOMP_TRACE=shaders` trace that prints each record at its
  first **use** with how it was obtained (`preloaded` or `on-demand` with
  stage times), `RECOMP_SHADER_PRELOAD=<file>` (one background thread
  compiles the records of a list from device-up into a staging table; the
  ack thread takes from it exactly where each cache would have compiled,
  after checking the staged source matches the live one) and
  `RECOMP_SHADER_CACHE=<dir>` (an append-only, never purged index of the
  records this player's runs used, preloaded on the next launch). Misses
  compile on demand exactly as today. With both keys unset or empty nothing
  changes. No compiler output is persisted: the DXBC blob store and Metal
  pipeline records are follow-ups with the requirements the review set.
- **CLI (game-agnostic):** `xbr shaders harvest LOG|index.txt ... -o list`
  merges first-use records from logs and indexes; `xbr shaders stats`
  counts them; `game.toml` gains an optional `[shaders] list`; `xbr
  package` bundles the list when present; the steamos and Windows launcher
  templates set the two keys only when the player's `launch.env` has not.
- **cat (game data and packaging):** `analysis/shaders/preload.txt`, the
  union of the golden harvests and one operator session on the Mac (the
  user's choice; `playthrough-replay` can refresh it later), gitignored
  with `analysis/`; `game.toml [shaders]`; the macOS launcher sets the keys
  under the same rule; `docs/env.md` rows; `docs/packaging.md` names
  `cache/`; the public-export audit greps for the `# xbr-shaders` marker.
- **Burnout 3:** nothing to write; its steamos and Windows launchers are the
  CLI's templates, its macOS `.in` gets the same lines, its list is
  harvested from its own bench runs.

## Capabilities

### New Capabilities
- `shader-precompile`: the record format and key, the first-use trace, the
  preload and its adoption rule, the per-player index, its home per host,
  threading, and where the game's list lives.

### Modified Capabilities
- `deployment`: the user-data root gains `cache/`, which installers never
  touch and the player may delete; the launchers set `RECOMP_SHADER_CACHE`
  and, when the bundle carries a list, `RECOMP_SHADER_PRELOAD`, only when
  the player has not defined them; `BLINX2_DATA_DIR` moves the cache with
  the rest.

## Impact

- **Backends:** D3D11 (Windows and Proton) and Metal, symmetrically: the
  same records, trace, preload thread, staging table, adoption rule and
  index. The CPU rasteriser has no shaders and only has to keep building.
- **Hosts:** Mac (Metal), Proton on the Linux/Proton host and the Deck (D3D11), native
  Windows untested as always.
- **Goldens:** identical. The golden environment pins neither key, and the
  code paths with the keys unset are today's. Task 4.2 runs the Metal and
  D3D11 goldens with a filled index and the list to show every verdict
  unchanged, and gates the launchers' default-on and the CLI's public round.
- **Toolkit:** yes, `posix-host/portability`: a new `src/d3d/nv2a_shader_cache.c`
  (records, index, staging table, the preload thread) and glue in both
  backends. Upstreamable as a PR of the GPU series after G6/G7 (plain
  `getenv`, `RECOMP_SHADER_TRACE=1` for the trace), not before: it has
  nothing to attach to upstream until the backends land. The
  `pr-stack-plan.md` row is an orchestrator step (task 5.1).
- **Stock behaviour:** unchanged with the keys unset. The packaged launchers
  set `RECOMP_SHADER_CACHE` (design D8 argues it stock-neutral: nothing
  persisted but a list of inputs, the same compiler in the same process,
  every adopted object checked against the live source), the same way the
  packaged app sets `RECOMP_HOST_PAD=1`; the player's `launch.env` wins.
- **Performance:** the first frame of a new scene no longer carries the
  compiles the list covers; the background thread competes for a core
  during the first seconds after boot (the intro movies). Measured in tasks
  4.1 and 4.3 on both hosts.
- **Legal:** the list, the index and a log with the `shaders` trace on are
  derived game data: never in the public repos, never tracked, so never
  in `blinx2 public export`'s tree; `scripts/test_gitignore.py` asserts the
  list is ignored, and the content marker becomes a public-audit check (in
  the CLI or in `audit-private`).
