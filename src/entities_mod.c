/*
 * entities_mod.c - the entities mod (entities_mod.h; openspec change
 * entity-mod-api, design D8).
 *
 * The mod owns the entity API (ent_api.c): attaching it registers the
 * hook, and its switch is the API's. On top it gives the player three
 * things through the API's public calls only, so they go through every
 * guard another mod gets: a copy of the enemy nearest player 0 beside the
 * player, the nearest live enemy defeated through the game's damage path,
 * and class-1 hp times hp_scale from the next area setup.
 *
 * Threads: the rows and the host actions only set a request flag; the
 * guest thread's on_frame reads the list and asks the API, whose answers
 * come back there too. The Status row reads the count and the last answer
 * from the menu's thread: a stale value only shows for a frame.
 *
 * RECOMP_DEBUG=entities_proof=<steps> drives the same calls on a schedule
 * for the design's live proof and logs the list each frame (proof_*).
 *
 * Off (the default, every golden): the hooks do not run, on_frame returns
 * before reading the guest, and no guest memory is allocated.
 */
#include <stddef.h>
#include "entities_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define ENTITIES_MOD 1
#    endif
#  endif
#endif

#ifdef ENTITIES_MOD

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "enhance_menu.h"
#include "ent_api.h"
#include "ent_api_logic.h"
#include "recomp_env.h"

/* A row's help, where the toolkit has the field (overlay-revamp D5). */
#ifdef ENHANCE_MENU_HELP
#  define ROW_HELP(h) , h
#else
#  define ROW_HELP(h)
#endif

enum { SET_ENABLE, SET_HP_SCALE, SET_N };
enum { CTL_SPAWN, CTL_KILL, CTL_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_ENTITIES", NULL, "Enemy tools",
      "Spawn a copy of the nearest enemy, defeat the nearest enemy and raise"
      " one enemy type's hp, from this page or a bound key. Not in VS; spawns"
      " wait out every time control, defeats work under PAUSE and SLOW.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
    [SET_HP_SCALE] = { "hp_scale", NULL, "RECOMP_ENTITIES_HP_SCALE", NULL, "Enemy hp",
      "Enemies of the game's first type (class 1, all four kinds) get their"
      " hp times this, from the next area or stage loaded.",
      "x", XBOX_SET_INT, ENHANCE_LIVE, 0, 1, 1, 10, 1, NULL },
};

static const struct xbox_mod_control k_ctl[CTL_N] = {
    /* id, label, help, when, kind, defaults, aliases, env */
    [CTL_SPAWN] = { "spawn", "Spawn a copy of the nearest enemy",
      "A copy of the enemy nearest the player appears beside the player. It"
      " does not come back once defeated.",
      "in a stage", XBOX_CTL_ACTION, NULL, NULL, "RECOMP_ENTITIES_SPAWN_KEY" },
    [CTL_KILL] = { "kill", "Defeat the nearest enemy",
      "The nearest live enemy takes its hp in damage, as from the vacuum.",
      "in a stage", XBOX_CTL_ACTION, NULL, NULL, "RECOMP_ENTITIES_KILL_KEY" },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Enemies",
    "Spawn and defeat enemies, enemy hp", NULL, "1",
    k_set, SET_N, k_ctl, CTL_N
};

/* The copy appears this far from player 0 along x and along z, as in the
 * spike (run live-2): close enough to fight, far enough that it does not
 * spawn inside the player. Along x alone, on 1-1's start, the copy stood
 * in state 5 and never came for the player (entity-mod-api proof A2). */
#define SPAWN_OFFSET    40.0f

/* stage_current, and the first checkpoint flag that the proof's play frames
 * count from (as in the spike). */
