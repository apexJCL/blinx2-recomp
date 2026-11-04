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

int cry_grants(const uint8_t *s, int c, int k)
{
    int i, n = 0, len = cry_row_len(s, c);

    for (i = 0; i < len; i++)
        n += cry_row_at(s, c, i) == k;
    return n + 1 >= 3;
}

int cry_push(uint8_t *s, int c, int k, uint16_t w)
{
    int len = cry_row_len(s, c), i, hearts = 0;

    if (len + 1 >= CRY_ROW) {
        cry_clear(s, c);
        return 0;
    }
    s[c * CRY_COLOURS + len] = (uint8_t)(k + 1);
    wr16(s, CRY_WORD(c, 0, len), w);
    /* The stock lit hearts show a partial set of up to two; the row's
     * three hearts have granted, so they light two as well. */
    for (i = 0; i <= len; i++)
        hearts += cry_row_at(s, c, i) == CRY_RETRY;
    s[c * CRY_COLOURS + CRY_RETRY] = (uint8_t)(hearts < 2 ? hearts : 2);
    return len + 1;
}

void cry_clear(uint8_t *s, int c)
{
    int i;

    memset(s + c * CRY_COLOURS, 0, CRY_COLOURS);
    for (i = 0; i < CRY_ROW; i++)
        wr16(s, CRY_WORD(c, 0, i), 0);
}

int cry_icon(int k, int heart_loaded)
{
    if (k < 0 || k >= CRY_COLOURS)
        return CRY_ICON_EMPTY;
    if (k == CRY_RETRY)
        return heart_loaded ? CRY_ICON_HEART : CRY_ICON_EMPTY;
    return CRY_ICON_COLOUR;
}

/* Set c's counts in dst (a copy of src) for the game's pickup; returns the
 * slot the game will write the word to, poisoned with ~w. */
static int prepare(const uint8_t *src, uint8_t *dst, int c, int k, uint16_t w)
{
    int len = cry_row_len(src, c), i, n = 0, slot = 0;
    uint16_t words[CRY_ROW];

    memset(dst + c * CRY_COLOURS, 0, CRY_COLOURS);
    if (cry_grants(src, c, k)) {
        /* The game copies slots 0..2 into the control's words: the set's
         * last two earlier crystals of k, then this one. */
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

void cry_pickup_begin(struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int k, uint16_t w)
{
    int t, c;

    p->k = k;
    p->w = w;
    for (t = 0; t < CRY_TEAMS; t++) {
        memcpy(p->snap[t], span[t], CRY_SPAN);
        for (c = 0; c < CRY_CHARS; c++)
            p->slot[t][c] = (uint8_t)prepare(p->snap[t], span[t], c, k, w);
    }
}

void cry_pickup_undo(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS])
{
    int t;

    for (t = 0; t < CRY_TEAMS; t++)
        memcpy(span[t], p->snap[t], CRY_SPAN);
}

int cry_settle(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int *depth, int *active)
{
    int undid = *active && span;

    if (undid)
        cry_pickup_undo(p, span);
    *depth = 0;
    *active = 0;
    return undid;
}

int cry_pickup_end(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int *team, int *ch)
{
    int t, c, ft = -1, fc = -1, set;

    /* The game writes the word only for the character it counts, so the
     * one poisoned slot that now holds w names it. */
    for (t = 0; t < CRY_TEAMS && ft < 0; t++)
        for (c = 0; c < CRY_CHARS; c++)
            if (rd16(span[t], CRY_WORD(c, p->k, p->slot[t][c])) == p->w) {
                ft = t;
                fc = c;
                break;
            }
    cry_pickup_undo(p, span);
    *team = ft;
    *ch = fc;
    if (ft < 0)
        return 0;
    set = cry_grants(span[ft], fc, p->k);
    cry_push(span[ft], fc, p->k, p->w);
    return set ? 2 : 1;
}

void cry_quad(const float *tpl, float *out, float x, float y, float scale, int own_uv)
{
    float cx = 0, cy = 0;
    int i;

    for (i = 0; i < 4; i++) {
        cx += tpl[i * 4] / 4;
        cy += tpl[i * 4 + 1] / 4;
    }
    for (i = 0; i < 4; i++) {
        const float *v = tpl + i * 4;

        out[i * 4] = x + (v[0] - cx) * scale;
        out[i * 4 + 1] = y + (v[1] - cy) * scale;
        out[i * 4 + 2] = own_uv ? (float)(v[0] > cx) : v[2];
        out[i * 4 + 3] = own_uv ? (float)(v[1] > cy) : v[3];
    }
}
