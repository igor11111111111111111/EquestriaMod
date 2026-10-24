# A "who owns what" picture: relief, settlements by kingdom, borders of holdings.
#
#   py tools/map_overview.py [Module folder] [output file]
#
# Draws from the generated XML (equestria_settlements.xml + equestria_clans.xml):
#   - land/water and terrain type as a pale background;
#   - holdings by the nearest settlement (Voronoi) - filled with the kingdom's color;
#   - towns (large square), castles (medium), villages (dot);
#   - kingdom labels in the middle of their lands and the number of settlements.
# Needed to check the kingdom balance and empty areas by eye.
import collections
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else "Module"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join("docs", "reference", "world_balance.png")

KINGDOM_COLOR = {
    "kingdom_equestria": (232, 181, 58),
    "kingdom_lunar": (70, 70, 150),
    "kingdom_friendship": (150, 80, 190),
    "kingdom_crystal": (110, 200, 220),
    "kingdom_changeling": (40, 90, 70),
    "kingdom_griffonia": (200, 120, 50),
    "kingdom_yakyakistan": (150, 120, 100),
    "kingdom_hippogriffia": (80, 180, 160),
    "kingdom_olenia": (210, 90, 90),
    "kingdom_dragons": (190, 60, 40),
}
SHORT = {
    "kingdom_equestria": "Солнечная", "kingdom_lunar": "Лунная", "kingdom_friendship": "Дружбы",
    "kingdom_crystal": "Кристальная", "kingdom_changeling": "Ульи", "kingdom_griffonia": "Грифония",
    "kingdom_yakyakistan": "Якьякистан", "kingdom_hippogriffia": "Гиппогриффия",
    "kingdom_olenia": "Оления", "kingdom_dragons": "Драконы",
}


def kind_of(s):
    comp = s.find("Components")
    if comp is None:
        return None
    if comp.find("Village") is not None:
        return "village"
    if comp.find("Hideout") is not None:
        return "hideout"
    town = comp.find("Town")
    if town is not None:
        return "castle" if town.get("is_castle") == "true" else "town"
    return None


def load():
    clans = {}
    for clan in ET.parse(os.path.join(MOD, "ModuleData", "equestria_clans.xml")).getroot().iter("Faction"):
        clans[clan.get("id")] = (clan.get("super_faction") or "").replace("Kingdom.", "")
    raw, bound = [], {}
    for s in ET.parse(os.path.join(MOD, "ModuleData", "equestria_settlements.xml")).getroot():
        kind = kind_of(s)
        if kind in (None, "hideout") or s.get("posX") is None:
            continue
        village = s.find("Components/Village")
        if village is not None:
            bound[s.get("id")] = (village.get("bound") or "").replace("Settlement.", "")
        raw.append([s.get("id"), kind, float(s.get("posX")), float(s.get("posY")),
                    (s.get("owner") or "").replace("Faction.", ""), s.get("name") or ""])
    owners = {r[0]: r[4] for r in raw}
    out = []
    for sid, kind, x, y, owner, name in raw:
        if not owner and sid in bound:
            owner = owners.get(bound[sid], "")
        kingdom = clans.get(owner, "")
        if kingdom:
            out.append((kind, x, y, kingdom, name.split("}")[-1]))
    return out


def draw(points, path):
    size = 1024
    land = equus_map.land_map() & (equus_map.heights() > 0.4)
    n = land.shape[0]
    idx = (np.linspace(0, n - 1, size)).round().astype(int)
    land = land[np.ix_(idx, idx)][::-1]        # row 0 is north, as in the picture
    img = np.zeros((size, size, 3), np.uint8)
    img[:] = (40, 60, 90)
    img[land] = (70, 80, 70)

    p = np.array([[x, y] for _k, x, y, _o, _n in points], np.float32)
    colors = np.array([KINGDOM_COLOR.get(o, (128, 128, 128)) for _k, _x, _y, o, _n in points], np.float32)
    step = equus_map.MAP_SIZE / (size - 1)
    ys, xs = np.nonzero(land)
    wx = xs * step
    wy = (size - 1 - ys) * step
    # nearest settlement for each land point - in chunks so as not to eat all the memory
    owner_idx = np.empty(len(xs), np.int32)
    for start in range(0, len(xs), 20000):
        sl = slice(start, start + 20000)
        d = np.hypot(wx[sl, None] - p[None, :, 0], wy[sl, None] - p[None, :, 1])
        owner_idx[sl] = d.argmin(1)
    tint = colors[owner_idx]
    img[ys, xs] = (img[ys, xs] * 0.45 + tint * 0.55).astype(np.uint8)

    pic = Image.fromarray(img)
    d = ImageDraw.Draw(pic)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
    except OSError:
        font = None
    marker = {"town": 5, "castle": 3, "village": 1}
    for kind, x, y, owner, _name in points:
        px, py = x / step, size - 1 - y / step
        r = marker[kind]
        color = KINGDOM_COLOR.get(owner, (128, 128, 128))
        d.rectangle([px - r, py - r, px + r, py + r], fill=(255, 255, 255) if kind == "town" else color,
                    outline=(0, 0, 0) if kind != "village" else None)
    # kingdom labels
    centers = collections.defaultdict(list)
    for kind, x, y, owner, _name in points:
        centers[owner].append((x, y))
    counts = collections.Counter((o, k) for k, _x, _y, o, _n in points)
    for owner, pts in centers.items():
        cx = sum(q[0] for q in pts) / len(pts)
        cy = sum(q[1] for q in pts) / len(pts)
        label = "%s %d/%d/%d" % (SHORT.get(owner, owner), counts[(owner, "town")],
                                 counts[(owner, "castle")], counts[(owner, "village")])
        d.text((cx / step - 40, size - 1 - cy / step), label, fill=(255, 255, 255), font=font,
               stroke_width=2, stroke_fill=(0, 0, 0))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pic.save(path)
    print("написано", path)


draw(load(), OUT)
