## Why

The user (2026-10-30): "I think the shaders tab should have 'profiles', in
which each profile is a combination of shaders in specific order and with
their respective parameters. This means the UI also needs a way to: Add
shaders to the pipeline; Reorder them; Change their individual settings;
Save/Load configurations." the tracker item (this spec).

Today the Shaders page (toolkit b4f60f0c) runs one slang
preset at a time: `present.shader` picks it, and its parameters persist as
`[present.shader_params.<preset>]` in the user config. A player who wants
FSR's sharpening under a CRT mask, or two CRT presets layered, has to write a
multi-pass `.slangp` by hand, and there is no way to keep several tuned looks
and switch between them.

RetroArch has the same shape (Load, Append and Prepend preset, per-pass
rows, Save preset), so this is a known idiom for players who know slang
shaders. librashader 0.12 builds a chain only from a preset file, so a
profile is composed into one `.slangp` and run through the path the
backends already use.

## What changes

- Toolkit (game-agnostic, only with `XBOXRECOMP_ENHANCE`; every game gets
  it):
  - A **shader profile**: a named, ordered list of stages, each a slang
    preset (a bundled name or a `.slangp` path), plus the parameter values
    that differ from the presets'. One TOML file per profile in
    `<root>/config/shader-profiles/<slug>.toml`, beside the user
    `config.toml`, versioned (`version = 1`), human-editable, written by
    the menu with `recomp_cfg_patch_text` so comments and unknown keys stay.
  - New module `src/enhance/shader_profile.{c,h}`: parse, validate,
    serialize, and **compose** a profile into one `.slangp` (passes
    renumbered, paths made absolute and quoted with forward slashes,
    `#reference` wrappers flattened, `parameters` lists merged, the stages'
    textures, aliases and pass-indexed references checked for clashes)
    written to `<save root>/ShaderCache/slangp/<slug>.slangp` through a new
    host-neutral cache-root accessor. A one-stage profile is
    not composed: the stage's preset is run as `present.shader` runs it now.
  - New key `present.profile` (default `"none"`), env row
    `RECOMP_PRESENT_PROFILE`. `present.shader` and
    `present.shader_params` keep working unchanged; the four bundled presets
    become **built-in one-stage profiles**, so the old setting is a profile
    the player never had to create.
  - `nv2a_present_chain` learns profile requests: the active table may span
    several presets (cap raised from 64 to 128 rows), each row tagged with
    its stage by name (from a per-stage describe at compose time), a
    profile error string for failures before any chain exists, and parameter names declared by more than one stage are one
    value (librashader's rule), flagged *shared* in the menu.
  - Menu, Shaders page: a *Profile* picker replaces the *Shader* picker
    (Off, the four built-ins, then the player's profiles). Under it the
    chain, one row per stage; a stage's sub-list holds its parameters, Move
    up, Move down, Remove and Reset to preset; *Add shader* opens a picker
    of bundled and user presets. Profile actions: Save as new, Rename,
    Duplicate, Delete (with the Reset row's confirm). Pad and keyboard use
    the existing events; Rename adds the menu's first text-entry row
    (keyboard typing, a character spinner on the pad).
  - Failure: a profile that does not parse, a stage that is missing, a
    compose clash or a chain that fails to compile gives one `[SHADER]`
    line naming the stage, the stock present, and a red row on the page.
    Nothing is retried until the next change (as today).
  - Descriptor dump: `"shaders"` gains `"profiles"` and `"active_profile"`.
    Schema stays 1 (fields added).
  - ctests: `tests/shader_profile` (parse, serialize, round trip, compose,
    clashes, limits, migration) and new cases in `tests/present_chain` and
    `tests/enhance_menu`.
  - `docs/runtime/config.md`: the profile file, `present.profile`, the page.
- BLiNX 2 (and each game repo at its next pin move): a commented
  `present.profile` row in `packaging/config.default.toml`, a `docs/env.md`
  row for `RECOMP_PRESENT_PROFILE`, the README row, and
  `present.profile = "none"` in the golden's stock keys.

Backends: Metal and D3D11 both run the composed preset through the code
they have; nothing backend-specific beyond what the tracker item has. The CPU
rasteriser and the SDL presenter run no chain (the page stays hidden there),
as today. Hosts: macOS, Windows, the Deck under Proton. Goldens: they run
with `RECOMP_CONFIG=none` and `present.profile` unset, so the frames are
stock; the Metal and Deck D3D11 goldens are still run because the present
path is touched. Upstream: not meant for upstream now (the whole present
chain is fork-only until the upstream re-assessment).

## Out of scope

- Per-pass scale, filter and wrap overrides in the menu. The composed passes
  keep each preset's own; the file format leaves room (design, decision 2).
- Renaming clashing parameters so two stages can hold different values for
  one name (it means rewriting shader sources). They are shared in v1.
- Presets that mods ship (a mod descriptor field for shaders): a follow-up
  once the mod settings work lands.
- Downloading presets or a preset catalogue (ruled it out).
- The CPU rasteriser and the SDL presenter.
