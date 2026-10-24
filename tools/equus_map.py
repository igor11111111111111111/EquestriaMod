# Карта мира Эквуса в одном месте: высоты, суша, типы местности и города — всё из assets/map
# (их собирает tools/make_equus_map.py по референсу Equestria at War).
#
# Отсюда берут данные генераторы поселений, сущностей сцены и раскраски рельефа, чтобы город
# стоял ровно на той высоте, что и земля под ним, и не оказался в море.
#
# Оси: x — на восток, y — на север, в метрах карты (0..MAP_SIZE). Картинки в assets/map лежат
# сверху вниз (первая строка — север), поэтому при чтении строки переворачиваются.
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "map")

# Номера TaleWorlds.Core.TerrainType (как в eq_map_terrain.png)
PLAIN, DESERT, SNOW, FOREST, STEPPE, MOUNTAIN, LAKE, WATER, RIVER, SWAMP = 1, 2, 3, 4, 5, 7, 8, 10, 11, 15

_cache = {}


def info():
    if "info" not in _cache:
        with open(os.path.join(DIR, "eq_map.json"), encoding="utf-8") as f:
            _cache["info"] = json.load(f)
    return _cache["info"]


MAP_SIZE = float(info()["map_size"])


def _image(name):
    """Картинка как массив, строка 0 — юг (y = 0)."""
    if name not in _cache:
        _cache[name] = np.asarray(Image.open(os.path.join(DIR, name)))[::-1]
    return _cache[name]


def heights():
    """Высоты в метрах, (SAMPLES x SAMPLES), строка 0 — юг. Так же их пересчитал импорт в редакторе."""
    if "heights" not in _cache:
        raw = _image("eq_map_heightmap.png").astype(np.float32) / 65535.0
        lo, hi = info()["min_height"], info()["max_height"]
        _cache["heights"] = lo + raw * (hi - lo)
    return _cache["heights"]


def terrain_map():
    return _image("eq_map_terrain.png")


def land_map():
    return _image("eq_map_land.png") > 127


def _index(x, y, size):
    i = int(round(min(max(x / MAP_SIZE, 0.0), 1.0) * (size - 1)))
    j = int(round(min(max(y / MAP_SIZE, 0.0), 1.0) * (size - 1)))
    return j, i


def height(x, y):
    """Билинейная интерполяция между 4 соседними отсчётами (сетка — 1 м/пиксель). Раньше брался
    ближайший пиксель без интерполяции — на ровном месте незаметно, но на каменистой осыпи/склоне
    (резкий перепад между соседними отсчётами) высота скакала на десятки сантиметров, и
    расставленные map_props.py предметы повисали в воздухе или садились мимо земли (замечено в
    игре 07.10.2026). Та же интерполяция, что использует сам движок между отсчётами heightmap при
    построении рельефа — методом ближайшего пикселя он не строит ступеньки.
    """
    h = heights()
    size = h.shape[0]
    fx = min(max(x / MAP_SIZE, 0.0), 1.0) * (size - 1)
    fy = min(max(y / MAP_SIZE, 0.0), 1.0) * (size - 1)
    i0, j0 = int(fx), int(fy)
    i1, j1 = min(i0 + 1, size - 1), min(j0 + 1, size - 1)
    tx, ty = fx - i0, fy - j0
    top = h[j0, i0] * (1 - tx) + h[j0, i1] * tx
    bottom = h[j1, i0] * (1 - tx) + h[j1, i1] * tx
    return float(top * (1 - ty) + bottom * ty)


def terrain(x, y):
    t = terrain_map()
    return int(t[_index(x, y, t.shape[0])])


def is_land(x, y):
    return terrain(x, y) not in (WATER, LAKE, RIVER) and bool(land_map()[_index(x, y, land_map().shape[0])])


def solid_ground(x, y, margin=4.0):
    """Точка на суше, и вокруг неё (margin м) тоже суша — поселение не повиснет над берегом."""
    return all(is_land(x + dx, y + dy) for dx, dy in
               ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)))


def nearest_ground(x, y, margin=4.0, limit=40.0):
    """Ближайшая к (x, y) точка твёрдой суши (по спирали), либо None."""
    if solid_ground(x, y, margin):
        return x, y
    step = 1.0
    r = step
    while r <= limit:
        for k in range(max(8, int(2 * math.pi * r / step))):
            a = 2 * math.pi * k / max(8, int(2 * math.pi * r / step))
            nx, ny = x + r * math.cos(a), y + r * math.sin(a)
            if 2 < nx < MAP_SIZE - 2 and 2 < ny < MAP_SIZE - 2 and solid_ground(nx, ny, margin):
                return nx, ny
        r += step
    return None


def cities():
    return info()["cities"]
