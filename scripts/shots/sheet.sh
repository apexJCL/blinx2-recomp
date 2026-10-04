#!/bin/sh
# sheet.sh DIR OUT [tile] : thumbnail contact sheet of DIR/*.bmp, labelled by filename
d=$1; out=$2; tile=${3:-8x}
magick montage "$d"/*.bmp -resize 200x150 -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 11 -set label '%t' -tile $tile -geometry +2+2 -background '#222' -fill white "$out"
