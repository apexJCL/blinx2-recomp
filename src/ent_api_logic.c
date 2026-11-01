/*
 * ent_api_logic.c - the entity API's pure rules (ent_api_logic.h).
 *
 * Every read goes through memcpy: objects sit at odd addresses (a pool slot
 * is a used byte, then the object), and a pointer the game left stale must
 * not fault the host, so each one is checked against the view first.
 */
#include "ent_api_logic.h"

#include <string.h>

/* The first guest page is never mapped: a pointer below it is garbage. */
#define ENTL_LOW 0x1000u

uint8_t *entl_host(const struct entl_mem *m, uint32_t va, uint32_t n)
{
    if (m->base && va >= ENTL_LOW && va < m->size && n <= m->size - va)
        return m->base + va;
    if (m->hi && va >= m->hi_va && va - m->hi_va < m->hi_size && n <= m->hi_size - (va - m->hi_va))
        return m->hi + (va - m->hi_va);
    return NULL;
}

int entl_ok(const struct entl_mem *m, uint32_t va, uint32_t n)
{
    return entl_host(m, va, n) != NULL;
}

uint32_t entl_rd32(const struct entl_mem *m, uint32_t va)
{
    uint32_t v = 0;
    uint8_t *h = entl_host(m, va, 4);

    if (h)
        memcpy(&v, h, 4);
    return v;
}

int16_t entl_rd16(const struct entl_mem *m, uint32_t va)
{
    int16_t v = 0;
    uint8_t *h = entl_host(m, va, 2);

    if (h)
        memcpy(&v, h, 2);
    return v;
}

float entl_rdf(const struct entl_mem *m, uint32_t va)
{
    float v = 0.0f;
    uint8_t *h = entl_host(m, va, 4);

    if (h)
        memcpy(&v, h, 4);
    return v;
}

static void wr32(const struct entl_mem *m, uint32_t va, uint32_t v)
{
    uint8_t *h = entl_host(m, va, 4);

    if (h)
        memcpy(h, &v, 4);
}

static void wrf(const struct entl_mem *m, uint32_t va, float v)
{
    uint8_t *h = entl_host(m, va, 4);

    if (h)
        memcpy(h, &v, 4);
}

/* ---- the list ---------------------------------------------------------- */

int entl_walk(const struct entl_mem *m, uint32_t *objs, int max)
{
    uint32_t node = entl_rd32(m, ENTL_LIST);
    int n = 0, k;

    for (k = 0; k < ENTL_MAX_NODES && n < max && node; k++) {
        uint32_t obj;

        if (!entl_ok(m, node, 12))
            break;
        obj = entl_rd32(m, node + 8);
        if (!entl_ok(m, obj, ENTL_OB_DEAD_FRAMES + 2))
            break;
        objs[n++] = obj;
        node = entl_rd32(m, node + 4);
    }
    return n;
}

uint32_t entl_tail(const struct entl_mem *m)
{
    uint32_t objs[ENTL_MAX_NODES];
    int n = entl_walk(m, objs, ENTL_MAX_NODES);

    return n ? objs[n - 1] : 0;
}

uint32_t entl_count(const struct entl_mem *m)
{
    return entl_rd32(m, ENTL_LIST_COUNT);
}

struct ent_handle entl_handle(const struct entl_mem *m, uint32_t obj)
{
    struct ent_handle h;

    h.obj = obj;
    h.placement = entl_rd32(m, obj + ENTL_OB_PLACEMENT);
    h.id = entl_rd16(m, obj + ENTL_OB_ID);
    return h;
}

int entl_handle_ok(const struct entl_mem *m, struct ent_handle h)
{
    uint32_t objs[ENTL_MAX_NODES];
    int n = entl_walk(m, objs, ENTL_MAX_NODES), i;

    if (!h.obj)
        return 0;
    for (i = 0; i < n; i++) {
        if (objs[i] == h.obj) {
            struct ent_handle now = entl_handle(m, h.obj);

            return now.placement == h.placement && now.id == h.id;
        }
    }
    return 0;
}

