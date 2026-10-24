# Эталон: как устроены многослойные узлы весов на ВАНИЛЬНОЙ карте мира.
#
#   python probe_vanilla_weights.py [папка игры]
#
# Для первых узлов с несколькими слоями печатает: сколько масок, их заголовки PNG и какие
# слои/уровни указаны у этого узла в scene.xscene. С этим сверяем свою раскраску.
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_bin as tb  # noqa: E402

GAME = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
FOLDER = os.path.join(GAME, "Modules", "SandBox", "SceneObj", "Main_map")

version, chunks, _blob = tb.read(os.path.join(FOLDER, "terrain.bin"))
for c in chunks:
    print("%-5s поток %-9d без сжатия %-9d заголовок %-6d служебные %s"
          % (c.name, c.length, c.raw_length, c.header_size,
             struct.unpack_from("<10I", c.data, c.header_size) if c.header_size else "-"))

w = [c for c in chunks if c.name == "WGHT"][0]
count = w.header_size // 4
offsets = list(struct.unpack_from("<%dI" % count, w.data, 0))
extra = struct.unpack_from("<10I", w.data, w.header_size)
print("узлов", count)
stream = tb.lz4_decompress(w.data[w.header_size + 40:], None)
print("поток весов распакован: %d байт (ждали %d)" % (len(stream), extra[2]))

# Маски узлов из сцены: выдёргиваем атрибуты регуляркой, сцена большая
text = open(os.path.join(FOLDER, "scene.xscene"), encoding="utf-8").read()
nodes_xml = text[text.find("<nodes>"):text.find("</nodes>")]
node_tags = re.findall(r"<node [^>]*>.*?</node>", nodes_xml, re.S)
print("узлов в сцене", len(node_tags))

shown = 0
for i, start in enumerate(offsets):
    end = offsets[i + 1] if i + 1 < len(offsets) else len(stream)
    blob = stream[start:end]
    layers = struct.unpack_from("<I", blob, 0)[0]
    if layers < 2:
        continue
    tag = node_tags[i] if i < len(node_tags) else ""
    mask = re.search(r'layer_is_used_mask_summer="(\d+)"', tag)
    levels = re.findall(r'<variable layer="(\d+)" value="(\d+)"', tag)
    print("-" * 70)
    print("узел %d: масок %d, маска слоёв %s, уровни %s"
          % (i, layers, mask.group(1) if mask else "?",
             [(l, v) for l, v in levels if v != "0"]))
    position = 4
    for j in range(layers):
        size = struct.unpack_from("<I", blob, position)[0]
        png = blob[position + 4:position + 4 + size]
        position += 4 + size
        width, height, depth, color = struct.unpack_from(">IIBB", png, 16)
        names = []
        p = 8
        while p + 12 <= len(png):
            ln, nm = struct.unpack_from(">I4s", png, p)
            names.append(nm.decode("ascii", "replace"))
            p += 12 + ln
            if nm == b"IEND":
                break
        print("   маска %d: %d байт, %dx%d бит=%d тип=%d, куски %s, первые байты %s"
              % (j, size, width, height, depth, color, names, png[:8] == tb.PNG_SIGNATURE))
    print("   хвост данных узла после масок: %d байт" % (len(blob) - position))
    shown += 1
    if shown >= 3:
        break
