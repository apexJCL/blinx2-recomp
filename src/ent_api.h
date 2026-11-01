/*
 * ent_api.h - BLiNX 2's enemy list for cat's mods: list, read, spawn,
 * kill and class-1 hp overrides, with the guards the entity spikes asked
 * for (openspec change entity-mod-api, design D2-D7).
 *
 * The API is live only while the `entities` mod (entities_mod.c) is on: it
 * owns the hook, the area-setup calls and the record block. Another mod calls these
 * functions and gets ENT_OFF (or -1) while it is off.
 *
 * Threads: reads run on the guest thread (a hook or on_frame) and return -1
 * elsewhere. Spawns and kills may be asked from any thread: they are queued
 * and run in the pre hook of ent_enemy_update_all (sub_0004E700), inside
 * the stage update and before any enemy runs that frame; each queued
 * request ends with exactly one done call, on the guest thread. A spawn's
 * comes in that hook. A kill's comes once the hit shows, a frame or two
 * later: ENT_OK when the enemy died, lost hp or left the list, and
 * ENT_IGNORED when after 4 frames it had not, which is how the game treats
 * a hit on a dormant or idling enemy (design D7).
 *
 * Without mod API v6 in the toolkit every call answers ENT_OFF or -1.
 */
#ifndef CAT_ENT_API_H
#define CAT_ENT_API_H

#include <stdint.h>

/* An enemy: valid while its object is listed and still holds the same
 * placement pointer and id. A respawn in place keeps all three, so a handle
 * survives it; a pool slot reused by another enemy fails it. */
struct ent_handle {
    uint32_t obj, placement;
    int16_t id;
};

/* A host copy of one enemy, filled field by field (objects sit at odd
 * addresses). */
struct ent_info {
    struct ent_handle h;
    uint32_t cls, state, flags;
    int16_t hp, hp_max;
    float pos[3], rot[3];
    uint16_t dead_frames;       /* +0xAC while dead */
    uint8_t dead, spawned;      /* state 0xA; placed by this API */
};

enum ent_status {
    ENT_OK,             /* done, or queued */
    ENT_OFF,            /* the entities mod is off */
    ENT_BUSY,           /* the request ring is full */
    ENT_TIMEOUT,        /* no enemy update ran for 60 frames (no stage, a menu) */
    ENT_TIME_CONTROL,   /* a time control or another play mode is running */
    ENT_CAP,            /* the list would pass 34 */
    ENT_CLASS,          /* a class the API does not spawn, or no such variant */
    ENT_RECORDS,        /* no placement record left this area */
    ENT_GONE,           /* the handle or record names no enemy */
    ENT_DEAD,           /* the enemy is already dead */
    ENT_MODE,           /* VS */
    ENT_LEAK,           /* a spawn went wrong; spawns refused until the next area */
    ENT_CALL,           /* the toolkit refused the guest call; nothing was spawned or hit */
    ENT_IGNORED         /* the game ran the hit but the enemy took none (dormant, idling) */
};

#define ENT_RESPAWN_NEVER 0u    /* the copy never respawns (mode 2) */
#define ENT_RESPAWN_KEEP  1u    /* the source placement's respawn mode */

struct ent_spawn_spec {
    struct ent_handle from;     /* copy this enemy's placement (obj != 0), or */
    int32_t stage, record;      /* record `record` of stage table entry `stage` */
    float pos[3];               /* with has_pos; else the source enemy's */
    uint8_t has_pos;            /* position, or the record's own */
    float rot_y;                /* with has_rot; else the placement's */
    uint8_t has_rot;
    uint8_t respawn;            /* ENT_RESPAWN_NEVER (0, the default) or _KEEP */
};

typedef void (*ent_done_fn)(enum ent_status s, struct ent_handle h, void *user);

/* Up to max listed enemies into out, in list order; the count, or -1 off
 * the guest thread, while the API is off or for a NULL out. Walks at most 64 nodes and stops
 * at a pointer outside guest memory. */
int ent_list(struct ent_info *out, int max);
/* One enemy by handle: 1 filled, 0 gone, -1 off the guest thread, off or a
 * NULL out. */
int ent_read(struct ent_handle h, struct ent_info *out);
/* The list's count, a relaxed read from any thread; -1 while off. */
int ent_count(void);
/* Queue a spawn or a kill: ENT_OK (done follows), else ENT_OFF or ENT_BUSY
 * (ENT_GONE for a NULL spec) at once with no done call. done may be NULL.
 * A kill's done comes once its hit shows: ENT_OK, ENT_IGNORED after four
 * enemy updates without it, ENT_TIMEOUT after 60 frames with no update. */
enum ent_status ent_spawn(const struct ent_spawn_spec *s, ent_done_fn done, void *user);
enum ent_status ent_kill(struct ent_handle h, ent_done_fn done, void *user);
/* Class-1 variant (1..4) hp from the next area setup, clamped to 1..9999;
 * a negative hp gives the game's back. ENT_CLASS for another variant. */
enum ent_status ent_type_hp(uint32_t variant, int16_t hp);

/* Short text for a status ("refused: time control running"). */
const char *ent_status_text(enum ent_status s);

/* ---- for the owner (entities_mod.c) ------------------------------------ */

struct xbox_mod_api;
struct xbox_mod;

/* From the owner's init: registers the hooks and on_frame. 0 when the
 * toolkit has no v6 calls or a hook slot is missing (one log line). */
int ent_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner);
/* The owner's switch: off answers queued requests ENT_OFF and gives the
 * game's class-1 hp back at the next area setup. Idempotent; from the
 * owner's init or its on_enable (the guest thread). */
void ent_api_enable(int on);
/* Class-1 hp times scale (1..10) from the next area setup, for variants
 * without an ent_type_hp override. */
void ent_api_hp_scale(int scale);
/* Guest thread: the API's spawned enemies still listed. */
int ent_api_spawned(void);
/* The live proof only (RECOMP_DEBUG=entities_proof killany, open question
 * 1): kills skip the time-control guard, so a run can see whether a kill
 * under PAUSE, SLOW, FF or REC holds. From the owner's init. */
void ent_api_proof_kill_any(int on);
/* Guest thread: the area setups seen while on, for the live proof's
 * rewarea step (open question 3), which counts from the last one. */
int ent_api_area_setups(void);
/* From recomp_manual.c's stage_area_setup wrapper (sub_000606F0), which a
 * mod hook slot cannot share: post 0 before the stage loads its
 * placements, 1 after; stage_start when the stage start called it (not a
 * retry or a teardown). While the mod is off only the hp written while on
 * go back, once, and a block from an earlier spawn keeps being swept. */
void ent_api_area_setup(int post, int stage_start);

#endif
