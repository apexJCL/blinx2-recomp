/*
 * ent_api.c - the entity API's calls, its request ring and its hook
 * (ent_api.h; openspec change entity-mod-api, design D3-D7).
 *
 * The guest calls happen in the pre hook of ent_enemy_update_all
 * (sub_0004E700): on the guest thread, inside the stage update, before any
 * enemy runs that frame, where the spike called both (run live-2). The
 * toolkit's guest_call saves and restores every guest register around
 * them.
 *
 * stage_area_setup (sub_000606F0) bounds the records' life: before it the
 * class-1 hp go in, ahead of the placements it loads; after it the records
 * in use are marked, and the next enemy update takes their copies off the
 * list and retires them (design D5, D6). That update, not the setup's own
 * return, because a retry restores the checkpoint after the setup and the
 * restore brings the copies back; and every update after it, because the
 * checkpoint frame keeps them, so each later retry or rewind brings them
 * back again. Retired records are freed only at a stage start, which takes
 * a new checkpoint. recomp_manual.c defines that function as the free
 * camera's wrapper, so the wrapper calls ent_api_area_setup instead of a
 * mod hook.
 *
 * Off (the default): the hook is not called, the ring is empty and no
 * record block is ever allocated. The area-setup calls return at once,
 * except to give back class-1 hp written while on, at the first area setup
 * after the switch (design D8). Switched off after a spawn, the block
 * stays: the area setups still mark its records and on_frame sweeps their
 * copies, since a checkpoint can bring them back long after.
 */
#include <stddef.h>
#include <string.h>
#include "ent_api.h"
#include "ent_api_logic.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define ENT_API_LIVE 1
#    endif
#  endif
#endif

static const char *const k_status_text[] = {
    [ENT_OK] = "done",
    [ENT_OFF] = "the entities mod is off",
    [ENT_BUSY] = "too many requests",
    [ENT_TIMEOUT] = "no stage running",
    [ENT_TIME_CONTROL] = "time control running",
    [ENT_CAP] = "34 enemies already",
    [ENT_CLASS] = "an enemy the API does not copy",
    [ENT_RECORDS] = "no records left in this area",
    [ENT_GONE] = "no such enemy",
    [ENT_DEAD] = "already defeated",
    [ENT_MODE] = "not in VS",
    [ENT_LEAK] = "the game refused; spawns off until the next area",
    [ENT_CALL] = "the game could not be called",
    [ENT_IGNORED] = "the enemy ignored the hit",
};

const char *ent_status_text(enum ent_status s)
{
    return (unsigned)s < sizeof k_status_text / sizeof *k_status_text ? k_status_text[s] : "?";
}

#ifdef ENT_API_LIVE

#include <xbox/xboxrecomp.h>     /* g_xbox_total_ram */

#define VA_SPAWN        0x0004EE20u     /* ent_enemy_spawn(placement*), EAX = list */
#define VA_DAMAGE       0x00050800u     /* ent_enemy_damage */
#define VA_UPDATE_ALL   0x0004E700u     /* ent_enemy_update_all */

#define RING            16u
/* A request no enemy update took for this many frames answers ENT_TIMEOUT:
 * no stage runs (a menu, a load), so none will soon. */
#define REQ_TIMEOUT     60u
/* Enemy updates a kill waits for the hit to show. It shows in the next
 * update, under PAUSE and SLOW too (PC proof runs Q1b); a dormant or idling
 * enemy never takes it (runs A4, Q7d). Updates, not frames: a frame
 * without a stage update cannot show it. */
#define KILL_WAIT       4u
/* Kills waiting: each update sends at most RING and answers every kill
 * KILL_WAIT updates old, so KILL_WAIT batches at most. */
#define KILLS           (RING * KILL_WAIT)
/* Frames between two log lines about a held area sweep. */
#define SWEEP_LOG_EVERY 300u

enum { REQ_SPAWN = 1, REQ_KILL };

struct req {
    uint8_t kind;
    uint32_t age;
    struct ent_spawn_spec spec;
    struct ent_handle h;
    ent_done_fn done;
    void *user;
};

