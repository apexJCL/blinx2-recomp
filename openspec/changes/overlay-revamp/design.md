## Context

**What exists today** (toolkit `posix-host/portability` ef8635e2, cat `main`
f2b9ef6).

- **Overlay** (`src/kernel/nv2a_overlay*.c`):
  - Four layers, STATS, TOAST, MENU and CURSOR, each a triple-buffered draw
    list.
  - microui 2.02 is unmodified and used only as a stream of draw commands.
    `nv2a_ovl_convert` turns that stream into textured triangles once, and
    every presenter (D3D11, Metal, the CPU reference) draws the same list.
  - Custom commands: OVL_CMD_RRECT, IMAGE and CURSOR, with 8 image slots.
  - Theme tokens are set at 1080 lines. `nv2a_ovl_ui_scale` =
    clamp(out_h / 1080, 0.5, 3.0), and sizes come from the placement rect,
    never the window.
  - The font, Atkinson Hyperlegible (OFL), is packed into one coverage atlas
    with `stbtt_PackFontRanges`.
- **Menu** (`src/enhance/enhance_menu.c`, 3846 lines):
  - A custom row model and state machine; microui's widgets and input are
    unused.
  - Pages: Render, Shaders, Pack, Game, Mods, Stats, Controls, Debug, Save.
  - Events: `ENHANCE_EV_UP/DOWN/LEFT/RIGHT/OK/BACK/PAGE_PREV/PAGE_NEXT/
    SAVE/CLEAR/CLOSE`, from held pad bits and VK edges
    (`xbox_FramebufferKeyDown`). Repeat is 150 ms, then 60 ms. `s_kbd`
    picks the footer text.
  - The panel is 40% of the width, up to 720 px at 1080 lines, and full
    width under 640 px or on portrait output.
  - The footer holds the hint, or the selected row's help, or the rename
    hint on the left; the status, the unsaved count and the live tag sit on
    the right.
- **Mouse:** none in the menu. Phase 3F of enhance-menu-preview (R9)
  designs it: snapshot, `xbox_InputMouseSuspend`, the CURSOR layer. F-9 and
  F-11 note that the D3D11 cursor and clicks arrive at guest flips.
  - The game's mouse model (`src/input/mouse.c`) carries *relative* counts
    only. `xbox_InputMouseDivert` hands those counts to a mod (the free
    camera) through `xbox_InputMouseTakeCounts`; it is one flag, not a
    stack. `xbox_InputMouseWin32Msg` only observes messages for that model.
    There is no absolute pointer position anywhere today.
- **Overlay atlas:** `nv2a_ovl_font_bake(out_h)` runs once, in
  `nv2a_overlay_arm`, at the scale of that moment (512², 1024² or 2048²).
  Nothing rebakes it; 3E.1's atlas worker was never built.
- **Text:** none. The rename editor maps VK codes as a US layout, with a pad
  letter-cycle. Neither `WM_CHAR` nor SDL text events are read.
- **Hosts:**
  - Windows, and Windows under Proton, use the Win32 windows in
    `fb_present.c` (GDI) and `nv2a_pb_d3d11.c`, with XInput. They never
    link SDL.
  - macOS and native Linux (future) use SDL3 (`fb_present_sdl.c`,
    `keyboard_sdl.c`, `mouse_sdl.c`).
  - Pad families: `XBOX_PAD_FAMILY_XBOX/PLAYSTATION/NINTENDO/STEAM/GENERIC`
    (`host_pad.h`). The SDL3 mapping already exists in
    `src/input/xinput_device.c` (gamepad-input-ux I2.6), read through
    `xbox_InputPadFamily` (`input_core.c`), with the `input.glyphs`
    override (`enhance_input.c`: auto, xbox, playstation, nintendo, steam;
    no `generic` yet).
  - The SDL event loop runs on the main thread (`fb_present_sdl.c`); the
    menu runs on the guest's thread. Window-side state the poll side
    changes is applied in the loop, as `xbox_InputSdlMouseSync` does for
    relative mode.
  - Win32 has a third window proc, `vp_wndproc` in `video_pump.c`, for the
    host movie player's window.
- **Mods** (`XBOX_MOD_API_VERSION` 6, descriptor version 1, `mod.h`): typed settings (BOOL, INT, FLOAT, ENUM) and
  controls, each with `label`, `help` and `unit`. mod-settings A and B are
  merged; C (the free camera descriptor) and D (captured controls and fly
  rebinding) are not started.
- **Shader params:** `struct nv2a_present_param {name, desc, initial, min,
  max, step, ...}` from `#pragma parameter`. Each is shown as
  ENHANCE_ITEM_RANGE.

### Findings

- **The blue dot is not a changed marker.** `draw_row` draws a filled
  accent dot after the label for every item whose `live` is ENHANCE_LIVE or
  ENHANCE_LIVE_FLUSH ("a dot for a change that shows now"). Words are drawn
  for the classes that wait. The dot ignores the value, so it shows on
  defaults.
  - The real unsaved state is `slot_saveable(s) && strcmp(s->cur,
    s->base)` (`enhance_menu_unsaved`), where `base` is the value as last
    loaded or saved.
  - Shader overrides (`nv2a_present_chain_override_at(..., &dirty)`), the
    `s_adirty` binding flags and `shader_edit_unsaved` are its other
    sources.
  - None of them can be rolled back today. `s_adirty` is a set-only flag
    with no copy of the saved bindings (`action_set` sets it, Save and
    reload clear it). The present chain's overrides have `_saved` and
    `_dirty` but no revert. The shader edit state has `reset_values`
    (back to the preset) but no revert to the file, and
    `shader_edit_delete` removes the profile's file at once.
  - Only the footer count and the Shaders tab dot read them.
- **Hints:** `struct enhance_item` has `note`, a dimmed word after the label
  ("scale 2+"), but no `help`. Mod settings and controls have `help`.
  Shader params have `desc`, but `param_list` already uses it as the row
  label (`desc`, else `name`), so it is no help text. Row help reaches the
  footer only.
- **Shader parameter inventory** (`assets/shaders`):

  | Preset | Param | Range / step | Today | Proposed |
  |---|---|---|---|---|
  | crt-lottes-fast | TRINITRON_CURVE | 0..1 / 1 | slider | toggle (inferred) |
  | crt-lottes-fast | MASK | 0..3 / 1 | slider | choice (sidecar) |
  | crt-lottes-fast | CORNER | 0..11 / 1 | slider | slider |
  | crt-lottes-fast | CRT_GAMMA | 0..51 / 0.1 | slider | slider (range kept as the preset has it) |
  | crt-lottes-fast | CURVATURE, MASK_INTENSITY, SCAN_BLUR, SCANLINE_THINNESS | continuous | slider | slider |
  | crt-lottes | scaleInLinearGamma | 0..1 / 1 | slider | toggle (inferred) |
  | crt-lottes | shadowMask | 0..4 / 1 | slider | choice (sidecar) |
  | crt-lottes | hardPix, hardScan | -20..0 / 1 | slider | slider |
  | crt-lottes | bloomAmount, brightBoost, hardBloomPix/Scan, maskDark/Light, shape, warpX/Y | continuous | slider | slider |
  | crt-hyllian-fast | SHARPER | 0..1 / 1 | slider | toggle (inferred) |
  | crt-hyllian-fast | BRIGHTBOOST, InputGamma, MASK_INTENSITY, OutputGamma, SCANLINES | continuous | slider | slider |
  | fsr-pass1 | FSR_GRAINCOLOR | 0..1 / 1, "Gray \| RGB" | slider | toggle (inferred; the user, 2026-10-31) |
  | fsr-pass1 | FSR_FILMGRAIN, FSR_GRAINPDF, FSR_SHARPENING | continuous | slider | slider |

- **Steam keyboard:**
  - SDL3's X11 backend (`X11_ShowScreenKeyboard`) opens
    `steam://open/keyboard?XPosition=..&YPosition=..&Width=..&Height=..&Mode=..`
    through `SDL_OpenURL`, and closes it with `steam://close/keyboard`. This
    runs from `SDL_StartTextInput` when
    `SDL_HINT_ENABLE_STEAM_SCREEN_KEYBOARD` (`"SDL_ENABLE_STEAM_SCREEN_KEYBOARD"`
    in the SDL3 headers we build with) is set, which Steam is expected to
    set in Game Mode (gamescope runs games on XWayland). E.0 confirms that
    Steam sets it on the Deck.
  - `SteamDeck=1` is set in Desktop mode too (gamepad-input-ux, "Platform facts"), so it
    does not mean Game Mode. The Game Mode signal is `SteamGamepadUI=1`,
    or gamescope's own environment (`GAMESCOPE_WAYLAND_DISPLAY`, or
    `XDG_CURRENT_DESKTOP=gamescope`). Which of these Proton passes to a
    Windows exe is checked in E.0 before any code relies on it.
  - No source confirms that the same URL works when sent from a Windows exe
    under Proton. Steam+X always opens the keyboard by hand.
  - Steamworks `ShowGamepadTextInput` needs `SteamAPI_Init` with a real
    appid, but our games are non-Steam shortcuts.

