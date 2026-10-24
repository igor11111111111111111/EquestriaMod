# -*- coding: utf-8 -*-
r"""Броня улья: перекраска ванильной асерайской брони в хитин со светящимися прожилками.

  py -3 tools/hive_armor.py

Откуда что берётся:
  - меши и текстуры асерайского дерева выгружены в assets/reference/vanilla_armor/<меш>/
    (утилитой tpac_export, см. tools/armor_catalog.py — там же список вещей);
  - у ванильной брони четыре текстуры: цвет (_d), маска цвета клана (_c), нормали (_n) и
    блики (_s). Нормали и блики остаются ванильными, их перекрашивать нечего.

Что делает скрипт: пишет eq_ch_<имя>_d.png — цвет брони улья. В нём сразу всё:
  - почти чёрный хитин, к светам холодный бирюзовый отблеск;
  - тёмная бирюза на ткани и кантах (места из маски _c);
  - ЯРКИЕ бирюзовые линии узора: прожилки в щелях между пластинами и кольцами кольчуги, кромка
    ткани и сота поверх неё.

Почему узор впечён, а не светится. У шейдера брони pbr_shading есть флаг self_illumination, и
карту свечения он берёт из слота 1 — того самого, где у ванили маска цвета клана. Сделать так
можно, и мы сделали, но померили цену: ОДИН меш с таким сочетанием флагов ставит движку 1332
сборки шейдера (примерно шесть в секунду — четыре минуты), а собранное нигде не сохраняется:
файл Shaders\D3D11\compressed_shader_cache.sack игра только читает. То есть четыре минуты при
КАЖДОМ запуске (замерено 24.09.2026). Поэтому свечение впекаем в цвет: днём разница почти не
видна, а флаги остаются ванильными и всё собрано заранее.

Дальше: импорт получившихся PNG в редакторе, потом материалы и привязка мешей кодом
(tools/hive_material.ps1 -NoGlow).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_catalog  # noqa: E402

PACK = "changeling"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
OUT = os.path.join(ROOT, "assets", "hive_armor", "textures")
PREFIX = "eq_ch_"      # наши текстуры и материалы: eq_ch_<ванильное имя>

# Хитин: от почти чёрного к холодному бирюзовому отблеску (та же палитра, что у тела
# чейнджлинга, tools/make_changeling_model.py).
CHITIN = [
    (0.00, (0.012, 0.014, 0.018)),
    (0.35, (0.045, 0.060, 0.075)),
    (0.70, (0.090, 0.200, 0.215)),
    (1.00, (0.330, 0.720, 0.700)),
]
# Ткань и канты (места из маски _c): почти чёрная с зеленоватым подсветом. Светлее делать нельзя —
# поверх неё ложится свечение, и ткань превращалась в сплошную бирюзовую простыню.
TRIM = [
    (0.00, (0.008, 0.020, 0.020)),
    (0.40, (0.014, 0.055, 0.052)),
    (0.75, (0.030, 0.120, 0.110)),
    (1.00, (0.080, 0.260, 0.210)),
]

GLOW_COLOUR = (0.35, 1.00, 0.88)   # цвет линий: светлая бирюза улья
GLOW_MIX = 0.95        # насколько линии перекрывают хитин под собой (1 — полностью)
# Светиться должны ЛИНИИ, а не площади: заливка по маске превращала халат в бирюзовый фонарь
# (видно на превью 24.09.2026). Поэтому три источника — щели между пластинами, кромка ткани
# и сота поверх ткани; все три тонкие.
VEIN_BLUR = 9         # радиус размытия, по которому ищутся щели (чем больше, тем шире прожилки)
VEIN_LOW = 0.05       # темнее окружения на столько — прожилка уже зажигается
VEIN_HIGH = 0.30      # и на столько — светится в полную силу
VEIN_POWER = 0.85     # яркость прожилок
EDGE_BLUR = 4         # на сколько пикселей размывается маска, чтобы найти её кромку
EDGE_GLOW = 0.80      # яркость кромки ткани
CELL = 110            # сторона соты узора в пикселях (узор поверх ткани)
CELL_LINE = 0.055     # толщина линии соты, доля стороны
CELL_GLOW = 0.70      # яркость сот


def log(*a):
    print("[hive]", *a, flush=True)


def ramp(t, stops):
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        k = ((t[m] - p0) / max(p1 - p0, 1e-6))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out


def smoothstep(x, low, high):
    t = np.clip((x - low) / max(high - low, 1e-6), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def find_textures():
    """{имя набора: (путь к diffuse, путь к маске или None)} — по всем вещам пакета."""
    found = {}
    for row in armor_catalog.pieces(PACK):
        folder = os.path.join(SRC, row["mesh"])
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith("_d.dds"):
                continue
            base = name[:-6]
            if base in found:
                continue
            mask = os.path.join(folder, base + "_c.dds")
            found[base] = (os.path.join(folder, name), mask if os.path.exists(mask) else None)
    return found


def read(path, size=None):
    img = Image.open(path).convert("RGB")
    if size and img.size != size:
        img = img.resize(size, Image.BILINEAR)
    return np.asarray(img, np.float32) / 255.0


_cells = {}


def honeycomb(shape):
    """Сота: сетка ШЕСТИугольников, единица — линия, ноль — пустота.

    Три набора наклонных линий дают треугольную решётку, а не соту (проверено на превью
    24.09.2026). Настоящие шестиугольники — это границы ячеек Вороного гексагональной решётки:
    считаем расстояния до двух ближайших центров, линия там, где они почти равны.
    """
    if shape in _cells:
        return _cells[shape]
    h, w = shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    step_x = CELL * 0.866                      # шаг решётки по горизонтали
    col = np.floor(x / step_x)
    row = np.floor((y - np.where(col % 2 == 0, 0.0, CELL / 2)) / CELL)
    best = np.full(shape, 1e9, np.float32)
    second = np.full(shape, 1e9, np.float32)
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1, 2):
            c = col + dc
            r = row + dr
            cx = (c + 0.5) * step_x
            cy = (r + 0.5) * CELL + np.where(c % 2 == 0, 0.0, CELL / 2)
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            best = np.where(closer, d, best)
    lines = 1.0 - smoothstep(second - best, 0.0, CELL * CELL_LINE)
    _cells[shape] = lines
    return lines


def make(diffuse_path, mask_path):
    img = read(diffuse_path)
    size = (img.shape[1], img.shape[0])
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    mask = read(mask_path, size)[..., :2].max(-1) if mask_path else np.zeros(luma.shape, np.float32)

    # ---- цвет
    colour = ramp(luma, CHITIN) * (1 - mask[..., None]) + ramp(luma, TRIM) * mask[..., None]

    # ---- свечение: щели между пластинами (там, где темнее окружения), кромка ткани и сота
    blurred = np.asarray(Image.fromarray((luma * 255).astype(np.uint8))
                         .filter(ImageFilter.GaussianBlur(VEIN_BLUR)), np.float32) / 255.0
    veins = smoothstep(blurred - luma, VEIN_LOW, VEIN_HIGH) * VEIN_POWER
    # кромка: там, где размытая маска расходится с чёткой, то есть по её границе
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(EDGE_BLUR)), np.float32) / 255.0
    edge = smoothstep(np.abs(soft - mask), 0.05, 0.25) * EDGE_GLOW
    cells = honeycomb(luma.shape) * (mask > 0.5) * CELL_GLOW
    glow = np.clip(np.maximum(np.maximum(veins, edge), cells), 0.0, 1.0)

    # ---- линии впекаем в цвет: яркая бирюза поверх хитина, с сохранением его светотени
    # Светотень исходника линиям оставляем, но не даём им темнеть вместе с кольчугой: без
    # свечения слишком тёмный узор просто пропадает.
    line = np.array(GLOW_COLOUR, np.float32)[None, None, :] * (0.78 + 0.22 * luma[..., None])
    weight = (glow * GLOW_MIX)[..., None]
    colour = colour * (1.0 - weight) + line * weight

    return Image.fromarray(np.clip(colour * 255.0, 0, 255).astype(np.uint8)), float(glow.mean())


def main():
    os.makedirs(OUT, exist_ok=True)
    textures = find_textures()
    log("наборов текстур в асерайском дереве:", len(textures))
    for base, (diffuse, mask) in sorted(textures.items()):
        colour, share = make(diffuse, mask)
        colour.save(os.path.join(OUT, PREFIX + base + "_d.png"))
        log("  %-34s маска %s, узор на %.0f%% площади"
            % (base, "есть" if mask else "нет", 100 * share))
    log("готово:", OUT)


main()