#define VA_STAGE        0x00B87168u
#define VA_CKPT         0x00AE73FCu
/* The player's time control request and its duration (sub_0008C530). */
#define VA_TC_REQ       0x00ADE76Cu
#define VA_TC_TIMER     0x00AEB818u
#define TC_REW          0x1000u
#define TC_FRAMES       0x12Cu
/* For the proof's log: the mission (sub_000E42D0 sets it), player 0's hp
 * (a short), and the time-record ring (10 frames of 0x16B0C; +0xC regions,
 * +0x10 bytes used; the budget is 0x16800 bytes and 0x20 regions). */
#define VA_MISSION      0x00B871B0u
#define VA_PLAYER0_HP   0x00CD24ACu
#define VA_REC_RING     0x00DDD198u
#define REC_FRAMES      10u
#define REC_FRAME_SIZE  0x16B0Cu

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

static int s_on;                        /* guest thread */
static int s_req_spawn, s_req_kill;     /* any thread sets, the guest thread takes */
static int s_last = -1;                 /* the last answer, or -1; any thread reads */
static int s_last_kill;
static int s_act_spawn = -1, s_act_kill = -1;

/* ---- the proof driver (guest thread) ----------------------------------- */

static FILE *s_out;
static long o_spawn = -1, o_fill = -1, o_kill = -1, o_rew = -1, o_spawnrew = -1;
static long o_tc = -1, o_tcreq = -1, o_rewarea = -1, o_from = -1;
static long o_keep = -1, o_atsrc = -1, o_tcdur = -1, o_setuponly = -1;
static int s_area_setups;
static uint32_t s_frame, s_play, s_area_frame;
static uint32_t s_area_key;             /* stage and mission when play started */
static int s_playing, s_filling, s_fill_wait, s_area_changed;
static struct ent_handle s_proof_h;

static float rdf(uint32_t va)
{
    uint32_t v = XBOX_MOD_MEM32(s_api, va);
    float f;

    memcpy(&f, &v, 4);
    return f;
}

static void player_pos(float p[3])
{
    int i;

    for (i = 0; i < 3; i++)
        p[i] = rdf(ENTL_PLAYER0_POS + 4u * (uint32_t)i);
}

/* The listed enemy nearest player 0 that is alive and, for a copy, of a
 * class the API spawns; -1 when none. */
static int nearest(const struct ent_info *e, int n, int copyable)
{
    float p[3];
    float best = 0;
    int i, k = -1;

    player_pos(p);
    for (i = 0; i < n; i++) {
        float dx = e[i].pos[0] - p[0], dy = e[i].pos[1] - p[1], dz = e[i].pos[2] - p[2];
        float d = dx * dx + dy * dy + dz * dz;

        if (e[i].dead || (copyable && !entl_class_allowed(e[i].cls)))
            continue;
        if (k < 0 || d < best) {
            best = d;
            k = i;
        }
    }
    return k;
}

static void proof_line(const char *fmt, enum ent_status st, struct ent_handle h)
{
    if (s_out)
        fprintf(s_out, "#%s f%u play %u status %s obj %08X placement %08X id %d count %d\n", fmt,
                s_frame, s_play, ent_status_text(st), h.obj, h.placement, h.id, ent_count());
}

static void done(enum ent_status st, struct ent_handle h, void *user)
{
    int kill = user != NULL;

    __atomic_store_n(&s_last, (int)st, __ATOMIC_RELAXED);
    __atomic_store_n(&s_last_kill, kill, __ATOMIC_RELAXED);
    if (st == ENT_OK)
        s_api->toast(&s_mod, kill ? "Enemy defeated" : "Enemy spawned");
    else
        s_api->toast(&s_mod, "%s refused: %s", kill ? "Defeat" : "Spawn", ent_status_text(st));
    s_api->log(&s_mod, "%s: %s (obj %08X)", kill ? "kill" : "spawn", ent_status_text(st), h.obj);
}

