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
#include "kernel.h"     /* xbox_GuestCpuRelease/Acquire: the pacer's sleep lets the guest CPU go */
#include <stddef.h>   /* ptrdiff_t: <windows.h> supplied it on Windows only */
#include <stdint.h>
#include "glow.h"       /* fx.glow: the sub_0005B7D0 wrapper below */
#include "free_camera.h"  /* camera.free: the view builders, pad poll and freeze below */
#include "nv2a_backend_common.h"  /* nv2a_host_opts: display.aspect, the sub_0003B180 wrapper */
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
     * waitable timer on Windows, where Sleep rounds to the 15.6 ms tick.
     * A host sleep, not a kernel call: let the guest CPU go for it
     * (RECOMP_GUEST_LOCK), or the ADX threads sleeping here would hold it
     * for a vblank each while the main thread and the movie decoder wait
     * (the title movie behind the story slot list ran at 15 fps). */
    {
        int held = xbox_GuestCpuRelease(XBOX_GUEST_CPU_HOST, 0x002E0DB0u);
        xbox_HostSleepNs(next - now);
        if (held)
            xbox_GuestCpuAcquire();
    }

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
 * RECOMP_INPUT_SCRIPT, on port 0, merged with the host controller pad_slots
 * puts on each port, src/pad_slots.h).
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
 * port 0, the host controller pad_slots puts on that port, src/pad_slots.h),
 * so the title opens and closes ports itself from the insert/remove masks,
 * as it would on hardware.
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
#include <string.h>
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



/* ── Free camera: the game camera's view builds ─────────────────────────
 *
 * The game camera is one struct, [0x4B271C] (0x039B4C20 in stage 1-1):
 * position p at +0x00, angles at +0x0C..+0x1C (+0x0C pitch, +0x10 yaw,
 * +0x14 roll), the eye written back at +0x2C, a shake offset o at +0x38.
 * Two functions turn it into the D3D view global 0xA72380, then call
 * SetTransform(VIEW) (sub_002E0B90 state 0) and sub_00042AE0 (projection
 * 0xAC1870, the four side cull planes from sub_0003B180, the inverse view
 * 0xA9C220):
 *
 *   sub_000292A0 (ebx = camera; from sub_0002DD40, the per-viewport pass
 *   setup): V = T(-(p - o)) . RotY(a1c) . RotX(-a18) . RotY(a10) . RotX(-ac)
 *   . RotZ(-a14), and it writes the eye p - o to +0x2C;
 *
 *   sub_0021B1F0 (from sub_00216D70, which the stage passes sub_00068E70 and
 *   sub_000693E9 call): the same rotations without a18/a1c, from the eye at
 *   +0x2C. It runs after the first, so its view is the one the stage's
 *   models are drawn with: a view changed in sub_000292A0 alone does not
 *   reach the screen (runs/free-cam-m0, fix-offset vs log).
 *
 * Every model's world x view (0xAAD3A0, sub_0003B5C0), the bone palettes
 * stored from it (sub_00038B00), the c[112] light (sub_000348A0 through
 * sub_0003FC40) and the cull's view-space centres (sub_0003B750) are taken
 * from 0xA72380 after these calls, so a view substituted in both reaches
 * all of them (hook 1a, openspec change free-camera D1).
 *
 * camera.free (free_camera.c) and RECOMP_DEBUG=cam_fix=... substitute
 * their camera the same way: for each build of the game camera the fields
 * are swapped in, the generated body runs, and each field is put back if it
 * still holds what was swapped in (a field the build or a callee changed
 * keeps the new value). The eye after sub_000292A0 is what the build
 * writes from the game's own p and o, exactly what stock writes. A depth
 * counter keeps a nested build from swapping twice. RECOMP_DEBUG=cam_log=n
 * prints the camera, V, the projection and the cull planes every n-th
 * build, and each camera other than the game's once. None of them active:
 * the generated bodies and nothing else. */

extern void sub_000292A0_gen(void);
extern void sub_0021B1F0_gen(void);

/* The camera fields a build reads or writes: +0x00..+0x1C (p, angles;
 * +0x20 is saved with them), +0x2C..+0x34 (eye), +0x38..+0x40 (o). */
#define CAM_NF 15
static const uint16_t s_cam_off_of[CAM_NF] = {
    0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20,
    0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40,
};

