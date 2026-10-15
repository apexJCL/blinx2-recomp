## Why

Spartan: Total Warrior (`spartan/tca`, a fresh `xbr new` scaffold, CLI v0.6.7, toolkit ac27175 = private 10d1611) crashes at boot on every host (Mac Metal, Proton, native Windows), before the first frame. The crash is a read of Xbox VA 0xFFFFFFFF in `sub_0025A92C+0x70` with esi=eax=0xFFFFFFFF and guest return address 0x001B16A3 (baseline `xbox-recomp/runs/spartan/20261014-210324-mac-metal-pinned/stdio.log`).

`sub_001B1590` is a static initialiser. It runs XGAssembleShader (`sub_0025E96F`, XGRPH) on four `xps.1.1` strings (.rdata 0x2AFF90, 0x2AFEA8, 0x2AFE48, 0x2AFD50). For each string it takes the buffer pointer (`sub_00256DDB`), creates a pixel shader into 0x354F40..0x354F50 (`sub_002284B0`, D3D) and releases the buffer (`sub_0025A92C`). The out-buffer is a stack local that is never initialised: `[esp]` for strings 1 and 2, `[esp+4]` for strings 3 and 4.

The working theory, a lifting bug that makes the assembler fail on string 3, is **refuted**. The assembler never runs:

