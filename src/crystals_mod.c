/*
 * crystals_mod.c - the crystals mod, shown to players as "BLiNX 1 crystals"
 * (crystals_mod.h; openspec change crystals-rewrite). Its id, keys and env
 * rows keep the crystals name so players' configs and the goldens'
 * enhance_stock still match.
 *
 * BLiNX 1's crystal row in BLiNX 2: four crystals in pickup order, three
 * of one colour give that time control, four give it twice, and the row
 * empties at four. The controls go into BLiNX 2's own stock, picked with
 * the d-pad, under its caps; a set made while the control is full pays
 * gold, as stock does.
 *
 * - The pickup (D1): a pre and a post on tc_crystal_collect, never a skip.
 *   The pre sets the record's counts so the game's own code grants exactly
 *   when the row says so; the post puts the record back and pushes the
 *   crystal into the row of whichever character the game counted it for
 *   (crystals_logic.c). Item freeing, sounds, redirects, bounces and the
 *   taken flag stay the game's.
 * - The row (D2) lives in the record's count bytes, so checkpoints,
 *   retries and the stage start's rebuild carry or clear it with no code
 *   here.
 * - The HUD (D3) hides the stock count pips and draws the row above the
 *   time-control slots through the game's sprite add; a heart crystal
 *   uses the heart drawn above the heart gauge.
 * - Only Sweepers stages (stage_team_mode 0); Tom Tom and VS stay stock
 *   (D4).
 *
 * Off (the default, every golden): the hooks do not run, on_frame returns
 * before reading the guest unless the proof runs, and no guest memory is
 * allocated.
 */
#include <stddef.h>
#include "crystals_mod.h"
#include "crystals_internal.h"

#ifdef CRYSTALS_MOD

#include <stdlib.h>
#include <string.h>
#include "crystals_logic.h"
#include "enhance_menu.h"
#include "recomp_env.h"

enum { SET_ENABLE, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_CRYSTALS", NULL, "BLiNX 1 crystals",
      "Collect crystals as in BLiNX 1: they fill a row of four in pickup"
      " order, three of one colour give that time control, four give it"
      " twice, and the row empties at four. Controls still go to the d-pad"
      " stock with its limits; a full control pays gold. Sweepers stages"
      " only; switching empties the rows.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "BLiNX 1 crystals",
    "Collect crystals the BLiNX 1 way: a row of four", NULL, "1",
    k_set, SET_N, NULL, 0
};

/* tc_crystal_collect: cdecl (item, free), the player in eax. Item +2 its
 * type (crystals 0x2A + k), +0xE its word. */
#define ITEM_TYPE       0x2u
#define ITEM_WORD       0xEu
/* The sprite add: vertices at ecx ({x, y, u, v} f32 x 4), frame eax of the
 * texture at [0xA723C8]; cdecl (count, depth, argb, 0, 0). */
#define VA_SPRITE_ADD   0x00042190u
#define VA_TEXTURE      0x00A723C8u
/* hud_time_controls_draw (sub_00072010)'s calls of it: each control slot's
 * icon, and the selected slot's count pips and their frames. */
#define RET_SLOT        0x000730BFu
#define RET_PIP         0x000736E6u
#define RET_PIP_FRAME   0x000737ADu
/* Its locals at the slot call, from the caller's esp (the call's esp plus
 * the return address and five arguments): the slot index j, the slot list
 * (control ids, -1 ended), its length n, the record and the player. */
#define SLOT_FRAME      0x18u
#define LOC_J           0x18u
#define LOC_PLAYER      0x24u
#define LOC_LIST        0x74u
#define LOC_RECORD      0x80u
#define LOC_N           0x84u
/* Control id -> the panel's frame, frame -> rgb (the slot icons' tint). */
#define TAB_SPRITE      0x003FD78Cu
#define TAB_COLOUR      0x003FD7C8u
/* The heart above the heart gauge (sub_0006B1F0's lit hearts, the add at
 * 0x6DB17): frame 3 of the texture at 0x418848, the whole texture. The
 * time-control panel has no RETRY slot, so its frames hold no heart.
 * 0x418848 is a static {frames, count}; sub_00037090 loads frame i's
 * handle into frames + i*0x24 + 0x20, the word the sprite add reads. */
