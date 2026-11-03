#!/bin/sh
# sheet.sh DIR OUT [tile] : thumbnail contact sheet of DIR's frame dumps, labelled by filename
# Each dump is the CLI's PNG of it (frames compact) when there is one, else the BMP.
# -alpha off: a dump whose fourth byte is not 0 is an RGBA PNG; drawn as the BMP was, opaque.
d=$1; out=$2; tile=${3:-8x}
set --
for f in "$d"/*; do
    case $f in
        *.png) ;;
        *.bmp) [ -f "${f%.bmp}.png" ] && continue;;
        *) continue;;
    esac
    [ -f "$f" ] && set -- "$@" "$f"
done
[ $# -gt 0 ] || { echo "sheet.sh: no .png or .bmp frames in $d" >&2; exit 1; }
magick montage "$@" -alpha off -resize 200x150 -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 11 -set label '%t' -tile $tile -geometry +2+2 -background '#222' -fill white "$out"
