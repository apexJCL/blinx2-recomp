## MODIFIED Requirements

### Requirement: Packaged games accept a controller by default
The packaged macOS app's default settings SHALL set `RECOMP_HOST_PAD=1`. The Windows and steamos bundles SHALL keep host pads on through the runtime's Windows default. Every bundle SHALL enable the keyboard and the mouse as a port-0 source that merges with a real pad and never masks it, through `input.keyboard = true` and `input.mouse = true` in the shipped `config.default.toml`, and no `launch.env.default` SHALL set `RECOMP_KEYBOARD` or `RECOMP_MOUSE`, so the player's `config/config.toml` can turn either off. The runtime's own default for an unset `RECOMP_HOST_PAD`, `RECOMP_KEYBOARD` or `RECOMP_MOUSE` SHALL NOT change.

#### Scenario: Controller on the Mac
- **WHEN** the packaged macOS app starts with a controller connected and no user override
- **THEN** the game log shows `host=on` and the controller drives the game

#### Scenario: Keyboard and mouse in every bundle
- **WHEN** a bundle starts with no controller and no user override
- **THEN** the game log shows `keyboard=on mouse=on ports=0x1`, Return advances the title, and the cursor is captured while the window has focus

#### Scenario: Player turns the mouse off
- **WHEN** the player's `config/config.toml` holds `[input]` `mouse = false`
- **THEN** the next launch logs `mouse=off`, the cursor is never captured, and the keyboard still works

#### Scenario: Golden runs unaffected
- **WHEN** `blinx2 bench golden` runs
- **THEN** every scenario's `sources` line reports `host=off keyboard=off mouse=off` as pinned by `golden.json`
