/*
 * speed_logic.h - the speed readout's ratio and peak (speed_mod.c; openspec
 * change b2-full-diagonal-movement, D4), apart from the guest so
 * scripts/test_speed.py can check it.
 *
 * The ratio is the player's speed (+0x154) over a full straight push's.
 * The walk's straight speed is the table's max times factors the walk
 * keeps in its own frame (the ground's slope, the upgrades, the 0.8 and
 * 0.6 modes; 0x17CF4C to 0x17D313): on stage 1-1 a straight push settles
 * at 2.19, not the table's 4.5. So the reference is learned, not computed:
 * the speed after SPEED_SETTLE_N frames in a row with the stick at full
 * length on the circle and the speed steady. A frame off the circle starts
 * the count again, so a corner's speed (L = sqrt 2) never becomes the
 * reference. The window is tight because the walk's speed follows L both
 * ways: (L - 0.4) / 0.6 below 1 and the fdm factor above it, so L within
 * 0.5% of 1 keeps the reference within 0.84%, under the card's 0.01. A
 * square stick's corner (and the keyboard's, with Square left stick) then
 * reads 1.00 stock and 1.69 with Full Diagonal Movement.
 *
 * speed_live_pad finds the pad player 0's walk reads (0x176421 to
 * 0x17643A): [0xADC794] + slot * 0x1E4, the slot being
 * pad_menu_index[(id / 4) % 4] (0xAE7A10, the walk's [esp+0x48]), with
 * the id byte signed and the divide and remainder truncating, as the
 * walk's cdq, sar and its and/dec/or/inc do. A negative index or slot
 * (an id of -4 to -15, say) would read before the table, so it gives no
 * pad.
 */
#ifndef CAT_SPEED_LOGIC_H
#define CAT_SPEED_LOGIC_H

#include <math.h>
#include <stdint.h>

#define SPEED_PEAK_N   30       /* frames in the peak: one second at 30 */
#define SPEED_SETTLE_N 8        /* frames within SPEED_SETTLE of the last */
#define SPEED_SETTLE   0.002f   /* relative change per frame */
#define SPEED_L_LO     0.995f   /* a full push on the circle */
#define SPEED_L_HI     1.005f
#define SPEED_MIN      0.5f     /* slower is not running */
#define SPEED_PAD_SIZE 0x1E4u
#define SPEED_N_PADS   4u

struct speed_state {
    float ref;                  /* 0 until a straight push has settled */
    float prev;
    int settled;
    float hist[SPEED_PEAK_N];
    int n, at;
};

/* One frame: the speed and the stick's length. Returns the ratio, or a
 * negative number while there is no reference yet; *peak gets the
 * highest ratio of the last SPEED_PEAK_N frames (negative likewise). */
static inline float speed_step(struct speed_state *st, float speed, float l, float *peak)
{
    float v = fabsf(speed), r, p;
    int i;

    if (!(v == v) || !(l == l))
        v = 0.0f, l = 0.0f;
    /* Every frame of the count must be a steady full straight push. */
    if (l >= SPEED_L_LO && l <= SPEED_L_HI && v >= SPEED_MIN
        && fabsf(v - st->prev) <= SPEED_SETTLE * v)
        st->settled++;
    else
        st->settled = 0;
    st->prev = v;
    if (st->settled >= SPEED_SETTLE_N)
        st->ref = v;
    r = st->ref > 0.0f ? v / st->ref : -1.0f;
    st->hist[st->at] = r;
    st->at = (st->at + 1) % SPEED_PEAK_N;
    if (st->n < SPEED_PEAK_N)
        st->n++;
    p = -1.0f;
    for (i = 0; i < st->n; i++)
        if (st->hist[i] > p)
            p = st->hist[i];
    *peak = p;
    return r;
}

/* The pad for the id byte, given [0xADC794] and pad_menu_index's four
 * entries; 0 when there is none. */
static inline uint32_t speed_live_pad(int id, uint32_t base, const uint32_t index[4])
{
    int i = id / 4 % 4;
    uint32_t slot;

    if (i < 0 || !base)
        return 0;
    slot = index[i];
    return slot < SPEED_N_PADS ? base + slot * SPEED_PAD_SIZE : 0;
}

#endif
