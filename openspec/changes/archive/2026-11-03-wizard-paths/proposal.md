## Why

The user asked (2026-10-17) for two clear paths at the start of
the build wizard, **Fresh build** and **Update build**, each with its own
screens, so the wizard does only what that case needs.

The incremental builds and patch installers (change
`wizard-incremental-builds`, CLI v0.8.0) made patches possible, but the
wizard still has one path, and three things in it surprise a player who
updates:

- **The base is picked silently.** `patch.choose` takes `--patch-from`
  (a hidden wizard flag), else the version installed on this host, else
  nothing (`package/patch.py:290-319`; a bundle record is a base only
  when `--patch-from` names it). A player who builds on the Mac for the
  Steam Deck never has "installed on this host", so the wizard makes a
  full 3.5 GB bundle unless they find the record picker hidden behind
  "Change..." on the Summary (`wizard/internal/screens/output.go:189-280`),
  and it never shows what that base carries.
- **An update drops the HUD pack.** A `package` run without `--hud-pack`
  stages no pack (`package/__init__.py:647`) and computes the `-o`
  options digest without it (`:388-389`), so a patch from a pack build
  deletes `enhance/hud.pack` and the `[textures]` key. The player loses
  the sharper HUD by leaving a box unticked.
- **Update repeats Fresh's work.** The wizard always asks for the disc
  and runs `import DUMP` before `enhance hud`
  (`wizard/internal/model/model.go:26`, `:179-200`), and always shows
  the config values form, whose seed the installers copy only when the
  player has no `config.toml` yet (`templates/steamos/install_lib.py:125-139`),
  which is never the case on an update.

The user's decisions (2026-10-17), fixed for this change:

1. The wizard opens with **Fresh build** and **Update build**. Fresh is
   always allowed, even when a build exists. Update makes a patch and
   skips what is not needed (no disc import when the game files match,
   no `enhance hud` when the pack inputs are unchanged).
2. Update never shows the config values form (the seed). It is Fresh
   only.
3. HUD/font tweaks are optional on Update. Selected: the wizard runs that
   step and packages what it needs. Not selected: the base build's
   tweaks are **kept**.
4. Removing tweaks is an explicit option ("Clear previous tweaks"), never
   the result of an unticked box.

## What Changes

- **CLI: explicit tweak flags.** `xbr package` gains `--keep-hud-pack`
  (carry the base's pack, byte for byte, into the new version) and
  `--clear-hud-pack` (the new version has none), beside today's
  `--hud-pack [DIR]` (a pack made now). The three are exclusive. When
  the run's base carries a pack and none of them is given, `package`
  refuses before building and names the three. A kept pack gives the
  same `-o` digest part as the base's.
- **CLI: a pack store.** Every staged pack is kept by its sha256 in the
  build state (`.git/xbr/packs/`). A kept pack comes from that store,
  else from `dist/enhance/hud/` when its sha256 matches, else it is made
  again from the inputs the manifest now records and accepted only when
  the sha256 matches. Otherwise the run refuses and says which choice
  fixes it.
- **CLI: a strict explicit base.** `--patch-from` also applies the
  half-size rule. A base that cannot take a patch, a patch that is not
  under half the full bundle, or a build equal to its base is refused
  with the reason, never turned into a full bundle. The checks that
  need only the manifests (product, target, `data_layout`, on Windows
  `stub_abi`) refuse before anything is built; the ones that need the
  new manifest (the game tree, the share, the version) refuse after the
  build, before the patch is written. A base built from other game
  files is refused unless the run imported them with `--dump`, and a
  patch that would remove game files needs `--allow-game-file-deletes`.
  `package --plan --json` reports each base's tweaks, its reason codes,
  how many game files the patch changes, adds and removes, and whether
  the disc is needed.
- **CLI: config overrides seen where they can be.** `install.sh`, the
  Windows `apply.exe` and the macOS `apply.command` say when the
  player's `config.toml` sets `[textures] pack`, which overrides the
  build's. `install.sh status` prints the current version's update ID
  (its manifest's sha256 prefix), which the wizard's base list shows.
- **Wizard: two paths.** The Welcome page asks Fresh or Update.
  - Fresh is today's path with `--full`: disc, platform, options with the
    seed, summary, build.
  - Update: platform, then "What does the device have now?" (the
    install on this computer, a build this folder made, or a
    `manifest.json` copied from the device), with the base's version
    and tweaks shown. Then the tweaks: HUD unticked keeps, ticked makes
    a new pack, and "Clear previous tweaks" removes. The disc is asked
    for only when the plan needs it. When no patch can be made, Update
    says why and offers a Fresh build.
  - The Summary's "Change..." output dialog goes away.

## Capabilities

### New Capabilities

- `build-wizard`: the two paths, choosing the Update base, tweaks kept,
  made or cleared, the disc asked for only when needed, and no silent
  fallback.

### Modified Capabilities

- `packaging`: "The owner's HUD pack in the private bundle" gains keep
  and clear, the refusal, the pack store and the recorded inputs.
- `patch-installers` (added by `wizard-incremental-builds`, not archived
  yet): "A patch is chosen from a usable base manifest" makes an
  explicit base strict, and a new requirement covers the config.toml
  override note in the appliers. This change is archived after
  `wizard-incremental-builds`.

## Impact

- **Code** (all in `xboxrecomp-cli/`): `main.py` (the flags),
  `package/__init__.py` (keep and clear, the early base check),
  `package/patch.py` (strict `--patch-from`, base summaries),
  `package/plan.py` (the hud row for keep, `import.needed`, base
  tweaks), `package/incr.py` (the pack store and its pruning),
  `enhance/pack.py` (atomic write), `enhance/hud.py` (the recorded
  inputs, a remake into a temporary folder),
  `templates/steamos/install_lib.py`, `templates/windows/apply.c`,
  `templates/macos/apply.command` (the override note, `status`), and
  `wizard/internal/{model,screens,runner}`.
- **Games:** cat and b3 need only the CLI pin. `[wizard]` and
  `config.default.toml` are unchanged.
- **Disk:** the pack store holds a few packs of about 160 MB each, as
  hard links where the file system allows. It is pruned with the bundle
  records and counted by `xbr clean`.
- **Legal:** kept packs are the owner's own derived files. They stay in
  the build folder and the player's bundles and are never published.
- **Not in scope:** changing render scale, fullscreen or other
  `config.toml` values on Update (they belong to the player's
  `config.toml`), the developer flags `--allow-debug` and
  `--allow-nonstock`, reading a remote device's `config.toml`, and
  tweaks other than the HUD pack (none exist yet).
