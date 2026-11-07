# Reset statics (cat)

Every piece of mutable C state in cat's own sources, classified for the
in-window game reset (openspec change `game-reset`, D5 and D6). The
toolkit's own state is in the toolkit's `docs/reset-statics.md`, with the
class rules. Generated code (`src/recomp/gen/`) is left out: its state is
guest RAM and the toolkit's register file, plus three host statics the
toolkit's generator owns (`g_flat_table`, `s_hook_slots_gen` and the
unresolved-stub log guard).

Check it with the toolkit's scanner:

    python3 <toolkit>/tools/reset_statics.py check --doc docs/reset-statics.md --exclude src/recomp/gen/ . src

Classes are the toolkit's: **keep** survives the reset, **reset** returns
to its start value, **constant** is the same on every boot. For a reset
row the hook is `game` (cat's band 12 hook) or `mods` (the mod's D6a
`on_reset`). Debug-harness state behind a DEBUG-tier key is keep: D7 rule 1
refuses a reset while such a key is set.

322 objects: 194 keep, 123 reset, 5 constant.

## Findings that change the plan

1. **`cat_pad_early_init` is host setup, not guest state.** It is
   `init_once()` (src/pad_input.c:1195-1198, guard `done` at :1117): it parses
   the script, sets `xbox_FileOpenHook`, calls `xbox_InputInit` and builds the
   slot map. On a second call it does nothing. D6 names it the game's
   `game_boot`, but re-running it resets nothing. It belongs in the host half.
   What the game hook actually needs is a new `cat_pad_reset()`, which zeroes
   `g_last`, the `trace_handles` `last[]` and `g_rumble_last`, and sends 0/0
   rumble to every host pad that holds a port.
2. **The init-flag patch clears bit 0 (`&= ~1u`, XINIT_MOUNT_UTILITY_DRIVE),
   not bit 1** (src/main.c:1284-1292). It writes the XBE header in guest RAM,
   so it must run again after band 8 reloads the image.
3. **The guest runs on the host_main thread.** `xbe_entry_point()` is called
   directly from `host_main` (src/main.c:1336). That makes this thread's
   RECOMP_TLS register file (`g_esp` and the rest, toolkit-owned) and cat's
   own TLS (`t_in_hook` in ent_api.c:133 and shop_api.c:100) live on a thread
   that the reset may reuse.
   - If the reset re-enters the guest on that same thread, a hook interrupted
     by the stop leaves `t_in_hook = 1`. A mod's on_reset, run on another
     thread, cannot clear it.
   - The toolkit must start the guest on a fresh thread, or zero these on the
     entry thread before `game_boot`. Possible approach: an
     `xbox_mod_api` "thread reset" callback, or simply a fresh thread.
4. **Hook-nesting and in-flight state is the most common hazard.** A guest
   stopped inside a hook leaves a flag set:
   - `s_q.active` in collision_mod.c and walls_mod.c;
   - `s_depth` in crystals_mod.c;
   - `s_cam_depth` in recomp_manual.c:638;
   - the spin lock `s_lock` in ent_api.c:109.
   Each one must be zeroed. A kept `s_cam_depth > 0` silently disables the
   camera swap; a kept `s_lock` deadlocks the menu.
5. **"Remember what I wrote" state must reset without a write-back.** Three
   mods record what they wrote into the old image:
   - lod_scale `s_state`;
   - shop_api `s_written`, `s_before` and `s_game`;
   - free_camera `s_fz`.
   After band 8 the image is stock again. If the state is kept, the mod
   either never re-applies its change (LOD_SAME or LOD_FOREIGN) or writes a
   stale restore into the fresh image (`fc_freeze_stop`, `put_stock`).
   on_reset must zero this state, and must not call the mods' shutdown or
   stop paths.
6. **guest_alloc blocks** (crystals `s_block`, walls `s_block`, ent_api
   `s_rec_va`) point into RAM that band 7 has cleared. Zeroing them only
   works if the toolkit also rewinds the guest_alloc arena in band 7. The
   arena is never freed today (mod.h:416), so without that rewind each
   reset leaks a block.
7. **`s_guest`** (ent_api.c:131, shop_api.c:98) caches `&t_marker` of the
   guest thread. If the guest is restarted on a new thread, the "on the
   guest thread" test fails until this is cleared.

## The objects

### src/collision_logic.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/collision_logic.c | col_query | stack | local_static | keep | - | scratch, rewritten on every call |

### src/collision_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/collision_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/collision_mod.c | - | s_on | file_static | keep | - | setting, toggle, action id |
| src/collision_mod.c | - | s_shown | file_static | keep | - | setting, toggle, action id |
| src/collision_mod.c | - | s_act_toggle | file_static | keep | - | setting, toggle, action id |
| src/collision_mod.c | - | s_frame | file_static | keep | - | mod frame counter and the frame last selected; monotonic, valid across a reset |
| src/collision_mod.c | - | s_sel_frame | file_static | keep | - | mod frame counter and the frame last selected; monotonic, valid across a reset |
| src/collision_mod.c | - | s_drew | file_static | keep | - | whether the host 3D layer holds a drawing (host) |
| src/collision_mod.c | - | s_viewed | file_static | reset | mods | per-frame view bookkeeping; on_reset: 0 |
| src/collision_mod.c | - | s_view_calls | file_static | reset | mods | per-frame view bookkeeping; on_reset: 0 |
| src/collision_mod.c | - | s_view_max | file_static | reset | mods | per-frame view bookkeeping; on_reset: 0 |
| src/collision_mod.c | - | s_v | file_static | reset | mods | view and projection read from the guest; on_reset: zero |
| src/collision_mod.c | - | s_p | file_static | reset | mods | view and projection read from the guest; on_reset: zero |
| src/collision_mod.c | - | s_stage | file_static | reset | mods | the stage collision baked from guest RAM; on_reset: s_stage.key = 0, s_stage.n = 0 (as on_enable does) |
| src/collision_mod.c | - | s_mark | file_static | keep | - | selection stamps (scratch) |
| src/collision_mod.c | - | s_stamp | file_static | keep | - | selection stamps (scratch) |
| src/collision_mod.c | - | s_sel | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_nsel | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_fv | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_ev | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_nf | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_ne | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_last_tris | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_last_edges | file_static | reset | mods | derived from s_stage; on_reset: counts 0 |
| src/collision_mod.c | - | s_q | file_static | reset | mods | the query in flight; a guest stopped between query_pre and query_post leaves active = 1; on_reset: 0 |
| src/collision_mod.c | - | s_contact | file_static | reset | mods | on_reset: valid = 0 |
| src/collision_mod.c | - | s_hit | file_static | reset | mods | on_reset: valid = 0 |

