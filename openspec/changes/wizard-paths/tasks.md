Conventions: **CLI** = a branch off `xboxrecomp-cli` `main` (30f599c or
later) in its own worktree, commits authored and committed as the noreply
identity, no tracker ids, host names or private paths. **cat** = a branch
in its own worktree for the CLI pin and docs. Design decisions are cited
as D1-D10. No toolkit change. Builds run on the Mac only, under the Mac
bench lock; nothing is built on the Deck. Goldens are skipped: this change
touches packaging and the wizard only.

Phase map:

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 1 Tweak flags and the guard | CLI | S | - |
| 2 Pack store and kept packs | CLI | M | 1 |
| 3 Strict base and plan fields | CLI | S | 1 |
| 4 Appliers: override note, status | CLI templates | S | - |
| 5 Wizard paths | CLI `wizard/` | M | 2, 3 |
| 6 Docs and gates | CLI, cat | S | 1-5 |
| 7 End-to-end on the Deck | Mac builds, Deck installs | S | 6 |
| 8 Review and merge | orchestrator | XS | 7 |

## 1. Tweak flags and the guard (CLI)

- [x] 1.1 `main.py`: put `--hud-pack [DIR]`, `--keep-hud-pack` and
      `--clear-hud-pack` in one exclusive group; refuse
      `--keep-hud-pack` with `--full` (D3).
- [x] 1.2 `package/__init__.py`: resolve the base before the first stage
      (`patch.load` for `--patch-from`, `host_base` without `--full`);
      when it records `enhance.hud_pack` and no HUD flag is given,
      refuse naming the three flags (D3).
- [x] 1.3 `--clear-hud-pack` stages nothing; a keep against a base with
      no pack says "keep: the base has no HUD pack" and stages nothing.

## 2. Pack store and kept packs (CLI)

- [x] 2.1 `enhance/pack.py`: write `hud.pack.tmp` and `os.replace` it, so
      a hard link to the old file keeps its bytes (D4).
- [x] 2.2 `package/incr.py`: `packs_dir()` beside `bundles_dir()`; add
      each staged pack by sha256 (link, else `lib.copy_file`); prune to
      the packs named by the newest 3 records per target plus the current
      run's, when a bundle is recorded; `xbr clean` lists the store.
- [x] 2.3 `enhance/hud.py` and `write_manifest`: record
      `enhance.hud_pack.made_with` (scale, languages, only, font sha256,
      `[enhance.hud]` digest, CLI version); check `lib.private_leaks`
      still passes.
- [x] 2.4 `--keep-hud-pack` lookup: store, then `dist/enhance/hud/` by
      sha256, then a remake into a temporary folder under the build
      state accepted by sha256, else the refusal naming `--hud-pack` and
      `--clear-hud-pack` (D4).
- [x] 2.5 The `-o` digest takes the kept pack's sha256; no other change
      to `options_digest`.

## 3. Strict base and plan fields (CLI)

- [x] 3.1 `patch.choose`: with `--patch-from`, apply the half-size rule
      and refuse on `problems()`, the share, or an equal version, with
      "make the full bundle with --full", before the wrap writes (D7).
- [x] 3.2 `plan.py`: per base `id`, `usable`, `why`, `tweaks`,
      `seed_config`; the installed base in the same shape; `output.kind
      = "none"` with the reason (D2, D7).
- [x] 3.3 `plan.py`: `import: {needed, why}` without `--dump` (missing
      or changed `game_files/`, or a HUD make or remake that needs them);
      the import row reads "run (needs the disc)" then (D6).
- [x] 3.4 `plan.py`: the hud row for keep ("keep (from the store)",
      "keep (made again)", or the refusal), and `config_overrides` from
      this host's `config.toml` on the host's own target (D6, D8).

## 4. Appliers (CLI templates)

- [x] 4.1 `templates/steamos/install_lib.py`: the `[textures] pack` line
      scan after a full install and a patch; `status` prints `update id:`
      and `tweaks:` (D8, D2).
- [x] 4.2 `templates/windows/apply.c`: the same scan and note after a
      patch, with a unit test where the Windows tests build `apply.exe`.
- [x] 4.3 `templates/macos/apply.command`: the same scan and note.

## 5. Wizard paths (CLI `wizard/`)

- [x] 5.1 `internal/model`: a `Path` (Fresh, Update) saved with the
      settings; `PatchFrom` and the tweak state (`Keep`, `Make`,
      `Clear`) turned into flags; Fresh always `--full`; Update never
      `--seed-config`; `--dump` and `import DUMP` only when the plan said
      `import.needed`; `enhance hud` only for `--hud-pack` (D1, D3, D6).