static void proof_done(enum ent_status st, struct ent_handle h, void *user)
{
    const char *what = user;

    proof_line(what, st, h);
    if (st == ENT_OK && !strcmp(what, "spawn"))
        s_proof_h = h;
    if (!strcmp(what, "fill")) {
        s_fill_wait = 0;
        if (st != ENT_OK) {
            s_filling = 0;
            s_api->log(&s_mod, "proof: fill stops at %s, count %d", ent_status_text(st),
                       ent_count());
        }
    }
}

/* A copy of the nearest enemy beside player 0; 0 when there is none. The
 * proof's from:<id> copies that enemy instead: the nearest one can be a
 * class that stands still until the player comes near, which shows
 * nothing of a copy that moves and attacks. keep:1 keeps the placement's
 * respawn mode and atsrc:1 spawns at the source enemy's position, to tell
 * apart what a copy that stands still reacts to. */
static int ask_spawn(ent_done_fn fn, void *user)
{
    struct ent_info e[ENTL_MAX_NODES];
    struct ent_spawn_spec s;
    int n = ent_list(e, ENTL_MAX_NODES), k = n > 0 ? nearest(e, n, 1) : -1, i;
    enum ent_status st;

    for (i = 0; o_from >= 0 && i < n; i++)
        if (e[i].h.id == o_from)
            k = i;
    if (k < 0)
        return 0;
    memset(&s, 0, sizeof s);
    s.from = e[k].h;
    s.stage = s.record = -1;
    player_pos(s.pos);
    s.pos[0] += SPAWN_OFFSET;
    s.pos[2] += SPAWN_OFFSET;
    s.has_pos = o_atsrc <= 0;
    s.respawn = o_keep > 0 ? ENT_RESPAWN_KEEP : ENT_RESPAWN_NEVER;
    st = ent_spawn(&s, fn, user);
    if (st != ENT_OK)
        fn(st, s.from, user);
    return 1;
}

static int ask_kill(struct ent_handle h, ent_done_fn fn, void *user)
{
    enum ent_status st;

    if (!h.obj) {
        struct ent_info e[ENTL_MAX_NODES];
        int n = ent_list(e, ENTL_MAX_NODES), k = n > 0 ? nearest(e, n, 0) : -1;

        if (k < 0)
            return 0;
        h = e[k].h;
    }
    st = ent_kill(h, fn, user);
    if (st != ENT_OK)
        fn(st, h, user);
    return 1;
}

static void proof_log(void)
{
    struct ent_info e[ENTL_MAX_NODES];
    int n = ent_list(e, ENTL_MAX_NODES), i;
    float p[3];

    uint32_t ring = XBOX_MOD_MEM32(s_api, VA_REC_RING), used = 0, regions = 0, k;

    /* The fullest frame of the ring: an over-budget region is dropped
     * silently, so the proof's fill reads how close a full list comes. */
    if (ring && ring < 0x04000000u - REC_FRAMES * REC_FRAME_SIZE)
        for (k = 0; k < REC_FRAMES; k++) {
            uint32_t u = XBOX_MOD_MEM32(s_api, ring + k * REC_FRAME_SIZE + 0x10);
            uint32_t c = XBOX_MOD_MEM32(s_api, ring + k * REC_FRAME_SIZE + 0xC);

            used = u > used ? u : used;
            regions = c > regions ? c : regions;
        }
    player_pos(p);
    fprintf(s_out,
            "F %u play %u stage %u mission %u team %u mode %X req %X n %d spawned %d rec %u/%u"
            " P %.1f %.1f %.1f hp %d |",
            s_frame, s_playing ? s_play : 0, XBOX_MOD_MEM32(s_api, VA_STAGE),
            XBOX_MOD_MEM32(s_api, VA_MISSION), XBOX_MOD_MEM32(s_api, ENTL_TEAM_MODE),
            XBOX_MOD_MEM32(s_api, ENTL_PLAY_MODE), XBOX_MOD_MEM32(s_api, VA_TC_REQ),
            ent_count(), ent_api_spawned(), used, regions, (double)p[0], (double)p[1],
            (double)p[2], (int)*(int16_t *)(s_api->mem + VA_PLAYER0_HP));
    for (i = 0; i < n; i++)
        fprintf(s_out, " %d:%X:%d/%d:%.0f,%.0f,%.0f:%X%s", e[i].h.id, e[i].cls, e[i].hp,
                e[i].hp_max, (double)e[i].pos[0], (double)e[i].pos[1], (double)e[i].pos[2],
                e[i].state, e[i].spawned ? "*" : "");
    fputc('\n', s_out);
    if (!(s_frame % 30))
        fflush(s_out);
}

