## Context

The pieces that already exist:
- `input_core.c` keeps a per-port connection cache: a connected port is read at every call, a disconnected one is asked at most once a second (`XBOX_INPUT_PROBE_MS`); `xbox_InputIsConnected` answers from that cache.
- cat's `pad_input.c` builds the connected mask from `xbox_InputIsConnected` (probing each port once a second itself) and logs `[INPUT] t=<s> ports=<mask>` on a change; `recomp_manual.c`'s `XGetDevices`/`XGetDeviceChanges` overrides turn mask changes into the insert and remove masks, once a frame.
- So the backend only has to make "is there a pad on port N" truthful. The XInput backend is (XInput probes the user index). The SDL backend held `g_pads[]`, filled once at init.

Threads: with a window (`xbox_HostWindowMain`), the process main thread pumps SDL (`SDL_WaitEventTimeout`, 100 ms, plus a wake per frame) and `g_main_pump` is set, so the backend never pumps. The game's poll threads call `get_state`/`set_state` (the title's pad poll, cat's rumble). Headless, nothing pumps and `get_state` calls `SDL_GameControllerUpdate` itself. SDL's own joystick calls take SDL's joystick lock; SDL posts device events (and runs event watches) with that lock held.

## D1. Device-index calls run on the thread that pumps SDL; the event watch only raises a flag

Two constraints decide where opening and closing can happen:
- **sdl2-compat's index list is not thread-safe.** The Mac's SDL2 is sdl2-compat over SDL3. Its device-index API (`SDL_NumJoysticks`, `SDL_JoystickGetDeviceInstanceID`, `SDL_IsGameController`, `SDL_GameControllerOpen`, ...) reads a global `joystick_list` that `SDL_NumJoysticks` frees and rebuilds with no lock (its own `FIXME` says so), and its event conversion calls `SDL_NumJoysticks` whenever a device-added event is posted or popped. A poll thread enumerating while the window thread pumps double-frees that list: the first version of this change did exactly that and the ctest aborted in `SDL_NumJoysticks` ("pointer being freed was not allocated"). Calls on an open pad's pointer (`GetAttached`, `GetButton`, `GetAxis`, `Rumble`, `Close`) map straight to SDL3 and are safe from any thread.
- **Lock order.** A poll takes our mutex, then SDL's joystick lock inside every `SDL_GameController*` call. SDL posts device events and runs event watches with its joystick lock held, so a watch that took our mutex (sdl3-migration D8 opens and closes in the watch) would invert that order: a deadlock waiting for a pad to be plugged in mid-poll.

