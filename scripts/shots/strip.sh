#!/bin/bash
# strip.sh OUT run:frame... : 4-wide comparison montage at 320x240
cd "$(dirname "$0")/../../analysis/runs"
out=$1; shift; files=()
for s in "$@"; do files+=("${s%:*}/fb/${s#*:}.bmp"); done
magick montage "${files[@]}" -resize 320x240 -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 12 -set label '%d %t' -tile 4x -geometry +2+2 -background '#222' -fill white "$out"
