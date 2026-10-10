## Context

- **Readers of the pins** (grep of `["commit"]`, `["branch"]` and `[cli]` in
  CLI main dde49a6):
  - `manifest.py` (schema, `_check_values`, `LINE_KEYS`);
  - `toolkit.py` (`clone_toolkit`, `checkout_pin`, `pin_note`);
  - `cli_dir.py` (`doctor_line`, `checkout_pin`);
  - `pins.py` (`head_report`);
  - `doctor.py` (the toolkit row);
  - `scaffold.py` (`GAME_TOML`, `resolve_cli_commit`, `resolve_toolkit_commit`);
  - `wrapper/game.py` (`cli_table`, `at_pin`, `clone`, `find_cli`).

  `bench` reads `[bench] toolkit_branch` and never the pin. `fetch.py`
  handles the llvm-mingw and NSIS downloads, not git pins.
- **The bootstrap is Python, not sh.** `blinx2` is
  `exec python3 blinx2.py`, and `blinx2.cmd` does the same on Windows. All
  pin logic lives in `blinx2.py`, standard library only, Python 3.9+. So
  "nothing beyond POSIX sh and git" holds as "nothing beyond the standard
  library and git", which is the rule the bootstrap already has.
- **Clones the CLI made are marked `.xbr-pin`** and move with the pin. A
  developer's checkout (no mark) is never moved.

## D1. Schema

```toml
[cli]
tag = "v0.2.0"                                     # optional
commit = "<40 hex>"                                # optional with a tag
url = "https://github.com/apexJCL/xboxrecomp-cli.git"

[toolkit]
url = "https://github.com/apexJCL/xboxrecomp.git"  # required
tag = "blinx2-v0.1.0"                              # optional
branch = "blinx2/portability"                      # required without a tag
commit = "<40 hex>"                                # required without a tag
```

- **`[cli]`** needs `tag` or `commit`.
- **`[toolkit]`** needs `tag`, or else `branch` and `commit` (today's rule).
- **`commit`**, when present, is 40 lowercase hex, as today.
- **`tag`** is a plain ref name: `[A-Za-z0-9._/-]`, starting with an
  alphanumeric, with no `..`, no `//`, and no trailing `/`, `.` or `.lock`.
  This is a subset of `git check-ref-format` that rules out a value the shell
  or git would read as an option or a revision expression (`v1^`, `-x`).
- **`[cli] tag`** joins `LINE_KEYS`: the bootstrap reads it with the line
  parser, so it must be a plain one-line string.
- The error names the key: `cli: tag or commit required`, `toolkit.branch:
  required without a tag`, `cli.tag: 'v1^' is not a plain tag name`.

## D2. Tag + commit: the commit is a lock

When both are set, the tag must resolve to the commit. Otherwise:

- every command that would check the pin out refuses (bootstrap clone or
  move, `setup`'s toolkit clone or move, `setup`'s CLI move):
  `toolkit: tag blinx2-v0.2.0 is 1234abcd5678 on <url>, not the pinned commit
  35ed68fc7f3c: the tag moved, or game.toml names the wrong pair`.
  A refused fresh clone leaves nothing behind;
- `pins refresh` reports it as a WARNING line;
- `doctor` prints a `warning:` line (D6).

*Why a lock and not a tag alone:* a tag can be moved or re-pushed, and the
toolkit sets what gen/ and every golden are built from. A lock turns a moved
tag into a loud refusal. It also lets a cached clone run offline with no tag
lookup, and keeps older bootstraps working (they read the commit and skip the
tag line). A tag alone stays valid for a game that prefers it, as the user
asked. `new` writes both; cat uses both.

## D3. Resolving a tag

`gitpin.resolve(d, tag, url, lock)`, and the same steps in the bootstrap:

1. **Local:** `git -C d rev-parse --verify --quiet refs/tags/<tag>^{commit}`.
   `^{commit}` peels an annotated tag to its commit, so an annotated or
   lightweight tag gives the same answer.
2. **Not local:** `git -C d fetch --quiet --no-tags origin
   refs/tags/<tag>:refs/tags/<tag>`, then step 1 again. The fetch never
   `--force`s, so a tag that moved on the remote never overwrites the local
   copy without a word: git refuses ("would clobber existing tag"), and the
   command fails with git's message.
3. **Not found:** `tag <tag> is not on <url>`.
4. **With a lock:** the result must equal it (D2).

Fresh clones: `git clone --no-checkout <url> <tmp>` fetches tags along with
the default branch's history. The clone then resolves as above, checks the
lock, checks the commit out, and writes the mark. Only then is it moved into
place (the bootstrap already clones aside; the toolkit clone now does the
same, so a refused clone leaves nothing behind). Without a tag, the toolkit
clone is `--branch <branch>` and then checks the commit out, as today.

**The mark** (`.xbr-pin`) still holds the commit the clone is at, so marks
written by older bootstraps stay valid.

## D4. Offline and cached checkouts

- **A marked clone at the lock:** nothing to do and no git call beyond
  `rev-parse HEAD`. That covers the bootstrap on every run, `setup`'s move
  check, and doctor.
- **A marked clone, tag only:**
  - the tag is resolved in the clone first (no network);
  - if the clone lacks the tag, it fetches;
  - offline, that is an error naming the tag: `git fetch failed: ...`, plus
    the bootstrap's usual "clone it beside this checkout, or set
    XBOXRECOMP_CLI_DIR".
- **Developer checkouts** (`$XBOXRECOMP_CLI_DIR`, `../xboxrecomp-cli`,
  `$XBOXRECOMP_DIR`, `../xboxrecomp`, or an unmarked `external/` clone):
  - never resolved over the network and never moved;
  - an unmarked `external/xboxrecomp-cli` that isn't at the pin is refused, as
    today. Its pin is the lock, or else its local tag. If the tag isn't
    there, it is refused with "is at X, not the pin <tag>".

## D5. `pins refresh`

`gitpin.remote_tags(url)` runs `git ls-remote --tags <url>`. A `^{}` line
(the peeled commit of an annotated tag) wins over the tag object's own line.

For each of the toolkit and the CLI:

- **Tag pin:** the candidates are the remote tags with the pinned tag's prefix
  followed by a dotted number. The prefix is everything before the trailing
  version number, so `v0.1.0` gives `v`, and `blinx2-v0.1.0` gives
  `blinx2-v`. Versions compare as tuples of ints. Suffixed tags (`v0.2.0-rc1`)
  don't count. Lines:
  - `toolkit: pinned blinx2-v0.1.0 (35ed68fc7f3c) = newest blinx2-v* tag`
  - `cli:     pinned v0.1.0 (dde49a6c2b0c); newest v* tag is v0.2.0
    (abcdef012345) (move the pin in game.toml if you want it)`
  - `cli:     WARNING pinned v0.1.0 is 1234abcd5678 on the remote, not the
    lock dde49a6c2b0c`
  - `cli:     WARNING pinned v0.3.0 is not on <url>`
  - `cli:     pinned v0.1.0; <url>: not reachable`
- **Commit pin:** the branch-head report, as today.

`game.toml` is still never written: moving a pin stays a reviewed edit.

## D6. `doctor`

The `cli:` and `toolkit:` rows name the pin as `v0.2.0 (abcdef012345)`, or
as the commit alone when there's no tag.

- The expected commit is the lock, else the tag in that checkout (offline).
- The notes stay as they are: `(pinned v0.2.0)`, `(differs from the pin …)`,
  and for a developer's checkout `(not the pin …)`.
- If the checkout's own copy of the tag resolves to a commit other than the
  lock, doctor prints
  `warning:    toolkit tag blinx2-v0.1.0 here is X, not the lock Y`.
  This is a warning, not a problem: it doesn't block a package target.
  Fetching refuses on its own (D2).
- Doctor makes no network call. A tag-only pin whose tag isn't in the
  checkout reads `(pin v0.2.0: not in this checkout's tags)`.

## D7. `xbr new`

- **`[cli]`:**
  - **This checkout:** if HEAD carries version tags (`v` followed by a dotted
    number; `git tag --points-at HEAD`), `new` writes the newest one plus the
    commit. A checkout ahead of a tag writes the commit alone: it must not pin
    an older release than the one running.
  - **The installed distribution:** the commit alone (PEP 610 records no
    tag).
  - **The remote:** the newest `v*` tag and its commit, else `main`'s head (as
    today).
  - **`--cli-tag TAG`:** writes that tag. Its commit comes from
    `--cli-commit`, or from the remote, or, offline, it is left out (tag
    alone).
