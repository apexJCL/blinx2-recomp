## 1. Toolkit (`fix/pad-record` off `posix-host/portability`)

- [x] 1.1 `usb_gamepad_game_press` / `_record` / `_pads` in `usb_gamepad.h`; report packing shared with `usb_gamepad_report`
- [x] 1.2 `script_pads` scans only the steps added since its last call (a game asks once per port per frame)
- [x] 1.3 `tests/usb_pad_game` ctest: script presses at their flips, record written, record replays to the same state per flip
- [x] 1.4 `src/input/README.md`
- [x] 1.5 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL (130 pass), `notes/build-all.sh` with the toolkit worktree (12/12 pass, runs/build-all/20261030-214829)

## 2. cat (`fix/pad-record`)

- [x] 2.1 `cat_pad_get_state`: press the toolkit script, record the title's state; the script's ports connected
- [x] 2.2 This spec
- [x] 2.3 `uv run pytest scripts`, ruff (149 passed, 1 skipped)

## 3. Verify

- [x] 3.1 Mac (Metal), headless: a `RECOMP_INPUT_SCRIPT` run with `pad_record` writes a record (`@story-hub`, 36 steps; golden `story` pass)
- [x] 3.2 Replaying that record with `RECOMP_PAD_SCRIPT=@file` alone reaches the same stage: `story-slack.txt` record, hub at flip 9311 / 9311 / 9312, file opens within 3 flips (design.md, Limits). `@story-hub` itself does not replay: its movie skip races the decoder
- [x] 3.3 Goldens: Metal on the Mac (attract, stage1, story pass); native Windows built on bench host-win (exe 52d73d3efec6: stage1 pass, attract and story pass-with-known the tracker item)
- [x] 3.4 Review before merge (orchestrator): merge with fixes; the re-review after the fixes (3.5) passed: merge
- [x] 3.5 Review fixes:
  - the record uses its poll's press flip;
  - script_pads rescans after a compaction (generation counter);
  - cat records disconnected ports too (D4);
  - the ctest covers the exit flush, two polls in one flip, a skipped flip and a flip boundary;
  - design numbers and limits corrected; env.md rows refreshed.
