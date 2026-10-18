/*
 * pad_slots.h - which host pad drives which of the title's four ports.
 *
 * A host numbers its pads by slot (the XInput user index on Windows and
 * Proton, the SDL backend's slot elsewhere). The title reads player 1 from
 * port 0, so slot N cannot simply be port N: a pad can sit alone on a slot
 * above 0, or behind a pad that never sends anything. Under Proton with the
 * Steam client running and Steam Input on for the game, Wine exposes
 * Steam's virtual pad (28de:11ff) on the low indices, inert, ahead of the
 * real one (the bench reproduces it: pads=0:0,1:1, START on port 1; with
 * PROTON_NO_STEAMINPUT=1 it reads pads=0:0). A
 * Steam Deck launched from Desktop Mode is suspected to be that case (its
 * log's pads= field will tell).
 *
 * This is the one map from host pads to the title's ports. The host's slot
 * is only the pad's identity: XInput's user index (the lowest free one when
 * a pad arrives), or the SDL backend's slot, which hot-plug gives
 * back to the same model when it is replugged. The SDL backend's own port
 * rules (sdl2-hotplug D2) are restated here at the title's ports, so they
 * hold on every host and alongside the rules below.
 *
 * Three rules:
 *   - A slot that comes up takes the port it last held, if that port is
 *     free and another host pad holds a port; otherwise the lowest port no
 *     other host pad holds. So a pad pulled and replugged comes back as
 *     the same player, and a pad that comes up while no other is up is
 *     player 1 (port 0) whatever its slot. Slots that come up together go
 *     in slot order.
 *   - A slot keeps its port until it goes away, so a pad plugged in or out
 *     never moves another player, and a pad left alone on a higher port
 *     stays there (as on the Xbox, where a port is a socket). With pads
 *     filling the slots from 0 in order (XInput hands out the lowest free
 *     index) a slot's port is its own number.
 *   - A pad's first activity (pad_slots_activity) swaps it with the lowest
 *     port held by a pad that has never been active, so an inert pad never
 *     keeps player 1 from the pad being used. A pad that has been active is
 *     never moved; the ports trade pads but stay present, so the title sees
 *     no remove or insert.
 *
 * Plain C with no host or guest state, so scripts/test_pad_slots.py can
 * compile it alone.
 */
#ifndef CAT_PAD_SLOTS_H
#define CAT_PAD_SLOTS_H

#include <stddef.h>
#include <stdint.h>

#define PAD_SLOTS 4

typedef struct {
    int8_t  port[PAD_SLOTS];    /* the port of each host slot, -1 for none */
    int8_t  last[PAD_SLOTS];    /* the port the slot held when it last went, -1 for none */
    uint8_t active[PAD_SLOTS];  /* the slot's pad has sent input since it came up */
} PadSlots;

/* A static PadSlots initialiser, the same state as pad_slots_init. */
#define PAD_SLOTS_INIT { { -1, -1, -1, -1 }, { -1, -1, -1, -1 }, { 0, 0, 0, 0 } }

/* No slot holds a port or has held one. */
void pad_slots_init(PadSlots *ps);

/* `slots` is the mask of host slots with a device now. Slots no longer in
 * it give their port up (remembering it) and forget their activity; then
 * each new slot, lowest first, takes its remembered port if that is free
 * and some other slot holds a port, else the lowest free port. Returns
 * nonzero when any slot's port changed. */
int pad_slots_update(PadSlots *ps, uint32_t slots);

/* `active_slots` is the mask of host slots whose pad shows input now. Each
 * such slot not yet marked active is marked; if a lower port than its own
 * is held by a never-active slot, the lowest such port and its own swap
 * slots. Slots without a port are ignored. Returns nonzero when any slot's
 * port changed. */
int pad_slots_activity(PadSlots *ps, uint32_t active_slots);

/* Never-active slots that hold a port. The caller watches every one of
 * them, even a lone pad, so a pad played alone is marked active before a
 * second pad can come up and take its port. */
uint32_t pad_slots_idle(const PadSlots *ps);

/* Slots that hold a port. */
uint32_t pad_slots_mapped(const PadSlots *ps);

/* The host slot driving `port`, or -1. */
int pad_slots_slot_of(const PadSlots *ps, uint32_t port);

/* The mask of ports some host slot drives. */
uint32_t pad_slots_ports(const PadSlots *ps);

/* "1:0,0:1" (slot:port, in slot order) or "none", for the [INPUT] log. */
void pad_slots_format(const PadSlots *ps, char *buf, size_t size);

#endif
