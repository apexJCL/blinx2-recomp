Worktrees: `wt/onboard/cat` on `feat/dev-onboarding` (off cat `main`
3ac4535) holds this spec; `wt/onboard/xboxrecomp-cli` on
`feat/dev-onboarding` (off CLI `main` 023c77e) holds the code and the
README. No toolkit worktree: the toolkit is not touched (F1 and F2 are
follow-ups).

Rules for every task:
- CLI commits are authored and committed as
  `carlos <4037632+apexJCL@users.noreply.github.com>`; cat commits as the
  local identity.
- No Linux/Proton host run, no game run, no game file: the end-to-end trial uses a
  scaffold with a placeholder dump path in a scratch directory.
- `feat/cli-housekeeping` is changing `build`, `integrate`, `recomp` and
  the bench's gc on the same `main`; this branch keeps out of those
  functions and mentions their work in the README only as coming.

## 0. Spec

- [x] 0.1 proposal, design, tasks and the dev-tooling delta, written by Fable.

## 1. The scaffold (CLI)

- [x] 1.1 `xbe.py`: `read_header(data)` returns the title, title ID, base
  address and entry point (retail key, else debug) from an XBE header;
  `package` reads the title ID through it. Test: a synthetic header with
  both keys, a short buffer, a wrong magic.
- [x] 1.2 `scaffold.py`: the files of D1 from the manifest's own defaults,
  the pins of D3, the template patches of D4, and `new`'s messages.
  Dispatched in `main.py` before the manifest loads; `--help` lists it
  under the developer commands. Tests, with a fake toolkit template, fake
  git and no network:
  - the written `game.toml` loads and validates, and `wrapper --check`
    passes on the bootstrap;
  - the title, title ID and entry point come from a synthetic XBE and are
    in the manifest and `main.c`;
  - every patch matches once; a changed template is reported, not fatal;
  - `--offline` writes the files and names the three follow-ups;
  - `DIR` not empty is refused; a slug that is not `[a-z0-9-]` is refused;
  - the `.gitignore` covers the dump, gen, out, the build dirs, `dist/`,
    `external/`, `third_party/`, `.venv/` and the capture extensions.
- [x] 1.3 `fetch.load_pins` raises `CliError` naming `pins refresh` when
  the file is missing. Test.
- [x] 1.4 `doctor` closes with `next: …` (D6). Test on the report lines.
- [x] 1.5 Windows (D8), tested on the Mac: `<slug>.cmd` is CRLF with the
  `py -3` route and the `python` fallback; `.gitattributes` fixes `*.cmd`
  to CRLF and the LF files; a scaffold with `host_os` mocked to `windows`
  gets the `winget` hint in `next:` and `/` paths in `main.c`.

## 2. The README and docs (CLI)

- [x] 2.1 README rewritten in D7's order; the maintainer sections kept
  under "Maintainers". `docs/manifest.md` gains the `xbr new` line.
- [x] 2.2 `helptext.DOC` lists `new` among the developer commands (the help
  prints the same text with and without uv: test_help_is_the_bootstraps).

## 3. Gates (CLI worktree)

- [x] 3.1 `uv run pytest tests`.
- [x] 3.2 `uv run ruff check . && uv run ruff format --check .`.
- [x] 3.3 `scripts/audit-public.sh main..HEAD` clean, and
  `git log --format='%ae %ce' main..HEAD` shows only the noreply address.

## 4. The trial on the Mac (scratch directory, no game files)

- [x] 4.1 `uv run xbr new <scratch>/mygame` from the worktree, with
  `XBOXRECOMP_DIR` at the main toolkit checkout (read only) so no clone is
  made, and `LLVM_MINGW_ROOT` at cat's `third_party/` copy so nothing is
  downloaded. Record the output.
- [x] 4.2 `./mygame doctor`, `./mygame setup --no-toolkit` (the venv from
  the fresh lock), `./mygame analyze` refusing on the missing dump with the
  message that says where it goes.
- [x] 4.3 Configure the scaffold's windows build with the CLI's toolchain
  file and compile `src/main.c` and `src/recomp_manual.c` to objects (not
  a link: there is no gen/ without a dump), so the patched template is
  known to compile under llvm-mingw.
- [x] 4.4 Record the before (15 steps) and after (5) in the report with the
  README's quickstart as it reads.
- [x] 4.5 The Windows VM checklist in the report (D8's last point), with
  the commands as the README gives them. Not a gate: the user runs it
  when the VM exists.

Done on CLI `feat/dev-onboarding` 5605be2 (code, tests) and f8fbca5
(README, manifest.md), both off `main` 023c77e. The trial's logs are in the
session's scratch directory under `onboard/` (new.log, doctor-fresh.log,
setup.log, analyze.log, configure.log, compile.log, uvx-new.log): the
patched template's two objects compile under llvm-mingw against the
toolkit, and `uvx --from git+file://…@feat/dev-onboarding xbr new` pins
`cli.commit` to the installed commit.

## 5. Review and merge (orchestrator)

- [ ] 5.1 Fable review of the merge (this branch is Fable's; the review is
  a read of the diff before the squash).
- [ ] 5.2 Squash onto CLI `main`; cat's spec branch onto cat `main`; move
  the pins in cat and b3 when the next round moves them.
- [ ] 5.3 Remove `wt/onboard/`, keep the branches; copy the trial's output
  to `notes/onboard/`; update `cat/TASKS.md` with F1, F2 and F3.
