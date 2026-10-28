## Context

**What exists today** (toolkit `posix-host/portability` 794d6b56, cat `main` 6d98517):
- **Mod API v2** (`src/enhance/mod.h`, `XBOX_MOD_API_VERSION 2u`). A mod is
  `struct xbox_mod {name, init, shutdown}`. `init` gets `xbox_mod_api`:
  - config getters and `cfg_bind_env`;
  - `on_frame`, `input_state`, `input_capture` and `batch_filter`;
  - from v2, `action_register`, `action_pressed`, `action_down`,
    `menu_add`, `on_enable`, `toast` and `actions_arm`.
- **Mods page** (enhance-menu-preview 3D):
  - one row per mod, switched by `mods."<name>"` (bool, default true);
  - a mod switched off by that key is never inited, and its prefix is
    marked read (`enhance_cfg_mark_read_prefix`);
  - `on_enable` and `actions_arm` can be called only from `init`;
  - `recomp_cfg.c` keeps `mods.` a flat table (`flat_tables[]`): every
    `mods.X...` key is one quoted name under `[mods]`;
  - a mod's sub-page opens only when it has `menu_add` items.
- **Controls page.** Every host action is an R_BIND row:
  - capture on OK, X clears;
  - pad chords need a 400 ms hold;
  - `capture_finish` refuses a duplicate binding inside the same action;
  - The tracker item (`fix/chord-conflict`, merged) adds three rules, numbered in
    `docs/runtime/config.md` "Host actions": rule 8, one input fires one
    action (the tie rule: a written binding beats a default, else the
    first registered keeps it); rule 9, the longest chord match wins; and
    rule 10, actions stay quiet while the menu captures. The rest of this
    design names them by what they say.
- **Free camera** (`src/free_camera.c`, mod `camera.free`):
  - It registers no actions and no items. It polls F6, F7, F8 and F5 with
    `xbox_FramebufferKeyDown`.
  - It always runs `init`, which prints `[ENHANCE] camera.free=on|off`;
    `game.toml`'s `enhance_stock` and `test_free_camera.py` read that line.
  - It reads its fly controls from `cat_pad_port0_last`. cat's
    `pad_input.c` records it, under its pad lock, after
    `xbox_enhance_pad_filter` (which removes consumed chord buttons) and
    before the neutral pad:
    - left stick moves, right stick looks;
    - RT or X rises, LT or Y sinks;
    - White is fast (x4), Black is slow (x0.25);
    - raw mouse motion looks.
  - `fly()` applies per-stick dead zones (7849 left, 8689 right) through
    `fc_axis`.
  - Its eight `camera.*` keys, each with a `RECOMP_CAMERA_FREE_*` env row,
    are clamped by hand. It has no invert.
  - Phase 5B of enhance-menu-preview (actions, live on and off, atomics)
    is specced but not built.

**The problem.** Everything the menu could show about a mod lives inside
`init`. A mod that is off has run no `init`, so it has nothing to show. The
fly controls are not actions: an action is a host hotkey that fires once,
while flying needs held buttons and sticks read every frame. So they can't
be rebound today.

## Goals / Non-Goals

**Goals:**
- A mod declares its info, settings and controls once, statically.
- The toolkit validates the settings, owns their config keys and builds
  their menu rows.
- Every mod gets a detail view, whether it is on, off or failed.
- The free camera's hotkeys and fly controls are shown and can be rebound.
- Every setting a player would sensibly want is exposed, each marked live
  or not (D10). For the free camera: speed, stick and mouse sensitivity,
  invert X and Y, the fast and slow multipliers and the HUD.
- A descriptor dump (`RECOMP_MODS_DESCRIBE=json`) lists every mod, setting
  and control without starting the game (D9).
- Stock stays stock.
- Mod tables without a descriptor keep working.

**Non-Goals:**
- A launcher, or the CLI or the wizard, editing mod settings before the
  game starts. The dump (D9) is what such a tool reads; the launcher is a
  follow-up (the user, 2026-10-27).
- Script or Lua mods, and per-mod themes.
- Rebinding the game's own buttons. That is `[input.bindings]`, which the
  Controls page already covers.

## Decisions

### D1. A static, versioned descriptor

```c
struct xbox_mod_desc {
    uint32_t version;              /* XBOX_MOD_DESC_VERSION, 1 */
    uint32_t size;                 /* sizeof, for appended fields */
    const char *title, *summary, *author, *version_text;
    const struct xbox_mod_setting *settings; uint32_t n_settings;
    const struct xbox_mod_control *controls; uint32_t n_controls;
};
struct xbox_mod { const char *name; init; shutdown;
                  const struct xbox_mod_desc *desc; };   /* v3: appended */
```

- **The descriptor is `const` data, read before any `init`.** Why: the page
  must describe a mod that is off, failed or never inited. A runtime
  `describe()` callback would have to run mod code for an off mod, and
  3D's rule is that an off mod runs nothing.
- **`version` and `size` in the descriptor.** The toolkit reads only the
  fields inside `size`, the same way it already handles `xbox_mod_api`.
  Why: a game built against an older toolkit header keeps working when
  fields are appended.
- **`XBOX_MOD_API_VERSION` goes to 3.** The new `desc` field is appended
  to `struct xbox_mod`, and a mod table without it (`desc` NULL) gets
  today's page. Why: mods built against v2 run unchanged, and cat is the
  only table today.
- **Source compatibility only.** `struct xbox_mod` itself has no version
  or size field, so appending `desc` is a source contract, not a binary
  one. That holds because mods are linked statically into the game; nobody
  should read it as a plugin ABI.
