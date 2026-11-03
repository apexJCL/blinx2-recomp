## Context

These are the phases of design.md "Migration Plan", grouped into waves
(the user, 2026-10-31, Q4: run in parallel wherever the work does not
collide).

- **Worktrees.** Each phase gets its own worktree set,
  `wt/ovl-<phase>/{xboxrecomp,cat}`, with only the repos it needs, and one
  agent per worktree.
  - Toolkit branches go off `posix-host/portability`; cat branches go off
    `main`.
  - A phase that waits on another rebases on it after it merges.
- **Mac.** Builds use
  `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Runs are
  headless with `SDL_AUDIODRIVER=dummy`. A hand check that opens a window
  plays no sound unless the user agrees.
- **Run data.** Shots go to `xbox-recomp/runs/overlay-revamp/`, never inside
  a worktree.
- **Gates** (CLAUDE.md):
  - the build, `tests/posix_ctest.sh` with 0 FAIL, and `pytest tools/...`
    when tools changed (`tools/overlay` joins that gate with GL, run as
    `uv run --with fonttools --with picosvg pytest tools/overlay`);
  - goldens for phases that touch the runtime or input;
  - the Windows exe built on the PC under its lock;
  - `sh notes/build-all.sh` per toolkit merge;
  - a review per merge.
  - Merges go one at a time through the orchestrator, even when the work
    ran in parallel.

## Waves and ownership

| Wave | Phase | Repo | Worktree | Owns (files) | Waits for | Days |
|---|---|---|---|---|---|---|
| 1 | A markers, Save, revert, dialog, hints data | toolkit + cat | `wt/ovl-a` | `enhance_menu.c` (draw_row, footer, Save page, revert, bindings base, dialog), `enhance_menu.h`, `nv2a_present_chain.{c,h}` (`override_revert`, appended), `shader_profile_edit.{c,h}` (`shader_edit_revert`) | - | 3.5 |
| 1 | GL icon and glyph assets and API | toolkit | `wt/ovl-glyphs` | `third_party/{lucide,kenney-input}`, `tools/overlay/`, `nv2a_overlay_font.c`, `nv2a_overlay_ui.c`, `nv2a_overlay_glyph.{c,h}`, `enhance_input.c` (`input.glyphs` gains `generic`); cat: gamepad-input-ux tasks (I4 absorbed) | - | 3 |
| 1 | K shader kinds | toolkit | `wt/ovl-kinds` | `shader_param_kinds.{c,h}`, `assets/shaders/param-kinds.toml`, `shader_profile.c`, `nv2a_present_chain.{c,h}` (the param's `file`, in the parser), one hunk in `param_list` | - (rebases on A for the two shared files) | 1.5 |
| 1 | T text ring | toolkit | `wt/ovl-text` | `src/input/text_input.{c,h}`, the `WM_CHAR` hunks in `fb_present.c` and `nv2a_pb_d3d11.c`, `fb_present_sdl.c` text events and `xbox_InputSdlTextSync` | - | 1.5 |
| 1 | MC free camera descriptor (mod-settings C) | cat | `wt/ovl-modset-c` | `src/free_camera.c`, `src/env/recomp_env_game.h`, `docs/env.md`, `packaging/config.default.toml`, `scripts/test_free_camera.py` | - | 1.5 |
| 1 | FB browser model | toolkit | `wt/ovl-browser` | `src/enhance/file_browser.{c,h}`, `tests/file_browser` | - | 1.5 |
| 2 | B layout | toolkit | `wt/ovl-layout` | `enhance_menu_layout.{c,h}`, `enhance_menu_draw`, `nv2a_ovl_ui_scale` (the multiplier and clamp) | A, GL | 2.5 |
| 2 | MD captured controls (mod-settings D) | toolkit + cat | `wt/ovl-modset-d` | `mod.h` controls, the capture code in `enhance_menu.c`, `input_core.c` (`xbox_InputGetState` record and neutral pad), `enhance_actions.c`, `docs/runtime/config.md`; cat `free_camera.c` fly reads and `pad_input.c` | MC | 2.5 |
| 3 | C mouse, focus, hints | toolkit | `wt/ovl-mouse` | `enhance_menu_input.c` (new), `src/input/pointer.{c,h}` (new), the pointer hunks in both Win32 procs and `fb_present_sdl.c`, the divert gate in `enhance_input.c`, tooltip, `recomp_env.h` (one TRACE row) | B (rebases on MD if MD merges first) | 4 |
| 3 | E rename editor, OSK, Proton keyboard | toolkit | `wt/ovl-mouse` (same agent, after C) | the rename editor, `enhance_osk.c` (new) | B, T, S1 result | 1.5 |
| 3 | MG mod glyph API and status panel | toolkit + cat | `wt/ovl-modglyph` | `mod.h` (the version 7 block), `mod.c` (`glyph_name`, `status`), `enhance_mod_status.{c,h}` (new), the `{ctl:..}` token in `enhance_text.c`, one appended hunk where the overlay builds its frame list, `tests/mod_status` (new); cat `free_camera.c` (panel and its two settings), `docs/env.md` if a key is added | GL, B, MD | 1.25 |
| 4 | F free camera page | cat + toolkit | `wt/ovl-camera` | `free_camera.c` help text and page summary, the rebinding rows | MD, C | 0.75 |
| 4 | G import and export | toolkit + cat | `wt/ovl-files` | the Files rows, import/export in `enhance_menu.c` | FB, C, E | 2 |
| 5 | H docs, hosts, goldens | cat (+ CLI check, other games' `golden.json`) | `wt/ovl-docs` | `docs/env.md`, `config.default.toml`, TASKS, `analysis/golden/golden.json` audits | all above | 2 |
| 6 | I native picker (optional, low priority) | toolkit | `wt/ovl-picker` | `file_dialog_{win32,sdl}.c` | G | 1 |

- **Parallel:**
  - Wave 1 is six independent worktrees. They own disjoint files except
    two: K's one `param_list` hunk in `enhance_menu.c`, and
    `nv2a_present_chain.{c,h}`, where A appends `override_revert` and K
    adds the param's `file` in the parser. K rebases on A for both.
  - **Shared build files.** `CMakeLists.txt` and `tests/CMakeLists.txt`
    take append-only edits (new sources, new ctests at the end of their
    list). Each wave has one owner who merges first: A in wave 1, B in
    wave 2, C in wave 3, G in wave 4. The other phases rebase their
    appended lines on the owner's merge.
  - In wave 2, B and MD run side by side.
  - In wave 4, F and G run side by side.
- **Critical path:** A (3.5) → B (2.5) → C (4) → E (1.5) → G (2) → H
  (2), about 15.5 days. GL (3) runs beside A and is off the path by half a
  day.
- **Total effort:** about 29.25 days (A 3.5, GL 3, K 1.5, T 1.5, MC 1.5,
  FB 1.5, B 2.5, MD 2.5, C 4, E 1.5, MG 1.25, F 0.75, G 2, H 2), plus the
  optional 1 for I. The review raised A (revert needs three new APIs),
  GL (tool deps, `generic`, I4) and C (pointer source, divert,
  chord suppression).
- MG runs in wave 3 beside C. It owns no file C owns; F rebases on MG
  for `free_camera.c`.
- **Sequential on purpose:** C and E share the menu's input code, so they
  get one agent in one worktree. MD and C both touch capture, so whichever
  merges second rebases.

## A. Toolkit: markers, Save, revert, the dialog, Files, hints data (D9, D9a, D10, D11 data), 3.5 days, wave 1

- [x] A.1 `enhance_menu_row_state(i)` with `ROW_UNSAVED | ROW_NONDEFAULT |
  ROW_FORCED`, from slot `cur`/`base` and `slot_stock()`, shader override
  dirty, the bindings against their base (A.4) and `shader_edit_dirty`.
  The comparison is by value (D10): numbers as numbers, toggles as
  booleans, text as strings.
- [x] A.2 `draw_row`:
  - drop the live-class dot;
  - draw the unsaved dot before the label;
  - draw a non-default value in `text` and a default one in `text_dim`;
  - keep the waiting-class words.
- [x] A.3 ctest (D10 cases 1-7) in `tests/enhance_menu`.
- [x] A.4 `enhance_menu_revert()` and the saved copies it needs (D9):
  - slots: `cur = base`, then `set()`;
  - bindings: `s_abase[id]`, the bindings as last loaded or saved, taken
    where `s_adirty` is cleared today (load, Save, reload). Dirty becomes
    `!same_binds(cur, base)`, so rebinding back to the saved keys clears
    it. Revert restores the base with `enhance_action_set_bindings`;
  - `nv2a_present_chain_override_revert()` in `nv2a_present_chain.{c,h}`:
    the preset-scope overrides back to their loaded or saved values, the
    ones added since removed, the params re-applied;
  - `shader_edit_revert()` in `shader_profile_edit.{c,h}`: the chosen
    entry, chains, names and values back to the files and the config;
  - profile delete stays immediate (D9): no undo, and the dialog says so.
  - Tests: revert after edits of each kind gives `enhance_menu_unsaved()
    == 0`; live `set()` is called with the saved values; rebinding an
    action and then back to its saved keys leaves it clean with no
    revert; an override ctest in the present chain's tests.
- [x] A.5 The unsaved-changes dialog (D9a):
  - modal layer; buttons Exit without saving / Exit and Save / Go Back;
  - Go Back focused, the 150 ms swallow;
  - pad and keyboard focus and access keys N/S/G (mouse lands in C);
  - triggers: top-level B/Esc, Cancel, close `x`, the menu toggle;
  - a failed save keeps it open;
  - the "deleted profiles are not restored" line when the session deleted
    one.
  - Tests as listed in D9a.
- [x] A.6 The footer as a summary (D9): device hint sets (pad and keyboard
  for now), unsaved or status, Cancel and Save buttons; pad View (on
  release, D3) and Shift+Esc = Cancel; F5, Ctrl+S and, on macOS, Cmd+S =
  Save.
  - View and L3 fire on release and are suppressed while they are held
    as part of a game's menu chord (the `menu.open` action's pad
    bindings, e.g. BLiNX 2's `back+left_thumb@400`). A ctest drives that
    chord and checks that neither Cancel nor the hints toggle fires.
  - Interim, until B or C draws hints at the rows: the selected row's
    help stays in the footer while no status shows (it stands in for the
    controls hint), and L3 flips the hints mode with no status line.
  - The footer buttons and hints are text for now. Their input glyphs
    come later, with GL's tokens.
- [x] A.7 Save becomes Files:
  - the path info row and Reset to defaults;
  - placeholders for import and export, hidden until G;
  - drop the Save and Unsaved rows.
  - Update the tests that select those rows.
- [x] A.8 Add `help` to `struct enhance_item` (appended, NULL-safe). Write
  help for every built-in item and add the section intro table. Shader
  param help comes from K's sidecar, not from `desc`.
- [x] A.9 cat: help strings on the game items, and
  `enhance_menu_page_intro("Game", ...)` (0.25 day, same worktree's cat).

## GL. Toolkit: icons and input glyphs (D7, D8), 3 days, wave 1

- [x] GL.1 Lucide subset:
  - `third_party/lucide/` holds `lucide-subset.ttf`, LICENSE and VERSION
    (Lucide release and the `pyftsubset` command);
  - LICENSE is Lucide's whole file: the ISC licence and Feather's MIT
    notice;
  - pack it as a second font in `try_pack`.
- [x] GL.2 Kenney Input Prompts subset (CC0):
  - pick the glyphs (D8 list, no platform logos);
  - write `tools/overlay/glyphs_to_ttf.py`: deterministic; fonttools and
    picosvg declared as PEP 723 inline metadata (the toolkit has no
    `pyproject.toml`) and run with `uv run`; the docstring says so;
  - commit the generated `third_party/kenney-input/{xbr-input.ttf,LICENSE,
    VERSION,glyphs.txt}` (the build never runs the script);
  - add `tools/overlay/test_glyphs_to_ttf.py`: a reproduce test (byte for
    byte; skips with a reason without fonttools) and a stdlib-only check
    of `glyphs.txt` and VERSION against the script's list. Add
    `tools/overlay` to the toolkit's pytest gate.
- [x] GL.3 The glyph command in the converter.
  `nv2a_overlay_glyph.h`: `nv2a_ovl_glyph_src/mouse/key` and
  `nv2a_ovl_ui_glyph`. Key caps use RRECT plus the layout key name
  (`GetKeyNameTextW` / `SDL_GetKeyName`).
- [x] GL.4 `enhance_text_draw` with tokens `{pad:..}`, `{key:..}`,
  `{mouse:..}` and `{act:..}`; unknown tokens draw as text.
- [x] GL.5 Family selection reuses what ships: `xbox_InputPadFamily`
  (`input_core.c`) and its SDL3 table in `src/input/xinput_device.c`
  (gamepad-input-ux D5, I2.6). GL adds only:
  - `generic` to the `input.glyphs` values in `enhance_input.c`, with its
    config.md line;
  - the family to glyph-set lookup. On Win32 `auto` stays Xbox, also under
    Proton; `RENV_STEAM_DECK` does not change it (gamepad-input-ux D5).
  - Test the lookup per family, including Switch SOUTH = "B".
  - Mark gamepad-input-ux I4 (I4.1, I4.2) as absorbed by overlay-revamp
    GL in that spec's tasks (cat).
- [x] GL.6 `tests/overlay`: glyph and key-cap quads through the reference
  rasteriser; the atlas-fit test: a bake at effective scale 3.0 (the
  clamp, D2) with the text font, `lucide-subset.ttf` and `xbr-input.ttf`
  and every size the menu packs fits 2048x2048.
- [x] GL.7 Audit allow-list: the two TTFs are the only binaries this
  change adds. Record them for the public export audit.
  - Recorded (GL): the binaries are
    `third_party/lucide/lucide-subset.ttf` (ISC, Lucide 1.57.0) and
    `third_party/kenney-input/xbr-input.ttf` (CC0, generated by
    `tools/overlay/glyphs_to_ttf.py` from the Kenney Input Prompts
    SVGs). Neither holds game data; both are vendored assets the public
    export keeps.
- GL notes (as built, `feat/ovl-glyphs`):
  - At 1080 lines the atlas is 1024x1024 (was 512x1024); at 3240 lines
    it fits 2048x2048 only by baking text of 40 px and up without the 2x1
    oversampling, the last try in `try_pack` (`tests/overlay` pins it).
  - The POSIX key-cap label is the code's own name
    (`xbox_InputCodeName`), not `SDL_GetKeyName`: SDL hosts record keys
    by keycode, so the name already follows the layout, and the kernel
    and enhance layer make no SDL call. Win32 uses `GetKeyNameTextW`.
  - No glyph: the Xbox paddles and touchpad, the Switch capture button,
    the PlayStation and Nintendo paddles. Those members draw their name.
  - `{key:a}` reads every member as a key; in `{act:}` a lowercase
    member is a pad name, as `enhance_actions.c` reads bindings.

## K. Toolkit: shader parameter kinds (D5), 1.5 days, wave 1

- [x] K.1 The resolver in `shader_param_kinds.{c,h}`: declared, then
  inferred toggle, then inferred choice from `desc` names, then slider.
  Values stay numeric.
- [x] K.2 `assets/shaders/param-kinds.toml` for MASK and shadowMask, keyed
  by shader file and param name, with `help` strings. The names come from
  each shader's source comments, and the sources are cited in the file.
- [x] K.2a `struct nv2a_present_param` gains `char file[64]`, the basename
  of the declaring shader, set in `nv2a_present_chain.c` where `#pragma
  parameter` is parsed (the first stage's file for a shared name). The
  sidecar lookup keys on it.
- [x] K.3 `[param_kinds]` in shader profiles (optional override); the
  profile version stays 1, and unknown tables are ignored by older builds.
- [x] K.4 `param_list` builds TOGGLE and CHOICE items; Save and the
  override writes stay numeric. The label drops a trailing `: a | b` names
  list (FSR_GRAINCOLOR reads "FSR LFGA Film Grain Color", a toggle, the
  user's decision); the row help is the sidecar's `help`. Rebase on A if A
  merged first.
- [x] K.5 `tests/shader_param_kinds` over the design inventory, including
  FSR_GRAINCOLOR as a toggle with its trimmed label, and the file key.

## T. Toolkit: the text ring (D4), 1.5 days, wave 1

- [x] T.1 `src/input/text_input.{c,h}`: the SPSC lock-free ring (64
  codepoints, producer-only head and consumer-only tail, acquire/release,
  a dropped count) and Begin/End as requests (state, rect and generation
  stored atomically). Control characters (< 0x20, 0x7F) are dropped at the
  producer. `tests/input_text`: UTF-8, surrogates (a lone one dropped),
  Tab and 0x13 dropped, overflow, gating, a two-thread run.
- [x] T.2 `WM_CHAR` in the two game window procs (`fb_present.c`,
  `nv2a_pb_d3d11.c`), gated by the request state; `video_pump.c`'s
  `vp_wndproc` gets none (the movie window, no menu).
- [x] T.3 SDL: `SDL_EVENT_TEXT_INPUT` in the loop, and
  `xbox_InputSdlTextSync(win)` beside `xbox_InputSdlMouseSync`, which
  calls `SDL_StartTextInput`, `SDL_StopTextInput` and
  `SDL_SetTextInputArea` on the main thread when the generation changes.
  No menu changes yet.

## MC. cat: free camera descriptor (mod-settings C, run here per Q4), 1.5 days, wave 1

- [x] MC.1 Carry out `openspec/changes/mod-settings/tasks.md` section C as
  written, with its gates. Tick its boxes there and reference this change
  in the commit body.

## FB. Toolkit: browser model (D6), 1 day, wave 1

- [x] FB.1 `src/enhance/file_browser.{c,h}`: roots (exports, config,
  shader profiles, home, Windows drives), listing callback, sorting,
  filters, the root stop, an `EPERM`/`EACCES` result per folder.
- [x] FB.2 Wine home through `Z:`: the Unix `HOME` turned into a DOS path
  with `wine_get_dos_file_name` (looked up with `GetProcAddress`); `Z:` is
  the Unix root `/`. `%USERPROFILE%` on Windows.
- [x] FB.3 The D6 safety rules in the model: name sanitising (separators,
  `..`, `:`, control characters, `CON`/`NUL`/`COM1`-style names on every
  host, trailing dot or space, 64 bytes), the symlink policy (a folder link
  opens only inside its root), the 256 KB import cap, the export
  overwrite-confirm state, temp+rename writes, UTF-16 calls on Windows
  (`_wfopen`, `FindFirstFileW`, `MoveFileExW`).
- [x] FB.4 `tests/file_browser` on a temp dir, including an unreadable
  folder, each refused name, a symlink out of the root and an oversized
  file.

## B. Toolkit: layout (D1, D2), 2.5 days, wave 2, after A and GL

- [x] B.1 `src/enhance/enhance_menu_layout.{c,h}` and `menu_hit()`: pure,
  with no overlay includes.
- [x] B.2 `tests/enhance_menu_layout`: the sizes in D2 at ui scale 0.75, 1
  and 2; toolbar collapse; the 16:9 cap in expanded mode; a row-centre
  hit-test round trip; clipped rows not hittable; the dialog rects; the
  toolbar's folded and unfolded rects (Q10), the unfolded one over the
  content without moving its rows.
- [x] B.3 Redraw `enhance_menu_draw` from the layout:
  - header with icon buttons, toolbar with icons and section dots;
  - the content intro line;
  - footer buttons with their shortcut glyph on the button ("[Y] Save",
    "[View] Cancel"; GL.4, Q11);
  - the toolbar folds to icons while CONTENT or FOOTER has the focus and
    unfolds with labels when it has it, plus the 1.5 s LB/RB peek (Q10);
  - the dialog.
  - Remove the tab strip.
- [x] B.4 Size modes and `overlay.menu_size` (default compact, file-only,
  written on toggle); R3 (on release) and the header button. Compact is
  `geom_of`'s panel as it is today (left at `pad`, 40% of the width, at
  most 720 px scaled, full width under 640 px or portrait). The write
  touches only that key and is skipped under `RECOMP_CONFIG=none`.
  (Done: the header button is drawn and `menu_hit` finds it; its click
  arrives with C's pointer.)
- [x] B.5 3E's `overlay.ui_scale` multiplier on `nv2a_ovl_ui_scale`,
  **restart-only** (D2: the atlas is baked once at arm; a live value needs
  3E.1's worker, left to 3E). Effective scale = clamp(output factor *
  ui_scale, 0.5, 3.0). The menu row is ENHANCE_RESTART. A test: the clamp
  at 3840x2160 with 2.0 gives 3.0, and 640x480 with 0.75 gives 0.5. Its
  `docs/runtime/config.md` line.

## MD. Toolkit and cat: captured controls (mod-settings D, run here per Q4), 2.5 days, wave 2, after MC

- [x] MD.1 Carry out `openspec/changes/mod-settings/tasks.md` section D as
  written, with its gates. Tick its boxes there. Rebase on C if C merges
  first: both touch capture in `enhance_menu.c`.
  *Merged in toolkit d683d5de.*

## C. Toolkit: mouse, focus and hints (D3, D11; absorbs enhance-menu-preview 3F), 4 days, wave 3, after B

- [x] C.1 `menu_device` (PAD, KEYBOARD, MOUSE) with the motion threshold;
  the open-time default.
- [x] C.2 Focus regions and Tab/Shift+Tab; Q/E in the toolbar. While a
  text field has focus, `enhance_actions_quiet(1)` (as `name_begin` does)
  and the letter shortcuts are off.
- [x] C.2a Pad footer focus (D3, Q11): Down past the last row enters
  FOOTER (Save when unsaved, else Cancel), Left/Right pick, A presses, Up
  or B returns to the row; the wrap in `move_sel` goes. The action table
  names each button's owner (global: Y, View, L3, R3, LB/RB; section: A,
  B, X, d-pad, left stick) and a ctest checks they are disjoint and that
  no section or mod page binds a global button.
- [x] C.2b Pad toolbar focus (D3, Q12): B at a section's top level moves
  to TOOLBAR on that entry (unfolded); Up/Down or LB/RB move entries; A or
  Right enters on the remembered row; B in TOOLBAR is the leave request
  (D9a dialog when unsaved). Update A.4's trigger (top-level B becomes
  toolbar B) and its ctest; a ctest drives B, B with and without unsaved
  rows.
- [x] C.3 The pointer source (D3), new: `src/input/pointer.{c,h}`, a
  seqlocked snapshot of window-space x/y, buttons, wheel steps and a
  sequence number, written by `WM_MOUSEMOVE`, the button messages and
  `WM_MOUSEWHEEL` in both Win32 game procs and by the SDL loop's mouse
  events (scaled by the pixel density); `xbox_InputPointerTake` reads it.
  A ctest feeds both writers' formats and checks the snapshot.
- [x] C.4 Mouse via the 3F design:
  - on open: record the state, `xbox_InputMouseSuspend(1)`, the CURSOR
    layer; a mod's divert turned off (`xbox_InputMouseDivert(0)`);
  - `enhance_input_capture` records a mod's capture but leaves the divert
    alone while the menu holds the mouse;
  - on close: `xbox_InputMouseSuspend(0)`, then
    `xbox_InputMouseDivert(enhance_input_captured())`;
  - window-to-placement mapping in one function.
  - Test: the free camera's capture on, menu open and closed, capture
    back with no counts carried over; capture released while open stays
    released.
  *Done on feat/ovl-mouse with one change: no CURSOR layer. The OS
  cursor is the menu's pointer (freed by the suspend, hidden on a pad or
  key press through `xbox_InputMouseCursorHide`, shown on motion), so
  D3D11's cursor does not wait for a guest flip. The pointer is fed from
  the one Win32 observer (`xbox_InputMouseWin32Msg`), which both game
  procs already call. The placement mapping is `pointer_step`'s.*
- [x] C.5 Hit actions:
  - hover selects on motion;
  - clicks on pill, arrows, slider (drag and snap), label, header and
    footer buttons, and the dialog's buttons;
  - the wheel scrolls; right-click is back (Go Back in the dialog);
  - outside clicks are inert.
  *Clicks act on the press, at the place pressed, also when the press and
  its release both fall between two menu steps (a tap). The slider drag
  sets the value once per motion, snapped to the item's step and clamped
  to its range. A dialog click waits out the dialog's 150 ms swallow, as
  the pad does. After a wheel scroll the next key or pad press only brings
  the selection back into view. Toolbar entries
  click too. Esc and Backspace act as B (the user, 2026-11-01): from a
  section's top level to the toolbar, from there the leave request. The
  wheel over a slider or a choice steps it one notch at a time; elsewhere
  it scrolls. Under `present.surface=internal` the pointer maps through
  the view each presenter publishes (`nv2a_overlay_set_view`; Metal's
  aspect fit, D3D11's stretch).*
- [x] C.6 Cursor hides on a pad or key press; the mouse hint set.
- [x] C.7 Hints (D11): the tooltip card with its timers, inline mode,
  `overlay.menu_hints` (the write touches only that key; skipped under
  `RECOMP_CONFIG=none`), and the header `?` / L3 (on release, chord
  suppressed as in A.6) / F1 toggle.
- [x] C.8 Tests: the D16 focus and tooltip cases and the dialog's mouse
  path, on synthetic events and a fake clock.
- [x] C.9 `RECOMP_TRACE=menu_input`: a TRACE-tier X-macro row in
  `recomp_env.h` (token `menu_input`, no legacy name), the log lines, and
  its `docs/runtime/config.md` line.
- [x] C.10 Mark enhance-menu-preview 3F as done by this change in that
  spec's tasks (cat).

## E. Toolkit: rename editor, OSK and the Game Mode keyboard (D4), 1.5 days, wave 3, after B and T (same agent as C)

- [x] E.0 S1 probe built (2026-10-31, `runs/overlay-s1/`). The user runs
  it on the Deck in Game Mode. Record the result:
  - whether the Steam keyboard shows;
  - whether `WM_CHAR` arrives;
  - both as a umu-run launcher shortcut (as BLiNX 2 runs) and as a Steam
    Proton shortcut;
  - which Game Mode signal reaches the Windows exe: `SteamGamepadUI`,
    `GAMESCOPE_WAYLAND_DISPLAY`, `XDG_CURRENT_DESKTOP`, and whether
    `SteamDeck` is set in Desktop mode as well (expected: yes, so it is
    not the signal);
  - whether Steam sets `SDL_ENABLE_STEAM_SCREEN_KEYBOARD` (the hint name
    in our SDL3 headers) for a native Linux run.
  - If the probe does not print the environment, the next probe run adds
    an env dump; E.3 waits on these answers.
- [x] E.1 The rename editor on the ring. Remove the US-layout VK map.
- [x] E.2 The in-overlay keyboard (OSK) grid, pad-driven, opened by the D4
  rule; its hint set, including "Steam + X" when Steam is present.
  *While the field is open, LB and RB move the text cursor and Start
  keeps the name (as Done). Typed text from a keyboard puts the grid
  away. A rename started by the mouse or a touch opens the grid too,
  unless a key has been pressed this session (the user, 2026-11-01).*
- [ ] E.3 The Proton Steam keyboard behind `overlay.steam_keyboard=auto`,
  only if S1 passed, and only when the Game Mode signal from E.0 is set
  (never on `SteamDeck=1` alone). The `ShellExecuteW` call runs on the
  window's thread through T's request and sync. Otherwise `auto` stays off
  under Wine, with a TASKS note. Its `docs/runtime/config.md` line.
  *Not done in this round (out of scope for feat/ovl-mouse): it waits on
  the S1 answers recorded on the tracker. Stays open.*

## MG. Toolkit and cat: mod glyph API and status panel (D12a, Q5), 1.25 days, wave 3, after GL, B and MD

- [x] MG.1 `mod.h`: the version 7 block (`glyph_name`, `status`,
  `XBOX_GLYPH_TOKENS`, `XBOX_GLYPH_TEXT`), appended after version 6;
  `XBOX_MOD_API_VERSION` 7. A v6 mod still loads (`tests` load one).
- [x] MG.2 `mod.c`: `glyph_name` over the action and control binding
  tables and the GL glyph lookup, for the latest device; the `{ctl:..}`
  token in `enhance_text.c`, resolved against the mod that owns the
  string. Update the `enhance_text.h` header comment (Q5 answered).
- [x] MG.3 `enhance_mod_status.{c,h}`: per-mod panels, copied under a
  lock, cut to 6 lines of 120 bytes, expanded at every draw, stacked in
  load order, hidden while the menu is open, dropped on disable or
  failure; drawn through the overlay command list at the effective UI
  scale.
- [x] MG.4 `tests/mod_status`: set, replace, clear, the cut (-1),
  disable drops it; the panel's quads through the reference rasteriser;
  `glyph_name` for a source, an action, a control, a chord, an unbound
  ref (-1), both flags, after a rebinding.
- [x] MG.5 cat `src/free_camera.c`: the panel while flying (D12a lines),
  cleared on exit; **Show indicator** and **Controls reminder**
  (Brief/Always/Never, Brief 10 s) in the descriptor, with their
  `config.default.toml` keys and `docs/env.md` rows if they get env
  keys; `scripts/test_free_camera.py` cases for the reminder timing and
  the off settings.
- [x] MG.6 `docs/runtime/config.md` (or the mod API doc): the version 7
  calls, the panel's limits and placement.
- [x] MG.7 Gates: Mac posix ctest; PC build and the BLiNX 2 D3D11
  goldens (the panel must not draw: free camera off). Hand check for the
  user: fly with pad and keyboard, switch devices mid-flight, rebind a
  control, the Brief collapse, both settings off.

## F. cat and toolkit: free camera page (D12), 0.75 day, wave 4, after MD and C

The settings themselves (invert X/Y, mouse sensitivity, fast and slow),
their env rows in `recomp_env_game.h` and `docs/env.md`, and their
`config.default.toml` keys are mod-settings C.3 and C.4, carried out in
MC. F adds none of them again.

- [x] F.1 cat `src/free_camera.c`: help text with tokens on MC's settings
  and actions, units on the sliders, and the page summary. The panel and
  its two settings are MG.5's, not F's.
- [x] F.2 The rebinding rows for actions and captured fly controls drawn as
  glyphs; capture on pad, keyboard and mouse; conflict status; "Reset
  camera controls". As built: `{bind:}` glyph rows, mouse capture for
  fly buttons only, the row named "Reset free camera controls" (D12).
- [ ] F.3 Freeze and reset defaults follow save-states (End and Home) when
  it has merged. Waits for the save-states merge; the defaults are already
  End and Home.
- [x] F.4 Check that F added no key; if it did, its `docs/env.md` row
  (cat). MC already wrote the rows for C.3's settings. F added none.

## G. Toolkit: import and export (D6), 2 days, wave 4, after FB, C and E

- [x] G.1 Export config (including unsaved values, labelled) and export
  shader profile; default names typed through the ring or OSK and
  sanitised (FB.3); the overwrite confirm on an existing file; temp+rename
  writes; status path.
- [x] G.2 Import config: the size cap, parse, version check, unknown-key
  list, preview count, applied as unsaved changes. Keys with no slot are
  kept and written on Save. `menu.enabled = false` is written on Save but
  not applied to the open menu, and the preview says it applies at the
  next start. Import shader profile under a unique slug, written
  atomically. Tests: "Exit without saving" undoes an import; an imported
  key with no slot survives Save; an import with `menu.enabled = false`
  leaves the menu open.
- [x] G.3 Files rows; "Open exports folder" on the desktop only
  (`ShellExecuteW` / `SDL_OpenURL`), hidden in Game Mode. An unreadable
  folder says so (no picker row before phase I).
- [x] G.4 Note in the save-states spec that 3G reuses this browser (cat).

  As built: toolkit `feat/ovl-files`. The deviations from D6 are
  under D6's "As built" list. The tests are `test_files_export`,
  `test_files_import` and `test_files_folders` in `tests/enhance_menu`.
  No new env key.

## H. Docs, CLI check, hosts and goldens, 2 days, wave 5

- [ ] H.1 cat `docs/env.md`: rows for the D15 config keys and the
  `RECOMP_TRACE=menu_input` token. Check that the toolkit's
  `docs/runtime/config.md` has the line each toolkit phase added (B.4,
  B.5, C.7, C.9, E.3, I).
- [ ] H.2 cat `config.default.toml`: commented `[overlay]` keys with their
  defaults.
- [ ] H.3 Goldens and the menu. `golden.py` sets no menu env; it fails a
  run whose log lacks `menu.enabled=off`. The pin lives in each game's
  `golden.json` `env`. Audit every game:
  - BLiNX 2 (`cat/analysis/golden/golden.json`): `RECOMP_MENU=0`,
    `RECOMP_CONFIG=none` (and `RECOMP_OVERLAY_STATS=0`), checked by
    `scripts/test_config_default.py`. No change.
  - JSRF (`config/golden/golden.json`): the same pins. No change.
  - SSX 3 (`config/golden/golden.json`): only `RECOMP_CONFIG=none`. Add
    `RECOMP_MENU=0` (and `RECOMP_OVERLAY_STATS=0`) on a branch in that
    repo, so the menu stays off if the config pin is ever dropped.
  - BLiNX 1, Burnout 3, KUF: no `golden.json` yet; note in TASKS that
    their first one carries both pins.
  - Confirm that no D15 key changes a golden run: all default to today's
    behaviour and none is read while the menu is closed. No CLI change
    expected; if one is needed, it goes on a CLI branch.
- [ ] H.4 Goldens for each phase that touches the runtime: D3D11 on the PC
  (native Windows when it is up), Metal on the Mac before a release round,
  and the Deck under Proton later, non-blocking.
- [ ] H.5 Hand checks (below), each on the orchestrator's slot. Shots go to
  `runs/overlay-revamp/`.
- [ ] H.6 `cat/TASKS.md`: the merges, any gap (e.g. the cursor at present
  time on D3D11, F-9), and S1's result.

## I. Toolkit: native picker fallback (D6), optional, low priority, 1 day, wave 6

- [ ] I.1 `file_dialog_sdl.c`: `SDL_ShowOpenFileDialog` /
  `SDL_ShowSaveFileDialog`, results delivered on the menu thread. Offered
  only:
  - from the "Choose with the system picker…" row after a macOS
    `EPERM`/`EACCES`;
  - in a sandboxed build (`FLATPAK_ID`);
  - when `overlay.file_dialog=native`.
- [ ] I.2 `file_dialog_win32.c` (`IFileDialog`): only for
  `overlay.file_dialog=native`, since the browser covers Windows and
  Proton. It may be skipped.
- [ ] I.3 Never the default; never shown in Game Mode.

### Planned hand checks (not run by the spec)

**Windows PC (native Windows 11, D3D11, borderless fullscreen):**
- [ ] Open with F10. Pad, keyboard and mouse mixed:
  - a still mouse never steals the selection;
  - a pad press hides the cursor;
  - the footer swaps glyphs (Xbox pad, then a DualSense if one is to hand).
- [ ] Click pill, arrows and slider drag; wheel; right-click back; the
  backdrop is inert; compact/expanded; the hints toggle.
- [ ] Rename with a Spanish or AZERTY layout: "ñ" and "é" arrive; key caps
  show the layout's names.
- [ ] Unsaved dot, Save from Render; B at the top level opens the dialog on Go Back, and "Exit without saving" reverts a live
  scale change; Cancel and the header close open the same dialog.
- [ ] BLiNX 2's menu chord (View + L3, held) with the menu open: it
  closes or opens the menu as today, and neither Cancel nor the hints
  toggle fires.
- [ ] Export, then import a config; "Exit without saving" undoes the import.
  (Phase I only: the native picker opens in front of the game.)
- [ ] 21:9 or 4K output if available: the expanded cap and the scale.

**macOS (Metal, Retina, a fullscreen Space; no sound unless the user
agrees):**
- [ ] Trackpad hover and click, two-finger scroll, mapping right at 2x
  HiDPI.
- [ ] Text with a non-US layout and with Latin composition (dead keys and
  the accent menu: "é", "ñ"). CJK IMEs are out of scope: the atlas has no
  CJK glyphs.
- [ ] Browser: open Documents; after a TCC "Don't Allow" the folder says it cannot be read (phase I: the system picker row appears and works as a sheet in fullscreen).
- [ ] Glyphs for a PlayStation or Switch pad over Bluetooth.

**Steam Deck, Game Mode (Proton, 1280x800):**
- [ ] Pad only: every section, the tooltip timing, the OSK rename,
  "Steam + X" in the hint, Deck glyphs including the L4/R4 grips.
- [ ] S1 result in practice: does the Steam keyboard open and type into the
  rename field?
- [ ] A touchscreen tap acts as a click.
- [ ] Browser: export to Home, then import back, both through `Z:`; Open
  folder is hidden.
- [ ] Free camera page: invert toggles and rebinding of a fly control to a
  back grip.
- [ ] Desktop mode once: the mouse and the Steam keyboard behave as on
  Linux desktop.


## R. Review and merge

- [ ] R.1 A review per phase merge. Fixes go back to that phase's
  agent.
- [ ] R.2 After the last phase, sync the `enhancements` capability spec
  and archive this change.
