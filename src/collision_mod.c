/*
 * collision_mod.c - the collision overlay mod (collision_mod.h; openspec
 * change collision-overlay, D7 to D10).
 *
 * The stage's baked collision triangles (collision_logic.h) within a
 * radius of player 0, drawn in the game's own 3D view with the Godot
 * collision view's look: the class colour or a flatness band, shaded, the
 * crease and open edges of each class, translucent or opaque, depth-tested
 * or x-ray. With "Contact" on, player 0's collision sphere and the face
 * its last query pushed it off.
 *
 * The drawing goes through the mod API v8 3D debug draw: the toolkit draws
 * the frame at the flip with the view and projection passed here. They are
 * the game's own: sub_000292A0 (for the game camera) and, on the stages
 * that run it, sub_0021B1F0 after it build the view the stage's models are
 * drawn with into 0xA72380 and the projection into 0xAC1870
 * (recomp_manual.c, the free camera's notes); their wrappers call
 * collision_mod_view right after, and the frame's last build wins (M23
 * builds the game camera five times a frame, sub_0021B1F0 never). The
 * player's sphere queries run after the view is built, so the contact
 * drawn is the previous frame's.
 *
 * The triangles are reloaded when the stage's bake changes
 * (col_stage_key, checked once a frame); the edges and bands are computed
 * then, not per frame. The octree walk picks the frame's triangles.
 *
 * Off (the default, every golden): on_frame and the view call return
 * before reading the guest, the hooks are not called, nothing is drawn.
 */
#include <stddef.h>
#include "collision_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 8
#      define COLLISION_MOD 1
#    endif
#  endif
#endif

#ifdef COLLISION_MOD

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "collision_logic.h"
#include "enhance_menu.h"
#include "recomp_env.h"

enum {
    SET_ENABLE, SET_FACES, SET_OPAQUE, SET_EDGES, SET_FLAT, SET_XRAY, SET_RADIUS, SET_CONTACT,
    SET_C_SOLID, SET_C_ENEMY, SET_C_CAMFLOOR, SET_C_CAMPASS, SET_C_BLUE, SET_C_UNTESTED,
    SET_C_OTHER, SET_N
};
#define N_CLASSES (SET_N - SET_C_SOLID)

static const char *const k_offon[] = { "off", "on", NULL };

#define BOOL_SET(nm, lbl, hlp, d)                                                              \
    { nm, NULL, NULL, NULL, lbl, hlp, NULL, XBOX_SET_BOOL, ENHANCE_LIVE, 0, d, 0, 1, 0, NULL }

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_COLLISION", NULL, "Collision overlay",
      "Draws the stage's collision triangles around Blinx in the game's"
      " view, as the collision extract shows them in Godot. A debug view:"
      " it changes nothing the game does. Off is the stock game.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
    [SET_FACES] = BOOL_SET("faces", "Faces", "The collision triangles, filled.", 1),
    [SET_OPAQUE] = BOOL_SET("opaque", "Opaque faces",
                            "Faces hide what is behind them, the game's scenery included;"
                            " off, they are see-through.", 0),
    [SET_EDGES] = BOOL_SET("edges", "Crease edges",
                           "Lines where faces of one class meet at more than 20 degrees,"
                           " and the open edges.", 1),
    [SET_FLAT] = BOOL_SET("flatness", "Flatness colours",
                          "Faces by how far they are off flat or vertical: grey under 0.1"
                          " degrees, yellow under 2, orange under 10, red past, dark grey"
                          " for slivers.", 0),
    [SET_XRAY] = BOOL_SET("xray", "X-ray",
                          "Draws through walls and floors: nothing hides the overlay.", 0),
    [SET_RADIUS] = { "radius", NULL, NULL, NULL, "Radius",
      "Only the triangles this close to Blinx are drawn.", "units", XBOX_SET_FLOAT,
      ENHANCE_LIVE, 0, 150, 20, 2000, 10, NULL },
    [SET_CONTACT] = BOOL_SET("contact", "Contact",
                             "Blinx's collision sphere, the face the game pushed it off"
                             " this frame and the push.", 0),
    [SET_C_SOLID] = BOOL_SET("class_solid", "Class: solid (0xBFBFBF)",
                             "Walls and floors, always tested.", 1),
    [SET_C_ENEMY] = BOOL_SET("class_enemy_wall", "Class: enemy wall (0x00FFFF)",
                             "Tested only around the enemy and object updates.", 1),
    [SET_C_CAMFLOOR] = BOOL_SET("class_camera_floor", "Class: camera floor (0x7F7F00)",
                                "Only the camera's height probe.", 1),
    [SET_C_CAMPASS] = BOOL_SET("class_camera_pass", "Class: camera pass (0xFF00FF)",
                               "Skipped while the stage's camera runs.", 1),
    [SET_C_BLUE] = BOOL_SET("class_unused_blue", "Class: unused blue (0x0000FF)",
                            "Its switch is never cleared; no stage holds it.", 1),
    [SET_C_UNTESTED] = BOOL_SET("class_untested", "Class: untested (0xFFFFFF)",
                                "Baked but never tested.", 0),
    [SET_C_OTHER] = BOOL_SET("class_other", "Other classes",
                             "The always-tested surface types (0x7F0000, 0xB2B2B2, ...).", 1),
};