- **The id stays `xbox_mod.name`** (`camera.free`). `title` is the display
  name ("Free camera"). Why: config keys, action owners and logs already use
  the name.
- **Text is UTF-8 and has no length cap,** because the overlay wraps it
  (D5). The summary is shown whole. Glyphs outside the 3E range render as
  the `.notdef` box.
- **Validation is done once, at registration.** A bad descriptor fails
  that mod, not the run:
  - duplicate setting names or control ids;
  - `lo > hi`;
  - an enum without choices;
  - an unknown kind;
  - more than one `XBOX_SET_ENABLE` setting.
  The mod's state becomes `XBOX_MOD_FAILED` with one `[MOD]` line (the tag
  `mod.c` already uses), and its info still shows. Why: a broken
  third-party mod must not take the game down.

### D2. Typed settings

```c
struct xbox_mod_setting {
    const char *name;     /* "speed": key mods."<id>.speed" */
    const char *key;      /* NULL, or a full legacy key ("camera.free_speed") */
    const char *env;      /* NULL, or a recomp_env row name */
    const char *const *aliases;   /* retired keys, NULL-terminated */
    const char *label, *help, *unit;
    uint8_t kind;         /* XBOX_SET_BOOL, _INT, _FLOAT, _ENUM */
    uint8_t live;         /* ENHANCE_LIVE, _LIVE_ACTIVATE, _LIVE_RESTART */
    uint8_t flags;        /* XBOX_SET_ENABLE: this is the mod's switch */
    double def, lo, hi, step;
    const char *const *choices;   /* enum: NULL-terminated; def is an index */
};
```

- **Four kinds.**
  - Bool, int, float and enum cover every mod setting that exists: the
    free camera, and the widescreen and frame-rate keys planned in
    mod-connectivity.
  - Strings and colours are left out until a mod needs them.
- **Reuses `enhance_item_live`, without FLUSH.** A mod setting never goes
  through `nv2a_host_opts`. Why:
  - mod state lives in the mod;
  - The tracker item's render-scale crash is in the FLUSH path, so mod rows stay
    out of it.
- **A new class, `ENHANCE_LIVE_ACTIVATE`: "at next activation".** The
  camera reads its HUD choice when flight starts. Why a new class:
  `ENHANCE_LIVE_STAGE` already means "at a later game point" (the next
  stage) for game items, and relabelling it would change those rows.
  `ENHANCE_LIVE_RESTART` keeps its meaning.
- **The toolkit owns the value.**
  - It resolves the value by D4's precedence table (env, then the user
    file, then the defaults file, each layer's key before its aliases,
    then the descriptor default).
  - It clamps a range value and snaps it to `step`; an unknown enum string
    falls back to the default. Either way it logs one
    `[MOD] <id>.<name>: <value> -> <used>` line.
  - It stores the result in an atomic.
  - The mod reads it with `api->setting(desc, idx)`, a relaxed atomic
    load: no string lookup and no lock. `idx` is the array index, so a mod
    keeps an enum beside its table.
  - Why: today every mod hand-writes the same clamp and the same log line.
    The free camera has four of them.
- **Changes from the menu.**
  - `api->on_setting(desc, fn(idx, value, user), user)` is deferred to the
    guest thread at the next `xbox_mod_frame`, the same queue as
    `on_enable`. Why: the mod's state is guest-thread state.
  - A mod without a callback just reads the atomic.
  - A `RESTART` setting only records the value; the row reads "applies at
    restart".
- **Env-forced values are read-only.** A setting whose `env` row is set
  shows its value with "set by `RECOMP_...`", and Save skips it. Why: the
  same rule other forced rows follow. Writing it would be silently
  overridden at the next start.
- **Env rows.** `env` names a `recomp_env` row, resolved through the same
  table `cfg_bind_env` uses. The game declares the row, as today, so fork
  code still has no raw `getenv`.
- **The enable setting's log line.** At start the toolkit prints
  `[ENHANCE] <key>=<value>` for every descriptor mod's `XBOX_SET_ENABLE`
  setting, whether or not the mod is inited (`[ENHANCE] camera.free=off`
  on a stock run). The value is the enum's choice text or `on`/`off` for a
  bool. Why: the golden's `enhance_stock` check reads that line. Under the
  init rule (D4) an off mod may not run `init`, so the line can't stay in
  the mod.

### D3. Controls: actions and captured controls

```c
struct xbox_mod_control {
    const char *id;       /* "toggle": action "<mod>.toggle"; "rise" */
    const char *label, *help, *when;    /* when: "while flying" */
    uint8_t kind;         /* XBOX_CTL_ACTION, _BUTTON, _STICK, _INFO */
    const char *const *defaults;        /* binding strings, NULL-terminated */
    const char *const *aliases;         /* legacy keys, NULL-terminated */
    const char *env;      /* NULL, or a recomp_env row name */
};
struct xbox_ctl_value {   /* control_value's answer */
    int16_t raw[2];       /* STICK: the axes as the pad reports them;
                             BUTTON: raw[0] 0..255, the largest binding */
    uint8_t src;          /* STICK: XBOX_CTL_SRC_LEFT or _RIGHT */
    uint8_t connected;    /* 0: port 0 has no pad and no keyboard source */
};
```

