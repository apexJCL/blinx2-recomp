- r1: CLI `wt/gen-names/xboxrecomp-cli` and cat `wt/gen-names/cat`, both on
  `feat/gen-names` (CLI off main 496c0a5, cat off main b9b5357); cat ran the
  CLI with `XBOXRECOMP_CLI_DIR=<CLI worktree>`, its `[cli]` pin not moved;
  scratch `xbox-recomp/runs/gen-names/`. The CLI side merged (b81263c).
- r2 (rework): cat `wt/gen-names-1104/cat` on `feat/gen-names-r2`, rebased
  on main 63d80cf0, which already pins CLI v0.20.0; run with
  `XBOXRECOMP_CLI_DIR` at CLI main d777966 (cat main's `[system]` needs it);
  scratch `xbox-recomp/runs/gen-names-1104/`.

## 1. CLI

- [x] 1.1 `manifest.py`: `[pipeline] symbols` (path, default `""`), checked
  as a game path; `Game.symbols`.
- [x] 1.2 `symbols.py`: load and check the map; `apply_names` on
  functions.json (D1, with the rerun reset); `annotate_gen` (D3) with the
  mtime snapshot.
- [x] 1.3 `pipeline.py`: `names` runs with a map and no Ghidra export;
  the map is applied after `merge_names` and the hooks; recomp snapshots
  then annotates; gen key inputs and argv (D4).
- [x] 1.4 `docs/symbols.md` (the format), `docs/manifest.md` row, CHANGELOG.
- [x] 1.5 Tests: load and refusals, apply and reset, annotation of a doc
  block, a global literal and a label, comment and string lines untouched,
  mtime kept for an unchanged file, gen key unchanged without the key.
- [x] 1.6 Gates: `uv run pytest tests`, ruff check and format.

## 2. cat

- [x] 2.1 `game.toml`: `symbols = "config/symbols.toml"`.
- [x] 2.2 `scripts/test_symbols.py`: the D6 checks.
- [x] 2.3 Gates: `uv run pytest scripts`, ruff check and format.
- [x] 2.4 The CLI at cat's `[cli]` pin (v0.18.0) refused the unknown
  `symbols` key, so cat's merge waited for a CLI release with this change.
  Symbols support first shipped in v0.19.0; cat main pins v0.20.0 (d047f6c,
  push round 19), which contains it (90e7ffe); cat main also
  needs CLI main for `[system]`, so the rework (`feat/gen-names-r2`, rebased
  on main 63d80cf0 without conflicts) ran with `XBOXRECOMP_CLI_DIR` at CLI
  main d777966. Regen there: 240 of the map's 250 functions have gen code
  (10 are `in_gen = false`); 196 carry their name in gen and 44 stay
  `sub_`: 36 named in `recomp_manual.c` (27 pinned, 9 wrapped; the design's
  count) and 8 hook slots; normalising diff vs a stock regen of the same tree empty
  (53 files); a second regen moves no gen mtime; Mac build passes.

## 3. Regenerate

- [x] 3.1 Stock regen with the CLI at base (gen copy in `runs/gen-names/`).
- [x] 3.2 (r1) Regen with the branch; names in gen; `[MOD]` hook counts
  unchanged. Of the map's 218 gen functions, 176 carry their name in gen
  and 42 stay `sub_`: 36 named in `recomp_manual.c` (comments included)
  and 6 hook slots.
- [x] 3.3 Normalising diff (names mapped back to `sub_`, the added comments
  stripped) against the stock regen: empty.
- [x] 3.4 A second `analyze && recomp`: no gen file's mtime moves.
- [x] 3.5 Review fixes: reserved names (x86 registers, `_`, `g_`,
  `recomp_`), idempotent annotation, no names in recomp's own comments,
  recomp applies the map first; header statics count in the toolkit clash
  test. Regen again: normalising diff empty, annotating annotated gen
  changes no file.

## 4. Gates

- [x] 4.1 Windows golden on the PC (`BENCH_BUILD_HOST=bench host-win`): attract
  pass-with-known the tracker item, stage1 pass, story pass-with-known the tracker item.
  Again on the rework (cat 6f35e4ba, toolkit 11e099c2, exe 0d6e3399):
  attract pass-with-known 34.7 flips/s, stage1 pass 33.4, story
  pass-with-known 49.6; no Deck run (the user had it).
- [x] 4.2 `sh notes/build-all.sh` (active set: BLiNX 2, BLiNX 1, KUF;
  macOS and Windows natively on the PC, `TOOLKIT=xboxrecomp` 11e099c2,
  `CLI=xboxrecomp-cli` d777966, `blinx2-tk` on this branch): 6/6 pass. The
  other games do not set `symbols`, so the change is inert there.
- [x] 4.3 Review; merged by the orchestrator (cat ad032a77, the tracker item Done).