static const uint32_t k_class_value[N_CLASSES - 1] = { 0xBFBFBFu, 0x00FFFFu, 0x7F7F00u,
                                                       0xFF00FFu, 0x0000FFu, 0xFFFFFFu };

enum { CTL_TOGGLE, CTL_N };
static const char *const k_toggle_def[] = { "F4", NULL };

static const struct xbox_mod_control k_ctl[CTL_N] = {
    /* id, label, help, when, kind, defaults, aliases, env */
    [CTL_TOGGLE] = { "toggle", "Show or hide the overlay",
      "Hides the drawing and shows it again, the mod staying on.", "while the mod is on",
      XBOX_CTL_ACTION, k_toggle_def, NULL, "RECOMP_COLLISION_KEY" },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Collision",
    "The stage's collision in the game's view", NULL, "1",
    k_set, SET_N, k_ctl, CTL_N
};

#define VA_VIEW         0x00A72380u     /* D3D view, row-major */
#define VA_PROJ         0x00AC1870u     /* D3D projection */

/* Player 0's record. */
#define VA_PLAYERS      0x00CD2440u
#define PLAYER_POS      0xECu

/* The sphere query and the triangle test (walls_mod.c has their frames). */
#define VA_QUERY        0x001636C0u
#define Q_NORMAL        0x28u           /* below the entry esp, after the return */
#define Q_PEN           0x10u
#define VA_FACE         0x00165630u
static const uint32_t k_sites[] = { 0x00178F92u, 0x00184F26u, 0x00185063u, 0x00185239u,
                                    0x00185503u, 0x00185959u, 0x00185B65u };
#define N_SITES ((int)(sizeof k_sites / sizeof k_sites[0]))
/* A player query's centre is a few units off the player's position. */
#define PLAYER_NEAR     12.0f

#define ALPHA_SEE       ((uint32_t)(COL_ALPHA * 255.0f + 0.5f))
#define CIRCLE_SEGS     32

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

static int s_on;                        /* guest thread */
static int s_shown = 1;                 /* the toggle */
static int s_act_toggle = -1;
static unsigned s_frame;
static unsigned s_sel_frame = ~0u;
static int s_drew;                      /* the last frame handed over held something */
static int s_viewed;                    /* a view call since the last on_frame */
static int s_view_calls, s_view_max;
static float s_v[16], s_p[16];

static struct col_stage s_stage;
static uint32_t s_mark[COL_TRI_MAX];
static uint32_t s_stamp;
static int s_sel[COL_TRI_MAX];
static int s_nsel;
static struct xbox_dbg_vtx s_fv[COL_TRI_MAX * 3];
static struct xbox_dbg_vtx s_ev[COL_TRI_MAX * 6];
static uint32_t s_nf, s_ne;
static int s_last_tris, s_last_edges;  /* for the menu's status row */

/* Player 0's query in flight, its last query and its last hit. The
 * player's queries run after the frame's view is built, so the view of
 * frame f shows those of frame f - 1: a contact older than that is gone. */
