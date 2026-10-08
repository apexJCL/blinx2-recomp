/**
 * Manual function overrides and ICALL diagnostics
 *
 * This file provides:
 *   - recomp_lookup_manual()  : intercept specific Xbox VAs with hand-written code
 *   - recomp_icall_fail_log() : log when an indirect call target can't be resolved
 *   - ICALL trace ring buffer  : globals used by the RECOMP_ICALL macro
 *
 * The recomp pipeline generates an auto-dispatch table (recomp_lookup) that
 * resolves most function addresses. recomp_lookup_manual() is called FIRST,
 * giving you a chance to override any function with a custom implementation.
 *
 * Common reasons to add manual overrides:
 *   - Trace a function to understand call flow (wrap the generated version)
 *   - Fix a function the lifter translated incorrectly
 *   - Stub out a function that crashes (return early, set eax to a safe value)
 *   - Redirect a function to a native implementation (e.g., skip CRT init)
 *   - Intercept D3D/audio calls for custom rendering or sound
 */

#include <stdio.h>
#include "recomp_env.h"
#include "host_time.h"  /* xbox_HostNowNs, xbox_HostSleepNs: the vblank pacer */
#include <stddef.h>   /* ptrdiff_t: <windows.h> supplied it on Windows only */
#include <stdint.h>
#include "glow.h"       /* fx.glow: the sub_0005B7D0 wrapper below */
/* The pacer's interlocked epoch. Before recomp_types.h, whose register
 * macros (eax, esp, ...) would otherwise reach the system headers. */
#ifdef _WIN32
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#endif

/* ── ICALL trace ring buffer ───────────────────────────────── */

/*
 * These globals are written by the RECOMP_ICALL macro (defined in
 * recomp_types.h) every time an indirect call is dispatched. When a
 * crash occurs, the VEH handler or recomp_icall_fail_log() can dump
 * the last 16 call targets to help you trace what happened.
 *
 * The runtime owns them: xbox_kernel defines all three in
 * src/kernel/xbox_memory_layout.c, and recomp_types.h declares them extern.
 * Declare, do not define -- a definition here as well is a duplicate symbol,
 * and a project built from the toolkit's template failed to link on all three:
 *
 *   xbox_memory_layout.obj : error LNK2005: g_icall_count already defined
 *                            in recomp_manual.obj
 */
extern volatile uint32_t g_icall_trace[16];
extern volatile uint32_t g_icall_trace_idx;
extern volatile uint64_t g_icall_count;

typedef void (*recomp_func_t)(void);

/* ── Register state (defined in xbox_memory_layout.c) ──────── */

/* The generated header, for the register model and MEM32. The registers are
 * thread-local there, so a plain `extern uint32_t g_eax` here would not even
 * name the same object. */
#include "gen/recomp_types.h"

/* ── Manual function overrides ─────────────────────────────── */

/*
 * Return a function pointer to override the given Xbox VA, or NULL
 * to fall through to the auto-generated dispatch table.
 *
 * This is called on every indirect call (RECOMP_ICALL) and every
 * direct call through the dispatch table, so keep it fast. A chain
 * of if-statements on uint32_t compiles to a simple comparison
 * sequence; for large override tables, consider a sorted array
 * with binary search.
 *
 * Examples of common override patterns:
 *
 *   // Trace wrapper: log entry/exit around the generated function
 *   extern void sub_00012345(void);
 *   static void traced_sub_00012345(void) {
 *       fprintf(stderr, "[TRACE] sub_00012345 entered, eax=0x%08X\n", g_eax);
 *       sub_00012345();
 *       fprintf(stderr, "[TRACE] sub_00012345 returned, eax=0x%08X\n", g_eax);
 *   }
 *
 *   // Stub: skip a function entirely (return 0 in eax)
 *   static void stub_00067890(void) {
 *       g_eax = 0;
 *   }
 *
 *   // Fix: replace a broken lifted function with correct C
 *   static void fixed_sub_000ABCDE(void) {
 *       // Read arguments from stack/registers per calling convention
 *       uint32_t arg1 = g_ecx;
 *       uint32_t arg2 = MEM32(g_esp + 4);
 *       // ... correct implementation ...
 *       g_eax = result;
 *   }
 */
