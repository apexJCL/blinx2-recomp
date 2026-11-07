## Context

What the game repos have today (2026-11-04):

| Repo | README | Wizard on releases | `[xbe]` release keys | Images |
|---|---|---|---|---|
| blinx2-recomp | 649 lines, players then developers | yes (v2026.11.1) | sha256 x2, region, version, title | 8, from 2026-10 |
| blinx1-recomp | 220 lines, the same layout | yes (v2026.11.1) | sha256, region, version, title | none |
| burnout3-recomp | 345 lines, its own layout (upstream's fork) | yes (v2026.11.2) | sha256 only | 4 (1x/2x pairs) |
| kuf-recomp | the `xbr new` stub | yes (v2026.11.2) | none (sha256 empty) | none |
| Auto Modellista | the `xbr new` stub, not public | no `[wizard]`, no `[package]` | none | none |

The pieces a standard README needs already exist in the CLI and the
manifests: `game.toml` `[xbe]` holds the release (`xbr fingerprint` reads
the certificate, and the wizard warns on another release before it
builds), `[wizard]` and `[[wizard.option]]` hold what the wizard offers,
`[package] app` names the data folder, `[public] url` the repo, and the
release workflow names the wizard assets
`<slug>-wizard-<tag>-{windows-x64.zip,macos.zip,linux-x64.tar.gz}`.
`public export` and the CLI audit allow README images only as plain PNGs
under `docs/images/` (`layout.README_IMAGE`, `png_problem`).

## Decisions

### D1. The template lives in the CLI, as a documented skeleton with marked blocks

Three places could hold it:

1. **A cat file the other games copy.** Cheap, but cat is one game: the
   next game copies BLiNX 2's prose and its facts with it, and every
   change to the shape is a hand edit in five repos.
2. **A README rendered whole from `game.toml`.** Never drifts, but the
   parts a player reads first (what the game is, how far it plays, the
   captions) are prose no manifest key can hold, and a renderer would
   either grow a key per sentence or produce the stub players have now.
3. **The CLI, as a skeleton plus marked blocks** (chosen). The CLI already
   owns everything game-agnostic about a game repo (`xbr new` writes its
   README stub, its workflows, its wrappers), and the facts the README
   must restate exactly (release keys, slug, repo, wizard options) are
   already in `game.toml`, which the CLI reads. So `templates/readme/`
   holds the skeleton and the issue form with `@TOKEN@` slots, the
   sections that restate the manifest sit between
   `<!-- xbr:readme:NAME -->` marks, and the rest is the game's prose.
   The CLI never holds a game fact: what it fills comes from the game's
   own `game.toml` at the time it runs.

Phase 1 (this spike) is the skeleton, the form and the doc; the pilot
fills the marks by hand. Phase 2 is `<slug> readme` (D7). The marks cost
nothing now and let the command take the blocks over without a rewrite.

### D2. The sections and their order

The user's list, plus three sections a player needs to finish the job
(the status, the build requirements and gotchas, and where the rest of
the docs are). The headings are the ones the user approved on 2026-11-05
(D11), in the order a first-time reader needs them:

1. title, a plain pitch and the hero image;
2. the download box (a GitHub TIP alert);
3. "no game included", one line;
4. the supported release (an IMPORTANT alert, D4);
5. *How the builder works*;
6. *Status* (how far it plays, platforms, top known issues);
7. the showcase: stills, *The in-game menu*, *Mods and enhancements*;
8. *Build requirements and common gotchas*;
9. report a bug;
10. more documentation;
11. legal, license and credits.

The headings are fixed so `--check` (D7) can find them and so a player who
read one game's README finds the same places in the next.

### D3. The dense material moves to two pages, not away

Nothing of the old README is dropped. It splits by reader:
`docs/playing.md` (a player who wants more than the wizard: building by
hand, installing each bundle, controls, saves, the full options table,
widescreen, free camera, the HUD pack, known issues, troubleshooting, the
crash checklist) and `docs/developers.md` (architecture, repos and paths,
build from source, the pins, testing and goldens, environment variables,
the docs index, contributing). The existing `docs/packaging.md`,
`docs/input.md`, `docs/env.md` and `docs/frame-generation.md` stay where
they are and are linked from both. Links into the old README's anchors
(`#build-the-game`, `#options`, `#widescreen`) are updated to the new pages.

### D4. The release disclaimer restates `[xbe]` and says how to check

The box lists the title, title ID, region (in the CLI's words:
`region-free`, `NTSC-U`, ...), version and every known `default.xbe`
sha256, then the two ways to check a copy: the wizard's Dump page, or
`./<slug> fingerprint /path/to/disc.iso`. It says plainly what another
release or a modded copy gets: a warning, and a game that may crash. A
player cannot be expected to hash an XBE inside an ISO, so the sha256 list
is there for the bug report and for the curious, and the wizard's check is
the one the box leads with.

### D5. Links go to `releases/latest`, the file names are shown as patterns

The wizard's assets carry the version in their names, so a per-file link
(`releases/latest/download/<name>`) would break at the next release.
The box links the release page and names the three files as
`<slug>-wizard-<version>-windows-x64.zip` and so on, so a player knows
which to click. Version-free asset aliases (one more copy per release)
would allow direct links; that is an open question for the user, not a
part of this change.

### D6. The issue form asks for what triage asks for today

The questions are the ones the last month's triage asked by hand: the
copy of the game (supported, another release, modded, not known, plus the
fingerprint or the boot line), the build version, wizard or CLI, platform,
GPU backend, system, what happened and the steps, the save described in
words, the settings, the logs with each platform's path, and a required
tick that nothing attached holds game files, a disc image, a save or a
bundle. Saves are described, never attached: a save is game data and an
issue is public. `config.yml` keeps blank issues (developers file those)
and links the troubleshooting section first.

### D7. Phase 2: `<slug> readme`

- `readme init`: write the skeleton and the issue form for a game that
  has none, with the tokens filled (refuses to overwrite).
- `readme sync`: rewrite the marked blocks from `game.toml` and leave the
  prose alone; with `--dry-run`, show the diff.
- `readme --check`: the checklist in the CLI's `docs/readme.md` (headings
  in order, blocks equal to what sync would write, images present and
  plain, the two docs pages, the form with no token left). `doctor`
  reports it as one line, and `public export` refuses a README that fails
  it, so a release cannot ship a stale disclaimer.
