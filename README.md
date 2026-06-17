# Polaroid Ganger

Bulk-import a folder of photos, frame them polaroid-style (**3.5 × 4.25"** — fits
standard Polaroid albums), tile them onto a print sheet with crop marks, and
export a print-ready PDF. Then print and guillotine into individual photos.

---

## 1. One-time setup

You need Python 3 and Pillow (image library).

```bash
# Check Python (macOS has it built in)
python3 --version

# Install Pillow if you don't have it
pip3 install Pillow

# Optional: only if your photos are iPhone .HEIC files
pip3 install pillow-heif
```

That's it. The whole tool is one file: `polaroid_ganger.py`.

---

## 2. Put your photos in a folder

Drop all the photos you want into one folder, e.g.:

```
~/Desktop/my-polaroids/
    IMG_001.jpg
    IMG_002.jpg
    vacation.png
    ...
```

Supported: jpg, jpeg, png, webp, tif/tiff, bmp, gif (+ heic with pillow-heif).

---

## 3. Run it

```bash
cd ~/claude/github/polaroid-ganger

python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --output album.pdf
```

You'll get `album.pdf` — open it, print at **100% / "Actual Size"** (no "fit to
page"), then cut along the corner crop marks. Each photo comes out 3.5 × 4.25".

---

## 4. Common recipes

**Cheapest route — one polaroid per 4×6 print** (upload-and-trim):
```bash
python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --sheet 4x6 --output prints.pdf
```

**Most per page — 12 on a 12×18 poster** (chin removed to fill space):
```bash
python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --sheet 12x18 --chin none --output poster.pdf
```

**Classic look with the vintage filter:**
```bash
python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --filter subtle --output album.pdf
```

**Dial in a warm, amber polaroid tone** (tweak the numbers to taste):
```bash
python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --filter 1.2 --warmth 2 --output album.pdf
```

**Caption every photo with its filename:**
```bash
python3 polaroid_ganger.py --input ~/Desktop/my-polaroids --caption filename --output album.pdf
```

---

## 5. Per-photo control (focus + captions) — meta.csv

To set where a photo crops, or add a caption, put a file named **`meta.csv`**
inside your photo folder:

```csv
filename,focus,caption
IMG_001.jpg,top,Lysefjord '24
IMG_002.jpg,0.3 0.6,Best boy
vacation.png,bottom-right,
```

- **filename** — the image file name (not the full path)
- **focus** — where to crop toward. A keyword
  (`center` `top` `bottom` `left` `right` `top-left` `top-right`
  `bottom-left` `bottom-right`) **or** two numbers `x y` from 0–1
  (`0 0` = top-left, `1 1` = bottom-right). Blank = center.
- **caption** — text printed on the white chin. Blank = no caption.

Photos not listed just use the defaults. The tool auto-detects `meta.csv` — no
flag needed.

---

## 6. All options

| Flag | Default | What it does |
|------|---------|--------------|
| `--input` | (required) | Folder of photos (+ optional meta.csv) |
| `--output` | `polaroid_sheets.pdf` | Output PDF path |
| `--style` | `polaroid` | `polaroid` (3.5×4.25) / `instax-mini` / `instax-square` |
| `--sheet` | `letter` | `letter a4 4x6 5x7 8x10 11x14 12x18` or custom `WxH` |
| `--dpi` | `300` | Print resolution |
| `--filter` | `subtle` | Fade/contrast: `none`/`subtle`/`strong` **or any number** (e.g. `1.5`) |
| `--warmth` | `1.0` | Amber dial: `0`=neutral, `1`=default, `2`=toasty, `3+`=heavy |
| `--chin` | `auto` | `classic`=always chin · `auto`=tall photos fill unless captioned · `none`=even borders |
| `--pack` | `center` | `center` / `tight` (top-left) / `fill` (spread to edges) |
| `--auto-orient` | off | Also try landscape sheet, keep whichever fits more |
| `--focus` | `center` | Default crop focus for photos without a meta entry |
| `--caption` | (none) | `filename` to caption all, or a fixed string |
| `--no-crop-marks` | off | Hide the corner cut ticks |

---

## 7. How many fit per sheet (3.5 × 4.25" photos)

| Sheet | Photos/page |
|-------|-------------|
| Letter 8.5×11 | 4 |
| 8×10 | 4 |
| 11×14 | 9 |
| 12×18 | 12 |

The photo size is fixed by your album, so more-per-page means a bigger sheet.

---

## 8. Printing tips

- Always print at **100% / Actual Size** — turn OFF "scale to fit," or cuts won't line up.
- Use a paper trimmer/guillotine and cut along the corner marks.
- For ordering prints online: a 4×6 print holds one polaroid with trim room; a
  12×18 poster holds 12.
