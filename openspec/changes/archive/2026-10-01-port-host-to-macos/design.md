## Context

See proposal.md for motivation and specs/ for the requirements. This section covers only the facts about the current code that shape the approach.

- `src/main.c` is the toolkit template, filled in for this title (it differs from the template only in title constants). Its boot sequence is already platform-neutral; the Windows-only parts sit at the edges:
  - the `<windows.h>`/`<dbghelp.h>` includes
  - `WinMain`, plus a `main` that calls it through `GetModuleHandle`/`GetCommandLineA`/`SW_SHOW`
  - the vectored exception handler (VEH) with dbghelp `SymSetOptions`/`SymInitialize`/`SymFromAddr`
  - the `0x140000000` native-stack heuristic
  - `MessageBoxA`

  None of the `GetModuleHandle`/`GetCommandLineA`/`SW_SHOW`/`Sym*` names exist off Windows.
- **The toolkit's POSIX compatibility layer** (`../xboxrecomp/src/platform/win32_compat.*`, `xbox_winnt.h`):
  - It provides the NT vocabulary through `kernel.h` (`WINAPI`, `CALLBACK`, `BOOL`, `LONG`, `HINSTANCE`, and `PCONTEXT` as `void *`).
  - It provides `MessageBoxA`, printing `[caption] text` to stderr.
  - Its `AddVectoredExceptionHandler` is a no-op stub returning NULL (`win32_compat.c:1915`), and it defines `PEXCEPTION_POINTERS` as an opaque `void *`.
  - No toolkit code installs signal handlers. The AC'97 and `RECOMP_WATCH` traps disarm themselves on POSIX when that registration returns NULL, so nothing in the toolkit competes with, or relies on, the handler added here.
- **Hardware-register (MMIO) servicing needs an x86-64 host.** `apu_hook_handle_mmio` and `mmio_decode.h` are `_WIN32`-only and decode and step over the *host* faulting instruction as x86-64. On arm64 the faulting instruction is A64.
  - `xbox_MemoryLayoutInit` reads `RECOMP_AC97_READY` itself (`xbox_memory_layout.c:2387`) and marks the APU page `PROT_NONE` regardless of whether a handler exists. It's the only other reader of that variable.
- **Guest memory is reserved `PROT_NONE`** (`VirtualAlloc(MEM_RESERVE, PAGE_NOACCESS)` → `mmap`). On macOS, a fault on a mapped-but-inaccessible page is `SIGBUS`; only truly unmapped addresses give `SIGSEGV`. So most guest faults will arrive as `SIGBUS` (verified on this machine).
- **Guest threads start in toolkit code.** Every guest thread runs `bridge_thread_main` (`kernel_bridge.c:470-497`) through `thread_trampoline`, with nothing this project can hook. `CreateThread(NULL, 0, …)` gives the 512 KB macOS default pthread stack, smaller than the 1 MB Windows default.
- **Guest registers are thread-local.** `g_eax`… are `RECOMP_TLS` (`__thread` on Clang), so a handler running on the faulting thread sees that thread's values.
- **Generated functions are external symbols** (`void sub_XXXXXXXX(void)`). Some carry Ghidra-recovered CRT names.

## Goals / Non-Goals

**Goals:**
- Get a macOS arm64 binary that boots to the guest entry point and crashes informatively. This is the priority; Windows is deferred.
- Keep one `main.c` with a single boot path. Platform code goes behind a small set of host functions, so the template's comments and the Step 8 debugging guidance still match the file.
- Make the POSIX crash report use the same fields, labels and order as the Windows one.
- Change nothing in `../xboxrecomp`.

**Non-Goals:**
- Verifying Windows. The Windows code paths are kept by moving them unchanged; checking them is the last, deferred task group.
- Fixing the toolkit's `AddVectoredExceptionHandler` stub. A general signal-to-VEH bridge belongs upstream and needs arch-specific context translation that doesn't exist.
- Alternate signal stacks on guest-created threads. That needs a toolkit change in `bridge_thread_main` (see Risks).

