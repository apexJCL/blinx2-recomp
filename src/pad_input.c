/**
 * Pad state for the XInput overrides in recomp_manual.c.
 *
 * Two sources, merged (OR of buttons, max of analog, first non-zero stick):
 *
 *   1. A script: RECOMP_INPUT_SCRIPT="wait open logo_mgs; tap START until
 *      open blinx2_opening", a path to a file of the same steps (one per
 *      line, # comments), or @name for a built-in preset (see PRESETS below).
 *   2. The host pad through the toolkit's xbox_input (XInput + RECOMP_KEYBOARD
 *      on Windows/Proton, SDL2 GameController elsewhere). RECOMP_HOST_PAD=0
 *      always disables it and =1 always enables it; unset, it is off when a
 *      script is set (so scripted and golden runs never see a pad on the
 *      machine), else on by default on Windows and off elsewhere. The
 *      keyboard is read through the host backend, so it is on only when
 *      RECOMP_KEYBOARD=1 and the host pad is on.
 *
 * The connected-port mask is the script's port 0 | the keyboard's port 0 |
 * the ports with a host device: no source, no pad.
 *
 * A script is a list of steps, separated by ';' or newlines, run in order:
 *
 *   wait open TEXT               until the game opens a file whose path
 *                                contains TEXT (any case), e.g. logo_mgs.sfd
 *   wait SECS                    SECS seconds
 *   wait until T                 until T seconds after the first pad poll
 *                                (done at once if T has passed): puts the
 *                                next steps back on the clock after an
 *                                event that comes at a varying time
 *   wait polls N                 N more polls of the pad (about one a frame)
 *   wait mem ADDR == V           until the 32-bit guest dword at ADDR is V
 *   wait mem ADDR != V           ... is not V (ADDR, V: C numbers, 0x ok)
 *   tap BUTTON [every P] until COND
 *                                press BUTTON for P/2 every P seconds (P
 *                                defaults to 0.5) until COND holds, then
 *                                release it at once; COND is "open TEXT"
 *                                or "mem ADDR ==|!= V", as for wait.
 *                                "every Np" counts N port-0 polls instead
 *                                (N >= 2, held N/2 polls), so the taps do
 *                                not depend on frame rate; each press logs
 *                                "[INPUT] t=... poll=<count> press BUTTON"
 *   poke ADDR V                  write the 32-bit guest dword at ADDR once
 *   ACTION[,ACTION...]           now
 *
 *   ACTION  BUTTON        press (analog buttons to 255)
 *           -BUTTON       release
 *           BUTTON/D      press, release D seconds later
 *           BUTTON/Np     press, release N port-0 polls later
 *           BUTTON=V      analog value 0..255, or a stick -32768..32767
 *
 *   BUTTON  UP DOWN LEFT RIGHT START BACK LTHUMB RTHUMB      (digital)
 *           A B X Y BLACK WHITE L R                         (analog)
 *           LX LY RX RY                                     (sticks)
 *
 * File opens are seen through the toolkit's xbox_FileOpenHook (called from
 * NtCreateFile), installed by cat_pad_early_init() before the game starts, so
 * opens before the game first polls the pad are not missed: every successful
 * open is kept, and each "wait open" / "until open" consumes the opens up to
 * and including the one it matched. A step therefore finishes at once if its
 * file opened while an earlier step was still waiting.
 *
 * The older absolute form still works, alongside the steps:
 *
 *   T:ACTION[,ACTION...]         at T seconds after the first pad poll
 *   T1-T2@P:BUTTON               tap BUTTON every P seconds in [T1,T2)
 *
 * Every pad change, step start and matched open is logged as "[INPUT] t=...",
 * t being seconds since the first pad poll. Also logged, each with wall=<s>
 * (CLOCK_REALTIME, to line up with a press sent from outside, scripts/vpad.py):
 *
 *   [INPUT] sources: script=<name|off> host=<on|off> keyboard=<on|off> rumble=<on|off> ports=<mask>
 *                                once, at init
 *   [INPUT] t=<s> ports=<mask>   whenever the connected-port mask changes
 *   [INPUT] t=<s> handles=<h0>,<h1>,<h2>,<h3>
 *                                with RECOMP_INPUT_TRACE=1, whenever the
 *                                title's open pad handles change
 *   [INPUT] t=<s> host port=<n> buttons=<state>
 *                                when a host port's state changes (once per
 *                                poll per port at most)
 *
 * RECOMP_INPUT_STRICT=1 makes a script error (a bad step, an unknown
 * button or preset) fatal: "[INPUT] strict: ..." and exit status 2 before the
 * guest starts. Without it the bad step is logged and dropped.
 *
 * RECOMP_INPUT_SCRIPT also turns on the pad itself; without it and without a
 * host pad the title sees an empty port, as before.
 */

#include <stdint.h>
#include "recomp_env.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#  define strncasecmp _strnicmp
#else
#  include <time.h>
#  include <pthread.h>
#endif

#include "xinput_xbox.h"

extern void (*xbox_FileOpenHook)(const char *guest_path, uint32_t status);

/* ── presets ───────────────────────────────────────────────────────────── */

/* The intro, as seen on macOS: logo_mgs.sfd (START skips it and the Artoon
 * logo after it), blinx2_opening.sfd (START skips it), then the title,
 * title_movie_1a.sfd. The title takes START only about 10 s after it opens,
 * so a START still held when it opens does nothing; the taps stop there
 * anyway. Left alone, the title runs the attract demo (stg0101) after about
 * 37 s (title state 0 times out after 600 frames).
 *
 * The story route does not reach stage 1-1. With no save, START on the title
 * plays R0_opening.sfd (START is ignored, A skips it), then the LOCKER ROOM
 * team editor (tsedit), back to the title, Story Mode / SAVE GAME (slot,
 * 1P MODE, NOW SAVING), and the hub loads (song_HUBsw.adx) into a CHALLENGE
 * drill, "Test 1 of 7" (camera, moving and jumping), that wants real stick
 * input. With a save, START goes to Story Mode / LOAD GAME and back into the
 * same drill. START there only pauses ("GAME PAUSED", no menu). The old
 * @stage1 tapped START through all this and ended paused in the drill.
 *
 * @stage1 therefore uses the title's own debug menu, the stage select that
 * the retail game keeps but never enters (sub_000133E0, the title state
 * machine; analysis/research/blinx2-menu-flow.md):
 *
 *   0x005EB5F4  -> the title state block, 0x005EB620 once the title runs
 *   0x005EB620  title state: 0 press start, 1 debug menu, 0xB SELECT A
 *               STAGE, 0x13 leaving for the stage
 *   0x005EB630  debug menu cursor (0 = 1P_MISSION(NORMAL))
 *   0x005EB638  stage cursor (0 = ST1-1&2 SWEEPER, stage index 0 = stg0101)
 *   0x00B22E3C  players in the menu, 0x00AE7A10 player 0's pad: START on
 *               "press start" sets them; the menus ignore the pad without
 *   0x00AE73FC  1 once the stage's first checkpoint is taken, which is the
 *               moment play starts (sub_001A95A0; 0 at stage init)
 *
 * In the stage the Operator's dialogue (A advances it), the voice line
 * IE_sw1-0_SWPC.adx and MISSION OBJECTIVES ("Press the A Button") come
 * first; A is tapped through them until the checkpoint flag is set, so the
 * script ends with Stick on the ground, the timer running and no button
 * held. START is never pressed after the title. */
