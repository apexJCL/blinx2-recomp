## Context

The call chain at the crash, from the Mac native stack and gen/ (`spartan/tca` is not a repo, so files are named relative to `spartan/tca/src/recomp/gen/` as generated on 2026-10-14):

| guest VA | role | where |
|---|---|---|
| `sub_0019E740` | game init. It calls device creation `sub_0019D730` at 0x19E7A7, then the shader initialiser `sub_001B1590` at 0x19E7F8 | recomp_0041.c:39917 |
| `sub_001B1590` | static initialiser: 4 × (assemble, GetBufferPointer, CreatePixelShader, Release) | recomp_0044.c:942 |
| `sub_0025E96F` | XGAssembleShader, `ret 44`. It builds a 16-byte frame object and calls `0x0025E4B2` | recomp_0069.c:5134 |
| `0x0025E4B2` | the assembler body. **Not detected**, so it is a `g_esp += 4` stub | recomp_stubs_unresolved.c |
| `sub_00256DDB` | `XGBUFFER::GetBufferPointer`: `mov eax,[esp+4]; mov eax,[eax+4]; ret 4` | recomp_0069.c:5064 |
| `sub_002284B0` | CreatePixelShader (D3D). It reaches stub 0x2284CB | recomp_0069.c:2313 |
| `sub_0025A92C` | `XGBUFFER::Release`: decrement `[this]`, free at zero. It faults on this=0xFFFFFFFF | recomp_0069.c:5080 |

The caller is lifted correctly. Its out slots are `ecx = esp+0x14` → `[esp]` after the call (strings 1 and 2) and `ecx = esp+0x18` → `[esp+4]` (strings 3 and 4). Both match `sub esp,8` and the stdcall `ret 44`. No lifted instruction on this path is wrong. The bug is coverage.

### How coverage breaks

With `text_only = true` and no `extra_sections`, `tools.disasm` sweeps `.text` only (`Disassembler._get_target_sections`). Pass 4 (`_pass_call_targets`, tools/disasm/functions.py) takes `engine.get_call_targets()` once and, for each target in an executable section the sweep did not decode, calls `engine.decode_at`, which decodes linearly from the target to its first terminator. Targets in unswept sections therefore become functions only when `.text` calls them directly. The calls inside those bodies are never collected: the target set was snapshotted before the realignment, and `recursive_descent` reads only already-decoded instructions. Each such callee becomes an unresolved stub that pops the return address and returns, leaving eax and every out-parameter untouched. That is the right behaviour for a missed mid-function entry and the wrong one for a whole library.

### What the section table says

The flags do not separate code from data. Xbox images mark nearly every section executable, DOLBY and BLiNX 2's model sections included, and the "inserted file" flag is set only on `$$XTIMAGE`-style resources. What survives from the PE linker is the order: in all three XBEs the code sections come first (`.text`, then the libraries), `.rdata` and `.data` follow, and everything after `.data` is data the linker placed in the initialised-data group (DOLBY, Burnout 3's XON_RD, BLiNX 2's 57 model and motion sections):

| title | code sections before `.rdata` | executable sections after `.data` |
|---|---|---|
| Spartan | XMV D3D D3DX DSOUND XGRPH XPP | DOLBY |
| Burnout 3 | XMV DSOUND WMADEC XONLINE XNET D3D XGRPH XPP | DOLBY XON_RD .data1 |
| BLiNX 2 | D3D D3DX XGRPH DSOUND PSFD_I PSFD_B PSFD_P PSFD00 SRCADV SRCED SRCAC XPP | DOLBY DATED DATADV MDL* G* M* MOTPL … (57) |

DOLBY is byte-identical in the three XBEs (29,036 bytes, sha256 f0a884e7…): the XDK's APU DSP image, not x86. BLiNX 2's `extra_sections` is exactly its code-before-`.rdata` column.

### Measured on Spartan