## Decisions

### 1. Platform seams inside `main.c` rather than a separate `host_posix.c`
Platform-specific code goes into a few `static` functions in `main.c`, each with a `#if defined(_WIN32)` / `#else` body:
- `host_install_crash_handler()`
- `host_symbol_for(void *pc, char *out, size_t n)`
- `host_report_fatal(const char *step, const char *detail)`

The Windows-only includes move behind `#if defined(_WIN32)`. Off Windows, the NT types come from `kernel.h`, which `main.c` already reaches through `<xbox/xboxrecomp.h>`. The guest-context printing (registers, symbol line, guest chain, ICALL ring, raw stack) moves out of the VEH into a shared `report_fault(...)`, which both handlers call with the host PC, data address and read/write flag. That one shared function is what keeps the reports identical across hosts.

- *Alternative: a separate `host_posix.c` / `host_win32.c` pair.* Cleaner on paper, but it splits the file the toolkit docs tell users to customize ("add game-specific diagnostics here"). Game-specific dumps would then have to be added twice.
- *Alternative: implement the VEH stub upstream via sigaction.* Rejected for this change (non-goal). `EXCEPTION_POINTERS` consumers in the toolkit assume an x86-64 `CONTEXT`.

### 2. POSIX crash handler: `sigaction` with `SA_SIGINFO | SA_ONSTACK | SA_NODEFER`, then re-raise
- **What's handled:** `SIGBUS` (the common case, see Context) and `SIGSEGV`.
- **Headers:** `<signal.h>` only. `<ucontext.h>` `#error`s on Darwin without `_XOPEN_SOURCE`, and `ucontext_t` and `mcontext` are already reachable through `<signal.h>`.
- **Fault details:**
  - Data address: `si_addr`.
  - Host PC: `uc->uc_mcontext->__ss.__pc` on arm64 Darwin (`uc_mcontext` is a pointer), behind a `host_fault_pc()` helper. x86_64 Darwin and Linux fallbacks compile, but neither is a target.
  - Read/write: from `__es.__esr`. Read the WnR bit (bit 6) only when the exception class (`ESR >> 26`) is `0x24` or `0x25` (data abort); otherwise report `unknown`. Verified on this machine: ESR `0x92000046` for a write.
- **Exiting:**
  - After reporting, the handler restores `SIG_DFL` and returns. The faulting instruction re-executes and the process dies by the original signal (verified: exit 138/139).
  - A `volatile sig_atomic_t` re-entry flag makes a nested fault restore `SIG_DFL` and return immediately. `SA_NODEFER` lets a same-signal fault inside the handler reach that guard instead of being force-killed by the kernel.
- **Alternate stack:** `SIGSTKSZ` (128 KB on Darwin), installed on the boot thread before guest code runs. 64 KB is too tight for `snprintf` + `dladdr` per frame.
- **Output:** `snprintf` into a stack buffer, then `write(2, …)`, avoiding stdio locks the faulting thread may hold.
- **Known async-signal-safety gaps, accepted for a bring-up tool:**
  - `snprintf` isn't formally async-signal-safe (it doesn't allocate for these formats on Darwin).
  - `dladdr` takes dyld's lock.
  - Darwin allocates `__thread` storage lazily, so a fault on a thread that never touched guest registers (SDL, watchdog) could `malloc` inside the handler.

  The Windows VEH has comparable exposure with `fprintf`.

- *Alternative: a Mach exception port (`EXC_BAD_ACCESS`) on a dedicated thread.* It works on every thread regardless of stack state. Rejected: the handler would run on another thread and couldn't read the faulting thread's `__thread` guest registers.

