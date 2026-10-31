## 1. Toolkit (`feat/ram-cache-default-on` off `posix-host/portability`)

- [x] 1.1 `enhance.c`: `storage.ram_cache` defaults to true
- [x] 1.2 `kernel_ramfs.c`: the env read without the layer is on unless 0/false/no/off (D2); header and `recomp_env.h` help text
- [x] 1.3 `mem_stats`: `ramcache_mib` and `ramcache_peak_mib` in the `[MEM]` line (D3); `kernel_ramfs.c` notes each charge change
- [x] 1.4 ctests:
  - `kernel_ram_cache`: on by default, its charge in the `[MEM]` reading;
  - `kernel_ram_cache_off_0` and `_off_false`: the variable turns it off and a `z:` write lands in `<hdd>/Cache`;
  - `enhance_cfg`: default on, file false off, variable 1 over file false, variable 0 over file true;
  - `mem_stats`: the new fields format, parse and note
- [x] 1.5 `docs/runtime/config.md` and `CHANGELOG-blinx2.md`
- [x] 1.6 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL, `notes/build-all.sh` with this toolkit

## 2. CLI (`feat/ram-cache-default-on` off `main`)

- [x] 2.1 The new-game template's `[storage]` block
- [x] 2.2 `tests/test_config_defaults.py`: `storage.ram_cache` leaves AHEAD for WANT (true)
- [x] 2.3 `CHANGELOG.md`; pytest and ruff

## 3. Games (one `feat/ram-cache-default-on` branch each)

- [x] 3.1 `packaging/config.default.toml` `[storage]` block: BLiNX 2, JSRF, SSX 3, Burnout 3, KUF, Spartan
- [x] 3.2 BLiNX 1: `docs/env.md` row reworded (the toolkit default is on)
- [x] 3.3 CHANGELOG and player docs where they list keys
- [x] 3.4 Goldens on native Windows (PC) with this toolkit for each game that has them; the smoke log shows `[FILE] ram cache: on` and the `ramcache_mib` figures, and no new files in the host's `hdd/Cache`

## 4. Close

- [ ] 4.1 Review, fixes on the branches
- [ ] 4.2 Squash merges; the toolkit change rides the same release tag and pin moves as the tracker item