### src/crystals_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/crystals_mod.c | - | cry_api | global | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/crystals_mod.c | - | cry_stats | global | reset | mods | pickup counters of the run; on_reset: zero |
| src/crystals_mod.c | - | s_on | file_static | keep | - | setting |
| src/crystals_mod.c | - | s_block | file_static | reset | mods | a guest_alloc block in the cleared guest RAM; on_reset: 0, so the next use allocates again (needs the toolkit to reset the guest_alloc arena in band 7) |
| src/crystals_mod.c | - | s_depth | file_static | reset | mods | hook nesting; a guest stopped inside a hook leaves them set; on_reset: 0 |
| src/crystals_mod.c | - | s_active | file_static | reset | mods | hook nesting; a guest stopped inside a hook leaves them set; on_reset: 0 |
| src/crystals_mod.c | - | s_item | file_static | reset | mods | the pickup and held crystals read from the guest; on_reset: zero |
| src/crystals_mod.c | - | s_pick | file_static | reset | mods | the pickup and held crystals read from the guest; on_reset: zero |
| src/crystals_mod.c | - | s_held | file_static | reset | mods | the pickup and held crystals read from the guest; on_reset: zero |
| src/crystals_mod.c | - | s_icon | file_static | reset | mods | slot icons drawn this frame; on_reset: 0 |
| src/crystals_mod.c | - | s_nicons | file_static | reset | mods | slot icons drawn this frame; on_reset: 0 |
| src/crystals_mod.c | - | s_drawing | file_static | reset | mods | slot icons drawn this frame; on_reset: 0 |
| src/crystals_mod.c | - | s_new_frame | file_static | reset | mods | slot icons drawn this frame; on_reset: 0 |
| src/crystals_mod.c | - | s_tex | file_static | reset | mods | guest texture and row values; on_reset: 0 |
| src/crystals_mod.c | - | s_row_rec | file_static | reset | mods | guest texture and row values; on_reset: 0 |
| src/crystals_mod.c | - | s_row_player | file_static | reset | mods | guest texture and row values; on_reset: 0 |

### src/crystals_proof.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/crystals_proof.c | - | cry_proof_out | global | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_mod | file_static | keep | - | the owner mod pointer (host) |
| src/crystals_proof.c | - | s_frame | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_play | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_seg_play | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_seg_mission | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_playing | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_spawned | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_seg_first | file_static | keep | - | proof run trackers; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_at | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_every | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_dup | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_rew | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_kill | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | o_seq | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_last | file_static | keep | - | proof diff baseline; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/crystals_proof.c | - | s_last_misc | file_static | keep | - | proof diff baseline; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |

### src/debug_menu.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/debug_menu.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/debug_menu.c | - | s_on | file_static | keep | - | setting, action id |
| src/debug_menu.c | - | s_req | file_static | reset | mods | a pending open for the old boot; on_reset: 0 |
| src/debug_menu.c | - | s_cursor | file_static | reset | mods | the title's cursor and state last frame; on_reset: -1 and UINT32_MAX |
| src/debug_menu.c | - | s_state | file_static | reset | mods | the title's cursor and state last frame; on_reset: -1 and UINT32_MAX |
| src/debug_menu.c | - | s_open_action | file_static | keep | - | setting, action id |

