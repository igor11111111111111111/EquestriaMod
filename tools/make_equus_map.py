# Карта мира Эквуса по референсу Equestria at War.
#
#   py -3 tools\make_equus_map.py [папка вывода]
#
# Вырезает материк Эквуса из карт мода (Hearts of Iron IV) и пересчитывает его в нашу карту
# MAP_SIZE x MAP_SIZE метров (рельеф 16x16 узлов по 64 м, как у ванильной карты, только крупнее):
#   eq_map_heightmap.png  — 16 бит, (NODES*64+1)^2 отсчётов; для кнопки Import HeightMap в редакторе
#   eq_map_land.png       — суша (белое) / вода (чёрное)
#   eq_map_terrain.png    — тип местности по палитре TERRAIN (см. ниже), для раскраски и сетки
#   eq_map_owner.png      — индекс владельца по списку owners в json
#   eq_map_preview.png    — всё вместе, с городами
#   eq_map.json           — масштаб, высоты, владельцы, города (в метрах нашей карты)
#
# Данные Equestria at War принадлежат её авторам: используем их только как справочник формы
# материка и расположения городов, сами файлы мода в наш мод не кладём.
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eaw_reference as ref  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "map")

NODES = 16                  # узлов рельефа по стороне
NODE_SIZE = 64.0            # метров в узле
MAP_SIZE = NODES * NODE_SIZE
SAMPLES = NODES * 64 + 1    # отсчётов высоты по стороне

# Участок карты HOI4 (пиксели): материк Эквуса с Летними островами.
FRAME = (190, 0, 1290, 1100)

# Высоты нашей карты, метры: дно моря и самые высокие горы. У ванильной карты дно всего
# около -0,7 м: при -3 м берег выходил отвесной стеной.
SEA_FLOOR = -1.0        # дно у самого берега
DEEP_FLOOR = -3.0       # дно открытого моря (низ шкалы высот)
DEPTH_REACH = 24        # за сколько метров от берега дно уходит на глубину (радиус сглаживания)
# Классы рек в rivers.bmp Equestria at War: 3 — ручьи, 6 — реки, 11 — крупные реки.
# Ручьи не рисуем: при масштабе карты они сплошь покрывали сушу голубой сеткой.
RIVER_CLASSES = (6, 11)
COAST = 0.4
PEAK = 32.0
SHORE_BLUR = 3   # радиус сглаживания рельефа, м — берег становится пологим склоном
# Шкала записи высот (рельеф в редакторе создан с этими границами, менять только вместе с ним)
SCALE_MIN, SCALE_MAX = -3.0, 32.0
# Рельеф суши. Раньше по всей суше сыпался равномерный шум ±0.4 м — карта выходила одинаково
# бугристой (нужен был выбор граней навсетки в редакторе, но типы граней мы теперь пишем кодом,
# tools/tag_navmesh.py). Вместо него: пологие широкие волны, редкие холмы и почти ровные полянки.
BUMPS = 0.06     # остаточная мелкая неровность, м — чтобы земля не выглядела стеклянной
ROLL_SCALE = 110   # длина волны пологих всхолмлений, м
ROLL_AMPL = 1.1    # их размах, м
HILL_SCALE = 44    # размер редких холмов, м
HILL_HEIGHT = 5.0  # высота холмов, м
HILL_RARITY = 2.6  # чем больше, тем реже холмы (степень отсечки шума)
GLADE_SCALE = 70   # размер ровных полянок, м
GLADE_FLAT = 0.75  # насколько сильно полянки приглаживают рельеф (0..1)
MOUNTAIN_FROM = 12.0  # выше этой высоты рельеф не трогаем — горы получились хорошо
RIVER_DEPTH = 1.0  # насколько русло ниже берегов, м
RIVER_WIDTH = 4    # радиус размытия русла, м

