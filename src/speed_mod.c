/*
 * speed_mod.c - the speed mod, shown as "Speed readout" (speed_mod.h;
 * openspec change b2-full-diagonal-movement, D4).
 *
 * Once a frame, while the mod is on, it reads player 0's speed (+0x154 of
 * the record at 0xCD2440) and the stick of the live pad that player's walk
 * reads, and puts "now 1.69  peak 1.69" under the title "Speed" on the
 * mod's status card, as BLiNX 1's readout does: the speed over a full
 * straight push's (speed_logic.h has why that is learned) and the highest
 * of the last second. It is its own mod, not a part of fdm, because a
 * card goes away with its mod and the readout is for comparing fdm off
 * and on.
 *
 * It writes no guest memory and hooks nothing. Off (the default, every
 * golden): the frame callback returns at once and there is no card. The
 * toolkit draws the card only while the menu layer is on (menu.enabled).
 */
#include <stddef.h>
#include "speed_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 7
#      define SPEED_MOD 1
#    endif
#  endif
#endif

#ifdef SPEED_MOD

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "enhance_menu.h"
#include "speed_logic.h"

enum { SET_ENABLE, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_SPEED_READOUT", NULL, "Speed readout",
      "Shows Blinx's run speed on screen: 1.00 straight, up to 1.69 on"
      " diagonals with Full Diagonal Movement.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Speed readout",
    "Debug readout of Blinx's run speed. Push straight on the stick or a"
    " key to set 1.00; diagonals reach 1.69 only with Full Diagonal Movement and Square left"
    " stick. Peak is the top of about the last second.",
    NULL, "1",
    k_set, SET_N, NULL, 0
};

#define VA_PLAYER0   0x00CD2440u        /* players, 0x30C each */
#define P_SPEED      0x154u             /* the walk's speed, eased to its target */
#define P_ID         0x00u              /* the player's signed id byte */
#define VA_PADS      0x00ADC794u        /* pad_active_ptr: the live pads' base */
#define VA_PAD_INDEX 0x00AE7A10u        /* pad_menu_index: a pad slot per player */
#define PAD_X        0x14u
#define PAD_Y        0x18u

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

/* Guest thread. */
static int s_on;
static struct speed_state s_st;
static char s_shown[64];

static inline float rdf(uint32_t va) { return XBOX_MOD_MEMF(s_api, va); }
static inline uint32_t rd32(uint32_t va) { return XBOX_MOD_MEM32(s_api, va); }

/* The live pad player 0's walk reads (speed_live_pad; 0x176FC7 reads
 * it). 0 when there is none. */
static uint32_t player0_pad(void)
{
    uint32_t index[4];
    unsigned i;

    for (i = 0; i < 4u; i++)
        index[i] = rd32(VA_PAD_INDEX + 4u * i);
    return speed_live_pad(*(volatile int8_t *)(s_api->mem + VA_PLAYER0 + P_ID), rd32(VA_PADS),
                          index);
}

static void on_frame(void *user)
{
    char text[sizeof s_shown];
    float r, peak, x, y;
    uint32_t pad;

    (void)user;
    if (!s_on || !s_api->mem)
        return;
    pad = player0_pad();
    x = pad ? rdf(pad + PAD_X) : 0.0f;
    y = pad ? rdf(pad + PAD_Y) : 0.0f;
    r = speed_step(&s_st, rdf(VA_PLAYER0 + P_SPEED), sqrtf(x * x + y * y), &peak);
    if (r < 0.0f)
        snprintf(text, sizeof text, "Speed\nnow --  (push straight once)");
    else
        snprintf(text, sizeof text, "Speed\nnow %.2f  peak %.2f", r, peak);
    /* A call only when the card changes. */
    if (strcmp(text, s_shown) == 0)
        return;
    memcpy(s_shown, text, sizeof s_shown);
    s_api->status(&s_mod, text);
}

static void on_enable(int on, void *user)
{
    (void)user;
    if (on == s_on)
        return;
    s_on = on;
    /* The toolkit drops the card when the mod goes off; a new card and a
     * new reference when it comes back. */
    memset(&s_st, 0, sizeof s_st);
    s_shown[0] = '\0';
}

static int init(const struct xbox_mod_api *api)
{
    s_api = api;
    if (api->size < offsetof(struct xbox_mod_api, status) + sizeof api->status || !api->status) {
        api->log(&s_mod, "no status card in this toolkit: no readout");
        return 1;
    }
    if (!api->on_frame(on_frame, NULL)) {
        api->log(&s_mod, "no frame slot: no readout");
        return 1;
    }
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_enable(on_enable, NULL);
    if (s_on)
        api->log(&s_mod, "on");
    return 0;
}

static const struct xbox_mod s_mod = { "speed", init, NULL, &k_desc, 0 };

const void *speed_mod(void)
{
    return &s_mod;
}

#else /* no mod API v7: no readout */

const void *speed_mod(void)
{
    return NULL;
}

#endif
