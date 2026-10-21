The recommendation is option (a): stay on C and invest in the runtime contract, the safety lanes and fuzzing (`design.md`, Recommendation). This file holds slice 1 in full and lists slices 2-4 for planning.

- **Parked (the user, 2026-10-21).** Option (a) is approved, but no slice is scheduled. They wait behind the current order: the wrap-up, then the APU DSP, then SDL3, then the release. Each slice then needs the user's go.
- Each slice runs in its own worktree, gets its own tracker item, and branches off `posix-host/portability` when it touches the toolkit.
- Slice 1 gets its own openspec change with requirements (`runtime-contract`) when it starts. The contract is a standalone, versioned document in its own repository (`design.md`, Decisions, 3).
- No slice may change stock behaviour. Slices 2-4 may only add build options, tests and diagnostics. A defect they find is fixed on its own branch, with the usual golden gates.

## 1. Slice 1: the runtime contract, version 1 (5-6 agent-days, parked)

- [ ] 1.0 Create the contract repository (working name `xbox-recomp-abi`) with `README.md`, `VERSION`, `CHANGELOG.md` and an MIT `LICENSE`, as `design.md` Decisions 3 says. `recomp_abi.h` keeps upstream's MIT notice ("Copyright (c) 2026 sp00nz") because it is carved out of `recomp_types.h`. It stays local until a public push round.
  - Every commit is authored and committed as `carlos <4037632+apexJCL@users.noreply.github.com>` from the first commit. Before each push, run `scripts/audit-public.sh` over the delta and check that `git log --format='%ae %ce'` shows only that address. Pushes are fast-forward only; release tags may be pushed. Its push round goes before the toolkit fork's, because the toolkit pins a contract tag (1.6).
  - Its gates: `uv run pytest` and `uv run ruff check . && uv run ruff format --check .` for `abi_symbols.py` (1.3).
- [ ] 1.0a Add the contract repository to CLAUDE.md: a Layout entry and a public-push entry with the rules of 1.0.
- [ ] 1.1 Write `contract.md` in the contract repository as a normative specification ("must", "may"), version 1, built from `templates/runtime/recomp_types.h` and the prose in `docs/technical/` (`register-model.md`, `memory-layout.md`, `indirect-calls.md`, `seh-handling.md`). It covers:
  - the guest register and FPU state (TLS globals, the x87 stack and its precision control, MXCSR, the direction flag, `eflags`);
  - the calling convention (`void(void)` functions, arguments on the guest stack, the return value in `g_eax`, the pushed return address);
  - guest memory: `g_xbox_mem_offset`, `volatile` access, the MMIO forms;
  - indirect calls: the lookup order (`recomp_lookup`, `_kernel`, `_manual`) and what a miss must do;
  - SEH, `setjmp`/`longjmp` and the guest's non-local jumps;
  - the scheduler's safe points and preemption (`xbox_GuestCpuPreempt`, `g_xbox_guest_cpu_preempt`);
  - the kernel import table and the thunk slots.

  Each clause names the header line or the function that implements it today. **Done when** a review finds every symbol the generated code references (task 1.3) covered by a clause.
- [ ] 1.2 Split the contract out of `recomp_types.h` into `recomp_abi.h`, which holds only the clauses of 1.1 with `RECOMP_ABI_VERSION 1`. It lives in the contract repository, and the toolkit vendors it from a pinned tag. The rest of `recomp_types.h` stays in the toolkit as lifter helpers that include it. `recomp_types.h` keeps including everything, so generated code does not change.
  - **Gate:** regenerate BLiNX 2 and Burnout 3. Each generated `.o` must have the same `.text` sha before and after (the M1 method in `design.md`). If any differs, the change touched what the game executes, so the Metal goldens, `blinx2 bench golden` and the B3 race gate are required.
- [ ] 1.3 Add the symbol checker `abi_symbols.py` to the contract repository with a test, The toolkit vendors it from the pinned tag, like `recomp_abi.h` (1.2), and runs it from `pytest tools/recomp`. It lists the undefined symbols of compiled generated objects (`nm -u`, or `llvm-nm` for the llvm-mingw objects). It fails when one is none of these:
  - a function declared in the game's `recomp_funcs.h`, which covers `sub_*` and library-named functions such as `sprintf_002D4ED0`;
  - libm;
  - a symbol named in `recomp_abi.h`.

  Run it over the BLiNX 2, Burnout 3, SSX 3, JSRF and Spartan generated code. Record any other symbol as a contract gap, or as a per-game manual override (`recomp_manual.c`) that the contract allows.