# Типы местности провинций HOI4 -> наш тип (номер = TaleWorlds.Core.TerrainType)
TERRAIN = {
    "plains": 1, "urban": 1, "farmlands": 1,
    "desert": 2, "arctic": 3, "snow": 3,
    "forest": 4, "jungle": 4,
    "hills": 5,          # степь/холмы — в Bannerlord это Steppe, проходимо
    "mountain": 7,
    "marsh": 15,
    "ocean": 10, "lakes": 8, "water_fjords": 10, "water_shallow_sea": 10, "water_deep_ocean": 10,
}
TERRAIN_COLORS = {0: (0, 0, 0), 1: (120, 170, 80), 2: (220, 200, 120), 3: (240, 240, 250),
                  4: (40, 110, 40), 5: (170, 160, 90), 7: (120, 110, 100), 8: (60, 120, 200),
                  10: (20, 50, 120), 15: (80, 120, 100)}

# Наши державы в EaW: тег -> id королевства в world_data (остальные — ничьи земли)
OWNERS = ["EQS", "CRY", "STG", "YAK", "CHN", "OLE", "PLB", "GRF", "DRG", "JAK", "GFF", "PNG", "BUF", "STL"]


def log(*a):
    print("[equus]", *a, flush=True)


def box_blur(field, radius):
    """Среднее по квадрату (2r+1)^2 через накопленные суммы."""
    k = 2 * radius + 1
    pad = np.pad(field.astype(np.float64), radius, mode="edge")
    c = np.pad(np.cumsum(np.cumsum(pad, 0), 1), ((1, 0), (1, 0)))
    return ((c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)).astype(np.float32)


