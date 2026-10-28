## Why

The menu lists the free camera on the Mods page, but the page shows
only a name and an Enabled switch. The player can't see what the mod does,
how to fly it or how to change its keys (the user, 2026-10-27: "Mods should
be allowed to declare some extra information, and probably configuration. In
this case, the camera mod should present the camera controls and allow
rebinding them as well").

Today a mod is only `{name, init, shutdown}`. Its keys, ranges and controls
are known only inside its `init`, so:
- a mod that is off, or whose `init` failed, has nothing to show;
- each mod clamps its own config by hand (the free camera has eight keys and
  four hand-written range checks);
- the fly controls (stick, triggers, White and Black) can't be rebound,
  because they are read straight from the merged pad.

## What Changes

- **Mod descriptor (toolkit, API v3).** `struct xbox_mod` gains a pointer to
  a static, versioned `struct xbox_mod_desc`:
  - text: title, summary, author, version;
  - typed settings: bool, int, float and enum, each with its default, range
    or choices, help text and when it applies (live, next activation or
    restart);
  - controls: actions (host hotkeys) and captured controls (inputs the mod
    reads while it holds the pad).
  The toolkit validates the settings at start, owns their config keys and
  builds their menu rows. A v2 mod table with no descriptor runs unchanged.
- **Config.** The flat `[mods]` table stays as 3D ships it:
  - the switch is `mods."<id>"`;
  - a mod's own keys are `mods."<id>.<name>"`, unless a descriptor keeps a
    legacy key (`camera.free_speed`);
  - captured-control bindings get their own flat table, `[input.controls]`.
  One precedence table orders env, the user file, the defaults file and
  aliases. Aliases in the user file are rewritten at the first Save.
  Unknown keys are reported and never dropped by Save.
- **Descriptor dump.** `RECOMP_MODS_DESCRIBE=json` (with
  `RECOMP_MODS_DESCRIBE_OUT=<path>` for a file) writes every mod's
  descriptor and resolved values as JSON and exits before the game starts,
  running no mod code. A launcher that edits these values before start is
  a follow-up.
- **Mods page detail view.** Every mod opens into a page with its info, its
  state, a Controls section and a Settings section:
  - controls can be rebound under the shared capture and conflict rules;
    
  - each setting is marked live or "applies at restart";
  - the footer shows the selected row's help.
  The Controls page groups actions by owner.
- **Captured controls.** The toolkit records port 0's guest state after
  the chord mask and before the neutral pad, through a new
  `xbox_enhance_pad_seen` call and a seqlock. `api->control_value` lets a
  mod read its fly controls by index. Bindings name guest buttons and
  sticks (or host keys), so they can be rebound, and the guest never sees
  them while the mod flies. `xbox_InputGetState` records and applies the
  neutral pad itself, so input_core titles get both without pad glue.
- **Free camera, the first user (cat).**
  - It absorbs enhance-menu-preview phase 5B: its four hotkeys become
    actions, it turns on and off live, and its parameters are atomics.
  - It follows a new principle: a mod exposes every setting a player could
    sensibly want, and says why each other value stays a constant.
  - Its settings: speed, look sensitivity, HUD while flying, and new mouse
    sensitivity, invert X, invert Y, and fast and slow multipliers.
  - Its fly controls become captured controls with the stock defaults.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `enhancements`: mod descriptor (API v3), descriptor-owned config keys,
  Mods page detail view, captured controls, the descriptor dump, the
  free camera's descriptor.

## Impact

- **Toolkit (`posix-host/portability`).**
  - `src/enhance/mod.{h,c}`;
  - `enhance_menu.{c,h}` (a new `ENHANCE_LIVE_ACTIVATE` class);
  - `enhance_actions.{c,h}`;
  - `enhance_input.c` and `input_core.c` `xbox_InputGetState` (the
    recorded port-0 state and the neutral pad);
  - `recomp_env.h`: `RECOMP_MODS_DESCRIBE` and `RECOMP_MODS_DESCRIBE_OUT`;
  - `enhance_cfg.c` (unknown-key report);
  - `recomp_cfg.c` (`input.controls.` added to `flat_tables[]`). New ctest
  `tests/mod_desc`; `tests/enhance_menu` and `tests/input_actions` grow.
  Docs: `docs/runtime/config.md` "Mods" and "Host actions".
- **cat.**
  - `src/free_camera.c` and `free_cam_fly.{c,h}`;
  - `src/pad_input.c`: `xbox_enhance_pad_seen` replaces `g_port0_seen`;
  - `packaging/config.default.toml`: `[input.actions]` and
    `[input.controls]` rows;
  - `docs/env.md`: rows for the five new camera settings and the two dump
    keys, and the four key rows now bound to actions;
  - `scripts/test_free_camera.py`.
- **Goldens.** Stock behaviour is unchanged: `camera.free` off,
  `[ENHANCE] actions hook=off`. Goldens run for the phases that touch the
  runtime and input (A, C and D).
- **Supersedes.** Phase 5B of enhance-menu-preview moves here (phase C). The
  `follows` field of mod-connectivity-layer D9 is replaced by the
  descriptor's enable setting; `needs` stays there. D9's
  `[mods.<name>] enabled` default false is not taken: the built flat
  `mods."<id>"` switch, default on, stays (see design D4).
- **Out of scope.** A launcher, or the CLI or the wizard, editing mod
  settings before start (a follow-up that reads the dump), Lua or script
  mods, and per-mod themes.
