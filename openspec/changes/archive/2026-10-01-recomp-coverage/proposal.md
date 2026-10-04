## Why

BLiNX 2 boots past XAPI initialization and then crashes inside guest heap code (`sub_002A02E0+0x2A8`, a write through the garbage pointer `0x89DF3BF8`). The crash survives the `toolkit-memory-layout` fix. Just before it, 25 indirect calls fail to resolve: 23 distinct guest addresses that were never translated. They fall into two groups:

- **XDK library sections are never disassembled.** `scripts/pipeline.sh` runs disasm with `--text-only`. The XGRPH, DSOUND, SRCADV and XPP static initializers that the CRT calls through its initializer tables (for example `0x003340D7`: `mov [0x0033A178], 0x00339AA4; ret`) don't exist as C, so the library globals they set are never initialized.
- **One function start was merged into its neighbor.** `sub_002D7024` (`push [esp+4]; call …; int3`) ends in a call that never returns. The detector carried on into the next function, a CRT thread-start routine at `0x002D702E`. The game starts a worker thread there, the dispatcher can't find it, and the thread exits without running.

## What Changes

- Disasm also sweeps the 12 non-`.text` sections that hold code: D3D, D3DX, XGRPH, DSOUND, PSFD_I, PSFD_B, PSFD_P, PSFD00, SRCADV, SRCED, SRCAC and XPP. `--text-only` stays, so the ~60 model-data sections the XBE also flags as executable are still skipped. They would produce phantom functions.
- A hand-maintained seed list, `config/seed_functions.json`, holds indirect-call targets measured at runtime. Disasm reads it through `--seed-functions`.
- `pipeline.sh` gets both settings as game configuration and passes them to disasm.
- The toolkit's `icall_feedback` loop (measure, merge, re-seed, recompile) is documented as the way to grow coverage. Its machine-generated database stays separate from the hand-maintained list.

## Capabilities

### New Capabilities
- `recomp-coverage`: which parts of the XBE get translated, and how runtime evidence of missed code feeds back into the next recompilation.

### Modified Capabilities
<!-- none -->

## Impact

- **Files:**
  - `scripts/pipeline.sh` (disasm stage)
  - `config/seed_functions.json` (new)
  - the regenerated `src/recomp/gen/`, which is shared by the macOS and Windows/Proton builds
- **Toolkit:** no change. It already provides `--extra-sections`, `--seed-functions` and `tools.recomp.icall_feedback`.
- **Cost:** a full disasm → names → recomp → build cycle, about 15–20 minutes. The generated code grows somewhat.
- **Proton:** host-independent. The Windows build uses the same `gen/` tree.
