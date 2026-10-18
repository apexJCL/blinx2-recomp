# new-game-portable-host: the `xbr new` template boots on Windows and macOS

Status: written by the reviewer (2026-10-14), so no separate spec review;
the merge gets the review. Facts were checked against the code at
these commits:
- toolkit `posix-host/portability` 38717b2 (public `blinx2-v0.3.0`,
  a63c64f): `templates/new-game/src/main.c` is Win32-only;
- xboxrecomp-cli `main` 9e400eb (v0.6.6): `xbr new` writes
  `targets = ["windows"]`;
- b3 `main` 58994b1 (`src/game/main.c`, the hand port of b3-macos-host) and
  cat `main` 127572f (`src/main.c`), the two games that already run on both
  hosts;
- Spartan: Total Warrior at `spartan/tca`, a fresh `xbr new` game from the
  public CLI v0.6.6 and toolkit blinx2-v0.3.0, which is the example of what
  `new` produces today. It is read only; nothing in it changes.

The spec lives in cat (openspec is here), like b3-macos-host and the CLI
changes.

## Why

A game made by `xbr new` cannot build or run on the Mac, and under Proton
it loses its own crash report.

- **Win32-only host.** The toolkit's `templates/new-game/src/main.c`
  includes `<windows.h>` and `<dbghelp.h>` unconditionally (lines 33-35),
  reports faults from a VEH with dbghelp symbols (132-287), boots from
  `WinMain` (291-427) with `MessageBoxA` for the fatal steps (322, 331)
  and has `main` call `WinMain` (469-474). `xbr new` copies that file and
  patches only the game's constants (`scaffold.py` 286-336), so Spartan's
  `src/main.c` differs from the template by its name, title ID, entry
  point and paths alone.
- **The manifest says so.** `scaffold.py` 100-102 writes
  `targets = ["windows"]` with a comment pointing at `docs/porting.md`
  "macOS as a target" (65-73), which tells the porter to write the POSIX
  host code by hand from cat's `src/main.c`; the CLI README repeats it
  (100-106). `./tca build macos` fails at `build.py` 47-48 with
  "game.toml's build.targets has no macos". The toolkit at 38717b2 has
  everything else a POSIX arm64 host needs (b3-macos-host used it with no
  toolkit edit): `xbox_PosixMmioFault`, `xbox_HostWindowMain` with the
  CAMetalLayer window, the SDL audio device, the partition images.
- **No stdio log.** The template never reads `RECOMP_STDIO_LOG`
  (recomp_env.h:100), and its executable is a GUI-subsystem program
  (`CMakeLists.txt` 66, `add_executable(... WIN32 ...)`), so under Proton
  its stdout and stderr go nowhere. The bench (`run_game.sh` 21-24), the
  Windows launcher (`launcher.c` 188) and the SteamOS launcher
  (`launch.sh` 113) all set the variable and read that file; cat
  (`host_stdio_setup`, main.c 1018-1052) and b3 (`stdio_log_setup`,
  main.c 121-133) honour it. Spartan's first Proton run on the Deck
  (2026-10-14) died at guest-main start with an access violation, and
  the `[CRASH]` report the VEH printed was lost with the rest of the log.
  The bench's fault check reads `game-stdio.log` for `bench.crash_tag`
  (`checks.py` 80-86; the default is `[CRASH]`, `manifest.py` 129), so
  a scaffolded game cannot even be benched to a verdict.

Both games that run on the Mac solved this by hand, and both the same way:
one `main.c`, a shared `host_main`, the host-specific parts under
`#if defined(_WIN32)` / `#else`. The template should ship that shape, so
the third game and every one after it start on both hosts.

## What changes

Two repos. No cat or b3 change: neither uses the template (cat's `main.c`
and b3's have long diverged from it), and the toolkit libraries are not
touched, so their builds and goldens cannot move.

**Toolkit** (`templates/new-game/`, branch off `posix-host/portability`):
- `src/main.c`: one file, one boot sequence (`host_main`), with the host
  sections the way cat and b3 have them. POSIX gets: `RECOMP_STDIO_LOG`
  and unbuffered stdio from the entry point; a SIGBUS/SIGSEGV handler on
  an alternate stack that hands trapped MMIO to `xbox_PosixMmioFault`
  first and prints the same `[CRASH]` report through `write(2)`;
  `dladdr` for the symbol the fault was in; the frame-pointer native
  stack on Apple arm64; the SDL window through `xbox_HostWindowMain`
  with the guest on its own thread, `RECOMP_HEADLESS=1` for none; Metal
  as the backend default on Apple when `RECOMP_PB_BACKEND` is unset.
  Windows gets `RECOMP_STDIO_LOG` (new: it was ignored) and keeps every
  other line of behaviour: the VEH, dbghelp, `MessageBoxA`, `WinMain`,
  the boot order and its messages. The file stays game-agnostic: the
  `YOUR_GAME_*` macros, the comment marks `xbr new` patches, and the
  tutorial comments stay; no title default enters it.
- `CMakeLists.txt`: the Windows import libraries under `if(WIN32)`; the
  OpenSSL hoist every POSIX game needs before `add_subdirectory` of the
  toolkit; Clang's `-Wno-parentheses-equality` on the generated sources
  (llvm-mingw is Clang too, so the Windows build quietens as well). The
  `xinput` import library is the tracker item's to change (`xinput1_4`, since a
  Mac-built exe imports `XINPUT1_3.dll` that stock Windows lacks); this
  change does not touch that line beyond moving it (design D7).
