## ADDED Requirements

### Requirement: Glow toggle and intensity
BLiNX 2 SHALL offer two game keys in the enhancements layer, read once at startup before any guest thread runs, and only when the layer is built (`XBOXRECOMP_ENHANCE`):
- `fx.glow`: `"on"` (default) or `"off"`, env `RECOMP_GLOW`;
- `fx.glow_intensity`: a float clamped to 0.0..2.0, default 1.0, env `RECOMP_GLOW_INTENSITY`.

Both SHALL be bound to their env variables through `recomp_env` (CONFIG tier, `src/env/recomp_env_game.h`) and reported on one `[ENHANCE] fx.glow=<v> fx.glow_intensity=<v>` line.

The keys SHALL act only on the game's mode-3 glow composite, `sub_0005B7D0`, through a wrapper around its generated body:
- With `fx.glow = "on"` and `fx.glow_intensity = 1.0`, the wrapper SHALL call the generated body and SHALL neither read nor write guest memory.
- Otherwise it SHALL scale each colour byte of the glow weight at `0xADC744` by the cube root of the intensity, rounded to the nearest byte and clamped to 0xFF, keeping byte 3; `"off"` uses intensity 0. It SHALL call the generated body through `RECOMP_ABI_CALL`.
- After the call, the wrapper SHALL write the game's value back, unless the word no longer holds the scaled value, in which case it SHALL keep the newer game value.

The post mode, mode 4 (`sub_0005BC60`), both downsamples (`sub_0005B330`) and the game's per-frame fade of the weight (`sub_000E4140`) SHALL run as stock: the fade SHALL never read a scaled value.

#### Scenario: Defaults are stock
- **WHEN** the game runs with the layer and neither key set, or with `fx.glow = "on"` and `fx.glow_intensity = 1.0`
- **THEN** no guest word is written by the wrapper, the log reads `[ENHANCE] fx.glow=on fx.glow_intensity=1`, and the Metal goldens pass with the same verdicts as before the change

#### Scenario: Glow off
- **WHEN** Metal `@attract` runs with `RECOMP_GLOW=off` and dumps flip 1141
- **THEN** the frame matches a run with `RECOMP_DEBUG=poke=0xADC738:0` (the pass not issued) at that flip within the golden limits (channel mae ≤ 0.5, ≤ 0.5% pixels off by more than 8), and is darker than stock by 12 to 18 levels in mean RGB

#### Scenario: Half and double intensity
- **WHEN** Metal `@attract` runs with `RECOMP_GLOW_INTENSITY=0.5` and with `2.0`, each dumping flip 1141
- **THEN** each frame's mean glow layer (the frame minus the glow-off frame) is 0.40 to 0.60 and 1.5 to 2.2 times the stock layer, respectively

#### Scenario: Game weight restored
- **WHEN** the wrapper has run with `fx.glow_intensity = 0.5` and the game has not written `0xADC744` during the call
- **THEN** `0xADC744` holds the game's value again after the call; and when the game wrote it during the call, the game's new value is kept

#### Scenario: Game fade unchanged
- **WHEN** `@attract` runs for 60 s with `fx.glow_intensity = 0.5` and a write watchpoint on `0xADC744`
- **THEN** the values the game itself writes (every write that is not the wrapper's store-and-restore pair) form the same sequence as in a stock run of the same length

#### Scenario: Other post effects untouched
- **WHEN** the post mode is 4 or any value other than 3
- **THEN** the wrapper is not reached and the frame equals the stock frame

### Requirement: Glow keys stay out of goldens
The golden configuration SHALL pin `RECOMP_GLOW=on` and `RECOMP_GLOW_INTENSITY=1`. The golden harness SHALL fail a run whose log reports `fx.glow` other than `on` or `fx.glow_intensity` other than 1, unless the run is an evaluation run started with `--allow-enhance` for that key. Such a run SHALL NOT be used to record references.

#### Scenario: Harness rejects glow off
- **WHEN** `golden.py check` evaluates a run whose log contains `[ENHANCE] fx.glow=off fx.glow_intensity=1`
- **THEN** the run is marked FAIL with a reason naming `fx.glow`; with `--allow-enhance fx.glow=off` its frames are judged and the reason is printed as a note

#### Scenario: Backends agree
- **WHEN** one D3D11 run under Proton and one CPU run on the Mac each dump flip 1141 of `@attract` with `RECOMP_GLOW=off`
- **THEN** each matches the same backend's `poke=0xADC738:0` frame within the golden limits, as Metal does
