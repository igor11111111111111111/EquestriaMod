# -*- coding: utf-8 -*-
r"""Лист значков для знамён: assets/banner_icons/eq_banner_icons_d.png.

  py -3 tools/make_banner_icons.py             собрать лист из гербов
  py -3 tools/make_banner_icons.py --test      заглушка: белый лист с чёрной каёмкой в каждой клетке
  py -3 tools/make_banner_icons.py --numbers   то же, но с номером клетки — проверить порядок

Размер и раскладка не наши, а игровые (замерено по ванильным листам 25.09.2026):
  * лист 2048x2048 пикселей;
  * на листе 4x4 значка, то есть клетка 512x512;
  * номер клетки — это texture_index в Module/ModuleData/equestria_banner_icons.xml, считается
    слева направо и сверху вниз, от 0 до 15. Больше шестнадцати значков в лист не положить,
    нужен второй материал.
Ванильные листы сжаты в BC7, но нам достаточно отдать в редактор обычный PNG — сжатие он сделает
сам.

Гербы кладутся по одному файлу в assets/banner_icons/src/, имена — по порядку клеток
(01_equestria.png, 02_lunar.png и так далее; сортировка по имени). Каждый герб — СИЛУЭТ на
прозрачном фоне: цвет знамя берёт из своего ключа, а всё непрозрачное заливает этим цветом.
Рисовать чёрную обводку или заливку внутри бесполезно — цвет всё равно будет один (проверено в
игре 25.09.2026: белый квадрат с чёрной каёмкой вышел на знамени ровным пятном без каёмки).
Детали внутри герба делаются дырками, то есть прозрачностью.

Подробности про знамёна — docs/banners.md.
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "banner_icons")
SRC = os.path.join(OUT, "src")
SHEET = 2048          # размер листа, пикселей
CELLS = 4             # клеток по стороне
BORDER = 24           # толщина каёмки заглушки, пикселей
MARGIN = 16           # отступ значка от края клетки, чтобы соседи не слипались


def log(*a):
    print("[banners]", *a, flush=True)


def test_cell(sheet, index, cell, numbers):
    """Клетка-заглушка: белый квадрат с чёрной каёмкой, по желанию с номером."""
    draw = ImageDraw.Draw(sheet)
    x = (index % CELLS) * cell
    y = (index // CELLS) * cell
    box = [x + MARGIN, y + MARGIN, x + cell - MARGIN - 1, y + cell - MARGIN - 1]
    draw.rectangle(box, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=BORDER)
    if numbers:
        # Номер — дыркой в квадрате: цвет знамя всё равно зальёт своим, а прозрачное не рисует.
        # Рисуем крупно, прямоугольниками, чтобы не зависеть от шрифтов в системе.
        digits = str(index)
        size = cell // 3
        thick = max(8, size // 8)
        left = x + (cell - size * len(digits)) // 2
        top = y + (cell - size) // 2
        for digit in digits:
            draw_digit(draw, digit, left, top, size, thick)
            left += size
    return sheet


# Отрезки семисегментного знака: (сегмент -> координаты в долях клетки)
_SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}


def draw_digit(draw, digit, x, y, size, thick):
    """Цифра семью отрезками — прозрачными, то есть вырезанными из квадрата."""
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
    """Клетка из готового герба: вписываем силуэт в клетку, ничего не подкрашивая."""
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
