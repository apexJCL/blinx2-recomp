# new-game-portable-host: design

## Context

**What the template does today** (`templates/new-game/src/main.c` at
38717b2): `WinMain` reads the environment (`recomp_env_init`, 303), sets
unbuffered stdio (306-307), loads symbols and installs the VEH (316-318),
then loads the XBE, maps the memory layout, brings up the APU when
`RECOMP_AC97_READY` says so (349-353), initialises the kernel, the paths
(`xbox_path_init(YOUR_GAME_DIR, NULL)`, 362-365) and the bridge, sets
`g_esp`, builds the flat dispatch table (401), arms the watchdog (413) and
calls `xbe_entry_point` (419). The VEH (223-287) routes trapped registers
through `xbox_VehMmioFault`, prints `[CRASH]`, the guest registers and
the guest VA, and `print_guest_context` (132-204) names the function with
dbghelp and scans the guest stack for return addresses, with the ICALL
ring and the raw frame when the scan is empty. `main` (469-474) calls
`WinMain`.

Everything in that list except the VEH, dbghelp, `MessageBoxA` and the
entry points is host-neutral already: the same calls, in the same order,
are what cat's `host_main` (main.c 1054-1295) and b3's (891-983) make.
The POSIX half both games wrote is the same code twice: a signal handler
on an alternate stack (cat 722-795, b3 643-719), `dladdr` (cat 205-212,
b3 244-252), a `write(2)`-based printf for the report (cat 163-179, b3
200-216), the frame-pointer walk on Apple arm64 (cat 681-716, b3
605-637), `xbox_HostWindowMain(host_main)` from `main` (cat 1448, b3
1115), `RECOMP_STDIO_LOG` first thing (cat 1018-1052, b3 121-133).

**What is title-specific in those two files and stays out of the
template:** cat's `xbox_SetTotalRam(XBOX_DEVKIT_RAM)` (1116), the
`Nv2aMirrorFence` and `Nv2aFrameCounter` addresses (cat 1144, b3 962-970),
the `RECOMP_VBLANK`, `RECOMP_TITLE_KEVENTS` and `RECOMP_GUEST_LOCK`
defaults (cat 1152-1174; b3 1087-1088 on POSIX only), b3's RenderWare
environment (`AC97_READY`, `USB`, `USB_PADS`, `PB_EXEC`, 1048-1073), its
`--headless`/`--record`/`--seconds` (1016-1029), the thread and memory
dumpers, the hang sampler and the NaN trap, the enhancements layer, and
`xbox_HostWindowSetTitle` (the toolkit falls back to the XBE
certificate's name, `fb_present_sdl.c` 64-66, so the template needs no
call).

**What the toolkit gives a POSIX host for free** (38717b2), so the
template does not carry it:
- `xbox_PosixMmioFault(ucv, si_addr)` dispatches APU, AC'97 and OHCI
  accesses on arm64 and returns 0 on any other host
  (`xbox_memory_layout.c` 866-893; declared under `#else` of `_WIN32` in
  the header, 268-272).
- `recomp_env` defaults `RECOMP_AC97_READY` on only where a decoder
  exists (x86-64 Windows, POSIX arm64; `recomp_env.c` 273-278), so the
  template's `if (recomp_env(RENV_AC97_READY))` needs no host guard.
- `xbox_HostWindowMain(guest_main)` opens the SDL window on the process
  main thread and runs the guest on a `guest-main` pthread, a CAMetalLayer
  when `RECOMP_PB_BACKEND=metal`, and returns `guest_main()` on the
  calling thread under `RECOMP_HEADLESS=1` or with no display
  (`fb_present_sdl.c` 506-540).
- `xbox_path_init(dir, NULL)` keeps the game dir and puts the saves and
  partition images under `$XDG_DATA_HOME` or `~/.local/share/xboxrecomp`
  (`kernel_path.c` 644-680), so the template's `NULL` save dir works on
  both hosts.
- `MessageBoxA` exists in the compat layer (`win32_compat.c` 1573), but
  a dialog is not what a headless Mac run wants (D5).