#define HEART_TEX       0x00418848u
#define HEART_FRAME     3u
#define TEX_FRAME_SIZE  0x24u
#define TEX_FRAME_HANDLE 0x20u

/* The row's quads: 60 % of a slot icon, 15 % of that apart. */
#define ROW_SCALE       0.6f
#define ROW_GAP         0.15f
#define CANVAS_TOP      (-240.0f)
#define MAX_SLOTS       8

static const struct xbox_mod s_mod;
const struct xbox_mod_api *cry_api;
struct cry_stats cry_stats;

static int s_on;                        /* guest thread */
static uint32_t s_block;

/* The pickup in flight (guest thread). */
static int s_depth, s_active;
static uint32_t s_item;
static struct cry_pickup s_pick;
static uint8_t s_held[CRY_TEAMS][CRY_CHARS * 8];

/* The slot icons drawn this frame (guest thread). */
static struct {
    float v[16];
    uint32_t frame;
} s_icon[MAX_SLOTS];
static int s_nicons, s_drawing, s_new_frame;
static uint32_t s_tex, s_row_rec, s_row_player;

static inline uint8_t rd8(uint32_t va) { return *(volatile uint8_t *)(cry_api->mem + va); }
static inline uint16_t rd16(uint32_t va) { return *(volatile uint16_t *)(cry_api->mem + va); }
static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(cry_api, va); }

static uint32_t record(int t)
{
    return CRY_RECORD + (uint32_t)t * CRY_RECORD_SIZE;
}

static void spans(uint8_t *out[CRY_TEAMS])
{
    int t;

    for (t = 0; t < CRY_TEAMS; t++)
        out[t] = (uint8_t *)(cry_api->mem + record(t) + CRY_SPAN_OFF);
}

static int sweepers(void)
{
    return rd32(CRY_VA_TEAM_MODE) == 0;
}

uint32_t cry_block(void)
{
    if (!s_block)
        s_block = cry_api->guest_alloc(&s_mod, CRY_BLOCK_SIZE, 0x1000);
    return s_block;
}

static void clear_rows(const char *why)
{
    uint8_t *s[CRY_TEAMS];
    int t, c;

    if (!cry_api->mem || !sweepers())
        return;
    spans(s);
    for (t = 0; t < CRY_TEAMS; t++)
        for (c = 0; c < CRY_CHARS; c++)
            cry_clear(s[t], c);
    cry_api->log(&s_mod, "rows emptied (%s)", why);
}

/* ---- the pickup (D1) ---------------------------------------------------- */

static void collect_pre(struct xbox_mod_call *c, void *user)
{
    uint8_t *s[CRY_TEAMS];
    uint32_t type;
    int t;

    (void)user;
    if (s_depth++ || !sweepers())
        return;
    s_item = XBOX_MOD_ARG32(cry_api, c, 0);
    if (!s_item || s_item >= CRY_GUEST_TOP)
        return;
    type = rd8(s_item + ITEM_TYPE);
    if (type < CRY_TYPE0)
        return;
    for (t = 0; t < CRY_TEAMS; t++)
        memcpy(s_held[t], (void *)(cry_api->mem + record(t) + CRY_REC_HELD), sizeof s_held[t]);
    spans(s);
    /* As the pickup's own slot: (type - 0x2A) % 6. */
    cry_pickup_begin(&s_pick, s, (int)((type - CRY_TYPE0) % CRY_COLOURS), rd16(s_item + ITEM_WORD));
    s_active = 1;
}

