# Reference for multi-layer painting: parsing the weight nodes of a regular (battle) game scene.
#
#   python probe_scene_weights.py <scene folder with terrain.bin and scene.xscene>
#
# For nodes with several layers it prints the layer mask from the scene and the node data layout:
# consecutive "counter + images" blocks and the remainder. We check our own writing against this.
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_bin as tb  # noqa: E402

FOLDER = sys.argv[1]
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 4

version, chunks, _blob = tb.read(os.path.join(FOLDER, "terrain.bin"))
w = [c for c in chunks if c.name == "WGHT"][0]
count = w.header_size // 4
offsets = list(struct.unpack_from("<%dI" % count, w.data, 0))
stream = tb.lz4_decompress(w.data[w.header_size + 40:], None)

text = open(os.path.join(FOLDER, "scene.xscene"), encoding="utf-8").read()
nodes_xml = text[text.find("<nodes>"):text.find("</nodes>")]
tags = re.findall(r"<node [^>]*?(?:/>|>.*?</node>)", nodes_xml, re.S)
print("узлов: в весах %d, в сцене %d, поток %d байт" % (count, len(tags), len(stream)))


def blocks(blob):
    """Layout: how many "counter + PNG" blocks can be read in a row."""
    out = []
    position = 0
    while position + 4 <= len(blob):
        n = struct.unpack_from("<I", blob, position)[0]
        if n > 32:
            break
        cursor = position + 4
        sizes = []
        ok = True
        for _ in range(n):
            if cursor + 4 > len(blob):
                ok = False
                break
            size = struct.unpack_from("<I", blob, cursor)[0]
            if blob[cursor + 4:cursor + 12] != tb.PNG_SIGNATURE:
                ok = False
                break
            sizes.append(size)
            cursor += 4 + size
        if not ok:
            break
        out.append((n, sizes))
        position = cursor
        if n == 0:
            break
    return out, len(blob) - position, blob[position:]


shown = 0
for i, start in enumerate(offsets):
    end = offsets[i + 1] if i + 1 < count else len(stream)
    blob = stream[start:end]
    tag = tags[i] if i < len(tags) else ""
    mask = int((re.search(r'layer_is_used_mask_summer="(\d+)"', tag) or [0, "0"])[1])
    bits = [b for b in range(16) if mask >> b & 1]
    if len(bits) < 2:
        continue
    lay, rest_len, rest = blocks(blob)
    levels = [(l, v) for l, v in re.findall(r'<variable layer="(\d+)" value="(\d+)"', tag) if v != "0"]
    print("-" * 70)
    print("узел %d: слои %s, уровни %s" % (i, bits, levels))
    for n, sizes in lay:
        print("   блок: картинок %d, размеры %s" % (n, sizes))
    print("   остаток %d байт: %s" % (rest_len, rest[:64].hex(" ")))
    shown += 1
    if shown >= LIMIT:
        break
if shown == 0:
    print("многослойных узлов не нашлось")
