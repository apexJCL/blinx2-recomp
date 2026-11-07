## 1. Fix

- [x] 1.1 Reproduce on Metal: stage 1 with the free camera flown by an input script, and the same with `cam_fix` offsets (`runs/ITEM/`).
- [x] 1.2 Find the reader: `sub_00042E50`, the screen projection `c[116..119]`, called between builds.
- [x] 1.3 Add the wrapper in `src/recomp_manual.c`, then run `blinx2 analyze` and `recomp`.

## 2. Gates

- [x] 2.1 Mac build, cat `uv run pytest scripts` and ruff.
- [x] 2.2 Metal goldens (stock unchanged).
- [x] 2.3 Free camera on, Metal: the shadows stay fixed on the ground while flying. Check the CPU backend once.
- [x] 2.4 D3D11 on the Deck through `blinx2 bench`, with the exe built on the PC (`BENCH_BUILD_HOST`).

## 3. Render-path readers

- [x] 3.1 Classify the readers in D2 (design D3), and fly stage 1 on Metal with each swap on and off (`runs/ITEM/`).
- [x] 3.2 Explain the stage 1 sky on a long flight (design D4): a world-fixed dome, the game's own behaviour, kept as it is with no follow-up.
- [x] 3.3 Add the wrappers on `sub_000E58D0`, `sub_001F73C0`, `sub_000DAEC0`, `sub_0004D740`, `sub_001A6E00` and `sub_0015BC40`, then run `blinx2 analyze` and `recomp`. Add a guard test for each one (`scripts/test_free_camera.py`).
- [x] 3.4 Gates: Mac build, pytest and ruff, Metal goldens, a far flight and a turn on Metal (the radar and billboards follow the free camera; the stage 1 sky is not checked, D4), D3D11 on the Deck.
- [x] 3.5 Effect step under the stage pass: confirm that the number of `rand_002D4FF2` draws does not depend on the camera (D3, gen reading plus the seed probe in `runs/ITEM/rng-*`). Wrap the effect draw pass `sub_0015BC40`.
- [ ] 3.6 Untested: the eye-centred sky dome at 0xE5A06. It runs only in split screen (`[0xAF0EE0]` > 1, D3), and no flight reached it (`runs/ITEM/sky-*`). Also untested: the `sub_000DAEC0` store into the entity's +0x44 on stage 0x1C (D3). Both need a split-screen or stage 0x1C flight with the free camera. They are kept, with the draw callbacks called through pointers that could not be followed, in `docs/known-gaps.md` at the repo root (pending, not urgent).
