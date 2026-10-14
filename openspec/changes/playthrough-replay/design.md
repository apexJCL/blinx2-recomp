## Context

The title reads the pad through `cat_pad_get_state()` (`src/pad_input.c`),
called from the overridden `XInputGetState` (`sub_00368457`,
`src/recomp_manual.c`) once per open port per game frame, right after the
main loop's vblank wait (`sub_0005F960`; divisor `[0x4AC760]`, 2 in 3D, 1 in
menus). There is no input thread. In that call the script engine advances
(timed events, poll-counted releases, `run_steps`, `peek_poll`), then the
host pad or the keyboard-and-mouse state is merged in (buttons OR, analog
max, a stick axis the script left at zero takes the host's), and the packet
number moves only when the merged state changes. The script's poll counter
`g_poll` exists but only counts while a script is on, and the file-open hook
(`xbox_FileOpenHook = on_file_open`) is installed only when a script loads.

What the pieces know today:

| Piece | Has | Lacks |
|---|---|---|
| `RECOMP_INPUT_SCRIPT` | event, poll and timed steps; `poke`; `memdump`; presets (whole-value `@name` only); strict parse errors (`exit 2`) | a recorder; timeouts; a poll or flip index on its log lines; a way to include a preset from a file |
| `pad_peek` (`RECOMP_DEBUG`) | `[PEEK] poll=N t=.. \|VA: v v ..` guest dwords per scripted poll; `:x` prints hex, anything else prints the bit pattern as a float | an interval; a way to print on demand |
| `kbm_script` (toolkit) | key and mouse injection by seconds or polls | coexistence with a pad script (refused on purpose) |
| `scripts/soak.py` | Mac launcher, verdict ladder, the stall rule (no flip for 30 s, also before the first; SIGUSR1 dump), DiagnosticReports | Proton, segments, perf |
| `golden_run.py` / `bench run` | locks, run directories, `[CRASH]` and exit checks, flip floors, frame dumps at flips, a `--secs` limit and a stop flip | a stall rule (golden run); a notion of where a stage starts |
| `scripts/shots/pad/*.txt`, presets | poll- and event-anchored navigation to every stage and boss through the debug stage select | gameplay that resembles a person's |
| `[GPU] flip N T ms .. batches B` | per-flip batch count on every backend; `T` is `xbox_log_ms()`, a timestamp since start | a per-flip frame time (that is `[PACING] flip N t_us`, trace `pacing=all`, which `pacing_stats.py` already parses) |

Timing facts that decide the design (from the toolkit and the generated
code, verified by the research agents and the Opus review, 2026-10-13):

- Every guest clock is host time (`KeTickCount`, QPC, `rdtsc` scaled to
  733 MHz, `KeQuerySystemTime`), but the title does not use a dt: each
  frame runs fixed logic, spins until `[0xAE7388] >= [0x3FD344]` vblanks,
  then swaps. A late frame slows game time; nothing catches up. **Game time
  is the poll count.**
- Loads run on a loader thread (`sub_0005E410`) whose loop bumps the game
  frame counter `0xAE7180` once per iteration and sleeps `[0x3FD33C] << 4`
  ms, so the counter's value after a load depends on wall-clock load time.
  `srand([0xAE7180])` at `loc_001618B1` and `srand([0xAE7180]+0x9999)` at
  `loc_00161A86` (`gen/recomp_0039.c`) seed from it; `srand(0)` at stage
  init (`0x60778`, `0x6078C`) does not. `rand` is the per-thread CRT LCG
  (`holdrand` at `ptd+0x14`).
- File opens come from whichever thread opens: stage data from the loader
  thread, `song_*`, voice and `.sfd` opens on the audio clock. Only
  main-thread state (a watched dword written by the frame logic) marks a
  game frame exactly.
- Sofdec movies and ADX use the audio device as master clock; flips per
  movie differ per host. The attract demo itself was observed deterministic
  on Metal (stage1-water spike).
- The light pool (`0xAACDFC`, `0x8E9088`) was a main/loader race (BLX-1);
  the title gates some draws on occlusion-query results, which differ
  between GPUs. Both are reasons a replay may *render* differently without
  being out of sync.
- Observed load times, "leaving title" (`0x5EB620 == 0x13`) to the stage
  jingle: 1.3 s Mac Metal, 2.25 s Proton on the Linux/Proton host; St5-1 to first
  checkpoint about 58 s on both. The Deck has no numbers yet.
- Known randomness not driven by the pad: the hub camera view (hub-a..d),
  AUTO SELECT's team, the moment A skips `R0_opening.sfd`. Golden runs avoid
  or tolerate them; replays should start past them (the debug stage select
  or a seeded save, `RECOMP_SAVE_SEED`).
- The shipped `packaging/config.default.toml` sets `pacing = "sleep"`, and
  a player's `config.toml` may set a render scale; `present-vblank-pacing`
  D9 says `sleep` picks animation phase by wall time.

Constraints: env keys go through the `recomp_env` table and `docs/env.md`;
features default off; recordings are game output and a person's play, so
they stay local like `analysis/golden/frames/`; the Deck's game is never
started unasked and `~/Games/BLiNX2/hdd` is never touched; the Mac never
plays sound without asking; the Linux/Proton host runs go through `blinx2 bench`, which
takes the run lock itself; `bench sync` excludes `analysis/` (it is cat's
`pipeline.out`), so nothing under it reaches the host unless pushed; the
CLI's `game.toml` schema rejects unknown tables, and `blinx2` runs the CLI
pinned in `[cli]`; the CLI is public, so its fixtures carry no game output.

## Goals / Non-Goals

Goals
- Record one human session on any host where the title runs with a window
  and a pad, keyboard or mouse, with no change to how the game feels.
- Replay it unattended on Mac/Metal, Proton/D3D11 and the Deck, with the
  same per-segment check on each: verdict, flips/s, p50/p95 frame ms,
  probe divergence, audio starves.
- Detect loss of sync at the step that lost it, and say which segment and
  poll.
- Reuse the script engine, the launchers, the locks and the log parsers
  that exist; add grammar, not a second engine.
- Game-agnostic tooling in the CLI; every address, event name, environment
  pin and performance constant in cat's game data.
- Phase 1 only: one recorded stage, three hosts, one check per host. The
  change archives when that is done.

Non-Goals
- Bit-exact frames across hosts or backends. Frames at anchors are a
  follow-up change with golden.py's statistics, thresholded.
- A deterministic or fixed-step guest clock. Replays are poll-anchored
  between game events; they do not try to make loads or movies take the
  same time.
- Replaying raw keyboard and mouse events through the kbm layer. The
  recorder captures what the title received; the kbm path has its own test
  (`kbm_script`).
- Automation that starts the game on the Deck. The CLI prepares the
  command; the user runs it.
- Cross-host performance verdicts. Hosts are compared by eye in phase 1;
  flags are per host and backend.
- Replacing `soak.py`'s seeded random play, `bench replay`, per-stage
  libraries, RNG pinning, Burnout 3: all follow-up changes (see § Follow-up
  changes).

## Decisions

### D1. Record at the title-facing seam, replay through the script engine

The recorder sits at the end of `cat_pad_get_state()` for port 0, after the
merge and before the packet number: it sees exactly the `XINPUT_GAMEPAD`
the title gets, whatever produced it (a prefix script, a pad, keys, the
mouse as a stick). It writes a line only when that state changes, as the
packet number does.

Replay is the existing engine: a lowered recording is a pad script, run by
`RECOMP_INPUT_SCRIPT=<path>` with `RECOMP_INPUT_STRICT=1`. There is no
"replay mode" and no new reader in C; the host pad, keyboard and mouse are
off during a replay as for any scripted run (the `input` spec's isolation
rule). Replaying through the script path also means the replay is
*scripted* input to the title, with the same OR-merge semantics, so a person
can hold a pad during a Mac replay to intervene (`RECOMP_HOST_PAD=1` by
hand), and `check` marks such a log TAINTED.

Why not record raw host events and replay them through `kbm_script` and a
pad injector? Two scripts on one port race (the reason `kbm_script` is
refused beside a pad script), the mouse's model would have to be byte-stable
across versions for the replay to mean the same thing, and the kbm layer is
already tested on its own. The title-facing seam is one format for every
source.

### D2. Poll index is the clock; events are checked, and re-base only where host time ends

The recording keys every line by a **port-0 poll counter** that counts
every `cat_pad_get_state(0)` call from the first one, script or not
(`g_poll` today counts only scripted polls and is incremented before
`run_steps`, so the first poll is 1; it becomes this counter, base 1
unchanged). One poll is one game frame, so a replay by poll count
reproduces the game frames a human saw, at any host speed, until something
that is not the title's frame logic intervenes: a load, a movie, a scene
change.

Those are the **anchors**: game events the recorder logs at their poll,
named in `config/replay.json` with a kind:

- `"check"` (the default): the lowering emits the `wait` for the event with
  a timeout, so a missing event is a desync, and `check` reports the poll
  offset between recording and replay at that event; it does **not**
  re-base the polls that follow. Opens from the loader or audio threads are
  always `check` anchors: re-basing on them would add a host-dependent
  offset of a few polls in the middle of gameplay, where poll replay is
  otherwise exact (the stage-1 walk's 0/3569 mismatches).
- `"resync"`: re-bases the following polls to the event's poll. Allowed
  only where a host-timed interval ends, which means a main-thread `mem`
  state written by the frame logic at the first poll after a load or a
  movie (the checkpoint flag `0xAE73FC == 1`, a title-state value, the
  scene word). `lower` refuses a `resync` on an `open`.

Stage 1-1 from `@stage1` is expected to need no resync after the
checkpoint: the prefix ends on `0xAE73FC == 1`, and from there to the goal
there is no load. Phase 1 replays it both ways, `lower` as configured and
`lower --no-anchors` (one poll-relative segment from `d`), as the A/B that
shows whether anchors buy anything on this stage.

What this does not fix, and why it is accepted for phase 1: the game frame
counter `0xAE7180` differs after a load, so the two `srand` sites that read
it may seed differently per host. Phase 1 *measures* this: `0xAE7180` is in
the probe set at every anchor, and `check` reports whether it matched.
Pinning it is a follow-up and a deviation (§ Follow-up changes).

### D3. The recording format: one text file, log-like, written by the game

`RECOMP_INPUT_RECORD=<file>` opens the file at the first poll and writes
lines through a buffered `FILE`, flushed at each anchor and probe so a
crash loses at most a few polls of input. Setting it also installs the
file-open hook in `cat_pad_early_init` whether or not a script is set, and
the recorder drains the open queue with **its own cursor**, so it never
consumes an open a `wait open` step is waiting for. Format (`xbr-rec 1`):

```
# xbr-rec 1
# game blinx2 host macos backend metal exe /path/to/cat_recomp at 2026-10-13T20:11:04Z
# env RECOMP_INPUT_SCRIPT=@stage1 RECOMP_HOST_PAD=1 ...
# watch 0x005EB620 0x00AE7424 0x00B871AC 0x00AE73FC 0x00B8BB60
# probe 0x00AE7180:1:x 0x00B871AC:1:x 0x00CD252C:3
p 1 none
p 37 START
o 412 d:\stg0101_tex.ipk
m 1133 0x00AE73FC 0x1
k 1133 0x12AB 0x0 467.54 -70.1 -1066.43
f 1133 flip 1510 vbl 3022
d 1140
p 1141 A=255 LS(12000,-3000)
p 1143 LS(14000,-2800)
k 1440 ...
```

- `p N STATE`: the merged pad state at poll N, in `fmt_state`'s wording
  (`START A=255 LS(x,y) RS(x,y)`, `none`), on change only, starting with
  the first poll's state;
- `o N PATH`: a successful open seen at or before poll N;
- `m N VA V`: a watched dword changed, its new value; addresses are always
  printed `0x%08X`, the form the `[INPUT] mem` line uses, so recording and
  log compare mechanically;
- `k N v..`: the probe row in `pad_peek`'s syntax, where `:x` prints hex
  and the default prints the dword's bit pattern as a float, so **integer
  probes carry `:x`** and float probes carry nothing; every `rec_every`
  polls (default 300, ten 3D seconds) and at every `m`/`o`;
- `f N flip F vbl V`: the walker's flip count and `xbox_VblankCount()` at
  the same polls as `k`, so the recording run's own pace is on record;
- `d N`: the prefix script's `script done` poll; lowering drops the `p`
  lines before it and keeps the prefix as text;
- `# end N`: written at exit when the process ends normally.

The header holds what the process knows: the exe path, backend, host and
the `RECOMP_*` environment. No sha is embedded in the exe, so the exe
sha256 and the cat and toolkit shas are added by the launchers (`record`
to `meta.json`, `run` and `bench run` to `run-info.txt`).

Text, not binary: `grep`, `diff` and an editor are the tools, as for every
other log in this project. A 15-minute stage at 30 polls/s with a stick
moving most frames is about 25 000 `p` lines, around 1 MB; the engine's
step arrays grow dynamically (`g_stepcap`), so a lowered script of that size
is not a problem, and lowering coalesces runs of identical stick values.

### D4. Lowering is the CLI's; the game data says where to cut

`xbr replay lower <rec> --game <game.toml> [-o replay.txt] [--no-anchors]
[--timeout-scale F]` reads `config/replay.json` through `game.toml`'s
`[replay]` table and emits:

1. the prefix: `include @stage1` for a preset (the new `include` step, D5,
   expands the preset's steps in place, since a `@name` line is not a step
   today and the preset text lives only in C), or a file prefix's steps
   copied. `lower` refuses a prefix whose last step is timed (`wait SECS`,
   `BUTTON/D`): segment 1 is based at `d`, so the prefix must end on an
   event or a poll count;
2. for each anchor the recording hit after `d`: a `wait open TEXT timeout
   S` or `wait mem VA == V timeout S` step with `S = max(30, 3 × the
   recorded gap in seconds)` unless `--timeout-scale` says otherwise;
   a `resync` anchor re-bases the polls that follow, a `check` anchor does
   not (D2);
3. between anchors, `wait polls k` and the pad actions that reproduce each
   `p` line, with `BUTTON/Np` for presses that release within the segment
   and explicit `-BUTTON` otherwise; stick axes as `LX=..,LY=..` values;
4. a `probe` step wherever the recording has a `k` line, so replay and
   recording probe at the same game frames;
5. a `# segment <name> kind=<check|resync> rec-flips F1-F2 rec-polls P1-P2`
   comment before each anchor, which `check` reads to label its report.

Anchors the recording did not hit are not emitted; an event that happens
twice in one segment anchors on the first. The output is a plain pad
script: a person can shorten a segment, add a `memdump`, or paste a segment
into a soak prefix.

`replay.json` (game data, committed, free-form JSON like `golden.json`):

```json
{
  "about": "...",
  "record_env": {"RECOMP_HOST_PAD": "1", "RECOMP_KEYBOARD": "1", "RECOMP_MOUSE": "1",
                 "RECOMP_PRESENT_PACING": "spin", "RECOMP_RENDER_SCALE": "1", "RECOMP_GLOW": "on",
                 "RECOMP_TRACE": "flip,pacing=all",
                 "RECOMP_DEBUG": "rec_watch=...,rec_probe=...,rec_every=300"},
  "replay_env": {"RECOMP_HOST_PAD": "0", "RECOMP_KEYBOARD": "0", "RECOMP_MOUSE": "0",
                 "RECOMP_INPUT_STRICT": "1", "RECOMP_CONFIG": "none", "RECOMP_RENDER_SCALE": "1",
                 "RECOMP_PRESENT_PACING": "spin", "RECOMP_GLOW": "on",
                 "RECOMP_TRACE": "flip,pacing=all,audio_host"},
  "anchors": [
    {"open": "stg", "name": "stage-load"},
    {"open": "jingle_stagestart", "name": "stage-start"},
    {"mem": "0x00AE73FC", "value": 1, "name": "checkpoint", "kind": "resync"},
    {"mem": "0x00AE7424", "name": "scene"},
    {"mem": "0x005EB620", "name": "title-state"}
  ],
  "probes": [
    {"va": "0x00AE7180", "type": "u32", "name": "frame-counter"},
    {"va": "0x00B871AC", "type": "u32", "name": "stage"},
    {"va": "0x00CD252C", "n": 3, "type": "f32", "name": "player-pos", "tol": 0.5}
  ],
  "perf": {"floor_flips": 27, "note": "lock30: a 3D median under 27 flips/s is a NOTE"},
  "prefixes": {"stage1": "@stage1", "st5": "scripts/shots/pad/st5.txt"}
}
```

`type: u32` lowers to `:x` in `rec_probe`, `f32` to no suffix. `game.toml`
gains `[replay] json = "config/replay.json" dir = "analysis/replay"`;
`manifest.py`'s strict schema learns the optional table, and cat adds the
table in the same commit that bumps `[cli]` to the release that knows it
(D11). Addresses never enter the CLI.

### D5. `include`, `timeout`, `probe`, and `poll=`/`flip=` on the engine's lines

Four grammar additions in `pad_input.c`, each small and useful on its own:

- `include @NAME`: expands the preset's steps in place, one level (no
  recursion, no `include` inside a preset), so a file can start where a
  preset ends. An unknown preset is a parse error (strict exits 2 before
  boot, as today).
- `wait .. timeout SECS|Np` and `tap .. until .. timeout SECS|Np`. Seconds
  are the right unit for loads (the pad is not polled while the loader
  thread runs, so polls do not advance); polls suit in-stage waits. On
  expiry the engine logs
  `[INPUT] t=<s> poll=<N> flip=<F> desync step k/n: <step text>`; with
  `RECOMP_INPUT_STRICT=1` it flushes stderr and the recorder and ends the
  process with status 4 through `_exit` (POSIX) or `ExitProcess` (Win32),
  not `exit`: the poll runs on a guest thread while the walker and audio
  threads are live, and atexit teardown there is a known risk on Metal.
  Without strict it drops the step and continues, as a bad step does today.
  A `wait` without `timeout` keeps waiting forever, as every existing
  preset expects.
- `probe`: prints the `rec_probe` row now as `[PEEK] poll=N flip=F |..`,
  the `pad_peek` line with a flip field. `pad_peek` and `rec_probe` share
  the parser, and `rec_every=N` makes the periodic print every N polls
  instead of every poll (0 = only on `probe` steps and at events).
- `[INPUT] t=.. step k/n: ..`, `opened`, `mem`, `poke`, `memdump`, `probe`
  and `desync` lines carry `poll=N flip=F`. `flip` comes from one toolkit
  accessor beside `xbox_VblankCount()` (`xbox_FlipCount()`, the counter
  `[GPU] flip N` prints, `s_gpu.flips`, read with a relaxed atomic load
  since the walker thread writes it). Scripts keep parsing `t=`;
  `soak.py`'s `script done` regex is anchored on `t=` and still matches.

### D6. The checks: one log reader, four questions per segment

`xbr replay check <run-dir|log> --rec <rec.txt> --script <replay.txt>
[--baseline <run-dir>]` answers, per segment and for the whole run:

1. **Did it run?** The `soak.py` ladder, in order: `[CRASH]` (the
   `bench.crash_tag`) or a signal exit → CRASH; `desync` line → DESYNC
   (segment, step, poll); the launcher's stall verdict (the launcher's
   rule, D7) → STALL; the process ended before `script done` →
   INCOMPLETE; exited on its own → EXIT; else ok. A `host port=0` line in a
   replay log adds TAINTED; an `[ENHANCE]` line that is not stock adds
   NONSTOCK (the `golden check` rule, reused).
