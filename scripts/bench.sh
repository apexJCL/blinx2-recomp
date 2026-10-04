#!/usr/bin/env bash
#
# Build and run the Windows x86_64 build of this game under Proton on a remote
# x86_64 Linux host, driven from this machine over SSH.
#
#   scripts/bench.sh <command> [args]
#
# Commands:
#
#   setup     create the build distrobox, install cmake/ninja/umu-launcher,
#             download llvm-mingw                                (once per host)
#   sync      rsync the toolkit (see XBOXRECOMP_DIR) and this project to
#             the host
#             --game-files  also set up game_files/ (your own host only):
#                       the host keeps ONE copy, BENCH_GAME_FILES. A sync
#                       from the tree that owns it copies this machine's
#                       game_files/ into it; any other tree gets a symlink
#                       to it (nothing copied)
#             --game-files=reflink  a btrfs reflink copy instead of the
#                       symlink, for a tree that must not share the files
#   build     configure + compile build-win/ on the host     [extra cmake args]
#             (holds the host's run lock, so no game runs during a build)
#   run       launch build-win/cat_recomp.exe under Proton, log to
#             bench-logs/<timestamp>/ on the host, then pull logs   [game args];
#             fails if any D3D11 flip presented a surface other than the one
#             the walker drew (check_present_mismatch)
#   golden    run the golden-frame scenarios (analysis/golden/golden.json)
#             and compare their frames; non-zero exit on a regression
#             first runs `tests` (below); a test failure fails golden
#             --record  take this run's frames as the new references
#                       (refused after a crash, a present mismatch or a
#                       test failure unless --force is also given). It
#                       records every frame: there is no --only here. To
#                       record one frame, run
#                       scripts/golden.py record --only NAME SCEN=DIR
#                       on a run's pulled frames
#   tests     build and ctest the toolkit's Proton tests (d3d8_hlsl_split,
#             d3d11_backend_smoke, input_map, nv2a_zbuf, apu_irq, kernel_irql_abi), holding the run
#             lock exclusively
#             also fails a run on [CRASH] or, with a limit, an early exit
#   logs      symbolize a run's crash reports, then pull bench-logs/ from the
#             host into ./bench-logs/              [stamp, default: newest run]
#   symbolize name the native addresses in a run's [CRASH] reports, into
#             bench-logs/<stamp>/crash-symbols.txt  [stamp, default: newest run]
#   shell     open an SSH shell in the host's project directory
#   all       sync, build, run
#   integrate sync + build the integration heads into BENCH_DIR (default
#             ~/xbox-recomp); run from the integration checkout (cat main,
#             toolkit posix-host/portability: another branch only warns),
#             clean trees only
#             --golden  then run golden once
#             --dirty   allow uncommitted changes in either tree
#
# Configuration, from the environment or scripts/bench.env (sourced if present,
# never synced or committed):
#
#   BENCH_HOST       ssh target, e.g. user@$HOST               (required)
#   BENCH_DIR        project root on the host          (~/xbox-recomp)
#   BENCH_BOX        distrobox name                    (xbr-build)
#   BENCH_IMAGE      distrobox image                   (fedora:42)
#   LLVM_MINGW_ROOT  llvm-mingw install on the host    ($BENCH_DIR/llvm-mingw)
#   LLVM_MINGW_TAG   llvm-mingw release to install     (20260922)
#   PROTONPATH       Proton for umu-run                (GE-Proton = latest GE)
#   BENCH_PREFIX     Wine prefix on the host           ($BENCH_DIR/prefix)
#   BENCH_GAME_FILES the host's single game_files copy  (~/xbox-recomp/<game>/game_files)
#                    every other tree links to it; it may be read-only
#                    (chmod -R a-w): no run writes there, saves and caches
#                    go to the save dir
#   BENCH_ENV        space-separated VAR=value pairs for the game, e.g.
#                    "RECOMP_AC97_READY=0 WINEDEBUG=+seh";
#                    RECOMP_SAVE_DIR=@run gives the run an empty save dir,
#                    bench-logs/<stamp>/save/ (the golden `story` scenario).
#                    RECOMP_TRACE=/RECOMP_DEBUG= entries add up (comma-joined)
#                    with the ones a scenario pins, rather than replacing them
#   BENCH_TIMEOUT    stop the game with SIGINT after this many seconds
#   BENCH_FRAMES     1: RECOMP_DEBUG=d3d11_dump into bench-logs/<stamp>/frames/ on
#                    the host (every 60th present; not pulled by logs)
#
# run-info.txt records the exe's sha256 and, from build-win/provenance.txt,
# the cat and toolkit commits it was built from and whether either tree was
# dirty at sync time.
#
#   XBOXRECOMP_DIR   local toolkit checkout   (external/xboxrecomp if present,
#                    else ../xboxrecomp)
#
# The host always gets the toolkit next to the project, so CMakeLists.txt finds
# it at ../xboxrecomp there (external/ is not synced):
#
#   $BENCH_DIR/xboxrecomp   toolkit working tree (whatever branch is checked out)
#   $BENCH_DIR/cat          this project; build-win/ and bench-logs/ live here
#
set -euo pipefail

GAME_DIR="${BENCH_GAME_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
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

[ -f "$GAME_DIR/scripts/bench.env" ] && . "$GAME_DIR/scripts/bench.env"

# Host paths keep a literal ~ so the host's shell expands it.
: "${BENCH_DIR:=~/xbox-recomp}"
: "${BENCH_BOX:=xbr-build}"
: "${BENCH_IMAGE:=fedora:42}"
: "${LLVM_MINGW_ROOT:=$BENCH_DIR/llvm-mingw}"
: "${LLVM_MINGW_TAG:=20260922}"
: "${PROTONPATH:=GE-Proton}"
: "${BENCH_PREFIX:=$BENCH_DIR/prefix}"
: "${BENCH_ENV:=}"
: "${BENCH_GAME_FILES:=~/xbox-recomp/$GAME_NAME/game_files}"

REMOTE_GAME="$BENCH_DIR/$GAME_NAME"

# Present while `pipeline.sh recomp` is rewriting gen/.
REGEN_MARKER="$GAME_DIR/src/recomp/.gen-regenerating"

step() { echo; echo "== $* =="; }
die()  { echo "bench: $*" >&2; exit 1; }

need_host() {
    [ -n "${BENCH_HOST:-}" ] || die "set BENCH_HOST (e.g. in scripts/bench.env)"
}