static int      s_cam_init;
static unsigned s_cam_log_every;           /* 0: no log */
static int      s_cam_fix;                 /* 0 off, 1 offset, 2 hold */
static float    s_cam_off[5];              /* dx, dy, dz, dyaw (+0x10), dpitch (+0x0C) */
static unsigned s_cam_hold_at;
static float    s_cam_held[CAM_NF];
static int      s_cam_have_held;
static unsigned s_cam_calls;
static int      s_cam_depth;               /* builds in progress (guest thread) */
static uint32_t s_cam_other[8];            /* other cameras logged once */

static void cam_debug_init(void)
{
    const char *e;

    s_cam_init = 1;
    e = recomp_env(RENV_CAM_LOG);
    if (e && *e) {
        s_cam_log_every = (unsigned)strtoul(e, NULL, 0);
        if (s_cam_log_every == 0)
            s_cam_log_every = 1;
    }
    e = recomp_env(RENV_CAM_FIX);
    if (e && *e) {
        if (!strncmp(e, "hold", 4)) {
            s_cam_fix = 2;
            s_cam_hold_at = e[4] == ':' ? (unsigned)strtoul(e + 5, NULL, 0) : 300;
        } else {
            int i;
            char *end = (char *)e;
            s_cam_fix = 1;
            for (i = 0; i < 5 && *end; i++) {
                s_cam_off[i] = strtof(end, &end);
                if (*end == ':')
                    end++;
            }
        }
        fprintf(stderr, "[CAM] cam_fix mode %d (hold at %u; offset %g %g %g yaw %g pitch %g)\n",
                s_cam_fix, s_cam_hold_at, s_cam_off[0], s_cam_off[1], s_cam_off[2],
                s_cam_off[3], s_cam_off[4]);
    }
}

static void cam_log_mat(const char *name, uint32_t va)
{
    int r;
    for (r = 0; r < 4; r++)
        fprintf(stderr, "[CAM]  %s r%d % .5f % .5f % .5f % .5f\n", name, r,
                MEMF(va + r * 16), MEMF(va + r * 16 + 4), MEMF(va + r * 16 + 8),
                MEMF(va + r * 16 + 12));
}

static void cam_log(const char *who, uint32_t cam, uint32_t ret)
{
    const uint32_t V = 0xA72380u;
    float t[3], eye[3];
    int i, j;

    if (!cam)
        return;
    for (i = 0; i < 3; i++)
        t[i] = MEMF(V + 0x30 + i * 4);
    /* V = T(-eye) . R, so eye = -t . R^T. */
    for (j = 0; j < 3; j++) {
        eye[j] = 0.0f;
        for (i = 0; i < 3; i++)
            eye[j] -= t[i] * MEMF(V + j * 16 + i * 4);
    }
    fprintf(stderr,
            "[CAM] %s %u cam=%08X ret=%08X p=(%.3f %.3f %.3f) ang c=%.4f 10=%.4f 14=%.4f"
            " 18=%.4f 1c=%.4f o=(%.3f %.3f %.3f) eye+2c=(%.3f %.3f %.3f) eyeV=(%.3f %.3f %.3f)"
            " vp=%gx%g c=(%g %g) focal=%g far=%g farcull=%u camptr=%08X\n",
            who, s_cam_calls, cam, ret, MEMF(cam), MEMF(cam + 4), MEMF(cam + 8),
            MEMF(cam + 0xC), MEMF(cam + 0x10), MEMF(cam + 0x14), MEMF(cam + 0x18),
            MEMF(cam + 0x1C), MEMF(cam + 0x38), MEMF(cam + 0x3C), MEMF(cam + 0x40),
            MEMF(cam + 0x2C), MEMF(cam + 0x30), MEMF(cam + 0x34), eye[0], eye[1], eye[2],
            MEMF(0x888620), MEMF(0xA10C08), MEMF(0xA72438), MEMF(0xAAF440),
            MEMF(0x885BC0), MEMF(0xA88498), MEM32(0x881080), MEM32(0x4B271C));
    cam_log_mat("V", V);
    cam_log_mat("P", 0xAC1870u);
    cam_log_mat("Vinv", 0xA9C220u);
    for (i = 0; i < 4; i++)
        fprintf(stderr, "[CAM]  plane%d % .5f % .5f % .5f\n", i,
                MEMF(0xA0019Cu + i * 12), MEMF(0xA0019Cu + i * 12 + 4),
                MEMF(0xA0019Cu + i * 12 + 8));
}