static const struct xbox_mod_api *s_api;
static const struct xbox_mod *s_owner;
static int s_on;                        /* written on the guest thread */
static int s_scale = 1;                 /* any thread, relaxed */
static int s_proof_kill_any;            /* entities_proof killany; init only */
static int s_area_setups;               /* guest thread: area setups seen while on */
static int16_t s_hp[ENTL_N_VARIANTS] = { -1, -1, -1, -1 };     /* any thread, relaxed */

/* The ring: any thread pushes, the guest thread takes. */
static volatile int s_lock;
static struct req s_ring[RING];
static unsigned s_n;

/* Guest thread only. */
static struct entl_hp s_hp_state;
static uint32_t s_rec_va;               /* the record block, or 0 */
static int s_alloc_failed, s_leaked, s_stale_logged, s_spawned;
static int s_sweep;                     /* records marked at an area setup */
static int s_stale_pending;             /* on_frame saw a copy of a free record */
static uint32_t s_sweep_frames;         /* enemy updates the sweep has waited */
static uint32_t s_rew_frames;           /* updates a rewind brought a copy back */

/* Kills sent, waiting for the hit to show (guest thread only). */
struct kill_wait {
    struct req r;
    int16_t hp_before;
    uint32_t updates;       /* enemy updates since the hit */
    uint32_t frames;        /* frames since the last enemy update */
};
static struct kill_wait s_kills[KILLS];
static unsigned s_nkills;
static const void *s_guest;             /* &t_marker on the guest thread */
static _Thread_local char t_marker;
static _Thread_local int t_in_hook;

static void lock(void)
{
    while (__atomic_exchange_n(&s_lock, 1, __ATOMIC_ACQUIRE))
        ;
}

static void unlock(void)
{
    __atomic_store_n(&s_lock, 0, __ATOMIC_RELEASE);
}

static struct entl_mem mem(void)
{
    struct entl_mem m;

    m.base = s_api ? (uint8_t *)s_api->mem : NULL;
    m.size = (uint32_t)g_xbox_total_ram;
    m.hi = NULL;
    m.hi_va = m.hi_size = 0;
    /* guest_alloc's block sits in the contiguous window, mapped apart from
     * main RAM at the same offset. A block there proves the window is
     * mapped, so only then are its addresses (our records, and the
     * placements of the enemies spawned from them) read. */
    if (m.base && s_rec_va >= ENTL_CONTIG_BASE) {
        m.hi = m.base + ENTL_CONTIG_BASE;
        m.hi_va = ENTL_CONTIG_BASE;
        m.hi_size = ENTL_CONTIG_SIZE;
    }
    return m;
}

static int on_guest_thread(void)
{
    return t_in_hook || (s_guest && s_guest == (const void *)&t_marker);
}

static int live(void)
{
    return s_api && s_api->mem && __atomic_load_n(&s_on, __ATOMIC_RELAXED);
}

/* ---- requests ---------------------------------------------------------- */

static enum ent_status push(const struct req *r)
{
    enum ent_status st = ENT_OK;

    if (!live())
        return ENT_OFF;
    lock();
    if (s_n >= RING)
        st = ENT_BUSY;
    else
        s_ring[s_n++] = *r;
    unlock();
    return st;
}

/* Takes the whole ring: a done call that asks again lands in the next
 * frame's batch. */
static unsigned take(struct req *out)
{
    unsigned n;

    lock();
    n = s_n;
    memcpy(out, s_ring, n * sizeof *out);
    s_n = 0;
    unlock();
    return n;
}

static void finish(const struct req *r, enum ent_status st, struct ent_handle h)
{
    if (r->done)
        r->done(st, h, r->user);
}

