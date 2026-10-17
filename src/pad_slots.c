/* Host pad slots onto the title's ports; see pad_slots.h. */

#include "pad_slots.h"

#include <stdio.h>

void pad_slots_init(PadSlots *ps)
{
    for (int s = 0; s < PAD_SLOTS; s++) {
        ps->port[s] = -1;
        ps->last[s] = -1;
        ps->active[s] = 0;
    }
}

int pad_slots_update(PadSlots *ps, uint32_t slots)
{
    int changed = 0;

    /* Free first, so a pad swapped for another in the same poll interval
     * hands its port straight on. */
    for (int s = 0; s < PAD_SLOTS; s++)
        if (ps->port[s] >= 0 && !(slots & (1u << s))) {
            ps->last[s] = ps->port[s];
            ps->port[s] = -1;
            ps->active[s] = 0;
            changed = 1;
        }
    for (int s = 0; s < PAD_SLOTS; s++) {
        uint32_t used;
        int p;
        if (ps->port[s] >= 0 || !(slots & (1u << s)))
            continue;
        used = pad_slots_ports(ps);
        /* A replugged pad's own port, while another pad is up to keep the
         * players apart; with none up it is player 1. The SDL backend
         * hands a replugged model its old slot (sdl2-hotplug D2), so the
         * slot's memory is the pad's. */
        p = ps->last[s];
        if (p < 0 || !used || (used & (1u << p)))
            for (p = 0; p < PAD_SLOTS && (used & (1u << p)); p++)
                ;
        ps->port[s] = (int8_t)p;    /* never full: at most PAD_SLOTS slots */
        changed = 1;
    }
    return changed;
}

int pad_slots_activity(PadSlots *ps, uint32_t active_slots)
{
    int changed = 0;

    for (int s = 0; s < PAD_SLOTS; s++) {
        int low = -1;
        if (ps->port[s] < 0 || ps->active[s] || !(active_slots & (1u << s)))
            continue;
        ps->active[s] = 1;
        /* The lowest port an inert pad holds, if below this one. */
        for (int t = 0; t < PAD_SLOTS; t++)
            if (t != s && ps->port[t] >= 0 && !ps->active[t]
                && ps->port[t] < ps->port[s]
                && (low < 0 || ps->port[t] < ps->port[low]))
                low = t;
        if (low >= 0) {
            int8_t p = ps->port[s];
            ps->port[s] = ps->port[low];
            ps->port[low] = p;
            changed = 1;
        }
    }
    return changed;
}

uint32_t pad_slots_idle(const PadSlots *ps)
{
    uint32_t m = 0;
    for (int s = 0; s < PAD_SLOTS; s++)
        if (ps->port[s] >= 0 && !ps->active[s])
            m |= 1u << s;
    return m;
}

uint32_t pad_slots_mapped(const PadSlots *ps)
{
    uint32_t m = 0;
    for (int s = 0; s < PAD_SLOTS; s++)
        if (ps->port[s] >= 0)
            m |= 1u << s;
    return m;
}

int pad_slots_slot_of(const PadSlots *ps, uint32_t port)
{
    for (int s = 0; s < PAD_SLOTS; s++)
        if (ps->port[s] >= 0 && (uint32_t)ps->port[s] == port)
            return s;
    return -1;
}

uint32_t pad_slots_ports(const PadSlots *ps)
{
    uint32_t m = 0;
    for (int s = 0; s < PAD_SLOTS; s++)
        if (ps->port[s] >= 0)
            m |= 1u << ps->port[s];
    return m;
}

void pad_slots_format(const PadSlots *ps, char *buf, size_t size)
{
    size_t n = 0;

    if (!size)
        return;
    buf[0] = 0;
    for (int s = 0; s < PAD_SLOTS && n < size; s++)
        if (ps->port[s] >= 0)
            n += (size_t)snprintf(buf + n, size - n, "%s%d:%d", n ? "," : "",
                                    s, ps->port[s]);
    if (!n)
        snprintf(buf, size, "none");
}
