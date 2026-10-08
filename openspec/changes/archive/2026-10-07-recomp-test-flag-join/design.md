## Context

The lifter snapshots a flag setter's operands into `_fa/_fb/_fas/_fbs` where the setter runs (`Lifter._snapshot_flags`, lifter.py). A later jcc, setcc or cmovcc reads them through `_make_condition`: the `cmp` arm emits `CMP_*(_fa, _fb)` or, for js/jns/jp/jnp, the sign or parity of the wrapped difference; the `test` arm emits `TEST_*(_fa, _fb)`, `CMP_*(_fa & _fb, 0)`, the sign or parity of the AND, and the constants 0 and 1 for jo/jno. The translator carries a flag state `(kind, ops)` along each control-flow edge and settles it to a fixed point before emitting (`translator.py`, "Settle the flag state before emitting anything"). At a join `_merge_flag_states` (translator.py:31) merges what the predecessors carry:
- identical states merge;
- cmp+cmp or test+test of the same width merge, because each predecessor writes the same temporaries;
- states whose ZF comes from the same destination register merge (`_merge_zero_flag`, je/jne only);
- anything else gives None. A consumer in a block with no state compiles to `_flags`, which nothing assigns, so the branch is never taken (`Lifter._lift_jcc`, `_lift_setcc`, `_lift_cmovcc`).

`normalise_zero_test` (lifter.py:1279) already rewrites `test X, X` as `cmp X, 0` so that it merges with a cmp. The stage 1 case is `test esi, 0x100` joined with `cmp eax, 0` (`sub_000F7C50`, guest 0x000F7F7C), which falls outside that rule.

### Where the 21,003 fallbacks come from

A classification pass over the current BLiNX 2 translation (the translator run as `blinx2 recomp` runs it, with `_incoming_flag_state` and `lift_basic_block` instrumented; script, per-site list and summary in `xbox-recomp/runs/recomp-test-flag-join/classify/`) gives the shape of the problem. "Unique" counts one guest `(address, condition)` once, however many alias bodies emit it; "reachable" means the owning function is in the static call closure from the XBE entry point plus the seed list, which under-counts (vtable and other indirect calls are not followed) but is the honest lower bound we have without a runtime profile.

Toolkit head `eb38e51`, cat analysis of 2026-10-06 (26,180 detected functions, 1,210 statically reachable):

| | emitted `if (_flags` | unique guest sites | in reachable functions |
|---|---|---|---|
| all | 21,161 | 2,004 | 166 (in 58 functions) |