def to_map(x, y):
    """Пиксель HOI4 -> метры нашей карты. Картинка идёт сверху вниз, а наша ось Y — на север."""
    fx0, fy0, fx1, fy1 = FRAME
    mx = (x - fx0) / (fx1 - fx0) * MAP_SIZE
    my = (1.0 - (y - fy0) / (fy1 - fy0)) * MAP_SIZE
    return round(float(mx), 1), round(float(my), 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    fx0, fy0, fx1, fy1 = FRAME
    ids, kinds = ref.province_map()
    states = ref.read_states()
    names = ref.read_localisation()
    ids = ids[fy0:fy1, fx0:fx1]

    # суша и тип местности по провинциям
    maxid = int(ids.max()) + 1
    is_land = np.zeros(maxid, dtype=bool)
    ttype = np.zeros(maxid, dtype=np.uint8)
    for pid, (kind, terrain) in kinds.items():
        if pid < maxid:
            is_land[pid] = kind == "land"
            ttype[pid] = TERRAIN.get(terrain, 10 if kind == "sea" else 1)
    land = is_land[ids]
    terrain = ttype[ids]
    terrain[~land & (terrain != 8)] = 10

    # владельцы
    owner_idx = np.zeros(maxid, dtype=np.uint8)
    for s in states:
        if s["owner"] in OWNERS:
            for p in s["provinces"]:
                if p < maxid:
                    owner_idx[p] = OWNERS.index(s["owner"]) + 1
    owner = owner_idx[ids]

    # высоты: над морем — от уровня берега до пика, под водой — дно
    hmap = np.asarray(Image.open(os.path.join(ref.EAW, "map", "heightmap.bmp")), dtype=np.float32)
    hmap = hmap[fy0:fy1, fx0:fx1]
    sea_level = float(np.percentile(hmap[land], 1))
    top = float(np.percentile(hmap[land], 99.9))
    log(f"уровень моря в HOI4 ~{sea_level:.0f}, вершины ~{top:.0f}")
    up = np.clip((hmap - sea_level) / max(top - sea_level, 1), 0, 1)
    meters = np.where(land, COAST + up ** 1.3 * (PEAK - COAST), DEEP_FLOOR)

    # реки прорезаем чуть ниже окружающей земли
    rivers = np.asarray(Image.open(os.path.join(ref.EAW, "map", "rivers.bmp")))[fy0:fy1, fx0:fx1]
    river = np.isin(rivers, RIVER_CLASSES) & land
    log(f"рек (кл. {RIVER_CLASSES}) пикселей: {int(river.sum())}, ручьёв пропущено: {int(((rivers == 3) & land).sum())}")
    meters = np.where(river, np.maximum(meters - 1.2, 0.1), meters)
    terrain[river] = 11  # River — в Bannerlord непроходимо без брода

    # сглаживаем и пересчитываем в сетку отсчётов
    img = Image.fromarray(meters.astype(np.float32), mode="F").resize((SAMPLES, SAMPLES), Image.BILINEAR)
    smooth = np.asarray(img).copy()
    smooth = box_blur(box_blur(smooth, SHORE_BLUR), SHORE_BLUR)
    under = smooth < COAST - 0.05
    # Глубина: у берега мелко (SEA_FLOOR), дальше дно плавно уходит к DEEP_FLOOR. По глубине
    # paint_terrain.py смешивает светлую и тёмную воду.
    near = box_blur(box_blur((~under).astype(np.float32), DEPTH_REACH), DEPTH_REACH)
    deep = np.clip(1.0 - near * 5.0, 0.0, 1.0) ** 0.7
    floor = SEA_FLOOR + (DEEP_FLOOR - SEA_FLOOR) * deep
    smooth = np.where(under, np.maximum(smooth, floor), smooth)

    # Рельеф суши: пологие волны + редкие холмы + ровные полянки. Горы (выше MOUNTAIN_FROM)
    # оставляем как есть. Мелкий шум почти убран — он делал всю карту одинаково бугристой.
    rng = np.random.default_rng(20260918)

    def wave(scale):
        """Плавный шум с заданной длиной волны: мелкая случайная сетка, растянутая по-бикубически."""
        side = max(4, int(round(smooth.shape[0] / max(scale, 1))))
        small = rng.normal(0.0, 1.0, (side, side)).astype(np.float32)
        img = Image.fromarray(small, mode="F").resize(smooth.shape[::-1], Image.BICUBIC)
        field = np.asarray(img, dtype=np.float32)
        return field / max(float(field.std()), 1e-6)

    shore = np.clip((smooth - SEA_FLOOR) / (COAST - SEA_FLOOR), 0.0, 1.0)
    lowland = np.clip((MOUNTAIN_FROM - smooth) / MOUNTAIN_FROM, 0.0, 1.0)  # к горам сходит на нет

    rolling = wave(ROLL_SCALE) * ROLL_AMPL
    hills = np.clip(wave(HILL_SCALE), 0.0, None) ** HILL_RARITY
    hills *= HILL_HEIGHT / max(float(hills.max()), 1e-6)
    glade = np.clip(wave(GLADE_SCALE), 0.0, None)
    glade = glade / max(float(glade.max()), 1e-6)          # 0 — обычный рельеф, 1 — ровная поляна
    smooth_flat = box_blur(box_blur(smooth, 12), 12)        # каким рельеф был бы без мелочей

    bumps = rng.normal(0.0, 1.0, smooth.shape).astype(np.float32)
    bumps = (bumps + np.roll(bumps, 1, 0) + np.roll(bumps, 1, 1) + np.roll(bumps, (1, 1), (0, 1))) / 4
    bumps *= BUMPS / max(float(bumps.std()), 1e-6)

    relief = (rolling + hills) * lowland + bumps
    land_now = shore * lowland
    smooth = smooth + (smooth_flat - smooth) * (GLADE_FLAT * glade * land_now)  # полянки
    smooth = smooth + relief * shore

    # Русла рек прорезаем ПОСЛЕ сглаживания: до него канава шириной в пиксель исчезала в размытии.
    river_big = Image.fromarray(river.astype(np.float32), mode="F").resize(smooth.shape[::-1], Image.BILINEAR)
    channel = box_blur(np.asarray(river_big, dtype=np.float32), RIVER_WIDTH)
    channel = channel / max(float(channel.max()), 1e-6)
    smooth = smooth - channel * RIVER_DEPTH * shore

    smooth = np.clip(smooth, DEEP_FLOOR, PEAK)

    # Высоты пишем в постоянной шкале SCALE_MIN..SCALE_MAX — как у рельефа сцены
    # (при импорте в редакторе: Scale = SCALE_MAX - SCALE_MIN, Offset = SCALE_MIN).
    lo, hi = SCALE_MIN, SCALE_MAX
    png16 = np.rint((smooth - lo) / (hi - lo) * 65535).astype(np.uint16)
    Image.fromarray(png16).save(os.path.join(OUT, "eq_map_heightmap.png"))

    def save_index(arr, name, size=SAMPLES):
        Image.fromarray(arr.astype(np.uint8)).resize((size, size), Image.NEAREST).save(os.path.join(OUT, name))

    save_index(land * 255, "eq_map_land.png")
    save_index(terrain, "eq_map_terrain.png")
    save_index(owner, "eq_map_owner.png")

    # города всех наших стран, с координатами в метрах
    cities = []
    ids_full, _ = ids, None
    for s in states:
        if s["owner"] not in OWNERS:
            continue
        for pid, value in s["victory_points"]:
            py, px = np.nonzero(ids == pid)
            if len(px) == 0:
                continue
            mx, my = to_map(px.mean() + fx0, py.mean() + fy0)
            cities.append({"name": names.get(f"VICTORY_POINTS_{pid}", f"VP {pid}"),
                           "owner": s["owner"], "value": value,
                           "state": names.get(s["name_key"] or "", s["name_key"]),
                           "x": mx, "y": my,
                           "terrain": kinds.get(pid, ("", ""))[1]})
    cities.sort(key=lambda c: (-c["value"], c["name"]))
    data = {"frame_hoi4": FRAME, "map_size": MAP_SIZE, "nodes": NODES, "node_size": NODE_SIZE,
            "samples": SAMPLES, "min_height": round(lo, 3), "max_height": round(hi, 3),
            "terrain_types": {str(k): v for k, v in TERRAIN.items()},
            "owners": OWNERS, "cities": cities}
    with open(os.path.join(OUT, "eq_map.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    log(f"высоты {lo:.1f}..{hi:.1f} м; суши {land.mean() * 100:.0f}%; городов {len(cities)}")

    # превью
    pal = np.zeros((256, 3), dtype=np.uint8)
    for k, c in TERRAIN_COLORS.items():
        pal[k] = c
    pal[11] = (60, 120, 220)
    shade = pal[terrain].astype(np.float32) * (0.6 + 0.5 * up[..., None])
    prev = Image.fromarray(np.clip(shade, 0, 255).astype(np.uint8)).resize((1100, 1100), Image.NEAREST)
    arr = np.asarray(prev).copy()
    o = np.asarray(Image.fromarray(owner).resize((1100, 1100), Image.NEAREST))
    border = (o != np.roll(o, 1, 0)) | (o != np.roll(o, 1, 1))
    arr[border & (o > 0)] = (255, 60, 60)
    prev = Image.fromarray(arr)
    draw = ImageDraw.Draw(prev)
    font = ImageFont.truetype("arial.ttf", 12)
    k = 1100 / MAP_SIZE
    for c in cities:
        if c["value"] < 5:
            continue
        px, py = c["x"] * k, (MAP_SIZE - c["y"]) * k
        r = 2 + int(c["value"] // 10)
        draw.ellipse((px - r, py - r, px + r, py + r), fill=(255, 255, 0), outline=(0, 0, 0))
        if c["value"] >= 10:
            draw.text((px + r + 2, py - 7), c["name"], fill=(255, 255, 255), font=font,
                      stroke_width=2, stroke_fill=(0, 0, 0))
    prev.save(os.path.join(OUT, "eq_map_preview.png"))
    log("записано в", OUT)


if __name__ == "__main__":
    main()
