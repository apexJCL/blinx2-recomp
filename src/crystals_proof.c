/*
 * crystals_proof.c - the crystals mod's live proof (crystals_internal.h;
 * openspec change crystals-rewrite, D6). Debug tier only:
 * RECOMP_DEBUG=crystals_proof=<steps> spawns crystals at player 1 on a
 * schedule, through the game's own ent_item_spawn so the game's own pickup
 * takes them, can zero player 1's hp or make a REW request, and logs the
 * record each time it changes. It runs with the mod on or off (on_frame
 * calls it either way), so a run with the mod off logs the stock counts.
 */
#include "crystals_internal.h"

#ifdef CRYSTALS_MOD

#include <stdlib.h>
#include <string.h>
#include "crystals_logic.h"

FILE *cry_proof_out;

#define VA_CKPT         0x00AE73FCu     /* stage_checkpoint_flag */
#define VA_STAGE        0x00B87168u
#define VA_MISSION      0x00B871B0u
#define VA_PLAY_MODE    0x00AE46ECu
#define VA_TC_REQ       0x00ADE76Cu
#define VA_TC_TIMER     0x00AEB818u
#define TC_REW          0x1000u
#define TC_FRAMES       0x12Cu
#define VA_ITEM_SPAWN   0x000794D0u
#define PLAYER_POS      0xECu
#define PLAYER_GOLD     0xDCu           /* int16 */
#define PLAYER_HP       0x6Cu           /* int16, ent_player_hp */
#define REC_CAP         0xC6u
#define REC_SEL         0x5ACu

static const struct xbox_mod *s_mod;
static uint32_t s_frame, s_play, s_seg_play, s_seg_mission;
static int s_playing, s_spawned, s_seg_first;
static long o_at = 60, o_every = 30, o_dup = -1, o_rew = -1, o_kill = -1;
static char o_seq[160];
static uint8_t s_last[CRY_SPAN + 0x30 + 8];
static uint32_t s_last_misc[5];

static inline uint8_t rd8(uint32_t va) { return *(volatile uint8_t *)(cry_api->mem + va); }
static inline int16_t rd16s(uint32_t va) { return *(volatile int16_t *)(cry_api->mem + va); }
static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(cry_api, va); }

static uint32_t p1_record(void)
{
    return CRY_RECORD + (uint32_t)(rd8(CRY_VA_PLAYERS) / 4) * CRY_RECORD_SIZE;
}

static void log_row(const char *why)
{
    const struct cry_stats *h = &cry_stats;
    uint32_t p = CRY_VA_PLAYERS, rec = p1_record();
    int ch = (int)(int8_t)rd8(p + CRY_PLAYER_CHAR), i, id;
    const uint8_t *s = (const uint8_t *)(cry_api->mem + rec + CRY_SPAN_OFF);

    if (ch < 0 || ch >= CRY_CHARS)
        ch = 0;
    fprintf(cry_proof_out, "F %u play %u %s stage %u mission %u team_mode %u mode %X req %X hp %d char %d row",
            s_frame, s_playing ? s_play : 0, why, rd32(VA_STAGE), rd32(VA_MISSION),
            rd32(CRY_VA_TEAM_MODE), rd32(VA_PLAY_MODE), rd32(VA_TC_REQ), rd16s(p + PLAYER_HP), ch);
    for (i = 0; i < CRY_COLOURS; i++)
        fprintf(cry_proof_out, " %u", s[ch * CRY_COLOURS + i]);
    fprintf(cry_proof_out, " | held(id1..6)");
    for (id = 1; id <= 6; id++)
        fprintf(cry_proof_out, " %u", rd8(rec + CRY_REC_HELD + (uint32_t)ch * 8 + (uint32_t)id));
    fprintf(cry_proof_out, " | cap");
    for (id = 1; id <= 6; id++)
        fprintf(cry_proof_out, " %u", rd8(rec + REC_CAP + (uint32_t)ch * 8 + (uint32_t)id));
    fprintf(cry_proof_out,
            " | hud slots %u (j %X n %u) pips %u rows %u hearts %u rejected %u row y %.1f size %.1f x %.1f..%.1f",
            h->slots, h->js, h->n, h->pips, h->rows, h->hearts, h->rejected, h->cy, h->size, h->x0, h->x1);
    fprintf(cry_proof_out, " | sel %d cursor %d | gold %d sets %d paid %d\n", (int)rd32(rec + REC_SEL),
            (int)rd32(rec + REC_SEL - 4), rd16s(p + PLAYER_GOLD),
            __atomic_load_n(&h->sets, __ATOMIC_RELAXED), __atomic_load_n(&h->gold, __ATOMIC_RELAXED));
}

static uint32_t collect(uint32_t item)
{
    uint32_t args[2] = { item, 1 }, ret = 0;
    struct xbox_guest_args a = { CRY_VA_PLAYERS, 0, 0, args, 2 };

    cry_api->guest_call(CRY_VA_COLLECT, &a, &ret);
    return ret;
}

