# Design: D3D11 shader cache on disk

## Context

`nv2a_pb_d3d11.c` has one compile point, `compile(what, src, target,
&blob)`, called by `vertex_shader()` (`vs_5_0`) and `combiner_ps()` and the
built-in shaders (`ps_5_0`), all with entry `main` and
`D3DCOMPILE_OPTIMIZATION_LEVEL3`. `D3DCompile` comes from
`d3dcompiler_47.dll` loaded with `LoadLibrary` (Wine's under Proton, the
system's on Windows). The in-process caches above it (`s_vs`, `VS_MAX` 128,
by program hash, no eviction, NULL when full; `s_rc`, `RC_MAX` 64, LRU)
are unchanged. Compiles happen on the thread that draws (the ack thread).

### Why steady state still compiles

The Deck baseline log of the JSRF title bench (s1-dsp0-43) has 28 `[d3d11]`
vertex compiles and 16 combiner compiles in a 160 s run, with no evictions
from either cache. 24 of the vertex compiles fall between presents 2400 and
2700, the load into the title scene; the others are one each at presents 1,
2700, 3000 and 3600. Every compile is a program seen for the first time in
the process, not a cache thrash, so only a store that outlives the process
removes them, and a warm run should compile nothing.

## Decisions

### D1. Key: everything the output depends on, compared in full

`shader_cache_key` = compiler identity, target, entry, `flags1`, `flags2`,
source. It is serialised with u32 length prefixes (so moving a character
between fields is another key) and hashed with FNV-1a 64; the hash names the
file `<16 hex>.bin`. The file stores the whole serialised key, and a load
compares it byte for byte: a hash collision, or any other key's entry under
the same name, is a miss and the file is kept. A hit is therefore always the
bytes stored for exactly this key.

Defines and includes are not in the key because `compile()` passes none.
A future caller that does must add them to the key first.

### D2. Compiler identity: the loaded DLL's path, size, write time and version

`GetModuleFileNameW` on the module `D3DCompile` came from, then
`GetFileAttributesExW`, plus the `VS_FIXEDFILEINFO` file version read from
the loaded module's own version resource (no `version.dll`):
`"<path>|<size>|<mtime>|<version>"`. The version catches a replacement that
keeps the old file's size and time (review L2). A Proton update replaces
the prefix's `d3dcompiler_47.dll` (new size or time), a Windows update
replaces the system's, a different Proton has another path: each starts a
new set of keys. If the identity cannot be read, or `D3DCreateBlob` is
missing, the cache stays off with one line: a key without the compiler could
hand one compiler's bytes to another.

