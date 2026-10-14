## ADDED Requirements

### Requirement: Keyboard and mouse as a Duke on port 0
The host keyboard and mouse SHALL be presented to the title as a Duke on port 0 (`toolkit:src/input/keyboard.c`, `mouse.c`): a stick key ramps to full deflection over `input.stick_ramp_ms` and two perpendicular keys are circle-normalised; a held walk key scales the stick; mouse motion between two polls becomes a stick deflection with a floor above the title's 0.4 deadzone and reads zero when the mouse rests; face buttons, shoulders, triggers and stick clicks from a key or a mouse button are 255 or 0.
- Reason: a PC has a keyboard and a mouse and often no controller; the title is unplayable without a port-0 pad, and its camera is the right stick.
- Risk: the triggers, which the title reads as analog, never report a partial pull from a key; a stick from keys has at most the ramp's resolution; the camera turns at a rate set by mouse speed rather than by a fixed angle per distance, so a flick is not a turn of a fixed size; a mouse at any speed turns at least at the floor's rate.
- Detect: a game mechanic that needs a half-pulled trigger or a held partial stick (none known; `analysis/bringup/input/analog-audit.md`, local); the `mouse` trace shows the model's output.
- Exit: none planned; the knobs (`stick_ramp_ms`, `walk_scale`, `mouse_sensitivity`, `mouse_min_deflection`) are the player's. Retired only if the title is found to need analog pressure from the keyboard, which would want a pressure modifier key.

#### Scenario: Suspected analog shortfall
- **WHEN** a move works on a controller and not on the keyboard
- **THEN** the trigger and stick values of the two runs are compared in the `[INPUT] host port=0` lines before anything else is suspected
