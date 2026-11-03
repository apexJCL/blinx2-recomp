## Context

- **Toolkit build.** `xboxrecomp/CMakeLists.txt` declares
  `option(XBOXRECOMP_APU_DSP ... OFF)` and calls `xboxrecomp_dsp56300()`
  (`cmake/dsp56300.cmake`). That call takes the pinned v1.0.0 archive for six
  triples: Apple, llvm-mingw and Linux, each on x86-64 and arm64. A target
  without an archive (iPadOS, MSVC, universal macOS) builds OFF with a
  warning.
- **Run time.** `src/platform/recomp_env.c` `apu_dsp_resolve()` runs after
  the game defaults. It turns `RECOMP_APU_DSP=1` into the JIT only in a build
  with both `XBOXRECOMP_APU_DSP` and `XBOXRECOMP_APU_DSP_DEVICE`. It then
  forces `apu_dsp_ack` to 0 and drops `apu_mixdown_all`. A run that finds no
  MCPX window keeps the stub (`mcpx_apu_dsp_device_on`).
- **Packaging.** `xbr package` passes `build.stock_cmake` on every packaging
  configure, and refuses a cache whose value differs from it
  (`xboxrecomp-cli` `docs/manifest.md`, `build.py` `stock_cmake_args`). The
  CLI's default for `stock_cmake` is `["-DXBOXRECOMP_ENHANCE=ON"]`
  (`manifest.py`); the new-game template has `stock_cmake = []`
  (`scaffold.py`).
- **Other builds never see `stock_cmake`.** It applies only to stock and
  package builds (`build.py` with `stock=True`, from `package/__init__.py`
  and `package/incr.py`). A plain `<game> build`, a local bench build
  (`bench/ship.py`) and a PC build-host build (`buildhost.py`) configure
  without it. For those exes, the toolkit's option default and the cache
  migration (D1) are what turn the DSP on.
- **Games today.**
  - BLiNX 2 sets the option ON in `CMakeLists.txt` and in `stock_cmake`, with
    a once-per-tree cache migration (`CAT_APU_DSP_MIGRATED`).
  - JSRF sets it in `stock_cmake`.
  - KUF's tracker item branch sets it in `stock_cmake` and adds
    `D(APU_DSP, "1")`.

## Decisions

### D1. Build default ON where an archive exists, with a one-time migration