# Run a bash script, read from stdin, on the host / inside its distrobox. The
# script travels on stdin so quoting stays local.
remote() { ssh -o BatchMode=yes "$BENCH_HOST" bash -s; }
in_box() { ssh -o BatchMode=yes "$BENCH_HOST" distrobox enter "$BENCH_BOX" -- bash -s; }
# Same, holding the host's run lock (the one run_game takes) for the whole
# script: a build overlapping a game run once made a golden run INCOMPLETE.
# Shared: builds may overlap each other (no gate reads a build's speed), a
# game run's exclusive lock excludes them all. Says who holds it while it
# waits, and exits 75 if it waited an hour, so cmd_build can say which.
# in_box_locked -x WHAT: exclusive, for scripts that start Proton (cmd_tests).
in_box_locked() {
    local fl=-s what=build
    [ "${1:-}" != -x ] || { fl=-x; what=${2:-tests}; }
    ssh -o BatchMode=yes "$BENCH_HOST" "
        exec 9>>~/.recomp-run.lock
        if ! flock $fl -n 9; then
            h=\$(lslocks -n -o PID,BLOCKER,PATH 2>/dev/null | awk '!h && /recomp-run\\.lock\$/ && NF == 2 {h = \$1} END {print h}' || true)
            echo \"bench: $what waiting for the run lock, held by: \$( [ -n \"\$h\" ] && ps -o pid=,args= -p \"\$h\" | cut -c1-200 || echo '?')\" >&2
            flock $fl -w 3600 -E 75 9 || exit 75
            echo 'bench: $what got the run lock' >&2
        fi
        distrobox enter '$BENCH_BOX' -- bash -s 9>&-"
}

# Prologue for every remote script. Unquoted on purpose: ~ expands on the host.
remote_vars() {
    cat <<EOF
set -euo pipefail
BENCH_DIR=$BENCH_DIR
REMOTE_GAME=$REMOTE_GAME
LLVM_MINGW_ROOT=$LLVM_MINGW_ROOT
BENCH_PREFIX=$BENCH_PREFIX
BENCH_BOX='$BENCH_BOX'
EOF
}

cmd_setup() {
    need_host
    step "setup: distrobox $BENCH_BOX ($BENCH_IMAGE)"
    { remote_vars; cat <<EOF
mkdir -p "\$BENCH_DIR"
if ! distrobox list | awk -F'|' -v box="\$BENCH_BOX" 'NR>1 {gsub(/ /,"",\$2)} \$2 == box {f=1} END {exit !f}'; then
    distrobox create --yes --name "\$BENCH_BOX" --image '$BENCH_IMAGE'
fi
EOF
    } | remote

    step "setup: packages"
    { remote_vars; cat <<'EOF'
sudo dnf install -y cmake ninja-build curl xz tar
EOF
    } | in_box

    # Proton runs from the host, not the box: the host ships umu-run.
    echo 'command -v umu-run >/dev/null || { echo "host has no umu-run" >&2; exit 1; }' | remote

    step "setup: llvm-mingw $LLVM_MINGW_TAG -> $LLVM_MINGW_ROOT"
    { remote_vars; printf 'TAG=%q\n' "$LLVM_MINGW_TAG"; cat <<'EOF'
cc="$LLVM_MINGW_ROOT/bin/x86_64-w64-mingw32-clang"
if [ -x "$cc" ] && [ "$(cat "$LLVM_MINGW_ROOT/.tag" 2>/dev/null)" = "$TAG" ]; then
    echo "already installed: $TAG, $("$cc" --version | sed -n 1p)"
    exit 0
fi
url=$(curl -fsSL "https://api.github.com/repos/mstorsjo/llvm-mingw/releases/tags/$TAG" \
      | grep -o 'https://[^"]*-ucrt-ubuntu-[0-9.]*-x86_64\.tar\.xz' | sed -n 1p)
[ -n "$url" ] || { echo "no llvm-mingw $TAG Linux x86_64 release found" >&2; exit 1; }
# Only ever replace an llvm-mingw install, so a mis-set LLVM_MINGW_ROOT
# cannot wipe anything else.
if [ -e "$LLVM_MINGW_ROOT" ]; then
    case "$LLVM_MINGW_ROOT" in
        */llvm-mingw*) ;;
        *) [ -x "$cc" ] || { echo "refusing to replace $LLVM_MINGW_ROOT: not an llvm-mingw install" >&2; exit 1; } ;;
    esac
    rm -rf "$LLVM_MINGW_ROOT"
fi
echo "fetching $url"
tmp=$(mktemp -d)
curl -fL "$url" -o "$tmp/llvm-mingw.tar.xz"
mkdir -p "$LLVM_MINGW_ROOT"
tar -xJf "$tmp/llvm-mingw.tar.xz" -C "$LLVM_MINGW_ROOT" --strip-components=1
rm -rf "$tmp"
echo "$TAG" > "$LLVM_MINGW_ROOT/.tag"
"$cc" --version | sed -n 1p
EOF
    } | in_box
}

# One line per tree: commit, branch, and whether the working tree differs
# from it (tracked changes or untracked, non-ignored files: rsync sends both).
tree_state() {
    local name=$1 dir=$2 sha branch n
    sha=$(git -C "$dir" rev-parse HEAD 2>/dev/null) || { echo "$name: (not a git checkout: $dir)"; return; }
    branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
    n=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$n" = 0 ]; then
        echo "$name: $sha $branch clean"
    else
        echo "$name: $sha $branch dirty ($n paths)"
    fi
}

# What a sync sent. Written to the host as bench-provenance.txt; a build copies
# it to build-win/provenance.txt, and run-info.txt quotes that copy, so a run
# names the sources its exe was built from.
provenance() {
    echo "synced: $(date -u +%Y-%m-%dT%H:%M:%SZ) from $(hostname -s):$GAME_DIR"
    tree_state "$GAME_NAME" "$GAME_DIR"
    tree_state toolkit "$TOOLKIT"
}

cmd_sync() {
    need_host
    local game_files=0 a
    for a in "$@"; do
        case "$a" in
            --game-files) game_files=link ;;
            --game-files=reflink) game_files=reflink ;;
            *) die "sync: unknown option $a" ;;
        esac
    done

    [ -e "$REGEN_MARKER" ] && die "gen/ is mid-regeneration ($REGEN_MARKER exists); wait for pipeline.sh recomp"

    echo "mkdir -p $REMOTE_GAME $BENCH_DIR/xboxrecomp" | remote

    # Source trees: -a without -t, plus --checksum. A file whose content
    # changed is rewritten and gets the host's current time; an unchanged one
    # is left alone. Preserving this machine's mtimes (-t) could give a
    # changed source a time older than the host's build objects, and ninja
    # then skipped the rebuild (stale build-win/tests objects).
    local src_opts=(-az --no-times --checksum --delete --info=stats1)

    step "sync: xboxrecomp @ $(git -C "$TOOLKIT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') $(git -C "$TOOLKIT" rev-parse --short HEAD 2>/dev/null || true)"
    rsync "${src_opts[@]}" \
        --exclude .git --exclude build/ --exclude 'build-*/' \
        --exclude .venv/ --exclude __pycache__/ --exclude .DS_Store \
        "$TOOLKIT/" "$BENCH_HOST:$BENCH_DIR/xboxrecomp/"

    # --delete leaves excluded paths alone, so the host's build-win/,
    # bench-logs/ and game_files/ survive a sync.
    step "sync: $GAME_NAME"
    rsync "${src_opts[@]}" \
        --exclude .git --exclude build/ --exclude 'build-*/' \
        --exclude /bench-logs --exclude /analysis --exclude /.venv-ghidra \
        --exclude /game_files --exclude /third_party --exclude .claude/ \
        --exclude /external/xboxrecomp \
        --exclude /bench-provenance.txt \
        --exclude src/recomp/.gen-regenerating --exclude scripts/bench.env \
        --exclude .DS_Store --exclude '*.log' \
        "$GAME_DIR/" "$BENCH_HOST:$REMOTE_GAME/"
    provenance | ssh -o BatchMode=yes "$BENCH_HOST" "cat > $REMOTE_GAME/bench-provenance.txt"
    provenance

    [ "$game_files" = 0 ] || sync_game_files "$game_files"
}