recomp_func_t recomp_lookup_manual(uint32_t xbox_va)
{
    /*
     * BLiNX 2 needs no overrides here at present. The hand-written XDK
     * replacements below (sub_002E0DB0, sub_00367EEC, ...) replace the
     * generated functions by name instead: scripts/pipeline.sh passes this
     * file to --exclude-manual, so the generator skips them. An override
     * here would be one line per VA, e.g.:
     *
     *   if (xbox_va == 0x00012345) return traced_sub_00012345;
     */

    (void)xbox_va;
    return (recomp_func_t)0;
}

/* ── XDK D3D8: vertical blank ──────────────────────────────────
 *
 * sub_002E0DB0 is D3DDevice_BlockUntilVerticalBlank: clear the device's
 * vblank KEVENT (device + 0x1DBC, SignalState at + 0x1DC0) and wait on it with
 * no timeout. On hardware the NV2A vblank interrupt (vector 3, ISR 0x002EA2E0)
 * signals it from a DPC. main.c turns the toolkit's vblank interrupt on
 * (RECOMP_VBLANK) for the title's vblank callback, so that DPC does run here,
 * but this wait still cannot rely on it: the event lives in D3D's .bss, and
 * the function clears it with a plain store to SignalState rather than
 * KeClearEvent, which the host event the kernel bridge shadows it with never
 * sees. The toolkit's stated remedy is to replace the D3D8 entry point that
 * owns the wait (kernel_bridge.c, the KeConnectInterrupt note); this one
 * becomes a 60 Hz pacer. Callers: the .text thunk sub_002A1870 (the ADX
 * threads) and the AvSetDisplayMode step loop in sub_002E6660.
 *
 * Defining it as `void sub_002E0DB0(void)` is what makes recomp leave it out
 * of gen/ (pipeline.sh recomp passes --exclude-manual this file). */
#define VBLANK_HZ 60

void sub_002E0DB0(void)
{
    /* Vblank N is at epoch + N * period, the same instants for every caller.
     * Two ADX threads wait here (the vsync server, sub_002A1B20, and its
     * sibling sub_002A1BA0), and on hardware the notification event wakes
     * both on every vblank. A pacer keeping one "next vblank" for all callers
     * gave each thread every other vblank, so the ADX server ran at 30 Hz
     * while ADXT_SetSvrFreq(60) sized its per-call decode for 60: the movie's
     * audio was supplied at ~0.75x real time and the voice ring kept running
     * dry (speech cut off in the attract movie). */
    static volatile uint64_t epoch;
    const uint64_t period = 1000000000u / VBLANK_HZ;
    uint64_t now = xbox_HostNowNs(), e = epoch, next;

    if (!e) {
        e = now;
#ifdef _WIN32
        InterlockedCompareExchange64((volatile LONG64 *)&epoch, (LONG64)e, 0);
#else
        __sync_val_compare_and_swap(&epoch, 0, e);
#endif
        e = epoch;
    }
    /* The first boundary strictly after now. */
    next = e + ((now - e) / period + 1) * period;
    /* The toolkit's clock (platform/host_time.h): a high-resolution
     * waitable timer on Windows, where Sleep rounds to the 15.6 ms tick. */
    xbox_HostSleepNs(next - now);

    {
        uint32_t device = MEM32(0x2F1FB8);
        if (device)
            MEM32(device + 0x1DC0) = 0;   /* as the original leaves it */
    }
    g_eax = 0;           /* STATUS_SUCCESS from the wait it replaces */
    g_esp += 4;          /* ret: 0 params */
}