/* A time control request as the player's own use makes it
 * (tc_player_activate): PAUSE 0x100, SLOW 0x200, FF 0x400, REW 0x1000,
 * REC 0x2000. */
static void proof_tc(uint32_t req, uint32_t frames)
{
    XBOX_MOD_MEM32(s_api, VA_TC_REQ) = req;
    XBOX_MOD_MEM32(s_api, VA_TC_TIMER) = frames;
    s_api->log(&s_mod, "proof: time control %#x request for %u frames f%u play %u", req, frames,
               s_frame, s_play);
}

static uint32_t area_key(void)
{
    return XBOX_MOD_MEM32(s_api, VA_STAGE) << 8 | (XBOX_MOD_MEM32(s_api, VA_MISSION) & 0xFF);
}

/* A spawnrew asks for its spawn this long after its REW request, when the
 * stage update has taken the request and the rewind runs. */
#define SPAWNREW_DELAY  30

static void proof_frame(void)
{
    s_frame++;
    if (!s_playing && XBOX_MOD_MEM32(s_api, VA_CKPT) == 1 && ent_count() > 0) {
        s_playing = 1;
        s_play = 0;
        s_area_key = area_key();
        s_area_setups = ent_api_area_setups();
        s_api->log(&s_mod, "proof: play starts f%u stage %u enemies %d", s_frame,
                   XBOX_MOD_MEM32(s_api, VA_STAGE), ent_count());
    }
    if (s_playing && !s_area_changed &&
        ((o_setuponly <= 0 && area_key() != s_area_key) ||
         ent_api_area_setups() - s_area_setups >= (o_setuponly > 1 ? o_setuponly : 1))) {
        /* The stage or mission moved on, or an area setup ran (a retry
         * keeps both): rewarea counts from here. setuponly:1 waits for the
         * area setup, since @stage1-2 switches mission without one before
         * its retry; setuponly:n for the nth, a later retry from the same
         * checkpoint. */
        s_area_changed = 1;
        s_area_frame = s_frame;
        s_api->log(&s_mod, "proof: area change f%u play %u: stage %u mission %u, area setups %d",
                   s_frame, s_play, XBOX_MOD_MEM32(s_api, VA_STAGE),
                   XBOX_MOD_MEM32(s_api, VA_MISSION), ent_api_area_setups());
    }
    if (s_area_changed && o_rewarea >= 0 && s_frame == s_area_frame + (uint32_t)o_rewarea)
        proof_tc(TC_REW, TC_FRAMES);
    if (s_playing) {
        long f = (long)s_play;

        if (f == o_spawn && !ask_spawn(proof_done, "spawn"))
            s_api->log(&s_mod, "proof: no enemy to copy at play %u", s_play);
        if (f == o_fill)
            s_filling = 1;
        if (s_filling && !s_fill_wait) {
            s_fill_wait = 1;
            if (!ask_spawn(proof_done, "fill"))
                s_filling = s_fill_wait = 0;
        }
        if (f == o_kill && !ask_kill(s_proof_h, proof_done, "kill"))
            s_api->log(&s_mod, "proof: no enemy to defeat at play %u", s_play);
        if (f == o_rew || f == o_spawnrew)
            proof_tc(TC_REW, TC_FRAMES);
        if (f == o_tc)
            proof_tc(o_tcreq >= 0 ? (uint32_t)o_tcreq : 0x100u,
                     o_tcdur > 0 ? (uint32_t)o_tcdur : TC_FRAMES);
        if (o_spawnrew >= 0 && f == o_spawnrew + SPAWNREW_DELAY)
            ask_spawn(proof_done, "spawnrew");
        s_play++;
    }
    if (s_out)
        proof_log();
}

