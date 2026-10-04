#!/usr/bin/env bash
#
# Run the xboxrecomp pipeline for this game, one stage or all of them.
#
#   scripts/pipeline.sh <stage> [extra args passed to that stage's tool]
#
# Stages, in order (see xboxrecomp/docs/GETTING_STARTED.md, Steps 2-7):
#
#   parse     XBE headers, sections, kernel imports  -> game_files/default_analysis.json
#   disasm    find functions, build xrefs           -> analysis/disasm/
#   funcid    classify CRT / XDK / game functions   -> analysis/func_id/
#   abi       recover calling conventions           -> analysis/abi/
#   ghidra    headless Ghidra analysis, name export  -> analysis/ghidra/  (slow, cached)
#   names     write Ghidra's names into functions.json (seconds; redo after disasm)
#   recomp    lift x86 to C                         -> src/recomp/gen/
#   build     configure + compile the executable    -> build/
#   analyze   parse..abi, then names if a Ghidra export exists
#   all       parse..build
#
# Every intermediate lives in this project, not in the toolkit clone, whose
# tools otherwise default to paths under xboxrecomp/tools/*/output.
#
set -euo pipefail

GAME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The toolkit: $XBOXRECOMP_DIR, else external/xboxrecomp inside this project,
# else a clone next to it.
if [ -z "${XBOXRECOMP_DIR:-}" ]; then
    if [ -d "$GAME_DIR/external/xboxrecomp" ]; then
        XBOXRECOMP_DIR="$GAME_DIR/external/xboxrecomp"
    else
        XBOXRECOMP_DIR="$GAME_DIR/../xboxrecomp"
    fi
fi
TOOLKIT="$(cd "$XBOXRECOMP_DIR" && pwd)"
GAME_NAME="$(basename "$GAME_DIR")"

XBE="$GAME_DIR/game_files/default.xbe"
ANALYSIS_JSON="$GAME_DIR/game_files/default_analysis.json"
OUT="$GAME_DIR/analysis"
GEN="$GAME_DIR/src/recomp/gen"
SPLIT="${SPLIT:-250}"   # functions per generated file; see GETTING_STARTED "Why 250"

PY="$TOOLKIT/.venv/bin/python3"

# Ghidra 12 ships no Jython, so the toolkit's Jython export script runs under
# PyGhidra instead, from a Python 3.13 venv (JPype has no 3.14 wheels yet).
GHIDRA_HOME="${GHIDRA_HOME:-$(brew --prefix ghidra 2>/dev/null)/libexec}"
GHIDRA_PY="$GAME_DIR/.venv-ghidra/bin/python3"
[ -x "$PY" ] || { echo "No venv at $TOOLKIT/.venv -- run tools/macos/setup.sh" >&2; exit 1; }

# xcode-select points at an older Xcode whose ld cannot read the macOS 27 SDK.
# The Command Line Tools toolchain matches it. Override by exporting your own.
if [ "$(uname)" = Darwin ] && [ -z "${DEVELOPER_DIR:-}" ] \
        && [ -d /Library/Developer/CommandLineTools ]; then
    export DEVELOPER_DIR=/Library/Developer/CommandLineTools
fi

step() { echo; echo "== $* =="; }

# The tools are run as `python -m tools.<name>` from the toolkit root.
tool() { (cd "$TOOLKIT" && "$PY" -m "tools.$1" "${@:2}"); }

require() {
    [ -e "$1" ] || { echo "Missing $1 -- run the '$2' stage first." >&2; exit 1; }
}

stage_parse() {
    step "parse"
    require "$XBE" "(dump the disc into game_files/)"
    tool xbe_parser "$XBE" --json "$ANALYSIS_JSON" "$@"
}

# Code outside .text: the XDK library sections. --text-only stays, because the
# XBE also flags ~60 model/motion data sections (DOLBY onwards) executable and
# sweeping those yields phantom functions. See openspec change recomp-coverage.
DISASM_EXTRA_SECTIONS="D3D,D3DX,XGRPH,DSOUND,PSFD_I,PSFD_B,PSFD_P,PSFD00,SRCADV,SRCED,SRCAC,XPP"
# Indirect-call targets measured at runtime: the hand-kept list, plus the
# toolkit's icall_feedback database once one exists (kept as separate files).
#
# The database is the raw cumulative measurement and is never seeded directly:
# it holds targets that are not function starts (uninitialised vtable reads
# landing inside .text), and seeding those split real functions and made Halo
# crash earlier (toolkit docs/technical/indirect-calls.md, "Seed
# icall_seeds.json, not icall_targets.json"). The filtered seed file is
# regenerated from it on every disasm, decoding each target against the XBE.
SEEDS="$GAME_DIR/config/seed_functions.json"
ICALL_DB="${ICALL_DB:-$TOOLKIT/tools/recomp/output/icall_targets.json}"
ICALL_SEEDS="$OUT/icall_seeds.json"

stage_disasm() {
    step "disasm"
    require "$ANALYSIS_JSON" parse
    local seeds=(--seed-functions "$SEEDS")
    if [ -f "$ICALL_DB" ]; then
        mkdir -p "$OUT"
        tool recomp.icall_feedback --db "$ICALL_DB" \
            seeds --out "$ICALL_SEEDS" --xbe "$XBE"
        seeds+=(--seed-functions "$ICALL_SEEDS")
    fi
    tool disasm "$XBE" --analysis-json "$ANALYSIS_JSON" -o "$OUT/disasm" \
        --text-only --extra-sections "$DISASM_EXTRA_SECTIONS" "${seeds[@]}" -v "$@"
}