- The `recomp_env` headers reach the game through the `recomp_env`
  target's PUBLIC include dirs (`src/platform/CMakeLists.txt` 27-31),
  which also put `src/` on the path, so `video/video_player.h`
  (`xbox_HostWindowMain`, line 89) is reachable with no CMake change.

## Decisions

### D1. One `main.c`, host sections, a shared `host_main`

The shape is cat's and b3's (b3-macos-host D1 gives the reason: a second
file duplicates the boot sequence and drifts). The file is reorganised,
not rewritten:
- Includes: `"recomp_env.h"` first, then `#if defined(_WIN32)`
  `<windows.h>`, `<dbghelp.h>` `#else` `<signal.h>`, `<dlfcn.h>`,
  `<unistd.h>`, `<pthread.h>` `#endif`, then the C headers (cat 34-54).
  The NT types the shared code uses (`BOOL`, `LONG`, `CALLBACK`) come
  from the toolkit's `kernel.h` through `<xbox/xboxrecomp.h>` on POSIX,
  as cat's comment at 40-43 records.
- `host_main(void)`: steps 1-7 of today's `WinMain`, verbatim in order
  and in their messages, with `host_install_crash_handler()` as step 1
  (D3) and `host_report_fatal()` for the two fatal steps (D5). The
  banner line, the `[BOOT]` lines and the `Starting game...` line are
  unchanged; the differences a Windows log may show are listed in D2.
- Entry points: `WinMain` under `_WIN32` and `main` on every host, each
  `recomp_env_init(); host_stdio_setup();` then `host_main()` on
  Windows or `xbox_HostWindowMain(host_main)` elsewhere (cat 1391-1450).
  Windows `main` no longer goes through `WinMain`; it does the same three
  calls, which is what `WinMain` did.
- Game-agnostic by construction: the three `YOUR_GAME_*` macros (85-87)
  and the header comment marks (24-27) keep their exact text, since
  `scaffold.py` `TEMPLATE_PATCHES` (286-325) match them by string and
  report "the template changed" otherwise; `test_real_template_patches_match`
  guards this. The template declares `extern int recomp_dispatch_init(void);`
  after `xbe_entry_point` (the generator emits it, `translator.py` 3424;
  `recomp_types.h` 1061 declares it, but main.c does not include that
  header), which makes the CLI's `DISPATCH_DECL` a no-op as its comment
  intends (326-328). The tutorial comments (the TODO blocks on CRT
  globals and game-specific diagnostics) stay, reworded where they said
  "Windows executable" or "VEH" of the host in general.

### D2. `host_stdio_setup`: `RECOMP_STDIO_LOG` and unbuffered stdio

cat's function (1018-1052), unchanged in behaviour: with the key set,
truncate the file, then on Windows `freopen` stdout and stderr onto it in
append mode (a GUI-subsystem exe has no stderr descriptor to `dup2`), and
elsewhere `freopen` stdout and `dup2` it onto stderr; then `_IONBF` on
both (what the template already did at 306-307) and
`recomp_env_flush_notes()` (recomp_env.h 272), so the deprecated-key
notes land in the log. Called from both entry points right after
`recomp_env_init`, before any other output and before any thread.

The main Windows behaviour change: a run with `RECOMP_STDIO_LOG` set gets
a log where it got nothing. The bench and both launchers set it
(proposal), so the Spartan-on-Proton case becomes diagnosable. A run
without it keeps the old boot sequence, VEH and crash report, with these
differences and no others (the review, 2026-10-14):
- the `[THREAD] ... role=process-main` and `role=guest-main` lines on
  stderr (D4);
- the `[FATAL]` line on stderr, and the dialog text naming the path (D5);
- the deprecation notes print at boot through `recomp_env_flush_notes()`
  instead of from the atexit hook;
