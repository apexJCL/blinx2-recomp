Conventions: **CLI** = branch `feat/wizard-incremental` off `xboxrecomp-cli`
`main` (06b9bc4 or later) in `wt/wizard-incr/xboxrecomp-cli`, commits
authored and committed as the noreply identity, no tracker ids, host names
or private paths. **Toolkit** = branch `feat/reproducible-link` off
`posix-host/portability` in `wt/wizard-incr/xboxrecomp` (D12 link flags
only). **cat** = branch `feat/wizard-incremental` in `wt/wizard-incr/cat`
(the CLI pin, docs). Design decisions are cited as D1-D15. Builds run on
the Mac only, under the Mac bench lock (`lockf`), and never on the Deck;
headless runs use `SDL_AUDIODRIVER=dummy`. Tasks marked **needs-user**
need a decision, the PC booted into Windows, or the Deck in desktop mode.

Phase map:

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 0 Decisions (done) | user | XS | - |
| 1 Stage state and keys | CLI | M | 0 |
| 2 Plan, clean, bundle records | CLI | S | 1 |
| 3 Reproducible output | toolkit, CLI | S | - |
| 4 Patches and appliers | CLI | L | 1, 2, 0.1 |
| 5 Local source mode and manifest schema 2 | CLI | S | - |
| 6 Wizard (Go) | CLI `wizard/` | M | 2, 4, 5 |
| 7 Gates | CLI, toolkit, cat | S | 1-6 |
| 8 SSX 3 and Spartan packaging | ssx3-ec, xb-windows | S | 5 |
| 9 Acceptance on the Steam Deck | Mac builds, Deck installs | M | 7, 8 |
| 10 Merge and release | orchestrator | XS | 9 |

## 0. Decisions (needs-user)