Options:
- **An event watch that opens and closes** (sdl3-migration D8): the inversion above, and under sdl2-compat it enumerates on whichever thread posts.
- **The poll threads rescan** (this change's first version): races sdl2-compat's list as above.
- **Chosen: the thread that pumps SDL enumerates.** With a window, `fb_present_sdl.c` calls `xbox_InputSdlPadSync()` once per event loop (at least every 100 ms); it opens the controller subsystem the first time host pads are asked for, then rescans. Headless, nothing else touches SDL, so the poll thread is the pump: `get_state` rescans and `SDL_GameControllerUpdate` posts the events. Either way the rescan holds `g_slot_lock`, and the watch only sets an atomic flag. A rescan runs on that flag, or at most once a second without it (`XBOX_INPUT_PROBE_MS`), a net for a missed event and how a headless run with no pad open finds its first one. The rescan: close every pad `SDL_GameControllerGetAttached` says is gone; open every game controller whose instance id is not in the table. Cost: a lock and a clock read per window loop, and once a second `SDL_NumJoysticks` plus a few per-device calls.

`sdl_init` still runs from the first `xbox_InputInit` on the guest's thread. With a window it marks host pads as wanted and waits for the window's next loop to open the subsystem and the pads: a condition variable on `g_slot_lock` (the wait drops the lock the loop takes), broadcast by `start_sdl`, against a 250 ms deadline (`XBOX_SDL_BOOT_WAIT_MS`). A loop runs at least every 100 ms, so a pad plugged in before launch is open at the title's first read and its port is connected from the first `ports` line, as before this change, when `sdl_init` opened the pads itself. The bound covers a first XInput call from the window thread itself, or before its loop starts: the wait times out, the ports read as empty, and the core asks again within a second. It is never unbounded, so no ordering of the threads can deadlock on it. Headless, `sdl_init` opens the pads on the caller's thread with no wait.

`get_state` and `set_state` hold the mutex across their SDL calls, so a close never frees a controller a poll is reading. `get_state` also closes its own port at once (by pointer) when the pad is no longer attached, so `ERROR_DEVICE_NOT_CONNECTED` comes from the first read after a removal, not a second later.

## D2. Ports: never shift; a model's last port, else the lowest free

- A pad keeps its port while attached; removal frees the port. Ports never compact, so player 1 keeps port 0 while player 2 comes and goes.
- A new pad takes the free port whose last occupant had the same joystick GUID, when another pad is still connected; else the lowest free port. Instance ids are new on every replug in SDL, so the GUID is the only thing that recognises a returning pad. It identifies a model, not a unit: two identical pads are interchangeable, which is "where practical".
- With no pad connected the GUID is ignored and the pad takes port 0: a pad that connects while no other pad is connected is player 1, whatever port it had before. BLiNX 2 is single-player, and a pad alone on port 1 would leave the title's player 1 empty.
- A pad already left alone does not move. With A on port 0 and B on port 1, unplugging A leaves B alone on port 1 and port 0 empty, as on the Xbox (a port is a physical socket there); B moves only if it is itself unplugged and replugged. The title's player 1 stays empty until a pad connects to port 0.
- A fifth pad is not opened; the rescan after a close (a close raises the flag) gives it the freed port.

## D3. Logging and env

`[INPUT] host pad added port=<n> "<name>"` and `[INPUT] host pad removed port=<n>`, unconditional (one line per physical change), next to cat's `[INPUT] t=<s> ports=<mask>`. The format is D8's from sdl3-migration, so the SDL3 port can keep it. No new env key; the behaviour is the fix, not an option, and it changes nothing when no pad comes or goes.

## D4. The window's exit is unchanged

`fb_present_sdl.c` calls `SDL_Quit` at window close only when no pad is open, else it shuts the video subsystem and `exit()` reclaims the rest. That still holds: pads open only on the window thread, which is the one asking (`xbox_InputAnyOpen`, now under the mutex), and with no pad open a poll thread makes no SDL call.

## D5. Windows and Proton

The `_WIN32` half of `xinput_device.c` is untouched, and `fb_present_sdl.c` is not built on Windows. The Windows exe (D3D11, XInput) is the same code, so the Proton and native Windows behaviour is unchanged; its hot-plug is XInput's, walked as G1-G3 on Proton separately.

## D6. Tests

`tests/input_hotplug_sdl` (POSIX, in-tree, beside `input_keyboard_sdl`): the real SDL backend behind the public API with a fake clock in the core only, so each step can be "a second later". SDL virtual joysticks (`SDL_JoystickAttachVirtualEx`, game controller type, 6 axes, 15 buttons; vendor and product set the GUID; a mapping is added if the SDL build has no automatic one). A pad's port is found by pressing its START and seeing which port reads it. The boot case runs first: with the window's loop standing in, a pad attached before the first XInput call reads connected on port 0 at that call; without it, the first call returns after its 250 ms bound with no port connected. Cases: attach/detach/reattach with ports and masks; a replugged model's port; a fifth pad. They run twice, headless (the poll rescans) and with the test's thread standing in for the window's loop (`xbox_InputSetMainPump(1)`, `xbox_InputSdlPadSync()` each step). Then a poll thread reads and rumbles every port while the window-side thread runs 200 attach/detach cycles; this case only runs the windowed way, because with sdl2-compat every device-index call must stay on one thread and the test's own attach and detach are such calls. Host joystick drivers are disabled through SDL's hints in the test environment, and the test skips (77) if a host joystick still shows, if SDL is older than 2.24 (no `SDL_JoystickAttachVirtualEx`), or if the first virtual attach fails (no virtual joystick driver). No window, `SDL_AUDIODRIVER=dummy`.

The hands-on (checklist G1-G3 of `input-real-devices` on macOS) is the user's, at the end.

## Risks

- A platform where the event watch never fires for a device: the once-a-second rescan still finds it.
- `SDL_GameControllerOpen` runs under `g_slot_lock` on the window thread, so the game's poll threads block on the lock while a pad's handshake runs (slow on some Bluetooth and HIDAPI pads). It happens once per hot-plug, not per frame.
- Rumble left on a pad at removal: SDL stops it with the device. A pad replugged into a port the title is rumbling gets the next `set_state` refresh.
