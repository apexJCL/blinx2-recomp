## ADDED Requirements

### Requirement: The inventory joins the game's archives and a runtime dump on the texel hash
`xbr enhance textures inventory [--dump DIR] [--json]` SHALL build `dist/enhance/inventory.json` from the sources `game.toml [enhance.textures] sources` lists, in order: `archive` (the CLI's readers), `loose` (`.dds`, `.xpr`, `.xbx` files under the game files), `hook` (a Python script in the game repository that prints an index and serves entries by name) and `dump` (a directory the runtime wrote under `RECOMP_DEBUG=tex_dump=<dir>`). Each archive entry SHALL be hashed as the guest holds it: DXT block data as is; uncompressed DDS data swizzled as the console's D3DX does; XPR0 data as it is, never swizzled again; DDS decoded by the game's load rules only, with no format change and no generated levels; a mipped file once per level prefix (1 to L levels), the dump confirming which the runtime bound. P8 SHALL come from the dump only, since the runtime folds the palette into the hash. Entries SHALL be keyed by hash; an archive entry and a dump entry with one hash SHALL be one inventory entry with the archive's name and the dump's facts (wrap modes, filters, use count, magnification); an archive entry no dump holds SHALL be listed as `not seen`; a dump entry no archive names SHALL be listed as `unnamed` and SHALL remain packable from its dumped texels. The file SHALL hold names, hashes, sizes, formats, classes, facts and counts, and never texels.

#### Scenario: Join on a synthetic tree and dump
- **WHEN** the command runs on a synthetic archive of three textures and a synthetic dump holding two of them plus one unnamed hash
- **THEN** the inventory has four entries: two joined with names and facts, one `not seen`, one `unnamed`, and the command prints the counts per class and the two lists

#### Scenario: Swizzled hash matches the runtime
- **WHEN** an uncompressed A8R8G8B8 texture of the shared test vector is hashed by the archive feeder
- **THEN** the hash equals the one the toolkit's `tests/tex_dump` writes for the same texels

#### Scenario: A game with no reader
- **WHEN** `sources = ["dump", "loose"]` and the game files hold no archive the CLI reads
- **THEN** the inventory is the dump's entries, every one `unnamed` unless a loose file names it, and the command says so in one line

### Requirement: Every entry has a class and facts, and the exact-size classes are excluded with their reason
Each inventory entry SHALL be assigned one class, `font`, `text`, `ui` or `world`, from `game.toml [enhance.textures.classes]` patterns, `[enhance.hud]` (the atlas, the languages and text patterns) and dump facts (a texture drawn only by pre-transformed batches is `ui`), and the facts `alpha`, `normal` (bump formats or a BUMPENVMAP stage), `data` (`min(w, h) == 1`, `max(w, h) <= 8`, or point-filtered at a one-texel footprint), `linear`, `palette`, `grid`, `rt` and `volatile`. Entries that are `rt` or `volatile` SHALL never be packed; `normal`, `data` and `linear` SHALL be skipped unless a rule includes them; a `palette` entry SHALL be packable from the dump only, one entry per palette variant with the variant count shown. `--list` and the GUI SHALL print each skipped entry with its reason.

#### Scenario: Exclusions named
- **WHEN** a synthetic inventory holds a 256x1 ramp, a V8U8 bump map, a linear movie frame marked volatile, and a DXT1 wall
- **THEN** `build --list` shows the first three skipped as `data`, `normal` and `volatile`, and the wall as `world`

#### Scenario: A rule includes a linear texture
- **WHEN** `[rule."linear/*"] skip = false` matches a linear texture that is not volatile
- **THEN** the entry is built and the manifest records its class and the rule

### Requirement: Upscalers are pluggable: built in, a command, a service
The CLI SHALL keep a registry of upscalers, each with `name`, `kind` (`builtin`, `command`, `http`), `scales`, `alpha` (`rgb` or `rgba`), `deterministic`, `batch` and a description of its parameters, and SHALL run the one a class or rule names. Built-in upscalers (`nearest`, `xbr` at 2, 3 and 4 with `level`, `eq`, `weights` and `alpha_edge`, `epx`, `lanczos`, `box`) SHALL be integer and give the same bytes on any host. A `command` upscaler SHALL run a template over PNG files in a temporary directory (`{in}`, `{out}`, `{in_dir}`, `{out_dir}`, `{scale}`, `{model}`, `{tile}`, `{gpu}` for an ncnn tool's `-g` index, `{device}` for the torch plugin's `auto|cuda|mps|cpu`), split with `shlex` and substituted into an argument list so that no shell runs, with a timeout, record the program's sha256 and version line, read the program's path, `gpu` and `device` from the untracked local file, and SHALL come from presets the CLI ships as templates only (Real-ESRGAN ncnn-vulkan, waifu2x ncnn-vulkan, Real-CUGAN ncnn-vulkan, Upscayl's CLI, chaiNNer `run`, Real-ESRGAN's Python script, the `xbr-upscale-torch` plugin), each with a found-on-PATH probe, its licence and homepage; the CLI SHALL download, vendor or run none of them by itself. An `http` upscaler SHALL speak the xbr upscale service contract v1 (`GET /v1/info`, `POST /v1/upscale?scale=&model=` with `image/png` in and out) or one of the adapters `a1111` and `comfyui`, using `urllib` only, SHALL allowlist `model` against the service's models and `scale` against its scales, cap the response body and check the PNG header against the expected size before decoding, time out each request, read the bearer token from the environment variable the local file names and never store it, and SHALL refuse to send the token over plain `http://` to a host that is not loopback unless the local file opts that service in. `xbr enhance serve` SHALL serve the contract over any registered upscaler, bound to `127.0.0.1` unless `--host` is given, SHALL require a token (compared in constant time) when the host is not loopback, cap the request body and image size, allowlist `model` and `scale` against its own `info`, and time out a stuck backend. A Python entry-point backend loaded into the CLI's process is not part of this change; the PyTorch backend is a separate program driven as a command.

#### Scenario: Built-ins reproducible
- **WHEN** a 64x64 RGBA crop is upscaled by each built-in at 2, 3 and 4 on two hosts
- **THEN** the bytes are identical and `textures-pack.toml` records `reproducible = true` and `reproducible_scope = "any"` for a pack that used only built-ins

#### Scenario: Command preset not found
- **WHEN** a class names an upscaler whose preset program is not on PATH and no `path` is set
- **THEN** `build` refuses before any work with the preset's name and homepage, and the GUI shows the preset as "not found"

#### Scenario: Service round trip
- **WHEN** a test server speaking the contract answers `info` with scales `[2, 4]` and `upscale` with a 4x PNG
- **THEN** the backend sends the crop, receives the result, records the server's `info` in the manifest and marks the pack not reproducible

#### Scenario: Token over plain http refused
- **WHEN** a service's local entry has `url = "http://<a LAN host>:8711"`, a `token_env`, and no `allow_plain_http`
- **THEN** the backend refuses before any request, naming the key that opts in; with `allow_plain_http = true` it warns once and proceeds

#### Scenario: Serve off loopback needs a token
- **WHEN** `xbr enhance serve --host 0.0.0.0` starts without `--token-env`
- **THEN** it refuses to start; with a token, a request with a wrong token is 401 and a body over the cap is 413

### Requirement: The PyTorch backend is a separate plugin driven as a command
The PyTorch backend SHALL be the optional package `xbr-upscale-torch` under the CLI repository's `plugins/torch/`, with its own `pyproject.toml` pinning exact `torch` and `spandrel` versions, and SHALL never be a dependency or an extra of the CLI; the CLI's process SHALL never import torch. `xbr enhance textures backend install torch` SHALL print, and never run, a `uv tool install` line for the host's platform (the CLI repository at the CLI's tag with `#subdirectory=plugins/torch`, or a local path; the PyTorch CUDA or ROCm index where a GPU is wanted; the pins as constraints). The CLI SHALL drive the plugin as a `command` upscaler with the fixed argument list `upscale --model PATH --scale S --in-dir DIR --out-dir DIR --device auto|cuda|mps|cpu --tile N --dtype fp32`, one batch directory per call. The plugin SHALL print one JSON line with the architecture, native scale, model sha256 and its `contract` version (`<major>.<minor>`, also printed by `--version`); the CLI SHALL refuse a plugin whose contract major differs from its own, naming the install line for its tag, and SHALL warn on a newer minor. The plugin SHALL load models only through `spandrel.ModelLoader` (its restricted unpickler for `.pth` and `.ckpt`; `.safetensors` preferred), never through a raw `torch.load`, SHALL never install `spandrel_extra_arches`, and when a preset names an expected sha256 SHALL hash the model file before loading and refuse a mismatch unless `--allow-model-mismatch` is given (the record then says so). The plugin SHALL open no network socket: `xbr enhance serve --backend torch` SHALL serve it remotely through one long-lived plugin process in a `worker` mode (length-prefixed JSON headers and PNG bodies over stdin and stdout, each model loaded once). The plugin's tests SHALL run with a tiny random model on the CPU, and the CLI's own tests SHALL not import torch.

