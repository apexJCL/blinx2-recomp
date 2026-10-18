## Why

The tracker item: BLiNX 2 hangs at the second Tom Tom Gang rank exam (mgtu_tg). Run 5, an ABI-check build on the user's PC, logged an esp-short chain starting at sub_001CFCA0: each caller came back with esp four bytes low until sub_00062FB0 popped a return address (0x00063659) into edi.

The cause is in function detection:
- sub_001CDFB0 dispatches through a two-entry arm table at 0x001CE000 (`movzx ecx, byte [eax+0x1CE008]; jmp [ecx*4+0x1CE000]`).
- resync_jump_tables leaves tables shorter than three entries in the sweep. The table's second entry, 0x001CDFE8, decodes as `e8 df 1c 00 ..`, which is `call 0x001CFCE8`.
- 0x001CFCE8 is inside the 10-byte `mov dword [0xEC5340], 2` at 0x001CFCE1 in sub_001CFCA0. The phantom call target became a function start and cut sub_001CFCA0 there (end 0x001CFCEB).
- The lifted sub_001CFCA0 ends after `MEM32(0xEC5340) = 2;` with no return path through the rest of its code or its `ret`. Nothing told the lifter the body ran off its end, so the C function simply returned without popping the return address.

## What Changes

- **Analyzer (toolkit `tools/disasm/functions.py`):** `_build_functions` refuses a weak start (call target, tail-jump target, alias and so on) when the body in front of it decodes, as reachable code, an instruction that runs across it. The body is measured again without it. Strong starts stay: the entry point, seeds and any start whose bytes probe as a prologue. A start reached only after a skipped table or a terminator (data that decodes) also stays. Refused starts are kept in `mid_instruction_starts`, so later passes cannot add them back as candidates or aliases. `disasm` prints the refused list.
- **Lifter (toolkit `tools/recomp/translator.py`):** a body that runs off its end into code where no function starts now ends with `RECOMP_ITAIL(end)`. That reaches an alias at that address, or logs the miss loudly at runtime and pops the return address, instead of silently returning esp-short. `recomp` prints a WARN with the count.
- **Tests:** `tools/disasm/test_mid_instruction_start.py` and `tools/recomp/test_falloff_dispatch.py`.
- **Cat:** regenerated gen.

Not changed: the two-entry table itself stays in the sweep. Accepting short tables that a byte index table vouches for was tried (design D2). It fixed this case too, but it accepted 60 tables and added 252 aliases, which nearly tripled the gen.

## Impact

- **Toolkit:** `tools/disasm/functions.py`, `tools/disasm/disasm.py`, `tools/recomp/translator.py`, `tools/recomp/__main__.py` and the new tests.
- **BLiNX 2:** sub_001CFCA0 is whole again (0x001CFCA0-0x001CFE40) and sub_001CFCE8 is gone. The other gen changes are the ITAIL tails on bodies that run off their end (design D3).
- **Burnout 3 and the other titles:** the analyzer change only drops weak starts that a decoded instruction crosses. Those titles are a follow-up.
