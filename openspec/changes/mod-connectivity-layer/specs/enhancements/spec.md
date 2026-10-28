## ADDED Requirements

### Requirement: Mod API v2 services
The enhancements layer SHALL offer `XBOX_MOD_API_VERSION 2`. It SHALL keep every v1 field at its offset and add:
- `aspect` and `pad`;
- `state_probe`, `state_probe_fn` and `state`;
- `poke`;
- `hook`;
- `place`;
- `rt_dims`.

A v1 mod table SHALL run unchanged. The layer SHALL sample every state probe at each flip, in every title, without game frame glue.

#### Scenario: Free camera at stock
- **WHEN** cat runs with `camera.free = "off"` and no other mod enabled
- **THEN** the free camera's `init` is not called, and the `[ENHANCE]` line reports `mods=none`

#### Scenario: Aspect at stock
- **WHEN** a v2 mod calls `aspect()` with no `display.aspect` and no `display.widescreen`
- **THEN** it reads mode stock, ratio 4:3, `wide_now` 0, and `pad(640, 480)` returns 0

#### Scenario: Probe in a title without frame glue
- **WHEN** b3 registers the `wide` probe and runs in native mode
- **THEN** `state("wide")` follows the game's flag, sampled at each flip

### Requirement: One enable gate for every mod
The layer SHALL call a mod's `init` only when `[mods.<name>] enabled = true` (default false), or when the key it names in `follows` holds a value different from that key's default. The rule SHALL apply to every mod in the table, v1 and v2 alike. A mod whose declared `needs` the layer cannot meet SHALL be left out, with one log line naming the missing need. The `[ENHANCE]` line SHALL report `mods=` followed by the names of the mods whose `init` succeeded, or `none`.

#### Scenario: Default
- **WHEN** a title lists a mod and the config has no `[mods.<name>]` table and its `follows` key is at its default
- **THEN** its `init` is not called, and `[ENHANCE]` reports `mods=none`

#### Scenario: Follows Hor+
- **WHEN** cat runs with `display.aspect = "16:9"`
- **THEN** `blinx2-wide-cull` runs, and at `display.aspect = "4:3"` it does not

#### Scenario: Missing hook slot
- **WHEN** a mod hooks a VA that is not in `[mods] hook_functions`
- **THEN** `hook` returns 0, the layer logs `[MOD name] needs hook: no slot for 0x...`, and the mod is left out

### Requirement: Guarded pokes
`poke` SHALL write only outside executable sections. It SHALL write only when the loaded XBE matches the game's `[xbe]` pins: the sha256, or the section hash covering the address. With `XBOX_MOD_POKE_EXPECT` it SHALL write only while the address holds the expected bytes or the poked bytes. With `XBOX_MOD_POKE_HOLD` the layer SHALL compare the poked bytes, of any length, at each flip and write them again when they differ.

#### Scenario: Code address
- **WHEN** a mod pokes an address inside `.text`
- **THEN** the poke is refused with a log line, and guest memory is unchanged

#### Scenario: Held value
- **WHEN** a mod holds a float at an address and the game rewrites it to the expected value on a menu change
- **THEN** the mod's value is back in place by the next flip

#### Scenario: Address reused
- **WHEN** a held poke with an expected value finds the address holding some third value
- **THEN** the layer does not write it, and logs once

### Requirement: Generated VA hooks
For each function listed in `game.toml` `[mods] hook_functions` (a VA, or a `sig:` name resolved by `analyze` to exactly one VA), the generated code SHALL dispatch registered pre callbacks, then the body unless a pre callback set `skip`, then the post callbacks in reverse order. Callbacks SHALL see the entry `esp`, `ecx` and `edx`, and run on the calling guest thread. Only a hook registered with `XBOX_MOD_HOOK_MAY_SKIP` MAY skip, and at most one per VA. A skip SHALL leave the stack as the body's `ret` would, popping the callee-cleaned argument bytes that `analyze` recorded. With no callback registered, the function SHALL behave as without the list, and with an empty list the generated code SHALL be byte-identical.

#### Scenario: Projection aspect
- **WHEN** a mod's pre callback on a `PerspectiveFovLH` hook multiplies `XBOX_MOD_ARGF(api, c, 2)` by 4/3
- **THEN** the matrix the body builds uses the widened aspect for that call only

#### Scenario: Skip on a callee-cleaned function
- **WHEN** a may-skip hook skips a function that ends in `ret 0x14`
- **THEN** the caller's stack pointer is the same as after the body would have returned

#### Scenario: Ambiguous signature
- **WHEN** a `sig:` entry matches zero times or twice in its section
- **THEN** `analyze` fails and names the signature

#### Scenario: Manual override conflict
- **WHEN** a VA in `hook_functions` also has a hand-written override in `recomp_manual.c`
- **THEN** `analyze` fails and names the VA

### Requirement: Hor+ placement overrides
A game's shipped `config.default.toml` MAY force a placement class (`stretch`, `centre`, `picture` or `rt`) with `[aspect.program]`, keyed by the program hash the `aspect` trace prints, and `[aspect.texture]`, keyed by the texture's address (masked to its low 27 bits, so a cached and an uncached alias match), format and size as that trace prints them. The overrides SHALL be read only under a wide `display.aspect`, SHALL be consulted before any other placement decision, and SHALL log a trace line per hit. An unknown class or a malformed key SHALL be reported once and skipped. This requirement moves here from the native-widescreen change.

#### Scenario: An override wins over the generic rule
- **WHEN** `[aspect.texture]` maps `0x80A98000 fmt 12 320x240` to `rt`, and that texture is sampled at 16:9
- **THEN** the batch is placed as over a padded render target, and the trace logs the override

#### Scenario: Stock ignores overrides
- **WHEN** the same file runs at `display.aspect = "4:3"`
- **THEN** no override is read and no trace line is logged

### Requirement: Placement order and letterbox bands
When the aspect is wide, a 2D batch's placement SHALL be decided in this order:
1. an `[aspect.program]` or `[aspect.texture]` override;
2. the mods' `place` callbacks, in table order;
3. the generic rules.

The generic rules SHALL stretch a full-width 2D batch over the padded target when the batch is a letterbox band, if the band rule is built: at most a quarter of the target high, and wholly within its top or bottom quarter. Full width SHALL be judged per triangle, or over quads that tile one row band, never over a whole batch's bounding box. A screen-layer test, if built, SHALL only feed the full-width and band decisions, and SHALL NOT make a batch 2D.

#### Scenario: Burnout 3 crash cam
- **WHEN** b3 runs at 16:9 Hor+ and a crash shows the crash-cam bars
- **THEN** both bars and the list backing span the whole width, and the HUD text in them stays at its 4:3 position

#### Scenario: Corner triangles
- **WHEN** BLiNX 2 draws four corner triangles in one batch at 16:9
- **THEN** the batch is not full width, and keeps its Hor+ placement

#### Scenario: Lens flare
- **WHEN** a lens-flare quad is drawn without depth at one w
- **THEN** it keeps its 3D placement

#### Scenario: Stock
- **WHEN** any game runs at 4:3
- **THEN** no override, callback or rule changes a placement, and the stock goldens pass