#define SKIP_INTRO "wait open logo_mgs.sfd;"                         \
                   "tap START until open blinx2_opening.sfd;"        \
                   "tap START until open title_movie"

#define STAGE1 SKIP_INTRO ";" \
                    "wait mem 0x5eb5f4 == 0x5eb620;"   /* the title state block is up */ \
                    "wait mem 0x5eb620 == 0;"          /* in "press start" */ \
                    "poke 0xb22e3c 1;"                 /* one player... */ \
                    "poke 0xae7a10 0;"                 /* ...on pad 0 */ \
                    "poke 0x5eb630 0;"                 /* 1P_MISSION(NORMAL) */ \
                    "poke 0x5eb638 0;"                 /* ST1-1 */ \
                    "poke 0x5eb620 1;"                 /* open the debug menu */ \
                    "wait 4;" \
                    "tap A until mem 0x5eb620 == 0xb;" /* to SELECT A STAGE */ \
                    "wait 4;" \
                    "tap A until mem 0x5eb620 == 0x13;" \
                    "wait open stg0101;" \
                    "wait open jingle_stagestart;" \
                    /* Every 3 s, not 2: the press at the jingle skips the \
                     * fly-over to Stick's close-up, and the close-up takes A \
                     * from about jingle + 60 frames. A 2 s period put the \
                     * second press on that edge, so one present of phase \
                     * decided whether the dialogue came at ~827 or ~887, \
                     * and golden runs split between the two. With 3 s the first \
                     * press is up by +45 and the second lands at ~+90: 30 \
                     * presents past the edge, 16 after the golden \
                     * stage1-stick dump (present 841, ~+74). */ \
                    "tap A every 3 until mem 0xae73fc == 1"

/* @stage1-enemies: from the checkpoint flag, walk round the west end of the
 * brick wall, north to the barricade (8 A presses clear the Operator
 * dialogue), jump onto the ledge, up the ramp to the top platform, and on to
 * its east end (bench dumps ~44-50). Every step counts polls, A included, so
 * no step depends on wall-clock time. The walk is still open-loop: no player
 * position or area-id address is known yet (blinx2-menu-flow.md lists none),
 * so there is no "wait mem" checkpoint in it. Drift shows only in the frames.
 * Add checkpoints here when such an address is found. */
#define WALK_TO_ENEMIES \
    "wait polls 90;" \
    "LX=-14000,LY=32767;" \
    "wait polls 50;" \
    "LX=0,LY=0;" \
    "wait polls 30;" \
    "LY=32767;" \
    "wait polls 45;" \
    "LY=0;" \
    "wait polls 30;" \
    "LY=32767;" \
    "wait polls 45;" \
    "LY=0;" \
    "wait polls 30;" \
    "LX=32767;" \
    "wait polls 45;" \
    "LX=0;" \
    "wait polls 30;" \
    "LX=32767;" \
    "wait polls 45;" \
    "LX=0;" \
    "wait polls 30;" \
    "LX=-32767;" \
    "wait polls 25;" \
    "LX=0;" \
    "wait polls 30;" \
    "LY=32767;" \
    "wait polls 65;" \
    "LY=0;" \
    "wait polls 60;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 39;" \
    "A;" \
    "wait polls 6;" \
    "-A;" \
    "wait polls 54;" \
    "LX=32767;" \
    "wait polls 6;" \
    "A;" \
    "wait polls 9;" \
    "-A;" \
    "wait polls 21;" \
    "LX=0;" \
    "wait polls 45;" \
    "LX=32767;" \
    "wait polls 30;" \
    "LX=0;" \
    "wait polls 30;" \
    "LY=32767;" \
    "wait polls 15;" \
    "LY=0;" \
    "wait polls 30;" \
    "LX=-23000,LY=23000;" \
    "wait polls 45;" \
    "LX=0,LY=0;" \
    "wait polls 45;" \
    "LX=-23000,LY=23000;" \
    "wait polls 45;" \
    "LX=0,LY=0;" \
    "wait polls 45;" \
    "LX=32767;" \
    "wait polls 30;" \
    "LX=0;" \
    "wait polls 45;" \
    "LX=32767;" \
    "wait polls 45;" \
    "LX=0;" \
    "wait polls 45"

/* @story-hub: the front door, from an empty save to the hub, with no poke.
 * Every step waits on a game event from the menu catalogue
 * (openspec/changes/input-real-devices/design.md, "Menu catalogue"):
 *
 *   title state 0 ("press start")  START -> 2, 0x15, 0xC, then 0x14 with
 *                                  next scene [0xAE7424] = 0x1B: R0_opening.sfd
 *   R0_opening (state 0x14)        START ignored, A skips it: next scene
 *                                  0x16, tsedit_tex (LOCKER ROOM) opens
 *   LOCKER ROOM (state 0x14)       host dialogue (A advances), AUTO SELECT /
 *                                  CUSTOM SELECT (cursor on AUTO, A), "Is this
 *                                  your team? ... press A.", "Congratulations!
 *                                  Your team is ready to go!", then the title
 *                                  runs again in state 0xD
 *   Story Mode (state 0xD)         SAVE GAME, slot 1 of 3, 1P MODE, NOW
 *                                  SAVING: U:\13C91777168C\blinx2data.bin
 *   leaving (state 0x13, 0x14)     next scene 0xA, stage index [0xB871AC] =
 *                                  0x32 (Sweepers hub): song_HUBsw.adx
 *
 * The editor has no file open or known address between its screens, so A is
 * tapped through all of them, on defaults only, until the title state comes
 * back as 0xD; AUTO SELECT picks the team, so the team name and members vary
 * from run to run. The taps are in seconds (1.5 s: the editor's screens fade
 * in slowly), not in polls. The script ends as the hub loads, before the
 * CHALLENGE drill's "Press the A Button", with nothing held. With a save
 * present the title goes to LOAD GAME instead and this preset does not
 * apply: run it from an empty RECOMP_SAVE_DIR.
 *
 * For the golden `story` frames: A skips R0_opening 4-9 s after it opens
 * (Proton, 9 runs; presses before that are ignored), so tsedit opens at
 * t=13-18. "wait until 24" puts the editor back on the clock: the host's
 * first line is up by then, one A brings AUTO SELECT / CUSTOM SELECT, which
 * is held for 8 s, and the SAVE GAME slot list is held for 7 s, so each
 * screen spans several frame dumps. If tsedit opens after t=24 the wait is
 * a no-op. macOS (CPU walker) opened it at t=20.8 and reached the hub at
 * t=187 with the same opens and `script done`. */