void entl_info(const struct entl_mem *m, uint32_t obj, uint32_t rec_va, struct ent_info *o)
{
    int i;

    memset(o, 0, sizeof *o);
    o->h = entl_handle(m, obj);
    o->cls = entl_rd32(m, obj + ENTL_OB_CLASS);
    o->state = entl_rd32(m, obj + ENTL_OB_STATE);
    o->flags = entl_rd32(m, obj + ENTL_OB_FLAGS);
    o->hp = entl_rd16(m, obj + ENTL_OB_HP);
    o->hp_max = entl_rd16(m, obj + ENTL_OB_HP_MAX);
    for (i = 0; i < 3; i++) {
        o->pos[i] = entl_rdf(m, obj + ENTL_OB_POS + 4u * (uint32_t)i);
        o->rot[i] = entl_rdf(m, obj + ENTL_OB_ROT + 4u * (uint32_t)i);
    }
    o->dead = o->state == ENTL_STATE_DEAD;
    o->dead_frames = o->dead ? (uint16_t)entl_rd16(m, obj + ENTL_OB_DEAD_FRAMES) : 0;
    o->spawned = entl_rec_index(rec_va, o->h.placement) >= 0;
}

/* The classes (& 0xFF) the stage table 0x4921E8 and the extra sets spawn,
 * less 0x14, whose init (ent_enemy_init_spawner) spawns again without
 * checking the count, and 0x21, the extra sets' only class, which the
 * spawn's switch sends to its default: no init, so a slot and a node leak
 * (audit, config/symbols.toml). */
static const uint8_t k_allowed[] = {
    0x01, 0x02, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0D,
    0x0E, 0x10, 0x12, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86,
};

int entl_class_allowed(uint32_t cls)
{
    size_t i;

    for (i = 0; i < sizeof k_allowed; i++)
        if (k_allowed[i] == (cls & 0xFFu))
            return 1;
    return 0;
}

/* ---- records ----------------------------------------------------------- */

uint32_t entl_rec_va(uint32_t rec_va, int i)
{
    return rec_va + (uint32_t)i * ENTL_PL_SIZE;
}

int entl_rec_index(uint32_t rec_va, uint32_t placement)
{
    uint32_t off;

    if (!rec_va || placement < rec_va)
        return -1;
    off = placement - rec_va;
    if (off >= ENTL_RECORDS * ENTL_PL_SIZE || off % ENTL_PL_SIZE)
        return -1;
    return (int)(off / ENTL_PL_SIZE);
}

static uint32_t used_va(uint32_t rec_va, int i)
{
    return rec_va + ENTL_RECORDS * ENTL_PL_SIZE + (uint32_t)i;
}

int entl_rec_used(const struct entl_mem *m, uint32_t rec_va, int i)
{
    const uint8_t *u = entl_host(m, used_va(rec_va, i), 1);

    return u && *u;
}

static void set_used(const struct entl_mem *m, uint32_t rec_va, int i, int used)
{
    uint8_t *u = entl_host(m, used_va(rec_va, i), 1);

    if (u)
        *u = (uint8_t)used;
}

void entl_rec_release(const struct entl_mem *m, uint32_t rec_va, int i)
{
    if (i >= 0 && (uint32_t)i < ENTL_RECORDS)
        set_used(m, rec_va, i, 0);
}

int entl_rec_free_index(const struct entl_mem *m, uint32_t rec_va)
{
    int i;

    if (!rec_va || !entl_ok(m, rec_va, ENTL_BLOCK_SIZE))
        return -1;
    for (i = 0; i < (int)ENTL_RECORDS; i++)
        if (!entl_rec_used(m, rec_va, i))
            return i;
    return -1;
}

/* The used byte: 0 free, 1 used, then the two states design D5 adds. */
#define REC_MARKED  2u  /* used before the last area setup */
#define REC_RETIRED 3u  /* swept; not reused until the next area setup */

static unsigned rec_state(const struct entl_mem *m, uint32_t rec_va, int i)
{
    const uint8_t *u = entl_host(m, used_va(rec_va, i), 1);

    return u ? *u : 0;
}

int entl_rec_age(const struct entl_mem *m, uint32_t rec_va, int stage_start)
{
    int i, n = 0;

    if (!rec_va || !entl_ok(m, rec_va, ENTL_BLOCK_SIZE))
        return 0;
    for (i = 0; i < (int)ENTL_RECORDS; i++) {
        unsigned st = rec_state(m, rec_va, i);

        /* A retired record stays so until a stage starts: the stage's
         * checkpoint frame still holds its copy, and every retry from it
         * brings the copy back (design D5). */
        if (st == REC_RETIRED) {
            if (stage_start)
                set_used(m, rec_va, i, 0);
        } else if (st) {
            set_used(m, rec_va, i, REC_MARKED);
            n++;
        }
    }
    return n;
}

static int rec_swept(unsigned st)
{
    return st == REC_MARKED || st == REC_RETIRED;
}