Three disasm runs from the same XBE and seeds (`summary.json`; the stub counts are recomp's `unresolved_stubs`, with the "not detected" kind in brackets):

| | `text_only = true` (baseline) | six `extra_sections` (scratch copy) | `text_only = false` (runs/spartan/20261014-214121-text-only-false) |
|---|---|---|---|
| functions | 17,356 | 18,293 | 18,083 |
| .text | 17,232 | 16,565 | 16,410 |
| XMV / D3D / D3DX | 6 / 73 / 0 | 127 / 265 / 7 | 86 / 258 / 7 |
| DSOUND / XGRPH / XPP | 28 / 9 / 8 | 432 / 674 / 223 | 424 / 674 / 223 |
| DOLBY | – | – | 1 (`sub_0035E798`, 15 bytes, imm_ref_target, no callers) |
| tail_jump_alias | 1,370 | 770 | 559 |
| unresolved stubs | 168 (148) | 12 (12) | 12 (12), the same twelve addresses |

The two fixed runs differ only in aliases and the one DOLBY phantom. Burnout 3's own DOLBY phantom is the same shape (`sub_007708F8`, 15 bytes, imm_ref_target) and it builds and runs.

Direct call targets from the swept sections into unswept code sections, what D3 would print (measured with the toolkit's own `linear_sweep` and `get_call_targets`):

| run | targets into unswept code sections |
|---|---|
| Spartan, `.text` only | D3D 72, DSOUND 28, XGRPH 9, XPP 8, XMV 6, D3DX 1 (e.g. XGRPH 0x00255D64) |
| Spartan, either fix | none |
| BLiNX 2, its `game.toml` list | none (6,958 call targets) |
| BLiNX 2, the XDK names only | SRCADV 50, SRCAC 5, SRCED 3, PSFD_B 2 |
| Burnout 3, `text_only = false` | none by construction: every code section is swept |

### The alias drop

Adding sections removes `.text` aliases: 710 between the baseline and the six-section run, and 155 more `.text` ones (plus 56 in XMV, DSOUND and D3D) between that and `text_only = false`. Of the 711 removed in the first step, 707 lie inside a detected function in the new set, where the branch that made them is now intra-body. The other 4 (0x11485, 0x70187, 0x7048B, 0x96C9E) lie in `.text` gaps in both runs; three are junk decodes (`add ecx,[ecx]`, `add al,[edx]`, `add [ecx],eax`) and the fourth a `je` chain in a gap. No instruction in either run's `xrefs.json` jumps to them, nothing in the new gen/ names them and none is a stub. They are aliases registered in an early tail-jump round whose containing body the next rebuild moved, which `_alias_entries` never revalidates. The stub list being identical across both fixed runs shows the alias set they do not share is unreferenced. Task 2.3 records this against the new gen/; it does not gate the Spartan change.

## Decisions

### D1. The CLI default is `text_only = false`: every code section is swept

Decided by the user on 2026-10-14 ("go with text_only = false like b3; probably that should be the default always"). Three places change in `xboxrecomp-cli`:

1. `scaffold.py` `GAME_TOML`: `text_only = false`, with a comment along Burnout 3's lines: every code section, because without the XDK sections there are no function boundaries there; a title whose XBE flags data sections executable (BLiNX 2's model data) sets `text_only = true` and names its code sections in `extra_sections`.
2. `manifest.py`: `"text_only": (BOOL, False)`, so a manifest without the key sweeps everything too.
3. `docs/manifest.md`: the `text_only` row says the default is `false`, why it differs from upstream's README (`--text-only` makes a new title stub its libraries), and when to set it true.

Neither shipped game changes. BLiNX 2 sets `text_only = true` plus `extra_sections` and Burnout 3 sets `text_only = false` plus `extra_sections = []`, both explicitly, so `disasm_cmds()` builds the same argv and `gen.key.json`'s `argv` hash is unchanged (cat's is d0409a17…). No gen/ byte moves for either.

What `text_only = false` costs, and why it is accepted:
- **DOLBY** is swept as x86. Measured: one 15-byte phantom function that nothing calls, in Spartan and in Burnout 3 alike. No skip list and no `exclude_sections` key: the harm is too small to carry a mechanism for. If a title shows more, that is the follow-up, and the position rule below is the candidate.
- **BLiNX-class titles**, whose XBE flags tens of MB of model data executable, would get thousands of phantom functions and the old `cr7` build break (`loader.py`, `get_code_sections`). Such a title opts into `text_only = true` plus `extra_sections`, as BLiNX 2 does; the manifest doc says so, and the disasm summary's functions-by-section table makes a data section that was swept obvious.

Alternatives weighed:
- **An allowlist of known XDK section names**, written by `xbr new` from the section table. It misses title code outside `.text`: on BLiNX 2 it leaves PSFD_*/SRC* out, which `.text` calls 60 times (table above), so a new BLiNX-class title would still stub its middleware. Rejected.
- **A position rule**, every executable section before `.rdata`. It reproduces all three titles' code lists exactly (table above), DOLBY and model data excluded, because the linker groups code sections before initialised data. It is more machinery than the problem needs today, and it rests on linker order rather than a documented flag. Recorded here, not implemented.
- **Keep `text_only = true` with a better comment.** The default would still break every new title. Rejected.

### D2. Spartan applies the fixed default