- `sub_0025E96F` is a 52-byte wrapper. It forwards its 11 arguments and a 16-byte stack object to `0x0025E4B2`, the real assembler.
- `0x0025E4B2` is not a detected function. In `src/recomp/gen/recomp_stubs_unresolved.c` it is `void sub_0025E4B2(void) { RECOMP_STUB_HIT(0x0025E4B2u); g_esp += 4; /* not detected */ }`. With `RECOMP_STUB_LOG=1` the run logs `[STUB] unresolved 0x0025E4B2 reached, return 0x0025E99F` (`runs/spartan/20261014-212008-mac-stublog`).
- A probe in a scratch copy (`runs/spartan/20261014-212043-extra-sections/run5-baseline-probe`) called the wrapper on all four strings with the out slot preset to 0xFFFFFFFF. For every string "hr" came back as 0x00F7FEA8 (the wrapper's `lea eax,[ebp-16]`, left in eax) and the out slot stayed 0xFFFFFFFF. No string assembles and no HRESULT is produced. Strings 1 and 2 survive only because `[esp]` happens to hold a value the Release path tolerates. String 3 is the first to use `[esp+4]`, which holds 0xFFFFFFFF.

**Root cause: our own `xbr new` writes a disasm default that sweeps `.text` only.** `spartan/tca/game.toml` has `[pipeline.disasm] text_only = true` and no `extra_sections`. That is the scaffold template's text (`xboxrecomp-cli/src/xboxrecomp_cli/scaffold.py`, `GAME_TOML`, since 5605be2 on 2026-10-07), and `text_only` also defaults to true when the key is absent (`manifest.py`). The template's comment, "A title with code in its XDK sections names them, for example `extra_sections = ["D3D", "DSOUND", "XPP"]`", treats library code outside `.text` as a special case. It is the normal case: every XDK title links D3D, DSOUND, XGRPH, XPP and the rest into sections of those names, so the default breaks every new game. A function in an unswept section is lifted only when `.text` calls it directly (`_pass_call_targets` in `tools/disasm/functions.py` realigns those targets with `decode_at`), and the realigned bodies' own calls are never collected, so every callee of a library function becomes a silent `g_esp += 4` stub. Spartan's baseline has 9 XGRPH functions out of 129 KB and 73 D3D functions, and reaches 9 such stubs before the crash: eight in D3D (0x22C6A0, 0x22A8C3, 0x22CE90, 0x229250, 0x22A515, 0x22A305, 0x228110 and 0x2284CB, from CreatePixelShader `sub_002284B0`) plus 0x25E4B2.

Both games we ship opt out of the default by hand. Burnout 3 (`b3/game.toml`) sets `text_only = false`: "without the XDK sections there are no function boundaries there". BLiNX 2 (`cat/game.toml`) sets `text_only = true` with twelve `extra_sections`: the XDK libraries plus PSFD_*/SRC*, the title's own middleware code outside `.text`. Nothing in the pipeline reports the gap for a new title, and the upstream README documents `--text-only` as the normal invocation.

The fix is verified two ways on Spartan, both from a stub count of 168 (148 "not detected") and 17,356 functions:

- The six library sections named in `extra_sections` (scratch copy `runs/spartan/20261014-212043-extra-sections/`): 18,293 functions, 12 unresolved stubs, no stub reached with `RECOMP_STUB_LOG=1`, and the probe returns hr=0 with a 240-byte buffer for all four strings (run4-probe). The crash is gone.
- Every code section, `text_only = false` as Burnout 3 (`runs/spartan/20261014-214121-text-only-false/`, the same disasm, func_id, abi and recomp commands the CLI runs): 18,083 functions and the same 12 stubs, address for address. The only extra section is DOLBY, the APU's DSP image, which yields one 15-byte phantom function that nothing calls (design.md D1). The 210 fewer functions are tail-jump aliases that nothing references (design.md, "The alias drop").

The user decided on 2026-10-14: `text_only = false`, as Burnout 3, becomes the default everywhere. Boot then stops at a new place, covered in "Not in this change".

## What Changes

- **CLI (`xboxrecomp-cli`), the primary change:** the scaffold writes `text_only = false` with a comment saying why (without the XDK sections there are no function boundaries there); the manifest default for an absent `text_only` flips to false; `docs/manifest.md` says why the default differs from upstream's `--text-only`, and when a title still wants `text_only = true` plus `extra_sections` (design.md D1). Tests: a fresh scaffold and a manifest without the key both sweep every code section, and the two shipped games' stage commands do not change.
- **Spartan (`spartan/tca`, not a git repo):** `game.toml` gets the fixed default, `text_only = false`, by hand: `new` never rewrites a manifest and re-scaffolding needs an empty directory. Then `./tca analyze`, `./tca recomp`, `./tca build`. This is the crash fix for Spartan and it is the same line the fixed scaffold writes (design.md D2).
- **Toolkit (`tools/disasm`), defence in depth:** disasm prints a warning, once per section, when a direct call from swept code targets an executable, non-data section that was not swept. It names the section, the target count, one example and the `--extra-sections` name to add (design.md D3). It changes no output, so goldens and both games' gen/ are unaffected. It matters for titles that keep `text_only = true`, as BLiNX 2 must.
- **Tests:** the CLI tests above; a disasm unit test for the warning with a negative control in which the section is swept.

## Not in this change

- **The next boot stop.** With the libraries translated, Spartan runs past static init and logs one flip (a clear, 0 draws), then spins for good in D3D `sub_00228FA0`, reached through `sub_0019E740` → `sub_0019D730` → `sub_0022A290` → `sub_0022A250` → `sub_00229890`. That looks like the pushbuffer make-space/kick wait, and the first flip's PB-PERF line shows `kickwait 180.18` ms (`run2-sample/sample.txt`). It happens during device creation, *before* `sub_001B1590`, so the shader path itself is verified only through the probe. It is a separate bug and gets its own tracker item.
- **An XBE-derived section list in the scaffold.** Weighed and set aside in design.md D1; the position rule recorded there is available if a BLiNX-class title ever needs the scaffold to pick sections for it.
- **A skip rule for non-x86 sections** (DOLBY) under `text_only = false`. Not needed: the measured harm is one uncalled 15-byte phantom, and Burnout 3 has shipped with it. Reopen if a title shows more.
- No lifter change: no lifting bug was found on this path.

## Impact

- Spartan: the boot crash is fixed by one manifest line, and the next blocker is exposed.
- New titles: `xbr new` stops producing a project that silently stubs its XDK libraries.
- BLiNX 2 and Burnout 3: no generated-code change. Both set `text_only` explicitly, so the default flip does not touch their stage commands (`gen.key.json`'s `argv` hash stays), and the warning only prints. No goldens move.
- hgeorgilas' fork (`runs/upstream-spartan/spartan`, origin/spartan) runs Spartan to gameplay. Their toolkit has no reference to 0x25E96F, 0x25A92C or 0x1B1590, and their lifter differs from upstream 193e299 only in f39a24a (port I/O) and 0b42f0a (pop esp), both of which ours has. Their README (line 205) and docs/DECOMP.md tell users to pass `--extra-sections` or drop `--text-only`, which is consistent with this finding: their game project, which is not in the repo, must translate the library sections. Nothing of theirs is copied.
