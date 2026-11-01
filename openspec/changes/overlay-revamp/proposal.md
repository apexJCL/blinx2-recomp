## Why

The in-game menu (enhance-menu-preview, then mod-settings A/B and the
shader profiles) is now the main way players change settings. It ships ON for
every game. It was built pad-first, and the user's list for 2026-10-31 names
the gaps:

1. **Keyboard and mouse.** There is no mouse support: phase 3F of
   enhance-menu-preview has a design, but it was never built. The keyboard
   gets VK edges only, so the rename editor reads key codes as a US layout.
   On Windows, macOS and Linux you should be able to hover, click, drag,
   scroll and type.
2. **Typing in SteamOS Game Mode.** There is no physical keyboard and no
   text input path at all, so naming a profile or a save in Game Mode means
   cycling through letters on the pad.
3. **Shader controls.** Every `#pragma parameter` is drawn as a slider, even
   on/off ones (TRINITRON_CURVE 0..1 step 1, SHARPER, scaleInLinearGamma,
   FSR_GRAINCOLOR) and mode pickers (MASK 0..3, shadowMask 0..4).
4. **Import and export.** There is no way to move a config or a shader
   profile in or out of the game, and microui has no file explorer. The save
   states spec (D9) needs the same picker for slot export.
5. **Free camera page.** It has an Enabled switch and nothing else. Its
   toggles (invert X/Y), speeds and keys need rows and rebinding
   (mod-settings C/D, not started).
6. **Layout.** The tab strip has nine text tabs, which no longer fit at
   compact widths. The footer mixes the controls, the selected row's help,
   the status and the live tag in one line. There is no header with window
   controls.

Added by the user on the same day:
- **Footer.** It should stay a summary: navigation hints for the device in
  use, whether there are unsaved changes, and Cancel and Save buttons so
  saving works from any section.
