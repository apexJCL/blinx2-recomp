/*
 * walls_mod.c - the walls mod (walls_mod.h; openspec change
 * collision-spike, tasks 1.6 and 1.7).
 *
 * The player's collision sphere slides through walls thinner than twice its
 * radius. The sphere query (sub_001636C0) walks the triangles near the
 * centre (sub_00165380) and keeps one contact: each triangle test
 * (sub_00165630) takes a vertex, an edge or a face only when its value is
 * at most the best so far, and a face's value is its signed distance. A
 * centre that went into a thin wall through its near face F is deeper
 * behind the far face B while it is less than half-way in, so B wins and
 * its push carries the sphere out of the far side (wall_logic.h).
 *
 * The fix runs in a post hook on the triangle test, only inside the
 * player's queries: when the test has just taken a face the centre is
 * behind, and the centre one frame earlier was behind it too, the face the
 * sphere entered by (wall_entry_face) becomes the contact instead, or, when
 * the walk has already taken something better than that face, the test's
 * outputs go back to what they were (or to the same triangle's own edge,
 * when that beat them; wall_decide). The walk, the dynamic objects
 * (sub_00163160) and the push stay the game's.
 *
 * Experimental: the rule is shown on the game's triangle test only (the
 * task 1.7 probe); a pass-through in play is not reproduced (design.md section 6).
 *
 * Off (the default, every golden): the hooks do not run, on_frame returns
 * before reading the guest, and no guest memory is allocated.
 *
 * RECOMP_DEBUG=walls_trace=<opts> logs every player query, each contact
 * the walk takes in it, the dynamic objects' answer and the push (task
 * 1.6), and can run the A/B probes of task 1.7 (opts below, at init).
 */
#include <stddef.h>
#include "walls_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define WALLS_MOD 1
#    endif
#  endif
#endif

#ifdef WALLS_MOD

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "enhance_menu.h"
#include "recomp_env.h"
#include "wall_logic.h"

enum { SET_ENABLE, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_WALLS", NULL, "Thin-wall fix (experimental)",
      "Meant to stop the player from sliding through thin walls: when the"
      " collision sphere has gone into a wall, the side it went in by pushes"
      " it back out, not the wall's far side. Experimental: shown only by a"
      " probe of the game's triangle test; sliding through in play is not"
      " reproduced, and the fix never acted in 5600 frames of play. Off is"
      " the stock game.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Walls",
    "Thin-wall tunneling fix", NULL, "1",
    k_set, SET_N, NULL, 0
};

/* The sphere query: cdecl (cx, cy, cz, r, ...), the out centre at edi;
 * returns the hit in eax and in [0xB90B88]. Before it returns, the contact
 * normal is at its entry esp - 0x28 and the push length at esp + 0x10 (the
 * r argument's slot): out = centre + normal * push. */
#define VA_QUERY        0x001636C0u
#define VA_QUERY_HIT    0x00B90B88u
#define Q_NORMAL        0x28u           /* below the entry esp */
#define Q_PEN           0x10u           /* above it */
/* The dynamic objects' query, called by sub_00163550 after the walk; its
 * contact overrides the walk's at 0x163647. Returns 0 or 1. */
#define VA_DYNAMIC      0x00163160u
/* The triangle test: cdecl (tri, centre*, r, flags, point*, normal*, pen*,
 * class*, best*); returns 1 when it took a contact. */
#define VA_FACE         0x00165630u
#define VA_STAMP        0x00EC5000u     /* the walk's query stamp */
#define VA_PEN_K        0x003DEFFCu     /* a face's push factor, 1.1 */
#define VA_SWITCH_A     0x0065B1E0u
#define VA_SWITCH_B     0x0065B1E8u
#define VA_SWITCH_C     0x0065B1ECu
#define VA_SWITCH_D     0x0065B1F0u
#define BEST_INIT       99999.0f

/* The player's calls of the sphere query, by return address. */
static const uint32_t k_sites[] = { 0x00178F92u, 0x00184F26u, 0x00185063u, 0x00185239u,
                                    0x00185503u, 0x00185959u, 0x00185B65u };
#define N_SITES ((int)(sizeof k_sites / sizeof k_sites[0]))

