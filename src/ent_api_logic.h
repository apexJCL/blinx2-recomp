/*
 * ent_api_logic.h - the entity API's guest layouts and its pure rules
 * (ent_api.c; openspec change entity-mod-api), over a view of guest memory
 * so scripts/test_entities.py can drive them on a fake one.
 *
 * Nothing here calls the game: ent_api.c runs sub_0004EE20 and sub_00050800
 * between the check, the write and the verify below.
 */
#ifndef CAT_ENT_API_LOGIC_H
#define CAT_ENT_API_LOGIC_H

#include <stdint.h>
#include "ent_api.h"

/* ent_enemy_list: +0 head and +4 tail of {prev, next, obj} nodes, +0x14
 * count. Nodes and objects are pool slots, each after its used byte. */
#define ENTL_LIST           0x00AF0E88u
#define ENTL_LIST_TAIL      0x00AF0E8Cu
#define ENTL_LIST_COUNT     0x00AF0E9Cu
#define ENTL_POOL_SLOTS     34u
/* Slots the cap keeps free for the game's own mid-stage spawns that do not
 * check the count first. None does: the loader runs on a list just reset
 * at area setup, the class 9 nest checks count < 0x22 before its spawn,
 * and the spawner class (0x14), which does not, is off the allowlist
 * (config/symbols.toml, the tracker item audit). */
#define ENTL_RESERVE        0u
#define ENTL_MAX_NODES      64

#define ENTL_PLAY_MODE      0x00AE46ECu     /* stage_play_mode: 0 normal play */
#define ENTL_MODE_PAUSE     0x100u          /* the PAUSE and SLOW time controls */
#define ENTL_MODE_SLOW      0x200u
#define ENTL_TEAM_MODE      0x00B21CB4u     /* stage_team_mode */
#define ENTL_TEAM_VS        3u
#define ENTL_STAGE_TABLE    0x004921E8u     /* [stage] -> {count, records*} */
#define ENTL_STAGES         60u
#define ENTL_PLAYER0_POS    (0x00CD2440u + 0xECu)
/* stage_area_setup's return address from the stage start (the call at
 * 0x63248 in sub_00062FB0). Its other callers are the retry (0x7533A) and
 * the teardowns before a menu (0xEB0D4, 0x20F504). */
#define ENTL_SETUP_STAGE_START 0x0006324Du

/* ent_placement: 0x5C bytes. */
#define ENTL_PL_SIZE        0x5Cu
#define ENTL_PL_CLASS       0x00u
#define ENTL_PL_POS         0x04u
#define ENTL_PL_ROT_Y       0x18u   /* rot (3 floats) at +0x14 */
#define ENTL_PL_MODE        0x54u   /* top nibble respawn mode, low bits colours */
#define ENTL_MODE_NEVER     2u

/* ent_enemy. */
#define ENTL_OB_CLASS       0x00u
#define ENTL_OB_STATE       0x04u
#define ENTL_OB_PLACEMENT   0x10u
#define ENTL_OB_FLAGS       0x18u
#define ENTL_OB_HP          0x28u
#define ENTL_OB_HP_MAX      0x2Au
#define ENTL_OB_ID          0x2Cu
#define ENTL_OB_POS         0x48u
#define ENTL_OB_ROT         0x6Cu
#define ENTL_OB_LIST        0x78u   /* the list header the object is on */
#define ENTL_OB_DEAD_FRAMES 0xACu
#define ENTL_STATE_DEAD     0xAu

/* ent_class1_variants: 0x20 each, hp short at +0xC. Variants 1..4 (class
 * byte 1, plus 2 when class byte 3 is set); index 0 and 5 on are code
 * pointers. */
#define ENTL_VARIANTS       0x004AFCD8u
#define ENTL_VARIANT_SIZE   0x20u
#define ENTL_VARIANT_HP     0x0Cu
#define ENTL_N_VARIANTS     4u

/* The record block (guest_alloc): the records, then a used byte each. */
#define ENTL_RECORDS        128u
#define ENTL_BLOCK_SIZE     (ENTL_RECORDS * ENTL_PL_SIZE + ENTL_RECORDS)

/* The contiguous window (the toolkit's kernel.h XBOX_CONTIG_BASE and
 * XBOX_CONTIG_SIZE, asserted equal in recomp_manual.c): mapped apart from
 * main RAM, far above it, and where guest_alloc's block comes from. */
#define ENTL_CONTIG_BASE    0x80000000u
#define ENTL_CONTIG_SIZE    (64u * 1024u * 1024u)

/* Guest memory as the host sees it: guest va is base + va, valid below
 * size; and, with hi, a second window [hi_va, hi_va + hi_size) at host
 * hi + (va - hi_va). In the game hi is base + hi_va (the contiguous window
 * is mapped at the same offset); a test gives it its own buffer. */
struct entl_mem {
    uint8_t *base;
    uint32_t size;
    uint8_t *hi;
    uint32_t hi_va, hi_size;
};

int entl_ok(const struct entl_mem *m, uint32_t va, uint32_t n);
/* The host address of n bytes at va, or NULL outside both windows. */
uint8_t *entl_host(const struct entl_mem *m, uint32_t va, uint32_t n);
uint32_t entl_rd32(const struct entl_mem *m, uint32_t va);   /* 0 outside */
int16_t entl_rd16(const struct entl_mem *m, uint32_t va);
float entl_rdf(const struct entl_mem *m, uint32_t va);

/* ---- the list ---------------------------------------------------------- */

