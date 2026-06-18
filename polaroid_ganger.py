#!/usr/bin/env python3
"""
Polaroid Ganger — bulk-import photos, frame them polaroid-style, tile them onto
print sheets with gutters + crop marks, export a print-ready PDF.

Workflow:
    1. Point --input at a folder of photos (jpg/png/heic*/webp/etc).
    2. (optional) Drop a `meta.csv` in that folder to set per-photo focus + caption.
    3. Pick a --style, --sheet, --filter, --pack.
    4. Get a multi-page print-ready PDF, then guillotine along the crop marks.

* HEIC needs `pip install pillow-heif`. Everything else is stock Pillow.

--- meta.csv (per-photo control) -------------------------------------------
Put a file named meta.csv next to your photos with these columns:

    filename,focus,caption
    photo_01.jpg,top,Lysefjord '24
    photo_02.jpg,0.3 0.6,Best boy
    photo_05.jpg,bottom-right,
    photo_07.jpg,,Summer

  - filename : the image file name (just the name, not the full path)
  - focus    : where to crop toward — a keyword (center/top/bottom/left/right/
               top-left/top-right/bottom-left/bottom-right) OR two numbers
               "x y" each 0..1 (0,0 = top-left, 1,1 = bottom-right). Blank = center.
  - caption  : text printed on the white chin. Blank = no caption.

Any photo not listed just uses the defaults. Columns you don't need can be left
blank. You can also force defaults for everything via --focus and --caption.

Examples:
    python3 polaroid_ganger.py --input ./photos --output sheets.pdf
    python3 polaroid_ganger.py --input ./photos --filter strong --pack fill
    python3 polaroid_ganger.py --input ./photos --caption filename --sheet 12x18
"""

import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

try:  # optional HEIC support
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    pass

# ---- Frame styles: all dimensions in INCHES --------------------------------
STYLES = {
    "polaroid":      {"frame": (3.5, 4.25),  "window": (3.1, 3.1),  "top": 0.23},
    "instax-mini":   {"frame": (2.13, 3.4),  "window": (1.8, 2.4),  "top": 0.20},
    "instax-square": {"frame": (2.8, 3.4),   "window": (2.4, 2.4),  "top": 0.22},
}

SHEETS = {  # width x height in inches (portrait)
    "letter": (8.5, 11.0), "a4": (8.27, 11.69), "4x6": (4.0, 6.0),
    "5x7": (5.0, 7.0), "8x10": (8.0, 10.0), "11x14": (11.0, 14.0), "12x18": (12.0, 18.0),
}

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".gif"}

FOCUS_KEYWORDS = {
    "center": (0.5, 0.5), "top": (0.5, 0.0), "bottom": (0.5, 1.0),
    "left": (0.0, 0.5), "right": (1.0, 0.5),
    "top-left": (0.0, 0.0), "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0), "bottom-right": (1.0, 1.0),
}

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Noteworthy.ttc",
    "/System/Library/Fonts/Supplemental/MarkerFelt.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def clamp01(v):
    return max(0.0, min(1.0, v))


def parse_sheet(spec):
    s = spec.lower().strip()
    if s in SHEETS:
        return SHEETS[s]
    if "x" in s:
        try:
            w, h = (float(p) for p in s.split("x", 1))
            return (w, h)
        except ValueError:
            pass
    sys.exit(f"❌ Bad --sheet '{spec}'. Use a preset {list(SHEETS)} or WxH e.g. 12x18.")


def parse_focus(s, default=(0.5, 0.5)):
    s = (s or "").strip().lower()
    if not s:
        return default
    if s in FOCUS_KEYWORDS:
        return FOCUS_KEYWORDS[s]
    parts = s.replace(",", " ").split()
    if len(parts) == 2:
        try:
            return (clamp01(float(parts[0])), clamp01(float(parts[1])))
        except ValueError:
            pass
    print(f"⚠️  Unrecognized focus '{s}', using center.")
    return default