Unique sites by why the state was lost (unique / reachable):
- **entry block, 1,643 / 160.** The function's first block starts at or just before a jcc with no setter in front of it. These are bodies that function detection starts at a branch target (`cc_boundary`, `call_target`, alias entries from "every direct branch out of a lifted body lands on an entry"), so the jcc consumes flags set in another function. The owner body that contains the same instruction emits a real condition; the fallback copy runs only when control enters at that address from outside. That is cross-function flag inheritance, not a join, and it is out of scope here (D5 records it).
- **in-block, 193 / 1.** A setter in the same block cannot answer the condition (`add/and/or/xor/sub` followed by `jo`, `imul` followed by `je`/`js`) or an untracked instruction cleared the state (`outsb`, `outsd`, `insd`, `popal`, `daa`, `bound`, `arpl`: data decoded as code).
- **predecessor unknown, 101 / 0.** A predecessor ends with its flags clobbered (`call`, `mul`/`div`, an untracked instruction) or has no computed state.
- **incoming state cannot answer, 14 / 0; no predecessors, 10 / 2.**
- **joins that did not merge, 43 / 3:**
  - a `cmp` and a `test` of the **same** width: 3 (0x000F7F7C, the stage 1 join; 0x000E0CE2; 0x0017F97E in the player update `sub_00176150`). D1 fixes these.
  - cmp/test states of **different widths** (`cmp eax, ..` meeting `test al, ..` or `cmp byte ptr`): 17, among them 0x0017F7E7 and 0x0018095B, also in `sub_00176150`. D1b fixes these for every condition but js/jns/jo/jno.
  - a cmp/test meeting an arithmetic result setter (`and ecx` + `cmp` + `inc ecx` is MSVC's counted loop; `cmp` + `sub eax`; `cmp` + `dec eax`): 20. Follow-up (D5).
  - arithmetic only (`add` + `imul`, `add` + `and`): 3. Genuinely different setters.

Two cautions on "reachable". `sub_00176150` runs every frame (the spike watched it) and is not in the static closure, because the title reaches it through a vtable, so the reachable column is a floor, not the set that matters. And the `jo` and `jp` sites that dominate the emitted count come almost entirely from the entry-block and data-decoded classes. What the table says: the headline number is an artefact; the fixable joins are a few dozen unique sites, five of them in the two functions the spike already implicated; and the per-site report (D3) is how the next one is found.

## Decisions

### D1. Lift every TEST as a CMP of its AND against zero

`test a, b` computes `r = a & b` at the operand width, sets ZF, SF and PF from r, and clears CF and OF. `cmp r, 0` computes `r - 0 = r`, so ZF, SF and PF are the same. CF is 0 because nothing borrows from zero, and OF is 0 because subtracting zero cannot overflow. The two are flag-identical, so every condition code reads the same answer from either. Checked against what the `cmp` arm of `_make_condition` and the macros in `templates/runtime/recomp_types.h` actually emit, with `_fa = r`, `_fb = 0`, `_fas = sx(r)`, `_fbs = 0`:

| jcc | flags | `cmp` arm emits | reads as |
|---|---|---|---|
| je/jne | ZF | `CMP_EQ/NE(_fa, _fb)` | `r == 0` / `r != 0` |
| jb/jae | CF | `CMP_B/AE(_fa, _fb)` | `r <u 0` is 0, `r >=u 0` is 1: CF=0 |
| jbe/ja | CF or ZF | `CMP_BE/A(_fa, _fb)` | `r <=u 0` is ZF, `r >u 0` is !ZF |
| jl/jge | SF xor OF | `CMP_L/GE(_fas, _fbs)` | `sx(r) < 0` is SF, since OF=0 |
| jle/jg | ZF or (SF xor OF) | `CMP_LE/G(_fas, _fbs)` | `sx(r) <= 0`, `sx(r) > 0` |
| js/jns | SF | `_sf_of_difference(_fas, _fbs)` | top bit of `(r - 0)` at the operand width |
| jp/jnp | PF | `RECOMP_PARITY8(_fa - _fb)` | parity of the low byte of r |
| jo/jno | OF | **None today** | see below |

`_cf`: the snapshot's zero-rhs rule (`zero_rhs` in `_snapshot_flags`) writes `_cf = 0`, which is what a `test` leaves. setcc and cmovcc go through `_make_condition` with the same state, so they follow. `lahf` and `pushfd` probe `_make_condition` per flag and get the same bits.

**jo/jno is the one gap, and it must be closed in the same change.** The `test` arm answers them with the constants 0 and 1; the `cmp` arm returns None, which is the `_flags` fallback. Normalising without fixing that turns `test; jno` from always-taken into never-taken, and makes `pushfd`/`lahf` after a test report OF as "not modelled" where today it is a known 0. The `cmp` arm therefore gains jo/jno computed exactly: OF of `a - b` at width w is bit `w*8-1` of `(a ^ b) & (a ^ (a - b))`, done in the unsigned type of the width like `_sf_of_difference` so no signed overflow is written in C. This also makes every real `cmp; jo` site a live branch. BLiNX 2 has no fused `test; jo/jno` today (`if (0 /* jo` and `if (1 /* jno` do not occur in gen/), so the guard is for other titles and for `pushfd`.

The snapshot for a test becomes:

```c
_fa = (uint32_t)((A) & (B)) & MASK; _fb = 0;
_fas = (int32_t)SX(_fa); _fbs = 0; /* test A, B (N-bit) */
_cf = 0; /* nothing borrows from zero */  (when the function tracks CF)
```

The comment keeps the original instruction, so the generated C still reads as the source.

**Representation.** The recorded state is `("cmp", [<and operand>, imm 0])` at the operand width. The AND operand is a new `Operand` type, `"expr"`, carrying the C text of the masked AND and `mem_size` = the width. It needs `_fmt_operand_read` (return the text) and `_operand_width` (return `mem_size`). Nothing else formats it: the `cmp` arm of `_make_condition` reads only the `_fa/_fb` temporaries for cmp/test states, `_merge_flag_states` only compares kinds and widths, and `_merge_zero_flag` is never reached for a `cmp`. The width comes from the test's own operands (`_operand_width(a) or _operand_width(b)`), exactly as `_snapshot_flags` computes it today, so an imm-only width never arises. `test X, X` falls out as a special case; `normalise_zero_test` becomes the general rule, and the emitted C for `test X, X` must not change (`test_lifter_zero_test_merge` pins it). The fused `cmp/test + jcc` path (`_try_match_cmp_jcc` and the fused snapshot in `lift_basic_block`) already goes through `normalise_zero_test`, so it follows for free.

**Tests whose meaning changes.** `test_lifter_zero_test_merge.test_a_test_of_two_different_registers_is_left_alone` asserts the opposite of this decision and is rewritten to assert the new form. `..._a_genuine_test_still_refuses_to_merge_with_a_compare` and `test_flag_join.test_mixed_operations_are_not_guessed` feed raw `("test", ...)` states to `_merge_flag_states`; they stay true, because the merge is unchanged, and their docstrings say the raw state no longer occurs from the lifter. Tests that expect `TEST_Z/TEST_NZ/TEST_S` text in generated C (grep `tools/recomp/test_*.py`) move to the `CMP_*` form.

Rejected:
- **Per-join conditions keyed on which edge was taken.** The edge would have to be recorded at runtime, which costs every block and every flag read.
- **Teaching `_merge_flag_states` a cmp/test mixed form that reads `TEST_*` or `CMP_*` depending on `_fb`.** That is the hack used in the spike's discarded experiment. It guesses from runtime values and fails for `cmp x, 0x100` joined with `test y, 0x100`.
- **Keeping kind `"test"` and letting the merge treat it as cmp.** The consumer would then emit `TEST_Z(_fa, _fb)` on one edge's temporaries and `CMP_EQ` on the other's; only a uniform snapshot (`_fb = 0` on both) makes one consumer right for both edges.

### D1b. Merge cmp states of different widths for the conditions that do not depend on width

After D1 every cmp and test is a `cmp` state, and the only thing that still separates two of them at a join is the operand width (`_merge_flag_states` refuses it "because sign/parity handling depends on them"). The snapshot already removes most of that dependence: `_fa/_fb` are masked to the edge's own width and `_fas/_fbs` are sign-extended from it. So on each edge, with that edge's own temporaries:
- ZF is `_fa == _fb` at any width (je, jne);
- CF and the unsigned conditions are `_fa < _fb` and friends on the zero-extended values (jb, jae, jbe, ja);
- the signed conditions are the int32 comparisons of the sign-extended values, which is exactly `a <s b` at the source width (jl, jge, jle, jg: `CMP_L(_fas, _fbs)` compares two int32s);
- PF is the parity of the low byte of `_fa - _fb`, and the low byte of a difference does not depend on the width it was computed at (jp, jnp).

What does depend on width is the sign bit of the difference (js, jns: `_sf_of_difference` picks the top bit of the width) and overflow (jo, jno). `cmp al, 0x80` against `cmp eax, 0x80` with al = 0x80 shows it: SF is 0 at 8 bits and 1 at 32.

So `_merge_flag_states` merges two cmp states of different widths into `("cmp_mixed", ops)`, and `_make_condition` answers it as it answers `cmp` for every condition except js, jns, jo and jno, which return None and keep the fallback. The mixed state also feeds `lahf`/`pushfd`, which probe per flag and so get SF and OF as "not modelled". `test_flag_join.test_mixed_widths_are_not_guessed` asserts the old refusal and is rewritten: the mixed join merges for `setne` and still falls back for `js`.

This goes in the same change because the sites it revives sit next to D1's in the same two functions, and because D3's before/after list keeps them attributable site by site. It is one new state kind and one table row in `_make_condition`.

### D2. Verify the wading fix before anything else

The spike could not do the A/B it wanted (a hand edit of `recomp_0028.c`, which CLAUDE.md forbids). The allowed way costs one regeneration and one headless run:
1. apply D1 in the toolkit worktree `wt/<name>/xboxrecomp`;
2. in `wt/<name>/cat`, with `XBOXRECOMP_CLI_DIR` pointing at the local `xboxrecomp-cli` checkout (the bootstrap cannot fetch the pinned CLI sha until it is pushed) and the toolkit resolved from `../xboxrecomp` (the worktree), run `blinx2 analyze` then `blinx2 recomp`, so the worktree's own `gen/` carries the fix;
3. Mac build, then `runs/stage1-water/scripts/warp7p.txt` on Metal, headless, with `RECOMP_DEBUG=pad_peek=0xCD24C4:1:x,0xCD24A0:1:x`.

Pass: the hit-stun byte stays 0 while wading and `[+0x84]` climbs without resets. Fail: stop and reopen the spike before touching goldens; the causal chain rests on the watchpoint stack and the lifted C, and this run is its only direct test.

### D3. Make the remaining fallbacks visible: a counted diagnostic, not an error

The translator keeps emitting `_flags` when no state can be known: a clobbered predecessor, a `popfd`, a real unknown. `recomp` now records each site it emits, with function, guest address, condition and the reason the state was lost (entry block, no predecessors, unknown predecessor, the kinds that met at the join, or the in-block setter that cannot answer the condition), to `analysis/recomp/flag_fallbacks.json`, counted unique by guest address so alias bodies do not inflate it. `summary.json` gets the totals; one summary line is printed, and the functions in the observed seed set (`"observed": true` in `config/seed_functions.json`) are listed by name, since a fallback there is the cheapest place to catch the next bug of this kind.

Why not a hard error: most sites sit in data decoded as code and in unreachable aliases, so a gate on the total can never pass, and the observed set (49 functions today) is too thin to be a correctness gate. The regression guard is the unit test for the merge shape plus this report, which TASKS.md tracks as a number. Why not a warning per site: 21k lines would hide the one that matters. The report is title-agnostic and goes upstream with the fix.

The report lands as its own commit, before D1, and runs once on the unchanged lifter. The difference between that file and the one written after D1 is the exact list of branches that come back to life, and D4 is built on it.

### D4. Risk management for the regeneration

Every function with a `test` gets different text, so the gen/ diff is large and mechanical. Behaviour changes only where a `_flags` branch becomes real. The rollout keeps those two apart:
1. **Mechanical check.** The gen/ diff, with the expected rewrites filtered out (`TEST_Z/NZ(_fa, _fb)` to `CMP_EQ/NE(_fa, _fb)`, `TEST_S` to `CMP_L`, `CMP_*(_fa & _fb, 0)` to `CMP_*(_fa, _fb)`, the snapshot lines and comments), must be empty apart from the resurrected branches. Anything else is a lifter bug.
2. **Resurrected branches.** The D3 before/after difference lists them by guest address; from the classification it is about 20 unique sites (3 from D1, 17 from D1b), so every one is read against the disassembly, not only the reachable ones, and the verdicts go in the change's notes. 0x000F7F7C and the three sites in `sub_00176150` must be in the list.
3. **BLiNX 2 goldens** on Metal (`blinx2 golden check`) and on D3D11 under Proton (`blinx2 bench golden`), stock resolution and frame rate. A moved golden is compared with xemu (`scripts/xemu_compare.py`) before it is re-blessed; a move toward xemu is re-blessed with the user's OK, a move away is a bug.
4. **Burnout 3 under Proton** (`b3/regen.sh` with the toolkit worktree, then boot and a race), per the upstream gate: this is an upstream-bound toolkit change. It runs on the Linux/Proton host under the run lock, BLiNX first, and is a merge gate for the toolkit commit, not for the cat commit.
5. **Bench**: flips/s and raster ms on Metal and D3D11 within the CLAUDE.md thresholds. The AND moves from the consumer into the snapshot, so the instruction count is unchanged and no change is expected.

### D5. Other join shapes, and which to touch now

From the classification (Context), the shapes that lose their state at a join are:
- **cmp + test, same width.** D1.
- **cmp/test, mixed widths.** D1b, for every condition but js/jns/jo/jno.
- **cmp or test + a result-writing setter** (`sub/add/and/or/xor/inc/dec/neg`, shifts; 20 sites, mostly MSVC's `and ecx` + `cmp` + `inc ecx` counted loop): `_merge_zero_flag` already merges two result setters on the same destination register. The cmp side is the obstacle: a result setter's ZF is `_fa == 0`, a cmp's is `_fa == _fb`, and `add`/`sub` and `inc`/`dec` use `_fb` for their source and for OF, so no snapshot expression is right on both edges today. A cmp against zero could be made to match by having the result setters write `_fb = 0`, which changes their snapshot shape and is a change of its own. Follow-up, with a TASKS.md entry.
- **Entry block (1,643 sites, 160 reachable):** cross-function flag inheritance at alias and boundary entries; the owner body already has the real condition. Whether any of these entries is ever taken is a question for `RECOMP_TRACE_ENTER` on the entry addresses, not for this change. Follow-up entry in TASKS.md.
- **Unknown predecessor, in-block clobber, no predecessors:** genuinely unknown or decoded data; the fallback is correct there. The result setters' missing `jo` arm (`add; jo` and friends, 34 sites) is cheap to add but has no reachable site; noted, not done.

## Risks

- **Hidden dependence on a branch that was always skipped.** A title path may have "worked" only because a branch was never taken, for example a wait that never waited. Making the branch real can expose a state that is wrong somewhere else. Mitigation: D4's list is read before the runs, then the attract demo, the stage 1 water room, the boot-to-menu and story goldens on Metal and D3D11; Burnout 3 boot and race under Proton.
- **An exactness slip in the AND operand.** A negative immediate (`test eax, -1`, capstone gives the signed value) or a sub-register read must mask to the operand width before the compare; the snapshot's `& MASK` does that, and the unit tests cover the sign bit and the mask at 8, 16 and 32 bits.
- **Code size and speed.** The AND moves from the consumer into the snapshot, so the instruction count stays the same. No perf change is expected; the bench check confirms it.

## Validation

- Unit tests (tools/recomp): cmp+test(reg, imm) joined, test(reg, imm)+test(reg, reg2) joined, test(mem, imm) at 8 and 16 bits, a mixed-width join that merges for je/jne/jb/ja/jl/jg/jp and refuses js/jns/jo/jno (with the `cmp al, 0x80` / `cmp eax, 0x80` case as the witness), every jcc family after a normalised test (je, jne, jb, jae, jbe, ja, jl, jge, jle, jg, js, jns, jp, jnp, jo, jno) checked against x86 semantics on edge values (0, the sign bit, the mask, a negative immediate), `cmp; jo/jno` on an overflowing pair, and the fallback report counting a known-unknown join once across an alias.
- BLiNX 2: D2's run; then the zone message still appears when the player stands in the zone and presses A (`[0xB8BD70]` goes 2→3→4→1 only on a press).
- Goldens and Burnout 3 as in D4.

## User decisions

1. Re-blessing a golden that moves toward xemu: the user signs off on each, as for every golden move.
2. The Burnout 3 Proton gate runs on the Linux/Proton host, so it waits for the user's go, like every Linux/Proton run; the cat merge can land before it, the toolkit squash to `posix-host/portability` cannot.
3. D5's follow-ups (the cmp + result-setter join, and whether the entry-block aliases are ever entered) get TASKS.md entries; the user decides when.
4. D1b widens the change beyond the bug's own shape. It is in because the revived sites sit in the player update and are attributable one by one; the user can ask for it to be split out, at the cost of a second regeneration round.
