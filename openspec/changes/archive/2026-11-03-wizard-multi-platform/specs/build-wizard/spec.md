## ADDED Requirements

### Requirement: A fresh build can make several platforms in one run
On the Fresh path the Platform page SHALL offer each buildable platform as a checkbox, with this computer's platform ticked first, and SHALL keep at least one ticked. The wizard SHALL run the prerequisite commands once, then `package` once per ticked platform, and SHALL pass `--clean` to one run a session: the first, or the next one when the first stopped before the CLI cleaned. A Retry after the clean SHALL NOT clean again. With several platforms ticked, the Summary SHALL sum the plans' disk needs per volume and warn when the sum is more than is free. Blocked platforms SHALL stay unavailable with their reason. The ticked platforms SHALL be saved in the settings, and a settings file holding a single platform string SHALL be read as that one platform.

#### Scenario: Windows and the Steam Deck
- **WHEN** the player ticks Windows and Steam Deck or Linux and builds
- **THEN** the wizard runs `package windows` then `package steamos`, the Building page heads each one's parts with its name, and Done shows both bundles

### Requirement: An update is for one platform
On the Update path the Platform page SHALL offer a single choice and SHALL say that an update is for one computer at a time.

#### Scenario: Update after a two-platform fresh build
- **WHEN** the saved settings tick two platforms and the player picks Update
- **THEN** the Platform page shows one choice and the build runs one `package` with its `--patch-from`

### Requirement: One platform's own failure does not stop the others
When a platform's `package` run fails in its package stage, the wizard SHALL go on to the next platform. When it fails in its build stage, the wizard SHALL list the later platforms on the same compile tree as not built and SHALL go on to the others. When a prerequisite fails, or a `package` run fails before any stage, in shared work (import, setup or generate) or for disk space, the wizard SHALL stop and list the remaining platforms as not built. Done SHALL list each platform's end and, for each one made, its bundle and install step.

#### Scenario: The Steam Deck build fails to compile
- **WHEN** Windows, Steam Deck or Linux and macOS are ticked and the Steam Deck's run fails in build
- **THEN** macOS is still built, and Done says Windows and macOS are ready and the Steam Deck stopped at build, with the failure's log and buttons

#### Scenario: Generate fails on the first platform
- **WHEN** the first platform's run fails in generate
- **THEN** no other platform runs, and Done lists them as not built

#### Scenario: Windows fails to compile
- **WHEN** Windows, Steam Deck or Linux and macOS are ticked and the Windows run fails in build
- **THEN** the Steam Deck is listed as not built, macOS is still built, and Done's log folder is the Windows run's

#### Scenario: Short of disk space
- **WHEN** the first platform's run refuses for disk space
- **THEN** no other platform runs, and Done lists them as not built

#### Scenario: Retry after a clean rebuild
- **WHEN** the player ticked Rebuild everything, the first platform's run cleaned and a later one failed, and the player presses Retry
- **THEN** no run of the Retry passes `--clean`
