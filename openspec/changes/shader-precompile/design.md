# Design: shader-precompile

Revised 2026-10-13 after the review (`runs/shaderpc/REVIEW-spec.md`):
the DXBC blob store and the `pso` records left v1 (Follow-up), adoption
happens inside the existing miss paths, the index is append-only and
never purged, and the trace and index are driven by first use.

## Context

The pushbuffer backends translate guest state into host shaders at run time
and compile each one where the draw happens:

| | D3D11 (`nv2a_pb_d3d11.c`) | Metal (`nv2a_pb_metal.m`) |
|---|---|---|
| vertex program | `vertex_shader()`: `d3d8_vsh_parse` + `d3d8_vsh_generate_hlsl_ex`, `compile()` = `D3DCompile(.., "vs_5_0", OPTIMIZATION_LEVEL3)`, `CreateVertexShader`; input layouts per stream-format set on first draw | `vs_cache()`: `d3d8_vsh_generate_msl`, `compile_fn()` = `newLibraryWithSource` + `newFunctionWithName` |
| combiners | `combiner_ps()`: `d3d8_combiners_generate_hlsl`, `compile()` `ps_5_0`, `CreatePixelShader`; `RC_MAX` 64, LRU, `s_rc_compiles` and `s_state_gen` drive the `setup_pixel` memo and the state cache | `fs_select()`: `d3d8_combiners_generate_msl`, `compile_fn()`; `FS_MAX` 512 |
| pipeline | blend, depth and rasteriser states (cheap objects); DXVK links the pipeline at the draw | `pipeline()`: `newRenderPipelineStateWithDescriptor` per `PsoKey`; `PSO_MAX` 512 |
| key today | `nv2a_vsh_program_hash` (FNV-1a of the program dwords from `start` to FINAL), `rc_hash` of `NV2ACombinerState` | the same program hash, `fnv` of the state, function pointers plus six dwords for the PSO |
| generator inputs | the parsed program plus a constant flag; for combiners the seven register arrays and the stage-modes word (`d3d8_combiners_from_regs`) plus two backend flags set afterwards, `fog_input = 1` and `rect_snap` = render scale > 1 | the same |
| lifetime | process | process |
| thread | the NV2A ack thread only; `init()` creates the device with flags 0 and loads `d3dcompiler_47` before any draw | the NV2A ack thread only; `s_opts` made in `init()`; MRC (`[x release]`) |
| exit | the window's close runs `recomp_exit_hook_run` then `ExitProcess` | nothing of its own |

Below the backends sit the hosts' own caches: macOS keeps a per-binary
shader cache keyed by source and options (the operator's second launch was
smooth); under Proton, DXVK 2.4 and later keep no state cache, DXVK turns
DXBC into SPIR-V synchronously inside `Create*Shader` on the calling thread
and compiles the pipeline library on its workers, and Mesa's disk cache
covers the driver half, but Wine's `D3DCompile` (vkd3d-shader's HLSL front
end) runs again on every launch.

## Measurements

All numbers from existing runs in `bench-logs/`, the operator's Mac logs,
and the timing build, read on 2026-10-13 with `runs/shaderpc/flipan.py`
(flip intervals from the `[GPU] flip N T ms` timestamps, compiles from the
`[d3d11] compiled` lines in between, combiner counts from the present
summaries) and `runs/shaderpc/spc-sum.py`. The Linux/Proton host was down during this
spec, so no new Proton run was taken; the 1-2 checkpoint run is
task 0.3.

**Proton, BLiNX 2 (the Linux/Proton host, GE-Proton11-7, D3D11), golden runs of
2026-10-13:**

