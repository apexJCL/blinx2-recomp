/*
 * crystals_logic.c - the crystal row's rules (crystals_logic.h).
 */
#include <string.h>
#include "crystals_logic.h"

const uint8_t cry_k_to_id[CRY_COLOURS] = { 2, 6, 4, 1, 5, 3 };

static uint16_t rd16(const uint8_t *s, unsigned off)
{
    return (uint16_t)(s[off] | s[off + 1] << 8);
}

static void wr16(uint8_t *s, unsigned off, uint16_t v)
{
    s[off] = (uint8_t)v;
    s[off + 1] = (uint8_t)(v >> 8);
}

int cry_row_at(const uint8_t *s, int c, int i)
{
    int v = s[c * CRY_COLOURS + i];

    return v >= 1 && v <= CRY_COLOURS ? v - 1 : -1;
}

int cry_row_len(const uint8_t *s, int c)
{
    int i;

    for (i = 0; i < CRY_ROW - 1; i++)
        if (cry_row_at(s, c, i) < 0)
            break;
    return i;
}

int cry_row_count(const uint8_t *s, int c, int k)
{
    int i, n = 0, len = cry_row_len(s, c);

    for (i = 0; i < len; i++)
        n += cry_row_at(s, c, i) == k;
    return n;
}

int cry_grants(const uint8_t *s, int c, int k)
{
    return cry_row_count(s, c, k) + 1 >= 3;
}

int cry_prepare(const uint8_t *src, uint8_t *dst, int c, int k, uint16_t w)
{
    int len = cry_row_len(src, c), i, n = 0, slot = 0;
    uint16_t words[CRY_ROW];

    memset(dst + c * CRY_COLOURS, 0, CRY_COLOURS);
    if (cry_grants(src, c, k)) {
        /* The set's earlier crystals of k, the last two when there are
         * three: the game copies slots 0..2 into the control's words. */
        for (i = 0; i < len; i++)
            if (cry_row_at(src, c, i) == k)
                words[n++] = rd16(src, CRY_WORD(c, 0, i));
        wr16(dst, CRY_WORD(c, k, 0), words[n - 2]);
        wr16(dst, CRY_WORD(c, k, 1), words[n - 1]);
        dst[c * CRY_COLOURS + k] = 2;
        slot = 2;
    }
    wr16(dst, CRY_WORD(c, k, slot), (uint16_t)~w);
    return slot;
}

int cry_counted(const uint8_t *dst, int c, int k, int slot, uint16_t w)
{
    return rd16(dst, CRY_WORD(c, k, slot)) == w;
}

int cry_push(uint8_t *s, int c, int k, uint16_t w)
{
    int len = cry_row_len(s, c);

    if (len + 1 >= CRY_ROW) {
        cry_clear(s, c);
        return 0;
    }
    s[c * CRY_COLOURS + len] = (uint8_t)(k + 1);
    wr16(s, CRY_WORD(c, 0, len), w);
    return len + 1;
}

void cry_clear(uint8_t *s, int c)
{
    int i;

    memset(s + c * CRY_COLOURS, 0, CRY_COLOURS);
    for (i = 0; i < CRY_ROW; i++)
        wr16(s, CRY_WORD(c, 0, i), 0);
}

int cry_settle(int *depth, int *active)
{
    int restore = *active;

    *depth = 0;
    *active = 0;
    return restore;
}