static void spawn(int k)
{
    uint32_t args[4], slot = 0, block = cry_block();
    struct xbox_guest_args a = { 0, 0, 0, args, 4 };

    if (!block)
        return;
    memcpy((void *)(cry_api->mem + block + CRY_BLOCK_POS),
           (void *)(cry_api->mem + CRY_VA_PLAYERS + PLAYER_POS), 12);
    args[0] = block + CRY_BLOCK_POS;
    args[1] = 0;
    args[2] = CRY_TYPE0 + (uint32_t)k;
    args[3] = 0;
    cry_api->guest_call(VA_ITEM_SPAWN, &a, &slot);
    fprintf(cry_proof_out, "#spawn play %u n %d k %d type 0x%X slot %08X\n", s_play, s_spawned, k,
            CRY_TYPE0 + (unsigned)k, slot);
    /* dup:<n>: the n-th crystal goes through the pickup twice at once, as
     * the player's touch does (free 1); only the first may count. */
    if (s_spawned == o_dup && slot && slot < CRY_GUEST_TOP) {
        uint32_t r1 = collect(slot), r2 = collect(slot);

        fprintf(cry_proof_out, "#dup slot %08X first %u second %u\n", slot, r1, r2);
    }
}

/* One step of the schedule: seq's next spawn, a REW request, a kill. */
static void step(void)
{
    size_t n = strlen(o_seq);

    /* '|' holds the rest of seq until the mission changes; its spawns
     * then count at and every from that change. */
    if (s_spawned < (int)n && o_seq[s_spawned] == '|') {
        if (rd32(VA_MISSION) != s_seg_mission) {
            s_seg_mission = rd32(VA_MISSION);
            s_seg_play = s_play;
            s_seg_first = ++s_spawned;
            fprintf(cry_proof_out, "#segment play %u mission %u\n", s_play, s_seg_mission);
        }
    } else if (s_spawned < (int)n &&
               (long)(s_play - s_seg_play) == o_at + (s_spawned - s_seg_first) * o_every) {
        char d = o_seq[s_spawned];

        if (d >= '0' && d <= '5')
            spawn(d - '0');
        s_spawned++;
    }
    if ((long)s_play == o_rew) {
        XBOX_MOD_MEM32(cry_api, VA_TC_REQ) = TC_REW;
        XBOX_MOD_MEM32(cry_api, VA_TC_TIMER) = TC_FRAMES;
        fprintf(cry_proof_out, "#rew play %u\n", s_play);
    }
    /* kill:f: player 1's hp to 0, so the game's own death and retry run
     * over a row in progress. */
    if ((long)s_play == o_kill) {
        *(volatile int16_t *)(cry_api->mem + CRY_VA_PLAYERS + PLAYER_HP) = 0;
        fprintf(cry_proof_out, "#kill play %u\n", s_play);
    }
}

void cry_proof_frame(void)
{
    uint32_t rec = p1_record();
    uint32_t misc[5] = { rd32(VA_STAGE), rd32(VA_MISSION), rd32(CRY_VA_TEAM_MODE),
                         (uint32_t)rd16s(CRY_VA_PLAYERS + PLAYER_GOLD),
                         (uint32_t)rd16s(CRY_VA_PLAYERS + PLAYER_HP) };
    uint8_t now[sizeof s_last];
    int changed;

    s_frame++;
    /* A Sweepers stage starts play at its first checkpoint; VS and Tom
     * Tom have none, so their play starts with the mission. */
    if (!s_playing && (rd32(VA_CKPT) == 1 || (rd32(CRY_VA_TEAM_MODE) && rd32(VA_MISSION)))) {
        s_playing = 1;
        s_play = 0;
        s_seg_mission = rd32(VA_MISSION);
        cry_api->log(s_mod, "proof: play starts f%u stage %u", s_frame, rd32(VA_STAGE));
    }
    if (s_playing) {
        step();
        s_play++;
    }
    memcpy(now, (void *)(cry_api->mem + rec + CRY_SPAN_OFF), CRY_SPAN);
    memcpy(now + CRY_SPAN, (void *)(cry_api->mem + rec + CRY_REC_HELD), 0x30);
    memcpy(now + CRY_SPAN + 0x30, (void *)(cry_api->mem + rec + REC_SEL - 4), 8);
    changed = memcmp(now, s_last, sizeof now) || memcmp(misc, s_last_misc, sizeof misc);
    if (changed || !(s_frame % 300)) {
        log_row(changed ? "chg" : "tick");
        memcpy(s_last, now, sizeof now);
        memcpy(s_last_misc, misc, sizeof misc);
        fflush(cry_proof_out);
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
void cry_proof_init(const struct xbox_mod *m, const char *v)
{
    char path[512] = "crystals_proof.tsv";

    s_mod = m;
    str_opt(v, "out:", path, sizeof path);
    str_opt(v, "seq:", o_seq, sizeof o_seq);
    o_at = opt(v, "at", o_at);
    o_every = opt(v, "every", o_every);
    o_dup = opt(v, "dup", o_dup);
    o_rew = opt(v, "rew", o_rew);
    o_kill = opt(v, "kill", o_kill);
    cry_proof_out = fopen(path, "w");
    if (!cry_proof_out)
        cry_api->log(m, "proof: cannot write %s", path);
    cry_api->log(m, "proof: log %s, seq %s, at %ld, every %ld, dup %ld, rew %ld, kill %ld", path,
                 o_seq, o_at, o_every, o_dup, o_rew, o_kill);
}

#else

/* No mod API v6: nothing to prove. ISO C needs a declaration here. */
typedef int cry_proof_unused;

#endif
