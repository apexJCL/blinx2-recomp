## Mod framework: docs, template, conventions

Worktrees: `wt/mod-framework/xboxrecomp` (`mod-framework/docs` off `posix-host/portability`), `wt/mod-framework/cat` (`mod-framework/spec` off `main`).

Runs and locks: Mac under `~/.recomp-mac.lock`, silent. No game runs.

This change doesn't alter what any game executes, so goldens and Proton don't apply. Each migration below merges on its own, with its own gates.

## 1. Audit and assessment

- [x] 1.1 Table of every mod by game, posted: API version, shared or game-specific, what should move down.
- [x] 1.2 The hook-point assessment, three options and a recommendation, posted.

## 2. Toolkit

- [x] 2.1 `templates/mod/demo_mod.{c,h}`.
- [x] 2.2 `tests/mod_demo/`: off, on, dormant then toggled, setting clamped and delivered, control and its key, dump, hook through a slot and silent while off; builds with no hook and with no API.
- [x] 2.3 `docs/runtime/mods.md`, `docs/runtime/mod-howto.md`, links from `docs/INDEX.md` and `config.md`.
- [x] 2.4 `templates/mod/SKILL.md`.

## 3. Migrations, filed and not done here

The tracker item glow, the tracker item free camera, the tracker item BLiNX 1 Hor+ wrappers, the tracker item frame function, the tracker item HUD shell, the tracker item `pad_slots`, the tracker item `fps.mode`, the tracker item direct reads and `needs`, the tracker item `name:` hook entries. The tracker item already covers BLiNX 2's cull and sea fan. Each states its golden gate.

- [x] 3.1 Filed. Each lands on its own branch through the normal gates; this change closes when they are filed, not when they land.
