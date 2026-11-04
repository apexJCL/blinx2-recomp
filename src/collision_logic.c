/*
 * collision_logic.c - the collision overlay's pure part (collision_logic.h).
 */
#include "collision_logic.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

const float col_band_deg[COL_SLIVER - 1] = { 0.1f, 2.0f, 10.0f };
const char *const col_band_name[COL_BANDS] = { "flat", "near", "tilted", "slope", "sliver" };
const uint32_t col_band_rgb[COL_BANDS] = { 0x9A9A9Au, 0xF0D020u, 0xF08020u, 0xE02020u,
                                           0x4A4A4Au };

static uint32_t rd32(const uint8_t *mem, uint32_t va)
{
    uint32_t v;

    memcpy(&v, mem + va, 4);
    return v;
}

static float rdf(const uint8_t *mem, uint32_t va)
{
    float v;

    memcpy(&v, mem + va, 4);
    return v;
}

int col_normal(const float v[3][3], float n[3])
{
    float u[3], w[3], l;
    int i;

    for (i = 0; i < 3; i++) {
        u[i] = v[1][i] - v[0][i];
        w[i] = v[2][i] - v[0][i];
    }
    n[0] = u[1] * w[2] - u[2] * w[1];
    n[1] = u[2] * w[0] - u[0] * w[2];
    n[2] = u[0] * w[1] - u[1] * w[0];
    l = sqrtf(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
    if (!(l > 0.0f) || !isfinite(l)) {
        n[0] = n[1] = n[2] = 0.0f;
        return 0;
    }
    for (i = 0; i < 3; i++)
        n[i] /= l;
    return 1;
}

float col_flatness_deg(const float n[3])
{
    /* atan2 keeps tenths of a degree exact where acos of a dot near 1
     * would not (the extract's flatness_deg). */
    float off = atan2f(hypotf(n[0], n[2]), fabsf(n[1])) * (180.0f / 3.14159265358979f);

    return off < 90.0f - off ? off : 90.0f - off;
}

int col_band(float deg)
{
    int b = 0, i;

    for (i = 0; i < COL_SLIVER - 1; i++)
        b += deg >= col_band_deg[i];
    return b;
}

static int near3(const float a[3], const float b[3])
{
    return fabsf(a[0] - b[0]) <= COL_WELD && fabsf(a[1] - b[1]) <= COL_WELD &&
           fabsf(a[2] - b[2]) <= COL_WELD;
}

int col_sliver(const float v[3][3])
{
    return near3(v[0], v[1]) || near3(v[1], v[2]) || near3(v[2], v[0]);
}

float col_shade(const float n[3])
{
    /* (0.5, 1, 0.25) normalised, then y and z negated: the bake's half
     * turn about X. */
    static const float l[3] = { 0.43643578f, -0.87287156f, -0.21821789f };
    float d = fabsf(n[0] * l[0] + n[1] * l[1] + n[2] * l[2]);

    return COL_AMBIENT + (1.0f - COL_AMBIENT) * d;
}

uint32_t col_scale_rgb(uint32_t rgb, float s)
{
    uint32_t out = 0;
    int k;

    for (k = 16; k >= 0; k -= 8) {
        float c = (float)((rgb >> k) & 0xFFu) * s + 0.5f;

        out |= (uint32_t)(c > 255.0f ? 255.0f : c < 0.0f ? 0.0f : c) << k;
    }
    return out;
}

static uint32_t fnv(uint32_t h, const uint8_t *p, size_t n)
{
    while (n--)
        h = (h ^ *p++) * 16777619u;
    return h;
}

static uint32_t tri_count(const uint8_t *mem)
{
    uint32_t n = rd32(mem, COL_TRI_COUNT);

    return n > (uint32_t)COL_TRI_MAX ? (uint32_t)COL_TRI_MAX : n;
}

uint32_t col_stage_key(const uint8_t *mem)
{
    uint32_t n = tri_count(mem), h = 2166136261u, i;

    h = fnv(h, (const uint8_t *)&n, 4);
    for (i = 0; i < n; i += 16)
        h = fnv(h, mem + COL_TRI_BUF + i * COL_TRI_SIZE, 0x28);
    if (n)
        h = fnv(h, mem + COL_TRI_BUF + (n - 1) * COL_TRI_SIZE, 0x28);
    return h;
}

/* ---- the edges (the extract's crease_edges, per class) ------------------- */

/* Weld cells: round(c / WELD) per axis, with the class, hashed into an
 * open-addressed table of point ids. */
#define PT_MAX  (COL_TRI_MAX * 3)
#define PT_HASH (1u << 16)              /* > 2 * PT_MAX */
#define ED_HASH (1u << 16)

struct weld {
    float p[PT_MAX][3];
    int32_t cell[PT_MAX][3];
    uint32_t cls[PT_MAX];
    int n;
    int32_t slot[PT_HASH];              /* point id + 1, 0 empty */
};

struct edge {
    int32_t a, b;                       /* point ids, a < b; a == -1 empty */
    int32_t tri;                        /* the first face on it, and its edge */
    uint8_t k, crease;
    uint16_t faces;
    float n0[3];
};

static uint32_t cell_hash(const int32_t c[3], uint32_t cls)
{
    uint32_t h = (uint32_t)c[0] * 73856093u ^ (uint32_t)c[1] * 19349663u ^
                 (uint32_t)c[2] * 83492791u ^ cls * 2654435761u;

    return h & (PT_HASH - 1);
}

static int weld_id(struct weld *w, const float p[3], uint32_t cls)
{
    int32_t k[3], c[3];
    int d0, d1, d2, i;
    uint32_t h;

    for (i = 0; i < 3; i++) {
        float q = p[i] / COL_WELD;

        /* lroundf is undefined past long's range (32 bits on Windows) and
         * the cell is an int32: a corner off the grid gets no point, so
         * its face is drawn without edges. */
        if (!(fabsf(q) < 2.0e9f))
            return -1;
        k[i] = (int32_t)lroundf(q);
    }
    /* Two corners within WELD can round into neighbouring cells. */
    for (d0 = -1; d0 <= 1; d0++)
        for (d1 = -1; d1 <= 1; d1++)
            for (d2 = -1; d2 <= 1; d2++) {
                c[0] = k[0] + d0;
                c[1] = k[1] + d1;
                c[2] = k[2] + d2;
                for (h = cell_hash(c, cls); w->slot[h]; h = (h + 1) & (PT_HASH - 1)) {
                    int q = w->slot[h] - 1;

                    if (w->cls[q] == cls && !memcmp(w->cell[q], c, sizeof c) &&
                        near3(w->p[q], p))
                        return q;
                }
            }
    if (w->n >= PT_MAX)
        return -1;
    i = w->n++;
    memcpy(w->p[i], p, sizeof w->p[i]);
    memcpy(w->cell[i], k, sizeof k);
    w->cls[i] = cls;
    for (h = cell_hash(k, cls); w->slot[h]; h = (h + 1) & (PT_HASH - 1))
        ;
    w->slot[h] = i + 1;
    return i;
}

static struct edge *edge_get(struct edge *e, int32_t a, int32_t b)
{
    uint32_t h = ((uint32_t)a * 2654435761u ^ (uint32_t)b * 40503u) & (ED_HASH - 1);

    for (;; h = (h + 1) & (ED_HASH - 1)) {
        if (e[h].a < 0) {
            /* Every field: find_edges reads faces before it sets tri. */
            memset(&e[h], 0, sizeof e[h]);
            e[h].a = a;
            e[h].b = b;
            return &e[h];
        }
        if (e[h].a == a && e[h].b == b)
            return &e[h];
    }
}

static void find_edges(struct col_stage *s)
{
    struct weld *w = calloc(1, sizeof *w);
    struct edge *e = calloc(ED_HASH, sizeof *e);
    const float cos_max = cosf(COL_CREASE_DEG * (3.14159265358979f / 180.0f));
    uint32_t h;
    int i, k;

    s->creases = s->opens = 0;
    if (!w || !e) {
        free(w);
        free(e);
        return;
    }
    for (h = 0; h < ED_HASH; h++)
        e[h].a = -1;
    for (i = 0; i < s->n; i++) {
        struct col_tri *t = &s->t[i];
        int v[3];

        if (!t->ok)
            continue;
        for (k = 0; k < 3; k++)
            v[k] = weld_id(w, t->v[k], t->cls);
        /* A triangle with two welded corners is left out. */
        if (v[0] < 0 || v[1] < 0 || v[2] < 0 || v[0] == v[1] || v[1] == v[2] || v[2] == v[0])
            continue;
        for (k = 0; k < 3; k++) {
            int a = v[k], b = v[(k + 1) % 3];
            struct edge *x = edge_get(e, a < b ? a : b, a < b ? b : a);

            if (!x->faces) {
                x->tri = i;
                x->k = (uint8_t)k;
                memcpy(x->n0, t->n, sizeof x->n0);
            } else if (fabsf(x->n0[0] * t->n[0] + x->n0[1] * t->n[1] + x->n0[2] * t->n[2]) <
                       cos_max) {
                /* A face's two sides are one plane: a seam wound either
                 * way is coplanar, a fold past 180 - 20 degrees too. */
                x->crease = 1;
            }
            if (x->faces < 0xFFFF)
                x->faces++;
        }
    }
    for (h = 0; h < ED_HASH; h++) {
        if (e[h].a < 0 || !(e[h].faces == 1 || e[h].crease))
            continue;
        if (e[h].tri < 0 || e[h].tri >= s->n || e[h].k > 2)
            continue;
        s->t[e[h].tri].edges |= (uint8_t)(1u << e[h].k);
        if (e[h].faces == 1)
            s->opens++;
        else
            s->creases++;
    }
    free(w);
    free(e);
}

int col_stage_load(struct col_stage *s, const uint8_t *mem)
{
    uint32_t n = tri_count(mem), i;
    int j, k;

    for (i = 0; i < n; i++) {
        const uint8_t *rec = mem + COL_TRI_BUF + i * COL_TRI_SIZE;
        struct col_tri *t = &s->t[i];
        float r2 = 0;

        memset(t, 0, sizeof *t);
        for (j = 0; j < 3; j++)
            for (k = 0; k < 3; k++)
                memcpy(&t->v[j][k], rec + 0x0C * (uint32_t)j + 4 * (uint32_t)k, 4);
        memcpy(&t->cls, rec + 0x24, 4);
        t->cls &= 0xFFFFFFu;
        t->ok = (uint8_t)col_normal(t->v, t->n);
        for (k = 0; k < 3; k++)
            t->c[k] = (t->v[0][k] + t->v[1][k] + t->v[2][k]) / 3.0f;
        for (j = 0; j < 3; j++) {
            float d = 0;

            for (k = 0; k < 3; k++)
                d += (t->v[j][k] - t->c[k]) * (t->v[j][k] - t->c[k]);
            if (d > r2)
                r2 = d;
        }
        t->r = sqrtf(r2);
        if (!isfinite(t->r))
            t->ok = 0;
        t->shade = col_shade(t->n);
        /* A sliver's normal is noise, so it gets a band of its own. */
        t->band = (uint8_t)(col_sliver(t->v) ? COL_SLIVER : col_band(col_flatness_deg(t->n)));
    }
    s->n = (int)n;
    find_edges(s);
    s->key = col_stage_key(mem);
    return s->n;
}

/* ---- the octree walk ------------------------------------------------------ */

static int node_of(uint32_t p, uint32_t nodes)
{
    uint32_t d;

    if (p < COL_NODE_BUF)
        return -1;
    d = p - COL_NODE_BUF;
    if (d % COL_NODE_SIZE || d / COL_NODE_SIZE >= nodes)
        return -1;
    return (int)(d / COL_NODE_SIZE);
}

static int box_meets(const uint8_t *mem, uint32_t node, const float c[3], float r)
{
    float h = rdf(mem, node + COL_NODE_HALF) + COL_NODE_PAD, d2 = 0;
    int k;

    if (!(h > 0.0f) || !isfinite(h))
        return 0;
    for (k = 0; k < 3; k++) {
        float m = rdf(mem, node + COL_NODE_CENTRE + 4 * (uint32_t)k), e;

        if (!isfinite(m))
            return 0;
        e = fabsf(c[k] - m) - h;
        if (e > 0)
            d2 += e * e;
    }
    return d2 <= r * r;
}

int col_query(const struct col_stage *s, const uint8_t *mem, const float c[3], float r,
              uint32_t *mark, uint32_t stamp, int *out, int cap)
{
    static int stack[COL_NODE_MAX + 8];
    uint32_t nodes = rd32(mem, COL_NODE_COUNT), refs = rd32(mem, COL_REF_COUNT);
    uint32_t tris = (uint32_t)s->n;
    int sp = 0, got = 0, visits = 0, steps = 0;

    if (nodes > (uint32_t)COL_NODE_MAX)
        nodes = (uint32_t)COL_NODE_MAX;
    if (refs > (uint32_t)COL_REF_MAX)
        refs = (uint32_t)COL_REF_MAX;
    if (!nodes || !tris || rd32(mem, COL_TRI_COUNT) != tris)
        return 0;
    stack[sp++] = 0;
    /* A tree visits each node once; a cycle (a bake in progress) stops at
     * the node count. */
    while (sp && visits++ < (int)nodes) {
        uint32_t node = COL_NODE_BUF + (uint32_t)stack[--sp] * COL_NODE_SIZE, p, k;
        uint32_t n;

        if (!box_meets(mem, node, c, r))
            continue;
        p = rd32(mem, node + COL_NODE_HEAD);
        n = rd32(mem, node + COL_NODE_NREF);
        for (k = 0; k < n && p && steps < COL_REF_MAX; k++, steps++) {
            uint32_t d, t, ti;

            if (p < COL_REF_BUF || (d = p - COL_REF_BUF) % COL_REF_SIZE ||
                d / COL_REF_SIZE >= refs)
                break;
            t = rd32(mem, p);
            p = rd32(mem, p + 4);
            if (t < COL_TRI_BUF || (t - COL_TRI_BUF) % COL_TRI_SIZE ||
                (ti = (t - COL_TRI_BUF) / COL_TRI_SIZE) >= tris || mark[ti] == stamp)
                continue;
            mark[ti] = stamp;
            if (s->t[ti].ok && got < cap) {
                const struct col_tri *x = &s->t[ti];
                float dd = 0, rr = r + x->r;
                int j;

                for (j = 0; j < 3; j++)
                    dd += (x->c[j] - c[j]) * (x->c[j] - c[j]);
                if (dd <= rr * rr)
                    out[got++] = (int)ti;
            }
        }
        for (k = 0; k < 8 && sp < (int)(sizeof stack / sizeof stack[0]); k++) {
            int ch = node_of(rd32(mem, node + COL_NODE_KIDS + 4 * k), nodes);

            if (ch > 0)
                stack[sp++] = ch;
        }
    }
    return got;
}
