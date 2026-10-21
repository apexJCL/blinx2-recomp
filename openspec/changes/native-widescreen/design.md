## Context

- **The EEPROM answer.**
  - `ExQueryNonVolatileSetting(XC_VIDEO = 8)` (`kernel_xbox.c:147`) returns `XC_VIDEO_FLAGS_WIDESCREEN | XC_VIDEO_FLAGS_HDTV`, which is 0x03.
  - The XDK's `XGetVideoFlags` (statically linked in each title) returns `(raw >> 16) & 0x5F`. If the AV pack is not HDTV or the standard is not NTSC-M, it then clears the HDTV bits with `& ~0x0E`.
  - In the return domain the bits are: widescreen 0x01, 720p 0x02, 1080i 0x04, 480p 0x08, letterbox 0x10, PAL-60 0x40.
  - So the raw word wants those bits shifted left by 16. The toolkit's defines are the return-domain values, so every title sees 0.
  - Index 8 is queried only through `XGetVideoFlags` in all four games. The other `ExQueryNonVolatileSetting` callers ask for 7, 9, 0xA, 0x100-0x104 and 0x11.
- **Per-game behaviour.** The proposal's table, from the generated code (read-only) and string scans of the game files.
  - **Burnout 3:**
    - `sub_00015A60` calls `sub_0003C8A0` on the video block at 0x4D6170. That stores `(flags & 1)` at +0xD (0x4D617D) and sets 640x480.
    - `sub_0002F380` reads +0xD and projects with aspect 16/9 (0x3B18EC) and a 1.2 factor (0x3B1768) instead of 4/3 (0x3B181C) and 1.0.
    - `sub_0003D690` sets `D3DPRESENTFLAG_WIDESCREEN` (0x10) in the present parameters from the same byte.
    - The "Aspect Ratio / 4:3 / 16:9" strings sit next to "Adjust Screen" in Globalus.bin. The menu code that writes +0xD was not pinned statically: there are no absolute writes, and the `+0xD` writers checked are unrelated. Task 1.3 pins it with `RECOMP_WATCH`.
  - **SSX 3:**
    - `sub_001226F0` maps the flags to [obj+0x28]: 1 when widescreen, 2 when letterbox (`(flags >> 3) & 2`), otherwise 0.
    - `sub_00050850` seeds the settings word 0x33925C, bits 20-21, from that value: widescreen gives 2 (Anamorphic), letterbox gives 1 (16:9, letterboxed), otherwise 0 (Off).
    - The options page `sub_0008F4C0` shows Off, 16:9 and Anamorphic (`kT_CMNOff`, `kT_19Widescreen169`, `kT_19WidescreenAnimorphic`). Its setter `sub_0008E0D0` writes `(v << 20) & 0x300000`, and the renderer (`sub_000E1F10`) passes the mode to the display object [0x379680].
    - The setting is saved with the profile, so the dashboard bit only picks a fresh profile's default.
  - **BLiNX 2 and Spartan:** they read only the PAL-60 bit (with the video standard) to pick 50 or 60 Hz. There are no widescreen strings in their game files.
- **The present today.** `present.filter` picks the letterbox fit (nearest or linear) or the integer fit. Both fits use the presented surface's own shape, which is 4:3 for an unpadded 640x480 and wider for a padded Hor+ target. The window's initial width is `nv2a_host_window_w`.

## Goals / Non-Goals

**Goals**
- Make a game's own 16:9 mode available from `config.toml` on the games that have one, with the right picture on Metal and D3D11.
- Make the EEPROM answer correct, in one place, with a stock value that leaves every golden unchanged.
- Fix the tracker item's two Hor+ edge glitches with generic rules, and add the per-hash fallback.