#define STORY_HUB SKIP_INTRO ";" \
                  "wait mem 0x5eb5f4 == 0x5eb620;"        /* the title state block is up */ \
                  "wait mem 0x5eb620 == 0;"               /* "press start" */ \
                  "tap START every 1 until open R0_opening.sfd;" \
                  "tap A every 1 until open tsedit;"      /* skip the story opening */ \
                  "wait until 24;"                        /* back on the clock */ \
                  "A/0.5;"                                /* the host's line -> AUTO SELECT */ \
                  "wait 8;" \
                  "tap A every 1.5 until mem 0x5eb620 == 0xd;" /* LOCKER ROOM on defaults */ \
                  "wait 7;"                               /* the SAVE GAME slot list */ \
                  "tap A every 1.5 until open blinx2data.bin;" /* SAVE GAME, slot 1, 1P */ \
                  "wait open song_HUBsw"

/* @story-load: the LOAD GAME door, from a seeded save to the hub, with no
 * poke (input-real-devices 7.1/7.2; run with RECOMP_SAVE_SEED, design.md
 * D11). Seen on macOS with a community save, re-signed locally
 * (Training and Stage 1 done):
 *
 *   title state 0         START -> 2, 0x15, then 0xD with title_movie_2a.sfd:
 *                         Story Mode (New Game / Load Game), then LOAD GAME,
 *                         slot 1 (the cursor starts on the newest save)
 *   slot, A               state 0x13, next scene [0xAE7424] 0x1B, stage
 *                         index 0x32: the round-2 intermission IM_sw2_1_4.sfd
 *                         (A skips it)
 *   leaving               next scene 0xA: tsinfo_tex, stg1101_tex (the hub),
 *                         song_HUBsw.adx
 *
 * A damaged or foreign-signed save stops on "Save game appears to be
 * damaged" in state 0xD: the script then waits forever. */
#define STORY_LOAD SKIP_INTRO ";" \
                   "wait mem 0x5eb5f4 == 0x5eb620;"        /* the title state block is up */ \
                   "wait mem 0x5eb620 == 0;"               /* "press start" */ \
                   "tap START every 1 until mem 0x5eb620 == 0xd;" /* Story Mode */ \
                   "wait 3;"   /* menu slide-in: title_movie_2a opens before state 0xD, so no later event marks it; A taps until 0x13 anyway */ \
                   "tap A every 1.5 until mem 0x5eb620 == 0x13;"  /* Load Game, slot 1 */ \
                   "tap A every 1 until mem 0xae7424 == 0xa;"     /* skip the intermission */ \
                   "wait open song_HUBsw"

static const struct { const char *name, *script; } PRESETS[] = {
    { "skip-intro", SKIP_INTRO },               /* ends idle on the title */
    { "attract",    SKIP_INTRO },               /* the same; the demo is the title's timer */
    { "new-game",   SKIP_INTRO ";"              /* story mode with no save: ends in tsedit */
                    "tap START until open R0_opening.sfd;"
                    "tap A until open tsedit" },
    { "stage1",     STAGE1 },
    { "story-hub",  STORY_HUB },                /* empty save -> team editor -> SAVE GAME -> hub */
    { "story-load", STORY_LOAD },               /* seeded save -> LOAD GAME -> hub */
    { "stage1-enemies", STAGE1 ";" WALK_TO_ENEMIES },
};

/* ── clock ─────────────────────────────────────────────────────────────── */

static double now_s(void)
{
#ifdef _WIN32
    static LARGE_INTEGER freq;
    LARGE_INTEGER t;
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart / (double)freq.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + ts.tv_nsec * 1e-9;
#endif
}

/* Wall-clock seconds (CLOCK_REALTIME; under Wine the host's realtime clock
 * too), on the host lines, so a press sent from outside the game (vpad.py
 * prints the same clock) can be subtracted from the poll that saw it. */
static double wall_s(void)
{
#ifdef _WIN32
    FILETIME ft;
    ULARGE_INTEGER u;
    GetSystemTimePreciseAsFileTime(&ft);
    u.LowPart = ft.dwLowDateTime; u.HighPart = ft.dwHighDateTime;
    return (double)(u.QuadPart - 116444736000000000ULL) * 1e-7;
#else
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + ts.tv_nsec * 1e-9;
#endif
}

/* ── state ─────────────────────────────────────────────────────────────── */

enum { K_DIGITAL, K_ANALOG, K_STICK };

static const struct { const char *name; int kind, bit; } BUTTONS[] = {
    { "UP", K_DIGITAL, XBOX_GAMEPAD_DPAD_UP },
    { "DOWN", K_DIGITAL, XBOX_GAMEPAD_DPAD_DOWN },
    { "LEFT", K_DIGITAL, XBOX_GAMEPAD_DPAD_LEFT },
    { "RIGHT", K_DIGITAL, XBOX_GAMEPAD_DPAD_RIGHT },
    { "START", K_DIGITAL, XBOX_GAMEPAD_START },
    { "BACK", K_DIGITAL, XBOX_GAMEPAD_BACK },
    { "LTHUMB", K_DIGITAL, XBOX_GAMEPAD_LEFT_THUMB },
    { "RTHUMB", K_DIGITAL, XBOX_GAMEPAD_RIGHT_THUMB },
    { "A", K_ANALOG, XBOX_BUTTON_A }, { "B", K_ANALOG, XBOX_BUTTON_B },
    { "X", K_ANALOG, XBOX_BUTTON_X }, { "Y", K_ANALOG, XBOX_BUTTON_Y },
    { "BLACK", K_ANALOG, XBOX_BUTTON_BLACK },
    { "WHITE", K_ANALOG, XBOX_BUTTON_WHITE },
    { "L", K_ANALOG, XBOX_BUTTON_LTRIGGER },
    { "R", K_ANALOG, XBOX_BUTTON_RTRIGGER },
    { "LX", K_STICK, 0 }, { "LY", K_STICK, 1 },
    { "RX", K_STICK, 2 }, { "RY", K_STICK, 3 },
};
#define NBUTTONS ((int)(sizeof BUTTONS / sizeof BUTTONS[0]))