/* The listed objects in order, at most max and ENTL_MAX_NODES; stops at a
 * node or object outside guest memory. */
int entl_walk(const struct entl_mem *m, uint32_t *objs, int max);
/* The last listed object (where sub_0004EE20 appends), or 0. */
uint32_t entl_tail(const struct entl_mem *m);
uint32_t entl_count(const struct entl_mem *m);
struct ent_handle entl_handle(const struct entl_mem *m, uint32_t obj);
/* 1 while h's object is listed with h's placement and id. */
int entl_handle_ok(const struct entl_mem *m, struct ent_handle h);
/* rec_va: the record block, or 0. */
void entl_info(const struct entl_mem *m, uint32_t obj, uint32_t rec_va, struct ent_info *o);

/* 1 for a class (& 0xFF) the game's own stage tables spawn and whose init
 * spawns nothing unchecked. */
int entl_class_allowed(uint32_t cls);

/* ---- records ----------------------------------------------------------- */

uint32_t entl_rec_va(uint32_t rec_va, int i);
/* The record index placement points at, or -1. */
int entl_rec_index(uint32_t rec_va, uint32_t placement);
int entl_rec_used(const struct entl_mem *m, uint32_t rec_va, int i);
/* Gives record i back: the spawn that took it never reached the game. */
void entl_rec_release(const struct entl_mem *m, uint32_t rec_va, int i);
/* The first record never used this area, or -1 (records are not reused
 * within an area: a rewind may bring back an object that points at one). */
int entl_rec_free_index(const struct entl_mem *m, uint32_t rec_va);
/* Area setup: marks every used record as spawned before it (used byte 2,
 * design D5), and at a stage start (not a retry) frees the retired ones
 * (3); the count marked. entl_area_sweep then removes their copies and
 * retires them. */
int entl_rec_age(const struct entl_mem *m, uint32_t rec_va, int stage_start);

struct entl_sweep {
    int unlisted;       /* copies taken off the list */
    int stale;          /* of them, copies of a free record */
    int freed;          /* marked records retired: free at the next area setup */
    int held;           /* marked records a listed object still points at */
    int partial;        /* the walk did not reach the list's count: nothing done */
};

/* Every enemy update (design D5). A listed copy of a record not in use
 * (marked, retired or free) came back with a retry's checkpoint restore
 * or a later rewind, after the teardown had already run its destructor:
 * it is taken off the list as sub_0004EDC0 does, and its pool slot and
 * node marked free, nothing else run again. Then every marked record no
 * listed object points at is retired. Both need a walk that reaches the
 * list's count; a short one does nothing. Unless full, a block with no
 * marked or retired record costs only its used bytes (no walk). 1 when no
 * marked record is left, 0 to try again next frame. */
int entl_area_sweep(const struct entl_mem *m, uint32_t rec_va, int full, struct entl_sweep *s);
/* A listed object that points at a free record (a restore from before a
 * stage start), or 0: the sweep's cue to walk. */
uint32_t entl_rec_stale(const struct entl_mem *m, uint32_t rec_va);
/* Listed objects that point into the block. */
int entl_rec_listed(const struct entl_mem *m, uint32_t rec_va);

/* ---- spawn (design D4) ------------------------------------------------- */

struct entl_plan {
    uint32_t src_placement;     /* the record copied */
    uint32_t src_obj;           /* the enemy copied, or 0 */
    int rec;                    /* the record taken */
    uint32_t rec_placement;     /* its guest va */
    uint32_t count_before;
};

/* Steps 1-6: play mode, VS, source, class, cap, record. leaked: a spawn
 * leaked this area (ENT_LEAK before anything else). */
enum ent_status entl_spawn_check(const struct entl_mem *m, uint32_t rec_va, int leaked,
                                 const struct ent_spawn_spec *s, struct entl_plan *p);
/* Step 7's writes: the record filled and marked used. */
void entl_spawn_write(const struct entl_mem *m, uint32_t rec_va, const struct entl_plan *p,
                      const struct ent_spawn_spec *s);
/* Step 8: ENT_OK with *h when the count grew by one and the tail points at
 * the record, else ENT_LEAK. */
enum ent_status entl_spawn_verify(const struct entl_mem *m, const struct entl_plan *p,
                                  struct ent_handle *h);

/* ---- kill (design D7) -------------------------------------------------- */

/* ENT_OK with the damage that empties the hp in *dmg, or the refusal.
 * any_mode skips the time-control guard: the live proof only (open
 * question 1), never a mod's kill. */
enum ent_status entl_kill_check(const struct entl_mem *m, struct ent_handle h, int any_mode,
                                int32_t *dmg);
/* After the hit: 1 once the game took it (the enemy gone from the list,
 * dead, or below hp_before), else 0. The hit shows in the next frame's
 * enemy update; a dormant or idling enemy never takes it. */
int entl_kill_took(const struct entl_mem *m, struct ent_handle h, int16_t hp_before);

/* ---- class-1 hp (design D6) -------------------------------------------- */

struct entl_hp {
    int16_t orig[ENTL_N_VARIANTS + 1];  /* the game's, saved at the first write */
    uint8_t saved[ENTL_N_VARIANTS + 1];
};

/* At area setup, before the placements load: for each variant, explicit
 * hp (>= 0), else the game's hp times scale (> 1), else the game's back if
 * it was changed. A variant whose game hp is not plausible (1..9999) is
 * left alone. Returns a mask of the variants left so (bit v). */
uint32_t entl_hp_apply(const struct entl_mem *m, struct entl_hp *o, const int16_t *explicit_hp,
                       int scale);

#endif
