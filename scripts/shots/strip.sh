#!/bin/bash
# strip.sh OUT run:frame... : 4-wide comparison montage at 320x240
# A frame is its .png (frames compact) when there is one, else its .bmp.
# -alpha off: a dump whose fourth byte is not 0 is an RGBA PNG; drawn as the BMP was, opaque.
cd "$(dirname "$0")/../../analysis/runs"
out=$1; shift; files=()
for s in "$@"; do
    f="${s%:*}/fb/${s#*:}"
    if [ -f "$f.png" ]; then files+=("$f.png"); else files+=("$f.bmp"); fi
done
magick montage "${files[@]}" -alpha off -resize 320x240 -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 12 -set label '%d %t' -tile 4x -geometry +2+2 -background '#222' -fill white "$out"