/* Answers every queued request with st (off, or no stage for a while). */
static void drain(enum ent_status st, uint32_t min_age)
{
    struct req batch[RING], keep[RING], busy[RING];
    unsigned n = take(batch), nk = 0, nb = 0, i;
    struct ent_handle none = { 0, 0, 0 };

    for (i = 0; i < n; i++) {
        if (batch[i].age >= min_age)
            finish(&batch[i], st, none);
        else
            keep[nk++] = batch[i];
    }
    if (!nk)
        return;
    lock();
    /* Back in front of anything pushed meanwhile, which is younger; the
     * youngest that no longer fit answer BUSY, so each request still gets
     * exactly one done. */
    if (s_n + nk > RING) {
        nb = s_n + nk - RING;
        memcpy(busy, s_ring + (s_n - nb), nb * sizeof *busy);
        s_n -= nb;
    }
    memmove(s_ring + nk, s_ring, s_n * sizeof *s_ring);
    memcpy(s_ring, keep, nk * sizeof *keep);
    s_n += nk;
    unlock();
    for (i = 0; i < nb; i++)
        finish(&busy[i], ENT_BUSY, none);
}

static void age_requests(void)
{
    unsigned i;

    lock();
    for (i = 0; i < s_n; i++)
        s_ring[i].age++;
    unlock();
}

/* ---- the guest calls --------------------------------------------------- */

static enum ent_status do_spawn(const struct ent_spawn_spec *s, struct ent_handle *h)
{
    struct entl_mem m;
    struct entl_plan p;
    struct xbox_guest_args a;
    enum ent_status st;
    uint32_t arg;

    if (!s_rec_va && !s_alloc_failed) {
        /* Asked at the first spawn, so a mod that is never used never
         * changes the guest's memory map. */
        s_rec_va = s_api->guest_alloc(s_owner, ENTL_BLOCK_SIZE, 16);
        if (!s_rec_va) {
            s_alloc_failed = 1;
            s_api->log(s_owner, "no guest memory for the placement records: spawns refused");
        }
    }
    m = mem();      /* the block's window, now that it exists */
    st = entl_spawn_check(&m, s_rec_va, s_leaked, s, &p);
    if (st != ENT_OK)
        return st;
    entl_spawn_write(&m, s_rec_va, &p, s);
    arg = p.rec_placement;
    memset(&a, 0, sizeof a);
    a.eax = ENTL_LIST;
    a.stack = &arg;
    a.n_stack = 1;
    if (!s_api->guest_call(VA_SPAWN, &a, NULL)) {
        /* guest_call logged why; the game never saw the record. */
        entl_rec_release(&m, s_rec_va, p.rec);
        return ENT_CALL;
    }
    st = entl_spawn_verify(&m, &p, h);
    if (st == ENT_LEAK) {
        s_leaked = 1;
        s_api->log(s_owner,
                   "spawn of class %08X from %08X: count %u -> %u, tail %08X: refused until the"
                   " next area",
                   entl_rd32(&m, p.src_placement), p.src_placement, p.count_before,
                   entl_count(&m), entl_tail(&m));
    }
    return st;
}

static enum ent_status do_kill(struct ent_handle h, int16_t *hp_before)
{
    struct entl_mem m = mem();
    struct xbox_guest_args a;
    uint32_t args[7];
    int32_t dmg;
    float one = 1.0f, zero = 0.0f;
    enum ent_status st = entl_kill_check(&m, h, s_proof_kill_any, &dmg);

    if (st != ENT_OK)
        return st;
    *hp_before = (int16_t)dmg;
    /* The vacuum's hit: (obj, source pos, 1.0f, damage, 0, 0.0f, 0), from
     * player 0's position. */
    args[0] = h.obj;
    args[1] = ENTL_PLAYER0_POS;
    memcpy(&args[2], &one, 4);
    args[3] = (uint32_t)dmg;
    args[4] = 0;
    memcpy(&args[5], &zero, 4);
    args[6] = 0;
    memset(&a, 0, sizeof a);
    a.stack = args;
    a.n_stack = 7;
    return s_api->guest_call(VA_DAMAGE, &a, NULL) ? ENT_OK : ENT_CALL;
}

/* Answers the kills whose hit showed, and after KILL_WAIT enemy updates
 * the ones whose hit never did: the game called the damage but left the
 * enemy as it was, so done must not say it is dead. update: from the
 * update's pre hook, else from on_frame, where REQ_TIMEOUT frames with no
 * update answer ENT_TIMEOUT (the stage ended) and off answers at once. */
