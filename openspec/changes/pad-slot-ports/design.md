## Context

The title reads player 1 from port 0 and opens the other ports only when `XGetDeviceChanges` reports a pad there. Host pads arrive on XInput user indices or SDL slots that need not start at 0, and Steam Input can put an inert virtual pad (28de:11ff) on slot 0 ahead of the real one. Until this change `pad_input.c` drove port N from slot N, and the toolkit merged the keyboard and mouse into its slot 0, which only matched the title's port 0 while slot N meant port N.

The connected mask is recomputed from `cat_pad_connected_mask` on the title's `XGetDevices`, `XGetDeviceChanges`, `XInputOpen` and `XInputGetCapabilities` calls and at init, all under cat's lock once the guest runs. Pad state is read per port from `cat_pad_get_state`, port 0 first in the title's per-frame poll.

## Goals / Non-Goals

**Goals**
- A lone pad drives player 1 whatever its slot.
- A pad that is pressed drives player 1 ahead of a pad that has never been pressed.
- A player who has pressed anything is never moved while their pad stays connected.
- One pad on slot 0 (the stock case, and every golden) behaves exactly as before.
- The keyboard and mouse are read once per port-0 poll, whichever slot drives port 0.
- The map is pure and unit-tested; the glue is logged well enough to read a Deck log.

**Non-Goals**
- Telling pads apart by VID/PID, a hand-pinned port, an env key. SDL hot-plug itself is BLX-15 (`sdl2-hotplug`); decision 7 is how its stable ports and this map are one.

## Decisions

### 1. Sticky ports, not dense packing
A slot that comes up takes the lowest port no other slot holds. Slots that come up together go in slot order. A slot keeps its port until it goes away. In one update, slots that went away free their ports before new slots are placed, so a pad swapped for another within one poll interval hands its port straight on.

Re-packing on every change (slot k to the k-th connected pad) would move player 2 onto port 0 when player 1's pad drops for a moment. Sticky assignment never moves a connected player, as on a console. XInput hands out the lowest free index, so pads plugged in from an empty machine fill the slots from 0 and keep slot N on port N: one pad on slot 0 is the stock case, and the map is the identity in every golden.

A slot that comes back takes the port it last held when that port is free and another pad holds a port (decision 7); with no other pad up it takes port 0, as any first pad does.

### 2. First press takes an inert pad's port
Each slot has an `active` flag, set the first time the pad shows input and cleared when the slot goes away. When a slot first becomes active and a never-active slot holds a lower port, the two swap ports: the lowest such port, if there are several. Both ports stay present, so the connected mask does not change and the title sees no remove or insert; player 1 simply starts responding. Slots whose first press falls in the same poll are handled in slot order, so of two never-pressed pads pressed together the lower slot ends on the lower port.

A pad that has once been active is never moved again, so a player who has pressed anything keeps their port. With two real pads and neither pressed yet, whoever presses first becomes player 1. That is the only visible change for two real pads, and it matches the usual "press START" expectation.

### 3. Activity is a button, not a stick
Input means a digital button, or an analog button above the title's own 30 threshold. Sticks do not count: real sticks drift, and a virtual pad can rest off centre (the bench's vpad reads `LS(0,-1) RS(0,-1)` at rest under Proton, bench-logs 20261013-194641). Identifying Steam's pad by VID/PID is not possible through XInput, and activity works on both backends.