`spartan/tca/game.toml` `[pipeline.disasm]` becomes `text_only = false`, with the scaffold's new comment, replacing the `text_only = true` line and its comment. This is what the fixed `xbr new` writes; it is applied by hand because `new` never rewrites a manifest and re-scaffolding needs an empty directory. The orchestrator applies it, since `spartan/tca` is neither a repo nor a worktree, and it can land before the CLI release: the CLI reads the explicit value either way. The `[cli]` pin moves to the release carrying D1 when that exists, so a re-scaffold would agree with the file.

Rejected for Spartan: the six-section `extra_sections` list. It was the first verified fix and gives the same twelve stubs, but it is a per-title list that the next title would have to rediscover, which is the bug being fixed.

Rejected in general:
- **Make `_pass_call_targets` iterate to a fixpoint.** That pulls reachable library code in without sweeping, with function ends guessed by `decode_at`'s run to the first terminator. Early-`ret` bodies and jump tables get cut short, which is worse than a clear stub.
- **Seeds in `config/seed_functions.json`.** Hundreds of seeds for one manifest line, and still incomplete.
- **Initialising the out slot or HLE-ing XGAssembleShader.** Hides the symptom and leaves eight D3D stubs on the boot path.

### D3. disasm warns about call targets in unswept code sections

In `_pass_call_targets`, a target whose section is executable, has raw data, is not in `DATA_SECTION_NAMES` and is not in the swept `sections` list is counted per section. After the pass, disasm prints one line per section:

```
  Warning: 9 call target(s) into unswept code section XGRPH (e.g. 0x00255D64); their callees will be stubs. Add it with --extra-sections XGRPH.
```

The behaviour is unchanged: the target is still realigned and kept as today, so BLiNX 2's and Burnout 3's gen/ and goldens do not move. The line goes to stdout with the other pass messages, which `xbr analyze` echoes. With D1 a new title never sees it; it is for titles that keep `text_only = true`, where a section added to the XBE by a later dump, or a middleware section the porter did not know about, would otherwise be stubbed silently. Measured: BLiNX 2 with its list prints nothing, Burnout 3 cannot print anything, and Spartan as scaffolded today prints six lines. The warning is title-agnostic and upstreamable.

Rejected: failing the analyze. A title may legitimately keep a section out, for example while bringing it up.

Known limit: the predicate is the one `loader.get_code_sections()` uses, so it cannot tell a data-like executable section (DOLBY, `$$XTIMAGE`, BLiNX 2's model sections) from code. A junk call target, a call operand decoded out of data, that lands in one of those would get misleading advice to add it with `--extra-sections`. Measured, it does not happen: Spartan's `.text`-only run warns only about its six library sections, BLiNX 2 with its list prints nothing, and Burnout 3 sweeps every section. If a title ever shows it, the position rule (D1, every executable section before `.rdata`) is the follow-up that excludes those sections.

## Validation

- **CLI:** `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`. `test_manifest.py`'s defaults assertion flips to `{"text_only": False, "extra_sections": []}`. New tests: a fresh offline scaffold's `game.toml` parses with `text_only` false and its `disasm_cmds()` carries no `--text-only`; a manifest without the key does the same; the two testdata games (`tests/testdata/game`, BLiNX-shaped, and `game2`, Burnout-shaped) build the same `disasm_cmds()` as before.
- **Shipped games:** `cat` and `b3` `gen.key.json` `argv` hashes are unchanged after the CLI change (the stage commands did not move), and `blinx2 analyze && blinx2 recomp` against the toolkit worktree produces no gen/ diff and no warning line.
- **Spartan, after D2 in the real `spartan/tca`:** `./tca analyze && ./tca recomp && ./tca build macos`. Counts SHALL match the `text_only = false` column: 18,083 functions, 12 unresolved stubs, 1 function in DOLBY. A headless run with `RECOMP_STUB_LOG=1` SHALL log no `[STUB]` line and no `[CRASH]`. The expected stop is the D3D pushbuffer wait in `sub_00228FA0` after flip 1, until the follow-up lands. Then the same exe on the Deck under Proton (Deck exes are built on the Mac and copied over).
- **Probe evidence** (scratch only, `runs/spartan/20261014-212043-extra-sections/`): `run5-baseline-probe` gives hr=0x00F7FEA8 and out=0xFFFFFFFF on all four strings (stubbed); `run4-probe` gives hr=0, a valid out pointer and size 240 on all four. The probe was a hand edit of a *scratch copy's* gen/ (marked `BLX-129 PROBE`) and is not part of any fix.
- **Toolkit:** `pytest tools/recomp tools/disasm`. The new test builds a three-section image (`.text`, XGRPH, and an executable `.rdata` as the data control) in which `.text` calls into XGRPH and into `.rdata`, and asserts one warning, for XGRPH only; its negative control sweeps XGRPH and asserts no warning. Also the Mac build and `tests/posix_ctest.sh` (0 FAIL).