# game_files/ on the host: one copy, BENCH_GAME_FILES, shared by every tree.
# The tree that owns it gets this machine's game_files/ rsynced in (made
# writable for the copy if it was read-only, then put back); any other tree
# gets a symlink to it, or with MODE reflink a btrfs reflink copy (no extra
# space until a file changes). A real directory already in a tree's place is
# left alone: it may be the only copy of something.
sync_game_files() {
    local mode=$1 owner
    # Owner: the tree whose own directory holds BENCH_GAME_FILES. Compared by
    # parent directory, since a linked tree's game_files resolves to it too.
    owner=$(ssh -o BatchMode=yes "$BENCH_HOST" "realpath -m ${BENCH_GAME_FILES%/*}; realpath -m $REMOTE_GAME" | uniq | wc -l | tr -d ' ')
    if [ "$owner" = 1 ]; then
        step "sync: game_files (to $BENCH_HOST only) -> $BENCH_GAME_FILES, the host's single copy"
        local ro
        ro=$(ssh -o BatchMode=yes "$BENCH_HOST" "mkdir -p $BENCH_GAME_FILES; [ -w $BENCH_GAME_FILES ] && echo 0 || { chmod -R u+w $BENCH_GAME_FILES; echo 1; }")
        local rc=0
        # Keeps -a's times on purpose: game_files/ is game data, not build
        # input, and the size+mtime quick check avoids re-reading every file
        # on both sides as --checksum would.
        rsync -az --info=stats1 --exclude .DS_Store "$GAME_DIR/game_files/" "$BENCH_HOST:$BENCH_GAME_FILES/" || rc=$?
        [ "$ro" = 0 ] || ssh -o BatchMode=yes "$BENCH_HOST" "chmod -R a-w $BENCH_GAME_FILES"
        return $rc
    fi
    step "sync: game_files -> $mode of $BENCH_GAME_FILES"
    { remote_vars; cat <<EOF
src=$BENCH_GAME_FILES
dst=$REMOTE_GAME/game_files
mode=$mode
EOF
      cat <<'EOF'
[ -f "$src/default.xbe" ] || { echo "sync: $src has no default.xbe; run sync --game-files from the tree that owns it (BENCH_DIR=${src%/*/game_files}) first" >&2; exit 1; }
if [ -L "$dst" ]; then
    rm "$dst"
elif [ -e "$dst" ]; then
    echo "sync: $dst is a real directory; left as is (remove it to share $src)"
    exit 0
fi
if [ "$mode" = reflink ]; then
    cp -a --reflink=always "$src" "$dst"
    chmod -R u+w "$dst"
    echo "sync: $dst is a reflink copy of $src"
else
    ln -s "$src" "$dst"
    echo "sync: $dst -> $src"
fi
EOF
    } | remote
}