| run | scenario | frame | interval | compiles in that frame | note |
|---|---|---|---|---|---|
| 193404 | `@stage1` | flip 774 (the first 3D frame of 1-1, 6091 batches) | **875 ms** | 27 vertex programs; combiners 2 to 10 in the same 300 flips | every `@stage1` run of the day shows the same frame |
| 193404 | `@stage1` | flips 775, 777, 818, 1048 | 53, 83, 42, 50 ms | 1, 4, 1, 1 | single programs met during play |
| 193245 | `@attract` | flip 902 (attract's first 3D frame) | **890 ms** | 27 | |
| 193245 | `@attract` | flips 1070, 1779 | 70, 63 ms | 3, 2 | |
| 193555 | `@story-hub` | flip 3954 (`script done`, the hub) | 242 ms | 8 | flips 1976, 1927, 778: 134, 77, 94 ms with 4, 3, 4 |

So about **30 ms per vertex shader** on this host (D3DCompile at
optimisation level 3 plus DXVK's own compile at `CreateVertexShader`; the
split between the two is task 0.3's `compile`/`create` stage times), and
the first frame of a scene carries 25-30 of them. The run's other 3D frames
sit at 33 ms. 37 vertex programs and 10 combiner states cover `@stage1`,
41 and 10 `@attract`, 22-24 and more combiners the story hub. The
operator's Deck slowdown right after the 1-2 checkpoint fits
this shape (new shaders at a scene change) but is not yet measured.

**Proton, Burnout 3** (`20261013-133515`, pacing series): flips 13237 and
14402 took 251 and 274 ms with 7 and 8 vertex-program compiles each;
flip 13240 took 137 ms with 2. The same cost per shader.

**Mac, Metal, operator logs:** `game-20261013-185821.log`, fragment count
14 to 20 between presents 6600 and 6900 at the 1-1 response event, the
hitch felt there; `game-20261013-191220.log` (second launch, `pacing=all`),
no gap over 33.6 ms and no new fragment shader near the event. Golden run
`20261013-124538-metal-stage1`: flip 763 (the stage's first 3D frame)
78 ms with 34 vertex and 8 fragment functions compiled between presents
600 and 900, on a warm system cache. (That log also shows 90-131 ms frames
every 5.0 s from flip 1444 on, each right after a 38 KB `[READ]`; not
shader work, noted for the tracker item's host contrast and left alone here.)

**Mac, Metal, timing build** (toolkit worktree `spike/shaderpc-timing`,
never merged: a `shaderpc:` line per `newLibraryWithSource` and per
`newRenderPipelineStateWithDescriptor`), `@stage1` headless, M4 Max,
macOS 27, 100 s runs under `runs/shaderpc/`:

| run | how the cache was made cold | vertex (37) | combiners (10) | PSO (61) | stage-start frame |
|---|---|---|---|---|---|
| `cold-1` | `SHADERPC_COLD`: a nonce comment in each source (front end cold, back end not: the AIR is unchanged) | **8.8 ms** median (4.8-12.6; 11 KB MSL) | **120 ms** median (117-124; 7.6 KB MSL) | 0.1 ms | flip 765: **1182 ms**, 1105 ms of it compiles (34 vs + 8 fs) |
| `warm-1` | same binary 100 s later | 0.0 ms (max 0.9) | 0.0 ms (max 0.1) | 0.1 ms | flip 770: 79 ms with 4 ms of compiles |
| `coldbin-1` | the binary copied to a new path (macOS keys its per-process shader cache on the binary's identity), no nonce | 9.0 ms median | 121 ms median (max 238) | **0.1 ms median, 0.2 ms max** | flip 765: 1353 ms, 1277 ms compiles |
| `coldbin-2` | same copy 100 s later | 0.0 ms (max 0.1) | 0.0 ms (max 0.1) | 0.1 ms | flip 764: 78 ms with 2 ms of compiles |

Read: on the Mac the cost is the **front end** (`newLibraryWithSource`,
MSL to AIR), and it is the **combiner shaders** that carry it: 120 ms each
against 9 ms for a vertex program, so the 6 new fragment shaders of the 1-1
response event are about 0.7 s, which is the hitch the operator felt.
`coldbin-1` is the measurement the first version of this design lacked:
its front end was as cold as `cold-1`'s (same 9 and 121 ms), which shows
the copy had no cache of its own, and its 61 pipeline builds still took
0.1-0.2 ms each. The pipeline back end is therefore not a cost worth a
record or a binary archive, with one caveat the implementation keeps an
eye on: if Apple served those builds from a cache this run could not
reach, a later Mac would show it as a `pipeline` stage time in the
first-use trace (D3), and the `pso` records of the Follow-up come back on
that evidence. Why a combiner shader compiles 13x slower than a longer
vertex program is a question for the implementation (task 2.3 records the
`library` time per kind; a cheaper combiner text that keeps the pixels
would help every Mac's first launch).

## Goals / Non-Goals

**Goals**
- No compile on the ack thread for a shader the game has seen before on
  this machine, or that the shipped list names.
- One mechanism for both backends, title-neutral, in the toolkit.
- Frames byte-identical to today's: the goldens never see the keys, and a
  preloaded object is provably the one the on-demand path would have
  built (D4's verification).
- Burnout 3 gets it with no code of its own.
- The smallest v1 that removes the measured hitch: records, key, trace,
  preload, per-player index.

**Non-Goals (v1)**
- Persisting compiler output (DXBC blobs, Metal binary archives): Follow-up,
  with the requirements the review set for it.
- Preloading Metal pipeline states (`pso` records): the back end measured
  at 0.1 ms; Follow-up on evidence.
- Rendering a frame with a stand-in shader while the real one compiles
  (changes pixels; rejected for stock, see Alternatives).
- A game-specific "stage load" hook: the whole list compiles at boot in the
  background.
- Changing `D3DCOMPILE_OPTIMIZATION_LEVEL3` or the Metal compile options:
  both are part of the pixels.

## Decisions

### D1. Placement: mechanism in the toolkit, harvest in the CLI, data in cat

- **Toolkit** (`posix-host/portability`): `src/d3d/nv2a_shader_cache.c/.h`
  (records: format and parse; the index file; the staging table; the
  preload thread; plain C, no backend headers, no game knowledge) and the
  glue in `nv2a_pb_d3d11.c` and `nv2a_pb_metal.m` (a `compile_record`
  callback each, the staging `take` at the existing build points, the
  first-use trace and index lines). It reads two environment keys and a
  file of records. This is what the user asked to keep game-agnostic, and
  it is the only place it can live: the records are built from
  `nv2a_pb_vsh` state and the combiner registers, and the compilers are
  the backends'.
- **CLI** (`xboxrecomp-cli`): `xbr shaders harvest|stats` (stdlib,
  synthetic tests), the optional `[shaders]` table, the bundle step in
  `package`, and the two conditional export lines in
  `src/xboxrecomp_cli/package/templates/steamos/launch.sh` and
  `templates/windows/launcher.c`. The CLI already owns the launchers and
  the golden and replay log parsers, so harvesting belongs beside them.
- **cat**: the harvested list (`analysis/shaders/preload.txt`), the
  `game.toml` table, the macOS launcher's lines, `docs/env.md` rows and
  `docs/packaging.md`. cat holds no mechanism.
- **Not in the toolkit:** the list itself (game data) and the harvest (a
  log tool; the public toolkit mirror must stay free of game output).

Upstream: the mechanism is offerable to sp00nznet/xboxrecomp as one PR of
the GPU series after G6 (D3D11) and G7 (Metal) in
`cat/analysis/upstream/pr-stack-plan.md`, with plain `getenv`
(`RECOMP_SHADER_PRELOAD`, `RECOMP_SHADER_CACHE`, `RECOMP_SHADER_TRACE=1`
in place of the trace list) and no env table. It depends on the backends,
so it cannot go earlier. That file is untracked and lives only in the main
cat checkout, so the row is an orchestrator step after the merge (task
5.1) with the text in `notes/shaderpc/`.

### D2. The record: inputs, not outputs

A record is one text line of what the generator consumes:

```
# xbr-shaders 1 backend=metal
vs 0 11 00000000 0020161B 0836106C 2070F800 ...      # start, slot count, 4 dwords per slot
fs 04200000 ... 00000000 1                           # 36 dwords: cicw[8] aicw[8] cocw[8] aocw[8] ctl fcw0 fcw1 modes; then the scale class
```

- `vs`: the `n` slots from `start` to the FINAL slot, the bytes
  `nv2a_vsh_program_hash` hashes and `d3d8_vsh_parse` reads (both stop at
  FINAL). The generators take the parsed program and a constant flag; no
  other state reaches the vertex text. Up to 136 slots, 4.9 KB of text at
  most; BLiNX's are 20-60 slots.
- `fs`: the seven register arrays and the stage-modes word that
  `fs_select` and `setup_pixel` already gather as `key[0..35]`
  (`d3d8_combiners_from_regs`'s inputs) and the scale class (`key[36]`,
  `rect_snap`). `fog_input` is a constant 1 in both backends and is not
  recorded; the day it becomes an input, the record format version moves.
  The derived `NV2ACombinerState` is rebuilt from the registers, so a
  change in `d3d8_combiners_from_regs` is picked up, which storing the
  state would miss.
- Unknown kinds are skipped with one log line, so a future `pso` record
  (Follow-up) in a list does not break an older runtime.
- **Key** = FNV-1a 64 of the record text. Backend-independent and stable
  across launches and builds, so one list serves both backends and a
  D3D11 harvest warms a Metal install. The in-process caches keep their
  32-bit hashes; each `VsEntry`/`FsEntry`/`RcEntry` also stores the
  64-bit record key, which the first-use trace and index need.
- The generator inputs are complete today (the review checked the
  parsers and generators: no mutable globals, no other state). D4's
  verification is the guard for the day they are not.
- Why not the generated source: it is backend-specific, 10-60 KB per
  shader, and changes with every generator fix. Why not the compiled
  object: GPU- and driver-bound on Metal, derived game data on both.

### D3. The trace: `RECOMP_TRACE=shaders`, driven by first use

Toolkit trace key (`X(SHADERS_TRACE, TRACE, "shaders", NULL, ..)`). The
**ack thread** prints one line per key at its first use in the run:
`[SHADER] vs 0 11 .. ; preloaded` when the staging table had it, or
`[SHADER] vs 0 11 .. ; on-demand generate 0.1 compile 28.4 create 1.3`
(D3D11) / `; on-demand library 31.0` (Metal) when it compiled there.
`pipeline` builds print their own time on Metal, so a back end that turns
out slow shows. The **preload thread** prints only failures
(`[SHADER] preload: <record> failed: ..`, once each) and one
`[SHADER] preload: N built, M skipped (on demand first), T ms` line at
its end. Each present summary gains one `[SHADER] summary: N vs, N fs,
N preloaded, N on demand, <ms> on the ack thread` line. Printing only.

The harvest reads the first-use lines, so a list holds what a run
**used**, never what a preload built: lists cannot grow with stale
records. The trace can join `golden.json`'s pinned `RECOMP_TRACE=flip`
later if the owner wants every golden to harvest (Follow-up; the golden
logs in `bench-logs/` would then carry microcode, which is private
anyway). A log with this trace on holds the title's microcode: it is off
by default, and a player's log attached to a public issue must not have it
on (D11).

### D4. The preload: one thread, a staging table, adoption at the build point

`RECOMP_SHADER_PRELOAD=<file>` (config key). When the backend's device is
up (end of `init()` on D3D11; the presenter's device adopted on Metal),
and either key is set, the backend calls
`nv2a_shader_preload_start(list_path, index_path, compile_record, ctx)`:
one thread (pthread on POSIX, `CreateThread` on Win32) that reads the
list, then the index (D5), de-duplicates by key, and for each record in
order calls the backend's
`compile_record(const ShaderRecord *, ShaderBuilt *out)`, pushing the
result into a staging table (`pthread_mutex`/`CRITICAL_SECTION`, a flat
array keyed by record key).

**What `compile_record` does.** D3D11: generate the HLSL, `D3DCompile`,
`ID3D11Device_CreateVertexShader`/`CreatePixelShader`, keep the blob for
input layouts. `ID3D11Device` creation methods are free-threaded (the
device is created with flags 0); `d3dcompiler_47` is documented safe from
several threads and Wine's builtin wraps vkd3d-shader, which is reentrant
(task 2.5 tests two threads compiling at once under Proton); the
immediate context (`s_ctx`) is never touched. Under DXVK, `Create*Shader`
also runs DXVK's DXBC to SPIR-V on the calling thread, now ours, and its
pipeline-library compile on DXVK's workers, so the draw later only links.
Input layouts stay per draw. Metal: `newLibraryWithSource` +
`newFunctionWithName`; `MTLDevice`, library and function objects are
thread-safe. No encoder, render target, texture or guest memory is touched
off the ack thread.

**Thread rules** (the review's S4):
- `compile_record` uses its own heap buffers, never the backends' static
  `parsed`/`hlsl`/`src`/`msl`;
- it touches no ack-thread counter (`s_compile_errors`, `s_vs_compiled`,
  `s_fs_compiled`, `s_rc_compiles`); the preload thread keeps its own,
  read under the staging mutex for the summary line;
- Metal: each record runs inside an `@autoreleasepool` (MRC file:
  `NSString`, `NSError`, `localizedDescription` are autoreleased);
- the staging table hands over +1 references; the ack thread takes
  ownership on adoption; entries never adopted are released at exit;
- the thread is not pinned to the guest core (`xbox_GuestCpuMask` is the
  guest's; this thread sets no affinity); on macOS it runs at
  `QOS_CLASS_UTILITY`, not background (background QoS lands on E-cores
  and propagates to `MTLCompilerService`); on Win32
  `THREAD_PRIORITY_BELOW_NORMAL`.

**Adoption happens inside the existing miss paths** (the review's B2).
The staging `take` replaces only the generate+compile+create step, at the
point where each cache already builds, after its slot choice, eviction
and counters: `vertex_shader` where it calls `compile()`
(`nv2a_pb_d3d11.c` ~1259), `combiner_ps` after `s_rc_compiles++` (~2032;
the LRU eviction, `Release` and `s_state_gen++` above it run unchanged,
so the `setup_pixel` memo and the state cache stay right), `vs_cache`
(`nv2a_pb_metal.m` ~1630) and `fs_select` (~1725). `combiner_ps` takes
the record key from `setup_pixel`'s `key[37]`, where the record lives.
Nothing is inserted into a cache from outside its miss path.

**Verification on adoption** (S1). `ShaderBuilt` carries the FNV-64 of
the source text the preload thread generated. On adoption the ack thread
regenerates the source from live state (0.1 ms, a few dozen times a run)
and compares the hash. A mismatch means a generator input the record does
not carry: the object is dropped, the shader compiles on demand, and one
`[SHADER] preload: record <key> disagrees with live state` line is
printed. A hitch, never a wrong pixel. `nv2a_shader_cache.c` holds
`_Static_assert(sizeof(NV2ACombinerState) == <today>, "new combiner
field: is it an input? extend the fs record, bump the format")` and the
same for `NV2AVshProgram`; the ctest checks record, parse, generate
equals the live generate for both kinds.

**Preload slower than the game** (S9). When the ack thread misses a key
the preload thread has not reached, it compiles on demand (as today) and
puts a tombstone for the key into the staging table under the same mutex;
the preload thread checks before each record and skips. The ack thread
never waits for an in-flight record; a duplicate compile of the same
record is correct and costs a core for its duration (task 4.1 records
on-demand compile times with and without the preload to see the
contention). On D3D11 that is two concurrent `D3DCompile` calls: task 2.5.

**Capacity** (N7). The staging table is bounded per kind by the backend's
in-process cache size (`VS_MAX` 128 and `RC_MAX` 64 on D3D11, 512 on
Metal), because staging memory is bounded and D3D11's `s_vs` has no
eviction (a 129th program is refused today). Counted after
de-duplicating list plus index; the list first in its order, then the
index **newest first**, so on D3D11 what is cut is the oldest index
records. The cut is logged once (`preload: list has N vs, capacity M`).
Task 2.4 raises `RC_MAX` to 128 if BLiNX's harvest exceeds 48 `fs`
records (today 10-21).

**Cost.** One thread at low priority during the first seconds. With
Proton's 30 ms per shader, 100 records are about 3 s under the opening
movies (`@stage1` reaches the title after 10 s); on the Mac 1.5 s. Task
4.1 measures the boot window's flips/s and audio starves with and without
the list, on both hosts. If they move, the thread yields between records
or starts after the first flip.

**Failure.** A record that fails to build is logged once (trace) and
skipped; the frame that needs it compiles on demand and fails as today.

**Exit** (S7). `nv2a_shader_preload_stop` is registered with
`recomp_exit_hook_add` (the Win32 window close path, which runs the
hooks before `ExitProcess`) and with `atexit` on POSIX: it sets a stop
flag, joins with a bound of 250 ms (a combiner compile is 120 ms; the
thread checks the flag between records), closes the index fd and
releases un-adopted staging objects. Never an unbounded join from the
window thread. No device is released at exit, on either backend.

### D5. The cache: an append-only index of records, never purged

`RECOMP_SHADER_CACHE=<dir>` (config key; empty means unset). The directory
holds `index.txt`, a record file (D2) with the header
`# xbr-shaders 1 backend=<d3d11|metal>` (the backend field is provenance;
the records are backend-neutral and an index written on one backend is
read by the other). At each key's **first use** in a run (D3), when the
key was not in the index read at start (an in-memory key set, which is
also what keeps the file free of duplicates), the ack thread appends the
record with **one `write()` on an `O_APPEND` descriptor** (POSIX) or one
`WriteFile` on a handle opened with `FILE_APPEND_DATA` (Win32): the whole
line plus `\n` in one call, so two processes sharing a directory never
interleave and a crash leaves at most one torn last line. The reader
skips, with one log line and never a purge, any line that fails to parse
or lacks its newline.

On the next launch the index is preloaded after the list (D4), newest
first, so **the cache is the per-player list**: whatever this player has
seen compiles ahead on the next launch, with or without a shipped list.
This is the whole Metal story in this change, and it is what makes the
public build useful without any shipped data.

Housekeeping runs on the **preload thread at its start**, never on the
ack thread: if the index holds more than 4096 records of a kind, it is
rewritten keeping the newest 4096 (temporary file plus rename, before the
ack thread's first append of the run, which the thread start orders).
Nothing else is ever deleted. Expected size: BLiNX 2 about 70 `vs` and 25
`fs` records, under 400 KB.

No compiler output is persisted in v1. The DXBC blob store, with the
requirements the review set for it (a compiler fingerprint in the key, a
checksummed blob header, unique temporary names, a size cap maintained on
the preload thread), is the first Follow-up, decided after task 0.3
measures how the 30 ms splits between `D3DCompile` and `Create*Shader`.

### D6. Invalidation: there is nothing to invalidate

Records are inputs, so the index never goes stale: a generator change
produces a different shader from the same record, which is what the
on-demand path would also produce, and D4's verification catches the one
case that matters (an input the record does not carry). There is no
generator version in the header and no purge; the format version
(`# xbr-shaders 1`) covers the record syntax only, and a file with another
version is skipped with one log line. A record the game never asks for
again costs one background compile per launch until the cap rotates it
out.

### D7. Where it lives

| host | `RECOMP_SHADER_CACHE` | set by |
|---|---|---|
| macOS app | `~/Library/Application Support/BLiNX2/cache/shaders` (`$DATA/cache/shaders`) | `cat/packaging/macos/BLiNX2.in` (and `b3/packaging/macos/Burnout3Takedown.in`) |
| Windows | `%LOCALAPPDATA%\BLiNX2\cache\shaders` | the CLI's `src/xboxrecomp_cli/package/templates/windows/launcher.c` |
| steamos / Deck | `Z:<root>/cache/shaders` (outside the prefix, like `hdd/`) | the CLI's `src/xboxrecomp_cli/package/templates/steamos/launch.sh` |
| Proton bench, Mac golden, ctests | unset | nothing: today's paths |
| `BLINX2_DATA_DIR=/x` | `/x/cache/shaders` | the launchers derive it from the root |

`RECOMP_SHADER_PRELOAD` is set by the same launchers to the bundled list
(`Contents/Resources/shaders/preload.txt`, `<exe dir>\shaders\preload.txt`,
`<root>/current/shaders/preload.txt`) only when the file exists.

**Precedence** (S10). All three launchers load `launch.env.default` and
the player's `config/launch.env` first and then export their paths, so a
plain export would override the player. The two keys are set **only when
not defined at all** after the loads: `[ -n "${RECOMP_SHADER_CACHE+x}" ]
|| export RECOMP_SHADER_CACHE=..` in the shell launchers,
`GetEnvironmentVariableW` returning 0 with `ERROR_ENVVAR_NOT_FOUND` in
`launcher.c`. The runtime treats an empty value of either key as unset
(`recomp_env` returns `""` for an empty variable), so
`RECOMP_SHADER_CACHE=` in `launch.env` is the off switch and
`RECOMP_SHADER_CACHE=/elsewhere` moves it. The deployment spec's
byte-identical set stays `hdd/`, `config/`, `logs/`; `cache/` is named as
something installers never touch and players may delete.
`docs/packaging.md` gains the line.

### D8. Stock-neutral, default off in the runtime, on in the bundles

CLAUDE.md: opt-in features default off and never change stock behaviour.
With both keys unset every path is today's, which is the runtime default
and the environment of every golden, bench and ctest. The packaged
launchers set `RECOMP_SHADER_CACHE`, as `launch.env.default.macos` sets
`RECOMP_HOST_PAD=1`, because for the player it changes nothing but when
and on which thread a compile runs: v1 persists no compiler output, the
same source and options go through the same compiler in the same process,
and the adoption check (D4) proves the object is the one the on-demand
path would have built, or drops it. It is not an enhancement (no
`XBOXRECOMP_ENHANCE` gate, no `config.toml` key): it draws nothing
differently and has no stock counterpart to deviate from. What it does
change is boot-window timing (a thread compiling for a few seconds),
which task 4.1 measures. The gate for the claim is task 4.2: the Metal and
D3D11 goldens with a filled index and the list in the environment, every
verdict unchanged. If a verdict moved, the launchers would not set the
keys and the change would stay opt-in through `launch.env`. The user
confirmed this on 2026-10-13 ("On by default, argue performance
optimization"; § Decisions taken, 2).

### D9. Backends agree

Same record, same key, same first-use trace, same preload module, same
staging protocol and adoption rule, same index file. v1 has no
backend-specific store, so there is no asymmetry to document; the DXBC
store (Follow-up) would be D3D11's. The CPU backend compiles no shader and
only has to keep building (`nv2a_shader_cache.c` has no backend
dependency).

### D10. Burnout 3

No code. Its steamos and Windows launchers come from the CLI templates;
its macOS `.in` gets the same lines as cat's (task 3.4 proposes them to
`b3/`; the b3 maintainer merges). It ships no list (the user, 2026-10-13:
"Leave it"; § Decisions taken, 5): B3 relies on its per-player index
alone, and `xbr shaders harvest` over its bench logs stays available if
that changes. The toolkit gate for this change runs its race smoke on the
branch with
`RECOMP_SHADER_CACHE` set to a scratch directory, twice, which exercises
the index on a second title.

### D11. Legal

A `vs` record is the title's vertex-program microcode; `fs` records are
register state. Under CLAUDE.md the microcode is game data, derived like
`src/recomp/gen/` (gitignored) and the golden frames. So:
`analysis/shaders/` is gitignored with the rest of `analysis/`;
`scripts/test_gitignore.py` asserts it; `export-public.sh` exports
`git ls-tree`, so it cannot see it; the public-push audits
(`export-public.sh`'s checks and the CLI's `scripts/audit-public.sh`)
grep for the content marker `# xbr-shaders`, which catches a list under
any name, besides the paths `analysis/shaders` and `cache/shaders`; the
bundles already carry `game_files/` and are never public, so the list
rides with them; the per-player index is never copied anywhere. A log
written with `RECOMP_TRACE=shaders` on holds microcode too: the trace is
off by default, and `docs/env.md` says a log for a public issue must not
have it on. A public player's first session compiles on demand as today
and every later session preloads from their own index (D5): the shipped
list only moves the first session's cost, which is why its privacy costs
the public build little. The user confirmed this reading on 2026-10-13
("Yes, it's private"; § Decisions taken, 1); the alternative that would
make a public list possible (`xbr shaders locate`, records as
`xbe:<offset>` references into the player's own files, no microcode in
the list) is a Follow-up, not v1.

### D12. CLI surface

- `xbr shaders harvest INPUT... -o LIST`: inputs are logs (`[SHADER]`
  first-use lines; `preload:` lines are ignored) or record files
  (`index.txt`, another list); output a record file, header
  `# xbr-shaders 1`, first-seen order, one copy per key; unknown kinds
  kept verbatim. Exit 2 on an unparsable record naming the file and line.
- `xbr shaders stats LIST`: counts per kind and the longest `vs`.
- `manifest.py`: optional `[shaders] list` (string path); `OPTIONAL`
  gains `shaders`; a manifest without it validates.
- `package`: when `[shaders] list` names an existing file, copy it to the
  bundle's `shaders/preload.txt` (macOS: `Contents/Resources/shaders/`);
  the launcher templates export `RECOMP_SHADER_PRELOAD` when the file is
  present and `RECOMP_SHADER_CACHE` always, both under D7's precedence.
- Tests on synthetic records (made-up dwords), as `test_pacing_stats.py`
  does for logs; `grep -nE '0x[0-9A-Fa-f]{5,}'` over `shaders.py` and its
  tests finds nothing.
- No new flags on `golden run`: it already takes `VAR=val` and adds
  `RECOMP_TRACE` lists up, so a harvest or a seeded-index run is
  `blinx2 golden run --backend metal RECOMP_SHADER_CACHE=<dir>
  RECOMP_TRACE=shaders`.

## Risks / Trade-offs

- **The preload thread steals a core at boot.** Mitigation: one thread at
  utility/below-normal priority, stops when the list ends; measured in
  4.1 on both hosts. If the boot window's flips/s or audio starves move,
  the thread yields between records or starts after the first flip.
- **DXVK's own compile still lands at `Create*Shader`.** On our preload
  thread (DXBC to SPIR-V) and DXVK's workers (pipeline library), before
  the draw if the preload is ahead; a record the list misses compiles
  exactly as today.
- **Concurrent compiles.** A miss while the preload thread is compiling
  means two compilers at once (two `D3DCompile`, or two
  `MTLCompilerService` jobs). Correct by API contract; task 2.5 tests the
  D3D11 case byte for byte, 4.1 measures the Mac contention.
- **An input the record does not carry.** Caught at adoption by the source
  hash (D4): a hitch and a log line, never a pixel.
- **Two scale classes.** The `fs` record carries the class, so a list
  harvested at scale 1 preloads nothing for scale 2; the player's index
  fills it in on their first scaled session. Goldens run at scale 1.
- **A torn index line after a crash.** Skipped on read (D5); at most one
  record is lost.
- **Thread-safety claims.** Both APIs document device creation as
  thread-safe; the smoke tests under ThreadSanitizer (Mac), the staging
  ctest under TSan, the Proton concurrent-compile ctest and a Proton run
  with `d3d11_memo=0` (4.3) are the evidence.

## Alternatives considered

- **Async on-demand compile with a stand-in shader** (draw the batch with
  `s_ps`/`fs_basic` or skip it until the real shader is ready). Removes
  the hitch without any list, but changes pixels for a frame or two: a
  stock behaviour change, rejected; could be an opt-in enhancement later.
- **Lower `D3DCOMPILE_OPTIMIZATION_LEVEL3` on the first compile and
  recompile at level 3 in the background.** Different DXBC, possibly
  different pixels across the swap; rejected for stock.
- **A DXBC blob store in v1.** Shortens background work and on-demand
  misses only (the preload already takes `D3DCompile` off the ack
  thread), and brings a compiler-identity problem (Wine's
  `d3dcompiler_47` changes with Proton; a key of source and flags would
  serve the old compiler's DXBC while an uncached run gets the new one),
  blob integrity (DXVK does not verify the DXBC checksum), caps and
  temporary files. Deferred to the Follow-up with those requirements.
- **`pso` records and a Metal binary archive.** The back end measured at
  0.1 ms cold (`coldbin-1`); records for it would add reserved keys for
  the built-in functions (`s_vs_pass`, `s_fs_basic`, the D3D11
  pass-through), a key-to-function map on the preload thread and
  `PsoKey` changes, for nothing measurable. Deferred on evidence.
- **Shipped Metal binary archives.** Bound to GPU family and OS version,
  and still need the front-end compile, which is the whole cost.
- **A game "stage load" hook.** Needs game knowledge in the toolkit or a
  cat-side trigger; the whole set is small enough to compile at boot.
- **Storing `NV2ACombinerState` in the record.** Misses generator changes
  in `d3d8_combiners_from_regs`; the registers are the input.
- **A toolkit-side harvest in `tools/`.** Game output would flow through
  the public toolkit's tooling; the CLI already parses these logs.

## Follow-up

- **DXBC blob store** (D3D11): `dxbc/<key>.bin` beside the index, where
  the key is FNV-64 of the HLSL text, the flags **and a compiler
  fingerprint** (FNV-64 of the DXBC `D3DCompile` produces for a fixed
  probe shader at preload start, which catches every Wine or native
  compiler change; or the DLL's file version); a 16-byte header per blob
  (magic, payload length, FNV-64 of the payload) checked on read, since
  DXVK does not verify the container checksum; unique temporary names
  (`<key>.<pid>.<tid>.tmp`) with rename; a 64 MB cap maintained on the
  preload thread at start; a fingerprint change drops blobs, never the
  index. Decide after task 0.3 shows how the 30 ms splits between
  `compile` and `create`; worth it only if `compile` dominates and the
  preload thread cannot get ahead of the game on the Deck.
- **`pso` records and a Metal binary archive:** closed on `coldbin-1`
  (0.1-0.2 ms per pipeline with a cold per-binary cache); re-open only if
  a first-use trace on some Mac shows `pipeline` times in the
  milliseconds. The record grammar reserves the `pso` kind.
- **Cheaper combiner MSL:** find why `d3d8_combiners_generate_msl`'s text
  compiles at 120 ms against 9 ms for a vertex program (the precise math
  mode on the many selects and clamps? a per-stage function inlined eight
  times?), and whether an equivalent text that keeps the pixels (goldens
  identical, `d3d8_msl_split` expected outputs updated) compiles faster.
  Independent of this change; it would help every Mac's first launch of a
  new scene.
- **`xbr shaders locate`:** turn inline microcode into
  `xbe:<offset>:<n>` references the runtime reads from the player's own
  `default.xbe` at boot, so a list could be public. Not asked for: the
  user keeps the list private (§ Decisions taken, 1); listed in case the
  public build ever wants a shipped list.
- **Harvest in every golden:** add `shaders` to `golden.json`'s pinned
  trace once the owner wants the goldens to double as harvests; the
  bench logs then carry microcode (private store, allowed).
- **Async on-demand compile as an opt-in enhancement** for titles whose
  shader set cannot be enumerated ahead.

## Decisions taken (the user, 2026-10-13)

The five questions the first version left open, with the user's answers
quoted. No question stays open.

1. **Privacy of the list (D11).** Asked: is the record list derived game
   data, harvested and bundled privately, never committed or published, or
   should the `locate` follow-up come first so the public cat repo can
   carry a list? Answer: **"Yes, it's private"**. The list is private
   derived game data; it never goes in a public repo or a public bundle.
   D11 and the deployment and shader-precompile requirements say so.
2. **Default on in the bundles (D8).** Asked: do the packaged launchers
   set `RECOMP_SHADER_CACHE` for every player (only when the player's
   `launch.env` has not defined it, `RECOMP_SHADER_CACHE=` turning it off,
   the runtime default staying off, nothing persisted but the record
   index), or does v1 stay opt-in? Answer: **"On by default, argue
   performance optimization"**. The launchers turn the per-player cache on
   by default; D8 argues it as a performance-only optimisation that leaves
   stock behaviour untouched (same compiler, same process, every adopted
   object checked against the live source; with the DXBC store deferred
   there is no persisted compiler output to argue about); the runtime
   default stays off; the launchers set the key only when it is undefined
   and an empty value means off, so `launch.env` can still turn it off.
   Task 4.2's seeded goldens remain the gate for the launcher lines.
3. **Where the cache sits on the Deck (D7).** Asked: `<root>/cache/shaders`
   beside `hdd/`, or `~/.cache/xboxrecomp/<slug>/`? Answer: **"Yes, inside
   the game folder"**. `<root>/cache/shaders`, as D7 proposes.
4. **Harvest source for v1 (D12, task 1.4).** Asked: the three goldens
   (61 vertex and 14 fragment shaders of the operator's full-session 64
   and 21), a one-time harvest of the operator's own Mac session, or
   `playthrough-replay` later? Answer: **"Probably a mix of both if
   possible?"**. The v1 list is the union of the golden harvests and a
   one-time harvest of the operator's own Mac session played with
   `RECOMP_TRACE=shaders` in `launch.env`; `xbr shaders harvest` merges
   several logs and lists and de-duplicates by key (D12), so the union is
   one command. The session is the user's own task (1.4), after the
   toolkit and CLI parts land, not an agent's; 1.5 harvests the union.
5. **Burnout 3's list (D10).** Asked: harvest one from its bench race
   smoke for the b3 Deck install, or leave B3 to its per-player index?
   Answer: **"Leave it"**. No Burnout 3 list; B3 relies on its per-player
   index alone.
