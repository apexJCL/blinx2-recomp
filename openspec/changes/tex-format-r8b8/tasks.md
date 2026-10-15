Worktrees:
- `wt/blx136/xboxrecomp`: toolkit, branch `blx136/tex-format-0x29` off `posix-host/portability` b958798. The prototype is a3e3de5.
- `wt/blx136/cat`: this spec, branch `blx136/tex-format-0x29-spec` off cat `main`.
- `wt/blx136/tca`: a `cp -c` clone of `spartan/tca` with its build dirs removed. `build/` is configured with `XBOXRECOMP_DIR` set to the toolkit worktree.

Raw runs go in `xbox-recomp/runs/blx136/`. Mac runs are headless: `SDL_AUDIODRIVER=dummy`, with perl `alarm` as the timeout. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Proton runs are on the Deck with a Mac-built exe copied over (memory note *deck-proton-bench*). Check `ListAgents` first: one agent on the Deck at a time, and never build there.

The change touches only a header that the generated code does not include in any way that affects it. So a game build against the branch may use `--stale-gen-ok` (`tca build macos --stale-gen-ok`; `blinx2 build ... --stale-gen-ok`) rather than regenerating. Record this in each provenance note.

## 0. Spec review

- [x] 0.1 A model other than Fable wrote this spec, so Fable reads and improves it, then commits the revision on the spec branch. Done: Fable verified the channel order against xemu's GL and Vulkan tables and Cxbx's row converters, settled signedness (design.md D3) and sized the gates (design.md, Validation).
- [x] 0.2 Implementation starts only from Fable's revised commit.
  Done: implementation resumed from 976d5dc.

## 1. Toolkit

- [x] 1.1 `src/kernel/nv2a_backend_common.h` gets the three table entries of design.md D1: twin 0x29 → 0x16, 0x16 as 2 bytes, and the 0x16 decode case. The case's comment names xemu's (G, R, R, G) swizzle and Cxbx's `____R8B8` row. The prototype a3e3de5 already has this and the review found it correct; keep it as is.
  Done: a3e3de5, unchanged.
- [x] 1.2 The ctest cases from design.md Validation in `tests/nv2a_tex/test_main.c`. The prototype has them. One fix: the comment on the swizzled 2x2 case calls the 9-level 256x256 extent "Spartan's"; Spartan's texture has one level (`mips 1`), so say the full chain is the extent check and Spartan's single level is the 131072-byte one. Show that the test fails against the base header (first failure: the twin check) and passes with the change. Keep both outputs in the branch notes.
  Done: comment fixed in 0f71a76. Against b958798's header the test stops at `FAIL line 128: nv2a_tex_linear_twin(0x29) == 0x16`; with the change `nv2a_tex: all passed` (`runs/blx136/nv2a_tex-ab.txt`).
- [x] 1.3 Re-check at merge time that no backend file needs a change: neither `nv2a_pb_metal.m` nor `nv2a_pb_d3d11.c` has a switch on texture format outside `rt_texture`/`rt_16bit` (true at b958798, checked at review). If a later toolkit commit added a native format map, extend it the same way on both backends, or record the gap in TASKS.md.
  Done at 0f71a76 (still b958798 + two commits): no format switch in either backend outside `rt_texture`/`rt_16bit`. Re-check if the base moves before the merge.

## 2. Gates

- [x] 2.1 Mac toolkit build and `tests/posix_ctest.sh <dir>`: 0 FAIL. `tools/recomp` and `tools/disasm` are untouched, so no pytest is needed. The prototype a3e3de5 passed: 59 pass, 1 skip (mmx_integer), 15 n/a, 0 FAIL (`runs/blx136/posix_ctest-summary.txt`). Re-run after 1.2.
  Done at 0f71a76: Mac build ok; 59 pass, 1 skip (mmx_integer), 15 n/a, 0 FAIL (`runs/blx136/posix_ctest-0f71a76-summary.txt`).
