## Context

An XBE section header has a virtual size (what the loader maps) and a raw size (what the file holds). The loader copies `raw_size` bytes and zero-fills the rest up to `virtual_size`. The linker sets raw size to the last non-zero byte, not the last instruction, so a section whose final instruction ends in zero bytes has a raw size that cuts that instruction. Spartan's D3DX section is such a case:

| | value |
|---|---|
| D3DX VA | 0x00237D40 |
| virtual size | 0x260 (ends 0x237FA0, where DSOUND starts) |
| raw size | 0x258 (file bytes end 0x237F98) |
| last instruction | `ret 0x10` = `C2 10 00` at 0x237F96..0x237F98 |
| bytes in the file | `C2 10` |

The section tables of the three titles (2026-10-15, from the headers): no section has `raw_size > virtual_size`, no two sections overlap in VA, and fills smaller than 14 bytes are common (Spartan's D3DX 8, BLiNX 2's D3DX 8 and its executable-flagged model sections 4 or 8; the large ones are D3D's 0x38C0 and XGRPH's 0xC7C). So `virtual_size` is the usual cap, the fill is always inside the section's own virtual range, and the page is never the bound.

The toolkit's two readers of guest code treat raw size differently:

- `tools/disasm/loader.py` `BinaryImage.get_section_data` returns exactly the file bytes. Every decoder in `engine.py` and `functions.py` works on that buffer. Capstone given `C2 10` decodes nothing, so 0x237EA5's body ends at the `leave` before it, and functions.json says `end 0x00237F96`.
- `tools/recomp/translator.py` `_read_func_bytes` slices the whole file from the function's file offset for `end - start` bytes. It reads past a section's raw end into the file's padding (zeros in practice), and `config.va_to_file_offset` returns None for any address at or past raw size. Two more places treat the raw end as the end of code: the coalesce request's "backed by one code section" test (`end <= section.va + section.raw_size`) and its `analysis_end`.

So the bound comes from disasm, and the lifter translates exactly the bytes up to that bound. The generated `sub_00237EA5` ends `esp = ebp; POP32(esp, ebp); /* leave */` with no return statement. In C that returns to the caller with the guest stack 20 bytes lower than the ret would have left it.

### How the stack error becomes "Couldn't find section ''"

`sub_0019F370` (the FE camera setup, `ecx` = 0x350200) has an aligned frame: `push ebp; mov ebp, esp; and esp, -16; sub esp, 0x114; push ebx; push esi; push edi`. Its epilogue pops edi, esi and ebx relative to esp, then `mov esp, ebp`. After the leaked call esp is 20 bytes low, so the three pops read the return address 0x0019F3B8 and two of the arguments (`ebx+0x150`, `ebx+0x1A0`). `mov esp, ebp` then repairs esp, which is why nothing crashes and `RECOMP_ABI_CHECK`'s "esp came back lower" test would not fire at that call (it checks esp, and the clobber shows only in the callee-saved registers).

The caller is the FE update `sub_0017F630`, which keeps the FE object in edi and ends:

```
eax = 0; ecx = [edi + 0xA4]; al = (ecx == 0)   ; 1 = keep updating, 0 = done
```

With edi = 0x0019F3B8 it reads the code bytes at 0x19F45C (`00 84 C0 F3`), which are non-zero, so it returns 0 on its first call. The section state machine `sub_000DC750` takes 0 as "done", runs the exit slot `sub_00182880`, which copies the real `[FE+0xA4]` (0, nothing selected yet) and asks `sub_000DC6E0` for section `""`, and the miss path is the fatal-error screen with its endless `Sleep(1000)`.

Measured, in order: `runs/ITEM/r1-lldb` (empty name on the guest stack, 24 sections loaded), `r3-bp` (the FE `LEVEL` action `sub_0017DAB0` never ran), `r7-exit` (`[FE+0xA4]` = 0 at exit), `r8-count` (one update call, then exit), `r9-edi` (the register trace through each call in the update, edi lost in `sub_0019F370`). The lldb scripts are in `runs/ITEM/scripts/`; guest registers are TLS, read by calling each symbol's TLV thunk from a breakpoint callback (`ITEM_cb4.py`).

