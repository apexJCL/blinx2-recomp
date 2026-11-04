## ADDED Requirements

### Requirement: A shader is identified by a backend-neutral record of its inputs
The toolkit SHALL describe every GPU shader the pushbuffer backends build by a one-line text record of the guest inputs it is generated from, never of the generated source or binary: `vs <start> <n> <hex dwords>` for a vertex program (the `n` slots from `start` to the FINAL slot, four dwords each, the bytes `nv2a_vsh_program_hash` hashes and `d3d8_vsh_parse` reads) and `fs <36 hex dwords> <scale-class>` for a register-combiner state (`rc_cicw[8]`, `rc_aicw[8]`, `rc_cocw[8]`, `rc_aocw[8]`, `rc_ctl`, `rc_fcw0`, `rc_fcw1`, the stage-modes word the backends derive from `s_stage[n].mode` and `raw_mode`, then 0 or 1 for `nv2a_host_render_scale() > 1`), the inputs `d3d8_combiners_from_regs` and the generators consume. A record's key SHALL be the 64-bit FNV-1a of its text, so the same record has the same key on D3D11 and Metal and across launches; each in-process cache entry SHALL keep its record's key. Record files SHALL start with `# xbr-shaders 1` (the format version, covering the syntax only) and MAY hold `#` comments; a line of an unknown kind (the reserved `pso`) or that fails to parse SHALL be skipped with one log line, never refused. The record SHALL contain no host path, no game name and no guest address. The toolkit SHALL hold a `_Static_assert` on `sizeof(NV2ACombinerState)` and on `sizeof(NV2AVshProgram)` whose message says a new field must be classified as a generator input and the record format moved if it is one.

#### Scenario: Same record, both backends
- **WHEN** the D3D11 and Metal backends compile the shaders for the same batch of `@stage1`
- **THEN** the `vs` and `fs` records they log are byte-identical and the HLSL and MSL they generate come from those records alone

#### Scenario: Round trip in a ctest
- **WHEN** `tests/nv2a_shader_cache` formats a record from a synthetic `nv2a_pb_vsh` state and synthetic combiner registers, parses it back and regenerates the source
- **THEN** the parsed program dwords and registers equal the originals, the generated source is byte-identical to the one generated from the live state, the key equals a fixed test vector, and an unknown-kind line and a torn line are skipped while the lines after them load

### Requirement: A trace names every shader a run uses, at its first use
With `RECOMP_TRACE=shaders` (toolkit trace key), the ack thread SHALL print one `[SHADER] <record> ; preloaded` or `[SHADER] <record> ; on-demand <stage> <ms> ..` line per record key at that key's first use in the run (stages `generate`, `compile`, `create` on D3D11; `library` on Metal, plus `pipeline <ms>` when a pipeline state is built), and one `[SHADER] summary: N vs, N fs, N preloaded, N on demand, <ms> on the ack thread` line in each present summary. The preload thread SHALL print only `[SHADER] preload: <record> failed: ..` once per failing record and one `[SHADER] preload: N built, M skipped, T ms` line at its end. The trace SHALL print only; nothing else changes with it on. The game's environment document SHALL say that a log written with this trace holds the title's vertex-program microcode and is not for public issues.

#### Scenario: Harvestable log
- **WHEN** `@stage1` runs on Metal with `RECOMP_TRACE=flip,shaders` and no preload
- **THEN** every function the present summary counts (`shaders N vs + N fs`) has exactly one `[SHADER] vs .. ; on-demand` or `[SHADER] fs .. ; on-demand` line, and `xbr shaders harvest` on the log yields that many records

#### Scenario: Preloaded records are not harvested unless used
- **WHEN** the same run has `RECOMP_SHADER_PRELOAD` naming a list with records the run never draws
- **THEN** those records appear in no `[SHADER]` first-use line, only in the preload summary's count, and `harvest` on the log does not contain them