/* A build of a camera other than the game's: logged once per struct under
 * cam_log, so the cases are known; never substituted. */
static void cam_note_other(uint32_t cam, uint32_t ret)
{
    unsigned i;

    if (!s_cam_log_every || !cam)
        return;
    for (i = 0; i < sizeof s_cam_other / sizeof s_cam_other[0]; i++) {
        if (s_cam_other[i] == cam)
            return;
        if (!s_cam_other[i]) {
            s_cam_other[i] = cam;
            fprintf(stderr, "[CAM] build292A0 of another camera %08X (game %08X) from %08X\n",
                    cam, MEM32(0x4B271Cu), ret);
            return;
        }
    }
}

/* The fields to swap in for the game camera: the free camera's when it
 * flies (o = 0, the eye = p, roll and the extra angles 0, +0x20 the
 * game's), else the debug camera's. 0 when neither: nothing to swap. */
static int cam_fields(const float *saved, float *f)
{
    struct fc_cam fc;
    int i;

    memcpy(f, saved, CAM_NF * sizeof f[0]);
    if (free_cam_view(&fc)) {
        for (i = 0; i < 3; i++) {
            f[i] = fc.p[i];
            f[9 + i] = fc.p[i];
            f[12 + i] = 0.0f;
        }
        f[3] = fc.pitch;
        f[4] = fc.yaw;
        f[5] = f[6] = f[7] = 0.0f;
        return 1;
    }
    if (s_cam_fix == 2 && !s_cam_have_held && s_cam_calls >= s_cam_hold_at) {
        memcpy(s_cam_held, saved, sizeof s_cam_held);
        s_cam_have_held = 1;
        fprintf(stderr, "[CAM] holding the camera from build %u\n", s_cam_calls);
    }
    if (s_cam_fix == 2 && s_cam_have_held) {
        memcpy(f, s_cam_held, sizeof s_cam_held);
        return 1;
    }
    if (s_cam_fix == 1) {
        for (i = 0; i < 3; i++) {
            f[i] += s_cam_off[i];
            f[9 + i] += s_cam_off[i];          /* the eye moves with p */
        }
        f[4] += s_cam_off[3];
        f[3] += s_cam_off[4];
        return 1;
    }
    return 0;
}

static int cam_same(float a, float b)
{
    uint32_t x, y;
    memcpy(&x, &a, 4);
    memcpy(&y, &b, 4);
    return x == y;
}

/* Put the game's fields back where they still hold what f swapped in.
 * After sub_000292A0 (eye_from_p) the eye is what that build writes, f's
 * p - o: it gets the game's own p - o, as stock writes it. */
static void cam_swap_out(uint32_t cam, const float *saved, const float *f, int eye_from_p)
{
    int i;

    for (i = 0; i < CAM_NF; i++) {
        uint32_t va = cam + s_cam_off_of[i];
        int eye = i >= 9 && i < 12;

        if (eye && eye_from_p) {
            if (cam_same(MEMF(va), f[i - 9] - f[i + 3]))
                MEMF(va) = saved[i - 9] - saved[i + 3];
        } else if (cam_same(MEMF(va), f[i])) {
            MEMF(va) = saved[i];
        }
    }
}

/* One build of camera cam (the game's when game is set) by gen. */
static void cam_build(uint32_t va, void (*gen)(void), const char *who, uint32_t cam,
                      int game, int eye_from_p)
{
    float saved[CAM_NF], f[CAM_NF];
    uint32_t ret;
    int i, swap = 0;

    if (!s_cam_init)
        cam_debug_init();
    if (!s_cam_log_every && !s_cam_fix && !free_cam_view(NULL)) {
        RECOMP_ABI_CALL(va, gen);
        return;
    }
    ret = MEM32(g_esp);
    s_cam_calls++;
    if (!game)
        cam_note_other(cam, ret);
    if (game && cam && s_cam_depth == 0) {
        for (i = 0; i < CAM_NF; i++)
            saved[i] = MEMF(cam + s_cam_off_of[i]);
        swap = cam_fields(saved, f);
        if (swap)
            for (i = 0; i < CAM_NF; i++)
                MEMF(cam + s_cam_off_of[i]) = f[i];
    }
    s_cam_depth++;
    RECOMP_ABI_CALL(va, gen);
    s_cam_depth--;
    if (swap)
        cam_swap_out(cam, saved, f, eye_from_p);
    if (s_cam_log_every && (s_cam_calls % s_cam_log_every) == 0)
        cam_log(who, cam, ret);
}

