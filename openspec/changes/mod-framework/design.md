## Context

`mod.h` at the toolkit tip is API 8, descriptor 2. Public `blinx2-v0.14.0` is API 8, descriptor 1: the mod API here, except `XBOX_SET_LINK`, is there. The tracker item moves JSRF, SSX 3 and Quantum Redshift onto it, so every active game has that API. Spartan stays parked on v0.7.0 (API 3).

The rest is newer than that tag. `[pipeline] names`, `XBR_VA` and `XBR_HAVE` need CLI v0.21.0 and a toolkit `recomp` with `--names` (toolkit 09c6283f, on the integration branch, in no public tag yet). `recomp` stops and says so on an older toolkit, so a game on those pins builds with a local toolkit or uses plain addresses until the next round. The docs, template and test come with this change.

`mod-connectivity-layer` stays open for what it designs (aspect, probes, pokes, place, the enable gate). This change doesn't redo that. It documents what exists and sets the conventions around it. Where the two meet: the `needs` gate (its 4.2) is still undone, so `needs` remains a declaration.

## Decisions

### D1. Where a mod's code lives

```
<game>/
  src/mods/<id>.c            the mod: guard, descriptor, init, accessor
  src/mods/<id>.h            const void *<id>_mod(void);
  src/mods/<id>_logic.{c,h}  pure logic: no guest access, no toolkit, unit tested
  src/fixes/                 stock-game crash fixes, unchanged
  config/names.toml          addresses by release, when the game has it
  config/hud.toml            a HUD mod's table
  game.toml [mods]           the hook slots the mods use
```

The flat `src/*_mod.c` in BLiNX 1 and 2 predates this. New mods use `src/mods/`, and the migration moves the old ones when it next touches them; a rename alone isn't worth a commit. A mod with several files takes `src/mods/<id>/`.

*Rejected: a `mods/` tree at the repo root.* It reads like a drop-in plugin directory, which it isn't (is where that gets decided).

### D2. What a mod declares

As const data, readable before any code runs:

- **Who:** `name` (the id), `desc.title`, `summary`, `author`, `version_text`.
- **Settings:** every value a player may want. One `XBOX_SET_ENABLE` setting, default off, except for a mod that does nothing on a stock setup (`hud`, `glow`).
- **Controls:** every key, with defaults, rebindable.
- **Needs:** `XBOX_MOD_NEED_*`, ORed. A declaration until the enable gate lands, but the gate can't land on bad data: `diag_clamp` and `draw_distance` touch guest memory and declare nothing.
- **Hooks:** in `game.toml [mods] hook_functions`, for now. D5 moves them next to the mod.

Not in the declaration: config read through `recomp_env` or `cfg_*`. Four BLiNX 2 mods read `recomp_env` directly for debug rows; that's a migration item.

### D3. The version contract

- Source contract, not a plugin ABI: a mod is compiled against the toolkit its game pins. The fields of `xbox_mod_api` and `xbox_mod_desc` are only added.
- A mod's guard names **the newest member it uses**. The audit compared each guard to what its mod calls, and they already agree, apart from `free_camera`, which guards at 6 and treats the v7 panel as optional behind a size check. That's the convention's one allowed form: a guard lower than a member the mod can run without.
- Below the guard, the accessor returns NULL and the game still builds. That's what lets a game move toolkit pins without touching its mods.
- `api->size` checks are needed for a member above the guard (the case above) and asked for by `config.md` on `glyph_name` and `status`; otherwise they're unneeded while mods are linked in, so `fdm` and `glow` having none isn't a bug. If the tracker item ever brings a loader, it needs its own ABI; this contract doesn't stretch to it.

### D4. How a mod reaches the game (the recommendation)

The options assessed in full:

| | A: C wrappers in `recomp_manual.c` | B: declared hook slots | C: per-mod manifest |
|---|---|---|---|
| Where the point is declared | `sub_X` in the game's manual file | `game.toml [mods] hook_functions` | `src/mods/<id>.toml`, merged by the CLI |
| Follows mod state | No: always in the path, tests its own state | Yes: silent while off | Yes |
| Several mods on one function | No: one owner, hand-chained | Yes: pres in table order, posts in reverse | Yes |
| Checked at generation | That the function has a body to wrap (`recomp` stops, naming it) | Function start, `ret n`, x87; single owner against address forms only (`XBR_GEN` wraps are missed) | Same as B |
| Other releases | Address in a C name, or `XBR_FN`/`XBR_GEN` with a `names.toml` row | VA or `sig:` places the slot; the mod's `api->hook` needs `XBR_VA` and a `names.toml` row too | Per-release rows, once in one file |
| Regeneration | Stable by name; a new one needs `recomp` to emit its `_gen` | Stable; a new one stales `gen/` through the generation key | Same as B |
| Can bracket, read the caller's frame | Yes | Pre, post, args, return, skip; no mid-function site | Same as B |
| Exists now | Yes | Yes: BLiNX 2, KUF, Auto Modellista | No |

