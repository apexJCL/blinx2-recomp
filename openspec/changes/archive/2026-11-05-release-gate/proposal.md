## Why

A player can hold another release of a game than the one a port was made
from: another region (PAL, NTSC-J) or a later version of the same title.
Its XBE is a different binary, so the lifted code, the seeds, the hooks and
the manual file's `sub_X_gen` wraps no longer line up. Today the pipeline
does not say so:

- `fingerprint` reads the certificate's title ID only. A PAL dump of BLiNX 2
  shows up as "code sections differ", the same words as a modded dump, and
  nothing names the two releases.
- `import` refuses any other title ID, also when the dump is the same game
  under another region's ID.
- The wizard asks before a build only for modded code. An unknown or
  truncated dump, or another release, builds without a word.
- `recomp` lets a declared `sub_X_gen` wrap with no generated body through;
  the link then fails on an undefined symbol, far from the cause.
- BLiNX 1 (and KUF) pin no sha256 and no `[xbe.sections]`, so the check is
  off for them.

## What Changes

- **CLI, release facts**: `xbe.cert_release` reads the certificate's
  alternate title IDs (+0x5C), region flags (+0xA0) and version (+0xAC).
  `[xbe]` gains optional `region`, `version`, `title` and `alt_title_ids`
  (the reference release; all default to unset). `fingerprint --toml`
  prints them for the dump it reads.
- **CLI, fingerprint**: a dump whose region or version differs from the
  manifest's is "another release". The verdict values stay as they are
  (known, header, data, code, unknown); the release is extra fields. The
  note, the doctor line, the plan record (`release`, `reference_release`,
  `other_release`, `region`, `version`, `why`) and the build stamp
  (` release=PAL,v2`) name both releases.
- **CLI, import**: another title ID is imported with a warning when one
  side's alternate title IDs name the other, or the normalized certificate
  title matches the game's; otherwise it is still refused.
- **Wizard**: unknown, truncated and other-release dumps get a Summary line
  and the build-anyway dialog that modded code already has (no default
  button, the way back first).
- **Toolkit, recomp**: a declared `sub_X_gen` wrap whose address gets no
  generated body fails the run, naming each address, why (not a function in
  this XBE's analysis, or inside another function), and that the dump may
  be another release. Code references to `sub_` names that are not known
  functions only warn.
- **BLiNX 1**: pin the known dump's sha256 and `[xbe.sections]` (works on
  CLI v0.20.0). The reference release keys come in a held commit, as for
  cat, until the `[cli]` pin moves to a CLI that knows them.

## Impact

- CLI: `xbe.py`, `manifest.py`, `fingerprint.py`, `dump.py`,
  `package/__init__.py`, `main.py`; docs (`manifest.md`, `commands.md`),
  README, CHANGELOG; wizard `runner`, `screens` (`copy.go`, `output.go`,
  `wizard.go`).
- Toolkit: `tools/recomp/__main__.py`, `tools/recomp/manual_scan.py`, a new
  `tools/recomp/test_manual_wraps.py`.
- cat: `game.toml` `[xbe]` release keys and the `RECOMP_BUILD_XBE` row in
  `docs/env.md` (held for the pin move).
- blinx: `game.toml` sha256 and sections (now); release keys (held).
- No generated code changes: the BLiNX 2 and BLiNX 1 regens stay byte
  identical, and no game in the pool trips the new recomp error.