2. **How fast?** Between a segment's `flip=` bounds (its anchor's step line
   and the next anchor's), per-flip intervals come from `[PACING] flip N
   t_us` (trace `pacing=all`, in `replay_env`), parsed by
   `pacing_stats.py`'s `PACING_FLIP_RE`, with its `[GPU] flip` fallback
   (consecutive timestamp differences) and its 3D rule (batches above 2):
   flips/s and p50/p95/max frame ms. **PERF flags only against the same host
   and backend**: `--baseline` names an earlier accepted run there (the
   first replay on a host is its own baseline and prints no PERF); the
   thresholds are CLAUDE.md's, a drop of 25 % or more in flips/s or a 1.5×
   rise in frame ms. The recording run's `f` rows and the other hosts'
   numbers print as information, never as flags. The lock-30 floor is the
   game's (`replay.json` `perf.floor_flips`, 27) and gives a NOTE.
3. **Same game?** Each `[PEEK]` row against the recording's `k` row at the
   same segment-relative poll: integer probes equal, floats within `tol`.
   The first differing row prints with the address name, both values and
   the poll; a divergence that recovers at the next anchor is noted, one
   that persists is DRIFT. `0xAE7180` is reported separately as "frame
   counter matched/offset by N", since D2 expects it to differ. At every
   `check` anchor the poll offset between recording and replay is printed.
4. **Did audio hold?** With `audio_host` traced, the 1 Hz
   `[AUDIO-HOST] .. starves=S .. underruns=U` summary and `[XA2] underrun`
   lines give starves per segment. Headless Mac runs use the dummy driver
   and report "n/a (dummy audio)"; the Linux/Proton host and the Deck have real devices.

Exit 1 on CRASH, DESYNC, DRIFT or PERF, 2 on INCOMPLETE or STALL, 0
otherwise. Stdlib Python with unit tests on **synthetic** fixtures: made-up
addresses (`0x1000`-style), invented log lines, no real recording, log,
host name or path, because the CLI is public. `scripts/audit-public.sh`
runs before the push, as for every CLI round.

### D7. Hosts: reuse each host's launcher, add only the stall rule

- **Mac.** `blinx2 replay run <name> --backend metal|cpu [--secs]` uses
  `golden_run.py`'s launcher (the `~/.recomp-mac-run.lock` mkdir lock, the
  load warning, `RECOMP_HEADLESS=1 SDL_AUDIODRIVER=dummy`, SIGINT then
  kill), extracted into a function both commands call, plus `soak.py`'s
  stall rule ported into it (no flip for 30 s, also before the first;
  SIGUSR1 thread dump then stop) with tests showing `golden run`'s
  behaviour unchanged. The replay environment and the run limit `1.5 × the
  recording's length + 60 s`; the run directory is
  `bench-logs/<stamp>-<backend>-replay-<name>/` with `run-info.txt` (the
  exe sha256, cat and toolkit shas, the environment), `game-stdio.log`,
  `exit-code`, `save/` and `replay.txt` (the check's output). The
  launcher's lock still jumps the `notes/mac-run-lock.sh` FIFO
  (TASKS.md:275); agents keep wrapping the command in that script until the
  follow-up lands. Audio stays dummy; a replay with sound on the Mac is the
  user's call, run by hand.
- **the Linux/Proton host.** Phase 1 needs no bench code. `bench sync` excludes
  `analysis/`, so the recording is pushed on purpose, once per recording:
  `rsync -e 'ssh -o BatchMode=yes' analysis/replay/<name>/replay.txt
  bench host:<BENCH_DIR>/cat/analysis/replay/<name>/` (an excluded path, so
  the next sync's `--delete` leaves it). Then `blinx2 bench run` with
  `BENCH_ENV` holding `replay_env` and
  `RECOMP_INPUT_SCRIPT=Z:<host path>/replay.txt`, and `BENCH_TIMEOUT` as
  above; `bench run` takes the host lock itself and pulls the run
  directory, which `replay check` then reads. A `bench replay` command that
  does the push and the check is a follow-up change. One agent at a time on
  the Linux/Proton host, BLiNX first, as always.
- **Deck.** `blinx2 replay deck-cmd <name> --root ~/blx-scratch/replay`
  prints two commands for the user: the `scp` of the recording's
  `replay.txt` and of the runner script `deckrun.sh`, which ships as CLI
  package data (`xboxrecomp_cli/replay/deckrun.sh`, the pattern of the
  scratch `runs/apulock-deck/scripts/deckrun.sh`: refuses a root under
  `~/Games`, refuses if a game is running, Desktop Mode env or Game Mode's
  `WAYLAND_DISPLAY=gamescope-0`, `timeout -s TERM`, copies the newest
  `logs/game-*.log` back), and the `ssh deck 'bash <root>/deckrun.sh ..'`
  that runs the scratch root's installed launcher with the replay
  environment in that root's `config/launch.env`. The scratch root holds a
  bundle built by `blinx2 package` from the merged main (so the engine has
  `include`, `timeout` and `probe`), copied there by the user, never to
  `~/Games/BLiNX2`. The CLI never runs these commands. `check` reads the
  copied log like any other; the Deck has no stall watchdog beyond the
  timeout, so a stall there reads as INCOMPLETE with the last flip's time.

### D8. The recording session

`blinx2 replay record <name> --prefix stage1` prints the command and
environment for the person to run (it does not launch a windowed game from
an agent's session): the prefix as `RECOMP_INPUT_SCRIPT`,
`RECOMP_INPUT_RECORD=analysis/replay/<name>/rec.txt`, `record_env` from
`replay.json`, which turns the host pad, keyboard and mouse on explicitly
(a script turns them off otherwise: `input` spec, isolation rule) and
**pins the frame rules to stock** (`RECOMP_PRESENT_PACING=spin`,
`RECOMP_RENDER_SCALE=1`, `RECOMP_GLOW=on`) while keeping the config file so
the person's key bindings apply, a fresh `RECOMP_SAVE_DIR`, windowed,
Metal, sound as the person chooses on their own machine. The prefix
navigates to the stage and ends; from `script done` the recording is the
person's. They play the stage to its end state (the goal, the boss, a
time) and quit the game; `record` then validates the file (`# end`, the
anchors hit, the `[ENHANCE]` lines stock by `[golden] enhance_stock` as
`golden check` does, refusing a non-stock recording), warns about host
input before `d` (lowering drops it), adds the exe sha256 and the cat and
toolkit shas to `meta.json`, and runs `lower`. A recording made on the Linux/Proton host
or the Deck is the same file written under the bundle's root; it is copied
back by hand.

Recordings are game output and a person's play: `analysis/replay/<name>/`
is under the gitignored `analysis/*`, so `export-public.sh`, which exports
`git ls-tree`, never sees it; `scripts/test_gitignore.py` asserts it, and
the public-push audit lists `analysis/replay` among the paths to grep for.
Nothing about them is checked in except `config/replay.json` and the names
in TASKS.md.

### D9. What replay pins on the host side

`replay_env` pins what the goldens pin for the same reasons: `RECOMP_CONFIG=none`,
`RECOMP_RENDER_SCALE=1`, `RECOMP_PRESENT_PACING=spin` (the console-original
pacing the goldens use; `sleep` picks animation phase by wall time),
`RECOMP_GLOW=on`, host devices off, strict on,
`RECOMP_TRACE=flip,pacing=all,audio_host`. `RECOMP_GUEST_LOCK` is already
cat's default. A replay is a stock run; `check` says NONSTOCK otherwise.

### D10. Scope of phase 1

The smallest useful step, and this change's whole scope: D1-D9 in cat and
the toolkit; `lower`, `check`, `run`, `record`, `deck-cmd` in the CLI
(`report`, a table across hosts, is cut: three `check` outputs answer the
question for one stage); `config/replay.json` with the stage-1 anchors and
probes; one recording of stage 1-1 by the user on the Mac from `@stage1`;
replays on Mac/Metal (three, to see the run-to-run noise, plus the
`--no-anchors` A/B), the Linux/Proton host through `bench run`, and the Deck through the
user; the findings in notes and TASKS. Expected size: cat S-M, toolkit S,
CLI M, runs S; about four agent days plus the user's half hour.

### D11. Release order: the CLI first, then cat's pin and `[replay]` together

`blinx2` runs the CLI pinned in `game.toml [cli]`, and the schema rejects
unknown tables. So: the CLI change merges to its `main` and is tagged and
audited first; cat then adds `[replay]` **in the same commit** that bumps
`[cli] tag`/`commit` to that release; the public CLI round goes before
cat's, as CLAUDE.md orders anyway. Likewise cat's call to `xbox_FlipCount()`
needs `game.toml [toolkit]` bumped to the toolkit commit that has it, and
that commit goes into the public toolkit round before cat's.

### D12. Placement summary

| Lives in | What |
|---|---|
| toolkit | `xbox_FlipCount()`; nothing else |
| cat `src/pad_input.c`, `src/env/recomp_env_game.h`, `docs/env.md` | poll counter, recorder, `include`, `timeout`, `probe`, `poll=`/`flip=`, four env rows |
| cat `config/replay.json`, `game.toml [replay]` | anchors with kinds, watches, probes with types, environments, the perf floor, prefixes, recordings directory |
| cat `analysis/replay/<name>/` (local) | `rec.txt`, `replay.txt`, `meta.json` |
| CLI `src/xboxrecomp_cli/replay.py`, `replay/deckrun.sh`, `manifest.py`, `golden_run.py` (shared launcher) | `lower`, `check`, `run`, `record`, `deck-cmd` |

## Follow-up changes (proposed, not part of this change)

Each is its own OpenSpec change and tracker item (task 0.2 files them),
blocked by this one:

- **replay-smoke-library**: a recording per entry of BLX-101's smoke list
  (prefixes exist in `scripts/shots/pad/`), `"end"` anchors per stage (goal
  or boss-defeated dwords), `xbr replay report` (segments down, hosts
  across), per-host baselines kept beside the recording
  (`baseline-<host>-<backend>.json`, `check --save-baseline`).
- **bench-replay**: `blinx2 bench replay <name> [--only seg]`, which pushes
  the recording, runs under `replay_env`, pulls, checks and appends a
  `golden-sessions.tsv` row; a `bench-methodology` delta then adds it to
  the command list.
- **replay-frames**: a `dump LABEL` step (the toolkit dumps the next flip on
  Metal and D3D11), frames at anchors compared with `golden.py`'s statistics
  against the recording host's frame, NEWVIEW on a different camera.
- **replay-rng-pin**, only if phase 1's evidence (the frame-counter offset
  and a probe divergence that tracks it) calls for it: `lower --pin VA`
  emits `poke 0xAE7180 <recorded>` after each post-load resync anchor; a
  `deviations` entry, replay-only, never in goldens. Seeding `holdrand`
  (per-thread CRT data, no fixed address) stays out of scope until a probe
  shows the main thread's seed matters.
- **soak-check**: `scripts/soak.py run --check` calls `xbr replay check` per
  run for the crash, stall and perf cells.
- **b3-replay**: a recorder and poll-indexed replay on the toolkit's USB pad
  path (`usb_gamepad.c` has only the ms-timed `RECOMP_PAD_SCRIPT`), plus
  `b3/config/replay.json` and `[replay]` in `b3/game.toml`. The format and
  `xbr replay` already fit.

## Risks / Trade-offs

- **A segment that depends on load-seeded randomness drifts every time.**
  Mitigation: the probe set includes `0xAE7180` and the player position at
  every anchor and every 300 polls, so phase 1 names the segment and the
  poll where it happens; `replay-rng-pin` is the planned answer. A drifting
  segment can still be scored for crashes and perf; `check` says DRIFT,
  not DESYNC.
- **Timeouts hide slow hosts as desyncs.** A Deck load that takes 3× the
  Mac's is possible on a cold cache. The lowering's floor of 30 s and factor
  of 3 are starting values; `check` prints the recorded and the observed
  gap for every anchor so they can be tuned from data, and `--timeout-scale`
  overrides them.
- **A `resync` on the wrong event adds the offset it was meant to remove.**
  Hence the kind, the default of `check`, and the rule that only
  main-thread `mem` states may resync; the `--no-anchors` A/B measures the
  effect on stage 1.
- **The recorder's cost on the poll thread.** One `fprintf` per state
  change into a buffered stream; a stick moving every frame is 30 lines a
  second. Phase 1 measures @stage1-enemies flips/s with the recorder on and
  off and reports both.
- **Recorded menu mashing.** A person taps A through dialogue faster than
  the game reads it; replayed by poll it lands on the same game frames, but
  across a load the taps are poll-relative to the anchor and may skip a
  different dialogue line. The next anchor reports the offset; a `"tap":
  "A"` on an anchor (lowering emits `tap A every Np until mem ..`) is the
  remedy if a stage needs it.
- **Occlusion-query gating and the light-pool race** make frames and some
  draws differ between GPUs without the game being out of sync; that is why
  frames are a follow-up and thresholded, and why `check` scores probes,
  not pixels.
- **Deck runs stay manual.** The rule is the user's; `deck-cmd` makes the
  manual step one paste. A stall on the Deck is a timeout, read as
  INCOMPLETE with the last flip's time.
- **`_exit` from the poll thread skips the recorder's own close.** The
  recorder is flushed before `_exit`; a truncated last line is accepted by
  `check`.

## Migration Plan

Nothing to migrate: every key is new and off by default; presets, goldens
and soaks are unchanged. Roll-out: the CLI release, then cat's pin bump
with `[replay]`, each behind an Opus review; then the recording session with
the user; then the three replays. Rollback is unsetting the keys.

## Open Questions (for the user)

1. **Which stage first?** Proposed: stage 1-1 from `@stage1` (fastest load,
   its route is golden-covered, its enemies and water are known content).
   The alternative is 5-1 from `scripts/shots/pad/st5.txt`, where BLX-10's
   crash lived.
2. **Where to record?** Proposed: on the Mac, windowed Metal, with the
   user's pad (sound on if they want it; it is their session). Recording on
   the Deck is possible from a scratch install's `config/launch.env` and is
   the more natural controller; it needs the user to copy the file back.
3. **Pin the frame counter if needed?** `replay-rng-pin` would write
   `0xAE7180` after each load in replays only, logged as a deviation. Yes,
   only on evidence, or never?
4. **Perf baseline.** Per host from the first replay on that host (then the
   25 % / 1.5× flags are relative to the host's own first run), or the
   recording run on the Mac as the one baseline with absolute floors
   (27 flips/s median at lock30)? Proposed: both printed, the per-host
   baseline the one that flags.
5. **Should a recording end on an event** (the goal flag, a boss-defeated
   dword) that `check` requires, or is "the person quit after finishing"
   enough for phase 1? Proposed: phase 1 accepts the quit;
   `replay-smoke-library` adds an `"end"` anchor per stage once the dwords
   are known.
6. **Mac sound during replays**: never (dummy), as proposed, so starves are
   measured only on the Linux/Proton host and the Deck?