#define VA_PLAYERS      0x00CD2440u
#define PLAYER_SIZE     0x30Cu
#define PLAYER_POS      0xECu
#define PLAYER_PREV     0xF8u
#define N_PLAYERS       4
/* A query belongs to the nearest player whose position is this close to
 * its centre (the sites' offsets are a few units). */
#define PLAYER_NEAR     12.0f

#define BLOCK_SIZE      0x100u
#define GUEST_TOP       0x04000000u
#define MAX_PAIRS       4096

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

static int s_on;                        /* guest thread */
static unsigned s_frame;
static uint32_t s_qid;                  /* the trace's query number */
static int s_fixed, s_kept;             /* this run; the menu reads them */

/* The triangles, copied once a frame at first use (guest thread). */
static struct wall_tri s_tris[WALL_TRI_MAX];
static int s_ntris;
static unsigned s_tris_frame = ~0u;
static uint32_t s_sw[4];

/* The player query in flight. */
static struct {
    int active, player, site, dyn, n_acc, last_tri, fix_y;
    float c[3], r, delta[3], pos[3], prev[3];
    float sn[3];                        /* the walk's last contact normal */
} s_q;

/* The triangle test in flight: its arguments and outputs before it ran. */
static struct {
    uint32_t tri, cp, flags, pt, np, penp, clsp, bestp;
    float r, best0, pt0[3], n0[3], pen0;
    uint32_t cls0;
} s_fc;

/* walls_trace options (s_out set: tracing). */
static FILE *s_out;
static int o_fix = -1;                  /* -1: the setting decides */
static long o_probe = -1, o_samples = 2000, o_rad = 295, o_wmax = 0;
static long o_tp = -1, o_tp_at = -1, o_depth = 30, o_tp_for = 120;
static int s_probing, s_hooked;
static uint32_t s_flags_seen = 7;     /* the player's test flags, once seen */
static uint32_t s_block;
static float s_off[3];                  /* player 0's centre - position */
static int s_have_off;
static struct { int f, b; float w; } s_pairs[MAX_PAIRS];
static int s_npairs;
static int s_tp_f = -1, s_tp_b = -1;
static unsigned s_tp_until;
static int s_tp_pending;                /* the next player 0 query steps in */
static float s_tp_c[3];
static uint32_t s_sw_last[4];
static int s_sw_seen;

static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(s_api, va); }
static inline float rdf(uint32_t va) { return XBOX_MOD_MEMF(s_api, va); }
static inline void wrf(uint32_t va, float f) { XBOX_MOD_MEMF(s_api, va) = f; }

static void rd3(uint32_t va, float v[3])
{
    v[0] = rdf(va);
    v[1] = rdf(va + 4);
    v[2] = rdf(va + 8);
}

static void wr3(uint32_t va, const float v[3])
{
    wrf(va, v[0]);
    wrf(va + 4, v[1]);
    wrf(va + 8, v[2]);
}

static int fixing(void)
{
    return o_fix >= 0 ? o_fix : 1;
}

static void read_switches(void)
{
    s_sw[0] = rd32(VA_SWITCH_A);
    s_sw[1] = rd32(VA_SWITCH_B);
    s_sw[2] = rd32(VA_SWITCH_C);
    s_sw[3] = rd32(VA_SWITCH_D);
}

/* The baked buffer changes only with the stage, but a copy a frame is a
 * few hundred kilobytes at most, and only on a frame where a player's
 * centre went behind a face (or the trace runs). */
static void load_tris(void)
{
    uint32_t n;
    int i;

    if (s_tris_frame == s_frame)
        return;
    s_tris_frame = s_frame;
    n = rd32(WALL_TRI_COUNT);
    if (n > (uint32_t)WALL_TRI_MAX)
        n = (uint32_t)WALL_TRI_MAX;
    for (i = 0; i < (int)n; i++)
        wall_tri_load(&s_tris[i], (const uint8_t *)(s_api->mem + WALL_TRI_BUF +
                                                    (uint32_t)i * WALL_TRI_SIZE));
    s_ntris = (int)n;
    read_switches();
}

