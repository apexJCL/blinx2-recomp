# Environment variables

Every variable the runtime reads goes through one table, `RECOMP_ENV_KEYS` in toolkit `src/platform/recomp_env.h`, and is read once at startup (`recomp_env_init`, called first in `main`) and cached. A lookup is an array load, so call sites in hot paths cost nothing. There are three tiers:

- **Config** (36): documented knobs, each its own variable (`RECOMP_PB_BACKEND=d3d11`). Six of them belong to the toolkit's enhancements layer (`RECOMP_ENHANCE_CONFIG`, `RECOMP_RENDER_SCALE`, `RECOMP_DISPLAY_ASPECT`, `RECOMP_PRESENT_FILTER`, `RECOMP_PRESENT_FULLSCREEN`, `RECOMP_PRESENT_PACING`) and exist only when it is built (`XBOXRECOMP_ENHANCE`, on by default in this project); each overrides its key in `enhance.toml`, which sits beside the executable (toolkit `docs/runtime/enhance-config.md`). The game's three keys, `RECOMP_FPS_MODE`, `RECOMP_GLOW` and `RECOMP_GLOW_INTENSITY`, override `fps.mode`, `fx.glow` and `fx.glow_intensity` the same way and are read only with the layer.
- **Trace** (54): log and report toggles, one comma list: `RECOMP_TRACE=flip,tex,heap=0x80123000`. Printing only; nothing changes behaviour. Every trace key is off when unset except `missing`, the missing-game-file report, which is on unless `missing=0`.
- **Debug** (83): hacks, A/B switches, experiments, dumps, watchpoints, one comma list: `RECOMP_DEBUG=pb_fast=0,fb_dump=/tmp/f_,fb_dump_at=61,121`. Anything that changes behaviour, writes files or installs machinery (a watchdog, a thread dumper) is here.