### Requirement: A record list is compiled ahead of use on a background thread and adopted where the cache would have compiled
With `RECOMP_SHADER_PRELOAD=<file>` (toolkit config key) or a non-empty `RECOMP_SHADER_CACHE`, the active GPU backend SHALL, once its device is up, start one background thread that reads the list and then the cache index, de-duplicates by key, and builds each record in order (D3D11: generate HLSL, `D3DCompile`, `ID3D11Device_CreateVertexShader` or `CreatePixelShader`; Metal: `newLibraryWithSource` and `newFunctionWithName`) into a staging table under a mutex, with the FNV-64 of the source it generated. The thread SHALL use only free-threaded API (the `ID3D11Device` creation methods, `D3DCompile`, the `MTLDevice` creation methods), its own buffers and counters, an `@autoreleasepool` per record on Metal, SHALL never touch the immediate context, an encoder, a render target, the texture cache, guest memory or an ack-thread counter, SHALL run unpinned at utility (macOS) or below-normal (Win32) priority, and SHALL hand over +1 references. The ack thread SHALL take from the staging table only at the point where each cache already generates and compiles (`vertex_shader`, `combiner_ps` after its eviction and `s_rc_compiles` update, `vs_cache`, `fs_select`), after regenerating the source from live state and comparing its hash: on a match it adopts the object, on a mismatch it logs `[SHADER] preload: record <key> disagrees with live state` once, drops the object and compiles on demand. A key the ack thread builds on demand SHALL be marked in the staging table so the preload thread skips it; the ack thread SHALL never wait for an in-flight record. Staging SHALL be bounded per kind by the backend's cache capacity, list first then index newest first, the cut logged once. A record that fails to build SHALL be logged once and skipped. `nv2a_shader_preload_stop`, registered with `recomp_exit_hook_add` and `atexit`, SHALL set a stop flag, join for at most 250 ms, close the index and release un-adopted objects. With both keys unset or empty no thread SHALL start and the backends SHALL be byte-for-byte today's.

#### Scenario: Stage start without compiles
- **WHEN** `@stage1` runs under Proton with `RECOMP_SHADER_PRELOAD` naming the list harvested from a previous `@stage1` run and `RECOMP_TRACE=flip,shaders`
- **THEN** the first 3D flip of the stage (the `first-3d` anchor) has only `; preloaded` first-use lines between it and the flip before, its interval is within 2x the median 3D interval of the run (the reference run paid 875 ms), and every verdict of the golden frames is unchanged

#### Scenario: A missing list
- **WHEN** `RECOMP_SHADER_PRELOAD` names a file that does not exist or has only the header
- **THEN** one `[SHADER] preload: list ..` line says so, the list is skipped, the cache index (if any) still preloads, and the run is otherwise today's

#### Scenario: Disagreeing record
- **WHEN** a ctest hands the ack-thread adoption path a staged object whose source hash differs from the live regeneration
- **THEN** the object is released, the on-demand compile runs, the disagreement line is printed once, and the frame is the one the on-demand path draws

#### Scenario: Thread safety in the smoke tests
- **WHEN** `nv2a_backend_smoke` (Metal, built with `-fsanitize=thread`) and `d3d11_backend_smoke` (Proton) run with a preload list built from their own scenes while drawing them, and the staging ctest runs put/take/tombstone from two threads for 10k rounds under TSan
- **THEN** every frame equals the run without the list and no race is reported

#### Scenario: Two compilers at once under Proton
- **WHEN** a Proton ctest compiles the same 200 synthetic HLSL sources on two threads concurrently and once serially
- **THEN** the blobs are byte-identical between the two runs and no compile fails

### Requirement: A per-player index remembers every shader used, append-only, never purged
With `RECOMP_SHADER_CACHE=<dir>` (toolkit config key) non-empty, the active GPU backend SHALL keep `<dir>/index.txt`, a record file with the header `# xbr-shaders 1 backend=<d3d11|metal>` (provenance; the records are read by either backend), and SHALL append each record at its key's first use in the run when the key was not in the index read at start, as one `write()` on an `O_APPEND` descriptor (POSIX) or one `WriteFile` on a `FILE_APPEND_DATA` handle (Win32) holding the whole line and its newline. The reader SHALL skip a line that fails to parse or lacks its newline, logging once and never purging. The index SHALL be preloaded on every launch after the list, newest record first. Housekeeping SHALL run on the preload thread at its start only: an index with more than 4096 records of a kind is rewritten keeping the newest 4096 through a temporary file and a rename; nothing else is deleted, and no header field (including a generator version) SHALL cause a purge. A directory that cannot be created or written SHALL be logged once and ignored. An empty value SHALL mean unset. No compiler output SHALL be persisted in this change.

#### Scenario: Second launch compiles nothing it has seen
- **WHEN** `@stage1` runs twice under Proton with the same `RECOMP_SHADER_CACHE` directory and `RECOMP_TRACE=shaders`
- **THEN** the second run's first-use lines for the records of the first run say `; preloaded`, the index gained no duplicate lines, and the golden verdicts of both runs are the same

#### Scenario: Torn line survives
- **WHEN** the index's last line is cut mid-record (a crash) and the game launches again
- **THEN** one `[SHADER] cache: skipped 1 bad line` appears, every other record preloads, and the next first use appends after the torn line

#### Scenario: Over the cap
- **WHEN** the index holds more than 4096 `vs` records at launch
- **THEN** the preload thread rewrites it keeping the newest 4096 before the ack thread's first append, and the run goes on