## Goals / Non-Goals

**Goals:**
- One menu that works with a pad, keyboard or mouse, mixed freely, on
  Windows, macOS, Linux and the Deck in Game Mode.
- Typing that works everywhere.
- A layout that holds at every output size the overlay supports.
- Correct unsaved state, Save and Cancel everywhere, and hints that mods
  can supply.
- Import and export of the config and shader profiles.
- Glyphs for pad, key and mouse inputs.

**Non-Goals:**
- Replacing the row model with microui widgets.
- Localisation. Text stays English, though the hint tokens make it
  possible later.
- Touch gestures. A tap on the Deck screen arrives as a mouse click, which
  is enough.
- Steamworks.
- Theme editing.
- The CPU backend beyond keeping it building.

## Decisions

### D1. Three-part layout and size modes

- **Header** (one title-height row): "Enhancements · <game>" on the left.
  On the right: the hints toggle `?` (D11), compact/expanded (one button
  that flips), and close `x`. The header buttons are icons (D7) with a
  hover state.
- **Content:**
  - Left: the toolbar, one `[icon label]` entry per section, with a dot on
    sections that hold unsaved rows (D10).
  - Right: the section. A one-line intro (D11) comes first, then the rows
    scrolled as today, with the scrollbar.
  - Under the toolbar's minimum width (icon plus 8 em of label) the toolbar
    shows icons only, and the focused entry's label shows as a tooltip.
  - **The toolbar stays on the left and follows the focus** (the user,
    2026-11-01, Q10): it reads as a menu beside its submenu. While the
    focus is in CONTENT or FOOTER it shows icons only, and the section gets
    the width. When TOOLBAR has the focus (a hover, Tab, or the pad path
    in D3), it shows icons and labels, drawn over the section's left edge
    so the rows do not reflow. LB/RB from CONTENT show the labels for
    1.5 s, then the toolbar folds back. Where the panel is too narrow for
    labels even then, the label shows as a tooltip, as above.
- **Footer** (D9): hints | unsaved/status | Cancel Save.
- **Sections:**
  - Render, Shaders, Pack, Game, Mods (each mod's page opens inside it, as
    now), Controls, Stats, Debug, Files (D9 shrinks Save into it).
  - Sections are listed only when they have rows, as pages are today.
- **Size modes** (`overlay.menu_size = compact|expanded`, default
  `compact`, file-only, written when the button is pressed):
  - *Compact* is today's side panel, restated from `geom_of`: anchored
    left at `pad`, 40% of the placement width, at most 720 px times the
    scale, and as tall as the placement less `2 * pad`. The toolbar is
    icons-only whenever the label column would leave the content less than
    60% of the panel.
  - *Expanded* is centred and covers the game with the 85% backdrop, with a
    32 px margin. Its width is capped at `out_h * 16/9` so that on 21:9 and
    32:9 outputs it does not stretch rows across the screen. The toolbar
    shows labels.
  - Under 640 px wide or on portrait output (`h > w`), both modes fill the
    width less `2 * pad`, as `geom_of` does today, with an icon toolbar.
- **Why keep compact as the default:**
  - It matches the shipped panel, so nothing changes for a player who never
    presses the button.
  - Live settings stay visible behind it, which is the point of the live
    classes.

### D2. One layout module, shared by draw and hit-test

- `src/enhance/enhance_menu_layout.{c,h}` is pure C11: it does no drawing,
  holds no state and has no overlay includes.
  - Input: the placement size, ui scale, size mode, hints mode, the row
    heights of the section, the scroll offset, and the font metrics as
    numbers.
  - Output, `struct menu_layout`: the header rect and its button rects,
    toolbar entry rects, the content viewport, row rects (with clipping),
    the scrollbar track and thumb, the footer slots, the tooltip anchor, and
    for each row its value-control rects (pill, slider track, choice
    arrows).
- `menu_hit(const struct menu_layout *, x, y)` returns `{region, index,
  part}`.
- The draw code reads the same struct. A hit-test can never disagree with
  what is drawn, which was R9's main risk.
- Mouse coordinates are mapped from the window to the placement rect
  (`nv2a_overlay_placement`) once, in the input layer, so letterbox bars and
  HiDPI factors are handled in one place.
- **Scaling:**
  - Every size is a theme token times the effective scale. This change
    lands 3E's `overlay.ui_scale` (a multiplier 0.75..2.0, default 1.0) on
    top of the output factor: effective = clamp(clamp(out_h / 1080, 0.5,
    3.0) * ui_scale, 0.5, 3.0). The outer clamp keeps 4K at 2.0 from
    asking for 4.0, past what the atlas holds.
  - **`overlay.ui_scale` is restart-only.** The atlas is baked once, at
    `nv2a_overlay_arm`, at the scale of that moment, and drawing at
    another scale would sample glyphs at the wrong size. A live value
    needs 3E.1's atlas worker (a rebake off the present thread, published
    by generation), which is its own day of work and is not needed for
    any goal here. The key is read at start, the menu shows it as
    ENHANCE_RESTART, and 3E.1 can make it live later without a format
    change.
  - The render scale does not enter: the overlay draws at output
    resolution after the present chain.
  - The layout test pins rects at 640x480, 1280x720, 1280x800 (Deck),
    1920x1080, 2560x1080, 3440x1440, 3840x2160 and 800x1280 (portrait), and
    at ui_scale 0.75 and 2.0 (3840x2160 at 2.0 checks the 3.0 clamp).
  - An atlas-fit ctest bakes at the maximum effective scale, 3.0, with the
    text font, the Lucide subset and the input-glyph TTF and every size
    the menu packs, and checks the result fits 2048x2048.

### D3. Focus model with three devices

- **Focus:**
  - One selection per section, as today (`s_sel[page]`).
  - A *focus region* is one of HEADER, TOOLBAR, CONTENT or FOOTER, and
    defaults to CONTENT.
- **Pad:**
  - Unchanged in CONTENT. LB/RB change section and the toolbar highlight
    follows; Up/Down move; Left/Right change values; A is OK, B is back,
    X clears, Y saves.
  - View/Back is Cancel (D9). The pad never needs to enter the header;
    the size and hints toggles get pad bindings (L3 = hints, R3 = size).
  - **B goes up to the toolbar** (the user, 2026-11-01, Q12): a menu and
    its submenu. B at a section's top level moves the focus to TOOLBAR, on
    that section's entry, and the toolbar unfolds (D1). In TOOLBAR, Up and
    Down (or LB/RB) move between entries and show each section beside it;
    A or Right enters the highlighted section on its remembered row. B in
    TOOLBAR is the leave request (D9a). The menu opens with the focus in
    CONTENT, as today, so one B still reaches the toolbar first and a
    second leaves.
  - **Down reaches the footer** (the user, 2026-11-01, Q11). Down on the
    last selectable row moves the focus to FOOTER, on Save when anything
    is unsaved and on Cancel otherwise. Left/Right pick the button, A
    presses it, Up and B return to the row the focus came from. Up on the
    first row stays there. This replaces today's wrap (`move_sel`), so
    Down no longer jumps from the last row to the first.
  - **Shortcuts show on their action.** Y (Save), View (Cancel), L3
    (hints) and R3 (size) stay as shortcuts. Each button that a shortcut
    presses draws its glyph beside its label (GL.4), so "[Y] Save" and
    "[View] Cancel" sit on the footer buttons themselves, not only in the
    hint list.
  - **Shortcuts never overlap the section.** The global set is Y, View,
    L3, R3 and LB/RB. CONTENT and FOOTER use only A, B, X, the d-pad and
    the left stick. A row, a section or a mod page may not bind a global
    button; a captured-control row (MD) takes every button only while it
    captures. The action table states each button's owner, and a ctest
    checks the two sets are disjoint.
  - **View, L3 and R3 act on release, not on press** (the user,
    2026-10-31). A game's menu chord can use them: BLiNX 2's is
    `back+left_thumb@400` (View plus L3, held 400 ms). While any button of
    a game's menu chord is held with another of its members, the menu
    suppresses those buttons' menu actions, and a release that ends such a
    chord fires nothing. A lone View or L3 press and release still fires
    Cancel or the hints toggle. The ctest drives the BLiNX 2 chord and
    checks that neither Cancel nor the hints toggle fires.
