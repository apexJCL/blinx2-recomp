## Context

`xbr package <target>` makes one target per run. Its stages are import
(when `--dump` is given and the import is not current), setup, generate
(skipped when current, see `pipeline.gen_stale_reasons`), build and
package. The build tree is `build_target(t)`: `macos` for macOS and
`windows` for every other target, so the Steam Deck's `.tar` and the
Windows setup share `build-pkg-win`. Running `package windows` and then
`package steamos` therefore imports and generates once and compiles
once. `prune_bundles` keeps bundles per target, so one run does not
prune the other's bundle.

## Goals / Non-Goals

- Goals: several platforms in one fresh run; each platform's progress
  and end on the pages; one platform's own failure costs only its
  installer.
- Non-Goals: a CLI verb that packages several targets; parallel
  platform builds; several platforms in an update.

## Decisions

### D1. The wizard runs package once per platform

`State.StepTargets` returns the prerequisites (target "") and then one
`PackageArgs` per platform from `Builds()`. The run loop adds
`--clean` once a session: on the first `package` run, and again on the
next run only if that one stopped before its `plan:` line (the CLI
prints it after the clean). A Retry after a clean does not clean again,
and ticking "Rebuild everything" again owes a new one. The CLI
reuses the shared work by its own staleness checks, so the wizard does
not need to know which stages are shared.
Alternative: a `package --targets a,b` in the CLI. It would duplicate
what the incremental state already gives and change a public command.

### D2. Update keeps one platform

An update is a patch from one base bundle, which is one platform's.
The Update path keeps the radios and its intro says an update is for
one computer at a time. `Builds()` returns the single `Target` on
Update.

### D3. Failure policy: continue after a platform's own failure

The progress parser knows the stage a run stopped in. When a package
run fails in `package`, the next platform runs: a packaging failure is
its own. When it fails in `build`, the later platforms on the same
compile tree (Windows and SteamOS share one, macOS has its own: the
CLI's `build_target`) are listed as not built, and those on another
tree still run. When a prerequisite fails, or package fails in
`import`, `setup`, `generate` or before any stage (the toolkit fetch, a
refused config, seed or content), or refuses for disk space, the run
stops and the rest are listed as not built: they share that work, or
the disk, and would fail the same way, only slower. A cancel stops
every platform. The run's error is the first failure, and Done shows its
details as before.

### D4. Pages

- **Platform:** checkboxes on Fresh, radios on Update, each with the
  platform glyph. Next needs every chosen platform buildable; the last
  ticked box stays ticked.
- **Summary:** "Platforms: a, b", a `Makes:` line and a data line per
  platform. The plan is asked once per platform; any plan short on disk
  shows the disk warning. With several ticked, the plans' `disk` lists
  are summed per volume as one run writes them (shared stages once, the
  largest; a compile per tree; staging and bundle per platform; the
  largest slack), and a sum over the free space says to untick a
  platform or free space. An older CLI's plan has no `disk` list and adds
  nothing; each run's own check still refuses. No CLI change.
- **This computer:** the notes about this computer (the config path,
  the override and the install step) follow this computer's platform
  when it is among those ticked, else the first ticked.
- **Building:** the checklist's parts carry a `Group` (the platform);
  the parts view heads each group with its icon and short name. One
  platform shows no heading.
- **Done:** each made platform has its ready line, bundle, install step,
  Open the folder, Install now (this computer's platform only) and data
  line. With a mix, a list of each platform's end comes first ("ready",
  "stopped at <step>", "not built"), then the first failure's details,
  its log folder from the failed platform's run.
  Retry runs every ticked platform again; the CLI skips what is current.

### D5. Settings

`Settings.Targets` is a `hostinfo.Targets` whose JSON reader takes a
list, a single string (the old one-value form) or anything else as
empty, and never fails the whole settings file. Unknown targets are
dropped by `SetTargets`.

## Risks / Trade-offs

- **Retry rebuilds the made platforms too.** Their stages are current,
  so it costs little; keeping per-platform retry is a later change.
- **A Windows compile failure is not retried on the Steam Deck build,
  which shares its tree.** It runs and fails the same way. The policy
  keys on the stage, not the tree, to stay game-agnostic; the cost is
  one quick extra failure.

## Migration Plan

None: an old settings file without `targets` keeps this computer's
platform.

## Open Questions

None.
