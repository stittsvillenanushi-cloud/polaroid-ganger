#!/usr/bin/env bash
# Usage: bash make_8x10.sh /path/to/photos
# Generates 8x10 JPG sheets (4 polaroids each) ready for photo-lab upload.
set -euo pipefail

INPUT="${1:?Usage: bash make_8x10.sh /path/to/photos}"

python3 polaroid_ganger.py \
    --input "$INPUT" \
    --sheet 8x10 \
    --margin 0.2 \
    --guide-weight 2.5 \
    --chin auto \
    --filter strong \
    --format jpg \
    --include-video \
    --output album_8x10.jpg
