#!/usr/bin/env bash
# Usage: bash make_8x10.sh /path/to/photos [filter] [warmth]
#   filter : none | subtle | strong | a number   (default: subtle)
#   warmth : 0=neutral 1=default 2=toasty 3+=heavy (default: 1)
# Examples:
#   bash make_8x10.sh ~/photos                 # subtle filter, normal warmth
#   bash make_8x10.sh ~/photos none 0          # no filter, no warmth (true colour)
#   bash make_8x10.sh ~/photos subtle 2        # subtle fade + toasty warmth
set -euo pipefail

INPUT="${1:?Usage: bash make_8x10.sh /path/to/photos [filter] [warmth]}"
FILTER="${2:-subtle}"
WARMTH="${3:-1}"

# Encode the settings into the filename so different runs don't overwrite
# each other — makes it easy to compare looks side by side.
OUTPUT="album_8x10_${FILTER}_w${WARMTH}.jpg"

python3 polaroid_ganger.py \
    --input "$INPUT" \
    --sheet 8x10 \
    --margin 0.2 \
    --guide-weight 2.5 \
    --chin auto \
    --filter "$FILTER" \
    --warmth "$WARMTH" \
    --format jpg \
    --include-video \
    --output "$OUTPUT"

echo "📋 wrote files starting with: ${OUTPUT%.jpg}_p01.jpg"
