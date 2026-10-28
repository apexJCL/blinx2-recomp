/* pad_pack.h - the title's 18-byte XINPUT_GAMEPAD from the host's
 * XBOX_GAMEPAD. cat_pad_get_state merges and filters an XBOX_GAMEPAD (the
 * toolkit's shape, which the host actions' pad filter takes as part of an
 * XBOX_INPUT_STATE) and hands the title this packing; header-only so
 * scripts/test_pad_pack.py can compile it alone. */
#ifndef CAT_PAD_PACK_H
#define CAT_PAD_PACK_H

#include <stdint.h>
#include <string.h>
#include "xinput_xbox.h"

/* XINPUT_GAMEPAD, packed little-endian: wButtons, bAnalogButtons[8],
 * sThumbLX, sThumbLY, sThumbRX, sThumbRY. */
static inline void cat_pad_pack(const XBOX_GAMEPAD *g, uint8_t out[18])
{
    const SHORT ax[4] = { g->sThumbLX, g->sThumbLY, g->sThumbRX, g->sThumbRY };

    out[0] = (uint8_t)g->wButtons;
    out[1] = (uint8_t)(g->wButtons >> 8);
    memcpy(out + 2, g->bAnalogButtons, 8);
    for (int i = 0; i < 4; i++) {
        out[10 + 2 * i] = (uint8_t)ax[i];
        out[11 + 2 * i] = (uint8_t)((uint16_t)ax[i] >> 8);
    }
}

#endif /* CAT_PAD_PACK_H */
