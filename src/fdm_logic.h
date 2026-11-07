/*
 * fdm_logic.h - the fdm mod's speed factor (fdm_mod.c; openspec change
 * b2-full-diagonal-movement), apart from the guest so scripts/test_fdm.py
 * can check it.
 *
 * The walk's speed is s = (min(L, 1) - dz) / (1 - dz) times the table's
 * max (0x17C91F to 0x17D301). fdm_factor is the unclamped s over the
 * clamped one: 1 at or below full length, (L - dz) / (1 - dz) above it,
 * with L at most a square stick's corner, sqrt(2), where it is 1.690 at
 * the walk's 0.4 deadzone (BLiNX 1's ratio).
 *
 * fdm_live_pad says whether the walk's pad pointer is one of the four live
 * pads (base = [0xADC794], 0x1E4 bytes each), the only input the mod
 * unclamps (fdm_mod.c has the other sources).
 */
#ifndef CAT_FDM_LOGIC_H
#define CAT_FDM_LOGIC_H

#include <math.h>
#include <stdint.h>

#define FDM_L_MAX 1.41421356f
#define FDM_PAD_SIZE 0x1E4u
#define FDM_N_PADS 4u

static inline float fdm_factor(float x, float y, float dz)
{
    float l = sqrtf(x * x + y * y);

    /* NaN-safe: a stick or deadzone that is not a number stays stock. */
    if (!(l > 1.0f) || !(dz < 1.0f))
        return 1.0f;
    if (l > FDM_L_MAX)
        l = FDM_L_MAX;
    return (l - dz) / (1.0f - dz);
}

static inline int fdm_live_pad(uint32_t pad, uint32_t base)
{
    return base && pad >= base && pad - base < FDM_N_PADS * FDM_PAD_SIZE
           && (pad - base) % FDM_PAD_SIZE == 0;
}

#endif