- **Keyboard:**
  - Arrows, Enter, Esc, Q/E and Delete as today. Esc and Backspace are B
    (the user, 2026-11-01): at a section's top level they go to TOOLBAR,
    and in TOOLBAR they are the leave request (D9a).
  - Tab and Shift+Tab cycle TOOLBAR, CONTENT and FOOTER. In TOOLBAR, Up and
    Down change section.
  - F5 and Ctrl+S save (Cmd+S as well on macOS), Shift+Esc cancels. F1
    toggles hints.
  - While a text field has focus, the menu calls `enhance_actions_quiet(1)`
    (as `name_begin` does today) and the letter and digit shortcuts (Q/E,
    N/S/G and the like) are off; F-keys, Esc, Enter and Ctrl/Cmd+S still
    work.
- **Mouse:**
  - Hover highlights the row or button under the pointer.
  - On a content row, hover *moves the selection*, but only on real pointer
    motion: at least 2 px at ui scale since the last event. A pad or key
    press therefore never loses its selection to a still mouse.
  - Left-click on a row selects it, then activates the part under the
    pointer:
    - pill: flips it;
    - choice arrows: step it;
    - slider: jump, and drag to the value snapped to `step`;
    - the label: OK.
  - The wheel over a slider or a choice (its track, arrows or value)
    steps the value, one step a notch, through the same event as the
    pad's Left/Right, so it applies live as the pad does (the user,
    2026-11-01). Anywhere else it scrolls the viewport without moving the
    selection. Once the selection leaves the viewport, the next key, pad
    or pointer press re-anchors it to the first visible row and is spent
    there: it does not also move, step or activate.
  - Right-click is back. Clicks on the backdrop do nothing; they never
    close the menu, so a missed click is never destructive.
- **Latest device:**
  - `menu_device` is PAD, KEYBOARD or MOUSE, set by the last event that
    counts: a pad press or a stick past its deadzone, a key press, or mouse
    motion past the threshold, a click or the wheel.
  - It drives the footer hint set and glyph family (D8), and the cursor:
    the cursor is shown while MOUSE is latest and hidden on the first pad or
    key event, as R9 planned.
  - When the menu opens, the device is the one that opened it. If that is
    unknown, it is PAD when a pad is connected, else KEYBOARD. This is the
    user's "gamepad hints when a gamepad is detected".
- **Pointer source (new).** The relative model cannot place a cursor, so
  phase C adds a pointer snapshot in `src/input/pointer.{c,h}`:
  - `struct xbox_pointer { int x, y; unsigned buttons; int wheel; uint32_t
    seq; }`: window-space client pixels, the held buttons (left, right,
    middle), the wheel steps since the last take, and a counter that moves
    on every pointer event (the D3 motion threshold compares positions
    across it).
  - Writers: the Win32 window procs (`WM_MOUSEMOVE`, the button messages,
    `WM_MOUSEWHEEL`, client coordinates) in `fb_present.c` and
    `nv2a_pb_d3d11.c`, and the SDL loop (`SDL_EVENT_MOUSE_MOTION`,
    `_BUTTON_*`, `_WHEEL`, in window coordinates, scaled by the pixel
    density). Each writer stores under a seqlock; the menu reads one
    consistent snapshot per frame with `xbox_InputPointerTake`.
  - It is fed always (a few stores per message) and read only while the
    menu is open.
  - `nv2a_overlay_placement` maps it to placement pixels once, in the
    input layer (above).
  - Under `present.surface = internal` the window and the output differ
    (the user, 2026-11-01). Each presenter publishes the window-to-output
    view (scale and letterbox offset) next to the placement with
    `nv2a_overlay_set_view`: Metal the layer's aspect fit
    (`kCAGravityResizeAspect`), D3D11 the DXGI stretch of the back buffer
    over the client area. SDL ignores `internal`, so its view is the
    identity. `pointer_step` maps the pointer through
    `nv2a_overlay_to_output` before the placement, and the IME's rect
    goes back through `nv2a_overlay_to_window`.
- **Game mouse while the menu is open:**
  - 3F is absorbed whole. On open the menu records the capture and divert
    state, calls `xbox_InputMouseSuspend(1)` (the cursor is freed and shown
    by the CURSOR layer) and, if a mod's divert is on (the free camera in
    flight), turns it off with `xbox_InputMouseDivert(0)`. The menu wins
    while it is open: the game and the mod get no motion.
  - The divert's one owner today is `enhance_input_capture` (a mod's
    `input_capture`). While the menu holds the mouse, that function records
    the mod's state but does not touch the divert. On close the menu calls
    `xbox_InputMouseSuspend(0)` and then
    `xbox_InputMouseDivert(enhance_input_captured())`, so a capture the mod
    took or released meanwhile is honoured. The divert drops pending counts
    on each edge, so the camera does not jump.
  - F-9 and F-11 (cursor and clicks at guest flips on D3D11) stay as they
    are: the menu runs at the guest's frame rate. A cursor drawn at present
    time is a follow-up, not part of this change.

### D4. Text input

- **Toolkit API** (`src/input/text_input.h`):
  - `xbox_InputTextBegin(x, y, w, h)` and `xbox_InputTextEnd()`, called by
    the menu on the guest's thread;
  - `int xbox_InputTextPop(char *utf8, size_t n)` reads one codepoint.
- **Threads.** The menu runs on the guest's thread; the SDL loop and the
  Win32 window procs run on the window's thread. `SDL_StartTextInput`,
  `SDL_StopTextInput` and `SDL_SetTextInputArea` must run on the window's
  thread, so Begin and End only *request*:
  - They store the wanted state (on or off, the field rect, a generation
    number) atomically, as the mouse capture does.
  - The SDL loop applies it each pass in `xbox_InputSdlTextSync(win)`,
    beside `xbox_InputSdlMouseSync`: a changed generation calls Start or
    Stop and sets the area. The rect is mapped from placement pixels to
    window coordinates there.
  - Win32 needs no host call for the ring (WM_CHAR arrives anyway); the
    gate is the same atomic, read in the window proc.
