## Context

The enhancements layer (`xboxrecomp/src/enhance/`, opt-in with
`XBOXRECOMP_ENHANCE=ON`) answers typed lookups by dotted key from two
slots, title and root, under the environment. As built today
(`enhance_cfg.c`):

- `enhance_cfg_init(root, title)` loads `<root>/<title>/enhance.toml`
  (slot 0) and `<root>/enhance.toml` (slot 1), or the one file
  `RECOMP_ENHANCE_CONFIG` names into slot 0, or nothing for `none`; it
  logs `[ENHANCE] config: <files> (N keys)` and one line per environment
  override. cat passes `root = recomp_exe_dir()`, `title = NULL`
  (`src/main.c:1360`).
- A lookup takes the bound environment variable, then the first slot
  holding the key, then the caller's default; a wrong type is said once
  and the next tier answers; `enhance_cfg_report_unused` lists the keys no
  lookup read; `enhance_cfg_file(i)` hands the parsed slots to prefix
  scans (`aspect.program.<hash>`); `enhance_cfg_source_of` answers
  `DEFAULT`, `ENV` or `FILE`.
- `textures.pack` resolves a relative path against `root`
  (`enhance.c load_tex_pack`), "the root the file itself is read from",
  so a bundle names `enhance/hud.pack`.
- `RECOMP_ENHANCE_CONFIG` is a `CONFIG` row of `RECOMP_ENV_ENHANCE_KEYS`
  with `LEGACY = NULL`. `recomp_env.c` honours a row's legacy name when
  the new one is unset and prints `[ENV] <old> is deprecated; use <new>`
  once per run (`RECOMP_LOG_LEVEL` / `XBOX_LOG_LEVEL` is the live
  example).
- `tests/enhance_cfg/test_main.c` (222 checks) writes files under
  `ecfg_root/`, drives the layering through `recomp_env_set` and pins the
  `[ENHANCE]` lines the golden check reads.

Packaging: `blinx2 package` copies the game's
`packaging/enhance.toml.default` into the payload (CLI
`package/__init__.py write_common`), `--hud-pack` appends `[textures]` to
that staged copy (`stage_hud_pack`), and the three launchers copy it to
`config/enhance.toml` when absent, refresh `config/enhance.toml.default`
every launch and set `RECOMP_ENHANCE_CONFIG` (CLI
`templates/steamos/launch.sh:69-74,104`, `templates/windows/launcher.c:189-199`,
cat `packaging/macos/BLiNX2.in`). `install.sh` / NSIS install and
uninstall exactly the staged files (`nsis_lists`). b3 ships the same
template through the same CLI templates but does not call the layer.

Goldens: `analysis/golden/golden.json` pins `RECOMP_ENHANCE_CONFIG=none`
with the per-key pins; `golden.py` reads only the `[ENHANCE]` key lines,
not the `config:` line. The CLI's `tests/testdata/golden.json` and
`bench_parity.json` carry the same pin.

Decisions already made (the user, 2026-10-11, in `enhance-menu-preview`
design P1 and "Decided" 4) are not reopened here: two files, differences
only, env on top, automatic rename, enhancement and mod keys only, the
per-title file kept, `config/` in the repository for a developer tree,
this change before the menu.

## Goals / Non-Goals

Goals: the runtime reads a shipped defaults file and a user differences
file under the environment; a bundle upgrade's new keys apply; the
rename of the variable, the files and the docs; the launchers and
`package` follow; goldens stay stock by construction; the layer exposes
what phase 3's Save needs; every behaviour testable standalone has a
ctest case.

Non-goals: the patcher and Save (3.5), the menu, `launch.env` rows, new
keys, b3's wiring, a compatibility window for `enhance.toml`.

## Decisions

### D1. Four layers, two files, one API (toolkit)

For a key, the first of these with a value wins:

1. the bound environment variable (`RECOMP_RENDER_SCALE`, ...), as now;
2. `<root>/<title>/config.toml`, the per-title user file (when `title` is
   given);
3. `<root>/config/config.toml`, the user file; or the one file
   `RECOMP_CONFIG=<path>` names, which replaces 2 and 3;
4. `<exe dir>/config.default.toml`, the defaults file shipped with the
   build, **read and never written**;
5. the caller's code default.

