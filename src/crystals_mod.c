/*
 * crystals_mod.c - the crystals mod (crystals_mod.h; openspec change
 * crystal-sets).
 *
 * BLiNX 1's crystal row in BLiNX 2: four crystals in pickup order, three
 * of one colour give that time control, four give it twice, and the row
 * empties at four. The controls go into BLiNX 2's own stock, picked with
 * the d-pad, under its caps; a set made while the control is full pays
 * gold, as stock does.
 *
 * The mod never replaces the pickup (D1): a pre and a post on
 * tc_crystal_collect (sub_0008BFD0) set the record's counts so the game's
 * own code grants exactly when the row says so, then put the record back
 * and push the crystal into the row of whichever character the game
 * counted it for. Item freeing, sounds, the two-player and team redirects,
 * bounces and the taken flag all stay the game's. The row lives in the
 * record's count bytes (D2), so checkpoints, retries and the stage start's
 * clear carry it with no code here. The HUD (D3) hides the stock count
 * pips and draws the row above the time-control slots through the game's
 * own sprite add (sub_00042190).
 *
 * Only Sweepers stages (stage_team_mode 0); Tom Tom and VS stay stock
 * (D4). Off (the default, every golden): the hooks do not run, on_frame
 * returns before reading the guest unless the proof runs, and no guest
 * memory is allocated.
 *
 * RECOMP_DEBUG=crystals_proof=<steps> spawns crystals at player 1 on a
 * schedule and logs the record each time it changes (proof_*; design D6).
 */
#include <stddef.h>
#include "crystals_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define CRYSTALS_MOD 1
#    endif
#  endif
#endif

#ifdef CRYSTALS_MOD

#include <stdint.h>
#include <stdio.h>
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
    [SET_ENABLE] = { "enable", NULL, "RECOMP_CRYSTALS", NULL, "BLiNX 1 crystal sets",
      "Crystals fill a row of four in pickup order, as in BLiNX 1: three of"
      " one colour give that time control, four give it twice, and the row"
      " empties at four. Controls still go to the d-pad stock with its"
      " limits; a full control pays gold. Sweepers stages only; switching"
      " empties the rows.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Crystals",
    "BLiNX 1-style crystal sets", NULL, "1",
    k_set, SET_N, NULL, 0
};

/* tc_crystal_collect: cdecl (item, free), the player in eax; returns 0 or
 * 1. Item +2 its type (crystals 0x2A + k), +0xE its word. */
#define VA_COLLECT      0x0008BFD0u
#define CRYSTAL_TYPE0   0x2Au
/* The sprite add: vertices at ecx ({x, y, u, v} f32 x 4), the sprite id in
 * eax, from the texture at [0xA723C8]; cdecl (count, depth, argb, 0, 0). */
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
/* Control id -> sprite id, sprite id -> rgb (the slot icons' tint). */
#define TAB_SPRITE      0x003FD78Cu
#define TAB_COLOUR      0x003FD7C8u

#define VA_TEAM_MODE    0x00B21CB4u     /* stage_team_mode: 0 Sweepers */
#define VA_PLAYERS      0x00CD2440u     /* players, 0x30C each */
#define PLAYER_SIZE     0x30Cu
#define PLAYER_CHAR     0x41u
#define PLAYER_POS      0xECu
#define PLAYER_GOLD     0xDCu           /* int16 */
#define REC_HELD        0xAEu           /* + c*8 + id */
#define REC_CAP         0xC6u
#define REC_SEL         0x5ACu
#define GUEST_TOP       0x04000000u

/* The row's quads: 60 % of a slot icon, 15 % of that apart. */
#define ROW_SCALE       0.6f
#define ROW_GAP         0.15f
#define CANVAS_TOP      (-240.0f)
#define BLOCK_SIZE      0x1000u
#define BLOCK_POS       0x800u          /* the proof's spawn position */

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

static int s_on;                        /* guest thread */
static int s_sets, s_gold;              /* this run; any thread reads */
static uint32_t s_block;                /* guest_alloc, at first use */

/* The pickup in flight (guest thread). */
static int s_depth, s_active, s_k;
static uint16_t s_w;
static uint32_t s_item;
static uint8_t s_snap[CRY_TEAMS][CRY_SPAN];
static uint8_t s_held[CRY_TEAMS][CRY_CHARS * 8];
static int s_slot[CRY_TEAMS][CRY_CHARS];