static struct {
    int active, last_tri;
    uint32_t tri_arg;
    float c[3], r;
} s_q;
static struct {
    int valid;
    unsigned frame;
    float c[3], r;
} s_contact;
static struct {
    int valid, tri;
    unsigned frame;
    float c[3], n[3], pen;
} s_hit;

static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(s_api, va); }
static inline float rdf(uint32_t va) { return XBOX_MOD_MEMF(s_api, va); }

static int set_on(uint32_t idx) { return s_api->setting(&k_desc, idx) != 0; }

static int class_shown(uint32_t cls)
{
    int i;

    for (i = 0; i < N_CLASSES - 1; i++)
        if (k_class_value[i] == cls)
            return set_on(SET_C_SOLID + (uint32_t)i);
    return set_on(SET_C_OTHER);
}

static void vtx(struct xbox_dbg_vtx *o, const float p[3], uint32_t argb)
{
    memcpy(o->p, p, sizeof o->p);
    o->argb = argb;
}

/* ---- the frame's triangles ------------------------------------------------ */

static void select_tris(void)
{
    float c[3], r = (float)s_api->setting(&k_desc, SET_RADIUS);
    int k;

    s_nsel = 0;
    for (k = 0; k < 3; k++)
        c[k] = rdf(VA_PLAYERS + PLAYER_POS + 4 * (uint32_t)k);
    if (!isfinite(c[0]) || !isfinite(c[1]) || !isfinite(c[2]) || !(r > 0))
        return;
    if (++s_stamp == 0) {
        memset(s_mark, 0, sizeof s_mark);
        s_stamp = 1;
    }
    s_nsel = col_query(&s_stage, (const uint8_t *)s_api->mem, c, r, s_mark, s_stamp, s_sel, COL_TRI_MAX);
}

static void build(void)
{
    int faces = set_on(SET_FACES), opaque = set_on(SET_OPAQUE), edges = set_on(SET_EDGES);
    int flat = set_on(SET_FLAT);
    uint32_t alpha = opaque ? 0xFFu : ALPHA_SEE;
    int i, j, k;

    s_nf = s_ne = 0;
    for (i = 0; i < s_nsel; i++) {
        const struct col_tri *t = &s_stage.t[s_sel[i]];

        if (!class_shown(t->cls))
            continue;
        if (faces) {
            uint32_t rgb = col_scale_rgb(flat ? col_band_rgb[t->band] : t->cls, t->shade);

            for (j = 0; j < 3; j++)
                vtx(&s_fv[s_nf++], t->v[j], alpha << 24 | rgb);
        }
        if (edges && t->edges) {
            uint32_t argb = 0xFF000000u | col_scale_rgb(t->cls, COL_EDGE_DARKEN);

            for (k = 0; k < 3; k++)
                if (t->edges & (1u << k)) {
                    vtx(&s_ev[s_ne++], t->v[k], argb);
                    vtx(&s_ev[s_ne++], t->v[(k + 1) % 3], argb);
                }
        }
    }
}

/* Player 0's sphere as three great circles, the pushed face and the push. */
static void draw_contact(void)
{
    struct xbox_dbg_vtx v[CIRCLE_SEGS * 2 * 3 + 2];
    uint32_t n = 0;
    int a, i, hit;

    if (!s_contact.valid || s_frame - s_contact.frame > 1)
        return;
    for (a = 0; a < 3; a++)
        for (i = 0; i < CIRCLE_SEGS; i++) {
            float p[2][3];
            int e;

            for (e = 0; e < 2; e++) {
                float t = (float)(i + e) * (6.2831853f / CIRCLE_SEGS);
                float u = cosf(t) * s_contact.r, w = sinf(t) * s_contact.r;

                memcpy(p[e], s_contact.c, sizeof p[e]);
                p[e][(a + 1) % 3] += u;
                p[e][(a + 2) % 3] += w;
            }
            vtx(&v[n++], p[0], 0xC0FFFFFFu);
            vtx(&v[n++], p[1], 0xC0FFFFFFu);
        }
    hit = s_hit.valid && s_frame - s_hit.frame <= 1;
    if (hit) {
        float q[3];

        for (i = 0; i < 3; i++)
            q[i] = s_hit.c[i] + s_hit.n[i] * s_hit.pen;
        vtx(&v[n++], s_hit.c, 0xFFFFFF00u);
        vtx(&v[n++], q, 0xFFFFFF00u);
    }
    s_api->draw3d_lines(v, n / 2, XBOX_DBG_XRAY);
    if (hit && s_hit.tri >= 0 && s_hit.tri < s_stage.n) {
        const struct col_tri *t = &s_stage.t[s_hit.tri];
        struct xbox_dbg_vtx f[3];

        for (i = 0; i < 3; i++)
            vtx(&f[i], t->v[i], 0xC0FF40FFu);
        /* With x-ray on, the hit face shows through what hides it, as the
         * stage faces do. */
        s_api->draw3d_tris(f, 1, XBOX_DBG_PULL | (set_on(SET_XRAY) ? XBOX_DBG_XRAY : 0u));
    }
}

