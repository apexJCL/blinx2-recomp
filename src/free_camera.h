/*
 * free_camera.h - camera.free: a free-flying camera through the game's own
 * view builders, a HUD hide and a world freeze (openspec change
 * free-camera). The enhancements layer's first mod (toolkit mod.h).
 *
 * The camera module owns the state; recomp_manual.c's wrappers ask it:
 *   sub_000292A0, sub_0021B1F0  free_cam_view: the fields to swap in
 *   sub_0005C930 (pad poll)     free_cam_frame: the mod frame
 *   sub_000EEB40 (events)       free_cam_events_pre/post: the game's flag
 *                               in for the event system, read back after
 *   sub_00161120                free_cam_freeze_tick: the freeze re-assert
 *   sub_000606F0 (stage start)  free_cam_stage_start: the freeze dropped
 * and pad_input.c asks free_cam_pad_neutral for the game's port 0.
 *
 * Without the layer, or with a toolkit that has no mod.h, every call is a
 * constant: the wrappers run the generated bodies and nothing else.
 */
#ifndef CAT_FREE_CAMERA_H
#define CAT_FREE_CAMERA_H

#include "free_cam_fly.h"

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API is not built. */
const void *free_cam_mod(void);

/* 1 while the free camera flies; c (may be NULL) gets its fields. Guest
 * thread. */
int free_cam_view(struct fc_cam *c);

/* Once per guest frame, after the game's pad poll (the mod frame). */
void free_cam_frame(void);

/* The four actions (toggle, HUD, freeze, reset), as the hotkeys run them;
 * call them on the frame thread (a mod's on_frame). Gamepad bindings come
 * through the host-action layer, which calls these. */
void free_cam_action_toggle(void);
void free_cam_action_hud(void);
void free_cam_action_freeze(void);
void free_cam_action_reset(void);

/* Around sub_000EEB40, the event system: while frozen, pre writes the
 * game's own 0xAF0EF4 value back for it and post reads what it left as the
 * value to put back on unfreeze, then writes 1. */
void free_cam_events_pre(void);
void free_cam_events_post(void);

/* After sub_00161120, just before the stage update's gate (0x652DC). */
void free_cam_freeze_tick(void);

/* The stage started or restarted (sub_000606F0). */
void free_cam_stage_start(void);

/* 1 while the camera has port 0: the game reads a released pad. */
int free_cam_pad_neutral(void);

#endif
