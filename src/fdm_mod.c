/*
 * fdm_mod.c - the fdm mod, shown as "Full Diagonal Movement" (fdm_mod.h;
 * openspec change b2-full-diagonal-movement).
 *
 * The walk in ent_player_update (sub_00176150) turns the stick into a
 * speed at 0x17C91F: L = sqrt(x^2 + y^2) clamped to 1, s = (L - dz) /
 * (1 - dz) above the deadzone dz (0.4; 0.6 with y forced to 0 while the
 * player's byte +0x38 is set), and at 0x17D2F5 the target speed is s times
 * the speed table's max (0x450A84, rows of 16 bytes: 4.5 and 7.2) times
 * the boost and time-scale factors. A square stick has L = sqrt(2) at a
 * corner, so the clamp makes a diagonal exactly as fast as a straight
 * line. BLiNX 1 has no clamp: there a diagonal runs (sqrt(2) - 0.4) / 0.6
 * = 1.69 times as fast, the speedrunners' technique. A round pad, and the
 * keyboard under a stick ramp (input.stick_ramp_ms; the shipped config has
 * 60), stay on the circle (L = 1) and need Square left stick for corners.
 *
 * The recompiled walk cannot be patched mid-function and reads its 1.0
 * from a constant shared with the whole game, so the mod scales the one
 * reader's input instead: the table's max is read only at 0x17D301 in the
 * whole XBE. Just before the clamp the walk calls the CRT pow
 * (sub_002D675C, returning to 0x17C8FC) with x, y and dz already in its
 * frame; a pre hook there writes max * g, with g the unclamped s over the
 * clamped one ((L - dz) / (1 - dz) for L above 1, where the clamped s is
 * 1), and ent_player_update's pre and post put the table back. Every other
 * user of s (the animation thresholds at 0x17CBB0 to 0x17CD05, player
 * +0xAC, the 0.75 mode scale at 0x17CE62) still sees the clamped value:
 * only the speed changes, and the walk cycle follows the speed at
 * 0x17D3xx, as under the game's own boosts.
 *
 * Only a human's live pad is unclamped. The walk's pad pointer ([esp+0x20],
 * set at 0x176FB0 to 0x177008) is the live pad [0xADC794] + slot * 0x1E4
 * for a human, but also the 0xCCCE00 + i * 0x1E4 array while [0xEC4B6C] is
 * set (0x176FB0), the CPU input array 0x5F0760 + i * 0x1E4 for a CPU player
 * (player byte +0x07), and REC playback (0xDD5B28, stage_play_mode bit
 * 0x4000). Those keep the speed their input was made at, as BLiNX 1's clamp
 * leaves demo and CPU input alone.
 *
 * Off (the default, every golden): the hooks do not run and the table is
 * the XBE's.
 */
#include <string.h>
#include <stddef.h>
#include "fdm_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 4
#      define FDM_MOD 1
#    endif
#  endif
#  if __has_include("pad_map.h")
#    include "pad_map.h"
#    define FDM_PAD_SETUP 1
#  endif
#endif

#ifdef FDM_MOD

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include "enhance_menu.h"
#include "fdm_logic.h"

/* The toolkit's Square left stick as a row of this page (a link setting,
 * descriptor version 2): the same switch as Controls > Sticks, so the
 * player turns on both here. An older toolkit has no links and the texts
 * name the Controls row instead. */
#if XBOX_MOD_DESC_VERSION >= 2
#  define FDM_SQUARE_ROW 1
#  define FDM_SQUARE_WHERE "Square left stick, below."
#  define FDM_SQUARE_HINT "Turn on Square left stick above"
#else
#  define FDM_SQUARE_WHERE "Controls > Sticks > Square left stick."
#  define FDM_SQUARE_HINT "Turn on Square left stick"
#endif

