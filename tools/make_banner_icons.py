# -*- coding: utf-8 -*-
r"""Icon sheet for banners: assets/banner_icons/eq_banner_icons_d.png.

  py -3 tools/make_banner_icons.py             build the sheet from the coats of arms
  py -3 tools/make_banner_icons.py --test      placeholder: a white sheet with a black border in every cell
  py -3 tools/make_banner_icons.py --numbers   the same, but with the cell number - to check the order

The size and layout are not ours but the game's (measured on vanilla sheets 25.09.2026):
  * the sheet is 2048x2048 pixels;
  * the sheet holds 4x4 icons, i.e. a 512x512 cell;
  * the cell number is the texture_index in Module/ModuleData/equestria_banner_icons.xml, counted
    left to right and top to bottom, from 0 to 15. More than sixteen icons do not fit on a sheet,
    a second material is needed.
Vanilla sheets are BC7-compressed, but it is enough for us to give the editor a plain PNG - it does the
compression itself.

Coats of arms go one file each into assets/banner_icons/src/, named in cell order
(01_equestria.png, 02_lunar.png and so on; sorted by name). Each coat of arms is a SILHOUETTE on a
transparent background: the banner takes the colour from its own key and fills everything opaque with it.
Drawing a black outline or a fill inside is pointless - there will be only one colour anyway (tested in
game 25.09.2026: a white square with a black border came out on the banner as a flat spot without the border).
Details inside a coat of arms are made with holes, i.e. transparency.

Details about banners - docs/banners.md.
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "banner_icons")
SRC = os.path.join(OUT, "src")
SHEET = 2048          # sheet size, pixels
CELLS = 4             # cells per side
BORDER = 24           # placeholder border thickness, pixels
MARGIN = 16           # icon margin from the cell edge, so neighbours do not stick together


def log(*a):
    print("[banners]", *a, flush=True)


def test_cell(sheet, index, cell, numbers):
    """Placeholder cell: a white square with a black border, optionally with a number."""
    draw = ImageDraw.Draw(sheet)
    x = (index % CELLS) * cell
    y = (index // CELLS) * cell
    box = [x + MARGIN, y + MARGIN, x + cell - MARGIN - 1, y + cell - MARGIN - 1]
    draw.rectangle(box, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=BORDER)
    if numbers:
        # The number is a hole in the square: the banner fills it with its colour anyway, transparent is not drawn.
        # We draw it large, with rectangles, so as not to depend on system fonts.
        digits = str(index)
        size = cell // 3
        thick = max(8, size // 8)
        left = x + (cell - size * len(digits)) // 2
        top = y + (cell - size) // 2
        for digit in digits:
            draw_digit(draw, digit, left, top, size, thick)
            left += size
    return sheet


# Segments of a seven-segment digit: (segment -> coordinates in fractions of a cell)
_SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}


def draw_digit(draw, digit, x, y, size, thick):
    """A digit from seven segments - transparent, i.e. cut out of the square."""
    w, h = size * 0.6, size * 0.9
    x += size * 0.2
    y += size * 0.05
    clear = (0, 0, 0, 0)
    lines = {
        "a": [x, y, x + w, y + thick],
        "b": [x + w - thick, y, x + w, y + h / 2],
        "c": [x + w - thick, y + h / 2, x + w, y + h],
        "d": [x, y + h - thick, x + w, y + h],
        "e": [x, y + h / 2, x + thick, y + h],
        "f": [x, y, x + thick, y + h / 2],
        "g": [x, y + h / 2 - thick / 2, x + w, y + h / 2 + thick / 2],
    }
    for segment in _SEGMENTS.get(digit, ""):
        draw.rectangle(lines[segment], fill=clear)


def art_cell(sheet, index, cell, path):
    """A cell from a finished coat of arms: fit the silhouette into the cell without tinting anything."""
    art = Image.open(path).convert("RGBA")
    side = cell - MARGIN * 2
    art.thumbnail((side, side), Image.LANCZOS)
    x = (index % CELLS) * cell + (cell - art.width) // 2
    y = (index // CELLS) * cell + (cell - art.height) // 2
    sheet.paste(art, (x, y), art)


def main():
    test = "--test" in sys.argv
    numbers = "--numbers" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    cell = SHEET // CELLS
    sheet = Image.new("RGBA", (SHEET, SHEET), (0, 0, 0, 0))

    art = []
    if os.path.isdir(SRC) and not (test or numbers):
        art = sorted(f for f in os.listdir(SRC) if f.lower().endswith(".png"))
        if len(art) > CELLS * CELLS:
            log("гербов %d, в лист влезает %d — лишние пропущены" % (len(art), CELLS * CELLS))
            art = art[:CELLS * CELLS]

    if art:
        for index, name in enumerate(art):
            art_cell(sheet, index, cell, os.path.join(SRC, name))
            log("клетка %2d (texture_index=%d) — %s" % (index, index, name))
    else:
        if not (test or numbers):
            log("гербов в %s нет, собираю заглушку" % os.path.normpath(SRC))
        for index in range(CELLS * CELLS):
            test_cell(sheet, index, cell, numbers)

    path = os.path.join(OUT, "eq_banner_icons_d.png")
    sheet.save(path)
    log("лист %dx%d, клеток %d по %d — %s"
        % (SHEET, SHEET, CELLS * CELLS, cell, os.path.normpath(path)))


main()
