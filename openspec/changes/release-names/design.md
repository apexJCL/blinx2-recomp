## Context

- gen-names carries `config/symbols.toml` names into gen as C
  identifiers and comments; hooks, seeds, `recomp_manual.c` and every
  runtime table stay keyed by address, on purpose.
- The release gate tells another release apart by the
  certificate's region and version and the section hashes
  (`fingerprint.classify`), and recomp stops when a declared
  `sub_X_gen` wrap gets no body.
- The matcher (`xboxrecomp_cli/match.py`, CLI 4e0fb09) pairs
  functions by masked bytes (exact, calls, order, neighbours passes) and
  globals by votes, and `Match.place(va)` returns the other release's
  address with a `sure`/`unsure` verdict. For BLiNX 1 NTSC-U v6 to PAL v3:
  56% of functions (67% of PAL's), every port item placed right, about
  70 s.

What BLiNX 1's hand-written side uses (the spike's table):

| What | NTSC-U v6 | PAL v3 | Spike verdict |
|---|---|---|---|
| wrap, Hor+ sphere test | 0x9AD80 | 0x34F90 | unsure (right) |
| wrap, lens flare | 0x96BB0 | 0x30B90 | unsure (right) |
| wrap, pad poll | 0xA2DE0 | 0x9EBC0 | sure |
| seeds, two thread routines | 0xF9860, 0xF98D0 | 0xFA350, 0xFA3C0 | code pointer |
| projection _11 | 0x3AE6A0 | 0x39DE50 | sure |
| 2D queue pointer | 0x8EC3E4 | 0x8DDF24 | conflict 317:1 (right) |
| far-cull 400.0f | 0x1D7394 | 0x1C83DC | sure |
| D3D device pointer | 0x143B58 | 0x142058 | (by hand) |
| fence offsets put/get | 0x2C/0x30 | 0x30/0x34 | not addresses |

## Decisions

### D1. BLiNX 1 PAL is the first user, not BLiNX 2