stage_funcid() {
    step "funcid"
    require "$OUT/disasm/functions.json" disasm
    tool func_id "$XBE" \
        --functions "$OUT/disasm/functions.json" \
        --strings   "$OUT/disasm/strings.json" \
        --xrefs     "$OUT/disasm/xrefs.json" \
        -o "$OUT/func_id" -v "$@"
}

stage_abi() {
    step "abi"
    require "$OUT/func_id" funcid
    tool abi_analysis "$XBE" --disasm-dir "$OUT/disasm" \
        --func-id-dir "$OUT/func_id" --output-dir "$OUT/abi" -v "$@"
}

stage_ghidra() {
    step "ghidra"
    require "$XBE" "(dump the disc into game_files/)"
    [ -x "$GHIDRA_HOME/support/analyzeHeadless" ] \
        || { echo "No Ghidra at $GHIDRA_HOME -- set GHIDRA_HOME." >&2; exit 1; }
    [ -x "$GHIDRA_PY" ] || { echo "No $GHIDRA_PY -- see README (PyGhidra venv)." >&2; exit 1; }

    local g="$OUT/ghidra" src="$TOOLKIT/tools/ghidra_naming"
    mkdir -p "$g/work" "$g/project" "$g/export" "$g/scripts"

    # Same scripts as upstream; only the runtime tag changes.
    cp "$src/ghidra_scripts/SetAnalysisOptions.java" "$g/scripts/"
    sed 's/^# @runtime Jython$/# @runtime PyGhidra/' \
        "$src/ghidra_scripts/ExportXbeNames.py" > "$g/scripts/ExportXbeNames.py"

    "$PY" "$src/extract_for_ghidra.py" "$XBE" --out-dir "$g/work"

    # Flags mirror tools/ghidra_naming/run_ghidra.sh, which only drives the
    # Windows .bat. No -analysisTimeoutPerFile: 0 there means zero seconds.
    "$GHIDRA_PY" "$GHIDRA_HOME/Ghidra/Features/PyGhidra/support/pyghidra_launcher.py" \
        "$GHIDRA_HOME" -H \
        "$g/project" "$GAME_NAME" \
        -import "$g/work/xbe_flat.bin" -overwrite \
        -loader BinaryLoader -loader-baseAddr 0x10000 \
        -processor "x86:LE:32:default" -cspec windows \
        -scriptPath "$g/scripts" \
        -preScript SetAnalysisOptions.java \
        -postScript ExportXbeNames.py "$g/export" nodecompile "$@"
    stage_names
}

stage_names() {
    step "names"
    require "$OUT/ghidra/export/functions.json" ghidra
    require "$OUT/disasm/functions.json" disasm
    "$PY" "$TOOLKIT/tools/ghidra_naming/merge_names.py" \
        --export-dir "$OUT/ghidra/export" --out "$OUT/ghidra/ghidra_names.json" \
        --functions-json "$OUT/disasm/functions.json" --apply "$@"
    # merge_names only reserves ISO C names; a recovered "read" or "write"
    # would replace libc's for the whole executable off Windows.
    "$PY" "$GAME_DIR/scripts/host_reserved_names.py" "$OUT/disasm/functions.json"
}

maybe_names() {
    if [ -e "$OUT/ghidra/export/functions.json" ]; then stage_names; fi
}

stage_recomp() {
    step "recomp"
    # recomp only warns when this is missing, then guesses cdecl for everything.
    require "$OUT/abi/abi_functions.json" abi
    # gen/ is half-written while this runs; bench.sh sync refuses while the
    # marker exists. It's removed only on success, so a failed run stays locked.
    local marker; marker="$(dirname "$GEN")/.gen-regenerating"
    touch "$marker"
    # --exclude-manual: functions src/recomp_manual.c defines by hand (an XDK
    # entry point replaced with host code, say) are declared in gen/, not emitted.
    tool recomp "$XBE" --all --split "$SPLIT" --gen-dir "$GEN" \
        --exclude-manual "$GAME_DIR/src/recomp_manual.c" \
        --game-name "$GAME_NAME" --disasm-dir "$OUT/disasm" \
        --func-id-dir "$OUT/func_id" --abi-dir "$OUT/abi" -o "$OUT/recomp" "$@" \
        || return 1
    rm -f "$marker"
}

stage_build() {
    step "build"
    require "$GEN/recomp_funcs.h" recomp
    # Building while recomp rewrites gen/ compiles half-written files and links
    # stale objects. A failed recomp leaves the marker: re-run recomp to clear it.
    [ ! -e "$(dirname "$GEN")/.gen-regenerating" ] \
        || { echo "gen/ is being regenerated (or the last recomp failed) -- wait, or re-run the 'recomp' stage." >&2; exit 1; }
    cmake -S "$GAME_DIR" -B "$GAME_DIR/build" -DCMAKE_BUILD_TYPE=Release "$@"
    cmake --build "$GAME_DIR/build" --config Release -j "$(sysctl -n hw.ncpu 2>/dev/null || nproc)"
}

stage="${1:-}"
[ $# -gt 0 ] && shift
case "$stage" in
    parse|disasm|funcid|abi|ghidra|names|recomp|build) "stage_$stage" "$@" ;;
    analyze) stage_parse; stage_disasm; stage_funcid; stage_abi; maybe_names ;;
    all)     stage_parse; stage_disasm; stage_funcid; stage_abi; maybe_names
             stage_recomp; stage_build ;;
    *) awk 'NR<3 {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$0"
       [ -z "$stage" ] && exit 0 || exit 2 ;;
esac
