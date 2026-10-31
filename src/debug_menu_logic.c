/*
 * debug_menu_logic.c - the debug_menu mod's pure rules (debug_menu_logic.h).
 */
#include "debug_menu_logic.h"

const char *const dbgm_entry_names[DBGM_ENTRIES] = {
    "1P_MISSION(NORMAL)", "2P_MISSION(NORMAL)", "1P_MISSION(EASY)", "2P_MISSION(EASY)",
    "2P_VS", "3P_VS", "4P_VS", "MINIGAME", "ODEKAKE", "MODEL_EDIT", "SHOP", "GARAGE",
    "MOVIE", "ENDING", "THEATER",
};

/* The rows that never leave the loading screen on a retail disc, from one
 * headless run per row (design D4): MODEL_EDIT retries d:\edit_model\,
 * which only a development disc had; GARAGE wants a loose
 * garage_ts_us.ipk; ENDING and THEATER wait with no file open,
 * likely on state a cold start lacks. Each one strands the
 * player, so the cursor steps over them. */
const uint32_t dbgm_unsafe = 1u << 9 | 1u << 11 | 1u << 13 | 1u << 14;

int dbgm_title_running(uint32_t scene)
{
    uint32_t id = scene & 0x7F;

    /* 0x80 set and nothing above it: a scene the loop has inited. */
    return (scene & ~0x7Fu) == 0x80 && (id == 1 || id == 0x1C);
}

int dbgm_at_press_start(uint32_t scene, uint32_t title_ptr, uint32_t state)
{
    return dbgm_title_running(scene) && title_ptr == DBGM_STATE
        && state == DBGM_ST_PRESS_START;
}

int dbgm_in_menu(uint32_t scene, uint32_t title_ptr, uint32_t state)
{
    return dbgm_title_running(scene) && title_ptr == DBGM_STATE && state == DBGM_ST_MENU;
}

int dbgm_pad_step(int up, int down)
{
    return up && !down ? -1 : down && !up ? 1 : 0;
}

int dbgm_cursor_pre(int cur, int step, uint32_t unsafe)
{
    int to, safe;

    if (step == 0 || cur < 0 || cur >= DBGM_ENTRIES)
        return cur;
    to = (cur + step + DBGM_ENTRIES) % DBGM_ENTRIES;
    safe = dbgm_cursor_fix(cur, to, unsafe);
    return (safe - step + DBGM_ENTRIES) % DBGM_ENTRIES;
}

int dbgm_cursor_fix(int prev, int now, uint32_t unsafe)
{
    int dir, i, r;

    if (now < 0 || now >= DBGM_ENTRIES || !(unsafe & (1u << now)))
        return now;
    /* Up from row 0 lands on the last row: a step of -1 too. */
    dir = (now == prev - 1 || (prev == 0 && now == DBGM_ENTRIES - 1)) ? -1 : 1;
    for (i = 1, r = now; i < DBGM_ENTRIES; i++) {
        r = (r + dir + DBGM_ENTRIES) % DBGM_ENTRIES;
        if (!(unsafe & (1u << r)))
            return r;
    }
    return now;
}

int dbgm_cursor_guard(int prev, int now, int step, uint32_t unsafe)
{
    int fix = dbgm_cursor_fix(prev, now, unsafe);

    return step ? dbgm_cursor_pre(fix, step, unsafe) : fix;
}

void dbgm_open_pokes(struct dbgm_poke out[DBGM_OPEN_POKES])
{
    out[0].va = DBGM_PLAYERS, out[0].value = 1;
    out[1].va = DBGM_PAD0, out[1].value = 0;
    out[2].va = DBGM_CURSOR, out[2].value = 0;
    out[3].va = DBGM_STAGE_CUR, out[3].value = 0;
    out[4].va = DBGM_STATE, out[4].value = DBGM_ST_MENU;
}
