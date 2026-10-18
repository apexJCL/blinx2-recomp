## Context

The executor decides which colour surface a flip puts on screen, for every backend (`present_pick()` at FLIP_STALL, `nv2a_pb_present_state()` in `nv2a_pb_state.h`). A surface is an offset plus the extent the clip gave it (`clip_x + clip_w`, `clip_y + clip_h`), recorded by `present_note()` at each draw and colour clear into `s_psurf[PRESENT_MAX = 16]`, LRU-evicted. The pick is size first: the largest fresh surface at the display address (`xbox_GetDisplayFramebuffer()`, the address AvSetDisplayMode gave, compared as physical addresses), else the largest stale one there (which leaves no candidate and keeps the screen), else, with nothing at the display address, the largest fresh surface anywhere; the pitch must be the display's, or twice it when no surface since the mode set has had the display's (field rendering, one field shown). Of that size, the newest draw since the last flip wins, else the newest clear, else the screen stays. A surface not used for `present_stale` flips (RECOMP_DEBUG, default 120) is stale. A display-mode generation (`xbox_DisplayModeGeneration()`, bumped by the AvSetDisplayMode bridge after address and pitch) resets the field latch.

D3D11's and Metal's `present_extent()` crop their render target to the pick's extent when the pick names that target, and `nv2a_present_rect()` fits that extent into the back buffer or drawable. The CPU path dumps and shows the pick directly. So the pick's `w, h` is the one number every present path scales from, and a change of it between flips moves the picture on screen under any scaling present.

The kernel records of a display mode are the resolved framebuffer address, the pitch and the generation (`xbox_memory_layout.c`); `xbox_AvSetDisplayMode` keeps the mode word (`g_av_display_mode`) for `AvSendTVEncoderOption`'s query and decodes nothing from it. BLiNX 2 sets mode 0x0801010D with fb 0x00104000, briefly 0x011A8040 and back during boot; Burnout 3 sets 0x080F0D12 with fb 0x005E8000. Both at pitch 2560, format 0x12 (A8R8G8B8), width 640.

## D1. Scanout set now; display-mode height as a separate phase, if wanted

Two fixes were on the table (`runs/b3jitter/REPORT.md`): a scanout set with eviction protection, or presenting the height of the display mode AvSetDisplayMode set, as the CRTC does. The recommendation is the scanout set now (this change) and the display-mode height as its own change later, only if the user wants the menu-to-race size step gone as well. The reasons, weighed:

**Hardware fidelity.** The CRTC scans the buffer `PCRTC_START` names at the mode's timing, 480 lines for every mode either title uses, and the title's clip rectangles are invisible to it. On that measure the display-mode height is the more faithful rule, and the scanout set is a repair of our own bookkeeping, not a model of the hardware. But the pick is already a deliberate model with tested departures from the CRTC: the frame is the clip extent, so a 320x240 frame on a 640x480 target shows 320x240 (`metal-present-mirror`, the `crop` case of `nv2a_backend_smoke`), a pause screen's idle buffers keep the screen, and a field buffer shows one field. Presenting the mode height overturns the first of those, and the smoke test with it; whether a 320x240 frame should show as the hardware would (the whole 640x480 buffer, with whatever sits in the rest) is a product decision, not a bug fix.

**What the kernel knows.** Nothing records a display height today. The mode word is a selector into the kernel's own CRTC table (0x0801010D, 0x080F0D12), not a width and height; the width is `pitch / bpp`, the height needs a word-to-timing table (nxdk's `lib/hal/video.c` mode table is the candidate source, to be verified against both words we have) or a bit decode, plus the field and interlace flags. That is new kernel knowledge to verify on two titles before it drives every present. The scanout set needs none: it reuses the display address, the pitch, the staleness window and the generation that are already there.

