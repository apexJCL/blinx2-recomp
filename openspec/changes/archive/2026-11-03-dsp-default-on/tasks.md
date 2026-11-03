## 1. Toolkit (`feat/dsp-default-on` off `posix-host/portability`)

- [x] 1.1 `CMakeLists.txt` and `cmake/dsp56300.cmake`: the default is ON when the target has an archive and OFF otherwise, with no warning; the new help string; `xboxrecomp_dsp56300_migrate()` (D1)
- [x] 1.2 `cmake/dsp56300.cmake`: extraction safe to share (a temporary directory, then the stamp, then the rename) and read-only once the stamp matches (D5)
- [x] 1.3 `recomp_env.c` `apu_dsp_resolve` (D2):
  - unset resolves to 1 in a build with the DSP and its device;
  - a build without them stays on the stub with no line;
  - the override line is worded for the default case;
  - the key row's help text in `recomp_env.h`
- [x] 1.4 ctest `apu_dsp_key` cases:
  - unset gives the JIT with the device, and the stub silently without it;
  - `0` and empty give the stub;
  - a game default of `0` gives the stub;
  - the override line in the default case
- [x] 1.5 `RECOMP_APU_DSP=0` in the ctest environment of the stub tests: `apu_dsp_ack`, `apu_mixdown`, `apu_irq`, `apu_monitor`, `apu_lifecycle`, and any other that the default breaks
- [x] 1.6 A `cmake -P` ctest for `xboxrecomp_dsp56300_migrate()`:
  - the old option's OFF turns ON once;
  - a command-line OFF in the same configure is kept;
  - with the marker set, an OFF is kept
- [x] 1.7 `tests/posix_ctest.sh` (D5):
  - one sequential configure fills `$B/_deps/dsp56300`;
  - `XBOXRECOMP_DSP56300_CACHE` is passed to `build_one`, the per-target case and `_root`;
  - a stub-only `template_main` leg;
  - the run time before and after is recorded
- [x] 1.8 Stale "opt-in" wording:
  - `CMakeLists.txt` (the DSP comment block);
  - `src/apu/CMakeLists.txt`;
  - `cmake/dsp56300.cmake`;
  - `README.md`;
  - `NOTICE`;
  - `docs/runtime/`
- [x] 1.9 `CHANGELOG-blinx2.md` entry
- [ ] 1.10 Gates:
  - Mac build;
  - `tests/posix_ctest.sh` with 0 FAIL;
  - `GAMES="cat blinx b3 ssx3/recomp spartan/tca jsrf/skates kuf/project" TOOLKIT=<worktree> sh notes/build-all.sh`, with `WIN_BUILD_HOST=bench host-win` when the PC is up on Windows
- [ ] 1.11 Review, fixes, merge; then the orchestrator's public toolkit round and its `blinx2-vX` tag

## 2. CLI (`xboxrecomp-cli` branch `feat/dsp-default-on`)

- [x] 2.1 `manifest.py`: the default `stock_cmake` gains `-DXBOXRECOMP_APU_DSP=ON`; so does the new-game template's `stock_cmake = []` (`scaffold.py`); `docs/manifest.md`
- [x] 2.2 Packaging and bench configures pass `-DXBOXRECOMP_DSP56300_CACHE=<per-user cache>/dsp56300` (D5)
- [x] 2.3 `credits.py`: drop "in games built with XBOXRECOMP_APU_DSP"
- [x] 2.4 `package/macos.py`: a comment that a hardened-runtime signature needs `com.apple.security.cs.allow-jit` (D4)
- [x] 2.5 A release wizard end-to-end case: a fresh tree with no network shows the dsp56300 configure error to the player
- [ ] 2.6 Gates: `uv run pytest tests`, ruff check and format; review; merge; the games' `[cli]` pins move with the next CLI release

## 3. Games (one branch each, in order; pins move to the new tag, D6)

Each branch carries:
- `-DXBOXRECOMP_APU_DSP=ON` in `stock_cmake`;
- the NOTICE dsp56300 section;
- the env doc row;
- `launch.env.default.{windows,macos}`: the JIT is on, and a commented `# RECOMP_APU_DSP=0` opt-out;
- a players-first CHANGELOG entry;
- the toolkit pin move.

No game runs goldens (the user, 2026-10-30). Each game is checked on the PC with a headless smoke and `audio_check`, paired with a stub run. The smoke exe comes from a plain `<game> build` or a bench build in an existing tree, not only a package, and its log must have no `[ENV] ... has no APU DSP` line (D6). A Metal pair runs on the Mac, and a Deck pair is non-blocking. The tracker item records per game: flips/s, GP/EP average and maximum per APU frame, and the listen commands for the Mac, the PC and the Deck.

- [x] 3.1 BLiNX 2:
  - the `CMakeLists.txt` block becomes the one `XBOXRECOMP_APU_DSP_MIGRATED` line (D1);
  - the `docs/env.md` `RECOMP_APU_DSP` row
- [x] 3.2 BLiNX 1
- [x] 3.3 JSRF:
  - the bench `dsp` axis gets `stock = 1`;
  - `README.md`
- [x] 3.4 SSX 3
- [x] 3.5 Burnout 3:
  - the front-end music (`B3XboxFx.bin`) plays (the JIT smoke runs `runs/dsp-default-ITEM/{pc,mac}/b3-jit`: past flip 5000 at 60 fps, `B3XboxFx.bin` opened, the GP at about 44,000 cycles a frame, first sound at 18.8 s, then a -24 dBFS median with no dropouts);
  - `race_gate.py` drops its `RECOMP_APU_DSP_ACK` setdefault;
  - `docs/running.md`
- [x] 3.6 KUF: after the tracker item's `feat/kuf-dsp-default` merges, drop its `D(APU_DSP, "1")`; the `stock_cmake` entry stays
- [ ] 3.7 Spartan (parked): `build-all` only; its NOTICE when it is un-parked
- [ ] 3.8 Any game that fails (D6): `D(APU_DSP, "0")`, a follow-up item, and the user is told

## 4. Close

- [ ] 4.1 A follow-up item for an `audio.dsp` config key and menu item (D3)
- [ ] 4.2 Archive `apu-dsp-emulation` first, with its open tasks resolved (done in this spec's commit), so that this delta applies to `specs/apu-dsp`
- [ ] 4.3 TASKS.md