/* ── XDK XInput (XPP library): scripted and host pads on ports 0-3 ──────
 *
 * The title reads the pad through the XDK's XInput entry points, translated
 * from the XPP section. Behind them is the XAPI USB stack (OHCI host
 * controller, XID class driver), which nothing here enumerates, so no device
 * ever arrives. Rather than bring the USB stack up, the seven entry points
 * the game calls are replaced: a gamepad is reported on each port that has a
 * source, and its state comes from src/pad_input.c (a script,
 * RECOMP_INPUT_SCRIPT, on port 0, merged with host controller N on port N).
 * Identified from the bodies and their callers (game input module
 * sub_0021C190 init / sub_0021C290 per-frame poll, rumble sub_0021C710):
 *
 *   sub_00367EEC  XGetDevices(PXPP_DEVICE_TYPE)               stdcall 1
 *   sub_00367F0E  XGetDeviceChanges(type, &ins, &rem)         stdcall 3
 *   sub_0036821D  XInputOpen(type, port, slot, params)        stdcall 4
 *   sub_00368273  XInputClose(handle)                         stdcall 1
 *   sub_0036827F  XInputGetCapabilities(handle, caps)         stdcall 2
 *   sub_00368457  XInputGetState(handle, state)               stdcall 2
 *   sub_003684CA  XInputSetState(handle, feedback)            stdcall 2
 *
 * XPP_DEVICE_TYPE (the XDK's private struct behind XDEVICE_TYPE_*) is
 *   +0 CurrentConnected   ports with a device now (bit N = port N)
 *   +4 ChangeConnected    ports that changed since the last XGetDeviceChanges
 *   +8 PreviousConnected  CurrentConnected as of that call
 * The game passes 0x00366B90 (XDEVICE_TYPE_GAMEPAD) for pads everywhere.
 * It also enumerates memory units, 0x00366B10 (XDEVICE_TYPE_MEMORY_UNIT,
 * from sub_001B7B60 before a save; bit N = port N top slot, bit N+16 = the
 * bottom slot): that and any other type keeps the library semantics on the
 * guest struct and, since nothing plugs one in, reports nothing, so the save
 * menus offer only the hard disk.
 *
 * Ports follow cat_pad_connected_mask() (src/pad_input.c): a port is
 * inserted exactly while it has a source (the script or the keyboard on
 * port 0, host controller N on port N), so the title opens and closes ports
 * itself from the insert/remove masks, as it would on hardware.
 *
 * Defining these is what makes recomp declare rather than emit them (see
 * sub_002E0DB0): adding or removing one needs `pipeline.sh recomp`. */
#define XDEVICE_TYPE_GAMEPAD_VA 0x00366B90u
#define PAD_HANDLE_BASE         0xFADE0000u   /* opaque; the game never derefs */

extern uint32_t cat_pad_connected_mask(void);
extern int      cat_pad_get_state(uint32_t port, uint8_t gamepad[18],
                                  uint32_t *packet);
extern void     cat_pad_rumble(uint32_t port, uint16_t left, uint16_t right);

/* Hot-plug the pads the host side has, the way the XID driver would. */
static void pad_plug(uint32_t type)
{
    if (type == XDEVICE_TYPE_GAMEPAD_VA) {
        uint32_t want = cat_pad_connected_mask();
        uint32_t cur  = MEM32(type);
        if ((cur & 0xF) != want) {
            MEM32(type)     = (cur & ~0xFu) | want;
            MEM32(type + 4) |= (cur ^ want) & 0xF;
        }
    }
}

/* XGetDevices */
void sub_00367EEC(void)
{
    uint32_t type = MEM32(g_esp + 4), cur;
    pad_plug(type);
    cur = MEM32(type);
    MEM32(type + 4) = 0;
    MEM32(type + 8) = cur;
    g_eax = cur;
    g_esp += 8;
}

