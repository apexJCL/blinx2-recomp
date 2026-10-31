Worktrees:
- `wt/<name>/xboxrecomp`: a branch off `posix-host/portability`.
- `wt/<name>/xboxrecomp-cli`: a branch off `main`.
- `wt/<name>/cat`: a branch off `main`.
- The b3 game worktree.

Runs and locks:
- Raw runs go under `xbox-recomp/runs/mod-layer/`.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock`, with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Deck (Proton) jobs go through `blinx2 bench`, which takes the Deck lock itself. Log the slot in `notes/benches.md`.

Every section merges on its own: the gates listed, then a review, then the merge. Review fixes go back to the branch's agent. Efforts are rough agent-days and include the gates.

## 1. Spike (done)

- [x] 1.1 Find and read the 16:9 mods for the four games. Record the technique, addresses, source and licence: `spike.md`, section 1.
- [x] 1.2 Sort the patterns into layer and mod (spike, sections 5 and 6).
- [x] 1.3 Recommend a fix for the tracker item (spike, section 7). Add notes for the tracker items (spike, section 8).
- [x] 1.4 Widen the search: every release of each game, the sibling games, the emulators' widescreen hacks and patch formats, and RenderWare (spike, sections 2 to 4).

## 2. The tracker item first (toolkit, b3; about 2 days)

- [x] 2.1 Run b3 at 16:9 Hor+ on Metal over a crash with `RECOMP_TRACE=aspect`. Find which candidate rect feeds the bars, as native-widescreen task 1.3 does:
  - 0x406A70, 0x4088D0 and 0x406B50 are static `.data` that the game reads, not writes, so `RECOMP_WATCH` (a write watchpoint) cannot see them;
  - poke each in turn with `RECOMP_POKE` (for example its width to 320) and see which bar moves;
  - or trace their readers, `sub_000BEC10`, `sub_000BFCB0` and `sub_000EE710`.
  Record:
  - each bar batch's program hash (or fixed-function), its w values, its texture or render-target size;
  - whether it is full width per triangle, or only as several quads that tile one row;
  - whether it samples an unpadded render target (cause (d), `flat_rt`).
  The reference frames are `runs/hor-plus-fx/b3/host-after/host_07000.bmp` and `host-before/host_05000.bmp`.
  Done (`runs/mod-layer/trace4/`, a per-batch dump armed on the first stretched composite; the poke was not needed):
  - every bar piece is program `1B73FAD1`, at one w of 24.3671875 with depth off, on the padded 640x480 frame;
  - the bars were already full width per triangle, so the tracker item's screen-quad rule stretched them;
  - the edge lines are two half-width quads drawn as separate batches;
  - the list backing samples a 32x32 guest texture;
  - no unpadded target (no cause (d)). See design D5 "Built".
- [x] 2.2 Build the one D5 rule that the trace calls for (band, row cover, or screen layer) in `nv2a_aspect_place`/`nv2a_aspect_scan`. Add a ctest over synthetic batches:
  - a top band and a bottom band (stretched);
  - a mid-screen banner (not a band);
  - a world sprite (not 2D);
  - BLiNX 2's four corner triangles in one batch (their union spans the width, but no triangle does: not full width, per Hor+ H4);
  - a lens-flare quad drawn without depth at one w (stays 3D; the screen-layer form never makes it 2D).
- [x] 2.3 b3: the crash-cam bars and the list backing reach both edges at 16:9 on Metal and D3D11 (Proton). Check the replay bars and loading screens on the same run.
  Metal, after the review fix (`runs/mod-layer/band2/`, toolkit 4cccbd91): the crash-cam bars, lines and backing reach both edges (host_05640, host_06810); the front-end menu frame (host_03000), the loading screen (host_03300) and the race intro (host_03600) keep their 4:3 frame; the race HUD is unchanged. D3D11 under Proton on the Deck (bench-logs 20261022-120854, present dumps every 60 presents in `runs/mod-layer/deck/b3-dump/`): the same, matching Metal frame for frame in layout: the crash-cam bars and the top line reach both edges (frame_0296, frame_0376), and the front-end menu keeps its 4:3 frame (frame_0100).
  Known minor, not blocking: the 1-px marker at x 609 on the crash-cam line reaches no edge, so it stays centred while the raised corner stretches. It still sits on the line. If a player sees it, fold it into the section 3 overrides.
- [x] 2.4 BLiNX 2 Hor+ regression: the Hor+ scenarios at 16:9 on Metal show no newly stretched banner or HUD element.
  Done: story, attract and stage1 at 16:9 hit the band rule 0 times, so nothing new stretches.
  This check covered BLiNX 2 only. It missed Burnout 3's front end, where the first band rule stretched the menu frame's header strips and bottom rule into the pads (review of 7db09a69). The fix takes a band piece only in a third that holds a stretched bar; the b3 front end is now checked under 2.3.
- [x] 2.5 Stock goldens: cat and b3 on Metal, and `blinx2 bench golden` on D3D11 under Proton (the change touches the renderer).
  Metal done: cat story, attract and stage1 pass; b3 has no golden.json, so its stock `race_gate.py` stands in (PASS). Rerun at toolkit 4cccbd91 (the bar rule): cat story, attract and stage1 pass (`runs/mod-layer/cat-golden3`); b3's race gate passes in all four runs of the speed A/B. D3D11 under Proton on the Deck, cat 232472f + toolkit 4cccbd91: `blinx2 bench golden` attract, stage1 and story pass, every pace within ±10% (`runs/mod-layer/deck/golden.log`). The toolkit base moved to 72f00b48 meanwhile (`apu_vp` only); the branch merges with it cleanly.
  Speed at 16:9 on Metal, base 03578754 against 4cccbd91, two rounds each (`runs/mod-layer/ab/`): b3 race 55.5 and 55.3 flips/s; SSX 3 race 50.7 and 54.2 flips/s, noisy in both arms (41.5 to 59.9). No drop.

## 3. `[aspect.*]` overrides (toolkit; moved from native-widescreen tasks 8; about 1 day)

- [ ] 3.1 Parse `[aspect.program]` (by hash) and `[aspect.texture]` (by address, format and size) in the game's `config.default.toml`. Read them only when the aspect is wide.
- [ ] 3.2 Overrides run first in the placement order (design D5).
- [ ] 3.3 Add a ctest, and a `docs/runtime/config.md` entry.
- [ ] 3.4 If 2.2 cannot reach a case, add b3's rows here.
- [ ] 3.5 Gates: the Mac build, `tests/posix_ctest.sh` (0 FAIL), stock goldens for cat and b3 on Metal, `blinx2 bench golden` on D3D11 under Proton, and a b3 Hor+ run under Proton (renderer change).

## 4. Mod API v4 (toolkit; about 3 days)

The design calls these services "v2". The toolkit's `mod.h` reached version 3 first (mod-settings: actions, menu, descriptors), so they land as version 4 (amended by hud-anchors). hud-anchors' fields follow as version 5, or share the bump if both land in one merge.


- [x] 4.1 `struct xbox_mod` gains `needs` and `follows`. `XBOX_MOD_API_VERSION 4`. v1 to v3 tables still work. No `api_min` until dynamic plugins.
- [ ] 4.2 One enable gate for every mod (design D9):
  - `[mods.<name>] enabled` (default false), or a `follows` key whose value differs from that key's default;
  - cat's free camera declares `follows = "camera.free"`, so it is not counted at stock;
  - the refusal lines;
  - a descriptor mod's `XBOX_SET_ENABLE` setting (mod-settings, v3) is its switch, the same switch as `[mods.<name>] enabled`, default off unless the descriptor says otherwise (hud-anchors' `hud` mod defaults on, an exception the user approved on 2026-10-30); a dormant init (switch off, menu on) does not pass the gate for `mods=` (4.9).
- [ ] 4.3 `aspect()` and `pad()` (design D2).
- [ ] 4.4 Probes:
  - `state_probe`, `state_probe_fn` and `state`, sampled by the layer at each flip, in every title (no frame glue needed);
  - `enhance_native_register()` becomes the `wide` probe (native-widescreen D4).
- [ ] 4.5 Pokes:
  - `poke` with HOLD (any length, compared and re-written at each flip) and the expected-value guard;
  - the guard that refuses addresses in executable sections;
  - the `[xbe]` pin check (design D4);
  - the built-in `pokes` mod over `[mods.pokes] entries`.
- [ ] 4.6 `place()` callbacks between the overrides and the generic rules (design D5).
- [ ] 4.7 `rt_dims()` (design D7).
- [ ] 4.8 ctests for each of 4.1 to 4.7, with a stub guest memory and a stub backend. Include a held poke the game overwrote with a value other than the expected one (not re-written).
- [x] 4.9 The `[ENHANCE]` line gains `mods=` (the mods that passed the gate, or `none`; a mod that reports an active state is listed only while it is set, so hud-anchors' default-on `hud` mod stays out of the token at 4:3), and `docs/runtime/config.md` gets a "Mods" section. This lands before the CLI requires the token (5.7).
- [ ] 4.10 Move `fx.glow` (`sub_0005B7D0`) onto cat's mod table (free-camera spike §6.4 step 1), behind the same gate.
- [ ] 4.11 Gates: the Mac build, `tests/posix_ctest.sh` (0 FAIL), `pytest tools/recomp tools/disasm` if the tools changed, stock goldens for cat and b3 on Metal (they must print `mods=none`), `blinx2 bench golden` on D3D11, and a Proton run (runtime change).

## 5. Hook slots (CLI, toolkit runtime; free-camera D7; about 3 days)

- [x] 5.1 `manifest.py`:
  - the `[mods]` table: `hook_functions` (VA strings or `sig:<name>`);
  - `[mods.signatures]` (name to pattern and section);
  - `docs/manifest.md`.
- [x] 5.2 `analyze`:
  - resolve each signature to exactly one VA in its section, and fail otherwise;
  - fail when a listed VA also has a hand-written override in `recomp_manual.c`;
  - record each VA's `ret_pop` (from its `ret imm16`) and whether it returns on the x87 stack;
  - write `config/hook_functions.json`;
  - the gen key includes the list.
- [x] 5.3 `recomp`: emit the pre and post dispatch around each listed function (design D3). A pytest checks that the generated code is byte-identical to a build without `[mods]` when the list is empty.
- [x] 5.4 The toolkit runtime: the `recomp_hook_*` table, and `hook()` in the API (design D3). ctests for:
  - the pre order and the reverse post order;
  - ecx and edx seen at entry (a fastcall stub);
  - post callbacks seeing the entry `esp`;
  - a skip from a `XBOX_MOD_HOOK_MAY_SKIP` hook on a `ret 0x14` function (the stack balanced after) and on a function returning st0;
  - a second may-skip hook on one VA refused at init, and a skip without the flag ignored;
  - the refusal when a slot is missing.
- [x] 5.5 The CLI's golden token: `golden.py` adds `("mods", ..., "none")` to `ENHANCE_STOCK`, and `manifest.TOOLKIT_ENHANCE_KEYS` gains `mods` (the CLI's `tests/test_manifest.py` checks they agree). Only after the toolkit from 4.9 is pinned in every game.
- [x] 5.6 CLI gates: `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`. Merge the CLI, then bump the `[cli]` pin in each game before it lists `hook_functions`. Stock goldens of a game built with a non-empty list (cat, after 6.1) prove the empty branch.

## 6. Proof: `blinx2-wide-cull` (cat; about 2 days)

- [ ] 6.1 `game.toml` `[mods] hook_functions = ["0x0003B180", "0x00215A40"]`. Then run `blinx2 analyze` and `blinx2 recomp`, never a hand edit.
- [ ] 6.2 `src/mods/wide_cull.c`:
  - the `sub_0003B180` cull scale and the `sub_00215A40` sea-fan scale, moved from `recomp_manual.c` onto `hook()`;
  - `follows = "display.aspect"`;
  - remove the two hand-written wrappers.
- [ ] 6.3 Move the `[HORCULL]` logging and its `cam_log` row with the cull, and the `RECOMP_DISPLAY_ASPECT` row in `docs/env.md`. The mod never runs at 4:3, so `[HORCULL]` at 4:3 is lost: either keep a 4:3 log line in the game, or record the loss in `docs/env.md`.
- [ ] 6.4 `[HORCULL]` behaviour unchanged at 16:9: the scenarios and the far-sea check.
- [ ] 6.5 Stock goldens: Metal and D3D11 (`blinx2 bench golden`), and a Proton Hor+ run.
- [ ] 6.6 Cat gates: `uv run pytest scripts`, and the ruff check and format. Add `scripts/test_*` cases for the `[mods]` keys.

## 7. Later, on evidence

- [ ] 7.1 The stock D3DX `PerspectiveFovLH`/`RH` signatures (design D3). Check them against SSX 3 USA (`sub_00249633`), BLiNX 2, and b3 if it links D3DX. This can fail: the code may differ by XDK version, and then the table gains a row per version, or the mod names the VA. Only when a mod needs a projection hook.
- [ ] 7.2 Design D6 (a native-mode 2D squeeze), only if native-widescreen 1.3 shows b3 or SSX 3 leave the HUD unsqueezed in native mode.
- [ ] 7.3 The Lua-class assessment (design D10), once `pokes`, `blinx2-wide-cull` and the free camera exist. This change only gives it input.
- [ ] 7.4 Pin the JSRF projection (`sub_001BAF70`, the view builder the `.JMP` patch changes), only if a JSRF mod or bug needs it.
- [ ] 7.5 Locate RenderWare's `RwCameraSetViewWindow` in b3 and add it as a stock RW signature, only if an RW-generic hook is wanted (spike, section 4).
- [ ] 7.6 An automatic `wide` probe in Dolphin's style (design D8), only if a game with a native mode has no probe.

## 8. After each merge

- [ ] 8.1 Copy the notes to `notes/<name>/` and update `TASKS.md`.
- [ ] 8.2 Merges that touch the renderer, the runtime or generated code (sections 2 to 6): sync the Deck and run `blinx2 bench integrate --golden`.