### 3. Symbol lookup: `dladdr` against the unstripped symbol table
On macOS, `dladdr` resolves addresses through the executable's nlist symbol table, not just exported symbols. Verified on this machine: global functions, static functions and pc+offset all resolve without `-export_dynamic`; only `strip -x` or `-Wl,-x` breaks static lookups. So no export flag is needed. The requirement is that the binary isn't stripped, which CMake's default Release build satisfies. `host_symbol_for` formats `dli_sname` (already without the leading underscore) plus `pc - dli_saddr`, or `<unknown>`.

- *Alternative: `ENABLE_EXPORTS` / `-export_dynamic`.* Unnecessary (verified), and it would export about 22,000 symbols for nothing.
- *Alternative: run `atos` when a crash happens.* That needs `fork`/`exec` in a signal handler, and it's slow. Rejected.

### 4. MMIO-dependent configuration is ignored with a message on hosts that can't decode the faulting instruction
A compile-time `HOST_CAN_SERVICE_MMIO` is `1` only for `_WIN32 && _M_X64`. When it's `0` and `RECOMP_AC97_READY` is set, `main.c`:
- prints `[BOOT] RECOMP_AC97_READY is unsupported on this host (needs x86-64 fault decoding); ignored`
- calls `unsetenv("RECOMP_AC97_READY")` **before** `xbox_MemoryLayoutInit`. That's required, not cosmetic: init would otherwise mark the APU page `PROT_NONE` with nothing to service the faults.
- skips `mcpx_apu_init_standalone`

- *Alternative: refuse to start.* Rejected. Ignoring the setting gets the user further, and the spec allows either.

### 5. Native stack on POSIX: walk the arm64 frame-pointer chain
The Windows `0x140000000` scan doesn't apply to macOS. Apple's arm64 ABI requires frame pointers, so the handler walks the chain from the signal context: first `__ss.__pc`, then `__ss.__lr`, then `[fp+8]` for each frame record `fp → [fp]`. It stops after 16 frames, at a null or misaligned `fp`, or when `fp` stops increasing. Each frame is named with `host_symbol_for`. This is async-signal-safe apart from `dladdr`, and unlike `backtrace()` it never drops the faulting leaf frame (verified that `backtrace()` drops it). The Windows block stays as it is.

### 6. Guest stack scan is range-checked before reading
`print_guest_context` reads up to 256 words from `g_esp`. With a garbage `esp`, or one within 1 KB of the guest RAM window's edge, the scan itself would fault in the middle of the report. The scan therefore runs only when `XBOX_BASE_ADDRESS <= g_esp` and `g_esp + 1024 <= g_xbox_total_ram` (from `xbox_memory_layout.h`). Otherwise it takes the "(no return addresses in range)" path and skips the raw dump, saying `esp outside guest RAM`. This applies on both hosts, since the shared `report_fault` owns it.

### 7. CMake: platform branches in this project only
- **Windows libraries:** the `d3d11 dxgi dxguid xinput winmm dbghelp` link list moves under `if(WIN32)`. `/LARGEADDRESSAWARE` and `/bigobj` stay under `if(MSVC)`.
- **`WIN32` keyword:** stays on `add_executable`. CMake ignores it off Windows (verified: a plain console `cat_recomp` is produced).
- **OpenSSL:** the `find_package(OpenSSL)` hoist stays, with a comment. It's what makes clean configures work.
- **Optimization level:** Release stays the default, with a `CAT_GEN_OPT` cache variable (default empty) that sets per-source `COMPILE_OPTIONS` on `src/recomp/gen/*.c`. It's the escape hatch if `-O3` over 787 MB is impractical.

## Risks / Trade-offs