- **The ring:** single producer (the window's thread), single consumer
  (the guest's thread), lock-free: 64 `uint32_t` codepoints, a head
  written only by the producer and a tail only by the consumer, both with
  acquire/release atomics. Input past 64 is dropped and counted (the trace
  logs the count). End empties it from the consumer side by moving the
  tail to the head; the producer stops writing when the gate closes.
- **Sources:**
  - Win32: `WM_CHAR`, with UTF-16 surrogates paired (a lone surrogate is
    dropped), in both game window procs (`fb_present.c` and
    `nv2a_pb_d3d11.c`), only while the gate is open. IME composition is
    left to the OS. The third proc, `vp_wndproc` in `video_pump.c`, owns
    the movie window, where the menu never opens; it gets no `WM_CHAR`
    hunk.
  - SDL3: `SDL_EVENT_TEXT_INPUT` in the loop, split into codepoints.
  - **Control characters are dropped** at the producer: every codepoint
    below 0x20, and 0x7F. That covers Tab (0x09), Enter (0x0D), Esc
    (0x1B), Backspace (0x08) and the Ctrl+letter codes (Ctrl+S gives
    0x13). Those keys reach the menu as edges.
  - Editing keys (Backspace, Delete, Left, Right, Home, End, Enter, Esc)
    stay VK or scancode edges, through the same path as today.
- The rename editor and every new text field read the ring. The US-layout
  VK mapping is removed, which fixes non-US layouts.
- **Game Mode:**
  - *Native Linux (SDL3):* nothing to add. SDL opens the Steam keyboard
    from `SDL_StartTextInput` when Steam sets the hint, and closes it on
    Stop. The field rect gets passed as the keyboard position.
  - *Proton (Win32):* spike S1 on the Deck, 0.5 day. Begin sends
    `steam://open/keyboard?...` with `ShellExecuteW`. Wine routes unknown
    URL schemes to winebrowser and then to xdg-open, so Steam may receive
    it. End sends `steam://close/keyboard`. S1 checks:
    1. whether the keyboard appears in Game Mode;
    2. whether its keys arrive as `WM_CHAR`;
    3. whether a non-Steam shortcut behaves like a Steam app.
  - The Proton path runs only when Wine is detected (`wine_get_version` in
    ntdll) and Game Mode is detected by the signal E.0 confirms (`SteamGamepadUI`
    or gamescope's environment, Context). `SteamDeck=1` alone
    is not enough: it is set in Desktop mode too, where a real keyboard or
    the Steam+X keyboard is the player's choice. It is gated by
    `overlay.steam_keyboard = auto|off`, default `auto`, file-only. If S1
    fails, `auto` means off under Proton, and the key stays for native
    Linux.
  - `ShellExecuteW` runs on the window's thread too, from the same
    request and sync as Begin and End.
  - *Always available:* the in-overlay keyboard (OSK). It is a pad-driven
    key grid docked under the field, with letters, digits, `-_ .`, space,
    backspace and done. It opens when a text field takes focus while PAD is
    the latest device, or when the mouse or a touch starts the edit and no
    key has been pressed this session (the user, 2026-11-01), and no
    Steam keyboard opened. It replaces the
    letter-cycle editor.
  - The OSK's footer hint names "Steam + X: system keyboard" when Steam is
    present.
- **Scripts:** the IME hand check covers Latin input only (dead keys and
  composed accents, e.g. "é", "ñ"). The atlas packs no CJK, so composed
  Japanese text would draw as boxes; CJK is a follow-up with localisation.
- **Why not Steamworks:** it needs `SteamAPI_Init`, a real appid and the
  redistributable DLL. Non-Steam shortcuts have none of these.

### D5. Shader parameter kinds

- **Order:** declared, then inferred toggle, then inferred choice, then
  slider. The first rule that matches wins.
  1. *Declared:* `assets/shaders/param-kinds.toml`, a toolkit sidecar keyed
     by the shader file and param name:
     `kind = "toggle" | "choice" | "slider"`, plus `choices = [...]` for a
     choice, and an optional `help = "..."`. It covers MASK and shadowMask.
     The choice names are read from each shader's own source comments when
     the sidecar is written; they are not invented. A user preset can carry
     the same table in its shader profile as `[param_kinds]`.
     - **Keying:** `struct nv2a_present_param` has no file today, so K adds
       `char file[64]` to it (the basename of the shader that declared the
       param, set where `nv2a_present_chain.c` parses `#pragma
       parameter`). A param shared by two stages keys on the first
       stage's file, as `stage` already does.
  2. *Inferred toggle:* `min == 0 && max == 1 && step == 1`. This takes
     TRINITRON_CURVE, SHARPER, scaleInLinearGamma and FSR_GRAINCOLOR. For
     FSR_GRAINCOLOR the user chose the toggle (2026-10-31): its label
     drops the ": Gray | RGB" choice text, so the row reads "FSR LFGA
     Film Grain Color" with the pill (on = RGB, the preset's 1.0), and the
     rule order
     above stays as it is: rule 2 runs before rule 3, so rule 3 never sees
     a 0..1 param.
  3. *Inferred choice:* min, max and step are integers, step is 1, the
     count is 3..8, and `desc` contains `|`-separated names whose count
     equals the count after the last `:`. No shipped param matches today;
     the rule is there for user presets.
  4. Everything else is a slider. A step of 0 still falls back to range/100.
- **Label clean-up:** when `desc` ends in `: name | name ...`, the label
  is `desc` up to that last `:`, trimmed, for a toggle and a choice alike,
  so the names never show in the label. A toggle with two names uses the
  second as its "on" word in the tooltip ("on: RGB").
- **Values stay numbers.** A toggle writes 0.0 or 1.0, and a choice writes
  min + index, so profile files and preset values are unchanged.
- **Mod settings are declared only.** XBOX_SET_BOOL is a toggle and
  XBOX_SET_ENUM is a choice. An XBOX_SET_INT 0..1 stays a slider, because
  the author chose INT. No inference runs on mods.
- **Help text:** a shader row's help is the sidecar's `help`, when it
  has one, then "range · preset value" as now. `desc` is the label
  (`param_list`), so using it again as help would only repeat the label.
- **Why a rule plus a sidecar:** the inference is exact for the four 0..1
  params and safe, since it never applies to a continuous range. Enum
  ranges cannot be inferred without names, and guessing them would label a
  value wrongly.

### D6. Import, export and the file browser

- **Decision (the user, 2026-10-31, Q2):**
  - The in-overlay browser is *the* picker.
  - The OS picker is low priority: a fallback used only where the browser
    really cannot work. It is built last, in optional phase I, and nothing
    else depends on it.
- **Where the browser really cannot work:**
  - **macOS protected folders.** Desktop, Documents, Downloads, iCloud
    Drive and removable or network volumes are guarded by TCC. A plain
    `opendir` there either raises a permission prompt or, once the player
    has said no, fails with `EPERM`. `NSOpenPanel` (behind
    `SDL_ShowOpenFileDialog`) grants access through the Powerbox with no
    prompt. The browser's own roots (exports, config, shader profiles,
    which live under Application Support) are never guarded.
  - **A sandboxed Linux package** (Flatpak, `FLATPAK_ID` set; native Linux
    is future work). Paths outside the sandbox are reachable only through
    the file chooser portal.
  - **Elsewhere, nowhere:**
    - On Windows the browser lists the drive letters and every folder the
      user can read.
    - Under Proton, `Z:` reaches the whole Unix tree.
    - In Game Mode a separate dialog is the worse choice anyway.
- **How the fallback is offered:**
  - When a listing fails with `EPERM`/`EACCES` on macOS, or the build runs
    sandboxed, the browser shows one row, "Choose with the system
    picker…".
  - `overlay.file_dialog = overlay|native` (default `overlay`, file-only)
    lets a desktop player always use the system picker.
  - Without phase I, the row is absent and the browser says the folder
    cannot be read.

  | | In-overlay browser | OS picker |
  |---|---|---|
  | Pad | full | poor (Win32 and portal dialogs are mouse and keyboard) |
  | Borderless fullscreen | draws in the game window | Win32 dialog can open behind the topmost window; macOS opens a sheet |
  | Proton | Wine paths through `Z:` | Wine's built-in dialog: works, looks foreign |
  | Game Mode | works | a portal or Wine dialog in another window may not get focus under gamescope |
  | Cost | ~1.5 days, all ctest-able | ~0.5 day per host, not ctest-able |

- **Browser model** (`src/enhance/file_browser.{c,h}`, pure apart from one
  directory-listing callback):
  - Roots:
    - *Exports* (`<user config dir>/exports/<game>/`, created on demand);
    - *Config* (the user config dir);
    - *Shader profiles*;
    - *Home*. On the Deck under Proton this is the Unix home through `Z:`:
      the Unix `HOME` (Wine passes the host environment through) is turned
      into a DOS path with `wine_get_dos_file_name` (kernel32, looked up
      with `GetProcAddress`, so a plain Windows build never needs it). On
      Windows it is `%USERPROFILE%`.
    - *Drives* on Windows (`GetLogicalDrives`). It is hidden under Wine,
      where `Z:` is the Unix root `/` and Home already reaches the
      player's files; the Unix root stays reachable with `..` from Home
      up to `Z:\`.
  - Folders are listed before files, sorted case-insensitively, with only
    the extensions asked for (`.toml`, plus the save-state extension for
    3G). `..` stops at the root.
  - Text input (D4) names new files. The default is
    `<kind>-<yyyymmdd-hhmm>.toml`.
- **Safety** (all in the pure model, so the ctest covers it):
  - *Names typed by the player* are sanitised before any path is built:
    `/`, `\`, `:` and control characters are refused; `.` and `..` are
    refused; a trailing dot or space is trimmed (Windows drops them); the
    Windows reserved names `CON`, `PRN`, `AUX`, `NUL`, `COM1`..`COM9` and
    `LPT1`..`LPT9` are refused with or without an extension, on every host
    (a file exported on the Mac may be imported on Windows); the name is
    at most 64 bytes of UTF-8 before the extension. A refused name keeps
    the field open with the reason.
  - *Symlinks:* listed with a marker. A link to a folder is followed only
    when its target stays under the same root (checked with `realpath` /
    `GetFinalPathNameByHandleW`); otherwise it shows but cannot be opened.
    `..` stops at the root after the resolution, so a link never climbs
    out of a root.
  - *Import size cap:* a file over 256 KB is refused before it is read
    (a user config is a few KB; a shader profile less).
  - *Export overwrite:* exporting onto an existing file opens a confirm
    ("Replace <name>?", focus on No). Default names carry the minute, so
    a repeat export a minute later never prompts.
  - *Atomic writes:* every export and every imported shader profile is
    written to `<name>.tmp` in the same folder, flushed, then renamed over
    the target (`rename` on POSIX, `MoveFileExW(...,
    MOVEFILE_REPLACE_EXISTING)` on Windows), so a crash leaves the old
    file or the new one, never half of one.
  - *Windows paths:* every path the browser opens, lists or writes is
    UTF-8 inside and UTF-16 at the call (`_wfopen`, `FindFirstFileW`,
    `MoveFileExW`), so non-ASCII user names and folders work.
- **Export:**
  - *Config:* the user config file as Save would write it now, including
    unsaved values (the footer says so).
  - *Shader profile:* the active profile's TOML.
  - The status line names the path. On the desktop, Files gets an "Open
    exports folder" row (`ShellExecuteW` or `SDL_OpenURL file://`); it is
    hidden in Game Mode.
- **Import:**
  - The file is parsed with the config parser and the version checked.
    Unknown keys are listed in the status and the log.
  - Keys with no menu slot (hand-written keys, keys from another build,
    a mod that is not loaded) are kept: they are merged into the pending
    config and written on Save as they were, never dropped. The preview
    counts them apart ("4 changes, 2 kept as written").
  - `menu.enabled = false` in an imported file is not applied to the
    running menu. It is written on Save (the player asked for it) and
    takes effect at the next start, and the preview says so: "menu.enabled
    = false: the menu will be off from the next start". The import never
    closes the menu under the player's hands.
  - A preview row shows "N changes". OK applies them *as unsaved changes*,
    so "Exit without saving" (D9) undoes an import and Save keeps it.
  - A shader profile is copied into `shader-profiles/` under a unique slug,
    and nothing is overwritten. Env-forced keys are skipped and named.
- **3G save-state export** (save-states D9) reuses the browser.
- **As built (phase G, toolkit `feat/ovl-files`):**
  - *The version check* is a marker comment on an export's first lines,
    `# xbr-export: config 1`, because a config has no version key. A
    second line names the unsaved keys an export included. An import
    refuses a marker with a higher format, or one that names another kind
    (a slot, later). A file with no marker is read as format 1, since it
    is a hand-written config.
  - *One Import row* tells a config from a shader profile by its
    top-level `stages` array. It replaces separate config and profile
    rows. The profile is checked with `shader_profile_parse` (a newer or
    broken one is refused). It is named by its own name's slug, as Save
    as new names files, then written with `fb_import_unique`, which uses
    an exclusive create and so needs no temp file.
  - *Export shader profile* writes the active profile's file as last
    saved. It is available only for a saved user profile. A profile with
    unsaved edits exports its saved file, and the row says so. A bundled
    preset or a path is a config key and goes out with Export settings.
  - *Exports* live in `<user config dir>/exports/`, with no `<game>`
    subfolder. The user config dir is already per game, so
    `fb_add_default_roots` gets `game` NULL.
  - *Game Mode* is `RECOMP_HOST_GAMESCOPE=1`, the launcher's signal that
    `present.surface=auto` already reads. It is not a new key.
  - *Kept keys* take effect at the next start, like `menu.enabled`. At
    most 64 are held per session. An import over that is refused whole.
    So is one whose kept keys would not patch into the user file (a kept
    `a.b` over a scalar `a`). A kept key equal to the user file's value
    is not counted.
  - *Imported bindings* (`input.actions.<name>` for a registered action)
    are changes, each binding checked by `enhance_action_check`. An
    unbound `menu.open` is refused, as Clear refuses it.
  - *Open exports folder:* `ShellExecuteW` runs on the menu's thread on
    Windows. Elsewhere the menu posts the path to a one-slot request that
    the SDL window thread takes each frame (`xbox_HostOpenSdlSync`),
    because SDL wants `SDL_OpenURL` on its own thread.

### D7. Section and header icons

- **Source:** a Lucide subset (ISC licence, shipped with the toolkit):
  - sections: sliders, sparkles (shaders), package, gamepad-2, puzzle,
    activity, keyboard, bug, folder;
  - header: help-circle, maximize-2, minimize-2, x;
  - rows: check, chevron-left/right, refresh-ccw, upload, download.
- **Packing:** the subset is kept as a TTF in the private-use area,
  `third_party/lucide/lucide-subset.ttf`, a few KB, generated with
  `pyftsubset`. The command and the Lucide version go in its VERSION file.
  Lucide's LICENSE ships whole, as the release has it: the ISC notice and
  the MIT notice for the icons that came from Feather.
  The font atlas packs it as a second font in `try_pack`, at the same
  sizes as the text, so icons scale with `ui_scale`.
- **Drawing:** a new `OVL_CMD_GLYPH` custom command, or MU_COMMAND_ICON
  extended to look up a codepoint, emits atlas quads. The converter is the
  only place that changes, so the backends agree.
- **Why a TTF:**
  - The font path, the scaling and the atlas exist already.
  - An SVG renderer would be a new dependency.
  - A PNG atlas would blur or cost one bake per size.

### D8. Input glyphs for pads, keys and mice

- **Source:** Kenney "Input Prompts" (CC0 1.0), which has monochrome vector
  sets for Xbox Series, PlayStation 5, Nintendo Switch, Steam Deck,
  generic, keyboard and mouse.
  - CC0 needs no attribution, but the toolkit still ships its licence and
    names the pack version.
  - Platform logo glyphs are left out. The guide button is drawn as a
    generic "home" glyph on every family, and no brand mark appears.
  - The PlayStation face shapes (cross, circle, square, triangle) are
    geometric symbols, used as every input prompt pack uses them.
  - Nothing comes from any game.
- **Subset**, about 30 glyphs per family:
  - face buttons, d-pad (4 directions and whole), sticks (L, R, click and
    directions), bumpers, triggers, start/menu, select/view, home;
  - Deck back grips L4, R4, L5 and R5;
  - PlayStation touchpad, Switch minus/plus/capture.
  - Generic gets a lettered fallback set.
  - Mouse: left, right, middle, wheel up/down, move.
  - That is about 170 glyphs in all.
- **Packing:**
  - At commit time, `tools/overlay/glyphs_to_ttf.py` converts the chosen
    SVGs into one PUA font, `third_party/kenney-input/xbr-input.ttf` (est.
    60-120 KB). It is deterministic, and the source list and the output
    TTF are both committed. The game build needs no Python.
  - The script is not stdlib-only: it needs fonttools (TTF writing) and
    picosvg (SVG path flattening). The toolkit has no `pyproject.toml`, so
    the script declares them as PEP 723 inline metadata and runs as `uv
    run tools/overlay/glyphs_to_ttf.py`; its docstring says so. Nothing at
    build or run time imports them. `pyftsubset` for the Lucide subset is
    fonttools too.
  - `tools/overlay` joins the toolkit's pytest gate. Its reproduce test
    (the script rebuilds the committed TTFs byte for byte) runs as `uv run
    --with fonttools --with picosvg pytest tools/overlay` and skips with a
    reason under a plain `pytest` without them; a stdlib-only test checks
    that `glyphs.txt` and the VERSION files agree with the script's list.
  - The font is baked into the same atlas as the text and the section
    icons. Only the sizes the menu uses are packed (small and body, plus 2x
    body for the rebinding prompt).
  - A ctest pins the atlas within 2048x2048 at the maximum effective
    scale, 3.0 (D2), with all three fonts and every size packed.
- **Keyboard keys:** drawn procedurally, not from the pack: a rounded-rect
  key cap (RRECT) with the key's name in the layout in use
  (`GetKeyNameTextW` on Win32, `SDL_GetKeyName` on SDL3). Any key and any
  layout are covered, and "Z" on an AZERTY board shows the key the player
  presses. Kenney's keyboard set is not shipped.
- **Family selection** follows gamepad-input-ux D5, which already ships
  it (I2.6):
  - `xbox_InputPadFamily` (`input_core.c`) uses the SDL3 table in
    `src/input/xinput_device.c` (`SDL_GetGamepadType`: Xbox 360/One,
    PS3/4/5, Switch Pro, Joy-Cons and GameCube; STEAM or 28de:1205 gives
    the Deck).
  - On Win32/XInput, native or under Proton, every pad reads as Xbox, and
    `auto` stays Xbox. `RENV_STEAM_DECK` does not switch it: Steam Input's
    virtual pad is an Xbox pad, and gamepad-input-ux D5 leaves the choice
    to the player through `input.glyphs = "steam"`.
  - Unknown pads get GENERIC. GL adds `generic` to the `input.glyphs`
    values (`enhance_input.c`), so the override covers every family.
  - The menu uses the family of the pad that sent the latest event.
  - This change carries out gamepad-input-ux I4 (the glyph strip); GL
    marks I4 there as absorbed by overlay-revamp.
- **Positional mapping:** glyphs are chosen by input source
  (`INPUT_SRC_SOUTH`, ...), which is positional. On the Switch family the
  SOUTH glyph is "B", so a prompt shows the physical button.
- **API** (`src/kernel/nv2a_overlay_glyph.h`):
  - `int nv2a_ovl_glyph_src(int family, enum input_src src)`,
    `nv2a_ovl_glyph_mouse(int button)`, and `nv2a_ovl_glyph_key(int vk)`
    (a key cap).
  - `nv2a_ovl_ui_glyph(ctx, glyph, rect, color)` draws one.
  - **Tokens in any menu text:** help, labels, notes, toasts and the footer
    expand `{pad:south}`, `{pad:lb}`, `{key:F5}`, `{mouse:left}` and
    `{act:<action>}`. The last is the action's current binding on the
    latest device, so hints follow rebinding.
    - Tokens are expanded by `enhance_text_draw`, which lays out text and
      glyphs on one baseline.
    - An unknown token draws as plain text.
    - Mods get glyphs by writing tokens in their `help`, `label` and
      toast strings. A mod's strings may also write `{ctl:<control>}`,
      one of its own captured controls (mod-settings D), which draws that
      control's binding on the latest device.
    - Outside menu text, mods use the version 7 API of D12a (Q5, the
      user, 2026-10-31): `glyph_name` and an on-screen status panel.
  - The Controls page, the free camera page (D12) and capture prompts draw
    bindings as glyphs, falling back to the text name when no glyph exists.

### D9. Footer, Cancel and Save, the Files section

- **Footer, left to right:**
  1. **Hints** for the latest device, as glyph and verb pairs:
     - pad: `{pad:south} Select · {pad:east} Back · {pad:lb}{pad:rb}
       Section · {pad:north} Save`;
     - keyboard: `Enter Select · Esc Back · Q E Section · F5 Save`;
     - mouse: `Click Select · Right-click Back · Wheel Scroll`.
     - The OSK and the rename field have their own sets. When space is
       short, pairs are dropped from the right.
  2. **Summary:** "3 unsaved" in the accent colour, or "All saved". A fresh
     status ("Saved to ...", "Import: 4 changes") replaces it for
     STATUS_MS.
  3. **Cancel** and **Save** buttons, mouse-clickable, with the pad glyph
     (`{pad:view}`, `{pad:north}`) or key (Shift+Esc / F5) drawn on them.
     Save is dimmed when nothing is unsaved or `RECOMP_CONFIG=none`.
- The selected row's help leaves the footer for the hints (D11), and the
  live tag moves into the tooltip.
- **Save** writes as today (`save()`), from any section, and keeps the menu
  open.
- **Cancel**, and every other way of leaving the menu, goes through the
  unsaved-changes dialog (D9a).
- **Revert** is new: `enhance_menu_revert()`. Only slots can be reverted
  today (`cur` and `base`); the other three sources need a saved copy
  first (Context, Findings), so phase A adds them:
  - *Slots:* each saveable slot's `cur` is set to `base` and `set()` is
    called, so live items change back now and RESTART items record the old
    value.
  - *Bindings:* a base snapshot, `s_abase[id]`, holds each action's
    bindings as last loaded or saved (taken where `s_adirty` is cleared
    today: load, Save and reload). Dirty becomes a comparison by value,
    `!same_binds(cur, s_abase[id])`, in place of the set-only flag, so
    rebinding back to the saved keys clears it. Revert calls
    `enhance_action_set_bindings` with the base for every action that
    differs.
  - *Present chain overrides:* `nv2a_present_chain_override_revert()` (new,
    `nv2a_present_chain.c`) puts every preset-scope override back to the
    value loaded or saved last, and removes the ones added since; the
    chain's params are re-applied, so the image changes back now.
  - *Shader edit state:* `shader_edit_revert()` (new,
    `shader_profile_edit.c`) puts the chosen entry, its chain, name and
    values back to what the files and the config hold, through the same
    path as a reload of the list.
  - *Profile delete stays immediate.* `shader_edit_delete` removes the
    file at once, and making it a pending operation would need a staged
    file and an undo across restarts for one rare action. Instead the
    delete row has its own confirm today, and D9a's body says, when the
    session deleted a profile, "Deleted profiles are gone already; this
    does not bring them back." Revert never claims to undo a delete.

### D9a. The unsaved-changes dialog (the user, 2026-10-31, Q7)

- **When it opens:** a request to leave the menu while
  `enhance_menu_unsaved() > 0`. That request is any of:
  - B, Esc or Backspace on the toolbar (Q12; Esc and Backspace act as B,
    the user, 2026-11-01). Any of them at a section's top level goes to
    the toolbar instead, and inside a mod page or a capture B still goes
    back one level;
  - the footer's Cancel button, pad View or Shift+Esc;
  - the header's close `x`;
  - the menu's own toggle (F10, guide+A, paddle1).
  With nothing unsaved, each of these closes at once, as today.
- **Content:**
  - Title: "Unsaved changes". Body: "3 settings changed since the last
    save." with up to three of the changed labels, then "…". When a shader
    profile was deleted in this session, a last line says the delete is
    not undone (D9).
  - Three buttons in this order: **Exit without saving**, **Exit and
    Save**, **Go Back**.
- **Actions:**
  - *Exit without saving:* `enhance_menu_revert()`, then close.
  - *Exit and Save:* `save()`. On success, close. On failure, or when
    `RECOMP_CONFIG=none`, the button is dimmed and inert, and a failed save
    keeps the dialog open with the error in its body and focus on Go Back.
  - *Go Back:* closes the dialog and leaves the menu as it was: same
    section, selection and scroll.
- **Focus:**
  - It is a modal layer drawn over the panel (the panel is dimmed), and it
    takes every input while open.
  - **Go Back has focus when the dialog opens**, so a repeated B, Esc or A
    can never lose or write anything by accident.
  - The dialog ignores input for 150 ms after it opens (the menu's first
    repeat delay), so the held key that opened it does not act on it.
- **Pad:**
  - Left/Right and Up/Down move focus between the buttons, without
    wrapping. A activates the focused button.
  - B is Go Back, from any focus.
  - View, the toggle and guide+A are Go Back too: pressing "leave" again
    never picks for the player.
  - The buttons carry no pad shortcuts beyond A and B. Y does not mean
    "Exit and Save" here, so that a reflex Y in the footer never closes the
    menu.
- **Keyboard:**
  - Left/Right, Tab and Shift+Tab move focus. Enter or Space activates.
  - Esc is Go Back.
  - Underlined access keys: **N** (Exit without saving), **S** (Exit and
    Save), **G** (Go Back).
- **Mouse:**
  - Hover highlights a button and moves focus only on real motion (the D3
    threshold). A click activates.
  - Clicks outside the dialog do nothing. Right-click is Go Back.
- **Glyphs:** each button shows its prompt for the latest device:
  `{pad:south}` on the focused button and `{pad:east}` on Go Back, or the
  key or access letter.
- **Behaviour change:** B or Esc at the top level used to close and keep
  unsaved changes pending for the session. Now it asks. The menu never
  closes with silent pending changes, so "unsaved" always means "you are
  looking at it".
- **Not from the game side:** a host quit (window close, Alt+F4) does not
  open the dialog. Unsaved values are lost, as today: the dialog belongs to
  the menu, not the process.
- **Tested** in `tests/enhance_menu`:
  - every trigger, with and without unsaved changes;
  - initial focus on Go Back;
  - the 150 ms swallow window;
  - B/Esc/View as Go Back;
  - access keys;
  - a failed save keeping the dialog open;
  - revert leaving `unsaved == 0`;
  - Go Back keeping section, selection and scroll.
- **Files** replaces Save:
  - an info row with the config path;
  - Import config…, Export config…, Import shader profile…, Export shader
    profile… (D6);
  - Open exports folder (desktop only);
  - Reset to defaults, with the confirm it has today.
  - The Save row and the "Unsaved changes" info row are dropped, because
    the footer holds both.
- **Why drop the Save row:** two Save paths that do the same thing invite
  "which one counts?". The footer button is reachable from every section,
  and Y and F5 already save anywhere.

### D10. Row markers: unsaved vs default (the badge bug)

- **The rule:**
  - **Unsaved:** a filled accent dot *before* the label, and a dot on the
    section's toolbar entry. A row is unsaved when:
    - it is a saveable slot with `cur != base`;
    - or it is a shader param whose override is dirty;
    - or it is a binding with `s_adirty`;
    - or it is a profile row with `shader_edit_dirty`.
  - **Not default:** the value is drawn in `text` rather than `text_dim`
    when it differs from the stock value. Stock is `slot_stock()`: the
    game's defaults file (`config.default.toml`) when it has the key, else
    the mod's stock or the item's `def`. The comparison is by value, not
    `strcmp`: numbers compare as numbers (a RANGE within half a `step`, an
    INT or numeric CHOICE exactly), so "1", "1.0" and "1.00" are one value;
    toggles compare as booleans; text choices compare as strings. The same
    comparison serves unsaved (`cur` against `base`). The clear action (X / Delete / the row's reset icon
    on hover) says "Reset to default (<def>)". It is quiet on purpose: most
    players change a few things and should not see a page of marks.
  - **Live class:** no mark for LIVE and FLUSH, the common "applies now"
    case. "applies at restart" (warn) and "next stage" / "next activation"
    (dim) stay as words, and the tooltip says "Applies now".
- **Introspection** for the ctest: `int enhance_menu_row_state(int i)`
  returns bit flags `ROW_UNSAVED | ROW_NONDEFAULT | ROW_FORCED`.
- **ctest** (`tests/enhance_menu`):
  1. A fresh item at its default is neither unsaved nor non-default.
  2. Setting it makes it unsaved and non-default.
  3. Save leaves it non-default only.
  4. Setting it back to the saved value clears unsaved.
  5. Clear makes it unsaved and default.
  6. Revert restores 3.
  7. An env-forced row is FORCED and never unsaved.

### D11. Hints

- **Text sources:**
  - `struct enhance_item` gains `const char *help` (appended; NULL means no
    help) for the built-in items and the game items in cat.
  - Mod settings and controls already have `help`.
  - Shader params use the sidecar's `help` (D5) when it has one, plus
    "range · preset value" as now. `desc` is already the row's label, so
    it is not repeated as help.
  - Section intros live in a toolkit table for the built-in sections.
    A mod's page uses its descriptor `summary`. Game items in cat can set a
    page intro with `enhance_menu_page_intro("Game", "...")`.
  - Help may use glyph tokens (D8).
- **Options assessed:**
  - **(a) Inline hints, toggled from the header.** Help draws as a second,
    dimmed, wrapped line under each row.
    - Good: it can be scanned, and it suits first use and the expanded
      mode.
    - Bad: it doubles the row height, so about half the rows fit, which
      hurts pad scrolling in compact mode.
  - **(b) Tooltip on focus.** A small card is anchored under the focused
    row (above when there is no room, inside the content viewport). It
    appears 350 ms after the pad or keyboard selection settles, or after
    500 ms of mouse hover, and hides on move.
    - Good: it costs no layout, and it works with pad focus and hover alike.
    - Bad: it covers the next row briefly, and it hides help until you
      stop.
- **Recommendation: both, with (b) as the default.**
  - `overlay.menu_hints = tooltip|inline|off` (default `tooltip`,
    file-only).
  - The header `?` button, L3 (on release, D3) and F1 flip between
    tooltip and inline, and the mode is written at once.
  - Writing `overlay.menu_size` or `overlay.menu_hints` touches only that
    one key in the user config: it does not run Save, does not write any
    other pending value, and is skipped (the mode lasts the session) under
    `RECOMP_CONFIG=none`.
  - The section intro line shows in every mode except `off`, which is the
    user's "short hint under each section".
  - In inline mode tooltips are off, since the text is already on screen.
- **Why:** the tooltip keeps compact mode dense for pad players, and inline
  serves a player reading the menu for the first time in expanded mode.
  Neither alone covers both.

### D12. Free camera page

- **mod-settings C and D run inside this change** (the user, 2026-10-31,
  Q4).
  - C (the free camera descriptor) and D (captured controls and fly
    rebinding) are carried out as this change's phases MC and MD. They
    follow the task lists and decisions of the mod-settings spec, which stays
    the source for their design, and their checkboxes are ticked there.
  - MC is cat-only and starts in the first wave. MD follows MC, as that
    spec orders.
  - The page work here (phase F) follows MD and the mouse phase C.
- **On top of C and D:**
  - **Toggles:** invert X and invert Y (XBOX_SET_BOOL), drawn as pills.
  - **Speeds:** fast and slow multipliers and mouse sensitivity as sliders
    with units.
  - **Rebinding:** rows for the actions (toggle, freeze, reset, speed
    cycle) and the captured fly controls (move stick, look stick, up and
    down, boost), drawn as glyphs (D8). Capture works on the pad, keyboard
    and mouse, conflicts are named in the status, and a "Reset camera
    controls" row is added.
  - The page intro and each row's help explain flying with tokens:
    "`{act:camera.toggle}` to fly, `{pad:ls}` move".
  - The freeze and reset defaults follow the save-states spec (End and
    Home) if it has merged by then. Otherwise they keep F7 and F5.
- **As built in phase F, where it differs from the above:**
  - **Glyph rows through a token.** The binding rows draw a glyph form of
    their value built from a new `{bind:}` token (one config binding: a
    pad chord as pad glyphs, anything else as key caps, `mouse1` .. `5` as
    the click). The Controls page shares the row code, so its rows draw
    glyphs too. The plain text stays the row's value; the glyph form falls
    back to it when it does not fit.
  - **Mouse capture binds fly buttons only.** A left, right or middle
    click binds a BUTTON control as `mouse1` .. `mouse3`, held like a key
    (a new `ENHANCE_CTL_MOUSE` source; the wheel steps, so it is refused).
    Actions keep refusing mouse inputs (the action table's rule), and a
    click on a stick row is refused with the reason. The click that was
    down as capture started never binds.
  - **The reset row is named after the mod:** "Reset free camera
    controls". It puts back every control's stock binding, actions and
    fly controls, and leaves the settings alone.
  - **The page intro is the descriptor summary,** the About row, with
    tokens: "`{ctl:toggle}` to fly, `{ctl:move}` move ...". The section
    intro above the rows stays the Mods page's.
  - **Token choice.** Settings and the summary use `{ctl:}`, which reads
    against the mod only on its own page. Action help is also shown on the
    Controls page, so it names other actions with `{act:camera.free.*}`.
  - **Units:** the five sliders read `×` (was `x`).
  - **F.3 waits:** the freeze and reset defaults were already End and
    Home; nothing changes until the save-states merge.

### D12a. Mod glyph API and status panel (Q5, the user, 2026-10-31)

The user chose an API over tokens alone, with the free camera as its test
bed: while flying, the mod shows that the free camera is on and which
controls do what.

- **`xbox_mod_api` version 7** (appended after version 6, so a v6 mod
  still loads; a v7 mod checks `size` before using these):
  - `int (*glyph_name)(const struct xbox_mod *m, const char *ref,
    char *out, size_t cap, uint32_t flags)`:
    - `ref` is a source (`pad:south`, `key:F5`, `mouse:left`), an action
      (`act:camera.free.toggle`), or one of the calling mod's controls
      (`ctl:move`).
    - It writes the binding on the latest device. With
      `XBOX_GLYPH_TOKENS` the output is tokens (`{pad:ls}`), which draw
      as glyphs in any text the overlay draws. With `XBOX_GLYPH_TEXT` it
      is plain names ("Left stick", "F5"), for log lines.
    - A chord joins its members with `+`. It returns the length written,
      or -1 when `ref` is unbound or unknown (then `out` holds `ref`'s
      own text).
    - Any thread; it reads the binding tables under their existing lock.
  - `int (*status)(const struct xbox_mod *m, const char *text)`:
    - Sets this mod's status panel. NULL or "" clears it.
    - The text is up to 6 lines (`\n`), 120 bytes each. The first line
      is the panel's title. Tokens are kept as written and expanded at
      every draw, so the panel follows the device in use and rebinding
      without the mod calling again.
    - Any thread. The text is copied under a lock. Returns 0, or -1 when
      the text was cut to fit.
- **The panel:**
  - It is a compact card at the top left, inside the title-safe area,
    with the menu's theme tokens at the effective UI scale (D2). The title
    line has the accent dot; the rest are hint lines as in the footer
    (glyph, verb).
  - One panel per mod. Several panels stack downwards in mod load order.
  - It is hidden while the menu is open (the menu shows the mod's page
    instead) and is dropped when the mod is disabled or fails.
  - It goes through the overlay's one command list (D13), so D3D11, Metal
    and the CPU reference draw it alike.
- **The free camera uses it:**
  - When flying turns on, the panel shows the title "Free camera" and
    reminder lines built from tokens over the mod's actions (`camera.free`
    `toggle`, `hud`, `freeze`, `reset`) and captured controls:
    `{act:camera.free.toggle} Exit · {act:camera.free.hud} HUD`,
    `{ctl:move} Move · {ctl:look} Look`, `{ctl:rise} {ctl:sink} Up/down`,
    `{ctl:fast} Fast · {ctl:slow} Slow`, `{act:camera.free.freeze} Freeze
    · {act:camera.free.reset} Reset`.
  - Two settings on its page (mod descriptor, saved like MC's): **Show
    indicator** (bool, default on) and **Controls reminder** (Brief,
    Always, Never; default Brief). Brief shows the reminder lines for 10
    seconds after flying starts, then the panel shrinks to its title line.
  - Turning flight off clears the panel.
- **Stock:** no mod sets a panel unless the user flies, and the free camera
  is off by default, so goldens draw none (D14). A v6 mod sees no change.

### D13. Backend parity

- Everything the menu draws reaches D3D11 and Metal as one triangle list,
  from the converter. New draw kinds (glyphs, key caps, tooltip cards) are
  converter work only, so no presenter changes.
- Per-host code is limited to input:
  - `WM_CHAR` and the pointer messages in both Win32 game window procs;
  - SDL text and mouse events, and the text-input sync on the main
    thread;
  - `ShellExecuteW` and `SDL_OpenURL`;
  - native pickers.
  - Each Win32 change goes in both the GDI and D3D11 procs, and each SDL
    change serves Metal and future Vulkan.
- The CPU reference rasteriser draws the same list, so overlay ctests can
  check pixels for glyphs and cards. The CPU backend only has to keep
  building.

### D14. What stays stock

- The menu ships ON (`menu.enabled = true` in `config.default.toml`, false
  in code).
- Goldens draw no menu. The CLI's golden tool does not set anything for
  this: it checks the run's log for `menu.enabled=off` and fails a run that
  has the menu on (`golden.py`, the stock-state table). The pin lives in
  each game's `golden.json` `env`:
  - BLiNX 2 (`cat/analysis/golden/golden.json`) and JSRF pin
    `RECOMP_MENU=0` and `RECOMP_CONFIG=none`, and cat's
    `scripts/test_config_default.py` checks both and that no scenario
    unpins them.
  - SSX 3 pins only `RECOMP_CONFIG=none`. That is enough today, since the
    code default is off and `none` skips `config.default.toml`, but it
    relies on one pin; H.3 adds `RECOMP_MENU=0` there too.
  - BLiNX 1, Burnout 3 and KUF have no `golden.json` yet; their first one
    gets both pins.
  So no menu, cursor, suspend or text input runs in a golden.
- With the menu closed nothing changes: no text input, the game's mouse
  untouched, no new per-frame cost beyond today's closed-menu check.
- New config keys default to today's behaviour: compact, tooltip hints
  (new, but shown only while the menu is open), the overlay browser, and
  the Steam keyboard on `auto` (only in Game Mode, only while a text field
  has focus).

### D15. Config and env keys

All config keys are file-only (`[overlay]` in the user config). The menu
writes them itself, and each gets a row in cat's `docs/env.md` config
table and in the toolkit's `docs/runtime/config.md` `[overlay]` section:

| Key | Values | Default |
|---|---|---|
| `overlay.menu_size` | compact, expanded | compact |
| `overlay.menu_hints` | tooltip, inline, off | tooltip |
| `overlay.file_dialog` | overlay, native | overlay |
| `overlay.steam_keyboard` | auto, off | auto |
| `overlay.ui_scale` (3E) | 0.75..2.0, restart-only (D2) | 1.0 |

One trace token: `RECOMP_TRACE=menu_input`.
- It logs device switches, focus regions, hits, chord suppression and
  text-ring traffic (including dropped codepoints).
- It is a TRACE-tier X-macro row in `recomp_env.h` (`X(MENU_INPUT_TRACE,
  TRACE, "menu_input", NULL, ...)`), like `hud` and `aspect`, with no
  legacy env name, read through `recomp_env`, plus a `docs/env.md` row and
  a line in `docs/runtime/config.md`.
- It is not a game key, so it needs nothing in `recomp_env_game.h`.

### D16. Tests

Standalone ctests in the toolkit, with no window and no GPU:

| Test | Covers |
|---|---|
| `tests/enhance_menu_layout` | D1 and D2 rects at the sizes in D2. The toolbar collapses below its minimum. The expanded cap holds on 21:9. Each row centre hit-tests to its row and part. Clipped rows are not hittable. |
| `tests/enhance_menu` (extended) | D3 focus with synthetic events: a still mouse does not steal the selection; hover moves it; a pad press hides the cursor; latest-device hint sets. D9a dialog (triggers, Go Back focus, swallow window, access keys, failed save), revert and Save from any page. D10 marker states, by-value compare against `slot_stock()`. D11 tooltip timing on a fake clock. Esc and Backspace as B; the wheel stepping a slider or choice and scrolling elsewhere; the OSK for a mouse-started rename; the pointer mapped through a published view. View and L3 fire on release; BLiNX 2's `back+left_thumb@400` chord fires neither Cancel nor the hints toggle. The menu's hold and release of a mod's mouse divert. |
| `tests/input_text` | UTF-8 and UTF-16 surrogate pairing (a lone surrogate dropped), control characters dropped (Tab, 0x13), ring overflow and its count, Begin/End gating, a producer thread against a consumer thread, the request generation seen by a fake sync. |
| `tests/shader_param_kinds` | D5 rule over the inventory above (FSR_GRAINCOLOR a toggle with its label trimmed), sidecar override and help, the file key. |
| `tests/file_browser` | D6 roots, sorting, filters, `..` stops at the root, unique import slugs, on a temp dir. Name sanitising (separators, `..`, `:`, reserved names, trailing dot or space, length), a symlink out of the root refused, the size cap, temp+rename writes, the overwrite confirm state. |
| `tests/enhance_menu` (revert) | Bindings back to the saved keys clear dirty; overrides and shader edit state revert; an imported key with no slot kept on Save. |
| `tests/overlay` (extended) | Glyph and key-cap quads through the reference rasteriser; the atlas fit at effective scale 3.0 with all three TTFs; the effective-scale clamp; unknown tokens fall back to text. |

## Risks / Trade-offs

- **Proton Steam keyboard may not work.** The OSK is the guaranteed path,
  and S1 runs early (phase E start) so that a "no" costs nothing.
- **`enhance_menu.c` grows past maintainability.** The change splits it:
  layout (D2), input and devices (D3, D4), browser (D6) and glyph text (D8)
  each get their own file. The row model stays put.
- **Hover-moves-selection surprises pad players.** The motion threshold and
  the "pad press hides cursor" rule contain it, and the ctest pins it.
- **Atlas growth.** Three fonts at several sizes. The ctest bounds it at
  the clamped maximum scale, and only the sizes in use are packed.
- **ui_scale needs a restart.** A player who changes it sees nothing until
  the next start; the row says "applies at restart". 3E.1 can make it live
  later.
- **mod-settings MD collides with C in `enhance_menu.c`.** Both edit the
  capture and input code. MD runs in its own worktree and rebases on C,
  whichever merges second. tasks.md names the files each phase owns.
- **Shared build files.** Every phase adds sources or ctests to
  `CMakeLists.txt` and `tests/CMakeLists.txt`. Edits there are
  append-only, and each wave names one owner who merges first; the others
  rebase their appended lines.
- **B/Esc now asks.** A player who relied on "close and keep pending" gets
  a dialog. Go Back as the default makes the dialog cost one press, and
  nothing is ever lost without an explicit choice.

## Migration Plan

Phases, waves, day estimates, repos and worktrees are in tasks.md:
- A: markers, Save, the dialog, hints data;
- GL: icon and glyph assets and API;
- K: shader kinds;
- T: the text ring;
- MC: free camera descriptor;
- FB: browser model;
- B: layout;
- MD: captured controls;
- C: mouse, focus, hints;
- E: rename editor, OSK, Proton keyboard;
- F: free camera page;
- G: import and export;
- H: docs, hosts, goldens;
- I: optional native picker.

The first wave (A, GL, K, T, MC, FB) runs in parallel, in separate
worktrees. Each phase merges on its own and passes the gates in CLAUDE.md.
Goldens are unaffected (each game's `golden.json` pins the menu off, D14)
but run because the runtime changes.

Behaviour changes a player notices, for the release notes:
- the row dot means unsaved, not "applies now";
- B or Esc on the toolbar asks when something is unsaved (D9a); in a section it goes back to the toolbar (Q12);
- X (pad) or Delete resets the selected row to its default on every row
  that has one, and the action is named "Reset to default (<value>)";
- View and L3 act on release;
- `overlay.ui_scale` needs a restart.

## Open Questions

- **Q1. Answered (the user, 2026-10-31):** compact is the default.
- **Q2. Answered:** the OS picker is low priority. It is a fallback only
  where the browser cannot work (macOS TCC-protected folders, a sandboxed
  Linux package), and it comes last, in optional phase I (D6).
- **Q3. Answered:** Lucide and Kenney are approved.
- **Q4. Answered:** mod-settings C and D run inside this change, as phases
  MC and MD. Work runs in parallel where it does not collide (tasks.md
  waves).
- **Q5. Answered (the user, 2026-10-31):** mods get an API too:
  `glyph_name` and a status panel in mod API version 7, with the free
  camera's on-screen indicator as the test bed (D12a). Tokens stay for
  menu text.
- **Q6. Answered:** the user runs S1 now, with the standalone probe (the tracker item
  comment). E.5 waits on its result.
- **Q7. Answered:** yes. Leaving with unsaved changes opens a three-button
  dialog (Exit without saving / Exit and Save / Go Back), with focus on Go
  Back (D9a).
- **Q8. Answered (the user, 2026-10-31):** FSR_GRAINCOLOR is a toggle, as
  every 0..1 step-1 param is. Its label drops ": Gray | RGB" (D5).
- **Q9. Answered (the user, 2026-10-31):** the View and L3 menu actions
  fire on release, and are suppressed while a game's menu chord is held,
  e.g. BLiNX 2's `back+left_thumb@400` (D3).
- **Q10. Answered (the user, 2026-11-01):** the toolbar stays on the left
  (a menu and its submenu). It shows icons only while the section or the
  footer has the focus, and icons and labels when it has the focus (D1).
- **Q11. Answered (the user, 2026-11-01):** Down from the last row moves
  to the footer's buttons. The shortcuts stay, with each one's glyph on
  its button, and never collide with a section's own buttons (D3).
- **Q12. Answered (the user, 2026-11-01):** B at a section's top level
  goes back to the toolbar, on that section's entry. A on the toolbar's
  active entry enters its section again. B on the toolbar is the leave
  request: it closes at once, or opens the unsaved-changes dialog (D9a).
