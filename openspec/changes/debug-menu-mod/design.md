## Context

The title (`sub_000133E0`) runs a 27-state machine in the block at
`0x5EB620`; `[0x5EB5F4]` points at the block while the title runs. State 0
is PRESS START, state 1 the debug menu (cursor `0x5EB630`), state 0xB
SELECT A STAGE (cursor `0x5EB638`, names at `0x3F15C0 + i*32`), 0x13 leaving
for the stage. The menus read the pad only for players `i < [0xB22E3C]`
through `[0xAE7A10 + i*4]`; the START handler of state 0 sets both, so a
poke into state 1 must too (blinx2-menu-flow.md, runs r4 and r5). The
`@stage1` preset and `runs/enemy-respawn/go-5-1.txt` prove the sequence.

The toolkit's mod API v4 gives a cat mod: a settings descriptor (the Mods
page's switch and rows, the describe dump), `menu_add` rows on the mod's
own page, `on_frame` on the guest's thread, `toast`, and descriptor ACTION
controls (host actions). No toolkit change is needed.

## Decisions

### D1. A mod with a menu row, not a game-page item
The `debug_menu` mod declares `enable` (its switch, default off), an
ACTION control `open` (host action `debug_menu.open`, unbound), and adds
two rows to its Mods sub-page: "Open the debug menu" (ACTION) and "Status"
(INFO). It is off by default like every enhancement; the player turns it on
on the Mods page (live) and then uses the row.

### D2. Only from PRESS START; no forced return to the title
Opening from PRESS START is the path the game's own START handler takes, so
the guest state is consistent. From a stage, the pause menu or the story
menus the mod would have to unwind the game's scene stack (stage teardown,
streaming, saves), for which no safe path is known; a wrong guess corrupts
the session. So elsewhere the row stays, its Status reads "go to the title's
PRESS START first", and a press only toasts that. The title is reachable by
the game's own means (quit from the pause menu, or a restart).

PRESS START is `[0x5EB5F4] == 0x5EB620` and `[0x5EB620] == 0`, but boot
sets that pointer and zeroes the block before the title first runs, so the
test alone is true through the logos and intro movies. The mod also needs
the scene loop (`sub_00062FB0`, scene `[0xAE73F0]`, bit 0x80 once inited)
on the title: scene 0x81 or 0x9C. The intro movies run at scene 0x80
(run fx3: F4 during them toasts and writes nothing).

### D3. Guest writes on the guest thread
The row's `set()` and the host action run on the menu or input thread; they
set an atomic request. `on_frame` (guest thread, `xbox_mod_frame`) takes the
request, checks PRESS START from guest memory, and writes players, pad,
both cursors and finally the state, the order the input scripts use. The
stage list's cursor `[0x5EB638]` is zeroed too: the game keeps it across
visits, and a stale one from a VS pick could point past the 1P list. The
Status row only reads two dwords from the menu thread; a stale read shows a
stale hint for one frame and changes nothing.

The overlay menu stays open after the press (the game reads a released pad
while it is open); the toast says to close it. A mod cannot close the menu
from the guest thread without racing the menu's step lock.

The host action fires through the actions hook, which the overlay menu arms
while it is on. The mod calls `actions_arm("mods.debug_menu.enable")` in
init, so with `RECOMP_MENU=0` its switch arms the hook and the binding still
works (run fx3, `RECOMP_MENU=0`, F4).

### D4. Unsafe rows: skipped by the cursor
Each debug row was entered headless on Metal (entry runs, tasks 2.1). A row
that hangs the port gets its bit in `dbgm_unsafe`; while the debug menu
shows, `on_frame` moves a cursor that lands on such a row on to the next
safe row in the direction it moved (wrapping). The text still shows, but it
cannot be picked. Each unsafe row is a follow-up item.

The handler takes the step and A in the same call, so a step and A in one
poll would pick the unsafe row before the after-the-fact skip runs. The mod
runs right after the pad poll (`sub_0005C930`), so it reads the step from
the pad structs (`[0xADC794] + idx*0x1E4`, edge byte +0x9A, repeat byte
+0xCE, for each player in the menu) and, when the step would land on an
unsafe row, writes the cursor one step short of the next safe row, so the
handler's own step lands there (run fx3: Up+A in one poll from row 0
logged "stepped past THEATER" and "picked MOVIE"). A cursor already on an
unsafe row (an outside write) gets the same treatment: the fallback moves
it to the safe row past it and, with a step that poll, one step short of
the next safe row from there (`dbgm_cursor_guard`).

Measured (runs e00-e14): none crash; four never leave the loading screen
with a retail disc. MODEL_EDIT (row 9) retries `d:\edit_model\`, which only
a development disc had. GARAGE (11) wants a loose
`garage_ts_us.ipk`. ENDING (13) and THEATER (14) wait with no file
open, likely on state a cold start lacks. The other eleven rows
load.

### D5. No team setting
`[0xB21CB4]` is the team mode (0 Sweepers, 1 Tom Tom, 3 VS). A first cut
had a `team` setting, but the game sets the team from the pick: a MISSION
row's A writes 0 (`0x150EE`), and the stage list's A (`0x156BF`-`0x15797`)
writes it from the stage, 1 for the TOMTOM stages (index % 5 == 2, and
0x19) and the TOMTOM BASE, 0 otherwise. Writing it before that A is
overwritten, and after it would contradict the stage (run fx2: Tom Tom set
on SELECT A STAGE, St1-1&2 SWEEPER loaded as Sweepers). To play Tom Tom, pick
a TOMTOM stage. The setting was dropped (review, 2026-10-30).

### D6. Headless check through the overlay
The input script's `key` step learns `up`, `down`, `left`, `right`,
`enter`, `esc` and `space`, the keys the overlay menu reads, so a run with
no window can open the menu (F10), page to Mods, open the mod's page and
press the row. The menu draws only on the presented frame, not in frame
dumps; the evidence is the mod's log line and the game's own debug menu and
stage frames, which are guest-drawn.

## Risks

- A `[0x5EB5F4]` that points at the block in a state the analysis did not
  see would only refuse the open; the mod writes nothing else outside state
  1 and the open.
- The attract demo starts after 600 frames of PRESS START; the request is
  taken within a frame, so the window is wide.