- [x] 0.1 Windows layout: `versions\` + `current.txt` with rollback, the
      one-time migration and the C `apply.exe` (the user, 2026-10-17; D8).
- [x] 0.2 One previous macOS app kept; patches may change game files with
      the warning; the flag is `--source`; `[wizard] repo` optional only
      with `private = true` (2026-10-17; see Resolved Questions).

## 1. Stage state and keys (CLI)

- [x] 1.1 `buildstate.py`: the state directory at `$(git rev-parse
      --git-dir)/xbr/` (`<game>/.xbr/` only outside git) (D1); load and
      save `build-state.json` atomically (`_write_json`),
      `stage_key(inputs, upstream)` (canonical JSON, sha256),
      `begin(stage)` (drop the entry), `record(stage, key, inputs,
      outputs)`, `check(stage, key)` returning reasons (D1, D3). A pytest
      that `tree_state` stays clean after a full run.
- [x] 1.2 Output checks: size + `mtime_ns`, sha256 on doubt or
      `--verify`; directory outputs as a listing digest (D3).
- [x] 1.3 Key inputs per stage as in D2:
      - import: the marker + the `game_files/` listing, with
        `game-files.json` caching sha256s, which `write_manifest` reads;
      - generate: the existing gen key, with import as its only upstream
        and no setup edge;
      - `compile:windows` (shared by windows and steamos) and
        `compile:macos`: the game tree + dirty diff; the whole toolkit's
        `HEAD^{tree}` + dirty diff, `XBOXRECOMP_DIR` included; the
        toolchain digest taken directly (llvm-mingw tag and sha after
        `LLVM_MINGW_TAG`, the toolchain file, cmake and ninja, and on
        macos clang, the SDK, the brew formulae and the dylib shas); the
        `host.build_env` values; the full `-D` list
        (`--allow-nonstock`, `--allow-debug`); the icon key;
      - icon, hud, `stage:<t>`;
      - `wrap:<t>`: the staged `manifest.json` sha256 first, then the kind,
        the base manifest sha256 and the wrapper versions (D2).
      Paths use `$ROOT` / `$TK`.
- [x] 1.4 Wire `package` through it: skip a stage when `check` passes,
      rerun it and everything below otherwise; a compile whose toolchain
      digest moved calls `start_afresh` first; `write_manifest` always
      reruns. `import` and `enhance hud`, which the wizard calls on their
      own, write their entries through the same module (D1).
- [x] 1.5 Reuse `dist/.stage-<target>/` in place: copy only files whose
      sha256 changed, clonefile or hard-link game files; the wrap writes
      the versioned bundle beside it and never renames it (D11).
- [x] 1.6 pytest:
      - key chaining: a change in each input class invalidates exactly
        its stage and the ones below;
      - a CLI or toolkit pin bump with unchanged `tools/` reuses generate;
      - a toolkit runtime-only change (`src/`) reruns compile and not
        generate;
      - a missing or corrupt state file reruns all once;
      - a deleted output reruns its stage;
      - a crash mid-stage (entry dropped) reruns it;
      - a toolchain change resets CMake;
      - paths moved with the folder keep the keys;
      - a rebase that keeps the tree still rewrites the manifest's
        commits, reruns the wrap (its key holds the staged manifest's
        sha256), and the new bundle's `manifest.json` names the new
        commits and version.

## 2. Plan, clean, bundle records (CLI)

- [x] 2.1 `package --plan --json`: per stage `reuse` or `run` with the
      reasons, and estimates from `build-logs/timings.json` (D13).
- [x] 2.2 `package --clean` (keeps gen/ and its gen key) and
      `--clean=all` (D3); `xbr clean [--bundles|--build|--all] [--yes]`
      printing what it frees, `--all` keeping `.git/xbr/wizard.json`
      (D11). pytest: `--clean` on an up-to-date folder reuses generate;
      `--clean=all` reruns it; the mark survives `clean --all`.
- [x] 2.3 At each wrap, copy the manifest to
      `.git/xbr/bundles/<target>/<manifest sha256>.json`; keep the newest 2
      bundles per target in `dist/` (`--keep-bundles N`); list them as
      `bases` in `package --plan --json` (D5.3).
- [x] 2.4 pytest for 2.1 to 2.3, including clean refusing paths outside
      the game folder.
- [x] 2.5 The plan's HUD stage estimate defaults to the measured 4 to 8 s
      when `timings.json` has no entry yet.

## 3. Reproducible output (toolkit, CLI)

- [x] 3.1 Toolkit runtime CMake: `-ffile-prefix-map` for the game root,
      `$TK`, the llvm-mingw root and the `.venv` on all targets; Windows
      `-Wl,--no-insert-timestamp` (the mingw driver the build uses;
      `/Brepro` only for a target linked by `lld-link` directly);
      macOS `ZERO_AR_DATE=1`, `-Wl,-reproducible` when the linker has it
      (D12). A ctest that links a small target twice and compares the
      bytes of the binary and the PDB, the PDB GUID included.
- [x] 3.2 CLI: `built` and the version's time from `SOURCE_DATE_EPOCH`,
      else the newest of the game's and the toolkit's commit times;
      `"volatile": ["built", "sources.*.branch"]`; the `-o<6 hex>` options
      digest in the version when the option set, the HUD pack or the CMake
      `-D` list is not stock (D12). pytest: two builds differing only in
      render scale, or only in `--allow-debug`, get different versions,
      and a stock build keeps today's format.
- [x] 3.3 Check by hand on BLiNX 2 (Mac, under the lock): two clean
      builds in two folders give equal `cat_recomp.exe`, `.pdb` and macOS
      binaries. Record the sha256s in the branch notes.
- [x] 3.4 Goldens on the first build with the flags: `blinx2 golden` on
      Metal and `blinx2 bench golden` for D3D11 under Proton, per the
      workspace gates (the flags touch the runtime build).

## 4. Patches and appliers (CLI)

- [x] 4.1 `package/patch.py`: base loading from a manifest, a version
      folder, an app, or a bundle tar (read in place); the usability check
      (app, target, `data_layout`, sha256 on every kept path); the diff
      into changed, new, deleted and kept; `patch.json` (D5, D6).
- [x] 4.2 Base lookup on the host (D5.2, the current version only) and
      from `.git/xbr/bundles/` (D5.3); `package --patch-from X`, `--full`,
      default patch when the base is usable and the patch is under half
      the full size.
- [x] 4.2b The patch-aware game-file sync (D6), shared by the steamos
      applier and modelled for `apply.c`: `want` from the new manifest,
      kept files verified before any change, only new and changed files
      written (`.partial` + flush + rename), only `deleted` removed,
      strays reported. pytest: a code-only patch leaves all 715 kept game
      files of a B3-shaped fixture in place; a kept file with a wrong
      sha256 refuses before any write.
- [x] 4.2a Game-file changes in a patch: on steamos and Windows the
      wizard and the applier warn "this update also changes game data;
      rolling back will not undo that" before applying; on macOS no
      warning, since rollback restores them (D10).
- [x] 4.3 SteamOS: `install_lib.py` `cmd_patch` (D7): `cmd_install`'s
      pre-steps and post-steps around the patch program step and the D6
      sync, in `cmd_install`'s order; `fsync` added to `install_program`,
      the patch step and `switch`; the `launch.lock` check, new for both
      `install` and `patch`; reuse of a complete `versions/<new>`; the
      reinstall path through `renameat2(RENAME_EXCHANGE)` with the
      two-rename fallback; `install.sh` running it when `patch.json` is
      present; the patch tar deterministic as the full tar is. pytest on
      temp roots:
      - apply equals a full install byte for byte, launcher, desktop entry
        and runtime marks included;
      - a base that is installed but not `current` refuses;
      - a wrong base manifest sha refuses and touches nothing;
      - a kill at each step (before and after the rename, during the
        game-file step, after the switch, between the reinstall path's
        renames) leaves a launchable version, and a rerun completes;
      - `install` and `patch` refuse while `launch.lock` is held;
      - rollback returns to the base, and `--keep 3` prunes;
      - a base from a pre-Proton-pin install gets the Proton step.
- [x] 4.4 macOS: `templates/macos/apply.command`, the `xbr-swap` helper
      (`renamex_np(RENAME_SWAP)`, `F_FULLFSYNC`; CLT clang, universal
      arm64 + x86_64, `-mmacosx-version-min` = the game's deployment
      target, signed ad hoc), the previous app at
      `<dir>/.<App>.previous.app` with `apply.command` and `xbr-swap`
      copied to `<dir>/.<App>.previous.tools/`, the journal at
      `<dir>/.<App>.apply.json`, and the patch DMG (D9). pytest on a
      fixture `.app` in a temp folder (`cp -c` falls back to `cp` off
      APFS):
      - `codesign --verify` passes after the overlay;
      - a kill before and after the swap leaves an app at the path, and a
        rerun completes;
      - rollback, also after the DMG is gone (from the tools copy), and
        it restores a changed game file;
      - the data folder is not written by apply or rollback;
      - an `EPERM` from the swap and an `EACCES` at the clone (both
        simulated) change nothing and offer `~/Applications`.
      Once by hand on this Mac: `/Applications` with and without the App
      Management permission (needs-user to toggle it).
- [x] 4.5 Windows (0.1 decided), as in D8:
      - the stable root stub (`stub_abi = 1`, reads `current.txt`); the
        manifest's `root` block (stub_abi, stub and `apply.exe` sha256
        and size) outside `files[]`; a Windows base usable only with
        `current.txt` and an equal `stub_abi` (D5);
      - the per-version launcher with `RECOMP_GAME_FILES` at the root
        `game_files\`, holding `Local\<App>-running`;
      - the NSIS installer writing the versioned layout with `apply.exe`
        and `state\history.txt` at the root, embedding `apply.exe` and
        calling `apply.exe migrate` / `apply.exe switch <v>` for links,
        flushes and `current.txt`; the migration in the safe order (link
        into `versions\<old>`, the `game_files` junction to the root,
        write `current.txt`, swap the stub, then delete); the uninstaller
        removing `versions\`, `current.txt`, the stub, `apply.exe` and
        `state\`, junctions without following them;
      - `apply.c` (llvm-mingw with `-Wl,--no-insert-timestamp`, BCrypt
        SHA-256, `CreateHardLinkW`, `FlushFileBuffers`, `MoveFileExW`,
        the junction via `FSCTL_SET_REPARSE_POINT`) with `apply`,
        `rollback`, `migrate`, `switch` and `--keep`, the base check
        against `current.txt`, reuse of a complete `versions\<new>`, the
        D6 sync, the running-game mutex, and each patch replacing the
        root `apply.exe` after the switch.
      Tests: a host-built unit test of `apply.c`'s portable plan logic,
      and a Python model test of the same plan.
- [x] 4.6 Base mismatch messages as in D10 on all three appliers (not
      current, a wrong manifest sha, a kept file mismatch), exit non-zero,
      and nothing changed.
- [x] 4.7 `docs/bundle.md` in the CLI (new): `manifest.json` schema 2,
      `patch.json`, the per-target layouts and appliers. `docs/manifest.md`
      documents `game.toml` and only gains `[wizard] private`.

## 5. Local source mode and manifest schema 2 (CLI)

- [x] 5.1 `[wizard] private` (bool, default false) in the manifest
      schema; `repo` may be absent only when `private = true`, else the
      existing config error; a private game's `wizard config` omits repo
      and update fields; `xbr wizard build` and the publish flow refuse a
      private game (D14). pytest for all four cases (public with repo,
      public without repo is an error, private without repo, private with
      repo refused for publish).
- [x] 5.2 Manifest `schema 2`: `source` (`tag` / `local` / `dev`, filled
      from the clone's mark), `volatile`; readers accept 1 and 2;
      `private_leaks` covers `source` (a pytest that neither a local path
      nor a `file://` origin ever lands in it).