- no fatal dialog under `RECOMP_HEADLESS` (D5);
- `xbox_log_thread_role("guest-main", 0)` also calls
  `xbox_DpcMarkGuestThread()` (kernel_bridge.c 563-566), so the boot
  thread drains queued DPCs at IRQL raises, releases and safe points.
  The old template never marked it; the toolkit expects the host's main
  to (kernel_bridge.c 560-562), and cat and b3 do.

### D3. The crash handler

Shared: `report_crash(host_pc, fault_addr, access)` prints today's
`[CRASH]` block (249-259) through `crash_printf`, which is `vfprintf(stderr)`
on Windows and `vsnprintf` into a stack buffer plus `write(2, ...)` on
POSIX, where the handler may run while the faulting thread holds stdio's
lock (cat 157-179). `print_guest_context` keeps its guest-stack scan, the
ICALL ring and the raw frame; its symbol lookup moves into
`host_symbol_for(pc, buf, n)`: `SymFromAddr` on Windows (unchanged),
`dladdr` on the unstripped executable elsewhere (cat 189-213). The host PC
label is `RIP` on x86-64 and `PC` on arm64 (cat 149-155).

Windows: the VEH body is unchanged, including the `0xFD000000` probe
skip, `xbox_VehMmioFault`, and the native-stack scan of the image range;
`SymInitialize` and `AddVectoredExceptionHandler` move from `WinMain`
into `host_install_crash_handler()`, called first in `host_main`, which
is the same point in the sequence (nothing ran between them before).

POSIX (cat 722-795, b3 643-719): `sigaction` for SIGBUS and SIGSEGV with
`SA_SIGINFO | SA_ONSTACK | SA_NODEFER` and a 128 KB `sigaltstack`
(a literal: `SIGSTKSZ` is not a compile-time constant on glibc >= 2.34,
b3 694-699) on the thread that calls `host_install_crash_handler`, which
is the guest thread because `host_main` runs there. Order in the handler:
1. `xbox_PosixMmioFault(ucv, si_addr)`: a serviced access returns with
   pc advanced, nothing printed.
2. An atomic re-entry guard (two faulting threads give one report), then
   `report_crash` with the signal's name, the host pc from the ucontext
   (Apple arm64 `__ss.__pc`, Apple x86-64 `__ss.__rip`, Linux arm64
   `uc_mcontext.pc`, else unknown; b3 586-599), the fault address and,
   when it lies inside guest memory, the guest VA; then the frame-pointer
   native stack on Apple arm64 (`fp`/`lr` chain, cat 681-716) or a
   "not available on this host" line.
3. `SIG_DFL` restored and return, so the instruction re-faults and the
   process dies by the original signal (exit status and core as usual).

The tag is `[CRASH]` on both hosts, the bench default (`manifest.py` 129).
b3 chose `[FAULT]` and sets `bench.crash_tag` in its own `game.toml`
(119); a scaffolded game has no such line, so the template prints the
default.

### D4. Window, headless, backend

- POSIX `main` returns `xbox_HostWindowMain(host_main)`. The process main
  thread belongs to AppKit; the whole boot and the guest run on the
  toolkit's `guest-main` pthread, so the handler and the watchdog
  (installed inside `host_main`) land on it. `RECOMP_HEADLESS=1` is the
  toolkit's key (recomp_env.h 85); the template adds no argv parsing (cat
  has none either; b3's `--headless` is b3's).
- Both entry points call `xbox_log_thread_role("process-main", 0)`
  (kernel.h 1266) and `host_main` logs `guest-main`, as cat does
  (1061, 1403, 1429): the thread names in a crash report then say which
  thread faulted on both hosts.
- Backend: on `__APPLE__`, `RECOMP_PB_BACKEND` defaults to `metal` when
  unset, through `recomp_env_set(RENV_PB_BACKEND, "metal")` right after
  `recomp_env_init`, before `xbox_HostWindowMain` reads it
  (`fb_present_sdl.c` 548). b3-macos-host D3 made the same call and gave
  the reason: the CPU rasteriser runs a title at a few fps on the Mac,
  which is not "boots and plays"; `RECOMP_PB_BACKEND=cpu` still asks for
  it. A host default, not an enhancement: the frame is the stock frame.
  Windows keeps the toolkit default (cpu, recomp_env.h 84): the bench and
  the launchers choose the backend themselves, and changing it would be a
  Windows behaviour change this spec rules out. Decided by the user
  (2026-10-14: "yes Metal default on the Mac").

