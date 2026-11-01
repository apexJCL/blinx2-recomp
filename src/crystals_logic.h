/*
 * crystals_logic.h - BLiNX 1's crystal row over BLiNX 2's crystal record
 * (crystals_mod.c; openspec change crystal-sets, D1 and D2), on a copy of
 * one team's span so scripts/test_crystals.py can drive it on a fake one.
 *
 * The span is tc_team_record +0xC .. +0xAD (CRY_SPAN bytes): the colour
 * counts at c*6 + k and the crystal words at CRY_WORD(c, k, n). The mod
 * keeps a character's row in its count bytes (k + 1 per crystal, 0 empty)
 * and the row's words in colour 0's word slots. Nothing here calls the
 * game.
 */
#ifndef CAT_CRYSTALS_LOGIC_H
#define CAT_CRYSTALS_LOGIC_H

#include <stdint.h>

#define CRY_RECORD      0x00ADCA58u     /* tc_team_record, team 0 */
#define CRY_RECORD_SIZE 0x5DCu
#define CRY_TEAMS       4
#define CRY_SPAN_OFF    0xCu            /* the span's start in the record */
#define CRY_SPAN        0xA2u
#define CRY_CHARS       3
#define CRY_COLOURS     6
#define CRY_ROW         4               /* BLiNX 1's row: four crystals */

/* Offset of word n of colour k of character c, from the span's start
 * (record +0x1E + ((c*6 + k)*4 + n)*2). */
#define CRY_WORD(c, k, n) (0x12u + ((((unsigned)(c) * 6u + (unsigned)(k)) * 4u + (unsigned)(n)) * 2u))

/* Crystal slot k (item type 0x2A + k) to its control id, as the pickup's
 * switch maps it: PAUSE 2, REC 6, FF 4, RETRY 1, REW 5, SLOW 3
 * (the jump table at 0x8C4F8). */
extern const uint8_t cry_k_to_id[CRY_COLOURS];

/* The row's length, 0..3 (a full row empties at once). */
int cry_row_len(const uint8_t *s, int c);
/* Crystal i of c's row as a colour 0..5, or -1 when empty. */
int cry_row_at(const uint8_t *s, int c, int i);
/* How many crystals of colour k c's row holds. */
int cry_row_count(const uint8_t *s, int c, int k);
/* 1 when colour k pushed into c's row gives its control: three or four of
 * one colour, each from the third on. */
int cry_grants(const uint8_t *s, int c, int k);

/* Before the game's pickup of a colour-k crystal with word w: make c's
 * counts in dst (a copy of src, the span the row is read from) say what
 * the game must do. On a grant, count[k] = 2 and the row's two last words
 * of k sit at word slots 0 and 1, so the game's third crystal grants (or
 * pays gold when the control is full) with the set's own words; else
 * count[k] = 0 and the game only counts. The other counts read 0. The
 * slot the game writes w to gets ~w; returns that slot (0 or 2). */
int cry_prepare(const uint8_t *src, uint8_t *dst, int c, int k, uint16_t w);
/* After the pickup: whether the game counted the crystal for c, that is
 * whether the slot cry_prepare poisoned now holds w. */
int cry_counted(const uint8_t *dst, int c, int k, int slot, uint16_t w);
/* Push colour k (word w) into c's row; at four crystals the row empties.
 * Returns the row's new length. */
int cry_push(uint8_t *s, int c, int k, uint16_t w);
/* Empty c's row: its count bytes and the row's words. */
void cry_clear(uint8_t *s, int c);
/* The mod toggled between the pickup's pre and post hook (the hooks only
 * run while it is on), which left the hook depth off by one: off mid-pickup
 * leaves it 1 and the record prepared, on mid-pickup makes it -1. Zero both
 * and return 1 when the spans must be put back from the pre hook's
 * snapshot. Call only with no pickup in flight (a frame boundary). */
int cry_settle(int *depth, int *active);

#endif