void collision_mod_view(void)
{
    int i, xray;

    if (!s_on || !s_api || !s_api->mem)
        return;
    s_viewed = 1;
    if (++s_view_calls > s_view_max) {
        s_view_max = s_view_calls;
        if (s_view_max > 1)
            s_api->log(&s_mod, "the view is built %d times in a frame: the last one draws",
                       s_view_max);
    }
    for (i = 0; i < 16; i++) {
        s_v[i] = rdf(VA_VIEW + 4 * (uint32_t)i);
        s_p[i] = rdf(VA_PROJ + 4 * (uint32_t)i);
    }
    if (!s_shown) {
        /* Hidden: one empty frame clears what is on the screen. */
        if (s_drew && s_api->draw3d_begin(&s_mod, s_v, s_p) == 0) {
            s_api->draw3d_end(&s_mod);
            s_drew = 0;
        }
        return;
    }
    if (s_sel_frame != s_frame) {
        s_sel_frame = s_frame;
        select_tris();
        build();
        s_last_tris = (int)(s_nf / 3);
        s_last_edges = (int)(s_ne / 2);
    }
    if (s_api->draw3d_begin(&s_mod, s_v, s_p) != 0)
        return;
    xray = set_on(SET_XRAY) ? (int)XBOX_DBG_XRAY : 0;
    if (s_nf)
        s_api->draw3d_tris(s_fv, s_nf / 3,
                           (uint32_t)xray | (set_on(SET_OPAQUE) ? XBOX_DBG_OPAQUE : 0u));
    if (s_ne)
        s_api->draw3d_lines(s_ev, s_ne / 2, (uint32_t)xray | XBOX_DBG_PULL);
    if (set_on(SET_CONTACT))
        draw_contact();
    s_api->draw3d_end(&s_mod);
    s_drew = 1;
}

/* ---- the contact (D9) ----------------------------------------------------- */

static int is_site(uint32_t ret)
{
    int i;

    for (i = 0; i < N_SITES; i++)
        if (k_sites[i] == ret)
            return 1;
    return 0;
}

static void query_pre(struct xbox_mod_call *c, void *user)
{
    float d = 0;
    int k;

    (void)user;
    s_q.active = 0;
    if (!set_on(SET_CONTACT) || !is_site(rd32(c->esp)))
        return;
    for (k = 0; k < 3; k++) {
        float e = XBOX_MOD_ARGF(s_api, c, k) - rdf(VA_PLAYERS + PLAYER_POS + 4 * (uint32_t)k);

        s_q.c[k] = XBOX_MOD_ARGF(s_api, c, k);
        d += e * e;
    }
    if (!(d < PLAYER_NEAR * PLAYER_NEAR))
        return;                         /* another player's */
    s_q.r = XBOX_MOD_ARGF(s_api, c, 3);
    s_q.last_tri = -1;
    s_q.active = 1;
}

static void query_post(struct xbox_mod_call *c, void *user)
{
    int k;

    (void)user;
    if (!s_q.active)
        return;
    s_q.active = 0;
    memcpy(s_contact.c, s_q.c, sizeof s_contact.c);
    s_contact.r = s_q.r;
    s_contact.frame = s_frame;
    s_contact.valid = 1;
    if (c->eax) {
        /* Below esp once the query has returned; no guest code ran since
         * (walls_mod.c, query_post). */
        float pen = rdf(c->esp + Q_PEN);

        if (!isfinite(pen) || fabsf(pen) > 1000.0f)
            return;
        for (k = 0; k < 3; k++)
            s_hit.n[k] = rdf(c->esp - Q_NORMAL + 4 * (uint32_t)k);
        memcpy(s_hit.c, s_q.c, sizeof s_hit.c);
        s_hit.pen = pen;
        s_hit.tri = s_q.last_tri;
        s_hit.frame = s_frame;
        s_hit.valid = 1;
    }
}