cmd_build() {
    local rc
    need_host
    step "build: $REMOTE_GAME/build-win"
    { remote_vars
      # printf '%q ' with no arguments still prints '' (one empty arg), which
      # made every build re-run cmake with an empty argument.
      printf 'EXTRA_ARGS=(%s)\n' "$( [ $# -eq 0 ] || printf '%q ' "$@")"
      cat <<'EOF'
cd "$REMOTE_GAME"
[ -f cmake/llvm-mingw-x86_64.cmake ] || { echo "cmake/llvm-mingw-x86_64.cmake missing -- not synced yet?" >&2; exit 1; }
export PATH="$LLVM_MINGW_ROOT/bin:$PATH"
if [ ! -f build-win/CMakeCache.txt ]; then
    cmake -S . -B build-win -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE=cmake/llvm-mingw-x86_64.cmake \
        -DLLVM_MINGW_ROOT="$LLVM_MINGW_ROOT" \
        -DCMAKE_BUILD_TYPE=Release \
        "${EXTRA_ARGS[@]}"
elif [ ${#EXTRA_ARGS[@]} -gt 0 ]; then
    cmake -B build-win "${EXTRA_ARGS[@]}"
fi
# Wall time of cmake --build alone (not ssh, distrobox or the lock wait),
# with ninja's last line: "no work to do" or the final [N/M] step.
start=$(date +%s.%N)
cmake --build build-win 2>&1 | tee build-win/last-build.log
echo "build: $(awk -v a="$start" -v b="$(date +%s.%N)" 'BEGIN {printf "%.2f", b - a}')s; last line: $(sed -n '$p' build-win/last-build.log | cut -c1-100)"
if [ -f bench-provenance.txt ]; then
    cp bench-provenance.txt build-win/provenance.txt
else
    echo "build: unknown sources (no bench-provenance.txt; synced by an older bench.sh?)" > build-win/provenance.txt
fi
ls -la build-win/*.exe
EOF
    } | in_box_locked || {
        rc=$?
        [ "$rc" = 75 ] && die "build: the run lock was held for an hour; nothing built"
        die "build failed (exit $rc)"
    }
}

# sha256 over src/recomp/gen/* (sorted by name), here or on the host. gen/ is
# gitignored, so only this says the host builds the code generated here.
gen_digest_local() {
    (cd "$GAME_DIR/src/recomp/gen" && shasum -a 256 -- * | LC_ALL=C sort -k2 | shasum -a 256 | cut -d' ' -f1)
}
gen_digest_remote() {
    { remote_vars; cat <<'EOF'
cd "$REMOTE_GAME/src/recomp/gen" && sha256sum -- * | LC_ALL=C sort -k2 | sha256sum | cut -d' ' -f1
EOF
    } | remote
}

# Sync + build the integration heads into BENCH_DIR. Refuses a non-integration
# branch or (without --dirty) a dirty tree, so the host's exe always names
# commits; checks gen/ arrived intact. game_files/ is never sent (sync's
# excludes keep the host's own copy, prefix/, shots/, probe/ and llvm-mingw/
# live outside the synced trees).
cmd_integrate() {
    need_host
    local golden=0 dirty=0 a b
    for a in "$@"; do
        case "$a" in
            --golden) golden=1 ;;
            --dirty)  dirty=1 ;;
            *) die "integrate: unknown option $a" ;;
        esac
    done
    b=$(git -C "$GAME_DIR" rev-parse --abbrev-ref HEAD)
    [ "$b" = main ] || die "integrate: $GAME_DIR is on $b, not main (run from the integration checkout)"
    b=$(git -C "$TOOLKIT" rev-parse --abbrev-ref HEAD)
    [ "$b" = posix-host/portability ] \
        || echo "integrate: WARNING $TOOLKIT is on $b, not posix-host/portability (the branch this project is tested with)" >&2
    if [ "$dirty" = 0 ]; then
        [ -z "$(git -C "$GAME_DIR" status --porcelain)" ] || die "integrate: $GAME_DIR is dirty (--dirty to sync anyway)"
        [ -z "$(git -C "$TOOLKIT" status --porcelain)" ] || die "integrate: $TOOLKIT is dirty (--dirty to sync anyway)"
    fi
    [ -n "$(ls "$GAME_DIR/src/recomp/gen" 2>/dev/null)" ] || die "integrate: no src/recomp/gen here (run pipeline.sh recomp first)"

    cmd_sync
    step "integrate: gen/ check"
    local lg rg
    lg=$(gen_digest_local)
    rg=$(gen_digest_remote)
    [ "$lg" = "$rg" ] || die "integrate: host gen/ differs from local ($rg vs $lg)"
    echo "gen: $(ls "$GAME_DIR/src/recomp/gen" | wc -l | tr -d ' ') files, sha256 $lg (host matches)"

    cmd_build
    step "integrate: built $REMOTE_GAME/build-win/cat_recomp.exe"
    { remote_vars; echo 'cd "$REMOTE_GAME"; sha256sum build-win/cat_recomp.exe; cat build-win/provenance.txt'; } | remote
    # Integration runs see no host pad or keyboard and fail on a bad script,
    # as golden.json's env pins for golden (a pad left on the bench is inert).
    BENCH_ENV="${BENCH_ENV:+$BENCH_ENV }RECOMP_HOST_PAD=0 RECOMP_KEYBOARD=0 RECOMP_INPUT_STRICT=1"
    [ "$golden" = 0 ] || cmd_golden
}

# Launch the game on the host and pull its logs; RUN_STAMP names the run.
run_game() {
    need_host
    local stamp; stamp=$(date +%Y%m%d-%H%M%S)
    RUN_STAMP=$stamp
    step "run: under $PROTONPATH -> bench-logs/$stamp"
    { remote_vars
      printf 'STAMP=%q\nPROTONPATH=%q\nGAME_ARGS=(%s)\nGAME_ENV=(%s)\nTIMEOUT=%q\nFRAMES=%q\n' \
          "$stamp" "$PROTONPATH" "$(printf '%q ' "$@")" "$BENCH_ENV" \
          "${BENCH_TIMEOUT:-}" "${BENCH_FRAMES:-0}"
      cat <<'EOF'
cd "$REMOTE_GAME"
[ -f build-win/cat_recomp.exe ] || { echo "no build-win/cat_recomp.exe -- run build first" >&2; exit 1; }
[ -f game_files/default.xbe ]   || { echo "no game_files/ in this tree -- run: sync --game-files" >&2; exit 1; }

# SSH has no display; borrow the logged-in desktop session's, which KDE and
# GNOME import into the systemd user environment.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
eval "$(systemctl --user show-environment 2>/dev/null \
        | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XAUTHORITY)=' | sed 's/^/export /')" || true
export DISPLAY="${DISPLAY:-:0}"
[ -n "${WAYLAND_DISPLAY:-}" ] || echo "warning: no desktop session found; the window may not open" >&2

LOG="bench-logs/$STAMP"
mkdir -p "$LOG" "$BENCH_PREFIX"
# Proton drops the game's stdout/stderr (GUI or console subsystem alike), so
# the game writes them to $RECOMP_STDIO_LOG itself; console.log only holds
# umu/Proton's own output.
export RECOMP_STDIO_LOG="$PWD/$LOG/game-stdio.log"

command -v umu-run >/dev/null || { echo "host has no umu-run" >&2; exit 1; }

# One game at a time on this host: every agent's runs take the same lock, so
# flips/s are not skewed by an overlapping run. Held on fd 9 until this
# script ends; the game itself does not inherit it (9>&- below).
LOCK="$HOME/.recomp-run.lock"
exec 9>>"$LOCK"
waited=0
if ! flock -n 9; then
    # The holder is the lock's one entry with no BLOCKER; the file's text
    # names only the last bench.sh run (a bare `flock FILE cmd` writes none).
    # awk reads to the end (no exit): under pipefail an early exit can
    # SIGPIPE lslocks, and set -e would then end this script silently.
    holder=$(lslocks -n -o PID,BLOCKER,PATH 2>/dev/null | awk '!h && /recomp-run\.lock$/ && NF == 2 {h = $1} END {print h}' || true)
    echo "bench: waiting for the run lock $LOCK, held by: $( [ -n "$holder" ] && ps -o pid=,args= -p "$holder" | cut -c1-200 || echo '?')"
    echo "bench:   (last bench.sh run to take it: $(cat "$LOCK" 2>/dev/null || echo none))"
    t0=$(date +%s)
    # Bounded: a wedged holder (a hung game run with no limit) fails every
    # waiter visibly instead of queueing them behind one line forever.
    flock -w 3600 9 || { echo "bench: FAIL the run lock $LOCK was held for an hour by: ${holder:-?}" >&2; exit 1; }
    waited=$(( $(date +%s) - t0 ))
    echo "bench: got the run lock after ${waited}s"
fi
echo "$(date -Is) $REMOTE_GAME/$LOG (pid $$)" > "$LOCK"
# Only under the lock: a run from this same checkout may be writing it.
rm -f xbox_kernel.log

export WINEPREFIX="$BENCH_PREFIX" GAMEID=umu-default PROTONPATH
export PROTON_LOG=1 PROTON_LOG_DIR="$PWD/$LOG"
# RECOMP_TRACE and RECOMP_DEBUG are lists: a scenario's pins and BENCH_ENV
# each add their keys (docs/env.md) instead of the last one winning. Start
# from empty so a list left in the calling shell does not leak in.
unset RECOMP_TRACE RECOMP_DEBUG
for kv in ${GAME_ENV[@]+"${GAME_ENV[@]}"}; do
    case "$kv" in
        RECOMP_TRACE=*|RECOMP_DEBUG=*)
            k=${kv%%=*}; cur=${!k:-}
            export "$k=${cur:+$cur,}${kv#*=}" ;;
        *) export "$kv" ;;
    esac
done
# RECOMP_SAVE_DIR=@run: the title's UDATA/TDATA go to a fresh, empty save/
# in this run's log dir (a Z: path for Wine), so every story run starts with
# no save game. Nothing outside $LOG is created or deleted.
if [ "${RECOMP_SAVE_DIR:-}" = @run ]; then
    mkdir -p "$LOG/save"
    export RECOMP_SAVE_DIR="Z:$PWD/$LOG/save"
    for i in "${!GAME_ENV[@]}"; do
        [ "${GAME_ENV[$i]}" != RECOMP_SAVE_DIR=@run ] || GAME_ENV[$i]="RECOMP_SAVE_DIR=$RECOMP_SAVE_DIR"
    done
fi
if [ "$FRAMES" = 1 ]; then
    # Wine sees the host's / as Z:.
    mkdir -p "$LOG/frames"
    export RECOMP_DEBUG="${RECOMP_DEBUG:+$RECOMP_DEBUG,}d3d11_dump=Z:$PWD/$LOG/frames/"
    GAME_ENV+=("RECOMP_DEBUG=d3d11_dump=Z:$PWD/$LOG/frames/")
fi

{
    echo "host:   $(hostname)  $(date -Is)"
    echo "proton: $PROTONPATH  prefix: $WINEPREFIX"
    echo "env:    ${GAME_ENV[*]:-(none)}"
    echo "args:   ${GAME_ARGS[*]:-(none)}"
    echo "limit:  ${TIMEOUT:-none}${TIMEOUT:+ s (SIGINT)}"
    echo "lock:   $LOCK, waited ${waited}s"
    sha256sum build-win/cat_recomp.exe
    if [ -f build-win/provenance.txt ]; then
        sed 's/^/built:  /' build-win/provenance.txt
    else
        echo "built:  unknown sources (build-win/provenance.txt missing)"
    fi
} > "$LOG/run-info.txt"

# game_files/ is found relative to the working directory: run from here
# (umu-run keeps it). stdin is /dev/null: this script itself arrives on stdin,
# and anything reading it would swallow the lines below.
# With a limit: SIGINT, then SIGKILL 10 s later if umu-run is still up. The
# game's output goes to the file, not through a pipe, so a Wine process that
# outlives umu-run cannot hold the run open; tail shows it live meanwhile.
LIMIT=()
[ -n "$TIMEOUT" ] && LIMIT=(timeout -k 10 -s INT "$TIMEOUT")

# This run's processes, whatever they are called: everything umu-run starts
# (pressure-vessel, Proton, wineserver, the game) inherits RECOMP_BENCH_RUN,
# which only this run's game command is given. No cwd or path assumption
# (the container's mount layout), and no tool that merely names the exe
# (llvm-symbolizer from a concurrent symbolize) matches. The ps pipeline is
# || true: a pid that exits between pgrep and ps must not end this script
# under pipefail + errexit.
survivors() {
    local p
    for p in $(pgrep -u "$(id -u)" .); do
        [ "$p" != $$ ] || continue
        grep -qxzF "RECOMP_BENCH_RUN=$STAMP" "/proc/$p/environ" 2>/dev/null || continue
        ps -o pid=,args= -p "$p" 2>/dev/null | cut -c1-300 || true
    done
}
loadavg() { cut -d' ' -f1-3 /proc/loadavg; }
# CPU pressure (PSI): microseconds during which some runnable task waited
# for a cpu. Empty where the kernel has PSI off.
psi_cpu() { sed -n 's/^some .*total=\([0-9]*\).*/\1/p' /proc/pressure/cpu 2>/dev/null || true; }
load_start=$(loadavg)
psi_start=$(psi_cpu); t_start=$(date +%s.%N)

set +e
: > "$LOG/console.log"
RECOMP_BENCH_RUN="$STAMP" ${LIMIT[@]+"${LIMIT[@]}"} umu-run "$PWD/build-win/cat_recomp.exe" ${GAME_ARGS[@]+"${GAME_ARGS[@]}"} </dev/null >"$LOG/console.log" 2>&1 9>&- &
pid=$!
tail -n +1 -f --pid="$pid" "$LOG/console.log" 9>&- &
tailpid=$!
# Once, 10 s in: what the sweep below would see. An empty list while
# umu-run is up means the sweep is blind (the tag did not propagate).
(
    sleep 10
    kill -0 "$pid" 2>/dev/null || exit 0
    procs=$(survivors)
    echo "procs:  $(printf '%s' "$procs" | grep -c . || true) tagged RECOMP_BENCH_RUN=$STAMP at +10 s"
    printf '%s\n' "$procs" | sed '/^$/d; s/^/procs:    /'
) >> "$LOG/run-info.txt" 9>&- &
procpid=$!
wait "$pid"
rc=$?
psi_end=$(psi_cpu); t_end=$(date +%s.%N)
sleep 1; kill "$tailpid" 2>/dev/null; wait "$tailpid" 2>/dev/null
wait "$procpid" 2>/dev/null
set -e
echo "$rc" > "$LOG/exit-code"

# For check_run_end: the guest paces itself at 30 Hz, so a clean run's flip
# count is pinned and a low one means a slow run. busy says whether the game
# was starved of cpu, measured, not guessed from who else is running (an
# idle-ish xemu on 16 cpus is not contention): busy if the PSI cpu stall
# share over the run is 5%+. Where PSI is off: a 1-min load at the end (the
# game's own 3-4 cores included) of nproc-2+, or at the start of nproc/2+.
# top and hog stay as attribution only. hog: the first process outside the
# game's stack at 50%+ of a cpu (ps pcpu is a lifetime average; the 2 s
# minimum age skips this script's own ps and sed).
ncpu=$(nproc)
top=$(ps -eo pcpu=,etimes=,args= --sort=-pcpu | sed -n '1,8p' | cut -c1-160)
hog=$(awk '$2 >= 2 && $1 >= 50 && $0 !~ /cat_recomp|wine|[Pp]roton|pressure-vessel|pv-adverb|srt-bwrap|umu|steam/ {
           if (!n++) { $2 = ""; print } }' <<<"$top")
load_end=$(loadavg)
stall=
if [ -n "$psi_start" ] && [ -n "$psi_end" ]; then
    stall=$(awk -v a="$psi_start" -v b="$psi_end" -v t0="$t_start" -v t1="$t_end" \
        'BEGIN {w = t1 - t0; printf "%.1f", (w > 0 ? (b - a) / 1e6 / w * 100 : 0)}') || stall=
fi
why=()
if [ -n "$stall" ]; then
    awk -v x="$stall" 'BEGIN {exit !(x >= 5)}' && why+=("cpu stall $stall% of the run")
else
    awk -v l="${load_end%% *}" -v n="$ncpu" 'BEGIN {exit !(l >= n - 2)}' && why+=("load $load_end at end")
    awk -v l="${load_start%% *}" -v n="$ncpu" 'BEGIN {exit !(l >= n / 2)}' && why+=("load $load_start at start")
fi
busy=no
if [ "${#why[@]}" != 0 ]; then
    busy="yes ($(IFS=';'; echo "${why[*]}"))"
    [ -z "$hog" ] || busy="$busy; top non-game:$hog"
fi
{
    if [ -f "$LOG/game-stdio.log" ]; then
        echo "flips:  $(grep -c '^\[D3D11\] flip' "$LOG/game-stdio.log" || true)"
    else
        echo "flips:  ? (no game-stdio.log)"
    fi
    echo "load:   $load_start at start, $load_end at end ($ncpu cpus)"
    if [ -n "$stall" ]; then
        echo "cpu-stall: $stall% (PSI cpu some over the run; busy at 5%)"
    else
        echo "cpu-stall: ? (PSI off; busy by load: end >= $((ncpu - 2)) or start >= $((ncpu / 2)))"
    fi
    echo "busy:   $busy"
    [ -z "$hog" ] || echo "hog:   $hog"
    sed -n '1,4p' <<<"$top" | sed 's/^ */top:    /'
} >> "$LOG/run-info.txt"

# Anything of this run still alive? Proton's pressure-vessel wrapper takes a
# few seconds to tear down after umu-run returns, so give it 20 s before
# calling anything a survivor.
for _ in $(seq 20); do [ -n "$(survivors)" ] || break; sleep 1; done
if [ -n "$(survivors)" ]; then
    # $LOG/survived: what outlived umu-run, and whether the sweep cleared it.
    # check_run_end fails the run only on "still alive"; a survivor that
    # was killed is a warning (the display is clean for the next run).
    {
        echo "survived umu-run exit $rc (after 20 s grace):"
        survivors
    } > "$LOG/survived"
    echo "!!! bench: the game outlived umu-run (exit $rc); killing it:" >&2
    cat "$LOG/survived" >&2
    ws=$(ls -d "$HOME"/.local/share/Steam/compatibilitytools.d/*/files/bin/wineserver 2>/dev/null | tail -1)
    [ -n "$ws" ] && WINEPREFIX="$WINEPREFIX" "$ws" -k || true
    sleep 2
    survivors | awk '{print $1}' | xargs -r kill -9 2>/dev/null || true
    sleep 1
    left=$(survivors)
    if [ -n "$left" ]; then
        { echo "still alive after wineserver -k and kill -9:"; echo "$left"; } >> "$LOG/survived"
        echo "!!! bench: still alive after wineserver -k and kill -9:" >&2
        echo "$left" >&2
    else
        echo "killed: none left after wineserver -k and kill -9" >> "$LOG/survived"
    fi
fi
[ -f xbox_kernel.log ] && cp xbox_kernel.log "$LOG/"
echo "exit code $rc; logs in $REMOTE_GAME/$LOG"
EOF
    } | remote || true
    cmd_logs "$stamp"
    echo "local: $GAME_DIR/bench-logs/$stamp"
}

# Fail a run whose flips did not show the surface the walker picked:
# `[D3D11] flip N ... present X walker Y` with X != Y (X is 0 when nothing was
# presented). Since the walker picks the present surface (toolkit Q10), X != Y
# means D3D11 had no render target for the walker's pick, which can happen on
# the first flips and on an eviction from the 8-slot RT pool. (Before Q10 the
# present surface came from the present_target() latch, which could hold a
# stale surface, so this check also caught a wrong latch.) A log
# without those lines (another backend, or RECOMP_TRACE without flip) passes with
# a note.
check_present_mismatch() {
    local log=$1 total bad
    [ -f "$log" ] || { echo "present: no log $log" >&2; return 1; }
    local re='^\[D3D11\] flip .* present 0x[0-9A-Fa-f]+ walker 0x[0-9A-Fa-f]+'
    total=$(grep -cE "$re" "$log" || true)
    if [ "$total" = 0 ]; then
        echo "present: no [D3D11] flip lines in $log (not checked)"
        return 0
    fi
    # The regex goes in through the environment: awk -v would eat its \[.
    bad=$(RE="$re" awk '$0 ~ ENVIRON["RE"] {
                  p = w = ""
                  for (i = 1; i < NF; i++) {
                      if ($i == "present") p = $(i + 1)
                      if ($i == "walker")  w = $(i + 1)
                  }
                  if (p != w) { n++; if (n <= 5) first = first " " $3 "(" p "/" w ")" }
               }
               END { printf "%d%s", n, first }' "$log")
    if [ "${bad%% *}" = 0 ]; then
        echo "present: 0/$total flips mismatched"
        return 0
    fi
    echo "present: FAIL ${bad%% *}/$total flips present a surface the walker did not draw; first: ${bad#* }"
    return 1
}

# Fail a run that crashed or ended before its limit. [CRASH] is the toolkit's
# fault report. With BENCH_TIMEOUT the only good end is timeout's 124 (the
# limit hit and SIGINT stopped it); 137 means it took SIGKILL. Without a limit
# the exit code is reported only: a run closed by hand exits 1 today.
# With MIN_FLIPS (golden.json's per-scenario floor) a run that flipped fewer
# times is INCONCLUSIVE (return 3) when run-info says the host was busy, and
# a FAIL (a perf regression) when it was idle: wall-time inputs land on other
# presents in a slow run, so its frames prove nothing either way.
check_run_end() {
    local log=$1 min_flips=${2:-} rc limit crash flips busy
    crash=$(grep -m1 '^\[CRASH\]' "$log/game-stdio.log" 2>/dev/null || true)
    if [ -n "$crash" ]; then
        echo "end: FAIL crashed: $crash"
        return 1
    fi
    rc=$(cat "$log/exit-code" 2>/dev/null || true)
    [ -n "$rc" ] || { echo "end: FAIL no exit-code in $log (host script died?)"; return 1; }
    limit=$(awk '/^limit: / && $2 != "none" {print $2}' "$log/run-info.txt" 2>/dev/null || true)
    if [ -f "$log/survived" ]; then
        if grep -q '^still alive' "$log/survived"; then
            echo "end: FAIL the game outlived umu-run and survived wineserver -k and kill -9; see $log/survived"
            return 1
        fi
        if ! grep -q '^killed:' "$log/survived"; then
            echo "end: FAIL the survivor sweep did not finish (host script died in it?); see $log/survived"
            return 1
        fi
        echo "end: warning: the game outlived umu-run and was killed; see $log/survived"
    fi
    if [ -z "$limit" ]; then
        echo "end: exit $rc (no limit set; not checked)"
        return 0
    fi
    case "$rc" in
        124) echo "end: ran to the ${limit} s limit" ;;
        137) echo "end: FAIL ignored SIGINT at the ${limit} s limit; SIGKILLed"; return 1 ;;
        *)   echo "end: FAIL exit $rc before the ${limit} s limit"; return 1 ;;
    esac
    [ -n "$min_flips" ] || return 0
    flips=$(awk '/^flips: / {print $2}' "$log/run-info.txt" 2>/dev/null || true)
    busy=$(sed -n 's/^busy: *//p' "$log/run-info.txt" 2>/dev/null || true)
    if [ "$flips" = "?" ]; then
        echo "end: FAIL no game-stdio.log: the game wrote no log, so no flip count"
        return 1
    fi
    if [ -z "$flips" ]; then
        echo "end: FAIL no flips: line in run-info (host script died after the run?)"
        return 1
    fi
    local rate; rate=$(awk -v f="$flips" -v l="$limit" 'BEGIN {printf "%.1f", f / l}')
    if [ "$flips" -ge "$min_flips" ]; then
        echo "end: $flips flips ($rate/s; floor $min_flips)"
        return 0
    fi
    local load; load=$(sed -n 's/^load: *//p' "$log/run-info.txt")
    case "$busy" in
        yes*) echo "end: INCONCLUSIVE $flips flips under the floor $min_flips ($rate/s): host busy, $busy; load $load"
              return 3 ;;
        *)    echo "end: FAIL $flips flips under the floor $min_flips ($rate/s) on an idle host: perf regression? load $load"
              return 1 ;;
    esac
}

cmd_run() {
    local rc=0 log
    run_game "$@"
    log="$GAME_DIR/bench-logs/$RUN_STAMP"
    check_run_end "$log" || rc=1
    check_present_mismatch "$log/game-stdio.log" || rc=1
    return $rc
}

# Toolkit tests that need Proton, because they exercise the Windows build's
# D3D11, input and kernel paths and can only run under Wine (toolkit
# posix-host/portability 5564c43+): configure build-win with the toolkit's
# proton_run.sh as the cross-compiling emulator, build the two test targets,
# and ctest them, holding the run lock exclusively (they start Proton like a
# game run). WINEPREFIX is the bench prefix; PROTON_RUN_LOCK is unset, since
# this script already holds the lock and proton_run.sh would wait on it.
# Non-zero on any failure.
cmd_tests() {
    need_host
    step "tests: d3d8_hlsl_split, d3d11_backend_smoke, input_map, nv2a_zbuf, apu_irq, kernel_irql_abi under Proton"
    local rc=0
    { remote_vars
      cat <<'EOF'
cd "$REMOTE_GAME"
export PATH="$LLVM_MINGW_ROOT/bin:$PATH"
emu=$(cd ../xboxrecomp 2>/dev/null && pwd -P || true)/tests/proton_run.sh
[ -x "$emu" ] || { echo "tests: $emu missing (toolkit older than 5564c43?)" >&2; exit 1; }
[ -f build-win/CMakeCache.txt ] || { echo "tests: no build-win (run bench.sh build first)" >&2; exit 1; }
cmake -B build-win -DCMAKE_CROSSCOMPILING_EMULATOR="$emu" >/dev/null
cmake --build build-win --target d3d8_hlsl_split d3d11_backend_smoke input_map_test
# tests/nv2a_zbuf, apu_irq and kernel_irql_abi are projects of their own
# (not in the game build): configure each beside build-win with the same
# toolchain.
standalone="nv2a_zbuf apu_irq kernel_irql_abi"
for t in $standalone; do
    src=../xboxrecomp/tests/$t
    [ -f "$src/CMakeLists.txt" ] || { echo "tests: $src missing (toolkit too old?)" >&2; exit 1; }
    cmake -S "$src" -B "build-win/tests/$t" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$PWD/cmake/llvm-mingw-x86_64.cmake" \
        -DLLVM_MINGW_ROOT="$LLVM_MINGW_ROOT" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CROSSCOMPILING_EMULATOR="$emu" >/dev/null
    cmake --build "build-win/tests/$t"
done
unset PROTON_RUN_LOCK
export WINEPREFIX="$BENCH_PREFIX"
fail=0
for d in src/d3d/d3d8_hlsl_split src/d3d/d3d11_backend_smoke src/input/input_map; do
    t=${d##*/}
    if ctest --test-dir "build-win/xboxrecomp/$d" --output-on-failure --no-tests=error; then
        echo "tests: $t pass"
    else
        echo "tests: FAIL $t"; fail=1
    fi
done
for t in $standalone; do
    if ctest --test-dir "build-win/tests/$t" --output-on-failure --no-tests=error; then
        echo "tests: $t pass"
    else
        echo "tests: FAIL $t"; fail=1
    fi
done
exit $fail
EOF
    } | in_box_locked -x tests || rc=$?
    case "$rc" in
        0)  echo "tests: pass" ;;
        75) echo "tests: FAIL the run lock was held for an hour; nothing run" ;;
        *)  echo "tests: FAIL (exit $rc)" ;;
    esac
    return $rc
}

