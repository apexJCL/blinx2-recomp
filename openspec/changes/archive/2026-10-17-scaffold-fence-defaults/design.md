## Context

**The three lines, and what each gates in the runtime.**

- `RECOMP_VBLANK`. `kernel_vblank_enabled()` (`kernel_bridge.c`) latches `recomp_env(RENV_VBLANK) != NULL` on its first call, from the kernel timer thread; the two vblank schedules return at once while it is off. When it is on, `kernel_vblank_raise()` still delivers nothing unless the title has connected the NV2A vector (`KeConnectInterrupt`, `xbox_GetConnectedInterrupt`) *and* set the vblank bit in `PCRTC_INTR_EN_0`; until then it returns, saying once `vblank held: PCRTC_INTR_EN_0 off`. So for a title that never asks for vblanks, `RECOMP_VBLANK=1` costs a 60 Hz timer wake, the vblank counter line and `xbox_PacingVblank`, and delivers nothing. For an XDK D3D title it delivers what the console delivers: D3D connects the ISR and enables the interrupt during device creation, and its DPC is the title's frame clock. Note the `!= NULL`: today `RECOMP_VBLANK=0` turns vblanks *on*. BLiNX 2 has lived with that since its default landed; it matters now because a template default makes "unset" unreachable, so `=0` has to mean off (D3, last item).
- `RECOMP_TITLE_KEVENTS`. `ke_guest_event()` latches `*e == '1'` on first use and engages only for an object that has no `KeInitializeEvent` shadow and whose header reads as an event (type 0 or 1, size 4 dwords); it then creates a host event with the same type and state, says so (16 lines at most), and keeps `SignalState` in guest memory current. A title that initialises every event through `KeInitializeEvent` never reaches it. Upstream keeps it opt-in because a wait that failed at once now blocks, and a setter the runtime does not model turns a retry loop into a block; on the titles here the setter is the vblank DPC, which the first key supplies. The two go together: with vblanks on and kevents off, the DPC's `KeSetEvent` hands the guest address to the host as a handle and faults on POSIX (`runs/ITEM/r6-proto`).
- Both latch on first use, so both must be set before `xbox_kernel_init()` starts the timer thread: after `xbox_MemoryLayoutInit`, where BLiNX 2 and Spartan set them. `recomp_env_init()` has already run in the entry points, and the template includes `recomp_env.h`.
- `xbox_Nv2aMirrorFence(device_ptr, 0x2C, 0x30)`. The ack loop's `fence_mirrors_tick()` copies submitted (`[dev+0x2C]`) into the completed word (`*[dev+0x30]`) until the executor's releases land on that word, then steps aside and stays for catch-ups and `RECOMP_PB_EXEC=0`. `fence_completed()` reads the first registered device's completed word, and `pgraph_fence_tick()` puts its low five bits into PGRAPH `0x400B10` bits 2..6, which D3D's wait-for-idle polls. With no mirror registered, `fence_completed()` returns 0 and the register stays 0: Spartan's `r9` stop.

**The fence wait is the same code in all three titles.** The XBE's section table names the XDK libraries (`D3D`, `D3DX`, `XGRPH`, `DSOUND`, ...), and its library-version table names their builds. Scanning each dump's `D3D` section for D3D's fence wait, with the device pointer as the one wildcard:

| Title | D3D library | Section `D3D` match | Bytes | Pointer | `get_ptr_off`, `put_off` |
|---|---|---|---|---|---|
| BLiNX 2 | D3D8 1.0.5849 | one, at `0x002E8110` (`sub_002E8110`, the function `cat/src/main.c` names) | `56 8B35 <ptr> 8B4630 8B08 8B462C 8BD0 2BD1` | `0x002F1FB8` | 0x30, 0x2C |
| Spartan | D3D8 1.0.5849 | one, at `0x00228FA0` (`sub_00228FA0`, the tracker item's hang) | the same | `0x00235528` | 0x30, 0x2C |
| Burnout 3 | D3D8LTCG 1.0.5849 | one, at `0x00351770` (`sub_00351770`, `b3/docs/boot.md` step 3) | `56 8B35 <ptr> 57 8BF8 8B4630 8B08 8B462C 8BD0 2BD1` | `0x0035FB48` | 0x30, 0x2C |

The LTCG build takes the fence in `eax` and parks it in `edi` (`push edi; mov edi, eax`) between the pointer load and the field reads; otherwise the bytes are the same. The pointer is loaded in 105 to 149 other places per title (`mov esi, [ptr]` alone: 149 in Burnout 3), so the pointer cannot be told apart by how often it is referenced (in the disasm xrefs it ranks 173rd in BLiNX 2 and 93rd in Spartan among data targets); the fence wait can, and it carries the pointer. The scan reads the section once, with a regular expression, in well under a second.

## D1. The two defaults are template lines, not toolkit defaults

The template's `host_main` gets, after the `Xbox memory mapped` line and before the APU and `xbox_kernel_init()`:

```c
    /* The vblank interrupt, which the toolkit raises only on request. XDK
     * D3D connects the NV2A interrupt during device creation and paces Swap,
     * BlockUntilVerticalBlank and the title's vblank callback on its DPC;
     * without it the boot stops in D3D's first vblank wait. Nothing is
     * delivered until the title connects the ISR and enables the interrupt,
     * so a title that never asks for it only pays a 60 Hz timer. An explicit
     * RECOMP_VBLANK in the environment still wins (=0 turns it off). */
    if (!recomp_env(RENV_VBLANK))
        recomp_env_set(RENV_VBLANK, "1");

    /* D3D8 builds the KEVENT its vblank DPC sets inline, without
     * KeInitializeEvent. The toolkit gives such an event a host event only on
     * request (upstream's ke_guest_event); without it KeSetEvent hands the
     * guest address to the host as a handle, which fails silently on Win32
     * and faults on POSIX. The vblank above needs it, and it does nothing for
     * an event KeInitializeEvent made. An explicit RECOMP_TITLE_KEVENTS in
     * the environment still wins (=0 turns it off). */
    if (!recomp_env(RENV_TITLE_KEVENTS))
        recomp_env_set(RENV_TITLE_KEVENTS, "1");
```

**Why not flip the toolkit's defaults** (the `recomp_env.h` X-macro rows, so every title built on the fork gets them with no line at all). Four reasons, none of them CLAUDE.md's opt-in rule:

1. The rule does not decide this. "Opt-in features default OFF and never change stock behaviour" is about enhancements; these two keys are the other way round: *on* is the console's behaviour (the hardware always raises vblank; the kernel accepts an event built by hand), and *off* is the emulation shortcut. So the question is only where the fidelity default should live.
2. The toolkit's defaults for upstream's keys mirror upstream's. `RECOMP_TITLE_KEVENTS` is upstream's (#160, opt-in there for the reason quoted above), and the fork sends PRs upstream and has a Spartan comparison promised on #184. The two defaults the fork has flipped (`RECOMP_PB_EXEC`, `RECOMP_AC97_READY`) are the fork's own features, gated on a fault decoder; flipping an upstream key's default would give every PR and every comparison a hidden difference to explain.
3. The toolkit runs titles the fork does not test. Wreckless, Half-Life 2, MechAssault, Halo and the Dashboard boot on upstream's defaults; whether each one's first fault moves under kevents-on is unknown here, and the fork's evidence is three titles, all XDK 5849. The template is exactly the scope that evidence supports: every title the fork scaffolds from now on, with the line in the porter's own file, where the porting loop already tells them to put it, and where `=0` in the environment or deleting the line undoes it.
4. A line in `main.c` carries its *why*. A table default is invisible, and the next porter whose title stops in a vblank wait would not know the key existed.

**Future work, recorded, not done.** `kernel_vblank_raise()` already gates on the two things that mean "the title wants vblanks": a connected NV2A ISR and the enable bit in `PCRTC_INTR_EN_0`. A `RECOMP_VBLANK` auto mode that raises vblanks once both hold, with no key at all, would be the hardware's own rule and would retire the template line; it is a toolkit behaviour change for every title and belongs in its own change, discussed with upstream.

**Rejected: a `game.toml` key for environment defaults.** The manifest is pipeline and packaging configuration; a game's environment defaults live in `main.c` by design (the CLI reads `game.env_header` for the game's *keys*, not for values), and a key the CLI turned into generated code would be a second place to look for the same decision.

**What a title that does not need them gets.** From the Context: a 60 Hz timer wake and a counter line for vblank, nothing for kevents. The one real exposure is upstream's: a title that waits on an inline event whose setter the runtime does not model blocks instead of retrying. That title was not working either way; the symptom moves from a busy loop to a wait, and `RECOMP_TITLE_KEVENTS=0` is the A/B.

## D2. The fence line: a marked example in the template, filled by `xbr new` from the dump

**The template block**, right after `xbox_MemoryLayoutInit` and before the two defaults (the order BLiNX 2 and Spartan use):

```c
    /* D3D's GPU completion fence. XDK D3D keeps a pointer to its device in a
     * global; the device holds the fence it last submitted at +0x2C and, at
     * +0x30, a pointer to the word the GPU writes as it completes work. The
     * toolkit drives PGRAPH 0x400B10, which D3D's wait-for-idle polls, from
     * that word. With RECOMP_PB_EXEC on the executor writes the word itself
     * at each semaphore release and this mirror steps aside after the first
     * one; it stays registered as the catch-up path when a walk stops short
     * of PUT, and as the only fence when the executor is off.
     *
     * The pointer is the game's: 0x2F1FB8 in BLiNX 2, 0x235528 in Spartan,
     * 0x35FB48 in Burnout 3 (XDK 5849; the same two offsets in all three).
     * `xbr new` fills the line in when it finds D3D's fence wait in the
     * dump's D3D section; otherwise find it as the CLI's docs/porting.md
     * ("The D3D fence") says and replace the example below. The runtime's
     * "NV2A fence mirror: ... now written by the executor; mirror off" line
     * confirms it. */
    /* xbox_Nv2aMirrorFence(0x00000000, 0x2C, 0x30); */
```

The example is a comment, so a scaffold the CLI could not fill compiles and runs as today, and `template_main` keeps building it.

**The CLI's detection**, in `xbr new`, stdlib only:

- `xbe.py` grows two readers over the header it already parses: `sections(data)` (count at `0x11C`, header table VA at `0x120`, 0x38-byte entries: flags, VA, virtual size, raw offset, raw size, name VA; the name read at `name - base`) and `libraries(data)` (count at `0x160`, table VA at `0x164`, 16-byte entries: name, major, minor, build). Both tables sit inside the first 64 KiB on every XBE seen; when the header says otherwise the reader fetches the rest, the same way it fetches the section below.
- `find_d3d_fence(section_bytes, section_va)` returns `(wait_va, device_ptr, put_off, get_ptr_off)` for exactly one match of

  ```
  8B 35 <ptr:4> (57 8B F8)? 8B 46 <get:1> 8B 08 8B 46 <put:1> 8B D0 2B D1
  ```

  and `None` for zero or several matches. The two displacements come from the match, not from a constant, so a D3D build that moved the fields would report its own offsets; the `56` (`push esi`) before the pointer load is not part of the match (LTCG may schedule differently) but the function start is reported as the match minus one when that byte is `56`, for the comment.
- `new` reads the `D3D` section from wherever it read the header: the XBE file, the dump folder, or the disc image through `dump.Source` (the entry's sector plus the raw offset). With no `D3D` section it scans every section whose flags say executable, with the same exactly-one rule. The result is a note in the summary, one of:
  - `D3D fence: device pointer 0x00235528 (+0x2C submitted, +0x30 completed), from the fence wait at 0x00228FA0 in D3D8 1.0.5849; main.c carries the mirror line`
  - `D3D fence: not found (<reason>: no XBE read | no D3D section | no match in D3D | 3 matches in D3D); main.c keeps the commented example, see docs/porting.md "The D3D fence"`

  and, on its own line, the libraries: `XDK libraries: XAPILIB 1.0.5849, D3D8 1.0.5849, ...`. The library line is the one place a porter sees which D3D they have before the first run.
- **The patch.** `TEMPLATE_PATCHES` gains an entry for `src/main.c` whose `old` is the example line, whose `new` is `@FENCE_LINE@`, and whose hint is "add `xbox_Nv2aMirrorFence(0x..., 0x2C, 0x30)` after xbox_MemoryLayoutInit yourself". The patch is applied only when the fence was found; `FENCE_LINE` is then

  ```c
      xbox_Nv2aMirrorFence(0x00235528, 0x2C, 0x30);   /* from D3D's fence wait at 0x00228FA0 */
  ```

  When it was not found the entry is skipped, so an older template without the example line produces no `(the template changed)` note for it, and a found fence against such a template produces the hint, not an error. `test_real_template_patches_match` keeps reading the toolkit's real template, so the example line and the patch are checked against each other on every CLI test run; `FAKE_MAIN` in the scaffold tests gains the example line.
- **Tests** (`tests/test_xbe.py`, `tests/test_scaffold.py`): `sections` and `libraries` on a synthetic header; `find_d3d_fence` on a synthetic section with the D3D8 form, the LTCG form, no match, two matches (`None`), and a match with other displacements (reported, not forced to 0x2C/0x30); `new` against the fake toolkit with a synthetic XBE whose `D3D` section carries the signature (the live line, the summary note) and one without it (the example line stays, the not-found note names the reason); `new --offline` with no dump (the not-found note says `no XBE read`).
- **`docs/porting.md`, "The D3D fence"** (after "Environment and enhancements", before "macOS as a target"): what the line registers and why the fence wait hangs without it (one paragraph, the `+0x2C`/`+0x30` layout, the wait loop's shape); that `new` fills it from the dump and what its note says; how to find it by hand when it did not: in `analysis/disasm/asm/D3D.asm` (the XDK library section the disasm names), search for `mov eax, dword ptr [esi + 0x30]` followed by `mov ecx, dword ptr [eax]` and `mov eax, dword ptr [esi + 0x2c]`; the `mov esi, dword ptr [0x......]` just above is the device pointer; the three titles' values as worked examples; how to confirm at runtime (`NV2A fence mirror: device 0x... fence word 0x... now written by the executor; mirror off`, and `RECOMP_TRACE=sema` for the releases); what a hang in that function looks like under `sample` or the watchdog (a loop reading `[edx]` with no calls); and that the mirror stays registered for the catch-up and executor-off cases even though the executor writes the fence. The existing paragraph on `RECOMP_TITLE_KEVENTS` is rewritten: the template now defaults both keys, and the paragraph says what `=0` is for.

**Why the CLI, not the toolkit's disasm or the runtime.** The disasm runs at `analyze`, after the scaffold exists, and knows functions, not which one is the fence wait; teaching it D3D's library would be a signature database it does not otherwise need. A runtime scan of the loaded image would register the mirror with no line in the game, for every title built on the fork, which spreads a deviation the fork is trying to retire and hides a per-title decision the porter should see. `new` already reads the dump, patches the template and prints notes; the detection is thirty lines beside that.

**Rejected: identify `D3D__pDevice` by reference count.** It is the most natural guess and it does not work (Context: rank 173 and 93 among data targets).

## D3. PGRAPH 0x400B10 follows the executor when no fence mirror is registered

The shape D3 of `spartan-semaphore-ctxdma` fixed, placed in `fence_completed()` so that every reader of the completed fence sees it:

```c
static int fence_completed(uint32_t *out)
{
    for (int i = 0; i < g_fence_mirror_count; i++) { ... }   /* as today */
    /* No mirror registered: the executor's last released value is the
     * GPU's own copy of the last semaphore, which is what the register
     * means. A registered mirror whose device is not readable yet is not
     * this case: the register waits for it, as before. */
    if (g_fence_mirror_count == 0 && nv2a_pb_exec_semaphore_releases()) {
        static int said;
        if (!said++)
            fprintf(stderr, "  NV2A PGRAPH fence: no fence mirror registered;"
                            " 0x400B10 follows the executor's semaphore releases\n");
        *out = nv2a_pb_exec_semaphore_last_value();
        return 1;
    }
    return 0;
}
```

- **Condition.** `g_fence_mirror_count == 0`, not "no readable mirror": a title that registered a mirror before its device exists (Burnout 3 registers before device creation; the chain is bounds-checked per poll) keeps today's behaviour, the register waiting for the device. `nv2a_pb_exec_semaphore_releases() > 0` is the "executor has released at least once" test and already implies the executor ran, so no `s_pb_exec` term is needed (and the ctest, which drives `nv2a_pb_exec_method` directly, never starts the ack loop that sets `s_pb_exec`).
- **Never overrides a mirror.** With `g_fence_mirror_count > 0` the new branch is unreachable.
- **One log line**, at the first tick that engages it. `pgraph_fence_tick()` is unchanged: it writes bits 2..6 only when they differ and wakes the spin-wait.
- **A side effect to name:** the `[NV2A]` trace line (`RECOMP_TRACE=nv2a`) prints the completed fence from the same function, so a no-mirror title now shows the value where it showed `-`. No bench or golden reader parses that column (`grep fence` over the CLI's bench and golden code is empty).
- **Testability.** `pgraph_fence_tick()` is static inside the ack loop and takes the register block. It is lifted to an exported `void xbox_Nv2aPgraphFenceTick(void)` that fetches the aperture itself (`xbox_Nv2aAperture()`, the host mapping of guest `0xFD000000`) and is a no-op when the aperture is not mapped; the ack loop calls it where it called the static. The header comment names the ack loop and the ctest as its callers, as `xbox_VblankRaiseBits`'s does.
- **Ctest `tests/pgraph_fence`**, in-tree beside `pb_semaphore` (added from `src/d3d/CMakeLists.txt` in the same non-WIN32 block; CPU backend, no GPU, every POSIX host), the same synthetic XBE and layout as `pb_semaphore`, in this order because mirror registrations cannot be undone:
  1. no mirror, no release: the register, pre-set to `0x101` (bits outside 2..6), is unchanged after a tick;
  2. one release of 5 through `nv2a_pb_exec_method` (bind handle 8 as `pb_semaphore` does): after a tick bits 2..6 are `(5 << 2) & 0x7C`, bits 0 and 8 still set;
  3. a release of 7: the bits follow;
  4. `xbox_Nv2aMirrorFence(P, 0x2C, 0x30)` where the word at `P` is 0 (no device yet), then a release of 9 and a tick: the register still shows 7 (count is 1, nothing readable, no fallback, no override);
  5. the device is written (`[P] = D`, `[D+0x2C] = 3`, `[D+0x30] = W`, `[W] = 3`), tick: the register shows 3, the mirror, not the executor's 9;
  6. the log line appeared exactly once (capture stderr or count through a small hook; the exact mechanism is the implementer's).
  Negative control recorded in the notes: with the new branch removed, checks 2, 3, 4 and 6 fail and 1 and 5 pass. Check 4 expects the 7 that only the fallback wrote in check 3, and check 6 counts the fallback's log line, so both depend on the branch (`runs/ITEM/pgraph_fence-negative-control.txt`). The ack loop ticks on its first pass and then every 2 s, both from the same state, so the ctest's direct ticks stand for either.
- **`RECOMP_VBLANK=0` turns vblanks off.** `kernel_vblank_enabled()` uses `recomp_env_on(RENV_VBLANK)` (set, non-empty, not `0`), the helper the runtime already has. This is what makes the template's A/B possible (D1 writes "=0 turns it off" in the comment) and it is the only reading under which the key is a switch; no recorded run sets `=0`. It rides on this branch because it is runtime code and this branch runs the runtime gates. The Spartan A/B in task 4.5 is its check (no `[NV2A] vblank` lines, the boot stops in `sub_00226790` as `r8` did); a ctest would need the kernel timer thread, which no harness starts, so none is asked for.
- **No environment key for the fallback.** The A/B is against the base toolkit, as `r9` against `r10` was; a knob for a register that has one honest value would be a knob nobody should turn.

**In this change, on its own branch.** The orchestrator asked whether the fallback belongs here or in its own change. Here: the tracker item was filed for both halves, the spec is the place that states the condition, and the fresh-scaffold matrix (Verification) is the fallback's three-title run as much as the template's. On its own toolkit branch, because its gates differ: it is runtime code, so it runs the goldens and a Proton run, while the template branch changes no runtime code and runs only its ctest. The two merge independently, in either order; the CLI release waits for the template, not for the fallback.

## Verification

The Spartan scaffold matrix, all from one fresh `xbr new` scratch scaffold (tasks 4.1 to 4.5; `spartan/tca` is never touched). Headless Mac runs (`SDL_AUDIODRIVER=dummy`, perl `alarm`); Proton runs on the Deck with the Mac-built exe (memory note *deck-proton-bench*). The reference stop is the tracker item's: 4 flips, render targets created, the `KeDelayExecutionThread` poll under `sub_001ADCA0` (`runs/spartan/20261015-001139-ITEM-mac`, `-001343-ITEM-deck`).

| Run | Toolkit | `src/main.c` | Expected |
|---|---|---|---|
| fresh scaffold, as `new` wrote it | template branch + fallback branch | no hand edit; the live mirror line from detection | `NV2A fence mirror: device at 0x00235528`, `now written by the executor; mirror off`, no `PGRAPH fence` line, the reference stop, Mac and Deck |
| the mirror line commented out | the same | one edit, the comment | `NV2A PGRAPH fence: no fence mirror registered; 0x400B10 follows ...`, the reference stop, Mac and Deck |
| the mirror line commented out | template branch only (no fallback) | the same edit | stops in the wait-for-idle `sub_00228CE0` as `r9` did: the fallback's negative control |
| `RECOMP_VBLANK=0` | both branches | as written | no vblank lines, stops in the vblank wait `sub_00226790` as `r8` did: the `=0` and the vblank default's negative control |
| `RECOMP_TITLE_KEVENTS=0` | both branches | as written | the DPC fault as `r6` (SIGSEGV on the Mac): the kevents default's negative control |

Gate titles (the fallback branch only): BLiNX 2 `blinx2 golden` on Metal and `bench golden` on the Deck, Burnout 3's Mac boot; their logs show the mirror lines as on main and no `PGRAPH fence` line.

## Work split

- **Toolkit branch A, `feat/template-fence-defaults`** off `posix-host/portability` (b958798): the template block and the two defaults, the `template_main` text check. Gates: Mac build, `tests/posix_ctest.sh`.
- **CLI branch, `feat/new-fence-detect`** off `main` (a3208e4, v0.7.0): `xbe.py` readers and `find_d3d_fence`, the `new` patch and notes, `porting.md`, tests, version 0.7.1. Gates: pytest, ruff, `scripts/audit-public.sh`, noreply identity, no tracker ids. Coupled to branch A through the example line (`test_real_template_patches_match` reads the real template through `XBOXRECOMP_DIR`, which points at branch A's worktree during the work), so one agent, two worktrees.
- **Toolkit branch B, `fix/pgraph-fence-executor-fallback`** off `posix-host/portability`: `fence_completed`, the exported tick, `tests/pgraph_fence`, `recomp_env_on` for `RECOMP_VBLANK`. Gates: Mac build, posix ctests, the goldens and the Proton run above. Independent of A and the CLI; a second agent.
- The scaffold matrix needs A, B and the CLI together: the agent holding A and the CLI runs it once B's branch exists (B's tip, not its merge).