static void face_pre(struct xbox_mod_call *c, void *user)
{
    (void)user;
    if (s_q.active)
        s_q.tri_arg = XBOX_MOD_ARG32(s_api, c, 0);
}

static void face_post(struct xbox_mod_call *c, void *user)
{
    uint32_t d;

    (void)user;
    if (!s_q.active || !c->eax || s_q.tri_arg < COL_TRI_BUF)
        return;
    d = s_q.tri_arg - COL_TRI_BUF;
    if (d % COL_TRI_SIZE == 0 && d / COL_TRI_SIZE < (uint32_t)s_stage.n)
        s_q.last_tri = (int)(d / COL_TRI_SIZE);
}

/* ---- the frame -------------------------------------------------------------- */

static void on_frame(void *user)
{
    uint32_t key;

    (void)user;
    s_frame++;
    s_view_calls = 0;
    s_q.active = 0;
    if (!s_on || !s_api->mem)
        return;
    if (s_act_toggle >= 0 && s_api->action_pressed(s_act_toggle)) {
        s_shown = !s_shown;
        s_api->toast(&s_mod, s_shown ? "Collision overlay shown" : "Collision overlay hidden");
    }
    /* A frame with no view built (a load, a movie, a menu of its own):
     * the last drawing must not stay over it. */
    if (!s_viewed && s_drew && s_api->draw3d_begin(&s_mod, s_v, s_p) == 0) {
        s_api->draw3d_end(&s_mod);
        s_drew = 0;
    }
    s_viewed = 0;
    key = col_stage_key((const uint8_t *)s_api->mem);
    if (key != s_stage.key) {
        col_stage_load(&s_stage, (const uint8_t *)s_api->mem);
        memset(s_mark, 0, sizeof s_mark);
        s_stamp = 0;
        s_contact.valid = s_hit.valid = 0;
        s_api->log(&s_mod, "stage bake: %d triangles, %d crease and %d open edges",
                   s_stage.n, s_stage.creases, s_stage.opens);
    }
}

static void on_enable(int on, void *user)
{
    (void)user;
    s_q.active = 0;
    if (on == s_on)
        return;
    s_on = on;
    s_drew = 0;
    s_stage.key = 0;                    /* reload: the stage may have changed while off */
    s_stage.n = 0;
    s_api->log(&s_mod, "%s", on ? "on" : "off");
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    (void)it;
    if (!s_on)
        snprintf(buf, n, "turn the mod on first");
    else
        snprintf(buf, n, "%d of %d triangles drawn, %d edges%s", s_last_tris, s_stage.n,
                 s_last_edges, s_shown ? "" : " (hidden)");
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.collision.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static int init(const struct xbox_mod_api *api)
{
    if (api->size < offsetof(struct xbox_mod_api, draw3d_end) + sizeof api->draw3d_end)
        return 1;   /* no v8 3D draw: nothing to show */
    s_api = api;
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    s_act_toggle = api->control_action(&k_desc, CTL_TOGGLE);
    /* The toggle fires through the actions hook, which the menu arms when
     * it is on; with RECOMP_MENU=0 the mod's switch arms it. */
    api->actions_arm("mods.collision.enable");
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_status_row);
    /* The contact only: both slots are in game.toml for the walls mod. */
    if (!api->hook(VA_QUERY, query_pre, query_post, 0, NULL) ||
        !api->hook(VA_FACE, face_pre, face_post, 0, NULL))
        api->log(&s_mod, "no hook slot for the sphere query: no contact view");
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "collision", init, NULL, &k_desc, XBOX_MOD_NEED_HOOK };

const void *collision_mod(void)
{
    return &s_mod;
}

#else /* no mod API v8: nothing to draw with */

const void *collision_mod(void)
{
    return NULL;
}

void collision_mod_view(void)
{
}

#endif