/* A timed change: the absolute form, and the releases of BUTTON/D and taps.
 * poll >= 0: due at that port-0 poll count instead of at time t. */
typedef struct { double t; int button; int value; long poll; } Event;
/* An action of a step; dur > 0 releases it dur seconds later, dpolls > 0
 * that many port-0 polls later (BUTTON/Np). */
typedef struct { int button; int value; double dur; long dpolls; } Act;

enum { S_ACTS, S_WAIT_SECS, S_WAIT_UNTIL, S_WAIT_POLLS, S_WAIT_COND, S_TAP, S_POKE };
enum { C_OPEN, C_MEM };     /* the condition of a wait / tap: open TEXT, mem ADDR OP V */
typedef struct {
    int    kind;
    double secs;            /* wait SECS; tap period */
    long   ppolls;          /* tap period in polls (every Np), 0 if in seconds */
    long   polls;           /* wait polls N */
    int    cond;            /* C_OPEN or C_MEM */
    char  *match;           /* open TEXT, lower case */
    uint32_t addr, val;     /* mem ADDR OP VAL; poke ADDR VAL */
    int    ne;              /* mem: 1 for !=, 0 for == */
    int    button;          /* tap */
    Act   *acts;            /* ACTION list */
    int    nacts;
    char  *text;            /* as written, for the log */
} Step;

static Event *g_ev;  static int g_nev, g_cap, g_next;   /* absolute form */
static Event *g_rel; static int g_nrel, g_relcap;       /* pending releases */
static Step  *g_steps; static int g_nsteps, g_stepcap;
static int    g_cur, g_entered;                         /* current step */
static double g_step_t, g_tap_next;
static long   g_step_polls, g_tap_next_poll;
static long   g_poll;                                   /* port-0 polls so far */

static char **g_opens; static int g_nopens, g_opencap, g_open_cur;

static int    g_script_on, g_host_on, g_started;
static int    g_rumble_on = 1;          /* RECOMP_RUMBLE=0 turns it off */
static int    g_errors;                 /* script parse errors (RECOMP_INPUT_STRICT) */
static double g_t0;
static XBOX_GAMEPAD g_script;          /* the script's current state */
static uint32_t g_packet[4];
static XBOX_GAMEPAD g_last[4];
static XBOX_GAMEPAD g_host_last[4];    /* the host's last state, per port */
static uint32_t g_mask_last;           /* the last connected mask logged */
static double   g_probe_t[4];          /* last host query per port (now_s) */
#ifndef _WIN32
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
#  define LOCK()   pthread_mutex_lock(&g_lock)
#  define UNLOCK() pthread_mutex_unlock(&g_lock)
#else
static CRITICAL_SECTION g_cs;
#  define LOCK()   EnterCriticalSection(&g_cs)
#  define UNLOCK() LeaveCriticalSection(&g_cs)
#endif

static void *grow(void *p, int n, int *cap, size_t size)
{
    if (n < *cap) return p;
    *cap = *cap ? *cap * 2 : 32;
    return realloc(p, (size_t)*cap * size);
}

static void add_event(double t, int button, int value)
{
    g_ev = grow(g_ev, g_nev, &g_cap, sizeof *g_ev);
    g_ev[g_nev].t = t; g_ev[g_nev].button = button; g_ev[g_nev].value = value;
    g_ev[g_nev].poll = -1;
    g_nev++;
}

static void add_release(double t, int button)
{
    g_rel = grow(g_rel, g_nrel, &g_relcap, sizeof *g_rel);
    g_rel[g_nrel].t = t; g_rel[g_nrel].button = button; g_rel[g_nrel].value = 0;
    g_rel[g_nrel].poll = -1;
    g_nrel++;
}

/* A release due at port-0 poll count `poll`. */
static void add_release_poll(long poll, int button)
{
    add_release(0, button);
    g_rel[g_nrel - 1].poll = poll;
}

static Step *add_step(int kind, const char *text)
{
    Step *s;
    g_steps = grow(g_steps, g_nsteps, &g_stepcap, sizeof *g_steps);
    s = &g_steps[g_nsteps++];
    memset(s, 0, sizeof *s);
    s->kind = kind;
    s->text = strdup(text);
    return s;
}

static char *lower_dup(const char *s)
{
    char *d = strdup(s);
    for (char *p = d; *p; p++) *p = (char)tolower((unsigned char)*p);
    return d;
}

static char *trim(char *s)
{
    char *e;
    while (isspace((unsigned char)*s)) s++;
    e = s + strlen(s);
    while (e > s && isspace((unsigned char)e[-1])) *--e = 0;
    return s;
}

/* ── parsing ───────────────────────────────────────────────────────────── */

static int find_button(const char *s, size_t n)
{
    for (int i = 0; i < NBUTTONS; i++)
        if (strlen(BUTTONS[i].name) == n
            && !strncasecmp(BUTTONS[i].name, s, n))
            return i;
    return -1;
}

static int press_value(int b) { return BUTTONS[b].kind == K_STICK ? 32767 : 255; }

/* One ACTION into *out; 0 if it is not one. */
static int parse_action(const char *a, Act *out)
{
    int release = 0, b;
    size_t n;

    while (isspace((unsigned char)*a)) a++;
    if (*a == '-') { release = 1; a++; }
    else if (*a == '+') a++;
    n = strcspn(a, "/= \t\r");
    if (!n) return 0;
    b = find_button(a, n);
    if (b < 0) {
        g_errors++, fprintf(stderr, "[INPUT] script: unknown button '%.*s'\n", (int)n, a);
        return 0;
    }
    a += n;
    out->button = b;
    out->dur = 0;
    out->dpolls = 0;
    if (release)          out->value = 0;
    else if (*a == '=')   out->value = (int)strtol(a + 1, NULL, 0);
    else {
        out->value = press_value(b);
        if (*a == '/') {
            char *end;
            double d = strtod(a + 1, &end);
            if (*end == 'p' || *end == 'P') {           /* BUTTON/Np: N polls */
                out->dpolls = (long)d;
                if (out->dpolls < 1 || d != (double)out->dpolls) {
                    g_errors++, fprintf(stderr, "[INPUT] script: bad hold '%s' (BUTTON/Np, N >= 1)\n", a - n);
                    return 0;
                }
            } else
                out->dur = d;
        }
    }
    return 1;
}