/* XGetDeviceChanges */
void sub_00367F0E(void)
{
    uint32_t type = MEM32(g_esp + 4);
    uint32_t pins = MEM32(g_esp + 8), prem = MEM32(g_esp + 12);
    uint32_t cur, chg, prev, ins, rem, both;

    pad_plug(type);
    cur = MEM32(type); chg = MEM32(type + 4); prev = MEM32(type + 8);
    if (!chg) {
        MEM32(pins) = 0; MEM32(prem) = 0;
        g_eax = 0;
    } else {
        ins  = cur & ~prev;
        rem  = prev & ~cur;
        both = chg & prev & cur;           /* out and back in since last call */
        MEM32(pins) = ins | both;
        MEM32(prem) = rem | both;
        MEM32(type + 4) = 0;
        MEM32(type + 8) = cur;
        g_eax = (ins | rem | both) ? 1 : 0;
    }
    g_esp += 16;
}

/* XInputOpen */
void sub_0036821D(void)
{
    uint32_t type = MEM32(g_esp + 4), port = MEM32(g_esp + 8);
    g_eax = (type == XDEVICE_TYPE_GAMEPAD_VA && port < 4
             && (cat_pad_connected_mask() >> port & 1))
          ? PAD_HANDLE_BASE + port : 0;
    g_esp += 20;
}

/* XInputClose */
void sub_00368273(void)
{
    g_esp += 8;
}

/* XInputGetCapabilities
 *
 * XINPUT_CAPABILITIES, packed (25 bytes):
 *   +0x00 BYTE  SubType           XINPUT_DEVSUBTYPE_GC_GAMEPAD (1)
 *   +0x01 WORD  Reserved
 *   +0x03 XINPUT_GAMEPAD In.Gamepad   a mask of what the device has:
 *         +0x03 wButtons 0x00FF  (d-pad, START, BACK, both thumb clicks)
 *         +0x05 bAnalogButtons[8] 0xFF each (A B X Y BLACK WHITE L R)
 *         +0x0D sThumbLX/LY/RX/RY 0xFFFF each (four axes)
 *   +0x15 XINPUT_RUMBLE Out.Rumble  wLeftMotorSpeed, wRightMotorSpeed 0xFFFF
 * That is a Duke: every input and both motors present. A handle that is not
 * ours, or a port whose source has gone, is not connected. */
void sub_0036827F(void)
{
    uint32_t h = MEM32(g_esp + 4), caps = MEM32(g_esp + 8), i;

    if ((h & ~3u) != PAD_HANDLE_BASE || !(cat_pad_connected_mask() >> (h & 3) & 1)) {
        g_eax = 0x48F;                     /* ERROR_DEVICE_NOT_CONNECTED */
        g_esp += 12;
        return;
    }
    MEM8(caps) = 1;                        /* XINPUT_DEVSUBTYPE_GC_GAMEPAD */
    MEM16(caps + 0x01) = 0;
    MEM16(caps + 0x03) = 0x00FF;           /* the eight digital buttons */
    for (i = 0; i < 8; i++)
        MEM8(caps + 0x05 + i) = 0xFF;      /* eight analog buttons */
    for (i = 0; i < 4; i++)
        MEM16(caps + 0x0D + 2 * i) = 0xFFFF;   /* four stick axes */
    MEM16(caps + 0x15) = 0xFFFF;           /* left (low-frequency) motor */
    MEM16(caps + 0x17) = 0xFFFF;           /* right (high-frequency) motor */
    g_eax = 0;
    g_esp += 12;
}

/* XInputGetState */
void sub_00368457(void)
{
    uint32_t h = MEM32(g_esp + 4), st = MEM32(g_esp + 8), i, packet = 0;
    uint8_t gp[18];

    if ((h & ~3u) != PAD_HANDLE_BASE
        || !cat_pad_get_state(h & 3, gp, &packet)) {
        g_eax = 0x48F;                     /* ERROR_DEVICE_NOT_CONNECTED */
    } else {
        MEM32(st) = packet;
        for (i = 0; i < 18; i++) MEM8(st + 4 + i) = gp[i];
        g_eax = 0;
    }
    g_esp += 12;
}