- [x] 2.2 BLiNX 2 Metal golden check, once, against the branch: `blinx2 golden run` and `golden check` from a cat worktree built against the toolkit branch (`--stale-gen-ok`, provenance note). Verdicts must match main's Metal verdicts (TASKS.md records the known Metal story failures on main). Record flips/s and mean frame ms from the run itself for the TASKS line; no A/B series against main is needed (design.md, Validation: nothing BLiNX binds changes). The run's log must contain no `not decoded` line.
  Done (toolkit 0f71a76, cat 976d5dc with main's gen, `--stale-gen-ok --system-tools`; exe sha256 in `runs/blx136/blinx2-metal-golden/provenance.txt`): attract, stage1, story all pass; no `not decoded` line. Flips/s and mean frame ms (flip intervals after flip 200): attract 45.8/s 21.84 ms, stage1 32.9/s 30.41 ms, story 52.0/s 19.23 ms (`runs/blx136/blinx2-metal-golden/flip-ms.txt`), in line with main's blx132 base runs (46.7, 33.4, 54.1). The story run started with another game process up (WARNING in its run-info) and still passed.
- [ ] 2.3 Burnout 3 race gate: not a gate for this change (design.md, Validation). Note in the TASKS line that B3's next toolkit pin bump runs it as usual. Optional, on the orchestrator's go, one Mac Metal run from b3 at main built against the branch; its log must contain no `not decoded` line.
- [ ] 2.4 Deck D3D11 BLiNX golden: the post-merge `integrate --golden` run (Mac `blinx2 build windows` with a provenance file, copy to the Deck's `~/blx-bench/cat/build-win/`, `blinx2 bench golden`), as CLAUDE.md step 5 requires. Not a pre-merge gate for this change. Verdicts for attract, stage1 and story must match the last main session (2026-10-15 00:32, all pass), with flips and mean frame ms recorded.
- [x] 2.5 Spartan on Metal (Mac) and D3D11 (Deck, Mac-built `tca build windows --stale-gen-ok`), both from `wt/blx136/tca`. Pre-merge, both. Expected:
  - no `texture format 0x29 ... not decoded: drawn magenta` line, and no `not decoded` line for any other format;
  - on a CPU run with `RECOMP_TRACE=tex=2`, the line `[TEXLOG] new 0x80720E00 fmt 0x29 swz 256x256 ... decode ok` (the prototype's run `runs/blx136/20261015-051845-r8b8-cpu-texdump/stdio.log` line 676 shows it);
  - frame dumps (`RECOMP_DEBUG=fb_dump=...`) under `runs/blx136/` only.

  The prototype's Metal run (`runs/blx136/20261015-051648-r8b8-mac/`) already shows the line gone (exit 142 is the perl alarm). All 10 of its frame dumps are one colour, because Spartan stops presenting after flip 4 (BLX-134) and the glow pass that samples the table never reaches a presented frame. If a later Spartan build presents that pass, add a frame dump of it from before and after the change to `runs/blx136/`. Frames are never published.
  Done (toolkit 0f71a76, `--stale-gen-ok`): Metal `runs/blx136/20261015-054234-spartan-metal/` has 0 `not decoded` lines (blx132 base: 1, for 0x29), and its 8 frame dumps are one colour (BLX-134 stall after flip 4). D3D11 on the Deck (Mac-built exe sha256 98c69aa7..., own dir `~/spartan-bench-blx136`, under the run lock) `runs/blx136/deck/20261015-060003/`: reaches the glow targets (`surface 0x0065C000`) with 0 `not decoded` lines (blx132 base: 1); exit 124 is the 150 s timeout. CPU with `RECOMP_TRACE=tex=2` `runs/blx136/20261015-054234-spartan-cpu-tex2/stdio.log` line 673: `[TEXLOG] new 0x80720E00 fmt 0x29 swz 256x256 ... stages 0x2 decode ok batches 1`, 0 `not decoded`/`no decoder` lines.

## 3. Follow-ups (file in TASKS.md at merge)

- [ ] 3.1 BUMPENVMAP (mode 6) on every path. Spartan's glow pass samples the R8B8 table through it (stage 1, mode 6; the offset is stage 0's `.b`/`.g`, the downsampled frame read as `LIN_R8G8B8A8`). One batch also has stage 3 in mode 6 with no texture logged. This joins the existing TASKS item for BLiNX 2's Boss 3 ripple and stage-1 ocean.
- [ ] 3.2 The `SET_TEXTURE_FILTER` `SIGNED` bits (28-31; XDK `D3DTSS_COLORSIGN`) are ignored on every path; xemu ignores them too (design.md D3). Spartan's R8B8 stage has them clear.
- [ ] 3.3 The `d3d8_xbox.h` bump-format enum values are not the XDK's aliases, and the HLE `d3d8_to_dxgi_format` maps R8B8/G8B8 to `R8G8_UNORM` without the swizzle the references use (design.md D4, item 3). The toolkit's `docs/technical/gap-analysis.md` (line 27) marks the HLE "Signed texture formats (R6G5B5, V8U8, V16U16)" row DONE on the strength of those "distinct compact values"; that row is revisited together with the enum values. Upstream code; an upstream PR candidate.
- [ ] 3.4 Depth texture formats 0x2A-0x31 and V16U16 (0x33/0x36), when a title samples one.

## 4. Review

- [ ] 4.1 An Opus review of the toolkit branch before the merge. Its fixes go back to the branch agent.