- [x] 5.2 `internal/screens`: the Fresh/Update choice on Welcome; the
      page list per path and the step bar; the Base page with the plan's
      rows, the file picker, the per-target paths and the
      `install.sh status` hint; the Changes page (D9); the Summary
      without the "Change..." dialog; the "Make a Fresh build instead"
      button on the Summary and the failure page (D7).
- [x] 5.3 `internal/runner`: the new plan fields.
- [x] 5.4 Go tests: the page lists, the base rows from a plan fixture
      (reasons, preselection), the flags for each tweak state, the
      skipped disc page, the switch to Fresh.

## 6. Docs and gates

- [x] 6.1 CLI `docs/wizard.md` (the two paths) and `docs/bundle.md` (the
      three flags, the pack store, `made_with`, strict `--patch-from`,
      the override note, the status lines).
- [x] 6.2 pytest (D10): exclusive flags and the guard; keep from the
      store, from `dist/` and by remake, and the sha256 refusal; the
      atomic pack write; strict `--patch-from` refusals with no bundle
      written; the plan fields; the override line.
- [x] 6.3 pytest patch chains on **steamos** and **windows**: full with
      pack A, then `--clear-hud-pack` (deletes `enhance/hud.pack`,
      changes `config.default.toml`), then `--hud-pack` B (adds both
      back with B's bytes); each applied tree equals that version's full
      install.
- [x] 6.4 pytest keep across an unrelated change: the patch keeps
      `enhance/hud.pack` and `config.default.toml` and does not ship
      them, `enhance.hud_pack` equals the base's, and `-o` equals the
      base's when the base had no seed.
- [x] 6.5 CLI gates: `uv run pytest tests`, `uv run ruff check . && uv
      run ruff format --check .`.
- [x] 6.6 Wizard gates: `wizard/check.sh` (`gofmt -l` empty, `go vet`,
      `go test`, `staticcheck` when available, the double build with
      equal sha256s per target).
- [ ] 6.7 cat: move the CLI pin in `game.toml`; `uv run pytest scripts`
      and the ruff checks. Goldens skipped (packaging and wizard only).
      The gates pass on the branch merged with main efdf3ec; the pin
      stays at v0.8.0 until the CLI is merged and tagged (8.2), and the
      branch was tested through `XBOXRECOMP_CLI_DIR`.

## 7. End-to-end on the Deck (the orchestrator schedules it)

- [ ] 7.1 On the Mac, the wizard's Fresh path for steamos; install it on
      the Deck; `install.sh status` shows the update ID and `tweaks:
      none`.
- [ ] 7.2 Update with Sharper HUD ticked, base chosen by that update ID;
      apply on the Deck; the log reads `[ENHANCE] textures.pack=enhance/hud.pack`.
- [ ] 7.3 A code or packaging change, Update with the box unticked (keep):
      no disc asked, no `enhance hud`; the patch does not ship the pack;
      the log still names it.
- [ ] 7.4 Update with Clear previous tweaks; apply; the log reads no
      pack and the stock HUD is drawn.
      The Mac half of 7.1-7.4 ran through the wizard: its pages, plans
      and build steps in Fyne's test driver against the real CLI (the
      e2e test, build tag `e2e`), on a scratch clone. Fresh made the
      full installer; Update with Sharper HUD shipped `enhance/hud.pack`
      with no disc asked (the game files were there); after a commit,
      Update unticked kept the pack (`--keep-hud-pack`, no `enhance
      hud`, no disc, the pack not shipped); Clear deleted it. The Deck
      half (install, status, launches) waits for the Deck.
- [x] 7.5 Roll back once to check the kept versions, with the default
      keep of 3.
      Done on a hard-linked copy of the Deck's root (design notes): a
      patch from the installed 0634-c72b8ef0 (built from main efdf3ec,
      toolkit dd8b1b4, HUD kept) installed with 4 files shipped and 485
      game files kept; status read `update id: 46ac5b91` and `tweaks: HUD
      pack 4x, 427 entries (8df7c673)`; prune removed the oldest of the
      copy; the rollback went back to 0634. The player's root was
      hashed and its status taken before and after: identical (the
      run's logs are kept with the agent's notes). 7.1-7.4 need the Fresh install and
      game launches on the player's root and stay open.

## 8. Review and merge

- [x] 8.1 Review of the CLI branch; fixes go back to its agent.
      Its fixes: the plan's `why` list parsed by the wizard (a contract
      test on a plan the CLI wrote); the game tree in the manifest and
      the base check, with `--allow-game-file-deletes`; the manifest-only
      checks before the build; reason codes in the plan and the
      `refused:` line, which the wizard switches on; the Summary's
      removed game files.
- [ ] 8.2 Merge the CLI (squash, noreply identity), then the cat pin;
      update `TASKS.md`; archive after `wizard-incremental-builds`.