/* A listed object pointing into the block is the API's: no game placement
 * lives there. Any state but used makes it a copy to remove (a free one:
 * a restore reached back past the setup that freed its record). */
static int rec_copy_gone(unsigned st)
{
    return st != 1u;
}

/* The list's nodes and objects, as entl_walk stops. */
static int walk_nodes(const struct entl_mem *m, uint32_t *nodes, uint32_t *objs)
{
    uint32_t node = entl_rd32(m, ENTL_LIST);
    int n = 0;

    while (n < ENTL_MAX_NODES && node) {
        uint32_t obj;

        if (!entl_ok(m, node - 1u, 13))
            break;
        obj = entl_rd32(m, node + 8);
        if (!entl_ok(m, obj - 1u, ENTL_OB_DEAD_FRAMES + 3))
            break;
        nodes[n] = node;
        objs[n++] = obj;
        node = entl_rd32(m, node + 4);
    }
    return n;
}

/* sub_0004EDC0 on node, then the used bytes sub_0004ED30 clears last. */
static void unlink_node(const struct entl_mem *m, uint32_t node, uint32_t obj)
{
    uint32_t head = entl_rd32(m, ENTL_LIST);
    uint32_t prev, next;
    uint8_t *u;

    if (head == entl_rd32(m, ENTL_LIST_TAIL)) {
        wr32(m, ENTL_LIST, 0);
        wr32(m, ENTL_LIST_TAIL, 0);
    } else {
        prev = entl_rd32(m, node);
        next = entl_rd32(m, node + 4);
        if (prev)
            wr32(m, prev + 4, next);
        if (next)
            wr32(m, next, prev);
        if (node == head)
            wr32(m, ENTL_LIST, next);
        else if (node == entl_rd32(m, ENTL_LIST_TAIL))
            wr32(m, ENTL_LIST_TAIL, prev);
    }
    wr32(m, ENTL_LIST_COUNT, entl_rd32(m, ENTL_LIST_COUNT) - 1u);
    if ((u = entl_host(m, obj - 1u, 1)) != NULL)
        *u = 0;
    if ((u = entl_host(m, node - 1u, 1)) != NULL)
        *u = 0;
}

int entl_area_sweep(const struct entl_mem *m, uint32_t rec_va, int full, struct entl_sweep *s)
{
    uint32_t nodes[ENTL_MAX_NODES], objs[ENTL_MAX_NODES];
    uint8_t ref[ENTL_RECORDS] = { 0 };
    int n, i;

    memset(s, 0, sizeof *s);
    if (!rec_va || !entl_ok(m, rec_va, ENTL_BLOCK_SIZE))
        return 1;
    /* It runs every frame: without a marked or retired record only a copy
     * of a free one can be left to remove, which the caller's own walk
     * finds (entl_rec_stale) and asks for with full. Otherwise the 128
     * used bytes are all it reads. */
    if (!full) {
        for (i = 0; i < (int)ENTL_RECORDS && !rec_swept(rec_state(m, rec_va, i)); i++)
            ;
        if (i == (int)ENTL_RECORDS)
            return 1;
    }
    /* A walk short of the count missed objects: one of them may point at a
     * record, so neither unlinking nor freeing is safe on it. */
    n = walk_nodes(m, nodes, objs);
    if ((uint32_t)n != entl_count(m)) {
        s->partial = 1;
        return 0;
    }
    for (i = 0; i < n; i++) {
        int r = entl_rec_index(rec_va, entl_rd32(m, objs[i] + ENTL_OB_PLACEMENT));

        /* Only an object on this list: the header is what the unlink
         * rewrites. */
        if (r >= 0 && rec_copy_gone(rec_state(m, rec_va, r)) &&
            entl_rd32(m, objs[i] + ENTL_OB_LIST) == ENTL_LIST) {
            s->stale += !rec_state(m, rec_va, r);
            unlink_node(m, nodes[i], objs[i]);
            s->unlisted++;
        }
    }
    n = walk_nodes(m, nodes, objs);
    if ((uint32_t)n != entl_count(m)) {
        s->partial = 1;
        return 0;
    }
    for (i = 0; i < n; i++) {
        int r = entl_rec_index(rec_va, entl_rd32(m, objs[i] + ENTL_OB_PLACEMENT));

        if (r >= 0)
            ref[r] = 1;
    }
    for (i = 0; i < (int)ENTL_RECORDS; i++) {
        if (rec_state(m, rec_va, i) != REC_MARKED)
            continue;
        if (ref[i]) {
            s->held++;
        } else {
            /* Retired, not free: a rewind can still bring back a copy
             * that points at it, which the next sweep takes off the list
             * only while no new spawn owns the record. */
            set_used(m, rec_va, i, REC_RETIRED);
            s->freed++;
        }
    }
    return !s->held;
}

