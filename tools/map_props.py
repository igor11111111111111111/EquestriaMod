# Environment props on the world map: boulders, rocks, single trees, groves, fallen trunks.
#
# Our map had only settlements: the land between towns looked empty, especially on the
# plains. Trees on the map grow from the terrain's vegetation layers (see paint_terrain.py) and
# cover only the forest; everything else is a bare texture. Here we add ordinary scene entities
# with world-map meshes (map_rock_*, map_tree_*, log_*), the way vanilla does.
#
# IMPORTANT: worldmap_tree_* meshes do not fit here, even though they look like map trees. They are
# terrain-layer flora: inside are TWO objects at one level of detail (worldmap_tree_beech_01.0.lod0
# and .1.lod0), the engine sows them itself at size 0.19..0.27 (see <meshes> in the layers of vanilla Main_map).
# Placed as separate entities at a scale of about 1.0, they came out four times larger than
# a normal tree and flickered: the leaf planes of both objects fight for depth
# (seen in game 2026-09-22). Ordinary props have their levels in order: lod0, lod1.
#
# The layout is tied to the terrain type from assets/map/eq_map_terrain.png and to the slope steepness:
# in the mountains rocks and blocks, in the forest deadwood and stones, on the plain groves and lone trees,
# in the steppe sparse stones and acacias, in the desert palms, in the swamp snags, by rivers willows and stones.
# Above the snow line (SNOW_LINE) stones are replaced by snowy variants, trees are not placed.
#
# The module is called from make_map_entities.py: place(entities, settlements, log).
import math
import os
import random
import xml.etree.ElementTree as ET

import numpy as np

import equus_map

# Overall density: 1.0 is as configured below, 2.0 is twice as many props.
DENSITY = float(os.environ.get("EQ_PROPS", "1.0"))
SEED = int(os.environ.get("EQ_PROP_SEED", "20260918"))

SNOW_LINE = 22.0          # snow lies above this height (as in paint_terrain.py)
TREE_LINE = 20.0          # trees do not grow above this
MIN_HEIGHT = 0.6          # below is beach and shallows, nothing is placed there
# Not closer than this to a settlement, otherwise props get into its model. There are many settlements (median
# distance to the nearest neighbour ~19 m), so the radius is small and depends on the kind.
SETTLEMENT_CLEAR = {"town": 13.0, "castle": 10.0, "village": 8.0, "hideout": 7.0}
BORDER = 12.0             # margin from the map edge

# Entity name: it is also used to remove them on a rerun.
PREFIX = "eq_prop_"

# Where to take the roads from: map_roads.py computes them from equestria_settlements.xml of the same Module folder.
MOD_FOR_ROADS = os.environ.get("EQ_MOD", "Module")
# How many metres to move props away from a riverbed: the drawn river is wider than the line on the terrain map
RIVER_CLEAR = 4.0


def item(mesh, lo, hi, snow=None, weight=1.0, tilt=0.18, tree=False, sink=0.1):
    """One prop kind: mesh, scale range, snowy variant, tilt and sinking into the ground."""
    return dict(mesh=mesh, lo=lo, hi=hi, snow=snow, weight=weight, tilt=tilt, tree=tree, sink=sink)


# Mercenary camps near the realm capitals. The camps themselves are parties on the map (CampSpots in
# src/EquestriaMercCamp.cs); here are only the tents that make them look like a camp. The points must
# match those in the code, otherwise the party stands away from its tents.
MERC_CAMPS = [
    (543.5, 502.5),    # Canterlot
    (426.8, 448.0),    # Las Pegasus
    (533.7, 454.1),    # Ponyville
    (666.5, 642.7),    # Crystal City
    (986.8, 812.9),    # Griffonstone
    (182.7, 564.5),    # Mount Aris
    (101.9, 648.2),    # Deer Grove
    (721.1, 297.6),    # Dragon Lord's Lair
    (555.7, 772.2),    # Yaktown
    (285.3, 800.8),    # Vesalipolis
]
# What stands around the point: three tents and an awning. The tent mesh radius is 0.36 m, so the scale is large.
CAMP_PROPS = [
    ("map_icon_siege_camp_tent", -0.4, 0.4, 6.0, 0.4),
    ("map_icon_siege_camp_tent", 0.7, -0.4, 5.4, 2.1),
    ("map_icon_siege_camp_tent", 0.3, 0.9, 5.0, 4.0),
    ("map_icon_siege_camp_a", -0.9, -0.5, 5.0, 1.2),
]

