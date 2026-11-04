## 1. Toolkit (`feat/ram-cache-partition` off `posix-host/portability`)

- [x] 1.1 `src/kernel/kernel_ramfs.{c,h}`: the store, its handles, the seed, the cap
- [x] 1.2 `kernel_file.c`: the backends become `host_Nt*`; the `xbox_Nt*File` dispatcher
- [x] 1.3 `kernel_path.c`: `xbox_path_cache_rest`
- [x] 1.4 `NtDuplicateObject` asks the store first
- [x] 1.5 `RECOMP_STORAGE_RAM_CACHE` CONFIG row; `storage.ram_cache` binding and `xbox_RamCacheEnable` call in the enhance layer; `docs/runtime/config.md`
- [x] 1.6 `tests/kernel_ram_cache` ctest: create, rewrite, seek, size, the cap, the FATX regrow, delete, listing, rename, the seed, no host writes
- [x] 1.7 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL (116 pass; `guest_cpu` "spin: the macro saw the waiter" fails at the base 9ae578c8 on this Mac too); BLiNX 1 Windows cross build

## 2. cat (`feat/ram-cache-partition`)

- [x] 2.1 This spec; `docs/env.md` row
- [x] 2.2 BLiNX 2 Metal golden with the key off: attract, stage1, story pass

## 3. Verify

- [x] 3.1 BLiNX 1 on the Deck (Proton): host writes to `hdd/Cache` with the key off and on, the user's route from a copy of the seed. 300 s each, `RECOMP_DISPATCH_GATE=1` (the fix): off 250 cache files, 456 MB written (write_bytes 453 MB); on 0 files (write_bytes 1.3 MB), same progress (vblank 17400, pelon250)
- [x] 3.2 Dropped: the tracker item is a DirectSound voice-list race, not the cache writes (fixed by the dispatch gate); neither A/B run froze with the gate on
- [x] 3.3 BLiNX 1 golden with the key off: BLiNX 1 has no golden set yet (no `[golden]` in its game.toml)
- [x] 3.4 Review: merge after fixes F1-F10 (toolkit f35e3740 for the POSIX append, be44b0ca for the store), the env.md symbol (F2), the D3 lines
- [x] 3.5 BLiNX 1: `storage.ram_cache = true` in its `config.default.toml` (the user's call, 2026-10-28; blinx 6797c28). A config default, not a game env default, so `config.toml` can still turn it off. Toolkit and BLiNX 2 stay off
