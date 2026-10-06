#!/usr/bin/env bash
#
# The pipeline stages, run through the blinx2 CLI (blinx2.py at the repo
# root), which holds all the logic and also runs on Windows. This wrapper
# keeps the stage names that bench.sh, TASKS.md and the openspec changes use.
#
#   scripts/pipeline.sh <stage> [extra args passed to that stage's tool]
#
#   parse disasm funcid abi ghidra names recomp analyze all
#             -> blinx2 <stage>           (blinx2 <stage> --help)
#   build     -> blinx2 build macos       on macOS; elsewhere blinx2 build,
#                                         which on Linux too is the Windows
#                                         cross-build into build-win/
#   build-win -> blinx2 build windows
#   toolchain -> blinx2 setup --no-toolkit
#
# Without a venv from `blinx2 setup`, build and all use the host's cmake and
# ninja (--system-tools), as this script always did.
#
set -euo pipefail

GAME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$(command -v python3 || command -v python)" \
    || { echo "pipeline.sh: no python3 on PATH" >&2; exit 1; }
CLI=("$PY" "$GAME_DIR/blinx2.py")

system_tools=()
[ -x "$GAME_DIR/.venv/bin/cmake" ] || system_tools=(--system-tools)

stage="${1:-}"
[ $# -gt 0 ] && shift
case "$stage" in
    parse|disasm|funcid|abi|ghidra|names|recomp|analyze)
        exec "${CLI[@]}" "$stage" "$@" ;;
    all)
        exec "${CLI[@]}" all "${system_tools[@]}" "$@" ;;
    build)
        if [ "$(uname)" = Darwin ]; then
            exec "${CLI[@]}" build macos "${system_tools[@]}" "$@"
        fi
        exec "${CLI[@]}" build "${system_tools[@]}" "$@" ;;
    build-win)
        exec "${CLI[@]}" build windows "${system_tools[@]}" "$@" ;;
    toolchain)
        exec "${CLI[@]}" setup --no-toolkit "$@" ;;
    *) awk 'NR<3 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
       [ -z "$stage" ] && exit 0 || exit 2 ;;
esac
