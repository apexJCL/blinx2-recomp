## Why

The CLI knows a dump only by the whole `default.xbe` sha256 (`[xbe]
sha256` in `game.toml`). Today any other XBE gets a one-line "unknown
dump" warning (`dump.py:704`, `package/__init__.py:384`,
`doctor.unknown_dump_note`), and the manifest records `"xbe": "unknown"`.
That warning can't tell apart the three cases that matter for support:

- **Header only.** The two dumps we know, 0c57fd72 and aa186954, have the
  same section bytes and differ only in the header. A third disc that
  differs the same way runs exactly the generated code.
- **Modded data.** Replaced textures, text or tables in data sections.
  The code is stock, so the recompiled functions still match.
- **Modded code.** Patched code sections. The generated code no longer
  matches what the XBE expects, so the game may crash.

A tester's crash came from a third XBE (38,551,552 bytes, against
38,543,360 and 38,541,312 for the known two). Nothing in the game log
flagged it, so triage had to guess.

The user's decisions (2026-10-18), fixed for this change:

1. Fingerprint each section. `game.toml` lists the known section hashes.
   An unknown XBE is classified as header-only (known, no warning),
   modded data ("code stock"), or modded code ("unsupported, may crash",
   naming the sections).
2. Never block in the CLI or the wizard. Modders who patch `default.xbe`,
   and players who replace assets, must still be able to build. The wizard
   shows one confirm screen ("Build anyway") on modded code. Only `bench
   golden` keeps refusing unknown dumps.
3. Stamp the XBE sha256 and the verdict in the build manifest and in the
   first lines of the game log at boot.
4. Assets are informational only: `doctor` reports the file count against
   the reference dump's count and never blocks.

Mod support (the analyzer finding functions a mod adds) is out of scope.

## What Changes

- **game.toml (cat):** `[xbe.sections]` maps each section name to the
  sha256 of its raw bytes. The table holds for both known XBEs.
  `[data] reference_files = 485` is the reference dump's file count.
  `[package] stamp_env = "RECOMP_BUILD_XBE"` names the boot-log key.
- **CLI `fingerprint` module:** classifies an XBE as `known`, `header`,
  `data`, `code` or `unknown` from the manifest's tables. Code sections
  are the ones the pipeline disassembles (`pipeline.disasm`). The module
  has no game constant of its own.
- **CLI messages:** `import`, `analyze`, `build`, `package` and `doctor`
  print the verdict's warning and go on. `doctor` gains an `assets:`
  line. `xbr fingerprint [PATH] [--toml]` prints the verdict for a dump,
  an image or an XBE, or the `[xbe.sections]` table for it.
- **Manifest:** `manifest.json` gains `xbe` = `{sha256, verdict,
  sections}` on every build. It replaces `"xbe": "unknown"`.
- **Boot stamp:** with `stamp_env` set, `package` appends `KEY=<sha256>
  <verdict>[ <sections>]` to the staged `launch.env.default`. Every
  launcher already exports that file. cat's `main.c` prints `[BOOT] build
  xbe: <value>` once, right after the stdio setup, and prints nothing when
  the key is unset or empty.
- **Plan and wizard:** `package --plan --json` gains `xbe` for the dump
  the run would build from: the `--dump` source, else `game_files/`. The
  wizard's Build button asks "Build anyway" when the verdict is `code`,
  and the Summary names a `data` verdict.
- **bench golden:** unchanged. It refuses any XBE not in `[xbe] sha256`,
  header-only ones included.

## Impact

- CLI: `fingerprint.py` (new), `manifest.py`, `doctor.py`, `dump.py`,
  `main.py`, `package/__init__.py`, `package/plan.py`, wizard
  `runner.go` and `screens/`, docs. The edits to `doctor` and `package`
  are small and local, because the tracker item changes them in parallel.
- cat: `game.toml`, `src/main.c` (one printf), `src/env/recomp_env_game.h`
  (one row), `docs/env.md`. This is a runtime change, so it gates on one
  Metal golden on the Mac and one short packaged boot on the Deck under
  Proton.
- Toolkit: none.
