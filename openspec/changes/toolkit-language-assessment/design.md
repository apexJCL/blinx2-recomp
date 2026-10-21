## Context

The xboxrecomp toolkit is our fork of sp00nznet/xboxrecomp (MIT), integration branch `posix-host/portability` (tip `4559bae9` on 2026-10-21, 1,319 commits since 2026-03-06). It is written in C11, with Objective-C for the Metal backend. The recompiler that turns an XBE into C is Python (`tools/recomp`, `tools/disasm`). The game-agnostic CLI `xbr` is Python and the player's build wizard is Go.

The user asked (2026-10-21) whether the toolkit should move to modern C or C++ (C23, C++20/23) or to Rust. The aim is preservation through a faithful migration, plus comfort enhancements. A reference implementation and a standard for Xbox static recompilation counts for a lot. Giving back to upstream counts for little.

All numbers below were measured for this spike on the Mac (M4 Max, 14 cores, Apple clang 21.0.0, `DEVELOPER_DIR=/Library/Developer/CommandLineTools`). Rust numbers use rustc 1.99.1, installed for the probe only into `runs/toolkit-language/rust/` and deleted after it. Nothing was changed in a main checkout.

## Goals / Non-Goals

**Goals**
- Measure what a language change would touch: the runtime, the generated code, the tests and the tools.
- Cost each option in agent-days and say what it buys against the project's real bug history.
- Recommend one path, with its first slice and its gates, and say what would change the answer.

**Non-Goals**
- Any migration work. This change is a report.
- The recompiler's own language. `tools/recomp` stays Python (CLAUDE.md: Python 3 stdlib-first). Only the language it emits is in scope.
- The CLI (Python) and the wizard (Go). Both follow their own rules in CLAUDE.md and are not affected by the choice.

## Inventory of today

### Toolkit size per subsystem

Line counts on `posix-host/portability` at `4559bae9`. Files in `src/kernel` that belong to the renderer are counted under the renderer.

| Subsystem | Where | Lines | Notes |
|---|---|---|---|
| Kernel / HLE | `src/kernel` (without the `nv2a_*` files) | 30,800 | `kernel_bridge.c` 11.4k, `xbox_memory_layout.c` 5.6k, HAL, files, threads, sync, scheduler, pacing |
| NV2A pushbuffer executor and CPU rasteriser | `src/kernel/nv2a_*` | 14,500 | `nv2a_pb_exec.c` 7.5k, backend common 2.9k, combiner, VSH fixed function, texture packing |
| NV2A register emulation (from xemu) | `src/nv2a` | 4,900 | `nv2a_regs.h` is LGPL-2.1+ |
| D3D11 backend, D3D8 layer, HLSL and MSL generators | `src/d3d/*.c`, `*.h` | 17,000 | `nv2a_pb_d3d11.c` 4.3k, the D3D8 compatibility layer (Windows only) |
| Metal backend | `src/d3d/nv2a_pb_metal.m`, `src/video/fb_present_metal.m` | 3,900 | Objective-C |
| Presentation and video | `src/video` | 3,000 | SDL2 present, FMV player (includes the Metal presenter) |
| APU (MCPX, from xemu) | `src/apu` | 7,900 | LGPL-2.1+; VP, DSP stub, frame thread |
| DirectSound / XAudio2 | `src/audio` | 860 | |
| Input and USB | `src/input`, `src/usb` | 5,800 | OHCI, pads, keyboard and mouse, bindings |
| Enhancements | `src/enhance` | 2,860 | config, render scale, filters, mods, input actions |
| POSIX / Win32 host | `src/platform` | 5,200 | `win32_compat.c` maps the Win32 vocabulary onto POSIX |
| **Runtime total** | `src/` | **96,200** | C plus about 3,900 lines of Objective-C |
| Tests | `tests/` | 31,300 | about 85 ctests, some under ASan |
| Tools | `tools/` | 47,500 Python | recomp 23.5k, disasm 7.8k, conformance 4.5k (with a differential x86 fuzzer) |
| Runtime header for generated code | `templates/runtime/recomp_types.h` | 1,734 | copied into each game's `gen/` |

The CLI (`xboxrecomp-cli`, `main` `85e24c9`) is 53.6k lines of Python plus the 16.7k-line Go wizard.