static void check_kills(int update)
{
    struct entl_mem m = mem();
    unsigned i, k = 0;

    for (i = 0; i < s_nkills; i++) {
        struct kill_wait *w = &s_kills[i];

        if (update) {
            w->updates++;
            w->frames = 0;
        } else {
            w->frames++;
        }
        if (s_api->mem && entl_kill_took(&m, w->r.h, w->hp_before))
            finish(&w->r, ENT_OK, w->r.h);
        else if (w->updates >= KILL_WAIT || !s_api->mem || !s_on)
            finish(&w->r, ENT_IGNORED, w->r.h);
        else if (w->frames >= REQ_TIMEOUT)
            finish(&w->r, ENT_TIMEOUT, w->r.h);
        else
            s_kills[k++] = *w;
    }
    s_nkills = k;
}

static void sweep(void)
{
    struct entl_mem m = mem();
    struct entl_sweep r;
    int full = s_stale_pending;

    s_stale_pending = 0;
    if (entl_area_sweep(&m, s_rec_va, full, &r)) {
        if (r.stale && !s_stale_logged) {
            /* A restore from before the stage start the record was freed
             * at (open question 3). Once per area: a held REW repeats it. */
            s_api->log(s_owner, "restore: %d copies of freed placement records off the list",
                       r.stale);
            s_stale_logged = 1;
        }
        if (!s_sweep) {
            /* Retired records only: a rewind brought back a copy. A held
             * REW at the ring's oldest frame restores it every frame
             * (run E6: 270 in a row), hence the rate limit. */
            if (r.unlisted > r.stale && s_rew_frames++ % SWEEP_LOG_EVERY == 0)
                s_api->log(s_owner,
                           "rewind: %d copies of retired placement records off the list"
                           " (%u times since the area setup)",
                           r.unlisted - r.stale, s_rew_frames);
            return;
        }
        if (r.unlisted || r.freed || s_leaked)
            s_api->log(s_owner, "area setup: %d copies off the list, %d placement records retired%s",
                       r.unlisted, r.freed, s_leaked ? ", spawns allowed again" : "");
        s_sweep = 0;
        s_leaked = 0;
        s_stale_logged = 0;
        return;
    }
    /* Held: the records stay used (no spawn takes them) and the sweep runs
     * again next frame. */
    if (s_sweep_frames++ % SWEEP_LOG_EVERY == 0)
        s_api->log(s_owner,
                   r.partial ? "area setup: the enemy list walk stops short of its count %u;"
                               " placement records held"
                             : "area setup: %d placement records still in use by a listed enemy;"
                               " held",
                   r.partial ? entl_count(&m) : (uint32_t)r.held);
}

/* ---- hooks ------------------------------------------------------------- */

static void pre_update(struct xbox_mod_call *c, void *user)
{
    struct req batch[RING];
    unsigned n, i;

    (void)c, (void)user;
    if (!s_on || !s_api->mem)
        return;
    t_in_hook++;
    /* The previous update's kills first: their hits show by now. */
    if (s_nkills)
        check_kills(1);
    /* Every update (design D5): a retry or a rewind can bring back a copy
     * of a retired record at any time until the next stage start. Before
     * the requests, so a spawn this update takes a record the sweep would
     * otherwise see as one of the old area's. */
    sweep();
    n = take(batch);
    for (i = 0; i < n; i++) {
        struct ent_handle h = { 0, 0, 0 };
        enum ent_status st;

        if (batch[i].kind == REQ_SPAWN) {
            st = do_spawn(&batch[i].spec, &h);
        } else {
            int16_t hp = 0;

            h = batch[i].h;
            /* KILLS holds every kill in flight (above); the check keeps a
             * sent kill from ever going unanswered if that changes. */
            st = s_nkills < KILLS ? do_kill(h, &hp) : ENT_BUSY;
            if (st == ENT_OK) {
                /* done once the hit shows (check_kills). */
                s_kills[s_nkills].r = batch[i];
                s_kills[s_nkills].hp_before = hp;
                s_kills[s_nkills].updates = 0;
                s_kills[s_nkills].frames = 0;
                s_nkills++;
                continue;
            }
        }
        finish(&batch[i], st, h);
    }
    t_in_hook--;
}

