# Reading and writing terrain.bin, the binary terrain of a Bannerlord scene.
#
# Format (version 2), worked out from our file:
#   "ZGR6RTRN" + version(4)
#   then the chunk table, 20 bytes per chunk:
#       name(4) + count(4) + offset(4) + length(4) + uncompressed_length(4)
#   chunks: MIDX (index), HGHT (heights), NRML (normals), WGHT (layer weights), PHYM (physics materials)
#   The content of each chunk is a plain PNG.
#
# WGHT is exactly "what is painted where": one image per layer, brightness = how visible the layer is.
import struct
import zlib

MAGIC = b"ZGR6RTRN"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- LZ4
# Chunks are compressed with block LZ4 (the same library as the .tpac assets). In the chunk table next to
# the length lies the uncompressed length: it is used to check that the decompression is right.
#
# Block format: a token byte (high nibble: how many bytes to copy as is, low nibble: the
# match length), then the bytes themselves, then the back offset (2 bytes) and the match length tail.
# A length of 15 means "continued in the following bytes until a non-255 is met".
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
        # Copy byte by byte: the pieces may overlap (that is how LZ4 encodes repeats).
        for i in range(match):
            out.append(out[start + i])

    if expected and len(out) != expected:
        raise ValueError("распаковано %d байт вместо %d" % (len(out), expected))
    return bytes(out)


def lz4_compress(data):
    """The simplest compression: all content as is, without searching for matches.

    A correct stream is enough for the game, and the size does not bother us: the weight map is small.
    This way we do not risk a mistake in the match search, and the decompressor is ours anyway.
    """
    # An LZ4 block is a series of "literals + match" sequences, and only the LAST one may
    # consist of literals alone. So the whole buffer is written as one such sequence:
    # a token with length 15 means "continued in the following bytes".
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
        if not all(65 <= b <= 90 for b in name):  # headers are uppercase Latin letters
            break
        count, offset, length, raw_length = struct.unpack_from("<4I", blob, position + 4)
        if offset + length > len(blob):
            break
        chunks.append(Chunk(name.decode("ascii"), count, offset, length, raw_length))
        position += 20

    # IMPORTANT: the "length" field in the table is the length of the COMPRESSED STREAM, not of the whole chunk.
    # Before the stream there is also an offset table per terrain node (4 bytes per node). So the real chunk
    # boundaries are taken from the start of the next chunk: this way nothing is lost at the tail.
    chunks.sort(key=lambda c: c.offset)
    for i, chunk in enumerate(chunks):
        end = chunks[i + 1].offset if i + 1 < len(chunks) else len(blob)
        chunk.data = blob[chunk.offset:end]
        chunk.header_size = len(chunk.data) - chunk.length
    return version, chunks, blob


def split_pngs(data):
    """A chunk may hold several PNGs in a row (one per layer or node)."""
    out = []
    position = 0
    while True:
        start = data.find(PNG_SIGNATURE, position)
        if start < 0:
            break
        end = data.find(b"IEND", start)
        if end < 0:
            break
        end += 8  # name length + checksum
        out.append(data[start:end])
        position = end
    return out


def png_info(png):
    """Width, height, bit depth, colour type from the PNG header."""
    width, height, depth, color = struct.unpack_from(">IIBB", png, 16)
    return width, height, depth, color


def png_pixels(png):
    """Unpack a non-interlaced PNG into a list of byte rows (after removing the filters)."""
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
    """Build a PNG. filter_type=2 ("up", row minus the previous one) shrinks the file a lot on
    smooth data like heights and normals: on a fine grid the difference is several times."""
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
    """Rebuild the file: the chunk table is recomputed for the new lengths."""
    header = MAGIC + struct.pack("<I", version)
    table_size = 20 * len(chunks)
    position = len(header) + table_size

    table = b""
    body = b""
    for chunk in chunks:
        # The table gets the length of the compressed stream (without the offset table at the start of the chunk).
        stream_length = len(chunk.data) - chunk.header_size
        table += (chunk.name.encode("ascii") + struct.pack("<4I", chunk.count, position,
                                                           stream_length, chunk.raw_length))
        body += chunk.data
        position += len(chunk.data)

    open(path, "wb").write(header + table + body)