static int tri_index(uint32_t tri)
{
    uint32_t d;

    if (tri < WALL_TRI_BUF)
        return -1;
    d = tri - WALL_TRI_BUF;
    if (d % WALL_TRI_SIZE || d / WALL_TRI_SIZE >= (uint32_t)s_ntris)
        return -1;
    return (int)(d / WALL_TRI_SIZE);
}

/* ---- the sphere query --------------------------------------------------- */

static int site_of(uint32_t ret)
{
    int i;

    for (i = 0; i < N_SITES; i++)
        if (k_sites[i] == ret)
            return i;
    return -1;
}

static void query_pre(struct xbox_mod_call *c, void *user)
{
    float best = PLAYER_NEAR * PLAYER_NEAR;
    int site, i, j;

    (void)user;
    site = site_of(rd32(c->esp));
    if (site < 0 || s_q.active || s_probing)
        return;
    memset(&s_q, 0, sizeof s_q);
    s_q.active = 1;
    s_q.site = site;
    s_q.player = -1;
    s_q.last_tri = -1;
    s_q.fix_y = -1;
    s_qid++;
    for (i = 0; i < 3; i++)
        s_q.c[i] = XBOX_MOD_ARGF(s_api, c, i);
    s_q.r = XBOX_MOD_ARGF(s_api, c, 3);
    for (i = 0; i < N_PLAYERS; i++) {
        uint32_t p = VA_PLAYERS + (uint32_t)i * PLAYER_SIZE;
        float pos[3], d = 0;

        rd3(p + PLAYER_POS, pos);
        for (j = 0; j < 3; j++)
            d += (s_q.c[j] - pos[j]) * (s_q.c[j] - pos[j]);
        if (d < best) {
            best = d;
            s_q.player = i;
            memcpy(s_q.pos, pos, sizeof pos);
            rd3(p + PLAYER_PREV, s_q.prev);
        }
    }
    if (s_q.player >= 0)
        for (j = 0; j < 3; j++)
            s_q.delta[j] = s_q.pos[j] - s_q.prev[j];
    if (s_q.player == 0) {
        for (j = 0; j < 3; j++)
            s_off[j] = s_q.c[j] - s_q.pos[j];
        s_have_off = 1;
    }
    if (s_q.player == 0 && s_tp_pending) {
        /* The teleport's step: the centre goes into the wall, the
         * previous position stays where the game left it. */
        s_tp_pending = 0;
        for (j = 0; j < 3; j++) {
            float v = s_tp_c[j];

            wrf(c->esp + 4 + 4 * (uint32_t)j, v);
            s_q.c[j] = v;
            s_q.pos[j] = v - s_off[j];
            s_q.delta[j] = s_q.pos[j] - s_q.prev[j];
        }
        wr3(VA_PLAYERS + PLAYER_POS, s_q.pos);
    }
    if (s_out)
        fprintf(s_out, "Q\t%u\t%u\t%X\t%d\t%.4f\t%.4f\t%.4f\t%.3f\t%.4f\t%.4f\t%.4f\n", s_frame,
                s_qid, k_sites[site], s_q.player, s_q.c[0], s_q.c[1], s_q.c[2], s_q.r,
                s_q.delta[0], s_q.delta[1], s_q.delta[2]);
}

static void query_post(struct xbox_mod_call *c, void *user)
{
    float n[3], pen;
    int i, over = 0;

    (void)user;
    if (!s_q.active || s_probing)
        return;
    s_q.active = 0;
    if (!s_out)
        return;
    /* The trace only: these slots lie in the query's own frame, below esp
     * once it has returned. No guest code runs between its ret and this
     * hook, so they still hold the values it pushed with. */
    rd3(c->esp - Q_NORMAL, n);
    pen = rdf(c->esp + Q_PEN);
    /* The dynamic objects' contact replaced the walk's (0x163647). */
    if (c->eax && s_q.dyn) {
        over = !s_q.n_acc;
        for (i = 0; i < 3 && !over; i++)
            over = fabsf(n[i] - s_q.sn[i]) > 1e-5f;
    }
    fprintf(s_out, "R\t%u\t%u\t%u\t%d\t%d\t%.5f\t%.5f\t%.5f\t%.4f\t%.4f\t%.4f\t%.4f\n", s_frame,
            s_qid, c->eax, s_q.dyn, over, n[0], n[1], n[2], c->eax ? pen : 0.0f,
            s_q.c[0] + (c->eax ? n[0] * pen : 0), s_q.c[1] + (c->eax ? n[1] * pen : 0),
            s_q.c[2] + (c->eax ? n[2] * pen : 0));
}

