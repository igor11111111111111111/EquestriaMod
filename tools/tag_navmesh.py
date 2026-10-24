# Terrain types of the world map navmesh faces, from code, using the Equus map.
#
#   py -3 tools\tag_navmesh.py <the mod's Module folder> [source mesh]
#
# The mesh itself is built by the editor (Generate Grids, see make_navmesh.py): 100x100 faces of ~10 m over
# the whole map, sea included. Marking in the editor where the sea is and where the land is cannot be done
# reliably (its face selection by "Terrain height" does not use absolute height). So we keep the editor mesh
# as is in assets/map/navmesh_grid_editor.bin and set the face types here:
#   water and lakes (from assets/map/eq_map_terrain.png): Water 10 / Lake 8, impassable;
#   high mountain ridges: Mountain 7, also impassable;
#   the rest of the land: its terrain type (plain, forest, steppe, snow, desert, swamp);
#   rivers are not marked: in a mesh of 10 m faces they would cut the whole map with no fords.
# Faces under settlements, their gates and hideouts are always passable.
#
# File format: "RNM1", the length of the rest, then 40 service bytes (3, 0, uncompressed length, 0,
# length of the rest, 0 and 16 bytes of garbage from the editor's memory; they affect nothing) and an LZ4 block.
# Face: number of corners, corners, edges, 5 int32 (the third is the terrain type), a byte (0 in vanilla,
# the editor sets 1 on selected faces).
import os
import struct
import sys
import xml.etree.ElementTree as ET

import lz4.block
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
from terrain_bin import lz4_decompress  # noqa: E402

MOD = sys.argv[1]
SOURCE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(equus_map.DIR, "navmesh_grid_editor.bin")
TARGET = os.path.join(MOD, "SceneObj", "Main_map", "navmesh.bin")
SETTLEMENTS = os.path.join(MOD, "ModuleData", "equestria_settlements.xml")

# Types passable for ordinary parties (DefaultPartyNavigationModel.IsTerrainTypeValidForDefault)
PASSABLE = {1, 2, 3, 4, 5, 6, 15, 16, 17, 20}
WATER_SHARE = 0.5        # a face is water if more than this share of it is water
RIDGE_HEIGHT = 20.0      # mountains are impassable if the face is entirely above this, m


def log(*a):
    print("[navmesh]", *a, flush=True)