The tracker item says "migrate BLiNX 2 first". BLiNX 1 is the only game with a
second release on hand (PAL v3, the operator's dump); BLiNX 2 has one
release, so a BLiNX 2 migration could prove only the first done-when
(byte-identical regen), never the second (another release boots). BLiNX 1
proves both, and its hand-written side is small enough to migrate whole.
BLiNX 2's address-keyed inputs (hooks, `[mods] hook_functions`, spin
waits, the HUD table's call sites, its larger `recomp_manual.c`) are a
later task (tasks 7.1), on the same mechanism; with no second release it
gains nothing until one turns up.

### D2. Port names apart from the gen symbol map

`symbols.toml` renames gen functions and comments gen lines; a port name
does neither. Folding them together would change gen for BLiNX 1 (which
has no symbol map) and break done-when (1). So `config/names.toml` holds
only what the hand-written side uses:

```toml
[[name]]
name = "gfx_sphere_visible"
kind = "function"          # function | global | site | value
addr = 0x0009AD80          # in the reference release ([xbe] sha256)
note = "bounding-sphere test; the Hor+ wrap"

[[name]]
name = "d3d_fence_put"
kind = "value"
value = 0x2C
```

Names are C identifiers checked by `symbols.reserved` (no `sub_`/`loc_`
shapes, keywords, registers, `_`/`g_`/`recomp_` prefixes) and unique.
BLiNX 2 can later point a name at a symbol row; that is part of 7.1.

### D3. One file per other release, written by `match`, owned by the port

`config/releases/<id>.toml`:

```toml
[release]
id = "pal-v3"
sha256 = ["3e4b51ed..."]   # dumps of this release
region = 0x4
version = 3
reference = "771b8b63..."  # the dump the map was made from

[[name]]
name = "gfx_sphere_visible"
addr = 0x00034F90
verdict = "unsure"         # sure | unsure | reviewed
how = "function (calls)"

[[name]]
name = "d3d_fence_put"
value = 0x30
verdict = "reviewed"
```

A name with no `addr` (or `value`) is unplaced. `match` writes every
name of `names.toml` in its order; a value is written unplaced with the
reference value in a comment, because a struct offset or a timing value
is not something the matcher sees (the spike: fence offsets moved with the
XDK). Rerunning `match` keeps the rows marked `reviewed` as they are, so
hand edits survive; others are rewritten.

### D4. The release is chosen by fingerprint, before any stage

`names.select(G)`, in this order:
- the fingerprint says known (the sha256 is in `[xbe] sha256`): the
  reference, `names.toml` as is;
- a release file whose `sha256` lists the dump's: that map. The sha256
  wins over every other heuristic, so a listed dump never falls to the
  fingerprint's reading of it;
- header or data (the reference's code, under a region or title patch or
  with other data), whatever `other` says: the reference;
- another release (`other`) with other code (`code`, `unknown`): stop,
  "another release (PAL, version 3) ... run `blinx1 match game_files`".
  The toolkit's guard stays as the backstop for a game without
  names;
- else (modded code of the same release, or unknown with no claim to
  another release): the reference, with the fingerprint's warning as
  today.

A release file that lists the reference's own sha256, or a sha256 that
another release file lists too, is refused. Each release row records the
reference address it was matched from (`ref`). A row whose `ref`
disagrees with `names.toml` stops `select` by name; `match` places it
afresh as `unsure`. A file without `ref` rows is used with a warning, as
is one whose `[release] reference` is not in `[xbe] sha256`.

Placed names no person reviewed (`unsure`, and `sure` from the matcher)
are printed as one warning per stage that resolves them.

### D5. The C form and gen/recomp_names.h

The CLI writes `gen/recomp_names.h` before recomp (beside the generated
code, so it always goes with the dump that gen came from):

```c
#define XBR_RELEASE "pal-v3"
#define XBR_FN(n)   XBR_FN_##n
#define XBR_GEN(n)  XBR_GEN_##n
#define XBR_VA(n)   XBR_VA_##n
#define XBR_VAL(n)  XBR_VAL_##n
#define XBR_HAVE(n) XBR_HAVE_##n
/* gfx_sphere_visible: function, unsure (function (calls)) */
#define XBR_HAVE_gfx_sphere_visible 1
#define XBR_VA_gfx_sphere_visible 0x00034F90u
#define XBR_FN_gfx_sphere_visible sub_00034F90
#define XBR_GEN_gfx_sphere_visible sub_00034F90_gen
```

An unplaced name gets only `XBR_HAVE_<n> 0`. Token pasting keeps the
argument unexpanded, so a name never collides with a macro. Both
`RECOMP_ABI_CALL(XBR_VA(n), XBR_GEN(n))` and `void XBR_FN(n)(void)` expand
to exactly the address form, so the compiled code is the same.

### D6. A missing name disables its code or stops by name

`#if XBR_HAVE(name)` (one name, with an optional `#else`) marks code that
may go: on a release without the name the block drops out of the build
and out of recomp's scan. Any other use of an unplaced name is an error
named before recomp: the CLI scans the game's C sources (not gen) for
`XBR_FN/GEN/VA/VAL(name)` outside such a block and stops with each name,
file and line. It also stops on a name in `XBR_HAVE(...)` that
`names.toml` lacks (a typo would drop the block from every release) and
on any `XBR_HAVE` use that is not a plain `#if XBR_HAVE(n)` line (`!`,
`&&`, `#elif`, continued lines, a wrapping macro): neither scanner
understands them. The check runs at analyze and recomp, and again at
build (so package too), since the sources are no gen input. The toolkit
does the same for the manual file on its own, so a direct recomp run
cannot reach the link either.

### D7. Toolkit: recomp --names

`--names FILE` is `{"addresses": {name: va}, "have": [name, ...]}`:
`addresses` holds the placed address names, `have` every placed name,
values included, so a value's `XBR_HAVE` block is kept as the header
keeps it. The plain object `{name: va}` is still read, its names being
its have list. `manual_scan` reads the manual file once through
`_live(path)`: strip `#if 0`, then drop `#if XBR_HAVE(n)` blocks for names
not in `have` (keeping the `#else` side), then rewrite `XBR_FN(n)` to
`sub_%08X`, `XBR_GEN(n)` to `sub_%08X_gen` and `XBR_VA(n)` to `0x%08Xu`.
All its scans (definitions, wraps, entry hooks, references, uses) run on
that text, so the rest of recomp is unchanged. A form naming a name the
map lacks, outside a dropped block, stops recomp with the name. Without
`--names` the forms are left alone and a manual file using them stops
with "needs --names".

### D8. Seeds by name

A seed row `{"name": "sys_thread_a", "source": ..., "observed": true}`
is resolved through the selected names into
`analysis/seeds/<path>` (the file's path under the root, so two files of
one basename do not collide) with `start`, and that file goes to disasm
and recomp. A row with both `name` and `start` is refused: the start is
the reference's only. A name the release lacks drops the seed with a warning (a
seed only helps analysis). A file with only `start` rows is passed as
before, so the argv of a game without names is unchanged.

### D9. The generation key

`gen_inputs` adds `names.toml`, the selected release file and the
release id. The seed files themselves are inputs already, so these key
the resolved seeds' inputs, not the resolved copies: a change to any of
them stales gen. The argv gains
`--names analysis/names.json` only when `[pipeline] names` is set.

### D10. Out of scope, recorded as tasks

- `[extract]` roots through the mapped table address (the spike: 48/48
  that way): tasks 7.2.
- PAL 50 Hz: the toolkit's vblank pacing is 60 Hz; a PAL release runs
  20% fast until a per-release `XBR_VAL(vblank_hz)` drives it: 7.3.
- Matcher hardening (faster align, the weaker `calls` pass, a second
  pair): 7.4.
- The wizard's another-release dialog says "run match" when a map is
  missing: 7.5.