/* The absolute form: T:ACTION[,ACTION...] or T1-T2@P:BUTTON. */
static void parse_timed(char *e)
{
    char *colon = strchr(e, ':'), *end, *act;
    double t1, t2, period;
    Act a;

    *colon = 0;
    act = colon + 1;
    t1 = strtod(e, &end);
    if (*end == '-' && strchr(end, '@')) {
        t2 = strtod(end + 1, &end);
        period = strtod(strchr(end, '@') + 1, NULL);
        if (period <= 0 || !parse_action(act, &a)) return;
        for (double t = t1; t < t2; t += period) {
            add_event(t, a.button, press_value(a.button));
            add_event(t + period / 2, a.button, 0);
        }
        return;
    }
    for (char *p = act;;) {
        size_t n = strcspn(p, ",");
        char c = p[n];
        p[n] = 0;
        int ok = parse_action(p, &a);
        if (ok && a.dpolls)
            g_errors++, fprintf(stderr, "[INPUT] script: '%s': polls (/Np) only in steps, "
                                "not in the T:ACTION form\n", p);
        else if (ok) {
            add_event(t1, a.button, a.value);
            if (a.dur > 0) add_event(t1 + a.dur, a.button, 0);
        }
        if (!c) break;
        p += n + 1;
    }
}

static int word(char **s, const char *w)
{
    size_t n = strlen(w);
    if (strncasecmp(*s, w, n) || ((*s)[n] && !isspace((unsigned char)(*s)[n])))
        return 0;
    *s = trim(*s + n);
    return 1;
}

/* "open TEXT" or "mem ADDR ==|!= VALUE" into s; 0 if it is neither. */
static int parse_cond(char *p, Step *s)
{
    char *end;
    if (word(&p, "open") && *p) {
        s->cond = C_OPEN;
        s->match = lower_dup(p);
        return 1;
    }
    if (!word(&p, "mem")) return 0;
    s->cond = C_MEM;
    s->addr = (uint32_t)strtoul(p, &end, 0);
    if (end == p) return 0;
    p = trim(end);
    if (!strncmp(p, "==", 2)) s->ne = 0;
    else if (!strncmp(p, "!=", 2)) s->ne = 1;
    else return 0;
    p = trim(p + 2);
    s->val = (uint32_t)strtoul(p, &end, 0);
    return end != p;
}

static void parse_line(char *e)
{
    char *text, *p;

    e = trim(e);
    if (!*e || *e == '#') return;
    text = e;
    if (isdigit((unsigned char)*e) && strchr(e, ':')) { parse_timed(e); return; }

    p = e;
    if (word(&p, "poke")) {
        char *end, *q;
        Step *s = add_step(S_POKE, text);
        s->addr = (uint32_t)strtoul(p, &end, 0);
        q = trim(end);
        s->val = (uint32_t)strtoul(q, &end, 0);
        if (end == q || !s->addr) {
            g_errors++, fprintf(stderr, "[INPUT] script: bad step '%s' (poke ADDR VALUE)\n", text);
            free(s->text);
            g_nsteps--;
        }
        return;
    }
    if (word(&p, "wait")) {
        if (!strncasecmp(p, "open", 4) || !strncasecmp(p, "mem", 3)) {
            Step *s = add_step(S_WAIT_COND, text);
            if (!parse_cond(p, s)) {
                g_errors++, fprintf(stderr, "[INPUT] script: bad step '%s' "
                        "(wait open TEXT | wait mem ADDR ==|!= VALUE)\n", text);
                free(s->text);
                g_nsteps--;
            }
        } else if (word(&p, "polls"))
            add_step(S_WAIT_POLLS, text)->polls = strtol(p, NULL, 0);
        else if (word(&p, "until"))
            add_step(S_WAIT_UNTIL, text)->secs = strtod(p, NULL);
        else if (isdigit((unsigned char)*p) || *p == '.')
            add_step(S_WAIT_SECS, text)->secs = strtod(p, NULL);
        else
            g_errors++, fprintf(stderr, "[INPUT] script: bad step '%s'\n", text);
        return;
    }
    if (word(&p, "tap")) {
        size_t n = strcspn(p, " \t");
        int b = find_button(p, n);
        double period = 0.5;
        char *rest = trim(p + n);
        Step *s;
        if (b < 0) { g_errors++, fprintf(stderr, "[INPUT] script: bad step '%s'\n", text); return; }
        long ppolls = 0;
        if (word(&rest, "every")) {
            period = strtod(rest, &rest);
            if (*rest == 'p' || *rest == 'P') {         /* every Np: N polls */
                ppolls = (long)period;
                if (ppolls < 2 || period != (double)ppolls) period = 0;   /* bad */
                rest++;
            }
            rest = trim(rest);
        }
        s = add_step(S_TAP, text);
        s->button = b;
        s->secs = period;
        s->ppolls = ppolls;
        if (!word(&rest, "until") || !parse_cond(rest, s) || period <= 0) {
            g_errors++, fprintf(stderr, "[INPUT] script: bad step '%s' "
                    "(tap BUTTON [every P | every Np, N >= 2] until open TEXT | until mem ADDR ==|!= VALUE)\n",
                    text);
            free(s->match); free(s->text);
            g_nsteps--;
        }
        return;
    }
    {
        Step *s = add_step(S_ACTS, text);
        for (p = e;;) {
            size_t n = strcspn(p, ",");
            char c = p[n];
            p[n] = 0;
            s->acts = realloc(s->acts, (size_t)(s->nacts + 1) * sizeof *s->acts);
            if (parse_action(p, &s->acts[s->nacts])) s->nacts++;
            if (!c) break;
            p += n + 1;
        }
        if (!s->nacts) {                /* nothing valid in it: drop the step */
            free(s->acts); free(s->text);
            g_nsteps--;
        }
    }
}

static int cmp_event(const void *x, const void *y)
{
    const Event *a = x, *b = y;
    return a->t < b->t ? -1 : a->t > b->t;
}

