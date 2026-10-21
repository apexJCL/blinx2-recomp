Conventions: **CLI** = `wt/font-link/xboxrecomp-cli`, branch
`feat/wizard-font-link` off `main` 029e875, commits authored and
committed as `carlos <4037632+apexJCL@users.noreply.github.com>`, no
Claude chat links; **cat** = `wt/font-link/cat`, branch
`spec/wizard-font-link`. The wizard-build-checklist change is implemented
on the same branches.

## 1. CLI: manifest and detection

- [x] 1.1 `manifest.py`: `WIZARD_OPTION["font_hint"] = (STR, "")`; an
  error when it is set and `[enhance.hud] font` is empty; tests.
- [x] 1.2 `wizard.py`: `wizard font [--json] [--name NAME]` through
  `hud.resolve_font`; tests for found, missing, no font named, and the
  JSON shape.

## 2. Wizard

- [x] 2.1 `gamecfg.Option.FontHint`; Parse test.
- [x] 2.2 `runner.Font` (the call and its parse); tests.
- [x] 2.3 Options page: unknown/missing/found states, the check on each
  visit, stale answers dropped; tests.
- [x] 2.4 The `external-link` glyph after every hint link (`strokeIcon`,
  `ColorNameHyperlink`), tappable, not focusable; tests for the recolour
  in both themes and the tap.
- [x] 2.5 The stop dialog (D5, D6) and the quit sentence; tests.

## 3. Docs and cat

- [x] 3.1 CLI `docs/wizard.md` (`font_hint`, `wizard font`, the glyph,
  the dialog), `docs/manifest.md` if it lists option keys.
- [x] 3.2 cat `game.toml`: `hud_pack` moves its font sentence to
  `font_hint`; `docs/packaging.md` notes the wizard's check.

## 4. Gates and host check

- [x] 4.1 CLI: `uv run pytest tests`, ruff check and format,
  `bash wizard/check.sh`, `bash scripts/audit-public.sh main..HEAD`.
- [x] 4.2 cat: `uv run pytest scripts`, ruff (against the v0.7.3 pin;
  note what cannot pass before the pin bump).
- [x] 4.3 Windows (`D:\bench\wizard-fb\` only): the CLI clone at the tip,
  `blinx2-wizard.exe` rebuilt (or `-next` while the user's copy runs),
  `wizard font --json` with the game's font and with a name that is not
  installed, recorded here.

## Results (2026-10-15)

- CLI `feat/wizard-font-link` 7395578 (on 64e96b7). `uv run pytest
  tests`: 645 passed, 1 skipped. ruff check and format: clean.
  `wizard/check.sh`: gofmt, vet, tests, race and staticcheck ok.
  `audit-public.sh main..HEAD`: clean; author and committer are the
  noreply address on both commits.
- cat: `uv run pytest scripts` 45 passed, 1 skipped; ruff clean. The
  v0.7.3 pin's manifest check refuses `font_hint` ("unknown key"), so
  the `[cli]` pin moves with this game.toml at merge; the branch's CLI
  loads it.
- Mac: `font_report` finds PT Sans Narrow Bold in
  `/System/Library/Fonts/Supplemental/PTSans.ttc` (macOS ships it).
- Windows 11 (`D:\bench\wizard-fb\` only): the CLI clone checked out at
  7395578 from a bundle; `blinx2-wizard.exe` rebuilt on the Mac
  (`./blinx2 wizard build --dev --only windows`, sha256 4c838494...)
  and replaced in place (no copy was running); `run-wizard.cmd`
  unchanged. The test checkout's `game.toml` (public main 87f6020)
  carries this branch's `hud_pack` lines, so `--game` shows them.
  `wizard font --json`: `{"font": "PT Sans Narrow Bold", "found": true,
  "path": "<home>\\AppData\\Local\\Microsoft\\Windows\\Fonts\\PTSansNarrow-Bold.ttf"}`
  (the per-user font folder); `--name "No Such Font Bold"`: `found:
  false, path: null`. `wizard config --json --dev` carries `hint` and
  `font_hint` apart. So on that PC the Options page shows "PT Sans
  Narrow Bold is installed." and no link.

## 5. Review fixes (review, 2026-10-15)

- [x] 5.1 Third-party notices in every archive: `wizard build` writes
  `NOTICES.txt` from the module cache (`go list -deps` over darwin
  arm64/amd64, windows and linux amd64; each linked module's root
  licence files plus those in each linked package's folder and its
  non-package subfolders; the Go standard library's LICENSE and
  PATENTS; the Tabler and wizard licences). It goes beside the exe, in
  the Linux tar and in the app's `Contents/Resources/`. A linked module
  with no licence file stops the build. 49 sections for CLI 8fd4028:
  Fyne (BSD-3) and its font licences, zenity (MIT), GLFW's zlib licence
  for its C sources, harfbuzz's, the golang.org/x PATENTS files.
  Tests: the gathering rules, the text, `linked_modules`, and the zip
  and app contents.
- [x] 5.2 The stop dialog follows a window resize (`sizeWatch` under the
  page); a test resizes the window while it shows.
- [x] 5.3 Retry's sentence: "Retry runs the build again and reuses most
  of what already finished."
- [x] 5.4 Gates for CLI 8fd4028: pytest 648 passed, 1 skipped; ruff
  clean; `wizard check --dev` (check.sh, race, staticcheck, and the
  double build of all three assets: equal sha256s, NOTICES.txt the same
  bytes, 8ea0c6d9..., in the zip, the app and the tar); audit-public
  clean, noreply only. Windows (`D:\bench\wizard-fb\` only, no copy
  running): exe replaced, sha256 35b42094...; the cli clone at 8fd4028.
