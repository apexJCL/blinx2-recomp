## Why

Every registered mod is already on the mod API (API 8, descriptors everywhere), but the road to it is undocumented and each game found its own. `config.md` has the full rules for each call and no starting point. A mod's game-specific part is reached in five ways with no stated order: C wrappers in `recomp_manual.c`, hook slots, the HUD table, raw `XBOX_MOD_MEM32` on hard-coded addresses, and `names.toml`. The first mod in a game with none must also invent its own frame glue.

The result of the audit:

- Nothing registered is off the API. What's left off it is **game code that drives a mod or acts as one**: wrappers for glow, the free camera and the entity API; Hor+ wrappers that aren't mods at all (BLiNX 2 cull and sea fan, BLiNX 1 sphere and lens flare); `fps.mode` in BLiNX 2's `main.c`.
- Frame glue sits inside mod files (`free_camera.c`, `draw_distance.c`) or is pasted between games (KUF and Auto Modellista's Swap wrappers).
- Three near-identical HUD mod shells (BLiNX 2, KUF, Auto Modellista, with the tracker items next), and `pad_slots.c` copied between BLiNX 1 and 2.

The full table and the hook-point assessment are comments. This change fixes the conventions, ships the docs and the template, and files one tracker item per real migration.

## What Changes

- **Docs (toolkit):** `docs/runtime/mods.md` (contract, what goes where, every call) and `docs/runtime/mod-howto.md` (minimal mod, settings, controls, status panel, hooks, testing), linked from `docs/INDEX.md` and `config.md`.
- **Template (toolkit):** `templates/mod/demo_mod.{c,h}`, a game-agnostic frame counter, off by default, built and run by the new `tests/mod_demo` ctest.
- **Skill (toolkit):** `templates/mod/SKILL.md`, for code-assisted mod authoring.
- **Conventions (this spec):** the game repo layout for mods, what a mod declares, the version contract, the order of ways to reach the game (D4 is the hook-point recommendation).
- **Migrations:** filed as tracker items, one per real migration. None runs in this change.

This change does not alter what any game executes: it adds docs, a template and a test. Each migration that moves a wrapper onto a hook slot does change generated code, and runs the golden gate on its own.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `enhancements`: mods have a documented contract, layout and declaration, and a template that builds on every toolkit test run.

## Impact

- **Toolkit:** docs, `templates/mod/`, `tests/mod_demo/`. No runtime or CMake change. The tracker item works in the same repo's CMake; this change doesn't touch it.
- **CLI:** none now. D4's `name:` hook entries, D5's manifest and D6's feature report are later CLI work, filed as items (overlaps).
- **Games:** none now.
- **Fixed, not reopened:** `src/fixes` stays for stock-game crash fixes, on by default; mods declare info, controls and settings in the menu; present shaders are built in; no generic bloom. BLiNX 2's Bloom mod removes the game's own bloom, and BLiNX 1's equivalent is the tracker item.
