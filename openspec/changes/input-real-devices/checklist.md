# Manual checklist: the normal route with a real controller (Proton)

Run on the Linux/Proton host through `blinx2 bench run` (it takes the run lock and writes
`bench-logs/<stamp>/`), with the D3D11 backend, no `RECOMP_INPUT_SCRIPT`, the host
pad on (the default without a script) and an empty `RECOMP_SAVE_DIR`. Keep the
filled copy locally as `analysis/bringup/input/manual-<stamp>.md` (local analysis, not published); never commit
frames or saves. Mark each item pass / fail / n.a. and note the time in the run.

How to launch (from the Mac, `cat/scripts`; a fresh save dir under the run's
log dir, kept locally):

    BENCH_ENV="RECOMP_SAVE_DIR=@run" BENCH_TIMEOUT=1800 blinx2 bench run

For D5 (relaunch with the save made in the first run), pass that run's save dir
instead, as a Wine path: `BENCH_ENV="RECOMP_SAVE_DIR=Z:<host path of
bench-logs/<stamp>/save>"`. For H, add `RECOMP_KEYBOARD=1` to BENCH_ENV. The
screens, title states and files of each step are in design.md § "Menu
catalogue"; the scripted reference run is `@story-hub`.

Setup to record first: controller model, connection (USB / Bluetooth), launched
through Steam (Steam Input on) or bare `umu-run`, `PROTON_ENABLE_HIDRAW`, Proton
build, the `[INPUT] sources` line.

## A. Boot and intro
- [ ] A1 `logo_mgs.sfd` plays; START skips it (and the Artoon logo).
- [ ] A2 `blinx2_opening.sfd` plays; START skips it.
- [ ] A3 `title_movie_1a.sfd` opens; "press start" appears; START is ignored for the first seconds, then taken.
- [ ] A4 Left alone for 20 s, the title does nothing else (the attract demo starts after about 600 frames; note the time).

## B. Title and story opening
- [ ] B1 START on the title goes to the story (title state 0x5EB620 leaves 0; `R0_opening.sfd` opens).
- [ ] B2 START during R0_opening is ignored; A skips it.
- [ ] B3 With no controller connected at the title: what the title shows (a prompt, or nothing). Note it.

## C. Team editor (LOCKER ROOM, tsedit)
- [ ] C1 The LOCKER ROOM host's dialogue plays (A advances), then AUTO SELECT / CUSTOM SELECT appears (CONFIRM A, EXIT B). Note whether B backs out.
- [ ] C2 UP/DOWN/LEFT/RIGHT move the cursor; A confirms; B goes back. Note any button that does nothing.
- [ ] C3 AUTO SELECT, then "Is this your team? ... press A.", A reaches "Congratulations! Your team is ready to go!" and returns to the title. AUTO SELECT picks a random team (Cougars, Steel Paw, Crystal Cats seen): note which.
- [ ] C4 Optional: CUSTOM SELECT; walk its screens once and note what each asks for (not scripted yet).

## D. Story Mode and save
- [ ] D1 Story Mode / SAVE GAME appears (no save present).
- [ ] D2 Slot 1 to 3 selectable; 1P MODE / 2P MODE; NOW SAVING shows.
- [ ] D3 `blinx2data.bin` and `SaveMeta.xbx` exist under `RECOMP_SAVE_DIR/UDATA/4d530065/13C91777168C/` after NOW SAVING.
- [ ] D4 No memory-unit prompt or MU slot appears anywhere (none is reported).
- [ ] D5 Quit and relaunch with the same save dir: START on the title goes to LOAD GAME; loading returns to the hub.

## E. Hub and drill
- [ ] E1 The hub loads (`song_HUBsw.adx`); the CHALLENGE drill "Test 1 of 7" starts.
- [ ] E2 Right stick looks around; the drill's balloon test completes. Note the right stick's vertical direction (bug 3.6).
- [ ] E3 Left stick walks; A jumps; camera follows. Note stick drift at rest and whether the game's own deadzone hides it.
- [ ] E4 START pauses ("GAME PAUSED"); START resumes.
- [ ] E5 How the hub leads to stage 1-1 (gate, terminal, menu): write down each screen and the buttons, with the files that open (`[FILE]` lines). This feeds task 7.1.

## F. Stage 1-1
- [ ] F1 stg0101 loads; Operator dialogue (A advances); MISSION OBJECTIVES; checkpoint; HUD timer runs.
- [ ] F2 L and R triggers: what they do in play (sweep / shoot / nothing); analog feel if any.
  Note: under Proton a device's very first trigger event is dropped when it lands at mid-travel straight from rest (seen with a virtual pad, tasks 3.8; likely SDL2's first-axis-value filter). Later values, and any press that starts low, arrive exact (0..255).
- [ ] F3 White (LB) and Black (RB): what they do; confirm they are not swapped against the in-game button prompts.
- [ ] F4 Rumble on a hit or a sweep; it stops when the game quits.

## G. Hot-plug
- [ ] G1 Unplug the controller in a menu: what the game shows; replug: the menu works again.
- [ ] G2 Unplug in play: pause or prompt?; replug: play resumes.
- [ ] G3 `[INPUT]` log shows `ports=0x0` and `ports=0x1` at the right moments.

## H. Keyboard (optional, `RECOMP_KEYBOARD=1`)
- [ ] H1 Enter = START on the title; Z = A in the story opening; arrows move menu cursors; W/S/A/D walk Stick in the hub (laptop map, D9).
- [ ] H2 With the window unfocused, keys do nothing.

Findings go back into `openspec/changes/input-real-devices/tasks.md` (6.6) and, for
anything the port cannot match, `openspec/changes/deviations-register`.
