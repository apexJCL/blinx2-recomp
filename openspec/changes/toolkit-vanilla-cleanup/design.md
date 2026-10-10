# Design

## Context

The audit's classes: **a** is text that names BLiNX 2 or cat (move it);
**b** is a generic rule whose comment uses BLiNX 2 as the example (keep the
code, reword); **c** is a constant whose value was decided on BLiNX 2 (keep
the value, make it a knob). The toolkit already has every seam the game
needs (audit section 5), so nothing here adds a hook; it moves text and
turns five constants into options.

Every change is checked against one rule: a BLiNX 2 run before and after is
the same run. Goldens at stock settings, `gen/` byte-identical, no new key
set anywhere.

## D1. The comment scrub rule

Each class-b comment keeps three things: the hardware or XDK rule the code
implements, the failure that the rule prevents, and the A/B switch if there
is one. It loses the title's `sub_` names and guest addresses, the game's
level and screen names ("hub", "stage 1", "mission-1 bomb door", "dark
water"), dates of private investigations, and paths in the game repo
(`runs/m1hang`). "BLiNX 2" becomes "a title" or "one title"; a measured
number stays when it is the evidence ("97 FAILED lines in 100 s") and goes
when it only dates the comment.

Burnout 3 is upstream's own reference title: its docs cite it by name
throughout, and the fork's Burnout 3 fixes are upstream-bound. A Burnout 3
mention without a symbol name or address stays. Where one carries a `sub_`
name or a guest address, the symbol goes and the title name may stay
("Burnout 3's DSOUND submit spins on the doorbell"). Upstream's own comments
(section 3.4 of the audit) are not touched.

Why not sed: the point of each comment is the *why*. "The DPC drained a list
its ISR was appending to with no linked check" is the rule; the `sub_` name
was only where it was first seen.

## D2. C1: the DPC sampler's code window

`kernel_prof.c` picks guest return addresses off a stalled DPC's stack by
the window `0x00011000..0x00400000`, which is BLiNX 2's `.text`. The loader
already records the executable sections' bounds in `g_xbox_code_lo` /
`g_xbox_code_hi` (`xbox_memory_layout.h`, set when the XBE sections are
mapped). The sampler uses those; when they are still zero (no image yet,
which the sampler never sees in practice) it falls back to the image bounds
`g_xbox_image_lo..hi`, and to nothing when those are zero too. Trace-only
code; the sampled numbers for BLiNX 2 are the same because its `.text` lies
inside the old window and the window inside its code bounds' page rounding.

## D3. C5: the present-surface staleness window

`PRESENT_STALE_FLIPS 120u` becomes `RECOMP_DEBUG=present_stale=N`
(`RENV_PRESENT_STALE`, debug tier: it changes which surface is presented).
Default 120. Read once into a static at first use, like `alias_check_on`.

## D4. C7: the GPU texture caches

D3D11 keeps 512 entries, Metal 256; both arrays are compile-time. One key,
`RECOMP_DEBUG=tex_cache=N`, sets the entries in use (1..512) on both
backends; the arrays are sized at the 512 cap on both (a Metal `TexEntry` is
under 64 bytes, so the cap costs 16 KB of statics). The defaults stay what
each backend has today, 512 on D3D11 and 256 on Metal: the audit shows no
measurement that says one value is right, only that 64 thrashed on D3D11,
and aligning them would be a behaviour change this spec rules out. A/B of
the two values on Metal is a separate measurement if anyone wants it.

## D5. C8: the CPU raster's depth-buffer slots

`ZB_MAX 8` is the array bound in `nv2a_zbuf_cache.h`; `zb_select_n` already
takes the count in use. The cap rises to 16 and the caller passes
`RECOMP_DEBUG=zbuf_slots=N` (1..16), default 8. Buffers are allocated on
first use per slot, so an unused slot costs its 24-byte key. CPU path only.
The nv2a_zbuf ctest's `ZB_MAX >= 8` check still holds.

## D6. C9: the disasm data-pointer probe budgets

`FunctionDetector.DATA_PTR_PROBE_INSNS` (64), `DATA_PTR_TABLE_PROBE_INSNS`
(512) and `DATA_PTR_MIN_NEIGHBOURS` (1) stay class attributes as the defaults
and become constructor keyword arguments, threaded from `Disassembler(...)`
and three `tools.disasm` flags (`--data-ptr-probe`,
`--data-ptr-table-probe`, `--data-ptr-min-neighbours`). The rule is generic
MSVC layout; the comment that justified the budgets with BLiNX 2 addresses
becomes the general statement (a long walk through zero-filled data finds a
`jmp` eventually, so the longer budget needs a neighbour in the table and a
boundary in front). Exposing the flags through `game.toml` is the CLI's job
and is a follow-up; no title needs another value today.

## D7. C3: `apu_dsp_ack` defaults to `auto`

`recomp_env.c` `load()` fills `RENV_APU_DSP_ACK` with `"auto"` when neither
spelling is set, before the game defaults are applied, so a game default or
the environment still wins. `=0` already parses to no addresses and is the
off switch (`dsp_ack_init`). `auto` is the XDK DSOUND GP layout (SGE[0] of
`GPSADDR` + 0x810), seen on BLiNX 2, Burnout 3 and Wreckless; a title whose
DSOUND never programs GPSADDR gets no doorbell and nothing changes for it.
cat and b3 drop their `D(APU_DSP_ACK, "auto")` rows. This is the shape
PR-04c wants (it removes upstream's per-title constant).

## D8. C2: the one-core pin as a game default

`RECOMP_GUEST_CPUS` takes a new spelling, `one` (the lowest core the process
may use), beside `all` and `<n>`. With it a game can write
`D(GUEST_CPUS, "one")` in `RECOMP_ENV_GAME_DEFAULTS`; cat and b3 do, so each
game's pinning is stated in the game and not inherited.

The toolkit's own default stays `one`. Why: the console has one CPU and a
title's threads only interleave at a quantum boundary or a wait, so
unsynchronised read-modify-writes on globals are correct there and racy on
two host cores; the failure mode is silent corruption (BLiNX 2's light pool
lost entries and terrain went black), not a crash that names itself. The pin
costs a title nothing it did not pay on the hardware, while `all` buys speed
only for a title whose threads never share a global unlocked, which no
console title had to be. The v0.13.1 sync already kept this over upstream's
`GUEST_LOCK` default, and changing it here would be the behaviour change
this spec rules out. `RECOMP_GUEST_CPUS=all` remains the A/B. macOS has no
thread affinity; BLX-31's guest-CPU lock is the Mac answer and is
independent of this key.

## D9. Docs

The toolkit's `recomp_env.h` points at `RECOMP_TRACE=help` /
`RECOMP_DEBUG=help` and "the title's own environment document" instead of
`cat/docs/env.md`. The enhancements doc keeps the five toolkit keys, one
neutral example of a game key (`game.mode`, bound with
`enhance_cfg_bind_env("game.mode", RENV_<the game's id>)`), and says a
title's keys are documented by the title. cat's `docs/env.md` gains the
moved text: an "Enhancements file" paragraph listing `[fps] mode`,
`[fx] glow` and `[fx] glow_intensity` with their stock values, beside the
three config rows it already has for the variables. Every new key gets a row
in `cat/docs/env.md` (`present_stale`, `tex_cache`, `zbuf_slots`; `guest_cpus`
gains the `one` spelling and its game default; `apu_dsp_ack` says toolkit
default). The row edits stay small where BLX-31 edits the same row.

## Validation

- Mac build of cat; the POSIX ctest dirs; `pytest tools/recomp tools/disasm`;
  cat `uv run pytest scripts`, ruff check and format.
- `./blinx2 recomp` against the branch toolkit: `gen/` unchanged.
- One Metal story golden and one stage1 golden through the CLI runner, run
  dirs under `runs/vanilla/`.
- `RECOMP_DEBUG=help` lists the three new keys; `RECOMP_DEBUG=apu_dsp_ack=0`
  still turns the ack off (read in the boot log).
- `git merge-tree` against `fix/mac-one-cpu`: conflicts, if any, confined to
  the `recomp_env.h` table tail and cat's `docs/env.md` rows.
- Proton, scheduled by the orchestrator: BLiNX 2 golden; Burnout 3 boot and
  audio (`apu_dsp_ack` auto now from the toolkit, `guest_cpus=one` from the
  game default).
