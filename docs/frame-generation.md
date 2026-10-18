# External frame generation (unsupported)

BLiNX 2 runs at 30 frames per second, as on the Xbox, and this build has
no 60 fps mode (the stage logic steps a fixed 1/30 s). Tools outside the
game can still show it at 60: they invent an in-between frame from two real
ones. They should work with this build, since they act on the finished
image, but I haven't tested them yet, and **I don't support them**: the
automated checks never use them, and a bug seen only with one of them is
not a bug in the game. Turn the tool off before you report a problem.

None of them changes how the game plays. Input, physics and timers stay at
30 Hz; only the picture is smoother.

## What to expect at a 30 fps base

Every tool here works on the finished image, with no depth or motion data
from the game, and from a base of only 30. So expect:

- **HUD ghosting.** The timer, the gauges and the menus are warped with the
  scene, so their edges smear or double while the camera moves.
- **Particle and transparency smear.** Sparks, smoke, the time-control
  effects and the glow pass tear or trail, and fast-moving edges wobble.
- **Extra latency.** About one base frame (33 ms) or more on top of the
  game's own, because the tool holds a real frame back to build the one
  before it.
- **A base below the vendors' guidance.** AMD recommends a base of at
  least 55 fps at 1080p and 70 at 1440p for Fluid Motion Frames. At 30 the
  in-betweens are guesses over twice the motion, so all of the above is
  stronger than in the vendors' demos.

What helps, for every tool:

| Setting | Where | Why |
|---|---|---|
| `present.pacing = "sleep"` | `config/config.toml` `[present]` (the default) | Keep the default. The frame wait sleeps instead of spinning, which frees the CPU core it would otherwise hold and leaves that headroom to the tool. The pacing itself is the same as with `"spin"`. |
| `present.fullscreen = true` | `config/config.toml` `[present]` | A borderless window over the display (the game never uses exclusive fullscreen). Lossless Scaling and the drivers need a borderless or windowed game. |
| `RECOMP_PRESENT_VSYNC` unset | `config/launch.env` | On Direct3D 11 the game presents without waiting for the display (stock), and the tool does the syncing. `=1` stalls the game's own flip and fights the tool. |
| `render.scale = 1` | `config/config.toml` `[render]` | Frame generation costs GPU time. On a Deck, keep the 3D at 1x so the real frames still make 30. |
| a 60 Hz or variable-refresh display | | 2x of 30 is 60. On a 120 Hz display use the tool's 4x, or accept judder. |

## Lossless Scaling (Windows)

- **Needs:** [Lossless Scaling](https://store.steampowered.com/app/993090/)
  from Steam (paid), any recent GPU, Windows 10 or 11. The Windows build of
  the game is untested on native Windows (see the README's Platforms).
- **Use:** start the game with `present.fullscreen = true`, start Lossless
  Scaling, pick LSFG as the frame generation with a 2x multiplier, press
  Scale and click the game window within the countdown.
- **Helps:** a lower flow scale if your GPU drops real frames below 30;
  the game's own 30 is already a stable cap, so don't add another limiter.

## lsfg-vk with decky-lsfg-vk (Linux and the Steam Deck)

- **Needs:** a Steam copy of Lossless Scaling (lsfg-vk loads its frame
  generation from it), and [lsfg-vk](https://lsfg-vk.dev), a Vulkan layer
  that runs under Proton because DXVK draws the game through Vulkan. On the
  Deck the easiest route is the
  [decky-lsfg-vk](https://github.com/xXJSONDeruloXx/decky-lsfg-vk) plugin
  for Decky Loader. Both are community projects; neither is Lossless
  Scaling's own, and how well they work varies with the Proton build.
- **Use on the Deck:**
  1. In Lossless Scaling's Steam properties, Game Versions & Betas, pick the
     `lsfg-vk` branch.
  2. Install decky-lsfg-vk from its release zip (Decky settings, Developer
     mode, install from zip), open it and install lsfg-vk.
  3. Start BLiNX 2 from its Steam entry (`./install.sh --steam`), then pick
     it in the plugin and set the multiplier to 2x.
- **Helps:** the plugin's performance mode and a lower flow scale on the
  Deck; leave Steam's frame-rate limit off, or at the output rate, since a
  30 limit caps the generated frames too.

## AMD Fluid Motion Frames (Windows)

- **Needs:** a Radeon RX 6000 or newer, or a Radeon 700M- or 800M-series
  laptop GPU, and a current Adrenalin driver. It is driver-level and works
  on Direct3D 11 games, so on this build. Not on Linux.
- **Use:** Adrenalin, Gaming, the game's profile (or global graphics),
  AMD Fluid Motion Frames on, with `present.fullscreen = true`.
- **Expect:** AMD recommends a base of at least 55 fps at 1080p (70 at
  1440p), so 30 is well below it. AFMF also pauses frame generation on fast
  motion, which at 30 can make the rate jump between 30 and 60 during camera
  turns.
- **Helps:** a FreeSync display; follow the driver's own vsync advice.

## NVIDIA Smooth Motion (Windows and Linux)

- **Needs:** a GeForce RTX 40 or 50 series GPU and a current driver. On
  Windows it covers Direct3D 11, 12 and Vulkan games; on Linux it is a
  Vulkan layer, which reaches this build through DXVK under Proton.
- **Use on Windows:** the NVIDIA app, Graphics, Program settings, add the
  game's executable, then Smooth Motion on under Driver settings.
- **Use on Linux:** launch with `NVPRESENT_ENABLE_SMOOTH_MOTION=1` in the
  environment (Steam launch options:
  `NVPRESENT_ENABLE_SMOOTH_MOTION=1 %command%`).
- **Helps:** no other frame limiter on top; a limiter layer that runs after
  Smooth Motion adds a lot of latency.

## Not available

- **macOS:** no system-level frame generation exists.
- **gamescope** (the Deck's compositor) scales and limits the output but
  does not generate frames.
