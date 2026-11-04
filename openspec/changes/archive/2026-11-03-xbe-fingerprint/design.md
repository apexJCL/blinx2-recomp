## Context

`[xbe] sha256` lists whole-file hashes. `bench golden` refuses any other
XBE, because its references were recorded on the listed ones. The rest of
the CLI only warns. The XBE's section table (`xbe.sections`, the CLI's
standard-library reader) gives each section's name, flags and raw bytes,
and the pipeline's `[pipeline.disasm]` says which sections it
disassembles. Those are the inputs a game-agnostic classification needs.

## Decisions

**D1. Section hashes in game.toml.** The table is `[xbe.sections]`, name to
sha256 of the section's raw bytes (`raw_off` .. `raw_off + raw_size` in the
file). It is a string table like `golden.enhance_stock`. One table serves
every listed XBE: the listed XBEs are expected to share their sections, and
`xbr fingerprint --toml` prints the table from a dump, so a maintainer
pastes it. The CLI holds no hash of its own.

**D2. Code is what the pipeline translates.** With `pipeline.disasm.text_only`,
the code sections are `.text` plus `extra_sections`. Without it, they are
every section with the executable flag (0x4). The flag alone would not do:
BLiNX 2 marks its model and motion data sections (M11, MDLPL, ...)
executable. A section the reference lacks counts as code when its own
flags are executable, and as data otherwise. A reference section the XBE
lacks counts as code when D2's rule names it, and as data otherwise.

**D3. Verdicts.**

| verdict | when | message |
|---|---|---|
| `known` | sha256 in `[xbe] sha256` | none |
| `header` | every section matches by name and hash | none (doctor: "header differs, sections match") |
| `data` | only data sections differ | `modded data, code stock: <sha12>; data sections differ: A, B` |
| `code` | any code section differs | `modded code, unsupported, may crash: <sha12>; code sections differ: .text, ...` |
| `unknown` | no `[xbe.sections]`, or the table cannot be read | today's unknown-dump note |

The section names are listed up to 8, then "and N more". A header that
moves a section's address while keeping its bytes is classed `header`.
That is a known limit; no such dump has been seen.

**D4. Never block.** `import`, `analyze`, `build` (with `all`), `package`
and `doctor` print the warning (`WARNING: ` before the `data` and `code`
notes) and go on. There is no override flag, because nothing refuses.
`bench golden`'s `check_dump` keeps its whole-file rule, so a `header`
dump is still refused there: its frames were never recorded.

**D5. One computation per XBE.** `fingerprint.of_path` caches by (real
path, size, mtime_ns). A run that warns in import and then in package
hashes the 38 MB XBE once.

**D6. Manifest field.** `write_manifest` sets `ex["xbe"] = {"sha256",
"verdict", "sections"}` (`sections`: the differing names, `[]` for
`known`/`header`). A known dump's manifest gains only this key. The
other bytes are unchanged for the same inputs.

**D7. Boot stamp through launch.env.default.** The runtime truncates
`RECOMP_STDIO_LOG` when it opens it, so a launcher cannot prepend lines.
The runtime does not print launch.env values it does not know, either.
So the stamp needs one runtime line (agreed with the orchestrator,
2026-10-18):

- `[package] stamp_env` (default `""`: no stamp) names the key, keeping
  the CLI game-agnostic.
- `stage` appends `# The XBE this build was made from (xbr fingerprint).`
  and `<KEY>=<sha256> <verdict>[ <sections, comma-joined>]` to the staged
  `launch.env.default`. That is the cat file plus two lines, LF.
- All three launchers export it. On the Deck, Proton passes the
  environment through.
- cat adds the game key `RECOMP_BUILD_XBE` (CONFIG tier) through
  `recomp_env`, with no raw getenv. `host_stdio_setup` ends with
  `[BOOT] build xbe: <value>` when it is set and not empty. That is once
  per run: each entry point calls it once.

A dev run (`blinx2 build`, goldens) has no launcher and prints nothing,
so stock output is unchanged.

**D8. Plan and wizard.** `make_plan` sets `xbe` once, before any early
return. The verdict is for the `--dump` source's XBE (read in place from
the image or folder, `Source.xbe_read`) when importing, else for
`game_files/`'s XBE, else `null`. The wizard's `Plan.Xbe` carries it.

- `code`: Build opens a confirm dialog that names the sections, with
  "Build anyway" and "Cancel".
- `data`: one line on the Summary, with no confirm.
- `null`, or an older CLI: no change.

The wizard passes no new flag.

**D9. Assets.** `[data] reference_files` (int, 0 = off) is the reference
dump's file count, without `game_files_exclude` names and the marker
(`dump.ignored`): 485 for BLiNX 2. `default_analysis.json` is excluded.
`doctor` prints `assets: N files (the reference dump has M)`, plus `, K
fewer` or `, K more`. It never adds a problem.

## Risks

- A future known XBE with other section bytes would need its own table.
  `xbr fingerprint --toml` shows the difference. Its sha256 still makes it
  `known` first, whatever the table says.
- The tracker item edits `doctor.py` and `package/__init__.py` too. The edits here
  are a few lines in place, plus the new module.
