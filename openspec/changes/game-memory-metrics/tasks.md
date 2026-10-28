## 1. Toolkit

- [x] 1.1 `mem_stats.{c,h}`: host sources, format and parse, exit paths, periodic sample.
- [x] 1.2 The `mem` TRACE row; start at process-main.
- [x] 1.3 GPU notes: Metal `currentAllocatedSize`, D3D11 `QueryVideoMemoryInfo`.
- [x] 1.4 ctest `tests/mem_stats`: format/parse round trip, n/a, a live sample.

## 2. cat

- [x] 2.1 `docs/env.md` row for `mem`.

## 3. CLI

- [x] 3.1 Parse the line; ingest into `metrics`.
- [x] 3.2 `regress` memory lines and the 25% flag; `mem_rise` in the manifest.
- [x] 3.3 `bench run` / `golden run` print the figures.
- [x] 3.4 pytest cases; ruff.

## 4. Baselines

- [x] 4.1 Mac Metal: BLiNX 2, BLiNX 1 (cache off).
- [x] 4.2 BLiNX 1 with the RAM cache, after the tracker item merges.
- [ ] 4.3 Deck (Proton) and the PC on Windows, when they are up.