- **`[toolkit]`:** unchanged: `branch` and `commit`. A new game has no fork
  release of its own, and `--toolkit-tag` would be a guess. The docs say how
  to add a tag.

## D8. Bootstrap (`wrapper/game.py`)

- **Parsing:** `cli_table()` reads `tag` as well as `commit` and `url`.
- **The target:** `want = commit or the resolved tag`.
  - `at_pin(d, cli)`:
    - HEAD equals the lock: run;
    - tag only: resolve the tag locally in `d`, and run if HEAD equals it;
    - marked: resolve (fetching the tag if needed), check the lock, check out,
      rewrite the mark;
    - unmarked: refuse.
  - `clone(cli, dest)`: clone aside with `--no-checkout`, resolve the tag
    (when there is one), check the lock, check out, verify HEAD, mark, then
    rename into place.
- **Messages:** they name the tag where there is one (`cloning <url> v0.2.0
  (abcdef012345)`, `the pin moved; checking out v0.2.0`).
- **Errors:** the mismatch error is the D2 text. Every failure stays a
  `NoCli`: no traceback, nothing left in `external/`.
- **Version:** the template stays Python 3.9 (`test_template_is_py39`).

## D9. Rollout and the next CLI tag

- CLI v0.1.0 refuses `tag` (unknown key), so cat pins the new CLI. The branch
  commit is not the commit that lands: CLI main takes a squash. So the
  orchestrator:
  1. squash-merges `feature/tag-pins` into CLI main;
  2. updates cat's `[cli] commit` to that squash sha (the tag stays
     `v0.2.0`);
  3. creates the annotated tag `v0.2.0` on that commit;
  4. pushes the CLI (`main` and `v0.2.0`) before blinx2-recomp.
- Until `v0.2.0` exists, cat's main checkout runs `../xboxrecomp-cli` (a
  developer checkout, used as it is), so local work goes on.
  `doctor` then says `(not the pin v0.2.0 …)` until the CLI's main is at the
  squash commit.
- **The toolkit** pin is `blinx2-v0.1.0` + 35ed68f, which already exist
  publicly.
