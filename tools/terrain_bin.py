# Чтение и запись terrain.bin — двоичного рельефа сцены Bannerlord.
#
# Формат (версия 2), разобран по нашему файлу:
#   "ZGR6RTRN" + версия(4)
#   далее таблица кусков, по 20 байт на кусок:
#       имя(4) + количество(4) + смещение(4) + длина(4) + длина_без_сжатия(4)
#   куски: MIDX (индекс), HGHT (высоты), NRML (нормали), WGHT (веса слоёв), PHYM (материалы физики)
#   Содержимое каждого куска — обычный PNG.
#
# WGHT и есть «что где покрашено»: по картинке на слой, яркость = насколько слой виден.
import struct
import zlib

MAGIC = b"ZGR6RTRN"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- LZ4
# Куски сжаты блочным LZ4 (той же библиотекой, что и ассеты .tpac). В таблице кусков рядом с
# длиной лежит длина без сжатия — по ней и проверяем, что распаковали верно.
#
# Формат блока: байт-признак (старшая половина — сколько байт копировать как есть, младшая —
# длина совпадения), затем сами байты, затем смещение назад (2 байта) и хвост длины совпадения.
# Длина 15 означает «продолжение в следующих байтах, пока не встретится не-255».
def lz4_decompress(data, expected):
    out = bytearray()
    position = 0
    size = len(data)
    while position < size:
        token = data[position]
        position += 1

        literals = token >> 4
        if literals == 15:
            while True:
                value = data[position]
                position += 1
                literals += value
                if value != 255:
                    break
        out += data[position:position + literals]
        position += literals
        if position >= size:
            break

        offset = data[position] | (data[position + 1] << 8)
        position += 2
        if offset == 0:
            raise ValueError("испорченный поток LZ4: нулевое смещение")

        match = token & 15
        if match == 15:
            while True:
                value = data[position]
                position += 1
                match += value
                if value != 255:
                    break
        match += 4

        start = len(out) - offset
        if start < 0:
            raise ValueError("испорченный поток LZ4: смещение за пределы вывода")
        # Копируем по байту: куски могут перекрываться (так LZ4 кодирует повторы).
        for i in range(match):
            out.append(out[start + i])

    if expected and len(out) != expected:
        raise ValueError("распаковано %d байт вместо %d" % (len(out), expected))
    return bytes(out)


def lz4_compress(data):
    """Простейшее сжатие: всё содержимое как есть, без поиска совпадений.

    Игре достаточно корректного потока, а размер нас не жмёт: карта весов невелика.
    Так мы не рискуем ошибиться в поиске совпадений — а распаковщик всё равно наш же.
    """
    # Блок LZ4 — это последовательности «литералы + совпадение», и только ПОСЛЕДНЯЯ может
    # состоять из одних литералов. Поэтому пишем весь буфер одной такой последовательностью:
    # признак с длиной 15 означает «продолжение в следующих байтах».
    size = len(data)
    out = bytearray()
    if size < 15:
        out.append(size << 4)
    else:
        out.append(0xF0)
        rest = size - 15
        while rest >= 255:
            out.append(255)
            rest -= 255
        out.append(rest)
    out += data
    return bytes(out)


class Chunk:
    def __init__(self, name, count, offset, length, raw_length):
        self.name = name
        self.count = count
        self.offset = offset
        self.length = length
        self.raw_length = raw_length
        self.data = b""
        self.header_size = 0

    def __repr__(self):
        return "<%s %d шт., %d байт>" % (self.name, self.count, len(self.data))