#### Scenario: Forbidden pickle refused
- **WHEN** `xbr-upscale-torch upscale` is given a `.pth` file whose pickle names the global `os.system`
- **THEN** the load is refused with spandrel's unpickling error, nothing runs, and no output is written

#### Scenario: Model sha256 mismatch
- **WHEN** a model preset expects sha256 `A` and the owner's file hashes to `B`
- **THEN** the plugin refuses before loading, naming both hashes and the override flag; with `--allow-model-mismatch` it loads and the JSON line and `textures-pack.toml` record the mismatch

#### Scenario: Contract major differs
- **WHEN** the installed plugin reports `contract = 2.0` and the CLI speaks contract 1
- **THEN** the CLI refuses the torch upscaler before any work and prints the install line for its own tag

#### Scenario: Remote torch through serve
- **WHEN** `xbr enhance serve --backend torch --host 0.0.0.0 --token-env VAR` serves 50 requests
- **THEN** one plugin process in `worker` mode answers them all, the model is loaded once, and the only listening socket is the server's

### Requirement: Reproducibility is a boolean with a scope
`textures-pack.toml` SHALL record `reproducible` as a boolean and `reproducible_scope` as one of `any`, `host` or `none`: `true` and `any` when every upscaler used is built in; `false` and `host` when every non-built-in upscaler is the torch plugin on `--device cpu` with `torch.use_deterministic_algorithms(True)` (equal bytes expected again on the same host, versions and tile); `false` and `none` otherwise. A torch entry SHALL also record `backend = "torch"`, `model_sha256`, `arch`, the native scale, the torch and spandrel versions, `device`, `dtype` and `tile`.

