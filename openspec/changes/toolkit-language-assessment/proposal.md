## Why

On 2026-10-21 the user asked whether the xboxrecomp toolkit should move from C11 to a modern C or C++ (C23, C++20/23) or to Rust. The goal of the whole effort is game preservation through a pristine migration of original Xbox games, plus enhancements that make them more comfortable to play. The question weighs the toolkit becoming a reference implementation and a standard for Xbox static recompilation. Giving the work back to upstream (sp00nznet/xboxrecomp, MIT) is not weighed heavily.

The toolkit is about 96k lines of C and Objective-C runtime, 31k lines of C tests and 47k lines of Python tools. It serves five games: BLiNX 2, Burnout 3, SSX 3, JSRF and Spartan. Their generated code adds 1 to 3.4 million lines of C per game, and the player compiles it on their own machine through the wizard. A language change touches all of this, so it needs numbers before anyone starts.

## What Changes

This is an assessment. It changes no behaviour and has no spec deltas (`skip_specs: true`).

- **`design.md`** holds:
  - the inventory of today: size per subsystem, the C idioms, the generated code and its coupling to the runtime, and the platforms;
  - five options with effort, risk, pros and cons: (a) C with targeted modernisation, (b) C++, (c) a full Rust rewrite, (d) Rust per subsystem over a C ABI, (e) Zig;
  - measurements made for this spike: real generated chunks compiled as C11, C23 and C++20; a synthetic Rust lowering with the same control flow; the toolkit compiled as C23 and as C++20;
  - the evidence from 1,319 toolkit commits on which bug classes each option would prevent;
  - the criteria matrix and the recommendation.
- **Recommendation: stay on C, move the baseline to C17 with selected C23 features, and spend the effort on what makes a reference implementation.** That means:
  - a written, versioned contract between the generated code and the runtime;
  - sanitizer, static-analysis and fuzzing lanes;
  - a warnings ratchet.

  C++ is allowed only for leaf components behind a C interface, such as a DSP56300 core. Rust stays a revisit trigger, not a plan.
- **`tasks.md`** holds the first slice (the runtime contract) in full and slices 2-4 for planning. All are parked: the user approved option (a) on 2026-10-21, and the slices wait behind the wrap-up, SDL3 and the release (`design.md`, Decisions).

## Capabilities

### New Capabilities
- None. The runtime contract (task 1) becomes its own change with requirements when it starts. It lives as a standalone, versioned document in its own repository, not in the toolkit (`design.md`, Decisions, 3).

### Modified Capabilities
- None.

## Impact

- No code, build or behaviour change from this change itself.
- The probes used throwaway files in `runs/toolkit-language/`: the synthetic generator `synth_cfg.py`, the object files and the logs. They are local only and can be cleaned up with `notes/cleanup-derived.py`. The probe Rust toolchain there is already deleted.
- The recommendation keeps the roadmap order: the wrap-up, then the APU DSP, then SDL3, then the release, then the overlay (the tracker item..292). The slices wait behind the wrap-up, SDL3 and the release, and touch no game-visible behaviour.