### src/ent_api.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/ent_api.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/ent_api.c | - | s_owner | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/ent_api.c | - | s_on | file_static | keep | - | settings |
| src/ent_api.c | - | s_scale | file_static | keep | - | settings |
| src/ent_api.c | - | s_proof_kill_any | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/ent_api.c | - | s_area_setups | file_static | reset | mods | area setups seen; on_reset: 0 |
| src/ent_api.c | - | s_hp | file_static | keep | - | settings |
| src/ent_api.c | - | s_lock | file_static | reset | mods | spin lock any thread takes; a guest thread stopped while holding it would deadlock the menu; on_reset: 0 (guest gone, nothing else holds it at band 11) |
| src/ent_api.c | - | s_ring | file_static | reset | mods | queued spawn/kill requests for the old world; on_reset: s_n = 0 |
| src/ent_api.c | - | s_n | file_static | reset | mods | queued spawn/kill requests for the old world; on_reset: s_n = 0 |
| src/ent_api.c | - | s_hp_state | file_static | reset | mods | the HP patch's record of what it wrote into the old image; on_reset: zero, so the fresh image is patched again |
| src/ent_api.c | - | s_rec_va | file_static | reset | mods | guest_alloc block; on_reset: 0 |
| src/ent_api.c | - | s_alloc_failed | file_static | reset | mods | on_reset: 0 |
| src/ent_api.c | - | s_leaked | file_static | reset | mods | on_reset: 0 |
| src/ent_api.c | - | s_stale_logged | file_static | keep | - | log once |
| src/ent_api.c | - | s_spawned | file_static | reset | mods | on_reset: 0 |
| src/ent_api.c | - | s_sweep | file_static | reset | mods | record sweep state; on_reset: 0 |
| src/ent_api.c | - | s_stale_pending | file_static | reset | mods | record sweep state; on_reset: 0 |
| src/ent_api.c | - | s_sweep_frames | file_static | reset | mods | record sweep state; on_reset: 0 |
| src/ent_api.c | - | s_rew_frames | file_static | reset | mods | record sweep state; on_reset: 0 |
| src/ent_api.c | - | s_kills | file_static | reset | mods | pending kill waits; on_reset: s_nkills = 0 |
| src/ent_api.c | - | s_nkills | file_static | reset | mods | pending kill waits; on_reset: s_nkills = 0 |
| src/ent_api.c | - | s_guest | file_static | reset | mods | &t_marker of the guest thread, the 'am I on the guest' test; on_reset: NULL, set again at the first hook of the new boot (the guest thread may be a new thread) |
| src/ent_api.c | - | t_marker | tls | keep | - | only its address is used |
| src/ent_api.c | - | t_in_hook | tls | reset | mods | set on the thread that was in a hook; if the guest re-enters on the same thread, it must be 0: on_reset cannot reach another thread's TLS, so the toolkit's band 2 must not reuse a thread stopped inside a hook, or the hook clears it on exit by a reset-safe path |

### src/entities_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/entities_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/entities_mod.c | - | s_on | file_static | keep | - | setting, action ids |
| src/entities_mod.c | - | s_req_spawn | file_static | reset | mods | pending requests; on_reset: 0 |
| src/entities_mod.c | - | s_req_kill | file_static | reset | mods | pending requests; on_reset: 0 |
| src/entities_mod.c | - | s_last | file_static | reset | mods | the last answer about the old world, shown by the menu; on_reset: -1, 0 |
| src/entities_mod.c | - | s_last_kill | file_static | reset | mods | the last answer about the old world, shown by the menu; on_reset: -1, 0 |
| src/entities_mod.c | - | s_act_spawn | file_static | keep | - | setting, action ids |
| src/entities_mod.c | - | s_act_kill | file_static | keep | - | setting, action ids |
| src/entities_mod.c | - | s_out | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_spawn | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_fill | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_kill | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_rew | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_spawnrew | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_tc | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_tcreq | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_rewarea | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_from | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_keep | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_atsrc | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_tcdur | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | o_setuponly | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/entities_mod.c | - | s_area_setups | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_frame | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_play | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_area_frame | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_area_key | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_playing | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_filling | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_fill_wait | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_area_changed | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |
| src/entities_mod.c | - | s_proof_h | file_static | reset | mods | play and area trackers of the old boot; on_reset: zero (cheap, though only the proof reads most of them) |

### src/fdm_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/fdm_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/fdm_mod.c | - | s_on | file_static | keep | - | setting |
| src/fdm_mod.c | - | s_scaled | file_static | reset | mods | whether the guest's speed table holds the scaled max; the reload puts the XBE's table back, so on_reset: 0 without writing the guest |
| src/fdm_mod.c | - | s_base | file_static | reset | mods | the table's max before the scale (with s_scaled); on_reset: zero |
| src/fdm_mod.c | - | s_last_g | file_static | reset | mods | the last walk's factor, shown by the menu; on_reset: 1000 |

### src/free_camera.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/free_camera.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/free_camera.c | - | s_on | file_static | keep | - | setting, action ids |
| src/free_camera.c | - | s_flying | file_static | reset | mods | flight state over the old camera; on_reset: stop flight without writing the guest (the image is fresh) |
| src/free_camera.c | - | s_cam | file_static | reset | mods | camera seeded from the guest; on_reset: zero |
| src/free_camera.c | - | s_fz | file_static | reset | mods | the freeze record of the guest's run/menu/stop flags; on_reset: clear it without fc_freeze_stop, whose write-back would land in the fresh image |
| src/free_camera.c | - | s_hud_hide_now | file_static | reset | mods | render thread reads it; on_reset: 0 |
| src/free_camera.c | - | s_act | file_static | keep | - | setting, action ids |
| src/free_camera.c | - | s_last_ns | file_static | reset | mods | flight state over the old camera; on_reset: stop flight without writing the guest (the image is fresh) |
| src/free_camera.c | - | s_fly_ns | file_static | reset | mods | flight state over the old camera; on_reset: stop flight without writing the guest (the image is fresh) |
| src/free_camera.c | - | s_panel | file_static | reset | mods | the panel the toolkit shows; on_reset: take the panel down (PANEL_NONE) |
| src/free_camera.c | - | s_back | file_static | reset | mods | guest back-buffer offsets the flips presented; the new boot allocates its own; on_reset: zero |
| src/free_camera.c | - | s_seen | file_static | keep | - | HUD batches logged once |
| src/free_camera.c | - | s_nseen | file_static | keep | - | HUD batches logged once |