- **[Risk] Building 787 MB of generated C at `-O3` with Clang may take a very long time or a lot of memory.** → `--split 250` keeps files around 9 MB. Cap `-j` if memory runs short; `CAT_GEN_OPT=-O1` is the fallback. The first build is measured and recorded in tasks.md.
- **[Risk] A stack overflow on a guest-created thread dies without a report.** Their 512 KB stacks make this likelier than on Windows. → The spec allows it, and the process still exits by signal. Follow-up: propose a per-thread `sigaltstack` (and optionally a larger stack) in `bridge_thread_main` upstream.
- **[Risk] The SDL window is created on whichever thread calls `CreateDevice`.** AppKit requires the main thread. → The boot thread is the main thread and runs `xbe_entry_point`. If BLiNX 2 creates its device from a worker thread, SDL will abort with an AppKit assertion, and a separate change will marshal window work to the main thread.
- **[Risk] Under lldb, `EXC_BAD_ACCESS` stops the process before the handler runs.** → Expected; `continue` delivers the signal to the handler. This is noted in the tasks so it isn't mistaken for the handler failing.
- **[Trade-off] Windows isn't verified by this change's macOS tasks.** → Windows statements are only moved, never edited. Checking that is the final, deferred task group, together with an MSVC build when a Windows machine is available.

## Migration Plan

No migration is needed: this is a development host, with no deployed users or data. Rollback means reverting `src/main.c` and `CMakeLists.txt` to the template-derived versions in git.

## Open Questions

- Whether BLiNX 2 creates its D3D device on the boot thread. Still open: the first macOS run exits before any D3D or window call (see below), so there was no AppKit main-thread assertion to observe.

### First macOS run (2026-10-01), input for the next change

- No fault. After `Starting game...` the title spawns one system thread and makes 2 memory allocations. It opens files (`NtCreateFile` returns success), then loops through about 340 string-compare kernel calls (ordinals 289/279, `RtlInitAnsiString`/`RtlEqualString`).
- It then writes launch data for its own title ID (`type=1 titleid=0x4D530065 path=''`) and calls `HalReturnToFirmware(routine=2)`. The title is asking to be relaunched, and the empty launch path looks like the thing to investigate. Exit status 0.
- The run looks the same before and after the libc-name fix, so that fix is not what's stopping the title from going further.
- No graphics, input or audio initialization happens before the exit.

## Implementation Notes

Found while applying this change, beyond what the decisions above anticipated:

- **Recovered names can shadow the host libc.** Ghidra names five CRT routines `write`, `read`, `close`, `lseek` and `isatty`. On macOS a global function with one of those names in the executable replaces libc's for every caller in the binary, so the crash reporter's `write(2, …)` and the toolkit's file I/O both ran guest code. `merge_names.py` reserves ISO C names only. `scripts/host_reserved_names.py`, run by `pipeline.sh names`, now renames any applied name that the host libc exports to `<name>_<ADDR>`. This should go upstream with the other follow-ups.
- **`src/recomp_manual.c` needed one include** (`<stddef.h>` for `ptrdiff_t`, which `<windows.h>` used to supply). The proposal said this file would not be touched. Its `extern uint32_t g_eax;` example also lacks `RECOMP_TLS`. That line is only used in comments, so it was left as is.
- **`main.c` declares `recomp_dispatch_init`.** Clang rejects the template's implicit declaration.
- **The `[CRASH]` register label is `PC` on arm64 and `RIP` elsewhere.** The rest of the report format is unchanged.
- **Guest page 0 is mapped read/write** by the toolkit's memory layout, so a guest NULL dereference does not fault. Forced-fault tests use the top of the 4 GB guest window instead.
- **The native frame walk had to handle recursion.** Recursive frames share a return address, so the duplicate-`lr` skip now fires only on the first frame record (found by task 4.3).
- **"Xbox VA of fault" is printed only when the address is inside the guest's 4 GB window.** Otherwise it says `(host address, outside guest memory)`. This changes the shared report on Windows too, and should be noted for 6.1.
- **lldb isn't usable on this binary.** The Xcode lldb crashed, and the CommandLineTools lldb hangs for more than 2 minutes loading the 111 MB executable. The `.ips` crash reports in `~/Library/Logs/DiagnosticReports/` give symbolized stacks instead.
