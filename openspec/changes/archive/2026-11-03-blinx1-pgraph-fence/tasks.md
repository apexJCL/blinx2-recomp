## 1. Toolkit (`fix/blinx1-fence`, off `posix-host/portability`)

- [x] 1.1 Executor: remember subchannel-nonzero `0x0310`, learn the shift from the adjacent release (`fence_shift_learn`), export `nv2a_pb_exec_fence_shift()`
- [x] 1.2 `xbox_Nv2aPgraphFenceTick`: write the field at the learned shift, 2 by default
- [x] 1.3 ctest `pgraph_fence_5558` (eleven checks; negative controls run)
- [x] 1.4 Mac build, `tests/posix_ctest.sh` 0 FAIL (on 3c75348a: `runs/blinx1-fence/ctest3.log`)
- [x] 1.5 Rebase onto `posix-host/portability` (f255b1a5, the tracker item merged)
- [x] 1.6 Review fixes: pair flag instead of the perf counter (M3), forget the word on a walk stop (M1), three pairs to move an established shift (M2), clear the old field (L1), thread note (L3), `docs/env.md` note for 5558 titles (L2)

## 2. Goldens (Metal)

- [x] 2.1 BLiNX 2 golden: attract, stage1, story pass; `bits 2..6` learned (rerun on 3c75348a)
- [x] 2.2 JSRF skates golden: title, garage, dogenzaka, dogenzaka-corn pass (JSRF has no 0x0310: nothing learned, default 2; rerun on 3c75348a)
- [x] 2.3 Burnout 3 (no golden; `scripts/race_gate.py` fast, Metal): PASS, race 55.5 flips/s (55.0 before), `bits 2..6` learned (`runs/blinx1-fence/b3`)
- [ ] 2.4 Deck and Windows goldens, scheduled by the orchestrator

## 3. BLiNX 1

- [x] 3.1 Metal, 128 MB diagnostic: `bits 0..4` logged, past the loading screen (`runs/blinx1-fence/r1`)
- [x] 3.2 Longer run: title screen and attract demo (stage 1-1) render, no new hang (`runs/blinx1-fence/r2`, `r3`; `r4` on 3c75348a loads the same 474 files)

## 4. Follow-ups (not here)

- [ ] 4.1 Model `0x400B10` as the latched `0x0310` word (design D2), with goldens
- [ ] 4.2 `xbr new` and the template's fence notes name only 5849 signatures
- [ ] 4.3 SSX 3 (5558): delete the `sub_0022F470` wait-for-idle override in `recomp/src/recomp_manual.c` in the same commit that moves its toolkit pin past this change, and run its menu golden