uint32_t entl_rec_stale(const struct entl_mem *m, uint32_t rec_va)
{
    uint32_t objs[ENTL_MAX_NODES];
    int n = entl_walk(m, objs, ENTL_MAX_NODES), i;

    for (i = 0; i < n; i++) {
        int r = entl_rec_index(rec_va, entl_rd32(m, objs[i] + ENTL_OB_PLACEMENT));

        if (r >= 0 && !entl_rec_used(m, rec_va, r))
            return objs[i];
    }
    return 0;
}

int entl_rec_listed(const struct entl_mem *m, uint32_t rec_va)
{
    uint32_t objs[ENTL_MAX_NODES];
    int n = entl_walk(m, objs, ENTL_MAX_NODES), i, k = 0;

    for (i = 0; i < n; i++)
        k += entl_rec_index(rec_va, entl_rd32(m, objs[i] + ENTL_OB_PLACEMENT)) >= 0;
    return k;
}

/* ---- spawn ------------------------------------------------------------- */

/* The stage table's record, or 0. */
static uint32_t table_record(const struct entl_mem *m, int32_t stage, int32_t record)
{
    uint32_t tab, recs;

    if (stage < 0 || (uint32_t)stage >= ENTL_STAGES || record < 0)
        return 0;
    tab = entl_rd32(m, ENTL_STAGE_TABLE + 4u * (uint32_t)stage);
    if (!entl_ok(m, tab, 8) || (uint32_t)record >= entl_rd32(m, tab))
        return 0;
    recs = entl_rd32(m, tab + 4) + (uint32_t)record * ENTL_PL_SIZE;
    return entl_ok(m, recs, ENTL_PL_SIZE) ? recs : 0;
}

enum ent_status entl_spawn_check(const struct entl_mem *m, uint32_t rec_va, int leaked,
                                 const struct ent_spawn_spec *s, struct entl_plan *p)
{
    memset(p, 0, sizeof *p);
    p->rec = -1;
    if (leaked)
        return ENT_LEAK;
    /* 1. The game's own respawn gate refuses at any nonzero play mode, and
     * REW undoes a spawn made before or during it (design D7). */
    if (entl_rd32(m, ENTL_PLAY_MODE) != 0)
        return ENT_TIME_CONTROL;
    /* 2. Two players and VS's own play-mode values were never tested. */
    if (entl_rd32(m, ENTL_TEAM_MODE) == ENTL_TEAM_VS)
        return ENT_MODE;
    /* 3. The source. */
    if (s->from.obj) {
        if (!entl_handle_ok(m, s->from) || !entl_ok(m, s->from.placement, ENTL_PL_SIZE))
            return ENT_GONE;
        p->src_obj = s->from.obj;
        p->src_placement = s->from.placement;
    } else {
        p->src_placement = table_record(m, s->stage, s->record);
        if (!p->src_placement)
            return ENT_GONE;
    }
    /* 4. A class whose init the game itself runs from its tables. */
    if (!entl_class_allowed(entl_rd32(m, p->src_placement + ENTL_PL_CLASS)))
        return ENT_CLASS;
    /* 5. Before the call: the game takes a slot and a node, then refuses
     * past 0x21 without giving them back. */
    p->count_before = entl_count(m);
    if (p->count_before + 1u + ENTL_RESERVE > ENTL_POOL_SLOTS)
        return ENT_CAP;
    /* 6. */
    p->rec = entl_rec_free_index(m, rec_va);
    if (p->rec < 0)
        return ENT_RECORDS;
    p->rec_placement = entl_rec_va(rec_va, p->rec);
    return ENT_OK;
}

