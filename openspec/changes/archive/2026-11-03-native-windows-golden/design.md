## Context

`xbr bench` drives one POSIX host: `ssh HOST bash -s` with a host script on
stdin (`bench/remote.py`), rsync for files, flock for the run lock and
umu-run for Proton (`bench/host/run_game.sh`). With `BENCH_BUILD=local` (the
default since the tracker item) the controller builds the exe, `bench/ship.py` puts it
in `<base>/runs/<sha>/`, and `run_game.sh` runs it there against the base's
single game files copy. `bench golden` (`bench/golden.py`) adds the plan's
env, `RECOMP_DEBUG=fb_dump_at=<golden dumpat>` and `d3d11_dump`
(`FRAMES=1`), then pulls `frame_<idx>.bmp` and the flips `golden pulls`
names, and runs `golden check` on the controller.

The PC under Windows 11 differs in five ways that matter, all seen in the
hand-run legs (`notes/win-checks/sync-leg/`):

1. The OpenSSH server's default shell is `cmd.exe`. PowerShell is there,
   bash is not.
2. An ssh session has no desktop. A game started from it gets no window,
   and its D3D11 device fails or never presents. The legs used a one-shot
   scheduled task, `schtasks /Create /IT ... /Run`, which starts in the
   logged-on user's session, and waited on a done file.
3. No rsync. `scp` and `sftp` ship with the OpenSSH client.
4. No flock. The legs held `D:\bench\.bench-lock`, a file whose text names
   the holder (`notes/benches.md` convention).
5. Paths are drive paths (`D:\bench\...`). There is no `~` and no symlinks
   the runtime would follow; `RECOMP_GAME_FILES` points at the copy instead.

## Goals / non-goals

- Goal: `bench golden`, `bench run` and `bench logs` against a Windows host,
  with the same scenario env, dumps, pulls, checks and verdicts as the Deck.
  A Windows golden verdict means the same as a Deck one.
- Goal: game-agnostic. Nothing BLiNX-specific in the CLI; the game's
  `game.toml` and golden plan say what runs.
- Non-goal: building, ctests, pacing, matrix runs or gc on Windows.
- Non-goal: managing the PC (boot, display mode, user installs).

## Decisions

### Host OS is configuration, not detection

`BENCH_HOST_OS=posix|windows` in `scripts/bench.env` or the environment,
default `posix`. Probing the host's shell on every command costs a round
trip and guesses wrong through a jump host. A Windows host also needs
`BENCH_DIR` as a drive path (`D:/bench`) and an explicit
`BENCH_GAME_FILES`. Config refuses a `~` in either, and refuses
`BENCH_BUILD=host`.

### Scripts as files, run with `powershell -File`

`ssh HOST powershell -Command -` reads stdin line by line and mis-parses
multi-line blocks. `-EncodedCommand` (what `psw.sh` uses) goes through
cmd.exe's 8191-character command line. So the controller copies
`bench/host/windows/*.ps1` to `<BENCH_DIR>/.xbr/host/<digest>/` with scp,
once per content digest, and runs
`powershell -NoProfile -ExecutionPolicy Bypass -File <script> -Params <json>`.
The parameters go in a small JSON file shipped next to the script, so no
value is quoted for cmd.exe. Only the paths are, and the CLI writes them.

### The game starts in the desktop session

`run_game.ps1` writes the run's `launch.ps1` (env, working directory, exe
and quit rule), registers a one-shot task with `Register-ScheduledTask`
(principal: the logged-on user, `-LogonType Interactive`), starts it and
polls its `done` file. The timeout is the scenario's secs plus 30 s, as the
legs did. Without a logged-on user the task cannot start: the script says
so and exits 1, and it does not log anyone on. The task is unregistered in
a `finally` block.

The run ends on `RECOMP_WINDOW_QUIT_AFTER=<secs>`, so the game exits by
itself and flushes its logs. A kill after secs+30 is the backstop, and
check_run_end reads a killed run as it does a Deck timeout.

### Borderless, refresh and a quiet PC

The scenario's own window mode stays, since the references were taken in
it (`RECOMP_PRESENT_SURFACE=window`). The bench does not add
`RECOMP_PRESENT_FULLSCREEN`. Speed legs are borderless (memory note
bench-run-order-borderless), goldens are not. The script refuses below
60 Hz and when a game process is already running, as `run-scen.ps1` does.
It kills one it did not start only on `--kill-game`, by process name, as
the Deck's `run_game.sh` does.