### D5. Fatal steps report on stderr everywhere, in a dialog on Windows

`host_report_fatal(step, detail)` (cat 1004-1011): `[FATAL] <step>:
<detail>` on stderr on every host, plus `MessageBoxA` under `_WIN32`,
which is what the template shows today for a missing XBE (322-325) and a
failed memory layout (331-335). The messages keep their words; the
first one also says the path it tried, since a scaffolded game runs from
its project root and the most common failure is the dump not being in
`game_files/`; the hint names `YOUR_GAME_DIR`, which `xbr new` patches.
Under `RECOMP_HEADLESS` (no window) the Windows dialog is skipped too: a
modal box in an unattended Proton ctest or bench run waits for a click
nobody gives and reads as a hang. Interactive runs never set the key and
keep the dialog. The key's description (recomp_env.h) and `docs/env.md`
say so.

### D6. No title defaults; the porting doc names the first one

The template sets nothing a title might not want. cat and b3 both needed
`RECOMP_TITLE_KEVENTS=1` for XDK 5849's D3D8, whose vblank DPC sets a
KEVENT built without `KeInitializeEvent`; without it `KeSetEvent` fails
silently on Win32 and dereferences the guest address on POSIX
(b3-macos-host D6, verified there with a `KEVENTS=0` run). That is an
XDK fact, not a host fact, and the toolkit keeps the key off by default
(recomp_env.h 93). So: the template leaves it alone, and
`docs/porting.md` says that a POSIX boot that faults in the vblank DPC
or `KeSetEvent` before the first frame should try `RECOMP_TITLE_KEVENTS=1`
in the environment, and set it in `main.c` once confirmed, the way cat
does (1160-1161). Whether Spartan needs it is part of the acceptance run
(tasks 3.3) and is reported, not decided here.

### D7. CMake

`templates/new-game/CMakeLists.txt`:
- `if(NOT WIN32) find_package(OpenSSL REQUIRED) endif()` before
  `add_subdirectory(${XBOXRECOMP_DIR} ...)`: `xbox_kernel` links
  `OpenSSL::Crypto` PUBLIC and finds it inside its own directory
  (`src/kernel/CMakeLists.txt` 55-57), where the imported target is
  invisible to the game executable; cat (41-43) and b3 (42-44) carry the
  same hoist with the same comment.
- The Windows SDK import libraries (81-91: d3d11, dxgi, dxguid, xinput,
  winmm, dbghelp) under `if(WIN32)`; elsewhere SDL2, the Metal frameworks
  and OpenSSL arrive through the toolkit targets (cat 135-153). The
  `xinput` line itself is BLX-127's: a Mac-built (llvm-mingw) exe imports
  `XINPUT1_3.dll`, which stock Windows lacks, and the fix there is to link
  `xinput1_4`. This change moves the line into the `if(WIN32)` block and
  otherwise leaves it as BLX-127 decides; whichever merges second rebases
  onto the other's spelling.
- `-Wno-parentheses-equality` on `${RECOMP_GEN_SOURCES}` when
  `CMAKE_C_COMPILER_ID MATCHES "Clang"` (cat 179-184, b3 78-81): the
  lifter writes `if ((a == b))`, tens of thousands of warnings per build.
  llvm-mingw is Clang, so the Windows cross build quietens too; a
  warning flag changes no code.
- `add_executable(... WIN32 ...)` stays: it selects the GUI subsystem on
  Windows and is ignored elsewhere (cat 90-91). No strip and no `-Wl,-x`:
  `dladdr` names the generated function from the symbol table.
- The MSVC block (94-100) is untouched; MinGW needs nothing new (the
  template never had the 16 MB stack or PDB options b3 adds, and adding
  them is a Windows change outside this spec).

