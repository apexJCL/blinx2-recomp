/*
 * free_cam_fly.h - the free camera's maths and freeze bookkeeping
 * (camera.free, openspec change free-camera D2 and D5).
 *
 * Plain C with no guest state and no toolkit headers, so
 * scripts/test_free_camera.py can compile it alone. free_camera.c reads the
 * guest and the input, calls these, and writes the guest.
 */
#ifndef CAT_FREE_CAM_FLY_H
#define CAT_FREE_CAM_FLY_H

#include <stdint.h>

/* The free camera: position and the two angles the builders read. Roll and
 * the extra angles (+0x14, +0x18, +0x1C) stay 0 (D2). */
struct fc_cam {
    float p[3];
    float pitch;            /* +0x0C; > 0 looks up (the world is Y-down) */
    float yaw;              /* +0x10; > 0 turns left */
};

/* One frame of input, already through the dead zones. */
struct fc_input {
    float lx, ly;           /* move: right, forward; -1..1 */
    float rx, ry;           /* look: right, up; -1..1 */
    float up, down;         /* rise, sink; 0..1 */
    int fast, slow;
    float mouse_dx, mouse_dy;   /* raw counts; mouse forward is dy < 0 */
};

struct fc_params {
    float speed;            /* camera.free_speed, a multiplier of FC_MOVE_BASE */
    float look_sens;        /* camera.free_look_sens, a multiplier of the rates */
};

#define FC_MOVE_BASE   80.0f    /* world units a second at full stick (the
                                 * stage-1 camera rides about 35 above Blinx) */
#define FC_LOOK_RATE   1.8f     /* rad a second at full stick */
#define FC_MOUSE_RATE  0.0025f  /* rad a count */
#define FC_FAST        4.0f
#define FC_SLOW        0.25f
#define FC_PITCH_MAX   1.50f    /* short of straight up or down */
#define FC_DT_MAX      0.1f     /* a hitch never throws the camera */

/* A stick axis (-32768..32767) through a radial-free dead zone, to -1..1. */
float fc_axis(int v, int dead);

/* The camera-space basis for pitch and yaw, row-vector D3DX convention as
 * sub_0021B1F0 builds it (R = RotY(yaw) . RotX(-pitch)): forward is the
 * view's +z, right its +x. */
void fc_basis(float pitch, float yaw, float fwd[3], float right[3]);

/* Moves and turns c by in over dt seconds. */
void fc_fly_step(struct fc_cam *c, const struct fc_input *in,
                 const struct fc_params *pr, float dt);

/* ---- freeze (D5): the event world-stop flag 0xAF0EF4 ----------------------- */

struct fc_freeze {
    int on;
    uint32_t restore;       /* what unfreeze writes back */
    unsigned game_writes;   /* game writes seen while frozen */
};

enum { FC_FZ_KEEP, FC_FZ_DROP };

/* Whether a freeze may start: the stage runs (0x449F40 == 1), no pause
 * menu or retry (0xAE73B4 == 0) and no event stop (0xAF0EF4 == 0). On 1
 * the caller writes 1 to the flag. */
int fc_freeze_start(struct fc_freeze *f, uint32_t run, uint32_t menu, uint32_t flag);

/* Once a frame after the event system, before the stage's update gate:
 * the flag as it reads now and the two guards. A value other than 1 that
 * differs from the restore value is a game write: it becomes the restore
 * value (an event that ends during the freeze ends on unfreeze). FC_FZ_KEEP: write 1. FC_FZ_DROP: the pause
 * menu opened or the stage is gone; the freeze is over and the caller
 * writes f->restore back, so the world does not stay stopped after the
 * menu closes (the menu stops it on its own meanwhile). *wrote is set when
 * this call saw a game write. */
int fc_freeze_tick(struct fc_freeze *f, uint32_t flag, uint32_t run, uint32_t menu,
                   int *wrote);

/* A game write to the flag while frozen: flag becomes the new restore
 * value. Called after the event system ran on the game's own value (the
 * caller wrote f->restore before it), where an event can write 1 (it stops
 * the world itself) that the re-assert would otherwise hide, and before it
 * with any value other than 1 found there (fc_freeze_pre), and after
 * sub_00161120 (fc_freeze_tick).
 * Returns 1 when the value changed (a game write). The caller writes 1
 * after the event system either way. */
int fc_freeze_events(struct fc_freeze *f, uint32_t flag);

/* Before the event system: flag is what the game left since the last
 * re-assert. A value other than 1 is a game write made outside the event
 * window (sub_00076030's snapshot restore) and becomes the restore value;
 * a 1 cannot be told from the freeze's own. Returns the value to put in
 * for the event system; *wrote is set when this call saw a game write. */
uint32_t fc_freeze_pre(struct fc_freeze *f, uint32_t flag, int *wrote);

/* Unfreeze: returns the value to write back; the freeze is over. */
uint32_t fc_freeze_stop(struct fc_freeze *f);

/* The guards failed or the stage (re)started: over; returns the value to
 * write back, as fc_freeze_stop. A stale 1 would stop the next stage. */
uint32_t fc_freeze_drop(struct fc_freeze *f);

#endif
