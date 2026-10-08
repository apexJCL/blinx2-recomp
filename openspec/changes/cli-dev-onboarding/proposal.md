# cli-dev-onboarding: a new game in one command, and a README that reads like one

Status: written by Fable (2026-10-07), so CLAUDE.md step 1's separate Fable
pass does not apply. Facts were checked against xboxrecomp-cli `main`
023c77e (the commit cat and b3 pin), cat `main` 3ac4535, b3 `main`, and the
toolkit `posix-host/portability` cb43f7b (its `templates/new-game/`).

The spec lives in cat because xboxrecomp-cli has no `openspec/`, as
b3-on-xbr's did. Nothing here touches the game, the toolkit, the renderers,
the goldens or the bench host: it is CLI code, CLI tests and CLI docs.

## Why

The CLI's README is written for the two games that already exist. It
explains how a game's bootstrap finds the CLI, how maintainers move pins and
how a public push is audited, and nothing about how a developer with a dump
of a third game gets to a first executable. That developer has to work it
out from `docs/manifest.md`, cat's tree and the toolkit's Getting Started,
and the steps they end up with are these (from an empty Mac or Linux
machine; Windows is a build host the CLI supports but nobody has tested):

1. Install git and uv (and, on a Mac, the Command Line Tools).
2. Clone xboxrecomp-cli.
3. Clone the toolkit fork at `blinx2/portability`.
4. Make a Python environment with capstone and pefile by hand, to run
   `tools.xbe_parser` once for the title ID and the entry point.
5. Make the game directory; copy the toolkit's `templates/new-game/`
   (CMakeLists.txt, `src/main.c`, `src/recomp_manual.c`).
6. Edit `project()` in CMakeLists.txt and the three constants in `main.c`.
7. Write `game.toml` from `docs/manifest.md`: twelve required keys, two of
   them 40-character shas found with `git rev-parse` in the two clones.
8. Copy `wrapper/game.py` from the CLI as `<slug>.py`; write the `<slug>`
   and `<slug>.cmd` wrappers from cat's.
9. Write `pyproject.toml` for the tools environment (copy cat's: cmake,
   ninja, capstone and pefile pinned, `package = false`, `no-build = true`).
10. `uv lock` for `uv.lock`.
11. `./<slug> pins refresh` for `config/setup-pins.json` (and without it,
    `setup` ends in a traceback, not a message).
12. Write `.gitignore` (copy cat's and fix the gen path), so the dump, the
    generated code, the toolchain and the bundles never enter git.
13. Copy the dump into `game_files/`.
14. `./<slug> setup`.
15. `./<slug> all` (analyze, recomp, build), and find that the toolkit
    template's `main.c` calls `recomp_dispatch_init()` without declaring
    it, which Clang (llvm-mingw) rejects and MSVC only warned about.

Fifteen steps, five of them copying files out of another game, and two
traps (11 and 15) that end in errors with no hint. For the project's own
goals this matters twice: the promise of cli-extraction ("a third game is a
manifest") is not kept until a third game can be started without reading
cat, and the public repositories are meant to be used by other porters.

## What changes

In xboxrecomp-cli (branch `feat/dev-onboarding` off `main` 023c77e):

- **`xbr new <dir>`**: one command writes a complete starter game: the
  manifest with every pin filled in, the bootstrap and its two wrappers,
  the tools `pyproject.toml`, `.gitignore`, `README.md`, the toolkit's
  `templates/new-game/` with the game's constants patched in, and the
  toolkit clone, `uv.lock` and `config/setup-pins.json` when the network
  allows (each one is a named follow-up otherwise). When the dump is
  already in place (or `--xbe` names it), the title, title ID and entry
  point come from the XBE header, read with the standard library.
- **An entry point that needs no checkout**: `xbr new` runs through
  `uvx --from git+https://github.com/apexJCL/xboxrecomp-cli xbr new …`,
  pinning `cli.commit` to the commit uv installed (PEP 610
  `direct_url.json`), or from a clone with `uv run xbr new …`. There is
  no `curl | sh` installer: uv is already the one prerequisite the
  bootstrap asks for, so a second installer would be a second thing to
  trust, and `uvx` is pinnable (`@<sha>`) and inspectable.
- **Two traps become messages**: a missing `config/setup-pins.json` is a
  `CliError` naming `pins refresh`; the scaffold declares
  `recomp_dispatch_init` in the copied `main.c` (and the toolkit template
  gets the same one-line fix as a follow-up, F1).
- **The README is rewritten** for a developer porting a game: a short
  pitch, prerequisites, the quickstart, "port your first game" (the loop
  after the first build), the command reference pointers, the bench host
  as an advanced optional, troubleshooting, and the maintainer material
  (pins, public pushes, the audit) moved to the end under its own heading.
  `docs/manifest.md` stays the reference and gains nothing but a line on
  `xbr new`.

The step count a new developer sees goes from fifteen to five: install uv
(and git), run `xbr new`, put the dump in `game_files/`, `./<slug> setup`,
`./<slug> all`.

Not in this change (coming on `feat/cli-housekeeping`, mentioned in the
README only as such): bench gc, golden pruning, `recomp --seeds`, the
`enhance_stock` keys moving to game.toml, and the stale-gen refusal in
`build` and `integrate`.

## Legal stance, kept

- The scaffold never copies, moves or links a dump. `--xbe` reads a header;
  the message says to put the dump in `game_files/` yourself.
- Nothing fetched is game data: the toolkit (a public repository at a
  pinned commit), llvm-mingw and NSIS (sha256-pinned), PyPI wheels (hashed
  in `uv.lock`).
- The scaffold's `.gitignore` keeps the dump, the generated code, the
  bundles and every capture out of git from the first commit.
- Enhancement assets are not part of a scaffold; the README says where
  they are made (locally, by the owner of the dump) and that they are
  never distributed.

## Windows as a development host

The CLI already treats Windows as a build host, not only a bundle target:
`<slug>.cmd` runs the bootstrap through the `py` launcher (else `python`),
`setup` fetches the llvm-mingw `ucrt-x86_64` (or `aarch64`) zip and the
portable NSIS zip into `third_party/`, `build windows` uses Ninja and the
CLI's toolchain file, `doctor` warns about a long checkout path and
`LongPathsEnabled`, and the D3D11 exe runs natively there. None of it has
been run on a Windows machine. This change plans the Windows path on the
same footing as the other two (design D8): the same `uvx` one-liner in
PowerShell (uv's own installer is the only `irm | iex` a developer
meets, and it is Astral's, not ours), the scaffold's `<slug>.cmd` with
CRLF and a `.gitattributes` that keeps it so, the toolchain story
(llvm-mingw through the CLI; MSVC stays the toolkit's own flow), the
path rules in the README, and tests that run on the Mac for everything
that is text (the `.cmd` wrapper, the attributes, the path warnings, the
`next:` line on a Windows host). The report lists what a Windows VM run
should verify, with the commands; it is not a gate for this merge.

## Affects

Hosts: macOS and Linux as build hosts (both tried for `xbr new`: the Mac
end to end in a scratch directory, Linux by the same tests); Windows as a
build host is supported by the CLI, covered by the Mac-runnable tests
above, and still unrun on a Windows machine, which the README says.
Render backends, goldens, bench runs: none. Toolkit: not touched; one
follow-up (F1) is an upstreamable one-line template fix.
