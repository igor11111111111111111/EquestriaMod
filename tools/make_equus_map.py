# World map of Equus based on the Equestria at War reference.
#
#   py -3 tools\make_equus_map.py [output folder]
#
# Cuts the Equus continent out of the mod's maps (Hearts of Iron IV) and converts it into our map of
# MAP_SIZE x MAP_SIZE metres (terrain of 16x16 nodes of 64 m, like the vanilla map, only larger):
#   eq_map_heightmap.png  - 16 bit, (NODES*64+1)^2 samples; for the Import HeightMap button in the editor
#   eq_map_land.png       - land (white) / water (black)
#   eq_map_terrain.png    - terrain type by the TERRAIN palette (see below), for painting and the grid
#   eq_map_owner.png      - owner index by the owners list in the json
#   eq_map_preview.png    - everything together, with cities
#   eq_map.json           - scale, heights, owners, cities (in metres of our map)
#
# The Equestria at War data belongs to its authors: we use it only as a reference for the shape of
# the continent and the city locations; the mod's files themselves are not put into our mod.
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eaw_reference as ref  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "map")

NODES = 16                  # terrain nodes per side
NODE_SIZE = 64.0            # metres per node
MAP_SIZE = NODES * NODE_SIZE
SAMPLES = NODES * 64 + 1    # height samples per side

# The HOI4 map region (pixels): the Equus continent with the Summer Islands.
FRAME = (190, 0, 1290, 1100)

# Heights of our map, metres: the sea floor and the highest mountains. The vanilla map's floor is only
# about -0.7 m: at -3 m the shore came out as a sheer wall.
SEA_FLOOR = -1.0        # the floor right by the shore
DEEP_FLOOR = -3.0       # the open sea floor (bottom of the height scale)
DEPTH_REACH = 24        # over how many metres from the shore the floor goes deep (smoothing radius)
# River classes in Equestria at War rivers.bmp: 3 = streams, 6 = rivers, 11 = large rivers.
# Streams are not drawn: at the map's scale they covered the land with a solid blue mesh.
RIVER_CLASSES = (6, 11)
COAST = 0.4
PEAK = 32.0
SHORE_BLUR = 3   # terrain smoothing radius, m: the shore becomes a gentle slope
# Height recording scale (the terrain in the editor was created with these bounds, change only together with it)
SCALE_MIN, SCALE_MAX = -3.0, 32.0
# Land relief. Previously a uniform ±0.4 m noise was sprinkled over all the land, and the map came out uniformly
# bumpy (it required selecting navmesh faces in the editor, but we now write face types in code,
# tools/tag_navmesh.py). Instead: gentle wide waves, rare hills and almost flat glades.
BUMPS = 0.06     # residual fine unevenness, m, so that the ground does not look like glass
ROLL_SCALE = 110   # wavelength of the gentle undulations, m
ROLL_AMPL = 1.1    # their amplitude, m
HILL_SCALE = 44    # size of the rare hills, m
HILL_HEIGHT = 5.0  # hill height, m
HILL_RARITY = 2.6  # the larger, the rarer the hills (noise cutoff exponent)
GLADE_SCALE = 70   # size of the flat glades, m
GLADE_FLAT = 0.75  # how strongly the glades flatten the relief (0..1)
MOUNTAIN_FROM = 12.0  # above this height the relief is not touched: the mountains turned out well
RIVER_DEPTH = 1.0  # how much lower the riverbed is than the banks, m
RIVER_WIDTH = 4    # riverbed blur radius, m

# HOI4 province terrain types -> our type (number = TaleWorlds.Core.TerrainType)
TERRAIN = {
    "plains": 1, "urban": 1, "farmlands": 1,
    "desert": 2, "arctic": 3, "snow": 3,
    "forest": 4, "jungle": 4,
    "hills": 5,          # steppe/hills: in Bannerlord this is Steppe, passable
    "mountain": 7,
    "marsh": 15,
    "ocean": 10, "lakes": 8, "water_fjords": 10, "water_shallow_sea": 10, "water_deep_ocean": 10,
}
TERRAIN_COLORS = {0: (0, 0, 0), 1: (120, 170, 80), 2: (220, 200, 120), 3: (240, 240, 250),
                  4: (40, 110, 40), 5: (170, 160, 90), 7: (120, 110, 100), 8: (60, 120, 200),
                  10: (20, 50, 120), 15: (80, 120, 100)}

# Our realms in EaW: tag -> kingdom id in world_data (the rest are no-man's lands)
OWNERS = ["EQS", "CRY", "STG", "YAK", "CHN", "OLE", "PLB", "GRF", "DRG", "JAK", "GFF", "PNG", "BUF", "STL"]


def log(*a):
    print("[equus]", *a, flush=True)


def box_blur(field, radius):
    """Mean over a (2r+1)^2 square via cumulative sums."""
    k = 2 * radius + 1
    pad = np.pad(field.astype(np.float64), radius, mode="edge")
    c = np.pad(np.cumsum(np.cumsum(pad, 0), 1), ((1, 0), (1, 0)))
    return ((c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)).astype(np.float32)