static void dynamic_post(struct xbox_mod_call *c, void *user)
{
    (void)user;
    if (s_q.active && !s_probing)
        s_q.dyn = c->eax != 0;
}

/* ---- the triangle test -------------------------------------------------- */

static void face_snapshot(uint32_t tri, uint32_t cp, float r, uint32_t flags, uint32_t pt,
                          uint32_t np, uint32_t penp, uint32_t clsp, uint32_t bestp)
{
    s_fc.tri = tri;
    s_fc.cp = cp;
    s_fc.r = r;
    s_fc.flags = flags;
    s_fc.pt = pt;
    s_fc.np = np;
    s_fc.penp = penp;
    s_fc.clsp = clsp;
    s_fc.bestp = bestp;
    s_fc.best0 = rdf(bestp);
    rd3(pt, s_fc.pt0);
    rd3(np, s_fc.n0);
    s_fc.pen0 = penp ? rdf(penp) : 0;
    s_fc.cls0 = clsp ? rd32(clsp) : 0;
}

static void face_pre(struct xbox_mod_call *c, void *user)
{
    (void)user;
    if (!s_q.active)
        return;
    face_snapshot(XBOX_MOD_ARG32(s_api, c, 0), XBOX_MOD_ARG32(s_api, c, 1),
                  XBOX_MOD_ARGF(s_api, c, 2), XBOX_MOD_ARG32(s_api, c, 3),
                  XBOX_MOD_ARG32(s_api, c, 4), XBOX_MOD_ARG32(s_api, c, 5),
                  XBOX_MOD_ARG32(s_api, c, 6), XBOX_MOD_ARG32(s_api, c, 7),
                  XBOX_MOD_ARG32(s_api, c, 8));
}

/* The test took a contact: trace it, and with the fix, swap a far face the
 * centre came from behind for the face it entered by (wall_decide). */
static void face_took(void)
{
    float best = rdf(s_fc.bestp), c[3], sx = 0, sy = 0;
    struct wall_contact out;
    int x = -1, y = -1, d = WALL_KEEP;
    char act = '-', kind = 'V';

    if (!(best <= s_fc.best0))
        return;
    /* Only a contact behind a face can need the rule; the copy of the
     * triangles waits for one (or for the trace, which logs them all). */
    if (best < 0 || s_out) {
        load_tris();
        x = tri_index(s_fc.tri);
    }
    rd3(s_fc.cp, c);
    if (x >= 0) {
        sx = wall_s(&s_tris[x], c);
        kind = fabsf(best - sx) < 1e-4f ? 'F' : 'V';
        d = wall_decide(s_tris, s_ntris, x, c, s_q.player >= 0 ? s_q.delta : NULL, s_fc.r,
                        s_fc.flags, s_sw, s_fc.best0, best, rdf(VA_PEN_K), &out, &y);
    }
    if (y >= 0) {
        sy = wall_s(&s_tris[y], c);
        s_q.fix_y = y;
    }
    if (d != WALL_KEEP)
        act = d == WALL_RESTORE ? 'r' : out.tri == y ? 'w' : 'e';
    if (d != WALL_KEEP && fixing()) {
        act = (char)(act - 'a' + 'A');
        if (d == WALL_RESTORE) {
            /* Something the walk took before beats the entry face: that
             * contact stands. */
            wrf(s_fc.bestp, s_fc.best0);
            wr3(s_fc.pt, s_fc.pt0);
            wr3(s_fc.np, s_fc.n0);
            if (s_fc.penp)
                wrf(s_fc.penp, s_fc.pen0);
            if (s_fc.clsp)
                XBOX_MOD_MEM32(s_api, s_fc.clsp) = s_fc.cls0;
            __atomic_fetch_add(&s_kept, 1, __ATOMIC_RELAXED);
        } else {
            wr3(s_fc.pt, out.p);
            wr3(s_fc.np, out.n);
            if (s_fc.penp)
                wrf(s_fc.penp, out.pen);
            if (s_fc.clsp)
                XBOX_MOD_MEM32(s_api, s_fc.clsp) = out.cls;
            wrf(s_fc.bestp, out.best);
            __atomic_fetch_add(&s_fixed, 1, __ATOMIC_RELAXED);
        }
    }
    if (act != 'R') {
        rd3(s_fc.np, s_q.sn);
        s_q.n_acc++;
        s_q.last_tri = act == 'W' || act == 'E' ? out.tri : x;
    }
    if (s_out && !s_probing) {
        float prev[3];
        int i;

        for (i = 0; i < 3; i++)
            prev[i] = c[i] - s_q.delta[i];
        fprintf(s_out, "H\t%u\t%u\t%d\t%c\t%X\t%06X\t%.5f\t%.5f\t%.5f\t%.5f\t%d\t%.5f\t%c\n",
                s_frame, s_qid, x, kind, s_fc.flags,
                x >= 0 ? s_tris[x].cls & 0xFFFFFFu : 0, sx,
                x >= 0 ? wall_s(&s_tris[x], prev) : 0.0f, s_fc.best0, best, y, sy, act);
    }
}