- [x] 5.3 `docs/manifest.md` (`[wizard] private`) and `docs/wizard.md`
      (developer section: `--source` and `--patch-from`, never shown to
      players).

## 6. Wizard (Go)

- [x] 6.1 `repo.Ensure` (D4): clone; fetch-and-checkout a clean marked
      clone at another commit (fetch `tag <tag>` and check it against the
      lock commit in player mode; fetch `REF` with no lock check in local
      mode); accept and mark a legacy clone
      (clean, origin == `[wizard] repo`, shallow, at a tag's commit);
      reset a local-mode origin on the next player-mode run; refuse local
      changes or an unknown clone. The mark is at `.git/xbr/wizard.json`.
      Go tests on temp repos: a tag bump, a legacy clone from today's
      `repo.Clone`, a downgrade, a dirty clone, a foreign origin, local
      then player mode, and a fetch failure leaving the old checkout.
- [x] 6.2 `--source PATH[#REF]`: checkout or bundle clone, `file://`
      origin, the mark with `source: local`, config from `wizard config
      --json --dev`, the banner on every screen, absent from settings and
      the player help (D14); a warning when the checkout is dirty; the
      hidden `--patch-from FILE` passed through to `package` (D5.1). Go
      tests for both kinds, a bad ref, a dirty checkout, and a game with
      a `repo` (the update check still runs, provenance is `local`).
- [x] 6.3 Screens (D13): the build folder line, the output choice per
      target from `package --plan --json`, "Rebuild everything",
      the cross-host base picker from the plan's `bases`, the end screen's
      apply steps and "Install now" on the host's own target, the disk
      line and "Free space".
- [x] 6.4 `xbr wizard check` passes: `wizard/check.sh` (`gofmt -l` empty,
      `go vet`, `go test`, `staticcheck`), then the double build with
      equal sha256s.

## 7. Gates

- [x] 7.1 CLI: `uv run pytest tests`, `uv run ruff check . && uv run ruff
      format --check .`, `xbr wizard check`.
- [x] 7.2 Toolkit: Mac build with `DEVELOPER_DIR=/Library/Developer/
      CommandLineTools`, `tests/posix_ctest.sh <build-dir>` 0 FAIL.
- [x] 7.3 Equality test (D12): a pytest on the CLI's fixture game that
      builds clean in one temp folder and incremental (previous commit,
      then one code change) in another, and compares `files[]` minus the
      declared volatile fields. Then once by hand on BLiNX 2 on the Mac
      under the lock: a clean steamos build and an incremental one after a
      one-line runtime change give equal staged manifests. Record the
      times of both runs.
      Done (2026-10-17): `tests/test_incremental.py::test_incremental_equals_clean`.
      BLiNX 2 by hand with a one-line toolkit runtime change that reaches
      the exe (bench branch 6117bf7f, a guest_vmem.c message; the exe
      sha256 goes from bcb8d71d to acf7a405): incremental 8.8 s wall,
      clean `--clean` 29.4 s; the same bundle name, 497 `files[]` equal,
      and the manifest equal minus `volatile`.
- [x] 7.4 cat: `uv run pytest scripts`, ruff, the CLI pin moved.
      Done against the CLI branch through `XBOXRECOMP_CLI_DIR`: 81 passed,
      ruff clean. The pin itself needs a tag, so it moves in 10.1.
- [x] 7.5 (needs-user: the PC in Windows) Windows:
      - a BLiNX 2 v1 in-place install migrates to the new layout, and the
        game starts;
      - a patch applies and the game starts;
      - `apply.exe rollback` (the root copy, with the patch folder
        deleted) returns to the v1 files, and v1 starts through its
        `game_files` junction;
      - the PC is powered off (or `apply.exe` is killed) during an apply,
        and after the restart the old version starts or a rerun
        completes;
      - the uninstaller leaves no program files, removes the junction
        without touching the root `game_files\` through it first, and
        keeps the data folder.
      Done (2026-10-17, native Windows 11, 7 of 7 pass, with the review
      fixes at CLI ec41b58): runs/wizard-incr-75/RESULTS.md. It also
      covered a damaged patch file ("damaged patch", nothing changed) and
      a reinstall repairing a damaged version.
- [x] 7.6 (Done 2026-10-18: MERGE WITH FIXES, the fixes at CLI ec41b58.) review of the CLI and toolkit branches; fixes back to the
      branch's agent.

## 8. SSX 3 and Spartan packaging (their sessions; this spec edits nothing there)

- [x] 8.1 (xb-windows) Spartan: `git init` in `spartan/tca` and a first
      commit, excluding the dump, the build trees and `tca-old/` via
      `.gitignore`, which also covers every output a package run writes
      (`build-pkg-*`, `dist/`, `analysis/`, `src/recomp/gen/`, `.venv`,
      `game_files/`, `build-logs/`).
- [x] 8.2 (ssx3-ec, xb-windows) Each game: enable `[package]` (`app` as
      drafted: `Ssx3`, `SpartanTotalWarrior`; targets the game builds),
      `[data]` defaults, and `[wizard]` with `private = true` and no
      `repo` until the game has a public repo, an icon if one exists and
      no config options (no enhancements layer) (D15).
- [x] 8.3 (ssx3-ec, xb-windows) `packaging/launch.env.default.windows`
      (and `.macos` where macos is a target), `packaging/windows/
      README.part` (and `macos/`).
- [x] 8.3a (ssx3-ec, xb-windows) A `LICENSE` on the same terms as cat's and
      b3's (the orchestrator's call, 2026-10-17); the CLI refuses to
      package without one.
- [x] 8.4 (ssx3-ec, xb-windows) `<game> package steamos --plain` builds a
      bundle on the Mac, and `<game> wizard config --json --dev` prints a
      valid config, both at the CLI pin that has phase 5. After the
      package run, `git status --porcelain` in the game tree is empty
      (the stage keys and the version need a clean tree).
      Done 2026-10-17 at CLI v0.8.0 (5e2f287): Spartan spartan/tca 4ccbc9c,
      d0219a6, 90c93da; SSX 3 ssx3/recomp a70e0ac plus d3b30d6
      (ITEM/packaging 60290f7). Both: package steamos rc 0, a
      schema 2 manifest, no config.default.toml, GE-Proton11-7 pinned, a
      clean tree after, and wizard config --dev valid (private, no repo).

## 9. Acceptance on the Steam Deck (needs-user: the Deck in desktop mode)

Every build runs on the Mac through the wizard (`xbr-wizard`, steamos
target, the output folder on the Mac); the bundle or patch is copied to
the Deck with `scp` and installed there over `ssh <bench-host>`. Nothing is built
on the Deck. The install keeps the default 3 versions; no larger `--keep`
is ever passed.

Burnout 3 (incremental build and patch):

- [ ] 9.1 Base. Read the base manifest locally from `b3/dist/
      Burnout3Takedown-20261012.1309-c56574b4-te5d407e-g7e7298dd-
      dirty90bdf81c-steamos.tar`, and check its sha256 equals
      `ssh <bench-host> sha256sum ~/Games/Burnout3Takedown/versions/<that
      version>/manifest.json`. That install was not made by the wizard;
      its schema 1 manifest is a valid base (D5).
- [ ] 9.2 First wizard build of B3 in a fresh build folder
      (`xbr-wizard --source` on the b3 checkout, plus the hidden
      `--patch-from` that tar) for steamos. The program differs from the base (new CLI, toolkit and
      determinism flags), so this makes a patch whose kept set is the 715
      game files. Apply it on the Deck with `./install.sh`: the new
      version is `current`, `versions/` holds at most 3, the game launches
      to the menu (windowed, with sound), `install.sh rollback` returns to
      the base and launches, then switch forward again.
- [ ] 9.3 Second build in the same folder after a code-only change (one
      line in b3's runtime hooks, on a scratch branch): the plan shows
      import, generate (unless the change is in gen inputs), icon and hud
      reused and only compile, stage and wrap run. The patch's base is the
      9.2 version from the plan's `bases`, and it holds only the changed
      program files (expected: `burnout3.exe` and `.pdb`, about 21 MB,
      plus the manifest, SHA256SUMS and the applier). Apply it, launch,
      roll back to 9.2, launch, and record the build time against 9.2's.
- [ ] 9.4 Negative: with the 9.2 version still installed but `current`
      switched back to the original base (`install.sh rollback`), apply the
      9.3 patch: it refuses with D10's message because its base is not
      `current`, and changes nothing (`status` before and after are
      equal). Switch forward again.
- [ ] 9.5 Equality: a clean wizard build of the 9.3 commit in another
      folder gives a staged manifest equal to 9.3's full tree (minus
      `volatile`).

SSX 3 and Spartan (full builder through local source mode):

- [ ] 9.6 SSX 3: `xbr-wizard --source ssx3/recomp` (checkout) on the Mac,
      steamos, full installer. On the Deck: `install.sh` into a fresh
      `~/Games/Ssx3`, the game launches, and `manifest.json` has `source.
      kind = "local"`, `via = "checkout"` and no path.
- [ ] 9.7 Spartan: `git bundle create` of `spartan/tca` into the
      scratchpad, `xbr-wizard --source <bundle>`, steamos, full installer;
      install into a fresh `~/Games/SpartanTotalWarrior`, launch, and check
      `source.via = "bundle"`.
- [ ] 9.8 Write the results (versions, sizes, times, launch and rollback
      verdicts) in the branch notes and `cat/TASKS.md`. Stop every poller
      started for the runs.

## 10. Merge and release

- [x] 10.1 Squash-merge the CLI and toolkit branches, tag the CLI, move
      the pin in cat and b3 (the orchestrator). Done 2026-10-17: CLI
      6b8cea3, release 5e2f287 tagged v0.8.0 (not pushed yet); toolkit
      c3cb5064; cat and b3 pin v0.8.0. The toolkit pin moves with the next
      fork push round.
- [ ] 10.2 After the merge, the workspace steps (notes, runs, worktree
      removal, TASKS).
- [ ] 10.3 Archive this change only after `cli-extraction` is archived:
      the packaging delta's "Manifest and version" is written over
      `cli-extraction`'s MODIFIED text, so archiving this one first would
      be overwritten by the older text. If `cli-extraction` is still open
      then, rebase the delta on the live `specs/packaging/spec.md`
      instead.