enum {
    SET_ENABLE,
#ifdef FDM_SQUARE_ROW
    SET_SQUARE,
#endif
    SET_N
};

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_FDM", NULL, "Full Diagonal Movement",
      "Diagonals run up to 1.69x as fast as straight, as in BLiNX 1. Needs"
      " Square left stick (pads and keyboard).",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
#ifdef FDM_SQUARE_ROW
    /* The label is the toolkit item's. */
    [SET_SQUARE] = { "square_left", "input.pad_square_left", NULL, NULL, NULL,
      "Pads and the keyboard need it for full diagonals. The same switch as"
      " Controls > Sticks.",
      NULL, XBOX_SET_LINK, 0, 0, 0, 0, 0, 0, NULL },
#endif
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Full Diagonal Movement",
    /* The mod page's About text: the switch's own help is a short tooltip. */
    "Stock BLiNX 2 caps diagonal speed at straight speed. This mod lifts the"
    " cap: diagonals run up to 1.69x as fast, as in BLiNX 1. Pads and the"
    " keyboard need " FDM_SQUARE_WHERE,
    NULL, "1",
    k_set, SET_N, NULL, 0
};

#define VA_PLAYER_UPDATE 0x00176150u    /* ent_player_update(player) */
#define VA_POW           0x002D675Cu    /* the CRT pow, st0 in and out */
#define VA_CALL_POW      0x0017C8F7u    /* the walk's call of pow */
#define RET_WALK         0x0017C8FCu    /* its return address */
#define VA_MAX_READ      0x0017D301u    /* fmul [ebx+0x450A84], max's one reader */
/* The walk's frame, from its esp at the call: the stick as the clamp reads
 * it (zeroed while the walk ignores the stick, y zeroed in the 0.6 mode)
 * and the deadzone. */
#define W_X              0x18u
#define W_Y              0x38u
#define W_DZ             0x28u
#define W_PAD            0x20u          /* the pad the stick comes from */
/* The live pads: pad_active_ptr -> 0x1E4-byte pad structs, one per port
 * (FDM_PAD_SIZE, fdm_logic.h). */
#define VA_PADS          0x00ADC794u
/* The speed table: rows of { ?, max, accel, turn }; the walk picks row
 * 0 or 1 (0x17D2F5) and reads max only there. */
#define VA_SPEED_MAX     0x00450A84u
#define SPEED_ROW        0x10u
#define N_ROWS           2

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

/* Guest thread: hooks, on_enable and init. */
static int s_on;
static int s_scaled;                    /* the table holds base * g */
static float s_base[N_ROWS];
/* The last walk's factor in thousandths, for the status row (the menu
 * reads it on its own thread). */
static unsigned s_last_g = 1000;

static inline float rdf(uint32_t va) { return XBOX_MOD_MEMF(s_api, va); }
static inline void wrf(uint32_t va, float f) { XBOX_MOD_MEMF(s_api, va) = f; }
static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(s_api, va); }

/* The XBE this mod was written against: the walk's call of pow and the
 * table's one reader. A modded XBE with other code there keeps the stock
 * walk. Guest memory is not mapped during init (api->mem is 0), so the
 * first pow call checks, once. */
static const uint8_t k_call_pow[] = { 0xE8, 0x60, 0x9E, 0x15, 0x00 };
static const uint8_t k_max_read[] = { 0xD8, 0x8B, 0x84, 0x0A, 0x45, 0x00 };

static int s_xbe;                       /* 0 unchecked, 1 known, -1 not */

static int code_is(uint32_t va, const uint8_t *b, size_t n)
{
    return memcmp((const void *)(s_api->mem + va), b, n) == 0;
}

static int xbe_known(void)
{
    if (s_xbe == 0) {
        s_xbe = code_is(VA_CALL_POW, k_call_pow, sizeof k_call_pow)
                && code_is(VA_MAX_READ, k_max_read, sizeof k_max_read) ? 1 : -1;
        if (s_xbe < 0)
            s_api->log(&s_mod, "the XBE's walk is not the one this mod knows"
                       " (0x%08X, 0x%08X): stock walk", VA_CALL_POW, VA_MAX_READ);
    }
    return s_xbe > 0;
}

