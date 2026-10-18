Branches: CLI `feature/tag-pins` off main dde49a6 (worktree
`wt/cli-tag-pins/xboxrecomp-cli`); cat `feature/tag-pins` off main 147a4cd
(worktree `wt/cli-tag-pins/cat`). CLI commits are authored and committed as
the noreply identity; there are no tracker ids, hosts or private paths in the
CLI. Tests make no network calls: the remotes are local bare repos with
annotated tags, in tmp.

## 1. CLI

- [x] 1.1 `manifest.py`, D1:
  - add `tag` to `[cli]` and `[toolkit]`;
  - make `commit` and `branch` conditional;
  - check the tag name;
  - add `LINE_KEYS` `cli.tag`.

  Tests in `tests/test_manifest.py`: tag alone, tag + commit, neither,
  toolkit without a branch and without a tag, a bad tag, and a tag that is
  not on one plain line.
- [x] 1.2 `gitpin.py`:
  - `local_tag`, `fetch_tag`, `resolve` (D3, D2);
  - `remote_tags`, `split_version`, `newest_like` (D5);
  - `describe(pin)`, `expected(d, pin)` (D6).
- [x] 1.3 `toolkit.py`:
  - `clone_toolkit` clones aside and resolves the tag (D3);
  - `checkout_pin` takes the pin table (D4);
  - `pin_note` names the tag.

  `cli_dir.py` follows.
- [x] 1.4 `pins.py`: `tag_report` and `pin_report` (D5).
- [x] 1.5 `doctor.py`: the toolkit row and the tag-moved warning (D6).
- [x] 1.6 `scaffold.py`: the CLI tag (D7), the `--cli-tag` flag, and the
  `GAME_TOML` tag line.
- [x] 1.7 `wrapper/game.py`, D8. Tests (`tests/test_tag_pins.py`) use real
  git against a bare repo:
  - a clone at a tag;
  - a tag with a lock;
  - a moved tag refused, with nothing left;
  - a stale marked clone moved to a new tag;
  - a cached clone run offline;
  - a tag-only clone without the tag, offline.
- [x] 1.8 Tests for D2 to D7 in `tests/test_tag_pins.py`:
  - resolving an annotated and a lightweight tag;
  - the mismatch refusal;
  - the `clone_toolkit` tag path and its refusal;
  - the refresh lines (newest, equal, moved, missing, unreachable);
  - the doctor rows;
  - the `new` tag cases.
- [x] 1.9 Docs: `docs/manifest.md` ([cli], [toolkit] and the line-parser
  paragraph) and README (how a game finds the CLI, troubleshooting, releases
  and pins). Version 0.2.0.
- [x] 1.10 Gates:
  - `PYTHON_COLORS=0 NO_COLOR=1 uv run pytest tests`;
  - `uv run ruff check . && uv run ruff format --check .`;
  - `bash scripts/audit-public.sh main..HEAD`.

## 2. cat

- [x] 2.1 `game.toml`:
  - `[cli] tag = "v0.2.0"` with the commit set to the CLI branch tip (the
    orchestrator moves it to the squash sha, D9);
  - `[toolkit] tag = "blinx2-v0.1.0"` + 35ed68f, keeping the branch;
  - `blinx2.py` takes the new template.
- [x] 2.2 README and `docs/packaging.md`: the pin wording.
- [x] 2.3 Gates:
  - `uv run pytest scripts`;
  - the ruff checks;
  - `./blinx2 --help` and `./blinx2 doctor` from the worktree, with the CLI
    worktree beside it.

## Done

CLI `feature/tag-pins` 2927770 (review fixes amended in: `--` before
every git url and no url starting with '-', the tag-name check in the
bootstrap, the `git tag -d` hint, `new`'s unreachable and local-only notes,
`clone_toolkit` refusing a full dest); 401 passed, 1 skipped (32 new: 31 in
`tests/test_tag_pins.py`, 1 in `tests/test_scaffold.py`). Two departures
from the list: the manifest cases of 1.1 sit in `tests/test_tag_pins.py`
beside the rest, and D5's `newest_like` is named `newest_with_prefix`.
cat: 27 passed in `scripts`; `./blinx2 doctor` shows
`cli: … @ 29277706ad32 (pinned v0.2.0)`.