- **The blue badge in Render shows on default values.** The code shows what
  it really is: the *live-class* dot (`draw_row`, "a dot for a change that
  shows now"). It is drawn for every LIVE or FLUSH item whatever its value.
  It is not a changed marker. The unsaved state exists (`slot.cur !=
  slot.base`) but only the footer count uses it. This is a bug: players read
  it as "changed".
- **Hints.** Each section, and each entry, needs a short explanation that
  works with the pad as well as the mouse. Mods should be able to supply
  their own.

## What Changes

- **Three-part layout (toolkit).**
  - **Header:** title, the hints toggle, compact/expanded and close.
  - **Content:** a vertical toolbar of `[icon label]` sections in place of
    the tabs, beside a scrollable section. Each section opens with a
    one-line intro.
  - **Footer:** a summary: device hints, the unsaved count or status, and
    **Cancel** and **Save** buttons.
  - Compact (today's side panel) and expanded (covers the game) size modes,
    remembered between sessions.
  - One pure layout and hit-test module feeds both the draw and the mouse,
    and is tested on its own.
- **Input model (toolkit).**
  - The pad, keyboard and mouse share one focus. A hover moves the selection
    only when the mouse really moves.
  - The *latest input device* drives the footer glyphs (Xbox, PlayStation,
    Nintendo, keys or mouse) and the cursor's visibility.
  - Mouse support absorbs 3F: suspend the game's mouse while the menu is
    open, and the cursor layer. A new absolute pointer snapshot (window
    position, buttons, wheel) comes from the Win32 procs and the SDL loop,
    since the game's mouse model has only relative counts. While open, the
    menu also holds back a mod's mouse divert (the free camera) and gives
    it back on close.
  - View and L3 act on release, and not while they are part of a game's
    menu chord (BLiNX 2's `back+left_thumb@400`).
- **Text input (toolkit).**
  - A lock-free single-producer, single-consumer text ring fed by
    `WM_CHAR` (both game windows) and `SDL_EVENT_TEXT_INPUT`. The menu asks
    for text input from the guest's thread; the window's thread applies it
    (`SDL_StartTextInput` and the input area), as the mouse capture does.
    Control characters are dropped; editing keys stay key edges.
  - On native Linux this brings up the Steam keyboard in Game Mode.
  - Under Proton, a Deck spike tests `steam://open/keyboard` through Wine.
  - An in-overlay pad keyboard is always the fallback. No Steamworks.
- **Unsaved marker fix (toolkit, phase 1).**
  - The row dot means *unsaved* (differs from the saved value).
  - Values that differ from the default get a separate, quieter mark.
  - The live class moves to words and the tooltip.
  - A ctest covers the rule.
- **Cancel and Save (toolkit).**
  - Save writes from anywhere: footer button, Y, F5, Ctrl+S or Cmd+S.
  - A new revert puts every unsaved change back: slots, bindings (now
    compared by value against a saved copy), the present chain's overrides
    and the shader edit state. A profile delete stays immediate, and the
    dialog says so.
  - Cancel, B/Esc at the top level, the close button and the menu toggle
    all open one dialog when there are unsaved changes: **Exit without
    saving**, **Exit and Save**, **Go Back**. Focus starts on Go Back.
  - The Save section shrinks into **Files**: path, import, export and reset
    to defaults.
- **Hints (toolkit, cat, mods).**
  - `struct enhance_item` gains `help`. Mod settings and controls already
    have it. Shader params take theirs from the kinds sidecar, since their
    description is already the row's label.
  - The focused entry gets a tooltip by default (pad focus or mouse hover).
    The header toggle switches to inline hints under each row, and the mode
    is remembered.
- **Shader parameter kinds (toolkit).**
  - A declared kind wins. Otherwise 0..1 step 1 becomes a toggle (the
    four on/off params, FSR_GRAINCOLOR included), and a small integer
    range whose description names its choices becomes a choice.
  - A toolkit sidecar declares the shipped presets (MASK, shadowMask).
  - Profile files keep their numbers.
- **Import and export (toolkit).**
  - An in-overlay file browser over known roots (exports, config, shader
    profiles, home). It works with the pad, in fullscreen, under Proton and
    in Game Mode.
  - The OS picker is a low-priority fallback, in the last, optional phase:
    only where the browser cannot read (macOS TCC-protected folders, a
    sandboxed Linux package).
  - Imports land as unsaved changes, so "Exit without saving" undoes them.
  - Names are sanitised, writes are atomic, exports confirm before they
    overwrite, and imports are size-capped.
- **Icons and input glyphs (toolkit).**
  - Section icons come from a Lucide subset (ISC).
  - Pad and mouse button glyphs come from a Kenney Input Prompts subset
    (CC0), one family per detected pad: Xbox, PlayStation, Switch, Steam Deck
    and a generic fallback.
  - Keyboard keys are drawn as key caps carrying the layout's key name.
  - Both sets are converted once into small TTFs and baked into the
    font atlas by stb_truetype, so they scale with the text.
  - Footer hints, rebinding rows, the free camera page and mod text ask for
    a glyph by input source or by action (`{pad:south}`, `{act:menu.save}`).
  - Nothing comes from any game, and no platform logos are used.
- **Free camera (cat and toolkit; mod-settings C and D run inside this change).** Toggles, speeds,
  mouse sensitivity, and rebinding of the actions and the captured fly
  controls on its page.
- **Config keys and docs (toolkit, cat).**
  - New keys, all file-only: `overlay.menu_size`, `overlay.menu_hints`,
    `overlay.file_dialog` and `overlay.steam_keyboard`.
  - `overlay.ui_scale` (3E) lands here, restart-only: the atlas is baked
    once at start, and a live rebake is 3E.1's worker, not this change.
  - One trace token, `RECOMP_TRACE=menu_input`, a TRACE-tier `recomp_env`
    row.
  - Each key gets a cat `docs/env.md` row and a toolkit
    `docs/runtime/config.md` entry.

## Capabilities

- Modified: **enhancements**: the menu's layout, input, hints, save flow and
  file import/export; shader parameter kinds; the free camera page.

## Impact

- **Toolkit (`posix-host/portability`):**
  - `src/enhance/enhance_menu.c` (split into layout, input and browser
    files);
  - `src/kernel/nv2a_overlay_ui.c` (icon glyphs);
  - `src/input/` (text ring, pointer snapshot, latest device);
  - the Win32 window procs in `fb_present.c` and `nv2a_pb_d3d11.c`
    (`WM_CHAR`, pointer messages);
  - `fb_present_sdl.c` (text and pointer events, the text-input sync);
  - `nv2a_present_chain.c` (override revert, the param's file) and
    `shader_profile_edit.c` (revert);
  - `third_party/lucide/` and `third_party/kenney-input/` (new, with
    licence files and the conversion script in `tools/`);
  - new ctests.
- **cat:**
  - `src/free_camera.c` (descriptor, already planned in mod-settings C);
  - `docs/env.md` rows;
  - `config.default.toml` comments.
- **CLI:** none expected. `golden.py` sets nothing for the menu; it fails
  a run whose log lacks `menu.enabled=off`. The pin is each game's
  `golden.json` env (`RECOMP_MENU=0`, `RECOMP_CONFIG=none`). H.3 audits
  every game's file: cat and JSRF have both; SSX 3 has only
  `RECOMP_CONFIG=none` and gets `RECOMP_MENU=0` added.
- **Stock behaviour:**
  - With the menu closed nothing changes.
  - Goldens pin the menu off in each game's `golden.json`, and the CLI
    checks the log, so they draw no menu.
  - The compact size mode matches today's panel.
- **Backends:** the menu still reaches D3D11 and Metal as one triangle list
  from the converter, so the two agree by construction. Only window message
  plumbing differs per host.
