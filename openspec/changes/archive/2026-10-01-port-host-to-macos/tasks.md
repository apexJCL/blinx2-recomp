## 1. Build system

- [x] 1.1 In `CMakeLists.txt`:
  - move the `d3d11 dxgi dxguid xinput winmm dbghelp` link list under `if(WIN32)`
  - keep `/LARGEADDRESSAWARE` and `/bigobj` under `if(MSVC)`
  - add a comment on why the OpenSSL `find_package` hoist exists

  Verify that `rm -rf build && cmake -S . -B build` succeeds on macOS with no "target was not found" error, and that `build/CMakeFiles/cat_recomp.dir/link.txt` has no Windows library and neither `-export_dynamic` nor `-Wl,-x`.
- [x] 1.2 Add the `CAT_GEN_OPT` cache variable (default empty). When set, it adds per-source `COMPILE_OPTIONS` to `RECOMP_GEN_SOURCES`. Verify that configuring with `-DCAT_GEN_OPT=-O1` puts `-O1` on a `recomp_0000.c` compile line (`make -n` / `VERBOSE=1`), and that an empty value adds nothing.

## 2. Host seams in main.c

- [x] 2.1 Move `#include <windows.h>` and `<dbghelp.h>` behind `#if defined(_WIN32)`. Off Windows, the NT types come from `kernel.h` through `<xbox/xboxrecomp.h>`. Verify that `main.c` compiles on macOS past the include section (remaining errors only in code that later tasks replace).
- [x] 2.2 Extract the shared `report_fault(void *host_pc, uintptr_t data_addr, int access)` from the current VEH. It prints the `[CRASH]` line, guest VA, registers, symbol line and guest context, using today's order and labels, with `access` = read/write/unknown. Verify by reading the diff that the Windows VEH now only decodes the exception record and calls it.
- [x] 2.3 Range-check the guest stack scan in `print_guest_context` (design Decision 6). Scan only when `XBOX_BASE_ADDRESS <= g_esp && g_esp + 1024 <= g_xbox_total_ram`; otherwise print `(no return addresses in range)` with an `esp outside guest RAM` note, followed by the ICALL ring, and skip the raw dump. Verify with a temporary debug call to `report_fault` after setting `g_esp = 0xFFFFFFF0` on macOS: it prints the note and doesn't fault. Remove the debug call afterwards.
- [x] 2.4 Add `host_symbol_for()`, using `SymFromAddr` on Windows and `dladdr` elsewhere, and printing `in <name>+0x<off>` or `in <unknown>`. Verify on macOS with a temporary debug call that resolves `&sub_00012000` to `sub_00012000+0x0`, without any export flag. Remove the debug call afterwards.
- [x] 2.5 Add `host_report_fatal(step, detail)`. On all hosts it writes `[FATAL] <step>: <detail>` to stderr; on Windows it also shows the existing `MessageBoxA`. Replace the two existing dialogs with calls to it. Verify on macOS that running from `/tmp` prints the attempted `game_files/default.xbe` path and exits with status 1 (`echo $?`).
- [x] 2.6 Make the entry point `main` on all hosts, with the boot sequence in a shared `host_main()`. Keep `WinMain` and the `SymInitialize`/`GetModuleHandle`/`GetCommandLineA`/`SW_SHOW` uses inside `#if defined(_WIN32)`. Verify on macOS that `nm build/cat_recomp | grep -iE 'winmain|GetModuleHandle|GetCommandLine|Sym(Init|FromAddr)'` is empty.

## 3. POSIX crash handler

- [x] 3.1 Implement `host_install_crash_handler()` for POSIX:
  - `sigaction` for `SIGBUS` and `SIGSEGV`, with `SA_SIGINFO | SA_ONSTACK | SA_NODEFER`
  - a `SIGSTKSZ`-sized `sigaltstack` on the boot thread
  - a `volatile sig_atomic_t` re-entry guard
  - restore `SIG_DFL` and return after reporting

  Include `<signal.h>` only, not `<ucontext.h>`. Verify by reading the code against design Decision 2.