### C idioms the runtime leans on

Counts over `src/` (`.c`, `.h`, `.m`):

- **Shared mutable state:** about 770 file-scope `static` variables and 270 `g_*` globals. The guest's registers are `__thread` globals (69 TLS sites).
- **Concurrency by hand:** 480 atomic sites (`__atomic_*`, `Interlocked*`, `_Atomic`), 259 lock sites (pthread mutexes, critical sections, SRW locks) and 36 thread creations. The kernel runs a console-like one-CPU guest scheduler with safe points, DPCs and ISRs.
- **Raw guest memory:** 301 `volatile` sites. Guest RAM is one mapping at a fixed offset (`g_xbox_mem_offset`), read and written through casts.
- **A Win32 vocabulary on POSIX:** `win32_compat.c` gives the kernel the same `HANDLE`, `CreateThread` and critical-section API on every host. 123 `_WIN32` or `__APPLE__` branches.
- **Other:** X-macro tables (222 rows, `recomp_env`), 71 function-pointer tables, 556 `memcpy`/`memset`, fault handlers (`sigaction` and vectored exceptions, 34 sites) and `setjmp`/`longjmp` for guest non-local jumps.

### Generated code

| Game | Lines | Size | Functions |
|---|---|---|---|
| BLiNX 2 (`cat/src/recomp/gen`) | 3,357,000 | 138 MB in 51 files | 11,750 |
| Burnout 3 | 1,881,000 | 67 MB in 29 files | |
| SSX 3 | 1,505,000 | 53 MB | 17,908 |
| Spartan | 1,507,000 | 53 MB | 18,091 |
| JSRF | 1,050,000 | 38 MB | 9,111 |

The lifter emits each x86 function as a `void(void)` C function:

- Control flow is labels and `goto`. One BLiNX 2 chunk (`recomp_0009.c`) holds 50,376 labels and 30,860 gotos across 250 functions, and its largest function has 1,939 basic blocks.
- Guest registers are TLS globals (`g_eax` ... `g_edi`, the x87 stack, MXCSR, the FPU control word). Arguments go on the simulated guest stack, and the return value comes back in `g_eax`.
- Every guest memory access is a `volatile` cast through `XBOX_PTR(addr)`, that is the address plus `g_xbox_mem_offset`. Constant MMIO addresses lift to `XBOX_MMIO_R/W`.
- x87 precision and rounding are modelled explicitly (`RECOMP_FP_PC`, `recomp_fp_round24`, MXCSR rounding).

**The coupling to the runtime is small and explicit.** Two BLiNX 2 chunks compiled to objects reference only these runtime symbols:

- the register and FPU globals;
- `g_xbox_mem_offset` and the code range;
- the indirect-call lookups (`recomp_lookup`, `_kernel`, `_manual`) and their trace counters;
- `xbox_GuestCpuPreempt`;
- libm.

Other functions from other chunks (`sub_*` and library-named ones such as `sprintf_002D4ED0`) are also referenced, but those are generated code too.

The rest of the contract is the 1,734-line `recomp_types.h`: about 95 globals and helpers, plus macros. That contract is documented in prose (`docs/technical/register-model.md`, `memory-layout.md`, `indirect-calls.md`, `seh-handling.md`), but not as a versioned interface with its own tests.

### Platforms and who compiles

- **Hosts:**
  - macOS arm64 (Metal), the main dev host;
  - Windows x86-64, cross-built with llvm-mingw from every host, Windows included;
  - Proton on the Steam Deck (the Windows build, D3D11);
  - Linux native;
  - iPadOS as a self-build only.
- **Toolchain pinning:** the CLI fetches CMake, Ninja, llvm-mingw and the toolkit at sha256-pinned versions. Builds are reproducible: two builds give the same sha256.
- **The player compiles the game.** Game code can't be distributed, so the wizard builds the generated code on the player's machine (about 15 GB free). So compile time, compiler memory and toolchain size are player-facing costs, not only developer costs.

## Measurements

Scripts, objects and logs are in `runs/toolkit-language/` (local only).

### M1. Real generated chunks: C11, C23 and C++20

Each chunk was compiled with the game's flags (`-O3 -DNDEBUG`, the cat include paths), once per language mode.

