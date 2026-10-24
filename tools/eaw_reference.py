# Разбор карты Equestria at War (мод Hearts of Iron IV) как референса для нашей карты мира.
#
#   py -3 tools\eaw_reference.py [страна EQS] [папка вывода]
#
# Читает из мода:
#   map/provinces.bmp + definition.csv — какая провинция где (цвет -> id);
#   history/states/*.txt               — области: владелец, провинции, victory_points (города);
#   localisation/russian/*.yml         — русские названия областей и городов;
#   map/heightmap.bmp, terrain.bmp, rivers.bmp — рельеф, типы местности, реки.
# Пишет:
#   <вывод>/eaw_<страна>.json — рамка страны на карте HOI4, её области и города с координатами;
#   <вывод>/eaw_<страна>_preview.png — рельеф и местность с границей страны и подписанными городами.
#
# Звуки, картинки и данные Equestria at War принадлежат её авторам — используем только как
# справочник для расстановки, в мод их не кладём.
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

EAW = r"C:\SteamLibrary\steamapps\workshop\content\394360\1826643372"
TAG = sys.argv[1] if len(sys.argv) > 1 else "EQS"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "reference")
MARGIN = 60  # пикселей карты HOI4 вокруг страны


def log(*a):
    print("[eaw]", *a, flush=True)


def read_localisation():
    names = {}
    pattern = re.compile(r'^\s*([A-Za-z0-9_.]+):\d*\s*"(.*)"\s*$')
    for path in glob.glob(os.path.join(EAW, "localisation", "russian", "**", "*.yml"), recursive=True):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    names.setdefault(m.group(1), m.group(2))
    return names


def read_states():
    states = []
    for path in glob.glob(os.path.join(EAW, "history", "states", "*.txt")):
        text = open(path, encoding="utf-8-sig", errors="replace").read()
        text = re.sub(r"#.*", "", text)
        sid = re.search(r"\bid\s*=\s*(\d+)", text)
        owner = re.search(r"\bowner\s*=\s*(\w+)", text)
        provinces = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", text)
        if not (sid and owner and provinces):
            continue
        vps = [(int(p), float(v)) for p, v in re.findall(r"victory_points\s*=\s*\{\s*(\d+)\s+([\d.]+)\s*\}", text)]
        states.append({
            "id": int(sid.group(1)),
            "name_key": (re.search(r'\bname\s*=\s*"([^"]+)"', text) or [None, None])[1],
            "file": os.path.basename(path),
            "owner": owner.group(1),
            "provinces": [int(x) for x in provinces.group(1).split()],
            "victory_points": vps,
            "category": (re.search(r"state_category\s*=\s*(\w+)", text) or [None, None])[1],
        })
    return states


def province_map():
    colors = {}
    with open(os.path.join(EAW, "map", "definition.csv"), encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) >= 7 and parts[0].isdigit():
                pid, r, g, b = map(int, parts[:4])
                colors[(r << 16) | (g << 8) | b] = (pid, parts[4], parts[6])
    rgb = np.asarray(Image.open(os.path.join(EAW, "map", "provinces.bmp")).convert("RGB"), dtype=np.int32)
    key = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
    ids = np.zeros(key.shape, dtype=np.int32)
    for k in np.unique(key):
        ids[key == k] = colors.get(int(k), (0, "", ""))[0]
    kinds = {pid: (kind, terrain) for pid, kind, terrain in colors.values()}
    return ids, kinds


def main():
    os.makedirs(OUT, exist_ok=True)
    names = read_localisation()
    states = [s for s in read_states() if s["owner"] == TAG]
    log(f"областей у {TAG}: {len(states)}")
    ids, kinds = province_map()
    height = np.asarray(Image.open(os.path.join(EAW, "map", "heightmap.bmp")))
    terrain = Image.open(os.path.join(EAW, "map", "terrain.bmp")).convert("RGB")
    rivers = Image.open(os.path.join(EAW, "map", "rivers.bmp"))

    own = np.isin(ids, [p for s in states for p in s["provinces"]])
    ys, xs = np.nonzero(own)
    x0, x1 = max(xs.min() - MARGIN, 0), min(xs.max() + MARGIN, ids.shape[1] - 1)
    y0, y1 = max(ys.min() - MARGIN, 0), min(ys.max() + MARGIN, ids.shape[0] - 1)
    log(f"рамка на карте HOI4: x {x0}..{x1}, y {y0}..{y1} ({x1 - x0}x{y1 - y0} пикс.)")

    # Центр провинции — среднее её пикселей. Карта HOI4 хранится снизу вверх (y=0 — юг),
    # а картинка сверху вниз: переворачиваем при записи «юг-север» координат.
    def centre(pid):
        py, px = np.nonzero(ids == pid)
        return float(px.mean()), float(py.mean())

    cities = []
    regions = []
    for s in states:
        sname = names.get(s["name_key"] or "", s["name_key"])
        pts = np.isin(ids, s["provinces"])
        py, px = np.nonzero(pts)
        regions.append({"id": s["id"], "name": sname, "category": s["category"],
                        "centre": [float(px.mean()), float(py.mean())],
                        "provinces": len(s["provinces"])})
        for pid, value in s["victory_points"]:
            cx, cy = centre(pid)
            cities.append({"name": names.get(f"VICTORY_POINTS_{pid}", f"VP {pid}"),
                           "province": pid, "value": value, "state": sname,
                           "x": cx, "y": cy, "terrain": kinds.get(pid, ("", ""))[1]})
    cities.sort(key=lambda c: -c["value"])
    data = {"tag": TAG, "frame": [int(x0), int(y0), int(x1), int(y1)],
            "hoi4_size": [int(ids.shape[1]), int(ids.shape[0])],
            "regions": regions, "cities": cities}
    json_path = os.path.join(OUT, f"eaw_{TAG}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    log(f"городов: {len(cities)}; записан {json_path}")

    # превью: местность, затемнённая по высоте, граница страны, реки, города
    box = (int(x0), int(y0), int(x1), int(y1))
    img = terrain.crop(box)
    h = height[y0:y1, x0:x1].astype(np.float32) / 255.0
    shade = np.asarray(img, dtype=np.float32) * (0.45 + 0.75 * h[..., None])
    img = Image.fromarray(np.clip(shade, 0, 255).astype(np.uint8))
    riv = np.asarray(rivers.crop(box))
    arr = np.asarray(img).copy()
    arr[(riv < 250)] = (40, 90, 220)
    edge = own[y0:y1, x0:x1]
    border = edge ^ np.roll(edge, 1, 0) | edge ^ np.roll(edge, 1, 1)
    arr[border] = (255, 40, 40)
    img = Image.fromarray(arr)
    scale = max(1, 1600 // img.width)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for c in cities:
        px, py = (c["x"] - x0) * scale, (c["y"] - y0) * scale
        r = 3 + int(c["value"] // 5)
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 0), outline=(0, 0, 0))
        draw.text((px + r + 2, py - 7), f'{c["name"]} ({c["value"]:g})', fill=(255, 255, 255),
                  font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    preview = os.path.join(OUT, f"eaw_{TAG}_preview.png")
    img.save(preview)
    log(f"превью {img.size}: {preview}")


if __name__ == "__main__":
    main()