- A standalone ctest, `tests/template_main`, that builds the template
  `main.c` against the toolkit with stub guest symbols and runs it
  without an XBE: the template cannot rot on either host again.

**CLI** (`xboxrecomp-cli`, branch off `main`):
- `scaffold.py`: `targets = ["windows", "macos"]` with a new comment;
  the template patches and the Clang declaration unchanged (the template
  will declare `recomp_dispatch_init` itself, which `DISPATCH_DECL`
  already treats as a no-op, 326-328); the README template and the
  `next:` summary name both build directories; a note (not an error)
  when the toolkit copied beside the game still has the Win32-only
  template.
- Docs: `README.md` "macOS" and `docs/porting.md` "macOS as a target"
  describe the two-host template instead of the hand port; `commands.md`
  and `manifest.md` need no change (`build [windows|macos]` and
  `build.targets` already describe both; the manifest default for a
  `game.toml` without the key stays `["windows"]`).
- Tests: `test_scaffold.py` follows the manifest change, and
  `test_real_template_patches_match` also checks that the real template
  is two-host (has the `_WIN32` host sections, no unconditional
  `<windows.h>`), so a template regression shows up in the CLI's suite,
  which runs with the toolkit checkout beside it.

## Non-goals

- A `linux` build target. Design D8 says what falls out at the source
  level and why it stays untested and unlisted.
- `package macos` for a scaffolded game: it needs `package.templates`
  (the macOS launcher, Info.plist, README part; `manifest.md` 162) that
  no template provides. The developer build (`build/<exe>`) is the
  deliverable, as in b3-macos-host.
- Title defaults in the template: `RECOMP_TITLE_KEVENTS`, `RECOMP_VBLANK`,
  `RECOMP_GUEST_LOCK`, the fence and frame-counter mirrors, the RAM size,
  the USB pad count. cat and b3 set them for their XDKs; a new title
  finds its own in the porting loop, and `docs/porting.md` names the
  first one to try when a POSIX boot faults in the vblank DPC (D6).
- `RECOMP_GAME_FILES` and `RECOMP_HDD_DIR` in the template (the packaged
  launchers set them; packaging is opt-in and out of scope here). A
  follow-up in TASKS.
- The Win32-only diagnostics cat and b3 carry (thread dumps, hang
  sampler, NaN trap, `--record`/`--seconds`): title tooling, not
  template code.
- Fixing anything the toolkit does wrong for Spartan once it boots. A
  fault in lifted code, correctly reported by the new host, is this
  change's success; what the fault is belongs to the Spartan port.

## Success criteria

1. A fresh `xbr new` game (the CLI and toolkit worktrees, Spartan's dump
   read in place) has `targets = ["windows", "macos"]`, and both
   `./<slug> build windows` (llvm-mingw, on the Mac) and
   `./<slug> build macos` (Apple clang, `DEVELOPER_DIR` set) build their
   executables from the unpatched template copy, with no hand edit of
   `main.c` or `CMakeLists.txt`.
2. The macOS build boots on Metal, headless, with `SDL_AUDIODRIVER=dummy`,
   to its first presented frames (`RECOMP_FB_DUMP`), or dies in lifted
   code with a complete `[CRASH]` report: the signal, the host PC and the
   generated function it is in, the guest registers, the guest return
   addresses, the native stack. Either outcome passes; a silent death or
   a hang without a report does not.
3. The Windows build, run under Proton on the Deck with `RECOMP_STDIO_LOG`
   set (the bench's way), writes its boot lines and, when it crashes, the
   `[CRASH]` report to that file. With the variable unset it behaves as
   before this change.
4. Toolkit gates: Mac build, `tests/posix_ctest.sh` 0 FAIL with the new
   `template_main` test among the passes; the test also passes under
   Proton on the Deck. CLI gates: `uv run pytest tests` (with the toolkit
   worktree as `XBOXRECOMP_DIR`, so the real-template test runs) and
   ruff. cat and b3 build unchanged against the toolkit worktree.
5. The CLI docs no longer tell a porter to write the POSIX host by hand.
