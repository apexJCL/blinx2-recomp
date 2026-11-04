## Why

The user asked (2026-10-19) for one wizard run to build several
platforms, for example Windows and the Steam Deck. Today the Platform
page is a single choice, so a player with a PC and a Deck runs the
wizard twice and waits through the shared work twice in the wizard's
eyes, even though the CLI already reuses it.

## What Changes

- **Platform page:** on a fresh build each buildable platform is a
  checkbox. This computer's platform is ticked first. Blocked platforms
  stay out of the list with their existing reason lines. The last ticked
  box cannot be unticked, so Next always has a platform.
- **Update stays one platform:** an update changes one computer's build
  from one base bundle (`--patch-from`), so the Update path keeps the
  single choice and says why.
- **Build:** the prerequisites (import, enhance hud) run once, then one
  `package <target>` per ticked platform in the CLI's order. `--clean`
  goes only on the first. The CLI's own incremental state reuses the
  import, the generated code and, for Windows and the Steam Deck, the
  same compile tree. No CLI change.
- **Pages:** the Summary lists the platforms, the plan's size per
  platform and the data folder per platform. The Building page heads
  each platform's parts with its icon and name. Done lists each
  platform's end and, for each one made, its bundle, install step,
  buttons and data folder.
- **Failures:** a failure in a platform's own compile or packaging lets
  the next platform run. A failure in a prerequisite or in shared work
  (import, setup, generate) stops the rest, which are listed as not
  built. A cancel stops everything.
- **Settings:** the ticked platforms are saved as `targets`. The reader
  takes a list, or a single string from an older or hand-edited file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `build-wizard` (added by `wizard-paths`, not archived yet): the
  Platform page's choice, the build's steps and the Summary, Building and
  Done pages for several platforms.

## Impact

- **Code** (all in `xboxrecomp-cli/wizard/internal/`): `model` (State's
  `Targets`, `SetTargets`, `Builds`, `For`, `StepTargets`), `runner`
  (the checklist's `Group`), `hostinfo` (the saved `targets`), and in
  `screens` the Platform page, the build loop, the Summary, Done and
  the parts view, plus tests and screenshots.
- **CLI (Python):** none. `xbr package` already makes one target per run
  and reuses the shared work between runs.
- **Games:** none. cat and b3 take the change with the next CLI pin.