# Props placed by hand at one point, not scattered.
FIXED = [(mesh, x + dx, y + dy, scale, turn)
         for x, y in MERC_CAMPS
         for mesh, dx, dy, scale, turn in CAMP_PROPS]


# Mesh radii (from tpac_export info) to get a sense of scale: map_rock_* ~0.3 m,
# map_rock_big_* ~1.3 m, map_mountain_rock_c..f 1.5..3.4 m, mainmap_cliff_* 4.7..8.5 m,
# map_tree_* ~1.1..1.6 m, log_* 0.8..3 m.
#
# PITFALL (07.10.2026, seen in game): map_tree_a/b/c/d have only lod0 (tpac_export list
# map_tree: meshes=1); without a fallback level the engine has nothing to replace the model with beyond the
# distance threshold:
# the tree simply disappears as the camera moves away instead of losing detail. map_tree_new_a/b/c/d have
# meshes=2 (lod0 + lod1 billboard), so only those are used. map_tree_small_a/b and map_tree_palm_a/b
# also have only lod0 (vanilla has no "new" version of them), so the same blinking risk remains,
# but no replacement has been found yet.
ROCKS_SMALL = [
    item("map_rock_a", 2.5, 5.0, "map_rock_a_snow"),
    item("map_rock_b", 2.5, 5.5, "map_rock_b_snow"),
    item("map_rock_c", 2.0, 4.5, "map_rock_c_snow"),
    item("map_rock_d", 2.5, 5.0, "map_rock_d_snow"),
    item("map_rock_e", 2.8, 5.5, "map_rock_e_snow"),
    item("map_rock_f", 2.5, 5.0, "map_rock_f_snow"),
]

GROUPS = [
    # Mountains and any steep slopes: rocks, outcrops, blocks.
    dict(
        name="горы и склоны",
        kinds=(equus_map.MOUNTAIN,),
        slope=0.9,
        spacing=13.0,
        cluster=(1, 4),
        radius=(4.0, 14.0),
        items=[
            item("map_mountain_rock_c", 0.50, 1.10, "map_mountain_rock_c_snw", weight=2),
            item("map_mountain_rock_d", 0.45, 1.00, "map_mountain_rock_d_snw", weight=2),
            item("map_mountain_rock_e", 0.35, 0.80, "map_mountain_rock_e_snw"),
            item("map_mountain_rock_f", 0.28, 0.65, "map_mountain_rock_f_snw"),
            item("map_rock_big_a", 0.80, 1.60, "map_rock_big_a_snow", weight=2),
            item("map_rock_big_b", 0.80, 1.60, "map_rock_big_b_snow", weight=2),
            item("map_rock_big_c", 0.80, 1.60, "map_rock_big_c_snow", weight=2),
        ],
    ),
    # Forest: deadwood, stones under the trees, sparse undergrowth.
    dict(
        name="лес",
        kinds=(equus_map.FOREST,),
        spacing=21.0,
        cluster=(1, 3),
        radius=(3.0, 10.0),
        items=[
            item("log_pine_k", 1.00, 2.00, tilt=0.25, weight=2),
            item("log_pine_m", 0.80, 1.60, tilt=0.25),
            item("log_tree_high_a", 0.70, 1.40, tilt=0.25),
            item("map_tree_small_a", 2.4, 4.5, tree=True, weight=2),
            item("map_tree_small_b", 2.4, 4.5, tree=True, weight=2),
        ] + ROCKS_SMALL,
    ),
    # Plain: groves and lone trees, occasionally boulders and stone scatters.
    dict(
        name="равнины",
        kinds=(equus_map.PLAIN,),
        spacing=24.0,
        cluster=(2, 6),
        radius=(5.0, 16.0),
        items=[
            item("map_tree_new_a", 2.0, 3.8, tree=True, weight=3, tilt=0.04),
            item("map_tree_new_b", 2.2, 4.2, tree=True, weight=3, tilt=0.04),
            item("map_tree_new_c", 2.0, 3.8, tree=True, weight=3, tilt=0.04),
            item("map_tree_new_d", 2.0, 4.0, tree=True, weight=3, tilt=0.04),
            item("map_rock_big_a", 1.20, 2.60, "map_rock_big_a_snow"),
            item("map_rock_groups_a", 2.0, 4.5, "map_rock_groups_a_snow"),
            item("map_rock_groups_b", 2.0, 4.5),
        ],
    ),
    # Steppe: barer than the plain, just stones and sparse acacias.
    dict(
        name="степь",
        kinds=(equus_map.STEPPE,),
        spacing=30.0,
        cluster=(1, 4),
        radius=(6.0, 18.0),
        items=[
            item("map_tree_small_a", 2.2, 4.0, tree=True, weight=2),
            item("map_tree_small_b", 2.2, 4.0, tree=True),
            item("map_rock_groups_b", 2.2, 5.0, weight=2),
            item("map_rock_big_b", 1.20, 2.40, "map_rock_big_b_snow"),
        ] + ROCKS_SMALL,
    ),
    # Desert: palms and weathered stones.
    dict(
        name="пустыня",
        kinds=(equus_map.DESERT,),
        spacing=14.0,
        cluster=(1, 4),
        radius=(4.0, 12.0),
        items=[
            item("map_tree_palm_a", 2.2, 4.0, tree=True, tilt=0.06, weight=2),
            item("map_tree_palm_b", 2.2, 4.0, tree=True, tilt=0.06, weight=2),
            item("map_rock_big_a", 1.20, 2.60),
            item("map_rock_new_e", 0.25, 0.60, tilt=0.10),
            item("map_rock_new_c", 0.25, 0.55, tilt=0.10),
        ] + ROCKS_SMALL,
    ),
    # Swamp: snags and tussocks.
    dict(
        name="болота",
        kinds=(equus_map.SWAMP,),
        spacing=16.0,
        cluster=(1, 3),
        radius=(4.0, 12.0),
        items=[
            item("log_pine_m", 0.80, 1.60, tilt=0.30, weight=2),
            item("log_tree_high_a", 0.70, 1.40, tilt=0.30, weight=2),
            item("map_tree_small_b", 2.2, 3.8, tree=True),
            item("map_rock_d", 2.5, 5.5),
        ],
    ),
    # River and lake shores: riverside trees and rounded stones.
    dict(
        name="берега рек",
        near_water=5,
        spacing=18.0,
        cluster=(1, 3),
        radius=(3.0, 9.0),
        items=[
            item("map_tree_new_b", 2.0, 3.8, tree=True, tilt=0.04, weight=3),
            item("map_tree_new_c", 2.0, 3.8, tree=True, tilt=0.04, weight=3),
            item("map_tree_new_d", 2.0, 3.8, tree=True, tilt=0.04, weight=2),
            item("waterfall_rock_c", 0.60, 1.30, tilt=0.20),
            item("map_rock_a", 3.0, 6.5, "map_rock_a_snow"),
            item("map_rock_c", 3.0, 6.5, "map_rock_c_snow"),
        ],
    ),
]


