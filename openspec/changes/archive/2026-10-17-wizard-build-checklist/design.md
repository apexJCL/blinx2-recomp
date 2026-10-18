## Context

Read at CLI `main` 029e875. The wizard runs `model.Steps`: one command per
prerequisite of a set flag (today `--hud-pack` needs `import DUMP` and
`enhance hud`), then `package <target> ... --plain`. Each command's merged
output is fed line by line to `runner.Progress` (`progress.go`), which
parses what `package --plain` prints (`package/progress.py View`):

- `plan: import (why), setup (a, b), generate (why), build (dir), package (target)`:
  printed once, before any work (`package()` prints `plan_line` right
  after `package_plan`, when the dump and the pack have been checked);
- `== [n/m] stage ==` per plan stage (`host.mark`; a stage outside the
  plan prints nothing);
- `  label ...`, `  label: NN% (i/n)`, the heartbeat
  `  label ... m:ss[, eta] | tool line`, `  ✓ label  m:ss`,
  `  FAILED label  m:ss`, `bundle: PATH`, `full log: PATH`.

The prerequisite commands run without the plain view: `host.step` prints
`== msg ==` (no `[n/m]`), which the stage pattern does not match.

## Decisions

**D1. The parts come from what the wizard already knows, with no new CLI
output.** Before the build the wizard knows its own commands. It makes
one row per prerequisite command and one placeholder row, "Build the
game", for `package`. `package --plain` prints its plan line within
seconds, before any long step. When the plan line arrives, the
placeholder is replaced by one pending row per plan stage. The first of
these takes over the placeholder's clock and lines and runs at once. A
`--dry` plan from the CLI would only show the same list a few seconds
earlier, at the cost of a second CLI run and a new flag, so the wizard
does not ask for one.

**D2. Graceful when the plan is unknown or changes.**
- No plan line (an older CLI, or a failure before the plan): the first
  stage line renames the placeholder to that stage, which keeps its
  clock and lines; with no stage line either, the placeholder stands
  for the whole command and takes its outcome. Its name reads right
  either way: "Build the game · done", not "Plan the build · done".
- A stage line whose name is not in the rows (added at run time): a new
  row is inserted after the running one.
- A stage line that jumps over pending rows: those rows become skipped.
- A command that ends well with rows still pending: they become skipped
  ("not needed").
- A failure or a cancel leaves the later rows pending ("not run").
- A line that comes before the first command starts is in no row (no
  part is running to hold it); the Details pane and `build-logs/` still
  have it. Between two commands the last part keeps the lines.

**D3. The model is plain Go in `runner` (`checklist.go`)**, apart from
Fyne, so it is tested on its own. `Checklist` holds `[]Part`, each with:
the CLI name, its kind, state, step label, percentage, `[i/n]`, start
and end, its own lines (capped at 2,000, the full log is in the CLI's
`build-logs/`), and a sequence number that changes with its lines.
`StartCommand`, `Feed(line, now)` and `EndCommand(err, canceled, now)`
drive it. `Fraction()` is (finished parts + the running part's share) /
parts, and never goes back. The existing `Progress` still parses the
bundle, the FAILED step and the log path, unchanged.

**D4. Player-facing names and icons per kind.** The kinds are the CLI's
own command and stage names, a generic table like
`model.Prerequisites`, never a game's:

| CLI name | Row | Tabler icon |
|---|---|---|
| import | Copy your game files | `download` |
| enhance hud | Redraw the HUD and menus | `photo` |
| (placeholder) | Build the game | `list-check` |
| setup | Get the tools | `settings` |
| generate | Translate the game's code | `code` |
| build | Compile | `hammer` |
| package | Make the installer | `package` |
| anything else | the CLI name, first letter upper case | `list-check` |

The row's status text names the CLI's step ("recomp · 42% · 4:12"), so
the CLI's names stay visible next to the player's words. The icons are
Tabler 3.34.1 outline glyphs (MIT, `LICENSES/tabler-icons-MIT.txt`),
embedded as published and recoloured through wizard-test-notes'
`strokeIcon`, in the foreground colour.

**D5. States.** Each state has an icon, a theme colour and words, so
colour is never the only cue (the checks page's rule, D6 of
wizard-ui-polish):

| State | Icon | Colour | Status words |
|---|---|---|---|
| pending | `circle-dashed` | placeholder | "waiting" / "not run" after a stop |
| working | Fyne activity spinner | primary | step · % or [i/n] · clock |
| done | `circle-check` | success | "done · m:ss" |
| failed | `circle-x` | error | "failed · m:ss" |
| skipped | `circle-minus` | placeholder | "not needed" |
| cancelled | `player-stop` | warning | "stopped · m:ss" |

**D6. Layout.** Top: the intro sentence, the overall line and Cancel. In
the middle, a scroll of rows. At the bottom, the Details pane (the
aggregated log, unchanged). A row is `[kind icon] Name … [state icon]
status [Log ▾]`. The status label truncates with an ellipsis, so a
narrow window cuts the status, never the name or the toggle. Under the
running row is a thin bar for its own percentage, which pulses with the
sheen while the part prints no percentage. The toggle opens the row's
log in place: a selectable monospace box, 160 px high, holding the last
500 lines, with Copy. A failed row opens on its own, with "What the
build said:" and the excerpt above its log.

**D7. Threads.** Lines arrive on the reader goroutine. The model is
behind a mutex. A line marks the view dirty and schedules at most one
`fyne.Do` refresh every 100 ms (the log pane's pattern, with the same
injectable `after` for the tests). The clock ticker refreshes the
running row's clock every second through `fyne.Do`. The refresh takes a
snapshot under the lock and then touches widgets only on the UI thread.
Rows are rebuilt only when the list of parts changes, and otherwise
updated in place.

**D8. Request 3, reconciled.** The running part's clock is in its row,
beside its player-facing name. That is the "part name instead of this
part" the user asked for, and it reads well at any width: the name has
its own column and the clock sits in the status, which truncates first.
The overall line becomes "Part 3 of 6 · 42% · 12:40 in all". Before the
first part starts it reads "12:40 in all". "in this part" and the part
timer fields of wizard-build-feedback (`partStart`, `partIndex`) go.

**D9. The Done page.** A failed or cancelled build shows the same
checklist, read-only, built from the model's final snapshot, with the
failed row open. It replaces the separate "What the build said" block.
"It stopped at: …", the exit status, the log folder and Retry stay.

## Risks

- Stage names that a future CLI adds get the generic icon and their CLI
  name until the table learns them.
- Many lines per second: the model appends under a lock, and the UI work
  is coalesced to 10 refreshes a second, as the Details pane already
  does.
