Each group is one toolkit branch off `posix-host/portability` in its own
worktree, merged on its own; the cat tasks go on a cat branch after the
toolkit pin moves. Gates per group are in section 7.

## 1. Probe (no code merged)
- [ ] 1.1 Scratch probe against the bundled librashader 0.12 on macOS and
      Windows: a hand-composed `fsr` + `crt-lottes` preset and a
      `crt-lottes-fast` + `crt-hyllian` preset (shared `MASK_INTENSITY`).
      Record what `libra_preset_get_runtime_params` reports for the shared
      name (which range and default win), that `set_param` moves both
      passes, and the first-build time of a 3-pass chain. Also
      `fsr` + `crt-hyllian`: crt-hyllian sets `InputSize` from
      `OriginalSize`, the game frame, so record how its scanlines look
      after the scaled picture (D3, *Original*). Post on the tracker item and amend
      design D3 if it differs.

## 2. Profile module (toolkit, no GPU)
- [ ] 2.1 `src/enhance/shader_profile.{c,h}`: the profile struct, parse
      (version, name, stages, `[params.<key>]`), limits, slugs, the
      unknown-key report; stage resolution (`shader_profile_stage_path`:
      bundled, `user:<stem>`, `<root>/shaders/` before the exe dir, bundled
      stem clash refused); `enhance_cfg_user_dir` for `<root>/config`;
      `docs/runtime/config.md` gets the file format
- [ ] 2.2 Serialize through `recomp_cfg_patch_text`: differences only,
      comments and unknown keys kept, atomic write, rename, delete; shared
      values read from any stage's table and saved under the current owner
- [ ] 2.3 The `.slangp` reader (`#reference` with depth and cycle checks,
      per-pass and texture keys, `parameters` lists) and the composer
      (renumbered passes, quoted absolute forward-slash paths, merged
      textures, `parameters` lists merged without duplicates, earlier stage
      wins a parameter value, alias and texture clash refused,
      `PassOutputN`/`PassFeedbackN` in a later stage refused, `Original` in
      a later stage flagged, pass cap) writing
      `<cache root>/slangp/<slug>.slangp`, with `xbox_path_shader_cache`
      as the host-neutral cache root (the D3D11 dxbc cache moves onto it)
- [ ] 2.4 ctest `tests/shader_profile`: the D10 parse, serialize, compose
      and limit cases, against copies of the bundled presets
- [ ] 2.5 ctest `tests/present_chain_lrs`: skips when librashader is not
      found; else composes `fsr` + `crt-lottes`, calls
      `nv2a_present_chain_describe` on the composed file and expects 17
      parameters (4 and 13 per stage)

## 3. Store (toolkit)
- [ ] 3.1 `nv2a_present_chain`: profile requests (slug, composed path,
      each stage's parameter names from `nv2a_present_chain_describe` at
      compose time), `NV2A_PRESENT_PARAMS_MAX` 128, stage index and shared
      flag on published rows tagged by name, the profile error string,
      override scopes (preset, profile)
- [ ] 3.2 Metal and D3D11: no logic change; check both publish through
      the widened table and present a composed preset (same commit, both
      backends, per "backends agree")
- [ ] 3.3 `tests/present_chain` cases: profile request, 128 rows, stage
      and shared flag by name, the profile error string, scopes;
      `fake_lrs.c` reports a composed preset's parameters (the real-library
      check is 2.5)

## 4. Config and resolution (toolkit)
- [ ] 4.1 Key `present.profile` and env row `RECOMP_PRESENT_PROFILE`
      (`recomp_env.h` config tier, `enhance_cfg_bind_env`)
- [ ] 4.2 `xbox_enhance_init`: resolve the request in the D7 order (env,
      then the highest config layer that sets either key, read per layer
      through `enhance_cfg_file`), read only the named profile file, log
      one line for what won and why; profile values loaded into the profile
      scope. The folder is listed lazily when the Shaders page opens
- [ ] 4.3 ctest cases for D7 (`present.shader` only, profile only, both,
      env over config, missing profile gives stock, the highest layer
      wins, `"none"` in a layer stops a lower one, `RECOMP_CONFIG=none`
      reads no profile, a stock start opens no profile file)

## 5. Menu (toolkit)
- [ ] 5.1 Profile picker in place of the Shader item (built-ins, user,
      broken and newer skipped); saves `present.profile` or
      `present.shader` as D5 says, writing `"none"` where a lower layer
      sets the key
- [ ] 5.2 Chain rows: notes, Left/Right move, X remove with confirm, last
      stage kept; built-in edit forks to "<name> custom"
- [ ] 5.3 Add shader picker (bundled, `<root>/shaders/*.slangp`), parse
      and clash check before adding, limits dimmed
- [ ] 5.4 Stage sub-list: info, parameter rows with the shared note, Move
      up/down, Remove, Reset this stage
- [ ] 5.5 Save as new, Duplicate, Delete with confirm (the file and the
      `present.profile` key removed at once)
- [ ] 5.6 `R_NAME` text entry as a modal `name_step` beside
      `capture_step` that swallows the mapped events: keyboard typing (US
      layout table) and pad spinner, name and slug checks; Rename
- [ ] 5.7 Save: changed profiles written, unsaved count, Reset to defaults
      leaves files; failure rows (broken, building, failed stage) read
      from the store's profile error
- [ ] 5.8 Descriptor dump: `active_profile`, `profiles`
- [ ] 5.9 `tests/enhance_menu` cases for 5.1 to 5.8
- [ ] 5.10 `docs/runtime/config.md`: the page, the keys, the limits

## 6. Game repos
- [ ] 6.1 cat: `packaging/config.default.toml` commented `present.profile`
      row, `docs/env.md` row for `RECOMP_PRESENT_PROFILE`, README row,
      `present.profile = "none"` in `game.toml` `[golden] enhance_stock`,
      a `scripts/test_*.py` case for the key
- [ ] 6.2 The other games (BLiNX 1, Burnout 3, JSRF, SSX 3) at their next
      toolkit pin move: the same config row and docs; `sh
      notes/build-all.sh` shows all of them building

## 7. Gates (per CLAUDE.md, for each toolkit merge)
- [ ] 7.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`),
      `tests/posix_ctest.sh <build-dir>` 0 FAIL
- [ ] 7.2 cat: `uv run pytest scripts`, `uv run ruff check . && uv run
      ruff format --check .`
- [ ] 7.3 Metal golden; D3D11 golden on native Windows with the exe built
      on the PC (Deck golden under Proton after, non-blocking)
- [ ] 7.4 By hand on Metal and D3D11: Off equals stock; a built-in equals
      the same `present.shader` run; `fsr` + `crt-lottes` runs on both;
      a broken stage gives stock and the red row; pad and keyboard drive
      every D5 action
- [ ] 7.5 `sh notes/build-all.sh` with `TOOLKIT=<worktree>` before the
      toolkit merge
- [ ] 7.6 Review of each merge; its fixes go back to the branch's
      agent
- [ ] 7.7 CPU backend: builds; page hidden; no follow-up needed beyond a
      TASKS.md line if it is not

## 8. Follow-ups (not in this change)
- [ ] 8.1 File a tracker item: Add shader lists presets that mods ship
      (a descriptor field), after the mod settings work
- [ ] 8.2 After the measurements, decide whether the Deck gets a
      lower pass cap than 16