### 4. Watch every never-active pad, once per port-0 poll
The check runs at the start of each port-0 poll while any pad holding a port is never-active (and of the other ports' polls while port 0 has no source, decision 7). It reads every such slot alone, not only the ports the title has open, since the title may never poll the real pad's port (at the title screen it reads port 0 alone, which was the bug). A lone pad is watched too: a pad played alone must be marked active, or a second pad plugged in later would take its port on its first press (round-2 review B1). Once every pad has been active, nothing is read.

The cost is one extra pad-only read per poll of each never-pressed pad: for one pad until its first press, for Steam's inert pad for the whole run. An XInput read of a connected index is cheap, and the empty-slot backoff is kept because the accessor uses the toolkit's probe rule.

Because the check runs before port 0's own read, a press that moves a pad onto port 0 is reported on port 0 in the same poll. Only a press that starts between the title's port-0 and port-1 polls of one frame shows on the old port for that one poll, before the next port-0 poll swaps it.

After a swap the per-port host log state (`g_host_last`) is cleared, so each port logs its next state afresh, and both swapped pads get zero motor speeds (and their rumble log state is reset) so a rumble does not stay on the pad that left the port; the title's per-frame resend restarts it on the right one.

### 5. The keyboard and mouse merge in cat, once, on port 0
With slot 0 driving a port other than 0, the toolkit's slot-0 merge and cat's port-0 merge both read the keyboard, so keys drove two ports and each frame's mouse delta went to whichever port polled first (round-1 review S1). The toolkit now offers `xbox_InputGetPadState` (the pad alone) and `xbox_InputMergeKbm` (the rule it uses on slot 0). Cat reads every slot through the first and merges on port 0 through the second, once per poll, when the keyboard or the mouse is on. The activity watch and the one-second probe use the same accessor, so a key press never marks a pad active and never consumes the mouse delta. `xbox_InputGetState` is now the two calls in sequence, so Burnout 3 keeps its behaviour.

The cat-only alternative, leaving slot 0 out of the map while the keyboard is on and it would land above port 0, was rejected: it drops a real pad to work around the toolkit.

### 6. Logging for the Deck triage
The sources line's `pads=` field answers BLX-117's open question on its own: `pads=1:0` is a lone pad on slot 1; `pads=0:0,1:1` followed by `pads=0:1,1:0 active=0x2` on the first press is Steam's inert pad on slot 0. `active=` lists every pad that has been active, so a later line can be read without the earlier ones. A first press that moves nothing is not logged: it changes nothing the title can see.

### 7. One port map with SDL hot-plug (BLX-15)
BLX-15 (toolkit 8c9f875b, `sdl2-hotplug` D2) gave the SDL backend its own port rules: a pad keeps its slot while attached, a replugged model (joystick GUID) takes the slot it last held when that is free and another pad is connected, else the lowest free slot, so a pad that connects alone lands on slot 0; ports never shift. This map then put those slots onto the title's ports with rules of its own. Layered, the two disagreed at the title's ports: with three pads up and two pulled, the one replugged first got its old slot back from the toolkit and then the lowest free port from this map, so "a replugged pad keeps its port" held for the slot and not for the player. Two sets of rules for one question is also two places to read when a Deck log looks wrong.

So this map is the only port map, and the backend's slot is only the pad's identity:
- XInput (Windows, Proton): the user index, which the system gives out lowest-free and keeps while the pad is connected.
- SDL (macOS, Linux): the backend's slot. Its D2 rules now matter here only as the identity rule: a replugged model gets its old slot, so the slot's memory below is the pad's.

D2's rules move up to the title's ports, so they hold on every host and next to decisions 1 and 2:
- A slot that comes up takes the port it last held if that port is free and another pad holds a port, else the lowest free port (D2's GUID rule, keyed by the slot). The port remembered is the one held when the slot went, after any swap, so a pad promoted over Steam's inert pad and then replugged comes back on port 0.
- With no other pad holding a port, a slot takes port 0 whatever it held before (D2's player-1 rule, and BLX-117's: the first host pad drives port 0 whatever its slot).
- Ports never shift: a pad left alone on a higher port stays there, and port 0 stays empty until a pad comes up (D2, as on the Xbox, where a port is a socket). Only a first press moves a pad, and only onto a port an inert pad holds, which keeps the connected mask.

On BLiNX the SDL backend's own D2 choices only decide which slot a pad gets, so they are not undone or duplicated. Burnout 3 has no map of its own and keeps reading slot N as port N, where D2 still is the port rule. The toolkit's `[INPUT] host pad added port=<n>` line therefore names a slot on BLiNX; the `pads=` line logged at the next mask update names the title's port.

Rejected: moving the map into the toolkit's input core, for both games and both backends, with the SDL backend reduced to lowest-free slots. It would be one map in a single file, but it changes Burnout 3's ports and the upstream-bound input API in a bug fix, and the first-press promotion is a policy for a single-player title with Steam's inert pad in view; a later toolkit port map can take this one over. Also rejected: keeping D2's rules only in the backend and dropping the memory here. XInput has no identity to give back, and the layering above stays.

The watch of decision 4 also runs on the other ports' polls while port 0 has no source, since the title then does not poll port 0. Without that, a pad left alone on port 1 (player 1's pad pulled, the keyboard off) was never marked while pressed, and when player 1's pad came back onto port 0 the next press of the pad on port 1 swapped them: the round-2 B1 failure in another form.

## Risks

- A player who never presses anything on pad 1 while pad 2 is pressed loses port 0 to pad 2. That is intended.
- A press between the port-0 and port-1 polls of one frame shows on the old port for one poll (decision 4). Harmless where it matters: the title reads port 0 alone at the title screen.
- With both the keyboard and the mouse off, a `kbm_script` is no longer stepped on the slot-0 path, since cat reads them only when one is on. It has no visible effect then, and the non-slot-0 path already behaved this way.
- The Deck's cause is unconfirmed. A Desktop Mode log with the `pads=` field settles it (task 5.5); both causes are fixed either way.
