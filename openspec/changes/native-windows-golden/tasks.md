## 1. Probe (before implementation)

- [x] 1.1 Run attract, stage1 and story natively on the PC with the
      post-sync cat exe (`43bde837…`), with the golden plan's env and dumps
      (`notes/win-checks/golden-probe/`), under `D:\bench\.bench-lock`
- [x] 1.2 Pull `frame_<idx>.bmp` and the `golden pulls` flips to
      `runs/ITEM-probe/`, and run `blinx2 golden check --log` on the Mac
- [x] 1.3 Record pass/fail, mae and bad fraction per frame in design.md
      *Refs* and, and decide: share the D3D11 refs or add
      `d3d11-win`. Done: shared D3D11 refs, windowed; story-menu is a
      known divergence, attract-title fails only borderless
- [x] 1.4 `known_divergence` on story-menu for `windows` (item the tracker item) in
      the private golden.json, and an export rule that drops the
      entries whole; check `public export` gives valid JSON with no item ref

## 2. CLI: host object and config (xboxrecomp-cli)

- [x] 2.1 `BENCH_HOST_OS`, `BENCH_LOCK` in `bench/config.py` and the
      `bench --help` table; refuse `~`, `BENCH_BUILD=host` and a missing
      `BENCH_GAME_FILES` on Windows
- [x] 2.2 `PosixHost` wraps today's ssh/rsync paths unchanged; `golden.py`
      and `logs` pull through it. Done without the wrapper: the POSIX
      paths are left as they were and `bench/hosts.py`'s `WindowsHost` is
      taken only when `cfg.windows`, so the Deck's assembled scripts stay
      byte for byte (the parity tests pass unchanged)
- [x] 2.3 `WindowsHost`: script copy by digest (scp), `powershell -File`
      with a JSON params file, `sftp -b` pulls
- [x] 2.4 Refuse `setup`, `build` (host mode), `tests`, `pacing`, `gc`,
      `doctor` on Windows with a message naming the host OS

- [x] 2.5 `golden check --host-os` (the bench passes `BENCH_HOST_OS`):
      KNOWN verdict for a frame marked for that host, never a pass;
      overall PASS-with-known naming each item, exit 0; FAIL and
      INCOMPLETE elsewhere still win; KNOWN-NOW-PASSES when a marked frame
      would pass; other hosts ignore the marking

## 3. CLI: Windows host scripts

- [x] 3.1 `bench/host/windows/ship.ps1`: run dir, sha256 check (exit as
      `EXE_CHANGED_RC`)
- [x] 3.2 `bench/host/windows/run_game.ps1`: lock file, game-process and
      refresh refusals, env (`@run` save, game files, stdio log, dump
      dirs, list keys joined), scheduled task in the desktop session,
      quit-after plus kill backstop, run-info
- [x] 3.3 Remove the task and the lock in `finally`; never remove a lock
      the script does not hold

## 4. Tests and gates

- [x] 4.1 Unit tests: config refusals, params JSON, RECOMP_DEBUG/TRACE
      joining, the sftp batch from `golden pulls`, verb refusals, Posix
      scripts unchanged (golden of today's assembled scripts); KNOWN on
      the marked host and a normal FAIL on others, PASS-with-known with the
      item in the output, KNOWN-NOW-PASSES when the marked frame matches
- [x] 4.2 `uv run pytest tests`, ruff check and format in `xboxrecomp-cli/`
- [x] 4.3 `blinx2 bench golden` with `BENCH_HOST_OS=windows` passes twice
      on the PC (item's "Done when"), with the Deck golden unchanged.
      PC: passed twice on 2026-10-24 (runs 5 and 6, exe 43bde837, windowed),
      with attract-title and story-menu KNOWN. Run 4 is why
      attract-title is marked: it fails at the ~60 fps pace in either window
      mode. Warm shader cache: runs 7 (CLI 5443677) and 8 (e1712a3) give
      the same verdicts. Deck on CLI c9e0de8: attract and stage1 pass;
      story passed on a story-only rerun (the first run's hub anchor came
      14 flips late, so hub-a's flip fell past the dumps: INCOMPLETE)
- [ ] 4.4 Review; fixes on the branch (review fixes: CLI c9e0de8,
      fc455ea, 5443677, e1712a3; design.md 611d3e8 and this commit)

## 5. Hand-off (through the user)

- [ ] 5.1 Gate wording for CLAUDE.md (native Windows golden next to the
      Deck's) proposed to the user, not edited here
- [ ] 5.2 Merge order: the CLI branch merges and is tagged first; this
      branch's golden.json entries land in the same squash as the
      game.toml `[cli]` re-pin to that tag. `scripts/test_public_golden.py`
      runs the pinned CLI's export step over golden.json and fails until
      then (on v0.10.1 the entries would be published)