**Field rendering (BLiNX's guard).** With `D3DPRESENTFLAG_FIELD` the back buffers are half height at twice the pitch, and the runtime shows one field. The scanout set is indifferent to it: the field pitch latch (`s_pitch_seen`) and `present_pitch_ok()` still filter the entries; the set holds offsets, not sizes. A mode-height rule would present 480 rows from a 240-row buffer unless it decodes the field flag and halves, or interleaves the fields, neither of which exists.

**Titles that change display mode.** BLiNX 2 sets the mode three times at boot with two different addresses, so the generation bump is exercised on every golden run. The scanout set is cleared on it (D2), so buffers of the old mode cannot set the size of the new one; the same hazard the staleness window was added for (`3ff3d6a` S2), closed at the source. A mode-height rule would follow the generation naturally and have the same property.

**What each buys.** The scanout set removes the per-flip alternation, which is the tracker item. Menus at 640x464 and the race at 640x480 remain two sizes, so one 3.4% step stays at each menu-race transition (TASKS follow-up (f)); the mode height would remove that too. That step is once per transition, not 60 times a second, and it does not block this fix.

So: phase 1 here, with no change to any present behaviour a test pins today. Phase 2 is written up as a follow-up in TASKS with the open items above (the mode table, fields, the crop semantics), and starts only on the user's decision.

## D2. The scanout set

A ring `s_scanout[SCANOUT_MAX = 8]` of `{ phys, last_flip }`: the physical form (`dma_resolve(offset) & 0x0FFFFFFF`, the compare the display address already uses) of each offset a flip presented, and the flip that last presented it. `present_pick()` adds or refreshes `s_present.offset` after a successful pick, evicting the entry with the oldest `last_flip` when full; an entry whose `last_flip` is more than `present_stale_flips()` ago is dropped on the next pick, so a title that moves to a different pair of buffers without a mode change stops protecting the old pair after two seconds, in step with the staleness of their surfaces. On a display-mode generation change the ring is cleared, in the same block that resets the field latch, since buffers presented before the mode set say nothing about the new mode (the reason `s_pitch_seen` resets there).

Eight entries cover double and triple buffering, a title that alternates two buffer pairs inside the window, and the display address itself; it is a bound on the ring, not a model of any title.

**Where the set is read.** Pass 0 of the size scan accepts an entry whose physical offset equals the display address *or* any live ring entry, with the pitch test unchanged. Nothing else moves:

- Pass 0 still runs only with a display mode (`disp` non-zero). Without one (the Dashboard case in the `fb_present` history), pass 1's "largest fresh surface anywhere" stays the rule; the ring would narrow it to offsets already presented, which is a behaviour change nobody asked for.
- The candidate loop (newest draw since the last flip, else newest clear, among entries of the chosen size and pitch) is unchanged, so it still accepts an offscreen target of the display's size and pitch drawn after the back buffer. B3 draws a 640x480 target at 0x0096C000 each race frame and the trace shows no wrong-buffer pick, so that target is either at another pitch or drawn before the composite; task 1.6 confirms which from the `[PRESENT]` trace. Preferring scanout entries among same-size candidates would be a tightening with its own cases (a title's first flip to a new buffer) and is out of scope.
- The staleness test, the field-pitch fallback and the stale-only "screen stays" rule apply exactly as before, over the widened pass 0.

For B3's card: pass 0 now sees both back buffers, the largest fresh entry at either is 640x480 on every flip, and the candidate is the buffer whose 640x480 composite was drawn this frame.

## D3. Eviction spares scanout entries; `PRESENT_MAX` 32

`present_note()` needs a slot only when `(offset, w, h)` is new and the table is full, a rare path. There it picks the LRU victim among entries that are *not protected*; an entry is protected when its physical offset is the display address or a ring entry and, once a mode is set, its pitch is the display's (or the field pitch when that is in force). Only when every entry is protected does plain LRU over all of them apply, so the protection cannot starve the table: a title that touches more scanout-sized entries than `PRESENT_MAX` still gets a slot, and the smoke case for it (D5, case 4) shows nothing worse than the old LRU happens. The pitch clause keeps a stray entry at a back-buffer offset with an offscreen pitch (the odd-frame case the present comment describes) from being protected.

`dma_resolve` of each candidate victim is paid only on this path, never per draw; the ring stores physical forms so the compare is one mask and compare per ring entry.

`PRESENT_MAX` goes from 16 to 32. B3's card needs 19 entries, so 32 makes the card fit outright with 13 to spare, and the protection is what holds for a title or scene that touches more. `present_note()`'s match loop runs over 32 entries per draw instead of 16; it is a linear scan of small structs, and the flips/s gate (D6) is where a cost would show. The `[PRESENT]` trace (`RECOMP_PRESENT_TRACE=1`) gains two things: the ring's contents on each printed flip, and a line the first 20 times eviction takes a protected entry, with a count in the end-of-run summary, so a run can say whether the protection was ever the deciding factor.