- [ ] 1.4 Add a `runtime_contract` ctest. Its fixtures live in the contract repository as the runtime conformance suite, and the toolkit builds them. A hand-written fixture in the style of generated code, compiled against the runtime libraries, checks each clause of 1.1:
  - stack push and pop and the return address;
  - the return value in `g_eax`;
  - x87 push and pop with 24-bit precision control;
  - MXCSR rounding on a conversion;
  - a guest memory round trip through the offset;
  - an indirect call through `recomp_lookup`, and a miss;
  - a guest `setjmp`/`longjmp` pair;
  - a preemption safe point.

  It runs in `tests/posix_ctest.sh` and under Proton.
- [ ] 1.5 Link-time version check. The runtime defines `recomp_abi_v1`, and the generated `recomp_dispatch.c` references it, so a runtime and generated code built against different contract versions fail to link instead of misbehaving.
  - This changes generated code, so it needs a regen of all five games and the full golden gates: Metal goldens, `blinx2 bench golden` on the Deck, the B3 race gate, and the SSX 3, JSRF and Spartan smoke runs.
  - Land it with the next regen that the roadmap needs anyway, not as a regen of its own.
- [ ] 1.6 Tag `v1.0` with a `CHANGELOG.md` entry. Write the conformance rule in the contract's README: an implementation names the tag and its role (runtime, lifter or both) and passes 1.4 (runtime) or 1.3 (lifter). List xboxrecomp there as the first implementation. Link the contract from the toolkit README and `docs/runtime/README.md`, and pin the tag in the toolkit.

**Slice 1 gates (CLAUDE.md):**
- the Mac build with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`;
- `tests/posix_ctest.sh` with 0 FAIL;
- `pytest tools/recomp tools/disasm`;
- the llvm-mingw cross-build and the ctests under Proton;
- a review.

Goldens only as 1.2 and 1.5 say.

## 2. Slice 2: safety lanes (3-4 agent-days, parked)

- [ ] 2.1 `XBR_SANITIZE=address,undefined` and `XBR_SANITIZE=thread` CMake options (default off). Mac ctest lanes for both. Record the findings in TASKS.md, each fixed on its own branch.
- [ ] 2.2 Clang `-Wthread-safety` annotations on the APU frame lock and the kernel lock wrappers, in the build only when the compiler supports them.
- [ ] 2.3 A `clang-tidy` and `scan-build` lane (bugprone, cert, concurrency checks), with a baseline file so that only new findings fail.
- [ ] 2.4 A warnings ratchet: `-Wconversion -Wsign-conversion -Wshadow` counts per library are recorded, may only fall, and new files must be clean.
- [ ] 2.5 Fix the two defects found by this spike: the thread-start cast in `src/apu/apu_shim.h:138`, and the out-of-bounds index in `src/nv2a/nv2a_pb_replay.c:284` (check whether the POSIX build reaches it).

## 3. Slice 3: fuzzing (2-3 agent-days, parked)

- [ ] 3.1 libFuzzer harnesses for the XBE parser, texture packs, enhance TOML (`recomp_cfg.c`, `enhance_cfg.c`), `kbm_script` and pushbuffer method decode, with seed corpora from local test files (no game data in the repo).
- [ ] 3.2 A bounded CI or bench run of each harness (for example 60 s per harness), with crashes kept as regression inputs.

## 4. Slice 4: language baseline (1 agent-day, parked)

- [ ] 4.1 `CMAKE_C_STANDARD 17` in the toolkit and the game templates. Add an `XBR_C23` probe that enables C23 features (`nullptr`, `typeof`, `static_assert`, `[[nodiscard]]`, `constexpr` objects, `#embed`) only when Apple clang, llvm-mingw clang and the Linux compilers all accept `-std=c23`. Write the rule in the toolkit's contributing notes.
- [ ] 4.2 A rule for C++ islands: `CXX` is enabled per target, behind a C header. Each island is named in TASKS.md with its licence, and credited in `NOTICE` with its text in `LICENSES/`. The first likely one is the tracker item DSP56300 core. A GPL-3.0 core is acceptable. The licence line stays "MIT, except the files listed in NOTICE, which keep their own licence", and `NOTICE` states that any distributed binary that links the core (toolkit-only binaries, or a future prebuilt build; players build the games themselves) is GPL-3.0 as a whole (`design.md`, Decisions, 2).