static char *load_script(const char *v)
{
    FILE *f;
    if (*v == '@') {
        for (size_t i = 0; i < sizeof PRESETS / sizeof PRESETS[0]; i++)
            if (!strcmp(PRESETS[i].name, v + 1))
                return strdup(PRESETS[i].script);
        g_errors++;
        fprintf(stderr, "[INPUT] unknown preset '%s'\n", v);
        return NULL;
    }
    if (!strpbrk(v, ";\n") && (f = fopen(v, "rb"))) {     /* a file */
        long n;
        char *s;
        fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
        s = malloc((size_t)n + 1);
        n = (long)fread(s, 1, (size_t)n, f);
        s[n] = 0;
        fclose(f);
        /* drop comments so ';' and newlines both split entries */
        for (char *p = s; *p; p++)
            if (*p == '#') while (*p && *p != '\n') *p++ = ' ';
        return s;
    }
    return strdup(v);
}

/* ── file opens ────────────────────────────────────────────────────────── */

static void on_file_open(const char *path, uint32_t status)
{
    char *p;
    if ((int32_t)status < 0 || !path) return;    /* a probe that failed */
    p = lower_dup(path);
    LOCK();
    g_opens = grow(g_opens, g_nopens, &g_opencap, sizeof *g_opens);
    g_opens[g_nopens++] = p;
    UNLOCK();
}

/* Consume the opens up to the first one containing m. Under the lock. */
static int match_open(const char *m, double t)
{
    for (int i = g_open_cur; i < g_nopens; i++)
        if (strstr(g_opens[i], m)) {
            g_open_cur = i + 1;
            fprintf(stderr, "[INPUT] t=%.3f opened %s\n", t, g_opens[i]);
            return 1;
        }
    return 0;
}

/* ── guest memory ──────────────────────────────────────────────────────── */

extern ptrdiff_t xbox_GetMemoryOffset(void);
#define GUEST_RAM_TOP 0x08000000u       /* 128 MB, the devkit RAM the game runs with */

static int guest_ok(uint32_t addr)
{
    return addr >= 0x1000 && addr <= GUEST_RAM_TOP - 4;
}

static uint32_t guest_read(uint32_t addr)
{
    uint32_t v = 0;
    if (guest_ok(addr))
        memcpy(&v, (const void *)((uintptr_t)xbox_GetMemoryOffset() + addr), 4);
    return v;
}

static void guest_write(uint32_t addr, uint32_t v)
{
    if (guest_ok(addr))
        memcpy((void *)((uintptr_t)xbox_GetMemoryOffset() + addr), &v, 4);
}

/* Whether the condition of step s holds now. Under the lock. */
static int cond_met(const Step *s, double t)
{
    uint32_t v;
    if (s->cond == C_OPEN) return match_open(s->match, t);
    v = guest_read(s->addr);
    if ((v == s->val) == !s->ne) {
        fprintf(stderr, "[INPUT] t=%.3f mem 0x%08X = 0x%X\n", t, s->addr, v);
        return 1;
    }
    return 0;
}

/* ── init ──────────────────────────────────────────────────────────────── */

/* The script as the sources line names it: a preset or a file as given, a
 * script written inline as "inline". */
static const char *script_name(const char *v)
{
    if (!g_script_on || !v) return "off";
    if (*v == '@' || !strpbrk(v, ";\n")) return v;
    return "inline";
}

/* The keyboard is part of the host backend (it is merged into port 0 inside
 * xbox_InputGetState on Windows), so it is on only when the host pad is. */
static int keyboard_on(void)
{
#ifdef _WIN32
    const char *k = recomp_env(RENV_KEYBOARD);
    return g_host_on && k && *k && *k != '0';
#else
    return 0;
#endif
}

static double t_now(void) { return g_started ? now_s() - g_t0 : 0.0; }

/* The host ports that report a device. The game queries the ports it has
 * open every frame, which keeps the backend's cache current for them; a port
 * nobody has asked about for a second is probed here, so a pad plugged in
 * later is seen without the "port 0 is always there" shortcut. */
static uint32_t host_mask(void)
{
    uint32_t m = 0;
    double t = now_s();
    if (!g_host_on) return 0;
    for (DWORD p = 0; p < 4; p++) {
        if (t - g_probe_t[p] >= 1.0) {
            XBOX_INPUT_STATE hs;
            g_probe_t[p] = t;
            (void)xbox_InputGetState(p, &hs);
        }
        if (xbox_InputIsConnected(p)) m |= 1u << p;
    }
    return m;
}

/* A port is there exactly while it has a source: the script and the
 * keyboard on port 0, a host device on its own port. Nothing else, so a run
 * with no source reports no pad (and a pad plugged in later shows up through
 * host_mask's probe, not through a port held open in advance). */
static uint32_t connected_mask_now(void)
{
    uint32_t m = host_mask();
    if (g_script_on || keyboard_on()) m |= 1;
    return m;
}

static void init_once(void)
{
    static int done;
    const char *v, *h;
    char *s;

    if (done) return;
    done = 1;
#ifdef _WIN32
    InitializeCriticalSection(&g_cs);
#endif
    v = recomp_env(RENV_INPUT_SCRIPT);
    if (v && *v && (s = load_script(v))) {
        for (char *e = s;;) {
            size_t n = strcspn(e, ";\n");
            char c = e[n];
            e[n] = 0;
            parse_line(e);
            if (!c) break;
            e += n + 1;
        }
        free(s);
        qsort(g_ev, (size_t)g_nev, sizeof *g_ev, cmp_event);
        g_script_on = 1;
        xbox_FileOpenHook = on_file_open;
        fprintf(stderr, "[INPUT] script '%s': %d steps, %d timed events, pad on port 0\n",
                v, g_nsteps, g_nev);
    }
    /* RECOMP_INPUT_STRICT=1: a script that does not parse, or names an
     * unknown preset, ends the run here, before the guest starts, instead of
     * running (and, on the bench, recording) a game with no input. */
    {
        const char *st = recomp_env(RENV_INPUT_STRICT);
        if (st && *st && *st != '0' && g_errors) {
            fprintf(stderr, "[INPUT] strict: %d script error(s) in '%s'; exiting\n",
                    g_errors, v ? v : "");
            fflush(stderr);
            exit(2);
        }
    }

    /* Who may drive the pad. RECOMP_HOST_PAD=0 always keeps host devices
     * out, =1 always lets them in (merged with a script). Unset: a script
     * keeps them out, so scripted and golden runs cannot see a pad left
     * plugged into the machine; with no script they are in where the host
     * has a backend the default trusts (Windows/Proton today; macOS still
     * needs =1 until its SDL path is verified). */
    h = recomp_env(RENV_HOST_PAD);
    if (h && *h)
        g_host_on = *h != '0';
    else if (v && *v)                   /* set, even if it failed to load */
        g_host_on = 0;
    else
#ifdef _WIN32
        g_host_on = 1;
#else
        g_host_on = 0;
#endif
    h = recomp_env(RENV_RUMBLE);
    g_rumble_on = !(h && *h == '0');
    if (g_host_on) {
        xbox_InputInit();
        fprintf(stderr, "[INPUT] host pad enabled\n");
    }
    g_mask_last = connected_mask_now();
    fprintf(stderr, "[INPUT] sources: script=%s host=%s keyboard=%s rumble=%s ports=0x%X wall=%.6f\n",
            script_name(v), g_host_on ? "on" : "off", keyboard_on() ? "on" : "off",
            g_rumble_on ? "on" : "off", g_mask_last, wall_s());
    fflush(stderr);
}