No new environment key: the window is `present_stale`, whose `docs/env.md` row gains the clause that it also bounds the scanout set, and `RECOMP_PRESENT_TRACE`'s row says it prints the set.

## D4. Stock behaviour and what the goldens prove

The unscaled copy (`stock` in D3D11's flip: scale 1, nearest, not fullscreen, the window as created; the Metal drawable and the CPU dump likewise) is not touched: the diff is confined to `nv2a_pb_exec.c`'s present block and the smoke test. What can change is the pick's `w, h` per flip, which is the copy path's only input from this code. So the proof is on that input, then on the output:

1. **Every BLiNX 2 flip presents a back buffer at 640x480.** `RECOMP_FLIP_LOG=1` prints `presents 0x%08X %ux%u` for every flip. For attract, stage1 and story, headless on the Mac (Metal), every flip on main and on the branch is 0x00104000 or 0x00230000 at 640x480 (the extracted columns kept in `runs/present-scanout/`). The per-flip sequences are not identical: they diverge with run-to-run timing at held flips, and two runs of one build diverge as much, so the proof is the set of `(offset, w, h)` values, not a flip-for-flip diff. A flip at any other size or offset is a regression in the pick.
2. **The goldens pass unchanged** on Metal (Mac) and D3D11 (Deck, `blinx2 bench golden`), with the same verdicts as main's last runs and no re-record; the `[d3d11] first present` line still reads `copy`. The golden frames are the back buffer's bytes after the copy, so with (1) they are the same bytes.
3. **The eviction count is zero for BLiNX 2:** the D3 trace count in the same three runs says the protection never fired, so (1) is not a coincidence of ordering.

For Burnout 3 at stock, the frame is not byte-identical and should not be: a 640x464 pick took D3D11's "overlap copy" branch (clear to black, copy 464 rows), a 640x480 pick takes `CopyResource`; with the pick at 640x480 on every flip, rows 464-479 come from the guest buffer at every flip, as the hardware shows them. In the race they are black bar the lit row 464 TASKS follow-up (a) describes, and the menus (still 640x464) are unchanged. The b3 race gate's own checks (frame content, FPS, stock `[ENHANCE]` line) are the acceptance there.

## D5. Tests: four CPU-path cases in `tests/nv2a_backend_smoke`

All on `nv2a_pb_cpu_backend()`, after the existing cases (they set a display mode, which the earlier cases run without, and end by clearing it and bumping the generation). The flip count advances at FLIP_INCREMENT_WRITE (0x012C) then FLIP_STALL (0x0130), as the crop case notes. The display is set with `xbox_SetDisplayFramebuffer()` and `xbox_DisplayModeBump()` (`xbox_memory_layout.h`, linked through `xboxrecomp`), with the address the bridge would record (the resolved form; the compare is on the low 28 bits). The frame pattern is B3's, reduced to what the table sees:

1. **Double-buffered card** (fails on the base). Display at A, pitch 2560. Frame k draws into `back[k & 1]`: one draw with the clip at 640x480, one 640x480 clear into an offscreen target at another offset (before the back buffer's composite, so the newest-draw rule is not what the test leans on), 18 distinct 128x128 targets each cleared once, then a 640x464 draw and a 640x463 draw into the back buffer, `SET_SURFACE_COLOR_OFFSET` to the other buffer, FLIP_INCREMENT_WRITE, FLIP_STALL. That is 2 x 3 + 19 = 25 entries, over 16 and under 32. From the third flip, eight consecutive flips must give `nv2a_pb_present_state()` = `{back[k & 1], 640, 480, 2560}`. On the base the pick alternates or holds 640x464: this stream holds it on every flip, while B3's own frame (13 targets) alternates.
2. **A mode change clears the set.** After case 1, set the display to C and bump the generation; draw into A at 1280x720 (bigger than anything) and into C at 640x480, flip. The pick must be C at 640x480: A left the set with the mode, so its larger entry cannot set the size. Without the clear, A's 1280x720 would set the size and A, drawn at that size this frame, would be the pick at 1280x720.
3. **Single-buffered title with many targets** (fails on the base). Display at A, every frame into A: a 640x480 draw, the 19 offscreen targets, a 640x464 draw, flip. Eight flips present A at 640x480. On the base the 480 entry is the oldest when the 17th target arrives and is evicted each frame, so the pick is 640x464; the protection, not the ring, is what fixes this case, which is why it is separate.
4. **A table full of protected entries still evicts.** Display at A; 40 draws into A at 40 distinct clip sizes, then a 640x480 draw and a flip. The pick is A at 640x480 (the newest 640x480 entry survived, being the last written); the point is that plain LRU over protected entries kicks in and nothing stalls or asserts.

Each case prints one `[backend-smoke] scanout: … PASS|FAIL` line. The test shows cases 1 and 3 failing on the base and all four passing on the branch; both outputs go in the notes.

The review added three more, each killing a mutant the four missed: **1b**, case 1 with 40 targets after two warm-up frames at 19 (fails when `present_scanout` ignores the set); **3c**, case 3b right after a mode set, checked from flip 2 (fails with the eviction protecting only the field pitch the first pick wants); **5**, an offset presented once still sets the size 120 flips later and no longer does at 121 (pins `scanout_live`'s `<=`).

## D6. Gates, and why no backend work

Both GPU backends' `present_extent()` read `nv2a_pb_present_state()` and clip their target to it; `nv2a_present_rect()` is shared; the CPU path dumps the pick. The fix changes what that state says, so the backends follow with no change to either, which is the "backends agree" rule satisfied at the source. The gates check it on each:

- **Toolkit:** Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`), `tests/posix_ctest.sh <dir>` 0 FAIL with the four new cases in `nv2a_backend_smoke`.
- **BLiNX 2:** Metal goldens on the Mac and D3D11 goldens on the Deck, verdicts unchanged; flips/s and mean frame ms against main's last runs (Metal 45.8 / 33.4 / 54.0 flips/s for attract / stage1 / story; D3D11 bench-logs 20261015-074306, -074426, -074617), flagged at a 25% drop or 1.5x rise; the D4 sequence diff and eviction count.
- **Burnout 3, Metal:** `b3/scripts/race_gate.py` on the Mac from a b3 build against the branch, passing, plus a dense dump across the card (`RECOMP_DEBUG=fb_dump_at=<range>` over the card's flips, found from the flip log, or `--dump-every 1` over that window): every BMP in the range is 640x480 and their count equals the flips in the range. A contact sheet like `runs/b3jitter/base-seq.png` for the notes.
- **Burnout 3, D3D11 under Proton:** the race gate's `--pad-script` variant on the Deck with `RECOMP_PRESENT_FULLSCREEN=1` (the user's configuration in the 11:26 log) and `RECOMP_FLIP_LOG=1`, under the run lock, from a Mac-built exe: no size change after the race load, to the end of the drive (the report's BASE run had 183). The menus' own changes before it (4, the same as base; menu 640x464 to race 640x480, follow-up (f)) are not this change's. The user's own look at the race start on the Deck is the acceptance for the eye.
- **CPU rasteriser:** builds; the four smoke cases are its check; no CPU golden (the rule since 2026-10-10).

## D7. Branch and overlap

Toolkit branch `fix/present-scanout` off `posix-host/portability` in `wt/present-scanout/xboxrecomp`, one or two commits (`pb_exec: a scanout set keeps both back buffers in the present size scan` and the test), landing by `git merge --squash`. Cat branch `spec/present-scanout` carries this spec and the two `docs/env.md` row changes; TASKS is the main session's.

`feat/fork-prs-aniso-bumpenv` touches `nv2a_pb_exec.c` at `vsh_method` (one `#define` and one `case` for `SET_SHADER_OTHER_STAGE_INPUT`, around lines 2184 and 2321) and `nv2a_pb_state.h` in `struct nv2a_pb_vsh`; this change touches the present block (lines 779-1038) and `tests/nv2a_backend_smoke/smoke.c`, which that branch does not. `git merge-tree` of the two should report no conflict; whichever lands second rebases trivially. On the cat side both edit `docs/env.md` in different rows.

## Validation

- `tests/posix_ctest.sh`: 0 FAIL; `nv2a_backend_smoke` with cases 1 and 3 shown failing on the base.
- BLiNX 2 goldens, Metal and D3D11, unchanged verdicts and speed within the limits; every flip 0x00104000 or 0x00230000 at 640x480 (D4); eviction count 0.
- B3 Metal race gate pass with every card dump 640x480; B3 Deck fullscreen race with zero size changes after the load.
- Review before the merge; fixes go back to the branch's agent.
