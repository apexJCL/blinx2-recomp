Spike the tracker item (`notes/release-matcher/release-matcher.md`).

- Worktrees `wt/release-names/{cat,xboxrecomp-cli,xboxrecomp,blinx}` on
  `feat/release-names` (CLI off `spike/release-matcher` 4e0fb09, toolkit
  off `posix-host/portability` a98c6893, blinx off main 96f9b12, cat off
  main 3f93fae8); scratch `xbox-recomp/runs/release-names/`.

## 1. CLI

- [x] 1.1 `manifest.py`: `[pipeline] names`, `releases`.
- [x] 1.2 `names.py`: load and check `names.toml` and release files (D2,
  D3); `select` (D4); `header` (D5); the source scan (D6); seeds (D8).
- [x] 1.3 `pipeline.py`: resolve before disasm and recomp, `--names`,
  `gen/recomp_names.h`, gen key inputs (D9).
- [x] 1.4 `match` verb: parse and disasm the other dump, run the matcher,
  write the release file, keep `reviewed` rows (D3).
- [x] 1.5 Docs (`names.md`, `manifest.md`, `commands.md`), CHANGELOG.
- [x] 1.6 Tests: loading and errors, selection cases, header text, scan,
  seeds, release file round trip, match on a synthetic pair.

## 2. Toolkit

- [x] 2.1 `manual_scan`: `_live`, `XBR_HAVE` blocks, name forms (D7).
- [x] 2.2 `recomp --names`; stop on a missing name.
- [x] 2.3 `test_manual_names.py`.

## 3. BLiNX 1

- [x] 3.1 `config/names.toml`; `[pipeline] names`.
- [x] 3.2 `recomp_manual.c`, `far_cull.h`, `main.c`, seeds in the name form.
  (The far-cull address moved from `far_cull.h` to `draw_distance.c`, so
  the header and its test driver stay free of the generated names.)
- [x] 3.3 `blinx1 match` on PAL v3; review against the spike's table;
  fence values by hand; `config/releases/pal-v3.toml`.
- [x] 3.4 `scripts/test_names.py`.

## 4. Gates

- [x] 4.1 CLI pytest and ruff.
- [x] 4.2 Toolkit `pytest tools/recomp tools/disasm`.
- [x] 4.3 blinx `uv run pytest scripts` and ruff.
- [x] 4.4 NTSC regen byte-identical to the base regen (every gen file;
  `recomp_names.h` new).
- [x] 4.5 PAL: analyze, recomp, macOS build, boot to the title screen on
  Metal (`SDL_AUDIODRIVER=dummy`), screenshot in `runs/release-names/`.
- [x] 4.6 `notes/build-all.sh` with this toolkit and CLI.

## 5. Review fixes (review)

- [x] 5.1 `select`: the sha256 of a release file first; header and data
  keep the reference whatever `other` says (D4).
- [x] 5.2 `names.json` carries a `have` list (values too); the toolkit's
  `strip_missing` reads it (D7).
- [x] 5.3 The source check refuses unknown names in `XBR_HAVE` and any
  non-plain `XBR_HAVE` use; it runs at build and package too (D6).
- [x] 5.4 Release files: refuse the reference's sha256 and a sha256 two
  files list; warn on a `reference` not in `[xbe] sha256`.
- [x] 5.5 `ref` per release row: a stale row stops `select`, and `match`
  sends it back to `unsure`.
- [x] 5.6 Seeds: a row with `name` and `start` is refused; resolved seeds
  keyed by path.
- [x] 5.7 Values: negatives in signed decimal; inf and nan refused. The
  review warning counts `sure` rows too.
- [x] 5.8 Gates rerun (section 4) and the BLiNX 1 Windows build on the Mac.

## 7. Later

- [ ] 7.1 BLiNX 2: hooks, `[mods] hook_functions`, spin waits, HUD call
  sites and `recomp_manual.c` in the name form, names pointing at
  `symbols.toml` rows.
- [ ] 7.2 `[extract]` roots followed through the mapped table address.
- [ ] 7.3 PAL 50 Hz: per-release vblank rate and timing values.
- [ ] 7.4 Matcher hardening (align speed, `calls` pass, a second pair).
- [ ] 7.5 Wizard: the another-release dialog names `match` when no map.
- [ ] 7.6 The fingerprint's "another release ... may fail" warning names
  the reviewed release map that will be used, when there is one.
