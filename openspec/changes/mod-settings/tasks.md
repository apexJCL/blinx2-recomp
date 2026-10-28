## Context

These are the phases of design.md "Migration Plan".
- **Worktrees.** Each phase gets one worktree set,
  `wt/<phase>/{cat,xboxrecomp}`, and one agent at a time.
  - The toolkit branches off `posix-host/portability`; cat branches off
    `main`.
- **Mac.** Builds use
  `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Runs are
  headless with `SDL_AUDIODRIVER=dummy`, except the window shots, which open
  a window and play no sound.
- **Run data.** Shots and dumps go to `xbox-recomp/runs/mod-settings/`,
  never inside a worktree.
- **Deck.** Proton runs wait for the orchestrator's slot and take the
  Deck's flock (`blinx2 bench` takes it itself).
- **Order.**
  - Phase B's rows can start now; B.8 waits for the tracker item to merge.
  - Phase C waits for phase A.
  - Phase D waits for B (with B.8), C and the tracker item.
  - Each phase rebases on whatever of the tracker item has landed in
    `enhance_menu.c`.

## A. Toolkit: descriptor, settings, config and the dump (D1, D2, D4, D9), 2.5 days

- [x] A.1 `src/enhance/mod.h`: add the following.
  - `struct xbox_mod_desc`, `xbox_mod_setting`, `xbox_mod_control` and
    `xbox_ctl_value` (descriptor version 1, `size`).
  - The `XBOX_SET_*`, `XBOX_CTL_*` and `XBOX_SET_ENABLE` constants.
  - `desc` appended to `struct xbox_mod`, with the comment that this is a
    source contract for statically linked mods, not an ABI (D1).
  - `XBOX_MOD_API_VERSION 3u`, with `setting`, `on_setting`,
    `control_action` and `control_value` appended to `xbox_mod_api`.
    `control_value` reports not connected until phase D.
  - `enhance_menu.h`: `ENHANCE_LIVE_ACTIVATE` ("at next activation");
    `ENHANCE_LIVE_STAGE` keeps its label.
- [x] A.2 `mod.c`: validate each descriptor at registration.
  - Refuse duplicate names and ids, `lo > hi`, an enum with no choices,
    unknown kinds and a second enable setting.
  - A refused descriptor makes the mod `XBOX_MOD_FAILED` with one `[MOD]`
    line.
  - A mod with no descriptor keeps the v2 path, including the prefix
    marking.
- [x] A.3 Reading the settings by D4's precedence table.
  - The rows, highest first: env; then the user file's key, then its
    alias; then the defaults file's key, then its alias; then the
    descriptor default.
  - A setting without `key` is `mods."<id>.<name>"` (flat).
  - Clamp and snap to `step`; an unknown enum falls back to the default.
    Each adjustment logs one `[MOD] <id>.<name>: <value> -> <used>` line.
  - Store each value in an atomic per setting.
  - Mark exactly the declared keys and aliases read, not the prefix (N4).
  - Every user-file alias goes on the pending-rewrite list.
- [x] A.4 The `on_setting` queue. Callbacks are deferred to the next
  `xbox_mod_frame`, beside `on_enable`. A RESTART setting records the value
  and never calls back.
- [x] A.5 The switch and the init rule (D4).
  - `mods."<id>"` (flat bool, default true) keeps its 3D meaning. There is
    no migration.
  - A mod with an `XBOX_SET_ENABLE` setting shows that setting as Enabled.
    `mods."<id>" = false` still keeps it from being inited.
  - The init rule, from the descriptor only:
    - `mods."<id>"` false: not inited;
    - enable on: inited;
    - enable off, menu on, enable class `ENHANCE_LIVE`: inited dormant. No
      `on_enable` after `init` gives one `[MOD]` warning and "applies at
      restart";
    - otherwise: not inited.
  - Print `[ENHANCE] <enable key>=<value>` for every descriptor mod's
    enable setting at start, inited or not.
- [x] A.6 Actions from the descriptor (D3).
  - Register each ACTION control as `<id>.<verb>`, owned by the mod, before
    `init`, with its defaults, aliases and `env` row.
  - Add `control_action(desc, idx)` returning the id.
  - When the mod is off, the action is dormant in `enhance_actions.c`:
    never fired, never consumed, and it does not arm the hook.
  - Its bindings still count in the "one input fires one action"
    resolution and in `enhance_action_owner`. A live switch rebuilds the
    table and re-evaluates the mod's arm key (D3, "the hook while flying").
- [x] A.7 Unknown keys. Undeclared `mods."<id>..."` keys, keys of ids
  not in the build, and undeclared `[input.controls]` keys go to
  `enhance_cfg_report_unused`. Neither Save nor Reset removes them.
  Naming the owner (longest registered id prefix) moved to B.11.
- [x] A.8 `recomp_cfg.c`: add `input.controls.` to `flat_tables[]`.
- [x] A.9 ctests.
  - New `tests/mod_desc`:
    - a valid descriptor;
    - each refusal;
    - a v2 table without a descriptor;
    - a short `size`, which reads only the known fields;
    - clamp, snap and enum fallback, with the exact `[MOD]` lines;
    - one case per precedence row, including a user alias over a
      defaults-file key, and the pending-rewrite list;
    - an env-forced value flagged read-only;
    - `on_setting` deferred to the frame;
    - each init-rule case, including "dormant, live-capable mod is inited
      and stays quiet" and `mods."<id>" = false` over enable on;
    - the `[ENHANCE] camera.free=off` line printed for a mod not inited;
    - `control_action` ids;
    - a typo under an off descriptor mod reported as unused.
  - `tests/input_actions`:
    - dormant actions neither fire nor arm the hook (`hook=off`);
    - a dormant binding keeps its input in the "one input fires one
      action" resolution, and `enhance_action_owner` reports it;
    - a live enable rebuilds the table with no binding moved;
    - an ACTION's env row replaces its bindings.
  - `tests/recomp_cfg_patch`: `[input.controls]` round trip; `[mods]`
    `"x"` and `"x.speed"` side by side; unknown `mods."y..."` keys
    survive a patch.
  - `tests/enhance_mod` and `tests/enhance_cfg` keep their current counts,
    plus the new cases.
- [x] A.10 Docs. In `docs/runtime/config.md`:
  - the "Mods" section: the descriptor, the flat keys, precedence, pending
    rewrites and unknown keys;
  - the `[MOD]` log lines and the toolkit's enable line.
- [x] A.11 Gates.
  - Mac build and `tests/posix_ctest.sh` (0 FAIL).
  - The cat build still uses the v2 table: stock Metal goldens unchanged,
    `[ENHANCE] actions hook=off`.
  - A.12's ctests run in the same pass.
- [x] A.12 The descriptor dump (D9), in its own file `src/enhance/mod_describe.c`.
  - `RECOMP_MODS_DESCRIBE` and `RECOMP_MODS_DESCRIBE_OUT` rows in
    `recomp_env.h` (config tier), and in cat `docs/env.md` and toolkit
    `docs/runtime/config.md`.
  - In `xbox_enhance_init`: with `=json`, skip every mod `init` and the
    hook, resolve settings and bindings as usual, write the schema-1
    JSON to the file or stdout, then `exit(0)`; exit 1 with one `[MOD]`
    line if the file can't be written. Any other value: one `[MOD]` line,
    ignored.
  - A small stdlib JSON writer with string escaping; no new dependency.
  - ctest `tests/mod_desc`:
    - the dump of a test table matches an expected file byte for byte;
    - no mod `init` and no frame hook ran;
    - `source` for each precedence row, an env-forced value as `env`;
    - `init` as `yes`, `dormant`, `no` and `failed` with a reason;
    - a descriptor-less mod as `"descriptor": false`;
    - an unwritable path exits 1;
    - an unknown value is ignored with its line.
- [x] A.13 Review fixes (2026-10-27, F1 to F8): the Mods page toggle saves
  the enable setting; the arm-key lock; the 64-byte key limit and the
  unbound env row line; the effective enable line; a patch skips only a
  refused key; `refused` in the dump; a refused descriptor's keys marked
  read; the notes in "Phase A as built" (design.md).

## B. Toolkit: Mods page detail view (D5), 1.5 days; B.8 after the tracker item

- [x] B.1 `enhance_menu.c`: every mod row opens its detail page.
  - Rows: header (title and version), Author, About, State, Enabled.
  - Then Controls, Settings and "Reset this mod".
  - A mod without a descriptor keeps the 3D rows.
  - A failed mod lists its controls and settings marked "unavailable".
  - State shows "Off (`mods."<id>"` = false)" when that key holds it off.
- [x] B.2 The R_TEXT row: word-wrapped to the panel width with the atlas's
  glyph widths, not selectable, and no line cap.
- [x] B.3 Settings rows from the descriptor.
  - TOGGLE, CHOICE and RANGE rows; RANGE uses `step` and `unit`.
  - Live rows get the live dot. `ENHANCE_LIVE_ACTIVATE` rows read "next
    activation" and RESTART rows read "applies at restart". STAGE rows of
    game items keep their label.
  - An env-forced row is greyed with "set by `RECOMP_...`" and skipped by
    `collect()`.
- [x] B.4 Controls rows.
  - ACTION controls reuse R_BIND. A dormant action is marked "(mod off)".
  - BUTTON, STICK and INFO controls show their bindings, plus the
    `[input.bindings]` keys in parentheses and the `when` note.
  - Captured rows are read-only until phase D.
- [x] B.5 The footer shows the selected row's `help` whenever no status
  message is showing.
- [x] B.6 Save and reset.
  - "Reset this mod" stages the mod's settings and bindings back to the
    stock: the defaults file's value, else the descriptor's default.
    Enabled is not reset, and unknown keys are untouched.
  - `collect()` always adds the pending-rewrite list (D4).
  - Turning Enabled on stages removing a `mods."<id>" = false`.
- [x] B.7 The Controls page groups actions by owner under the owner's title.
  The toolkit's group comes first, then the game's, then the mods'. A
  dormant mod's group says so.
- [x] B.8 After the tracker item merges: capture conflicts extend its check.
  - Binding a key that a dormant action owns is refused, and the footer
    names the owner and the label.
  - Binding an action to a key a captured control names directly is
    refused (D3 conflict rule 2, the action-side direction).
  - The dormant-default collision line (D3) when two defaults name one
    input and either action is dormant, with a ctest.
  - Add the tracker item's final rule numbers once, next to the rules D3 names by
    content (its tie rule, longest match, quiet capture), so reviewers can
    map them. Until it merges, D3 cites them by content only.
- [x] B.9 ctests in `tests/enhance_menu`:
  - the detail rows of a test descriptor, and a failed mod's rows;
  - the wrap at three panel widths;
  - live, activate, restart and forced rows, and an unchanged STAGE row;
  - Reset this mod against a hand-written expected patch;
  - a Save with no edits that carries a pending alias rewrite;
  - Enabled on removing `mods."<id>" = false`;
  - the dormant-action conflict, and the action-onto-captured-key
    conflict;
  - the Controls page grouping.
- [x] B.10 Docs. In `docs/runtime/config.md` "In-game menu": the detail
  view and the grouping. Then the gates of A.11. This phase skips goldens
  (menu only), but the Mac menu shots (`runs/mod-settings/b-*`) show a test
  mod's page.
  - Done 2026-10-27: the Metal shots of the running build are in
    `runs/ITEM/` (`mods-list`, `lod-detail`, `lod-detail-reset`,
    `freecam-detail-v2`, `controls-grouped`). The Mods list rows show the
    descriptor title (`lod` reads "Character detail"), and a forced Enabled
    switch names its variable ("set by `RECOMP_LOD`"). No cat mod registers
    host actions yet (the v2 free camera reads its own keys until C), so the
    running build's Controls page shows only the Toolkit group; the mod
    groups and "(mod off)" are covered by the ctest.
  - Review fixes (review): one separator per key in a
    captured control's key list (`rt, x, R (keys 3, C)`, full-string
    test); the draw takes `geom_of`; a float with no step shows and saves
    the decimals its computed step needs; a failed mod's INFO rows read
    "unavailable"; an alias rewrite whose value is the stock drops the key,
    and the Save status counts the player's changes apart from renamed
    keys; tests for the Game group and for an edit that wins over a
    pending rewrite. `tests/posix_ctest.sh` now unsets every `RECOMP_*`
    first: a `RECOMP_MENU=0` left in the shell by a golden run failed
    `enhance_cfg`, `input_actions(_tsan)` and `mod_desc`.
- [x] B.11 The unknown-key report names the owner: the longest registered
  id that prefixes the key (moved from A.7, D4). The detail view lists
  a mod's unknown keys.

## C. cat: the free camera's descriptor (D6, D10, 5B), 1.5 days, after A

End and Home are confirmed as the freeze and reset defaults (the user,
2026-10-27), so C can start once A lands.

- [ ] C.1 `src/free_camera.c`: add a static descriptor with the D6 tables.
  - Delete the hand-written range checks, the key polling and the
    `[ENHANCE] camera.free=` printf (the toolkit prints it now).
  - `on_frame` polls `action_pressed` on the ids from `control_action`.
  - `fc_params` reads `api->setting`.
  - This takes over enhance-menu-preview 5B.1. Mark 5B "moved to
    mod-settings C" there.
- [ ] C.2 5B.2 as written there.
  - `on_frame` and `batch_filter` are registered only when the mod is
    inited (D4's init rule), and gated on an atomic.
  - `init` calls `actions_arm("camera.free")`. The toolkit re-evaluates
    that key on a live switch (A.6).
  - `on_enable` runs the toggle-off path: camera restored, freeze dropped,
    HUD shown.
- [ ] C.3 The new settings (D6, D10): `mouse_sens`, `invert_x`,
  `invert_y`, `fast` and `slow`.
  - `fc_params` gains them. `fc_fly_step` flips the yaw sign for
    `invert_x` and the pitch sign for `invert_y` (stick and mouse),
    multiplies `FC_MOUSE_RATE` by `mouse_sens` on top of `look_sens`, and
    uses `fast` and `slow` in place of `FC_FAST` and `FC_SLOW`.
  - With every default, `fc_fly_step` gives today's result: a
    `free_cam_fly.h` harness case in `scripts/` checks it.
  - `RECOMP_CAMERA_FREE_MOUSE_SENS`, `_INVERT_X`, `_INVERT_Y`, `_FAST` and
    `_SLOW` rows in `src/env/recomp_env_game.h` and `docs/env.md`.
  - The D6 audit table goes in a comment above the descriptor's settings
    table, so the next change to the mod sees what was left out and why.
  - The four key env rows stay, bound to the actions; `docs/env.md` says
    so and gives the new defaults.
- [ ] C.4 `packaging/config.default.toml`:
  - `[input.actions]` rows for `camera.free.toggle`, `.hud`, `.freeze` and
    `.reset`;
  - `camera.free_mouse_sens = 1.0`, `camera.free_invert_x = false`,
    `camera.free_invert_y = false`, `camera.free_fast = 4.0` and
    `camera.free_slow = 0.25` under `[camera]`;
  - the alias keys removed, with a comment that they are still read.
  The README's free-camera paragraph lists the controls.
- [ ] C.5 `scripts/test_free_camera.py`:
  - `KEYS` keeps all eight env rows with the new defaults (End, Home) and
    adds the five new settings;
  - `test_config_default_is_stock` follows the new `[camera]` and
    `[input.actions]` layout;
  - `test_golden_knows_the_stock_value` checks the descriptor marks
    `camera.free` as the enable, in place of the printf string (the line
    itself is checked by `tests/mod_desc`);
  - an alias still read;
  - the clamp lines in place of the old messages.
  The `key` script step still reaches the actions (5B.3): confirm it, or
  route the step through the action.
- [ ] C.6 Gates.
  - `uv run pytest scripts`, ruff, and the Mac build.
  - Stock Metal goldens unchanged: `[ENHANCE] camera.free=off` still in the
    log, `hook=off`.
  - The free-camera golden scenario, if one exists, otherwise `@stage1`:
    - toggle from F6 and from Guide+Y;
    - enable from the Mods page with the menu on (dormant init), then fly;
    - off from the Mods page mid-flight;
    - rebind toggle from the detail view;
    - change speed, mouse sensitivity, fast and slow live;
    - invert X and invert Y on.

## D. Captured controls and fly rebinding (D3), 2.5 days, after B, C and the tracker item

- [ ] D.1 The recorded state, on its own.
  - `xbox_enhance_pad_seen(port, &gamepad, connected)` in the toolkit,
    behind a seqlock, recording only while a mod holds `input_capture`.
  - Called by `input_core.c` `xbox_InputGetState` directly, after `FILTER`
    and at `KEEP`, whether or not `g_filter` is set, and by cat's
    `pad_input.c` in place of `g_port0_seen` (after
    `xbox_enhance_pad_filter`, before the neutral pad).
  - `xbox_InputGetState` applies the neutral pad while a mod holds
    capture: `Gamepad` zeroed, `dwPacketNumber` bumped when it starts and
    ends; a failed poll untouched. cat's `free_cam_pad_neutral` asks the
    toolkit's capture state.
  - ctest `tests/input_actions`:
    - input_core: a mod holds capture with the hook disarmed (`g_filter`
      NULL); the poll records and the guest reads neutral, connected,
      with a new packet number; releasing capture restores the pad with
      another new number;
    - no record without capture;
    - the consumed-chord mask is applied before the record (Guide+Y
      leaves no Y);
    - a pulled pad reads not connected;
    - a reader concurrent with a writer never sees a torn state.
- [ ] D.2 `control_value(desc, idx, out)`.
  - STICK: the raw axes and `src`.
  - BUTTON: the largest analog value over its bindings; a host key reads
    255.
  - Bindings from `[input.controls]` `<id>.<control>`, defaults from the
    descriptor, env row if set.
- [ ] D.3 The menu's R_CTL capture.
  - It runs through the tracker item's capture phases and quiet mode.
  - 400 ms hold for chords.
  - A host pad source is mapped through the active pad setup to its guest
    button. A source with no guest slot (paddles, Guide) is refused with
    "fly controls take buttons the game sees".
  - Any direction of a stick past 0.6 is stored as the whole stick, and
    STICK rows take only sticks.
  - Keys are stored as keys.
  - D3's conflict rules 1 to 5 live in `enhance_actions.c` beside the tracker item's
    check.
  - X clears, but a control must keep one binding.
- [ ] D.4 cat: `fly()` takes `control_value` in place of
  `cat_pad_port0_last`.
  - It keeps `fc_axis` with each source stick's dead zone (7849 left, 8689
    right), `analog()` and the White and Black threshold.
  - A cat test (a `free_cam_fly.h` harness under `scripts/`, or a ctest)
    proves the same `fc_input` as today with the default bindings, and
    the right dead zones with the sticks swapped.
- [ ] D.5 ctests in `tests/input_actions` and `tests/enhance_menu`:
  - each conflict rule, both directions of rule 2;
  - a captured key that `report_unknown`, `classify` and `build` never see
    (no "no action named" warning, no refusal of `rt`);
  - a host key bound to `rise`;
  - a host button mapped through a remapped pad setup;
  - a paddle refused;
  - stick swap;
  - Y alone sinks while Guide+Y toggles, through the consumed-chord mask.
- [ ] D.6 Docs. In `docs/runtime/config.md` "Host actions": the
  `[input.controls]` table, the guest source names and the capture rules.
- [ ] D.7 Gates: as C.6, plus the Mac `@stage1` run:
  - rebind rise to Space;
  - swap the sticks;
  - check that the game never sees the fly input (the trace shows the
    neutral pad).

## E. Hosts, parity and docs, 1 day, on the orchestrator's slots

- [ ] E.1 Build on the Mac and install on the Deck. Run `tests/mod_desc`,
  `enhance_menu` and `input_actions` under `tests/proton_run.sh`, and add
  `mod_desc` to `bench/host/tests.sh`.
- [ ] E.2 `blinx2 bench golden` on D3D11: unchanged, with `camera.free=off`
  and `hook=off`.
- [ ] E.3 Deck hands-on on D3D11 (on "go"):
  - the detail page against the Mac shots (wrap, greyed rows, footer help);
  - the controls listed;
  - rebind toggle to a back grip's key;
  - rebind rise;
  - speed, both sensitivities, fast, slow and both inverts live;
  - Save and restart keep them.
  Shots go in `runs/mod-settings/d3d11-*`. Flips/s with the menu open must
  stay within 25% of the same run with the menu closed.
- [ ] E.4 Native Windows, when the PC is up on Windows (never switch the
  boot for it): the E.2 golden and the E.3 list.
- [ ] E.5 After any large merge, a Mac CPU-backend build check. A gap goes
  in TASKS.md.
- [ ] E.6 TASKS.md entry, with the follow-ups:
  - a launcher (or the CLI or wizard) that reads the D9 dump and edits mod
    settings before the game starts (the user, 2026-10-27);
  - a free-camera FOV setting, which needs a game field the mod doesn't
    write today (D6 audit);
  - About text that wraps past the panel's visible rows cannot be scrolled
    to (text rows are not selectable): scroll the page at the first or last
    stop, or cap About with an ellipsis (review L4);
  - a mixed-case pad chord reads "bound already" in the menu while the
    table parser refuses it: make pad-name parsing case-insensitive
    (review L8, older than phase B).
- [ ] E.7 The dump on real builds: `RECOMP_MODS_DESCRIBE=json` on the Mac
  exe prints `camera.free` with 9 settings and 11 controls and exits 0
  with no window; on the Deck under Proton, `RECOMP_MODS_DESCRIBE_OUT`
  writes the same JSON to a file.