#### Scenario: Deterministic CPU torch run
- **WHEN** a pack uses `xbr` for ui and the torch plugin on `--device cpu` with deterministic algorithms for world
- **THEN** `textures-pack.toml` records `reproducible = false`, `reproducible_scope = "host"`, and the world upscaler's model sha256, arch, versions, device, dtype and tile

#### Scenario: GPU run
- **WHEN** the same pack is built with the torch plugin on MPS
- **THEN** it records `reproducible = false` and `reproducible_scope = "none"`

### Requirement: Scales 2, 3 and 4 with the render-scale default
Every class and rule SHALL take a scale of 2, 3 or 4, and every check the CLI makes on a scale (the `xbr` kernel, `enhance hud --scale`, `[enhance.hud] scale` in `game.toml`) SHALL accept 3. With `R` the config's `render_scale`, the default scale SHALL be `clamp(R, 2, 4)` for `ui`, and for `world` once its upscaler is not `lanczos`; `world` with `lanczos` SHALL default to 2, `text` to 2 and `font` to 4; a class or rule that sets `scale` SHALL win. An upscaler whose native scale differs from the target SHALL be followed by the premultiplied `lanczos` to the target size inside the padded image, before the crop and before a `binary` alpha threshold, and the record SHALL name both steps.

#### Scenario: Defaults follow the render scale
- **WHEN** the config sets `render_scale = 3`, `[class.world] upscaler = "esrgan"` and no `scale` in either class
- **THEN** ui and world are built at 3x, text at 2x and font at 4x; with `render_scale = 1` ui and world are built at 2x, and with `[class.world] upscaler = "lanczos"` world is 2x at any `R`

#### Scenario: A 4x model at 3x
- **WHEN** a world entry of 128x128 is built at 3x by a 4x-native model with `alpha = "binary"`
- **THEN** the entry is 384x384, the record names the model and the `lanczos` step, and the coverage check runs on the 384x384 alpha

