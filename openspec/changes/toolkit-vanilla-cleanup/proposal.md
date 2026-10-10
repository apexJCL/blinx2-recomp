# Toolkit vanilla cleanup

Plane BLX-47. Input: `xbox-recomp/notes/vanilla-audit/REPORT.md` (2026-10-09),
approved by the user the same day. Written by Fable, so no separate spec
review.

## Why

The toolkit fork (`xboxrecomp/` `posix-host/portability`) is about to be cut
into upstream PRs. Its delta over v0.13.1 carries no BLiNX 2 logic, but it
reads like a BLiNX 2 project: the enhancements doc describes this game's own
keys, a header points at `cat/docs/env.md`, test fixtures are named after the
game, about fifty comments explain a generic console rule through a BLiNX 2
`sub_` name, guest address or a private run directory, and nine constants
were sized on BLiNX 2 with no way to change them. Each PR branch would
inherit all of it. Cleaning once on the integration branch, before the PR
series, is cheaper than cleaning per PR, and the public toolkit fork
(`apexJCL/xboxrecomp` `blinx2/portability`) gets the same vanilla text.

## What changes

Behaviour is unchanged for BLiNX 2 and Burnout 3. Every new knob defaults to
today's value; the two policy changes pick the value both games already set.

1. **Text out of the toolkit** (audit A1-A4). The BLiNX 2 rows and paragraphs
   of `docs/runtime/enhance-config.md` move to `cat/docs/env.md`; the toolkit
   doc keeps its five keys, one neutral game-key example and the bind call.
   `recomp_env.h` stops naming `cat/docs/env.md` and cat's golden tooling.
   The spin-wait example site becomes a round number in `spin_waits.py`,
   `docs/pipeline/04-lifting.md` and the test fixture.
2. **Fixture renames** (A5-A10, H2). Neutral title, keys, file names and
   addresses in the tests; the four oracle files lose the private-history sha
   in their names.
3. **Comment scrub** (the ~53 class-b rows, plus H3). Each comment keeps the
   hardware or XDK rule and the failure it prevents, phrased without the
   title's symbol names, guest addresses or private paths (design D1).
4. **BLiNX-tuned defaults become config at today's values** (C1, C5, C7, C8,
   C9): the DPC sampler's code window reads the loaded image's code bounds;
   the present-surface staleness window, the GPU texture caches and the CPU
   depth-buffer slots get `recomp_env` debug keys; the disasm data-pointer
   probe budgets become detector parameters with CLI flags.
5. **Policy** (user-approved): `apu_dsp_ack` defaults to `auto` in the
   toolkit (C3), and the one-core pin gets an explicit `one` spelling so a
   game can state it in `RECOMP_ENV_GAME_DEFAULTS` (C2). cat and b3 set
   `GUEST_CPUS=one` and drop their now-redundant `APU_DSP_ACK=auto`.

Out of scope, recorded as TASKS follow-ups: H1 (the generator emits a raw
`getenv` into stub code), H4 (one shared physical-address resolver for the
APU and the OHCI), and the rewrite of the PR plan. `game.toml` plumbing for
the new disasm flags is a CLI follow-up; the flags exist from this change.

## Impact

- Toolkit: `docs/runtime/enhance-config.md`, `docs/pipeline/04-lifting.md`,
  `src/platform/recomp_env.{h,c}`, `src/kernel/kernel_prof.c`,
  `src/kernel/nv2a_pb_exec.c`, `src/kernel/nv2a_zbuf_cache.h`,
  `src/d3d/nv2a_pb_d3d11.c`, `src/d3d/nv2a_pb_metal.m`,
  `src/kernel/kernel_thread.c`, `tools/disasm/{functions,disasm,__main__}.py`,
  `tools/recomp/spin_waits.py`, comment-only edits in the kernel, APU and
  renderer sources, and the tests named in the audit.
- cat: `src/env/recomp_env_game.h`, `docs/env.md`, this spec, TASKS.
- b3: `src/env/recomp_env_game.h`.
- Generated code: none. `blinx2 recomp` output is byte-identical (the lifter
  and disasm changes are comments and defaults).
- Hot paths: each new key is read once into a static; no per-draw lookup.
- BLX-31 (`fix/mac-one-cpu`) lands first and touches `kernel_hal.c`,
  `kernel_bridge.c`, `kernel_pacing.c`, `recomp_env.h` and three tests. This
  change keeps its edits in those files to comments and to rows added at the
  end of the table, so the rebase is mechanical.
- Proton (not run here): the BLiNX 2 golden, and Burnout 3 boot plus audio
  for C2 and C3 (both are no-ops for b3 by construction; the run is the
  gate because the ack path is audio).
