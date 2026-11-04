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
 *
 * Why atomics: the glow mod (glow_mod.c) reconfigures from the mod frame
 * while the wrapper reads on the guest thread that draws; the factor is
 * kept as its bits so each load is whole. The pair may tear for one call,
 * which draws one frame with the old value (openspec change glow-mod, D3).
 */
#include <math.h>
#include <string.h>
#include "glow.h"

static int s_active;
static uint64_t s_factor_bits = 0x3FF0000000000000ull;   /* 1.0 */
static int s_off;               /* as configured, for the start line */
static double s_k = 1.0;

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
    double f = off ? 0.0 : k;
    uint64_t b;

    s_off = off;
    s_k = k;
    memcpy(&b, &f, sizeof b);
    __atomic_store_n(&s_factor_bits, b, __ATOMIC_RELAXED);
    __atomic_store_n(&s_active, off || k != 1.0, __ATOMIC_RELAXED);
}

int glow_active(void)
{
    return __atomic_load_n(&s_active, __ATOMIC_RELAXED);
}

double glow_factor(void)
{
    uint64_t b = __atomic_load_n(&s_factor_bits, __ATOMIC_RELAXED);
    double f;

    memcpy(&f, &b, sizeof f);
    return f;
}

void glow_settings(int *off, double *k)
{
    *off = s_off;
    *k = s_k;
}
