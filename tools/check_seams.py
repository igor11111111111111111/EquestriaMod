# Find seams between the world map's terrain nodes.
#
#   py -3 tools\check_seams.py [the mod's Module folder]
#
# Neighbouring nodes share an edge: the last column (row) of one node's masks is the first column
# (row) of the other. If the layer shares on this edge differ between the two nodes (a layer is present
# in one node and dropped in the other), the game shows a straight border along the whole node. The script
# reads the masks from Main_map/terrain.bin and prints such edges, worst first.
import io
import os
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_bin as tb  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
LIMIT = 0.15   # layer-share mismatch on the edge above which the seam is noticeable


def node_masks(mod):
    scene = ET.parse(os.path.join(mod, "SceneObj", "Main_map", "scene.xscene")).getroot()
    terrain = scene.find(".//terrain")
    n = int(terrain.get("node_dimension_x"))
    slots = {}
    for node in terrain.find("nodes").findall("node"):
        levels = node.find(".//variable[@name='weightmap_levels']")
        slots[(int(node.get("idx")), int(node.get("idy")))] = len(levels.findall("variable"))
    _v, chunks, _b = tb.read(os.path.join(mod, "SceneObj", "Main_map", "terrain.bin"))
    chunk = {c.name: c for c in chunks}["WGHT"]
    count = chunk.header_size // 4
    offsets = struct.unpack_from("<%dI" % count, chunk.data, 0)
    stream = tb.lz4_decompress(chunk.data[chunk.header_size + 40:], None)
    masks = {}
    for i in range(count):
        key = (i % n, i // n)
        blob = stream[offsets[i]:offsets[i + 1] if i + 1 < count else len(stream)]
        pos, layers = 0, {}
        for slot in range(slots[key]):
            flag = struct.unpack_from("<I", blob, pos)[0]
            pos += 4
            if flag:
                size = struct.unpack_from("<I", blob, pos)[0]
                pos += 4
                layers[slot] = np.asarray(Image.open(io.BytesIO(blob[pos:pos + size])), dtype=np.float32) / 255
                pos += size
        masks[key] = layers
    return n, masks


def normalized(layers):
    """Masks -> layer shares. The game lays layers one by one (lower index below); a mask is the
    layer's opacity over what is already painted: layer share = mask * (1 - masks of all layers above)."""
    out = {}
    order = sorted(layers)
    for i, k in enumerate(order):
        share = layers[k].copy()
        for above in order[i + 1:]:
            share = share * (1.0 - layers[above])
        out[k] = share
    return out


def seams(n, masks):
    found = []
    norm = {k: normalized(v) for k, v in masks.items()}
    for (ix, iy), a in norm.items():
        for dx, dy in ((1, 0), (0, 1)):
            other = norm.get((ix + dx, iy + dy))
            if other is None:
                continue
            if dx:
                edge_a = {k: v[:, -1] for k, v in a.items()}
                edge_b = {k: v[:, 0] for k, v in other.items()}
            else:
                edge_a = {k: v[-1, :] for k, v in a.items()}
                edge_b = {k: v[0, :] for k, v in other.items()}
            zero = np.zeros(65, dtype=np.float32)
            worst, layer = 0.0, None
            for k in set(edge_a) | set(edge_b):
                diff = float(np.abs(edge_a.get(k, zero) - edge_b.get(k, zero)).mean())
                if diff > worst:
                    worst, layer = diff, k
            found.append((worst, (ix, iy), (ix + dx, iy + dy), layer))
    found.sort(reverse=True)
    return found


def main():
    n, masks = node_masks(MOD)
    found = seams(n, masks)
    bad = [f for f in found if f[0] > LIMIT]
    print("краёв между узлами: %d, заметных швов (> %.2f): %d" % (len(found), LIMIT, len(bad)))
    for worst, a, b, layer in bad[:25]:
        print("  %s | %s: слой %s расходится на %.2f (узлы в метрах: %d,%d)"
              % (a, b, layer, worst, a[0] * 64, a[1] * 64))


if __name__ == "__main__":
    main()
