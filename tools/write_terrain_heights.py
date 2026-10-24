# Writing the world map heights straight into terrain.bin - without the Import HeightMap button in the editor.
#
#   py -3 tools\write_terrain_heights.py <mod Module folder>
#
# Takes assets/map/eq_map_heightmap.png (built by make_equus_map.py) and rewrites two chunks in
# Main_map/terrain.bin:
#   HGHT - per terrain node a 16-bit grey 65x65 image: 0..65535 = min_height..max_height
#          from <terrain> in scene.xscene;
#   NRML - per node an RGBA 65x65 image with normals: R = nx·127.5+127.5, G = ny·127.5+127.5,
#          B = 63, A = 0 (that is how the editor writes it; checked against its file, difference ~1 in 255).
# The PHYM chunk (physics materials) does not depend on heights and is not touched. In scene.xscene
# the nodes' min_height/max_height are updated.
#
# Node order in terrain.bin is row by row from the south (node i: column i % N, row i // N); the first
# image row is the node's southern edge. The terrain size (nodes, step) must match the heightmap:
# the terrain itself is created in the editor once (16x16 nodes of 64 m, heights -3..32).
import os
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import terrain_bin as tb  # noqa: E402

MOD = sys.argv[1]
SCENE = os.path.join(MOD, "SceneObj", "Main_map", "scene.xscene")
TERRAIN = os.path.join(MOD, "SceneObj", "Main_map", "terrain.bin")
# Samples per node: 2^LEVEL + 1. The same goes into the node's heightmap_level/normalmap_level.
# 64 (level 6) gave a 1 m cell, and on EVERY node border a stripe exactly one cell wide was visible -
# that is what was taken for "chunk borders" (measured from a game screenshot: step 63.5 m at a scale
# of 8.5 pixels per metre, stripe width 1.3 m). The vanilla map has a 0.21 m cell, and no stripe is visible.
LEVEL = int(os.environ.get("EQ_TERRAIN_LEVEL", "8"))
PER_NODE = 1 << LEVEL


def log(*a):
    print("[heights]", *a, flush=True)


def parse(chunk):
    count = chunk.header_size // 4
    offsets = struct.unpack_from("<%dI" % count, chunk.data, 0)
    extra = struct.unpack_from("<10I", chunk.data, chunk.header_size)
    return count, list(extra)


def rebuild(chunk, extra, blobs):
    stream = b""
    offsets = []
    for blob in blobs:
        offsets.append(len(stream))
        stream += blob
    packed = tb.lz4_compress(stream)
    extra = list(extra)
    extra[2] = len(stream)
    extra[4] = 40 + len(packed)
    chunk.data = (b"".join(struct.pack("<I", o) for o in offsets) + struct.pack("<10I", *extra) + packed)
    chunk.header_size = 4 * len(blobs)
    chunk.raw_length = extra[2]


