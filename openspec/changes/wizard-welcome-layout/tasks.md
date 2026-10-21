Conventions: **CLI** = branch `wizard-ui/welcome` off `xboxrecomp-cli`
`main` f8949f6 in `wt/wizard-ui/xboxrecomp-cli`, committed with the
noreply identity, with no tracker ids. **cat** = branch `wizard-ui/spec`
for this spec. No toolkit change. Goldens are skipped: wizard only.

## 1. Credits (CLI)

- [x] 1.1 Footer button `creditsButton` (LowImportance) centred between
      Back and Next; it opens `creditsDialog`
- [x] 1.2 Remove Welcome's list, `welcomeRows`, the header's info
      button and `creditsHeading`

## 2. Statements and tips (CLI)

- [x] 2.1 `tip.go`: `tipLayer` in the content Stack; `tipItem`
      (Hoverable, Tappable; RichText lead)
- [x] 2.2 Welcome: a three-column row with StorageIcon, DownloadIcon and
      VisibilityOffIcon; a page change closes a tip

## 3. Path tiles (CLI)

- [x] 3.1 `pathtile.go`: an icon over a label, a chosen frame, hover and
      focus tints, Space or Return
- [x] 3.2 `pathChoice` and `syncPath`: tiles and the line under them;
      `pathPickHint`

## 4. Errors (CLI)

- [x] 4.1 `errorHelp` and `logButtons`; `logFile`; `openFolder`
- [x] 4.2 `plainPrepare` fallback becomes `prepareOther`; `checkRow.Err`;
      `rowView` adds the help; the raw error goes to the checks pane's
      log
- [x] 4.3 `errorBox`: log the error, show a custom modal
- [x] 4.4 Failure page: Copy error and Copy log path before Retry

## 5. Tests, docs and gates (CLI)

- [x] 5.1 Update credits, paths and screens tests; add `welcome_test.go`
- [x] 5.2 Add the new shots to `TestScreenshots`
- [x] 5.3 `docs/wizard.md` (Welcome, Checks, Done, Logs, Credits); the
      Tabler README's `info-circle` row
- [x] 5.4 `wizard/check.sh`; `uv run pytest tests`; ruff check and
      format
- [x] 5.5 A macOS wizard .app for one game, built and not installed;
      headless screenshots

## 6. Round 3 (CLI)

- [x] 6.1 Footer button text "♥️ Open-source", drawn as an outline button
      (`outline.go`), pink on light and dark
- [x] 6.2 `errorBody`: a `playerError` in the chain is shown as it is;
      `errorText` otherwise; `errorHelp` under both; `installNoScript`
- [x] 6.3 Tests (`TestErrorBox`, credits text); the excerpt stays

## 7. Review and merge (orchestrator)

- [ ] 7.1 Review
- [ ] 7.2 Squash-merge to `xboxrecomp-cli` `main`; re-pin the games at
      the next release round
