## Context

The XBE certificate holds, at these offsets from its start: title ID
(+0x08), title (+0x0C, UTF-16, 0x50 bytes), 16 alternate title IDs (+0x5C),
region flags (+0xA0: 1 NTSC-U, 2 NTSC-J, 4 PAL, 0x80000000 manufacturing)
and version (+0xAC). Its size field (+0) is 0x1D0 or more on every retail
dump we hold, so all of them reach +0xB0.

`fingerprint.classify` compares the dump's sha256 with `[xbe] sha256`, then
the header-free section hashes with `[xbe.sections]`, and says known,
header, data, code or unknown (`why=truncated` when the file ends early).
The wizard reads the verdict from the plan JSON (`xbe` block) and asks only
for `code`.

Release facts of the dumps on hand:

| game | title ID | region | version |
|---|---|---|---|
| BLiNX 1 | 0x4D530013 | 0x1 NTSC-U | 6 |
| BLiNX 2 | 0x4D530065 | 0x7 region-free | 1 |
| KUF | 0x504C0006 | 0x7 region-free | 1 |
| JSRF | 0x5345000A | 0x1 NTSC-U | 1 |

## Decisions

### D1. Key names and meaning

`[xbe] region`, `version` (integers, 32-bit, default unset), `title`
(string, default `""`) and `alt_title_ids` (integers, each 1..0xFFFFFFFF,
default `[]`). They describe the release the port was made from. A key left
unset never takes part in a comparison, so a game without them behaves as
before. `fingerprint --toml` prints them with a region comment
(`region = 0x7  # region-free`) so a game copies them in with the sections.
The sha256 comes as a comment to add to the list (pasted as a key it would
repeat `sha256`), and `alt_title_ids` commented out under a "keep only IDs
of this same game" line: a sequel may list its prequel's ID. The region
keys need `[xbe.sections]` beside them, or a stock dump with only its
region flags patched reads as another release instead of `header`. CLI
v0.20.0 refuses all four keys (D8).

### D2. Another release is a field, not a verdict

The five verdict values are a contract (plan JSON, wizard, stamp, tests), so
they stay. `Verdict` gains `region`, `version`, `ref` (the manifest's
release text), `other` (bool) and `title_id` (the dump's, when it is not
`[xbe] title_id`). `other` is set when the manifest sets a region or
version and the dump's differs, or when the certificate's title ID is not
`[xbe] title_id`: import lets such a dump in (D3), and its code is its own.
A listed sha256 is never other: the game said that dump is fine. When the
title IDs differ, both release texts lead with them ("title ID 0x4D530099,
NTSC-U, version 6" against "title ID 0x4D530013, NTSC-U, version 6"), so
the two sides never read the same.

Precedence:
- `truncated` wins over other: a cut file's certificate may be garbage.
  `verdict()` clears `other` for it once, so the note, the plan record's
  `other_release` and the stamp claim no release.
- `header` plus other stays quiet in the wizard (the sections match, so the
  code is the same; the region flag alone changed) and the doctor line adds
  "; another release, X". The `fingerprint` command still names both.
- `code` or `data` plus other: the note says "another release: X, where
  this port was made from Y; the build may fail or the game misbehave",
  then which sections differ.
- The check off (no sha256, no sections) plus other gives `unknown`, not
  `known`: without hashes the release is the only fact, and it says the
  dump is not the reference.

### D3. Import across title IDs

`title_match(header, cert, manifest)` accepts another title ID when the
dump's alternate IDs name the game's, or the game's `alt_title_ids` name the
dump's, both only when the two IDs have the same publisher (the high 16
bits: a sequel that lists its prequel's ID is another game), or the dump's
title, normalized (lowercase, alphanumerics only),
equals `[xbe] title`, or `game.name` when `title` is unset. Import and
package then print a warning naming both IDs and both releases and go on;
anything else is refused as before. Title matching is loose on purpose:
the fingerprint, not import, decides whether the build will work.

### D4. Stamp token

`RECOMP_BUILD_XBE` gets ` release=PAL,v2` (region text, comma, `v` and the
version, then `,id=0x<title id>` when the title IDs differ) only when other
is set, so stock stamps do not change.

### D5. Wizard

`Plan.XbeRisk()` maps the plan's xbe block to Fine (known, header), Release
(other, not truncated, with a reference), Code (code), or Unknown (unknown,
truncated included). Anything but Fine adds a Summary line and opens the
build-anyway dialog before the build: the same dialog as modded code, with
no default button and "Back" first. Its title and text come from
`xbeQuestion(p)`; the strings live in `copy.go`, one for the Summary line
and the dialog text. `ModdedCode()` is gone: `XbeRisk` replaced its only
caller.

### D6. recomp: a wrap with no body fails

With `--exclude-manual`, recomp collects the manual file's wraps (`extern
... sub_X_gen`) and emits a body under that name for each. When an address
has no function in the analysis, or lies inside another function, no body
is emitted and the link fails on `sub_X_gen`. recomp now checks first and
stops, with the player's sentence first:

```
ERROR: Your game's XBE is probably another release (another region or
version) than the one this port was made from: the hand-written code is
keyed to that release's addresses, and the game's fingerprint command
names both releases.
src/recomp_manual.c needs 1 function this XBE's analysis does not give it,
so the link would fail:
  sub_00012340_gen: 0x00012340 is not a function in this XBE's analysis
```

The toolkit knows neither the game's command name nor its XBE path
(Burnout 3's is not `game_files/default.xbe`), so the CLI catches the
failed recomp and adds the fingerprint's note for the current dump and the
command, e.g. `./blinx1 fingerprint game_files/default.xbe`.

### D7. Uses of unknown functions fail, declarations warn

A `sub_` name the manual file uses in a function body (comments, strings,
preprocessor directives and `#if 0` blocks stripped) that is not a known
function, not wrapped and not skipped also fails at link: a call
(`sub_X(`), or the name as a value (`RECOMP_ABI_CALL(va, sub_X)`). Those
join the D6 error. Only uses inside braces count: at file scope a weak
declaration (`extern void __attribute__((weak)) sub_X(void);`), a second
declarator (`void sub_A(void), sub_B(void);`) and an unexpanded macro body
(`#define CALLIT() sub_X()`) all link, and are hard to tell from a use
without a C parser. Inside a body, a name after a type or a `*` is a local
declaration. Everything else is a WARN only (a file-scope `= sub_X`
initializer included).

Limit: recomp reads only the manual (scan) file, so a body that calls a
`sub_X` another of the game's sources defines (say `src/glow.c`) still
stops it, though it would link. Reaching the game's other sources from
recomp needs a new argument, which would change every game's gen key
argv; we chose to document the limit instead. No game in the pool has
such a call. A game that needs one makes the call from the file that
defines the function, or through a function pointer that file exports. Every manual file carries the example `sub_00012345`
in a comment, which is why comments never count. No game in the pool has
either today (cat, blinx, KUF, JSRF measured against their analyses).

### D8. Pins and held commits

cat pins CLI v0.20.0, which rejects unknown `[xbe]` keys. The release keys
for cat and blinx therefore sit in separate commits held until the `[cli]`
pin moves to a CLI with this change. BLiNX 1's sha256 and sections work on
v0.20.0 and merge now. KUF has neither (check off); this change reports it
and leaves it.