def main():
    tree = ET.parse(SCENE)
    root = tree.getroot()
    terrain = root.find(".//terrain")
    n = int(terrain.get("node_dimension_x"))
    size = float(terrain.get("node_size"))
    lo, hi = float(terrain.get("min_height")), float(terrain.get("max_height"))
    source = equus_map.heights().astype(np.float32)
    if source.shape != (n * 64 + 1,) * 2 or abs(n * size - equus_map.MAP_SIZE) > 1e-3:
        raise SystemExit("рельеф сцены (%dx%d по %.0f м) не совпадает с картой высот %s"
                         % (n, n, size, source.shape))
    if PER_NODE == 64:
        heights = source.astype(np.float64)
    else:
        # Smooth upsampling: two to four times finer than the source map. Linear is no good here -
        # it glues the surface together from flat pieces, and edges appear at the source grid seams.
        side = n * PER_NODE + 1
        from PIL import Image as _Image
        heights = np.asarray(_Image.fromarray(source, mode="F").resize((side, side), _Image.BICUBIC),
                             dtype=np.float64)
        log("сетка уплотнена: %d -> %d отсчётов, ячейка %.2f м"
            % (source.shape[0], side, size / PER_NODE))
    if abs(lo - equus_map.info()["min_height"]) > 1e-3 or abs(hi - equus_map.info()["max_height"]) > 1e-3:
        raise SystemExit("высоты сцены %.2f..%.2f, а карты %.2f..%.2f — создайте рельеф заново"
                         % (lo, hi, equus_map.info()["min_height"], equus_map.info()["max_height"]))

    raw = np.clip(np.rint((heights - lo) / (hi - lo) * 65535), 0, 65535).astype(">u2")
    step = size / PER_NODE
    gy, gx = np.gradient(heights, step)
    normal = np.stack([-gx, -gy, np.ones_like(heights)], -1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    rgba = np.zeros(heights.shape + (4,), dtype=np.uint8)
    rgba[..., 0] = np.clip(np.rint(normal[..., 0] * 127.5 + 127.5), 0, 255)
    rgba[..., 1] = np.clip(np.rint(normal[..., 1] * 127.5 + 127.5), 0, 255)
    rgba[..., 2] = 63

    version, chunks, _blob = tb.read(TERRAIN)
    by_name = {c.name: c for c in chunks}
    hght, nrml = by_name["HGHT"], by_name["NRML"]
    count, h_extra = parse(hght)
    _count, n_extra = parse(nrml)
    if count != n * n:
        raise SystemExit("в terrain.bin %d узлов, а в сцене %dx%d" % (count, n, n))

    h_blobs, n_blobs, ranges = [], [], {}
    for i in range(count):
        ix, iy = i % n, i // n
        ys = slice(iy * PER_NODE, iy * PER_NODE + PER_NODE + 1)
        xs = slice(ix * PER_NODE, ix * PER_NODE + PER_NODE + 1)
        part = raw[ys, xs]
        png = tb.make_png(part.shape[1], part.shape[0], 16, 0,
                          [row.tobytes() for row in part], filter_type=2)
        h_blobs.append(struct.pack("<I", len(png)) + png)
        part = rgba[ys, xs]
        png = tb.make_png(part.shape[1], part.shape[0], 8, 6,
                          [row.tobytes() for row in part], filter_type=2)
        n_blobs.append(struct.pack("<I", len(png)) + png)
        ranges[(ix, iy)] = (float(heights[ys, xs].min()), float(heights[ys, xs].max()))
    rebuild(hght, h_extra, h_blobs)
    rebuild(nrml, n_extra, n_blobs)

    backup = TERRAIN + ".before_heights"
    if not os.path.exists(backup):
        import shutil
        shutil.copy2(TERRAIN, backup)
        log("резервная копия", backup)
    tb.write(TERRAIN, version, chunks)
    log("записан %s: %d узлов, высоты %.2f..%.2f" % (TERRAIN, count, heights.min(), heights.max()))

    # height_complexity is the only remaining node setting that can make the engine subdivide
    # neighbouring nodes differently; by the data we have no seams (heights on shared edges match
    # bit for bit, normals and weights too), yet grid lines are visible in game.
    # The vanilla formula cannot be recovered (best correlation with terrain measures 0.61), so
    # we give all nodes ONE value: whatever meaning it carries, neighbours will not differ.
    # The previous values ranged from 0 to 2.78, and 29 nodes declared themselves flat with
    # a height difference of up to 2 m.
    # 2.784 is the largest of the previous values on our map, i.e. "the node is as complex as the most
    # complex one the game has already drawn". No reason to set less: the higher it is, the finer the
    # engine subdivides the node, and with equal values neighbours do not differ in any case.
    complexity = os.environ.get("EQ_NODE_COMPLEXITY", "2.784")
    for node in terrain.find("nodes").findall("node"):
        low, high = ranges[(int(node.get("idx")), int(node.get("idy")))]
        node.set("min_height", "%.3f" % low)
        node.set("max_height", "%.3f" % high)
        node.set("height_complexity", complexity)
        for name in ("heightmap_level", "normalmap_level"):
            variable = node.find(".//variable[@name='%s']" % name)
            if variable is not None:
                variable.set("value", str(LEVEL))
    ET.indent(root, space="\t")
    tree.write(SCENE, encoding="utf-8", xml_declaration=True)
    log("в сцене обновлены границы высот узлов; height_complexity у всех %s" % complexity)


if __name__ == "__main__":
    main()
