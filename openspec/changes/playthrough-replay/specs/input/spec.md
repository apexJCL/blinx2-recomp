## MODIFIED Requirements

### Requirement: A script drives the pad on port 0
When `RECOMP_INPUT_SCRIPT` is set, port 0 SHALL report a gamepad whose state follows the script. The value is an inline list of steps separated by `;`, a path to a file of steps (one per line, `#` comments), or `@name` for a built-in preset. Steps SHALL run in order:
- `include @NAME`: the preset's steps, expanded in place, one level (no `include` inside a preset); an unknown preset is a parse error;
- `wait open TEXT`: until the title opens a file (successfully) whose guest path contains TEXT, case-insensitively;
- `wait SECS`: SECS seconds; `wait until T`: until T seconds since the first pad poll;
- `wait polls N`: N more polls of port 0;
- `wait mem ADDR == V | != V`: until the guest dword compares;
- `tap BUTTON [every P | every Np] until open TEXT | until mem ADDR ==|!= V`: press BUTTON for half the period every P seconds (default 0.5) or every N polls until the condition holds, then release it at once;
- `poke ADDR V`: one 32-bit guest write; `memdump LABEL`: a memory dump now;
- `probe`: print the `rec_probe` row now as `[PEEK] poll=N flip=F |..`;
- `ACTION[,ACTION...]`: applied at once. An action is `BUTTON` (press), `-BUTTON` (release), `BUTTON/D` (press, release D seconds later), `BUTTON/Np` (press, release N polls later) or `BUTTON=V` (an analog or stick value).

Every `wait open`, `wait mem`, `wait polls` and `tap .. until` step MAY end with `timeout SECS` or `timeout Np`. On expiry the engine SHALL log `[INPUT] t=<s> poll=<N> flip=<F> desync step k/n: <step text>`; with `RECOMP_INPUT_STRICT=1` it SHALL flush stderr and the recorder and end the process with status 4 through `_exit` (POSIX) or `ExitProcess` (Win32), never `exit`, since the poll runs on a guest thread while the walker and audio threads are live; otherwise it SHALL drop the step and continue. A step without `timeout` waits without limit, as before.

Buttons are the digital `UP DOWN LEFT RIGHT START BACK LTHUMB RTHUMB`, the analog `A B X Y BLACK WHITE L R` (a press is 255), and the sticks `LX LY RX RY`. File opens SHALL be observed from before the game starts and kept, so an open that happens before the first pad poll, or while an earlier step is waiting, still satisfies the step that waits for it; each match consumes the opens up to it. The absolute form `T:ACTION[,ACTION...]` and `T1-T2@P:BUTTON` (seconds since the first pad poll) SHALL still work alongside the steps. Each pad change SHALL be logged as `[INPUT] t=<seconds> buttons=<state>`; each step start, matched open, matched memory value (`mem 0x%08X = 0x%X`), poke, memdump, probe and desync SHALL be logged as an `[INPUT] t=<s> poll=<N> flip=<F> ..` line, where N is the port-0 poll counter (counting every port-0 poll from the first, base 1, script or not) and F the walker's flip count; `script done` SHALL keep its `[INPUT] t=<s> script done` form. The packet number SHALL advance only when the state changes.

#### Scenario: Presets reach their targets at any speed
- **WHEN** the title runs on macOS with `@skip-intro`, `@attract` or `@new-game`, both normally and slowed down (busy loops on every core)
- **THEN** `@skip-intro` and `@attract` end idle on title_movie_1a.sfd and the attract demo loads stg0101; `@new-game` reaches R0_opening.sfd and then the Time Sweeper editor (tsedit); no step depends on wall time

#### Scenario: Scripted START skips the intro
- **WHEN** the title runs with `@skip-intro`
- **THEN** stderr shows each step and matched open, logo_artoon.sfd is never opened, and title_movie_1a.sfd opens a few seconds after start instead of about 84 s

#### Scenario: Unknown button or bad step
- **WHEN** a script names a button that does not exist, or a step that does not parse
- **THEN** an `[INPUT] script:` line is logged and the remaining steps still run

#### Scenario: A file continues a preset
- **WHEN** a file whose first line is `include @stage1` and whose next lines are `wait polls 30` and `START/6p` runs under `RECOMP_INPUT_STRICT=1`
- **THEN** the `[INPUT]` step lines are `@stage1`'s followed by the two steps, and `include @no-such` in its place exits 2 before the guest starts

#### Scenario: A wait times out under strict
- **WHEN** the inline script `wait mem 0x5eb620 == 0x77 timeout 2` runs with `RECOMP_INPUT_STRICT=1`
- **THEN** `[INPUT] t=2.0.. poll=.. flip=.. desync step 1/1: wait mem 0x5eb620 == 0x77 timeout 2` is logged and the process ends with status 4 on the Mac and under Proton (`exit-code` reads 4)

#### Scenario: A wait times out without strict
- **WHEN** the same script runs with `RECOMP_INPUT_STRICT` unset followed by `START/0.2`
- **THEN** the desync line is logged, the START tap still happens, and the run goes on

#### Scenario: Probe steps print at their polls
- **WHEN** a script holds `probe; wait polls 30; probe` with `RECOMP_DEBUG=rec_probe=0xae7180:1:x,rec_every=0`
- **THEN** exactly two `[PEEK] poll=` lines appear, 30 polls apart, each with a `flip=` field and a hex frame-counter value, the two values 30 apart

## ADDED Requirements

### Requirement: The pad the title receives can be recorded per poll
With `RECOMP_INPUT_RECORD=<file>` (game key, config tier) the host SHALL write the `xbr-rec 1` recording defined by the `playthrough-replay` capability from the port-0 poll, after the merge of script, host pad, keyboard and mouse, so the file holds exactly the states the title read. Setting it SHALL install the file-open hook in `cat_pad_early_init` whether or not a script is set, and the recorder SHALL drain opens with its own cursor. `RECOMP_DEBUG=rec_watch=VA[,VA..]` SHALL name the dwords whose transitions are recorded, `rec_probe=VA:N[:x],..` the probe row (the `pad_peek` syntax: `:x` prints hex, otherwise the dword's bit pattern prints as a float; shared with the `probe` step and the periodic peek), and `rec_every=N` the probe interval in polls (0: only at events and `probe` steps). Each key SHALL have a `recomp_env` row and a `docs/env.md` row. With the keys unset the poll path SHALL be unchanged and nothing SHALL be written.

#### Scenario: Recording cost
- **WHEN** `@stage1-enemies` runs three times on Metal with `RECOMP_INPUT_RECORD` set and three times without
- **THEN** flips/s agree within the run-to-run noise (CLAUDE.md flags a 25 % drop)

#### Scenario: Unwritable file
- **WHEN** `RECOMP_INPUT_RECORD=/nonexistent/dir/rec.txt`
- **THEN** one `[INPUT] record: cannot open` line is logged, the game runs, and no other behaviour changes

#### Scenario: Recorder beside a preset's waits
- **WHEN** `@stage1` runs with `RECOMP_INPUT_RECORD` set
- **THEN** every `wait open` of the preset still matches and the recording's `o` lines list the same opens: the two cursors are independent
