# Paints the world map terrain directly into terrain.bin, without the editor.
#
#   python paint_terrain.py <mod Module folder>
#
# What is painted where is stored in the WGHT chunk of terrain.bin. Layout (worked out byte by byte,
# see tools/terrain_bin.py and probe_weights.py):
#
#   chunk = offset table per terrain node (4 bytes per node)
#         + 10 service numbers (among them the uncompressed length and the stream length)
#         + ONE LZ4 stream with all node data in a row
#   node data = one record per EVERY layer slot: "1, length, PNG mask" or "0" if the layer is absent
#   mask = 65x65 grayscale image, brightness = how much the layer is visible at that point
#
# Node order in terrain.bin is row by row from the south: node number i is in column i % N and row i // N,
# and the first row of its image is the southern edge. In scene.xscene, however, nodes are listed by
# columns (idx, then idy). The game knows which mask belongs to which layer from the bit mask
# layer_is_used_mask_* of the node in scene.xscene, so the scene file is edited as well.
#
# We paint by the terrain types of the Equestria at War map (assets/map, see tools/equus_map.py):
# plains - grass, forests - forest, mountains - rock, the north - snow, wastelands - sand, swamps - mud,
# sea and rivers - "water bed". The layers and their textures are set by make_map_entities.py.
#
# RUN ORDER: first make_map_entities.py (it rewrites scene.xscene entirely and resets the layer
# masks), then this script.
import os
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import map_roads  # noqa: E402
import terrain_bin as tb  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MOD = ARGS[0]
SCENE = os.path.join(MOD, "SceneObj", "Main_map", "scene.xscene")
TERRAIN = os.path.join(MOD, "SceneObj", "Main_map", "terrain.bin")

# Layer numbers as in the scene's <layers> (the layer set of the vanilla world map):
# 0 default, 1 flora_forest, 2 rock, 3 grass, 4 dirt, 5 dirt2, 6 forest2, 7 river
LAYER_OF_TERRAIN = {
    equus_map.PLAIN: 0,
    equus_map.FOREST: 1,
    equus_map.MOUNTAIN: 2,
    equus_map.SNOW: 3,       # the grass layer is repainted as snow
    equus_map.STEPPE: 4,     # hills and steppe - dry earth
    equus_map.DESERT: 5,     # the dirt2 layer is repainted as sand
    equus_map.SWAMP: 6,      # the forest2 layer is repainted as swamp mud
    equus_map.WATER: 7,      # the river layer - the "water bed" of the vanilla map
    equus_map.LAKE: 7,
}
LAYERS = 9
WATER_LAYER = 7
DEEP_LAYER = 8           # "deep water" - added by make_map_entities.py
# Depth at which water turns dark, m (the bed near the shore is -1, in the open sea -3)
DEEP_FROM, DEEP_TO = -1.2, -2.6
RIVER_STRENGTH = 0.85    # (unused: the riverbed is drawn as a ribbon, see layer_weights)
RIVER_CORE = 1           # how many metres to widen the riverbed line by: ribbon width = 2*CORE + 1
RIVER_SOFT = 1           # softness of the ribbon edge, metres
RIVER_GAIN = 1.8         # how much to boost the blurred ribbon so its middle stays solid
RIVER_BANK = 2           # width of the bank on both sides of the riverbed, metres
MOUTH_REACH = 24         # how many metres to extend a broken-off riverbed to reach the sea
BANK_LAYER = 4           # the bank is dry earth, the same layer as roads
BANK_STRENGTH = 0.85     # how much the bank covers what is underneath it
MAX_NODE_LAYERS = int(os.environ.get("EQ_NODE_LAYERS", "6"))
# How many layers one node carries. With four layers there were not enough for nine terrain types, and
# neighbouring nodes took DIFFERENT sets of four: on 87 borders out of 480 the set changed, at the edge
# the layers were reduced to the common ones, and inwards they diverged twice as fast as usual - hence the
# straight stripes along the node grid (worked out from the data 2026-09-22). If the layers cover the whole
# map at once, all nodes share one set and there are no seams by construction. The old note "the game
# does not draw more than four, water disappeared" dates from before the writing of empty slots was
# fixed; if water disappears again, go back to 4 via EQ_NODE_LAYERS.
# How much a node looks at its neighbours when choosing which terrain types to keep
KEEP_COHERENCE = float(os.environ.get("EQ_KEEP_COHERENCE", "0.35"))
KEEP_ROUNDS = 8
# How much the share of a type on the whole map is taken into account when choosing (so that the same
# type is dropped everywhere, not different ones in neighbouring nodes)
# Weight of a layer's overall share on the map when choosing a node's set. Without it neighbouring nodes
# drop different terrain types (in the north there are five of them for four slots) and the map breaks
# up into rectangles. 2.5 was tuned by the number of sets in the north (10 -> 3) and of junctions without
# a common layer (2 -> 0), at the cost of the steppe almost vanishing, which snow hides there anyway.
GLOBAL_BIAS = float(os.environ.get("EQ_GLOBAL_BIAS", "1.0"))
# What to replace a layer that did not fit into a node with: one that looks similar, so the seam at the
# node border is softer. Forest and swamp -> grass, sand -> steppe, snow -> rock, etc.
SUBSTITUTE = {1: 0, 6: 0, 5: 4, 3: 2, 0: 4, 4: 0, 2: 4, 8: 7, 7: 8}
# The game draws the combination grass + steppe + water (0, 4, 7) without rock wrongly: the whole node is
# dark, the layers are not visible (checked in game, tools/tour.ps1 + EQ_NODE_PROBE). With an added
# near-zero rock mask (2) the node is drawn correctly.
BROKEN_SET = {0, 4, 7}
PAD_LAYER = 2
PAD_ORDER = [2, 0, 4, 1]   # what to pad a node with up to four layers
FLORA_LAYERS = (1, 6)      # layers from which the engine grows trees
SHORE_HEIGHT = 0.5         # below this height (m) there must be no trees - it is water and the waterline
SHORE_MARGIN = 4           # how many samples (metres) to move the forest away from water
RIVER_MARGIN = 3           # the same for rivers: riverbed plus bank, metres
FLORA_BAN = None           # shared "no flora here" mask (see layer_weights)
SEA_NODE = 0.5             # water share at which a node counts as sea
HAS_WATER = 0.02           # water share at which a node must carry the water layer
HAS_DEEP = 0.01            # the same for deep water
FOREST_LAYER = 1           # the layer from which the engine grows trees
HAS_FOREST = 0.02          # forest share at which a node must carry the forest layer
OPEN_SEA = 0.8             # water share at which a node is open sea
SEA_SET = (0, 2, 7, 8)     # the single layer set of the open sea
ROADS = os.environ.get("EQ_ROADS", "1") != "0"   # whether to draw roads between settlements
ROAD_LAYER = 4     # dry earth layer (ground_earth) - roads are drawn with it
SNOW_LINE = 22.0   # above this height there is snow on the mountains, m
BLUR = 2           # border softening radius, in samples (1 sample = 1 m)
MIN_WEIGHT = 8     # layer shares below this (out of 255) are not written
# Row order of the mask inside a node. Checked in game (EQ_PAINT_PROBE=1: a snow circle under
# Ponderosa, a sand one 30 m to the north): the first row is the southern edge, as with heights.
ROW_ORDER = os.environ.get("EQ_WGHT_ROWS", "south")


