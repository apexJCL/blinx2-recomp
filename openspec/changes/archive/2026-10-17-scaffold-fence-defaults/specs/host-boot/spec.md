## ADDED Requirements

### Requirement: A new game's template boots with the XDK D3D defaults
The toolkit's new-game template (`templates/new-game/src/main.c`, the file `xbr new` copies into every new game) SHALL, after the Xbox memory layout is mapped and before the kernel is initialised, set `RECOMP_VBLANK` to `1` and `RECOMP_TITLE_KEVENTS` to `1` unless the environment already sets each, with a comment on each that says why (XDK D3D paces its swap, vblank wait and vblank callback on the vblank DPC; that DPC sets a KEVENT D3D built without `KeInitializeEvent`). It SHALL carry, before those two, a fence block whose last line is the commented example `/* xbox_Nv2aMirrorFence(0x00000000, 0x2C, 0x30); */` and whose comment names the device layout (`+0x2C` submitted, `+0x30` pointer to the completed word), the three known pointers (BLiNX 2 `0x2F1FB8`, Spartan `0x235528`, Burnout 3 `0x35FB48`) and where the porting doc explains how to find one. The example SHALL compile as a comment, so a scaffold the CLI could not fill builds and runs as before.

`xbr new` SHALL look for D3D's fence wait in the dump it reads the header from (the `D3D` section, or every executable section when there is none), by the instruction sequence `mov esi, [ptr]; (push edi; mov edi, eax;)? mov eax, [esi+g]; mov ecx, [eax]; mov eax, [esi+p]; mov edx, eax; sub edx, ecx`, and SHALL replace the example line with `xbox_Nv2aMirrorFence(ptr, p, g);` only when that sequence occurs exactly once; `p` and `g` SHALL come from the match. In every other case (no dump read, no match, several matches) the example line SHALL stay and the summary SHALL say which case it was and point at the porting doc. The summary SHALL name the XDK libraries and builds the dump's library table lists. Against a template without the example line, a found fence SHALL produce a note telling the porter to add the line, never an error.

#### Scenario: Fresh scaffold of an XDK 5849 title
- **WHEN** `xbr new` scaffolds Spartan: Total Warrior from its dump and the game is built with no hand edit to `src/main.c`
- **THEN** `src/main.c` carries `xbox_Nv2aMirrorFence(0x00235528, 0x2C, 0x30);`, the runtime logs `NV2A fence mirror: device at 0x00235528` and later `now written by the executor; mirror off`, and the boot reaches the same stop as the hand-edited game (the `KeDelayExecutionThread` poll under `sub_001ADCA0`) on the Mac and under Proton

#### Scenario: The fence wait is not found
- **WHEN** the dump cannot be read, has no match, or has more than one
- **THEN** the example line is left as a comment, the summary says `D3D fence: not found (<reason>)` and names `docs/porting.md`'s "The D3D fence", and the scaffold builds

#### Scenario: The defaults can be switched off
- **WHEN** `RECOMP_VBLANK=0` or `RECOMP_TITLE_KEVENTS=0` is in the environment of a scaffolded game
- **THEN** the template's default does not override it: with `RECOMP_VBLANK=0` no vblank is raised and the boot stops in D3D's vblank wait; with `RECOMP_TITLE_KEVENTS=0` the vblank DPC's `KeSetEvent` fails as before the default

#### Scenario: The template is checked by the toolkit's own test
- **WHEN** `tests/template_main` runs
- **THEN** it builds the template with the new lines, and its `defaults` test fails if either guarded `recomp_env_set` line or the example line is missing or changed
