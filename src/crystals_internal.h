/*
 * crystals_internal.h - what crystals_mod.c shares with its live proof
 * driver, crystals_proof.c (openspec change crystals-rewrite, D6). Both
 * build only with the mod API v6; CRYSTALS_MOD says so.
 */
#ifndef CAT_CRYSTALS_INTERNAL_H
#define CAT_CRYSTALS_INTERNAL_H

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

/* Guest addresses both files read. */
#define CRY_VA_COLLECT      0x0008BFD0u /* tc_crystal_collect */
#define CRY_TYPE0           0x2Au       /* item type of crystal colour 0 */
#define CRY_VA_TEAM_MODE    0x00B21CB4u /* stage_team_mode: 0 Sweepers */
#define CRY_VA_PLAYERS      0x00CD2440u /* players, 0x30C each */
#define CRY_PLAYER_SIZE     0x30Cu
#define CRY_PLAYER_CHAR     0x41u
#define CRY_REC_HELD        0xAEu       /* + c*8 + id */
#define CRY_GUEST_TOP       0x04000000u
/* The mod's one guest block: the HUD row's quads from 0, the proof's
 * spawn position at CRY_BLOCK_POS. */
#define CRY_BLOCK_SIZE      0x1000u
#define CRY_BLOCK_POS       0x800u

/* What the mod saw, for the Status row and the proof log. sets and gold
 * are read from the menu thread too (atomics); the rest is the guest
 * thread's. */
struct cry_stats {
    int sets, gold;
    uint32_t slots, pips, rows, rejected, hearts, js, n;
    float cy, size, x0, x1;
};

extern const struct xbox_mod_api *cry_api;
extern struct cry_stats cry_stats;

/* The mod's guest block, allocated at first use; 0 when there is none. */
uint32_t cry_block(void);

/* The proof (crystals_proof.c): set up from RECOMP_DEBUG=crystals_proof,
 * stepped once a frame. cry_proof_out is its log, NULL when it is off. */
void cry_proof_init(const struct xbox_mod *m, const char *steps);
void cry_proof_frame(void);
extern FILE *cry_proof_out;

#endif
#endif
