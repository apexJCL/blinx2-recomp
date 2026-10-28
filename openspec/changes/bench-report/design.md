# Design: bench-report

## D1. One verb, a renderer over the analyser

`<game> bench-matrix report RESULT [--baseline DIR] [--out DIR] [--public
REPO]` sits beside `plan`/`run`/`collect`/`analyse`, because it reads the
same scene TOML and the same result tree. (The user called it `bench
report`, but every bench-matrix verb lives under `bench-matrix`, and
`bench` is the bench-host group.) It reads `summary.json` (rows, arms,
verdict rules, and the tracker item's spin and per-CPU columns when present), the
per-run `run.json` for series charts, and each `run-info.json` for `hw` and
`build`. All frame statistics come from `analyse`. The report adds only
share-of-target ratios, the best-settings pick and the layout. With
`--baseline`, rows pair by (host, arm) and the deltas come from calling
The tracker item's `bench_matrix.compare()` in-process (not from a `compare.csv`
whose location the caller chose).

Outputs:
- `RESULT/report/index.html`: the private report (D7).
- `RESULT/report/report.json`: the model both outputs are built from (per
  host: the metrics, the best pick and why, `hw`, `build`), so a test or a
  later tool reads facts and does not have to parse the HTML.
- `--public REPO`: D8.

Python stdlib only. SVG is written as text, so no plotting library and no
JS are needed for the charts. The private HTML has a small inline script
for tooltips only.

## D2. The four figures, per host and arm

All four come from the **steady part** of the window: the window's frames
after the warm-up (`warmup_s`, 20 s for the JSRF title), as in
bench-matrix D2. A frame belongs to the part its end flip falls in.
- **Target fps**: `report.target_fps` in the scene, the rate the game is
  meant to run at (60 for JSRF, 30 for a 30 fps game). If the host's
  display refresh (from `hw`) is below the target, the host's row says so,
  and the target is not lowered.
- **Mean fps**: steady frames / steady seconds (`steady_fps`).
- **Lowest fps**: the headline is the **1% low**, 1000 / the mean of the
  slowest 1% of steady frame times (`steady_low1_fps`). It is stable over
  an 80 s window and responds to hitches. The **worst second**, the lowest
  whole 1-second bucket of the steady part (`steady_worst_s_fps`, a new
  analyse column), is kept beside it in the private report. It is easy to
  read but noisy, and buckets can read 61-62 at the cap. The public table
  shows the 1% low only, labelled "1% low".
- **p99 frame cost (ms)**: the nearest-rank 99th percentile of steady
  frame times (`steady_p99_ms`). This is the flip-to-flip interval, not
  CPU or GPU work time, so it is never under one refresh period on a
  vsync-bound host. The page says this under the table.

Across repeats, an arm's figure is the median of its clean runs (not
disturbed, as in analyse), with n and the min-max beside it. A host with a
`[verdict]` rule also shows good/bad counts, and its pick follows D4.

**Sampler group.** `analyse` groups runs by (host, arm, prof rate), and a
result tree often holds one arm at several rates (every Deck arm
at 0, 100 and 250 Hz). The sampler costs fps (1.1-1.3% at 250 Hz on the
Deck), so groups are never mixed in one median, one chart or one pick. Per
host, the report uses the **lowest rate that covers every arm the host
has a clean run of**: no sampler (prof 0) when every such arm has clean
unsampled runs. Arms with only disturbed runs don't count toward coverage. Otherwise it
falls back to the lowest rate with full coverage. Only when no rate covers
every arm does it take the lowest rate per arm, and it flags the host
"mixed sampler" with each arm's rate. The group is named in the host's
table, the radar caption, `report.json` and the public table. The other
groups appear only in the private sampler-cost note. On the tracker item this gives
the Deck at prof 0 (36 runs), the Mac at 250 Hz (12 arms with a clean
run; s2-dsp0-43, s2-dsp0-169, s3-dsp0-43 and s4-dsp0-169 have only
disturbed runs) and the PC at 250 Hz (its unsampled runs cover only
`s1-dsp0-43`). An arm with only disturbed runs is shown in the radar and
the table as a gap marked "disturbed", not "not run", and is not judged.

**How runs are taken** (implements this; the report states it in
its method section and in the disclosure, D5): by default every run uses a
borderless fullscreen window (fullscreen-desktop, not exclusive). A scene
can opt out with `scene.fullscreen = false`, and the report then flags
every such run as a disclosed deviation ("windowed"). The remote hosts
(PC, Deck) run first, and the Mac runs last and quiet.