**Non-Goals**
- Exposing HDTV modes (480p, 720p, 1080i) or PAL-60 to players. Burnout 3 picks a progressive present flag on 480p, but the host has no interlace, so nothing changes on screen. They stay reachable through the debug key.
- Letterboxed 16:9 (SSX 3's "16:9"). It is the game's own choice in its menu and needs nothing from us.
- An in-game overlay menu.
- Native widescreen above 16:9: the games' wide projections are fixed at 16/9. A 21:9 window pillarboxes the 16:9 picture.

## Decisions

### D1. One key with two values, not a third `display.aspect` value

`display.widescreen = "off" | "native"`. `display.aspect` stays the shape of the Hor+ target, which is a different thing: it widens the guest's render targets. Native mode does not touch them. It sets a console setting and changes only the present.

Keeping the two keys apart means:
- a player's `aspect = "16:9"` keeps working on every game;
- `native` can be the wizard's pick on b3 and ssx3 without changing the other games' configs.

Wizard defaults (the user, 2026-10-18): when the player picks a wide display, the wizard writes `display.widescreen = "native"` on a game whose `game.toml` declares native support (b3, ssx3), and `display.aspect = "<ratio>"` (Hor+) on the others (BLiNX 2, Spartan). A player can still pick Hor+ on b3 or ssx3 by hand. D9 says how.

Alternatives considered:
- `display.aspect = "native"` would lose the ratio on games without native support.
- A separate `[video]` table would put a display choice away from its siblings.

### D2. Native and Hor+ never stack

When `native` is active on a declaring game, Hor+ is off for the run:
- `nv2a_host_opts()->aspect_w/aspect_h` are left at stock 0:0 (no padding);
- the log reads `display.aspect=16:9 ignored: display.widescreen=native`.

Stacking would pad an already-16:9 projection to 16:9 again: the picture would be 1.33x too wide, with Hor+'s classifier at work on a frame that needs none.

On a game without a registration, `native` logs `display.widescreen=native: no native widescreen registered; ignored` and Hor+ follows `display.aspect` as before. The decision comes from the registration's absence, not from a list of games.

### D3. EEPROM: correct defines, stock raw 0, one function, no link to the layer

The kernel and the presenters never link the enhancements layer (toolkit `docs/runtime/config.md`). Without the layer every host option is zero. So native state lives in `nv2a_host_opts` (`nv2a_backend_common.h`), beside `aspect_w/h`:

```c
    /* display.widescreen=native on a game that registered it (enhance.c
     * fills these; 0 without the layer = stock): the dashboard widescreen
     * bit, and the present stretch while the probe reads wide. */
    int      native_active;
    uint32_t native_va;         /* 0 = always wide */
    unsigned native_size;       /* 1, 2 or 4 bytes */
    uint32_t native_mask, native_wide;
```

`xbox_enhance_init` fills them. `xbox_video_flags_raw()` and `nv2a_present_dar()` read only these fields, never an `enhance_*` call. A build without the layer (`-DXBOXRECOMP_ENHANCE=OFF`, or upstream's toolkit) gets 0 and no stretch, and the define fix stands alone.

- `kernel.h` gets the raw-domain defines: `XC_VIDEO_FLAGS_WIDESCREEN 0x00010000`, `_HDTV_720p 0x00020000`, `_HDTV_1080i 0x00040000`, `_HDTV_480p 0x00080000`, `_LETTERBOX 0x00100000` and `_PAL_60Hz 0x00400000`.
  - The old return-domain names `XC_VIDEO_FLAGS_HDTV` and `XC_VIDEO_FLAGS_PAL_I` go away, since neither is a raw EEPROM bit.
  - Task 2.1 checks by grep that nothing else uses them.
- `xbox_video_flags_raw()` builds the answer:
  - 0 by default;
  - `| XC_VIDEO_FLAGS_WIDESCREEN` when `nv2a_host_opts()->native_active`;
  - replaced whole by `RECOMP_DEBUG=video_flags=0x...` when that is set, for spikes, and logged.
- `kernel_xbox.c` returns that function's value, with a comment on why stock is 0.
- The file's header comment (`kernel_xbox.c:122`, "Video: NTSC, widescreen+HDTV enabled") gets the same fix: "Video: NTSC, 4:3, no HDTV modes (raw 0)".

**Why stock is 0, not the corrected `WIDESCREEN | HDTV`:**
- 0 is what every title has seen since the first boot, and every golden, bench timing and save fixture was made with it.
- It is also the factory setting: a console on a 4:3 TV with no HDTV modes enabled.
- Correcting the defines while keeping the old intent (widescreen on) would change two games' stock picture:
  - Burnout 3 would render squeezed with nothing stretching it;
  - SSX 3 would seed Anamorphic into every fresh profile.
- That is exactly what "opt-in features default OFF" forbids. The old comment's intent ("widescreen and HDTV support enabled") was never in effect.

The AV-pack answer (`AV_PACK_HDTV`, NTSC-M, 60 Hz) stays as it is. It keeps the HDTV bits from being masked if a spike sets them, and the games read it only at boot.

### D4. Native state probe: follow the game's own setting

A game that draws wide only some of the time needs the stretch to follow it:
- Burnout 3's player can switch the aspect in its options;
- SSX 3's player can pick Off, 16:9 or Anamorphic, and its saved profile wins over the dashboard bit.

So the game registers what "the game is drawing anamorphic" means:

```c
/* game code, in host_enhance_init before xbox_enhance_init
 * (b3: src/game/main.c, ssx3: src/main.c) */
enhance_native_register(&(struct enhance_native){
    .kind = ENHANCE_NATIVE_ANAMORPHIC,
    .va = 0x4D617D, .size = 1, .mask = 0xFF, .wide = 1,   /* Burnout 3 */
});
/* SSX 3: .va = 0x33925C, .size = 4, .mask = 0x300000, .wide = 0x200000 */
```

- **Order.** `enhance_native_register()` runs before `xbox_enhance_init`, inside each game's `host_enhance_init` under `RECOMP_ENV_HAVE_ENHANCE_KEYS` (b3 `src/game/main.c:884`, ssx3 `recomp/src/main.c:965`). `xbox_enhance_init` reads `display.widescreen`, checks the registration and fills the `nv2a_host_opts` fields (D3). A registration after init logs `enhance_native_register: after init; ignored` and does nothing. A ctest covers both orders.
- At each flip the present reads that guest word, `(word & mask) == wide`, and stretches only then.
- A registration with `va = 0` means always wide under `native`.
- The read is one guest load per flip. At stock nothing is read, because `native` off skips it.
- The registration is game code because the address is a game constant, and the toolkit stays game-agnostic.
- `game.toml [display] native = "anamorphic"` is the declaration the CLI reads. A `scripts/test_*.py` case in each game repo checks that the boot log's `native: anamorphic probe 0x...` line exists when the declaration does, so the two cannot drift.
- Generating the C registration from `game.toml` was considered and rejected (the user, 2026-10-18): the CLI does not emit C, and the probe stays in the game repo's code.

Native never forces the game's setting (the user, 2026-10-18). On SSX 3 it only seeds a fresh profile's default through the dashboard bit, and the stretch follows whatever the player picks.

The probe also explains SSX 3's "16:9" setting: that is letterboxed (`0x100000`), not wide, so the stretch stays off and the game's own bars show at 4:3. That is the stock-faithful picture for that choice.

### D5. Present stretch: through the shared fit

- `nv2a_present_dar(w, h, &num, &den)` (`nv2a_backend_common.c`) gives the display aspect of the presented surface. It reads only `nv2a_host_opts()` and the probe word:
  - `w:h` stock;
  - `16:9` when `native_active` and the probe reads wide.
- **The one fit.** `nv2a_present_rect()` (`nv2a_backend_common.c:1089`) gains the display aspect as `dar_num, dar_den`, and all three callers pass it:
  - Metal: `fb_present_metal.m:365` passes `nv2a_present_dar`;
  - D3D11: `nv2a_pb_d3d11.c:3836` passes `nv2a_present_dar`;
  - SDL/CPU: `fb_present_sdl.c:751` passes `w, h`, so nothing changes there. It logs `display.widescreen ignored` once, and the gap is recorded in TASKS.md.
  - With `dar == w:h` the function returns exactly what it returns today: a ctest compares the old and new results over a grid of sizes.
- **The letterbox fit** fits a `dar`-shaped rectangle instead of `w:h`.
- **The integer branch** uses a whole vertical multiple `k = dst_h / src_h`, with width `src_h * k * dar`.
  - It returns 1 ("whole: drawn at an exact multiple") today; under a stretch the width is not a whole multiple of `src_w`, so it returns 0, and the callers draw through the scaled path.
  - That changes the return value's meaning ("the copy can be 1:1 on both axes") for the stretched case only. The header comment says so, and the callers' "whole" shortcuts are checked in task 3.3.
- **D3D11 shortcuts.** The `stock` and `same` `CopyResource` paths (`nv2a_pb_d3d11.c:3905-3930`) copy the frame unscaled. Both also require `dar == w:h`, otherwise the frame goes through `present_blit`.
- **`present.surface = internal`** (the Deck's gamescope default, `internal(auto)`): the compositor scales the swap chain, keeping its aspect. Under native the swap chain or drawable is made `nv2a_host_window_w` wide, which is 854x480 times the scale, and the frame is blitted stretched into it.
  - `nv2a_host_window_w` (`nv2a_backend_common.c:998`) returns `(w + 2 pad) * scale` today, which is 640 under native since the pad is 0. It gains a native case: `round(h * 16/9) * scale` while `native_active`.
  - That width is fixed for the run. When the probe reads not wide, the fit pillarboxes the 4:3 frame inside the 854-wide surface.
  - Its third caller, `fb_present_sdl.c:556`, passes the 4:3 width explicitly (the SDL path ignores native), noted beside the Hor+ CPU window follow-up in TASKS.md.
  - The surfaces:
  - Metal: the drawable size and `kCAGravityResizeAspect` at `fb_present_metal.m:155-161` take the 854-wide size;
  - D3D11: `internal_resize` makes the swap chain that size, and the blit path runs (not `same`).
  - The window's initial size is also `480 * 16/9 = 854` wide at native.
- **Filter.** The sampler follows `present.filter` as resolved. A nearest 4/3 horizontal stretch repeats every third column, and the shipped `config.default.toml` sets `filter = "nearest"`. So the rule is:
  - under native, the stretch samples linear unless `present.filter` comes from the player: the environment or the player's `config.toml`. `enhance_cfg_source_of("present.filter")` returns `ENHANCE_SRC_ENV` or `ENHANCE_SRC_FILE` for that case, against `ENHANCE_SRC_DEFAULTS` for the shipped file.
  - `enhance.c` stores the result as `present_filter_native` in `nv2a_host_opts`, so the presenters still do not link the layer. The `[ENHANCE]` line says which filter the stretch uses.
- **Unchanged:** the present rect changes and nothing else. Guest targets, write-back, frame dumps and goldens stay 640x480. Host dumps (`metal_host_dump`) stay the presented surface, unstretched.
- A new trace, `native`, logs the probe's value and the stretch when they change, not per flip.
- **Both backends** change together in one change.

### D6. Hor+ frame copies: provenance, then binding

The tracker item found the race seam's source: the glow composite `C8AF571F` samples a 320x240 guest texture at 0x80A98000, which is a copy of the post buffer and not a host render target. So it is a guest texture, it is placed as a picture, and it is centred. The tracker item's speed blur is the same shape or the same pass.

The fix is generic: **a texture that holds a padded target's picture is a render target for placement and sampling.** Two ways that texture comes to exist, and a rule for each:

1. **The game copies a render target on the GPU** (a blit, or a draw into a 320x240 target whose surface the game then textures from).
   - If the destination is a host target, the existing `rt_texture()` lookup already finds it, and the miss means it was not created as one. That happens when the copy is a surface-to-surface blit (NV062/NV09F image-from-CPU or a `D3DDevice_CopyRects` pushbuffer path) that the backends carry out in guest memory.
   - Rule: the blit path records `{dst va, w, h, src target}` in a small provenance table. `rt_texture()` checks it next, and returns a host target made to match:
     - its pad is `nv2a_host_pad(w, h)`, with the source's pad scaled for a downsample;
     - its contents come from a host-side copy (or a downsample) of the source.
2. **The CPU copies the write-back** (a `memcpy` from the guest frame).
   - The backend cannot see that copy. Rule: a texture whose surface pages were last written by the CPU, with a byte range and shape equal to a padded target's write-back range or a 2x downsample of it, is matched by a checksum of its first row against the write-back. On a match it binds the host target.
   - This is costlier and less certain, so it is behind the probe's finding: implement it only if the trace says the copy is CPU-side.

In both cases the batch then has `guest_tex = 0`, and samples a padded target, so it is a stretch over a padded source (`nv2a_aspect_place`). The source is read whole, `nv2a_rt_stretch_read`, and the seam goes.

The probe comes first (task 4.1): `RECOMP_TRACE=aspect` plus a texture trace on the race at 16:9 names the pass, the texture's va, how it is written (pushbuffer blit, draw or CPU), and from which target.

### D7. The menu grid strip

The ~16 px strip at the old 4:3 edges of the menus' grid backdrop has three likely causes. Each has a rule, and the probe (task 5.1) picks one:
- **(a) The backdrop is tiled across 640 columns** as many 2D quads, none of them full width. Each is centred and scissored to the 4:3 frame (design H6 of Hor+), and the pads show the clear. Rule: a set of 2D batches with one texture and one program, whose union spans the full width (cover-sum), is a backdrop and is stretched. The HUD rule from the tracker item is untouched, because the HUD's pieces never tile the full width with one texture.
- **(b) It is full width, but its texture is a picture** (`nv2a_aspect_picture`), so it follows `display.movie` (black). A backdrop that is a repeating grid should fill. Rule: a full-width 2D batch whose texture coordinates span more than one repeat (u range > 1.5 with wrap addressing) is a pattern, not a picture, and is stretched by extending u (Hor+ for a tiled pattern: the pattern continues into the pads without being widened).
- **(c) It is 3D** (a camera-facing plane) culled at the 4:3 edge. That is the documented frustum limit, not a classifier gap: record it and leave it.

### D8. Overrides as the fallback

`[aspect.program]` and `[aspect.texture]` take a class: `stretch`, `centre`, `picture` or `rt`. They are keyed by what the `aspect` trace already prints on both backends, so a maintainer can copy a key from a log (the overrides live only in the shipped `config.default.toml`):
- `[aspect.program]`: by the program hash at the head of the `[aspect.program] %08X flip ...` line (`nv2a_pb_d3d11.c:3047`, and its Metal twin);
- `[aspect.texture]`: by the stage's texture address, format and size, as that line prints them (`0x80A98000 fmt 12 320x240`).
  - The address is masked to its low 27 bits, as `rt_texture` does (`nv2a_pb_d3d11.c:2201`), so 0x80A98000 and 0x00A98000 match the same entry.
  - There is no texture content hash in the trace today, and adding one costs a hash per bind, so the address key is used. That is stable for a game that allocates its post buffers once at boot.
  - A pooled address that another texture of the same format and size reuses would take the override too. Task 8.1 checks each entry across two boots and in a second scene.
- `cat/docs/env.md`'s `aspect` row needs no change.

Rules:
- They live in the game's shipped `config.default.toml`, not in the player's file.
- They are read only when `display.aspect` is wide.
- They apply after the generic rules, so a generic fix makes an override unnecessary rather than conflicting.
- The Hor+ spec dropped `[aspect.program]` because BLiNX 2's HUD is one program. Here the overrides are a per-batch class, not HUD layout, and they are only for the cases D6 and D7 do not reach.
- Each override needs a comment naming the scene and the trace line that justified it.

### D9. Wizard: the existing `choice` kind

Today the wizard has no display option and does not detect the display. Its options are `[[wizard.option]]` entries (b3 `game.toml:158-178`, cat `game.toml:227-246`); SSX 3 and Spartan declare none.

The CLI already has a `choice` kind (`manifest.py:603-609`, `wizard/internal/gamecfg/gamecfg.go:349-353`, `wizard.py:195-206`, `docs/manifest.md:297-303`):
- it writes one config key;
- its default must equal the shipped defaults file's value;
- it shows radio buttons for up to 3 values and a drop-down above that.

The user's decision: a wide display means Native on b3 and SSX 3, and Hor+ on BLiNX 2 and Spartan. Built with that kind:
- **Not detected.** The build may run on another screen than the one it is played on (the Deck docked, a TV), so the player picks.
- **BLiNX 2 (`cat/game.toml`) and Spartan (`spartan/tca/game.toml`):**
  - `kind = "choice"`, `config = "display.aspect"`;
  - `values = ["4:3", "16:9", "16:10", "21:9"]`, `default = "4:3"`;
  - the default matches `cat/packaging/config.default.toml:18`, and Spartan's defaults file gains the same line.
- **b3 and SSX 3:**
  - `kind = "choice"`, `config = "display.widescreen"`, `values = ["off", "native"]`, `default = "off"`;
  - the label and hint carry the wording ("Widescreen 16:9: the game's own wide picture, for a 16:9 screen; on a 21:9 screen it shows pillarboxed");
  - Hor+ stays reachable on these games by hand-editing `display.aspect`.
- **Optional CLI addition:** `labels` for `choice`. Today `labels` is range-only (`RANGE_KEYS`). With it, the values show as "4:3, as on the Xbox" and "Native 16:9" rather than the raw strings. It is not needed for the decision.
- **Gates:** the CLI's pytest and ruff, plus `wizard/check.sh` when the Go side changes (only with the `labels` addition).

### D10. The `[ENHANCE]` line and the golden check

- **The log token.** The `[ENHANCE]` summary line gains `display.widescreen=off|native`.
  - It logs the **effective** value: `native` only when a registration took it.
  - A request that was ignored gets its own line (D2) and leaves `off` in the summary.
  - So the golden check's stock token is `display.widescreen=off` on every game.
- **The CLI's tables.**
  - `ENHANCE_STOCK` (`golden.py:1050`) gains `("display.widescreen", ENHANCE_WIDESCREEN_RE, "off")`.
  - `TOOLKIT_ENHANCE_KEYS` (`manifest.py:331`) gains `"display.widescreen"`.
- **The manifest.** It rejects unknown tables (`manifest.py:391`), so `[display]` with `native = "anamorphic" | ""` (default `""`) goes into its spec first, with `docs/manifest.md`. The game repos then bump their `[cli]` pin before declaring it.

## Risks / Trade-offs

- **The Burnout 3 menu might gate its "Aspect Ratio" item on the dashboard flag.** Then a player with `native` off never sees it, which is stock and fine. If the item is always there, a player who picks 16:9 with `native` off gets the squeeze, exactly as on a 4:3 console. Task 1.3 checks it.
- **Probe drift.** A game update or region would move the address. The game repos pin one XBE by sha256 (`[xbe]`), so the address is valid for the only build we run.
- **Provenance misses** leave today's seam, with no new harm. A false match would stretch a real still. The checksum and shape tests keep that rare, and the trace logs every match.
- **The integer fit loses whole-pixel scaling on the horizontal axis** under native. That is inherent to anamorphic content.

## Migration Plan

- Existing `config.toml` files have no `widescreen` key, so they get stock.
- `config.default.toml` gains `widescreen = "off"` in `[display]` with a comment.
- No golden changes. The golden harness adds `display.widescreen` to the keys it refuses at a non-stock value (D10).

## Resolved Questions (the user, 2026-10-18)

- Wizard default for a wide display: Native on b3 and ssx3, Hor+ on BLiNX 2 and Spartan.
- SSX 3: the stretch follows the in-game setting; native does not force Anamorphic.
- The probe stays in the game repo's C code (`enhance_native_register()`).
- The video-flags define fix is fork-only for now and is left out of the next upstream PR round. It is revisited at the upstream re-assessment.

## Open Questions

- Burnout 3's "Aspect Ratio" menu writer, and whether the dashboard flag gates the menu item (task 1.3, an open spike task).