/* XInputSetState */
void sub_003684CA(void)
{
    uint32_t h = MEM32(g_esp + 4), fb = MEM32(g_esp + 8);
    /* XINPUT_FEEDBACK: a 0x42-byte header (dwStatus, hEvent, ...), then the
     * rumble motors. Complete synchronously: the game skips a new request
     * while dwStatus is still ERROR_IO_PENDING (0x3E5). */
    if ((h & ~3u) != PAD_HANDLE_BASE) {
        /* Not a handle XInputOpen gave out: no device behind it. The status
         * is final too, so a caller waiting on 0x3E5 does not spin. */
        MEM32(fb) = 0x48F;              /* ERROR_DEVICE_NOT_CONNECTED */
        g_eax = 0x48F;
        g_esp += 12;
        return;
    }
    cat_pad_rumble(h & 3, MEM16(fb + 0x42), MEM16(fb + 0x44));
    MEM32(fb) = 0;
    g_eax = 0;
    g_esp += 12;
}

/* ── ICALL failure logging ─────────────────────────────────── */

/*
 * Called when RECOMP_ICALL cannot resolve a target address.
 * This usually means one of:
 *   - A vtable dispatch to an address not in the dispatch table
 *   - A function pointer loaded from uninitialized or corrupt memory
 *   - A kernel thunk address that the bridge doesn't handle
 *
 * During early bring-up you will see many of these. Most are harmless
 * (the ICALL macro pops the dummy return address and continues).
 * Focus on the ones that cause crashes or incorrect behavior.
 */
void recomp_icall_fail_log(uint32_t va)
{
    fprintf(stderr, "[ICALL] Failed to resolve VA 0x%08X (total calls: %llu)\n",
            va, (unsigned long long)g_icall_count);

    /* Dump last 16 call targets from the ring buffer */
    fprintf(stderr, "  Recent ICALL targets:\n");
    for (int i = 0; i < 16; i++) {
        int idx = (g_icall_trace_idx - 16 + i) & 15;
        if (g_icall_trace[idx])
            fprintf(stderr, "    [%2d] 0x%08X\n", i, g_icall_trace[idx]);
    }
    fflush(stderr);
}

/* An indirect call whose target is not code: a null or wild function pointer.
 *
 * Skipping these is right -- calling a data address is worse -- but skipping
 * them *silently* is not. They almost always arrive inside a loop, so the
 * symptom is a hang with no output rather than a diagnosable null vtable call.
 *
 * Rate-limited per address: a spin can produce millions of these, and the
 * useful information is which addresses occur, not how often.
 */
void recomp_icall_not_code_log(uint32_t va)
{
    enum { SLOTS = 16 };
    static uint32_t seen[SLOTS];
    static uint64_t hits[SLOTS];
    static int count;
    int i;

    for (i = 0; i < count; i++)
        if (seen[i] == va)
            break;
    if (i == count) {
        if (count == SLOTS)
            return;
        seen[count] = va;
        hits[count] = 0;
        count++;
    }
    hits[i]++;
    /* Report at 1, 10, 100, 1000 ... rather than once. A single line says a
     * wild pointer was skipped; the progression says it is being skipped in a
     * loop, which is the difference between a curiosity and the reason the
     * title is hung. */
    {
        uint64_t n = hits[i];
        while (n >= 10 && n % 10 == 0)
            n /= 10;
        if (n != 1)
            return;
    }
    fprintf(stderr, "[ICALL] target 0x%08X is not code -- skipped %llu time(s) "
                    "(null or wild function pointer, at call #%llu)\n",
            va, (unsigned long long)hits[i],
            (unsigned long long)g_icall_count);
    fflush(stderr);
}

