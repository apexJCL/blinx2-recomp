## 1. Toolkit (`fix/contig-image-alias` off `posix-host/portability` 18607bd9)

- [x] 1.1 `RECOMP_CONTIG_AVOID_IMAGE` defaults on; recomp_env help text and header comments
- [x] 1.2 Fallback and top-down passes never take a named image page (`contig_page_free`)
- [x] 1.3 Late naming reported once per page in `xbox_PhysNoteRamName`
- [x] 1.4 `mcpx_apu_phys_data` and OHCI comments: why the rule stays
- [x] 1.5 `tests/contig_image_alias` ctest (named, unnamed, late); `memory_regressions contig-fill-image`
- [x] 1.6 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL (115 suites)
- [x] 1.7 Review fixes (`notes/ITEM/review-ITEM.md`):
  - `=0` is the old order exactly: the named-page refusal applies only while
    the switch is on (MED-1);
  - the first pass jumps past the image in one step (LOW-2);
  - `0`, `off`, `false`, `no` are off, anything else on (LOW-3);
  - tests: fill-named (`=0` over a named page), range-constrained requests
    into the image page, no reuse of a freed late-named page (LOW-7). Top-down
    below a named page is not testable with the one-page conformance image;
  - gates re-run: Mac build, `tests/posix_ctest.sh` 0 FAIL (115 suites) with
    `RECOMP_MENU` unset

## 2. cat (`spec/contig-image-alias`)

- [x] 2.1 This spec; `docs/env.md` row for the new default

## 3. Verify

- [x] 3.1 BLiNX 2 Metal golden: attract, stage1, story pass; no late-name reports
- [x] 3.2 JSRF Metal golden: title, garage, dogenzaka, dogenzaka-corn pass (13 EXACT, 2 CLOSE at mae 0.000)
- [x] 3.3 JSRF scale change 1x -> 2x -> 3x -> 1x (Metal):
  - WAV: 100 windows, no clipping; the tonal peaks match the fix run's music;
  - voices 64-67 read `imgnamed` at rms 0;
  - no logged block overlaps the image. This is the deciding evidence: the
    WAV and the voice stats show the symptom is gone, but only the absence of
    any window block on an image number shows the cause is gone
- [x] 3.4 B3 race gate (Metal, fast): pass, 57.4 flips/s. The first try timed out at the options menu with the Mac at load 39 on 14 CPUs; the retry passed
- [x] 3.5 BLiNX 1 with `RECOMP_XBE_PAGING=1` boots through the intros to the attract demo:
  - two late-named `.data` pages, the same as with `=0`
- [ ] 3.6 Deck/Proton goldens for BLiNX 2 and JSRF before merge (MED-2), on the
  review-fix toolkit tip; JSRF's garage-load is judged against base
- [ ] 3.7 Review before merge
- [x] 3.8 BLiNX 2 audio A/B on the Mac (MED-3; stage1, Metal, dummy driver, WAV tap):
  - default vs `=0`: clip 0 in both, rms max -21.2 / -22.2 dB, median loud
    -31.5 / -31.4 dB, tonal max 61.0 / 60.9 dB, one noise-like window each
  - APU-VSTAT classes named/ram/win only, no `hiwin` in either run; counts
    scale with run length (158 vs 143 windows)
  - 0 late-name reports in either run

## 4. Follow-ups

- [ ] 4.1 One physical space for the heap and the contiguous arena, so each number has one owner:
  - heap and stack numbers under the high-water mark (NV2A's `dma_resolve`
    ignores the RAM-name map, so it takes the window for them);
  - this covers small images too: with blocks above the image, B3's and
    JSRF's blocks reach stack and heap numbers about 7.5 MB and 2.5 MB of
    allocation sooner, not only BLiNX's large images
- [ ] 4.2 Image fallback takes read-only sections first, off `.data` (BLiNX 1's late-named pages)
- [ ] 4.3 Upstream PR round: propose the default flip, with the console argument and the JSRF case. Until then the flip is fork-only and the upstream README entry ("opt-in") stays as it is (design: upstream note)
- [ ] 4.4 Smoke-boot Spartan and SSX 3 at their next toolkit bump: both get the moved layout then