static void pre_area_setup(int on)
{
    struct entl_mem m = mem();
    int16_t hp[ENTL_N_VARIANTS];
    uint32_t i, skipped;

    if (!s_api->mem)
        return;
    if (!on) {
        /* Off writes only to give back what on wrote. */
        for (i = 1; i <= ENTL_N_VARIANTS && !s_hp_state.saved[i]; i++)
            ;
        if (i > ENTL_N_VARIANTS)
            return;
    }
    for (i = 0; i < ENTL_N_VARIANTS; i++)
        hp[i] = on ? __atomic_load_n(&s_hp[i], __ATOMIC_RELAXED) : (int16_t)-1;
    skipped = entl_hp_apply(&m, &s_hp_state, hp,
                            on ? __atomic_load_n(&s_scale, __ATOMIC_RELAXED) : 1);
    if (skipped)
        s_api->log(s_owner, "class-1 variants %#x hold no plausible hp: left alone", skipped);
}

static void post_area_setup(int stage_start)
{
    struct entl_mem m = mem();

    if (!s_rec_va || !s_api->mem) {
        s_leaked = 0;
        return;
    }
    /* Marked now, swept at the next enemy update (design D5): a retry
     * restores its checkpoint after this setup returns. A setup with
     * nothing marked still runs the sweep, for the leak flag and its line.
     * Retired records go free only at a stage start: until then the
     * stage's checkpoint frame holds their copies. */
    entl_rec_age(&m, s_rec_va, stage_start);
    s_sweep = 1;
    s_sweep_frames = 0;
    s_rew_frames = 0;
}

static void on_frame(void *user)
{
    (void)user;
    if (!s_guest)
        s_guest = &t_marker;
    if (s_nkills)
        check_kills(0);
    if (!s_on) {
        drain(ENT_OFF, 0);
    } else {
        age_requests();
        drain(ENT_TIMEOUT, REQ_TIMEOUT);
    }
    if (s_rec_va && s_api->mem) {
        struct entl_mem m = mem();

        s_spawned = entl_rec_listed(&m, s_rec_va);
        /* A copy of a free record: a restore reached back across the stage
         * start that freed it (open question 3). The sweep reads only the
         * used bytes until told to walk. */
        if (entl_rec_stale(&m, s_rec_va))
            s_stale_pending = 1;
        /* Off, the toolkit runs no hook of the mod, so the sweep runs here,
         * after the frame's enemy update: a copy a restore brought back
         * gets that one update first. */
        if (!s_on)
            sweep();
    }
}

/* ---- the public calls -------------------------------------------------- */

int ent_list(struct ent_info *out, int max)
{
    struct entl_mem m;
    uint32_t objs[ENTL_MAX_NODES];
    int n, i;

    if (!live() || !on_guest_thread() || max < 0 || (!out && max))
        return -1;
    m = mem();
    n = entl_walk(&m, objs, max < ENTL_MAX_NODES ? max : ENTL_MAX_NODES);
    for (i = 0; i < n; i++)
        entl_info(&m, objs[i], s_rec_va, &out[i]);
    return n;
}

int ent_read(struct ent_handle h, struct ent_info *out)
{
    struct entl_mem m;

    if (!live() || !on_guest_thread() || !out)
        return -1;
    m = mem();
    if (!entl_handle_ok(&m, h))
        return 0;
    entl_info(&m, h.obj, s_rec_va, out);
    return 1;
}

int ent_count(void)
{
    if (!live())
        return -1;
    return (int)XBOX_MOD_MEM32(s_api, ENTL_LIST_COUNT);
}

enum ent_status ent_spawn(const struct ent_spawn_spec *s, ent_done_fn done, void *user)
{
    struct req r;

    if (!s)
        return ENT_GONE;
    memset(&r, 0, sizeof r);
    r.kind = REQ_SPAWN;
    r.spec = *s;
    r.done = done;
    r.user = user;
    return push(&r);
}

enum ent_status ent_kill(struct ent_handle h, ent_done_fn done, void *user)
{
    struct req r;