static long opt(const char *v, const char *name)
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
    return -1;
}

/* RECOMP_DEBUG splits on commas, so the steps are joined by '+'. */
static void proof_init(const char *v)
{
    char path[512] = "entities_proof.tsv";
    const char *o = strstr(v, "out:");

    if (o) {
        size_t l = strcspn(o + 4, "+");

        if (l >= sizeof path)
            l = sizeof path - 1;
        memcpy(path, o + 4, l);
        path[l] = 0;
    }
    o_spawn = opt(v, "spawn");
    o_fill = opt(v, "fill");
    o_kill = opt(v, "kill");
    o_rew = opt(v, "rew");
    o_spawnrew = opt(v, "spawnrew");
    o_tc = opt(v, "tc");
    o_tcreq = opt(v, "tcreq");
    o_rewarea = opt(v, "rewarea");
    o_from = opt(v, "from");
    o_keep = opt(v, "keep");
    o_atsrc = opt(v, "atsrc");
    o_tcdur = opt(v, "tcdur");
    o_setuponly = opt(v, "setuponly");
    if (opt(v, "killany") > 0) {
        ent_api_proof_kill_any(1);
        s_api->log(&s_mod, "proof: kills skip the time-control guard");
    }
    s_out = fopen(path, "w");
    if (!s_out)
        s_api->log(&s_mod, "proof: cannot write %s", path);
    s_api->log(&s_mod,
               "proof: log %s, spawn %ld, fill %ld, kill %ld, rew %ld, spawnrew %ld, tc %ld (%#lx),"
               " rewarea %ld, from %ld, keep %ld, atsrc %ld, tcdur %ld, setuponly %ld",
               path, o_spawn, o_fill, o_kill, o_rew, o_spawnrew, o_tc, o_tcreq, o_rewarea, o_from,
               o_keep, o_atsrc, o_tcdur, o_setuponly);
}

/* ---- the mod ----------------------------------------------------------- */

static void on_frame(void *user)
{
    int spawn, kill;

    (void)user;
    spawn = __atomic_exchange_n(&s_req_spawn, 0, __ATOMIC_ACQ_REL);
    kill = __atomic_exchange_n(&s_req_kill, 0, __ATOMIC_ACQ_REL);
    if (s_act_spawn >= 0 && s_api->action_pressed(s_act_spawn))
        spawn = 1;
    if (s_act_kill >= 0 && s_api->action_pressed(s_act_kill))
        kill = 1;
    if (!s_on || !s_api->mem) {
        if (spawn || kill)
            s_api->toast(&s_mod, "Enemies: turn the mod on first");
        return;
    }
    if (spawn && !ask_spawn(done, NULL))
        s_api->toast(&s_mod, "Spawn: no enemy nearby to copy");
    if (kill && !ask_kill((struct ent_handle){ 0, 0, 0 }, done, (void *)1))
        s_api->toast(&s_mod, "Defeat: no live enemy");
    if (o_spawn >= 0 || o_fill >= 0 || o_kill >= 0 || o_rew >= 0 || o_spawnrew >= 0 || o_tc >= 0 ||
        o_rewarea >= 0 || s_out)
        proof_frame();
}

static void on_enable(int on, void *user)
{
    (void)user;
    ent_api_enable(on);
    if (on == s_on)
        return;
    s_on = on;
    s_api->log(&s_mod, "%s", on ? "on" : "off");
}

