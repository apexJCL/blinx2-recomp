## Context

The wizard runs before any toolchain exists on the player's machine.
What it knows offline is the config the CLI embedded at build time
(`internal/gamecfg/config.json`), or, in `--game DIR` mode, what
`wizard config --json --dev` prints. Game constants never go in the
CLI; generic ones never go in a game.

## Decisions

**D1. The list lives in the CLI, in `src/xboxrecomp_cli/credits.py`.**
Two tuples of entries, each `{name, role, license, url}`:
- `OURS`: xboxrecomp-cli, the toolkit fork (apexJCL/xboxrecomp) and its
  upstream (sp00nznet/xboxrecomp, by sp00nz, MIT, per its LICENSE).
- `THIRD_PARTY`: the projects the wizard and the build use directly,
  in three groups: what the wizard is made with, what goes into the
  game the build makes, then the build's tools. Each one is checked
  against the code that uses it (D6). Transitive dependencies are left
  out; `NOTICES.txt` carries their licences.

**D2. A game's entries come from `[[wizard.credit]]`** in game.toml:
`name`, `role`, `license` and `url`, all required strings. The url is
an https address. `license` is an SPDX expression (checked loosely: the
characters SPDX uses, no spaces at the ends). manifest.py refuses an
unknown key and a missing field, as for `[[wizard.option]]`.