### D8. Linux: falls out at the source level, out of scope as a target

The `#else` branches are POSIX, not Darwin: `sigaction`, `dladdr`,
`write`, `pthread_self`, `xbox_HostWindowMain` (built under
`!defined(_WIN32)`, `fb_present_sdl.c` 65). The two arch-specific spots
take b3's shape: the ucontext pc has a `__linux__ && __aarch64__` branch
(b3 593-594) and an "unknown" fallback, the frame walk is Apple arm64
only with a one-line fallback. On x86-64 Linux `xbox_PosixMmioFault`
returns 0 and `RECOMP_AC97_READY` defaults off (recomp_env.c 277), so a
title boots without audio and a fault is still reported. The platform
layer adds `_GNU_SOURCE` on Linux for `dladdr` (`src/platform/CMakeLists.txt`
51-53).

That is as far as this change goes. The CLI has no `linux` build target
(`manifest.py` 190 `BUILD_TARGETS`; `test_manifest.py` 83 rejects it),
the Proton bench host runs the Windows build, and no Linux-native gate
host exists, so nothing here is tested on Linux and `xbr new` does not
list it. A `linux` target (CLI, toolchain, a gate host) is a separate
change, recorded in TASKS as a follow-up. The template code is written so
that change needs no `main.c` edit beyond what a Linux build turns up.

### D9. CLI: the manifest, the notes, the docs, the tests

- `scaffold.py` `GAME_TOML` (97-104): `targets = ["windows", "macos"]`,
  comment: "windows builds on every host (llvm-mingw); macos builds on a
  Mac (Apple clang). Drop one to stop `build` offering it." The scaffold
  test's assertion (test_scaffold.py 109) follows.
- `summary()` (675-694) step 3 names this host's default build directory
  (`build/<exe>` on a Mac, `build-win/<exe>.exe` elsewhere), matching
  `build.default_build_target` (build.py 37-42). The `README` template
  (251-279) says the first build is `build-win/<exe>.exe` with llvm-mingw
  on any host, or `build/<exe>` on a Mac.
