## Why

The user (2026-10-18): "Assess in-game native 16:9 support, for any game that does support it, offer it through the config.toml file". This is paired with the Hor+ edge glitches left on Burnout 3, fixed like BLiNX 2's.

The spike checked all four games. Each one reads the dashboard video flags through `XGetVideoFlags`. The kernel answers the `XC_VIDEO` EEPROM query with `WIDESCREEN | HDTV`, but its defines are in the `XGetVideoFlags` domain (0x01, 0x02), not the raw EEPROM domain (bits 16 and up). `XGetVideoFlags` returns `(raw >> 16) & 0x5F`, so every game sees 0: standard 4:3, no letterbox, no HDTV modes, no PAL-60. The "always widescreen" answer is in effect "never widescreen", and it changes no game's picture today.

| Game | Flags read (XGetVideoFlags, caller) | In-game option | With the widescreen bit | Recommendation |
|---|---|---|---|---|
| BLiNX 2 | `sub_00298AA3`, once from `sub_0005F960` at 0x0005F99F: PAL-60 bit only (0xEC4BF4) | none | none | Hor+ only (`display.aspect`) |
| Burnout 3 | `sub_001CF913` from `sub_0003C8A0` (0x0003C8AF): `flags & 1` to byte 0x4D617D; `sub_0003D690` (0x0003D743, 0x0003D78D): PAL-60 and 480p; `sub_00020760`: PAL-60 | "Aspect Ratio 4:3 / 16:9" in the options (Globalus.bin) | anamorphic: `sub_0002F380` projects at 16/9 (x1.2 FOV factor) into the same 640x480, and present flags gain `D3DPRESENTFLAG_WIDESCREEN` | native anamorphic plus the present stretch |
| SSX 3 | `sub_00181940` from `sub_001226F0` (0x001226FE) and `sub_001D1720`: widescreen gives 2, letterbox gives 1, to settings bits 20-21 of 0x33925C | "Widescreen: Off / 16:9 / Anamorphic" (`sub_0008F4C0`), the dashboard seeds it | anamorphic when Anamorphic, letterboxed 16:9 when 16:9 | native anamorphic plus the present stretch, following the in-game setting |
| Spartan | `sub_001B2309` from `sub_0019D730` and `sub_001AFF10`: PAL-60 with the video standard | none | none | Hor+ only |

