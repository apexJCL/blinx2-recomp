## Context

BLiNX 2's player update is `ent_player_update` (`sub_00176150`, 0x176150 to 0x18C442). The player record is its first stack argument (in `ebp`; player 0 at `0xCD2440`, stride `0x30C`). The pad record it reads is at `[esp+0x20]` (`+0x14` x, `+0x18` y, floats in -1..1).

## 1. The walk's f(L)

At 0x17C87D (ground states below 0x10, and 0x2A):

- x = `[esp+0x18]`, y = `[esp+0x38]` from the pad (0x17C8A2). Both are zeroed when `[esp+0x44]` or `[esp+0x188]` says the walk ignores the stick (0x17C8B6).
- dz = `[esp+0x28]` = 0.4 (0x3ECCCCCD). While the player's byte `+0x38` is set, dz = 0.6 and y = 0 (0x17C8DB).
- 0x17C8F7 calls the CRT pow (`sub_002D675C`, returning to 0x17C8FC) for the speed's decay this tick.
- 0x17C91F: L = sqrt(x² + y²), then `if L > 1.0 (0x3DECDC) L = 1.0`.
- L > dz: s = (L - dz) / (1 - dz) to `[esp+0x34]` (0x17C96F); else s = 0 (0x17CB49). The heading atan2 goes to `[ebp+0x28]`.
- 0x17D2F5: target = s × `max[row]` (`0x450A84 + 16 × [esp+0x74]`) × the boost factor `[esp+0x18]` (1.0 by default, 0x17CF57) × `[0x3FD334]` (1.0, time scale) × 0.6 when `[ebp+0x2C]`. The speed `+0x154` eases to it by `accel[row]` (`0x450A88`) × dt, skipped while `+0x38`.

The table at 0x450A80 has rows of 16 bytes: row 0 = { 0, 4.5, 0.125, 0.5 }, row 1 = { -2.75, 7.2, 0.1667, 0.5 }.

So **f(L) = max × (min(L, 1) - 0.4) / 0.6** for L > 0.4. Unclamped at a full corner, f(sqrt 2) / f(1) = (1.41421 - 0.4) / 0.6 = **1.690**, exactly BLiNX 1's ratio.

## 2. Users of the clamped length

| Where | What | With the mod |
|---|---|---|
| 0x17CBB0, 0x17CBF0 | s > 0.4: walk or run animation state `+0x8A` | clamped (stock) |
| 0x17CC81 | s > 0.75 (`0x3DEE14`): run state | clamped |
| 0x17CD05 | s threshold: state change via `sub_001759D0` | clamped |
| 0x17CE62 | s × 0.75 when `+0x35` is 2, 5 or 6 | clamped (s × 0.75 times the scaled max feeds the same speed target, so it still runs 1.69× faster there) |
| 0x17CF2E | s to player `+0xAC`, read only as s > 0.4 (0x17A88B, 0x17CC62, 0x17CE70, 0x17F682) | clamped |
| 0x17D2F5 | s × `max[row]`: the target speed | **unclamped** |
| 0x17D3xx | the walk cycle `+0x15C` += rate × max(abs(`+0x154`), 1) | follows the faster speed, as under the game's own boosts: the feet keep in step |
| `+0x154` readers (`hud_draw_status` 0x6DF36, `ent_character_draw` 0x18F78E, `sub_001759D0` 0x175BBE, `sub_0004FD90`, `sub_0015DFD0`, `sub_00193CF0`, `sub_0019DCB0`) | the current speed | see the faster speed, as with a boost |
| 0x17C712 (states 0x31, 0x32, 0x34) | own (L - 0.4) × 5/3 into `+0x2D8`, jumps past 0x17D2F5 | stock (not the walk; the clamp there is its own) |
| 0x17C5D1 (states 0x36, 0x37) | (L - 0.4) × 5/3 × 1.5 within an angle window into `+0x2D8` | stock |
| 0x18C166 | L > 0.4 trigger: adds π to the facing yaw `+0x108` | stock (a threshold) |
| 0x450A8C (turn rate), read at 0x1767E4, 0x178997, 0x17C9E2, 0x17CA9B | not scaled | stock |

Decision (D1): only the target speed sees the unclamped value. Every threshold and the animation-state choice keep the clamped s, so the player animates and changes state exactly as in stock; it just covers more ground on a diagonal, as in BLiNX 1. The Time Sweeper abilities do not read s (they read the buttons and the state byte), and the camera follows the position, not the stick.