`enhance_cfg_init(root, title)` keeps its signature and meaning for the
user files; `root` is the **user data root**, not the executable's
directory any more. The defaults file is found by the layer itself from
`recomp_exe_dir()` (the test already links `recomp_exe_dir.c`), so no
caller has to know two roots. Slots become three: 0 title, 1 user root
(or the `RECOMP_CONFIG` file), 2 defaults. `enhance_cfg_file(0)` and
`(1)` keep their meaning for the prefix scans; `enhance_cfg_file(2)` is
the defaults file. `ENHANCE_FILES` is 3. The user file's old location
`<root>/enhance.toml` moves under `config/` because that is where every
launcher already puts the player's files (`config/launch.env`) and where
the repository keeps its inputs (D7).

The log line names each file with its own key count, so the layering is
visible in every run log:

```
[ENHANCE] config: build/config.default.toml (9 keys), config/config.toml (1 key)
[ENHANCE] config: none (RECOMP_CONFIG)
[ENHANCE] config: Z:/home/deck/Games/BLiNX2/current/config.default.toml (10 keys), Z:/home/deck/Games/BLiNX2/config/config.toml (0 keys)
```

A file that does not parse is reported with its line and skipped whole,
defaults file included (a packaging bug is then one visible line, and
the run is stock). `enhance_cfg_report_unused` reports the defaults
file's unread keys too; a key the title or user file overrides counts as
used, as today (the slot order makes the existing `j < i` check cover
it). `enhance_cfg_source_of` gains `ENHANCE_SRC_DEFAULTS` (the value
came from `config.default.toml`), appended to the enum so `DEFAULT`,
`ENV` and `FILE` keep their numbers.

### D2. `RECOMP_CONFIG`, with `RECOMP_ENHANCE_CONFIG` as the legacy name (toolkit)

The row becomes
`X(CONFIG, CONFIG, "RECOMP_CONFIG", "RECOMP_ENHANCE_CONFIG", "configuration: the user's config.toml (a path), or none for no file at all; default <root>/<title>/config.toml, <root>/config/config.toml; config.default.toml beside the executable is read under it")`
(enum `RENV_CONFIG`). The table already resolves a legacy name when the
new one is unset and prints the deprecation line once, so the old name
costs nothing and goes when the row's `LEGACY` is dropped later.

Values:

- `RECOMP_CONFIG=<path>`: the user file, replacing layers 2 and 3. The
  defaults file (layer 4) is still read. This is what every launcher
  sets (`<data>/config/config.toml`), so a bundle's shipped defaults apply
  under the player's choices.
- `RECOMP_CONFIG=none`: **no file at all**, neither user nor defaults.
  `none` keeps its golden meaning, "every key at its code default plus
  the environment", whatever the shipped `config.default.toml` says. A
  bundle's defaults file will turn the menu on (phase 5) and name a pack
  (`--hud-pack`); a golden must not see either even if a per-key pin
  were dropped by mistake, and phase 3's Save is dimmed under `none`
  because there is no user file.
- unset or empty: the default locations.

### D3. The user file: where it is, who creates it (toolkit, launchers)

Default locations are D1's. The launchers name the file explicitly, as
they do today, so the data root never has to be guessed from the
executable: `RECOMP_CONFIG=<data>/config/config.toml` (SteamOS in the
`Z:` form).

When the user file the layer would read is absent and its directory
exists, `enhance_cfg_init` creates it as a comment header (no key), so the
player finds a file to edit that says where the defaults are:

```toml
# BLiNX 2 settings. Only the keys you change go here; every other key
# comes from config.default.toml beside the game's executable (read, not
# copied: a new version's keys apply to you too). The in-game menu writes
# this file. Environment variables (config/launch.env) override it.
```

(The product name comes from the title the game passes, or is omitted
when `title` is NULL; the toolkit writes a generic first line.) The layer
never creates a directory, never writes under `RECOMP_CONFIG=none`, and
says once and goes on when the write fails (a read-only location). The
launchers already `mkdir -p config/`; a developer tree has `config/`
(D7). The header is written to the title file when `title` is given and
that directory exists, else to the root file: the file Save will target
(D5).

### D4. Migration: one automatic rename, in the runtime (toolkit)

Before loading a user file at a location (the `RECOMP_CONFIG` path when
its basename is `config.toml`; else `<root>/<title>/config.toml` and
`<root>/config/config.toml`), if that file is absent and `enhance.toml`
exists in the same directory, the layer renames it (`rename(2)`;
`MoveFileExW` semantics under Wine are the same for a rename within one
directory) and logs one line:

```
[ENHANCE] config: renamed Z:/.../config/enhance.toml to config.toml (one-time migration)
```

A rename that fails is said once and the run goes on without that file.
The old root location `<root>/enhance.toml` (a developer's build
directory) is not migrated: there is no user base, and a developer sets
`config/config.toml` by hand. A `RECOMP_CONFIG` path with another
basename (`ecfg_init.toml` in the tests) is never a rename candidate. The
keys are the same, so a renamed full copy works as it is; its keys equal
to the defaults are harmless under D5 and disappear at the first Save or
Reset.

The launchers do not rename. They stop copying the template, delete the
stale `config/enhance.toml.default` they themselves wrote (the runtime
never deletes a file), and set `RECOMP_CONFIG`. One implementation of
the rename, covered by one ctest, serves the three launchers, a developer
tree and b3 alike. The deployment promise "install, update, rollback and
uninstall leave `config/` byte-identical" holds: the rename and the
deletion happen at **launch**, by the runtime and the launcher, as the
launcher's copy did before.

### D5. Differences only: the contract here, the writer in phase 3 (toolkit)

`config.toml` holds the keys whose value differs from
`config.default.toml`. This change fixes the contract and exposes what a
writer needs; the comment-preserving patcher `recomp_cfg_patch` and Save
are `enhance-menu-preview` 3.5 and D8:

- `const char *enhance_cfg_user_path(void)`: the file Save writes, the
  title file when one was read (or created), else the user root file or
  the `RECOMP_CONFIG` file; NULL under `none`. Phase 3 dims Save on NULL.
- `const recomp_cfg *enhance_cfg_defaults(void)`: the parsed defaults
  file (slot 2), or NULL. A writer compares a new value with
  `recomp_cfg_*` on it and, when the key is absent there, with the item's
  own code default; equal means delete the key, different means write
  it.
- `ENHANCE_SRC_DEFAULTS` (D1) lets the menu show where a value comes
  from and mark an env-forced item.

The ctest covers the contract from the read side: with defaults
`scale = 1` and a user file `scale = 2`, the lookup is 2 from `FILE`;
with the user file removed it is 1 from `DEFAULTS`; `enhance_cfg_user_path`
names the right file in each configuration (title, root, `RECOMP_CONFIG`
path, `none`); `enhance_cfg_defaults` answers the defaults file's values.

### D6. `textures.pack` stays relative to the executable (toolkit)

`load_tex_pack` resolves a relative pack path against `recomp_exe_dir()`
instead of `root`, because `root` is now the user data root and the pack
sits beside the executable (`enhance/hud.pack`;
`../Resources/enhance/hud.pack` on macOS). This is the documented rule
("relative to the executable's directory") and what `--hud-pack` writes
into `config.default.toml`, which lives in the same directory. An
absolute path is taken as it is.

### D7. A developer tree reads `config/config.toml` in the repository (cat)

cat already runs from the repository root during development
(`RECOMP_GAME_FILES` defaults to `game_files/` in the working directory;
`blinx2 golden run` starts the executable with `cwd = game.root`). So
`src/main.c` passes the working directory as the user root,
`xbox_enhance_init(".", NULL)`: a developer's choices live in
`cat/config/config.toml` (gitignored, beside the pipeline inputs), and
nothing bakes a source path into a binary (a bundle's executable is the
same build; a baked path would also trip the public audit). CMake copies
`packaging/config.default.toml` beside the built executable at build
time, so the defaults layer exists in a developer build and a stale copy
cannot survive an edit of the template. In a bundle the launcher's
`RECOMP_CONFIG` makes `root` irrelevant.

### D8. Launchers, `package` and `--hud-pack` (CLI, cat)

- `write_common` stages `packaging/config.default.toml` as
  `config.default.toml` beside the executable: top-level in the Windows
  and SteamOS payloads (the `enhance/` subdirectory fix, TASKS (d), is
  unrelated), `Contents/Resources/config.default.toml` on macOS, where the
  app's other read-only files are. The layer finds it: on Apple platforms,
  when `<exe dir>/config.default.toml` is absent, it looks at
  `<exe dir>/../Resources/config.default.toml` (the bundle layout the pack
  path already encodes). No new variable.