static void face_post(struct xbox_mod_call *c, void *user)
{
    (void)user;
    if (!s_q.active)
        return;
    s_hooked++;
    if (!s_probing)
        s_flags_seen = s_fc.flags;
    if (c->eax)
        face_took();
}

/* ---- the probes (task 1.7) ---------------------------------------------- */

static void find_pairs(float wmax)
{
    int f;

    load_tris();
    s_npairs = 0;
    for (f = 0; f < s_ntris && s_npairs < MAX_PAIRS; f++) {
        float w;
        int b = wall_pair(s_tris, s_ntris, f, wmax, s_sw, &w);

        if (b >= 0) {
            s_pairs[s_npairs].f = f;
            s_pairs[s_npairs].b = b;
            s_pairs[s_npairs].w = w;
            s_npairs++;
        }
    }
}

/* One walk the way sub_00165380 does it, through the game's own triangle
 * test, over the triangles whose bounds reach the sphere, in buffer order
 * (the octree's order only breaks ties). Returns the hit and the push. */
static int probe_walk(const float c[3], const float prev[3], float r, int fix, float out[3])
{
    uint32_t b = s_block, args[9];
    struct xbox_guest_args a;
    float n[3], pen;
    int i, j, hit = 0;

    memset(&a, 0, sizeof a);
    wr3(b, c);
    wrf(b + 0x30, BEST_INIT);
    wrf(b + 0x34, 0);
    XBOX_MOD_MEM32(s_api, VA_STAMP) = rd32(VA_STAMP) + 1;
    memset(&s_q, 0, sizeof s_q);
    s_q.active = 1;
    s_q.player = 0;
    s_q.last_tri = -1;
    s_q.fix_y = -1;
    for (j = 0; j < 3; j++)
        s_q.delta[j] = c[j] - prev[j];
    o_fix = fix;
    args[1] = b;
    memcpy(&args[2], &r, 4);
    args[3] = s_flags_seen;
    args[4] = b + 0x0C;
    args[5] = b + 0x18;
    args[6] = b + 0x34;
    args[7] = b + 0x38;
    args[8] = b + 0x30;
    a.stack = args;
    a.n_stack = 9;
    for (i = 0; i < s_ntris; i++) {
        const struct wall_tri *t = &s_tris[i];
        float d = 0, k = r + t->radius;
        uint32_t eax = 0;
        int before;

        for (j = 0; j < 3; j++)
            d += (c[j] - t->centroid[j]) * (c[j] - t->centroid[j]);
        if (d >= k * k)
            continue;
        args[0] = WALL_TRI_BUF + (uint32_t)i * WALL_TRI_SIZE;
        before = s_hooked;
        face_snapshot(args[0], b, r, args[3], args[4], args[5], args[6], args[7], args[8]);
        if (!s_api->guest_call(VA_FACE, &a, &eax))
            break;
        /* The lifted call may not pass through the hook slot. */
        if (s_hooked == before && eax)
            face_took();
        hit |= eax != 0;
    }
    s_q.active = 0;
    rd3(b + 0x18, n);
    pen = rdf(b + 0x34);
    for (j = 0; j < 3; j++)
        out[j] = c[j] + (hit ? n[j] * pen : 0);
    return hit;
}

