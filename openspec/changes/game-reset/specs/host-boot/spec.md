## MODIFIED Requirements

### Requirement: Boot order
The host SHALL initialize the runtime in this order, and SHALL NOT enter guest code until every step has succeeded or been explicitly declared optional:
1. install crash diagnostics
2. load the XBE
3. map the Xbox memory layout
4. start the emulated APU (optional; only when requested and the host supports it, see below)
5. initialize the kernel
6. set the game and save directories
7. initialize the kernel bridge
8. set the guest stack pointer to the top of the Xbox stack
9. build the dispatch table (optional)
10. start the hang watchdog
11. call the recompiled entry point (`0x0029A1DA`)

Steps 1 to 7, 9 and 10 are the host half and SHALL run once per process. A game that boots through the toolkit's boot loop (`xbox_boot_run`) SHALL hand it steps 8 and 11 and its own guest-side setup (the XBE init-flag patch, the game's boot callback); the loop runs them, and after a restart runs them again. Before the guest half runs again, the reset SHALL have cleared guest memory in place, loaded the XBE's sections again, and run again the guest-memory parts of steps 4 and 7 (the thunk table patch, the kernel's exported data, the thread blocks and stacks, the APU's guest windows). After a restart the loop SHALL print one `[RESET] boot <n>` line before the guest half. A pre-launch screen, once one exists, belongs to the host half and SHALL NOT be shown again. With no restart, the order and its output SHALL be unchanged.

#### Scenario: Optional dispatch table
- **WHEN** the flat dispatch table cannot be allocated
- **THEN** the host prints one line saying indirect calls will use the binary search, and continues booting

#### Scenario: Crash diagnostics armed before guest code
- **WHEN** the first guest instruction executes
- **THEN** the crash diagnostics from `host-crash-diagnostics` are already installed

#### Scenario: Second boot
- **WHEN** the player restarts the game once
- **THEN** the log shows the first boot's lines, the `[RESET]` lines, then `[RESET] boot 1`, and the title's own boot output again, in the same process, with no host-half step run twice

#### Scenario: No restart
- **WHEN** the game starts and is never restarted
- **THEN** no `[RESET]` line is printed and the boot output is as before this change

### Requirement: Clean exit
When the guest entry point returns, the host SHALL shut down the kernel and memory layout, release the XBE buffer, and exit with status 0. A restart SHALL NOT go through this path: the boot loop runs the guest half again instead, and the shutdown runs once, when the process ends. A title's `HalReturnToFirmware` SHALL still end the process, before or after a restart.

#### Scenario: Guest returns
- **WHEN** the recompiled entry point returns normally
- **THEN** the host prints that the game returned, runs shutdown, and exits 0

#### Scenario: The title exits itself
- **WHEN** the title calls `HalReturnToFirmware`, before or after a restart
- **THEN** the process ends with `[EXIT] HalReturnToFirmware` in the log, as on a first boot