- [x] 3.2 Implement `host_fault_pc()` and read/write detection for arm64 Darwin:
  - the PC from `uc_mcontext->__ss.__pc`
  - WnR (ESR bit 6) trusted only when `ESR >> 26` is `0x24` or `0x25`
  - fallbacks for x86_64 Darwin and Linux that compile without `#error` and report `unknown` access

  Verify that it compiles on macOS arm64 with no warnings from these functions.
- [x] 3.3 Write the POSIX report through `snprintf` into a stack buffer plus `write(2, …)`. Then append a native frame list of up to 16 frames, walked from `__ss.__pc`, `__ss.__lr` and the `__ss.__fp` chain, with `host_symbol_for` on each (design Decision 5; not `backtrace()`). Verify the output format in 4.2: the first native frame is the faulting function.

## 4. Build and boot on macOS

- [x] 4.1 Run `scripts/pipeline.sh build` on macOS arm64. Record wall-clock time and peak memory in this task. If the build is impractical at the default optimization level, rebuild with `-DCAT_GEN_OPT=-O1` and record that as well. Verify that `file build/cat_recomp` reports `Mach-O 64-bit executable arm64`.
- [x] 4.2 Run `build/cat_recomp 2>stderr.txt` from the project root. Verify that the boot banner reaches `Starting game...`. After that, the run either returns cleanly or faults with a complete report as defined in specs/host-crash-diagnostics:
  - a `[CRASH]` line
  - the guest VA and registers
  - an `in sub_…+0x…` line
  - a guest chain or the "no return addresses" fallback
  - a signal exit status (`echo $?` > 128)

  Result: the banner reaches `Starting game...`, then the title returns cleanly through `HalReturnToFirmware(routine=2)` (exit 0, no fault). The report format was checked with forced faults instead (`analysis/port/selftest-null.txt`): `[CRASH] … PC=… (write)`, guest VA, registers, `in <symbol>+0x…`, the no-return-addresses fallback, the ICALL ring, raw dump, native frames, and exit 139.

  Result (2026-10-01): full build at the default `-O3` took 266 s wall-clock on 14 cores, with about 9.9 GB peak compiler memory. `CAT_GEN_OPT` wasn't needed. The output is `Mach-O 64-bit executable arm64`, 111 MB.

  Run it outside lldb. Under lldb the first `EXC_BAD_ACCESS` stops before the handler, so `continue` once.
- [x] 4.3 Check the boot-thread `sigaltstack` with a forced guest fault: a temporary `recomp_manual.c` override that recurses without bound. It must not be a tail call (a `volatile` local or array is touched after the recursive call), since `-O3` turns tail self-recursion into a loop. Verify that a report is still printed and the process exits by signal, then remove the override.
- [x] 4.4 Check MMIO configuration (design Decision 4). Define `HOST_CAN_SERVICE_MMIO` (1 only for `_WIN32 && _M_X64`). When it's 0 and `RECOMP_AC97_READY` is set:
  - print the `[BOOT] … unsupported on this host … ignored` line
  - `unsetenv` it before `xbox_MemoryLayoutInit`
  - skip `mcpx_apu_init_standalone`

  Result: the report printed with 16 native frames, all `cat_selftest_recurse`, and the process exited by signal (139). This test found that the duplicate-`lr` skip in the frame walk was swallowing every recursive frame; it now skips only the first record.

  Verify on macOS that `RECOMP_AC97_READY=1 build/cat_recomp` prints the line and does not print `[BOOT] emulated APU`.
- [x] 4.5 Record what the first real run showed (fault site; whether there was an AppKit main-thread assertion) in design.md's Open Questions, as input for the next change.

## 5. Follow-ups (outside this change, track only)

- [x] 5.1 Draft the upstream issues; filing is postponed. Drafts are in `analysis/upstream/` (see its README.md):
  - 01: `xbox_memory_layout.c` VEH bodies don't build off Windows (the local patch)
  - 02: POSIX names missing from the reserved lists (`merge_names.py`, `lifter.py`)
  - 03: guest threads have no `sigaltstack` (`kernel_bridge.c` `bridge_thread_main`)
  - 04: template portability nits

  Policy: we fix these in the toolkit only if the game can't progress otherwise, and then on a `posix-host/portability` branch in the clone. Record issue/PR links here if they're ever filed.

## 6. Windows

Moved to its own change, `verify-windows-host`, which is postponed indefinitely.
