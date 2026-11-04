## ADDED Requirements

### Requirement: The wizard asks before building a dump it cannot vouch for
For a plan whose xbe verdict is `unknown` (truncated included), or another
release with differing sections, the wizard SHALL show a Summary line and
the build-anyway dialog before the build, with no default button and the
way back first. Known dumps and header-only differences SHALL build without
a question.

#### Scenario: Other release
- **WHEN** the plan says another release with code sections that differ
- **THEN** the dialog names both releases and the build starts only on the explicit build-anyway choice