static float frand(unsigned *seed)
{
    *seed = *seed * 1103515245u + 12345u;
    return (float)((*seed >> 8) & 0xFFFF) / 65535.0f;
}

static void probe_run(void)
{
    float r = (float)o_rad / 100.0f, wmax = o_wmax ? (float)o_wmax / 100.0f : 2 * r;
    int k, i, j, saved_fix = o_fix;
    long tun[2] = { 0, 0 }, samples = 0, changed = 0, changed_tun = 0, hits = 0;
    unsigned seed = 1;

    if (!s_block)
        s_block = s_api->guest_alloc(&s_mod, BLOCK_SIZE, 0x1000);
    if (!s_block)
        return;
    find_pairs(wmax);
    s_probing = 1;
    /* Thin pairs: the centre at eight depths in F, from F's front. */
    for (k = 0; k < s_npairs; k++) {
        const struct wall_tri *tf = &s_tris[s_pairs[k].f], *tb = &s_tris[s_pairs[k].b];
        float w = s_pairs[k].w;

        for (i = 0; i < 8; i++) {
            float d = w * ((float)i + 0.5f) / 8.0f, c[3], prev[3], out[2][3], sf[2];
            int f;

            for (j = 0; j < 3; j++) {
                c[j] = tf->centroid[j] - tf->n[j] * d;
                prev[j] = c[j] + tf->n[j] * (d + 0.3f);
            }
            for (f = 0; f < 2; f++) {
                probe_walk(c, prev, r, f, out[f]);
                sf[f] = wall_s(tf, out[f]);
                tun[f] += sf[f] < -WALL_EPS;
            }
            samples++;
            fprintf(s_out, "PT\t%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n", k,
                    s_pairs[k].f, s_pairs[k].b, w, d, sf[0], sf[1], wall_s(tb, out[0]),
                    wall_s(tb, out[1]));
        }
    }
    s_api->log(&s_mod, "probe: %d thin pairs (w < %.2f, r %.2f), %ld samples, through the far"
               " side: stock %ld, fixed %ld", s_npairs, wmax, r, samples, tun[0], tun[1]);
    fprintf(s_out, "#probe pairs %d wmax %.3f r %.3f samples %ld tunnel_stock %ld tunnel_fix %ld\n",
            s_npairs, wmax, r, samples, tun[0], tun[1]);
    /* Elsewhere: spheres near random triangles, moving any way; the fix
     * must change only the walks where the centre came through a face. */
    for (k = 0; k < o_samples && s_ntris; k++) {
        const struct wall_tri *t = &s_tris[(int)(frand(&seed) * (float)(s_ntris - 1))];
        float c[3], prev[3], out[2][3], u = (frand(&seed) * 2 - 1) * r;
        int h0, h1, diff = 0;

        if (wall_skipped(t->cls, s_sw))
            continue;
        for (j = 0; j < 3; j++) {
            c[j] = t->centroid[j] + t->n[j] * u + (frand(&seed) - 0.5f) * r;
            prev[j] = c[j] + (frand(&seed) - 0.5f) * 1.0f;
        }
        h0 = probe_walk(c, prev, r, 0, out[0]);
        h1 = probe_walk(c, prev, r, 1, out[1]);
        hits += h0;
        for (j = 0; j < 3; j++)
            diff |= fabsf(out[0][j] - out[1][j]) > 1e-4f;
        diff |= h0 != h1;
        if (diff) {
            int y = s_q.fix_y;

            changed++;
            /* Changed for the reason the fix exists: stock pushed the
             * centre behind the face the fix took. */
            if (y >= 0 && wall_s(&s_tris[y], out[0]) < -WALL_EPS &&
                wall_s(&s_tris[y], prev) >= -WALL_EPS)
                changed_tun++;
            fprintf(s_out, "PR\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n",
                    k, c[0], c[1], c[2], prev[0], prev[1], prev[2], y, out[0][0], out[0][1],
                    out[0][2], out[1][0], out[1][1], out[1][2]);
        }
    }
    s_probing = 0;
    o_fix = saved_fix;
    s_api->log(&s_mod, "probe: %ld random spheres (%ld hit), %ld changed, %ld of them stock"
               " through the entry face", o_samples, hits, changed, changed_tun);
    fprintf(s_out, "#random samples %ld hit %ld changed %ld changed_tunnel %ld\n", o_samples, hits,
            changed, changed_tun);
    fflush(s_out);
}

