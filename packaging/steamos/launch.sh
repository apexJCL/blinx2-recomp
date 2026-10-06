#!/usr/bin/env bash
#
# BLiNX 2 launcher for a SteamOS-like Linux PC: runs the Windows build under
# Proton through umu-run. Installed as <root>/versions/<version>/launch.sh by
# install.sh and started through the stable <root>/BLiNX2 (the Steam
# shortcut's target).
#
# Everything the game keeps lives under <root>, outside the program files
# and outside the Wine prefix (Steam or a Proton update may recreate a
# prefix): game_files/ (the dump), hdd/ (saves), config/, logs/. Settings:
# launch.env.default beside this script, then <root>/config/launch.env
# (KEY=value lines, yours win).
#
# No lock: this is the game for play. A bench on the same machine checks for
# a running game itself (scripts/running_game.py).
#
set -euo pipefail

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # versions/<v>, not current
ROOT="$(cd "$HERE/../.." && pwd)"

fail() {
    echo "@NAME@: $*" >&2
    if { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; } && command -v notify-send >/dev/null; then
        notify-send -a "@NAME@" "@NAME@ cannot start" "$*" || true
    fi
    exit 1
}

# KEY=value lines; blank lines and # comments skipped; anything else is an
# error with its line number, so a typo is not silently ignored.
load_env() {
    local file=$1 n=0 line
    [ -f "$file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        n=$((n + 1))
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || fail "$file:$n: not a KEY=value line: $line"
        export "${line%%=*}=${line#*=}"
    done < "$file"
}

load_env "$HERE/launch.env.default"
load_env "$ROOT/config/launch.env"

[ -f "$ROOT/game_files/default.xbe" ] || fail "no game files at $ROOT/game_files/default.xbe; run install.sh from the bundle again"
command -v umu-run >/dev/null || fail "umu-run is not installed; it runs the game under Proton"

mkdir -p "$ROOT/config" "$ROOT/logs" "$ROOT/prefix"
# Your enhance.toml is made once and never touched again; the .default
# beside it follows the installed version (refreshed here, not by the
# installer, which never writes config/).
[ -e "$ROOT/config/enhance.toml" ] || cp "$HERE/enhance.toml.default" "$ROOT/config/enhance.toml"
cmp -s "$HERE/enhance.toml.default" "$ROOT/config/enhance.toml.default" \
    || cp "$HERE/enhance.toml.default" "$ROOT/config/enhance.toml.default"

stamp=$(date +%Y%m%d-%H%M%S)
log="$ROOT/logs/game-$stamp.log"
# The newest LOG_KEEP logs, this one included.
keep=${LOG_KEEP:-10}
ls -1t "$ROOT"/logs/game-*.log 2>/dev/null | tail -n +"$keep" | while IFS= read -r old; do rm -f -- "$old"; done || true

# Paths the game opens are Windows paths: Wine maps the host's / to Z:.
export RECOMP_GAME_FILES="Z:$ROOT/game_files"
export RECOMP_HDD_DIR="Z:$ROOT/hdd"
export RECOMP_ENHANCE_CONFIG="Z:$ROOT/config/enhance.toml"
export RECOMP_STDIO_LOG="Z:$log"
export WINEPREFIX="$ROOT/prefix" GAMEID="${GAMEID:-umu-default}" PROTONPATH="${PROTONPATH:-GE-Proton}"

# xbox_kernel.log opens in the working directory. umu-run's and Proton's own
# output (Steam shows none of it) goes to umu.log, the last launch's only.
cd "$ROOT/logs"
exec umu-run "$HERE/cat_recomp.exe" "$@" >"$ROOT/logs/umu.log" 2>&1
