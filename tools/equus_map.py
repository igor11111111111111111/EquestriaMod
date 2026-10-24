# The Equus world map in one place: heights, land, terrain types and cities - all from assets/map
# (built by tools/make_equus_map.py from the Equestria at War reference).
#
# The settlement, scene entity and terrain painting generators take their data from here, so that a
# town stands at exactly the same height as the ground under it and does not end up in the sea.
#
# Axes: x - east, y - north, in map metres (0..MAP_SIZE). The images in assets/map are stored
# top to bottom (first row is north), so rows are flipped on reading.
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "assets", "map")

# TaleWorlds.Core.TerrainType numbers (as in eq_map_terrain.png)
PLAIN, DESERT, SNOW, FOREST, STEPPE, MOUNTAIN, LAKE, WATER, RIVER, SWAMP = 1, 2, 3, 4, 5, 7, 8, 10, 11, 15

_cache = {}


def info():
    if "info" not in _cache:
        with open(os.path.join(DIR, "eq_map.json"), encoding="utf-8") as f:
            _cache["info"] = json.load(f)
    return _cache["info"]


MAP_SIZE = float(info()["map_size"])


def _image(name):
    """Image as an array, row 0 is south (y = 0)."""
    if name not in _cache:
        _cache[name] = np.asarray(Image.open(os.path.join(DIR, name)))[::-1]
    return _cache[name]


def heights():
    """Heights in metres, (SAMPLES x SAMPLES), row 0 is south. The editor import converted them the same way."""
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
    """Bilinear interpolation between 4 neighbouring samples (grid is 1 m/pixel). Previously the
    nearest pixel was taken without interpolation - unnoticeable on flat ground, but on a rocky scree/slope
    (a sharp drop between neighbouring samples) the height jumped by tens of centimetres, and
    props placed by map_props.py hung in the air or sank off the ground (noticed in game on
    07.10.2026). The same interpolation the engine itself uses between heightmap samples when
    building the terrain - it does not build steps the nearest-pixel way.
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
    """The point is on land, and the area around it (margin m) is land too - a settlement will not hang over the shore."""
    return all(is_land(x + dx, y + dy) for dx, dy in
               ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)))


def nearest_ground(x, y, margin=4.0, limit=40.0):
    """The point of solid land nearest to (x, y) (searched in a spiral), or None."""
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
