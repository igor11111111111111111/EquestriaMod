# Разбор terrain.bin — двоичного файла рельефа сцены.
#
#   python read_terrain_bin.py <terrain.bin> [ещё один для сравнения]
#
# Нужен, чтобы понять, лежат ли в нём веса слоёв (что где покрашено). Формат не документирован,
# поэтому идём наощупь: ищем текстовые метки-заголовки и печатаем размеры кусков между ними.
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

    # Метки в этом формате — короткие латинские слова заглавными (HGHT, NRML и подобные).
    marks = [(m.start(), m.group().decode("ascii"))
             for m in re.finditer(rb"[A-Z][A-Z0-9]{3,7}", data[:len(data)])]
    # Оставляем только те, что похожи на заголовки кусков: идут не подряд и не внутри чисел.
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