### Lock file

`BENCH_LOCK` (default: the PC's shared lock file) is created with
`[IO.File]::Open(..., CreateNew)`, so two holders cannot both win. The file
holds `bench <slug> <stamp> <controller host> pid=<pid> start=<ticks>`,
the PowerShell process and its start time. The script waits up to an hour
for it (exit 75, naming the holder and how to clear it), deletes it in
`finally`, and never deletes a lock whose text is not its own.

A bench lock whose process is gone, or whose pid now belongs to a process
started at another time, is stale: a killed ssh session or a reboot left
it. The script takes it over in place: it opens the file with
`FileShare.None`, re-reads the text through that handle, and only if it is
still the dead holder's writes its own. The file is never deleted, so a
second taker gets a sharing violation and then reads the first one's live
text: two takers cannot both win. A takeover that fails (a sharing
violation, no write access) waits as for a live holder, within the same
hour. After a takeover, a game of the same name running from this base's
directories is the dead run's (only bench runs start games there), so it
is ended and noted in `warnings.txt`. Any other game process is still the
`--kill-game` rule's.
A lock without the `bench` prefix (a hand-run leg's) is only waited for.
`BENCH_LOCK_HELD=1` (as on the Deck) skips the lock when a caller already
holds it, which is how the hand-run legs work.

### Shader cache

The runtime keeps its DXBC cache under the save root, and each run gets a
fresh save root (`@run`), so every Windows run compiled its shaders cold.
The bench sets `RECOMP_DXBC_CACHE=<base>/shader-cache` unless the scenario
env names one: the cache persists across runs on that base like the Deck's
prefix does, and stays out of the user's install.

### Ship and pull with scp and sftp

`ship.py` keeps the per-run directory model: `<base>/runs/<sha>/` gets the
exe and changed runtime files, never a tree. A Windows host computes the
sha256 with `Get-FileHash`. Pulls use one `sftp -b` batch per pull, built
from the same lists as today (`logs`' file set, `golden frames`, `golden
pulls`), so the frame dumps do not leave the host unless the check reads
them. Windows OpenSSH's sftp names a drive path `/D:/bench/...`, while scp
takes `D:/bench/...`. A missing file is a warning, as an rsync miss is today.

### What stays shared

The POSIX paths are left as they were: there is no `PosixHost` wrapper.
`bench/hosts.py`'s `WindowsHost` (`ship`, `run_game`, `pull(files)`) is
taken only when `BENCH_HOST_OS=windows`, so the Deck's assembled scripts
stay byte for byte (the parity tests pass unchanged). `checks.py` does not
change.

The verdicts gain what known divergence needs, on every host:

- `golden check --host-os` reads KNOWN, KNOWN-NOW-PASSES and
  PASS-with-known (below);
- the bench's verdict word for such a run is `pass-with-known`, not
  `pass`. It is its own word: count passes by the whole field
  (`=…:pass` at a column end), since a `:pass` or `\bpass\b` grep
  also matches `:pass-with-known`;
- each golden-sessions.tsv line ends with `host=posix|windows`, so a Deck
  pass and a Windows pass with known frames are told apart. It is the last
  column, so a reader of the older ones keeps its places.

### Refs

**Probe (2026-10-24).** Attract, stage1 and story ran natively on
the PC with the post-sync exe (`43bde837…`), the golden plan's env and
dumps, under `D:\bench\.bench-lock`. The Mac checked them against the D3D11
(Proton) refs with `blinx2 golden check --log`. One windowed round (the
plan's own surface) and three borderless rounds. Frames and logs stay on
the PC and in `runs/ITEM-probe/`.

| frame | window r1 | borderless r1–r3 |
|---|---|---|
| attract-title | CLOSE, mae 3.6, bad 0.03% | FAIL, mae 7.9–8.3, bad 0.30%, tile 11% (limits 6.0, 0.20%, 10%) |
| attract-cliff | CLOSE, mae 0.0 | CLOSE, mae 0.0 |
| stage1-stick | CLOSE, mae 0.34, bad 1.3% | CLOSE, mae 0.05, bad 0.08% |
| stage1-enemies-objectives | CLOSE, mae 4.3, bad 10.7% | CLOSE, mae 6.8–10.7, bad 14–18% |
| stage1-hud | CLOSE, mae 2.4, bad 2.7% | CLOSE, mae 1.8–1.9, bad 2.5–2.8% |
| story-tsedit | CLOSE, mae 0.0 | EXACT or CLOSE, mae 0.0 |
| story-menu | FAIL, mae 6.2, bad 29.9% | FAIL, mae 6.0, bad 29.2%, all three |
| story-hub | CLOSE, bad 0.000% | CLOSE, bad 0.000% |

What the failures are:

- **The surface changes pacing, not rendering.** Both modes dump 640x480.
  Windowed, the title ran at 29.6 fps against 59.9 borderless.
  The gate keeps the plan's windowed surface, as on every other host;
  borderless is for benches.
- **attract-title** passes windowed. Borderless, the title crystal's
  exact phase sits 80 flips after the anchor, against −9 windowed. Its
  phase follows wall time, not the flips from the anchor.
- **attract-title** also fails windowed when the title runs at the
  ~60 fps pace (run 4, 2026-10-24): the windowed pass in r1 came from the
  29.6 fps pace. So it is marked as well, under the same item.
- **story-menu** fails in every mode and every round, at the same numbers.
  The PC and the Deck dump at the same wall time (about 59.0 s) and the
  same flip distance from the anchor, yet no flip within ±300 of the dump
  matches menu-a. The timing source is unknown and filed as the tracker item. It is
  consistent, so it is a bug, not a refs difference.

**Decision: Windows shares the D3D11 refs**, windowed, with the shared
thresholds unchanged. A second ref set would hide the very
Windows-vs-Proton differences this host is for.

**Known divergence.** Until the tracker item is fixed, attract-title and story-menu
would fail every Windows run. A frame entry in golden.json may carry a host-scoped marking:

```json
"known_divergence": [{"host": "windows", "item": "ITEM",
                      "why": "menu dump timing on native Windows"}]
```

- On that host (`golden check --host-os windows`, set by the bench from
  `BENCH_HOST_OS`) the frame is checked as usual and reported as KNOWN,
  with its numbers and the item. KNOWN is never counted as a pass.
- Only an ordinary outside-limits compare may read KNOWN. A size
  mismatch or a missing reference PNG, with any of a frame's references
  (even when another compared normally), or a wrong screen (bad at or
  past the frame's `pace_fail_bad`) stays FAIL: the marking covers the divergence
  its item describes, not a new regression on that host.
- A scenario with a KNOWN frame is not a pass for pruning: `--used` gives
  it verdict 3, so its frames are kept for the item.
- A host other than `posix` or `windows`, in the entry or in `--host-os`,
  is refused: a misspelt host would silently never match.
- Every other frame gates as usual, and other hosts ignore the marking.
- The overall verdict on that host is PASS-with-known when nothing else
  fails, and the output names each item. It exits 0, so the bench
  continues; a FAIL or INCOMPLETE elsewhere wins as today.
- **Stale marking.** A KNOWN frame whose verdict would pass (EXACT or
  CLOSE) is reported as `KNOWN-NOW-PASSES` and named in the summary, so the
  marking is dropped once the fix lands. It still exits 0 and the frame is
  still not counted as a pass, so the run's verdict doesn't change until
  the marking is removed.
- **Public export.** golden.json goes into the public repo, and the export
  rewrite strips tracker refs (the public copy has none). The export must
  drop `known_divergence` entries whole, so the public file stays valid
  JSON and carries no item ref. The item ref lives only in the private
  golden.json.
- **Merge order.** The CLI merges and is tagged first. cat's golden.json
  entries land in the same squash as the `game.toml` re-pin to that tag:
  an older CLI does not know `known_divergence` and would fail both frames
  on Windows.

## Risks

- **Scheduled tasks need a logged-on user.** After a reboot to Windows
  with no one logged on, runs fail with a clear message. Acceptable, since
  the user decides when the PC runs Windows.
- **The PC sleeps.** The bench reports ssh exit 255 as "host not
  reachable" and leaves the boot alone.
- **Display mode.** A golden at a non-native mode could change scaling.
  The window surface at render scale 1 does not depend on the desktop mode,
  and the probe checks this.
- **A Proton fix that hides a Windows bug, or the reverse.** That is the
  point of the host; no mitigation needed.