## 3. Mechanism

The recompiled walk cannot be hooked mid-function (hook slots are per function), and its 1.0 is the shared constant `0x3DECDC`, which the whole game reads. The table's max, though, is read only at 0x17D301 in the whole XBE and written nowhere.

D2: scale the max for the one walk that is about to read it.

- **Pre hook on `sub_002D675C`** (pow; seven call sites, the D3DX range among them, 0x1B bytes, `st0` slot). It acts only when the return address is 0x17C8FC, the walk's call. At that point x, y and dz are final in the walk's frame (caller esp = `c->esp + 4`; `+0x18`, `+0x38`, `+0x28`), after the stick-ignore zeroing and the 0.6 mode. g = `fdm_factor(x, y, dz)` = (L - dz) / (1 - dz) when L > 1, else 1, with L capped at sqrt(2). When g is not 1 it saves both rows' max and writes max × g.
- **Pre and post hooks on `ent_player_update`** (`no_st0` slot) put the table back, so the scaled max never reaches another player's update.
- `on_enable(off)` puts it back too, at the end of the frame (Risks).
- Live pads only: the pre hook scales only when the walk's pad pointer `[f+0x20]` is one of the four live pads, `[0xADC794]` + slot × 0x1E4 (`fdm_live_pad`, `src/fdm_logic.h`). The walk's other sources keep the stock walk: REC playback (0xDD5B28, stage_play_mode bit 0x4000), the CPU input array `0x5F0760` + i × 0x1E4 (a CPU player, player `+0x07`; 0x176FFA), and `0xCCCE00` + i × 0x1E4, taken while `[0xEC4B6C]` is set (0x176FB0). A recording made without the mod plays back as recorded, and CPU players keep their speed. The status row's factor is stored only for a live pad's walk, so it shows the human's walk. BLiNX 1 has no such split, but its recordings were made with its own walk.
- XBE guard: the first pow call with the mod on compares the call at 0x17C8F7 (`E8 60 9E 15 00`, pow) and the read at 0x17D301 (`D8 8B 84 0A 45 00`, `fmul [ebx+0x450A84]`). On a mismatch (a modded or other XBE) it logs one line and the pre hook does nothing from then on, so the walk stays stock. The check cannot run in `init`: guest memory is not mapped then (`api->mem` is 0, mod.h), and reading it there crashed the first test run.

The pad pointer at `[esp+0x20]` can be replaced after the first pad read (0x1785A5), so reading the stick from the walk's own frame at the pow call is what the clamp sees, not a guess.

Edge cases: the walk ignoring the stick gives x = y = 0, so g = 1. The 0.6 mode forces y = 0, so L ≤ 1 and g = 1. A NaN stick is stock. Two players: each update scales and restores its own.

## 4. Square left stick

A round pad's stick reports about a circle: L ≤ 1, or a little over at some angles on SDL pads, so the mod gives little or no gain without the toolkit's Square left stick (`input.pad_square_left`), which maps the circle onto the square gate. The keyboard's diagonals are full corners (`INPUT_DIAGONAL_FULL`) only with `input.stick_ramp_ms` at 0 (the toolkit's default, or `RECOMP_CONFIG=none`). With a ramp, two perpendicular keys give (-23170, 23170), L = 1 (measured in runs/b2-fdm/spd-on), and `packaging/config.default.toml` ships `stick_ramp_ms = 60`. The user's decision (2026-11-05): with Square left stick on, the toolkit keeps the keyboard's two-key diagonal at full length under the ramp too (a separate toolkit fix). So the texts say pads and the keyboard need Square left stick.

D3: the player-facing text has three places.