def log(*a):
    print("[terrain]", *a, flush=True)


def box_blur(field, radius):
    """Mean over a (2r+1)^2 square via cumulative sums - no scipy needed."""
    if radius <= 0:
        return field
    pad = np.pad(field, radius, mode="edge")
    k = 2 * radius + 1
    c = np.cumsum(np.cumsum(pad, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def layer_weights():
    """Layer shares over the whole map: (LAYERS, S, S), row 0 is south, sum over layers = 1."""
    terrain = equus_map.terrain_map()
    heights = equus_map.heights()
    if terrain.shape != heights.shape:
        raise SystemExit("карта местности %s и высот %s разного размера" % (terrain.shape, heights.shape))
    index = np.zeros(terrain.shape, dtype=np.int8)
    for kind, layer in LAYER_OF_TERRAIN.items():
        index[terrain == kind] = layer
    index[(index == 2) & (heights > SNOW_LINE)] = 3
    # The engine grows trees from the flora layers, and near water they end up in the sea. We remove flora
    # from the terrain type map itself - before blurring and before splitting layers among nodes: then
    # both neighbouring nodes see the same data and no seam appears at the border (checked in game 18.09.2026).
    shore = heights < SHORE_HEIGHT
    if SHORE_MARGIN > 0:
        shore = box_blur(shore.astype(np.float32), SHORE_MARGIN) > 1e-3
    river = terrain == equus_map.RIVER
    river = reach_the_sea(river, np.isin(terrain, (equus_map.WATER, equus_map.LAKE)), log)
    # Trees are not wanted on rivers either, and they do not go away by themselves: the river is put into
    # the weights on top of the finished picture and dims the forest only by RIVER_STRENGTH, leaving it 15%
    # - enough for the engine to plant pines right along the riverbed (noticed in game 2026-09-22). So the
    # forest is removed from the terrain types themselves along the riverbed and the bank strip.
    if RIVER_MARGIN > 0:
        near_river = box_blur(river.astype(np.float32), RIVER_MARGIN) > 1e-3
    else:
        near_river = river
    no_flora = shore | near_river
    for layer in FLORA_LAYERS:
        index[(index == layer) & no_flora] = substitute(layer, [k for k in range(LAYERS)
                                                               if k not in FLORA_LAYERS and k != WATER_LAYER])
    # under the river - the terrain around it (taken from neighbours along the row), the river itself goes on top
    for shift in (1, -1, 2, -2, 3, -3):
        fill = river & (index == 0) & ~np.roll(river, shift, 1)
        index[fill] = np.roll(index, shift, 1)[fill]
    if os.environ.get("EQ_PAINT_PROBE"):
        # Mask orientation check: around Ponderosa (485.7, 461.9) everything is grass, under it a snow
        # circle, 30 m to the north a sand one.
        yy, xx = np.mgrid[0:terrain.shape[0], 0:terrain.shape[1]]
        k = (terrain.shape[0] - 1) / equus_map.MAP_SIZE
        cx, cy = 485.7 * k, 461.9 * k
        index[(xx - cx) ** 2 + (yy - cy) ** 2 < 100 ** 2] = 0
        index[(xx - cx) ** 2 + (yy - cy) ** 2 < 12 ** 2] = 3
        index[(xx - cx) ** 2 + (yy - cy - 30) ** 2 < 12 ** 2] = 5
    if os.environ.get("EQ_NODE_PROBE"):
        # Check of what each layer is drawn with: nodes around (9,9) are painted with stripes of known layers.
        plan = {(8, 10): [0], (9, 10): [4], (10, 10): [2],
                (8, 9): [0, 4], (9, 9): [0, 4, 7], (10, 9): [0, 2, 4, 7],
                (8, 8): [0, 1, 7], (9, 8): [4, 7], (10, 8): [0, 7]}
        for (nx, ny), layers in plan.items():
            for k, layer in enumerate(layers):
                x0 = nx * 64 + k * 64 // len(layers)
                x1 = nx * 64 + (k + 1) * 64 // len(layers) + 1
                index[ny * 64:ny * 64 + 65, x0:x1] = layer
    weights = np.stack([box_blur((index == layer).astype(np.float32), BLUR) for layer in range(LAYERS)])
    weights /= np.maximum(weights.sum(0), 1e-6)
    # Roads between settlements: in vanilla they are baked into the map's virtual texture, which we do not
    # have, so we lay them ourselves (tools/map_roads.py). They are put in AFTER blurring, like rivers:
    # if they are put into the terrain types before it, the road spreads to twice its width and reads not
    # as a road but as a light stripe across half the view (noticed in game 2026-09-22). Here the width and
    # edge softness are exactly those set in map_roads. Flora will not grow on the road: the forest layer
    # weight under it fades along with the others.
    if ROADS:
        road = map_roads.mask(weights.shape[1], MOD, log)
        road *= 1.0 - np.clip(weights[WATER_LAYER] + weights[DEEP_LAYER], 0.0, 1.0)  # do not go over water
        weights *= 1.0 - road
        weights[ROAD_LAYER] += road
        log("дороги: занято %.2f%% карты" % (100.0 * float((road > 0.5).mean())))
    # Rivers on top. The riverbed on the terrain map is a line one sample thick, and if it is put in as is
    # and not at full strength, the game shows a pale blue smear: 85% water, grass showing through under
    # it, and an edge one texture sample wide smeared by filtering. So we do the same as with roads - a
    # ribbon of constant width with a soft edge of exactly RIVER_SOFT and at full strength, and on the sides
    # we put a strip of dry earth: this is the bank, without it the water lies right on the grass.
    # In vanilla the same thing is painted by an artist right into the baked map texture, and we have
    # nothing to reproduce it with (Main_map/TileSets, 2.1 GB, baked by the editor for terrain version 1).
    core = box_blur(river.astype(np.float32), RIVER_CORE) > 1e-6
    banks = box_blur(core.astype(np.float32), RIVER_BANK) > 1e-6
    open_water = np.isin(terrain, (equus_map.WATER, equus_map.LAKE))
    bank = np.clip(box_blur((banks & ~core & ~open_water).astype(np.float32), 1), 0.0, 1.0)
    bank = bank * BANK_STRENGTH * (1.0 - open_water.astype(np.float32))
    weights *= 1.0 - bank
    weights[BANK_LAYER] += bank
    stream = np.clip(box_blur(core.astype(np.float32), RIVER_SOFT) * RIVER_GAIN, 0.0, 1.0)
    weights *= 1.0 - stream
    weights[WATER_LAYER] += stream
    log("реки: русло %.1f%% карты, берега %.1f%%"
        % (100.0 * float((stream > 0.5).mean()), 100.0 * float((bank > 0.2).mean())))
    # depth: part of the water turns dark
    deep = np.clip((heights - DEEP_FROM) / (DEEP_TO - DEEP_FROM), 0.0, 1.0).astype(np.float32)
    weights[DEEP_LAYER] = weights[WATER_LAYER] * deep
    weights[WATER_LAYER] *= 1.0 - deep
    # Trees grow from the flora layers (1 - forest, 6 - swamp): even a barely visible mask on water gives
    # a forest in the middle of the sea. So where water is more than half, flora is removed completely and
    # the remaining weights are renormalized (checked in game 18.09.2026: trees in the sea in the north).
    return weights


def reach_the_sea(river, sea, log):
    """Extends riverbeds to the sea: in the source map they break off before reaching the shore.

    We look for riverbed ends (points with fewer than two riverbed neighbours) and, if there is sea
    nearby, draw a straight segment to its nearest point. Without this every mouth keeps a strip of
    land between the river and the sea (noticed in game 2026-09-22: of 3565 riverbed points, 40
    touched the sea).
    """
    river = river.copy()
    a = river.astype(np.float32)
    around = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                around += np.roll(np.roll(a, dy, 0), dx, 1)
    ends = np.argwhere(river & (around <= 1.5))
    size = river.shape[0]
    joined = 0
    for y, x in ends:
        lo_y, hi_y = max(int(y) - MOUTH_REACH, 0), min(int(y) + MOUTH_REACH + 1, size)
        lo_x, hi_x = max(int(x) - MOUTH_REACH, 0), min(int(x) + MOUTH_REACH + 1, size)
        window = sea[lo_y:hi_y, lo_x:hi_x]
        if not window.any():
            continue
        ys, xs = np.nonzero(window)
        ys, xs = ys + lo_y, xs + lo_x
        best = np.argmin((ys - y) ** 2 + (xs - x) ** 2)
        ty, tx = int(ys[best]), int(xs[best])
        steps = max(abs(ty - int(y)), abs(tx - int(x)))
        if steps == 0:
            continue
        for i in range(steps + 1):
            py = int(round(y + (ty - y) * i / steps))
            px = int(round(x + (tx - x) * i / steps))
            river[py, px] = True
        joined += 1
    log("устья рек доведены до моря: %d" % joined)
    return river


def limit_node_layers(index, heights, per_node=64):
    """Before smoothing: no more than MAX_NODE_LAYERS terrain types in each node.

    Which type to drop is not decided per node alone: if a neighbour dropped a different one, a
    straight line across the whole cell is visible at the border. Especially in the north, where there
    are five types for four slots (snow, forest, rock, earth, water) - the chunks were visible all over
    there (checked 18.09.2026). So the set of kept types is chosen with an eye on the neighbours
    (KEEP_COHERENCE), and the dropped ones are replaced with similar ones (substitute).
    """
    import itertools
    index = index.copy()
    n = (index.shape[0] - 1) // per_node
    areas, rooms, forced = {}, {}, {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            core = index[y0:y0 + per_node + 1, x0:x0 + per_node + 1]
            kinds, counts = np.unique(core, return_counts=True)
            areas[(ix, iy)] = {int(k): int(c) for k, c in zip(kinds.tolist(), counts.tolist())}
            # deep water has its own layer: leave room for it
            deep = bool(((core == WATER_LAYER)
                         & (heights[y0:y0 + per_node + 1, x0:x0 + per_node + 1] < DEEP_FROM)).any())
            rooms[(ix, iy)] = MAX_NODE_LAYERS - (1 if deep else 0)
            forced[(ix, iy)] = {WATER_LAYER} if WATER_LAYER in areas[(ix, iy)] else set()

    total = float(index.size)
    global_share = {int(k): float(c) / total
                    for k, c in zip(*[a.tolist() for a in np.unique(index, return_counts=True)])}

    keep = {}
    for key, area in areas.items():
        order = sorted(area, key=lambda k: -area[k])
        keep[key] = (forced[key] | set(order))
        keep[key] = set(list(forced[key]) + [k for k in order if k not in forced[key]])
        keep[key] = set(list(keep[key])[:rooms[key]]) if len(keep[key]) > rooms[key] else keep[key]

    for _round in range(KEEP_ROUNDS):
        changed = 0
        for key in sorted(areas):
            ix, iy = key
            area, room = areas[key], rooms[key]
            if len(area) <= room:
                keep[key] = set(area)
                continue
            scale = max(area.values())
            neighbours = [keep[(ix + dx, iy + dy)] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                          if (ix + dx, iy + dy) in keep]
            must = forced[key] & set(area)
            rest = [k for k in area if k not in must]
            take = max(room - len(must), 0)
            best = None
            for combo in itertools.combinations(rest, min(take, len(rest))):
                chosen = must | set(combo)
                # add the type's share on the whole map to its area in the node: otherwise neighbouring
                # nodes drop DIFFERENT types and a straight line is visible at the border
                value = (sum(area[k] + GLOBAL_BIAS * scale * global_share.get(k, 0.0) for k in chosen)
                         + KEEP_COHERENCE * scale * sum(len(chosen & other) for other in neighbours))
                if best is None or value > best[0]:
                    best = (value, chosen)
            if best and best[1] != keep[key]:
                keep[key] = best[1]
                changed += 1
        if not changed:
            break

    changed = 0
    for key, area in areas.items():
        ix, iy = key
        y0, x0 = iy * per_node, ix * per_node
        core = index[y0:y0 + per_node + 1, x0:x0 + per_node + 1]
        for kind in sorted(area, key=lambda k: area[k]):
            if kind in keep[key]:
                continue
            target = substitute(int(kind), sorted(keep[key]))
            core[core == kind] = target
            changed += 1
    log("заменено мелких видов местности в узлах: %d" % changed)
    return index


def substitute(layer, allowed):
    """A similar layer from allowed along the SUBSTITUTE chain, otherwise the first of allowed."""
    seen = set()
    while layer in SUBSTITUTE and layer not in seen:
        seen.add(layer)
        layer = SUBSTITUTE[layer]
        if layer in allowed:
            return layer
    if not allowed:
        return 0
    # The fallback layer is not just the first one: forest comes first by number, and water and steppe
    # leaked into it - trees grew on the sea (checked in game 18.09.2026).
    return next((k for k in allowed if k not in FLORA_LAYERS), allowed[0])


def parse_chunk(chunk):
    """Chunk = offset table (4 bytes per node) + 40 service bytes + LZ4 stream."""
    count = chunk.header_size // 4
    offsets = list(struct.unpack_from("<%dI" % count, chunk.data, 0))
    extra = list(struct.unpack_from("<10I", chunk.data, chunk.header_size))
    return offsets, extra


def build_chunk(extra, blobs):
    """Reassembly: offset table, service numbers, compressed stream."""
    stream = b""
    offsets = []
    for blob in blobs:
        offsets.append(len(stream))
        stream += blob
    packed = tb.lz4_compress(stream)
    extra = list(extra)
    extra[2] = len(stream)        # uncompressed length
    extra[4] = 40 + len(packed)   # stream length INCLUDING these 40 service bytes
    header = b"".join(struct.pack("<I", o) for o in offsets)
    header += struct.pack("<10I", *extra)
    return header + packed


WATER_BONUS = 30      # how many times more important water is when choosing the layer set
# Deep water is also a thin strip near the shore: without its own weight it dropped out in the
# neighbouring node, and a straight border between shades was visible in the sea (checked 18.09.2026).
DEEP_BONUS = 8
FEATHER = int(os.environ.get("EQ_FEATHER", "28"))   # width of the strip at the node edge where layers
# are reduced to those shared with the neighbour, in samples. The wider, the softer the transition between
# nodes with different layer sets; 16 was too little - in the north, where there are more terrain types
# than slots, the junctions are visible.
# How much more important agreement with neighbours is than the node's own layers (as a fraction of its
# own score). 0 - every node on its own and straight lines are visible at borders; too much - the map
# loses variety. 0.12 was tuned by the number of neighbour pairs with 4 common layers.
COHERENCE = float(os.environ.get("EQ_COHERENCE", "0.7"))
ROUNDS = 12           # agreement passes, usually converges in 3-4
MIN_COMMON = 3        # how many layers neighbouring nodes must have in common
LAND_ORDER = [0, 4, 2, 1, 5, 3, 6, 7, 8]


def allowed(layer_set):
    """Combinations the game draws wrongly (checked in game): grass+steppe+water without rock."""
    return not (BROKEN_SET <= layer_set and PAD_LAYER not in layer_set)


def target_layer(layer, layer_set):
    """Where to send the weight of a layer missing from the node's set: a similar layer, else by order."""
    if layer in layer_set:
        return layer
    seen, x = set(), layer
    while x in SUBSTITUTE and x not in seen:
        seen.add(x)
        x = SUBSTITUTE[x]
        if x in layer_set:
            return x
    order = ([WATER_LAYER, DEEP_LAYER] if layer in (WATER_LAYER, DEEP_LAYER) else []) + LAND_ORDER
    return next(x for x in order if x in layer_set)


def project(part, layer_set):
    out = np.zeros_like(part)
    for layer in range(LAYERS):
        if part[layer].any():
            out[target_layer(layer, layer_set)] += part[layer]
    return out


def single_set(weights):
    """One layer set for the whole map, if there are no more terrain types than node slots.

    Layers are taken by their weight on the map; water and depth get a bonus - they are thin in area,
    but without them the sea and rivers disappear. Returns None if everything does not fit: then the
    set is chosen for each node separately, as before.
    """
    share = weights.reshape(LAYERS, -1).mean(1).astype(np.float64)
    score = share.copy()
    score[WATER_LAYER] *= WATER_BONUS
    score[DEEP_LAYER] *= DEEP_BONUS
    used = [k for k in range(LAYERS) if share[k] > 0.001]
    if len(used) > MAX_NODE_LAYERS:
        used = sorted(sorted(range(LAYERS), key=lambda k: -score[k])[:MAX_NODE_LAYERS])
    chosen = set(used)
    # pad to the full size - the game draws nodes with an incomplete set wrongly
    for layer in PAD_ORDER + LAND_ORDER:
        if len(chosen) >= MAX_NODE_LAYERS:
            break
        chosen.add(layer)
    if not allowed(chosen):
        chosen.add(PAD_LAYER)
    dropped = [k for k in range(LAYERS) if share[k] > 0.001 and k not in chosen]
    log("общий набор слоёв на всю карту: %s%s"
        % (sorted(chosen), (", не поместились: %s" % dropped) if dropped else ""))
    return sorted(chosen)


def choose_sets(weights, n, per_node):
    """Exactly MAX_NODE_LAYERS layers for each node (the game draws nodes with 2-3 layers wrongly).

    The set is not chosen per node alone: neighbours should share as many layers as possible, otherwise
    a straight line along the whole node is visible at the border - a layer the neighbour lacks breaks
    off. So agreement with the neighbours' already chosen sets (COHERENCE) is added to the score of the
    node's own layers, and the choice is repeated until it stops changing.
    """
    import itertools
    size = weights.shape[1]
    total = float(weights.sum())
    map_share = (weights.sum(axis=(1, 2)) / max(total, 1e-6)).astype(np.float32)
    sums = {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            core = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1].sum(axis=(1, 2))
            ring = weights[:, max(y0 - FEATHER, 0):min(y0 + per_node + 1 + FEATHER, size),
                           max(x0 - FEATHER, 0):min(x0 + per_node + 1 + FEATHER, size)].sum(axis=(1, 2))
            score = core + 0.5 * (ring - core)
            # rivers are thin lines and always lose by area, but without the water layer they disappear
            score[WATER_LAYER] *= WATER_BONUS
            score[DEEP_LAYER] *= DEEP_BONUS
            # The layer's share on the whole map: without it neighbouring nodes drop DIFFERENT types (in the
            # north there are five for four slots), and the map breaks up into rectangles (checked 18.09.2026).
            score = score + GLOBAL_BIAS * float(score.max()) * map_share
            sums[(ix, iy)] = score
    combos = [set(c) for c in itertools.combinations(range(LAYERS), MAX_NODE_LAYERS) if allowed(set(c))]
    # A sea node must contain both water layers: if one node got deep water and its neighbour did not,
    # a dark square the size of the whole cell is visible in the sea (checked in game 18.09.2026).
    # Flora has no business in the sea - the engine grows trees from its layers.
    choices = {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            part = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1]
            water = float(part[WATER_LAYER].mean())
            deep = float(part[DEEP_LAYER].mean())
            need = set()
            forest = float(part[FOREST_LAYER].mean())
            if forest > HAS_FOREST:
                # the engine grows trees from the forest layer: no layer - the forest breaks off at the node edge
                need.add(FOREST_LAYER)
            if water > HAS_WATER:
                need.add(WATER_LAYER)
            if deep > HAS_DEEP:
                # the node has deep water: without its layer it comes out lighter than the neighbour, and
                # a straight border a whole cell long is visible in the sea (checked in game 18.09.2026)
                need.update((WATER_LAYER, DEEP_LAYER))
            allowed_here = [c for c in combos if need <= c]
            if water + deep > OPEN_SEA:
                # Open sea: all such nodes have ONE layer set. Otherwise neighbouring nodes differ not only
                # in depth but also in what lies under the water, and a straight border is visible in the
                # sea (checked in game 18.09.2026 at the junction of nodes (14,15) and (15,15)).
                allowed_here = [set(SEA_SET)]
            elif water + deep > SEA_NODE:
                # almost solid water: no place for flora here, otherwise trees grow in the sea
                no_flora = [c for c in allowed_here if not set(FLORA_LAYERS) & c]
                allowed_here = no_flora or allowed_here
            choices[(ix, iy)] = allowed_here or combos
    scale = {key: max(float(score.max()), 1.0) for key, score in sums.items()}
    # first pass - without neighbours, then we reconcile
    sets = {key: max(choices[key], key=lambda c: sum(score[layer] for layer in c))
            for key, score in sums.items()}
    for _round in range(ROUNDS):
        changed = 0
        for key in sorted(sums):
            ix, iy = key
            score, own = sums[key], scale[key]
            neighbours = [sets[(ix + dx, iy + dy)] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                          if (ix + dx, iy + dy) in sets]

            def value(combo):
                same = sum(len(combo & other) for other in neighbours)
                return sum(score[layer] for layer in combo) + COHERENCE * own * same

            best = max(choices[key], key=value)
            if best != sets[key]:
                sets[key] = best
                changed += 1
        log("  согласование: проход %d, изменено узлов %d" % (_round, changed))
        if not changed:
            break

    # Finish off the remaining weak junctions (usually the shore: the sea has {water, depth}, the land has
    # grass with rock). In one of the nodes the least needed layer is swapped for the neighbour's layer -
    # so at least MIN_COMMON common layers remain on the shared border, and no layer break along the whole
    # node is visible.
    for _round in range(4):
        fixed = 0
        for (ix, iy) in sorted(sums):
            for dx, dy in ((1, 0), (0, 1)):
                key_b = (ix + dx, iy + dy)
                if key_b not in sets:
                    continue
                a, b = sets[(ix, iy)], sets[key_b]
                if len(a & b) >= MIN_COMMON:
                    continue
                best = None
                for key, other in (((ix, iy), b), (key_b, a)):
                    score, own = sums[key], scale[key]
                    current = sets[key]
                    for drop in current - other:
                        if drop == WATER_LAYER:
                            continue  # without water, rivers and the sea disappear
                        for add in other - current:
                            combo = (current - {drop}) | {add}
                            if combo not in choices[key]:
                                continue
                            loss = (score[drop] - score[add]) / own
                            if best is None or loss < best[0]:
                                best = (loss, key, combo)
                if best is not None:
                    sets[best[1]] = best[2]
                    fixed += 1
        if not fixed:
            break
    log("наборы слоёв: %d разных, север %d" % (
        len({frozenset(v) for v in sets.values()}),
        len({frozenset(v) for k, v in sets.items() if k[1] >= 10})))
    return sets


def node_part(weights, sets, ix, iy, n, per_node):
    """Node weights: inside - its own layer set, smoothly towards the edge - the set shared with the
    neighbours. On the shared edge the two neighbours get identical weights, and there is no seam."""
    y0, x0 = iy * per_node, ix * per_node
    part = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1]
    d = np.arange(per_node + 1, dtype=np.float32)
    low = np.clip(1.0 - d / FEATHER, 0.0, 1.0)
    high = low[::-1]
    ramp = {-1: low, 0: 1.0 - low - high, 1: high}
    out = np.zeros_like(part)
    missing = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            factor = ramp[dy][:, None] * ramp[dx][None, :]
            if not factor.any():
                continue
            layer_set = set(sets[(ix, iy)])
            for key in {(ix + a, iy + b) for a in {0, dx} for b in {0, dy}}:
                if key in sets:
                    layer_set &= sets[key]
            if not layer_set:
                layer_set = set(sets[(ix, iy)])
                missing += 1
            out += factor * project(part, layer_set)
    return out, missing


PROBE_SETS = [{0, 2, 4, 7}, {2, 4, 5, 6}, {1, 2, 3, 4}, {2, 3, 4, 5}]


def set_probe(weights, sets, per_node):
    """Blending probe: in nodes (8..11, 9) and (8..11, 10) a smooth rock -> earth transition from left
    to right, with different layer sets in neighbouring nodes. Row 9 - layer shares (as we write now),
    row 10 - "cumulative" writing: layer mask = its share among itself and the layers below."""
    out = {}
    total = 4 * per_node + 1
    for row, cumulative in ((9, False), (10, True)):
        for k, layer_set in enumerate(PROBE_SETS):
            ix = 8 + k
            sets[(ix, row)] = set(layer_set)
            x = (np.arange(per_node + 1) + k * per_node) / (total - 1)
            ramp = np.tile(x[None, :], (per_node + 1, 1)).astype(np.float32)
            part = np.zeros((LAYERS, per_node + 1, per_node + 1), dtype=np.float32)
            rock, dirt = 1.0 - ramp, ramp
            if cumulative:
                part[2] = np.where(rock > 0, 1.0, 0.0)   # layer 2 is below layer 4 in all sets
                part[4] = dirt
            else:
                part[2], part[4] = rock, dirt
            out[(ix, row)] = part
    return out


def to_alpha(part, present):
    """Layer shares -> masks as the game understands them. Checked with a probe (EQ_SET_PROBE): the game
    lays the node's layers one after another, from the lower number to the higher, and a layer's mask is
    its opacity over what is already drawn. So the layer mask = its share among itself and the layers
    below. The bottom layer covers everything (otherwise there is black under it - that is where the dark
    nodes came from). If plain shares are written, the result depends on the node's layer set, and a seam
    is visible at node borders."""
    alpha = np.zeros_like(part)
    below = np.zeros(part.shape[1:], dtype=part.dtype)
    for k, layer in enumerate(present):
        below = below + part[layer]
        if k == 0:
            alpha[layer] = 1.0
        else:
            alpha[layer] = np.where(below > 1e-6, part[layer] / np.maximum(below, 1e-6), 0.0)
    return alpha


def main():
    version, chunks, _blob = tb.read(TERRAIN)
    weight_chunk = {c.name: c for c in chunks}["WGHT"]
    offsets, extra = parse_chunk(weight_chunk)

    tree = ET.parse(SCENE)
    root = tree.getroot()
    terrain_node = root.find(".//terrain")
    n = int(terrain_node.get("node_dimension_x"))
    if int(terrain_node.get("node_dimension_y")) != n or len(offsets) != n * n:
        raise SystemExit("ожидался квадратный рельеф: узлов в файле %d, в сцене %sx%s"
                         % (len(offsets), n, terrain_node.get("node_dimension_y")))
    nodes = {(int(e.get("idx")), int(e.get("idy"))): e for e in terrain_node.find("nodes").findall("node")}
    per_node = 64
    log("узлов рельефа: %dx%d, по %d отсчётов" % (n, n, per_node))

    weights = layer_weights()
    shares = weights.reshape(LAYERS, -1).mean(1)
    log("доли слоёв на карте: " + ", ".join("%d:%.0f%%" % (i, v * 100) for i, v in enumerate(shares)))

    blobs = []
    used_layers = {}
    common = single_set(weights)
    if common is not None:
        sets = {(ix, iy): set(common) for iy in range(n) for ix in range(n)}
    else:
        sets = choose_sets(weights, n, per_node)
    probe = set_probe(weights, sets, per_node) if os.environ.get("EQ_SET_PROBE") else {}
    no_common = 0
    for i in range(n * n):
        ix, iy = i % n, i // n
        node = nodes[(ix, iy)]
        slots = len(node.find(".//variable[@name='weightmap_levels']").findall("variable"))
        part, missing = node_part(weights, sets, ix, iy, n, per_node)
        if (ix, iy) in probe:
            part = probe[(ix, iy)]
        no_common += missing
        present = sorted(sets[(ix, iy)])
        if (ix, iy) in probe:
            alpha = part
        else:
            alpha = to_alpha(part, present)
        values = np.rint(np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        if ROW_ORDER == "north":
            values = values[:, ::-1, :]
        blob = b""
        for slot in range(slots):
            if slot in present:
                size = values.shape[1]
                rows = [values[slot, y].tobytes() for y in range(size)]
                image = tb.make_png(values.shape[2], size, 8, 0, rows)
                blob += struct.pack("<II", 1, len(image)) + image
            else:
                blob += struct.pack("<I", 0)
        blobs.append(blob)
        used_layers[(ix, iy)] = present

    log("наборы слоёв согласованы с соседями; участков без общего слоя: %d" % no_common)
    weight_chunk.data = build_chunk(extra, blobs)
    weight_chunk.header_size = 4 * len(blobs)
    weight_chunk.raw_length = struct.unpack_from("<I", weight_chunk.data, weight_chunk.header_size + 8)[0]
    backup = TERRAIN + ".bak"
    if not os.path.exists(backup):
        import shutil
        shutil.copy2(TERRAIN, backup)
        log("резервная копия", backup)
    tb.write(TERRAIN, version, chunks)
    log("записан %s (веса: %d байт)" % (TERRAIN, len(weight_chunk.data)))

    for key, node in nodes.items():
        mask = 0
        for layer in used_layers[key]:
            mask |= 1 << layer
        for season in ("summer", "fall", "winter", "spring"):
            node.set("layer_is_used_mask_%s" % season, str(mask))
        node.set("layer_is_used_mask", "true")
        levels = node.find(".//variable[@name='weightmap_levels']")
        if levels is not None:
            for variable in levels.findall("variable"):
                layer = int(variable.get("layer"))
                variable.set("value", "6" if (mask >> layer) & 1 else "0")
    ET.indent(root, space="\t")
    tree.write(SCENE, encoding="utf-8", xml_declaration=True)
    log("в сцене обновлены маски используемых слоёв")


if __name__ == "__main__":
    main()
