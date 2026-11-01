/*
 * wall_logic.c - the walls mod's thin-wall rule (wall_logic.h).
 */
#include <math.h>
#include <string.h>
#include "wall_logic.h"

static float rdf(const uint8_t *p)
{
    float f;

    memcpy(&f, p, 4);
    return f;
}

void wall_tri_load(struct wall_tri *t, const uint8_t *rec)
{
    int i, j;

    for (i = 0; i < 3; i++)
        for (j = 0; j < 3; j++)
            t->v[i][j] = rdf(rec + i * 0xC + j * 4);
    for (j = 0; j < 3; j++) {
        t->n[j] = rdf(rec + 0x2C + j * 4);
        t->centroid[j] = rdf(rec + 0x38 + j * 4);
    }
    t->radius = rdf(rec + 0x44);
    t->cls = (uint32_t)rec[0x24] | (uint32_t)rec[0x25] << 8 | (uint32_t)rec[0x26] << 16 |
             (uint32_t)rec[0x27] << 24;
}

static float dot3(const float a[3], const float b[3])
{
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

float wall_s(const struct wall_tri *t, const float p[3])
{
    float d[3] = { p[0] - t->v[0][0], p[1] - t->v[0][1], p[2] - t->v[0][2] };

    return dot3(d, t->n);
}

/* Each edge's cross product with the projection, pairwise in the same
 * direction (or zero): the game's three sign checks against 0.0f. */
int wall_inside(const struct wall_tri *t, const float c[3], float s)
{
    float p[3], x[3][3];
    int i;

    for (i = 0; i < 3; i++)
        p[i] = c[i] - t->n[i] * s;
    for (i = 0; i < 3; i++) {
        const float *a = t->v[i], *b = t->v[(i + 1) % 3];
        float e[3] = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
        float q[3] = { a[0] - p[0], a[1] - p[1], a[2] - p[2] };

        x[i][0] = e[1] * q[2] - e[2] * q[1];
        x[i][1] = e[2] * q[0] - e[0] * q[2];
        x[i][2] = e[0] * q[1] - e[1] * q[0];
    }
    return dot3(x[0], x[1]) >= 0.0f && dot3(x[1], x[2]) >= 0.0f && dot3(x[0], x[2]) >= 0.0f;
}

int wall_skipped(uint32_t cls, const uint32_t sw[4])
{
    switch (cls & 0xFFFFFFu) {
    case WALL_CLASS_NONE:
        return 1;
    case WALL_CLASS_A:
        return sw[0] != 0;
    case WALL_CLASS_B:
        return sw[1] != 0;
    case WALL_CLASS_C:
        return sw[2] != 0;
    case WALL_CLASS_D:
        return sw[3] != 0;
    default:
        return 0;
    }
}

/* A baked normal is unit length; anything else (a degenerate triangle, a
 * zero or NaN normal) gives no usable side, so the rule leaves it alone.
 * The comparison is false for NaN. */
static int unit_normal(const struct wall_tri *t)
{
    float l = dot3(t->n, t->n);

    return l > 0.5f && l < 1.5f;
}

int wall_entry_face(const struct wall_tri *tris, int n, int x, const float c[3],
                    const float prev[3], float r, const uint32_t sw[4])
{
    const struct wall_tri *tx;
    int i, best = -1;
    float best_s = 0;

    if (x < 0 || x >= n || !unit_normal(&tris[x]))
        return -1;
    tx = &tris[x];
    if (!(wall_s(tx, c) < 0.0f) || !(wall_s(tx, prev) < -WALL_EPS))
        return -1;          /* the centre came from x's front: its push is right */
    for (i = 0; i < n; i++) {
        const struct wall_tri *ty = &tris[i];
        float s;

        if (i == x || wall_skipped(ty->cls, sw) || !unit_normal(ty) ||
            !(dot3(tx->n, ty->n) < -0.5f))
            continue;
        s = wall_s(ty, c);
        if (!(fabsf(s) <= r) || !(wall_s(ty, prev) >= -WALL_EPS) || !wall_inside(ty, c, s))
            continue;
        if (best < 0 || s < best_s) {
            best = i;
            best_s = s;
        }
    }
    return best;
}

int wall_vertex_edge(const struct wall_tri *t, int ti, const float c[3], float r, uint32_t flags,
                     struct wall_contact *out)
{
    float best = 0, p[3] = { 0, 0, 0 };
    int i, j, have = 0;

    for (i = 0; i < 3 && (flags & WALL_FLAG_VERTS); i++) {
        float d[3], dd;

        for (j = 0; j < 3; j++)
            d[j] = c[j] - t->v[i][j];
        dd = sqrtf(dot3(d, d));
        if (!(dd <= r) || !(dd > 0.0f) || (have && !(dd < best)))
            continue;
        have = 1;
        best = dd;
        memcpy(p, t->v[i], sizeof p);
    }
    for (i = 0; i < 3 && (flags & WALL_FLAG_EDGES); i++) {
        const float *a = t->v[i], *b = t->v[(i + 1) % 3];
        float e[3], q[3], len, u, dd, f[3];

        for (j = 0; j < 3; j++) {
            e[j] = b[j] - a[j];
            q[j] = c[j] - a[j];
        }
        len = sqrtf(dot3(e, e));
        if (!(len > 0.0f))
            continue;
        u = dot3(q, e) / len;
        if (!(u >= 0.0f && u <= len))
            continue;
        for (j = 0; j < 3; j++)
            f[j] = a[j] + e[j] * (u / len);
        for (j = 0; j < 3; j++)
            q[j] = c[j] - f[j];
        dd = sqrtf(dot3(q, q));
        if (!(dd <= r) || !(dd > 0.0f) || (have && !(dd < best)))
            continue;
        have = 1;
        best = dd;
        memcpy(p, f, sizeof p);
    }
    if (!have)
        return 0;
    for (j = 0; j < 3; j++) {
        out->p[j] = p[j];
        out->n[j] = (c[j] - p[j]) / best;
    }
    out->pen = r - best;
    out->best = best;
    out->cls = t->cls;
    out->tri = ti;
    return 1;
}

int wall_decide(const struct wall_tri *tris, int n, int x, const float c[3], const float delta[3],
                float r, uint32_t flags, const uint32_t sw[4], float best0, float best,
                float push_k, struct wall_contact *out, int *y)
{
    struct wall_contact ve;
    const struct wall_tri *ty;
    float prev[3], step = 0, sy;
    int j, have_ve;

    *y = -1;
    if (!delta || x < 0 || x >= n || !(best < 0.0f) || !(best <= best0))
        return WALL_KEEP;
    /* The test took x's face, not one of its vertices or edges (whose
     * values are distances, never negative). */
    if (!(fabsf(best - wall_s(&tris[x], c)) < 1e-4f))
        return WALL_KEEP;
    for (j = 0; j < 3; j++) {
        step += delta[j] * delta[j];
        prev[j] = c[j] - delta[j];
    }
    if (!(step <= WALL_STEP_MAX * WALL_STEP_MAX * r * r))
        return WALL_KEEP;
    *y = wall_entry_face(tris, n, x, c, prev, r, sw);
    if (*y < 0)
        return WALL_KEEP;
    ty = &tris[*y];
    sy = wall_s(ty, c);
    /* Without x's face the test would have left the earlier contact or
     * taken x's own vertex or edge; the entry face must beat that, by the
     * game's strict comparison, or the earlier one stands. */
    have_ve = wall_vertex_edge(&tris[x], x, c, r, flags, &ve) && ve.best < best0;
    if (!(sy < (have_ve ? ve.best : best0))) {
        if (!have_ve)
            return WALL_RESTORE;
        *out = ve;
        return WALL_WRITE;
    }
    for (j = 0; j < 3; j++) {
        out->p[j] = c[j] - ty->n[j] * sy;
        out->n[j] = ty->n[j];
    }
    out->pen = (r - sy) * push_k;
    out->best = sy;
    out->cls = ty->cls;
    out->tri = *y;
    return WALL_WRITE;
}

int wall_pair(const struct wall_tri *tris, int n, int f, float wmax, const uint32_t sw[4],
              float *w)
{
    const struct wall_tri *tf = &tris[f];
    int i, best = -1;
    float best_w = 0;

    if (wall_skipped(tf->cls, sw) || fabsf(tf->n[1]) >= 0.7f)
        return -1;
    for (i = 0; i < n; i++) {
        const struct wall_tri *tb = &tris[i];
        float s;

        if (i == f || wall_skipped(tb->cls, sw) || dot3(tf->n, tb->n) >= -0.9f)
            continue;
        s = wall_s(tb, tf->centroid);
        if (s >= 0.0f || -s >= wmax || !wall_inside(tb, tf->centroid, s))
            continue;
        if (best < 0 || -s < best_w) {
            best = i;
            best_w = -s;
        }
    }
    if (best >= 0)
        *w = best_w;
    return best;
}