/* Put player 0 just in front of the k-th thin pair's near face, then make
 * its next query a step d percent of the way into the wall (query_pre).
 * The game copies the position to +0xF8 before it moves the player, so a
 * teleport straight into the wall would leave the previous centre in the
 * wall too; the two steps give the single long step of a wall jump. */
static void teleport(void)
{
    float r = (float)o_rad / 100.0f, wmax = o_wmax ? (float)o_wmax / 100.0f : 2 * r;
    uint32_t p = VA_PLAYERS;
    const struct wall_tri *tf;
    float c[3], pos[3], prev[3], d;
    int j;

    find_pairs(wmax);
    if (o_tp >= s_npairs || !s_have_off) {
        s_api->log(&s_mod, "tp: no pair %ld of %d, or no player query yet", o_tp, s_npairs);
        return;
    }
    s_tp_f = s_pairs[o_tp].f;
    s_tp_b = s_pairs[o_tp].b;
    tf = &s_tris[s_tp_f];
    d = s_pairs[o_tp].w * (float)o_depth / 100.0f;
    for (j = 0; j < 3; j++) {
        c[j] = tf->centroid[j] - tf->n[j] * d;
        s_tp_c[j] = c[j];
        pos[j] = tf->centroid[j] + tf->n[j] * 0.5f - s_off[j];
        prev[j] = pos[j];
    }
    wr3(p + PLAYER_POS, pos);
    wr3(p + PLAYER_PREV, prev);
    s_tp_pending = 1;
    s_tp_until = s_frame + (unsigned)o_tp_for;
    fprintf(s_out, "#tp frame %u pair %ld f %d b %d w %.4f d %.4f pos %.4f %.4f %.4f\n", s_frame,
            o_tp, s_tp_f, s_tp_b, s_pairs[o_tp].w, d, pos[0], pos[1], pos[2]);
    s_api->log(&s_mod, "tp: pair %ld (f %d, b %d, w %.3f) at depth %.3f", o_tp, s_tp_f, s_tp_b,
               s_pairs[o_tp].w, d);
}

/* ---- the mod ------------------------------------------------------------ */

static void trace_frame(void)
{
    uint32_t sw[4];
    int i;

    sw[0] = rd32(VA_SWITCH_A);
    sw[1] = rd32(VA_SWITCH_B);
    sw[2] = rd32(VA_SWITCH_C);
    sw[3] = rd32(VA_SWITCH_D);
    if (!s_sw_seen || memcmp(sw, s_sw_last, sizeof sw)) {
        fprintf(s_out, "S\t%u\t%u\t%u\t%u\t%u\n", s_frame, sw[0], sw[1], sw[2], sw[3]);
        memcpy(s_sw_last, sw, sizeof sw);
        s_sw_seen = 1;
    }
    for (i = 0; i < 2; i++) {
        uint32_t p = VA_PLAYERS + (uint32_t)i * PLAYER_SIZE;
        float pos[3], prev[3];

        rd3(p + PLAYER_POS, pos);
        rd3(p + PLAYER_PREV, prev);
        fprintf(s_out, "P\t%u\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\t%.4f\n", s_frame, i, pos[0], pos[1],
                pos[2], prev[0], prev[1], prev[2]);
    }
    if (s_tp_f >= 0 && s_frame <= s_tp_until && s_have_off) {
        float c[3], pos[3];
        int j;

        load_tris();
        rd3(VA_PLAYERS + PLAYER_POS, pos);
        for (j = 0; j < 3; j++)
            c[j] = pos[j] + s_off[j];
        fprintf(s_out, "T\t%u\t%.4f\t%.4f\n", s_frame, wall_s(&s_tris[s_tp_f], c),
                wall_s(&s_tris[s_tp_b], c));
    }
    if ((long)s_frame == o_probe)
        probe_run();
    if ((long)s_frame == o_tp_at)
        teleport();
    if (!(s_frame % 60))
        fflush(s_out);
}

