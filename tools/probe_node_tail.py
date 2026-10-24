# Что лежит в данных узла весов ПОСЛЕ масок.
#
#   python probe_node_tail.py <terrain.bin>
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_bin as tb  # noqa: E402

version, chunks, _blob = tb.read(sys.argv[1])
w = [c for c in chunks if c.name == "WGHT"][0]
count = w.header_size // 4
offsets = list(struct.unpack_from("<%dI" % count, w.data, 0))
stream = tb.lz4_decompress(w.data[w.header_size + 40:], None)
for i in range(min(4, count)):
    end = offsets[i + 1] if i + 1 < count else len(stream)
    blob = stream[offsets[i]:end]
    layers = struct.unpack_from("<I", blob, 0)[0]
    position = 4
    for _ in range(layers):
        size = struct.unpack_from("<I", blob, position)[0]
        position += 4 + size
    tail = blob[position:]
    print("узел %d: %d байт, масок %d, хвост %d байт" % (i, len(blob), layers, len(tail)))
    print("   ", tail[:80].hex(" "))
    if tail.find(tb.PNG_SIGNATURE) >= 0:
        print("    в хвосте есть PNG на смещении", tail.find(tb.PNG_SIGNATURE))
