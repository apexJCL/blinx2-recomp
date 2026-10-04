#!/usr/bin/env bash
# Capture xemu reference frames on the xemu host, under the run lock.
#
#   scripts/xemu_capture.sh attract [seconds] [extra xemu_ref.py args]
#   scripts/xemu_capture.sh stage1  [seconds] [...]
#   scripts/xemu_capture.sh story   [seconds] [...]   (needs ~400 s)
#
# Frames land in ~/xemu-ref/out/<scenario>-<timestamp>/ (PNG via QMP
# screendump, or spectacle of the *active* window when xemu lacks it: keep
# the desktop untouched during a run; frames.json, xemu.log).
# Refuses to run while any app.xemu.xemu instance (e.g. the user's) is up. Never commit or upload them.
# xemu runs on a private config copy in ~/xemu-ref (HDD/EEPROM copied once);
# the user's xemu.toml and HDD are only read. See scripts/xemu_ref.py.
#
# The disc image is your own dump of the game: set XEMU_ISO, in the
# environment or in ~/xemu-ref/xemu.env (sourced if present), or pass
# --iso PATH among the extra args.
set -euo pipefail
if [ -f ~/xemu-ref/xemu.env ]; then set -a; . ~/xemu-ref/xemu.env; set +a; fi
scenario=${1:-attract}
seconds=${2:-90}
shift $(( $# > 2 ? 2 : $# )) || true
here=$(cd "$(dirname "$0")" && pwd)
out=~/xemu-ref/out/${scenario}-$(date +%Y%m%d-%H%M%S)
mkdir -p "$out"
exec 9>>~/.recomp-run.lock
if ! flock -n 9; then
    echo "xemu_capture: waiting for the run lock" >&2
    flock -w 3600 -E 75 9 || exit 75
fi
echo "$(date -Iseconds) xemu_capture $out (pid $$)" > ~/.recomp-run.lock
# 9>&-: python (and xemu) must not inherit the lock fd; only this shell holds it.
python3 "$here/xemu_ref.py" --scenario "$scenario" --seconds "$seconds" --out "$out" "$@" 9>&-
echo "$out"