- `xbr new` writes the skeleton and the form instead of today's stub.

### D8. Images: fresh, few, small, and from the build players get

The first pilot set was taken for the README on the Windows PC (native
Direct3D 11, the build host's release exe, cat 961599c7 with toolkit
7a97fcd0), from the game's own scripted stage routes (`scripts/shots/pad`)
so before/after pairs are the same frame: the scripted runs replay
exactly, so one flip number gives the same moment in each run, and the
runtime's D3D11 frame dump (`d3d11_dump` with `fb_dump_at`) writes it at
the render size, with the shader's output beside it. The menu shot is a
desktop capture, as the dump is taken before the overlay. Raw captures
stay in `runs/readme-standard/`; only the chosen set goes in
`docs/images/`, downscaled to the width the README shows and stripped of
text chunks. They are not golden references, test frames or A/B captures;
they are made for the README and the user approves them before any
public push.

After the approval round (D11) a Mac Metal build is fine too, at stock
resolution unless the shot is about render scale or aspect. The Metal
pairs come from `fb_dump` (the game's render target, before the overlay
and the shader) of runs of the same pad script, one run per setting; a
shot of the overlay or a shader needs the drawable (`RECOMP_WINDOW_SHOT`).
A shot that cannot be taken is a marked placeholder
(`<!-- TODO(screenshot): ... -->` plus a *Screenshot to come* line), listed
for the user; a golden or test frame is never reused.

### D9. One entry per mod: a pair where a picture shows it, an origin note where not

*Mods and enhancements* is a table with one row per mod the menu lists:
the name as the overlay shows it, the menu page, a brief description and
the default. The rows come from the build's descriptor dump
(`RECOMP_MODS_DESCRIBE=json`), the mods' About and help texts in `src/`,
and the toolkit menu's items (`enhance_menu.c`) at the game's pin; never
from memory. The toolkit rows every game shares are Render scale, Aspect
ratio, Anisotropic filtering, Overscan crop and the Shaders page's
Profile (or Shader on a pin before profiles); the texture pack and
Language rows only where the game has them.

Under the table, one `####` entry per row in the table's order. A mod
that changes the picture gets an on/off pair: one image, stock on the
left and the mod's on the right, the same moment of the same scripted
run. A mod a still cannot show gets a short note on its origin instead:
why it exists, and which hardware or game behaviour it comes from (the
TV overscan band, BLiNX 1's square-gate diagonals, the game's own cull
distance).