def read(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"RNM1":
        raise SystemExit("не сетка проходимости: " + path)
    head = bytearray(raw[:48])
    data = bytearray(lz4_decompress(raw[48:], struct.unpack_from("<I", raw, 16)[0]))
    return head, data


def faces(data):
    count = struct.unpack_from("<I", data, 4)[0]
    vertices = np.frombuffer(bytes(data[8:8 + count * 12]), dtype="<f4").reshape(-1, 3)
    off = 8 + count * 12
    edges = struct.unpack_from("<I", data, off)[0]
    off += 4 + edges * 24
    total = struct.unpack_from("<I", data, off)[0]
    off += 4
    out = []
    for _ in range(total):
        n = struct.unpack_from("<I", data, off)[0]
        corners = list(struct.unpack_from("<%dI" % n, data, off + 4))
        off += 4 + n * 8
        out.append((off, vertices[corners]))   # off is the start of the face's five numbers
        off += 21
    return out


def settlement_points():
    points = []
    for node in ET.parse(SETTLEMENTS).getroot():
        for kx, ky in (("posX", "posY"), ("gate_posX", "gate_posY")):
            if node.get(kx) is not None:
                points.append((float(node.get(kx)), float(node.get(ky))))
    return points


FORDING = 6


def connect_islands(data, face_list, boxes, must_pass):
    """Islands with settlements are joined to the mainland by a ford, a straight chain of faces.
    The editor mesh is a regular grid, so a face's neighbours are found by its cell."""
    cell = boxes[0][2] - boxes[0][0]
    origin = min(b[0] for b in boxes), min(b[1] for b in boxes)
    grid = {}
    for index, (x0, y0, _x1, _y1) in enumerate(boxes):
        grid[(int(round((x0 - origin[0]) / cell)), int(round((y0 - origin[1]) / cell)))] = index
    where = {index: key for key, index in grid.items()}

    def kind(index):
        return struct.unpack_from("<5i", data, face_list[index][0])[2]

    def components():
        label = {}
        current = 0
        for start in grid.values():
            if start in label or kind(start) not in PASSABLE:
                continue
            stack = [start]
            label[start] = current
            while stack:
                cx, cy = where[stack.pop()]
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    other = grid.get((nx, ny))
                    if other is not None and other not in label and kind(other) in PASSABLE:
                        label[other] = current
                        stack.append(other)
            current += 1
        return label

    added = 0
    for _round in range(50):
        label = components()
        sizes = {}
        for comp in label.values():
            sizes[comp] = sizes.get(comp, 0) + 1
        main = max(sizes, key=sizes.get)
        islands = {label[i] for i in must_pass if i in label and label[i] != main}
        if not islands:
            break
        comp = islands.pop()
        mine = [where[i] for i, c in label.items() if c == comp]
        mainland = np.array([where[i] for i, c in label.items() if c == main])
        best = None
        for x, y in mine:
            d = np.abs(mainland[:, 0] - x) + np.abs(mainland[:, 1] - y)
            k = int(d.argmin())
            if best is None or d[k] < best[0]:
                best = (d[k], (x, y), tuple(mainland[k]))
        _dist, (x, y), (tx, ty) = best
        while (x, y) != (tx, ty):   # in steps along the grid, so that the ford is connected
            if abs(tx - x) >= abs(ty - y):
                x += 1 if tx > x else -1
            else:
                y += 1 if ty > y else -1
            index = grid[(x, y)]
            if kind(index) not in PASSABLE:
                off = face_list[index][0]
                five = list(struct.unpack_from("<5i", data, off))
                five[2] = FORDING
                struct.pack_into("<5i", data, off, *five)
                added += 1
    return added


def main():
    head, data = read(SOURCE)
    terrain = equus_map.terrain_map()
    heights = equus_map.heights()
    size = terrain.shape[0]
    scale = (size - 1) / equus_map.MAP_SIZE
    face_list = faces(data)

    boxes = []
    for _off, corners in face_list:
        boxes.append((corners[:, 0].min(), corners[:, 1].min(), corners[:, 0].max(), corners[:, 1].max()))
    must_pass = set()
    for x, y in settlement_points():
        for index, (x0, y0, x1, y1) in enumerate(boxes):
            if x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3:
                must_pass.add(index)

    stats = {}
    for index, (off, _corners) in enumerate(face_list):
        x0, y0, x1, y1 = boxes[index]
        i0, i1 = int(x0 * scale), int(np.ceil(x1 * scale)) + 1
        j0, j1 = int(y0 * scale), int(np.ceil(y1 * scale)) + 1
        part = terrain[j0:j1, i0:i1].ravel()
        water = np.isin(part, (equus_map.WATER, equus_map.LAKE))
        if water.mean() > WATER_SHARE and index not in must_pass:
            kind = equus_map.LAKE if (part == equus_map.LAKE).sum() > (part == equus_map.WATER).sum() \
                else equus_map.WATER
        else:
            land = part[~np.isin(part, (equus_map.WATER, equus_map.LAKE, equus_map.RIVER))]
            if len(land) == 0:
                kind = equus_map.PLAIN
            else:
                values, counts = np.unique(land, return_counts=True)
                kind = int(values[counts.argmax()])
            if kind == equus_map.MOUNTAIN:
                low = float(heights[j0:j1, i0:i1].min())
                if low < RIDGE_HEIGHT or index in must_pass:
                    kind = equus_map.STEPPE
            if kind not in PASSABLE and kind != equus_map.MOUNTAIN:
                kind = equus_map.PLAIN
        five = list(struct.unpack_from("<5i", data, off))
        five[2] = kind
        struct.pack_into("<5i", data, off, *five)
        data[off + 20] = 0
        stats[kind] = stats.get(kind, 0) + 1
    fords = connect_islands(data, face_list, boxes, must_pass)
    if fords:
        stats = {}
        for off, _corners in face_list:
            kind = struct.unpack_from("<5i", data, off)[2]
            stats[kind] = stats.get(kind, 0) + 1
    log("типы граней:", dict(sorted(stats.items())), "; под поселениями проходимых:", len(must_pass),
        "; бродов к островам:", fords)

    packed = lz4.block.compress(bytes(data), mode="high_compression", compression=12, store_size=False)
    if lz4_decompress(packed, len(data)) != bytes(data):
        raise SystemExit("сжатие не сошлось при проверке")
    struct.pack_into("<I", head, 4, 40 + len(packed))
    struct.pack_into("<I", head, 16, len(data))
    struct.pack_into("<I", head, 24, 40 + len(packed))
    with open(TARGET, "wb") as f:
        f.write(bytes(head) + packed)
    log("записан %s (%d байт)" % (TARGET, 48 + len(packed)))


if __name__ == "__main__":
    main()