/* ── Untranslated instructions ───────────────────────────────────────────
 *
 * The lifter emits RECOMP_UNIMPL(text, va) at every instruction it has no
 * translation for, in place of the bare comment it used to leave. The
 * instruction is still a no-op; this only stops the omission being silent.
 * RECOMP_UNIMPL_TRAP=1 aborts at the first hit, at the guest address of the
 * cause rather than wherever the damage surfaces. */
#include <stdlib.h>
#include "unimpl_budget.h"

/* Lines per site before only hits 10, 100, 1000 ... print. Override with
 * RECOMP_TRACE=unimpl_budget=n, like kernel_budget; the first hit of a site
 * prints whatever n is (see unimpl_budget.h). */
static long unimpl_log_budget(void)
{
    static long budget = -1;

    if (budget < 0) {
        const char *env = recomp_env(RENV_UNIMPL_BUDGET);
        budget = env ? strtol(env, NULL, 0) : 3;
        if (budget < 1)
            budget = 1;
    }
    return budget;
}

void recomp_unimpl(const char *text, uint32_t va)
{
    static struct unimpl_budget sites;
    const char *trap = recomp_env(RENV_UNIMPL_TRAP);
    int stop = trap && *trap && *trap != '0';
    uint32_t n = unimpl_budget_hit(&sites, va, unimpl_log_budget());

    if (n || stop) {
        char hit[32] = "";
        if (n == UINT32_MAX)
            snprintf(hit, sizeof hit, ", site table full");
        else if (n > 1)
            snprintf(hit, sizeof hit, ", hit %u", n);
        fprintf(stderr,
                "[UNIMPL] untranslated instruction REACHED: `%s` at 0x%08X"
                " (a no-op%s; set RECOMP_DEBUG=unimpl_trap to stop here)\n",
                text, va, hit);
        fflush(stderr);
    }
    if (stop) abort();
}


/* ── fx.glow: the weight of the mode-3 glow pass ─────────────────────────
 *
 * sub_0005B7D0 (one caller, sub_0005B550 in post mode 3) screen-blends a
 * 4-tap blur of the 320x240 downsample over the frame, with the game's glow
 * weight 0xADC744 as the quad's vertex colour. The generator emits its body
 * as sub_0005B7D0_gen (the extern below, tools/recomp/manual_scan.py) and
 * every call lands here.
 *
 * At the defaults (glow on, intensity 1) this is the generated body and
 * nothing else: the guest is never touched. Otherwise the weight is scaled
 * (glow.c says why by a cube root) for the call only. `off` is weight 0, not
 * a skipped call: a zero vertex colour makes every combiner stage 0, and the
 * screen blend d + 0*(1-d) leaves the frame's bytes as they were on every
 * backend, while the D3D state the pass sets and sub_0005B550 resets stays
 * exactly as stock.
 *
 * The game's value goes back afterwards because sub_000E4140 fades the word
 * from whatever it holds each frame. The restore happens only if the word
 * still holds the scaled value, so a write by another thread is kept. Every
 * path out of the body is its one ret, so the restore always runs. */

extern void sub_0005B7D0_gen(void);

void sub_0005B7D0(void)
{
    uint32_t orig, scaled;

    if (!glow_active()) {
        RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0_gen);
        return;
    }
    orig = MEM32(0xADC744);
    scaled = glow_weight(orig, glow_factor());
    {
        /* One line, so a run can place the wrapper's stack against the
         * game's writers of the word (RECOMP_DEBUG=watch=0xADC744). */
        static int said;
        if (!said) {
            said = 1;
            fprintf(stderr, "[GLOW] weight %08X -> %08X esp=%08X\n",
                    orig, scaled, g_esp);
        }
    }
    if (scaled == orig) {
        RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0_gen);
        return;
    }
    MEM32(0xADC744) = scaled;
    RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0_gen);
    if (MEM32(0xADC744) == scaled)
        MEM32(0xADC744) = orig;
}