/* Before the game starts, so the opens of the first movies are seen. */
void cat_pad_early_init(void)
{
    init_once();
}

/* ── running the script ────────────────────────────────────────────────── */

static void fmt_state(char *buf, size_t size, const XBOX_GAMEPAD *g)
{
    static const char *dn[] = { "UP", "DOWN", "LEFT", "RIGHT", "START",
                                "BACK", "LTHUMB", "RTHUMB" };
    static const char *an[] = { "A", "B", "X", "Y", "BLACK", "WHITE", "L", "R" };
    int n = 0;

    for (int i = 0; i < 8; i++)
        if (g->wButtons & (1 << i))
            n += snprintf(buf + n, size - (size_t)n, "%s ", dn[i]);
    for (int i = 0; i < 8; i++)
        if (g->bAnalogButtons[i])
            n += snprintf(buf + n, size - (size_t)n, "%s=%u ", an[i],
                          g->bAnalogButtons[i]);
    if (g->sThumbLX || g->sThumbLY || g->sThumbRX || g->sThumbRY)
        n += snprintf(buf + n, size - (size_t)n, "LS(%d,%d) RS(%d,%d) ",
                      g->sThumbLX, g->sThumbLY, g->sThumbRX, g->sThumbRY);
    if (!n) snprintf(buf, size, "none");
    else buf[n - 1] = 0;
}

static void log_state(double t, const XBOX_GAMEPAD *g)
{
    char buf[256];
    fmt_state(buf, sizeof buf, g);
    fprintf(stderr, "[INPUT] t=%.3f buttons=%s\n", t, buf);
}

/* A host port's state changed: once per poll per port at most, since the
 * game polls each open port once a frame. */
static void log_host_state(double t, uint32_t port, const XBOX_GAMEPAD *g)
{
    char buf[256];
    fmt_state(buf, sizeof buf, g);
    fprintf(stderr, "[INPUT] t=%.3f host port=%u buttons=%s wall=%.6f\n",
            t, port, buf, wall_s());
}

static void set_button(int b, int value)
{
    switch (BUTTONS[b].kind) {
    case K_DIGITAL:
        if (value) g_script.wButtons |= (WORD)BUTTONS[b].bit;
        else       g_script.wButtons &= (WORD)~BUTTONS[b].bit;
        break;
    case K_ANALOG:
        g_script.bAnalogButtons[BUTTONS[b].bit] =
            (BYTE)(value < 0 ? 0 : value > 255 ? 255 : value);
        break;
    default: {
        SHORT v = (SHORT)(value < -32768 ? -32768 : value > 32767 ? 32767 : value);
        SHORT *axes[4] = { &g_script.sThumbLX, &g_script.sThumbLY,
                           &g_script.sThumbRX, &g_script.sThumbRY };
        *axes[BUTTONS[b].bit] = v;
    } }
}

/* Drop the pending releases of b (it is being released now). */
static void cancel_releases(int b)
{
    int j = 0;
    for (int i = 0; i < g_nrel; i++)
        if (g_rel[i].button != b) g_rel[j++] = g_rel[i];
    g_nrel = j;
}

/* Advance the steps at a port-0 poll. Under the lock. */
static void run_steps(double t)
{
    while (g_cur < g_nsteps) {
        Step *s = &g_steps[g_cur];
        int done = 0;

        if (!g_entered) {
            g_entered = 1;
            g_step_t = t;
            g_step_polls = 0;
            g_tap_next = t;
            g_tap_next_poll = g_poll;
            fprintf(stderr, "[INPUT] t=%.3f step %d/%d: %s\n",
                    t, g_cur + 1, g_nsteps, s->text);
        }
        switch (s->kind) {
        case S_ACTS:
            for (int i = 0; i < s->nacts; i++) {
                cancel_releases(s->acts[i].button);
                set_button(s->acts[i].button, s->acts[i].value);
                if (s->acts[i].dur > 0) add_release(t + s->acts[i].dur, s->acts[i].button);
                if (s->acts[i].dpolls > 0)
                    add_release_poll(g_poll + s->acts[i].dpolls, s->acts[i].button);
            }
            done = 1;
            break;
        case S_WAIT_SECS:  done = t - g_step_t >= s->secs; break;
        case S_WAIT_UNTIL: done = t >= s->secs; break;
        case S_WAIT_POLLS: done = g_step_polls++ >= s->polls; break;
        case S_WAIT_COND:  done = cond_met(s, t); break;
        case S_POKE:
            fprintf(stderr, "[INPUT] t=%.3f poke 0x%08X: 0x%X -> 0x%X\n",
                    t, s->addr, guest_read(s->addr), s->val);
            guest_write(s->addr, s->val);
            done = 1;
            break;
        case S_TAP:
            if (cond_met(s, t)) {
                cancel_releases(s->button);
                set_button(s->button, 0);
                done = 1;
            } else if (s->ppolls) {
                if (g_poll >= g_tap_next_poll) {
                    set_button(s->button, press_value(s->button));
                    add_release_poll(g_poll + s->ppolls / 2, s->button);
                    g_tap_next_poll = g_poll + s->ppolls;
                    fprintf(stderr, "[INPUT] t=%.3f poll=%ld press %s\n",
                            t, g_poll, BUTTONS[s->button].name);
                }
            } else if (t >= g_tap_next) {
                set_button(s->button, press_value(s->button));
                add_release(t + s->secs / 2, s->button);
                g_tap_next = t + s->secs;
            }
            break;
        }
        if (!done) break;
        g_cur++;
        g_entered = 0;
        if (g_cur == g_nsteps)
            fprintf(stderr, "[INPUT] t=%.3f script done\n", t);
    }
}

