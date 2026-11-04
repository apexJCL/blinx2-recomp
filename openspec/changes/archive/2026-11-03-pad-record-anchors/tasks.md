## 1. Toolkit (`feat/pad-record-anchor` off `posix-host/portability`)

- [x] 1.1 `pad_script.c`: parse `f<flip>:@open:<text>[:<buttons>/<period>]`; `PadAnchors`; assign steps to anchors (D1, D2); anchor clock and retry (D4, D5)
- [x] 1.2 Recorder: anchor lines with the inferred retry (D6); `pad_anchor` env row (D7)
- [x] 1.3 `usb_gamepad.c`: anchors in the script, live lines and compaction; `usb_gamepad_file_open`, called from NtCreateFile (D8)
- [x] 1.4 ctests: `tests/pad_script` (grammar, assignment, clock, retry, recorder line); `tests/usb_pad_anchor` (an anchored step waits for the open, the retry presses, a record with anchors parses back)
- [x] 1.5 `src/input/README.md`
- [x] 1.6 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL (toolkit 84fc33db: 133 pass, 3 skip, 18 n/a)

## 2. cat (`feat/pad-record-anchor`)

- [x] 2.1 This spec; `docs/env.md` row for `pad_anchor`, `RECOMP_PAD_SCRIPT` row names the anchor

## 3. Verify

- [x] 3.1 Mac (Metal), headless: record `@story-hub` with anchors, replay the record alone to the hub (`runs/pad-record-anchor/`): A hub at flip 3975; B1 3975+92 (tsedit 92 flips late, the retry took it); B2 3974
- [x] 3.2 Golden: PC Windows (bench host-win), exe c43e76db2224: attract pass-with-known, stage1 pass, story pass-with-known (only)

## 4. Review fixes

- [x] 4.1 F1/F7: `s_anchor_lock` (SRW) around the open's match and anchor line, the give-up tick and retry, and the recorder feed while recording; stock opens stay one cached load (D8)
- [x] 4.2 F2: a retry needs three evenly spaced same-button presses, the open within one spacing; `# retry` comment line (D6)
- [x] 4.3 F3: give-up 1800 flips late, logged once, steps on the clock they were due by (D9)
- [x] 4.4 F4: live lines take no anchors (D10); F5: bare texts match the file name's start; F6: Limits note; F9: parser bounds; F12: spin yield, cached anchor pads, clock comments
- [x] 4.5 F8: env.md `(none)` row, kernel_bridge.c:4792, current call-site lines; PAD_SCRIPT help names anchors
- [x] 4.6 F10/F11: neutral test names, no tracker ref; `usb_pad_anchor_{main,stock,threads}`; the record check counts its step
- [x] 4.7 Gates (toolkit 16b86f61): POSIX ctests 133 pass, 3 skip, 18 n/a, 0 FAIL; Mac build
- [x] 4.8 Mac (Metal) re-record `@story-hub` (`runs/pad-record-anchor/`, round 1 in `r1/`): anchors `R0_opening.sfd:start/61`, `tsedit_tex_us.tmp:a/61`, `blinx2data.bin` (no retry; round 1's `a/90` was a false one). Hub: A 3977, B1 3977, B2 3976; every open matched (+0, -1, +0 flips), no give-up
- [x] 4.9 Golden on the PC (bench host-win), exe 72eb1fd558a1: stage1 pass, story pass-with-known (only); bench-logs 20261031-071217, 20261031-071549

## 5. Second review fixes

- [x] 5.1 Give-up keeps the later anchors (D9): an open matching a later anchor while the armed one is late gives up the ones between and takes it (within 1800 record flips); a give-up takes the later anchors its clock passed, silently; skipped steps counted and logged; log wording fixed; `test_anchor_give_up` updated, `test_anchor_skip_ahead` added; `seen_flip` is 64-bit (a given-up anchor's may be before 0)
- [x] 5.2 `test_threads` races without the lock: built with `s_anchor_lock` compiled out (scratch `-D`, not committed), it failed 44 of 50 runs; with the lock, 0 of 50. No hardening needed
- [x] 5.3 `# no retry` comment for three same-button presses that miss the tap rule (D6); retry capped at 8 taps, then waits (`PAD_RETRY_MAX_TAPS`)
- [x] 5.4 Match and give-up lines printed after the lock is released (D8)
- [x] 5.5 `pad_record_open` line buffer 512; an overflow logs "its anchor line is too long", not "(its name)" (`pad_recorder_anchor` returns -1)
- [x] 5.6 Nits: test_stock's no-record claim reworded (no record path without the key); `test_anchor_early_limit`; live-anchor skip message; one `strlen` in `anchor_matches`; env.md call-site lines
- [x] 5.7 Gates (toolkit 229511a1): POSIX ctests 133 pass, 3 skip, 18 n/a, 0 FAIL; Mac build; cat pytest 168 passed, ruff clean. Metal replay of the round-2 `story.rec` (`runs/pad-record-anchor/B3`, `B4`): every open matched (B3 +0, +0, +0; B4 +0, -1, +0 flips), no give-up, hub 3977 and 3976. These replays matched every anchor on time, so they did not reach the look-ahead or the joint give-up; the unit tests cover those

## 6. Third review fixes

- [x] 6.1 The look-ahead refuses a re-open of the last seen anchor's file (or one on its record flip): the recorder collapses repeated opens, so a looping movie must not jump to its name's next anchor (D9); a, b, a test
- [x] 6.2 Anchors on the armed one's record flip are taken early when on time (two loader opens swapped), with a test; D9 says what the look-ahead covers, Limits the swap across record flips
- [x] 6.3 The open's thread no longer reads the script: a give-up marks its anchors, the pad thread counts the skipped steps at its next tick (`announced` test dropped) (D8)
- [x] 6.4 The retry's "waiting on" and "still late" lines go through the log buffer, printed after the lock (D8); a full log buffer ends in "...\n"; `# no retry` only for a last press within three spacings of the open (D6)
- [x] 6.5 Gates: POSIX ctests 133 pass, 3 skip, 18 n/a, 0 FAIL; Mac build; cat pytest 168 passed, ruff clean. Metal replay of `story.rec` (`runs/pad-record-anchor/B5`): every open matched (+0, -1, +0 flips), no give-up, hub 3976; it reaches neither the re-open rule nor the same-flip look-ahead, which the unit tests cover

## 7. Fourth review fixes

- [x] 7.1 Re-open refusal by the midpoint: an open of the last seen anchor's file is refused only while its clock is before (at_seen + at_j)/2, so a, b (missed), a at its own flip is taken; the looping movie is still refused (D9); tests for both
- [x] 7.2 The re-open rule only for a match past the armed anchor's record flip: x, y, x on one flip replays as x, x, y (D9); test
- [x] 7.3 Limits: a file sharing the armed anchor's record flip can fire it early; a live compaction can drop skipped steps before they are counted (only the logged count is wrong)
- [x] 7.4 Log nits: `pad_record_open`'s refusals go to the open's log buffer, printed after the lock (D8); the same-flip swap logs "taken before ... (same record flip)", not a skip; the match offset is from the clock before the raise; a line that exactly fills the buffer still leaves "...\n" for the one dropped
- [x] 7.5 Gates (toolkit dcaca8dd): POSIX ctests 133 pass, 3 skip, 18 n/a, 0 FAIL; Mac build; cat pytest 168 passed, 1 skipped, ruff clean. No replay: B5 matched every anchor on time, so it reaches none of these paths; the unit tests cover them