### D10. What the other games lack (the gap list)

Read 2026-11-04 (the last five rows 2026-11-05) from each main checkout's `game.toml`, README and
`docs/`. None has `.github/ISSUE_TEMPLATE/`, and none but BLiNX 2 sets
`[package] stamp_env`, so their forms drop the `[BOOT] build xbe:` half of
the fingerprint hint (or the game adds the stamp first).

| Game | Release block | Wizard block | Prose | Showcase | Other |
|---|---|---|---|---|---|
| BLiNX 1 (`blinx/`) | complete: `0x4D530013`, NTSC-U, version 6, one sha256, title | 2 options (render scale, fullscreen) | 220 lines in BLiNX 2's old layout: split to the two pages as here | no images at all: stills, the menu, render scale, widescreen; the draw-distance mod | no `stamp_env` |
| Burnout 3 (`b3/`) | sha256 and title ID (`0x4541005B`) only: add `region`, `version`, `title` from `fingerprint --toml` | 2 options | upstream's fork layout (345 lines, `docs/running.md`, `architecture.md`, `boot.md`): keep upstream's credit and history near the top, map its sections onto the standard's | 4 images (1x/2x pairs); needs stills of a race, the menu, a widescreen pair | the user decides whether the fork follows the standard or keeps upstream's shape |
| KUF (`kuf/project`) | title ID (`0x504C0006`) only, `sha256 = []`: the box cannot be written until the supported dump's sha256, region and version are in `[xbe]` | 2 options | the `xbr new` stub (96 lines): all prose to write, including how far it plays | none: stills, the menu, the HUD mod and the HUD pack pair | the form wants a battle or mission field after *Steps* |
| Auto Modellista (`automodellista/recomp`) | title ID (`0x4343000E`) only, `sha256 = []` | 2 options (`[wizard]` since the tracker item) | the 28-line stub | none, and no Mac build to take them on | public at its first round (`apexJCL/automodellista-recomp`) |
| Quantum Redshift (`qrs/`) | title ID (`0x4D530015`) only, `sha256 = []` | no `[wizard]`, no `[public]` | a placeholder | none | packages for Windows and SteamOS only |
| SSX 3 (`ssx3/recomp`) | title ID only, `sha256 = []` | 2 options | the stub with Progress and Options | none | older pin (blinx2-v0.10.0): a Shader row, not Profile |
| JSRF (`jsrf/skates`) | title ID only, `sha256 = []` | no `[wizard]` | the stub with the bench block | none | older pin, as SSX 3 |
| Spartan (`spartan/tca`) | title ID only, `sha256 = []` | 2 options, Windows and SteamOS | the stub | nothing renders yet | pin blinx2-v0.7.0: no Shaders page |

### D11. The approval round (the user, 2026-11-05)

The user approved the standard with five changes, applied to the CLI's
standard and template and to every game:

1. The headings *How the builder works*, *Status* and *Build requirements
   and common gotchas* replace "What the builder does", "Where the game
   is at" and "Make sure the build works".
2. *Mods and enhancements* is a table of the game's mods (D9).
3. Each mod that a picture can show gets an on/off entry, such as a pair
   of fresh screenshots.
4. A mod with no visual difference gets a brief note on its origin.
5. The README never names a `config.toml` key or value, nor an
   environment variable: it names only what the player sees, the overlay
   page, the option and its values. The keys stay in `docs/playing.md`.

The rollout covers every game repo on branch `docs/readme-standard` in
`wt/readme-standard/<game>`, in order: the active pool (BLiNX 2, BLiNX 1,
Burnout 3, KUF), then Auto Modellista and Quantum Redshift, then SSX 3,
JSRF and Spartan. Mod rows come from the source, facts from each repo's
docs, CHANGELOG and `cat/TASKS.md`.

## Risks / Trade-offs

- Two copies of the same facts (README and `docs/playing.md`) can drift.
  The README keeps only the summary and links the page; the marked blocks
  are the ones `sync` will keep exact.
- GitHub renders alerts (`> [!IMPORTANT]`) only on github.com; other
  viewers show a plain quote, which still reads.
- A screenshot set ages with each release. The showcase captions name the
  release they were taken on, so a stale shot is visible as such.
