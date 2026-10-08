## 1. Root cause
- [x] 1.1 Write watch on the sand vertex colour (`0x81399940`) in good and bad hub-route runs: the bake writes `FF000000` in the bad run from the same chain (`runs/water/88ad521-watch-9,10`, `c26f617-watch-11..16`).
- [x] 1.2 Watch report samples the `RECOMP_PEEK` globals (toolkit c26f617): the bad bake selected 3 lights from a mangled pool, the good one 8.
- [x] 1.3 Watch on the pool count `0xAACDFC`: the main thread and the loader thread add lights at the same time, each transition written twice (`bench-logs/20261007-134259`).

## 2. The pin
- [x] 2.1 `xbox_GuestCpuMask`/`xbox_GuestThreadPin` in `kernel_thread.c`, called at guest-main (both thread modes) and every bridge worker; `RECOMP_GUEST_CPUS` row (`=all`, `=<n>`) (toolkit 6eaeab0, 00bac45).
- [x] 2.2 POSIX compat: `SetThreadAffinityMask`, `GetProcessAffinityMask`, Win32 semantics for a new thread's mask (00bac45).
- [x] 2.3 ctest `tests/kernel_guest_cpu`: one fixed core in the process set, `=all` no mask, `=<n>` that core; on Linux the pinned main and worker sit on the core and an unpinned thread made before or after the pin keeps the process mask; on Win32 the pin took. Passes on the Mac (no-affinity branch); Linux native and Win32 under Proton in 3.x.
- [x] 2.4 `docs/env.md` rows: `RECOMP_GUEST_CPUS`, the Debug count, the two-view `RECOMP_WATCH` note.
- [x] 2.5 CLI: `kernel_guest_cpu` in the Proton bench test list (`xboxrecomp-cli` fix/d3d11-dark-water).

## 3. Gates
- [x] 3.1 Mac game build; POSIX ctests kernel_guest_cpu, kernel_bridge, memory_layout_posix, irq_safe_points.
- [x] 3.2 the Linux/Proton host: 10/10 hub-route runs good with the pin (`runs/water/bench host/loop-px-a.out`); `blinx2 bench tests` and `bench golden` pass (85810b9).
- [ ] 3.3 the Linux/Proton host at the branch tip: 10 more pinned runs (20/20) and 5-10 runs at `RECOMP_DEBUG=guest_cpus=all` showing the bad rate without the pin.
- [ ] 3.4 Uncapped D3D11 flips/s, pinned vs `all`, stage 1 and the hub; flag a 25% drop.
- [ ] 3.5 `Cpus_allowed_list` of every thread of one Proton run: only guest-main and the workers on the core.
- [ ] 3.6 Native Linux ctest on the Linux/Proton host (the Linux branch of 2.3) and `bench tests` with the Win32 one.
- [ ] 3.7 One Burnout 3 smoke under Proton on the tip (menu, one race start); the full B3 gate before any upstream PR.

## 4. Follow-ups
- [ ] 4.1 BLX-31: the guest-CPU token (design, alternative A), which also covers macOS.
- [ ] 4.2 Mac A/B of the hub route (20 runs) to measure the bad rate without affinity.