def read(path):
    blob = open(path, "rb").read()
    if blob[:8] != MAGIC:
        raise SystemExit("это не terrain.bin")
    version = struct.unpack_from("<I", blob, 8)[0]

    chunks = []
    position = 12
    while position + 20 <= len(blob):
        name = blob[position:position + 4]
        if not name.isalpha() and not name.isalnum():
            break
        if not all(65 <= b <= 90 for b in name):  # заголовки — латиница заглавными
            break
        count, offset, length, raw_length = struct.unpack_from("<4I", blob, position + 4)
        if offset + length > len(blob):
            break
        chunks.append(Chunk(name.decode("ascii"), count, offset, length, raw_length))
        position += 20

    # ВАЖНО: поле «длина» в таблице — это длина СЖАТОГО ПОТОКА, а не всего куска. Перед потоком
    # ещё лежит таблица смещений по узлам рельефа (по 4 байта на узел). Поэтому настоящие границы
    # куска берём по началу следующего: так ничего не теряется в хвосте.
    chunks.sort(key=lambda c: c.offset)
    for i, chunk in enumerate(chunks):
        end = chunks[i + 1].offset if i + 1 < len(chunks) else len(blob)
        chunk.data = blob[chunk.offset:end]
        chunk.header_size = len(chunk.data) - chunk.length
    return version, chunks, blob


def split_pngs(data):
    """Внутри куска может лежать несколько PNG подряд (по одному на слой или узел)."""
    out = []
    position = 0
    while True:
        start = data.find(PNG_SIGNATURE, position)
        if start < 0:
            break
        end = data.find(b"IEND", start)
        if end < 0:
            break
        end += 8  # длина имени + контрольная сумма
        out.append(data[start:end])
        position = end
    return out


def png_info(png):
    """Ширина, высота, глубина бита, тип цвета из заголовка PNG."""
    width, height, depth, color = struct.unpack_from(">IIBB", png, 16)
    return width, height, depth, color


def png_pixels(png):
    """Распаковка PNG без чересстрочности в список строк байтов (после снятия фильтров)."""
    width, height, depth, color = png_info(png)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = width * channels * depth // 8

    data = b""
    position = 8
    while position < len(png):
        length, name = struct.unpack_from(">I4s", png, position)
        if name == b"IDAT":
            data += png[position + 8:position + 8 + length]
        position += 12 + length
    raw = zlib.decompress(data)

    rows = []
    previous = bytearray(stride)
    step = max(1, channels * depth // 8)
    position = 0
    for _ in range(height):
        filter_type = raw[position]
        line = bytearray(raw[position + 1:position + 1 + stride])
        position += 1 + stride
        for i in range(stride):
            left = line[i - step] if i >= step else 0
            up = previous[i]
            up_left = previous[i - step] if i >= step else 0
            if filter_type == 1:
                line[i] = (line[i] + left) & 255
            elif filter_type == 2:
                line[i] = (line[i] + up) & 255
            elif filter_type == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif filter_type == 4:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                best = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                line[i] = (line[i] + best) & 255
        rows.append(bytes(line))
        previous = line
    return width, height, depth, color, rows


def make_png(width, height, depth, color, rows, filter_type=0):
    """Сборка PNG. filter_type=2 («вверх», строка минус предыдущая) сильно уменьшает файл на
    плавных данных вроде высот и нормалей — на мелкой сетке это разница в разы."""
    if filter_type == 2:
        lines, previous = [], bytes(len(rows[0])) if rows else b""
        for row in rows:
            lines.append(b"\x02" + bytes((row[i] - previous[i]) & 255 for i in range(len(row))))
            previous = row
        raw = b"".join(lines)
    else:
        raw = b"".join(b"\x00" + row for row in rows)

    def chunk(name, payload):
        body = name + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (PNG_SIGNATURE
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def write(path, version, chunks):
    """Пересборка файла: таблица кусков пересчитывается под новые длины."""
    header = MAGIC + struct.pack("<I", version)
    table_size = 20 * len(chunks)
    position = len(header) + table_size

    table = b""
    body = b""
    for chunk in chunks:
        # В таблицу пишем длину сжатого потока (без таблицы смещений в начале куска).
        stream_length = len(chunk.data) - chunk.header_size
        table += (chunk.name.encode("ascii") + struct.pack("<4I", chunk.count, position,
                                                           stream_length, chunk.raw_length))
        body += chunk.data
        position += len(chunk.data)

    open(path, "wb").write(header + table + body)
