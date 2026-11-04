/*
 * glow.h - fx.glow and fx.glow_intensity: the weight of the game's glow pass.
 *
 * In post mode 3 (0xADC738) the frame routine sub_0005B550 calls
 * sub_0005B7D0, which screen-blends a 4-tap blur of the 320x240 downsample
 * over the frame. The game's weight 0xADC744 (0x00RRGGBB, alpha 0) is the
 * quad's vertex colour; recomp_manual.c wraps sub_0005B7D0 and scales that
 * word for the duration of the call (openspec change glow-toggle). The glow
 * mod (glow_mod.c, openspec change glow-mod) sets the factor, live.
 *
 * Plain C with no guest state, so scripts/test_glow.py can compile it alone.
 */
#ifndef CAT_GLOW_H
#define CAT_GLOW_H

#include <stdint.h>

/* The weight w scaled so the glow layer scales by about k: each colour byte
 * times cbrt(k), rounded and clamped to 0xFF. Byte 3 (alpha) is kept; k <= 0
 * leaves only it. */
uint32_t glow_weight(uint32_t w, double k);

/* From the glow mod (glow_mod.c: its init, then the mod frame on a live
 * change), or once from host_enhance_init without the mod API. Any thread. */
void glow_configure(int off, double k);

/* Nonzero when the wrapper must scale (off, or an intensity other than 1).
 * Zero until glow_configure: a build without the layer stays stock. */
int glow_active(void);

/* The factor the wrapper passes to glow_weight: 0 for off, else k. */
double glow_factor(void);

/* The last glow_configure's arguments (off 0 and 1 before any), for the
 * start line. Not for the wrapper: only the thread that configures, or one
 * that runs after it, reads them. */
void glow_settings(int *off, double *k);

#endif