- **ACTION** is a host hotkey that fires once.
  - The toolkit registers it as `<mod>.<id>`, owned by the mod, from the
    descriptor, before `init`.
  - The mod gets the ids from `api->control_action(desc, idx)`, which
    returns the action id for control `idx` (-1 for a captured or info
    control). It then polls `action_pressed` and `action_down` as v2 does.
    Why: v2's `action_register` refuses a duplicate name, and `mod.h` has
    no lookup by name, so without this the mod could not reach its own
    actions.
  - If the mod is off, the action is **dormant**:
    - it shows on the Controls page, can be rebound and is checked for
      conflicts;
    - it never fires and never consumes input;
    - its bindings still take part in the "one input fires one action"
      resolution and in `enhance_action_owner`, so enabling the mod live
      moves no binding between actions;
    - turning the mod on or off rebuilds the binding table, as an edit
      does today.
  - Registering an action does not arm the hook (R3: only feature keys
    arm it), so a stock run still logs `[ENHANCE] actions hook=off`.
  - Why register an off mod's actions: a player who turns the camera on
    must not find F6 already taken by a binding made while it was off.
  - An ACTION's `env` row replaces its bindings when set (env beats file,
    as for settings), with one `[MOD]` line. That keeps the camera's four
    key rows (D6).
- **BUTTON and STICK** are captured controls, read every frame while the
  mod holds `input_capture`.
  - **Namespace: guest sources.** A binding names a Duke button or trigger
    (`rt`, `x`, `white`, ...) or a stick (`left_stick`, `right_stick`) as
    the game sees it, after `[input.pad]` and `[input.bindings]`. It can
    also name a host key, read straight from the framebuffer key state.
    Why guest sources:
    - it is what the camera reads today, so the default bindings give the
      same output;
    - keys reach the camera through `[input.bindings]` as today (E is X,
      so E rises) with no second keyboard table.
    The cost: host-only buttons (paddles, Guide) can't drive a fly
    control, because they have no slot in the guest pad. They stay for
    actions, or can be mapped to a guest button in `[input.pad]`.
  - **Capture translates host to guest.** The menu's capture sees host
    sources. R_CTL maps the pressed host source through the active pad
    setup (the same `xbox_pad_setup` that `classify()` uses) to the guest
    button it feeds, and stores that name. A source that feeds no guest
    button is refused: "fly controls take buttons the game sees". A key is
    stored as the key.
  - **A stick is captured whole.** `capture_step` turns a stick past 0.6
    into a direction source (`left_stick_up`). For a STICK row, any
    direction of a stick is stored as that stick (`left_stick`). A STICK
    row takes only sticks, so a STICK binding can only swap with the other
    stick.
  - **Values keep today's shape.** `api->control_value(desc, idx, out)`
    fills a `struct xbox_ctl_value`. A STICK gives the raw axes and which
    stick they came from. A BUTTON gives the largest analog value of its
    bindings (keys read 255), the same "rt > x ? rt : x" the camera
    computes now. The dead zone and the response curve stay in the mod.
    Why: `fly()` uses per-stick dead zones and `fc_axis`'s shape. With
    `src` the mod applies the physical stick's own dead zone (7849 left,
    8689 right), so swapped sticks keep theirs.
- **INFO** is a row with no binding, such as "Mouse: look". It is shown and
  never rebound. Why: raw mouse motion is not a source a binding can name.
  Its sensitivity is a setting.
- **The recorded state.** A new call, `xbox_enhance_pad_seen(port, &gamepad,
  connected)`, records port 0's guest state.
  - **Where.** Two callers, each after the consumed-chord mask, so a
    matched chord's buttons are gone before the record. That is why Y
    sinks but Guide+Y toggles without sinking.
    - The title's pad glue calls it after `xbox_enhance_pad_filter` and
      before the neutral pad, exactly where cat now sets `g_port0_seen`
      (`pad_input.c`, after the `CAT_HAVE_PAD_FILTER` block).
    - `input_core.c` `xbox_InputGetState` calls it itself, under
      `XBOXRECOMP_ENHANCE`, after the `FILTER` step and at the `KEEP` step
      (where `keep_last` already copies port 0 for `xbox_InputLastState`),
      **whether or not `g_filter` is set**. Why: input_core reaches the
      filter only through `g_filter`, which `install()` sets only when the
      hook is armed, so a call inside the filter would record nothing for
      a mod that holds capture without arming the hook.
    - A title uses one path or the other. cat's glue does not call
      `xbox_InputGetState`, so nothing is recorded twice.
  - **When.** It records only while some mod holds `input_capture` (one
    atomic load otherwise). Why: the filter itself returns at once while
    the hook is disarmed, which is the stock state, so recording can't
    depend on the hook. A stock run pays one load per poll and records
    nothing.
  - **Threading.** The poll thread writes and the guest thread reads
    through `control_value`. The copy sits behind a seqlock: the writer
    bumps the sequence around the copy, and the reader retries on a change.
    Why: the poll must never wait on the guest, and the struct is too big
    for one atomic. `connected` is recorded too, so a pulled pad reads as
    neutral, not as its last state.
  - This replaces `cat_pad_port0_last` and `g_port0_seen`: the toolkit
    owns the state, so it stays game-agnostic and b3 gets it through
    `xbox_InputGetState`.
  - **The neutral pad.** While a mod holds `input_capture`, the guest reads
    port 0 connected and released, so nothing the player does to fly also
    moves the character.
    - In cat's glue this stays as it is (`free_cam_pad_neutral`, now asking
      the toolkit's capture state).
    - **input_core applies it too**, right after the record: with a mod
      holding capture and the poll successful, it zeroes `Gamepad` and
      bumps `dwPacketNumber` when the neutral pad starts and when it ends.
      Why apply it there, not leave it to each title's glue: an
      input_core title such as b3 has no pad glue, so the guest would read
      the fly input. The toolkit already knows the capture state
      (`xbox_mod_input_captured`), and keeping the neutral pad beside the
      record means they can't drift apart. The packet bump is needed
      because the title reads edges by packet number (the comment in
      `xbox_InputMergeKbm`), so a state that turns to zero under the same
      number would read as still held.
    - A failed poll is left as it is: no pad, nothing to neutralise.
