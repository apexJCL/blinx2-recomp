## D1. Refuse the start, not the instruction

There are two readings of an overlap between a body's instruction and the next start:
- the instruction is real and the start is a misread;
- or the start is real and the bytes before it are data that happens to decode.

`_find_function_end` tells the two apart. It marks the walk *suspect* after it skips a jump table or steps past a terminator, and clears that mark when it reaches a branch target inside the body. Only branches decoded outside the suspect stretches count as targets, so a branch read out of table bytes cannot clear the mark. The straddle counts only outside the suspect stretches. In the BLiNX 2 baseline:
- three straddles are byte index tables after a measured arm table (sub_000324C0, sub_00043BE0 and sub_00057040), and those starts are real;
- only sub_001CFCA0 straddles in code.

The start's own evidence also decides. A start probed as a prologue, or one that is the entry point or a seed, is kept even when crossed.

Either decode can be the wrong one, so the two starts are weighed against each other. A crossed weak start is refused only when:
- the crossing body's start is at least as strong (a prologue, entry or seed counts as strongest; otherwise the detection confidences compare); or
- no reachable code calls or jumps to the crossed start.

Reachable means recursive descent from the candidate starts and the measured jump-table arms. Descent stops at terminators and indirect jumps, so table bytes and data past a `ret` never vouch. A call from the start's own decode does not count either. This keeps a called FPO function that a weaker `cc_boundary` misread runs across.

In BLiNX 2, sub_001CFCA0 and 0x001CFCE8 are both call targets, so the start is refused on strength. Nothing reachable calls it: the phantom `call` sits in the table bytes after `jmp [ecx*4+0x1CE000]`. `disasm` names any detected body that still reaches a refused start ("refused start X is called from sub_Y"), since one of the two decodes is then wrong. BLiNX 2 prints none.

## D2. Short tables stay in the sweep

The direct cause is that the two-entry table at 0x001CE000 is decoded. One option was to accept a short table when an adjacent `movzx` loads a byte index table straight after it and every index uses an arm. That removed the phantom call. It also matched 60 two-entry tables in BLiNX 2: function count 11,758 to 11,994, with 252 new aliases mostly inside sub_0007A460 and sub_00176150, and the gen grew from 3.3 M to 8.9 M lines. The tables look real, but the alias growth needs its own look. That is a follow-up in TASKS.md, not part of a hang fix. The refusal in D1 removes the phantom start whatever decoded it.

## D3. Fall-off tails dispatch by address

A body that ends without a terminator and with no function at `end` was emitted as a plain return. That is wrong whenever the body is actually executed: x86 keeps running at `end`. The lifter now emits `g_seh_ebp = ebp; RECOMP_FALLOFF_TAIL(end); return;`. Off-section ends (and ends past the last code byte) emit nothing.

`RECOMP_FALLOFF_TAIL` dispatches like `RECOMP_ITAIL`: it reaches an alias or a function at `end` when one exists. On a miss it pops the return address, so esp stays balanced. It logs the address (`recomp_icall_fail_log`) once per site, because such a body usually runs in a loop. Most of these bodies are data decoded after a real `ret` and never run.