static void restore(void)
{
    int i;

    if (!s_scaled)
        return;
    for (i = 0; i < N_ROWS; i++)
        wrf(VA_SPEED_MAX + (uint32_t)i * SPEED_ROW, s_base[i]);
    s_scaled = 0;
}

static void pow_pre(struct xbox_mod_call *c, void *user)
{
    uint32_t f = c->esp + 4;            /* the walk's esp before the call */
    float g;
    int i;

    (void)user;
    if (!xbe_known() || rd32(c->esp) != RET_WALK)
        return;
    restore();
    /* A human's pad this frame, not CPU, recorded or replayed input. */
    if (!fdm_live_pad(rd32(f + W_PAD), rd32(VA_PADS)))
        return;
    g = fdm_factor(rdf(f + W_X), rdf(f + W_Y), rdf(f + W_DZ));
    /* The status row shows a human's walk only. */
    __atomic_store_n(&s_last_g, (unsigned)lrintf(g * 1000.0f), __ATOMIC_RELAXED);
    if (g == 1.0f)
        return;
    for (i = 0; i < N_ROWS; i++) {
        uint32_t va = VA_SPEED_MAX + (uint32_t)i * SPEED_ROW;

        s_base[i] = rdf(va);
        wrf(va, s_base[i] * g);
    }
    s_scaled = 1;
}

/* Both ends of the update put the table back: the scaled max must never
 * reach another player's walk or outlive the update that set it. */
static void update_hook(struct xbox_mod_call *c, void *user)
{
    (void)c;
    (void)user;
    restore();
}

static void on_enable(int on, void *user)
{
    (void)user;
    /* The switch's state changes at once, on the menu's thread, and only
     * this call waits for the next xbox_mod_frame. A switch off between
     * pow_pre and ent_player_update's post skips that post (the hooks
     * follow the state), so the scaled max can reach the later player
     * updates of that one frame; this restore ends it at the frame's end
     * (design, Risks). */
    restore();
    if (!on)
        __atomic_store_n(&s_last_g, 1000u, __ATOMIC_RELAXED);
    if (on == s_on)
        return;
    s_on = on;
    s_api->log(&s_mod, "%s", on ? "on" : "off (stock walk)");
}

static int square_left(void)
{
#ifdef FDM_PAD_SETUP
    xbox_pad_setup s;

    xbox_InputPadSetup(&s);
    return s.square_left != 0;
#else
    return -1;
#endif
}

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    unsigned g = __atomic_load_n(&s_last_g, __ATOMIC_RELAXED);
    int sq = square_left();

    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0)
        snprintf(buf, n, "turn the mod on first");
    /* Short enough for the row's value column (about 46 characters); the
     * About text says the rest. */
    else if (sq == 0)
        snprintf(buf, n, "%s", FDM_SQUARE_HINT);
    else
        snprintf(buf, n, "ready; last walk x%.2f", g / 1000.0);
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.fdm.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL,
    "Whether diagonals can run faster now, and the last walk's speed factor:"
    " 1.00 straight, 1.69 on a full diagonal."
};

static int init(const struct xbox_mod_api *api)
{
    s_api = api;
    if (!api->hook(VA_POW, pow_pre, NULL, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock walk", VA_POW);
        return 1;
    }
    if (!api->hook(VA_PLAYER_UPDATE, update_hook, update_hook, 0, NULL)) {
        api->log(&s_mod, "no hook slot for 0x%08X: stock walk", VA_PLAYER_UPDATE);
        return 1;
    }
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_enable(on_enable, NULL);
    api->menu_add(&k_status_row);
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "fdm", init, NULL, &k_desc,
                                       XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK };

const void *fdm_mod(void)
{
    return &s_mod;
}

#else /* no mod API: stock */

const void *fdm_mod(void)
{
    return NULL;
}

#endif