static void on_frame(void *user)
{
    (void)user;
    s_frame++;
    /* A query cut off by the mod going off (its post hook then does not
     * run) must not leave the triangle hooks acting on every caller. */
    s_q.active = 0;
    if (s_out && s_on && s_api->mem)
        trace_frame();
}

static void on_enable(int on, void *user)
{
    (void)user;
    /* A switch lands at a frame boundary, between queries; an off and on
     * again before the next frame still drops a query left open. */
    s_q.active = 0;
    if (on == s_on)
        return;
    s_on = on;
    s_api->log(&s_mod, "%s", on ? "on" : "off");
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0)
        snprintf(buf, n, "turn the mod on first");
    else
        snprintf(buf, n, "%d contacts moved to the entry face, %d kept",
                 __atomic_load_n(&s_fixed, __ATOMIC_RELAXED),
                 __atomic_load_n(&s_kept, __ATOMIC_RELAXED));
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.walls.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static long opt(const char *v, const char *name, long def)
{
    size_t l = strlen(name);
    const char *p;

    for (p = v; p && *p;) {
        if (!strncmp(p, name, l) && p[l] == ':')
            return strtol(p + l + 1, NULL, 0);
        p = strchr(p, '+');
        if (p)
            p++;
    }
    return def;
}

static void str_opt(const char *v, const char *name, char *out, size_t cap)
{
    const char *o = strstr(v, name);
    size_t l;

    if (!o)
        return;
    o += strlen(name);
    l = strcspn(o, "+");
    if (l >= cap)
        l = cap - 1;
    memcpy(out, o, l);
    out[l] = 0;
}

/* RECOMP_DEBUG splits on commas, so the options are joined by '+'. */
static void trace_init(const char *v)
{
    char path[512] = "walls_trace.tsv";

    str_opt(v, "out:", path, sizeof path);
    o_fix = (int)opt(v, "fix", -1);
    o_probe = opt(v, "probe", -1);
    o_samples = opt(v, "samples", o_samples);
    o_rad = opt(v, "rad", o_rad);
    o_wmax = opt(v, "wmax", o_wmax);
    o_tp = opt(v, "tp", -1);
    o_tp_at = opt(v, "at", -1);
    o_depth = opt(v, "depth", o_depth);
    o_tp_for = opt(v, "for", o_tp_for);
    s_out = fopen(path, "w");
    if (!s_out) {
        s_api->log(&s_mod, "trace: cannot write %s", path);
        return;
    }
    fprintf(s_out, "#walls_trace %s\n", v);
    fprintf(s_out, "#Q frame id site player cx cy cz r dx dy dz\n"
                   "#H frame id tri kind flags class s s_prev best_before best_after entry s_entry act\n"
                   "#R frame id hit dyn override nx ny nz push ox oy oz\n"
                   "#P frame player x y z px py pz\n#S frame A B C D\n#T frame s_near s_far\n");
    s_api->log(&s_mod, "trace: %s, fix %d, probe %ld, tp %ld at %ld depth %ld%%", path, o_fix,
               o_probe, o_tp, o_tp_at, o_depth);
}

static int init(const struct xbox_mod_api *api)
{
    const char *trace = recomp_env(RENV_WALLS_TRACE);

    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc)
        return 1;   /* no v6 guest calls: stock */
    s_api = api;
    if (!api->hook(VA_FACE, face_pre, face_post, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock walls", VA_FACE);
        return 1;
    }
    if (!api->hook(VA_QUERY, query_pre, query_post, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock walls", VA_QUERY);
        return 1;
    }
    if (!api->hook(VA_DYNAMIC, NULL, dynamic_post, 0, NULL))
        api->log(&s_mod, "no hook slot for 0x%08X: the trace cannot see overrides", VA_DYNAMIC);
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_status_row);
    if (trace)
        trace_init(trace);
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "walls", init, NULL, &k_desc,
                                       XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK };

const void *walls_mod(void)
{
    return &s_mod;
}

#else /* no mod API v6: stock */

const void *walls_mod(void)
{
    return NULL;
}

#endif
