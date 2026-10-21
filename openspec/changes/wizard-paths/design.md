## Context

cat `main` 7158b61 and `xboxrecomp-cli` `main` 30f599c (v0.8.0, which
has `wizard-incremental-builds`). Facts below are from reading those
trees on 2026-10-17. Nothing was built or run for this spec. Paths are
in `xboxrecomp-cli/` unless they start with `cat/`.

How a patch is made today:

- `package()` stages the payload, writes the manifest, then `wrap()`
  calls `patch.choose` on the new manifest
  (`src/xboxrecomp_cli/package/__init__.py:1019-1100`, `:849-869`).
- `patch.choose` (`package/patch.py:290-319`):
  - `--full` makes the full bundle;
  - `--patch-from` makes a patch against that base, refused when
    `problems()` names a reason, but with **no half-size rule**;
  - otherwise it takes the version installed on this host
    (`host_base`, `:228-268`), applies the half-size rule, and falls back
    to the full bundle with a reason line.
- A bundle record (`.git/xbr/bundles/<target>/<sha256>.json`,
  `package/incr.py:528-584`) is a base only when `--patch-from` names it
  (`wizard-incremental-builds` design, implementation notes).
- `package --plan --json` lists the records as `bases` and predicts the
  output (`package/plan.py:248-361`). Its import row is always "reuse"
  without `--dump` (`plan.py:88`).

How the HUD pack reaches a bundle:

- `--hud-pack [DIR]` (`main.py:196-204`) names `DIR/hud.pack`, default
  `dist/enhance/hud/hud.pack` (`hud_pack_path`, `__init__.py:442-457`).
- `stage_hud_pack` copies it to the payload's `enhance/hud.pack` and
  appends a `[textures]` table with `pack = "enhance/hud.pack"`
  (`../Resources/enhance/hud.pack` on macOS) to the staged
  `config.default.toml` (`:507-547`). `check_content` refuses a game
  whose `config.default.toml` already has a `[textures]` table
  (`:476-504`); cat's is commented out (`cat/packaging/config.default.toml:40-47`).
- The manifest records `enhance.hud_pack` (`sha256`, `scale`, `entries`,
  `path`; `__init__.py:673-674`), and the pack's sha256 is part of the
  `-o` options digest (`lib.py:259-281`, called at `__init__.py:388-389`).
- Without the flag, nothing is staged, so the new manifest has no
  `enhance/hud.pack` and the patch lists it as deleted. The orchestrator
  confirmed on 2026-10-17 that add, remove and rework already go through
  the file list.
- `enhance hud` writes `hud.pack` in place: `open(path, "wb")`
  (`enhance/pack.py:106`). It is skipped when its stage key is current
  (`enhance/hud.py:340-348`). The key's inputs are the `[enhance.hud]`
  config digest, scale, languages, `--only`, the font's sha256, the XBE,
  the output folder and the CLI tree, plus the import key
  (`hud_record`, `:472-497`).
- The runtime treats a missing or bad pack as stock, with a log line
  (`xboxrecomp/src/enhance/enhance.c:26-55`).
- The Windows full installer deletes an in-place install's
  `enhance\hud.pack` during the migration and on uninstall
  (`templates/windows/installer.nsi.in:106`, `:188`). Versioned installs
  keep each version's own `enhance\`.

The seed:

- The wizard writes the values form as `config.seed.toml` and passes
  `--seed-config` (`wizard/internal/model/model.go:103-158`).
- Every installer copies it to `config/config.toml` only when that file
  is missing (`templates/steamos/install_lib.py:125-139`). A steamos
  patch takes the seed from the patch, else from the current version
  (`:1353-1356`).
- The seed's sha256 is part of `-o` (`lib.py:277`).

The wizard (`wizard/`, Go and Fyne):

- Pages: Welcome, Checks, Dump, Target, Options, Summary, Build, Done
  (`internal/screens/wizard.go:287-290`).
- Options come from `[[wizard.option]]`: render scale and fullscreen
  (both `config` keys, so seed values) and the HUD pack (a `flag`,
  `--hud-pack`) (`cat/game.toml:128-163`).
- `--hud-pack` has the prerequisites `import DUMP` and `enhance hud`
  (`model.go:22-27`). Every run passes `--dump` (`:137`).
- The output choice is a line on the Summary and a "Change..." dialog:
  update from the installed version, "The Deck has: [records]", or the
  full installer, plus "Rebuild everything"
  (`internal/screens/output.go:189-280`).