/* The slot icons drawn this frame (guest thread). */
#define MAX_SLOTS 8
static struct {
    float v[16];
    uint32_t sprite;
} s_icon[MAX_SLOTS];
static int s_nicons, s_drawing, s_new_frame;
static uint32_t s_tex, s_row_rec, s_row_player;

/* What the HUD hooks saw, for the proof log (guest thread). */
static struct {
    uint32_t slots, pips, rows, rejected, js, n;
    float cy, size, x0, x1;
} s_hud;

static FILE *s_out;

static inline uint8_t rd8(uint32_t va) { return *(volatile uint8_t *)(s_api->mem + va); }
static inline uint16_t rd16(uint32_t va) { return *(volatile uint16_t *)(s_api->mem + va); }
static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(s_api, va); }

static uint8_t *span(int t)
{
    return (uint8_t *)(s_api->mem + CRY_RECORD + (uint32_t)t * CRY_RECORD_SIZE + CRY_SPAN_OFF);
}

static int sweepers(void)
{
    return rd32(VA_TEAM_MODE) == 0;
}

static void clear_rows(const char *why)
{
    int t, c;

    if (!s_api->mem || !sweepers())
        return;
    for (t = 0; t < CRY_TEAMS; t++)
        for (c = 0; c < CRY_CHARS; c++)
            cry_clear(span(t), c);
    s_api->log(&s_mod, "rows emptied (%s)", why);
}

/* ---- the pickup (D1) ---------------------------------------------------- */

static void collect_pre(struct xbox_mod_call *c, void *user)
{
    uint32_t type;
    int t, ch;

    (void)user;
    if (s_depth++ || !sweepers())
        return;
    s_item = XBOX_MOD_ARG32(s_api, c, 0);
    if (!s_item || s_item >= GUEST_TOP)
        return;
    type = rd8(s_item + 2);
    if (type < CRYSTAL_TYPE0)
        return;
    /* As the pickup's own slot: (type - 0x2A) % 6. */
    s_k = (int)((type - CRYSTAL_TYPE0) % CRY_COLOURS);
    s_w = rd16(s_item + 0xE);
    for (t = 0; t < CRY_TEAMS; t++) {
        uint32_t rec = CRY_RECORD + (uint32_t)t * CRY_RECORD_SIZE;

        memcpy(s_snap[t], span(t), CRY_SPAN);
        memcpy(s_held[t], (void *)(s_api->mem + rec + REC_HELD), sizeof s_held[t]);
        for (ch = 0; ch < CRY_CHARS; ch++)
            s_slot[t][ch] = cry_prepare(s_snap[t], span(t), ch, s_k, s_w);
    }
    s_active = 1;
}

