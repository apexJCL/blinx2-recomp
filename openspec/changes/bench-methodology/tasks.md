## 1. Run record

- [x] 1.1 `bench.sh` writes `run-info.txt` (host, Proton, env, args, exe sha).
- [x] 1.2 `bench.sh sync` refuses while `.gen-regenerating` exists.
- [x] 1.3 `bench.sh logs` / `symbolize` write `crash-symbols.txt` (`9a756d5`).
- [x] 1.4 `pipeline.sh recomp` writes `gen/PROVENANCE` (toolkit commit, seed files, `recomp_manual.c` hash).
  - Done differently (2026-10-06 cleanup): `blinx2 recomp` writes `src/recomp/gen.key.json` (the inputs that decide the generated code), and `bench.sh integrate` compares the local and remote `gen/` digests.
- [ ] 1.5 `run-info.txt` also records the toolkit and cat commits and the `gen/PROVENANCE` content.
  - Status (2026-10-06): `run-info.txt` quotes `build-win/provenance.txt` (cat and toolkit commits, branches, dirty state at sync). Open: the `gen/` digest or `gen.key.json` in `run-info.txt`.

## 2. Instrumentation

- [x] 2.1 `RECOMP_FLIP_LOG` per-flip line and `[THREAD]` role lines (toolkit `a47bfb0`).
- [ ] 2.2 Movie-window open/close lines (`fmv-playback` 2.1).

## 3. Report

- [ ] 3.1 A report step (`blinx2 bench report` or a script under `scripts/`) that classes frames as movie, 2D or 3D, and prints flips/s, p50/p95/p99 frame ms and fence per frame for 3D frames, with the dump names.
- [ ] 3.2 Map `top-threads.txt` tids to `[THREAD]` roles in the same report.
- [ ] 3.3 First baseline on the Linux/Proton host after the `NtFreeVirtualMemory` fix (wt/kmem) lands.