- The hidden `-patch-from` flag passes a base straight through
  (`cmd/wizard/main.go:43`, `:57`).

## Goals / Non-Goals

**Goals:**

- Two paths with their own screens. Fresh always makes the full
  installer. Update always makes a patch, or says why it cannot.
- Update shows the base it patches (its version and tweaks), and the
  player chooses it, for this computer or another device.
- An unticked tweak keeps what the base has. Removing is a separate,
  explicit choice. The CLI enforces this, not only the wizard.
- Update skips the disc and `enhance hud` when they are not needed.
- The wizard stays a front end: every choice is a CLI flag, and every
  fact it shows comes from `package --plan --json`.

**Non-Goals:**

- Changing `config.toml` values (render scale, fullscreen, anything in
  the seed) on Update.
- Reading the target device's files over a network, or a remote
  device's `config.toml`.
- New tweak kinds. The HUD pack is the only one today, but the design
  leaves room for more.
- Developer flags (`--allow-debug`, `--allow-nonstock`, `--no-build`) in
  the wizard.

## Decisions

### D1. Two paths, chosen on the Welcome page

The Welcome page keeps its folders and statements and adds one required
choice:

- **Fresh build**: "A complete installer: for a first install, a new
  device, or to start over. Your saves and settings on the device are
  kept."
- **Update build**: "A small update for a device that already has a
  build made with this wizard. Only what changed is copied."

The choice is saved with the settings, so the wizard opens on the last
path used. No other default applies.

The pages after Checks depend on the path:

| Fresh (today's pages) | Update |
|---|---|
| Dump | Target |
| Target | Base ("What does the device have now?") |
| Options (with the seed) | Changes (tweaks) |
| Summary | Dump, only when the plan needs it (D6) |
| Build, Done | Summary, Build, Done |

The step bar counts the pages of the chosen path. Back to Welcome
switches paths and keeps the target and folders.

Fresh passes `--full` always. "Fresh" names the output, not the folder:
the kept build folder still reuses its stages, and "Rebuild everything"
(`--clean`) stays a separate box on both paths' Summary. The Summary's
output line and its "Change..." dialog go away, since the path is the
output choice.

Why: today the patch-or-full decision sits on the last page before the
build, inferred from state the player cannot see. Asking first puts the
case up front, and each path can then drop the pages it does not need.

### D2. The base: shown and chosen, never guessed

The Base page lists, from the plan, each candidate:

1. **This computer's install**, when the target is the host's own
   platform (`plan.output.installed`, today's `host_base`).
2. **The builds this folder made** for the target (`plan.bases`), newest
   first.
3. **"A file from the device..."**: a file picker for a `manifest.json`
   the player copied from the device. Next to it, the page says where
   the file is, by target:
   - steamos: `~/Games/<App>/current/manifest.json`;
   - windows: `%LOCALAPPDATA%\Programs\<App>\versions\<version in
     current.txt>\manifest.json`;
   - macos: `<App>.app/Contents/Resources/manifest.json`.

Each row shows the version as date and time, when it was made, its
**update ID** (the first 8 hex of the manifest's sha256), its tweaks
("Sharper HUD, 4x" or "no tweaks"), and the update's size. A row that
cannot take a patch is shown greyed out with its reason (D7).

For a device that is not this computer, the page says "On the Deck, run
`./install.sh status` in the game's folder: it shows the update ID."
`install.sh status` gains an `update id:` line (the current manifest's
sha256 prefix) and a `tweaks:` line.

Selection:

- On the host's own target, the install is preselected, and it is the
  only candidate the CLI would have used before.
- For another device, nothing is preselected when there is more than
  one record. The player picks a row or a file. With exactly one record,
  it is preselected, and the page still shows it.

The wizard passes `--patch-from <path>` for the install or a file, and
`--patch-from <sha256 prefix 12>` for a record. Both are forms `package`
takes today (`patch.load`, `patch.py:79-110`). Nothing reaches
`package` without the player having seen it.

A wrong pick is caught on the device: every applier refuses a patch
whose base is not the current version, by version and manifest sha256
(`wizard-incremental-builds` D6 and D10). The Done page says so: "If the
device has another version, the update refuses and changes nothing.
Make a Fresh build then."

The plan gains, per base (records, the installed one and a
`--patch-from` file alike):

```json
{"version": "...", "made": "...", "sha256": "...", "id": "1a2b3c4d",
 "size": 0, "patch_size": 0, "usable": true, "why": [],
 "tweaks": {"hud_pack": {"sha256": "...", "scale": 4, "entries": 41}
            | null},
 "seed_config": false}
```

`tweaks` and `seed_config` are read from the base manifest's
`enhance.hud_pack` and `seed_config` fields. A schema 1 manifest without
them reads as no tweaks.

### D3. Tweak flags: make, keep, clear

`xbr package` gets three exclusive flags for the HUD pack, in one
argparse group:

- `--hud-pack [DIR]`: today's flag. Stage the pack in `DIR` (made now
  by `enhance hud`).
- `--keep-hud-pack`: stage the **base's** pack, the same bytes (the
  manifest's `enhance.hud_pack.sha256`), found as in D4. It needs a
  base, so it is refused with `--full`. With a base that has no pack,
  it is a no-op that says so ("keep: the base has no HUD pack").
- `--clear-hud-pack`: stage no pack. Against a base with a pack, the
  patch deletes `enhance/hud.pack` and changes `config.default.toml`.

The guard: when the run has a base (a `--patch-from` base, or without
`--full` the host's install that `choose` would take), and that base's
manifest has `enhance.hud_pack`, and none of the three flags is given,
`package` refuses **before anything is built**:

> the base 20261012.1309 carries a HUD pack: pass --keep-hud-pack to keep
> it, --clear-hud-pack to remove it, or --hud-pack to make a new one

Both base sources are known before the build (`patch.load` and
`host_base` read only manifests), so this costs nothing. A run with
`--full` and no `--hud-pack` makes a bundle without a pack, as today:
Fresh is "what you tick".

Why flags and not a default: keeping silently would hide a removal the
other way, for example a player who wants the stock HUD back. A
refusal that names the choices makes the CLI as explicit as the wizard,
so a script cannot drop a pack by accident either. Why one flag per
tweak and not `--keep-tweaks`: each tweak has its own source and checks,
and with one tweak today, a generic flag would only rename this one.
The wizard's "Clear previous tweaks" passes every `--clear-*` flag
there is (today only one).

The `-o` digest: `options_digest(vals, seed, hud_sha)` is unchanged.
With a kept pack, `hud_sha` is the base's, so the pack's part of `-o`
equals the base's. The seed part follows D5.

The packaging spec's "Without the flag" sentence changes: without any
of the three, and with no base that has a pack, the payload has no pack.

### D4. Where a kept pack comes from

The records hold manifests, not files, and `dist/enhance/hud/hud.pack`
is overwritten by the next `enhance hud`. So a kept pack is looked up
in this order, and each candidate is accepted only when its sha256
equals the base's `enhance.hud_pack.sha256`:

1. **The pack store**, `.git/xbr/packs/<sha256>.pack`, beside the
   bundle records. Every `package` run that stages a pack (made or kept)
   adds it:
   - as a hard link to the file it staged from, when on the same volume;
   - else a clone (APFS, `lib.copy_file`);
   - else a copy.

   For the hard link to be safe, `pack.write` writes to `hud.pack.tmp`
   and renames it over (`os.replace`), so a later `enhance hud` makes a
   new file and never rewrites a linked one. The staged copy in the
   payload is already a separate file (`shutil.copy2`).
2. **`dist/enhance/hud/hud.pack`**, when its sha256 matches. It is then
   added to the store.
3. **Made again** from the recorded inputs. The manifest's
   `enhance.hud_pack` gains `made_with`:

   ```json
   {"scale": 4, "languages": ["en"], "only": [],
    "font_sha256": "...", "config": "<digest of [enhance.hud]>",
    "cli": "0.9.0"}
   ```

   These are `hud_record`'s inputs without the paths (`out`, the font
   path) and with the CLI version for the CLI tree, which keeps the
   manifest free of private data (`lib.private_leaks`). When the current
   `[enhance.hud]` digest equals `config` and an installed font has
   `font_sha256`, `package` runs `enhance hud` with that scale,
   languages and `--only` into a temporary folder under the build state,
   and keeps the result if its sha256 matches. The pack is
   deterministic (`enhancements-hud-pack`, measured 4 to 8 s), so a
   match is the normal case when the game files and the CLI's pack code
   are unchanged.
4. **Otherwise, refuse** before the stage, naming what is missing:

   > --keep-hud-pack: the HUD pack of 20261012.1309 (sha256 1a2b3c4d...)
   > is not in this build folder and could not be made again the same
   > (the HUD settings changed). Make a new one with --hud-pack, or
   > remove it with --clear-hud-pack.

   The wizard shows this as "The sharper HUD on the device can't be
   rebuilt here: tick Sharper HUD to make a new one, or Clear previous
   tweaks." Because the plan runs the same lookup without writing (D6),
   this shows on the Changes page, not after a build.

Step 3 needs `game_files/`. When they are missing, the plan marks the
disc as needed (D6).

Store pruning: the store keeps the packs named by the newest 3 bundle
records of each target, the same 3 a SteamOS install keeps by default,
and whatever the current run staged. Older packs are dropped when a
bundle is recorded. `xbr clean` lists the store under its own heading.
A base older than that falls back to step 2 or 3.

Rejected: a patch that ships a kept pack by reference only (listed as
kept, bytes absent from the stage). The staged tree must stay the full
new tree. The patch-equals-full property, the stage reuse, the
equality test (`wizard-incremental-builds` D12) and a Fresh build of the
same version all depend on that, and the bytes are almost always on
this machine anyway.

### D5. The seed on Update: not carried

Update passes no `--seed-config`, and the new version has no
`config.seed.toml`.

- A seed is read only when the device has no `config.toml`, which after
  a first install means the player deleted it. Then the steamos patch
  falls back to the current version's seed (`install_lib.py:1353-1356`).
  Windows and macOS keep the previous version's files beside the new
  one. Either way nothing the player chose is lost.
- The `-o` digest drops its seed part. A kept pack's part still equals
  the base's. Across an unrelated change, `-o` is therefore equal to the
  base's when the base had no seed, and differs only by the seed
  otherwise. The version changes anyway with the new commits, so `-o`
  only has to keep two different option sets apart. It does.

The Changes page says: "Render scale, fullscreen and the other settings
are in your config.toml on the device (<path for the target>). An
update never changes them." Changing them on Update is out of scope,
because the device's `config.toml` wins over anything a bundle ships.

### D6. Doing only what is needed

**The disc.** `package --plan --json` without `--dump` gains:

```json
"import": {"needed": false, "why": ""}
```

`needed` is true when `game_files/` is missing, its marker is missing,
or its listing no longer matches the recorded import key
(`incr.import_inputs`, `incr.py:97-109`), with `why` naming which. Two
more cases make it true: a `--keep-hud-pack` that must remake its pack
(D4.3) or a `--hud-pack` whose `enhance hud` must run, when
`game_files/` is missing. Then the import row reads "run (needs the
disc)" instead of today's unconditional "reuse".

The wizard's Update path asks the plan first. It shows the Dump page
only when `import.needed` is true, saying why ("The game files in the
build folder are missing or changed"). It then passes `--dump` and runs
`import DUMP`. Otherwise it passes neither.

**The HUD.** On Update the wizard's steps are:

- HUD ticked: `enhance hud`, then `package ... --hud-pack`. `enhance
  hud` skips itself when its key is current (`hud.py:340-348`). The plan
  row says which.
- HUD unticked, and the base has a pack: `package ... --keep-hud-pack`,
  with no `enhance hud` step. The plan's hud row reads "keep (from the
  store)", "keep (made again, ~6 s)" or the refusal.
- Clear previous tweaks: `package ... --clear-hud-pack`, with no `enhance
  hud`.

`model.Prerequisites` becomes path-aware. On Update, `import DUMP` is a
step only when the plan said `import.needed`, and `enhance hud` only for
`--hud-pack`. Fresh keeps today's steps.

**The rest** is the incremental build as it is. Generate, compile,
stage and wrap rerun only when their keys move.

### D7. When no patch can be made: say why, offer Fresh

`--patch-from` becomes strict. `choose` refuses (exit non-zero, before
the wrap writes anything) when:

- `problems()` names a reason (another game or target, `data_layout`
  changed, a manifest entry without sha256, on Windows an in-place
  install or another `stub_abi`). This is today's behaviour;
- the patch would not be under half the full bundle (new: today the
  rule applies to the host base only);
- the build equals its base ("it is this version already").

The message names the reason and ends "make the full bundle with
--full". The host-base path without `--patch-from` keeps its full
fallback for CLI users, but the wizard's Update never takes that path:
it always passes `--patch-from`.

The plan predicts the same. A base row has `usable` and `why`, and
`output.kind` is `"none"` with the reason when the chosen base cannot
take this patch. The half-size check in the plan uses the newest
record's manifest as the stand-in, as `plan_output` does today
(`plan.py:275-345`), and the run decides again on the real manifest.

The wizard:

- On the Base page, an unusable row shows its reason and cannot be
  picked.
- When the plan says `none` for the picked base, the Summary replaces
  the Build button with the reason and **"Make a Fresh build instead"**,
  which switches to the Fresh path, keeping the target, folders and
  disc. Texts:
  - "The game data layout changed since that build, so it can't be
    updated."
  - "This update would be most of the full installer (62%)."
  - "Nothing changed since that build."
- If the run itself refuses (the plan's estimate was wrong), the
  failure page shows the CLI's reason with the same button.

Never a silent full bundle: on Update, a full bundle is made only after
the player pressed that button.

### D8. A player's config.toml that overrides the pack

A player's `config/config.toml` overrides `config.default.toml`, so a
hand-written `[textures] pack = "none"` hides a pack the player chose,
and a `pack = "enhance/hud.pack"` left behind after a clear points at a
file that is gone (the runtime then logs it and stays stock). The
wizard runs on the build machine and cannot read the device's file, so
the note goes where the file can be seen:

- **The appliers and installers on the device.** `install.sh` (full and
  patch), `apply.exe` (Windows patch) and `apply.command` (macOS patch)
  look for a `[textures]` table with a `pack` key in the data folder's
  `config/config.toml`. They use a line scan (a `[textures]` header,
  then `pack =` before the next header), not a TOML parser, since
  `apply.exe` is C and `apply.command` is sh. When the key is found and
  differs from the new `config.default.toml`'s, they print one line
  after the apply:

  > note: your config/config.toml sets textures.pack = "none", which
  > overrides this build's HUD pack; remove that line to use it

  A false negative (an unusual layout) only loses the note. The scan
  never changes the file.
- **The wizard, on the host's own target.** The plan gains
  `config_overrides` (`[{"key": "textures.pack", "value": "none"}]`)
  from the same scan of this host's data folder. The Changes and Done
  pages then name the line to remove. For another device they show a
  static note when a HUD pack is made or kept: "If your config.toml on
  the device sets pack under [textures], it overrides this. The
  installer will say so."
- The Windows full installer (NSIS) and the macOS DMG get no scan. The
  static note in README.txt already covers them, and Fresh is their
  path.

### D9. What Update's screens say

- **Target**: as today.
- **Base**: D2.
- **Changes**:
  - "On the device now: Sharper HUD (4x, 41 entries)" or "no tweaks".
  - The HUD box, unticked, with the hint "Unticked: the device's sharper
    HUD stays as it is" when the base has one, or "Unticked: no sharper
    HUD" when it has none. Ticked: "A new sharper HUD is made from your
    game files and replaces the device's".
  - "Clear previous tweaks" (unticked): "Removes the sharper HUD from
    the device's build". Ticking it unticks and disables the HUD box,
    because a version with a new pack replaces the old one anyway. The
    box is hidden when the base has no tweaks.
  - The config.toml note (D5, D8).
- **Summary**: the base (version, update ID), "Keeps: ..." / "Changes:
  ...", the update's size, the plan rows, "Rebuild everything", and the
  technical details with the exact commands.
- **Done**: today's apply text for a patch, the wrong-base note (D2) and
  the override note (D8).

Players still never see the word "base", manifests' contents or keys.
"Update ID" is the one identifier shown, because it is what the device
prints.

### D10. Tests

CLI (pytest, on the fixture game):

- the three flags are exclusive, `--keep-hud-pack` with `--full` is
  refused, and the guard refuses before the build when a base has a pack
  and no flag is given (`--patch-from` and host base);
- keep finds the pack in the store, then in `dist/enhance/hud/` after
  the store was emptied, then by remaking it; it refuses when the
  remade sha256 differs;
- `pack.write` replaces the file, so a hard link taken before keeps the
  old bytes;
- strict `--patch-from`: the half-size rule, an equal version and a
  `data_layout` change each refuse with no bundle written;
- the plan: `import.needed` for missing and changed `game_files/`, base
  `tweaks` and `id`, `output.kind = "none"`, and `config_overrides`;
- **patch chains on steamos and windows**: a full bundle with pack A,
  then a patch with `--clear-hud-pack` (the patch deletes
  `enhance/hud.pack` and changes `config.default.toml`), then a patch
  with `--hud-pack` B (it adds both back with B's bytes). Each patch
  applied to the previous install gives a tree equal to that version's
  full install (the existing patch-equals-full check);
- **keep across an unrelated change**: from a base with pack A, a code
  change with `--keep-hud-pack` gives a patch whose kept set includes
  `enhance/hud.pack` and `config.default.toml`, a manifest whose
  `enhance.hud_pack` equals the base's, and the same `-o` part as the
  base when the base had no seed;
- the appliers' override line: `install_lib` and `apply.command` in
  pytest, `apply.c`'s scan as a unit test where the Windows tests build
  it.

Wizard (Go): the page lists per path, the base list from a plan fixture
(greyed reasons, preselection rules), the flags built for each tweak
state, the Dump page skipped when `import.needed` is false, and the
"Make a Fresh build instead" switch.

## Risks / Trade-offs

- **[The guard breaks a script that patched without a HUD flag]:** a
  developer's `package --patch-from X` from a pack build now refuses.
  → The refusal costs no build and names the flag. This is the point:
  that script was dropping the pack.
- **[A kept pack can't be found]:** a base older than the store and the
  HUD settings changed since.
  → D4.4 refuses on the Changes page with the two ways out. Remaking is
  the usual rescue, and it is deterministic.
- **[The player picks the wrong row for another device]:** the applier's
  base check refuses and changes nothing (D10 of the earlier change),
  and `install.sh status`'s update ID lets them check first.
- **[The line scan misreads config.toml]:** it only prints a note. It
  never decides anything or edits the file.
- **[The pack store grows]:** at most about 3 packs per target of about
  160 MB, mostly hard links to files that exist anyway, and listed by
  `xbr clean`.
- **[A strict `--patch-from` refuses a patch a developer wanted]:** they
  pass `--full`, or move the base. The half rule now means the same
  thing everywhere.

## Migration Plan

- Manifests made before this change have no `made_with`. Keeping their
  pack uses the store or `dist/` only (D4.1 and D4.2), and the store is
  empty at first. So the first Update from an older pack build finds the
  pack in `dist/enhance/hud/` when it is still that one, else it refuses
  with the two ways out.
- The store starts empty and fills with each package run.
- `install.sh status`'s new lines appear on installs made after this
  change. Older installs show the version, and the wizard's rows show
  the version too, so the player can match by date.
- The CLI pin moves in cat and b3 when it ships. The games need no
  other change.

## Open Questions

None.

## Implementation notes

Where the code made the implementation differ from the decisions above,
and why.

- **The guard covers every base `run_base` reads** (D3): `--patch-from`'s
  and, without `--full`, the host's own install. Both are known from
  manifests alone before anything is built, so one check covers both.
- **Two moments for `--patch-from`'s refusal** (D7, from the review):
  product, target, `data_layout`, the entries' fields and on Windows
  the layout and `stub_abi` need only the base's manifest and the
  game's settings, so they refuse before anything is built, next to the
  HUD guard. The game tree, the half rule and "this version already"
  need the new manifest and refuse after the build, before the patch is
  written.
- **The game tree is part of the base check** (D7, from the review): a
  Deck patch once came from a base whose game files differed from the
  build's (the cause is tracked apart). Manifests record `game_tree`
  (the XBE's sha256, the count and a listing digest), and a base whose
  tree differs is refused ("built from other game files") unless this
  run imported the game files with `--dump`, which is the player saying
  the disc is the one. A patch that would remove `game_files/` entries
  needs `--allow-game-file-deletes`. A manifest made before `game_tree`
  is judged by a tree computed from its entries, and a patch removing
  game files from it is refused even with the flag: nothing recorded
  says the removal is the game's. The plan gives each base its
  `game_files` counts, and the Summary says "Removes N game files"
  when N > 0.
- **Reason codes, not message text** (D7, from the review): each
  reason in the plan has a code (`why_codes` on bases and the output),
  and a refusal's last line is `<name>: refused: CODE`. The wizard
  chooses its words and the failure page's Fresh offer by code, so a
  reworded CLI message cannot break either; an unknown code shows the
  CLI's message.
- **A same-version build stays pickable on the Base page** (D2): the
  Base page's plan has no tweak flags yet, so right after a Fresh build
  every row read "nothing changed", though ticking a tweak makes a new
  version (the `-o` digest). The row is offered with a note, and the
  Summary's plan, which has the flags, says when nothing changed.
- **The plan says `kind: "none"` instead of raising** (D7): a strict
  `--patch-from` that the run would refuse is a plan answer, so the
  wizard can show the reason without parsing an error.
- **No `pack: "none"` row without a pack**: a run with no pack and no
  HUD flag has nothing to report, and the extra row read as a choice.
- **`made_with` comes from `hud-pack.toml`** (D4): `enhance hud` already
  writes that file beside the pack; recording from it keeps `package`
  from re-deriving the inputs. A pack whose file names another sha256,
  or predates the fields, records no `made_with`.
- **A remake with `font_sha256` null still runs**: a pack drawn without
  a font file (the game's own glyphs only) has nothing to check.
- **The import marker counts toward `import.needed`** (D6): an
  interrupted import leaves `game_files/` incomplete, which the file
  check alone would miss.
- **No clear row in the plan**: `--clear-hud-pack` stages nothing, so
  there is no stage to name.
- **The half rule is undecidable for the newest record** before the
  build: the plan judges it against the newest record (as before), and
  the run decides again on the real manifest.
- **The pack store is listed in `clean`'s state category**: it sits
  under `.git/xbr/` with the records, not with the bundles.
- **`apply.exe` reads `%LOCALAPPDATA%` from the environment** for the
  config.toml note (D8), the same way it finds the install.
- **The Windows patch chain test (6.3) uses a model applier**: building
  `apply.exe` needs llvm-mingw, which the local test run skips; the
  chain is checked against the model, and a mingw-built run is a
  follow-up.
- **`apply.command` gets the data folder through `patch.env`**
  (`DATA_DIR`, `DATA_DIR_ENV`): the script has no game config to read.
- **The plan's installed row gains `path`**: `origin` says where the
  install was found ("host"), not its folder, and the wizard passes the
  folder as `--patch-from` so the build and the plan agree on one base.
- **The Base page lists bases with `package T --full --plan --json`**
  (D2): `--full` is the one plan that needs no disc and no chosen base,
  and it still lists every record and the host's install.
- **The Changes page's config line is generic** ("The game's settings
  are in config.toml…") instead of naming render scale and fullscreen:
  the wizard is game-generic and those keys are BLiNX 2's.
- **A picked file's tweaks come from the Changes page's plan**
  (`output.base`): the wizard never reads a manifest itself, so the
  file's tweaks are known only once the CLI has read it, and the plan is
  asked again with the flags they call for.
- **The Base and Changes pages are indexed after Done** in the wizard's
  page list, so the Fresh pages keep their indices; the order per path
  is a separate list.
- **A no-change update is "this version already"**: the version is
  stamped from the commits (cat, toolkit, gen) and the options digest,
  not the build time, so Update with nothing new and the HUD kept is the
  strict D7 refusal (`output.kind = "none"`). 7.3's "code or packaging
  change" is needed for a keep patch; the Mac smoke used a docs-only
  commit in its scratch clone.
- **Phase 7 on the Deck ran against a hard-linked copy of the install
  root**, without launching the game (the orchestrator, 2026-10-18): on
  the player's root, a fourth version prunes the oldest at the default
  keep of 3 and a rollback leaves `previous:` on the new version, so
  install-then-rollback cannot leave `install.sh status` as it was. The
  copy shares `versions/` and `game_files/` by hard link (the installer
  only links, renames and unlinks there), with its own `state/`,
  `config/`, launcher and `launch.sh`/`install.sh` inodes; the player's
  tree is hashed before and after. The `[ENHANCE]` log lines of 7.2-7.4
  need a launch and stay a follow-up.
- **The Deck patch was built against the toolkit the Deck runs**
  (dd8b1b4, the integration branch), not the pin in `game.toml`
  (blinx2-v0.5.1): a patch on the pin would have taken the Hor+ toolkit
  fixes back out of the player's build.
- **A `game_files/` without the dump marker reads as needing the disc**
  (D6): an import older than the marker (`.xbr-dump.json`) cannot be
  told from a hand-edited folder, so the plan says `import.needed` and
  the wizard's Update path asks for the disc once; the import writes the
  marker. `package` without `--dump` still builds from the folder as it
  is. The Deck patch was built that way from a marker-less copy of the
  main checkout's game files, the ones the Deck's install was made from.