static void collect_post(struct xbox_mod_call *c, void *user)
{
    uint8_t *s[CRY_TEAMS];
    int t, ch, r, got = 0;

    (void)user;
    if (--s_depth || !s_active)
        return;
    s_active = 0;
    spans(s);
    r = cry_pickup_end(&s_pick, s, &t, &ch);
    if (r == 2) {
        int id = cry_k_to_id[s_pick.k];

        /* The game granted when the held count went up, else paid gold. */
        got = rd8(record(t) + CRY_REC_HELD + (uint32_t)ch * 8 + (uint32_t)id) > s_held[t][ch * 8 + id];
        __atomic_fetch_add(got ? &cry_stats.sets : &cry_stats.gold, 1, __ATOMIC_RELAXED);
    }
    if (cry_proof_out)
        fprintf(cry_proof_out, "#collect item %08X k %d word %04X ret %u counted %d team %d char %d"
                " row %d%s\n", s_item, s_pick.k, s_pick.w, c->eax, r > 0, t, ch,
                r > 0 ? cry_row_len(s[t], ch) : 0, r == 2 ? (got ? " set" : " gold") : "");
}

/* ---- the HUD row (D3) --------------------------------------------------- */

static void quad_bounds(const float *v, float *x0, float *y0, float *x1, float *y1)
{
    int i;

    *x0 = *x1 = v[0];
    *y0 = *y1 = v[1];
    for (i = 1; i < 4; i++) {
        float x = v[i * 4], y = v[i * 4 + 1];

        *x0 = x < *x0 ? x : *x0;
        *x1 = x > *x1 ? x : *x1;
        *y0 = y < *y0 ? y : *y0;
        *y1 = y > *y1 ? y : *y1;
    }
}

/* How a row slot draws (cry_icon): the colour's control icon from the
 * panel's texture, tinted with the colour; a heart for RETRY; the first
 * icon, faint, when the slot is empty. */
struct row_icon {
    uint32_t tex, frame, argb;
    int own_uv;
};

/* The heart's frame is loaded: before the stage's HUD textures load, its
 * handle is 0 and the sprite add would draw nothing useful. */
static int heart_loaded(void)
{
    uint32_t frames = rd32(HEART_TEX);

    return frames && frames < CRY_GUEST_TOP && rd32(HEART_TEX + 4u) > HEART_FRAME &&
           rd32(frames + HEART_FRAME * TEX_FRAME_SIZE + TEX_FRAME_HANDLE) != 0;
}

static struct row_icon row_icon(int k)
{
    struct row_icon r = { s_tex, s_icon[0].frame, 0x40808080u, 0 };

    switch (cry_icon(k, k == CRY_RETRY && heart_loaded())) {
    case CRY_ICON_HEART:
        r.tex = HEART_TEX;
        r.frame = HEART_FRAME;
        r.argb = 0xF0FFFFFFu;
        r.own_uv = 1;
        cry_stats.hearts++;
        break;
    case CRY_ICON_COLOUR:
        r.frame = rd32(TAB_SPRITE + 4u * cry_k_to_id[k]);
        r.argb = 0xF0000000u | (r.frame < 16 ? rd32(TAB_COLOUR + 4u * r.frame) & 0xFFFFFFu : 0xFFFFFFu);
        break;
    }
    return r;
}