void sub_000292A0(void)
{
    uint32_t cam = g_ebx;
    cam_build(0x000292A0u, sub_000292A0_gen, "build292A0", cam, cam == MEM32(0x4B271Cu), 1);
}

void sub_0021B1F0(void)
{
    cam_build(0x0021B1F0u, sub_0021B1F0_gen, "build21B1F0", MEM32(0x4B271Cu), 1, 0);
}

/* ── Free camera: the pad poll, the event system and the stage start ──────
 *
 * sub_0005C930 polls the pads once a frame, from the main loop (0x60375)
 * just before the frame's update and render (sub_00062FB0 at 0x603A2): the
 * mods' frame runs after it, so the camera reads this frame's pad and its
 * hotkeys act before the frame builds its view (D3). The game itself reads
 * a released port 0 while the camera has it (pad_input.c).
 *
 * sub_000EEB40 is the event system, called at 0x652CD in sub_000649B0;
 * its script opcodes write 0xAF0EF4 and nothing on that path reads it
 * (spike.md 9.6). While frozen, the game's own value goes in before it and
 * what it leaves is read back as the value unfreeze restores, so an event
 * that stops the world during a freeze (a write of 1) still holds after
 * F8; then the flag is 1 again.
 *
 * sub_00161120 has one caller, 0x652D7 in sub_000649B0, after the event
 * system and right before the stage update's gate on 0xAF0EF4 at 0x652DC:
 * the freeze re-asserts the flag there too, so a write by sub_001D5FB0 or
 * sub_00161120 does not unfreeze the world.
 *
 * sub_000606F0 starts a stage (sub_00062FB0's state entry, 0x63248) and
 * writes 0 to 0xAF0EF4 itself: a freeze ends there, and the game's value
 * is put back before the stage's own write, so a stale 1 never survives. */

extern void sub_0005C930_gen(void);
extern void sub_000EEB40_gen(void);
extern void sub_00161120_gen(void);
extern void sub_000606F0_gen(void);

void sub_0005C930(void)
{
    RECOMP_ABI_CALL(0x0005C930u, sub_0005C930_gen);
    free_cam_frame();
}

void sub_000EEB40(void)
{
    free_cam_events_pre();
    RECOMP_ABI_CALL(0x000EEB40u, sub_000EEB40_gen);
    free_cam_events_post();
}

void sub_00161120(void)
{
    RECOMP_ABI_CALL(0x00161120u, sub_00161120_gen);
    free_cam_freeze_tick();
}

void sub_000606F0(void)
{
    free_cam_stage_start();
    RECOMP_ABI_CALL(0x000606F0u, sub_000606F0_gen);
}



/* ── Hor+ cull: the side planes of the view frustum ──────────────────────
 *
 * sub_00042AE0 builds the projection (sub_0029EEF2, fov -atan(640/512),
 * aspect 4:3) after every view build, then calls sub_0003B180(fov,
 * -(h/w), zf) at 0x42C78, its one caller. With t = tan(fov/2) it writes
 * the four side-plane normals at 0xA0019C + i*12: two from a horizontal
 * half-extent t/(h/w), two from the vertical t. sub_0003B2D0 tests models
 * against them, so under display.aspect (Hor+) everything past the 4:3
 * edge is culled and pops in at the pads (stage 1-1's grass).
 *
 * With a wide aspect A the argument is scaled by (4/3)/A for the main
 * view (h/w = 3/4): the horizontal planes open to the padded frame's
 * width and the vertical ones stay, as does the projection, which was
 * built before the call. Square targets keep their own aspect (design D6,
 * openspec change free-camera). At 4:3, or without the layer (aspect
 * 0:0), the wrapper calls the generated body and nothing else.
 *
 * RECOMP_DEBUG=cam_log also prints each distinct aspect argument once. */

extern void sub_0003B180_gen(void);

static int   s_cull_init;
static float s_cull_scale;                 /* 0: stock */

/* The game thread is the only caller, so the lazy init needs no lock; the
 * scale is still set before the flag so a reader never sees the flag with a
 * stale scale. */