List syntax: `key` means `1`, `key=value` sets a value, and a later entry wins. Only keys whose values hold commas (`fb_dump_at`, `peek`, `peek_chain`, `px`, `px_consts`, `dsp_ack`, `apu_dsp_ack`, `poke`, `window_shot`, `pad_script`, and the game's `mem_dump` and `pad_peek`) take the fragments after them as part of the value, so `fb_dump_at=61,121,181`, `peek_chain=0x1315A8,8,0x10,0` and `px=10,20;30,40` each read as one value. After any other key, a fragment that is not a key gets the unknown-key warning, so a typo such as `d3d11_dump=Z:\d,pb_fsatt=0` is reported, not glued onto the path. `RECOMP_TRACE=help` (or `RECOMP_DEBUG=help`) prints the table. A key given in the wrong list is accepted with a note. An unknown key is ignored with a warning.

Rows marked (game) are this game's own keys. They are defined in `cat:src/env/recomp_env_game.h`, which the toolkit table pulls in through its `RECOMP_ENV_GAME_KEYS` hook (CMakeLists.txt sets `RECOMP_ENV_HAVE_GAME_KEYS`); the toolkit itself no longer knows them.

**Old names still work.** Each replaced variable is an alias that prints one line at startup, e.g. `[ENV] RECOMP_FLIP_LOG is deprecated; use RECOMP_TRACE=flip`. When both spellings are set, the new one wins. Defaults are unchanged except two config knobs that now default on: `RECOMP_PB_EXEC` and `RECOMP_AC97_READY` (x86-64 Windows/Proton, and macOS/Linux arm64); `=0` turns either off. The game also defaults `apu_dsp_ack` to `auto`, the GP doorbell found from `GPSADDR` (see below). Keys whose old variable defaulted on (`pb_vsh`, `pb_rc`, `pb_fast`, `pb_bilinear`, `pb_clip`, `fast_kick`, `d3d11_memo`, `apu_mixdown_all`) are still switched off with `=0`.

Scripts: `blinx2 bench` and `golden.py plan` merge `RECOMP_TRACE` / `RECOMP_DEBUG` from several sources (a scenario's pins, `BENCH_ENV`, `BENCH_FRAMES`) by joining them with commas. Any other variable is replaced, as before.

Code that sets a variable after startup uses `recomp_env_set(RENV_X, value)`; tests that `setenv` call `recomp_env_reload()`. The generated `recomp_stubs_unresolved.c` still calls `getenv("RECOMP_STUB_LOG")`, so `recomp_env` exports that variable when `RECOMP_TRACE=stub` is set.

File:line columns list the call sites as of this change (first three; `toolkit:` is xboxrecomp, `cat:` is this repo).

## Config

| Old name | New name | Meaning | Read at |
|---|---|---|---|
| `RECOMP_PB_EXEC` | `RECOMP_PB_EXEC` (unchanged) | pushbuffer executor (draws frames). **Default on**; `=0` turns it off | `toolkit:src/kernel/nv2a_pb_scan.c:303`, `toolkit:src/kernel/xbox_memory_layout.c:3110`, `toolkit:src/kernel/xbox_memory_layout.c:3113` |
| `RECOMP_PB_BACKEND` | `RECOMP_PB_BACKEND` (unchanged) | executor backend: cpu (default), metal, d3d11, null | `toolkit:src/d3d/nv2a_pb_d3d11.c:3049`, `toolkit:src/d3d/nv2a_pb_metal.m:1995`, `toolkit:src/kernel/nv2a_pb_exec.c:4991` +2 |
| `RECOMP_HEADLESS` | `RECOMP_HEADLESS` (unchanged) | 1: no window (SDL host) | `toolkit:src/video/fb_present_sdl.c:348` |
| `RECOMP_WINDOW_SCALE` | `RECOMP_WINDOW_SCALE` (unchanged) | initial window size in points, 640x480 times this (SDL host, default 2); how the frame fills the window is `RECOMP_PRESENT_FILTER` | `toolkit:src/video/fb_present_sdl.c:420` |
| `RECOMP_PRESENT_VSYNC` | `RECOMP_PRESENT_VSYNC` (unchanged) | vsync at present. SDL host (CPU and Metal): default on, 0 turns it off. D3D11 window: default off (`Present(0, 0)`, stock), 1 waits for vsync and logs one `[d3d11] present vsync` line. The D3D11 wait happens inside the flip, on the window-pumping thread, so `=1` stalls the guest's flip by up to a frame and, on a display that is not 60 Hz, double-paces against the guest vblank | `toolkit:src/video/fb_present_sdl.c:518`, `toolkit:src/d3d/nv2a_pb_d3d11.c:434` |
| `RECOMP_WINDOW_QUIT_AFTER` | `RECOMP_WINDOW_QUIT_AFTER` (unchanged) | close the window after this many seconds | `toolkit:src/video/fb_present_sdl.c:344`, `toolkit:src/video/fb_present_sdl.c:345` |
| `RECOMP_FB_WINDOW` | `RECOMP_FB_WINDOW` (unchanged) | Windows: show the framebuffer window | `toolkit:src/video/fb_present.c:349` |
| `RECOMP_SAVE_DIR` | `RECOMP_SAVE_DIR` (unchanged) | root for the title's UDATA/TDATA, inside whichever save root is in force (`RECOMP_HDD_DIR` or the toolkit default); the partition images and caches stay in the save root | `toolkit:src/kernel/kernel_path.c:380`, `toolkit:src/kernel/kernel_path.c:581`, `cat:src/save_seed.c:141` |
| `RECOMP_GAME_FILES` | `RECOMP_GAME_FILES` (new) | the game files directory (`default.xbe` and the disc). Default: `game_files/` in the working directory. An installed game's launcher sets it (docs/packaging.md) (game) | `cat:src/main.c:1044` |
| `RECOMP_HDD_DIR` | `RECOMP_HDD_DIR` (new) | the emulated hard disk: partition images, `TitleData/`, `UserData/`, `Cache/` and the UDATA/TDATA saves. Default: the toolkit's save root (`%LOCALAPPDATA%\xboxrecomp`, inside the Wine prefix under Proton; `~/.local/share/xboxrecomp` elsewhere). Launchers set it outside the program files and any prefix. Either key set prints one `[BOOT] game files:` line (game) | `cat:src/main.c:1142` |
| `RECOMP_SAVE_SEED` | `RECOMP_SAVE_SEED` (unchanged) | seed the save dir from this save before boot (game) | `cat:src/save_seed.c:140` |
| `RECOMP_AC97_READY` | `RECOMP_AC97_READY` (unchanged) | emulated APU and audio. **Default on** on x86-64 Windows/Proton and on macOS/Linux arm64 (A64 MMIO decoder); `=0` turns it off. On x86-64 POSIX always off, with an "audio unsupported on this host" line if set to 1 | `toolkit:src/kernel/xbox_memory_layout.c:3182`, `toolkit:templates/new-game/src/main.c:363`, `cat:src/main.c:905` +2 |
| `RECOMP_VBLANK` | `RECOMP_VBLANK` (unchanged) | deliver the vblank interrupt | `toolkit:src/kernel/kernel_bridge.c:2587`, `cat:src/main.c:957`, `cat:src/main.c:958` |
| `RECOMP_INPUT_SCRIPT` | `RECOMP_INPUT_SCRIPT` (unchanged) | scripted pad: @preset, file or inline script (game) | `cat:src/pad_input.c:904` |
| `RECOMP_INPUT_STRICT` | `RECOMP_INPUT_STRICT` (unchanged) | 1: a bad input script ends the run (game) | `cat:src/pad_input.c:925` |
| `RECOMP_HOST_PAD` | `RECOMP_HOST_PAD` (unchanged) | 0/1: host gamepads in or out (game) | `cat:src/pad_input.c:940` |
| `RECOMP_KEYBOARD` | `RECOMP_KEYBOARD` (unchanged) | 1: keyboard drives pad 1 (every host; needs the host pad on; keys in toolkit `src/input/README.md`) | `toolkit:src/input/keyboard.c:128`, `toolkit:src/usb/usb_gamepad.c:600`, `cat:src/pad_input.c:853` |
| `RECOMP_RUMBLE` | `RECOMP_RUMBLE` (unchanged) | 0: no rumble (game) | `cat:src/pad_input.c:951` |
| `RECOMP_PAD_DEADZONE` | `RECOMP_PAD_DEADZONE` (unchanged) | stick deadzone, 0..32767 (default 0) | `toolkit:src/input/input_map.c:50` |
| `RECOMP_STDIO_LOG` | `RECOMP_STDIO_LOG` (unchanged) | send stdout/stderr to this file | `toolkit:tests/d3d11_backend_smoke/smoke.c:170`, `toolkit:tests/d3dcompile_smoke/smoke.c:280`, `cat:src/main.c:987` |
| `XBOX_LOG_LEVEL` | `RECOMP_LOG_LEVEL` | kernel log level, 0 (error) .. 4 (trace) | `toolkit:src/kernel/kernel_thunks.c:410` |
| `RECOMP_AUDIO_BUF_SAMPLES` | `RECOMP_AUDIO_BUF_SAMPLES` (unchanged) | audio output buffer size in samples | `toolkit:src/apu/apu_xaudio2.c:80`, `toolkit:src/apu/apu_sdl2.c` |
| `RECOMP_AUDIO_BUF_COUNT` | `RECOMP_AUDIO_BUF_COUNT` (unchanged) | audio output buffer count | `toolkit:src/apu/apu_xaudio2.c:83`, `toolkit:src/apu/apu_sdl2.c` |
| `RECOMP_CMDLINE` | `RECOMP_CMDLINE` (unchanged) | launch-data command line handed to the title | `toolkit:src/kernel/kernel_bridge.c:243` |
| `RECOMP_FMV_HOST` | `RECOMP_FMV_HOST` (unchanged) | play the title's movies through the host player | `toolkit:src/kernel/kernel_bridge.c:3478` |
| `RECOMP_RASTER_THREADS` | `RECOMP_RASTER_THREADS` (unchanged) | CPU raster threads, 1..16 (default: cores - 4; 1 = serial) | `toolkit:src/kernel/nv2a_pb_exec.c:3527` |
| `RECOMP_USB_PADS` | `RECOMP_USB_PADS` (unchanged; from upstream) | emulated USB pads plugged in, 1..4 (default 1; Burnout 3 sets 2 in its game defaults) | `toolkit:src/usb/ohci.c:1281` |
| `RECOMP_ENHANCE_CONFIG` | `RECOMP_ENHANCE_CONFIG` (new; enhancements layer) | the enhancements file: a path, or `none` for no file. Default: `enhance.toml` in the executable's directory. Golden runs pin `none` | `toolkit:src/enhance/enhance_cfg.c:140` |
| `RECOMP_RENDER_SCALE` | `RECOMP_RENDER_SCALE` (new; enhancements layer) | `render.scale`: internal resolution factor 1..4 (default 1 = stock 640x480). Metal and D3D11 render every target at N times its size; the CPU backend ignores it (one log line). Golden runs pin 1, and `golden.py` fails a run whose log shows another value | `toolkit:src/enhance/enhance_cfg.c:36` |
| `RECOMP_DISPLAY_ASPECT` | `RECOMP_DISPLAY_ASPECT` (new; enhancements layer) | `display.aspect`: 4:3 (stock). Hor+ widescreen is not implemented yet; another value is reported and 4:3 is used (and `golden.py` fails the run) | `toolkit:src/enhance/enhance_cfg.c:37` |
| `RECOMP_PRESENT_FILTER` | `RECOMP_PRESENT_FILTER` (new; enhancements layer) | `present.filter`: `nearest` (stock letterbox), `linear` (letterbox, bilinear), `integer` (largest whole multiple that fits, centred; a frame larger than the window is fitted, linear). SDL window and D3D11 window | `toolkit:src/enhance/enhance_cfg.c:38` |
| `RECOMP_PRESENT_FULLSCREEN` | `RECOMP_PRESENT_FULLSCREEN` (new; enhancements layer) | `present.fullscreen`: 1 opens the window borderless fullscreen at start (no mode change; 1/0, true/false, yes/no, on/off) | `toolkit:src/enhance/enhance_cfg.c:39` |
| `RECOMP_PRESENT_PACING` | `RECOMP_PRESENT_PACING` (new; enhancements layer) | `present.pacing`: how the main loop's frame wait (0x00060475, lowered by `config/spin_waits.json`) waits. `spin` (stock): it busy-waits as on the console, holding a host core (about 97% in the fps spike's samples). `sleep`: it blocks until the kernel signals (a vblank, an ISR or DPC, a fence) or 1 ms passes, which frees that core; frames are the game's own either way. Golden runs pin `spin`, and `golden.py` fails a run whose log shows another value unless `--allow-enhance present.pacing=sleep` (evaluation only) | `toolkit:src/enhance/enhance_cfg.c:40`, `toolkit:src/enhance/enhance.c:44` |
| `RECOMP_FPS_MODE` | `RECOMP_FPS_MODE` (new; enhancements layer) | `fps.mode`: `lock30` only. `lock60` and `free` are not available: the stage logic advances a fixed 1/30 s per frame, so a 60 Hz loop runs the game at double speed (the fps spike); either one logs one line and runs `lock30`, nothing in the guest changes. `blinx2 golden check` fails a run that asked for another value: the check reads `fps.mode`'s stock value from `game.toml` `[golden] enhance_stock` (game) | `cat:src/main.c:1296` |
| `RECOMP_GLOW` | `RECOMP_GLOW` (new; enhancements layer) | `fx.glow`: `on` (stock) or `off`. `off` draws the game's glow pass (post mode 3, `sub_0005B7D0`: a 4-tap blur of the 320x240 downsample, screen-blended over the frame) with weight 0, which leaves the frame unchanged; mode 4 and the downsamples run as stock. The weight `0xADC744` is scaled only for the call and put back, so the game's own fade of it is untouched. Backend-neutral (the pass reads the weight as its vertex colour). Golden runs pin `on`, and `blinx2 golden check` fails a run whose log shows `off` unless `--allow-enhance fx.glow=off` (stock value from `game.toml` `[golden] enhance_stock`) (game) | `cat:src/main.c:1348`, `cat:src/recomp_manual.c:502` |
| `RECOMP_GLOW_INTENSITY` | `RECOMP_GLOW_INTENSITY` (new; enhancements layer) | `fx.glow_intensity`: 0.0 to 2.0, default 1.0 (stock); scales the mode-3 glow layer by about this much (the weight by its cube root, since it enters the pass's combiner three times; near-white areas clip under 2). Out of range is clamped with one line. At `on` and `1` the guest is never written. Golden runs pin `1`, and `blinx2 golden check` fails a run whose log shows another value, compared as a number (stock value from `game.toml` `[golden] enhance_stock`) (game) | `cat:src/main.c:1351`, `cat:src/glow.c:21` |

## Trace (`RECOMP_TRACE=`)

| Old name | New name | Meaning | Read at |
|---|---|---|---|
| `RECOMP_FLIP_LOG` | `flip` | one line per flip (golden.py reads it) | `toolkit:src/d3d/nv2a_pb_d3d11.c:2789`, `toolkit:src/d3d/nv2a_pb_metal.m:1854`, `toolkit:src/kernel/nv2a_pb_exec.c:5305` +1 |
| `RECOMP_PRESENT_TRACE` | `present` | present-surface choices | `toolkit:src/kernel/nv2a_pb_exec.c:599` |
| `RECOMP_PRESENT_STATS` | `present_stats` | SDL host present statistics | `toolkit:src/video/fb_present_sdl.c:341` |
| (none) | `metal_prof` | Metal flip cost every 300 flips: GPU wait, host readback, write-back, readback-mode window copy and hand-off, layer-mode slot blit, GPU time, write-backs and decode syncs | `toolkit:src/d3d/nv2a_pb_metal.m:312` |
| (none) | `metal` | Metal render-target events: each decode sync (target, texture, flip) and every stale drop, not only the first 20 | `toolkit:src/d3d/nv2a_pb_metal.m:562` |
| `RECOMP_VSH_TRACE` | `vsh` | vertex programs and their batches | `toolkit:src/kernel/nv2a_pb_exec.c:2061`, `toolkit:src/kernel/nv2a_pb_exec.c:3963`, `toolkit:src/kernel/nv2a_pb_exec.c:4044` |
| `RECOMP_VSH_ZLOG` | `zlog` | depth clears and z-buffer use | `toolkit:src/kernel/nv2a_pb_exec.c:2265`, `toolkit:src/kernel/nv2a_pb_exec.c:3956` |
| `RECOMP_TEX_LOG` | `tex` | texture format survey; =2 also every texture | `toolkit:src/kernel/nv2a_pb_exec.c:2381`, `toolkit:src/kernel/nv2a_pb_exec.c:2526` |
| `RECOMP_TEX_STATE` | `tex_state` | texture-state methods seen, in the report | `toolkit:src/kernel/nv2a_pb_exec.c:5663` |
| `RECOMP_CLIP_TRACE` | `clip` | near-plane clipping, per triangle | `toolkit:src/kernel/nv2a_pb_exec.c:3907` |
| `RECOMP_ZPASS_TRACE` | `zpass` | occlusion report writes | `toolkit:src/kernel/nv2a_pb_exec.c:4616` |
| `RECOMP_PB_EXEC_VERBOSE` | `pb_verbose` | executor bring-up detail | `toolkit:src/kernel/nv2a_pb_exec.c:4666`, `toolkit:src/kernel/nv2a_pb_exec.c:4706`, `toolkit:src/kernel/nv2a_pb_exec.c:5008` +1 |
| `RECOMP_SURF_TRACE` | `surf` | =offset: surface methods from that colour offset | `toolkit:src/kernel/nv2a_pb_exec.c:5036` |
| `RECOMP_PB_SEMA_TRACE` | `sema` | every semaphore release | `toolkit:src/kernel/nv2a_pb_exec.c:5223` |
| `RECOMP_PB_UNHANDLED_ALL` | `unhandled_all` | list every unhandled method, not ten | `toolkit:src/kernel/nv2a_pb_exec.c:5680` |
| `RECOMP_PB_SCAN` | `pb_scan` | pushbuffer survey and its report | `toolkit:src/kernel/nv2a_pb_scan.c:193`, `toolkit:src/kernel/nv2a_pb_scan.c:305`, `toolkit:src/kernel/xbox_memory_layout.c:3112` |
| `RECOMP_NV2A_TRACE` | `nv2a` | NV2A register poll | `toolkit:src/kernel/xbox_memory_layout.c:3111` |
| `RECOMP_PB_WRAP_TRACE` | `pb_wrap` | pushbuffer wraps | `toolkit:src/kernel/xbox_memory_layout.c:1456` |
| `RECOMP_HEAP_TRACE` | `heap` | =va: heap blocks covering that address | `toolkit:src/kernel/xbox_memory_layout.c:4264` |
| `RECOMP_KERNEL_LOG_BUDGET` | `kernel_budget` | =n: kernel log lines per call site (200) | `toolkit:src/kernel/kernel_bridge.c:390` |
| `RECOMP_TRACE_BUDGET` | `call_budget` | =n: call-trace line budget (400000) | `toolkit:src/kernel/recomp_trace.c:34` |
| `RECOMP_TRACE_ARGS` | `call_args` | =n: call trace prints n stack args | `toolkit:src/kernel/recomp_trace.c:164`, `toolkit:src/kernel/recomp_trace.c:166` |
| `RECOMP_TRACE_DEREF` | `call_deref` | call trace follows pointer args | `toolkit:src/kernel/recomp_trace.c:182` |
| `RECOMP_TRACE_PROFILE` | `call_profile` | call profile; =n report interval | `toolkit:src/kernel/recomp_trace.c:104`, `toolkit:src/kernel/recomp_trace.c:115` |
| `RECOMP_IRQL_TRACE` | `irql` | first IRQL transitions | `toolkit:src/kernel/kernel_hal.c:161` |
| (none) | `pacing` | frame pacing: every 600 flips, `[PACING] flips 600:` with the flip interval p5/p50/p95/max, the vblank gap range, process CPU and the pacing mode, then one line per spin-wait site (waits, immediate, wakes, timeouts, skipped at DISPATCH; loop exits on a wake and on the timeout; in-wait and thread CPU). `=all` adds `[PACING] flip N t_us T batches B` per flip, which `blinx2 pacing-stats` reads | `toolkit:src/kernel/kernel_pacing.c:282` |
| (none) | `dpc` | where the host-run guest routines (timer and queued DPCs, vblank/APU/USB ISRs, KeSynchronizeExecution) spend the timer thread: per routine its runs, run time and longest run, and its waits on the dispatch gate, the APU lock and KeStallExecutionProcessor; three or more `[DPCPROF]` lines under each `[NV2A] vblank N: last 600` line, top eight by run plus gate wait; a timer-thread DPC past 20 ms is also sampled once a millisecond (NV2A interrupt words, last kernel ordinal, guest return addresses) | `toolkit:src/kernel/kernel_prof.c:40` |
| (none) | `missing` | missing game files. **On by default.** A failed read-only `FILE_OPEN` of a file, by absolute name, in the game files tree (D:, CdRom0, E:, C:, Y:, after the title's own drive links) whose directory exists prints `[FILE] missing <guest> -> <host>` once; that path's later `[FILE] … FAILED` lines are counted, not printed. At exit (`exit`, HalReturnToFirmware, KeBugCheck, the Win32 window close) one `[FILE] summary:` line counts the missing files, the misses under absent directories, the failed opens and the repeats not printed; it prints only when a game file is missing. The watchdog and the crash report print `[FILE] missing at watchdog/crash: H high, L low`. `=all` also lists misses under absent directories, misses in the HDD, save and cache trees, failed attribute probes and relative names (`[FILE] not found (…)`), prints every FAILED line, logs the NtOpenFile and IoCreateFile successes (NtCreateFile's always print; those two print only their failures otherwise), and ends the summary with the exit that printed it (`[at window]`); `=0` turns it off and prints every FAILED line as before | `toolkit:src/kernel/kernel_missing.c:73` |
| `RECOMP_APU_TRACE` | `apu` | APU register and frame trace; [APU-IRQ] line every 5 s (traps, delivered by the frame thread, posted to the gate holder and delivered by it, held-off and forced frames under `irq_safe_points=0`) | `toolkit:src/apu/apu_core.c:160`, `toolkit:src/apu/apu_mmio_hook.c:150`, `toolkit:src/apu/apu_vp.c:1190` |
| (none) | `audio_host` | host audio playback vs wall clock; [AUDIO-HOST] starve lines (on with `apu`); `blinx2 audio-check --log` splices the starves in | `toolkit:src/apu/apu_core.c:543` |
| (none) | `apu_ring` | looping APU buffers refilled by the title: [APU-RING] writer lead and stale-lap replays once a second; `blinx2 audio-check --log` fails on any (`max_ring_stale` 0), except with `--golden`: the golden gate leaves it out until a clean run shows a stream's last lap, replayed as the stream ends, does not trip it | `toolkit:src/apu/apu_vp.c:968` |
| `RECOMP_USB_TRACE` | `usb` | OHCI trace | `toolkit:src/usb/ohci.c:1080` |
| `RECOMP_USB_STATS` | `usb_stats` | OHCI summary line every 5 s | `toolkit:src/usb/ohci.c:700` |
| `RECOMP_INPUT_DIAG` | `input_diag` | input chain probe once a second | `toolkit:src/usb/usb_gamepad.c:310` |
| `RECOMP_INPUT_TRACE` | `input` | pad handles and states (game) | `cat:src/pad_input.c:1120` |
| (none) | `unimpl_budget` | =n: [UNIMPL] lines per address (3), then only hits 10, 100, 1000 ...; a new address always prints once (game) | `cat:src/recomp_manual.c:494` |
| `RECOMP_KEY_TRACE` | `key` | key-down events, every window (first 40) | `toolkit:src/video/fb_present.c:160`, `toolkit:src/d3d/nv2a_pb_d3d11.c:251`, `toolkit:src/input/keyboard_sdl.c:64` |
| (none) | `title` | the window title also shows FPS and draws, refreshed once a second (`<name> \| FPS: n \| draws: n`); without it the title is only the game's name and is written only when the name changes. Every window: Win32, D3D11 (via `fb_present.c`), SDL (CPU, Metal) | `toolkit:src/video/fb_present.c:296`, `toolkit:src/video/fb_present_sdl.c:404` |
| `RECOMP_CS_TRACE_CRT` | `cs_crt` | CRT critical sections; =all every one | `toolkit:src/kernel/kernel_rtl.c:405` |
| `RECOMP_CS_WATCH` | `cs_watch` | =va: critical section at that address | `toolkit:src/kernel/kernel_rtl.c:426` |
| `RECOMP_KERNEL_WATCH` | `kernel_watch` | =va: report bridges that change it | `toolkit:src/kernel/kernel_bridge.c:9779` |
| `RECOMP_KERNEL_WATCH_ALL` | `kernel_watch_all` | kernel_watch: every new value | `toolkit:src/kernel/kernel_bridge.c:9880` |
| `RECOMP_PEEK` | `peek` | =va[:n],...: print guest memory at reports | `toolkit:src/kernel/nv2a_pb_exec.c:5529`, `toolkit:src/kernel/xbox_memory_layout.c:2272` |
| `RECOMP_PEEK_CHAIN` | `peek_chain` | =va,off,...: follow a pointer chain | `toolkit:src/kernel/nv2a_pb_exec.c:5560` |
| `RECOMP_FIND_NAN` | `find_nan` | scan for NaN matrices at reports | `toolkit:src/kernel/nv2a_pb_exec.c:5598` |
| `RECOMP_FIND_QUAD` | `find_quad` | scan for quad vertices once | `toolkit:src/kernel/nv2a_pb_exec.c:5604` |
| `RECOMP_D3D11_VERBOSE` | `d3d11_verbose` | D3D11 shader sources | `toolkit:src/d3d/nv2a_pb_d3d11.c:250`, `toolkit:src/d3d/nv2a_pb_d3d11.c:1606` |
| `RECOMP_D3D11_PX` | `px` | =x,y[;x,y]: D3D11/CPU draws touching a pixel | `toolkit:src/d3d/nv2a_pb_d3d11.c:2201`, `toolkit:src/kernel/nv2a_pb_exec.c:5041` |
| `RECOMP_D3D11_PX_FLIPS` | `px_flips` | =a[-b]: px only in those flips | `toolkit:src/d3d/nv2a_pb_d3d11.c:2201`, `toolkit:src/kernel/nv2a_pb_exec.c:5041` |
| `RECOMP_D3D11_PX_MAX` | `px_max` | =n: px line limit (400) | `toolkit:src/d3d/nv2a_pb_d3d11.c:2202`, `toolkit:src/kernel/nv2a_pb_exec.c:5042` |
| `RECOMP_D3D11_PX_CONSTS` | `px_consts` | =a-b,c: px also prints these constants | `toolkit:src/d3d/nv2a_pb_d3d11.c:2057` |
| `RECOMP_D3D11_PX_VERTS` | `px_verts` | px also prints program and vertices | `toolkit:src/d3d/nv2a_pb_d3d11.c:2077` |
| `RECOMP_STUB_LOG` | `stub` | name each unresolved stub reached | generated `src/recomp/gen/recomp_stubs_unresolved.c` (via the exported variable) |
| `RECOMP_PB_REPORT_MS` | `pb_report_ms` | =ms: [PB] report / fb_dump interval (10000, min 100; from upstream) | `toolkit:src/kernel/xbox_memory_layout.c:1638` |

## Debug (`RECOMP_DEBUG=`)

| Old name | New name | Meaning | Read at |
|---|---|---|---|
| `RECOMP_PB_VSH` | `pb_vsh` | =0: no vertex-program interpreter | `toolkit:src/kernel/nv2a_pb_exec.c:1834` |
| `RECOMP_PB_RC` | `pb_rc` | =0: no register combiners (MODULATE) | `toolkit:src/kernel/nv2a_pb_exec.c:2720`, `toolkit:src/kernel/nv2a_pb_exec.c:4307` |
| `RECOMP_PB_FAST` | `pb_fast` | =0: CPU raster without fast paths | `toolkit:src/kernel/nv2a_pb_exec.c:2941` |
| `RECOMP_PB_FAST_AB` | `pb_fast_ab` | compare fast and slow raster per batch | `toolkit:src/kernel/nv2a_pb_exec.c:4238` |
| `RECOMP_PB_BILINEAR` | `pb_bilinear` | =0: CPU raster samples nearest, whatever the filter | `toolkit:src/kernel/nv2a_pb_exec.c:2690` |
| `RECOMP_PB_MIPS` | `pb_mips` | =0: CPU raster samples mip level 0 only | `toolkit:src/kernel/nv2a_pb_exec.c:2707` |
| `RECOMP_PB_CLIP` | `pb_clip` | =0: no near-plane clipping | `toolkit:src/kernel/nv2a_pb_exec.c:3764` |
| `RECOMP_PB_CULL_FLIP` | `pb_cull_flip` | CPU raster culls the other winding | `toolkit:src/kernel/nv2a_pb_exec.c:2779`, `toolkit:src/kernel/nv2a_pb_exec.c:3530` |
| `RECOMP_PB_VSH_AB` | `pb_vsh_ab` | compare vertex-program paths per batch | `toolkit:src/kernel/nv2a_pb_exec.c:4472` |
| `RECOMP_PB_VSH_AB_DUMP` | `pb_vsh_ab_dump` | =prefix: pb_vsh_ab differing batches | `toolkit:src/kernel/nv2a_pb_exec.c:4417` |
| `RECOMP_RASTER_TEST` | `raster_test` | draw a known triangle on every clear | `toolkit:src/kernel/nv2a_pb_exec.c:1093` |
| `RECOMP_ZPASS_FIXED` | `zpass_fixed` | =n: every occlusion report reads n | `toolkit:src/kernel/nv2a_pb_exec.c:4600` |
| `RECOMP_PB_NULL_DRAW_US` | `null_draw_us` | =us: null backend cost per draw | `toolkit:src/kernel/nv2a_pb_exec.c:4993` |
| `RECOMP_PB_INJECT_STOP` | `pb_inject_stop` | =n: stop every nth walk (test hook) | `toolkit:src/kernel/nv2a_pb_scan.c:315`, `toolkit:src/kernel/nv2a_pb_scan.c:316` |
| `RECOMP_FAST_KICK` | `fast_kick` | =0: ack loop ticks at Sleep(1) | `toolkit:src/kernel/xbox_memory_layout.c:1340` |
| `RECOMP_FORCE_RETURN` | `force_return` | honour forced returns in the build | `toolkit:src/kernel/xbox_memory_layout.c:2448` |
| `RECOMP_TRAP_NULL` | `trap_null` | guest page zero faults | `toolkit:src/kernel/xbox_memory_layout.c:2611`, `toolkit:tests/memory_layout_posix/test_main.c:267`, `toolkit:tests/memory_layout_posix/test_main.c:294` |
| `RECOMP_DSP_ACK` | `dsp_ack` | =va,...: zero these words (no APU) | `toolkit:src/kernel/xbox_memory_layout.c:678` |
| `RECOMP_APU_DSP_ACK` | `apu_dsp_ack` | =auto\|va,...: APU DSP acks the GP doorbell, or these words. **Game default** `auto` (`RECOMP_ENV_GAME_DEFAULTS` in `cat:src/env/recomp_env_game.h`): the doorbell is GP scratch page 0 + 0x810, the page read from the `GPSADDR` scatter-gather table the title programs, so it follows the contiguous allocator (it was the constant `0x80A1C810`; upstream's page-0 reservation moved it to `0x80A20810`); `=0` turns it off | `toolkit:src/apu/apu_dsp.c` |
| `RECOMP_APU_SOLO` | `apu_solo` | =voice: mix only this APU voice | `toolkit:src/apu/apu_core.c` |
| `RECOMP_APU_VOICE_DUMP` | `apu_voice_dump` | =voice\|all: raw s16 stereo samples of one APU voice to a file; `all` writes `<file>.<voice>.raw` for every voice that renders (slots differ between runs). `blinx2 audio-check --voice-dump` finds replays in them | `toolkit:src/apu/apu_vp.c:768` |
| `RECOMP_APU_VOICE_DUMP_FILE` | `apu_voice_dump_file` | =path: apu_voice_dump output, default voice_dump.raw | `toolkit:src/apu/apu_vp.c` |
| `RECOMP_APU_MIXDOWN_ALL` | `apu_mixdown_all` | =0: mix only two bins | `toolkit:src/apu/apu_dsp.c:92` |
| `RECOMP_APU_FAULT_BENCH` | `apu_fault_bench` | =n: time n trapped APU accesses (game) | `cat:src/main.c:973`, `cat:src/main.c:975` |
| `RECOMP_POKE` | `poke` | =va:value,...: write guest words | `toolkit:src/kernel/xbox_memory_layout.c:715` |
| `RECOMP_WORKERS` | `workers` | =inline: run worker threads inline | `toolkit:src/kernel/kernel_bridge.c:951`, `toolkit:src/kernel/kernel_bridge.c:8261` |
| `RECOMP_GUEST_CPUS` | `guest_cpus` | =all: the title's threads on every host core; =<n>: that core. **Default: one core**, as on the console's one CPU: the main thread and every PsCreateSystemThreadEx worker are pinned to the lowest core the process may use (Win32 and Linux; macOS has no thread affinity and says so once). BLiNX 2's stage loader and its loader thread add lights to one global pool with a read-modify-write that only interleaves at a quantum boundary on one CPU; on two cores it lost entries and the terrain baked black (dark water, 2026-10-07) | `toolkit:src/kernel/kernel_thread.c:460` |
| `RECOMP_CS_MODE` | `cs_mode` | =single: one lock for every guest lock | `toolkit:src/kernel/kernel_rtl.c:253` |
| `RECOMP_ASYNC_IO` | `async_io` | asynchronous file I/O | `toolkit:src/kernel/kernel_bridge.c:3810` |
| `RECOMP_UNIMPL_TRAP` | `unimpl_trap` | stop at an unimplemented instruction | `toolkit:templates/new-game/src/recomp_manual.c:188`, `cat:src/recomp_manual.c:774` |
| (none) | `cpuid_mmx` | =1: cpuid reports MMX (leaf 1 edx bit 23) and with it FXSR and SSE (bits 24, 25). Default masked, all three, so the CPU stays self-consistent: with MMX, D3DX's JPEG decoder switches to its MMX IDCT (sub_00307F41), which has never run lifted | `toolkit:src/kernel/kernel_hal.c:1235` |
| `RECOMP_D3D11_MEMO` | `d3d11_memo` | =0: no D3D11 state memo | `toolkit:src/d3d/nv2a_pb_d3d11.c:80` |
| `RECOMP_D3D11_NO_CULL` | `d3d11_no_cull` | D3D11 culls nothing | `toolkit:src/d3d/nv2a_pb_d3d11.c:974` |
| `RECOMP_D3D11_CULL_FLIP` | `d3d11_cull_flip` | D3D11 culls the other winding | `toolkit:src/d3d/nv2a_pb_d3d11.c:976` |
| `RECOMP_D3D11_NO_MIPS` | `d3d11_no_mips` | D3D11 uploads level 0 only | `toolkit:src/d3d/nv2a_pb_d3d11.c:1165` |
| `RECOMP_D3D11_POINT` | `d3d11_point` | D3D11 point sampling | `toolkit:src/d3d/nv2a_pb_d3d11.c:1432` |
| `RECOMP_D3D11_NO_RTT` | `d3d11_no_rtt` | D3D11 decodes render targets from memory | `toolkit:src/d3d/nv2a_pb_d3d11.c:1672` |
| `RECOMP_D3D11_DEBUG_PS` | `d3d11_debug_ps` | =name: replace pixel shaders | `toolkit:src/d3d/nv2a_pb_d3d11.c:1723` |
| `RECOMP_D3D11_DEBUG_PS_SKIP_POST` | `d3d11_debug_ps_skip_post` | debug_ps spares post passes | `toolkit:src/d3d/nv2a_pb_d3d11.c:2664` |
| `RECOMP_D3D11_OCC` | `d3d11_occ` | =sync\|fixed: D3D11 occlusion mode | `toolkit:src/d3d/nv2a_pb_d3d11.c:2922`, `toolkit:tests/d3d11_backend_smoke/smoke.c:649` |
| `RECOMP_METAL_NO_MIPS` | `metal_no_mips` | Metal uploads level 0 only | `toolkit:src/d3d/nv2a_pb_metal.m:776` |
| `RECOMP_METAL_POINT` | `metal_point` | Metal point sampling | `toolkit:src/d3d/nv2a_pb_metal.m:968` |
| `RECOMP_METAL_NO_RTT` | `metal_no_rtt` | Metal decodes render targets from memory; implies `metal_writeback=always` | `toolkit:src/d3d/nv2a_pb_metal.m:1388` |
| `RECOMP_METAL_OCC` | `metal_occ` | =sync\|fixed: Metal occlusion mode | `toolkit:src/d3d/nv2a_pb_metal.m:1621` |
| (none) | `metal_present` | =layer\|readback: how Metal frames reach the SDL window. `layer` (default): a CAMetalLayer window; the backend blits its frame into a GPU slot and the main thread draws it, with no CPU copy. `readback`: the old texture readback and `SDL_UpdateTexture`. The window falls back to `readback` by itself when the layer cannot be made | `toolkit:src/video/fb_present_sdl.c:554` |
| (none) | `metal_writeback` | =lazy\|always: when Metal copies a render target into guest memory. `lazy` (default): only when something reads it (fb_dump, fb_dump_at, the report dump, a texture decode over it, eviction of a presented target). `always`: the present surface at every flip, as before | `toolkit:src/d3d/nv2a_pb_metal.m:1777` |
| (none) | `metal_fb_guard` | trap title access to the last Metal present surface (pages PROT_NONE after each flip); a read is logged with thread and pc and switches the run to `metal_writeback=always`, a write is logged once. Debug only: kernel-side I/O into those pages fails while armed | `toolkit:src/d3d/nv2a_pb_metal.m:1950` |
| (none) | `rt_alias_check` | =0: Metal and D3D11 keep a render target whose guest memory the title has rewritten (as before rt-stale-alias): it is bound in place of the new texels and, on Metal, written back over them. Default on: a target not drawn this flip whose bytes no longer hash as at its creation or last write-back is dropped without a write-back (one line per drop, the first 20; the count in the present summary) | `toolkit:src/d3d/nv2a_pb_metal.m:526`, `toolkit:src/d3d/nv2a_pb_d3d11.c:583` |
| `RECOMP_FB_VA` | `fb_va` | =va: framebuffer window shows that address | `toolkit:src/video/fb_present.c:52`, `toolkit:src/video/fb_present.c:68` |
| `RECOMP_USB` | `ohci` | emulated OHCI/XID USB (unused path) | `toolkit:src/usb/ohci.c:1076` |
| `RECOMP_USB_PORT` | `usb_port` | =n: USB pad port | `toolkit:src/usb/ohci.c:909` |
| `RECOMP_USB_HC` | `usb_hc` | =1: pad on the second controller | `toolkit:src/usb/ohci.c:1082` |
| `RECOMP_USB_NDP` | `usb_ndp` | =n: root-hub ports, 1..4 | `toolkit:src/usb/ohci.c:1083` |
| `RECOMP_PAD_PRESS` | `pad_press` | =mask: pulse these buttons (USB pad) | `toolkit:src/usb/usb_gamepad.c:254` |
| `RECOMP_FB_DUMP` | `fb_dump` | =prefix: frame dumps (CPU/Metal, window) | `toolkit:src/kernel/nv2a_pb_exec.c:765`, `toolkit:src/kernel/nv2a_pb_exec.c:790`, `toolkit:src/kernel/nv2a_pb_exec.c:852` +2 |
| `RECOMP_FB_DUMP_AT` | `fb_dump_at` | =flips: fb_dump at these flips | `toolkit:src/kernel/nv2a_pb_exec.c:795` |
| `RECOMP_FB_DUMP_FLIPS` | `fb_dump_flips` | =n: fb_dump every nth flip | `toolkit:src/kernel/nv2a_pb_exec.c:5286` |
| `RECOMP_FB_WINDOW_DUMP_EVERY` | `fb_window_dump_every` | =n: window dump period | `toolkit:src/video/fb_present.c:324` |
| `RECOMP_WINDOW_SHOT` | `window_shot` | =flips: SDL window shots | `toolkit:src/video/fb_present_sdl.c:280` |
| `RECOMP_WINDOW_SHOT_PREFIX` | `window_shot_prefix` | =prefix: window shot files | `toolkit:src/video/fb_present_sdl.c:306` |
| `RECOMP_TEX_DUMP` | `tex_dump` | =prefix: textures, first use | `toolkit:src/kernel/nv2a_pb_exec.c:1257` |
| `RECOMP_TEX_DUMP_EVERY` | `tex_dump_every` | =n: tex_dump every nth bind too | `toolkit:src/kernel/nv2a_pb_exec.c:351` |
| `RECOMP_VSH_DUMP` | `vsh_dump` | =prefix: vertex programs, raw | `toolkit:src/kernel/nv2a_pb_exec.c:2074` |
| `RECOMP_D3D11_DUMP` | `d3d11_dump` | =prefix: D3D11 present 60k+1 (golden) | `toolkit:src/d3d/nv2a_pb_d3d11.c:2710` |
| `RECOMP_FMV_DUMP` | `fmv_dump` | =prefix: two movie frames | `toolkit:src/video/video_pump.c:144`, `toolkit:src/video/video_pump.c:147` |
| `RECOMP_AUDIO_WAV` | `audio_wav` | =path: WAV of the audio output | `toolkit:src/apu/apu_core.c:222` |
| `RECOMP_AUDIO_WAV_SECS` | `audio_wav_secs` | =s: audio_wav length cap | `toolkit:src/apu/apu_core.c:223` |
| `RECOMP_MEM_DUMP` | `mem_dump` | =va,bytes,prefix: guest memory dumps (game) | `cat:src/main.c:806` |
| `RECOMP_MEM_DUMP_EVERY` | `mem_dump_every` | =s: mem_dump period, default 20; 0 dumps only at `memdump LABEL` steps of an input script (game) | `cat:src/main.c:806` |
| (none) | `pad_peek` | =va:n[:x],...: guest dwords (float, or hex with `:x`) printed on every scripted pad poll (game) | `cat:src/pad_input.c:1169` |
| `RECOMP_THREAD_DUMP` | `thread_dump` | dumps every thread (game): SIGUSR1 on macOS, `touch thread_dump.trigger` in the game dir on Windows/Proton | `cat:src/main.c:753`, `cat:src/main.c:1169` |
| `RECOMP_WATCH` | `watch` | =spec: write watchpoint on a guest address. On Win32 a watch on the contiguous window or the tiled aperture traps both views of the page and a re-arm thread puts the protection back every 20 ms (a title's own VirtualProtect takes it off), naming the changes it missed; the POSIX watch covers the one view | `toolkit:src/kernel/xbox_memory_layout.c:2197` |
| `RECOMP_WATCH_RAW` | `watch_raw` | watch also prints the raw frame | `toolkit:src/kernel/xbox_memory_layout.c:1909` |
| `RECOMP_WATCH_DEPTH` | `watch_depth` | =n: watch stack depth (14) | `toolkit:src/kernel/xbox_memory_layout.c:2008` |
| `RECOMP_WATCH_LEN` | `watch_len` | =bytes: watch range | `toolkit:src/kernel/xbox_memory_layout.c:2103` |
| `RECOMP_WATCHDOG_SECS` | `watchdog` | =s: dump and exit after s seconds | `toolkit:src/kernel/xbox_memory_layout.c:2400` |
| `RECOMP_PAD_SCRIPT` | `pad_script` | =ms:btn[+btn][:hold],... or =@file: timed pad presses (from upstream; takes commas) | `toolkit:src/usb/usb_gamepad.c:412` |
| `RECOMP_PAD_LIVE` | `pad_live` | =file: press each line appended to it, btn[+btn][:hold] (from upstream) | `toolkit:src/usb/usb_gamepad.c:462` |
| (none) | `vblank_clock` | =ms: the timer thread's previous loop, vblanks on the whole-millisecond grid with `Sleep(ms)`, for A/B against the nanosecond schedule (default); logs one `[NV2A] vblank clock:` line | `toolkit:src/kernel/kernel_bridge.c:2805` |
| (none) | `missing_list` | =path: write the unique misses of the missing-file report once, at the first summary point (a later exit leaves the file alone), one `<class> <attempts> <guest> <host>` line each (`class`: high, low, other, probe), replacing the file | `toolkit:src/kernel/kernel_missing.c:327` |
| (none) | `irq_safe_points` | =0: device interrupts (vblank, APU, OHCI) that find the one-CPU gate held run beside its holder, after the old hold-offs (APU 50 frames, OHCI 500 polls, vblank none), with an `[IRQ] ... runs ungated beside gate holder` line for the first 20 per line. Default: posted, and the holder runs the routine on its own thread at its next safe point (a kernel call, a spin-wait yield, the gate's release), never alongside; an `[IRQ]` summary under the 600-vblank line (posted, run on the holder, longest wait per line) when anything was posted | `toolkit:src/kernel/kernel_hal.c:345` |
| (none) | `irq_safe_ms` | =ms: how long a posted interrupt waits for the holder's safe point before the `[IRQ] wait:` line (holder thread, raise site, pending lines), repeated every second while it lasts; default 250. A wait line names a guest loop at DISPATCH that wants a `config/spin_waits.json` entry | `toolkit:src/kernel/kernel_hal.c:347` |
| (none) | `irq_safe_force` | =1: past `irq_safe_ms`, deliver the interrupt beside the holder anyway (A/B for a title that spins at DISPATCH on something only an ISR does; it reinstates the race the safe points remove) | `toolkit:src/kernel/kernel_hal.c:346` |

## Deleted

The `RECOMP_WHITE_*` probes from the white-geometry investigation are gone, along with their code in `nv2a_pb_exec.c` (batch trace, pixel probe, raw-vertex dump, per-flip surface dumps) and `nv2a_pb_d3d11.c` (batch selection for the trace). No script, scenario or env file used them; they appear only in historical notes.

| Name | What it did |
|---|---|
| `RECOMP_WHITE_TRACE` | `[WHITE]` trace of up to N large batches (vertices, stages, attributes) |
| `RECOMP_WHITE_MIN` | minimum vertex count for a traced batch (default 300) |
| `RECOMP_WHITE_TEXOFF` | trace batches that sample the texture at this address instead |
| `RECOMP_WHITE_PX` | `x,y`: trace the batch that paints this pixel white |
| `RECOMP_WHITE_RAW` | raw bytes of a traced batch's first vertices |
| `RECOMP_WHITE_DUMP` | dump every surface drawn in a flip to this prefix |
| `RECOMP_WHITE_EVERY` | flip interval for WHITE_DUMP (default 30) |

## Launcher variables

The packaged launchers (`BLiNX2.app`, `BLiNX2.exe`, the steamos `launch.sh`)
read these before the game starts; the game itself never sees them, so they
are not `recomp_env` keys.

| Name | Where | Meaning |
|---|---|---|
| `BLINX2_DATA_DIR` | macOS and Windows launchers | user-data root instead of `~/Library/Application Support/BLiNX2` or `%LOCALAPPDATA%\BLiNX2` (`hdd/`, `config/`, `logs/` follow it). Tests set it to a scratch folder so they never touch the player's data |
| `BLINX2_ROOT` | steamos `install.sh` | install and data root instead of `~/Games/BLiNX2` (same as `--root`) |
| `LOG_KEEP` | all launchers, from `launch.env` | game logs kept in `logs/` (default 10) |
| `PROTONPATH` | steamos `launch.sh`, from `launch.env` | the Proton build `umu-run` uses (default `GE-Proton`) |
| `UMU_RUN` | steamos `launch.sh`, from `launch.env` | the `umu-run` to use, before the search (PATH, `~/.local/bin`, the installer's copy) |
| `LAUNCH_NOTICE` | steamos `launch.sh`, from `launch.env` | `0` turns off the first-launch notice (default on) |
| `LOG_MAX_MB` | steamos `launch.sh`, from `launch.env` | at launch, a log in `logs/` over this many MB is cut to its first and last halves (default 64; `0` keeps them whole) |
| `PROTON_LOG, PROTON_LOG_DIR` | Proton, steamos `launch.sh` | `PROTON_LOG=1` in `launch.env` writes Proton's own log; the launcher points `PROTON_LOG_DIR` at `logs/` |
| `NOTICE_MAX` | steamos `launch.sh`, from `launch.env` | seconds the first-launch notice stays up at most (default 1200) |

## Not in the table

These are read with plain `getenv` and are out of scope:

| Name | Where | Why |
|---|---|---|
| `HOME, XDG_DATA_HOME` | toolkit:src/kernel/kernel_path.c | host paths, not ours |
| `RECOMP_STUB_LOG` | generated recomp_stubs_unresolved.c | emitted by the recompiler; fed from `RECOMP_TRACE=stub` |
| `MSL_DUMP, MSL_NO_COMPILE, MSL_EXPECT_OUT` | toolkit:tests/d3d8_msl_split | test-local |
| `HLSL_DUMP, HLSL_EXPECT_OUT` | toolkit:tests/d3d8_hlsl_split | test-local |
| `SMOKE_PRINT_HLSL` | toolkit:tests/d3dcompile_smoke | test-local |
| `RECOMP_SMOKE_BACKEND, RECOMP_SMOKE_DUMP` | toolkit:tests/nv2a_backend_smoke | test-local |
| `RECOMP_TEST_MIXDOWN_EXPECT` | toolkit:tests/apu_mixdown | test-local |
| `INPUT_MAP_README_OUT` | toolkit:tests/input_map | test-local |
| `RECOMP_BENCH_RUN, RECOMP_RUN_LOCK` | xboxrecomp-cli bench (host scripts), scripts/vpad.py | script-side only; the game never reads them |
| `BENCH_PROTON_LOG` | xboxrecomp-cli bench | Proton's log per run (`steam-default.log`): `cap` keeps its first and last 8 MiB and `logs` pulls none larger (default), `full` (or `--proton-log`) keeps and pulls all of it, `off` does not write it |
| `BENCH_*`, `LLVM_MINGW_ROOT, LLVM_MINGW_TAG, PROTONPATH, XBOXRECOMP_DIR` | xboxrecomp-cli (`blinx2 bench --help`) | the bench's host settings, from the environment or `scripts/bench.env`; the game never reads them |
| `XBOXRECOMP_CLI_DIR` | blinx2.py | which xboxrecomp-cli checkout `./blinx2` runs (docs/packaging.md); the game never reads it |
| `SDL_AUDIODRIVER` | toolkit:src/apu/apu_sdl2.c | SDL's own variable. With `RECOMP_HEADLESS` the SDL audio backend sets it to `dummy` unless it is already set, so headless runs make no sound |

Adding a variable: add a row to `RECOMP_ENV_KEYS` (pick the tier by the rules above), read it with `recomp_env(RENV_X)` / `recomp_env_on` / `recomp_env_int`, and add it to this file. Never call `getenv` directly.
