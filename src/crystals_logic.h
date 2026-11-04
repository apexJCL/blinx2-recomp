/*
 * crystals_logic.h - BLiNX 1's crystal row over BLiNX 2's crystal record
 * (crystals_mod.c; openspec change crystals-rewrite, D1 and D2). Pure: it
 * works on copies of the teams' spans, so scripts/test_crystals.py drives
 * it on fake ones. Nothing here calls the game.
 *
 * A span is tc_team_record +0xC .. +0xAD (CRY_SPAN bytes): the colour
 * counts at c*6 + k and the crystal words at CRY_WORD(c, k, n). The mod
 * keeps character c's row in c's first three count bytes (k + 1 per
 * crystal, 0 empty; at most three, since the fourth empties the row), the
 * row's heart crystals, at most two, in c's RETRY count byte (c*6 + 3, the
 * byte the stock lit hearts above the heart gauge read) and the row's
 * words in colour 0's word slots.
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
#define CRY_RETRY       3               /* the heart crystal's colour */

/* Offset of word n of colour k of character c, from the span's start
 * (record +0x1E + ((c*6 + k)*4 + n)*2). */
#define CRY_WORD(c, k, n) (0x12u + ((((unsigned)(c) * 6u + (unsigned)(k)) * 4u + (unsigned)(n)) * 2u))

/* Crystal colour k (item type 0x2A + k) to its control id, as the pickup's
 * switch maps it: PAUSE 2, REC 6, FF 4, RETRY 1, REW 5, SLOW 3 (the jump
 * table at 0x8C4F8). */
extern const uint8_t cry_k_to_id[CRY_COLOURS];

/* The row's length, 0..3. */
int cry_row_len(const uint8_t *s, int c);
/* Crystal i of c's row as a colour 0..5, or -1 when empty. */
int cry_row_at(const uint8_t *s, int c, int i);
/* 1 when colour k pushed into c's row gives its control: the row then
 * holds three or four of k. */
int cry_grants(const uint8_t *s, int c, int k);
/* Push colour k (word w) into c's row; the fourth crystal empties it.
 * Returns the row's new length. */
int cry_push(uint8_t *s, int c, int k, uint16_t w);
/* Empty c's row: its count bytes and its words. */
void cry_clear(uint8_t *s, int c);

/* How a row slot holding colour k (-1 empty) is drawn: its colour's
 * control icon, the heart above the heart gauge for a heart crystal, or
 * the faint empty slot, also for a heart crystal while the heart's texture
 * is not loaded (heart_loaded 0). */
enum { CRY_ICON_EMPTY, CRY_ICON_COLOUR, CRY_ICON_HEART };
int cry_icon(int k, int heart_loaded);

/* One pickup of a colour-k crystal (word w), around the game's own
 * tc_crystal_collect (D1). begin snapshots every team's span and sets each
 * character's count so that the game grants exactly when that character's
 * row would: on a grant count[k] = 2 with the set's two earlier words at
 * slots 0 and 1, else count[k] = 0. The slot the game will write w to gets
 * ~w, so end can tell which character the game counted (redirects
 * included). */
struct cry_pickup {
    int k;
    uint16_t w;
    uint8_t snap[CRY_TEAMS][CRY_SPAN];
    uint8_t slot[CRY_TEAMS][CRY_CHARS];
};

void cry_pickup_begin(struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int k, uint16_t w);

/* After the game's pickup: put every span back, then push the crystal into
 * the row of the character the game counted, if any. Returns 0 when the
 * game counted nobody (a bounce, an item already taken), 1 when it counted
 * the crystal and 2 when that also completed a set (the game granted or
 * paid gold); *team and *ch name the character. */
int cry_pickup_end(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int *team, int *ch);

/* Put every span back as begin found it, counting nothing: for a pickup
 * whose end never ran (the mod switched off in between). */
void cry_pickup_undo(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS]);

/* The mod switched on or off, maybe between a pickup's begin and end (the
 * hooks run only while on, so the depth is off by one): undo the pickup
 * in flight when *active and the spans are there (span non-NULL), then
 * start balanced, *depth and *active 0. Returns 1 when it undid one. */
int cry_settle(const struct cry_pickup *p, uint8_t *const span[CRY_TEAMS], int *depth, int *active);

/* One HUD row quad (D3): the template quad tpl ({x, y, u, v} x 4, as the
 * sprite add takes it) scaled by scale about its centre and moved to
 * (x, y). own_uv 0 keeps tpl's UVs (a slot icon of the panel's texture);
 * 1 gives every corner the whole texture, u 0 on the left and v 0 at the
 * top, as sub_0006B1F0 draws the heart above the heart gauge. */
void cry_quad(const float *tpl, float *out, float x, float y, float scale, int own_uv);

#endif
