## 1. Configuration

- [x] 1.1 Classify the 23 distinct unresolved ICALL targets in `analysis/bringup/layout-1.err` (local analysis, not published):
  - XGRPH ×3, DSOUND ×4, SRCADV ×14 and XPP ×1 are library static initializers
  - `0x002D702E` (.text) is a thread entry merged into `sub_002D7024`
- [x] 1.2 Write `config/seed_functions.json` with the 23 measured targets, recording the source log for each.
- [x] 1.3 In `scripts/pipeline.sh` `stage_disasm`:
  - add `DISASM_EXTRA_SECTIONS` (D3D, D3DX, XGRPH, DSOUND, PSFD_I, PSFD_B, PSFD_P, PSFD00, SRCADV, SRCED, SRCAC, XPP)
  - pass `--seed-functions config/seed_functions.json`
  - also pass `--seed-functions` with the toolkit `icall_targets.json` when that file exists

  Do this only while no `pipeline.sh` run is in progress.

## 2. Regenerate and verify

- [x] 2.1 Run disasm → names → recomp, with the `.gen-regenerating` marker held throughout. Verify:
  - functions.json has functions in all 12 library sections and none in DOLBY or later sections
  - `0x002D702E` is a function start
- [x] 2.2 Rebuild on macOS and boot. Verify that none of the 23 targets logs `[ICALL] Failed to resolve`, and record the new boot result and the next blocker in design.md.
