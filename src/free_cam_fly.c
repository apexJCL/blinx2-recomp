/*
 * free_cam_fly.c - the free camera's maths and freeze bookkeeping (see
 * free_cam_fly.h).
 *
 * Why these axes: sub_0021B1F0 builds V = T(-eye) . RotY(a10) . RotX(-a0C)
 * . RotZ(-a14) in D3DX's row-vector form, so with roll 0 the view's rows
 * in world space are right = (cos y, 0, sin y), up = (-sin y sin p, cos p,
 * cos y sin p) and forward = (-sin y cos p, -sin p, cos y cos p). The world
 * is Y-down: rising is -y, and stage 1's resting pitch of -0.262 looks down
 * at Blinx.
 */
#include <math.h>
#include "free_cam_fly.h"

float fc_axis(int v, int dead)
{
    float a = (float)(v < 0 ? -v : v);
    float span = 32767.0f - (float)dead;

    if (a <= (float)dead)
        return 0.0f;
    a = (a - (float)dead) / span;
    if (a > 1.0f)
        a = 1.0f;
    return v < 0 ? -a : a;
}

void fc_basis(float pitch, float yaw, float fwd[3], float right[3])
{
    float sp = sinf(pitch), cp = cosf(pitch), sy = sinf(yaw), cy = cosf(yaw);

    fwd[0] = -sy * cp;
    fwd[1] = -sp;
    fwd[2] = cy * cp;
    right[0] = cy;
    right[1] = 0.0f;
    right[2] = sy;
}

void fc_fly_step(struct fc_cam *c, const struct fc_input *in,
                 const struct fc_params *pr, float dt)
{
    float fwd[3], right[3], v, look;
    int i;

    if (!(dt > 0.0f))
        return;
    if (dt > FC_DT_MAX)
        dt = FC_DT_MAX;
    look = pr->look_sens;
    c->yaw -= (in->rx * FC_LOOK_RATE * dt + in->mouse_dx * FC_MOUSE_RATE) * look;
    c->pitch += (in->ry * FC_LOOK_RATE * dt - in->mouse_dy * FC_MOUSE_RATE) * look;
    if (c->pitch > FC_PITCH_MAX)
        c->pitch = FC_PITCH_MAX;
    if (c->pitch < -FC_PITCH_MAX)
        c->pitch = -FC_PITCH_MAX;
    /* Keep the yaw in one turn so a long session does not lose float bits. */
    c->yaw = remainderf(c->yaw, 6.28318531f);

    v = FC_MOVE_BASE * pr->speed * dt;
    if (in->fast)
        v *= FC_FAST;
    if (in->slow)
        v *= FC_SLOW;
    fc_basis(c->pitch, c->yaw, fwd, right);
    for (i = 0; i < 3; i++)
        c->p[i] += (fwd[i] * in->ly + right[i] * in->lx) * v;
    c->p[1] += (in->down - in->up) * v;
}

int fc_freeze_start(struct fc_freeze *f, uint32_t run, uint32_t menu, uint32_t flag)
{
    if (f->on || run != 1 || menu != 0 || flag != 0)
        return 0;
    f->on = 1;
    f->restore = flag;
    f->game_writes = 0;
    return 1;
}

int fc_freeze_tick(struct fc_freeze *f, uint32_t flag, uint32_t run, uint32_t menu,
                   int *wrote)
{
    *wrote = 0;
    if (!f->on)
        return FC_FZ_DROP;
    /* As in fc_freeze_pre: 1 is the re-assert's own, and a value equal to
     * the restore one changes nothing, so neither counts as a write. */
    *wrote = flag != 1 && fc_freeze_events(f, flag);
    if (run != 1 || menu != 0) {
        f->on = 0;
        return FC_FZ_DROP;
    }
    return FC_FZ_KEEP;
}

int fc_freeze_events(struct fc_freeze *f, uint32_t flag)
{
    if (!f->on || flag == f->restore)
        return 0;
    f->restore = flag;
    f->game_writes++;
    return 1;
}

uint32_t fc_freeze_pre(struct fc_freeze *f, uint32_t flag, int *wrote)
{
    /* The re-assert left 1; anything else is the game's own write. */
    *wrote = flag != 1 && fc_freeze_events(f, flag);
    return f->restore;
}

uint32_t fc_freeze_stop(struct fc_freeze *f)
{
    f->on = 0;
    return f->restore;
}

uint32_t fc_freeze_drop(struct fc_freeze *f)
{
    f->on = 0;
    return f->restore;
}