- The switch's own `help` is the tooltip card under the Mods list row and under the mod page's Enabled row. The card holds 159 bytes, so the help is one short ASCII line (106 bytes): "Diagonals run up to 1.69x as fast as straight, as in BLiNX 1. Needs Square left stick (pads and keyboard)."
- The integration toolkit before 23fccfda (fix/mod-toggle-help 61c40406) showed no card for a mod's switch. Since 23fccfda, both rows copy the enable setting's help for every mod. This change needs nothing more from the toolkit.
- The mod's summary is the mod page's About text, wrapped to the width, plain and ASCII only (the user, 2026-11-05): "Stock BLiNX 2 caps diagonal speed at straight speed. This mod lifts the cap: diagonals run up to 1.69x as fast, as in BLiNX 1. Pads and the keyboard need Controls > Sticks > Square left stick."
- A live Status row (`mods.fdm.status`, info, not saved, not focusable) reads `xbox_InputPadSetup()`. Its value column shows about 46 characters, so the values are short: "turn the mod on first", "Turn on Square left stick" (the mod on, the square off) and "ready; last walk x1.69" (the last walk's factor).
- `scripts/test_fdm.py` pins both texts, checks they are ASCII and checks both help lengths.
- Screenshots in `runs/b2-fdm/shots/`: the Mods list, the About and Enabled, the hint with the square off, the ready line with it on, and the tooltip on both rows. They show the earlier, longer texts; the layout is the same.

A button that turns the square on from the mod's page would need a toolkit API to set and save another item by key; not in this change (tasks 4.1).

## 5. Stock

Off is the default. The hook functions do not run while the mod is off, and the table is the XBE's. The golden check's `enhance_stock` refuses a run that shows `mods.fdm.enable=on`.

The hooks are not free while the mod is off. With `menu.enabled = true` and `XBOXRECOMP_ENHANCE` live, the mod is registered and its hooks are published while it is dormant, so every pow call (seven call sites, the D3DX range among them) and every `ent_player_update` go through `recomp_hook_run` and the mod's state check before the original runs. Measured cost: §6, Metal flips/s with the mod off.

## Risks

- Switch-off mid-update. `xbox_mod_setting_set` stores off at once on the menu thread; only `on_enable` is deferred, to the next `xbox_mod_frame`. If the mod goes off between the pow pre hook and `ent_player_update`'s post, that post is skipped (hooks of an off mod do not run), and later player updates in the same frame read the scaled max until `on_enable(0)` restores it. The window is at most one frame, and only on the frame of the switch. An `on_frame` restore would run at the same point as `on_enable`, so it would not shorten it.
- Recordings and demos keep the stock walk (live pads only, §3). A recording made with the mod on would play back stock.
- A different XBE: the guard in §3 keeps the walk stock.
- Keyboard with the shipped config. `packaging/config.default.toml` sets `input.stick_ramp_ms = 60`, and with a ramp the toolkit scales a two-key diagonal to the circle (L = 1), so the keyboard gains nothing until the toolkit fix keeps it full with Square left stick on (the user's decision, §4; another agent's change). The texts say pads and the keyboard need Square left stick.

## 6. Measurement

Stage 1-1, player 0's speed `+0x154` (`pad_peek`), past the ease-in of each hold:

| Run | Host | Input | Cardinal | Diagonal | Ratio |
|---|---|---|---|---|---|
| off1 | Mac, Metal | scripted (0, 32767), then (-32767, 32767) | 2.1942 | 2.2037 | 1.004 |
| on1 | Mac, Metal | scripted (0, 32767), then (-32767, 32767) | 2.1942 | 3.7106 | 1.691 |
| kbd-on | Mac, Metal | host keyboard W, then W+A (`RECOMP_KEYBOARD=1`, `RECOMP_CONFIG=none`: no ramp) | 2.1942 | 3.7106 | 1.691 |
| sq-on2 | Deck, Proton D3D11 | vpad round pad (0, 32767), then (-23170, 23170), Square left stick on | 2.1946 | 3.6997 | 1.686 |
| sq-off1 | Deck, Proton D3D11 | the same, Square left stick off | 2.1946 | 2.1820 | 0.994 |

The ground distance per poll agrees: 1.008 off and 1.701 on (Mac). The theory says 1.690. The Deck's diagonal is a little lower because the player was still turning toward the new heading for the first part of the hold. With Square left stick on, the game saw the round pad's diagonal as LS(-32767, 32767) (`[INPUT] host port=0`). With it off, the game saw LS(-23170, 23170): L = 1, so the mod leaves the speed stock, as §4 says. The third hold of each Deck run (a cardinal again) ran into a wall, so it is not in the table.

- Mac runs: `runs/b2-fdm/run.sh` and `ratio.py`.
- Deck runs: `runs/b2-fdm/sq-run.sh`, with vpad held to the run's lock (`--lock-owner`), and `ratio2.py`.

Mod off, the dormant hooks' cost (§5): Metal flips/s, this branch against its base (3a9fe81d, built from the same tree without the two hook slots), the attract and stage1 goldens, in turns:

| Run | attract | stage1 |
|---|---|---|
| base 1 / branch 1 | 44.7 / 42.8 | 33.6 / 34.5 |
| base 2 / branch 2 | 46.2 / 30.0 | 34.5 / 33.6 |
| base 3 / branch 3 | 45.6 / 46.4 | - |

No drop near 25%. Branch 2's attract ran while another job loaded the Mac (max load 28 against 4 to 10 in the others) and is not counted; branch 3 and the goldens on the final build (45.2, 34.4, 54.2) match the base. Stage1 is paced at 30 fps, so it bounds only a large cost. Logs: `runs/b2-fdm/ab-*.log`.

Mod on, the attract (Metal, `RECOMP_FDM=on`, checked with `--allow-enhance`): attract-title and attract-cliff are CLOSE with the same numbers as the stock run, so the demo does not desync (`runs/b2-fdm/attract-fdm-on`).

## 7. Speed readout

D4: a separate debug mod, `speed` ("Speed readout", `mods.speed.enable`, `RECOMP_SPEED_READOUT`), off by default, shows player 0's run speed on the toolkit's status card (mod API v7). It is its own mod because a card goes away with its mod, and the readout is for comparing fdm off and on. It hooks nothing and writes no guest memory: an `on_frame` reads `+0x154` of 0xCD2440 and the stick (`+0x14`, `+0x18`) of the live pad player 0's walk reads: `[0xADC794]` + slot × 0x1E4, the slot being `pad_menu_index[(id / 4) % 4]` (0xAE7A10, the player's signed id byte `+0x00`, a truncating divide and remainder; the walk's `[esp+0x48]`, 0x176421 to 0x17643A). `speed_live_pad` in `src/speed_logic.h` computes it, and `scripts/test_speed.py` checks it.

The card's title is Speed and its line reads `now 1.00  peak 1.00`, the format of the BLiNX 1 readout: the speed over a full straight push's, and the highest of the last second (30 frames).

The straight push's speed cannot be read from the table. The target at 0x17D2F5 is s × max[row] × a boost × the time scale × 0.6 when `+0x2C`, and the boost is a local of the walk (0x17CF57 to 0x17D2ED: 0.8 when `+0x2F` is 2, 1.25 with `[esi+0xFC]`, the upgrade level when `+0x07`, and a slope term). On stage 1-1, row 0 (4.5), time scale 1, `+0x2C` and `+0x2F` clear, a straight push settles at 2.19. The row is a local too (1 when `+0x2F9` is 4 and `+0x0C` is clear, 0x178B82). Max over the table would read 0.49 there.

So the reference is learned: the speed after eight frames in a row that each have the stick at full length on the circle (L from 0.995 to 1.005) and the speed within 0.2% of the frame before (at least 0.5). A frame outside the window starts the count again, so a settled corner speed followed by one straight frame teaches nothing. The window is tight because the walk's speed follows L on both sides of 1: (L - 0.4) / 0.6 below it, the fdm factor above it, so ±0.5% in L is at most ±0.84% in the reference, under the card's 0.01. A corner (L = sqrt 2) then reads 1.00 stock and 1.69 with fdm. Until the first straight push it reads `now --  (push straight once)`. The toolkit draws the card only while the menu layer is on (`menu.enabled`; `RECOMP_MENU=1` in a scripted run). The reference follows the ground whenever the player pushes straight again; a corner on other ground than the last straight push reads that ground's difference too. That is the price of not hooking the walk.

Checked on the Mac (Metal, `RECOMP_MENU=1`, `stick_ramp_ms = 0`, keyboard W for 90 polls then W+A for 180, stage 1-1; `runs/b2-fdm/spd2-off`, `spd2-on`, PNGs in `runs/b2-fdm/shots/speed-*`): the straight push reads `now 1.00  peak 1.00` in both runs, and the corner reads `now 1.00  peak 1.00` with fdm off and `now 1.69  peak 1.69` with it on.

After the delta review (the tight window, the count reset off the circle, the pad by the player's slot), `runs/b2-fdm/spd3-on` (fdm on, same script; this run reached the stage 90 frames sooner) reads `now 1.67  peak 1.70` 66 frames into the corner and `now 0.69  peak 1.68` while slowing after the release: the reference was learned from the player's pad.

`scripts/test_speed.py` checks the logic (`src/speed_logic.h`), pins the texts, and checks that the mod only reads.
