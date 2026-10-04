#!/bin/sh
# run.sh NAME SCRIPT SECONDS [DUMP_EVERY] [extra env...]: one headless Metal run, no sound
# SCRIPT: @preset or a path. Saves go to a per-run scratch dir unless RECOMP_SAVE_DIR is set.
set -u
here=$(cd "$(dirname "$0")/../.." && pwd)
name=$1 script=$2 secs=$3 every=${4:-20}
shift 3; [ $# -gt 0 ] && shift
case $script in @*) ;; *) script=$(cd "$(dirname "$script")" && pwd)/$(basename "$script");; esac
case $name in
    ''|.*|*/*) echo "run.sh: bad NAME '$name' (no '/', no leading '.')" >&2; exit 2;;
esac
out=$here/analysis/runs/$name
rm -rf "$out"; mkdir -p "$out/fb" "$out/save"
cd "$here"
env RECOMP_HEADLESS=1 SDL_AUDIODRIVER=dummy RECOMP_PB_BACKEND=metal \
    RECOMP_SAVE_DIR="${RECOMP_SAVE_DIR:-$out/save}" RECOMP_HOST_PAD=0 RECOMP_KEYBOARD=0 \
    RECOMP_INPUT_SCRIPT="$script" RECOMP_TRACE=flip \
    RECOMP_DEBUG="fb_dump=$out/fb/,fb_dump_flips=$every" "$@" \
    perl -e "alarm $secs; exec @ARGV" build/cat_recomp > "$out/log.txt" 2>&1
echo "$name rc=$? dumps=$(ls "$out/fb" | wc -l) flips=$(grep -c 'METAL\] flip' "$out/log.txt")"
"$here/scripts/shots/sheet.sh" "$out/fb" "$out/sheet.png" 10x