/* ── interface for recomp_manual.c ─────────────────────────────────────── */

/* RECOMP_INPUT_TRACE=1: the title's open handle of each pad (pad structs at
 * 0xEBD278, stride 0x1E4, handle at +0x88; 0 = port closed), logged as
 *   [INPUT] t=<s> handles=<h0>,<h1>,<h2>,<h3> wall=<s>
 * whenever one changes. Checked once per XGetDeviceChanges, i.e. once a
 * frame, so a port opened on this frame's insert mask shows on the next. */
#define PAD_STRUCT_VA     0x00EBD278u
#define PAD_STRUCT_STRIDE 0x1E4u
#define PAD_HANDLE_OFF    0x88u

static void trace_handles(void)
{
    static int on = -1;
    static uint32_t last[4];
    uint32_t h[4];
    if (on < 0) {
        const char *e = recomp_env(RENV_INPUT_TRACE);
        on = e && *e && *e != '0';
    }
    if (!on) return;
    for (int i = 0; i < 4; i++)
        h[i] = guest_read(PAD_STRUCT_VA + i * PAD_STRUCT_STRIDE + PAD_HANDLE_OFF);
    if (memcmp(h, last, sizeof h)) {
        memcpy(last, h, sizeof h);
        fprintf(stderr, "[INPUT] t=%.3f handles=0x%X,0x%X,0x%X,0x%X wall=%.6f\n",
                t_now(), h[0], h[1], h[2], h[3], wall_s());
        fflush(stderr);
    }
}

uint32_t cat_pad_connected_mask(void)
{
    uint32_t m;
    init_once();
    LOCK();
    m = connected_mask_now();
    if (m != g_mask_last) {
        g_mask_last = m;
        fprintf(stderr, "[INPUT] t=%.3f ports=0x%X wall=%.6f\n", t_now(), m, wall_s());
        fflush(stderr);
    }
    trace_handles();
    UNLOCK();
    return m;
}

int cat_pad_get_state(uint32_t port, uint8_t out[18], uint32_t *packet)
{
    XBOX_GAMEPAD g;
    double t;
    int connected = 0;

    init_once();
    if (port > 3) return 0;
    memset(&g, 0, sizeof g);
    LOCK();
    if (!g_started) { g_started = 1; g_t0 = now_s(); }
    t = now_s() - g_t0;
    if (port == 0 && g_script_on) {
        XBOX_GAMEPAD before = g_script;
        while (g_next < g_nev && g_ev[g_next].t <= t) {
            set_button(g_ev[g_next].button, g_ev[g_next].value);
            g_next++;
        }
        g_poll++;
        for (int i = 0; i < g_nrel;)
            if (g_rel[i].poll >= 0 ? g_poll >= g_rel[i].poll : g_rel[i].t <= t) {
                set_button(g_rel[i].button, 0);
                g_rel[i] = g_rel[--g_nrel];
            } else i++;
        run_steps(t);
        if (memcmp(&before, &g_script, sizeof before)) log_state(t, &g_script);
        fflush(stderr);
        g = g_script;
        connected = 1;
    }
    if (g_host_on) {
        XBOX_INPUT_STATE hs;
        g_probe_t[port] = now_s();
        if (xbox_InputGetState(port, &hs) == 0) {
            const XBOX_GAMEPAD *h = &hs.Gamepad;
            if (memcmp(h, &g_host_last[port], sizeof *h)) {
                g_host_last[port] = *h;
                log_host_state(t, port, h);
                fflush(stderr);
            }
            g.wButtons |= h->wButtons;
            for (int i = 0; i < 8; i++)
                if (h->bAnalogButtons[i] > g.bAnalogButtons[i])
                    g.bAnalogButtons[i] = h->bAnalogButtons[i];
            if (!g.sThumbLX) g.sThumbLX = h->sThumbLX;
            if (!g.sThumbLY) g.sThumbLY = h->sThumbLY;
            if (!g.sThumbRX) g.sThumbRX = h->sThumbRX;
            if (!g.sThumbRY) g.sThumbRY = h->sThumbRY;
            connected = 1;
        }
    }
    /* The packet number moves only when the state does, as on hardware. */
    if (memcmp(&g, &g_last[port], sizeof g)) {
        g_last[port] = g;
        g_packet[port]++;
    }
    *packet = g_packet[port];
    UNLOCK();

    /* XINPUT_GAMEPAD, packed little-endian: wButtons, bAnalogButtons[8],
     * sThumbLX, sThumbLY, sThumbRX, sThumbRY. */
    out[0] = (uint8_t)g.wButtons; out[1] = (uint8_t)(g.wButtons >> 8);
    memcpy(out + 2, g.bAnalogButtons, 8);
    {
        SHORT ax[4] = { g.sThumbLX, g.sThumbLY, g.sThumbRX, g.sThumbRY };
        for (int i = 0; i < 4; i++) {
            out[10 + 2 * i] = (uint8_t)ax[i];
            out[11 + 2 * i] = (uint8_t)((uint16_t)ax[i] >> 8);
        }
    }
    return connected;
}

/* The title's XInputSetState motor words (XINPUT_FEEDBACK +0x42/+0x44, see
 * recomp_manual.c), forwarded only to a port with a host controller on it:
 * a scripted port, the keyboard or an empty port has nothing to shake, and
 * the title's feedback still completes. RECOMP_RUMBLE=0 forwards nothing. */
void cat_pad_rumble(uint32_t port, uint16_t left, uint16_t right)
{
    static uint32_t last[4] = { 0, 0, 0, 0 };
    int fwd;

    /* Under the lock like cat_pad_get_state: last[] and the backend call are
     * then never raced by another guest thread. Same lock order as there
     * (this lock, then the toolkit's), and nothing here re-enters it. */
    init_once();
    LOCK();
    fwd = g_rumble_on && g_host_on && port < 4 && xbox_InputIsConnected(port);

    /* One line per change of a port's motor words: the title re-sends the
     * same values every frame while a rumble plays. */
    if (port < 4 && last[port] != ((uint32_t)left << 16 | right)) {
        last[port] = (uint32_t)left << 16 | right;
        fprintf(stderr, "[INPUT] rumble port=%u left=%u right=%u %s\n",
                port, left, right, fwd ? "sent" : "not sent");
        fflush(stderr);
    }
    if (fwd) {
        XBOX_VIBRATION v = { left, right };
        xbox_InputSetState(port, &v);
    }
    UNLOCK();
}