### Requirement: A compare grid and pick before the GUI
`xbr enhance textures compare [--class C] [--upscaler NAME] [--scale S] [--samples N] [--pick NAME] [--crop N] [--repeat 2] [--out DIR]` SHALL choose samples per class (the game's `[enhance.textures] preview` picks first, then the busiest texture per size band, deterministic by hash), SHALL run every registered upscaler (or those named) through the build's own alpha, edge and down-to-scale code, and SHALL write under `dist/enhance/compare/<stamp>/` a `grid_<class>.png` per class (rows samples, columns upscalers, each cell the busiest crop over a checkerboard), the full outputs, a static `index.html` with no script and no external resource, and `compare.json` (per upscaler the identity, licence and its flag, seconds per source megatexel, and with `--repeat 2` whether two runs gave equal bytes). It SHALL time each external upscaler as the subprocess the build runs, start-up included, and merge the timings into `build-logs/timings.json`. `xbr enhance textures pick CLASS UPSCALER [--scale S]` SHALL write that class's row of `config/enhance-textures.toml` with the config writer the GUI's Save uses. The renderer SHALL be the function the GUI's compare panel calls.

#### Scenario: Grid on the synthetic tree
- **WHEN** `compare --repeat 2` runs on the synthetic tree with the built-ins and a fake command backend
- **THEN** each `grid_<class>.png` has one row per sample and one column per upscaler, `compare.json` lists each upscaler with its seconds per megatexel and `deterministic = true`, and `index.html` loads no external resource

#### Scenario: Pick round trip
- **WHEN** `pick world lanczos --scale 3` runs and the config is read back
- **THEN** `[class.world]` holds `upscaler = "lanczos"` and `scale = 3`, the file's other tables and comments are unchanged, and `build --list` shows world at 3x with `lanczos`

### Requirement: Alpha, edges, mip chains, encoding and size limits
Before an upscaler that takes `rgb` sees a texture with alpha, the builder SHALL split it (`split`: colour edge-extended under transparent texels, alpha upscaled as grey, recombined; `binary`: the coverage thresholded to within 1% of the source's; `native` for `rgba` upscalers). It SHALL pad each texture by 8 source texels by the recorded wrap mode (`wrap`, `clamp`, or `cells` with a cell size) and crop after. It SHALL regenerate the mip chain from the upscaled base by an alpha-weighted integer 2x2 box filter (`full` to 1x1, `keep` the source's level count, or `none`). It SHALL encode per class or rule as `raw`, `bc1`, `bc3` or `auto` (bc1 opaque, bc3 with alpha) with the CLI's integer encoders, and MAY use a vectorised path that produces identical blocks or an external encoder command that marks the pack not reproducible. An entry whose side would exceed 16384 or the class's `max_side` SHALL be built at the largest scale that fits, and said.

#### Scenario: No seam on a wrapped tile
- **WHEN** a 64x64 tileable gradient with `edges = "wrap"` is upscaled 4x by `lanczos`
- **THEN** the texel row at the output's bottom edge continues the top row within one level, and with `edges = "clamp"` it does not

#### Scenario: Cutout keeps its coverage
- **WHEN** a sprite with hard alpha is built with `alpha = "binary"`
- **THEN** the output's opaque fraction is within 1% of the source's and no transparent texel has a dark colour

#### Scenario: Chain to 1x1 in BC1
- **WHEN** a 128x64 DXT1 world texture with 8 source levels is built at 4x with `mips = "full"` and `encode = "auto"`
- **THEN** the entry has 10 levels, 512x256 down to 1x1, every level BC1 blocks, and the toolkit's `tests/tex_pack` vector matches the encoder on the shared block

### Requirement: The config, the build and the pack manifest
`xbr enhance textures build [--preset P] [--config F] [--out DIR] [--jobs N] [--only PATTERN] [--language L] [--list]` SHALL read the tracked `config/enhance-textures.toml` (schema 1: `preset`, `render_scale`, `[coverage]`, `[class.<name>]`, `[rule."<glob|hash:HEX>"]` in order, `[upscaler.<name>]` with names and numbers only, `[budget]`, `[font]`) and the untracked `config/enhance-textures.local.toml` beside it (per upscaler the program `path`, `gpu`, `device`, service `url`, `token_env`, `allow_plain_http`; merged over the tracked file) when present, SHALL refuse a tracked file that holds a `path` or `url` key, apply per entry the class defaults, the class table, then the matching rules in order, and write `DIR/textures.pack` (version 3) and `DIR/textures-pack.toml` (the tracked config's path and sha256, per class the entries, scale, encode and bytes, each upscaler's identity without paths or URLs, `reproducible` and `reproducible_scope`, the XBE's sha256). `xbr enhance hud` SHALL be `build --preset hud` with its existing flags and its existing output names (`hud.pack`, `hud-pack.toml`); without a config the hud preset's art and font payloads SHALL equal what `enhance hud` wrote before this change. `package --texture-pack [DIR]` SHALL stage the pack and name it in `config.default.toml`; `--texture-preset NAME` SHALL build it first; `--keep-texture-pack` and `--clear-texture-pack` SHALL mirror the HUD pack's flags; `--texture-pack` with `--hud-pack` SHALL be refused, since a bundle carries one pack; the incremental reader SHALL accept either pack manifest.

#### Scenario: Rules in order
- **WHEN** `[class.world] upscaler = "lanczos"`, a rule `"dds/floor_*"` sets `xbr` and a later rule `"dds/floor_01*"` sets `skip = true`
- **THEN** `floor_02` is built with `xbr`, `floor_01` is skipped with the rule named, and every other world entry uses `lanczos`

#### Scenario: HUD preset unchanged
- **WHEN** `enhance hud` runs on the synthetic tree of the existing end-to-end test
- **THEN** the art and font payload bytes equal the previous version's, the header is version 3 and the kinds are as before

#### Scenario: Estimate before the build
- **WHEN** `xbr enhance textures estimate --preset all` runs after an inventory
- **THEN** it prints per class the entries, the texels, the pack MB per encode at the configured scale, the resident VRAM MB per dumped scene, and the build minutes from the calibration cache or "not measured yet"

### Requirement: Coverage by magnification is advice the owner tunes
With `coverage.mode = "traced"` and `render_scale = R`, the builder and the GUI SHALL propose per traced entry `skip` when the entry's magnification at 1x times `R` is at most 1, and otherwise the smallest of 2, 3 and 4 at or above it, capped at 4, SHALL treat untraced entries by `coverage.untraced` (`skip` or `class`), and SHALL write the owner's choices as rules so the build stays declarative. The GUI SHALL show the table of name, class, magnification, proposal and bytes saved.

#### Scenario: Proposal per render scale
- **WHEN** a HUD piece was traced at 1.0 pixels per texel and a wall at 2.6, and `R` is 2
- **THEN** the HUD piece is proposed `2x` (2.0) and the wall `4x` (5.2, capped at the largest offered); with `R = 1` the HUD piece is proposed `skip` (1.0) and the wall `3x` (2.6); with `R = 3` the HUD piece is proposed `3x`

### Requirement: The preview GUI's Textures tab
`xbr enhance preview [--config FILE] [--port N] [--no-browser]` SHALL serve one page on `127.0.0.1` with no external resource, SHALL put a random per-session token in the URL it opens and require it on every route (page, JSON and images; 403 without), SHALL accept only requests whose `Host` is `127.0.0.1:<port>` or `localhost:<port>`, reject any request carrying a foreign `Origin`, take POST bodies as JSON only, make no request to a registered service URL outside the `http` backend's allowlisted calls, and exit on `/quit`, Ctrl-C or its parent's exit. Its Textures tab SHALL offer: the upscaler registry with found/not-found, version, licence and homepage per preset, a form to register a service (URL, token environment variable, Test), a path field for a tool off PATH, and each upscaler's parameters; the game's coverage presets, the editable class table, rules added from a texture, the exclusions with their reasons, and bars per preset for pack MB, resident VRAM MB and build minutes; a compare panel over the inventory (preview picks, then the dump's most used) with a crop the owner drags, side-by-side panels and a slider between two results, each labelled with its upscaler, time and encoded bytes, raw beside BC1/BC3 on request, and an on-screen view that resamples the result to its footprint at `render_scale` through the recorded filter and chain level, beside the stock texture's own; a runtime panel that imports `[TEXPACK] miss` lines and the magnification trace; and Save, which writes names and numbers to `config/enhance-textures.toml` and paths and URLs to `config/enhance-textures.local.toml` and prints the `build` command. Every image SHALL be rendered by the modules the build uses, held in memory, and the tool SHALL write nothing but the two configs and the per-user font cache.

#### Scenario: Slider between two upscalers
- **WHEN** the page requests a 128x128 crop of a wall at 4x through `lanczos` and a registered service
- **THEN** it receives one PNG per upscaler with the time and encoded bytes, the slider wipes between them, and the `lanczos` PNG equals the crop of what `build` writes for that texture

#### Scenario: On-screen view at scale 1
- **WHEN** a HUD piece traced at 1.0 pixels per texel is shown on screen at `render_scale = 1`
- **THEN** the upscaled and the stock renders of the footprint are identical within one level, and the panel says the texture is not magnified at that scale

#### Scenario: Save, then build
- **WHEN** the owner sets `world` to a found command preset, adds a `skip` rule from a texture and saves
- **THEN** `config/enhance-textures.toml` holds the preset's name, model and the rule, `config/enhance-textures.local.toml` holds the program's path, neither holds game bytes, and `build --config` applies them

#### Scenario: Cross-site request refused
- **WHEN** a request reaches a JSON route without the session token, with a foreign `Origin`, with a `Host` that is not loopback, or as a form-encoded POST
- **THEN** it is refused with no body and nothing is registered or rendered

### Requirement: The wizard offers the presets and hands off to the preview
A `[[wizard.option]]` of `kind = "choice"` MAY carry `flag`; the wizard SHALL pass the chosen value after the flag (`--texture-preset world`), and `wizard config` SHALL check the values against the tag's `[enhance.textures.presets]`. The Options page SHALL show under the choice the estimate per value from `package --plan --json`'s `textures` row, or "not measured yet". A `Configure…` button, enabled once Checks passed and the dump is known, SHALL run `<game> enhance preview --no-browser` in the clone through the runner, open the printed URL with its token, show when `config/enhance-textures.toml` appears, and stop the server when the page is left or the wizard exits; before any runtime dump exists the page SHALL show the archive feeder's inventory, or the way to make a dump when the game has no reader. The wizard's tweak table SHALL carry `--texture-preset` with its keep and clear flags beside `--hud-pack`. The wizard SHALL run no upscaler in its process and link nothing new; `wizard/check.sh` SHALL pass.

#### Scenario: Choice with a flag
- **WHEN** the player picks `world` and builds
- **THEN** the runner's `package` command carries `--texture-preset world`, the Summary names the preset and the config's sha, and the Build page shows the `textures` stage with its estimate

#### Scenario: Configure before Checks
- **WHEN** the Options page is shown before Checks passed
- **THEN** the button is disabled with a line saying what it needs

### Requirement: Packs, dumps and game-derived images stay out of every repository
A pack, its manifest, a dump directory, a decoded texture, a frame, a crop, or the owner's local config SHALL never be committed or exported: `*.pack`, `enhance/`, the dump directory, `dist/` and `config/enhance-textures.local.toml` SHALL be gitignored in the game, and the CLI's `scripts/audit-public.sh` and the export's refused paths (`layout.py` `refused_path`, `DATA_EXT`) SHALL refuse `*.pack`, `*.xtd`, `textures-pack.toml`, `hud-pack.toml` and the local config. The tracked config SHALL hold no path and no URL, and the inventory file no texels. The CLI SHALL ship no model weights and download none; the presets SHALL be templates and licence notes only. Every test SHALL build its own fixtures (archives, DDS blocks, a synthetic dump, a test server) and read no game files.

#### Scenario: Audit clean
- **WHEN** `scripts/audit-public.sh main..HEAD` runs on the CLI branch and `git status` runs in the game after a build and a dump
- **THEN** the audit is clean and neither the pack nor a dump file is untracked or staged

#### Scenario: Tests without a dump or a tool
- **WHEN** `uv run pytest tests` runs on a host with no game files and no upscaler installed
- **THEN** every `enhance` test passes