- **The hook while flying.** A mod that reads captured controls arms the
  hook only for its own needs. `actions_arm` stays init-only. A mod with
  live enable (D4) calls it in `init` with its enable key, and the toolkit
  re-evaluates armed keys on every live switch of that key. Why: today a
  key arms the hook only if it was true at init, so a camera enabled live
  from the menu would have dead actions. With the menu on, the hook is
  already armed by `menu.enabled`.
- **Bindings live in their own table, `[input.controls]`**, for example
  `"camera.free.rise" = ["rt", "x"]`. It is flat like `[input.actions]`, so
  `recomp_cfg.c` adds `input.controls.` to `flat_tables[]`. Action bindings
  stay in `[input.actions]`. Why a separate table: everything in
  `enhance_actions.c` treats an `input.actions.*` key as an action.
  - `report_unknown()` would warn "no action named" for each control.
  - `classify()` would mark single game buttons (`rt`, `x`) inactive and
    refuse them, under the rule that a single guest source can't be an
    action.
  - `build()` would add them to the action table.
  Keeping them apart leaves those paths untouched. The unknown-key check
  for `[input.controls]` is the descriptor's (D4).
- **Conflict rules.** These are checked in `enhance_actions.c`, beside
  the tracker item's check. The refusal names the owner and the label in the
  footer: "F6 is Free camera: Toggle flight".
  1. Inside one mod, a captured binding can't repeat one of its other
     captured controls. Why: two fly controls on one button cannot both
     work.
  2. A captured key can't equal an action's single key, and an action
     can't be bound to a key a captured control names directly (both
     directions). Why: actions are consumed first, so the control would
     never see it, and the reverse capture must not create the same clash.
     Guest buttons need no such check: an action can't be a single game
     button (R3), so no action single owns `x`.
  3. A captured single button can coexist with an action chord that
     contains it (Y sinks, Guide+Y toggles). Why: the consumed-chord mask
     removes the chord's buttons before the state is recorded. The tracker item's
     longest match (rule 9) only orders action against action.
  4. Captured controls of different mods may share a source, because only
     one mod holds capture at a time.
  5. Dormant actions count in every check.
- **A dormant default on a live default.** The tracker item's tie rule (rule 8; a written
  binding beats a default, else the first registered keeps it) stays as
  it is. When two defaults name the same input and either action is
  dormant, the build logs one line:
  `[MOD] <input>: <kept action> keeps it over <other action> (dormant)`.
  Why log rather than give the live action the tie: the winner would then
  change whenever a mod is switched live, which is exactly what counting
  dormant bindings prevents (enabling a mod moves no binding). No default
  collides today (camera: F6, guide+y, F7, End, Home; toolkit and cat:
  F10, guide+a, paddle1, back+left_thumb), so the line is a guard for
  later mods. A ctest in `tests/input_actions` checks it.