**Decision: B is the documented default. A stays as the named escape hatch. C-lite comes later, only for what B makes awkward.**

- Order for a new mod: frame + memory, hook slot, HUD table, `guest_call`, wrapper. The how-to and the skill both say so.
- A wrapper stays right for frame glue itself, and for the few sites a pre/post can't express. It keeps to a single call into the mod's file, and its comment says why it isn't a hook.
- `symbols.toml` stays documentary. Hooks are address-keyed by design, and a rename must not change lifted code.
- Addresses come from `config/names.toml` (per release, with `XBR_HAVE` guards). A later CLI change lets `hook_functions` take `name:<symbol>` too, so one file holds a game's addresses (filed).
- Mid-function sites stay out of scope: the wrappers that need them are the argument for keeping A at all. The tracker item's pokes and probes are separate.

Regeneration, concretely: a mod over a hook needs no change when `gen/` is rebuilt, as long as the function is still there. If the function start moves, both forms stop with a named error: `analyze` on the hook entry, `recomp` on the wrapper (`tools/recomp/__main__.py`). So early failure isn't what separates them. Slots add the `ret n` and x87 checks, the ownership check, and silence while the mod is off.

Other releases, concretely: a `sig:` entry only places the slot. The mod still passes a VA to `api->hook`, so a second release also needs a `names.toml` row and `XBR_VA(name)`. That's why a `name:` entry would be worth having: one row would do both.

Moving a wrapper onto a slot changes generated code: the golden gate applies per migration, with mods off.

### D5. C-lite manifest, later

`src/mods/<id>.toml` would hold the mod's hook entries and name rows, and the CLI would merge them into the generation inputs. Worthwhile when a game has enough mods that `game.toml [mods]` no longer says which mod owns which slot, or when a mod moves between games. Not now: BLiNX 2 has 16 slots, and a comment does the job. It belongs with the tracker item's `mod new` and `mod hooks`, and the tracker item may subsume it. Noted there, not filed separately.

### D6. Shared layer first

"The CLI reports a shared feature missing from a game" needs a list of shared features and a way to see a game's copy of one. Filed under the tracker item's namespace rather than designed here. Candidates to move down, from the audit: the HUD mod shell (three near-identical `init`s plus the CMake that embeds `hud.toml`), frame glue as a declared function, `free_cam_fly`, `pad_slots`.

### D7. Docs, template and skill

- **`docs/runtime/mods.md`** is a map. `config.md` keeps the long rules, since every link into it would otherwise rot; the map links to its sections.
- **`docs/runtime/mod-howto.md`** walks through the template.
- **`templates/mod/demo_mod.c`** counts frames, the one thing every game has. It needs no address. It shows a descriptor, a setting, a control, a panel, `on_enable`, `on_setting` and, under `DEMO_MOD_HOOK_VA`, a hook. `tests/mod_demo` builds this exact file, so the how-to can't drift from the API without a failure.
- **`templates/mod/SKILL.md`** goes with the template, in the toolkit, because that's where the versions it describes live: a game reads it at its own pin. A game that wants it auto-loaded copies it to `.claude/skills/xbr-mod/`, and `mod new` will do that. I don't copy it per game now: a copy goes stale, and the game repos are exported publicly.

*Rejected: a demo with a real effect (camera shake, tint).* An effect needs game addresses or a toolkit-side renderer change, and either defeats the point.

## Risks

- **A mod author reaches for a wrapper anyway**, because existing games have many. The how-to names the cost, and the migrations remove the example over time.
- **`needs` stays unread** until the gate lands, so nothing enforces it. Accepted: the tracker item carries the gate.
- **Hook slots can't cover everything the free camera does.** It reads a caller's return address and swaps state around view builds. Its item starts with the six `cam_build` wrappers that are pure pre/post, and the rest stay until shown otherwise.

## Open Questions

None blocking. For the user: whether the tracker item's drop-in format should absorb D5, decided when that spike runs.
