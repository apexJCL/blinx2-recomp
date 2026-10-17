# Design: upstream v0.14.0 sync decisions

Toolkit `merge/upstream-v0.14.0`: merge b87b386 (parents 70c4371, eb0aa1d; merge base
193e299), recomp_env aliases 36c4aa4. cat `merge/upstream-v0.14.0-cat`: env.md rows, this
change. The per-file resolution log, with every hunk pick, is `wt/up14sync/notes/decisions.txt`
(copied to `notes/up14sync/` after the merge).

Most of the 98 upstream commits merged cleanly. About a third of them are our own PRs as
upstream reviewed them (10c4a31d, ba81c34d, 0fd8b4cc, ae11965f, 46aee91e, the APU series):
there the conflict is the review wording and small review fixes against the fork's
original, and the review fixes are taken.

## Same problem, fixed twice

| problem | kept | why |
|---|---|---|
| KeWaitForMultipleObjects on title-built KEVENTs | **upstream** (Vlad's f775a5a3, `ke_guest_event_prepare`, per-index `event_types`) | Same semantics as the fork's inline `guest_sync`/`n_sync`; upstream also uses the helper in KeWaitForSingleObject. Upstream first. |
| Keyboard and mouse as a virtual pad | **ours**: the fork's layer (`RECOMP_KEYBOARD`, `RECOMP_MOUSE`, runtime bindings, capture state machine, F9 release, enhance TOML) | Upstream #205's `RECOMP_MKB` (mkb_input.c, Win32 raw input only, its own `RECOMP_MKB_*` knobs and mkb.ini) duplicates it; the fork's runs on SDL/POSIX too. Two knobs for one feature is what the policy avoids, so mkb_input.c/.h are removed. **Upstream PR candidate.** |
| Missing game-file report switches | **ours** (`RECOMP_TRACE=missing`, `RECOMP_DEBUG=missing_list`, 4096 slots) with upstream's names as aliases (36c4aa4) | Upstream's `RECOMP_MISSING_FILES[_LIST]` are raw-getenv spellings of the same report (our 10c4a31d PR). Values mean the same, so the old names alias. |
| Guest window reservation on Windows | **ours**: always one 4 GB placeholder (`win_reserve_guest_window`) | Upstream gates it behind `RECOMP_WIN_PLACEHOLDER` (opt-in, tested under Wine only). The fork runs it by default on every Proton and native Windows golden since 819c96e. **Upstream PR candidate.** |
| Contiguous arena reuse | **ours**: freed blocks always reused | Upstream gates reuse on `RECOMP_HEAP_RECLAIM`. BLiNX 2 exhausted the arena without reuse (v0.13.1 design: 64 MB exhausted vs 24.9 MB peak). **Upstream PR candidate.** |
| E:\CACHE routing | **ours**: TitleCache rule, `match_rule` boundary check for every rule | Upstream's `rule_match` is the same check limited to save rules. Upstream's "saves already in <game>/UDATA stay there" is taken; its `USER_RULE_SLOT` would have sent TitleCache to the TDATA slot, so it became `user_rule_in_game()`. |
| VBlank tick | **ours** (clock, schedule, ack machinery) | Upstream's simple `kernel_vblank_tick` is the subset of our 46aee91e PR; the fork's tick already counts `g_vblank_total` once. |
| Duplicate ApuIrqStats/irq stats line | **ours** (superset: posted, holder_delivered, se_frames, fe_trapped_frames) | Same struct, fewer fields upstream. |
| SDL framebuffer window | **ours** | Upstream's copy is our older a1862e0f/eb1758f2; `xbox_FramebufferWindowSetAA` added as a no-op, as in c659c356. |
| recomp_exit_hook | **ours** (inside recomp_env, `recomp_exit_hook_add`) | Upstream builds it as its own target; the fork's mouse clip needs the add form. |
| Executor `never divide by w` (LeandroSSB 0ca09473) | **ours** (9879d328) | The fork's executor covers it. |

## Upstream review fixes taken (theirs)
- APU: GPRST gate pausing the `=auto` DSP ack, per-poll doorbell re-read, reset clears
  `s_gp_in_reset`; pace step device-queue stall fallback (`pace_stalled`,
  `mcpx_apu_pace_rendered`; the fork's xa2 submit skips while stalled); XGSCNT
  `sample_count`, SSL tick (ISTS bit 3); WAV deadline against the clock; SDL buffer clamp.
- Kernel: `NtFreeVirtualMemory` as `bridge_free_guest_pages` (a release inside a block is
  refused with STATUS_FREE_VM_NOT_AT_BASE, decommit clamped to the block); ContiguousClaim
  claims each still-free run; FATX overwrite mark cleared on a reused HANDLE; comment
  wording without internal refs.
- Platform: arm64 decoder (unsigned shifts before sign extension, LDP Q/opc 3 and STGP
  rejected); OHCI 8-byte split on the Win32 decoder; win32_compat `RegionSize` at address 0;
  libm and `_GNU_SOURCE` on Linux; link group under GNU ld.
- Lifter: sahf/fcomi/fprem, lock xadd flags, FCMOVcc, MXCSR rounding, neg, parity readers,
  COMISD lanes, x87 tbyte; trig in the pr-186b form (upstream gate + pi66 helpers).
  Fork-only kept: `recomp_pushfd(known, bits)` and the g_eflags lifter for pushfd/popfd/cpuid,
  the translator's section clamp, port I/O tests.
- Disassembler: NoRain211's callback and tail recovery series, in the up14/pr-186b design
  (probe-only data pointers, no budget walk, no `--data-ptr-*` flags); the fork's
  `_pass_branch_alias_closure` stays (cat needs it).
- Tests: new upstream dirs (apu_dsp_ack, kernel_directory_posix, win32_compat_posix,
  win32_thread_posix) build in the POSIX ctests; proton_run.sh takes upstream's batch file
  and quoting and keeps the `HLSL_*` passthrough.

## Not ported (fork follow-ups in TASKS.md)
The fork's pushbuffer executor (Metal and D3D11 behind `nv2a_pb_state.h`) has diverged by
about 6,800 lines from upstream's, so nv2a_pb_exec.c and nv2a_pb_scan.c are the fork's.
Not taken from #162 / 53f49ad7 / 1d050ac6 / 19ef9f0a / 27c95f49: the render back-end
interface (`nv2a_backend.h`), fixed-function T&L, anti-aliased surfaces, the opt-in DMA
walk (`RECOMP_PB_WALK=dma`, with `xbox_Nv2aFenceWordVa`, `AckBusyBits`, `RegPtr`), and
`RECOMP_VSH_DUMP`. Their tests (nv2a_ffp_backend, nv2a_pb_walk) are removed with them.
The fork's executor answers the same titles through its own paths; whether the FFP T&L or
the DMA walk helps a title the fork does not run yet is a separate assessment.

## Semantic conflicts found after the textual merge
- apu_state.h: the auto-merge declared `monitor_frame`/`pace_step` and the ApuStarve
  typedef twice (build error); one copy removed.
- xbox_memory_layout.c: the auto-merge kept two `xbox_Ac97PosixFault` definitions (kept
  upstream's, which checks mprotect), two `apu_wav.h` includes, a stale `get_written = put`,
  a doubled `heap_forget_ram_names`, and turned the fork's two-argument `nv2a_pb_scan`
  extern into upstream's one-argument form. Upstream's `(void)s_ac97_stepping` lines name a
  Windows-only static and broke the POSIX build; dropped.
- kernel.h: upstream's copy of the fork's `xbox_path_tree` block auto-merged as a second
  definition; removed.
- kernel_bridge.c: the `[CONTIG] refused` block existed on both sides and would have doubled.
- Raw getenv: no new raw `getenv` outside recomp_env in src/ and templates/ (3 before, 3 after).
- Env knobs: every upstream switch in v0.14.0 already has a fork row except the two
  missing-file names (now aliases) and the features not ported (no rows needed).

## Disassembler speed (76ae8e6, c3cc70c)
Upstream's data-pointer pass proves each data-table target callable by walking its CFG
(`_probes_as_tail_body` → `probes_as_callback_body` → `disassemble_cfg`), with no budget.
On the merged toolkit that took Burnout 3's disasm from 21 s (70c4371) to 871 s, and
BLiNX 2's from 30 s to over 35 minutes (never finished). Two exact fixes, both with
byte-identical functions, labels, xrefs and summary output:
- 76ae8e6: the pass memoises each tail proof on (entry, upper bound, frame flag, the
  entries the walk proved), and skips targets inside a known function that are not
  instruction boundaries before probing. BLiNX 2 runs the same chains through its 90 KB
  body at 0x176150 thousands of times. B3 871 → 793 s, BLiNX 2 → 1,455 s.
- c3cc70c: capstone's `Cs.disasm(code, addr)` decodes the whole buffer, with detail,
  before it yields the first instruction, and every probe passed the rest of the section.
  `disasm_lazily` decodes 32 instructions at a time; the engine's four walks use it.
  B3 → 58 s, BLiNX 2 → 633 s.
The rest is the per-target CFG proofs themselves; matching 70c4371's speed means a
budget or a cache across passes, which changes upstream's design, so it is an upstream
follow-up, not done here.

Upstream's proof also keeps fewer data-table aliases on BLiNX 2: 2,535 against 15,947 on
70c4371, and 11,752 functions against 26,180 (the 14,429 only-base entries are
`tail_jump_alias`). Whether BLiNX 2 needed those aliases is what the goldens below answer.

Decode cache (9bdc359): the profile after c3cc70c showed 99,990 CFG decodes re-decoding
35.8M instructions, 650 s of a 1,146 s profiled run. One address -> Instruction cache is
shared by the probes, and an entry is reused only where the buffer holds the same bytes.
Checked on both titles (runs/up14sync/time-cache.sh): functions, labels, xrefs and summary
are identical with and without it, and BLiNX 2's regenerated gen is identical to the
pre-cache gen. Disasm BLiNX 2 633 → 126 s, B3 58 → 45 s, peak RSS about 1.8 and 1.9 GB.
Kept. This supersedes the note in 9bdc359's commit message (output identity still to be
checked, revert if it differs): the output is verified identical. The message stays as
written, because the branch has merges after it and must stay fast-forwardable.

## Integration tip
posix-host/portability f79c201 (nv2a clear rect, near clip, border colour) merged in as
5319027 with no conflicts: it touches only the fork's executor and back ends, kept as ours above.
posix-host/portability 06e87d1 (BLX-164, APU voice hold) merged in as b6589fb, also clean;
the duplicate NV1BA0_PIO_SET_SSL_SEGMENT_* defines in apu_regs.h predate it and are identical.

Burnout 3 base: burnout3-recomp f7baab9 (the reworded history's name for the same tree
as 4c85e50).

## Function-set reduction (26,180 → 11,752)
Checked from files and logs only (functions.json, xrefs.json, gen, golden logs).

The drop is 14,449 starts, and 21 are new. 14,429 of the dropped starts are
`tail_jump_alias`; the rest are 11 `cc_boundary`, 3 `imm_ref_target`, 3 `gap_prologue`
and 3 `tail_jump_target`. 14,249 of them fall inside a merged function's body, so their
code is still lifted. 200 (82 KB) fall outside every merged body, so they are not lifted.

1. Seeds: all 49 entries of config/seed_functions.json (30 observed) are functions in the
   merged functions.json and are defined in gen. 0x0009D970 (observed) is now detected as `prologue` instead
   of `seed_vtable_thunk`. None is lost.
2. Calls into dropped code: no `call` xref reaches a dropped start. Other references from
   kept functions into dropped starts:

   | Reference | Target interior to a merged body | Target outside every merged body |
   |---|---|---|
   | `jmp` | 11 | 2 |
   | `jcc` | 68 | 8 |
   | Immediate (`data_imm`) | 43 | 11 |

   - The sampled jumps lift as local `goto loc_*` in the owning function (for example
     0x002CFF6A in sub_002CF587); they need no entry.
   - Immediates into outside starts (possible callbacks with no lifted body): 0x00235730
     (469 B), 0x0032E7C0, 0x0032E7C8, 0x00339650, 0x0033CED0, 0x0033D0B0, 0x0033D0E0,
     0x0036E924, 0x0005E410, plus 0x00040368/0x0004036C, which look like constants.
   - The analysis records no indirect-target table, and jump-table entries are not in
     xrefs.json, so dropped entries reached that way are not counted here (0x002DA624 is
     one).
3. Runtime evidence. Base logs no `[ICALL]` failures. Merged logs these on every run:

   | Run | 0x002DA624 | 0x0005E410 |
   |---|---|---|
   | Metal attract | 2,951 | 1 |
   | Metal stage1 | 24,787 | 1 |
   | Metal story | 2,462 | 2 |
   | CPU attract | 2,863 | 1 |
   | CPU stage1 | 11,463 | 1 |
   | CPU story | 2,466 | 2 |

   No other merged-only VA appears, and no miss or unresolved lines appear.
   - 0x002DA624 (`fstp st0; fstp st0; fldz; ret`) is a CRT x87 helper entry reached through
     `jmp [ebx]` at 0x002DA611. Base had it as a 7-byte `tail_jump_alias`; merged starts at
     0x002DA626 instead.
   - 0x0005E410 is the body of a worker thread: thread routine 0x002980E7 receives it as the
     PsCreateSystemThreadEx ctx and calls it. Base had it as a 176-byte `cc_boundary`, with
     immediates from 0x0005E39F, 0x001E0237 and 0x001FD994.

   Both are real code that the merged analysis lost, which makes this a real gap even though
   the goldens pass.
4. Which upstream change drops them is not proven. The candidate named first was c0dc1f9c
   (NoRain211, "fix(disasm): tighten entry proofs and seed trust from review"), whose message
   reports a DOA3 x87 case that resembles 0x002DA624. A revert of c0dc1f9c alone on the
   merged toolkit (scratch branch scratch/up14-revert-c0dc1f9c, 614cbef4 on b6589fb1; disasm
   only, pre-seed seeds) gives 12,147 functions against 11,752 at the tip, and neither VA is
   an entry in either run (runs/up14sync/bisect-c0dc.out, bisect-{tip,revert}/). So
   c0dc1f9c is not what drops them. The remaining suspects are the pr-186b probe-only
   data-pointer walk (`_pass_data_ptr_targets`) and the other v0.14.0 disasm commits,
   8c54af7c ("reject non-callable interior table entries") first. This text says "v0.14.0's
   entry proofs" until a bisect names the commit.

Fix (game side, no toolkit change; the documented path for missed functions): seeds in
config/seed_functions.json.
- Observed: 0x002DA624 and 0x0005E410.
- The eight starts that kept code points at, judged on 70c4371's decode:

  | Start | Verdict | Reason |
  |---|---|---|
  | 0x00235730 | seeded, unobserved | stored as a callback at obj+0x9C beside two other code pointers; a 469-byte body ending `pop ecx; ret` |
  | 0x0033CED0, 0x0033D0B0, 0x0033D0E0 | seeded, unobserved | atexit destructor thunks (`mov ecx, obj; jmp sub_00348580`), each pushed to sub_002D5678 by a static initializer |
  | 0x0032E7C0, 0x0032E7C8 | not seeded | ASCII text decoded as code (`outsd`, `add [eax], al`) |
  | 0x00339650 | not seeded | data (`add [eax], eax` runs) |
  | 0x0036E924 | not seeded | the string `\Device\MU_0` |

  0x00040368 and 0x0004036C are skipped as plain numbers.
- Result (cat 6d7ff1d, toolkit b6589fb):
  - Analyze, recomp and the macOS build pass, giving 11,758 functions. All six seeds are
    defined in gen.
  - Metal goldens pass with 0 `[ICALL] Failed to resolve` in every scenario (13 to 24,788
    before the seeds). Flips/s: story 53.1, attract 46.1, stage1 33.9.
  - cat-win builds (37 MB exe) for the Deck goldens.
  - Logs: runs/up14sync/gate-seeds.out, golden-metal-seeds-*, cat-pipeline-seeds.log,
    cat-win-seeds.log.
- Upstream issue draft: notes/upstream-v0.14.0-entry-proofs.md (untracked, not filed; bisect
  the cause before filing).

## Gates
Filled in tasks.md.
