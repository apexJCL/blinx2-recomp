Conventions: **CLI** = branch `feat/xbe-fingerprint` off `xboxrecomp-cli`
`main` (a00a9c7), noreply identity, no tracker ids. **cat** = branch
`feat/xbe-fingerprint` off cat `main` (5e2e35b). Decisions D1-D9 are in
design.md. Tests use synthetic XBEs, never game data.

## 1. Fingerprint (CLI)

- [x] 1.1 `fingerprint.py`: section hashes, the code set (D2), the
      classification and the messages (D3), and the cache (D5).
- [x] 1.2 `manifest.py`: `xbe.sections` (string table, sha256 values),
      `data.reference_files` (int >= 0) and `package.stamp_env` (an env
      name or `""`).
- [x] 1.3 `xbr fingerprint [PATH] [--toml] [--json]`.

## 2. Warn, never block (CLI)

- [x] 2.1 `doctor`: the game files line carries the verdict, plus the
      `assets:` line (D9); `dump_state` keeps its shape.
- [x] 2.2 `import`, `package`, `analyze`, `build`: one warning each, then
      they go on (D4).
- [x] 2.3 `bench golden` unchanged; its test gains a header-only XBE that
      is still refused.

## 3. Stamps (CLI, cat)

- [x] 3.1 `write_manifest`: `xbe` {sha256, verdict, sections} (D6).
- [x] 3.2 `stage`: append the `stamp_env` line to `launch.env.default`;
      none when `stamp_env` is empty (D7).
- [x] 3.3 cat: `RECOMP_BUILD_XBE` row, `[BOOT] build xbe:` line,
      `docs/env.md` row, and `game.toml` `[xbe.sections]`,
      `reference_files`, `stamp_env`.

## 4. Plan and wizard (CLI)

- [x] 4.1 `package --plan --json`: `xbe` for the dump the run builds from
      (D8).
- [x] 4.2 wizard: `Plan.Xbe`; "Build anyway" confirm on `code`; Summary
      line on `data`; Go tests.

## 5. Tests and gates

- [x] 5.1 CLI tests: known, header-only, modded data, modded code,
      unknown (no table), manifest field, stamp line on and off, plan
      field, golden refusal.
- [x] 5.2 CLI `uv run pytest tests`, ruff, `wizard/check.sh`; cat `uv run
      pytest scripts`, ruff.
- [x] 5.3 Real runs on the Mac: `doctor` on cat's game_files, and on
      copies under `runs/xbe-fingerprint/` with one data byte and one code
      byte changed.
- [x] 5.4 Runtime gate: Mac build, one Metal golden; one short packaged
      boot on the Deck showing the `[BOOT] build xbe:` line (ask the
      orchestrator first).