**Default.** `cmake/dsp56300.cmake` is included unconditionally; it only
defines functions. The option's default is ON when
`_xboxrecomp_dsp56300_triple` finds an archive for the target, and OFF
otherwise. MSVC (upstream's Windows build), iPadOS and universal macOS
therefore configure without a warning on every run. An explicit ON on such
a target still warns, once per configure, as today. This keeps an upstream
MSVC configure quiet and free of downloads.

**Migration.** `option()` never replaces a cached value. Every existing tree
would stay OFF: dev, bench, `wt/build-matrix` and the `D:/bench` trees.
Only package trees get the value from `stock_cmake`; dev, bench and
build-host trees depend on this migration.
The migration is a function in `cmake/dsp56300.cmake`,
`xboxrecomp_dsp56300_migrate()`, which a `cmake -P` test can drive:

1. The option's help string changes, because the option is no longer
   "opt-in".
2. Before `option()` runs, the function checks two things:
   `XBOXRECOMP_APU_DSP_MIGRATED` is not set, and the cached entry is OFF
   with the old help string (what the old `option()` left behind). When both
   hold, it sets the option ON with FORCE and prints a STATUS line.
3. Then it caches `XBOXRECOMP_APU_DSP_MIGRATED` (INTERNAL), on every
   configure where the flag is unset.
4. A `-DXBOXRECOMP_APU_DSP=OFF` given in that same configure carries
   CMake's own help string, so it is kept.

After one configure, every cached OFF carries `option()`'s help string
(checked with CMake 4.4.4). An OFF chosen under the old toolkit therefore
looks like the old default, and is turned ON once. The STATUS line names
it. Nobody ships stub-only, so this case is rare.

**BLiNX 2.** A BLiNX 2 tree that went through `CAT_APU_DSP_MIGRATED` and
was then set OFF by the user would be flipped by the toolkit's migration.
That would break the promise in BLiNX 2's `docs/env.md`. So BLiNX 2's
`CMakeLists.txt` keeps one line before `add_subdirectory`: when
`CAT_APU_DSP_MIGRATED` is set, it sets `XBOXRECOMP_APU_DSP_MIGRATED`. The
rest of its migration block goes, including its own
`set(XBOXRECOMP_APU_DSP ON CACHE ...)`.

### D2. Run-time default: on when the build can run it

**Default.** In `apu_dsp_resolve()`, an unset key resolves to `"1"` in a
build with the DSP and its device. An unset key means it is neither in the
environment nor a game default. This follows the existing `default_on`
convention: unset is on, and `0` or empty is off.

**Builds without the device or the DSP.** An unset key stays on the stub,
with no line, because a build without it is a choice and not a mistake. An
explicit `1` keeps its line.

**Overrides.** The ack and mixdown overrides apply to the default exactly as
they do to an explicit `1`. Their line is printed only when the user set
either key. The line says "the APU DSP (default on) overrides ..." when the
key was unset, and keeps its `RECOMP_APU_DSP=1` wording when the key was set.

**Game hook.** It stays. A game's `D(APU_DSP, "0")` keeps the game on the
stub (the failure policy, D6). A `D(APU_DSP, "1")` becomes redundant.

**Stub tests.** Toolkit ctests that test the stub's ack, fold, interrupt or
lifecycle set `RECOMP_APU_DSP=0` in their ctest environment, so they keep
testing the stub in a DSP build: `apu_dsp_ack`, `apu_mixdown`, `apu_irq`,
`apu_monitor` and `apu_lifecycle`. The others are checked when the default
lands.

### D3. No config.toml key or menu item now

A player-facing `audio.dsp` key was considered and left out:

- The stub is the approximation and the JIT is the hardware's path. Every
  choice the menu offers is either faithful or an enhancement. This one
  would offer a path known to be incomplete.
- `RECOMP_APU_DSP` is resolved in `recomp_env` before the config layer
  loads, and it forces two other keys. A config key would need a second
  resolution point in the APU's start-up. That is runtime code that the
  menu work (the mod API v4 branch) is also changing.
- The escape hatches stay:
  - `D(APU_DSP, "0")` for a game that breaks;
  - `RECOMP_APU_DSP=0` for a player, in `config/launch.env` or the Steam
    launch options. Every game's `launch.env.default` names this line.

  The JIT costs at most about 4% of one Deck core.

A follow-up item is filed for `audio.dsp`: a config key plus a
restart-applied menu item, picked up if a player needs one.

### D4. macOS

**Universal builds.** They stay stub-only, with no warning (D1). No path
builds the game universal:

- `xbr package` and the wizard configure the game on the player's Mac for
  its own architecture;
- neither the CLI nor any game sets `CMAKE_OSX_ARCHITECTURES`;
- only the wizard app is universal, and it links no toolkit.

The packaged Mac app therefore runs the JIT. A universal build would need
both Apple archives merged with `lipo`, and nobody needs one today.

**Intel Macs.** They get `x86_64-apple-darwin`, which has an archive, so they
link the JIT. Audio is off on x86-64 macOS anyway (`AC97_READY`), so the
JIT never runs there.

**Code signing.** The JIT maps executable memory at run time. The packaged
app is signed ad hoc, without the hardened runtime (`package/macos.py`
`codesign --sign -`), and that is what lets the JIT run. If the app is ever
signed with `--options runtime` (notarisation), it needs the
`com.apple.security.cs.allow-jit` entitlement. The CLI's packaging code gets
a comment saying so.

### D5. The download becomes mandatory for every game

**Where it is fetched.** Every first configure fetches the pinned archive
(10–12 MB per target) inside CMake. The fetch does not use the CLI's own
pinned fetch (`fetch.py`, `setup-pins.json`). The pins stay in
`cmake/dsp56300.cmake`, so the two lists cannot drift apart.

**A shared cache.** A player's fresh tree, and every `start_afresh`, would
download the archive again. So the CLI passes
`-DXBOXRECOMP_DSP56300_CACHE=<per-user cache>/dsp56300` on its packaging
and bench configures. That makes the download one-time per user and
target. A shared cache needs extraction that is safe to share. The toolkit
therefore:

1. extracts into a temporary directory next to the final one;
2. writes the sha stamp there;
3. renames the directory into place.

If the rename fails because another configure won the race, it uses the
winner's directory once its stamp matches. A tree whose stamp already
matches is only read.

**A failed download stays fatal**, unlike librashader's.
- A silently stub-only build is what made BLiNX 2 compile the JIT in: the
  Deck's test builds ran the stub for days unnoticed.
- The error names the offline copy (`XBOXRECOMP_DSP56300_ARCHIVE`) and the
  opt-out (`-DXBOXRECOMP_APU_DSP=OFF`).
- The release wizard's end-to-end test gets a case for it: a fresh tree with
  no network, in which the configure error has to reach the player's error
  view.

**CI** needs no network. The game repos' `checks.yml` runs only uv, pytest
and ruff, and the toolkit and the CLI have no workflows.

**`tests/posix_ctest.sh`.** It builds about 61 standalone projects in
parallel, each with the toolkit as a subdirectory. With the default ON, each
would download and extract about 26 MB, roughly 1.6 GB per run. Instead:

1. One sequential configure fills `$B/_deps/dsp56300` first.
2. Every `build_one`, the per-target case, and the `_root` configure then get
   `-DXBOXRECOMP_DSP56300_CACHE=$B/_deps/dsp56300`. With a matching stamp,
   that tree is only read.
3. `template_main`'s DSP leg becomes a stub-only leg
   (`-DXBOXRECOMP_APU_DSP=OFF`).

Gate 1.7 records how much longer the run takes with the JIT linked into
every project. If it grows by more than 25%, projects that do not touch the
APU build with the option OFF.

**Licences.** The licence texts are already staged in every package
(`stage_toolkit_licenses`). Each game's NOTICE gains the dsp56300 section
that BLiNX 2 and JSRF have, and a game without a NOTICE (Burnout 3, KUF)
gets one. Spartan's NOTICE follows when Spartan is un-parked.

### D6. Rollout, pins and failure policy

Order: BLiNX 2, BLiNX 1, JSRF, SSX 3, Burnout 3, KUF. Spartan is parked:
`build-all` only.

**`stock_cmake`.** Every game keeps `-DXBOXRECOMP_APU_DSP=ON` in
`stock_cmake`, or gains it. It is never redundant, because it is the
packaging stock rule (Context). It only covers package trees, though: dev,
bench and build-host exes get the DSP from the toolkit default and D1's
migration, not from this flag. The CLI's default `stock_cmake`
(`manifest.py`) and the new-game template (`scaffold.py`) gain it too, so
new games get the JIT. A game can add the flag before its pin moves: on an
older toolkit it only compiles the JIT in, and the stub stays the run-time
default.

**Pins.**

1. The toolkit change merges on `posix-host/portability`.
2. The orchestrator runs a public toolkit round (scrub plus mailmap) and
   tags a new `blinx2-vX`.
3. Each game's pin moves to that tag on its own branch.

Until the tag exists, games are tested on the workspace toolkit, through
`TOOLKIT=` or BLiNX 2's `../xboxrecomp`.

**Gates for the pin moves.** Every game's pin move has the same gates:
`build-all`, the ctests, and the per-game check below. The user listens by
hand, and no game runs goldens (the user, 2026-10-30).

- BLiNX 2, BLiNX 1 and KUF pin `blinx2-v0.9.0` (local `878012fc`), so their
  move brings only this change.
- JSRF, SSX 3 and Burnout 3 pin `blinx2-v0.8.0` (public `e5a7087`, local
  `2c03630`). Their move also brings four toolkit commits: `b4f60f0c`
  (Shaders menu page), `5fcda2ee` (Windows librashader), `01472df0`
  (licences) and `878012fc` (changelog). Those were golden-validated on
  BLiNX 2 (native Windows D3D11) and passed `build-all` on every game.
  They are present-chain and opt-in work (shaders are off at stock), so they
  need no goldens of their own.

**KUF.** `feat/kuf-dsp-default` (`0a3f9f0`) merges first. KUF's
pin move then drops its `D(APU_DSP, "1")`; its `stock_cmake` entry stays.

**Per-game branch contents:**
- `stock_cmake` entry;
- NOTICE;
- env doc;
- player docs: the `launch.env.default.{windows,macos}` lines, which today
  say "built in but off", plus the commented `# RECOMP_APU_DSP=0` opt-out;
  also JSRF's `README.md` and Burnout 3's `docs/running.md`;
- a players-first CHANGELOG entry;
- the pin move.

**Per-game extras:**
- BLiNX 2: the D1 migration line;
- JSRF: its bench `dsp` axis changes to `stock = 1`;
- Burnout 3: `race_gate.py` drops its `env.setdefault("RECOMP_APU_DSP_ACK",
  "auto")`. `auto` has been the toolkit's default since `f465cd3`, and with
  the JIT on, the setdefault would only print the override line on every
  run.

**Per-game check.**

1. Run one headless smoke and `audio_check` on the PC (native D3D11) with
   the JIT on by default and no env var, paired with a stub run
   (`RECOMP_APU_DSP=0`). The exe comes from a plain `<game> build` or a
   bench build in a tree configured before this change, not only from a
   package, so the check covers the path that never sees `stock_cmake`
   and D1's migration.
2. Pass means all of these:
   - it boots;
   - the log has no `[ENV] ... has no APU DSP` line, and no line that the
     device is missing;
   - the GP runs (`apu_dsp_stats` frames > 0);
   - there are no new dropouts or cap hits;
   - flips/s does not drop by 25% or more;
   - frame ms does not rise by 1.5× or more (CLAUDE.md's flags).
3. The same pair runs on the Mac (Metal), quietly.
4. A Deck/Proton pair per game is non-blocking. Before this change only
   KUF was measured there.
5. The tracker item records, per game: flips/s, GP/EP average and maximum per APU
   frame, and the listen commands for the Mac, the PC and the Deck.

**Failure policy.** A game that fails gets `D(APU_DSP, "0")` in its game
defaults, a follow-up item, and the user is told. A failure is any of:

- a hang or a crash;
- new dropouts or cap hits;
- a performance flag;
- the user's listen.

A failed game does not block the others.

**Build-all.** `notes/build-all.sh`'s default `GAMES` lacks `kuf/project`, so
gate 1.7 passes the full list explicitly.

## Risks

- **Existing trees.** D1's migration covers cached OFF. A tree whose
  configure fails on the download stops until the network is back or the
  archive is given. That is the intended behaviour.
- **Goldens and bench references** were recorded on the stub. A later golden
  that drifts because of the JIT is judged against the DSP first, and is
  re-baselined in that change, not here.