- A game whose `packaging/` has `enhance.toml.default` and no
  `config.default.toml` is refused before building, with the rename named:
  the templates and the game's content must agree, and a silent fallback
  would ship a launcher that reads one name and a payload that carries
  the other. b3 renames its file in the tracker item before it re-pins.
- `stage_hud_pack` appends the `[textures]` table to the staged
  `config.default.toml`. Because the runtime reads that file, the key
  applies on an upgrade too: the "copy the line yourself" step of
  `packaging.md` §6 and the README goes away, and the player turns the
  pack off with `pack = "none"` in `config.toml` (the layer treats `none`
  as unset, as today).
- `launch.sh`, `launcher.c`, `BLiNX2.in`: `mkdir -p config/`, remove
  `config/enhance.toml.default` if present, export
  `RECOMP_CONFIG=<data>/config/config.toml`. Nothing is copied. NSIS and
  `install.sh` install and uninstall `config.default.toml` like any staged
  file (the lists are generated from the payload).
- `README.txt.in` (the bundle's README) and `docs/manifest.md`
  (`[package] content`) name the new file and the rule in two sentences.
- The CLI's test fixtures (`tests/testdata/game/analysis/golden/golden.json`,
  `tests/testdata/bench_parity.json`) pin `RECOMP_CONFIG=none`; the
  parity fixture's `GAME_ENV` string follows because it is rendered from
  that `golden.json`.

### D9. Goldens and pins (cat, CLI)

`analysis/golden/golden.json` pins `RECOMP_CONFIG=none`; nothing else
moves (`game.toml [golden] enhance_stock`, the CLI's `ENHANCE_STOCK`
table and `golden.py` read key lines, not the variable). A run started
with the legacy pin prints `[ENV] RECOMP_ENHANCE_CONFIG is deprecated;
use RECOMP_CONFIG` and is otherwise stock; the Mac check runs it once so
the legacy path is seen working.

### D10. Docs

Toolkit: `git mv docs/runtime/enhance-config.md docs/runtime/config.md`,
first section "Two files and the environment" with the layering table,
the `RECOMP_CONFIG` row (legacy name noted), the migration paragraph, the
API additions; every reference follows (`docs/formats/texture-pack.md`,
`docs/pipeline/04-lifting.md`, `src/enhance/CMakeLists.txt`, `enhance.h`,
`enhance_cfg.h`, `recomp_cfg.h`). cat: `docs/env.md` row
`RECOMP_ENHANCE_CONFIG` → `RECOMP_CONFIG` in the Old/New columns (the
Config count stays 43; the intro sentence and the "Enhancements file"
section are rewritten for the two files), `docs/packaging.md` §6 and
`### Your HUD texture pack`, the README `Options`, `HUD texture pack` and
`Environment variables` sections, `packaging/config.default.toml`'s own
header. The `enhance-menu-preview` spec deltas still say
`RECOMP_ENHANCE_CONFIG` in two places; they are updated on the phase-3
branch (tasks).

### D11. Backends agree

No backend, presenter or kernel code changes. Metal and D3D11 receive
the same `nv2a_host_opts` from the same reader; the CPU rasteriser is
untouched.

## What b3 inherits (not in this change)

After this merge b3 wires the layer as cat did (cat 627b578): build with
`XBOXRECOMP_ENHANCE=ON`, `xbox_enhance_init(".", NULL)` in its `main.c`
before the guest starts, `enhance_cfg_report_unused()` after its own
keys, `packaging/config.default.toml` (every key stock, its header saying
the file is read), `RECOMP_CONFIG` in `packaging/macos/Burnout3Takedown.in`
(which copies nothing today), `RECOMP_CONFIG=none` and the per-key pins in
its golden configuration, the CLI tag re-pinned in its `game.toml`. The
Windows and SteamOS launchers come from the CLI templates and need no b3
change.

## Risks / Trade-offs

- **`none` reads no defaults file.** A developer who wants "the shipped
  defaults but not my file" has no value for it; they move their
  `config/config.toml` aside. Accepted: `none` is the golden pin and must
  mean stock without reading any file.