void entl_spawn_write(const struct entl_mem *m, uint32_t rec_va, const struct entl_plan *p,
                      const struct ent_spawn_spec *s)
{
    uint32_t dst = p->rec_placement;
    int i;
    uint8_t *to = entl_host(m, dst, ENTL_PL_SIZE);
    const uint8_t *from = entl_host(m, p->src_placement, ENTL_PL_SIZE);

    if (!to || !from)
        return;
    memmove(to, from, ENTL_PL_SIZE);
    for (i = 0; i < 3; i++) {
        uint32_t va = dst + ENTL_PL_POS + 4u * (uint32_t)i;

        if (s->has_pos)
            wrf(m, va, s->pos[i]);
        else if (p->src_obj)
            wrf(m, va, entl_rdf(m, p->src_obj + ENTL_OB_POS + 4u * (uint32_t)i));
    }
    if (s->has_rot)
        wrf(m, dst + ENTL_PL_ROT_Y, s->rot_y);
    if (s->respawn == ENT_RESPAWN_NEVER) {
        uint32_t mode = entl_rd32(m, dst + ENTL_PL_MODE);

        wr32(m, dst + ENTL_PL_MODE, (mode & 0x0FFFFFFFu) | (ENTL_MODE_NEVER << 28));
    }
    set_used(m, rec_va, p->rec, 1);
}

enum ent_status entl_spawn_verify(const struct entl_mem *m, const struct entl_plan *p,
                                  struct ent_handle *h)
{
    uint32_t tail = entl_tail(m);

    if (entl_count(m) != p->count_before + 1u || !tail
        || entl_rd32(m, tail + ENTL_OB_PLACEMENT) != p->rec_placement)
        return ENT_LEAK;
    *h = entl_handle(m, tail);
    return ENT_OK;
}

/* ---- kill -------------------------------------------------------------- */

enum ent_status entl_kill_check(const struct entl_mem *m, struct ent_handle h, int any_mode,
                                int32_t *dmg)
{
    uint32_t mode = entl_rd32(m, ENTL_PLAY_MODE);
    int16_t hp;

    *dmg = 0;
    /* A kill under PAUSE or SLOW runs its death through the control and
     * stays dead after it and after a later REW, as in normal play (open
     * question 1, PC proof runs Q1b-pause and Q1b-slow). FF was never
     * taken from a request and REC's playback runs the death twice, so
     * they stay refused with REW and the other modes. */
    if (!any_mode && mode != 0 && mode != ENTL_MODE_PAUSE && mode != ENTL_MODE_SLOW)
        return ENT_TIME_CONTROL;
    if (!entl_handle_ok(m, h))
        return ENT_GONE;
    hp = entl_rd16(m, h.obj + ENTL_OB_HP);
    if (entl_rd32(m, h.obj + ENTL_OB_STATE) == ENTL_STATE_DEAD || hp <= 0)
        return ENT_DEAD;
    *dmg = hp;
    return ENT_OK;
}

int entl_kill_took(const struct entl_mem *m, struct ent_handle h, int16_t hp_before)
{
    int16_t hp;

    if (!entl_handle_ok(m, h))
        return 1;
    hp = entl_rd16(m, h.obj + ENTL_OB_HP);
    return entl_rd32(m, h.obj + ENTL_OB_STATE) == ENTL_STATE_DEAD || hp <= 0 || hp < hp_before;
}

/* ---- class-1 hp -------------------------------------------------------- */

static uint32_t hp_va(uint32_t v)
{
    return ENTL_VARIANTS + v * ENTL_VARIANT_SIZE + ENTL_VARIANT_HP;
}

uint32_t entl_hp_apply(const struct entl_mem *m, struct entl_hp *o, const int16_t *explicit_hp,
                       int scale)
{
    uint32_t v, skipped = 0;

    for (v = 1; v <= ENTL_N_VARIANTS; v++) {
        int16_t game = o->saved[v] ? o->orig[v] : entl_rd16(m, hp_va(v));
        int32_t want = -1;

        if (!entl_ok(m, hp_va(v), 2))
            continue;
        if (!o->saved[v] && (game < 1 || game > 9999)) {
            /* Not the hp short the variant table holds: a different build
             * or a misread. Leave it alone. */
            if (explicit_hp[v - 1] >= 0 || scale > 1)
                skipped |= 1u << v;
            continue;
        }
        if (explicit_hp[v - 1] >= 0)
            want = explicit_hp[v - 1];
        else if (scale > 1)
            want = (int32_t)game * scale > 0x7FFF ? 0x7FFF : (int32_t)game * scale;
        if (want < 0) {
            if (o->saved[v]) {
                uint8_t *h = entl_host(m, hp_va(v), 2);

                if (h)
                    memcpy(h, &o->orig[v], 2);
                o->saved[v] = 0;
            }
            continue;
        }
        if (!o->saved[v]) {
            o->orig[v] = game;
            o->saved[v] = 1;
        }
        {
            int16_t w = (int16_t)want;
            uint8_t *h = entl_host(m, hp_va(v), 2);

            if (h)
                memcpy(h, &w, 2);
        }
    }
    return skipped;
}