#### Scenario: Empty value is off
- **WHEN** the game runs with `RECOMP_SHADER_CACHE=` (empty) and no preload list
- **THEN** no `[SHADER] cache:` line is logged, no directory is created, no thread starts

### Requirement: The index lives in the player's data root, per host, and goldens never see it
The packaged launchers SHALL set `RECOMP_SHADER_CACHE` to `<data root>/cache/shaders`: `~/Library/Application Support/<App>/cache/shaders` on macOS, `%LOCALAPPDATA%\<App>\cache\shaders` on Windows, `Z:<root>/cache/shaders` on steamos (outside the Wine prefix, as `hdd/`), following `<App>_DATA_DIR` when it is set; and, when the bundle carries a record list, `RECOMP_SHADER_PRELOAD` to it. Each SHALL be set only when the variable is not defined at all after the launcher's `launch.env.default` and the player's `config/launch.env` have loaded, so the player's line wins and `RECOMP_SHADER_CACHE=` turns the cache off. Installers, updates, rollbacks and uninstalls SHALL never create, read or write `cache/`; the player MAY delete it at any time. The runtime's own defaults for both keys SHALL stay unset, so the golden scenarios (whose environment pins neither key), `blinx2 bench`, the ctests and every run that does not set them are byte-for-byte today's. A verification run SHALL pass the keys as plain `VAR=val` arguments of `golden run` or through `BENCH_ENV`; no new runner flag is added.

#### Scenario: Goldens unchanged by default
- **WHEN** `blinx2 golden run --backend metal` and `blinx2 bench golden` run after the merge
- **THEN** their `run-info.txt` shows neither key, no `[SHADER]` line appears without the trace, and every verdict is the one before the merge

#### Scenario: Goldens unchanged with a filled index and the list
- **WHEN** the same scenarios run with `RECOMP_SHADER_CACHE=<dir>` naming a directory filled by a previous run and `RECOMP_SHADER_PRELOAD` naming the harvested list
- **THEN** every frame gets the same verdict and the per-frame limits are met by the same margins within noise

#### Scenario: Redirected data root
- **WHEN** the macOS launcher runs with `BLINX2_DATA_DIR=/scratch/d`
- **THEN** `RECOMP_SHADER_CACHE` is `/scratch/d/cache/shaders` and nothing under the real Application Support folder is created

### Requirement: The game's record list is harvested by the CLI and stays private
`xbr shaders harvest INPUT... -o LIST` SHALL read `[SHADER]` first-use lines from run logs (ignoring `preload:` and `summary:` lines) and records from record files (`index.txt`, another list), keep one copy of each record in first-seen order, keep unknown kinds verbatim, refuse an input whose records fail to parse (exit 2, naming file and line), and write a record file; `xbr shaders stats LIST` SHALL print the counts per kind. The CLI SHALL know no game: its tests use synthetic records (made-up dwords, no game output). `game.toml` MAY hold `[shaders] list = <path>`; `xbr package` SHALL copy the file into the bundle when it exists and the launcher templates SHALL export `RECOMP_SHADER_PRELOAD` only when the bundled file is present. In cat the list SHALL live at `analysis/shaders/preload.txt`, gitignored with `analysis/*`, so `export-public.sh` never sees it, and `scripts/test_gitignore.py` SHALL assert it; the public-push audits (`export-public.sh`'s checks and the CLI's `scripts/audit-public.sh`) SHALL grep for the content marker `# xbr-shaders` as well as the paths `analysis/shaders` and `cache/shaders`. The record list and the per-player index are derived game data (vertex-program microcode and register state) and SHALL never be committed to a public repo or shipped in a public bundle; the owner's private bundles MAY carry the list.

#### Scenario: Harvest from logs and an index
- **WHEN** `xbr shaders harvest a.log b.log index.txt -o preload.txt` runs on synthetic inputs where `b.log` repeats two records of `a.log` and `a.log` also holds `preload:` lines
- **THEN** the output holds the header, every distinct first-use record once in first-seen order, none of the `preload:` lines, and `stats` reports the counts per kind

#### Scenario: List never tracked
- **WHEN** `analysis/shaders/preload.txt` exists in cat
- **THEN** `git check-ignore analysis/shaders/preload.txt` exits 0, `git status` is clean, `scripts/test_gitignore.py` passes, and a file holding `# xbr-shaders` anywhere in the export is refused by the audit

#### Scenario: Game without a list
- **WHEN** a `game.toml` has no `[shaders]` table, or names a file that does not exist
- **THEN** `xbr` validates it, `xbr package` bundles no list and the launcher exports no `RECOMP_SHADER_PRELOAD`
