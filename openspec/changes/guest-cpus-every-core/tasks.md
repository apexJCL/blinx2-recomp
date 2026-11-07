## 1. Change
- [x] 1.1 `src/env/recomp_env_game.h`: drop `D(GUEST_CPUS, "one")`; rewrite the comment
- [x] 1.2 `docs/env.md` `RECOMP_GUEST_CPUS` row, README one-CPU paragraph, `src/main.c` comment
- [x] 1.3 spec delta `kernel-threads`

## 2. Evidence (done on the player's version, cat 6b995348, toolkit 0d40abad)
- [x] 2.1 Native Windows A/B with the player's config: `one`/`=2`/`all` with spin, `one` with sleep (proposal table)
- [x] 2.2 Mac Metal clean with the player's config (no pin exists there): 0 stale blocks, 0.1 clicks/s

## 3. Gates (owner: orchestrator)
- [x] 3.1 The user's decision: every core is the default (2026-11-05, reversing 2026-10-10); b3 left alone
- [x] 3.2 Mac build; `uv run pytest scripts`; ruff
- [x] 3.3 Goldens: Metal, Deck D3D11 under Proton, native Windows (water: the tracker item)
- [x] 3.4 Native Windows boot capture with the player's config: `apu_ring` stale 0, clicks under 1/s

## 4. Frame pacing per build (the user, 2026-11-05)
- [x] 4.1 Spin against sleep on the branch, story and stage1, 3 runs per arm: native Windows, Deck (Proton), Mac Metal (proposal table)
- [x] 4.2 `src/main.c`: spin as the code default of `present.pacing` (toolkit `enhance_cfg_set_code_default`, branch `fix/enhance-code-default`, with its ctests), Windows build only; `packaging/config.default.toml` leaves the key out
- [x] 4.3 docs: `RECOMP_PRESENT_PACING` row, README, `docs/packaging.md`, `docs/frame-generation.md`; spec delta `enhancements`
- [ ] 4.4 Follow-ups for TASKS.md: the bundle README pacing paragraph per target (CLI `pacing_sleeps`; the macOS app's README lost it); why native Windows stalls host reads at sleep
