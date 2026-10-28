## How to read this plan

**Sizes:** S is half a day or less, M is one to two days, L is more.

**Naming:** this spec's phases are I1 to I8. The overlay phases of `enhance-menu-preview` are always written "overlay 3A" and so on:
- overlay 3A (In Review);
- overlay 3B (Done);
- overlay 3C, the live switch;
- overlay 3D, the menu;
- overlay 3E, font and theme;
- overlay 6, Proton and Deck validation;
- overlay 9, extra pad buttons, which is folded into I5 here.

**Decisions:** Q1 to Q12 are decided (design, "Decisions taken"). The details of Q4 wait on the user's confirmation, and only I3 depends on them.

## I1. Decisions, the tracker item and probes (S)

- [x] I1.1 Record the user's answers in design.md (Q1-Q10 on 2026-10-23, then Q11 and Q12 the same day).
- [ ] I1.2 Merge the tracker item (`feat/overlay-paddle` `74fd70e9`) as the first step, once overlay 3A merges (Q10):
  - `paddle1` joins `menu.open`'s defaults;
  - the `config.md` Deck section: Steam keeps Guide, and R4 is bound to F10 in Steam Input;
  - correct the paddle line there to "DualSense Edge right back button".
  - Gates: toolkit ctests (`input_actions`). No goldens, because the hook stays off under `RECOMP_CONFIG=none`.
- [ ] I1.3 **Blocked until linux-native-vulkan provides a native Linux SDL3 binary.** The Deck never builds, and its built-in pad cannot be attached to a Mac.
  - The alternative, which needs the user's approval and a Deck slot: a prebuilt SDL3 probe that compiles nothing, for example the PySDL3 wheel run under uv on the Deck.
  - Read-only: log `SDL_GetGamepadType`, the VID:PID and `SDL_GetGamepadSteamHandle` for the built-in pad, with Steam Input on and off.
  - It settles which family the Deck reports (design D5). Until then, `input.glyphs` is the answer for the Deck.

## I2. Adopt #203, raw host state, pad map, host-space actions (L, about 4 days; beside overlay 3C)

- [x] I2.1 Adopt upstream #203's pad half (Q11, design D3). Size M, about 1.5 days.
  - Cherry-pick `650dfe14` (`input_map.{c,h}`, `tests/input_map`, `src/input/README.md`), or take it with the next upstream merge if that comes first.
  - Rename the fork's table module to `input_host.{c,h}`, with its ctest (`tests/input_host`) and the README row generator, and update every include site.
  - The keyboard half of #203 (`InputBindings`, `keyboard.c` changes) is taken only as far as it compiles beside the fork's `keyboard.c`. Its merge with `[input.bindings]` is a follow-up in TASKS.md.
- [x] I2.2 `input_host.c`: fill an `InputRaw` from XInput and from SDL.
  - **Triggers:** scaled into 0..32767 so that `>> 7` and `ApplyTrigger(v, 0)` give back the same 0..255.
  - **Stick-direction sources:** #203 says "the adapter must populate directional sources explicitly". The adapter fills `INPUT_SRC_LSTICK_UP` through `INPUT_SRC_RSTICK_RIGHT` from the clamped magnitude of each half-axis, in 0..32767. The opposite half reads 0, because `src[]` treats negative values as 0.
  - **Inversion:** `pad_invert_*` negates the host axis here, before `PadMap`, and clamps `-(-32768)` to `32767`.
  - **Stock polling:** the extras and `XInputGetStateEx` are used only while a pad filter is installed or the map names `guide`.
- [x] I2.3 `input_core.c`:
  - the runtime identity: `PadMapDefaults`, then White = LB, deadzones 0 and trigger threshold 0;
  - the raw-stick write-back after `PadMap` for a stick with deadzone 0, honouring the swap (design D3, review R2-1);
  - the alternate map, and `PadMerge`.
- [x] I2.4 `enhance_input.c`: parse `[input.pad]` with upstream's control and source names (no aliases), the two-cell lists, `left_stick`/`right_stick` as `left|right|none`, and the pad options (`pad_deadzone_left/right` in percent, `pad_threshold`, `pad_invert_ly/ry`). It uses the `[input.bindings]` layering, cross-file removal, and a warning for a source named twice in one file. `RECOMP_PAD_DEADZONE` keeps its integer meaning, and the file key wins with a log line.
- [x] I2.5 `enhance_actions.c`, the host-space rules (design D4):
  - rule 1 checks both maps;
  - masking goes through both maps;
  - guest control names in chords as the identity's sources; old spellings log `unknown name`;
  - the chord kind is derived from the map at every rebuild, with `B_MOD`'s `modbit` widened to a mask so a chord can have several modifiers;
  - an all-mapped chord without a hold of 200 ms or more goes inactive with a warning;
  - a derived modifier chord keeps rule 7's press order and its `@N` hold;
  - a single-source binding that becomes mapped goes inactive with a warning.
