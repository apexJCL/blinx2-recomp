/*
 * glow.c - the weight maths behind fx.glow_intensity (see glow.h).
 *
 * Why a cube root: the pass's combiner (read from the CPU pixel trace of the
 * bloom spike) is r0 = v0 * sum(taps), r1 = dot(r0, 0.4)^2, out = r1 * r0,
 * so the weight v0 enters the source colour three times and the layer grows
 * with its cube. Scaling each byte by cbrt(k) scales the layer by k, up to
 * byte rounding and the combiner's [-1, 1] clamps near white.
 *
 * Why the wrapper restores the word after the call: sub_000E4140 fades the
 * weight every frame from whatever the word holds (low byte, +-1 a frame,
 * replicated to R, G and B). A scaled value left behind would become the
 * fade's next starting point and compound frame after frame.
 */
#include <math.h>
#include "glow.h"

static int s_active;
static double s_factor = 1.0;

uint32_t glow_weight(uint32_t w, double k)
{
    uint32_t out = w & 0xFF000000u;
    double f;
    int i;

    if (!(k > 0.0))
        return out;
    f = cbrt(k);
    for (i = 0; i < 24; i += 8) {
        long v = lround((double)((w >> i) & 0xFFu) * f);
        if (v > 0xFF)
            v = 0xFF;
        out |= (uint32_t)v << i;
    }
    return out;
}

void glow_configure(int off, double k)
{
    s_factor = off ? 0.0 : k;
    s_active = off || k != 1.0;
}

int glow_active(void)
{
    return s_active;
}

double glow_factor(void)
{
    return s_factor;
}
