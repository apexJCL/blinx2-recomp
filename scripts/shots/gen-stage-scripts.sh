#!/bin/sh
# Regenerate the per-stage pad scripts in pad/ from pad/stage.txt.in: the
# title's debug stage select, which the retail game keeps but never enters.
# The pokes in the template (title state machine sub_000133E0):
#   0x005EB5F4  -> the title state block, 0x005EB620 once the title runs
#   0x005EB620  title state: 0 press start, 1 debug menu, 0xB SELECT A STAGE,
#               0x13 leaving for the stage
#   0x005EB630  debug menu cursor (0 = 1P_MISSION(NORMAL))
#   0x005EB638  stage cursor: index into the 32-byte names table at 0x3F15C0
#               (1 "St1-4 BOSS1", 6 "St2-4 BOSS2", 0x1C "St6-4 LASTBOSS", ...)
#   0x00B22E3C  players in the menu, 0x00AE7A10 player 0's pad (START on
#               "press start" sets them; the menus ignore the pad without)
#   0x00AE73FC  1 once the stage's first checkpoint is taken (play starts)
# A is tapped through the intro dialogue, then a stick/A/X/B cycle keeps
# something happening on screen.
cd "$(dirname "$0")/pad"
gen() { sed "s/@IDX@/$2/g" stage.txt.in > "$1.txt"
  i=0; while [ $i -lt 20 ]; do
    echo 'LX=20000,LY=20000;X/0.3;wait 1;A/0.3;wait 1;LX=-20000,LY=12000;X/0.3;wait 1;B/0.3;wait 1;LX=0,LY=-20000;A/0.3;wait 1;X/0.3;wait 1' >> "$1.txt"
    i=$((i+1)); done; }
gen boss1 1; gen boss2 6; gen boss3 0xd; gen boss4 0x10; gen boss5 0x15
gen boss5in 0x19; gen lastboss 0x1c; gen lastrd 0x2b; gen tomtom1 2; gen vs1 3
gen st2 5; gen st3 0xa; gen st4 0xf; gen st5 0x14; gen bonus 0x28
gen hubswe 0x32; gen hubtom 0x37