- **Two roots in one call.** `root` changes meaning (user data root, was
  the executable's directory). cat is the only caller and changes in the
  same merge; b3 gets the new meaning from the start; the header and
  `config.md` say it plainly. `textures.pack` resolution moves to the
  executable's directory explicitly (D6) so nothing silently depends on
  `root`.
- **Rename and header creation write under `config/` at launch.** Both
  are one-shot and said in the log; the launcher's template copy wrote
  there on every launch before. A read-only data root gets one line each
  and a stock-plus-defaults run.
- **Wine paths.** The rename and the header creation run on `Z:` paths
  under Proton; `rename` and `fopen` through the CRT are what the layer
  already uses for reads, and the Windows bundle check (tasks) exercises
  the upgrade path.
- **macOS `Resources` lookup.** A second probe on Apple platforms only,
  at init, when the first path is absent. The alternative (staging a
  text file in `Contents/MacOS`) was rejected: `codesign --deep --strict`
  treats that directory as code, and the pack path already encodes the
  `Resources` layout.
- **The ctest grows past 222 checks** and keeps the pack-line pins that
  `golden.py` reads; the Proton CRT's `\r\n` stderr (hud-pack 8.1b) is
  handled as before.
- **CLI refusal of `enhance.toml.default`** breaks `package` for a game
  that has not renamed its template. Only b3 is in that position and it
  pins its own CLI sha; the refusal names the rename.

## Migration Plan

One worktree set, `wt/config/{cat,xboxrecomp,xboxrecomp-cli}`, one
agent, in this order: toolkit (D1-D6, D10, the ctest), CLI (D8, tagged),
cat (D7-D10, the CLI tag re-pinned), Mac gates, Proton on "go",
review, squash merges. `enhance-menu-preview` phase 3 starts after the
merge and builds Save on D5.

Rollback: `RECOMP_CONFIG=none` is stock; a `config.default.toml` at
stock values changes nothing; a player's `config.toml` is their old
`enhance.toml` renamed, so the previous release reads it again after a
rename by hand. A build without `XBOXRECOMP_ENHANCE` reads no file.

## Recorded decisions (the user, 2026-10-11)

The eight open questions of the spec were answered by the user on
2026-10-11, who accepted every recommendation. They are decisions now;
the rejected alternatives are kept for the record.

1. **Does `RECOMP_CONFIG=none` also skip `config.default.toml`?**
   Decided: yes (D2). `none` is the golden pin and means "code
   defaults plus the environment" whatever the shipped file says; Save is
   dimmed under it anyway. Alternative: `none` skips the user file only
   and a second word (`stock`) skips both; rejected as a second spelling
   for the pin that every golden fixture would have to learn.
2. **Who renames `enhance.toml`: the runtime, the launchers, or both?**
   Decided: the runtime alone (D4); the launchers only delete the
   stale `config/enhance.toml.default` and set `RECOMP_CONFIG`. One
   implementation, one ctest, the same behaviour for a developer tree and
   for b3. Alternative: both; rejected as two copies of a one-shot.
3. **Who creates the empty `config.toml`?** Decided: the runtime, as
   a comment header, only when the directory exists (D3). The user's
   wording was "created as a comment header on first launch"; Save
   (phase 3) can then patch an existing file in every case. Alternative:
   leave it to Save; rejected because a player who wants to edit by hand
   would find no file.
4. **Where does the macOS app carry `config.default.toml`?** Decided:
   `Contents/Resources`, with the layer's Apple-only `../Resources` probe
   (D8). Alternative: beside the executable in `Contents/MacOS`; rejected
   for `codesign --deep --strict` (a non-code file where the signature
   expects code) and because the pack path already points at
   `Resources`.
5. **Does the CLI fall back to `enhance.toml.default` when a game has not
   renamed it?** Decided: no, refuse with the rename named (D8).
   Only b3 is affected and it re-pins the CLI in the tracker item.
6. **How does a developer build find the repository's
   `config/config.toml`?** Decided: the working directory is the user
   root (`xbox_enhance_init(".", NULL)`, D7), as `game_files/` already
   resolves from it. Alternatives: a compile-time source path (bakes a
   private path into every binary, including bundles), or the CLI setting
   `RECOMP_CONFIG` for developer runs (a plain `./build/cat_recomp` would
   then read nothing).
7. **Is the user file `<root>/config/config.toml` or `<root>/config.toml`?**
   Decided: under `config/` (D1), where the launchers keep
   `launch.env` and the repository keeps its inputs; the per-title file
   stays `<root>/<title>/config.toml` as implemented.
8. **A tagged CLI release for this change?** Decided: yes, `v0.5.0`
   (`cli-tag-pins`: prefer tags), since the payload file name and the
   launcher templates change together and cat's `game.toml` re-pins to it
   in the same merge.
