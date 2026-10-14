## ADDED Requirements

### Requirement: Per-poll pad state is a trace
The game's `[INPUT] ... host port=N buttons=...` line (one per poll in which a host pad's state changed) and its `[INPUT] rumble port=N ...` line (one per change of the motor words) SHALL print only under `RECOMP_TRACE=input`, beside the `handles=` line already there. The `[INPUT] ... ports=0x..` change line, the scripted pad's `buttons=` line and the script's `script done` line are unchanged.

#### Scenario: Playing with a pad by default
- **WHEN** a player moves the sticks for a minute with no trace key set
- **THEN** the log gains no `host port=` or `rumble` lines

#### Scenario: Latency measurement
- **WHEN** `vpad.py` measures press-to-poll latency against a game started with `RECOMP_TRACE=input`
- **THEN** the `host port=` lines carry the `wall=` stamp it subtracts from, as before