### src/glow.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/glow.c | - | s_active | file_static | keep | - | the configured glow factor (fx.glow_intensity); the wrapper restores the guest word after each call, so no guest value is cached |
| src/glow.c | - | s_factor_bits | file_static | keep | - | the configured glow factor (fx.glow_intensity); the wrapper restores the guest word after each call, so no guest value is cached |
| src/glow.c | - | s_off | file_static | keep | - | the configured glow factor (fx.glow_intensity); the wrapper restores the guest word after each call, so no guest value is cached |
| src/glow.c | - | s_k | file_static | keep | - | the configured glow factor (fx.glow_intensity); the wrapper restores the guest word after each call, so no guest value is cached |

### src/glow_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/glow_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/glow_mod.c | - | s_on | file_static | keep | - | setting; the wrapper in recomp_manual.c holds no guest value across calls, so on_reset has nothing to do |

### src/hud_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/hud_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it; on_reset re-installs the HUD_ADD_VA hook the toolkit removed |

### src/lod_scale.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/lod_scale.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/lod_scale.c | - | s_on | file_static | keep | - | setting |
| src/lod_scale.c | - | s_state | file_static | reset | mods | lod_step's record of the last table write (design D5 guards); the fresh image has the stock table again, so a kept s_state reads LOD_SAME or LOD_FOREIGN and never writes; on_reset: zero it, never put_stock (shutdown's restore would write into the fresh image for nothing) |

### src/main.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/main.c | - | g_image_lo | file_static | keep | - | crash handler: the host image range |
| src/main.c | - | g_image_hi | file_static | keep | - | crash handler: the host image range |
| src/main.c | - | g_last_fault_pc | file_static | keep | - | crash diagnostics |
| src/main.c | - | g_last_fault_addr | file_static | keep | - | crash diagnostics |
| src/main.c | - | g_in_crash_handler | file_static | keep | - | crash handler re-entry guard |
| src/main.c | - | g_crash_altstack | file_static | keep | - | sigaltstack buffer, installed once |
| src/main.c | host_install_thread_dump | set | local_static | keep | - | signal mask built once |
| src/main.c | - | s_md_addr | file_static | keep | - | RECOMP_DEBUG mem dump config (debug key: reset refused) |
| src/main.c | - | s_md_len | file_static | keep | - | RECOMP_DEBUG mem dump config (debug key: reset refused) |
| src/main.c | - | s_md_every | file_static | keep | - | RECOMP_DEBUG mem dump config (debug key: reset refused) |
| src/main.c | - | s_md_pre | file_static | keep | - | mem dump file prefix |
| src/main.c | host_enhance_init | mods | local_static | keep | - | the mod table, filled once by host_enhance_init and kept by the toolkit (mod.h: kept, not copied) |