Considered: hashing the DXBC of a fixed probe shader at start
(shader-precompile's follow-up suggests it). It also catches a compiler
whose file did not change but whose behaviour did, which cannot happen
without the file changing; it costs one compile (30 ms under Wine) per
launch. Rejected for now; the format number (D4) allows adding it.

Output identity: with the same DLL, the same source, target, entry and
flags, `D3DCompile` is deterministic (no timestamps in DXBC; the container
hash is over the content). So a hit equals what a compile would give, and
the goldens cannot change. The goldens check that, cold and warm (tasks 3).

### D3. Where: beside the saves, per game

Default `<save root>/ShaderCache/dxbc`, where the save root is
`RECOMP_HDD_DIR` (each launcher sets it per game: `<data>\hdd` on Windows,
`Z:<root>/hdd` on the Deck) or the toolkit default
(`%LOCALAPPDATA%\xboxrecomp`). `ShaderCache` is not a name any guest path
maps to (the mapped ones are `TitleData`, `UserData`, `Cache`,
`SystemData`, `UDATA`, `TDATA`, `TitleCache` and the partition images).
The toolkit exposes the root as `xbox_path_hdd_root()`. Under Proton the
directory is a `Z:` path outside the prefix whenever the launcher set
`RECOMP_HDD_DIR`, so a new prefix keeps it, and the key (D2) still keeps
the old compiler's entries apart.

`RECOMP_DXBC_CACHE` reads its switch words like `recomp_env_on`: set but
empty, anything starting with `0`, and `off`, `false` or `no` in any case
are off (the old path exactly: no file is opened). Unset, `1`, `on`, `true`
and `yes` are the default directory. Anything else is a directory, which
must be absolute (a drive or UNC path on Windows): a relative one would land
wherever the game was started from, so it turns the cache off with a line.
Init writes and removes one temporary, so a directory that cannot be
written logs off rather than on (review M1, L4). Named for
DXBC because shader-precompile reserves `RECOMP_SHADER_CACHE` for
its per-player record index; the two stay independent.

### D4. Entry format and validation

```
0  "XRSC"    4  u32 format (1)   8  u32 key length   12  u32 code length
16 u64 FNV-1a of the key bytes   24 u64 FNV-1a of the code
32 key bytes, then code bytes
```

A load checks the magic, the format, both lengths against a 16 MB bound and
against the file size, then both hashes over the bytes read. Any failure is
a damaged entry: counted, removed, and reported as a miss, so the caller
compiles (and stores a good entry). DXVK does not verify the DXBC checksum,
so this header check is what stands between a flipped bit and the GPU. A
format bump removes old entries on their first load.

### D5. Concurrency: unique temporary plus rename

A store writes `<entry>.<pid>-<seq>.tmp` and renames it over the entry
(`MoveFileExW(MOVEFILE_REPLACE_EXISTING)` on Windows, `rename` elsewhere).
Readers see the old entry or the new one, never a partial one. Two
processes storing the same key both succeed with identical bytes; if the
rename fails (a reader holds the file open on Windows), the temporary is
removed and the store counted as failed: the entry already there is as
good. Only one thread calls `compile()`, so the per-process sequence needs
no lock.

### D6. Bound: prune at open

At open, `shader_cache_prune(cap = 64 MB)` lists the directory, removes
`.tmp` files older than an hour (a store a crash cut short) and, when the
`<16 hex>.bin` entries add up to more than the cap, removes the least
recently used ones until 48 MB are left. A hit sets the entry's write time
to now, so recently used means used, not written. Other files are never
touched. A game's whole set is a few hundred entries of a few KB each
(JSRF's title scene: 44), so the cap only ever trims entries of old
compilers.

### D7. Visibility

`[d3d11] shader cache: <dir> (<n> old files removed)` or
`shader cache: off (<why>)` once at init; at present 1 and every 300th:
`[d3d11] shaders: <n> compiled (<ms>), <n> from the cache (<ms>), <n> cache
misses, <n> damaged entries, <n> failed stores`. The bench comparison reads
these lines.

## Metal

No change. The Metal load gap on the Mac is 0.31-0.35 s in the JSRF title
bench, and macOS already keeps compiled MSL per binary across launches; the
cost left there is the combiner front end on a cold system cache, which a
blob store would not remove. Recorded in the proposal and TASKS.

### D8. On by default (an exception to the opt-in rule)

CLAUDE.md has opt-in features default off. The user approved this one
being on by default on 2026-10-23 (review M3), for three reasons:
- a hit is the byte-identical DXBC the same compiler made, so frames
  cannot change (the goldens pass cold and warm);
- it writes at most 64 MB into the save root (the prune cap, D6);
- `RECOMP_DXBC_CACHE=0` turns it off and restores the old path exactly.

## Measurements

Deck (GE-Proton11-7), JSRF title, `xbr bench-matrix`, arm s1-dsp0-43,
toolkit 5de4556c, 2026-10-23. Each arm: 3 runs without the sampler and 1
profiled. Every run compiles or loads 45 shaders; the title load holds 41
of them, and 4 more come in the first seconds of the 3D title.

| arm | load gap ms (4 runs) | mean | compile / load ms | steady fps (good runs) | compiler share (prof) |
|---|---|---|---|---|---|
| off (`RECOMP_DXBC_CACHE=0`) | 1071, 1104, 1179, 1173 | 1132 | 1068-1145 compile | 58.4-59.4 | 0.02% |
| cold, default dir in the fresh per-run hdd | 1368, 1358, 1398, 1408 | 1383 | 1299-1349 compile | 59.3-59.4 | 0.03% |
| cold, fresh dir outside the hdd (3 runs) | 1102, 1302, 1116 | 1173 | 1062-1306 compile | 59.4-59.5 | - |
| warm (primed kept dir) | 339, 307, 346, 329 | 330 | 25-78 load | 59.2-59.5 | 0.00% |

- Warm saves ~800 ms of the ~1130 ms gap (-71%): 45 loads take 25-78 ms
  where the compiles took ~1.1 s. The ~300 ms left is not shader work.
- Cold costs no more than off. The miss path is one failed open, and
  the `compiled` time excludes the store; the cold-in-hdd arm's higher
  compile time (+~230 ms) is the compiler's own run-to-run spread, which
  the fresh-dir arm shows (one of three at 1306 ms, two at 1062-1077).
- Steady state: no compile after the first seconds of the title, in any
  arm, so steady fps does not move and the compiler's share of steady
  samples is noise (0.02-0.03% off/cold, 0 warm). The in-memory caches
  do not thrash; the steady-state compiles in the baseline were programs
  seen for the first time, which a warm disk cache now also serves.
- BLiNX 2 D3D11 golden on the Deck, twice in one tree: pass both. The
  first golden's attract run compiled 51 (2.0 s) with 51 misses; its
  stage1 run then loaded 48 from the cache and story 26 with 5 compiles.
  The second golden: 0 compiles, all from the cache (51, 48, 28).
- Bimodal Deck "slow mode" verdicts (off r3, off prof, cold prof, warm r1,
  warm r3) are the known effect and fall in every arm.

Evidence: `runs/bench-matrix/shader-cache/deck/{off,cold,fresh,warm}/`,
`runs/bench-matrix/shader-cache/golden/`. PC numbers: task 4.3.

## Follow-ups (from the review)

- **L1, format bumps.** An entry of another `SHADER_CACHE_FORMAT` counts
  as damaged and is removed. The Deck keeps 3 installed builds, which
  share one save root, so after a bump alternating launches of an old and
  a new build would delete each other's entries. Fix: treat a format
  mismatch as a miss and leave the file (the prune cap retires it), or
  put the format in the file name.
- **L6, bench timings.** `blinx2 bench golden` leaves `RECOMP_HDD_DIR`
  unset, so a bench tree's cache carries over from run to run: the first
  scenario of a fresh tree runs cold, later ones warm. Not a correctness
  issue. Bench reports should quote the `[d3d11] shader cache:` and
  `shaders:` lines, or the matrix should say cold or warm per arm
  (`xbr bench-matrix` copies a fresh hdd, so it is cold unless an arm
  sets a directory).

## Risks

- A compiler that changes output without changing its file: not known to
  exist; the format number allows a probe hash later (D2).
- A full disk or a read-only save root: stores fail, counted; compiles go on
  as before.
- Concurrent prune and store from two processes on one directory: a prune
  can remove an entry another process just stored, which then compiles
  again. Harmless.
