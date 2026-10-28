## ADDED Requirements

### Requirement: A script step requests a save state
The pad script SHALL accept `savestate NAME`, which requests a save state to the fixture path for NAME and waits, without advancing the script, until the save is written or refused for good. A refusal for good SHALL end a strict run with a desync line naming the reason.

#### Scenario: Fixture recipe
- **WHEN** a recipe ends `include @stage1; wait polls 30; savestate stage1-walk`
- **THEN** the state is written once the save's safe point is reached and `[INPUT] .. savestate stage1-walk written` is logged