### src/pad_input.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/pad_input.c | now_s | freq | local_static | constant | - | QueryPerformanceFrequency |
| src/pad_input.c | - | g_ev | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set (RECOMP_INPUT_SCRIPT) |
| src/pad_input.c | - | g_nev | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set (RECOMP_INPUT_SCRIPT) |
| src/pad_input.c | - | g_cap | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set (RECOMP_INPUT_SCRIPT) |
| src/pad_input.c | - | g_next | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set (RECOMP_INPUT_SCRIPT) |
| src/pad_input.c | - | g_rel | file_static | keep | - | script releases; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_nrel | file_static | keep | - | script releases; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_relcap | file_static | keep | - | script releases; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_steps | file_static | keep | - | script steps; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_nsteps | file_static | keep | - | script steps; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_stepcap | file_static | keep | - | script steps; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_cur | file_static | keep | - | script steps; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_entered | file_static | keep | - | script steps; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_step_t | file_static | keep | - | script clock; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_tap_next | file_static | keep | - | script clock; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_step_polls | file_static | keep | - | script clock; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_tap_next_poll | file_static | keep | - | script clock; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_poll | file_static | keep | - | script clock; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_opens | file_static | keep | - | script file opens; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_nopens | file_static | keep | - | script file opens; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_opencap | file_static | keep | - | script file opens; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_open_cur | file_static | keep | - | script file opens; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_script_on | file_static | keep | - | sources chosen at start (host) |
| src/pad_input.c | - | g_host_on | file_static | keep | - | sources chosen at start (host) |
| src/pad_input.c | - | g_started | once | keep | - | sources chosen at start (host) |
| src/pad_input.c | - | g_rumble_on | file_static | keep | - | RECOMP_RUMBLE |
| src/pad_input.c | - | g_errors | file_static | keep | - | script parse errors |
| src/pad_input.c | - | g_t0 | file_static | keep | - | script time base and state; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_script | file_static | keep | - | script time base and state; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_packet | file_static | keep | - | XInput packet numbers; they only have to change on a new state, and a monotonic count across a reset is what a replug looks like on hardware |
| src/pad_input.c | - | g_last | file_static | reset | game | the state the title last read per port; game hook: zero it so the new boot sees no held button |
| src/pad_input.c | - | g_host_last | file_static | keep | - | the host device's last state |
| src/pad_input.c | - | g_mask_last | file_static | keep | - | the connected mask last logged (host pads stay connected) |
| src/pad_input.c | - | g_probe_t | file_static | keep | - | host query throttle |
| src/pad_input.c | - | g_slots | file_static | keep | - | host slot -> port map: the player's pads keep their ports |
| src/pad_input.c | - | g_sources_logged | file_static | keep | - | log |
| src/pad_input.c | - | g_lock | file_static | keep | - | the pad lock; the reset runs with the guest stopped, so it is free |
| src/pad_input.c | - | g_cs | file_static | keep | - | the pad lock; the reset runs with the guest stopped, so it is free |
| src/pad_input.c | init_once | done | local_static | keep | - | host setup (script parse, xbox_FileOpenHook, xbox_InputInit, slots); must not run again, so cat_pad_early_init is a no-op on a second call |
| src/pad_input.c | fmt_state | dn | local_static | constant | - | tables |
| src/pad_input.c | fmt_state | an | local_static | constant | - | tables |
| src/pad_input.c | input_trace_on | on | local_static | constant | - | RENV_INPUT_TRACE |
| src/pad_input.c | trace_handles | last | local_static | reset | game | the guest pad handles last logged; game hook: zero (a log only, but stale handles would hide the new boot's opens) |
| src/pad_input.c | - | g_peek_n | file_static | keep | - | RECOMP_DEBUG=pad_peek; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_peek_va | file_static | keep | - | RECOMP_DEBUG=pad_peek; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_peek_len | file_static | keep | - | RECOMP_DEBUG=pad_peek; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_peek_hex | file_static | keep | - | RECOMP_DEBUG=pad_peek; debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/pad_input.c | - | g_rumble_last | file_static | reset | game | the title's last motor words; game hook: send 0/0 to each host pad holding a port (a pad would keep vibrating) and zero the array |

### src/recomp_manual.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/recomp_manual.c | sub_002E0DB0 | epoch | local_static | keep | - | the shared vblank grid on the host clock; any epoch is valid, and the ADX threads of the new boot just join the grid |
| src/recomp_manual.c | recomp_icall_not_code_log | seen | local_static | keep | - | log rate limiter |
| src/recomp_manual.c | recomp_icall_not_code_log | hits | local_static | keep | - | log rate limiter |
| src/recomp_manual.c | recomp_icall_not_code_log | count | local_static | keep | - | log rate limiter |
| src/recomp_manual.c | unimpl_log_budget | budget | local_static | constant | - | from RENV_UNIMPL_BUDGET, read once |
| src/recomp_manual.c | recomp_unimpl | sites | local_static | keep | - | per-site log budget |
| src/recomp_manual.c | sub_0005B7D0 | said | local_static | keep | - | one log line per process |
| src/recomp_manual.c | - | s_cam_init | once | keep | - | env parsed once (cam_debug_init); must not re-run |
| src/recomp_manual.c | - | s_cam_log_every | file_static | keep | - | RECOMP_DEBUG=cam_log/cam_fix config, from env |
| src/recomp_manual.c | - | s_cam_fix | file_static | keep | - | RECOMP_DEBUG=cam_log/cam_fix config, from env |
| src/recomp_manual.c | - | s_cam_off | file_static | keep | - | RECOMP_DEBUG=cam_log/cam_fix config, from env |
| src/recomp_manual.c | - | s_cam_hold_at | file_static | keep | - | RECOMP_DEBUG=cam_log/cam_fix config, from env |
| src/recomp_manual.c | - | s_cam_held | file_static | reset | game | the camera captured from the old guest; game hook: s_cam_have_held = 0 |
| src/recomp_manual.c | - | s_cam_have_held | file_static | reset | game | the camera captured from the old guest; game hook: s_cam_have_held = 0 |
| src/recomp_manual.c | - | s_cam_calls | file_static | reset | game | builds since boot, compared with s_cam_hold_at; game hook: 0 |
| src/recomp_manual.c | - | s_cam_depth | file_static | reset | game | builds in progress; a guest stopped inside cam_build leaves it above 0 and the next build would skip the swap; game hook: 0 |
| src/recomp_manual.c | - | s_cam_other | file_static | keep | - | cameras logged once |
| src/recomp_manual.c | - | s_cull_init | once | keep | - | from the host display aspect (nv2a_host_opts), not guest state |
| src/recomp_manual.c | - | s_cull_scale | file_static | keep | - | from the host display aspect (nv2a_host_opts), not guest state |
| src/recomp_manual.c | sub_0003B180 | seen | local_static | keep | - | log rate limiter |
| src/recomp_manual.c | sub_0003B180 | nseen | local_static | keep | - | log once |
| src/recomp_manual.c | - | s_fan_logged | file_static | keep | - | log once per process |

### src/save_seed.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/save_seed.c | - | s_files | file_static | keep | - | cat_save_seed runs once in the host half |
| src/save_seed.c | - | s_errors | file_static | keep | - | cat_save_seed runs once in the host half |

### src/shop_api.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/shop_api.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/shop_api.c | - | s_owner | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/shop_api.c | - | s_on | file_static | keep | - | settings |
| src/shop_api.c | - | s_ready | once | reset | mods | the game's tables read from the guest; on_reset: s_ready = 0 so they are read again from the fresh image |
| src/shop_api.c | - | s_game | file_static | reset | mods | the game's tables read from the guest; on_reset: s_ready = 0 so they are read again from the fresh image |
| src/shop_api.c | - | s_over | file_static | keep | - | settings |
| src/shop_api.c | - | s_speed | file_static | reset | mods | the stock values saved before the overrides were written; on_reset: re-read with s_game |
| src/shop_api.c | - | s_life | file_static | reset | mods | the stock values saved before the overrides were written; on_reset: re-read with s_game |
| src/shop_api.c | - | s_interval | file_static | reset | mods | the stock values saved before the overrides were written; on_reset: re-read with s_game |
| src/shop_api.c | - | s_pct_price | file_static | keep | - | settings |
| src/shop_api.c | - | s_pct_ammo | file_static | keep | - | settings |
| src/shop_api.c | - | s_pct_power | file_static | keep | - | settings |
| src/shop_api.c | - | s_pct_speed | file_static | keep | - | settings |
| src/shop_api.c | - | s_pct_interval | file_static | keep | - | settings |
| src/shop_api.c | - | s_written | file_static | reset | mods | what was written into the old image; on_reset: 0, so the overrides are applied again |
| src/shop_api.c | - | s_before | file_static | reset | mods | what was written into the old image; on_reset: 0, so the overrides are applied again |
| src/shop_api.c | - | s_pre_gun | file_static | reset | mods | the shot in flight; on_reset: 0 |
| src/shop_api.c | - | s_pre_plr | file_static | reset | mods | the shot in flight; on_reset: 0 |
| src/shop_api.c | - | s_shot_fn | file_static | keep | - | callback shop_mod registered at init (host) |
| src/shop_api.c | - | s_shot_user | file_static | keep | - | callback shop_mod registered at init (host) |
| src/shop_api.c | - | s_guest | file_static | reset | mods | as ent_api.c s_guest: on_reset NULL |
| src/shop_api.c | - | t_marker | tls | keep | - | address only |
| src/shop_api.c | - | t_in_hook | tls | reset | game | as ent_api.c t_in_hook |

### src/shop_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/shop_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/shop_mod.c | - | s_on | file_static | keep | - | setting |
| src/shop_mod.c | - | s_out | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_gun | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_fire | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_every | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_shots | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_gold | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | o_goldat | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/shop_mod.c | - | s_frame | file_static | reset | mods | play trackers; on_reset: 0 |
| src/shop_mod.c | - | s_play | file_static | reset | mods | play trackers; on_reset: 0 |
| src/shop_mod.c | - | s_playing | file_static | reset | mods | play trackers; on_reset: 0 |
| src/shop_mod.c | - | s_fired | file_static | reset | mods | play trackers; on_reset: 0 |

### src/speed_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/speed_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/speed_mod.c | - | s_on | file_static | keep | - | setting |
| src/speed_mod.c | - | s_st | file_static | reset | mods | the learned reference and the peak's frames of the old boot; on_reset: zero |
| src/speed_mod.c | - | s_shown | file_static | reset | mods | the card's last text; on_reset: "" so the next frame sets it again |

### src/walls_mod.c

| file | scope | name | kind | class | hook | why |
|---|---|---|---|---|---|---|
| src/walls_mod.c | - | s_api | file_static | keep | - | the host API table, valid for the process; on_reset reuses it |
| src/walls_mod.c | - | s_on | file_static | keep | - | setting |
| src/walls_mod.c | - | s_frame | file_static | keep | - | monotonic mod frame and trace query number |
| src/walls_mod.c | - | s_qid | file_static | keep | - | monotonic mod frame and trace query number |
| src/walls_mod.c | - | s_fixed | file_static | reset | mods | counts for 'this run', shown by the menu; on_reset: 0 |
| src/walls_mod.c | - | s_kept | file_static | reset | mods | counts for 'this run', shown by the menu; on_reset: 0 |
| src/walls_mod.c | - | s_tris | file_static | reset | mods | triangles gathered from the guest; on_reset: s_ntris = 0, s_tris_frame = ~0u |
| src/walls_mod.c | - | s_ntris | file_static | reset | mods | triangles gathered from the guest; on_reset: s_ntris = 0, s_tris_frame = ~0u |
| src/walls_mod.c | - | s_tris_frame | file_static | reset | mods | triangles gathered from the guest; on_reset: s_ntris = 0, s_tris_frame = ~0u |
| src/walls_mod.c | - | s_sw | file_static | reset | mods | the copy of the guest triangle source the frame used (with s_tris); on_reset: zero |
| src/walls_mod.c | - | s_q | file_static | reset | mods | the query, triangle test and dynamic query in flight; a guest stopped inside a hook leaves them active; on_reset: zero |
| src/walls_mod.c | - | s_fc | file_static | reset | mods | the query, triangle test and dynamic query in flight; a guest stopped inside a hook leaves them active; on_reset: zero |
| src/walls_mod.c | - | s_out | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_fix | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_probe | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_samples | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_rad | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_wmax | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_tp | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_tp_at | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_depth | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_tp_for | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | s_probing | file_static | keep | - | probe mode (debug option) |
| src/walls_mod.c | - | s_hooked | file_static | keep | - | a count of hook entries, compared before and after a guest_call (:579-584); monotonic, valid across a reset |
| src/walls_mod.c | - | s_flags_seen | file_static | reset | mods | the player's test flags seen in the old boot; on_reset: 7 |
| src/walls_mod.c | - | s_block | file_static | reset | mods | guest_alloc block; on_reset: 0 |
| src/walls_mod.c | - | s_off | file_static | reset | mods | player 0 centre offset; on_reset: s_have_off = 0 |
| src/walls_mod.c | - | s_have_off | file_static | reset | mods | player 0 centre offset; on_reset: s_have_off = 0 |
| src/walls_mod.c | - | s_pairs | file_static | reset | mods | on_reset: s_npairs = 0 |
| src/walls_mod.c | - | s_npairs | file_static | reset | mods | on_reset: s_npairs = 0 |
| src/walls_mod.c | - | s_tp_f | file_static | reset | mods | teleport in flight; on_reset: -1, -1, 0, 0 |
| src/walls_mod.c | - | s_tp_b | file_static | reset | mods | teleport in flight; on_reset: -1, -1, 0, 0 |
| src/walls_mod.c | - | s_tp_until | file_static | reset | mods | teleport in flight; on_reset: -1, -1, 0, 0 |
| src/walls_mod.c | - | s_tp_pending | file_static | reset | mods | teleport in flight; on_reset: -1, -1, 0, 0 |
| src/walls_mod.c | - | s_tp_c | file_static | reset | mods | teleport in flight; on_reset: -1, -1, 0, 0 |
| src/walls_mod.c | - | s_sw_last | file_static | reset | mods | on_reset: zero |
| src/walls_mod.c | - | s_sw_seen | file_static | reset | mods | on_reset: zero |
| src/walls_mod.c | - | o_dyn | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_dynper | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_gat | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_gx | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_gy | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_gz | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_tris | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_pd | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | o_pdn | file_static | keep | - | debug harness option or output; a DEBUG-tier key, so D7 rule 1 refuses the reset while it is set |
| src/walls_mod.c | - | s_dq | file_static | reset | mods | the query, triangle test and dynamic query in flight; a guest stopped inside a hook leaves them active; on_reset: zero |

## host_main split (cat, src/main.c:1102-1346)

D6 calls `xbox_boot_run(entry, game_boot)`. Its host half runs once. Its
guest half runs at the first boot and again on every reset (after bands
1-12).

| line | step | half | why |
|---|---|---|---|
| 1109 | `xbox_log_thread_role("guest-main")` | host | names the thread; with a fresh guest thread on reset, the toolkit names it again |
| 1112-1113 | crash handler, thread dump | host | once per process |
| 1115-1147 | RENV_GAME_FILES / HDD_DIR, `load_xbe` into `xbe_data` | host | keep `xbe_data` alive: band 8 reloads the sections from it (it is freed only at :1343) |
| 1150-1163 | the AC97/MMIO trap comment and env defaults | host | env is kept |
| 1164-1165 | `xbox_SetTotalRam`, `xbox_MemoryLayoutInit` | host | the mapping stays. Band 7 clears RAM in place and band 8 copies the image, using the toolkit's loader split out of MemoryLayoutInit |
| 1173-1175 | `g_xbox_mem_offset`, `host_install_mem_dump` | host | mapping constant; mem dump is debug |
| 1194 | `xbox_Nv2aMirrorFence(0x2F1FB8, 0x2C, 0x30)` | host | registers a constant guest VA with the NV2A side. This is host config and stays registered. The mirrored fence word lives in guest RAM, so the toolkit's NV2A reset (band 4/5) must reset its *value*, not unregister it |
| 1206-1227 | `recomp_env_set` VBLANK / TITLE_KEVENTS / GUEST_LOCK defaults | host | env kept |
| 1238-1246 | `mcpx_apu_init_standalone`, fault bench | host | the APU object stays. Band 3 resets its state (see dsp-jit-keying.md) |
| 1253 | `xbox_kernel_init` | host | the kernel's guest-facing tables are reset by their bands, not by re-running init |
| 1258 | `xbox_path_init` | host | paths kept |
| 1266 | `xbox_kernel_bridge_init` | host | bridge table constant |
| 1269 | `g_esp = XBOX_STACK_TOP` | **guest** | the guest stack; on the entry thread's TLS (finding 3) |
| 1284-1292 | init-flag patch: guest 0x00010124 `&= ~1u` (MOUNT_UTILITY_DRIVE) | **guest** | writes the XBE header in guest RAM, so it must re-run after band 8 |
| 1315 | `recomp_dispatch_init` | host | dispatch table constant (design "What stays") |
| 1327 | `xbox_WatchdogStart` | host | one watchdog per process. Its counters should be re-armed when the guest restarts (toolkit) |
| 1329 | `cat_save_seed()` | host | once, as the brief says: seeds saves into the save dir |
| 1330 | `cat_pad_early_init()` | host (was: guest) | idempotent host setup (finding 1). Replace it in `game_boot` with a new `cat_pad_reset()` |
| 1336 | `xbe_entry_point()` | **guest** | the entry |
| 1341-1343 | kernel shutdown, layout shutdown, free | host | process exit only |

So cat's `game_boot` = `g_esp = XBOX_STACK_TOP`, the init-flag patch, and
(on a reset only) `cat_pad_reset()`, then the entry. `main`/`WinMain` (
`recomp_env_init`, `host_stdio_setup`, `host_enhance_init` with the mod
table, `xbox_HostWindowSetTitle`, `xbox_HostWindowMain(host_main)`) are all
host, once.

## Mods: `needs` vs. use (D6a)

Flags: ASPECT 0x01, STATE 0x02, POKE 0x04, HOOK 0x08, PLACE 0x10
(xboxrecomp src/enhance/mod.h:136-140). "reads" means guest RAM read through
`api->mem` (`XBOX_MOD_MEM32/MEMF`, `rd*`), outside hook arguments.

| mod (file:line of the table) | needs | hooks (`api->hook`) | pokes (writes via `api->mem`) | reads | other guest API | gaps |
|---|---|---|---|---|---|---|
| collision (collision_mod.c:521) | HOOK | VA_QUERY 0x001636C0, VA_FACE 0x00165630 (:513-514) | none | player pos, view/proj, stage collision (`col_stage_load` over `api->mem`) | draw3d (host) | **STATE** |
| crystals (crystals_mod.c:492) | POKE\|HOOK | CRY_VA_COLLECT, VA_SPRITE_ADD | yes | `rd8/16/32` (pickups, VA_TEXTURE :342) | `guest_alloc` (:153), `guest_call` VA_SPRITE_ADD (:327); crystals_proof: `guest_call` CRY_VA_COLLECT, VA_ITEM_SPAWN | **STATE**; no flag covers `guest_alloc` / `guest_call` |
| debug_menu (debug_menu.c:277) | POKE | none | `DBGM_CURSOR`, open table (:110, :153, :162) | title state, cursor (`rd`, `rd8`) | none | **STATE** |
| entities (entities_mod.c:562, with ent_api.c) | POKE\|HOOK | VA_UPDATE_ALL (ent_api.c:608, owner = entities) | yes (HP, records) | `entl_rd32` over `api->mem` (ent_api.c:150) | `guest_alloc` (ent_api.c:268), `guest_call` VA_SPAWN (:284), VA_DAMAGE (:325) | **STATE**; guest_alloc / guest_call |
| camera.free (free_camera.c:722) | POKE | none | `G32(STOP_FLAG)` and the camera (:274-305) | 28 `G32`/`GF` uses (run/menu/stop flags, camera) | `batch_filter` (:697; renderer side, host) | **STATE** |
| glow (glow_mod.c:116) | POKE | none (the sub_0005B7D0 wrapper is in recomp_manual.c, not an API hook) | none through the API. The wrapper writes 0xADC744 with `MEM32` (recomp_manual.c:557) | none | none | none against the API, but the D6a recorder can never see the wrapper's write. POKE is a declaration on its behalf; keep it |
| hud (hud_mod.c:119) | HOOK\|ASPECT | HUD_ADD_VA (:111) | none | hook arguments only (`XBOX_MOD_ARG32`); `hud_apply` reads the vertices inside the toolkit | `hud_table` (:108) | none |
| lod (lod_scale.c:176) | **0** (the table has no needs field; v3-style init) | none | the LOD table at LOD_TABLE_VA (:80-82 via `lod_step`) | the same table | none | **POKE and STATE** |
| shop (shop_mod.c:378, with shop_api.c) | POKE\|HOOK | VA_FIRE (shop_api.c:448, owner = shop) | gun tables (`shopl_apply`) | `shopl_read_game` (shop_api.c:240) | `guest_call` VA_FIRE (shop_mod.c:211) | **STATE**; guest_call |
| walls (walls_mod.c:984) | POKE\|HOOK | VA_FACE, VA_QUERY, VA_DYNAMIC (:961-971) | `wrf` (:195) | `rd32`/`rdf` | `guest_alloc` (:610), `guest_call` VA_FACE (:581) | **STATE**; guest_alloc / guest_call |

Gaps in one line: no cat mod declares STATE, though eight read guest RAM
outside hook arguments (all but glow and hud). lod declares nothing
although it pokes and reads.

There are also two structural gaps in D6a:

- **Raw memory access cannot be recorded.** `XBOX_MOD_MEM32/MEMF` dereference
  `api->mem` directly (mod.h:506-507). Pokes and reads through it never pass
  through a toolkit function, so the D6a recorder cannot see them (and the
  same holds for `col_stage_load`, `entl_*`, `shopl_*` and `lod_step`, which
  take `api->mem` as a base pointer). Only these calls are observable:
  - `hook`;
  - `guest_call`;
  - `guest_alloc`;
  - `hud_table`/`hud_apply`;
  - `batch_filter`.
  So either STATE and POKE stay pure declarations, with the rule turning the
  restart off for any declared mod without on_reset, or the API gains
  accessor calls. Recommend the first: one flag, checked at init.
- **No flag covers `guest_alloc` and `guest_call`.** guest_alloc owns guest
  RAM that the reset wipes, so it must be counted as POKE for the rule, or a
  new `XBOX_MOD_NEED_ALLOC`/`CALL` must be added. Recording them under POKE
  (alloc) and HOOK (call) keeps the flag set unchanged.

All ten mods hold reset-class state (tables above), so all ten need an
on_reset. glow's can be empty, and hud's only re-installs the hook.

## BLiNX 1 host_main split (blinx/src/main.c:703-925, blinx HEAD d54c71e)

| line | step | half | why |
|---|---|---|---|
| 707-713 | log, `xbox_log_thread_role("guest-main")`, crash handler | host | once |
| 716-761 | game dir, `load_xbe` into `xbe_data` | host | kept for band 8 |
| 762 | `xbox_SetSectionPaging(1)` | host | layout config, before MemoryLayoutInit |
| 763-772 | `xbox_MemoryLayoutInit`, `g_xbox_mem_offset` | host | mapping stays |
| 790 | `xbox_Nv2aMirrorFence(0x00143B58, 0x2C, 0x30)` | host | as cat |
| 803, 813 | VBLANK / TITLE_KEVENTS defaults | host | env |
| 823-827 | `mcpx_apu_init_standalone` when AC97_READY | host | as cat |
| 843 | USB=1 default | host | env |
| 846 | `blinx1_pad_init()` | host | the pad source (script, host pads); no guest state. Like cat's, it should get a separate pad reset |
| 847 | `xbox_OhciInit()` | host | the OHCI controller object. Its guest-visible registers and the device list are USB-band state that the toolkit must reset; it is not re-run here |
| 851-864 | `xbox_kernel_init`, `xbox_path_init`, `xbox_kernel_bridge_init` | host | as cat |
| 867 | `g_esp = XBOX_STACK_TOP` | **guest** | |
| 898 | `recomp_dispatch_init` | host | |
| 910 | `xbox_WatchdogStart` | host | |
| 916 | `xbe_entry_point()` | **guest** | runs on the host_main thread too |
| 921-923 | shutdown, free | host | |

BLiNX 1 has no init-flag patch and no save seed. The comment at 872-879
about `ACTIVE_HEAP_VA` is template text only; no code follows it. Its guest
half is just `g_esp` + entry (plus a pad reset). It was not checked
against BLiNX 1's own statics; that audit is a separate task.