| Chunk | gnu11 | gnu23 | gnu++20 | `.text` (bytes) | `.text` sha, all three |
|---|---|---|---|---|---|
| `recomp_0005.c` (3.3 MB) | 3.3 s | 3.3 s | 3.5 s | 726,308 | identical |
| `recomp_0009.c` (15.8 MB) | 6.2 s | 6.2 s | 6.9 s | 973,588 | identical |
| All 49 BLiNX 2 files at `-j14` | 23 s wall | | 25 s wall | 42.65 MB vs 42.80 MB of objects | |

The generated code compiles unchanged as C23 and as C++20, and the machine code is byte-identical. The only differences are C++ name mangling, which an `extern "C"` block would remove, and +7-11% compile time. **Moving the runtime to C23 or C++ puts no golden at risk through the generated code.**

### M2. Rust with the same control flow (synthetic)

Rust has no `goto`, so a Rust emitter has to lower each function to a state machine. The usual shape is `loop { match block { ... } }`, which is also c2rust's fallback for irreducible flow.

`runs/toolkit-language/synth_cfg.py` keeps each real function's blocks, statement counts and goto edges. It swaps the statements for equal register and guest-memory operations (volatile reads and writes through the same offset) and emits both C and Rust. The two outputs differ only in language.

| Chunk (real CFG) | C `-O3` | Rust `opt-level=3` | Rust front end only (`--emit metadata`) | C `.text` | Rust `.text` |
|---|---|---|---|---|---|
| 0005 (10,397 blocks, largest 463) | 1.8 s | 2.7 s | 0.9 s | 271 KB | 647 KB (2.4x) |
| 0009 (50,376 blocks, largest 1,939) | 3.4 s | **19.6 s** | 15.8 s | 430 KB | **2,607 KB (6.1x)** |

- Rust's front end grows faster than linearly with function size: 0009 spends 15.8 s before code generation.
- Code size grows 2.4-6x. That is i-cache pressure in the hot loop of every game, and it threatens the 25% flips/s gate.
- A smarter structuring pass (a relooper) would shrink the gap. It would also be a new, hard compiler component, and irreducible guest flow still falls back to the state machine.
- The probe is synthetic, so the ratios are indicative, not exact. They all point the same way.

**Emitting Rust is the wrong target for the lifter. Any Rust option keeps the generated code in C, linked over the C ABI.**

### M3. The runtime as C23 and as C++20

Every portable toolkit file was compiled with `-fsyntax-only` in four ways. The base is the 84 `src/*.c` files left after removing the Windows-only backends by name (`win32`, `d3d11`, `dxgi`, `wgl`, `xinput`, `d3d8_gl`, `hlsl`, `dsound_device`, `xaudio`). 77 of them build; the other 7 are the D3D8 layer (`src/d3d/d3d8_*.c` minus the MSL and parse files), which needs Windows headers and fails on the Mac in every mode, C11 included. Logs: `runs/toolkit-language/langprobe/`.