- **R_CTL capture runs through the same capture phases** as R_BIND
  (the tracker item's `cap_phase` and `enhance_actions_quiet`, rule 10). So no action fires
  while the player presses a source to bind.

### D4. Config keys and precedence

- **The layout stays flat.** `recomp_cfg.c` keeps `mods.` a flat table: a
  key `mods.X...` is one quoted name under `[mods]`.
  - The switch stays `mods."<id>"` (bool, default true), as 3D ships it.
  - A setting without `key` is `mods."<id>.<name>"`:

    ```toml
    [mods]
    "camera.free" = true
    "some.mod.speed" = 2.0
    ```

  - The toolkit builds each full key from the id and the name, so it never
    has to split a key. An undeclared key goes to the generic unused-key
    report. Naming its owner (the longest registered id that prefixes
    the key) moved to phase B, with the detail view that would show it.
  - There is no migration. Why: the writer and parser already handle this
    form, and a table form (`[mods."<id>"] enabled`) would need parser and
    writer changes in `recomp_cfg.c` for no gain the user asked for.
  - mod-connectivity D9's default-off `enabled` is not taken.
- **Captured-control bindings** live under `[input.controls]` (D3).
  **Action bindings** stay in `[input.actions]`.
- **A mod with an `XBOX_SET_ENABLE` setting.** Its Enabled row is that
  setting (for the free camera, `camera.free`).
  - `mods."<id>"` keeps its 3D meaning as a file-only override: `false`
    means the mod is never inited.
  - The State row then reads "Off (`mods."<id>"` = false)".
  - Turning Enabled on from the menu stages both the enable setting and
    the removal of `mods."<id>"`.
  - Why: a stale 3D `false` from the menu must not silently beat
    the new row, and keeping the key's meaning needs no migration.
  - This replaces D9's `follows` field. D9's `needs` stays in
    mod-connectivity.
- **The init rule.** It can't depend on `on_enable`, because a mod
  registers that from inside `init`. It depends on the descriptor:
  - `mods."<id>"` false: not inited.
  - The enable setting on: inited.
  - The enable setting off, the menu on, and the enable's live class
    `ENHANCE_LIVE`: inited **dormant**. `init` must register `on_enable`
    and leave the stock path untouched (5B.2). If it returns without
    `on_enable`, one `[MOD]` warning is logged and the row reads "applies
    at restart".
  - Otherwise not inited. Its row reads "applies at restart" when changed.
  - A mod with no enable setting follows `mods."<id>"` as in 3D.
  - Why: turning a mod on live needs `init` to have run, and a stock run
    (menu off) must run nothing.
- **Precedence**, highest first, for a setting or an action's bindings:

  | # | source | note |
  |---|---|---|
  | 1 | env row | read-only in the menu |
  | 2 | user file, current key | `config.toml` |
  | 3 | user file, an alias | queued for rewrite |
  | 4 | defaults file, current key | `config.default.toml` |
  | 5 | defaults file, an alias | stock; never rewritten |
  | 6 | descriptor default | |

  - The defaults file is applied per layer, so a user alias (row 3) beats
    a defaults-file key (row 4). Why: the user's file is what the player
    edited, whatever its form.
  - A value equal to stock, meaning rows 4 to 6, is removed on Save, as
    today.
  - `mods."<id>"` = false sits above all of these for the init rule, as
    stated above.
- **Pending rewrites.** At load, every alias read from the user file
  (row 3) goes on a pending-rewrite list: write the current key with the
  value and remove the alias. `collect()` always includes that list, so the
  rewrite happens at the first Save even if nothing was edited. Why:
  `collect()` writes only changed slots and dirty actions, so an untouched
  alias would otherwise never move. Defaults-file aliases are never
  rewritten: that file ships with the game.
- **Unknown keys.**
  - With a descriptor, the toolkit knows the mod's valid keys. It marks
    exactly those read, off or on, instead of marking the whole prefix.
    The unused-key report then lists one line per undeclared key under
    `mods."<id>..."` or `[input.controls]`, and per key of an id not in
    this build.
  - Save never removes them, and "Reset this mod" and "Reset all" don't
    either: `recomp_cfg_patch` writes only the keys it owns.
  - Why: a typo under a disabled mod should be reported, and a config
    shared between builds, or kept for a mod the player removed, must
    survive.
  - A mod with no descriptor keeps 3D's prefix marking.
- **Stock.** Every default comes from the descriptor, and
  `config.default.toml` repeats it for the player's reference. A missing
  key means the default.

### D5. Mods page detail view

Every mod row opens its detail page; OK no longer toggles it.

```
Free camera                                  v1.0
Author        BLiNX 2 recomp
About         Fly a detached camera around the stage. The game
              pauses its camera while you fly; the HUD can hide.
State         Off
Enabled       [ off ]                               ●
-- Controls --------------------------------------------
Toggle flight      F6, Guide+Y
Toggle HUD         F7
Freeze game        End
Reset camera       Home
Move               Left stick (keys W A S D)   while flying
Look               Right stick (keys I J K L)  while flying
Rise               RT, X (keys R, E)           while flying
Sink               LT, Y (keys LShift, Q)      while flying
Fast               White (key C)               while flying
Slow               Black (key Z)               while flying
Mouse              Look                         while flying
-- Settings --------------------------------------------
Speed              1.00x                            ●
Look sensitivity   1.00x                            ●
Mouse sensitivity  1.00x                            ●
Invert look X      off                              ●
Invert look Y      off                              ●
Fast multiplier    4.0x                             ●
Slow multiplier    0.25x                            ●
HUD while flying   keep               next activation
Reset this mod
------------------------------------------------------
Footer: Units per second, times the base speed. 0.05 to 20.
```

- **Header, Author and About** come from the descriptor. About is a new
  R_TEXT row: it is word-wrapped to the panel width and can't be selected.
  Why: the overlay has no wrap today, and a summary cut to one line was the
  complaint.
- **State** shows On, Off, "Off (`mods."<id>"` = false)", Failed (with the
  reason from the log line) or "On at restart".
- **A failed mod's page still lists its controls and settings** from the
  descriptor, marked "unavailable". Its actions were dropped by
  `drop_owner`, so they can't be rebound until the next start. Why: the
  player should still see what the mod offers and why it isn't working.
- **Controls.**
  - Action rows reuse the R_BIND capture: OK captures, X clears.
  - Captured rows get a new R_CTL capture (D3) with the same 400 ms chord
    hold and the same capture phases.
  - A dormant action is marked "(mod off)".
  - The keys in parentheses come from `[input.bindings]` and are
    read-only; the row's help says where to change them.
- **Settings** use the TOGGLE, CHOICE and RANGE rows built from D2.
  - The live dot is drawn as on other pages.
  - "next activation" and "applies at restart" stand in for the dot.
  - An env-forced row is greyed out with "set by `RECOMP_...`".
- **The footer shows the selected row's help** whenever no status message
  is showing (the 3 s status line still wins). Why: the help text needs a
  place to show without crowding the rows.
- **Reset this mod** puts the mod's settings and bindings back to the
  stock: the defaults file's value, else the descriptor's default. They
  are staged like any edit until Save. Enabled is not reset, and unknown
  keys are kept.
- **A mod with no descriptor** shows its name, State, Enabled and its
  `menu_add` items, as 3D does now.
- **The Controls page groups actions by owner** under the owner's title.
  Mod groups follow the toolkit's own (`menu.*`, `shot.*`) and the game's,
  and a dormant mod's group says so. Captured controls show only on the
  mod's own page. Why: they only work while that mod holds capture.

### D6. The free camera, the first user

The free camera absorbs enhance-menu-preview phase 5B in full, plus the
descriptor below.

**Actions** (defaults from 5B, the user and orchestrator, 2026-10-22;
the user confirmed End and Home on 2026-10-27):

| id | label | defaults | aliases | env |
|---|---|---|---|---|
| `toggle` | Toggle flight | `F6`, `guide+y` | `camera.free_toggle` | `RECOMP_CAMERA_FREE_TOGGLE` |
| `hud` | Toggle HUD | `F7` | `camera.free_hud_key` | `RECOMP_CAMERA_FREE_HUD_KEY` |
| `freeze` | Freeze game | `End` | `camera.free_freeze_key` | `RECOMP_CAMERA_FREE_FREEZE_KEY` |
| `reset` | Reset camera | `Home` | `camera.free_reset_key` | `RECOMP_CAMERA_FREE_RESET_KEY` |

- The old defaults F8 and F5 move: F5 is the quick save. A config that
  names them through an alias keeps them. The camera is opt-in, so only
  players who turned it on see the change.
- The four env rows stay, in `recomp_env_game.h` and `docs/env.md`, now
  bound to the actions (D3). `test_free_camera.py` keeps all eight env
  mappings, with the new defaults.

**Captured controls**, all with the note "while flying", in
`[input.controls]`:

| id | kind | defaults |
|---|---|---|
| `move` | STICK | `left_stick` |
| `look` | STICK | `right_stick` |
| `rise` | BUTTON | `rt`, `x` |
| `sink` | BUTTON | `lt`, `y` |
| `fast` | BUTTON | `white` |
| `slow` | BUTTON | `black` |
| `mouse` | INFO | Look |

`fly()` reads them through `control_value` in place of
`cat_pad_port0_last`. It keeps `fc_axis` with each source stick's dead
zone, `analog()`, and the White and Black threshold. With the default
bindings it computes the same `fc_input` as today, and a cat test proves
it.

**Settings.** Legacy keys are kept through `key`, so existing configs and
env rows keep working.

| name | key | kind | default, range | live |
|---|---|---|---|---|
| enable | `camera.free` | enum off/on, ENABLE | off | live |
| speed | `camera.free_speed` | float 0.05..20 step 0.05 | 1.0 | live |
| look_sens | `camera.free_look_sens` | float 0.05..10 step 0.05 | 1.0 | live |
| mouse_sens | `camera.free_mouse_sens` | float 0.05..10 step 0.05 | 1.0 | live |
| invert_x | `camera.free_invert_x` | bool | false | live |
| invert_y | `camera.free_invert_y` | bool | false | live |
| fast | `camera.free_fast` | float 1..20 step 0.5 | 4.0 | live |
| slow | `camera.free_slow` | float 0.05..1 step 0.05 | 0.25 | live |
| hud | `camera.free_hud` | enum keep/hide | keep | next activation |

- **New settings: `mouse_sens`, `invert_x`, `invert_y`, `fast` and
  `slow`.** Each default gives today's flight exactly.
  - `invert_x` flips the yaw sign and `invert_y` the pitch sign, for the
    stick and the mouse alike.
  - `fast` and `slow` replace the constants `FC_FAST` (x4) and `FC_SLOW`
    (x0.25) in `fc_fly_step`; they become `fc_params` fields.
  - `mouse_sens` multiplies `FC_MOUSE_RATE` only. `look_sens` keeps
    multiplying both the stick and the mouse. Why not split `look_sens`
    into stick-only: a config with `look_sens = 2` would then turn the
    mouse slower than it does today. With `mouse_sens` on top, a mouse
    player tunes the mouse alone and every existing value means what it
    did.
  - Each gets a `RECOMP_CAMERA_FREE_*` row (`_MOUSE_SENS`, `_INVERT_X`,
    `_INVERT_Y`, `_FAST`, `_SLOW`) in `recomp_env_game.h` and
    `docs/env.md`, like its siblings. Why: `scripts/test_free_camera.py`
    drives every camera key through env.
- **What the camera holds, and what is exposed** (the D10 principle, from
  `free_camera.c` and `free_cam_fly.{c,h}` at cat `main`):

  | value in the code | today | exposed | why |
  |---|---|---|---|
  | `FC_MOVE_BASE` 80 units/s | constant | through `speed` | `speed` is its multiplier; a second knob would say the same thing |
  | `FC_LOOK_RATE` 1.8 rad/s | constant | through `look_sens` | same: `look_sens` is its multiplier |
  | `FC_MOUSE_RATE` 0.0025 rad/count | constant | `mouse_sens` (new) | mouse and stick players want different rates |
  | `FC_FAST` x4, `FC_SLOW` x0.25 | constants | `fast`, `slow` (new) | how much faster or slower is a preference |
  | pitch and yaw signs | fixed | `invert_x`, `invert_y` | a preference, commonly asked for |
  | HUD hidden while flying | `camera.free_hud` | `hud` | already a key |
  | stick dead zones 7849 / 8689 | constants in `fly()` | no | the toolkit's `input.pad_deadzone_left` and `_right` already apply before the recorded state, for the game and the camera alike; a camera-only dead zone would stack on top of them. The constants are the XInput standard thumb dead zones, the floor `fc_axis` needs |
  | trigger threshold for fast/slow | `XBOX_ANALOG_BUTTON_THRESHOLD` | no | a toolkit constant shared by every button read, not the mod's |
  | `FC_PITCH_MAX` 1.50 rad | constant | no | a correctness limit: it stops short of straight up or down, since past +-pi/2 the view would turn upside down |
  | `FC_DT_MAX` 0.1 s | constant | no | a hitch guard, not a preference: a long frame must not throw the camera |
  | roll and the extra angles (+0x14..+0x1C) | written 0 | no | free-camera D2 keeps them 0; a roll control would need flight work first |
  | field of view | not touched | no | the camera writes only position, pitch and yaw; it holds no FOV. A FOV setting would be a new feature on a game field the mod doesn't own today, so it is a follow-up, not a setting to expose |
  | the freeze rules (dropped on the menu, retry or a stage start) | code | no | they keep the game's state sound (free-camera D5); an option to keep a freeze would corrupt it |
  | guest addresses, HUD program hashes | `#define`s | no | game facts, not choices |
  | `cam_log` lines | always | no | diagnostics, not a player setting |
- **The log line** `[ENHANCE] camera.free=on|off` keeps its text, but the
  toolkit prints it (D2). The printf leaves `free_camera.c`.
  `test_free_camera.py`'s source check moves to a `tests/mod_desc` case
  for the toolkit's line, and the cat test checks the descriptor marks
  `camera.free` as the enable. Why: the stock run must still print it for
  `enhance_stock`, and under D4's init rule the camera's `init` doesn't
  run on a stock run (menu off, `camera.free` off).
- **The hand-written range checks are deleted.** The toolkit's clamp lines
  replace them, and the test expectations move with them.

### D7. Backends

- **The pages are drawn by the overlay** (microui, shared draw list). The
  overlay is rendered by the overlay renderer on both Metal and D3D11. No
  backend file changes.
- **Parity risks are in the new rows:**
  - the wrapped text, which depends on glyph metrics from the same atlas;
  - the greyed and dimmed colours.
  The Deck (D3D11 under Proton) hands-on checks both against the Mac
  shots, and it folds into enhance-menu-preview phase 6 if that hasn't run
  yet.
- **The CPU rasteriser** only has to keep building. It has no overlay, so
  any gap goes in TASKS.md.

### D8. Sequencing around the tracker items

- **Phase A has no menu dependency** and can start now.
- **Phase B's rows (B.1-B.7) don't depend.** Only its conflict
  check (B.8) and phase D's R_CTL capture do. Why: they extend the tracker item's
  check and use its capture phases, and both edit `capture_finish`. So B
  can start before the tracker item merges, and B.8 lands after it.
- **The tracker item shares no code path with this change.** Mod settings never use
  FLUSH (D2). The only overlap is textual in `enhance_menu.c`: whichever
  merges second rebases.

### D9. The descriptor dump

- **`RECOMP_MODS_DESCRIBE=json`** writes every mod's descriptor and its
  resolved values as JSON, then exits before the game starts.
  - A toolkit config-tier row in `recomp_env.h`, with a row in cat's
    `docs/env.md`. Any other value logs one `[MOD]` line and is ignored.
    Why a format value rather than `=1`: a later format needs no new key.
  - `RECOMP_MODS_DESCRIBE_OUT=<path>` writes the JSON to that file,
    replacing it; without it the JSON goes to stdout. Why a file option:
    the Windows build is a GUI-subsystem exe with no stdout, and Proton
    drops a game's stdio (cat `main.c` `host_stdio_setup`), so a launcher
    there needs a file. Logs stay on stderr either way.
- **When.** Inside `xbox_enhance_init`, which cat calls from
  `host_enhance_init` before the window, audio or guest exist.
  - Config files and env are read as usual. Descriptor actions are
    registered and every setting and binding is resolved by D4's
    precedence table, then the action table is built as a start builds
    it (`enhance_actions_rebuild`: parse, classify, one input per
    action). Only `enhance_actions_start`'s report of unknown
    `[input.actions]` keys is left out, since it arms nothing.
  - No mod `init` runs, nothing is armed and no `[ENHANCE]` hook line is
    printed. Why: the dump must describe a mod without running its code,
    the same rule as the detail view (D1).
  - Then it writes the JSON and calls `exit(0)`; a file it can't write
    logs one `[MOD]` line and exits 1.
  - A title must call `xbox_enhance_init` before it opens a window. cat
    does; b3 is checked when it adopts descriptors.
- **Content** (schema 1, UTF-8, JSON-escaped):

  ```json
  {"schema": 1, "api": 3, "mods": [
    {"id": "camera.free", "title": "Free camera", "summary": "...",
     "author": "...", "version": "...", "descriptor": true,
     "init": "no", "enable": "camera.free",
     "settings": [
       {"name": "speed", "key": "camera.free_speed", "kind": "float",
        "label": "Speed", "help": "...", "unit": "x",
        "default": 1.0, "lo": 0.05, "hi": 20, "step": 0.05,
        "live": "live", "env": "RECOMP_CAMERA_FREE_SPEED",
        "value": 1.0, "source": "default"}],
     "controls": [
       {"id": "toggle", "kind": "action", "action": "camera.free.toggle",
        "label": "Toggle flight", "help": "...", "when": null,
        "defaults": ["F6", "guide+y"], "bindings": ["F6", "guide+y"],
        "env": "RECOMP_CAMERA_FREE_TOGGLE", "source": "default"}]}]}
  ```

  - `init` is what D4's init rule would do this run: `yes`, `dormant`,
    `no`, or `failed` with a `reason`.
  - `source` names the precedence row that won: `env`, `user`,
    `user_alias`, `defaults`, `defaults_alias` or `default`.
  - An enum's `default` and `value` are choice text, with `choices`
    listed. Fields that don't apply are left out.
  - A control's `bindings` are its texts as the config gives them.
    `refused`, present only when nonempty, lists those that would never
    fire at a start: an unknown input name, an input another action
    holds, or a pad input left to the game (an off binding). Why mark
    rather than drop: the launcher shows the player's own text and says
    which of it does not bind, and it never reruns the toolkit's rules.
  - A mod without a descriptor is listed with its id and
    `"descriptor": false` only.
  - Only mods are listed; the toolkit's and the game's own keys are not.
- **Stability.** Fields are only added. A change that removes or changes
  the meaning of a field bumps `schema`. Why: the launcher (a follow-up)
  and the CLI will read it, and they ship separately from the game.

### D10. A mod exposes every sensible setting

- **The principle** (the user, 2026-10-27): anything a mod holds that a
  player could sensibly want to change is a descriptor setting, with a
  label, help, range and live class. A value is left as a constant only
  for a stated reason, recorded beside the mod's settings table:
  - another knob already covers it (a base rate under a multiplier);
  - the toolkit owns it for every input (pad dead zones, the button
    threshold);
  - it keeps the game or the maths correct (pitch limit, freeze rules);
  - it is a game fact or a diagnostic, not a choice.
- **Why:** the player should not need a rebuild or an env row to tune what
  a mod already computes, and the dump (D9) then gives a launcher the
  whole set.
- **Applied to the free camera** in D6's audit table: four values are
  newly exposed (`mouse_sens`, `invert_x`, `fast`, `slow`) beside
  `invert_y`, and each one left out has its reason.
- **Review rule.** A mod's descriptor review checks the mod's source for
  constants that should be settings, the same way D6's table was built.

## Risks / Trade-offs

- **Two binding tables.** Actions live in `[input.actions]` and captured
  controls in `[input.controls]`, because they behave differently: actions
  fire once and are consumed, captured controls are held. The rows say
  "while flying", and the Controls page shows only actions.
- **Guest-source fly controls** can't use paddles or Guide (D3). A player
  can still map a paddle to a guest button in `[input.pad]`.
- **Recording costs one atomic load per poll** on a stock run. Recording
  happens only while a mod holds capture.
- **The `[ENHANCE] camera.free=` line moves into the toolkit.** If the
  descriptor were wrong, the stock line would vanish. A ctest checks it,
  and the CLI treats a missing line as stock, so a golden would not fail
  loudly.
- **Startup cost.** The descriptor's keys are read and checked once, for
  the free camera's 9 settings and 11 controls. That is negligible.
- **API v3 for one field.** Bumping the version is cheap, and the `size`
  field keeps later additions free of further bumps.

## Migration Plan

Phases are in `tasks.md`.

| phase | where | days | what |
|---|---|---|---|
| A | toolkit | 2.5 | descriptor, settings, config, precedence, API v3, the dump |
| B | toolkit | 1.5 | detail view and Controls grouping; B.8 after the tracker item |
| C | cat | 1.5 | free camera descriptor, 5B, the new settings |
| D | toolkit + cat | 2.5 | recorded state, captured controls, fly rebinding |
| E | hosts | 1 | hands-on Mac, Deck and Windows; docs |

Rollback: each phase is one squash commit. A descriptor-less mod table is
the v2 behaviour.

## Phase A as built (review, 2026-10-27)

Where phase A differs from the text above, or settles what it left open:

- **`[input.actions]` fall-through.** A value of the wrong type in the
  user's `config.toml` now falls through to the defaults file's row, not
  to the built-in default, as D4 does for settings. Before, the built-in
  default won. This changes behaviour for existing action keys, in the
  player's favour: the shipped defaults file still applies.
- **Owner attribution** of unknown keys moved to phase B (D4).
- **The Mods page toggle** of a descriptor mod saves its enable setting
  under that setting's key (an ENUM as its choice text), never
  `mods."<id>"`. Turning it on also drops a stale `mods."<id>" = false`.
- **The enable log line** prints the value the run uses:
  `[ENHANCE] <key>=off (held off by mods.<id>)` when the switch wins.
- **Key length.** A setting or control key of 64 bytes or more refuses
  the descriptor (`enhance_cfg_bind_env` holds 63). An env row that
  still cannot bind (a full table) logs one `[MOD]` line.
- **A refused descriptor** marks its `mods.<id>.` and
  `input.controls.<id>.` keys read, so its one refusal line is not
  followed by an unknown-key line per key.
- **A config patch** skips only a key refused for a table and
  writes the rest; the caller gets every skipped key in one message.
- **The arm keys** have their own lock, since a live switch changes them
  from the menu thread while the input thread reads them.
- **The dormant mark** runs for every mod that is not inited, v2
  included; a mod with no registered action has nothing to mark.
- **Setting values** read through `api->setting` stay valid until the
  process exits: shutdown frees nothing, only a re-init (the tests) does.
- **The dump's bindings**: see D9, `refused`.

## Decisions from the user (2026-10-27)

The four open questions of the first draft, answered by the user:

1. **Fly controls on host keys directly: yes.** `[input.controls]` takes
   guest sources and host keys (D3), so keys need not go through
   `[input.bindings]`.
2. **More settings: yes, "anything a mod has that seems sensible to expose
   and configure to the end user should be presented".** It became the
   D10 principle; D6 applies it to the free camera (invert X, fast and
   slow multipliers, mouse sensitivity) and lists what stays a constant
   and why.
3. **A descriptor dump: yes, so a launcher can tweak values before the
   game starts.** The dump is specified here (D9). The launcher is a
   follow-up, not in this change; E.6 files it.
4. **End and Home stay the freeze and reset defaults: yes.** Phase C is
   unblocked.
