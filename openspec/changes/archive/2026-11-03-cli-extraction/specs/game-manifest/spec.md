## ADDED Requirements

### Requirement: A game is described by one manifest
A game project SHALL carry `game.toml` at its root, read by `xboxrecomp-cli` on every command. The manifest SHALL declare `schema`, `[game]` (`name`, `slug`), `[xbe]` (`path`, `title_id`, optional `sha256` list), `[cli]` (`commit`, optional `url`), `[toolkit]` (`url`, `branch`, `commit`), `[toolchain]` (`llvm_mingw`, `nsis`), `[pipeline]` (`game_name`, `gen`, `out`, `seeds`, `icall_seeds`, `spin_waits`, `exclude_manual`, `split`, `names_hooks`, `ghidra`, `[pipeline.disasm]` `text_only` and `extra_sections`), `[build]` (`exe`, `targets`, `windows_dir`, `macos_dir`, `toolchain_file`, `stock_cmake`, `nonstock_vars`, `icon_var`), `[data]` (`game_files`, `game_files_exclude`, `dir_env`, `windows`, `steamos`, `macos`), `[input]` (`script_env`, `presets`), `[golden]` (`json`, `frames`, `audio`), `[package]` (`app`, `product`, `targets`, `brew`, `dylib_companions`, `content`, `templates`, `icon`) and `[bench]` (`remote_name`, `main_branch`, `toolkit_branch`, `toolkit_tests`, `pacing_scenario`), with the defaults the design names. The CLI SHALL hold no game name, title ID, path or constant of its own: every such value SHALL come from the manifest. An unknown key, a missing required key or a value of the wrong type SHALL stop the command with the key and the reason. Paths SHALL be relative to the game root.

#### Scenario: BLiNX 2 manifest
- **WHEN** the CLI loads cat's `game.toml`
- **THEN** the pipeline, build, packaging and bench values equal the constants `blinx2.py`, `package_lib.py`, `game_icon.py` and `scripts/benchlib` carried at cat 70bf5c8, and every command behaves as it did

#### Scenario: Typo in a key
- **WHEN** `game.toml` has `[pipeline] extra_section = [...]` (no `s`)
- **THEN** every command exits non-zero naming `pipeline.extra_section` as unknown, and nothing runs

#### Scenario: A game without packaging
- **WHEN** `game.toml` has no `[package]` table
- **THEN** `setup`, `doctor`, the pipeline stages, `build` and `bench` work, `package` says the manifest has no `[package]`, and `doctor` lists no packageable target

#### Scenario: Unknown dump
- **WHEN** `xbe.sha256` is non-empty and the dump's hash is not in it
- **THEN** `doctor` and `package` warn "unknown dump" and `package` records `"xbe": "unknown"` in `manifest.json`, the build and the bundle still complete, and `bench golden` (check or record) exits non-zero before any run, naming the dump's hash and the known ones

#### Scenario: Known dumps
- **WHEN** `xbe.sha256` lists the current dump and the old one, and the code in both is identical
- **THEN** either dump passes every check without a warning

