"""Перекраска ванильной брони под хитин чейнджлингов.

  py -3 tools/recolor_armor.py [пакет]      пакет по умолчанию — changeling

Откуда что берётся:
  - меши и текстуры пакета выгружены утилитой tpac_export в assets/reference/vanilla_armor/<меш>/;
  - у каждой ванильной брони есть diffuse (_d) и маска цвета клана (_c): красный канал — первый цвет
    клана, зелёный — второй. По ней движок красит ткань и канты, поэтому «чёрное с бирюзовыми и
    зелёными полосками» получается само, если цвета клана заданы (tools/world_data.py, улей).

Что делает скрипт:
  1. diffuse переводит в хитин: почти чёрная основа, к светам — холодный бирюзовый отблеск;
  2. места из маски оставляет нейтрально-светлыми, чтобы цвет клана ложился чисто, а не поверх песка;
  3. кладёт результат в assets/pony_armor_changeling/textures/<имя>_d.png — эти текстуры
     импортируются в редакторе, нормали и блики берём ванильные (они не красятся).
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armor_catalog  # noqa: E402

PACK = sys.argv[1] if len(sys.argv) > 1 else "changeling"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
OUT = os.path.join(ROOT, "assets", f"pony_armor_{PACK}", "textures")

# Хитин: от почти чёрного к бирюзовому отблеску (цвета согласованы с моделью чейнджлинга,
# tools/make_changeling.py — там та же палитра у тела).
CHITIN = [
    (0.00, (0.012, 0.014, 0.018)),
    (0.35, (0.045, 0.060, 0.075)),
    (0.70, (0.090, 0.200, 0.215)),
    (1.00, (0.330, 0.720, 0.700)),
]
# Участки из маски _c движок в наших проверках так и не покрасил цветами фракции (ни в разговоре,
# ни при кричащих цветах клана и культуры), поэтому цвет улья впекаем прямо в текстуру: ткань и
# канты — тёмная бирюза с зелёным подсветом, а не нейтральная подложка.
TRIM = [
    (0.00, (0.010, 0.030, 0.030)),
    (0.40, (0.020, 0.110, 0.105)),
    (0.75, (0.045, 0.300, 0.260)),
    (1.00, (0.180, 0.620, 0.420)),
]
PREFIX = "eq_ch_"  # наши текстуры и материалы: eq_ch_<ванильное имя>


def log(*a):
    print("[recolor]", *a, flush=True)


def ramp(t, stops):
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        k = ((t[m] - p0) / max(p1 - p0, 1e-6))[..., None]
        out[m] = np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out


def find_textures():
    """{имя текстуры без _d: (путь к diffuse, путь к маске или None)}"""
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


def recolor(diffuse_path, mask_path):
    img = np.asarray(Image.open(diffuse_path).convert("RGB"), np.float32) / 255.0
    luma = img @ np.array([0.299, 0.587, 0.114], np.float32)
    chitin = ramp(luma, CHITIN)
    if mask_path:
        m = Image.open(mask_path).convert("RGB").resize(
            (img.shape[1], img.shape[0]), Image.BILINEAR)
        mask = np.asarray(m, np.float32)[..., :2].max(-1) / 255.0
    else:
        mask = np.zeros(luma.shape, np.float32)
    trim = ramp(luma, TRIM)
    out = chitin * (1 - mask[..., None]) + trim * mask[..., None]
    return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8))


def main():
    os.makedirs(OUT, exist_ok=True)
    textures = find_textures()
    log(f"текстур в пакете {PACK}: {len(textures)}")
    for base, (diffuse, mask) in sorted(textures.items()):
        # префикс обязателен: иначе имя совпадёт с ванильной текстурой и материал возьмёт не ту
        out = os.path.join(OUT, PREFIX + base + "_d.png")
        recolor(diffuse, mask).save(out)
        log(f"  {base}: маска {'есть' if mask else 'нет'} -> {os.path.basename(out)}")
    log("готово:", OUT)


main()