Two games draw a true 16:9 picture squeezed into 640x480 when told to. Shown as-is, that picture is too narrow. Today an SSX 3 player who picks Anamorphic in its menu gets that squeezed picture at 4:3, with nothing to undo it. Native mode adds the console setting and the TV's half: it sets the dashboard bit and stretches the frame to 16:9 at present. The result is the game's own wide framing, HUD and culling included, which Hor+ cannot give (Hor+ keeps the 4:3 frustum's pop-in at the edges).

Hor+ stays the answer for the games without native support, and the tracker item's two edge glitches are classifier gaps that also affect any other title that copies a frame into a texture.

## What Changes

- **`display.widescreen = "off" | "native"`** (env `RECOMP_DISPLAY_WIDESCREEN`, default `off` = stock), in `config.toml` beside `display.aspect`.
  - On a game that declares native support, `native` sets the dashboard widescreen bit and stretches the 640x480 frame to 16:9 at present, on Metal and D3D11, whenever the game's declared state says it is drawing wide.
  - On a game that does not declare it, the key logs one line and is ignored.
  - With `native` active, Hor+ is off. `display.aspect` is ignored with a log line, since widening an already-wide projection would double it.
- **EEPROM video flags, config-driven.**
  - The `XC_VIDEO` defines are corrected to the raw EEPROM bits (`0x00010000` widescreen, `0x00020000` 720p, `0x00040000` 1080i, `0x00080000` 480p, `0x00100000` letterbox, `0x00400000` PAL-60). The return-domain names `XC_VIDEO_FLAGS_HDTV` and `_PAL_I` go away, and the header comment in `kernel_xbox.c` is fixed to match.
  - The answer comes from one function, `xbox_video_flags_raw()`, which defaults to 0. It reads only `nv2a_host_opts`, never the enhancements layer, so a build without the layer gets 0. That is the stock value: what every game sees today, what every golden was recorded on, and a factory console's setting for a 4:3 TV with no HDTV modes enabled.
  - `display.widescreen = native` adds the widescreen bit. The debug key `RECOMP_DEBUG=video_flags=0x...` sets the raw word for spikes.
  - The AV-pack and encoder answers stay as they are.
- **Per-game declaration.**
  - `[display] native = "anamorphic"` in `game.toml` (b3, ssx3). The CLI reads it for the wizard and README option, and for the gate that a stock golden never runs with the key on.
  - The game's C code registers the state probe through `enhance_native_register()`, before `xbox_enhance_init`: a guest address, a mask and the "wide" value. B3's is byte 0x4D617D == 1, and SSX 3's is `0x33925C & 0x300000 == 0x200000`.
  - Without a probe the stretch is always on under `native`.
- **Present stretch.** The shared fit `nv2a_present_rect()` gains a display-aspect argument. Metal and D3D11 pass `nv2a_present_dar()` (16:9 while the game draws wide), and SDL passes the frame's own shape. The D3D11 unscaled-copy shortcuts, the internal-surface path (an 854-wide drawable or swap chain) and the window's initial size follow it, with `nv2a_host_window_w` given a native case. The native state lives in `nv2a_host_opts`, so the kernel and the presenters never link the enhancements layer. The CPU rasteriser ignores the stretch and logs it.
- **Hor+ edge fixes**, generic rules first:
  - **Frame copies are render targets.** A guest texture whose surface is a padded render target's write-back, or a copy of one, is bound as that host target and read whole. This fixes the speed-blur and glow seam at x = 107 and 747 (`C8AF571F`, 320x240 at 0x80A98000). The cause is pinned with `RECOMP_TRACE=aspect`, and the design gives the rule for each likely cause.
  - **Tiled backdrops.** The ~16 px grid strip in the menus is probed with `RECOMP_TRACE=aspect`, and the matching rule is in the design.
  - **Override fallback.** `[aspect.program]` (by the program hash the `aspect` trace prints) and `[aspect.texture]` (by address, format and size) in a game's `config.default.toml` force one class, only for cases no generic rule reaches.
- **Wizard and menu.**
  - The wizard gains one option of the existing `choice` kind. On BLiNX 2 and Spartan it writes `display.aspect` (4:3, 16:9, 16:10, 21:9; default 4:3). On b3 and SSX 3 it writes `display.widescreen` (off, native; default off), with the 16:9 wording in the label and hint. The wizard does not detect the display.
  - Wide defaults (the user, 2026-10-18): when the player picks a wide display, the wizard defaults to Native on a game that declares it (b3, ssx3), and to Hor+ (`display.aspect`) on the others (BLiNX 2, Spartan).
  - There is no in-game overlay menu in this change.

## Capabilities

### Modified Capabilities
- `enhancements`: new requirements "Native widescreen", "Dashboard video flags", "Hor+ frame copies", "Hor+ tiled backdrops" and "Hor+ placement overrides". "Enhancements default to stock" is modified, building on `changes/enhancements-hor-plus`'s version of it (which is archived first): `display.widescreen` joins the key list, the golden refusal list and the stock `[ENHANCE]` line.

## Impact

- **Toolkit** (fork-first, on a branch off `posix-host/portability`):
  - `src/kernel/kernel.h`, `kernel_xbox.c` (the defines and `xbox_video_flags_raw`);
  - `src/enhance/enhance.{c,h}` (the key, the registration, filling `nv2a_host_opts`), `enhance_cfg` (the overrides parser);
  - `src/platform/recomp_env.h` (`DISPLAY_WIDESCREEN`, debug `video_flags`, trace `native`);
  - `src/kernel/nv2a_backend_common.{c,h}` (the native fields of `nv2a_host_opts`, `nv2a_present_dar`, the `nv2a_present_rect` argument, the copy-provenance table);
  - `src/video/fb_present_metal.m`, `src/video/fb_present_sdl.c` (passes `w:h`), `src/d3d/nv2a_pb_d3d11.c`, `src/d3d/nv2a_pb_metal.m`;
  - `tests/` (flags, dar, the fit, the registration order, provenance, `tests/enhance_cfg` for the overrides);
  - `docs/runtime/config.md`.
- **cat**: `docs/env.md` (three rows: config `RECOMP_DISPLAY_WIDESCREEN`, debug `video_flags`, trace `native`, and the tier counts), `packaging/config.default.toml` (the `widescreen` line, `off`), `TASKS.md`, this change. BLiNX 2 declares no native mode.
- **b3, ssx3**: `game.toml [display]` and the wizard option, the probe registration in game code, and `config.default.toml`. **Spartan**: the wizard option (Hor+).
- **CLI** (first, since the manifest rejects unknown tables):
  - `manifest.py`: the `[display]` table, and `display.widescreen` in `TOOLKIT_ENHANCE_KEYS`;
  - `golden.py`: `display.widescreen=off` in `ENHANCE_STOCK`;
  - optional: `labels` for `choice` options (the CLI and the Go wizard).
  - The game repos then bump their `[cli]` pins.
- **Goldens**: none change. Stock keeps raw flags 0 and no stretch, which is byte for byte what main runs today. The kernel answer is shared by every game, so the b3 stock goldens run too.
- **Upstream**: all of it is fork-only for now (the user, 2026-10-18). The define fix and `xbox_video_flags_raw` are the only upstream candidates. They are not in the next upstream PR round, and are revisited at the upstream re-assessment. The native mode, the present stretch and the classifier rules sit on the fork's enhancements layer (`XBOXRECOMP_ENHANCE`), which upstream's toolkit does not have (b3 `src/game/main.c:880`: without the layer, `-DXBOXRECOMP_ENHANCE=OFF` or upstream's toolkit, `host_enhance_init` is empty).