# Golden frames: run each scenario in analysis/golden/golden.json with frame
# dumps on, pull the frames it names, and compare them (scripts/golden.py).
# Exits non-zero on a regression, a missing frame, or a present mismatch.
#   golden            check against the recorded references
#   golden --record   record the references from this run instead
cmd_golden() {
    need_host
    local mode=check force=0 a scen secs minf env prc=0 erc=0 grc=0 inc=0 e dirs=() idx
    for a in "$@"; do
        case "$a" in
            --record) mode=record ;;
            --force)  force=1 ;;
            *) die "golden: unknown option $a" ;;
        esac
    done
    local plan; plan=$(python3 "$GAME_DIR/scripts/golden.py" plan) || die "golden: no plan"
    # Missing reference PNGs (gitignored: they are game frames) are named
    # now, not after the runs: a check without them can only FAIL, so it
    # stops here; --record makes them, so there it only warns.
    if [ "$mode" = record ]; then
        python3 "$GAME_DIR/scripts/golden.py" refs || true
    else
        python3 "$GAME_DIR/scripts/golden.py" refs || die "golden: reference PNGs missing (see above)"
    fi
    local trc=0
    cmd_tests || trc=1
    while IFS=$'\t' read -r -u 3 scen secs minf env; do
        step "golden: $scen (${secs}s)"
        # The scenario's env goes last so it wins over BENCH_ENV: the
        # references are D3D11 ones whatever the caller exported.
        # The flips around each frame (golden.py dumpat) are dumped too, as
        # flip_NNNNN.bmp, so an anchored frame is checked at the same distance
        # from its event as the reference, not at a fixed present.
        local dumpat; dumpat=$(python3 "$GAME_DIR/scripts/golden.py" dumpat "$scen") ||
            die "golden: no dumpat list for $scen"
        BENCH_ENV="${BENCH_ENV:+$BENCH_ENV }$env RECOMP_DEBUG=fb_dump_at=$dumpat" BENCH_TIMEOUT=$secs BENCH_FRAMES=1 run_game
        local log="$GAME_DIR/bench-logs/$RUN_STAMP"
        [ "$minf" != 0 ] || minf=
        e=0; check_run_end "$log" "$minf" || e=$?
        case "$e" in 0) ;; 3) inc=1 ;; *) erc=1 ;; esac
        check_present_mismatch "$log/game-stdio.log" || prc=1
        mkdir -p "$log/frames"
        for idx in $(python3 "$GAME_DIR/scripts/golden.py" frames "$scen"); do
            rsync -az "$BENCH_HOST:$REMOTE_GAME/bench-logs/$RUN_STAMP/frames/frame_$idx.bmp" "$log/frames/" ||
                echo "golden: $scen frame_$idx.bmp was not dumped"
        done
        # Only the flips the check reads (each target +-2, from the run's
        # anchors), not all of dumpat's window (150-230 MB a scenario).
        python3 "$GAME_DIR/scripts/golden.py" pulls "$scen" "$log/game-stdio.log" \
            > "$log/frames/pulls.txt" || : > "$log/frames/pulls.txt"
        # A directory source with --files-from does not get its leading ~
        # expanded on the host; the remote rsync starts in $HOME anyway.
        rsync -az --files-from="$log/frames/pulls.txt" \
            "$BENCH_HOST:${REMOTE_GAME#\~/}/bench-logs/$RUN_STAMP/frames/" "$log/frames/" ||
            echo "golden: $scen: some flip dumps were not pulled (the check says INCOMPLETE if it needed them)"
        dirs+=("$scen=$log/frames")
    done 3<<<"$plan"
    step "golden: $mode"
    if [ "$mode" = record ] && [ "$force" = 0 ] && { [ "$prc" != 0 ] || [ "$erc" != 0 ] || [ "$inc" != 0 ] || [ "$trc" != 0 ]; }; then
        echo "golden: not recording: a toolkit test failed, or a run crashed, ended early, ran slow or presented surfaces the walker did not draw (--force to record anyway)"
        return 1
    fi
    python3 "$GAME_DIR/scripts/golden.py" "$mode" "${dirs[@]}" || grc=1
    [ "$erc" = 0 ] || echo "golden: FAIL: a run crashed or ended early (see end: above)"
    [ "$prc" = 0 ] || echo "golden: FAIL: a run presented surfaces the walker did not draw (see present: above)"
    [ "$trc" = 0 ] || echo "golden: FAIL: a toolkit test failed (see tests: above)"
    [ "$mode" = record ] && [ "$force" = 1 ] && [ "$prc$erc$inc$trc" != 0000 ] &&
        echo "golden: WARNING: recorded with --force from a bad run; re-record after a clean one"
    # A hard failure wins; then a slow run on a busy host (exit 3: the
    # frames compare above is printed but proves nothing); then the compare.
    [ "$prc" = 0 ] && [ "$erc" = 0 ] && [ "$trc" = 0 ] || return 1
    if [ "$inc" != 0 ]; then
        echo "golden: INCONCLUSIVE: a run was slow on a busy host (see end: above); run again on a quiet host"
        return 3
    fi
    [ "$grc" = 0 ]
}

