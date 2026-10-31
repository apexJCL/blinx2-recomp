/*
 * debug_menu.c - the debug_menu mod (debug_menu.h; openspec change
 * debug-menu-mod).
 *
 * The title's state 1 is the developers' debug menu (1P_MISSION ...
 * THEATER) and its 1P_MISSION row leads to SELECT A STAGE (state 0xB),
 * which loads any stage. Only other debug states lead there, so a retail
 * game never shows them (analysis/research/blinx2-menu-flow.md). The mod
 * opens it from PRESS START with the writes the START handler and a debug
 * state would make (debug_menu_logic.c), so the game's own menu code runs
 * from there on.
 *
 * Threads: the menu's rows and the host action only queue a request
 * (s_req); every guest write happens in on_frame, which xbox_mod_frame runs
 * on the guest's thread between the pad poll and the frame's work. The
 * status row reads two guest dwords from the menu's thread: a stale value
 * there only shows the wrong hint for a frame.
 *
 * Only PRESS START opens it: a stage, the pause menu or the story menus
 * have no return path to the title that the mod could take safely, so
 * elsewhere a request only says where to go (design D2).
 *
 * Rows that hang the port (dbgm_unsafe) are skipped: while the
 * debug menu shows, a cursor that lands on one moves on in the direction
 * it went (design D4).
 *
 * Off (the default, every golden): on_frame returns before reading the
 * guest, so nothing is written.
 */
#include <stddef.h>
#include "debug_menu.h"
#include "debug_menu_logic.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 4
#      define DEBUG_MENU_MOD 1
#    endif
#  endif
#endif

#ifdef DEBUG_MENU_MOD

#include <stdint.h>
#include <stdio.h>
#include "enhance_menu.h"

enum { SET_ENABLE, SET_N };
enum { CTL_OPEN, CTL_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_DEBUG_MENU", NULL, "Debug menu",
      "The developers' debug menu and stage select, opened from this page at"
      " the title's PRESS START. MODEL_EDIT, GARAGE, ENDING and THEATER, which"
      " hang on the loading screen, are skipped.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
};

static const struct xbox_mod_control k_ctl[CTL_N] = {
    /* id, label, help, when, kind, defaults, aliases, env */
    [CTL_OPEN] = { "open", "Open the debug menu",
      "Opens the debug menu at the title's PRESS START, as the row on this page.",
      "at PRESS START", XBOX_CTL_ACTION, NULL, NULL, "RECOMP_DEBUG_MENU_KEY" },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Debug menu",
    "The game's own debug menu and stage select", NULL, "1",
    k_set, SET_N, k_ctl, CTL_N
};

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

static int s_on;                /* guest thread */
static int s_req;               /* any thread sets, the guest thread takes */
static int s_cursor = -1;       /* the cursor last frame in the menu, or -1 */
static uint32_t s_state = UINT32_MAX;   /* the title's state last frame, or MAX */
static int s_open_action = -1;

static uint32_t rd(uint32_t va)
{
    return XBOX_MOD_MEM32(s_api, va);
}

static uint8_t rd8(uint32_t va)
{
    return *(volatile const uint8_t *)(s_api->mem + va);
}

static void open_now(void)
{
    struct dbgm_poke p[DBGM_OPEN_POKES];
    int i;

    dbgm_open_pokes(p);
    for (i = 0; i < DBGM_OPEN_POKES; i++)
        XBOX_MOD_MEM32(s_api, p[i].va) = p[i].value;
    s_cursor = 0;
    s_api->log(&s_mod, "debug menu opened");
    s_api->toast(&s_mod, "Debug menu open: close this menu to use it");
}

/* The pad's step this frame for the players the menu reads, as the
 * handler sees it (0x14FA0, 0x15010): it ORs every player below
 * [0xB22E3C]. */
static int pad_step(void)
{
    uint32_t pads = rd(DBGM_PADS), n = rd(DBGM_PLAYERS), i;
    int up = 0, down = 0;

    if (!pads)
        return 0;
    for (i = 0; i < n && i < 4; i++) {
        uint32_t idx = rd(DBGM_PAD0 + i * 4), pad = pads + idx * DBGM_PAD_SIZE;

        if (idx >= 4)
            continue;   /* not a pad slot: left to the skip below */
        uint8_t edge = rd8(pad + DBGM_PAD_EDGE);
        uint8_t rep = rd8(pad + DBGM_PAD_REPEAT);

        up |= (edge & 1) || (rep & 4);
        down |= (edge & 2) || (rep & 8);
    }
    return dbgm_pad_step(up, down);
}

/* The menu's handler steps the cursor and takes A in one call, so an
 * unsafe row one step away could be picked before the next frame's skip:
 * the cursor is put one step short of the next safe row, so the
 * handler's own step lands there (design D4). Otherwise a cursor on an
 * unsafe row anyway (a write by something else) moves on. */
