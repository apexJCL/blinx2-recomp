## MODIFIED Requirements

### Requirement: Measured indirect targets seed function detection
The pipeline SHALL pass a hand-maintained list of runtime-measured indirect-call targets (`config/seed_functions.json`) to function detection. Each listed address SHALL become a function start in the next recompilation. The pipeline SHALL NOT pass the raw `icall_feedback` database to `--seed-functions`. When the database exists, the disasm stage SHALL regenerate `analysis/icall_seeds.json` from it with `tools.recomp.icall_feedback seeds --xbe` and pass that filtered file as a second seed file.

#### Scenario: Thread entry inside a merged function
- **WHEN** the game starts a thread at `0x002D702E`
- **THEN** the dispatcher resolves it to `sub_002D702E`, and the thread runs instead of exiting immediately

#### Scenario: Seed list kept separate from generated feedback
- **WHEN** `tools/recomp/output/icall_targets.json` (or `$ICALL_DB`) exists and the disasm stage runs
- **THEN** `analysis/icall_seeds.json` is rewritten from it, disasm is invoked with `--seed-functions config/seed_functions.json --seed-functions analysis/icall_seeds.json`, and the hand-maintained list is not rewritten