def _dilate(mask, radius):
    """Dilate the mask by radius cells (without scipy: a maximum over shifts)."""
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def _masks():
    """Terrain masks at heightmap resolution (1 m per sample), row 0 is the south."""
    heights = equus_map.heights()
    kind = equus_map.terrain_map()
    land = equus_map.land_map()
    size = heights.shape[0]
    # Maps may have different resolutions: bring them to the height grid by nearest neighbour.
    def fit(a):
        if a.shape[0] == size:
            return a
        idx = (np.linspace(0, a.shape[0] - 1, size)).round().astype(int)
        return a[np.ix_(idx, idx)]
    kind, land = fit(kind), fit(land)
    water = np.isin(kind, (equus_map.WATER, equus_map.LAKE, equus_map.RIVER))
    ground = land & ~water & (heights > MIN_HEIGHT)
    gy, gx = np.gradient(heights)
    slope = np.hypot(gx, gy)
    # Roads: nothing is placed on them, otherwise a boulder lies in the middle of the road. The mask comes
    # from the same module as the terrain painting, so the roads are the same in both places.
    try:
        import map_roads
        road = map_roads.mask(size, MOD_FOR_ROADS) > 0.25
    except Exception:
        road = np.zeros_like(ground)
    ground = ground & ~road
    # River: the riverbed on the terrain map is a one-metre line, but it is drawn as a ribbon of about 3 m
    # plus banks.
    # So nothing is placed right by the water: otherwise big map_tree_* stand right in the river (seen
    # in game 2026-09-22, 99 props were within four metres of the riverbed).
    river = np.isin(kind, (equus_map.RIVER,))
    if RIVER_CLEAR > 0:
        step = equus_map.MAP_SIZE / (size - 1)
        radius = max(int(round(RIVER_CLEAR / step)), 1)
        band = np.zeros_like(river)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                band |= np.roll(np.roll(river, dy, 0), dx, 1)
        river = band
    ground = ground & ~river
    return dict(heights=heights, kind=kind, ground=ground, water=water, slope=slope, size=size,
                road=road, river=river)