static void draw_row(uint32_t rec, uint32_t player)
{
    const uint8_t *s = (const uint8_t *)(cry_api->mem + rec + CRY_SPAN_OFF);
    int ch = (int)(int8_t)rd8(player + CRY_PLAYER_CHAR), i, tpl = 0, len;
    float bx0 = 0, by0 = 0, bx1 = 0, by1 = 0, w = 0, size, gap, total, cy;
    uint32_t tex, block;

    if (ch < 0 || ch >= CRY_CHARS || !s_nicons || !(block = cry_block()))
        return;
    /* The smallest icon is an unselected one: its size sets the row's. */
    for (i = 0; i < s_nicons; i++) {
        float x0, y0, x1, y1;

        quad_bounds(s_icon[i].v, &x0, &y0, &x1, &y1);
        if (!i || x1 - x0 < w) {
            w = x1 - x0;
            tpl = i;
        }
        bx0 = !i || x0 < bx0 ? x0 : bx0;
        by0 = !i || y0 < by0 ? y0 : by0;
        bx1 = !i || x1 > bx1 ? x1 : bx1;
        by1 = !i || y1 > by1 ? y1 : by1;
    }
    if (w <= 0)
        return;
    size = w * ROW_SCALE;
    gap = size * ROW_GAP;
    total = CRY_ROW * size + (CRY_ROW - 1) * gap;
    /* Above the slots, clear of the held bars the game draws over each
     * icon (one row height), or below when the panel sits at the top. */
    cy = by0 - gap - size / 2 - size;
    if (cy - size / 2 < CANVAS_TOP)
        cy = by1 + gap + size / 2;
    len = cry_row_len(s, ch);
    cry_stats.rows++;
    cry_stats.cy = cy;
    cry_stats.size = size;
    cry_stats.x0 = bx0;
    cry_stats.x1 = bx1;
    tex = rd32(VA_TEXTURE);
    s_drawing = 1;
    for (i = 0; i < CRY_ROW; i++) {
        struct row_icon ic = row_icon(i < len ? cry_row_at(s, ch, i) : -1);
        float x = bx0 + (bx1 - bx0 - total) / 2 + size / 2 + i * (size + gap), q[16];
        uint32_t va = block + (uint32_t)i * sizeof q;
        uint32_t args[5] = { 4, 0x3F800000u, ic.argb, 0, 0 };
        struct xbox_guest_args a = { ic.frame, va, 0, args, 5 };

        cry_quad(s_icon[tpl].v, q, x, cy, ROW_SCALE, ic.own_uv);
        memcpy((void *)(cry_api->mem + va), q, sizeof q);
        XBOX_MOD_MEM32(cry_api, VA_TEXTURE) = ic.tex;
        cry_api->guest_call(VA_SPRITE_ADD, &a, NULL);
    }
    s_drawing = 0;
    XBOX_MOD_MEM32(cry_api, VA_TEXTURE) = tex;
}

static void sprite_pre(struct xbox_mod_call *c, void *user)
{
    uint32_t ret;

    (void)user;
    if (s_drawing)
        return;
    ret = rd32(c->esp);
    if (ret == RET_SLOT)
        s_tex = rd32(VA_TEXTURE);
    else if ((ret == RET_PIP || ret == RET_PIP_FRAME) && sweepers()) {
        /* The pips would count the row's bytes: drawn fully clear. */
        XBOX_MOD_ARG32(cry_api, c, 2) &= 0x00FFFFFFu;
        cry_stats.pips++;
    }
}

static void sprite_post(struct xbox_mod_call *c, void *user)
{
    uint32_t b, j, n, list, rec, player;

    (void)user;
    if (s_drawing || rd32(c->esp) != RET_SLOT || !sweepers())
        return;
    cry_stats.slots++;
    b = c->esp + SLOT_FRAME;
    j = rd32(b + LOC_J);
    n = rd32(b + LOC_N);
    list = rd32(b + LOC_LIST);
    rec = rd32(b + LOC_RECORD);
    player = rd32(b + LOC_PLAYER);
    /* Read from the caller's frame: anything out of range (a changed
     * frame) leaves the row undrawn rather than drawing from garbage. */
    if (n < 1 || n > MAX_SLOTS || j >= n || !list || list >= CRY_GUEST_TOP ||
        rec < CRY_RECORD || rec >= record(CRY_TEAMS) || (rec - CRY_RECORD) % CRY_RECORD_SIZE ||
        player < CRY_VA_PLAYERS || player >= CRY_VA_PLAYERS + 4 * CRY_PLAYER_SIZE ||
        !c->ecx || c->ecx >= CRY_GUEST_TOP) {
        cry_stats.rejected++;
        return;
    }
    cry_stats.js |= 1u << j;
    cry_stats.n = n;
    /* The slot loop skips controls it does not show, so the last slot
     * drawn need not be j == n - 1: the row goes out at the first slot
     * of the next frame, from the icons the previous frame drew. */
    if (s_new_frame) {
        s_new_frame = 0;
        if (s_nicons)
            draw_row(s_row_rec, s_row_player);
        s_nicons = 0;
    }
    if (s_nicons >= MAX_SLOTS)
        return;
    memcpy(s_icon[s_nicons].v, (void *)(cry_api->mem + c->ecx), sizeof s_icon[0].v);
    s_icon[s_nicons].frame = c->eax;
    s_nicons++;
    s_row_rec = rec;
    s_row_player = player;
}