static void on_setting(uint32_t idx, double value, void *user)
{
    (void)user;
    if (idx == SET_HP_SCALE) {
        ent_api_hp_scale((int)value);
        s_api->log(&s_mod, "hp_scale %d from the next area", (int)value);
    }
}

/* ---- the rows on the mod's page (menu thread) -------------------------- */

static void spawn_set(const struct enhance_item *it, const char *value)
{
    (void)it, (void)value;
    __atomic_store_n(&s_req_spawn, 1, __ATOMIC_RELEASE);
}

static void kill_set(const struct enhance_item *it, const char *value)
{
    (void)it, (void)value;
    __atomic_store_n(&s_req_kill, 1, __ATOMIC_RELEASE);
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    int count, last;

    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0) {
        snprintf(buf, n, "turn the mod on first");
        return buf;
    }
    count = ent_count();
    if (count < 0 || !s_api->mem) {
        snprintf(buf, n, "the game has not started");
        return buf;
    }
    last = __atomic_load_n(&s_last, __ATOMIC_RELAXED);
    if (last < 0)
        snprintf(buf, n, "%d of %u enemies, %d spawned", count, ENTL_POOL_SLOTS,
                 ent_api_spawned());
    else
        snprintf(buf, n, "%d of %u enemies, %d spawned; last %s: %s", count, ENTL_POOL_SLOTS,
                 ent_api_spawned(), __atomic_load_n(&s_last_kill, __ATOMIC_RELAXED) ? "defeat" : "spawn",
                 last == ENT_OK ? "done" : ent_status_text((enum ent_status)last));
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.entities.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL ROW_HELP("The enemies in the stage, and whether the actions can run")
};

static const struct enhance_item k_spawn_row = {
    "mods.entities.spawn_now", "Spawn a copy of the nearest enemy", NULL, ENHANCE_ITEM_ACTION,
    NULL, 0, 0, 0, "in a stage", spawn_set, NULL, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL ROW_HELP("Adds one more of the enemy closest to Blinx")
};

static const struct enhance_item k_kill_row = {
    "mods.entities.kill_now", "Defeat the nearest enemy", NULL, ENHANCE_ITEM_ACTION,
    NULL, 0, 0, 0, "in a stage", kill_set, NULL, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL ROW_HELP("Defeats the enemy closest to Blinx, as a hit would")
};

static int init(const struct xbox_mod_api *api)
{
    const char *proof = recomp_env(RENV_ENTITIES_PROOF);

    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc)
        return 1;   /* no v6 guest calls: the API stays off */
    s_api = api;
    /* First: the API's hooks and on_frame, so its frame work (the guest
     * thread's mark, the request timeouts) runs before this mod asks. */
    if (!ent_api_attach(api, &s_mod))
        return 1;
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    ent_api_enable(s_on);
    ent_api_hp_scale((int)api->setting(&k_desc, SET_HP_SCALE));
    s_act_spawn = api->control_action(&k_desc, CTL_SPAWN);
    s_act_kill = api->control_action(&k_desc, CTL_KILL);
    /* The actions fire through the actions hook, which the menu arms when
     * it is on; with RECOMP_MENU=0 the mod's switch arms it. */
    api->actions_arm("mods.entities.enable");
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->on_setting(&k_desc, on_setting, NULL);
    api->menu_add(&k_status_row);
    api->menu_add(&k_spawn_row);
    api->menu_add(&k_kill_row);
    if (proof)
        proof_init(proof);
    if (s_on)
        api->log(&s_mod, "on: hp_scale %d", (int)api->setting(&k_desc, SET_HP_SCALE));
    return 0;
}

static const struct xbox_mod s_mod = { "entities", init, NULL, &k_desc,
                                       XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK };

const void *entities_mod(void)
{
    return &s_mod;
}

#else /* no mod API v6: stock */

const void *entities_mod(void)
{
    return NULL;
}

#endif
