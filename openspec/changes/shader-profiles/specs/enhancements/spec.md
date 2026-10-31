## ADDED Requirements

### Requirement: Shader profiles default to stock
`present.profile` SHALL default to `"none"`. With it `none` and
`present.shader` `none`, no profile SHALL be composed, no chain built and the
present SHALL be stock, and no profile file SHALL be read before the menu
opens the Shaders page. With `RECOMP_CONFIG=none` no profile file SHALL be
read.

#### Scenario: Golden run
- **WHEN** a golden runs with `RECOMP_CONFIG=none`
- **THEN** the log shows `present.profile` off and the frames match stock

### Requirement: A profile is an ordered chain with its own values
A shader profile SHALL be a TOML file `<root>/config/shader-profiles/<slug>.toml`,
in that folder even when a per-title config file exists, with `version = 1`, a `name`, a `stages` array of 1 to 8 preset references
(the `present.shader` grammar), and `[params.<preset key>]` tables holding
only the values that differ from the composed preset's. A file with an
unknown higher version SHALL be listed read-only and never written; a file
that does not parse SHALL be listed as broken and never written. A value
for a parameter shared by several stages SHALL be read from any stage's
table and saved under the first stage that declares it.

#### Scenario: Round trip keeps comments
- **WHEN** the menu saves a hand-written profile after moving a stage
- **THEN** only the `stages` line changes, unless a shared value changes owner, and its comments and unknown keys stay

### Requirement: A multi-stage profile runs as one composed preset
A profile of two or more stages SHALL be composed into one `.slangp` (passes
in stage order, each preset's own pass settings, absolute paths, the earlier
stage winning a preset parameter value) and run through the same path as
`present.shader` on Metal and D3D11. A one-stage profile SHALL run its
preset as `present.shader` does. A parameter name declared by more than one
stage SHALL be one value, and the menu SHALL mark its row "shared with
stage N", naming the first stage that declares it. Preset-level
`parameters` lists SHALL be merged without duplicates. Paths SHALL be
written quoted with forward slashes. Two stages declaring the same alias or
texture name SHALL NOT compose, nor SHALL a stage after the first that
refers to a pass by index (`PassOutputN`, `PassFeedbackN`).

#### Scenario: FSR then CRT
- **WHEN** the profile's stages are `fsr`, `crt-lottes`
- **THEN** the chain has three passes on Metal and on D3D11, and the menu lists the parameters of both

### Requirement: A failed profile presents stock and says so
A profile that is missing, broken, refused by the composer or whose chain
fails to build SHALL give the stock present, one `[SHADER]` line naming the
profile and, where known, the stage, and a red row on the Shaders page. It
SHALL NOT be retried until the next change.

#### Scenario: A stage is missing
- **WHEN** a profile names a `.slangp` that does not exist
- **THEN** the present is stock, the log names the stage, and the Chain header is red

### Requirement: The existing shader setting keeps working
`present.shader` and `present.shader_params` SHALL keep their meaning. The
bundled presets SHALL appear as built-in one-stage profiles whose values are
those keys. `RECOMP_PRESENT_SHADER` SHALL win over a profile, and
`RECOMP_PRESENT_PROFILE` over the config. Among the config layers the
highest layer that sets either `present.profile` or `present.shader` SHALL
decide, and within it a set `present.profile` SHALL win over
`present.shader`; a set but missing profile SHALL give stock, not
`present.shader`. When the menu saves a choice that needs a key gone and a
lower layer sets that key, it SHALL write the key as `"none"`.

#### Scenario: A per-title shader over a shared profile
- **WHEN** the per-title config sets `present.shader = "fsr"` and `<root>/config/config.toml` sets `present.profile = "soft-crt"`
- **THEN** the run presents `fsr`

#### Scenario: An existing config
- **WHEN** a config has `present.shader = "crt-lottes"` and tuned `[present.shader_params.crt-lottes]` and no profile
- **THEN** the run is unchanged and the Shaders page shows the built-in *crt-lottes* with those values

### Requirement: The Shaders page edits profiles on pad and keyboard
The Shaders page SHALL let the player pick the active profile (Off, the
built-ins, user profiles), add a stage, move a stage earlier or later, remove
a stage (with a confirm, never the last), edit a stage's parameters, reset
them, save as new, duplicate, rename and delete a profile, with the menu's
existing events on the pad and the keyboard. Save SHALL write only the
profiles that changed and only the values that differ from the presets'.

#### Scenario: Reorder and save
- **WHEN** the player moves a stage with Right and presses Save
- **THEN** the chain changes at the next present and the profile file's `stages` line is the only line rewritten, unless a shared value changes owner

#### Scenario: Typing a name
- **WHEN** the player renames a profile on the keyboard and types Q, E, Y or Space
- **THEN** the characters go into the name and no page change or Save fires

### Requirement: Profile limits and the user presets folder
A profile SHALL hold at most 8 stages, and its composed preset at most 16
passes. An edit past either limit SHALL be refused with a footer message,
and a file past the stage limit SHALL load its first 8 stages with one log
line. The Add shader picker SHALL list the bundled presets and then the
`.slangp` files in `<root>/shaders/`; a user preset whose name equals a
bundled one SHALL be refused. A stage's relative or bare name SHALL resolve
against `<root>/shaders/` before the executable's directory. A profile SHALL NOT carry per-pass
scale or filter settings: each pass SHALL keep its preset's own.

#### Scenario: Ninth stage
- **WHEN** the player adds a stage to a profile that has 8
- **THEN** the Add row is dimmed and the footer names the limit