static void cull_init(void)
{
    const struct nv2a_host_opts *o = nv2a_host_opts();

    /* enhance.c's own wide test: it already refuses 4:3 and narrower */
    if (o && o->aspect_w && o->aspect_h && o->aspect_w * 3u > o->aspect_h * 4u) {
        s_cull_scale = (float)(4.0 * o->aspect_h / (3.0 * o->aspect_w));
        fprintf(stderr, "[HORCULL] display.aspect=%u:%u: main-view side planes x%.4f\n",
                o->aspect_w, o->aspect_h, 1.0 / s_cull_scale);
    }
    s_cull_init = 1;
}

void sub_0003B180(void)
{
    float a;

    if (!s_cull_init)
        cull_init();
    if (!s_cam_init)
        cam_debug_init();
    if (s_cam_log_every) {
        static uint32_t seen[8];
        static unsigned nseen;
        uint32_t bits = MEM32(g_esp + 8);
        unsigned i;
        for (i = 0; i < nseen && seen[i] != bits; i++)
            ;
        if (i == nseen && nseen < 8) {
            seen[nseen++] = bits;
            fprintf(stderr, "[HORCULL] aspect arg %g (fov %g zf %g) ret=%08X\n",
                    MEMF(g_esp + 8), MEMF(g_esp + 4), MEMF(g_esp + 12), MEM32(g_esp));
        }
    }
    if (!s_cull_scale) {
        RECOMP_ABI_CALL(0x0003B180u, sub_0003B180_gen);
        return;
    }
    /* The main view only: -(480/640) within 1%, as nv2a_host_pad picks the
     * 4:3 targets it pads. */
    a = MEMF(g_esp + 8);
    if (a < -0.7425f && a > -0.7575f)
        MEMF(g_esp + 8) = a * s_cull_scale;
    RECOMP_ABI_CALL(0x0003B180u, sub_0003B180_gen);
}

/* ── Hor+: the far sea's view fan ─────────────────────────────
 *
 * sub_00215A40 (eax: the sea object) builds the far sea once per stage: a
 * vertex buffer (+0x4C) of rows of 29 vertices (+0x50 holds the count) in
 * the camera's yaw frame, x across and z ahead, y 0. Each row spans the
 * 4:3 view's half-width at its depth plus a small margin, so a wedge just
 * wider than the stock frame; the draw (vertex program 0xBCAF4F3A) turns
 * it with the camera, carries the reflection and the sea colour, and
 * leaves the flat base sea outside the wedge. The Hor+ frame reaches past
 * the wedge's sides: in stage 1-1 at 16:9 the reflective sea stops on two
 * slanted lines at guest x -72 and 708.
 *
 * With a wide aspect A every vertex's x is scaled by A/(4/3) after the
 * build, which opens the wedge's tangent by the same factor as the frame
 * (and keeps the stock margin). The texture coordinates come from the
 * world and screen positions in the vertex program, so they follow. At
 * 4:3, or without the layer, the wrapper calls the generated body and
 * nothing else. */

extern void sub_00215A40_gen(void);

static int s_fan_logged;   /* the [HORCULL] line, once per run */

void sub_00215A40(void)
{
    uint32_t obj = g_eax, vb, data, n, i;

    if (!s_cull_init)
        cull_init();
    RECOMP_ABI_CALL(0x00215A40u, sub_00215A40_gen);
    /* A failed create returns a negative HRESULT and leaves no buffer. */
    if (!s_cull_scale || (int32_t)g_eax < 0 || !(vb = MEM32(obj + 0x4C)))
        return;
    /* D3DResource.Data is physical; ORed with 0x80000000 it is the same
     * address the build's Lock (sub_002E5B10) returned and wrote through. */
    data = MEM32(vb + 4) | 0x80000000u;
    n = MEM32(obj + 0x50);
    /* Never past the 0x3918-byte buffer the build created. */
    if (n > 0x3918u / 12u)
        n = 0x3918u / 12u;
    if (!s_fan_logged) {
        s_fan_logged = 1;
        fprintf(stderr, "[HORCULL] far sea fan: %u vertices at %08X, x%.4f\n", n, data,
                1.0 / s_cull_scale);
    }
    for (i = 0; i < n; i++)
        MEMF(data + i * 12u) /= s_cull_scale;
}
