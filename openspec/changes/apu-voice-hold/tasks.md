Worktrees: `wt/voicehold/cat` off `main` (a8ba49c) and `wt/voicehold/xboxrecomp` off `posix-host/portability` (70c43712), both on `feat/apu-voice-hold`. Raw runs go in `xbox-recomp/runs/voicehold/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`) under `notes/mac-run-lock.sh`; Deck runs under `flock -w 3600 ~/.recomp-run.lock`, exes built on the Mac only. The Linux/Proton host is unavailable (PC booted into Windows).

## 1. Toolkit

- [x] 1.1 `apu_state.h`: `hold_waiting`, `hold_exempt`, `hold_count`, `hold_timeouts`, `hold_max_us` in `MCPXAPUVPState`.
- [x] 1.2 `apu_vp.c`: walk-then-process in `mcpx_apu_vp_frame` (D1); `vp_hold_locked_voices` with the 2 ms bound and exemption (D2, D4); `voice_lock` signals on unlock only while the hold waits (D3); `[APU-HOLD]` in `vp_stat_report` (D5); `hold_exempt` cleared in reset.
- [x] 1.3 `tests/apu_voice_lock`: hold, release, bound and exemption, title-never-blocks cases.
- [x] 1.4 ADPCM bounds from upstream #217 b380f021 with `tests/apu_vp`, adapted to the fork (D6); negative control under AddressSanitizer.
- [x] 1.5 Mac build; `tests/posix_ctest.sh` with 0 FAIL.
- [x] 1.6 Review fixes: the deadline is checked before each wait, so the hold yields for the last part of the bound instead of a 1 ms wait that would cross it (D4); `hold_wakes` and the ctest's wake case, which fails with the wake removed (D5); the wake is a broadcast (D3); `qatomic_load64` seq-cst off MSVC (D3); a one-time DPRINTF when the voice work queue is full. Rebased onto `posix-host/portability` f79c2012.

## 2. Game checks

- [x] 2.1 BLiNX 2 Metal goldens against the branch: attract and stage1 pass; story INCOMPLETE at host load 33.9, then pass on a rerun at low load.
- [x] 2.2 BLiNX 2 audio on the Mac: base vs branch WAV dumps (`RECOMP_AUDIO_WAV`), `[APU-HOLD]` counts; no dropouts, stuck voices or freezes. Result: attract PASS in both arms; stage1 one host-starvation dropout in each arm (base 18.7 ms, branch 14.4 ms) under host load.
- [x] 2.3 Burnout 3 on the Mac through the vehicle select, base vs branch, from an APFS clone of the dump, race_gate runs (boot, vehicle select, 60 s race).
  - First round, five runs per build plus three extra pairs: every run reached the race with no 1 s stall; 3 of 8 hold runs had host-starvation dropout bursts (58, 41, 234) against none of 8 base runs. Discounted: those runs overlapped another agent's Burnout 3 A/B and builds, with host load up to 34, and the bursts did not line up with holds (one started before the first hold).
  - Quiet-Mac rerun (`runs/voicehold/b3-mac-rerun/`): 8 alternating base/hold pairs, each under the Mac locks after waiting for a 1-minute load under 6 (start loads 1.5-6.0). Dropouts base 29 vs hold 36, starvation 24 vs 31, 0 bursts (no run over 12 dropouts), no 1 s stall, 0 hold timeouts (longest hold 2.8 ms, before the bound fix). Stuck voices appear in both builds (base 127/51/93 in three runs, hold 93/234/24 in three). One unrepeated outlier: hold-2 had the largest frame gap of the 16 runs, 486 ms. The hold does not cause the bursts.
- [x] 2.4 Steam Deck under Proton: BLiNX 2 and Burnout 3 with sound, exes built on the Mac. D3D11 goldens attract, stage1 and story pass; BLiNX 2 audio PASS in both arms except one 56.5 ms dropout in the branch's stage1; Burnout 3 five runs per build all reached the race with no 1 s stall and the same one dropout (the ~300 ms gap at 30.7 s present in every run on both hosts); stale-lap replays in 1 base and 3 hold runs. `apu_voice_lock` and `apu_vp` pass under Proton.

## 3. Upstream

- [x] 3.1 `notes/newprs/c217-hold.md`: revised #217 comment offering the hold (credit xemu), pointing at the fork commit and ctest. Not posted by the agent.

## Follow-ups

- `apu_vp` in the CLI's Proton standalone test list (`bench/host/tests.sh`), beside `apu_voice_lock`.