### Requirement: Pins run game to CLI to toolkit
A game commit SHALL pin the CLI by commit (`cli.commit`) and name where it is cloned from (`cli.url`, the public `apexJCL/xboxrecomp-cli` for this project's games), and the toolkit by URL, branch and commit (`[toolkit]`); `config/setup-pins.json` SHALL hold only download hashes (llvm-mingw assets for `toolchain.llvm_mingw`, NSIS). `setup` SHALL clone the toolkit, and the wrapper SHALL clone the CLI, into `external/` at the pinned commit when neither is found beside the checkout, marking each clone with `.xbr-pin`; a clone SHALL be checked out by sha, never by branch head. `pins refresh` SHALL rewrite the hashes and print the current heads of the toolkit branch and of the CLI next to the pinned shas, and SHALL NOT write `game.toml`. `doctor` SHALL report the CLI and the toolkit in use with their HEAD and whether each matches its pin. No command SHALL resolve a dependency against the network at run time: Python environments are `uv sync --locked` and `uv run --locked`.

#### Scenario: Fresh clone with the CLI reachable
- **WHEN** `./blinx2 setup` runs in a fresh clone of cat with `cli.url` set and no `../xboxrecomp-cli`
- **THEN** the wrapper clones the CLI into `external/xboxrecomp-cli` at `cli.commit`, `setup` clones the toolkit into `external/xboxrecomp` at `toolkit.commit`, and `doctor` prints both as "(pinned)"

#### Scenario: Pin moved
- **WHEN** `game.toml`'s `cli.commit` changes and `external/xboxrecomp-cli` carries `.xbr-pin` at the old commit
- **THEN** `setup` checks out the new commit, and until then `doctor` prints "differs from the pin"

#### Scenario: Refresh does not edit the manifest
- **WHEN** a maintainer runs `./blinx2 pins refresh`
- **THEN** `config/setup-pins.json` is rewritten, `game.toml` is byte-identical, and the output names the newer toolkit and CLI heads if any

### Requirement: The wrapper is thin and the override is an environment variable
The game SHALL ship `blinx2` (POSIX sh), `blinx2.cmd` and `blinx2.py`, a bootstrap of about 60 lines of standard-library Python 3.9 copied from the CLI's `wrapper/` template, which finds uv, finds the CLI in the order `XBOXRECOMP_CLI_DIR`, `external/xboxrecomp-cli`, `../xboxrecomp-cli`, clones it at the pin when absent, and execs `uv run --project <cli> --locked xbr --game <root> --prog <slug> <args>`. Without uv it SHALL print the install hint for the host's OS and exit non-zero, except that `--help` SHALL print without uv. `XBOXRECOMP_CLI_DIR` SHALL point at a developer's CLI checkout or worktree, which runs from source with no install step. `xbr wrapper --check` SHALL report whether a game's bootstrap matches the template.

#### Scenario: One command unchanged
- **WHEN** a user runs `./blinx2` in a clone of cat with the dump in place
- **THEN** setup, generate, build and package run as before and a bundle appears under `dist/`, and `./blinx2 --help` is byte-identical to cat 70bf5c8's

#### Scenario: Developer override
- **WHEN** `XBOXRECOMP_CLI_DIR=wt/cli/xboxrecomp-cli ./blinx2 doctor` runs
- **THEN** the `cli:` row names that path and its HEAD, and no clone happens

#### Scenario: No uv
- **WHEN** `./blinx2 setup` runs with no uv on `PATH`
- **THEN** the wrapper prints the install command for the OS and exits 1, and `./blinx2 --help` still prints the command list

### Requirement: Byte-identical behaviour through the migration
Each migration phase on cat SHALL be gated on: `./blinx2 --help`, `bench --help` and `package --help` byte-equal to 70bf5c8's; the bench parity record passing with only the documented fixture edits (the `cli:` provenance line in phase A, the prologue assignments in phase B); `src/recomp/gen.key.json` unchanged by the move, so `./blinx2` on a current tree plans `build, package` only; every payload file of `package windows`, `steamos` and `macos` equal by sha256 to the same commit packaged before the move, except `manifest.json`, `SHA256SUMS` and the exe's timestamps; `uv run pytest` and ruff green in both repositories; `blinx2 bench integrate --golden` with the previous verdict; and the fresh-clone cases of the wrapper.

#### Scenario: Payload compare
- **WHEN** `scripts/compare-bundles.py` runs over a bundle made before the move and one made after it from the same commit
- **THEN** it lists only `manifest.json`, `SHA256SUMS` and the executable, and the manifest differs only in `built`, `version` and the added `sources.cli`

#### Scenario: Key stable
- **WHEN** `./blinx2` runs on a tree whose `gen.key.json` was written before the move
- **THEN** the plan is `build, package` and the key file is not rewritten