## Goals / Non-Goals

**Goals:** the disassembler sees the bytes the loader maps, so an instruction cut by raw size decodes; nothing past the file end is decoded as code of its own; the lifter reads the same bytes; the shipped games move only where the cut actually splits an instruction; the next body that tears down its frame and falls off its end is named at generation time.

**Non-Goals:** emulating the whole zero tail as code; the unfiltered "function runs off its end" lint (Alternatives); the XPP seeds (separate item).

## Decisions

### D1. Section bytes carry a bounded zero fill; no instruction starts in it

`get_section_data(section)` returns the file bytes, and for an executable section with `virtual_size > raw_size` appends `min(virtual_size - raw_size, MAX_INSN_LEN - 1)` zero bytes (`MAX_INSN_LEN` = 15, the longest x86 instruction). That is the most an instruction starting at the last file byte can need.

The bound. `virtual_size` caps the fill because that is where the loader's zeros end; past it lies the next section (Spartan's DSOUND starts exactly at D3DX's virtual end) or unmapped memory, neither of which is this section's code. No next-section or page check is needed: the section tables do not overlap, so a fill that stays below `virtual_size` stays inside the section. A section with `virtual_size <= raw_size` gets no fill and is read as today; none of the three titles has one, and an XBE with `raw_size > virtual_size` is a loader question, not a decoder one. A cut instruction that needs more bytes than the fill holds (Spartan's D3DX has 8 spare, so a `ret` fits, a 15-byte instruction would not) stays undecoded, which is right: on hardware it would read into the next section, and no linker emits that.

The fill must only finish instructions. `engine.py` gets a helper `_file_end(section, data)` (VA of the end of the file bytes, `min(raw_size, len(data))` for the test doubles that have no raw size), and:

- `linear_sweep` loops to the file end, not `len(data)`, and breaks out of capstone's stream at the first instruction whose address is at or past it;
- `decode_at` refuses a start at or past the file end, and stops its stream there the same way.

These are the only two places that insert into `engine.instructions`. The other readers of `get_section_data` only test bytes and never insert: the prologue-shape and terminator helpers in `engine.py` decode zeros as `add [eax], al`, which is neither a prologue nor a terminator, so their answers do not change; the prologue and CC-padding passes in `functions.py` match nothing in zeros and only add candidates at addresses already in `engine.instructions`; `labels.py` reads `.rdata`, a data section. The `_file_end` docstring says so, so the next reader does not have to re-derive it.

One clamp does change. `functions.py` `_build_alias_entries` bounds a gap alias (a tail-jump target with no enclosing body) at `virtual_addr + min(virtual_size, raw_size)`, so that it does not run into the next section. That is the raw end, and an alias into a function that ends in a cut instruction would lose the same `ret` D1 restores. It bounds at `virtual_addr + len(get_section_data(section))` instead: since no instruction starts in the fill, that bound admits at most the straddling instruction.

Without the "no start in the fill" half, the first version of the prototype (e4e5315 alone) grew BLiNX 2's phantom `sub_00330162` through 13 bytes of `add [eax], al` (0x33131A → 0x331329). With it (762fe10) the phantom gains only the straddling 3-byte instruction (→ 0x33131D). That 3-byte move is accepted rather than special-cased: `36 00 00` is what the hardware would execute at 0x33131A, the decoder has no notion of "real" functions, and a rule that completed instructions only for functions ending in an epilogue would be a heuristic layered on a fact.

### D2. The lifter reads zeros past raw size

The lifter gets one notion of a code section's readable end, `raw end + min(virtual_size - raw_size, 14)`, next to `va_to_file_offset` in `config.py`, and three places use it:

- `Translator._read_func_bytes(start, end)` builds the body from the owning section's file bytes and zero-fills from the raw end to `end`, rather than slicing the file. An `end` past the readable end is unreadable, and the function is skipped the way an unreadable body is today (`None`), after one message naming the function and the section; D1 never produces such a bound, so the message means a manual seed or a coalesce request is wrong.
- The coalesce request's "extent is not backed by one code section" test and its `analysis_end` accept an `end` up to the readable end, so a request for a function that ends in the fill is not refused for the one byte the loader supplies.
- `va_to_file_offset` is unchanged: a start in the fill is still not code.

On the three titles D2 changes no generated byte: in all three XBEs the 14 file bytes after every code section's raw end are zero (`runs/ITEM/scripts/padcheck.py`), and task 2.4 checks the generated output. It removes the remaining ways the two readers could disagree.

### D3. A frame teardown that falls off its end is reported

`translate_function` already computes `continues_past_end` (the last instruction is not a terminator) and `fallthrough_target` (the function that starts at `end`, when one does). When the first holds, the second is None, and the last instruction is `leave` or `pop ebp`, it prints one warning naming the function, its last instruction and the owning section's raw end. Those two instructions tear a frame down and in compiler output only ever precede a `ret`, so a body that ends in one without a terminator is a cut body, not data. Measured on the generated C of the three titles (last statement `POP32(esp, ebp)` or `esp = ebp`, `runs/ITEM/scripts/falloff.py` with the epilogue filter, 2026-10-15): 0 in Spartan after the fix, 0 in BLiNX 2, 0 in Burnout 3; the pre-fix `sub_00237EA5` (`esp = ebp; POP32(esp, ebp);`) is the one body it would have named. A warning, not an error: a title whose seeds produce such a body still generates, and the gate is that the three titles produce none.

### D4. Where the evidence for "no other title is affected" comes from

A/B disasm of each XBE with the base toolkit (b958798) and the prototype, the games' own seeds and section flags, outputs under `runs/ITEM/disasm-ab/` (`fdiff.py` compares bounds):

| title | functions | bounds changed |
|---|---|---|
| Spartan | 18,083 | 1: 0x237EA5 0x237F96 → 0x237F99 |
| BLiNX 2 | 18,670 | 1: 0x330162 0x33131A → 0x33131D (phantom, string data in XGRPH) |
| Burnout 3 | 24,000 | 0 |

A linear-sweep survey of every executable section's tail (`runs/ITEM/scripts/tailcheck.py`) finds many "instructions" crossing raw ends, but in data; only Spartan's D3DX tail is a real instruction. The function bound diff is the test that matters, because only a function bound feeds the lifter. The A/B is repeated on the implementation branch once it carries the alias clamp and sits on the current head (b53cb78), since `posix-host/portability` moved after the prototype was cut.

## Alternatives

- **Pad the full virtual size.** Zero tails of up to 0x38C0 bytes (Spartan's D3D) would be swept as `add [eax], al` chains. Rejected (D1).
- **Patch only Spartan, by seeding a manual function or an end override.** Fixes the symptom; the next title with the same linker output fails the same silent way.
- **The unfiltered lifter warning for bodies that run off their end.** 55 in Spartan's gen/, 1,358 in BLiNX 2's, 34 in Burnout 3's, nearly all phantom functions over data. Rejected as noise; D3 is the filtered form, which is silent on all three.
- **`RECOMP_ABI_CHECK` builds.** They check ebx/esi/edi around each call. Here they would have flagged `sub_0019F370`'s callers, one level above the cause, and require a full rebuild. The register trace in `r9-edi` reached the same place without one.

## Risks

- **BLiNX 2 gen/ moves in one phantom function.** `sub_00330162` is string bytes in XGRPH. Nothing calls it at run time as far as the dispatcher logs show, and the added statement is one more `add` it never executes. The goldens on Metal and D3D11 decide.
- **A title whose fill holds a jump table or data the sweep must not see.** The fill is at most 14 bytes and no instruction may start in it, so the worst case is one instruction completed with zeros. That is what the hardware executes.
- **cat's committed gen/ lags the toolkit.** Until the pin moves, `cat/src/recomp/gen/` is generated by blinx2-v0.3.1 and the scratch regeneration is the only tree with the 3-byte move. That is the existing arrangement for every toolkit change between push rounds.

## Hosts

Generation only. No runtime, renderer, audio or kernel file changes, so no Proton runs are needed for the toolkit change itself. Spartan's rebuilt exe and the BLiNX 2 D3D11 golden still run on the Deck (standing in for the Linux/Proton host), because gen/ moves in both titles.
