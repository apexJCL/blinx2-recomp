Worktrees `wt/readme-standard/<game>` on
`docs/readme-standard` off each repo's main (cat off a5bc49e5, CLI off
dfe1f0b; the first pilot was `spike/readme-standard`);
scratch `xbox-recomp/runs/readme-standard/`, PC scratch
`D:\bench\scratch\readme-standard-bench`.

## 1. The standard (CLI, phase 1)

- [x] 1.1 `docs/readme.md`: the sections, the marked blocks, the issue
  form's questions and tokens, the image rules, the checklist, phase 2.
- [x] 1.2 `templates/readme/README.md`: the skeleton, with the marks and
  `write:` comments.
- [x] 1.3 `templates/readme/.github/ISSUE_TEMPLATE/bug_report.yml` and
  `config.yml`; both parse as YAML.
- [x] 1.4 CHANGELOG (Unreleased).

## 2. BLiNX 2 pilot

- [x] 2.1 `docs/playing.md` and `docs/developers.md` from the old README,
  nothing dropped; links fixed for the new paths; a Troubleshooting
  heading; the bug section points at the form.
- [x] 2.2 The issue form, rendered for BLiNX 2.
- [x] 2.3 Fresh screenshots on the PC (D3D11, the 2026.11.2 exe 78c114a6, cat
  961599c7, toolkit 7a97fcd0): stills, the menu, a pair per enhancement;
  raw in `runs/readme-standard/`, the chosen set in `docs/images/`
  (plain PNG, no text chunks, downscaled); the old set removed, `free-camera.png`
  kept for docs/playing.md. The menu shot (F10 from the capture script
  never opened the menu on the PC) came later on the Mac (2b.3); a fresh
  free-camera shot is still open, and the README uses the kept one.
- [x] 2.4 `README.md` to the template.
- [x] 2.5 `uv run pytest scripts` and ruff (docs only; no goldens).
- [x] 2.6 The rendered pilot as a private Artifact for the user (its link
  is on the tracker item).
- [ ] 2.7 The user approves the README and every image (no public push
  before).

## 2b. The approval round (design D11)

- [x] 2b.1 The CLI standard and template: the renamed headings, the mods
  table and its entries, no config keys or environment variables, the
  issue form's settings question by menu page.
- [x] 2b.2 The pilot redone on cat main: the renamed headings, the mods
  table (19 rows from the descriptor dump and `src/`), an entry per row,
  `pair-glow`/`pair-hud` renamed to `pair-bloom`/`pair-texture-pack`.
- [x] 2b.3 New Metal pairs: HUD at the screen edges, Character detail,
  Collision, Anisotropic filtering; the menu shot (Mac Metal, build-matrix
  `blinx2-tk` exe; the menu through `kbm_script` F10 and window shots).
  The README's free camera entry uses the kept `free-camera.png`.
- [x] 2b.4 The review round: the toolkit's picture-changing Render rows
  (2D on guest grid, Scaling filter, HUD margin where a HUD table exists)
  in every game, the opening's "unless the table says otherwise", BLiNX 1's
  Square left stick on by default (main 35c326c), images quantised under
  1280 px, no tracker ids in public text, a CLI test for the template.

## 3. The other games (gap list: design D10)

Each repo gets README.md, docs/playing.md, docs/developers.md and the
issue form on `docs/readme-standard`, and the gaps in D10 stay listed for
the user.

- [x] 3.1 BLiNX 1: the mods table (Draw distance, Clamp diagonal speed,
  Speed readout, Square left stick), attract-demo shots (hero, title,
  stage); the pairs are placeholders.
- [x] 3.2 Burnout 3: the fork's README to the standard, upstream's credit
  near the top, upstream's Windows route kept in docs/developers.md; no
  Shaders row (the build ships no presets).
- [x] 3.3 KUF: the HUD at the screen edges and texture pack rows; a
  title-screen hero (the runs never got past the title, so the pairs are
  placeholders).
- [x] 3.4 Auto Modellista: the HUD at the screen edges row; placeholders
  (no Mac build).
- [x] 3.5 Quantum Redshift: toolkit rows only (no Shaders page: the build
  ships no presets); no wizard block yet; a fresh Mac hero.
- [x] 3.6 SSX 3, JSRF, Spartan: toolkit rows at each pin (no Shaders page:
  none ships presets); placeholders.

## 4. Phase 2: `<slug> readme` (CLI)

- [ ] 4.1 `readme init` (skeleton and form, tokens from `game.toml`).
- [ ] 4.2 `readme sync` (the marked blocks; `--dry-run` diff).
- [ ] 4.3 `readme --check`; one `doctor` line; `public export` refuses a
  failing README.
- [ ] 4.4 `xbr new` writes the skeleton and the form instead of the stub.
- [ ] 4.5 Tests: tokens, sync keeps prose, check cases.
