## Why

The user, testing the wizard on Windows on 2026-10-15 (verbatim):

- "currently building and the timer says "MM:SS in this part...", can we
  show the actual part/step name instead of "this part"?"
- "Also, if the parts are known beforehand, probably we could just
  display a checklist of each part in order, and show individual
  progress/step. That way it is clearer to the user where the process is
  at, logs can be rendered in isolation instead of a single window and
  will look nicer. Each entry could have a dedicated icon to make it
  nicer, and use appropriate working/ready colors"
- "Details at the bottom can still show the logs as normal, as a way to
  also show logs fully aggregated"

Today the Building page shows one bar, one label ("Part 3 of 5: build
(recomp)"), one clock line ("42% · 4:12 in this part · 12:40 in all")
and one log pane. The player cannot see what is done, what is left, or
which output belongs to which part.

## What changes

- The Building page shows an ordered **checklist of the build's parts**.
  Each row has an icon for what the part does, a player-facing name, a
  state (pending, working, done, failed, skipped or cancelled; an icon,
  a theme colour and words for each), and for the running part its own
  step, percentage or `[i/n]`, clock and a thin bar. Each row has its own
  log, which expands in place and holds only that part's output.
- The page keeps one overall line: the part count, the percentage and
  the total clock ("Part 3 of 6 · 42% · 12:40 in all"). The **Details**
  pane at the bottom stays as it is: the full, aggregated log.
- Request 3 is folded in. The running part's clock sits in its own row,
  beside its name, so "in this part" goes away. The overall line keeps
  only the total.
- A failed part opens on its own and shows the failure excerpt
  (wizard-build-feedback's `failureExcerpt`, from that part's lines). The
  Done page of a failed or cancelled build shows the same checklist, with
  the failed row open, in place of the separate excerpt block.

## Not in scope

- New CLI output. The plan line, the stage lines and the step lines that
  `package --plain` prints today are enough (design D1).
- Changing which commands the wizard runs.