static void guard_cursor(void)
{
    int now = (int)rd(DBGM_CURSOR);
    int step = pad_step();
    int pre = dbgm_cursor_pre(now, step, dbgm_unsafe);
    int fix;

    if (pre != now) {
        XBOX_MOD_MEM32(s_api, DBGM_CURSOR) = (uint32_t)pre;
        s_api->log(&s_mod, "stepped past %s",
                   dbgm_entry_names[(now + step + DBGM_ENTRIES) % DBGM_ENTRIES]);
        /* pre may be unsafe itself: the handler steps off it this frame. */
        s_cursor = (pre + step + DBGM_ENTRIES) % DBGM_ENTRIES;
        return;
    }
    fix = dbgm_cursor_guard(s_cursor < 0 ? now : s_cursor, now, step, dbgm_unsafe);
    if (fix != now) {
        XBOX_MOD_MEM32(s_api, DBGM_CURSOR) = (uint32_t)fix;
        s_api->log(&s_mod, "skipped %s", dbgm_entry_names[now]);
    }
    s_cursor = (fix + step + DBGM_ENTRIES) % DBGM_ENTRIES;
}

static void on_frame(void *user)
{
    uint32_t scene, ptr, state, prev;
    int req;

    (void)user;
    req = __atomic_exchange_n(&s_req, 0, __ATOMIC_ACQ_REL);
    if (s_open_action >= 0 && s_api->action_pressed(s_open_action))
        req = 1;
    if (!s_on || !s_api->mem) {
        if (req)
            s_api->toast(&s_mod, "Debug menu: turn the mod on first");
        return;
    }
    scene = rd(DBGM_SCENE);
    ptr = rd(DBGM_TITLE_PTR);
    state = rd(DBGM_STATE);
    prev = s_state;
    s_state = dbgm_title_running(scene) && ptr == DBGM_STATE ? state : UINT32_MAX;
    if (req) {
        if (dbgm_at_press_start(scene, ptr, state))
            open_now();
        else
            s_api->toast(&s_mod, "Debug menu: only at the title's PRESS START");
    }
    /* Out of the menu to anything but PRESS START (B) or out of the title:
     * A picked the row under the cursor. */
    if (prev == DBGM_ST_MENU && s_state != DBGM_ST_MENU && s_state != DBGM_ST_PRESS_START
        && s_state != UINT32_MAX) {
        int row = (int)rd(DBGM_CURSOR);

        if (row >= 0 && row < DBGM_ENTRIES)
            s_api->log(&s_mod, "picked %s", dbgm_entry_names[row]);
    }
    if (!dbgm_in_menu(scene, ptr, state)) {
        s_cursor = -1;
        return;
    }
    if (dbgm_unsafe)
        guard_cursor();
}

static void on_enable(int on, void *user)
{
    (void)user;
    if (on == s_on)
        return;
    s_on = on;
    s_cursor = -1;
    s_state = UINT32_MAX;
    s_api->log(&s_mod, "%s", on ? "on" : "off");
}

/* ---- the rows on the mod's page (menu thread) ---------------------------- */

static void open_set(const struct enhance_item *it, const char *value)
{
    (void)it, (void)value;
    __atomic_store_n(&s_req, 1, __ATOMIC_RELEASE);
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0)
        snprintf(buf, n, "turn the mod on first");
    else if (!s_api->mem)
        snprintf(buf, n, "the game has not started");
    else if (dbgm_at_press_start(rd(DBGM_SCENE), rd(DBGM_TITLE_PTR), rd(DBGM_STATE)))
        snprintf(buf, n, "ready (PRESS START)");
    else if (dbgm_in_menu(rd(DBGM_SCENE), rd(DBGM_TITLE_PTR), rd(DBGM_STATE)))
        snprintf(buf, n, "open: close this menu to use it");
    else
        snprintf(buf, n, "go to the title's PRESS START first");
    return buf;
}

static const struct enhance_item k_open_row = {
    "mods.debug_menu.open_now", "Open the debug menu", NULL, ENHANCE_ITEM_ACTION,
    NULL, 0, 0, 0, "at PRESS START", open_set, NULL, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static const struct enhance_item k_status_row = {
    "mods.debug_menu.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static int init(const struct xbox_mod_api *api)
{
    if (api->size < offsetof(struct xbox_mod_api, active))
        return 1;   /* no v3 settings and v2 rows */
    s_api = api;
    /* Inited dormant (switched off, the menu able to turn it on) or on. */
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    s_open_action = api->control_action(&k_desc, CTL_OPEN);
    /* The open action fires through the actions hook, which the menu arms
     * when it is on; with RECOMP_MENU=0 the mod's switch arms it. */
    api->actions_arm("mods.debug_menu.enable");
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_open_row);
    api->menu_add(&k_status_row);
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "debug_menu", init, NULL, &k_desc, XBOX_MOD_NEED_POKE };

const void *debug_menu_mod(void)
{
    return &s_mod;
}

#else /* no mod API v4: stock */

const void *debug_menu_mod(void)
{
    return NULL;
}

#endif
