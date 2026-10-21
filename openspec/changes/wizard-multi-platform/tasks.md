Conventions: **CLI** = branch `wizard-ui/welcome` in
`wt/wizard-ui/xboxrecomp-cli`, committed with the noreply identity, with
no tracker ids. **cat** = branch `wizard-ui/spec`. No toolkit change.
Goldens are skipped: wizard only.

## 1. Investigation

- [x] 1.1 How `xbr package` builds a target; what two runs share
      (import, generate, `build-pkg-win`); no CLI change needed

## 2. Model and settings (CLI)

- [x] 2.1 `State.Targets`, `SetTargets`, `Builds`, `For`,
      `StepTargets`; `--clean` on the first only
- [x] 2.2 `hostinfo.Targets` with the lenient reader; `targets` saved
- [x] 2.3 `runner.Part.Group`, `NewGroupedChecklist`

## 3. Pages (CLI)

- [x] 3.1 Platform: checkboxes on Fresh, radios on Update
- [x] 3.2 Build loop: a result per platform; the failure policy
- [x] 3.3 Summary: platforms, plan and data per platform
- [x] 3.4 Building: group headings; Done: each platform's end

## 4. Tests and gates (CLI)

- [x] 4.1 `TestTargets`, `TestSettingsTargets`, `TestChecklistGroups`,
      `TestTargetPage`, `TestBuildPlatforms`, `TestSumDisk`,
      `TestHereTarget`; `go vet -tags e2e` in check.sh
- [x] 4.2 Screenshots: platform-multi, summary-multi, building-multi,
      done-multi-partial, platform-update
- [x] 4.3 `wizard/check.sh`; a macOS .app built, not installed

## 5. Review and merge (orchestrator)

- [ ] 5.1 Review
- [ ] 5.2 Squash-merge with `wizard-welcome-layout`
