# Запись высот карты мира прямо в terrain.bin — без кнопки Import HeightMap в редакторе.
#
#   py -3 tools\write_terrain_heights.py <папка Module мода>
#
# Берёт assets/map/eq_map_heightmap.png (его собирает make_equus_map.py) и переписывает в
# Main_map/terrain.bin два куска:
#   HGHT — по узлу рельефа 16-битная серая картинка 65x65: 0..65535 = min_height..max_height
#          из <terrain> в scene.xscene;
#   NRML — по узлу RGBA-картинка 65x65 с нормалями: R = nx·127,5+127,5, G = ny·127,5+127,5,
#          B = 63, A = 0 (так пишет редактор; сверено с его файлом, расхождение ~1 из 255).
# Кусок PHYM (физические материалы) от высот не зависит и не трогается. В scene.xscene
# обновляются min_height/max_height узлов.
#
# Порядок узлов в terrain.bin — построчно с юга (узел i: столбец i % N, строка i // N), первая
# строка картинки — южный край узла. Размер рельефа (узлы, шаг) должен совпадать с картой высот:
# сам рельеф создаётся в редакторе один раз (16x16 узлов по 64 м, высоты -3..32).
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
# Отсчётов на участок: 2^LEVEL + 1. Столько же ставится в heightmap_level/normalmap_level узла.
# 64 (уровень 6) давало ячейку в 1 м, и на КАЖДОЙ границе участков была видна полоса ровно в одну
# ячейку — её и принимали за «границы чанков» (померено по снимку игры: шаг 63.5 м при масштабе
# 8.5 пикселя на метр, ширина полосы 1.3 м). У ванильной карты ячейка 0.21 м, и полосы не видно.
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
        # Сглаженное уплотнение: вдвое-вчетверо мельче исходной карты. Линейное тут не годится —
        # оно склеивает поверхность из плоских кусков, и на стыках исходной сетки появляются грани.
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

    # height_complexity — единственная оставшаяся настройка участка, которая может заставить
    # движок дробить соседние участки по-разному; по данным у нас швов нет (высоты на общих
    # кромках совпадают бит в бит, нормали и веса тоже), а линии по сетке в игре видны.
    # Формула ванили не восстанавливается (лучшая корреляция с мерами рельефа 0.61), поэтому
    # ставим всем участкам ОДНО значение: какой бы смысл в него ни вкладывался, разнобоя между
    # соседями не будет. Прежние значения были от 0 до 2.78, причём 29 участков объявляли себя
    # ровными при перепаде до 2 м.
    # 2.784 — наибольшее из прежних значений на нашей карте, то есть «участок сложный, как самый
    # сложный из тех, что игра уже рисовала». Меньше ставить незачем: чем выше, тем подробнее
    # движок дробит участок, а разнобоя между соседями при одинаковом значении нет в любом случае.
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