| Mode | Result |
|---|---|
| gnu11, `-Wall -Wextra` (today's flags) | 76 warnings |
| `-std=c23` | **all 77 compile unchanged** |
| `-Wconversion -Wsign-conversion -Wshadow -Wcast-qual` | 2,179 warnings, 2,005 of them sign conversions (1,770 in `kernel_bridge.c`) |
| C++20 | 12 errors in 6 files: implicit `void*` conversions, one duplicate definition, three critical-section overloads |

Two of today's warnings point at real defects:

- `apu_shim.h:138` casts a `void *(*)(void *)` to `LPTHREAD_START_ROUTINE`, which is a call through the wrong function type. It warns 4 times.
- `nv2a_pb_replay.c:284` indexes 7455 into a one-element array on the POSIX build.

Both are the kind a warnings ratchet catches in any language.

## Bug history: what each option would have prevented

I classified the 1,319 toolkit commit messages by keyword, then read the APU fixes the brief names:

| Class | Commits | Examples | Prevented by Rust? | Prevented by C++? | Caught by C tooling? |
|---|---|---|---|---|---|
| Lifter semantics (x87, flags, MXCSR, decode) | ~40 x87/FP, ~10 flags/UB | `c50c597f` MXCSR rounding, `c7fa9c5c` SF from a compare, `a960b88e` rotate width | No | No | Differential fuzzing (it exists and found 7) |
| Guest concurrency and scheduling (IRQ, DPC, one-CPU gate) | ~16 | `37201d81`, `0988b9cf`, `0d61734e` | No: the race is in the guest's model | No | TSan partly; mostly by tracing |
| Races on guest RAM shared with host threads | several | `4a090834` APU `VOICE_OFF` lost: the title writes a voice word in guest RAM while the frame thread read-modify-writes it | No: guest RAM is raw bytes, so this is `unsafe` in Rust by nature | `std::atomic_ref` reads better, nothing more | TSan |
| Lock hold and contention (performance) | ~8 | `66587631` lock-free `VOICE_LOCK` | No | No | Profiling |
| Host lifetimes and leaks | ~7 | `8d0442be` directory searches freed on close, `9547d391` reservation leak, worker stacks | **Yes** | Mostly (RAII) | ASan/LSan |
| Bounds on host buffers | ~5 | `d628801f` inline vertex buffer overflow, `6b8c625b` unchecked guest buffers | Partly: host side yes, guest pointers no | Partly (`std::span`) | ASan, fuzzing |
| Uninitialised values | ~3 | `366c8c51` generated `ebp` local | Yes for the runtime; the generated case is C either way | Partly | `-Wuninitialized`, MSan, UBSan |

The defects that cost this project the most time live in the lifter's semantics and in the guest's concurrency model. They sit at the boundary between guest bytes and host code, where every language is unsafe. The classes Rust removes (host lifetimes, host bounds, uninitialised host data) are real but a minority. Sanitizers and fuzzing catch most of them in C, at a fraction of the cost.

## Options

Effort is in agent-days: one agent working one day, with gates. The ranges cover the five games' regression runs.

### (a) Stay on C, with targeted modernisation

The baseline moves to C17. C23 features (`nullptr`, `typeof`, `static_assert`, `[[nodiscard]]`, `constexpr` objects, `#embed`, fixed-width enums) come behind a feature check while one supported toolchain lacks them. The investment goes into:

- **The runtime contract:** a written, versioned specification of the interface between generated code and the runtime, with a conformance test suite (first slice, below).
- **Safety lanes:** ASan+UBSan and TSan ctest builds on the Mac, a `clang-tidy` and `scan-build` lane, and a warnings ratchet (new code clean under `-Wconversion`, existing counts may only fall).
- **Fuzzing:** libFuzzer harnesses for the parsers that take outside input: XBE, texture packs, `enhance` TOML, `kbm_script`, pushbuffer decode.
- **Thread-safety annotations:** Clang `-Wthread-safety` on the lock wrappers (APU frame lock, kernel locks), so the "who holds what" rules are checked at compile time.

| | |
|---|---|
| Effort | 10-14 agent-days for everything above, in slices; 0 days of freeze |
| Risk | Low. No game-visible change; goldens unchanged by construction (M1) |
| Pros | Zero migration cost. Generated code, xemu-derived LGPL files, nxdk and xemu all stay in one language. Every host toolchain already in the pins. The player's build is unchanged. The contract is useful whatever language a second implementation uses |
| Cons | No compiler-enforced memory safety. Discipline and tooling carry it. Contributors who want a modern language see C |

### (b) C++20/23

**(b1) Gradual.** The runtime compiles as C++ first (fix 12 portable errors plus the D3D8 COM layer, whose C `COBJMACROS` idiom differs in C++). Then selected subsystems move to idiomatic C++: RAII locks, `std::atomic_ref` on guest words, `std::span`, `metal-cpp` or Objective-C++ for Metal, plain C++ for D3D11.

**(b2) Full rewrite.** Everything is redone in idiomatic C++.

| | b1 gradual | b2 full |
|---|---|---|
| Effort | 4-6 agent-days to compile as C++; 50-80 more to make the kernel, the renderer and the APU idiomatic | 120-180 agent-days |
| Freeze | None for the first step; per subsystem, about a week of that subsystem's feature work | 3-5 months of toolkit features |
| Risk | Low to medium. Each subsystem move risks goldens (renderer, APU) | High |

- **Pros:**
  - RAII ends most host lifetime bugs.
  - D3D11 and Metal (`metal-cpp`) are native C++ APIs.
  - The large emulation codebases (Dolphin, RPCS3, Cxbx-Reloaded, gearmulator) and the recompilers I know of (N64Recomp's toolchain, XenonRecomp's runtime) are C++, so contributors from them can read it.
  - Generated code compiles identically (M1).
- **Cons:**
  - C++ is a large language. Without a style rule (no exceptions or RTTI in hot paths, a subset), readability for a reference implementation gets worse, not better.
  - It is not memory-safe either.
  - The xemu LGPL files and upstream are C.
  - The ABI contract still has to be C, so other implementations can use it.

### (c) Rust, full rewrite

The runtime is rewritten in Rust, and the generated code stays C over FFI (M2).

| | |
|---|---|
| Effort | 180-260 agent-days for ~96k lines: the kernel's HLE surface, both GPU backends, the APU, input, enhancements, the hosts and the tests. Plus 8-12 days of build plumbing (below) |
| Freeze | 4-8 months on toolkit features for all five games. No incremental golden comparison until large parts work together |
| Risk | Very high. The renderer and APU fidelity reached through hundreds of golden-checked fixes has to be re-earned |

- **Pros:**
  - Compiler-checked lifetimes and data races on host-owned state.
  - Cargo, `cargo test` and docs.
  - An attractive contributor story for newcomers.
  - The `windows-gnullvm` targets match the llvm-mingw cross-build. `objc2-metal`, `windows-rs` and `sdl3-sys` exist. iOS targets exist.
- **Cons:**
  - Most of the runtime handles raw guest memory, guest registers in TLS shared with generated C, fault handlers, `setjmp` across frames and MMIO hooks. That is `unsafe` Rust, which gives less safety than it seems and is harder to read than the C it replaces.
  - The bug classes that cost the most are not prevented (bug history above).
  - It adds a second compiler and the Rust standard library for every target to the player's build: about 455 MB for the minimal macOS toolchain alone, plus each target's std, all to pin and verify in the CLI and the wizard.
  - Reproducible double builds need new work.
  - The LGPL xemu files keep their licence when translated, and translating them loses the line-for-line diffability against xemu that the APU and NV2A work relies on.

### (d) Rust incrementally, per subsystem over a C ABI

Leaf subsystems move first (enhance config, input bindings, texture-pack loader), then the APU, then the renderer backends, then the kernel. Each crate exports a C ABI. CMake drives Cargo (Corrosion or a custom command). Generated code stays C.

| | |
|---|---|
| Effort | 8-12 agent-days of infrastructure (Cargo in CMake for the three hosts, llvm-mingw and gnullvm linking, iPadOS, reproducible builds, CLI and wizard toolchain pins, Proton check). Then per subsystem: leaves 8-12, APU 15-25, renderer backends 40-60, kernel 60-90. Total 130-200 agent-days over a long period |
| Freeze | None globally. Each subsystem's feature work pauses while it moves |
| Risk | Medium per slice, high in sum. A permanent two-language boundary |

- **Pros:**
  - It can stop at any slice.
  - Leaves that take untrusted input (mod and texture packs, TOML, the planned upscaler server) gain the most.
  - It is the honest Rust path if one is wanted.
- **Cons:**
  - All of (c)'s toolchain cost, from the first slice on.
  - The FFI boundary sits exactly where the shared state is (guest RAM, the scheduler, the frame lock), so most crates would be `unsafe`-heavy shims.
  - Two languages for every contributor to know.
  - The leaves it starts with are the code with the fewest bugs.

### (e) Others

- **Zig:** Zig's language is pre-1.0 and changes between releases, its contributor pool is small, and Metal and D3D11 bindings would be ours to keep. `zig cc` as a cross-compiler only would duplicate llvm-mingw, which already works. Not competitive.
- **C plus a small C++ island:** valid as part of (a). A third-party C++ component (for example a DSP56300 core) sits behind a C header. CMake enables `CXX` for that target only, and llvm-mingw and Apple clang already carry libc++. Licences, checked on GitHub on 2026-10-21:
  - gearmulator's DSP56300 core (`dsp56300/dsp56300` at bf222a32c2, used by gearmulator at b8e1a28d4e) is GPL-3.0: the repository's `LICENSE.md` is the GPL-3.0 text. The source files carry no headers, so whether "or later" applies is unverified.
  - xemu's DSP56300 core is GPL-2.0-or-later, not LGPL. `hw/xbox/mcpx/apu/dsp/dsp.c`, `dsp_c.c`, `dsp_jit.c` and `interp/dsp_cpu.c` (xemu at bf817de2b0) are "Adapted from Hatari DSP M56001 emulation, (C) ARAnyM developer team" under the GPL, version 2 or later. Only the MCPX glue `gp_ep.c` is LGPL-2.1-or-later, like the APU files we already carry.

  Either core is acceptable under the licence decision below (Decisions, 2).

## Criteria matrix

Ratings: ++ strong, + good, 0 neutral, - weak, -- poor.

| Criterion | (a) C + tooling | (b1) C++ gradual | (b2) C++ full | (c) Rust full | (d) Rust per subsystem |
|---|---|---|---|---|---|
| Faithfulness: goldens stay bit-identical | ++ nothing game-visible moves | + per-subsystem golden gates | - | -- months without comparable goldens | - per slice |
| Memory safety, host state | 0 sanitizers + fuzzing | + RAII | + | ++ (outside `unsafe`) | + in moved crates |
| Thread safety, host state | + TSan + `-Wthread-safety` | + | + | ++ | + |
| The bug classes that dominate (lifter, guest concurrency, guest RAM) | 0 (fuzzing, tracing) | 0 | 0 | 0 | 0 |
| Performance, generated code | ++ | ++ identical (M1) | ++ | ++ if it stays C; -- if emitted as Rust (M2) | ++ (stays C) |
| Performance, runtime | ++ | + | + | + | + (FFI calls at hot boundaries) |
| Platforms (llvm-mingw, Metal, D3D11, SDL3, iPadOS, Proton) | ++ all pinned today | ++ | ++ | + new toolchain and targets | + same, from slice 1 |
| Build time and the player's toolchain | ++ | + (+7-11%) | + | - second toolchain, ~0.5-1 GB | - |
| Reference implementation: readable, specified, tested | + once the contract exists | + | 0 (large language) | + | - (two languages) |
| Ecosystem (xemu, nxdk, upstream) and licensing | ++ same language as xemu and nxdk | + | 0 | - LGPL files rewritten, diffability lost | 0 |
| Effect on the roadmap (DSP, SDL3, overlay, release) | ++ none | + | -- | -- | - |
| Freeze cost | ++ none | + small | -- | -- | - |
| Effort (agent-days) | 10-14 | 4-6, then 50-80 | 120-180 | 190-270 | 130-200 |

## The reference-implementation goal

A standard for Xbox static recompilation is not mainly about the runtime's implementation language. It is about three things other people can rely on:

1. **The runtime contract.** It is what generated code may assume and what a runtime must provide: register and FPU state, the guest stack, memory access and MMIO, indirect calls, SEH and `setjmp`, the scheduler's safe points, and the kernel import table. Today it is a header plus prose spread across `docs/technical/`. Written down with a version, and checked by conformance tests that any runtime can run, it lets a second runtime (in Rust, C++ or anything else) or a second lifter interoperate. That is what a standard is. The contract must be a C ABI in any option, because C is the only ABI every language can call and implement.
2. **Conformance and differential tests.** `tools/conformance` already compares the lifter with an independent x86 core. Generalised, it becomes the test suite of the standard.
3. **Readable, explained code.** The toolkit's comments already say why the hardware or the game behaves as it does. A rewrite would reset that.

Option (a) puts the effort on 1 and 2 directly. Options (b) to (d) spend most of their effort re-expressing code that already works, and still need 1 and 2 afterwards.

## Effect on the current roadmap

- **The tracker item (in flight) and the tracker item follow-ups:** unaffected by (a).
- **APU DSP:**
  - If it adopts a C++ DSP56300 core, (a) takes it as a C++ island behind a C header, which costs about 1 agent-day of build plumbing.
  - Licence: xemu's C core (GPL-2.0-or-later) and gearmulator's core (GPL-3.0) are both acceptable (Decisions, 2). Either makes any distributed binary that links it GPL as a whole, and that has to be stated.
  - Under (c) or (d) the core would sit behind two FFI layers.
- **SDL3:** C is SDL3's native API. Unaffected by (a). Under (c) or (d) the SDL3 work would be done twice, or wait.
- **Overlay (the tracker item..292):** C plus the existing backends; unaffected by (a).
- **Release round:** unaffected by (a). Any rewrite pushes the first public release back by months.
- **Five games:** (a) needs no per-game work. Every other option needs each game's glue (`recomp_manual.c`, the game hooks) and goldens re-checked per slice.

## Recommendation

**Stay on C. Move the baseline to C17 with selected C23 features, and spend the effort on the runtime contract, the safety lanes and fuzzing (option a).** Allow small C++ islands behind C headers where a third-party component calls for it. Don't migrate to C++ or Rust now.

Reasoning:

1. **The pristine guarantee is safest when nothing game-visible moves.** M1 shows that even a language-mode switch leaves the generated machine code byte-identical. A rewrite of the renderer or the APU would have to re-earn hundreds of golden-checked fixes.
2. **The bugs that matter are not the ones a new language prevents.** The costly classes are lifter semantics, the guest's concurrency model and races on guest RAM. They live where every language is unsafe. The host-side classes Rust and RAII remove are a minority, and ASan, UBSan, TSan, `-Wthread-safety` and fuzzing catch most of them in C.
3. **The generated code must stay C anyway.** Emitting Rust costs 1.5-6x compile time and 2.4-6x code size on real control flow (M2), and the player pays that compile on their own machine. So any Rust option adds a permanent C/Rust boundary at the busiest interface.
4. **The reference-implementation goal is met by a specified contract and conformance tests,** which any language can implement. Writing them is cheaper and more durable than rewriting the runtime.
5. **No freeze.** The roadmap (SDL3, the release, the overlay) goes on. The slices wait behind it (Decisions, 1).

### Roadmap

1. **Slice 1: the runtime contract (spec plus tests),** 5-6 agent-days, published as a standalone document (Decisions, 3). See `tasks.md`.
2. **Slice 2: safety lanes,** 3-4 agent-days: ASan+UBSan and TSan ctest builds, `clang-tidy` and `scan-build`, `-Wthread-safety` on the APU and kernel lock wrappers, a warnings ratchet, and the two defects from M3.
3. **Slice 3: fuzzing,** 2-3 agent-days. libFuzzer harnesses for XBE, texture packs, enhance TOML, `kbm_script` and pushbuffer decode, run in CI for a bounded time.
4. **Slice 4: language baseline,** 1 agent-day. `CMAKE_C_STANDARD 17`, with C23 features behind a `XBR_C23` check, enabled once Apple clang, llvm-mingw clang and the Linux GCC/clang all build `-std=c23` (the probe shows Apple clang already does).
5. **Islands as needed:** `CXX` enabled only for the target that needs it (for example the tracker item DSP core), behind a C header.

Gates for every slice: the CLAUDE.md gates (Mac build, `tests/posix_ctest.sh` 0 FAIL, `pytest tools/recomp tools/disasm` when tools change), a review, and the toolkit generic ctests under Proton. Slices 2-4 change only build flags, tests and diagnostics, so goldens are required only if a fix from them changes runtime code. Then the Metal goldens and `blinx2 bench golden`, plus the B3 race gate.

### What would change the recommendation

- **Contributors:** a stable group of outside contributors who will only work in Rust or C++, and who would maintain a subsystem. Then (d) or (b1) for that subsystem, behind the contract.
- **Safety evidence:** the safety lanes keep finding host-side lifetime or race bugs after slice 2, at a rate that tooling cannot keep down (say more than one shipped-to-players host memory bug per release round). Then (b1) for the subsystem concerned (RAII), or (d) for a leaf.
- **Untrusted input grows:** mods, scripting (the static and Lua assessment) or an HTTP upscaler that takes outside data become central. Then a Rust leaf for that parser, behind a C header, becomes worth its toolchain cost.
- **The lifter changes target:** a new lifter that emits structured code (no irreducible `goto`) with no compile-time or size penalty. Then re-measure M2.
- **Upstream moves to C++ or Rust.** It is weighed lightly, but it would change the ecosystem argument.

## Risks

- **The C path can drift into "no safety work".** Mitigation: slices 2 and 3 are the price of choosing C, and they have their own gates and ratchet.
- **C23 support differs between toolchains.** Mitigation: C17 is the baseline, and C23 features come behind a check.
- **A C++ island grows into a second runtime language.** Mitigation: islands are third-party or self-contained cores behind a C header, each named in TASKS.md.
- **M2 is synthetic.** Its ratios could be off by a factor. They would have to be off by about 5x to change the conclusion for chunk 0009.

## Decisions (the user, 2026-10-21)

1. **Option (a) is approved and parked.** The toolkit stays on C11 until slice 4, with the tooling of slices 2-4 and the runtime contract of slice 1. No slice starts now. They wait behind the current order: the wrap-up, then the APU DSP, then SDL3, then the release. Each slice then needs the user's go.
2. **Third-party licences.** Any licence that fits the current repos is acceptable. The project is never closed-source, so third-party code is allowed when it is disclosed and credited: an entry in `NOTICE` and the licence text in `LICENSES/`, as the toolkit already does for the LGPL-2.1 xemu APU files. The repos stay "MIT, except the files listed in NOTICE, which keep their own licence". A GPL-3.0 component, such as gearmulator's DSP56300 core, is acceptable when it is credited and its effect is stated. Game binaries are never distributed, because players build them (Platforms), so the GPL-3.0 effect falls on binaries we do distribute that link the component: toolkit-only binaries, and any prebuilt build we ship in future. Each of those is GPL-3.0 as a whole and comes with an offer of its source. The LGPL-2.1-or-later xemu files combine with GPL-3.0 through their "or later" clause, and so would xemu's GPL-2.0-or-later DSP core.
3. **The runtime contract is a standalone, versioned document,** proposed as a standard that other projects can reference and that is updated over time. It does not live in the toolkit's `docs/runtime/`.
   - **Home:** its own repository (working name `xbox-recomp-abi`), local first, then public at a push round like the other repos, with only `main`. It is MIT. `recomp_abi.h` is carved out of upstream's MIT `recomp_types.h`, so it keeps that notice ("Copyright (c) 2026 sp00nz") next to ours. It holds `contract.md` (the normative text), `recomp_abi.h` (the clauses as a C header), the conformance fixtures and the symbol checker, `CHANGELOG.md` and `VERSION`. Why its own repo: the contract has its own release cadence, its readers include people who never take the toolkit (a second runtime or lifter), and a version tag of the document must not move with toolkit commits. A directory inside the toolkit would tie each contract version to a toolkit sha and make the toolkit look like the owner of the standard.
   - **Repo rules:** the ones CLAUDE.md sets for `xboxrecomp-cli`. Every commit is authored and committed as `carlos <4037632+apexJCL@users.noreply.github.com>` from the first commit. Before each push, `scripts/audit-public.sh` runs over the delta and `git log --format='%ae %ce'` shows only that address. Pushes are fast-forward only; pushing release tags is allowed. Its push round goes before the toolkit fork's, because the toolkit pins a contract tag. Its own gates are `uv run pytest` and the ruff checks for `abi_symbols.py`. It gets a Layout and a public-push entry in CLAUDE.md.
   - **Versioning:** `MAJOR.MINOR`, tagged `v1.0`, `v1.1`, ... A major version changes the ABI: generated code built against v1 does not work with a v2 runtime. It bumps `RECOMP_ABI_VERSION` and the link symbol (`recomp_abi_v1` to `recomp_abi_v2`, task 1.5). A minor version only adds clauses that are compatible, or makes clarifications. Every tag gets a `CHANGELOG.md` entry. Drafts are `v1.0-draft.N` until the first tag.
   - **Conformance:** an implementation claims "conforms to the Xbox recomp runtime contract vX.Y" when it passes that tag's conformance suite. A runtime must pass the clause fixtures (task 1.4) and define the link symbol. A lifter must emit code whose undefined symbols pass the symbol checker (task 1.3). The claim names the tag and the role (runtime, lifter or both) in the implementation's README. The contract's README keeps a list of known implementations and the version each claims. xboxrecomp is the first, as runtime and lifter.
   - The toolkit pins a contract tag, the way `game.toml` pins the CLI sha, and vendors `recomp_abi.h` and `abi_symbols.py` from it. Its `docs/runtime/` links to the contract instead of holding it.
4. **The probe Rust toolchain** under `runs/toolkit-language/rust/` is already deleted.
