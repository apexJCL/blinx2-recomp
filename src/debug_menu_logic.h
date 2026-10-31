/*
 * debug_menu_logic.h - the debug_menu mod's guest addresses and its pure
 * rules (debug_menu.c; openspec change debug-menu-mod), kept apart so
 * scripts/test_debug_menu.py can drive them without the game.
 *
 * The title (sub_000133E0) keeps its state block at 0x5EB620 and points
 * [0x5EB5F4] at it while it runs; the state dword's 27 states have their
 * jump table at 0x16A90 (analysis/research/blinx2-menu-flow.md).
 *
 * The pointer alone does not prove the title runs: boot (0x601C6) sets it
 * with the state still 0, before the intro movies, and the title's init
 * (sub_00012F50) resets the block later. The scene loop (sub_00062FB0)
 * dispatches on [0xAE73F0] & 0x7F, where scenes 1 and 0x1C run the title,
 * and sets bit 0x80 once the scene's init has run.
 */
#ifndef CAT_DEBUG_MENU_LOGIC_H
#define CAT_DEBUG_MENU_LOGIC_H

#include <stdint.h>

#define DBGM_TITLE_PTR   0x5EB5F4u  /* the title's state block, while it runs */
#define DBGM_STATE       0x5EB620u  /* the block's state dword */
#define DBGM_CURSOR      0x5EB630u  /* the debug menu's cursor */
#define DBGM_STAGE_CUR   0x5EB638u  /* SELECT A STAGE's cursor */
#define DBGM_PLAYERS     0xB22E3Cu  /* players the menus read the pad for */
#define DBGM_PAD0        0xAE7A10u  /* player 0's pad index */
#define DBGM_SCENE       0xAE73F0u  /* the scene loop's scene, 0x80 inited */
#define DBGM_PADS        0xADC794u  /* -> the pad structs, 0x1E4 bytes each */
#define DBGM_PAD_SIZE    0x1E4u
/* What the debug menu's handler reads (0x14FA0, 0x15010, 0x15090): up is
 * byte +0x9A bit 1 or the repeat byte +0xCE bit 4, down +0x9A bit 2 or
 * +0xCE bit 8, A byte +0x48 bit 0x10 or the dword +0x4C. */
#define DBGM_PAD_EDGE    0x9Au
#define DBGM_PAD_REPEAT  0xCEu

enum {
    DBGM_ST_PRESS_START = 0,
    DBGM_ST_MENU = 1,               /* the debug menu */
    DBGM_ST_STAGES = 0xB,           /* SELECT A STAGE */
    DBGM_ST_LEAVING = 0x13          /* off to the stage */
};

/* The debug menu's rows, in the game's order. */
#define DBGM_ENTRIES 15
extern const char *const dbgm_entry_names[DBGM_ENTRIES];

/* Bit i set: row i hangs the port and is skipped. */
extern const uint32_t dbgm_unsafe;

/* 1 while the scene loop runs the title, its init done. */
int dbgm_title_running(uint32_t scene);

/* 1 when the title shows PRESS START, the one state the menu opens from. */
int dbgm_at_press_start(uint32_t scene, uint32_t title_ptr, uint32_t state);

/* 1 while the debug menu shows. */
int dbgm_in_menu(uint32_t scene, uint32_t title_ptr, uint32_t state);

/* The pad's step this frame: -1 up, 1 down, 0 neither or both (the
 * handler then moves the cursor up and back down). */
int dbgm_pad_step(int up, int down);

/* The cursor to write before the handler steps it by step (-1, 0, 1)
 * from cur: cur itself when the row it steps to is safe, else one step
 * back from the next safe row in that direction, so the handler lands
 * there. The handler takes A in the same call, after the step, so the
 * after-the-fact skip (dbgm_cursor_fix) would come a frame late. */
int dbgm_cursor_pre(int cur, int step, uint32_t unsafe);

/* The row the cursor should be on: now when it is safe, else the next safe
 * row in the direction it moved from prev (wrapping, as the game's cursor
 * does at either end). now itself when every row is unsafe or it is out of
 * range. */
int dbgm_cursor_fix(int prev, int now, uint32_t unsafe);

/* The cursor to write when the cursor sits on an unsafe row (an outside
 * write, or the menu opening there): the fixed row from dbgm_cursor_fix,
 * and with a step this poll, one step short of the next safe row past it,
 * since the handler steps after the mod. Without that a Down from 9 would
 * write 10 and the handler would step onto GARAGE (11). */
int dbgm_cursor_guard(int prev, int now, int step, uint32_t unsafe);

/* One write of the open sequence. */
struct dbgm_poke {
    uint32_t va, value;
};
#define DBGM_OPEN_POKES 5
/* The writes that open the debug menu from PRESS START, in order, the state
 * last: what the START handler of state 0 sets (players and pad, which the
 * menus need to read the pad at all), both cursors on row 0, as the
 * scripts set them (the stage list keeps its cursor from the last visit). */
void dbgm_open_pokes(struct dbgm_poke out[DBGM_OPEN_POKES]);

#endif