/* ---- the mod ------------------------------------------------------------ */

static void on_frame(void *user)
{
    (void)user;
    s_new_frame = 1;
    if (cry_proof_out && cry_api->mem)
        cry_proof_frame();
}

static void on_enable(int on, void *user)
{
    (void)user;
    /* A toggle between collect's pre and post (the hooks run only while
     * on) leaves the depth off by one and, turned off, the record
     * prepared. No pickup is in flight at this frame boundary: put the
     * spans back and start balanced, also when an off and on in one frame
     * reach here as a repeat of the state. */
    if (cry_api->mem) {
        uint8_t *s[CRY_TEAMS];

        spans(s);
        cry_settle(&s_pick, s, &s_depth, &s_active);
    } else {
        cry_settle(&s_pick, NULL, &s_depth, &s_active);
    }
    if (on == s_on)
        return;
    s_on = on;
    /* Off, the game would read a row as counts; on, the mod would read
     * counts as a row (D2): either way the rows start empty. */
    clear_rows(on ? "on" : "off");
    cry_api->log(&s_mod, "%s", on ? "on" : "off");
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    static const char *const names[CRY_COLOURS] = { "PAUSE", "REC", "FF", "RETRY", "REW", "SLOW" };
    const uint8_t *s;
    int ch, i, len, o;

    (void)it;
    if (cry_api->setting(&k_desc, SET_ENABLE) == 0) {
        snprintf(buf, n, "turn the mod on first");
        return buf;
    }
    if (!cry_api->mem) {
        snprintf(buf, n, "the game has not started");
        return buf;
    }
    if (!sweepers()) {
        snprintf(buf, n, "stock crystals in Tom Tom and VS");
        return buf;
    }
    s = (const uint8_t *)(cry_api->mem + record(rd8(CRY_VA_PLAYERS) / 4) + CRY_SPAN_OFF);
    ch = (int)(int8_t)rd8(CRY_VA_PLAYERS + CRY_PLAYER_CHAR);
    if (ch < 0 || ch >= CRY_CHARS)
        ch = 0;
    len = cry_row_len(s, ch);
    o = snprintf(buf, n, "row:");
    for (i = 0; i < len && o > 0 && (size_t)o < n; i++)
        o += snprintf(buf + o, n - (size_t)o, " %s", names[cry_row_at(s, ch, i)]);
    if (o > 0 && (size_t)o < n)
        snprintf(buf + o, n - (size_t)o, "%s; %d sets, %d paid in gold", len ? "" : " empty",
                 __atomic_load_n(&cry_stats.sets, __ATOMIC_RELAXED),
                 __atomic_load_n(&cry_stats.gold, __ATOMIC_RELAXED));
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.crystals.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static int init(const struct xbox_mod_api *api)
{
    const char *proof = recomp_env(RENV_CRYSTALS_PROOF);

    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc)
        return 1;   /* no v6 guest calls: stock */
    cry_api = api;
    if (!api->hook(CRY_VA_COLLECT, collect_pre, collect_post, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock crystals", CRY_VA_COLLECT);
        return 1;
    }
    if (!api->hook(VA_SPRITE_ADD, sprite_pre, sprite_post, 0, NULL))
        api->log(&s_mod, "no hook slot for 0x%08X: the row is not drawn", VA_SPRITE_ADD);
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_status_row);
    if (proof)
        cry_proof_init(&s_mod, proof);
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "crystals", init, NULL, &k_desc,
                                       XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK };

const void *crystals_mod(void)
{
    return &s_mod;
}

#else /* no mod API v6: stock */

const void *crystals_mod(void)
{
    return NULL;
}

#endif