def _pick(rng, items, total):
    r = rng.uniform(0.0, total)
    for it in items:
        r -= it["weight"]
        if r <= 0.0:
            return it
    return items[-1]


def place(entities, settlements, log=print):
    """Adds environment props to the scene's entities section. settlements is {id: (kind, x, y)}."""
    for e in list(entities):
        if (e.get("name") or "").startswith(PREFIX):
            entities.remove(e)

    m = _masks()
    size = m["size"]
    step = equus_map.MAP_SIZE / (size - 1)
    rng = random.Random(SEED)
    towns = np.array([[x, y, SETTLEMENT_CLEAR.get(kind, 8.0)]
                      for kind, x, y in settlements.values()], dtype=np.float32) \
        if settlements else np.zeros((0, 3), np.float32)

    def cell(x, y):
        return int(round(y / step)), int(round(x / step))

    placed = {}
    total = 0
    for group in GROUPS:
        if "kinds" in group:
            mask = m["ground"] & np.isin(m["kind"], group["kinds"])
            if group.get("slope"):
                mask |= m["ground"] & (m["slope"] > group["slope"])
        else:
            mask = m["ground"] & _dilate(m["water"], group["near_water"])
        spacing = group["spacing"] / math.sqrt(DENSITY)
        weights = sum(it["weight"] for it in group["items"])
        count = 0
        steps = int(equus_map.MAP_SIZE / spacing)
        for cj in range(steps):
            for ci in range(steps):
                cx = (ci + rng.random()) * spacing
                cy = (cj + rng.random()) * spacing
                j, i = cell(cx, cy)
                if not (BORDER < cx < equus_map.MAP_SIZE - BORDER
                        and BORDER < cy < equus_map.MAP_SIZE - BORDER) or not mask[j, i]:
                    continue
                for k in range(rng.randint(*group["cluster"])):
                    if k == 0:
                        x, y = cx, cy
                    else:
                        a = rng.uniform(0, 2 * math.pi)
                        r = rng.uniform(*group["radius"])
                        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
                    j, i = cell(x, y)
                    if not (0 <= i < size and 0 <= j < size) or not mask[j, i]:
                        continue
                    if len(towns) and np.any(np.hypot(towns[:, 0] - x, towns[:, 1] - y) < towns[:, 2]):
                        continue
                    h = float(m["heights"][j, i])
                    it = _pick(rng, group["items"], weights)
                    if it["tree"] and h > TREE_LINE:
                        continue
                    mesh = it["snow"] if (it["snow"] and h > SNOW_LINE) else it["mesh"]
                    scale = rng.uniform(it["lo"], it["hi"])
                    tilt = it["tilt"]
                    entity = ET.SubElement(entities, "game_entity", {
                        "name": PREFIX + mesh, "old_prefab_name": "",
                    })
                    ET.SubElement(entity, "transform", {
                        "position": "%.3f, %.3f, %.3f" % (x, y, h - it["sink"] * scale),
                        "rotation_euler": "%.3f, %.3f, %.3f" % (
                            rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt),
                            rng.uniform(-math.pi, math.pi)),
                        "scale": "%.3f, %.3f, %.3f" % (scale, scale, scale),
                    })
                    ET.SubElement(ET.SubElement(entity, "components"),
                                  "meta_mesh_component", {"name": mesh})
                    placed[mesh] = placed.get(mesh, 0) + 1
                    count += 1
        total += count
        log("предметы окружения, %s: %d" % (group["name"], count))

    for mesh, x, y, scale, turn in FIXED:
        entity = ET.SubElement(entities, "game_entity", {"name": PREFIX + mesh, "old_prefab_name": ""})
        ET.SubElement(entity, "transform", {
            "position": "%.3f, %.3f, %.3f" % (x, y, equus_map.height(x, y)),
            "rotation_euler": "0.000, 0.000, %.3f" % turn,
            "scale": "%.3f, %.3f, %.3f" % (scale, scale, scale),
        })
        ET.SubElement(ET.SubElement(entity, "components"), "meta_mesh_component", {"name": mesh})
        placed[mesh] = placed.get(mesh, 0) + 1
        total += 1
    log("поставленных руками: %d (стоянки наёмников у %d столиц)" % (len(FIXED), len(MERC_CAMPS)))

    log("предметов окружения всего: %d, видов мешей %d" % (total, len(placed)))
    return total
