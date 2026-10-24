# Разведка куска WGHT (веса слоёв рельефа) в terrain.bin.
#
#   python probe_weights.py <terrain.bin> [ещё один для сравнения]
#
# Что выяснилось по байтам: кусок устроен так —
#   таблица смещений картинок (по 4 байта на узел рельефа),
#   затем 10 служебных чисел (в них длина без сжатия и длина сжатого потока),
#   затем ОДИН поток LZ4, в котором лежат все PNG подряд.
# Смещения из таблицы указывают внутрь распакованного потока.
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_bin as tb  # noqa: E402


def header_of(chunk):
    """Возвращает (смещения картинок, начало потока LZ4)."""
    offsets = [struct.unpack_from("<I", chunk.data, 0)[0]]
    position = 4
    while True:
        value = struct.unpack_from("<I", chunk.data, position)[0]
        if value <= offsets[-1]:
            break
        offsets.append(value)
        position += 4
    # сразу после таблицы идут 10 служебных чисел, среди них длина без сжатия и длина потока
    extra = struct.unpack_from("<10I", chunk.data, position)
    return offsets, position + 40, extra


def png_chunks(png):
    position = 8
    while position + 12 <= len(png):
        length, name = struct.unpack_from(">I4s", png, position)
        if position + 12 + length > len(png):
            return
        data = png[position + 8:position + 8 + length]
        stored = struct.unpack_from(">I", png, position + 8 + length)[0]
        yield name, data, (zlib.crc32(name + data) & 0xFFFFFFFF) == stored
        position += 12 + length
        if name == b"IEND":
            return


for path in sys.argv[1:]:
    version, chunks, _blob = tb.read(path)
    print("=" * 78)
    print(os.path.basename(path), "версия", version)
    for chunk in chunks:
        if chunk.name not in ("WGHT", "HGHT"):
            continue
        offsets, stream_start, extra = header_of(chunk)
        print("%s: картинок %d, поток с байта %d, служебные числа %s"
              % (chunk.name, len(offsets), stream_start, extra[:5]))
        try:
            body = tb.lz4_decompress(chunk.data[stream_start:], None)
        except Exception as e:
            print("   LZ4 не пошёл:", e)
            continue
        print("   распаковано %d байт (в служебных числах значилось %d)" % (len(body), extra[2]))

        for i in range(min(3, len(offsets))):
            begin = offsets[i]
            end = offsets[i + 1] if i + 1 < len(offsets) else len(body)
            png = body[begin:end]
            ok = png.startswith(tb.PNG_SIGNATURE)
            if not ok:
                print("   #%d: не PNG (%s)" % (i, png[:8].hex(" ")))
                continue
            width, height, depth, color = struct.unpack_from(">IIBB", png, 16)
            good = all(valid for _n, _d, valid in png_chunks(png))
            idat = b"".join(d for n, d, _v in png_chunks(png) if n == b"IDAT")
            raw = zlib.decompress(idat)
            counts = {}
            for b in raw:
                counts[b] = counts.get(b, 0) + 1
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
            print("   #%d: %dx%d бит=%d тип=%d, суммы %s, распаковано %d байт, значения %s"
                  % (i, width, height, depth, color, "сходятся" if good else "НЕ сходятся",
                     len(raw), top))
