## Why

The golden gate runs D3D11 only under Proton on the Deck. CLAUDE.md treats
Windows as a gate and Proton as a stop-gap (the Linux-native decision of
2026-10-21), yet nothing checks the frames the shipped exe draws on native
Windows. The upstream-sync v0.16 leg (2026-10-24) and the tracker item ran the BLiNX 2
golden scenarios on the PC by hand, with PowerShell scripts in
`notes/win-checks/`, outside the CLI. The tracker item makes that a CLI host: `bench
golden` against the dual-boot PC under Windows 11, the same checks and the
same verdicts as the Deck.

## What changes

- `xbr bench` gains a host OS, `BENCH_HOST_OS=windows` (default `posix`, the
  Deck as today). A Windows host is reached over the OpenSSH server that
  ships with Windows, and needs no bash, distrobox, Proton or rsync.
- On a Windows host the bench supports `run`, `golden` and `logs`. The exe
  is built on the controller and shipped as today (`BENCH_BUILD=local` only).
  `setup`, `build` in host mode, `tests`, `pacing`, `gc` and `doctor` refuse
  with a message naming the host OS. They can follow later.
- Host scripts for Windows are PowerShell files under
  `bench/host/windows/`, copied to the host and run with `powershell -File`.
  The game is started in the logged-on desktop through a one-shot scheduled
  task. An ssh session has no desktop, and D3D11 and the window need one.
- The run lock on a Windows host is a lock file (`D:\bench\.bench-lock` today,
  `BENCH_LOCK` in general), taken and released by the host script with the
  same one-hour wait and exit 75 as the Deck's flock.
- Golden references: decided from the probe (design.md, *Refs*).
- Tests: unit tests for the Windows script assembly, the env and dump
  arguments, the lock and quit rules, the pulls and the refusals, with a
  fake ssh/scp like the existing bench tests.

## Out of scope

- Making native Windows a required gate, or changing CLAUDE.md's gate
  wording. That goes through the user after the item's "two passes" check.
- Building on the Windows host, its ctests, and the pacing and matrix
  commands there.
- Burnout 3 and JSRF goldens on Windows. The host is game-agnostic, so they
  come for free once their goldens exist, but this change only checks BLiNX 2.
- Switching the PC's boot. The bench refuses when the host is not up, and
  the user decides which OS runs.