def to_map(x, y):
    """HOI4 pixel -> metres of our map. The image goes top to bottom, while our Y axis points north."""
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

    # land and terrain type by province
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

    # owners
    owner_idx = np.zeros(maxid, dtype=np.uint8)
    for s in states:
        if s["owner"] in OWNERS:
            for p in s["provinces"]:
                if p < maxid:
                    owner_idx[p] = OWNERS.index(s["owner"]) + 1
    owner = owner_idx[ids]

    # heights: above the sea, from the shore level to the peak; under water, the floor
    hmap = np.asarray(Image.open(os.path.join(ref.EAW, "map", "heightmap.bmp")), dtype=np.float32)
    hmap = hmap[fy0:fy1, fx0:fx1]
    sea_level = float(np.percentile(hmap[land], 1))
    top = float(np.percentile(hmap[land], 99.9))
    log(f"уровень моря в HOI4 ~{sea_level:.0f}, вершины ~{top:.0f}")
    up = np.clip((hmap - sea_level) / max(top - sea_level, 1), 0, 1)
    meters = np.where(land, COAST + up ** 1.3 * (PEAK - COAST), DEEP_FLOOR)

    # rivers are cut slightly below the surrounding land
    rivers = np.asarray(Image.open(os.path.join(ref.EAW, "map", "rivers.bmp")))[fy0:fy1, fx0:fx1]
    river = np.isin(rivers, RIVER_CLASSES) & land
    log(f"рек (кл. {RIVER_CLASSES}) пикселей: {int(river.sum())}, ручьёв пропущено: {int(((rivers == 3) & land).sum())}")
    meters = np.where(river, np.maximum(meters - 1.2, 0.1), meters)
    terrain[river] = 11  # River: impassable in Bannerlord without a ford

    # smooth and convert into the sample grid
    img = Image.fromarray(meters.astype(np.float32), mode="F").resize((SAMPLES, SAMPLES), Image.BILINEAR)
    smooth = np.asarray(img).copy()
    smooth = box_blur(box_blur(smooth, SHORE_BLUR), SHORE_BLUR)
    under = smooth < COAST - 0.05
    # Depth: shallow by the shore (SEA_FLOOR), farther out the floor smoothly goes down to DEEP_FLOOR. By depth
    # paint_terrain.py blends light and dark water.
    near = box_blur(box_blur((~under).astype(np.float32), DEPTH_REACH), DEPTH_REACH)
    deep = np.clip(1.0 - near * 5.0, 0.0, 1.0) ** 0.7
    floor = SEA_FLOOR + (DEEP_FLOOR - SEA_FLOOR) * deep
    smooth = np.where(under, np.maximum(smooth, floor), smooth)

    # Land relief: gentle waves + rare hills + flat glades. The mountains (above MOUNTAIN_FROM)
    # are left as they are. The fine noise is almost removed: it made the whole map uniformly bumpy.
    rng = np.random.default_rng(20260918)

    def wave(scale):
        """Smooth noise with a given wavelength: a small random grid stretched bicubically."""
        side = max(4, int(round(smooth.shape[0] / max(scale, 1))))
        small = rng.normal(0.0, 1.0, (side, side)).astype(np.float32)
        img = Image.fromarray(small, mode="F").resize(smooth.shape[::-1], Image.BICUBIC)
        field = np.asarray(img, dtype=np.float32)
        return field / max(float(field.std()), 1e-6)

    shore = np.clip((smooth - SEA_FLOOR) / (COAST - SEA_FLOOR), 0.0, 1.0)
    lowland = np.clip((MOUNTAIN_FROM - smooth) / MOUNTAIN_FROM, 0.0, 1.0)  # fades out towards the mountains

    rolling = wave(ROLL_SCALE) * ROLL_AMPL
    hills = np.clip(wave(HILL_SCALE), 0.0, None) ** HILL_RARITY
    hills *= HILL_HEIGHT / max(float(hills.max()), 1e-6)
    glade = np.clip(wave(GLADE_SCALE), 0.0, None)
    glade = glade / max(float(glade.max()), 1e-6)          # 0 = regular relief, 1 = flat glade
    smooth_flat = box_blur(box_blur(smooth, 12), 12)        # what the relief would be without the small details

    bumps = rng.normal(0.0, 1.0, smooth.shape).astype(np.float32)
    bumps = (bumps + np.roll(bumps, 1, 0) + np.roll(bumps, 1, 1) + np.roll(bumps, (1, 1), (0, 1))) / 4
    bumps *= BUMPS / max(float(bumps.std()), 1e-6)

    relief = (rolling + hills) * lowland + bumps
    land_now = shore * lowland
    smooth = smooth + (smooth_flat - smooth) * (GLADE_FLAT * glade * land_now)  # glades
    smooth = smooth + relief * shore

    # River beds are cut AFTER smoothing: before it, a one-pixel-wide ditch disappeared in the blur.
    river_big = Image.fromarray(river.astype(np.float32), mode="F").resize(smooth.shape[::-1], Image.BILINEAR)
    channel = box_blur(np.asarray(river_big, dtype=np.float32), RIVER_WIDTH)
    channel = channel / max(float(channel.max()), 1e-6)
    smooth = smooth - channel * RIVER_DEPTH * shore

    smooth = np.clip(smooth, DEEP_FLOOR, PEAK)

    # Heights are written in the constant SCALE_MIN..SCALE_MAX scale, as for the scene terrain
    # (on import in the editor: Scale = SCALE_MAX - SCALE_MIN, Offset = SCALE_MIN).
    lo, hi = SCALE_MIN, SCALE_MAX
    png16 = np.rint((smooth - lo) / (hi - lo) * 65535).astype(np.uint16)
    Image.fromarray(png16).save(os.path.join(OUT, "eq_map_heightmap.png"))

    def save_index(arr, name, size=SAMPLES):
        Image.fromarray(arr.astype(np.uint8)).resize((size, size), Image.NEAREST).save(os.path.join(OUT, name))

    save_index(land * 255, "eq_map_land.png")
    save_index(terrain, "eq_map_terrain.png")
    save_index(owner, "eq_map_owner.png")

    # cities of all our countries, with coordinates in metres
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

    # preview
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