static void collect_post(struct xbox_mod_call *c, void *user)
{
    int t, ch, ft = -1, fc = -1, grant = 0, len = 0, got = 0;

    (void)user;
    if (--s_depth || !s_active)
        return;
    s_active = 0;
    for (t = 0; t < CRY_TEAMS && ft < 0; t++)
        for (ch = 0; ch < CRY_CHARS; ch++)
            if (cry_counted(span(t), ch, s_k, s_slot[t][ch], s_w)) {
                ft = t;
                fc = ch;
                break;
            }
    for (t = 0; t < CRY_TEAMS; t++)
        memcpy(span(t), s_snap[t], CRY_SPAN);
    if (ft >= 0) {
        uint32_t rec = CRY_RECORD + (uint32_t)ft * CRY_RECORD_SIZE;
        int id = cry_k_to_id[s_k];

        grant = cry_grants(s_snap[ft], fc, s_k);
        len = cry_push(span(ft), fc, s_k, s_w);
        if (grant) {
            got = rd8(rec + REC_HELD + (uint32_t)fc * 8 + (uint32_t)id) >
                  s_held[ft][fc * 8 + id];
            __atomic_fetch_add(got ? &s_sets : &s_gold, 1, __ATOMIC_RELAXED);
        }
    }
    if (s_out)
        fprintf(s_out, "#collect item %08X k %d word %04X ret %u counted %d team %d char %d"
                " row %d%s\n", s_item, s_k, s_w, c->eax, ft >= 0, ft, fc, len,
                grant ? (got ? " set" : " gold") : "");
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

static void draw_row(uint32_t rec, uint32_t player)
{
    const uint8_t *s = (const uint8_t *)(s_api->mem + rec + CRY_SPAN_OFF);
    int ch = (int)(int8_t)rd8(player + PLAYER_CHAR), i, tpl = 0, len;
    float bx0 = 0, by0 = 0, bx1 = 0, by1 = 0, w = 0, size, gap, total, cy;
    uint32_t tex;

    if (ch < 0 || ch >= CRY_CHARS || !s_nicons)
        return;
    if (!s_block)
        s_block = s_api->guest_alloc(&s_mod, BLOCK_SIZE, 0x1000);
    if (!s_block)
        return;
    /* The smallest icon is an unselected one: its size sets the row's. */
    for (i = 0; i < s_nicons; i++) {
        float x0, y0, x1, y1;

        quad_bounds(s_icon[i].v, &x0, &y0, &x1, &y1);
        if (!i || x1 - x0 < w) {
            w = x1 - x0;
            tpl = i;
        }
        if (!i) {
            bx0 = x0, by0 = y0, bx1 = x1, by1 = y1;
        } else {
            bx0 = x0 < bx0 ? x0 : bx0;
            by0 = y0 < by0 ? y0 : by0;
            bx1 = x1 > bx1 ? x1 : bx1;
            by1 = y1 > by1 ? y1 : by1;
        }
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
    s_hud.rows++;
    s_hud.cy = cy;
    s_hud.size = size;
    s_hud.x0 = bx0;
    s_hud.x1 = bx1;
    tex = rd32(VA_TEXTURE);
    XBOX_MOD_MEM32(s_api, VA_TEXTURE) = s_tex;
    s_drawing = 1;
    for (i = 0; i < CRY_ROW; i++) {
        const float *tv = s_icon[tpl].v;
        int k = i < len ? cry_row_at(s, ch, i) : -1, j;
        float x0, y0, x1, y1, ox, oy, nx = bx0 + (bx1 - bx0 - total) / 2 + size / 2 + i * (size + gap);
        float q[16];
        uint32_t sprite, argb, va = s_block + (uint32_t)i * 64u;
        uint32_t args[5];
        struct xbox_guest_args a;

        quad_bounds(tv, &x0, &y0, &x1, &y1);
        ox = (x0 + x1) / 2;
        oy = (y0 + y1) / 2;
        for (j = 0; j < 4; j++) {
            q[j * 4] = nx + (tv[j * 4] - ox) * ROW_SCALE;
            q[j * 4 + 1] = cy + (tv[j * 4 + 1] - oy) * ROW_SCALE;
            q[j * 4 + 2] = tv[j * 4 + 2];
            q[j * 4 + 3] = tv[j * 4 + 3];
        }
        if (k >= 0) {
            sprite = rd32(TAB_SPRITE + 4u * cry_k_to_id[k]);
            argb = 0xF0000000u | (sprite < 16 ? rd32(TAB_COLOUR + 4u * sprite) & 0xFFFFFFu : 0xFFFFFFu);
        } else {
            sprite = s_icon[0].sprite;
            argb = 0x40808080u;
        }
        memcpy((void *)(s_api->mem + va), q, sizeof q);
        args[0] = 4;
        args[1] = 0x3F800000u;
        args[2] = argb;
        args[3] = 0;
        args[4] = 0;
        a.eax = sprite;
        a.ecx = va;
        a.edx = 0;
        a.stack = args;
        a.n_stack = 5;
        s_api->guest_call(VA_SPRITE_ADD, &a, NULL);
    }
    s_drawing = 0;
    XBOX_MOD_MEM32(s_api, VA_TEXTURE) = tex;
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
        XBOX_MOD_ARG32(s_api, c, 2) &= 0x00FFFFFFu;
        s_hud.pips++;
    }
}

static void sprite_post(struct xbox_mod_call *c, void *user)
{
    uint32_t b, j, n, list, rec, player;

    (void)user;
    if (s_drawing || rd32(c->esp) != RET_SLOT || !sweepers())
        return;
    s_hud.slots++;
    b = c->esp + SLOT_FRAME;
    j = rd32(b + LOC_J);
    n = rd32(b + LOC_N);
    list = rd32(b + LOC_LIST);
    rec = rd32(b + LOC_RECORD);
    player = rd32(b + LOC_PLAYER);
    /* Read from the caller's frame: anything out of range (a changed
     * frame) leaves the row undrawn rather than drawing from garbage. */
    if (n < 1 || n > MAX_SLOTS || j >= n || !list || list >= GUEST_TOP ||
        rec < CRY_RECORD || rec >= CRY_RECORD + CRY_TEAMS * CRY_RECORD_SIZE ||
        (rec - CRY_RECORD) % CRY_RECORD_SIZE || player < VA_PLAYERS ||
        player >= VA_PLAYERS + 4 * PLAYER_SIZE || !c->ecx || c->ecx >= GUEST_TOP) {
        s_hud.rejected++;
        return;
    }
    s_hud.js |= 1u << j;
    s_hud.n = n;
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
    memcpy(s_icon[s_nicons].v, (void *)(s_api->mem + c->ecx), sizeof s_icon[0].v);
    s_icon[s_nicons].sprite = c->eax;
    s_nicons++;
    s_row_rec = rec;
    s_row_player = player;
}

/* ---- the proof driver (guest thread; D6) -------------------------------- */

static uint32_t s_frame, s_play, s_seg_play, s_seg_mission;
static int s_playing, s_spawned, s_seg_first;
static long o_at = 60, o_every = 30, o_dup = -1, o_rew = -1;
static char o_seq[160];
static uint8_t s_last[CRY_SPAN + 0x30 + 8];
static uint32_t s_last_misc[4];

#define VA_CKPT         0x00AE73FCu
#define VA_STAGE        0x00B87168u
#define VA_MISSION      0x00B871B0u
#define VA_PLAY_MODE    0x00AE46ECu
#define VA_TC_REQ       0x00ADE76Cu
#define VA_TC_TIMER     0x00AEB818u
#define TC_REW          0x1000u
#define TC_FRAMES       0x12Cu
#define VA_ITEM_SPAWN   0x000794D0u

static void proof_row(const char *why)
{
    uint32_t p = VA_PLAYERS, rec = CRY_RECORD + (uint32_t)(rd8(p) / 4) * CRY_RECORD_SIZE;
    int ch = (int)(int8_t)rd8(p + PLAYER_CHAR), i, id;
    const uint8_t *s = (const uint8_t *)(s_api->mem + rec + CRY_SPAN_OFF);

    if (ch < 0 || ch >= CRY_CHARS)
        ch = 0;
    fprintf(s_out, "F %u play %u %s stage %u mission %u team_mode %u mode %X req %X char %d row",
            s_frame, s_playing ? s_play : 0, why, rd32(VA_STAGE), rd32(VA_MISSION),
            rd32(VA_TEAM_MODE), rd32(VA_PLAY_MODE), rd32(VA_TC_REQ), ch);
    for (i = 0; i < CRY_COLOURS; i++)
        fprintf(s_out, " %u", s[ch * CRY_COLOURS + i]);
    fprintf(s_out, " | held(id1..6)");
    for (id = 1; id <= 6; id++)
        fprintf(s_out, " %u", rd8(rec + REC_HELD + (uint32_t)ch * 8 + (uint32_t)id));
    fprintf(s_out, " | cap");
    for (id = 1; id <= 6; id++)
        fprintf(s_out, " %u", rd8(rec + REC_CAP + (uint32_t)ch * 8 + (uint32_t)id));
    fprintf(s_out, " | hud slots %u (j %X n %u) pips %u rows %u rejected %u row y %.1f size %.1f x %.1f..%.1f",
            s_hud.slots, s_hud.js, s_hud.n, s_hud.pips, s_hud.rows, s_hud.rejected, s_hud.cy,
            s_hud.size, s_hud.x0, s_hud.x1);
    fprintf(s_out, " | sel %d cursor %d | gold %d sets %d paid %d\n", (int)rd32(rec + REC_SEL),
            (int)rd32(rec + REC_SEL - 4),
            (int)*(volatile int16_t *)(s_api->mem + p + PLAYER_GOLD),
            __atomic_load_n(&s_sets, __ATOMIC_RELAXED), __atomic_load_n(&s_gold, __ATOMIC_RELAXED));
}

static uint32_t proof_collect(uint32_t item)
{
    uint32_t args[2] = { item, 1 }, ret = 0;
    struct xbox_guest_args a = { VA_PLAYERS, 0, 0, args, 2 };

    s_api->guest_call(VA_COLLECT, &a, &ret);
    return ret;
}

static void proof_spawn(int k)
{
    uint32_t args[4], slot = 0;
    struct xbox_guest_args a = { 0, 0, 0, args, 4 };

    if (!s_block)
        s_block = s_api->guest_alloc(&s_mod, BLOCK_SIZE, 0x1000);
    if (!s_block)
        return;
    memcpy((void *)(s_api->mem + s_block + BLOCK_POS),
           (void *)(s_api->mem + VA_PLAYERS + PLAYER_POS), 12);
    args[0] = s_block + BLOCK_POS;
    args[1] = 0;
    args[2] = CRYSTAL_TYPE0 + (uint32_t)k;
    args[3] = 0;
    s_api->guest_call(VA_ITEM_SPAWN, &a, &slot);
    fprintf(s_out, "#spawn play %u n %d k %d type 0x%X slot %08X\n", s_play, s_spawned, k,
            CRYSTAL_TYPE0 + (unsigned)k, slot);
    /* dup:<n>: the n-th crystal goes through the pickup twice at once, as
     * the player's touch does (free 1); only the first may count. */
    if (s_spawned == o_dup && slot && slot < GUEST_TOP) {
        uint32_t r1 = proof_collect(slot), r2 = proof_collect(slot);

        fprintf(s_out, "#dup slot %08X first %u second %u\n", slot, r1, r2);
    }
}

static void proof_frame(void)
{
    uint32_t rec = CRY_RECORD + (uint32_t)(rd8(VA_PLAYERS) / 4) * CRY_RECORD_SIZE;
    uint32_t misc[4] = { rd32(VA_STAGE), rd32(VA_MISSION), rd32(VA_TEAM_MODE),
                         (uint32_t)*(volatile int16_t *)(s_api->mem + VA_PLAYERS + PLAYER_GOLD) };
    uint8_t now[sizeof s_last];

    s_frame++;
    /* A Sweepers stage starts play at its first checkpoint; VS and Tom
     * Tom have none, so their play starts with the mission. */
    if (!s_playing && (rd32(VA_CKPT) == 1 || (rd32(VA_TEAM_MODE) && rd32(VA_MISSION)))) {
        s_playing = 1;
        s_play = 0;
        s_seg_mission = rd32(VA_MISSION);
        s_api->log(&s_mod, "proof: play starts f%u stage %u", s_frame, rd32(VA_STAGE));
    }
    if (s_playing) {
        size_t n = strlen(o_seq);

        /* '|' holds the rest of seq until the mission changes; its spawns
         * then count at and every from that change. */
        if (s_spawned < (int)n && o_seq[s_spawned] == '|') {
            if (rd32(VA_MISSION) != s_seg_mission) {
                s_seg_mission = rd32(VA_MISSION);
                s_seg_play = s_play;
                s_seg_first = ++s_spawned;
                fprintf(s_out, "#segment play %u mission %u\n", s_play, s_seg_mission);
            }
        } else if (s_spawned < (int)n &&
                   (long)(s_play - s_seg_play) == o_at + (s_spawned - s_seg_first) * o_every) {
            char d = o_seq[s_spawned];

            if (d >= '0' && d <= '5')
                proof_spawn(d - '0');
            s_spawned++;
        }
        if ((long)s_play == o_rew) {
            XBOX_MOD_MEM32(s_api, VA_TC_REQ) = TC_REW;
            XBOX_MOD_MEM32(s_api, VA_TC_TIMER) = TC_FRAMES;
            fprintf(s_out, "#rew play %u\n", s_play);
        }
        s_play++;
    }
    memcpy(now, (void *)(s_api->mem + rec + CRY_SPAN_OFF), CRY_SPAN);
    memcpy(now + CRY_SPAN, (void *)(s_api->mem + rec + REC_HELD), 0x30);
    memcpy(now + CRY_SPAN + 0x30, (void *)(s_api->mem + rec + REC_SEL - 4), 8);
    if (memcmp(now, s_last, sizeof now) || memcmp(misc, s_last_misc, sizeof misc) ||
        !(s_frame % 300)) {
        proof_row(memcmp(now, s_last, sizeof now) || memcmp(misc, s_last_misc, sizeof misc)
                  ? "chg" : "tick");
        memcpy(s_last, now, sizeof now);
        memcpy(s_last_misc, misc, sizeof misc);
        fflush(s_out);
    }
}

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

/* RECOMP_DEBUG splits on commas, so the steps are joined by '+'. */
static void proof_init(const char *v)
{
    char path[512] = "crystals_proof.tsv";

    str_opt(v, "out:", path, sizeof path);
    str_opt(v, "seq:", o_seq, sizeof o_seq);
    o_at = opt(v, "at", o_at);
    o_every = opt(v, "every", o_every);
    o_dup = opt(v, "dup", o_dup);
    o_rew = opt(v, "rew", o_rew);
    s_out = fopen(path, "w");
    if (!s_out)
        s_api->log(&s_mod, "proof: cannot write %s", path);
    s_api->log(&s_mod, "proof: log %s, seq %s, at %ld, every %ld, dup %ld, rew %ld", path, o_seq,
               o_at, o_every, o_dup, o_rew);
}

/* ---- the mod ------------------------------------------------------------ */

static void on_frame(void *user)
{
    (void)user;
    s_new_frame = 1;
    if (s_out && s_api->mem)
        proof_frame();
}

static void on_enable(int on, void *user)
{
    (void)user;
    if (on == s_on)
        return;
    s_on = on;
    /* A toggle between collect's pre and post leaves s_depth off by one
     * and, turned off, the record prepared; at this frame boundary no
     * pickup is in flight, so put the spans back and start balanced. */
    if (cry_settle(&s_depth, &s_active) && s_api->mem) {
        int t;

        for (t = 0; t < CRY_TEAMS; t++)
            memcpy(span(t), s_snap[t], CRY_SPAN);
    }
    /* Off, the game would read a row as counts; on, the mod would read
     * counts as a row (D2): either way the rows start empty. */
    clear_rows(on ? "on" : "off");
    s_api->log(&s_mod, "%s", on ? "on" : "off");
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    static const char *const names[CRY_COLOURS] = { "PAUSE", "REC", "FF", "RETRY", "REW", "SLOW" };
    const uint8_t *s;
    int ch, i, len, o;

    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0) {
        snprintf(buf, n, "turn the mod on first");
        return buf;
    }
    if (!s_api->mem) {
        snprintf(buf, n, "the game has not started");
        return buf;
    }
    if (!sweepers()) {
        snprintf(buf, n, "stock crystals in Tom Tom and VS");
        return buf;
    }
    s = (const uint8_t *)(s_api->mem + CRY_RECORD + (uint32_t)(rd8(VA_PLAYERS) / 4) * CRY_RECORD_SIZE +
                          CRY_SPAN_OFF);
    ch = (int)(int8_t)rd8(VA_PLAYERS + PLAYER_CHAR);
    if (ch < 0 || ch >= CRY_CHARS)
        ch = 0;
    len = cry_row_len(s, ch);
    o = snprintf(buf, n, "row:");
    for (i = 0; i < len && o > 0 && (size_t)o < n; i++)
        o += snprintf(buf + o, n - (size_t)o, " %s", names[cry_row_at(s, ch, i)]);
    if (o > 0 && (size_t)o < n)
        snprintf(buf + o, n - (size_t)o, "%s; %d sets, %d paid in gold", len ? "" : " empty",
                 __atomic_load_n(&s_sets, __ATOMIC_RELAXED),
                 __atomic_load_n(&s_gold, __ATOMIC_RELAXED));
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
    s_api = api;
    if (!api->hook(VA_COLLECT, collect_pre, collect_post, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock crystals", VA_COLLECT);
        return 1;
    }
    if (!api->hook(VA_SPRITE_ADD, sprite_pre, sprite_post, 0, NULL))
        api->log(&s_mod, "no hook slot for 0x%08X: the row is not drawn", VA_SPRITE_ADD);
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_status_row);
    if (proof)
        proof_init(proof);
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