    memset(&r, 0, sizeof r);
    r.kind = REQ_KILL;
    r.h = h;
    r.done = done;
    r.user = user;
    return push(&r);
}

enum ent_status ent_type_hp(uint32_t variant, int16_t hp)
{
    if (variant < 1 || variant > ENTL_N_VARIANTS)
        return ENT_CLASS;
    if (!live())
        return ENT_OFF;
    /* 1..9999: hp 0 would make that variant's enemies dead on arrival. */
    if (hp >= 0)
        hp = hp < 1 ? 1 : hp > 9999 ? 9999 : hp;
    __atomic_store_n(&s_hp[variant - 1], hp < 0 ? (int16_t)-1 : hp, __ATOMIC_RELAXED);
    return ENT_OK;
}

int ent_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner)
{
    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc) {
        api->log(owner, "the toolkit's mod API is older than v6 (no guest_call): off");
        return 0;
    }
    s_api = api;
    s_owner = owner;
    if (!api->hook(VA_UPDATE_ALL, pre_update, NULL, 0, NULL)) {
        api->log(owner, "the hook slot 0x0004E700 is missing (game.toml [mods] hook_functions): off");
        s_api = NULL;
        return 0;
    }
    api->on_frame(on_frame, NULL);
    return 1;
}

void ent_api_enable(int on)
{
    int i;

    __atomic_store_n(&s_on, on ? 1 : 0, __ATOMIC_RELAXED);
    if (on) {
        /* Switching on again is the user's way to retry: the leak line
         * stays in the log, and the cap still guards the count. */
        s_leaked = 0;
        return;
    }
    for (i = 0; i < (int)ENTL_N_VARIANTS; i++)
        __atomic_store_n(&s_hp[i], (int16_t)-1, __ATOMIC_RELAXED);
    if (s_api)
        drain(ENT_OFF, 0);
}

void ent_api_hp_scale(int scale)
{
    __atomic_store_n(&s_scale, scale < 1 ? 1 : scale > 10 ? 10 : scale, __ATOMIC_RELAXED);
}

int ent_api_spawned(void)
{
    return s_spawned;
}

void ent_api_proof_kill_any(int on)
{
    s_proof_kill_any = on;
}

int ent_api_area_setups(void)
{
    return s_area_setups;
}

void ent_api_area_setup(int post, int stage_start)
{
    /* The wrapper runs whatever the mod's state, unlike a hook. */
    int on = __atomic_load_n(&s_on, __ATOMIC_RELAXED);

    if (!s_api)
        return;
    if (!post) {
        pre_area_setup(on);
        return;
    }
    if (on)
        s_area_setups++;
    /* Off after a spawn too: the records' copies still need sweeping. */
    if (on || s_rec_va)
        post_area_setup(stage_start);
}

#else /* no mod API v6: every call refuses */

int ent_list(struct ent_info *out, int max)
{
    (void)out, (void)max;
    return -1;
}

int ent_read(struct ent_handle h, struct ent_info *out)
{
    (void)h, (void)out;
    return -1;
}

int ent_count(void)
{
    return -1;
}

enum ent_status ent_spawn(const struct ent_spawn_spec *s, ent_done_fn done, void *user)
{
    (void)s, (void)done, (void)user;
    return ENT_OFF;
}

enum ent_status ent_kill(struct ent_handle h, ent_done_fn done, void *user)
{
    (void)h, (void)done, (void)user;
    return ENT_OFF;
}

enum ent_status ent_type_hp(uint32_t variant, int16_t hp)
{
    (void)variant, (void)hp;
    return ENT_OFF;
}

int ent_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner)
{
    (void)api, (void)owner;
    return 0;
}

void ent_api_enable(int on)
{
    (void)on;
}

void ent_api_hp_scale(int scale)
{
    (void)scale;
}

int ent_api_spawned(void)
{
    return 0;
}

void ent_api_proof_kill_any(int on)
{
    (void)on;
}

int ent_api_area_setups(void)
{
    return 0;
}

void ent_api_area_setup(int post, int stage_start)
{
    (void)post, (void)stage_start;
}

#endif
