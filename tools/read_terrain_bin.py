# Parsing terrain.bin, the binary terrain file of a scene.
#
#   python read_terrain_bin.py <terrain.bin> [another one for comparison]
#
# Needed to find out whether it holds layer weights (what is painted where). The format is undocumented,
# so we feel our way: look for text header tags and print the sizes of the chunks between them.
import os
import re
import struct
import sys

PATHS = sys.argv[1:]


def show(path):
    data = open(path, "rb").read()
    print("=" * 78)
    print("%s — %d байт" % (os.path.basename(path), len(data)))
    print("начало:", data[:32])

    # Tags in this format are short uppercase Latin words (HGHT, NRML and the like).
    marks = [(m.start(), m.group().decode("ascii"))
             for m in re.finditer(rb"[A-Z][A-Z0-9]{3,7}", data[:len(data)])]
    # Keep only those that look like chunk headers: not back to back and not inside numbers.
    seen = []
    for offset, name in marks:
        if seen and offset - seen[-1][0] < 4:
            continue
        seen.append((offset, name))

    print("найдено меток: %d, первые 40:" % len(seen))
    for i, (offset, name) in enumerate(seen[:40]):
        nxt = seen[i + 1][0] if i + 1 < len(seen) else len(data)
        size = nxt - offset
        head = struct.unpack_from("<4I", data, offset + len(name)) if offset + len(name) + 16 <= len(data) else ()
        print("  0x%08X  %-8s  до следующей %8d байт   далее: %s"
              % (offset, name, size, " ".join("%d" % v for v in head)))


for path in PATHS:
    show(path)