## D3. Radar chart, one per host

- **Spokes**: one per arm, in plan order (`arms(scene)`, the axis order of
  the scene), the same order on every host, so shapes compare across
  charts. An arm a host excludes (the Deck's scale 4) keeps its spoke: the
  label is greyed with "not run", and each series is drawn as a line
  broken at that spoke and is never joined across it. Spoke labels come
  from the axis display names (`display` on the `[[axis]]` entry, D6), for
  example `3x · DSP · 16:9`. Past 24 arms the labels stop being readable,
  so the chart splits by the first `report.best.split` axis, or by the
  scene's first axis when `split` is empty, one radar per value, and says
  so in its caption.
- **Spread**: when an arm has n > 1, its spoke carries a short radial tick
  from the min to the max of the mean series, so a spread like the Deck's
  shows on the chart and not only in the table.
- **Radius**: value / target fps, on a linear scale from 0 at the centre to
  110% at the rim. Rings at 25, 50 and 75%, and a heavier labelled
  **target ring at 100%**. Values over 110% are drawn on the rim with an
  outward tick. The scale starts at zero so that small differences are not
  exaggerated: at the cap, mean shapes sit on the ring, and the 1% low
  series carries the visible differences. The caption says this: "Means
  at the target sit on the ring; the gaps show in the 1% low line and in
  the table." The exact numbers are in the table beside the chart.
- **Series**: mean fps (filled at low opacity, solid outline) and 1% low
  (outline only, dashed, no fill). The colours are fixed per series, not
  per host, so every chart reads the same way. When spokes are missing,
  the mean fill is drawn for each contiguous run of present spokes as a
  wedge closed through the centre, so it never spans a gap. With
  `--baseline` (the previous benchmark round), the baseline's two series
  are drawn under them in the muted ink, thin and dotted, and the legend
  names the baseline's build and date. The overlay goes into the public
  SVGs too, so progress is visible in the README (the user, 2026-10-23).
- **Labels**: the SVG has a `<title>` and a `<desc>` that give the target,
  the D4 pick per split value ("none at <value>" for a split value with
  no pick; an arm's display already names its split value), the highest
  and lowest mean, and the share of arms within the mean threshold, so a
  reader who cannot see the chart gets its summary.
- **Light and dark**: in the private HTML, the radar is inline SVG drawn
  with the page's colour tokens (`:root` variables, redefined under
  `prefers-color-scheme: dark` and `[data-theme]`, as in the page),
  so it follows the page. A README image cannot read the page's CSS, so
  the export writes two SVGs per chart, `-light.svg` and `-dark.svg`, each
  with its palette baked in, a transparent background and the system font
  stack. The README picks one with GitHub's `<picture>` and `<source
  media="(prefers-color-scheme: dark)">`, which follows GitHub's theme. A
  test checks each palette against GitHub's light and dark backgrounds:
  WCAG 3:1 for marks, 4.5:1 for label text. The SVGs have no scripts, external references or embedded
  fonts.

## D4. Best settings, per host

**The bar.** A run passes when it clears three checks. Each check measures
something different:

| key | default | what it measures |
|---|---|---|
| `mean_share_min` | 0.97 | throughput: steady mean fps >= 97% of target |
| `hitches_per_min_max` | 15 | how often frames miss: steady hitches (over 1.5x the median, bench-matrix D2) per minute |
| `low1_share_min` | 0.60 | how bad the worst frames are: steady 1% low >= 60% of target |

p99 is reported but is not a check. Under nearest rank, p99 sits at or
below every frame of the slowest 1%, so p99 <= 1000 / 1% low. A run that
passes the 1% low check has p99 <= 27.8 ms at 60 fps, and a p99 check
could never be the one that fails. Hitches and the 1% low are related but
not redundant: 40 short misses and 2 very long stalls fail different
checks. The bar is strict by choice (the user, 2026-10-23). A host that
averages the target but drops frames does not qualify until the drops
are fixed. For the Mac, that means its 5 s hitch pair.

The scene's `[verdict]` and this bar do different jobs. The verdict
(for example the Deck's `warmup_fps_min = 50`, `steady_hitches_max = 30`)
sorts runs into a host's good and slow **modes**. The bar judges a
setting's **quality**. The report never uses a verdict threshold as a
quality check.

**Pass share, exact for small n.** `min_pass` is a fraction string,
default `"2/3"`, parsed with `fractions.Fraction`. An arm passes when
`passes * den >= num * n`, in integers, so 1 of 1, 2 of 2, 2 of 3 and 3 of
4 pass, and 1 of 2 does not. No float rounding is involved.

**Modes that come and go at random (the Deck).** If a host's slow mode
strikes at random and a slow run counted as a fail, the pick would be a
coin flip. The tracker item's Deck had 18 slow runs of 36. With p = 0.5 and n = 3,
P(at least 2 good) = 0.5 for every arm, so the pick would say which arms
happened to draw good runs, not which settings hold 60 fps. It would even
give "16:9 at 3x qualifies but 4:3 at 3x does not". So, for a host with a
`[verdict]` rule:
1. **Test whether the mode follows a setting.** For each axis, run a
   permutation test on the host's pooled clean runs. The statistic is the
   range of the slow share across the axis's values. Use 20000 shuffles
   with a fixed seed (stdlib `random`; exact enough, and it handles axes
   with more than two values) and a Bonferroni-corrected level of
   0.05 / number of axes. The counts per value are printed with the p.
   the tracker item: scale p = 0.53, DSP p = 1.0, aspect p = 0.32, so no axis
   explains the mode.
2. **Mode not tied to a setting** (no axis significant): the mode is a
   property of the host. Each arm is judged on its **good runs only**.
   They estimate the arm's good-mode performance without bias, and its
   slow runs say nothing about the arm. An arm with no good run is "not
   judged". At p = 0.5 and n = 3 this happens to 1 arm in 8. If such an
   arm would rank above the pick, it is named under the pick. The host is
   flagged **unstable** when its pooled slow share is above
   `unstable_share` (default 0.10). The share, its counts and a 95% Wilson
   interval are shown in the private and the public output: "starts in a
   slow mode in 18 of 36 runs (50%, 34-66%)".
3. **Mode tied to a setting** (an axis significant): for the arms at a
   value whose pooled slow share is above `unstable_share`, the slow mode
   is part of the setting. Those arms are judged on all their clean runs,
   and slow runs fail. The arms at the other values are judged as in case
   2, on their good runs only. The host is flagged unstable only if the
   pooled slow share of those other arms is still above `unstable_share`.
   The report and the public line quote both shares with their counts:
   "slow mode in 9 of 12 runs at 16:9" for the tied value, and, when
   flagged, "starts in a slow mode in k of n runs (x%, lo-hi%)
   elsewhere".

A host without a `[verdict]` is judged on all its clean runs. `min_runs`
(default 1; good runs on a host with a mode) is the n below which an arm is
not judged. A pick that rests on one run is marked "single run"
everywhere it appears, the public table included (D8).

**Pick**: among the qualifying arms, the richest by
`report.best.priority`, a list of axes. Each axis has a `prefer` order, for
example scale `[4, 3, 2, 1]`, then dsp `[1, 0]`. An axis with no `prefer`
prefers its `stock` value, then the listed order. Once a scene has a
`[report]` table, `stock` is required on every axis, env axes included
(`arms()` needs it only for config axes today); a missing one is a schema
error (D6). The comparison is
lexicographic, so the highest scale that holds the target wins, and DSP on
is chosen at that scale when it also qualifies ("DSP on when free"). Arms
are unique per sampler group (D2), so the pick is unique. Each value of an
axis in `report.best.split` gets its own pick. The CLI default is `[]`;
the JSRF scene sets `["aspect"]`, since 16:9 against 4:3 is the player's
choice, not a richer setting.

**No arm qualifies**: the summary names the failing figures of the
closest arm, not a flat verdict. The closest arm has the smallest
**largest relative shortfall** over the three checks: (threshold - value)
/ threshold for the mean and the 1% low, and (value - limit) / limit for
hitches. Using the largest shortfall rather than a count of failed checks
means one cause is not counted twice. Text: "No tested setting holds 60
fps without frame drops. Closest: 1x · DSP · 16:9, 59.9 fps average, 1% low
35 (needs 36), 20 hitches/min (limit 15)." The public fragment uses the
same text.

**Expected picks on the tracker item** (a regression fixture for task 3.3, replayed
on `runs/bench-matrix/jsrf-title/summary.json`):
- Deck, prof 0: unstable (18 of 36 slow; no axis significant). 4:3 picks
  `3x · DSP · 4:3` and 16:9 picks `3x · DSP · 16:9`, each from a single
  good run, so both are marked "single run". No arm is left not judged
  above them.
- Mac, 250 Hz: none qualifies. 12 arms are judged (one clean run each);
  the four disturbed-only arms are not. The mean check (>= 58.2) passes
  on 11 of them, from s4-dsp1-43 at 58.65 to s1-dsp1-169 at 59.875, and
  fails only on s4-dsp1-169 (56.55). Every run fails on hitches
  (20.2-45.0/min) and the 1% low (24.2-34.8). Closest: 16:9
  `1x · DSP · 16:9` (hitches 20.2/min, the largest shortfall); 4:3
  `1x · DSP off · 4:3`.
- PC, 250 Hz: `4x · DSP` for both aspects, single run.

Thresholds: the defaults are in the CLI and are the same for every game;
`[report.best]` in the scene overrides them and `[report.best.hosts.<key>]`
overrides per host. The report prints the thresholds it used under each
best-settings box.

## D5. Hardware and build disclosure (runner)

`run` and `run-arm.ps1` add `hw`, `run` and `build` to `run-info.json`, captured
once per run, because clock caps and drivers can change mid-matrix. A
capture function per OS fills a fixed schema from named fields only. Raw
tool output is never stored, so nothing it happens to contain can leak.

```
hw: {schema: 1,
  os: {name, version, build, kernel},
  device: {model},                     # "Mac15,8", DMI product_name "Jupiter"
  cpu: {model, cores, threads, p_cores, e_cores, max_mhz, governor},
  gpu: [{model, vendor, driver, vram_mb, max_mhz}],
  ram_gb,
  display: {refresh_hz, width, height},
  power: {source, profile, tdp_w, gpu_mhz_cap, cpu_mhz_cap, perf_level},
  backend: {name, translation, translation_version}}
run: {sampler_hz,                      # 0 = no sampler (D2's group)
  pacing,                               # the log's present.pacing (sleep, spin...)
  present_mode, vsync,                  # when the runtime logs them
  order}                                # leg position
build: {version, version_public, game_sha, toolkit_sha, cli_version, exe_sha256}
```

`run` holds the facts about how the run was taken that change the numbers.
The sampler costs fps on the Deck. The pacing mode separates sleep from
spin builds (measured spin). The order follows the bench rules
The tracker item implements (remote hosts first, the Mac last and quiet).

The tracker item already writes some of these facts into run-info, so they are
read from its fields and not captured twice:
- the window mode from `present_fullscreen` (borderless fullscreen-desktop
  when set; a run without it, e.g. `scene.fullscreen = false`, is flagged
  "windowed" as a disclosed deviation);
- `hw.display.refresh_hz` from `refresh_hz` when present (the per-OS
  capture below fills it only when it is missing);
- quietness from `quiet_wait_s`, `busy_during` and `focus_lost`, which
  already decide `disturbed`.

The disclosure, the public one included, shows the sampler, the pacing,
the present mode and the window mode. The order and the quiet figures
stay private.

| | macOS | Steam Deck / Linux | Windows |
|---|---|---|---|
| CPU | `sysctl -n machdep.cpu.brand_string hw.physicalcpu hw.logicalcpu hw.perflevel{0,1}.physicalcpu` | `/proc/cpuinfo` model name, `lscpu`, `cpufreq/scaling_max_freq`, `scaling_governor` | `Get-CimInstance Win32_Processor` Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed |
| GPU, driver | `system_profiler SPDisplaysDataType -json` (chipset model, cores, Metal family) | `vulkaninfo --summary` (deviceName, driverName, driverInfo) if present, else `lspci -nn` VGA line plus the DXVK log's adapter and driver lines | `Win32_VideoController` Name, DriverVersion; `nvidia-smi --query-gpu=driver_version,clocks.max.gr` |
| RAM | `sysctl hw.memsize` | `/proc/meminfo` MemTotal | `Win32_ComputerSystem` TotalPhysicalMemory |
| OS | `sw_vers` | `/etc/os-release` NAME, VERSION_ID, BUILD_ID; `uname -r` | `Win32_OperatingSystem` Caption, Version, BuildNumber |
| Refresh | `SPDisplaysDataType` resolution and Hz of the main display | `xrandr --current` on the game's display (gamescope's Xwayland) | `Win32_VideoController` CurrentRefreshRate and resolution |
| Power, caps | `pmset -g` lowpowermode, `pmset -g batt` source | amdgpu `power_dpm_force_performance_level`, `pp_od_clk_voltage` OD_SCLK, `pp_dpm_sclk` top level, hwmon `power1_cap` (TDP); the observed `gpu.mhz_max` from run.json beside them | `powercfg /getactivescheme` (the name only), `Win32_Battery` presence; nvidia-smi `power.limit` pending |
| Backend | `metal`; Metal family | `PROTONPATH`'s basename (`GE-Proton11-7`), the DXVK version from Proton's files or its log | `d3d11`, feature level from the game log |

The Deck's 1040 MHz case: the disclosure gives the cap the driver reports
next to the highest clock seen in the run ("GPU clock cap 1040 MHz of 1600;
seen max 1040"). Either one alone does not explain the scale-3 numbers.

The Windows column as built (reconciled it with the code):
- RAM is `TotalPhysicalMemory`, the memory the OS can use, which matches
  what Linux's MemTotal reports; the DIMM capacity sum would read a few
  hundred MB higher on the same machine and is not needed for the
  disclosure.
- The nvidia-smi query is `driver_version,clocks.max.gr` (the name comes
  from `Win32_VideoController`);
  `power.limit` (GPU and caps) is not captured yet. It goes in once a PC
  run checks its output on the real card; until then the PC's
  power line omits it, since the report and the export skip a power key
  with no value.

`build.version` comes from the payload manifest that `package` writes
(`write_manifest`'s version). `run` finds it next to the exe or in the
dist the exe was taken from. If there is none, as with a hand-copied exe
like the tracker item's `skates_recomp-t4ec1a73.exe`, `run` needs
`--build-version`, and with neither it refuses. The shas come from the
same manifest's provenance, or from `--game-sha`/`--toolkit-sha`. The
Windows leg runs unattended from the series, so it does not refuse: its
`build.version` is the run's version folder name, which is always there,
and its shas are recorded only when that folder has the manifest. A
refusal there would lose the leg; the shas are private-only, and the
report shows a missing one as not recorded. A
version such as `20261023.0049-c5d8e7b0-t4ec1a73` embeds private short
shas, so `build.version_public` is its date and sequence part only
(`20261023.0049`, everything before the first `-`). Matching a build to a
public release tag would need the export's sha map, so it is left out:
the date and sequence part is always what gets published. Private shas
are never published (D8).

Free text a machine's owner can set (the `powercfg` scheme name, DMI
`product_name`, GPU names reported by drivers) is capped at 64 characters
and limited to `[A-Za-z0-9 ._()+,/:-]`; anything else becomes `?`. It
still goes through the D8 leak check.

**Never captured**: host names (`hostname`, `scutil`, `Win32_ComputerSystem.Name`,
ssh aliases), user names, any path (Proton is reduced to its basename, and
`exe` stays out of `hw`/`build`), serials and UUIDs
(`SPHardwareDataType` is never called; DMI `product_serial`/`product_uuid`/
`board_serial`, `Win32_BIOS.SerialNumber`, disk serials and the GPU UUID are
not read), MAC and IP addresses, SSIDs, and the monitor EDID serial. Runs
from before this change have no `hw`. The report shows "not recorded" for
them, and the public export refuses such a host.

If a host's runs disagree on `hw` or `build` (a driver update mid-matrix,
for example), the report lists each variant with its run count and flags
the host.

## D6. Report config in the game repo

The scene TOML (`config/bench/<scene>.toml`) gets a `[report]` table, and
each `[[axis]]` gets an optional `display` list. The CLI holds only the
generic defaults (D4) and the renderer.

`display` sits on the `[[axis]]` entry next to `labels`. `labels` name arm
ids and run dirs (`43`, `169`), and `display` is what readers see (`4:3`).
When `display` is missing, the label is used, then the value.
`load_scene` checks that `display` has the same length as `values`, as it
does for `labels`.

```toml
[[axis]]
name = "scale"
values = [1, 2, 3, 4]
display = ["1x", "2x", "3x", "4x"]
stock = 1
# ... config as today; likewise dsp (display ["DSP off", "DSP"], stock = 0,
# new) and aspect (stock = "4:3")

[report]
target_fps = 60
label = "Title screen, 100 s after the intro"

[report.best]
priority = ["scale", "dsp"]
split = ["aspect"]
prefer = { scale = [4, 3, 2, 1], dsp = [1, 0] }

[report.public]
readme = "README.md"
images = "docs/images/bench"
hosts.deck = { label = "Steam Deck LCD (Proton, D3D11)", slug = "steam-deck" }
hosts.mac = { label = "Mac, Apple silicon (Metal)", slug = "mac" }
hosts.windows = { label = "Windows PC (D3D11)", slug = "windows-pc" }
```

Schema errors stop the report with the offending key named: a
`priority`, `split` or `prefer` axis that is not in `[[axis]]`, a `prefer`
value that is not in its axis's `values`, `split` and `priority` sharing
an axis, a `min_pass` that is not a fraction in (0, 1], an axis without
`stock`, or a public host missing from `[hosts]`.

A host is published only when it is listed in `[report.public.hosts]`. The
scene's host keys (`deck` is also the Deck's ssh alias) never appear in
public output: file names use `slug`, and text uses `label`.

## D7. The private report

One self-contained HTML file (no CDN; the system font stack or the
The tracker item font tokens with local fallbacks). It uses the page's
layout: a 70ch reading column, charts up to 1040px, colour tokens with
dark mode, 16px gutters and no horizontal scroll at phone width (wide
tables scroll inside their box). The sections, in order. Those marked
(new) are added; the rest are the sections, generated:

1. Header: game, scene label, build versions and shas, run dates, run
   count, baseline if any.
2. Verdict per host: cards with steady fps range, 1% low range and p99
   range.
3. (new) Per host: the radar, the four-figure table for every arm (target,
   mean, 1% low, worst second, p99, n, min-max, good/bad, baseline delta),
   the sampler group, the best-settings box (thresholds, the mode test with
   counts and p, the unstable flag, arms not judged), and the disclosure
   (`hw`, `run`, `build`, with the variants when runs disagree and a note
   when the refresh is below the target).
4. The matrix: dot plots of steady fps, 1% low and p99 per arm across
   hosts, and the full table.
5. Range: best and worst run per host, the spread of steady fps by run.
6. Per-host detail, for every host with a `[verdict]` or with more than one
   run per arm: fps per second for all runs, coloured by verdict; the
   steady frame-time histogram by mode; warm-up fps against steady hitches
   with the verdict thresholds drawn.
7. Hot paths: the median share per function per host, with spin loops
   marked (the tracker item's spin-site column when present).
8. CPU and GPU headroom: GPU busy and clock by scale, the spin share and
   per-CPU busy, and the DSP's cost (the dsp axis's paired
   delta).
9. Methodology and caveats: generated from the scene (window, warm-up,
   start rule), how runs are taken (borderless fullscreen-desktop window,
   remote hosts first, the Mac last and quiet), the n per host,
   disturbed runs left out, the sampler group per host and the sampler
   cost from the other groups, and the thresholds.
10. Notes: `RESULT/report-notes.md`, if present, rendered as is (key
    findings, hypotheses, follow-ups). These the tracker item sections were written
    by hand and can't be generated, so they have a slot instead.

A test renders the report from a fixture result tree and checks that every
section is present, that every number in the four-figure table matches
`summary.json`, and that the page has no external URLs.

## D8. Public export

`--public REPO` writes into the game repo's working tree only. It never
commits or pushes.
- `<images>/<scene>/<slug>-light.svg`, `<slug>-dark.svg`: the radar per
  published host (D3), with the baseline overlay when `--baseline` is given.
- In `README.md`, the text between `<!-- xbr:bench <scene> begin -->` and
  `<!-- xbr:bench <scene> end -->` is replaced with:
  - a heading with the scene label, the date of the newest run and
    `build.version_public` (one build when every host ran the same, else
    each host's, "not recorded" where a host has none, so one host's
    build is never read as everyone's), and with `--baseline`, "since
    <baseline version_public>";
  - one `<picture>` per host;
  - a table with two rows per host and pick: the **best-settings** row and
    the **stock** row, so readers see where the settings start (the user,
    2026-10-23). The stock arm has every axis at its `stock` value, except
    that with `split` each split value gets its own stock row, holding the
    split axis at that value (JSRF: `1x · DSP off · 4:3` beside the 4:3
    pick, `1x · DSP off · 16:9` beside the 16:9 pick). When that arm has no
    usable data, the row stays and gives the reason in place of the
    figures: "not run" (excluded on the host), "disturbed" (only disturbed
    runs) or "not judged" (no good run, D4). Columns: platform,
    settings, target fps, mean fps, 1% low, p99 ms, n and the sampler
    group. With `--baseline` it adds a "since <version>" delta for mean
    and 1% low. A best row judged on its good runs shows those runs'
    medians (n reads "judged of all"), and its delta compares them with
    the baseline arm's good runs, "-" when the baseline was not judged on
    good runs; every other row and delta covers every run. A pick that rests on one run carries a "single run"
    mark, explained under the table;
  - the D4 lines where they apply: "no tested setting holds", and
    "unstable: starts in a slow mode in k of n runs (x%, lo-hi%)";
  - a `<details>` "Hardware" block per host with the allow-listed D5
    fields: device model, OS and version, CPU and cores/threads, GPU and
    driver, RAM, refresh, power mode and caps, backend and translation
    layer, and from `run` the sampler, pacing, present mode and window
    mode. The hardware block per platform is public, limited to these
    allow-listed fields (the user, 2026-10-23).

  If the markers are missing, it prints the fragment and exits 1. It never
  guesses where the fragment goes.

  The fragment replaces the scene's whole block, so a host in
  `[report.public.hosts]` with no runs in the result is refused (exit 1,
  nothing written), like a host without `hw` (D5): leaving it out would
  silently drop its published figures. To publish without it, drop it
  from `[report.public.hosts]`.

**Allow-list**: the public model is built field by field from `report.json`.
It holds the four figures with n and the sampler group, the picks and the
D4 lines, the allow-listed `hw` and `run` fields, `build.version_public`
and the run dates. It never reads `env`, `exe`, run dirs, profiles, hot
paths, GPU/CPU series, logs, notes, `build.version` or the shas.

**Leak check** over every file it writes, before it exits 0. It fails on:
- home and private paths (the macOS, Linux, immutable-host and Windows
  user folders, and Wine's `Z:` view of them), email addresses, links into
  Claude's web app, MAC and IPv4/IPv6
  addresses (generic patterns in the CLI);
- the private patterns of the game's `public audit`, loaded with
  `public.py`'s `private_patterns()` (the same lookup: `$XBR_PUBLIC_DIR`,
  then `$XBR_AUDIT_PRIVATE`, then `<git dir>/info/audit-private`). Private
  host names and the tracker id pattern belong there, not in a CLI regex.
  If no patterns file is found, the check cannot run and the export exits
  2, as `public audit` does;
- the scene's host keys, but only where an identifier could appear: in
  file names, in URLs, as `user@key` or `key:` in a path, and after
  `ssh`/`scp`/`rsync`. Plain prose is not checked against them, so the
  labels "Steam Deck LCD", "Mac, Apple silicon" and "Windows 11" pass.

Tests (pytest):
- a poisoned fixture built from a real `run-info.json`, so a field
  added there later is covered, with a host name, user paths, an email, a
  Claude web-app link, a serial, a MAC and an IP planted in every string field
  outside the allow-list (`env`, `exe`, the remote paths, `build.version`,
  the hw fields not published) and in fake raw tool output. The tracker item
  run-infos predate the `hw` and `build` blocks, so the fixture is a Deck
  run-info from the D5 runner (2026-10-24), its paths, shas and names
  scrubbed for the public CLI repo. The export's files hold none of them, and the
  leak check fails when one is planted in a template;
- a scene whose host key is `deck` and whose label is "Steam Deck": the
  export passes, and a planted `<bench-host>:~/x` or `ssh <bench-host>` fails;
- an `audit-private` file in a temp `$XBR_PUBLIC_DIR` whose pattern is
  planted in a label: the export fails.

**Rules this follows** (CLAUDE.md, "Public repos and legal"): charts and
tables are data, not game frames, so they don't fall under the frames
ban. Like the README screenshots, the user approves the images and the
fragment before any public push. The files go out only in a normal round
(`<game> public export`, which replaced `cat/scripts/export-public.sh`,
then `public audit`), and the round's audit greps the SVG text as it does
any added file. A task checks that the game's export rules carry
`docs/images/bench/**.svg` and the README fragment through unchanged:
the export applies the repo's rewrite rules and `!fail` checks to every
file, and when the repo has a `game.toml`, refuses a file its `public
export` would drop (`[public] exclude`, the private set) or refuse (the
layout refusals, a data extension).