**D3. The order is the CLI's, the same for every game: our repos,
then the third party** (the user: "Start with our repos, then on the
third-party tools"). In order:
1. the game's own repo or repos: its `[[wizard.credit]]` entries marked
   `own = true`, in game.toml's order. The mark is explicit; position in
   game.toml does not decide it.
2. `OURS`: the CLI, the toolkit fork, upstream.
3. The game's other entries (blinx2's PT Sans Narrow), in game.toml's
   order, leading the third-party section rather than merged into
   `THIRD_PARTY`. `THIRD_PARTY` is grouped by what uses each project
   (the wizard, the game, the build's tools), and a game's extra fits
   none of those groups; placing it first also puts what is particular
   to this game where its players look first, with no sorting rule to
   keep.
4. `THIRD_PARTY`.

With no `[[wizard.credit]]`, the list starts with the CLI (the generic
wizard's own project). A url is listed once, where it first comes in
that order, so a game that also names, say, SDL keeps its own wording.
manifest.py refuses two of a game's own entries with one url, which
would otherwise vanish without a word. `own` only picks the place: the
config's entries carry the four shown fields. blinx2 lists blinx2-recomp,
xboxrecomp-cli, the fork, upstream, PT Sans Narrow, then `THIRD_PARTY`.

**D4. The channel is the config's `credits` key**, not a subcommand:
- the binary embeds the config at build time, so the list works offline
  and on first launch, before uv or Python exist;
- `--game DIR` already reads `wizard config --json --dev`, so developers
  see the same list without a second CLI run;
- a new optional key keeps `CONFIG_SCHEMA` at 1: an older wizard
  ignores it (Go's JSON decoding drops unknown keys), and a newer wizard
  with an older CLI's config finds no key and uses its fallback.

`gamecfg.Credit` mirrors the entry. Validate refuses an entry without a
name or with a url that is not https.

**D5. The fallback** (no `credits` key): xboxrecomp-cli, Go, Fyne,
zenity and Tabler Icons, from `gamecfg.FallbackCredits`, the wizard's
own direct dependencies.

**D6. The third-party list, as checked on 2026-10-15:**

| Name | Role | Licence | Where it is used |
|---|---|---|---|
| Go | the wizard's language and runtime | BSD-3-Clause | the wizard binaries |
| Fyne | the wizard's window toolkit | BSD-3-Clause | go.mod |
| zenity | the wizard's file dialogs | MIT | go.mod |
| Tabler Icons | the wizard's icons | MIT | `screens/tabler/`, the generic icon |
| xemu | the toolkit's audio (MCPX APU) and NV2A register code | LGPL-2.1-or-later | toolkit README, Licence |
| SDL | window, input and sound on macOS | Zlib | toolkit `find_package(SDL2)` off Windows |
| OpenSSL | the Xbox kernel's crypto on macOS | Apache-2.0 | toolkit `src/kernel` off Windows |
| libepoxy | OpenGL loading on macOS | MIT | toolkit `src/d3d` off Windows |
| Python | runs the CLI and the toolkit's tools | PSF-2.0 | the CLI |
| uv | installs Python and the build's tools | MIT OR Apache-2.0 | wizard pins, `env.find_uv` |
| Git | fetches the game, the toolkit and the CLI | GPL-2.0-only | the wizard's clone; MinGit on Windows |
| Homebrew | installs the macOS libraries | BSD-2-Clause | wizard pins `homebrew_install` |
| CMake | configures the game's build | BSD-3-Clause | the game's pyproject, `build.py` |
| Ninja | runs the game's build | Apache-2.0 | the game's pyproject, `build.py` |
| llvm-mingw | the Windows compiler | ISC AND Apache-2.0 WITH LLVM-exception | `fetch.MINGW_ASSETS` |
| NSIS | makes the Windows installer | Zlib | `[toolchain] nsis`, `package` |
| Capstone | decodes the game's code for the lifter | BSD-3-Clause | the toolkit's disasm tools |
| pefile | reads the game's executable | MIT | the toolkit's tools |
| umu-launcher | runs the Windows build on SteamOS | GPL-3.0-only | `package/steamos.py` |

URLs: each project's GitHub repository, except NSIS (not on GitHub:
nsis.sourceforge.io).

**D7. One builder, `creditsList(compact)`, two layouts.** Each entry's
name is a hyperlink with the external-link glyph (the hint link's
`tapRow` from wizard-test-notes); links open through the `openLink`
seam. The role and licence are quiet (dimmed) text.
- The dialog (`compact` false) gives each entry two lines: the link,
  then "role · licence" wrapping beneath it. The dialog exists to be
  read, so nothing is cut; a narrow window wraps the role instead.
- Welcome (`compact` true) gives each entry one line: the link, then
  "role · licence" on the same line, cut with an ellipsis when the
  window is narrow. The list there credits at a glance and must not
  push the folder pickers, the page's real work, out of view; the
  dialog, one tap away, has the full text.

**D8. The info button** is `widget.NewButtonWithIcon("", info-circle)`
with low importance at the right end of the header line, after the
step counter. It is focusable, so the keyboard reaches it. Fyne has no
tooltips or accessible names for icon buttons, so the dialog's title
says what it is: "Open-source credits". `render` hides it on Welcome
and shows it elsewhere.

**D9. The dialog** is a `dialog.NewCustom` with "Close", the list in a
vertical scroll, then one sentence: "NOTICES.txt, which came with the
wizard, holds each licence's full text." Width min(560, window − 48);
height min(520, window − 96); both follow a resize through the
`sizeWatch` from wizard-test-notes.

**D10. On Welcome** the list sits right below the intro paragraph,
under a bold "Made with these open-source projects" line, before the
folder statements, as the user asked. It is in a vertical scroll whose
height is eight rows (eight times a row's height): enough to show our
repos and the wizard's own projects at once and to say the list goes
on, and short enough that the folder pickers stay on a 580-pixel-high
window's first screen with the intro.

**D11. What the Windows exe links statically** (checked on the
blinx2 dev build, 2026-10-15). llvm-mingw links the MinGW-w64 runtime's
startup code and CRT helpers into it (its "Mingw-w64 runtime failure"
and pseudo-relocation strings are in the exe). The runtime's
`COPYING.MinGW-w64-runtime.txt` asks for its notices with a binary, so
NOTICES.txt carries it as a section, from a copy in
`wizard/notices/` that the Windows build checks against the pinned
llvm-mingw (so a new pin cannot ship stale notices). No notice is needed
for compiler-rt's builtins (Apache-2.0 WITH LLVM-exception, whose
exception covers compiled programs). The C code (GLFW) is not C++, and
nothing links libunwind, libc++ or winpthreads. The CRT itself is the
system's UCRT, linked as DLLs. The Linux build links glibc dynamically
and libgcc under the GCC Runtime Library Exception, so neither needs a
notice. The licence finder also takes REUSE-style `LICENSES/<id>.txt`
folders, at a module's root and in a linked package's folder.

## Risks

- A scroll inside the scrolling Welcome page: the mouse wheel over the
  box scrolls the box first. Eight rows keep the box small enough that
  the page's own scroll is easy to reach around it.
- The third-party list is curated by hand: a new tool the build starts
  using must be added. A test pins the list's shape (each entry has the
  four fields and an https url) but not its completeness.