def load_meta(folder):
    """Read optional meta.csv → {filename: {'focus':..., 'caption':...}}."""
    path = os.path.join(folder, "meta.csv")
    meta = {}
    if not os.path.isfile(path):
        return meta
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            name = row.get("filename")
            if name:
                meta[name] = {"focus": row.get("focus", ""), "caption": row.get("caption", "")}
    print(f"📋 Loaded meta.csv ({len(meta)} entries)")
    return meta


def load_images(folder):
    if not os.path.isdir(folder):
        sys.exit(f"❌ --input folder not found: {folder}")
    files = sorted(
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in EXTS
    )
    if not files:
        sys.exit(f"❌ No images found in {folder} (looked for {sorted(EXTS)}).")
    return files


def cover_crop(img, target_w, target_h, fx=0.5, fy=0.5):
    """Resize+crop so img fills target exactly, biased toward focus point (fx,fy)."""
    img = img.convert("RGB")
    sw, sh = img.size
    scale = max(target_w / sw, target_h / sh)
    nw, nh = round(sw * scale), round(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = round((nw - target_w) * fx)
    top = round((nh - target_h) * fy)
    left = max(0, min(left, nw - target_w))
    top = max(0, min(top, nh - target_h))
    return img.crop((left, top, left + target_w, top + target_h))


def polaroid_filter(img, strength, warmth=1.0):
    """Vintage polaroid look.

    strength : fade/contrast/saturation amount (0 = off, 1 = subtle, 2 = strong).
    warmth   : amber tone, dialed independently (0 = neutral, 1 = default,
               2 = toasty, 3+ = heavy amber). You can push warmth even with
               strength low if you only want the warm cast.
    """
    if strength <= 0 and warmth <= 0:
        return img
    if strength > 0:
        img = ImageEnhance.Color(img).enhance(1.0 + 0.06 * strength)      # touch more saturation
        img = ImageEnhance.Contrast(img).enhance(1.0 - 0.07 * strength)   # softer contrast
        img = ImageEnhance.Brightness(img).enhance(1.0 + 0.03 * strength) # slight lift

    def lut(lift, gain):
        return [min(255, int(lift + v * (255 - lift) / 255 * gain)) for v in range(256)]

    lift = 16 * max(strength, 0.0)
    r, g, b = img.split()
    r = r.point(lut(lift, 1.0 + 0.05 * warmth))         # warm up reds
    g = g.point(lut(lift, 1.0 + 0.01 * warmth))         # a hair of green for amber
    b = b.point(lut(lift * 1.25, 1.0 - 0.05 * warmth))  # pull blues down
    return Image.merge("RGB", (r, g, b))


def fit_font(draw, text, max_w, max_size):
    for size in range(max_size, 9, -2):
        font = load_font(size)
        if draw.textlength(text, font=font) <= max_w:
            return font
    return load_font(10)


_FONT_PATH = None


def load_font(size):
    global _FONT_PATH
    if _FONT_PATH is None:
        for p in FONT_CANDIDATES:
            if os.path.isfile(p):
                _FONT_PATH = p
                break
        _FONT_PATH = _FONT_PATH or ""
    try:
        return ImageFont.truetype(_FONT_PATH, size) if _FONT_PATH else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def make_tile(path, style, dpi, fx, fy, caption, filt, chin_mode="classic", warmth=1.0):
    fw, fh = (round(d * dpi) for d in style["frame"])
    border = round(style["top"] * dpi)

    tile = Image.new("RGB", (fw, fh), "white")
    with Image.open(path) as im:
        src_w, src_h = im.size
        portrait = src_h > src_w * 1.1
        # chin needed for captions; otherwise decide by mode/orientation
        use_chin = bool(caption) or chin_mode == "classic" or \
            (chin_mode == "auto" and not portrait)
        if use_chin:
            ww, wh = (round(d * dpi) for d in style["window"])
            top, left = round(style["top"] * dpi), (fw - ww) // 2
        else:  # even borders all around — photo fills the extra space
            ww, wh = fw - 2 * border, fh - 2 * border
            top, left = border, border
        photo = cover_crop(im, ww, wh, fx, fy)
    photo = polaroid_filter(photo, filt, warmth)
    tile.paste(photo, (left, top))

    if caption:
        draw = ImageDraw.Draw(tile)
        chin_top = top + wh
        chin_h = fh - chin_top
        font = fit_font(draw, caption, ww, round(0.22 * dpi))
        bbox = draw.textbbox((0, 0), caption, font=font)
        tx = (fw - (bbox[2] - bbox[0])) // 2 - bbox[0]
        ty = chin_top + (chin_h - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((tx, ty), caption, fill=(45, 45, 48), font=font)
    return tile


def draw_crop_marks(draw, x, y, w, h, dpi, gap):
    # Outward-only ticks that live in the gutter/margin — never on the tile.
    # `gap` caps the length so two neighbours' marks meet without crossing tiles.
    n = max(2, min(round(0.1 * dpi), gap))
    c, wd = (150, 150, 150), max(1, round(dpi / 200))
    for cx, cy, sx, sy in ((x, y, -1, -1), (x + w, y, 1, -1),
                           (x, y + h, -1, 1), (x + w, y + h, 1, 1)):
        draw.line([(cx, cy), (cx + sx * n, cy)], fill=c, width=wd)  # horizontal, outward
        draw.line([(cx, cy), (cx, cy + sy * n)], fill=c, width=wd)  # vertical, outward


def draw_cut_lines(draw, rects, sw, sh, dpi, weight, color=(90, 90, 90)):
    """Full-page alignment/cut lines along every tile edge.

    Drawn *before* the tiles are pasted, so each line shows only in the gutters
    and margins — but because every edge spans the whole sheet you get one
    continuous straight reference top-to-bottom and left-to-right. With a
    shared-edge grid (zero gutter) the marks land in the top/bottom/left/right
    margins perfectly in line, so a guillotine cuts straight across in one pass.
    `weight` scales thickness (1 = hairline, 2 = default chunky guide).
    """
    if not rects:
        return
    xs, ys = set(), set()
    for x, y, w, h in rects:
        xs.update((x, x + w))
        ys.update((y, y + h))
    wd = max(1, round(dpi / 200 * weight))
    for x in sorted(xs):
        draw.line([(x, 0), (x, sh)], fill=color, width=wd)   # vertical, full height
    for y in sorted(ys):
        draw.line([(0, y), (sw, y)], fill=color, width=wd)   # horizontal, full width


def grid_for(sheet_in, tw, th, dpi, gutter_in, margin_in):
    sw, sh = (round(d * dpi) for d in sheet_in)
    g, m = round(gutter_in * dpi), round(margin_in * dpi)
    cols = max(0, (sw - 2 * m + g) // (tw + g))
    rows = max(0, (sh - 2 * m + g) // (th + g))
    return sw, sh, g, m, cols, rows


def build_sheets(tiles, sheet_in, dpi, gutter_in, margin_in, guides, guide_weight,
                 pack, auto_orient):
    tw, th = tiles[0].size

    # Shared-edge grid: butt tiles together (no gutter) so neighbours share a
    # single cut line — fits more per sheet and minimises cuts.
    if pack == "grid":
        gutter_in = 0.0

    candidates = [sheet_in]
    if auto_orient:
        candidates.append((sheet_in[1], sheet_in[0]))  # rotated
    best = None
    for cand in candidates:
        sw, sh, g, m, cols, rows = grid_for(cand, tw, th, dpi, gutter_in, margin_in)
        if cols * rows and (best is None or cols * rows > best[0]):
            best = (cols * rows, cand, sw, sh, g, m, cols, rows)
    if best is None:
        sys.exit("❌ Tile is larger than the sheet. Use a bigger --sheet or smaller --style.")
    _, sheet_in, sw, sh, g, m, cols, rows = best
    per_page = cols * rows

    pages, i = [], 0
    while i < len(tiles):
        page = Image.new("RGB", (sw, sh), "white")
        draw = ImageDraw.Draw(page)
        on_page = min(per_page, len(tiles) - i)
        # how many rows this page actually fills (last page may be short)
        used_rows = (on_page + cols - 1) // cols

        # First pass: work out every tile's rectangle + its local gutter.
        placements = []  # (slot, x, y, gut)
        for slot in range(on_page):
            r, c = divmod(slot, cols)
            row_items = min(cols, on_page - r * cols)
            if pack == "tight":
                x, y, gut = m + c * (tw + g), m + r * (th + g), g
            elif pack == "fill":
                # spread tiles edge-to-edge inside the margins
                gx = (sw - 2 * m - row_items * tw) // max(1, row_items - 1) if row_items > 1 else 0
                gy = (sh - 2 * m - used_rows * th) // max(1, used_rows - 1) if used_rows > 1 else 0
                x, y, gut = m + c * (tw + gx), m + r * (th + gy), min(gx, gy)
            else:  # center / grid (grid forced g=0 above)
                bw = cols * tw + (cols - 1) * g
                bh = rows * th + (rows - 1) * g
                x = (sw - bw) // 2 + c * (tw + g)
                y = (sh - bh) // 2 + r * (th + g)
                gut = g
            placements.append((slot, x, y, gut))

        # Full-page alignment lines go down *first* so tiles cover the inner
        # part and only the gutter/margin reference remains.
        if guides in ("lines", "both"):
            rects = [(x, y, tw, th) for _, x, y, _ in placements]
            draw_cut_lines(draw, rects, sw, sh, dpi, guide_weight)

        for slot, x, y, gut in placements:
            page.paste(tiles[i + slot], (x, y))
            if guides in ("marks", "both"):
                draw_crop_marks(draw, x, y, tw, th, dpi, max(1, gut // 2))
        pages.append(page)
        i += on_page
    return pages, sheet_in, cols, rows, per_page


def main():
    ap = argparse.ArgumentParser(description="Bulk polaroid gang-print tool.")
    ap.add_argument("--input", required=True, help="Folder of photos (+ optional meta.csv)")
    ap.add_argument("--output", default="polaroid_sheets.pdf")
    ap.add_argument("--style", default="polaroid", choices=list(STYLES))
    ap.add_argument("--sheet", default="letter", help=f"{list(SHEETS)} or WxH inches")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--gutter", type=float, default=0.1, help="Gap between tiles (inches)")
    ap.add_argument("--margin", type=float, default=0.18, help="Sheet edge margin (inches)")
    ap.add_argument("--pack", default="grid", choices=["grid", "center", "tight", "fill"],
                    help="grid=shared edges, no gutter (most photos, fewest cuts); "
                         "center=grid centered; tight=top-left packed; fill=spread to edges")
    ap.add_argument("--auto-orient", action="store_true",
                    help="Try landscape sheet too, keep whichever fits more tiles")
    ap.add_argument("--filter", default="subtle",
                    help="Fade/contrast strength: none|subtle|strong, or any number "
                         "(e.g. 1.5). 0 = off.")
    ap.add_argument("--warmth", type=float, default=1.0,
                    help="Amber warmth dial: 0=neutral, 1=default, 2=toasty, 3+=heavy.")
    ap.add_argument("--chin", default="auto", choices=["classic", "auto", "none"],
                    help="classic=always polaroid chin; auto=portrait photos fill (no chin) "
                         "unless captioned; none=even borders for all")
    ap.add_argument("--focus", default="center", help="Default crop focus for photos w/o meta")
    ap.add_argument("--caption", default="", help="'filename' to caption all, else a fixed string")
    ap.add_argument("--guides", default="lines",
                    choices=["lines", "marks", "both", "none"],
                    help="lines=full-page cut/alignment lines (default); marks=corner "
                         "ticks only; both=lines+ticks; none=no guides")
    ap.add_argument("--guide-weight", type=float, default=2.0,
                    help="Thickness of full-page guide lines (1=hairline, 2=default, 3+=bold)")
    ap.add_argument("--no-crop-marks", action="store_true",
                    help="Shortcut for --guides none")
    ap.add_argument("--format", default="pdf", choices=["pdf", "jpg", "png", "both"],
                    help="pdf=single multipage PDF; jpg/png=one image file per sheet "
                         "(for photo-lab upload, e.g. Walmart 11x14); both=PDF + images")
    args = ap.parse_args()

    guides = "none" if args.no_crop_marks else args.guides

    style = STYLES[args.style]
    sheet_in = parse_sheet(args.sheet)
    files = load_images(args.input)
    meta = load_meta(args.input)
    default_focus = parse_focus(args.focus)
    presets = {"none": 0.0, "subtle": 1.0, "strong": 2.0}
    fkey = args.filter.strip().lower()
    if fkey in presets:
        filt = presets[fkey]
    else:
        try:
            filt = max(0.0, float(args.filter))
        except ValueError:
            sys.exit(f"❌ Bad --filter '{args.filter}'. Use none/subtle/strong or a number.")

    print(f"📋 {len(files)} photos | {args.style} | {args.sheet} @ {args.dpi}dpi"
          f" | filter={filt:g} warmth={args.warmth:g} | pack={args.pack}")
    tiles = []
    for n, f in enumerate(files, 1):
        name = os.path.basename(f)
        m = meta.get(name, {})
        fx, fy = parse_focus(m.get("focus"), default_focus)
        if m.get("caption"):
            cap = m["caption"]
        elif args.caption == "filename":
            cap = os.path.splitext(name)[0]
        else:
            cap = args.caption
        try:
            tiles.append(make_tile(f, style, args.dpi, fx, fy, cap, filt, args.chin, args.warmth))
        except Exception as e:
            print(f"\n⚠️  Skipped {name}: {e}")
        print(f"\r🔄 Framing {n}/{len(files)}", end="", flush=True)
    print()
    if not tiles:
        sys.exit("❌ No usable images.")

    pages, used_sheet, cols, rows, per_page = build_sheets(
        tiles, sheet_in, args.dpi, args.gutter, args.margin,
        guides, args.guide_weight, args.pack, args.auto_orient,
    )
    tile_area = style["frame"][0] * style["frame"][1] * per_page
    sheet_area = used_sheet[0] * used_sheet[1]
    print(f"📋 Grid: {cols}×{rows} = {per_page}/page on {used_sheet[0]}x{used_sheet[1]}\" "
          f"→ {len(pages)} page(s) | sheet fill ≈ {tile_area / sheet_area * 100:.0f}%")

    base, ext = os.path.splitext(args.output)
    wrote = []
    if args.format in ("pdf", "both"):
        pdf_path = args.output if ext.lower() == ".pdf" else base + ".pdf"
        pages[0].save(pdf_path, "PDF", resolution=args.dpi,
                      save_all=True, append_images=pages[1:])
        wrote.append(pdf_path)
    if args.format in ("jpg", "png", "both"):
        imgfmt = "png" if args.format == "png" else "jpg"  # 'both' exports JPG
        pil_fmt = "PNG" if imgfmt == "png" else "JPEG"
        opts = {"dpi": (args.dpi, args.dpi)}
        if pil_fmt == "JPEG":
            opts.update(quality=95, subsampling=0)
        for n, page in enumerate(pages, 1):
            suffix = f".{imgfmt}" if len(pages) == 1 else f"_p{n:02d}.{imgfmt}"
            img_path = base + suffix
            page.save(img_path, pil_fmt, **opts)
            wrote.append(img_path)

    px_w, px_h = pages[0].size
    print(f"✅ Wrote {len(tiles)} polaroids on {len(pages)} sheet(s) "
          f"@ {px_w}×{px_h}px ({args.dpi}dpi):")
    for p in wrote:
        print(f"   • {p}")
    print("   Print at 100% / 'Actual size' (no scaling), then guillotine straight"
          " across along the full-page guide lines.")


if __name__ == "__main__":
    main()