- `patch_template` (536-566): when the copied `main.c` has no
  `#if defined(_WIN32)` host section, append a note: "the toolkit at
  <sha> has the Win32-only template: `build macos` will not compile until
  the toolkit pin moves past blinx2-v0.3.0, or drop macos from
  build.targets". A note, not an error: the Windows path still works, and
  `new` never refuses over a template it can copy. This covers a
  developer whose `XBOXRECOMP_DIR` or `../xboxrecomp` is an old checkout
  (`toolkit_checkout`, 441-449; `resolve_toolkit_commit` pins that
  checkout's HEAD, 452-463).
- Docs: `README.md` "macOS" (100-106) and `docs/porting.md` "macOS as a
  target" (65-73) describe the two-host template, the Mac build and run
  (`SDL_AUDIODRIVER=dummy`, `RECOMP_HEADLESS=1`, the Metal default,
  `RECOMP_STDIO_LOG`), the D6 note, and that an older toolkit pin needs
  the hand port. `docs/manifest.md` keeps `build.targets` default
  `["windows"]` (110): that is the default for a manifest without the
  key, and cat's and b3's manifests list both explicitly.
- Tests (`tests/test_scaffold.py`): the manifest assertion;
  `test_windows_wrapper_and_messages` and `test_offline_scaffold...`
  check the host-dependent step 3; a test for the Win32-only-template
  note with a `FAKE_MAIN` that lacks the mark versus one that has it;
  `test_real_template_patches_match` additionally asserts the real
  template contains `#if defined(_WIN32)` and `xbox_HostWindowMain`, and
  that `#include <windows.h>` appears only inside a `_WIN32` section.
  The CLI suite is run with `XBOXRECOMP_DIR` at the toolkit worktree so
  that test is not skipped (`REAL_TOOLKIT`, 403-412).

### D10. The toolkit ctest

`tests/template_main/` is a standalone project (its own `project()`, so
`posix_ctest.sh` configures and builds it on its own, as the script's
header describes): it adds the toolkit with `add_subdirectory`, compiles
`../../templates/new-game/src/main.c` as is, plus a `stubs.c` defining
`xbe_entry_point` (prints a line and returns), `recomp_lookup`,
`recomp_lookup_manual`, `recomp_dispatch_init` and `recomp_icall_fail_log`
(the symbols the generated code and `recomp_manual.c` would provide), and
links the executable the way the template's own `CMakeLists.txt` does.
Two tests, both deterministic and both without game data:
`template_main_no_xbe` runs the binary with `RECOMP_HEADLESS=1` in a
directory with no `game/`, and expects exit status 1 with `[FATAL] load
XBE` on stderr; `template_main_stdio_log` runs it the same way with
`RECOMP_STDIO_LOG=<tmp>` and expects that line in the file and an empty
console. No test boots a stub XBE: the memory layout wants a real image,
and the boot itself is what the acceptance run (tasks 3) checks. The
project has no POSIX-only code, so the CLI's Proton standalone list
(`bench/host/tests.sh`) carries it too and the Deck runs it.

The point is not coverage of the boot; it is that `main.c` compiles and
links against the toolkit on every host the toolkit builds on, so the
template can no longer fall behind the runtime unnoticed (the APU hook
and the `recomp_dispatch_init` declaration both did).

### D11. Spartan is re-made from the new template

`spartan/tca` has not been edited since `xbr new` wrote it (its `main.c`
and `CMakeLists.txt` differ from the template only by the patched
constants), so after the merge it is scaffolded again with a fresh
`xbr new` from the released CLI, the dump read in place, rather than
hand-patched to the new `main.c`. Decided by the user (2026-10-14:
"fresh scaffold"). The re-make is a step after this change's merge and
the toolkit push round, done outside any agent worktree (tasks 4.4).

### D12. Upstream

The template is upstream's file (sp00nznet/xboxrecomp `templates/new-game`;
the fork's delta at 38717b2 is 33 lines in `main.c` and 6 in
`recomp_manual.c`, from the `recomp_env` wiring, the APU route through
`xbox_VehMmioFault` and `<stddef.h>`). The two-host template is a natural
part of PR 5 in `cat/analysis/upstream/pr-stack-plan.md` ("Devices on
POSIX hosts": the SIGBUS dispatcher, the SDL window), since it is the
file that shows a title how to use them, and it follows that plan's
binding decisions: plain `getenv` in the PR version (the fork's
`recomp_env` calls are fork-only), no title text, tested on Burnout 3,
and named hosts (native Windows, Proton, macOS/Metal). This spec only
notes that; the PR is cut when PR 5 is, from the merged template, and
nothing here is shaped for upstream at the fork's expense.

## Risks

- **A scaffold against an old toolkit.** `new` resolves the toolkit pin
  from a checkout beside the game or the fork's branch head
  (`resolve_toolkit_commit`); until the toolkit round that carries this
  template is pushed, a public `xbr new` writes both targets and copies
  the Win32-only template. D9's note covers it, and the push order in
  tasks 6 (toolkit before the CLI release) closes it.
- **The handler's known gaps** (cat 631-636, b3 580-584): `vsnprintf` and
  `dladdr` are not async-signal-safe, and Darwin allocates `__thread`
  storage lazily. Accepted for a bring-up tool by both games; the
  Windows VEH has the same exposure with `fprintf`.
- **The Metal default surprises a CPU-backend user.** Only on Apple, only
  when unset, and `cpu` is one variable away; the same decision has
  stood for b3 since 2026-10-09.
- **Spartan faults early on the Mac for a title reason** (D6's KEVENT, a
  lifted-code bug). Criterion 2 counts a correctly reported fault as a
  pass; the fault itself is handed to the Spartan port with the report.
- **`_IONBF` on a redirected log under Proton** costs a `write` per line
  (async-log-writer's context). The template did `_IONBF` already; the
  only new cost is that the lines now reach a file. Unchanged
  elsewhere.