- [x] I2.6 Family and Steam detection, pulled forward from I4 because they do not need overlay 3E:
  - `xbox_InputPadFamily(slot)` with the D5 table (GameCube, Steam and 28de:1205 included), and the `input.glyphs` override;
  - `xbox_InputSteamInput(slot)`: on via the Steam handle or 28de:11ff, `maybe` under Proton when `SteamGameId` or `SteamDeck` is set;
  - those two read through new `recomp_env` config-tier rows, never a raw `getenv`, with rows in `cat/docs/env.md`.
- [x] I2.7 ctests, as in design D12:
  - `input_map` (upstream's, as is);
  - `input_host`: identity equivalence including the stick corners, `-32768` and a swap; the XInput entry point; the `-32768` inversion clamp; the direction sources;
  - `input_pad_map`: each conversion row, the merge, inversion before a swap, a non-zero deadzone through #203's rescale, layering, old names refused;
  - `input_actions`: every chord-kind transition (two modifiers, all-mapped without a hold, press order, the `@N` hold), and `paddle1` mapped, unmapped and remapped;
  - `input_hotplug_sdl` (families, 11ff against 1205, paddles).
- [x] I2.8 Docs: `docs/runtime/config.md` (the `[input.pad]` section, the pad options, the "not mapped to the game" wording for host actions, and the Steam detection lines), `docs/env.md` rows, and a TASKS.md follow-up for the keyboard half of #203.
- Deviations recorded for I2:
  - I2.1: #203 came in with the v0.16 upstream merge (`4f887107`, then `e2b6a5af`), so there was nothing to cherry-pick. The fork's table module keeps the name `pad_map.{c,h}` (with `tests/pad_map` and its README generator) instead of `input_host`: the input-vocab merge had already settled that name across cat, b3 and skates, and a rename buys nothing.
  - I2.2: the converters (`xbox_PadRawXInput`, `xbox_PadRawSdl`) live in `pad_map.c` beside the table they read, rather than in a separate `input_host.c`.
  - I2.7: the `[input.pad]` parser tests live in `tests/enhance_cfg` (its file harness) rather than a new `input_pad_map` ctest; the identity, conversion, merge, inversion and deadzone rows are in `tests/pad_map`.
- [x] I2.9 Gates:
  - the Mac build and the POSIX ctests;
  - the goldens (Metal, and D3D11 under Proton), which prove the identity because this touches the runtime input path;
  - a Proton run;
  - a Burnout 3 build and a menu run, to show the identity there.
  - Results (2026-10-26): POSIX ctests 107 pass, 0 FAIL; cat pytest 102 passed and ruff clean; Metal golden attract, stage1 and story pass (`20261026-094650`, `094718`, `094837`); D3D11 golden under GE-Proton11-7 attract and stage1 pass, story INCOMPLETE on story-hub only (the known gap; `20261026-100218`, `100338`, `100529`; a first run at `095627` was INCONCLUSIVE on a busy host); Burnout 3 Mac build and `race_gate` fast PASS through the menus into a race (54.6 race flips/s against 55.0 before).

## I3. Steam Input template for the Deck (S-M, about 1 day; once Q4's details are confirmed)

- [ ] I3.1 Write `<slug>_neptune.vdf`, per design D6:
  - R4 = F10;
  - R5 = F6 for BLiNX 2;
  - L4 and L5 left unbound until save-states task 4.0, then F5 and F9;
  - the base layout is Gamepad with Mouse Trackpad when `[input] mouse` is on, else Gamepad.
  - Validate it by exporting a hand-made layout from Steam on the Deck and diffing the files (needs a Deck slot).
- [ ] I3.2 CLI: the `steamos` (and later `linux`) package templates carry the file, rendered from game.toml's slug and title and from the game's defaults. `install.sh` copies it into `controller_base/templates/` on every install and prints the one-line pick step. The README part gets the step and the manual fallback ("bind R4 to F10"). This supersedes the overlay spec's follow-up F-6; note it there.
- [ ] I3.3 Once save-states task 4.0 lands: add L4 = F5 and L5 = F9 (a CLI template change).
- [ ] I3.4 CLI tests: the rendered template, and `install.sh` placing it under a fake HOME. The CLI pytest and ruff gates apply. No goldens (packaging).

## I4. Glyph strip (S-M, about 1 day; after overlay 3E)

- [ ] I4.1 Kenney's CC0 input prompts (Q7) in the overlay atlas, drawn by source name and family. The audit allow-list names the files.
- [ ] I4.2 An `enhance_menu` ctest that draws a glyph for every family against a reference strip.

## I5. Controls page remap (L, about 3 days; after overlay 3D, I2 and I4; folds in overlay 9 / the tracker item)

- [ ] I5.1 The Pad (primary and alternate cells) and Keyboard groups beside 3D.3's Host actions group, with rows from `[input.labels]` (design D9).
- [ ] I5.2 Capture as in design D8:
  - arm after release, and take a single input on its release;
  - cancel by holding Start+Back for 1 s or with Esc;
  - time out after 5 s;
  - Start+Back is never captured as a chord in Host actions; an early release shows "reserved for cancel".
- [ ] I5.3 Conflicts:
  - within a group, Swap (the default) or Cancel; Add only in Host actions;
  - the cross-group prompt for Pad against Host actions, naming the bindings that remain and any chord that changes kind;
  - reset per row and per group.
- [ ] I5.4 Live apply, and Save as differences only (3D.5's `recomp_cfg_patch`). The deliverability check for `menu.open` runs on every live apply, on menu close and on Save. Under Proton's `maybe` with no keyboard seen, it protects the last pad fallback chord.
- [ ] I5.5 The Steam Input line (`on` or `maybe`) and the test strip.
- [ ] I5.6 Overlay 9's checks, done here:
  - rebind `menu.open` from the page to `left_thumb+right_thumb@400`, `guide+b` and `F4`;
  - rebind it to `paddle1` and to a remapped-away Back;
  - each one survives a restart.
- [ ] I5.7 Quick save and load rows (Q12): `state.save` and `state.load` appear once save-states registers them with `[states]` defaults. Add the matching task to the save-states spec.
- [ ] I5.8 `enhance_menu` ctests (design D12): capture; cancel, including Start+Back held in Host actions (never a chord, cancel at 1 s); the cross-group prompt; and the deliverability cases (native Deck-like, Proton `maybe`, desktop). Then a Mac run with a real pad (an Xbox pad, and a DualSense if one is at hand) with `SDL_AUDIODRIVER=dummy`.
- [ ] I5.9 Each game's `config.default.toml` gains `[input.labels]` and its fallback chord: BLiNX 2 here, Burnout 3 and JSRF in their repos. Goldens unaffected (`RECOMP_CONFIG=none`).
- [ ] I5.10 This phase lands before overlay 6, so the Proton and Deck validation covers the remap page.

## I6. SDL3 input on Windows, opt-in (L, about 3.5 to 4 days; after I2; Q1 decided)

- [ ] I6.1 Move the shared SDL code (the slot model, rescan, `sdl_extra`, `sdl_read_pad`) into a file both halves include. The POSIX path changes only by the move. POSIX ctests stay green.
- [ ] I6.2 `_WIN32` SDL path:
  - `LoadLibraryW` and a `GetProcAddress` table (about 25 entry points), with the vendored SDL3 headers for the types;
  - the thread shim (`SRWLOCK`, `CONDITION_VARIABLE`, `QueryPerformanceCounter`);
  - the headless pump (`SDL_INIT_GAMEPAD`, `SDL_HINT_JOYSTICK_THREAD=1`, background events, `SDL_UpdateGamepads` from the poll), and a focus gate that matches XInput.
- [ ] I6.3 `input.backend = "xinput" | "sdl" | "auto"`, defaulting to `"xinput"` for one release. `RECOMP_INPUT_BACKEND` as a config-tier row, with the fallback log line.
- [ ] I6.4 CLI:
  - build SDL3 with llvm-mingw at a pinned release;
  - ship `SDL3.dll` in the Windows bundle, with a NOTICE line;
  - pin `input.backend = "xinput"` in the `steamos` bundle's defaults.
- [ ] I6.5 ctest: a missing DLL falls back to XInput (`tests/proton_run.sh`).
- [ ] I6.6 (needs a Deck or PC slot) A Proton probe with `input.backend = "sdl"`: which devices winebus exposes with Steam Input on and off, and whether paddles or the controller type survive. Record the result. The Proton pin changes only if SDL gains something there.
- [ ] I6.7 Native Windows gate, once the user boots Windows:
  - an Xbox pad and a DualSense on `"sdl"`;
  - Guide through SDL (the D2 claim not verified here);
  - hot-plug and focus behaviour;
  - the D3D11 golden on the default `"xinput"`.
- [ ] I6.8 After one release with player reports, ask the user before flipping the Windows default to `"auto"`.

## I7. Gyro (M, about 1.5 days; later; Q9 decided)

- [ ] I7.1 The `input.gyro*` keys (design D10): enable the SDL sensor, map the rate to a right-stick deflection merged with `PadMerge` (with the 0.41 floor), and add the hold source.
- [ ] I7.2 A ctest with a virtual sensor, and a Mac run with a DualSense.

## I8. Later

- [ ] I8.1 Per-port maps (`[input.pad.portN]`), only if a player asks (S-M).
- [ ] I8.2 Digital sources driving one stick direction, as a fork extension, only if asked (S).
- [ ] I8.3 Upstream, in the release-round re-assessment, each part tested on Burnout 3 on all three hosts:
  - the White = LB default argued for `PadMapDefaults`, and `ApplyStick` passing the stick through at deadzone 0;
  - the `input_host` adapter;
  - `xbox_InputPadFamily`;
  - the SDL3 loader.

## Order at a glance

`overlay 3A merge` -> `I1.2` -> `I2` (beside overlay 3C) -> `overlay 3D` -> `overlay 3E` -> `I4` -> `I5` (with overlay 9) -> `overlay 6`.

- `I3` goes any time after Q4's details are confirmed, and `I3.3` after save-states task 4.0.
- `I6` goes after `I2`.
- `I7` is last.
- `I1.3` waits on linux-native-vulkan.

The total is about 14 to 15 days: I2 4, I3 1, I4 1, I5 3, I6 4, I7 1.5, and I1 under a day.