# Name the native addresses in a run's [CRASH] reports, into
# bench-logs/<stamp>/crash-symbols.txt. Wine's dbghelp names nothing from the
# lld PDB, so this is done offline on the host with llvm-mingw's
# llvm-symbolizer: each address in the exe's loaded range is rebased from
# where Wine put it to the link-time ImageBase and looked up in the PDB.
cmd_symbolize() {
    need_host
    { remote_vars; printf 'STAMP=%q\n' "${1:-}"; cat <<'EOF'
cd "$REMOTE_GAME"
[ -n "$STAMP" ] || STAMP=$(ls -1 bench-logs 2>/dev/null | sort | tail -1)
LOG="bench-logs/$STAMP"
[ -n "$STAMP" ] && [ -d "$LOG" ] || { echo "symbolize: no run $LOG" >&2; exit 1; }
stdio="$LOG/game-stdio.log" out="$LOG/crash-symbols.txt"
grep -q '^\[CRASH\]' "$stdio" 2>/dev/null || { echo "symbolize: no [CRASH] in $LOG"; exit 0; }

# The PDB has to be the one built with the exe that ran.
exe=build-win/cat_recomp.exe pdb=build-win/cat_recomp.pdb
ran=$(awk '/cat_recomp\.exe/ {print $1}' "$LOG/run-info.txt" 2>/dev/null || true)
now=$(sha256sum "$exe" | cut -d' ' -f1)
[ "$ran" = "$now" ] || { echo "symbolize: $exe was rebuilt since $STAMP ran; not symbolizing" >&2; exit 0; }

bin="$LLVM_MINGW_ROOT/bin"
hdr=$("$bin/llvm-readobj" --file-headers "$exe")
pref=$(awk '/ImageBase:/ {print $2}' <<<"$hdr")
size=$(awk '/SizeOfImage:/ {print $2}' <<<"$hdr")

# Where the exe was loaded: the crash report's own image range, else Proton's
# loader trace (PROTON_LOG=1).
base=$(grep -m1 -o 'return addrs in image [0-9A-Fa-fx]*' "$stdio" | awk '{print $NF}') || true
[ -n "$base" ] && [ $((16#${base#0x})) -ne 0 ] ||
    base=$(grep -m1 -o 'cat_recomp\.exe" at [0-9A-Fa-f]*' "$LOG/steam-default.log" 2>/dev/null | awk '{print $NF}') || true
[ -n "$base" ] || { echo "symbolize: no load address for the exe in $LOG" >&2; exit 1; }
base=$((16#${base#0x})) pref=$((pref)) size=$((size))

{
    printf 'exe %s  loaded at 0x%X  ImageBase 0x%X\n' "$now" "$base" "$pref"
    # RIP= on the [CRASH] line, then the "[i] 0x... in ..." native stack lines.
    grep -E '^\[CRASH\]|^    \[[0-9]+\] 0x' "$stdio" | while IFS= read -r line; do
        case "$line" in
            '[CRASH]'*) echo; echo "$line"
                        a=$(grep -oE 'RIP=0x[0-9A-Fa-f]+' <<<"$line" | cut -d= -f2) || true ;;
            *)          a=$(grep -oE '0x[0-9A-Fa-f]+' <<<"$line" | head -1) || true ;;
        esac
        [ -n "$a" ] || continue
        a=$((a))
        if [ "$a" -ge "$base" ] && [ "$a" -lt $((base + size)) ]; then
            link=$((pref + a - base))
            sym=$("$bin/llvm-symbolizer" --obj="$exe" --pdb="$pdb" --pretty-print \
                  "$(printf '0x%X' "$link")" | sed -e '/^$/d' -e 's/ at ??:0:0$//' | paste -sd'|' | sed 's/|/ <- /g')
            printf '  0x%X  (0x%X)  %s\n' "$a" "$link" "$sym"
        else
            printf '  0x%X  outside the exe\n' "$a"
        fi
    done
} > "$out"
echo "symbolize: $(grep -c '^\[CRASH\]' "$out") crash report(s) -> $out"
EOF
    } | remote
}

cmd_logs() {
    need_host
    cmd_symbolize "${1:-}" || true
    mkdir -p "$GAME_DIR/bench-logs"
    # Frame dumps stay on the host (golden pulls the ones it needs).
    # Pulls (here and in golden) keep -a's times: logs and frames are not
    # build input, and the host's times are the runs' real times.
    rsync -az --exclude '/*/frames/' "$BENCH_HOST:$REMOTE_GAME/bench-logs/" "$GAME_DIR/bench-logs/"
}

cmd_shell() {
    need_host
    ssh -t "$BENCH_HOST" "cd $REMOTE_GAME 2>/dev/null || cd $BENCH_DIR; exec \$SHELL -l"
}

cmd="${1:-}"; shift || true
case "$cmd" in
    setup) cmd_setup "$@" ;;
    sync)  cmd_sync "$@" ;;
    build) cmd_build "$@" ;;
    run)   cmd_run "$@" ;;
    logs)  cmd_logs "$@" ;;
    symbolize) cmd_symbolize "$@" ;;
    shell) cmd_shell ;;
    golden) cmd_golden "$@" ;;
    all)   cmd_sync; cmd_build; cmd_run ;;
    integrate) cmd_integrate "$@" ;;
    tests)     cmd_tests "$@" ;;
    *)     sed -n '3,/^set -euo/p' "$0" | sed '$d'; exit 1 ;;
esac
