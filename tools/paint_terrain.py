# Раскраска рельефа карты мира прямо в terrain.bin — без редактора.
#
#   python paint_terrain.py <папка Module мода>
#
# Что где покрашено, хранится в куске WGHT файла terrain.bin. Устройство (разобрано по байтам,
# см. tools/terrain_bin.py и probe_weights.py):
#
#   кусок = таблица смещений по узлу рельефа (4 байта на узел)
#         + 10 служебных чисел (среди них длина без сжатия и длина потока)
#         + ОДИН поток LZ4 со всеми данными узлов подряд
#   данные узла = по записи на КАЖДЫЙ слот слоя: "1, длина, PNG-маска" или "0", если слоя нет
#   маска = серая картинка 65x65, яркость = насколько слой виден в этой точке
#
# Порядок узлов в terrain.bin — построчно с юга: узел номер i лежит в столбце i % N и строке i // N,
# и первая строка его картинки — южный край. А в scene.xscene узлы перечислены по столбцам
# (idx, затем idy). Какому слою какая маска — игра понимает по битовой маске layer_is_used_mask_*
# у узла в scene.xscene, поэтому файл сцены правится заодно.
#
# Красим по типам местности карты Equestria at War (assets/map, см. tools/equus_map.py):
# равнины — трава, леса — лес, горы — скалы, север — снег, пустоши — песок, болота — грязь,
# море и реки — «водное дно». Слои и их текстуры задаёт make_map_entities.py.
#
# ПОРЯДОК ЗАПУСКА: сначала make_map_entities.py (он переписывает scene.xscene целиком и сбросит
# маски слоёв), потом этот скрипт.
import os
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import map_roads  # noqa: E402
import terrain_bin as tb  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MOD = ARGS[0]
SCENE = os.path.join(MOD, "SceneObj", "Main_map", "scene.xscene")
TERRAIN = os.path.join(MOD, "SceneObj", "Main_map", "terrain.bin")

# Номера слоёв — как в <layers> сцены (набор слоёв ванильной карты мира):
# 0 default, 1 flora_forest, 2 rock, 3 grass, 4 dirt, 5 dirt2, 6 forest2, 7 river
LAYER_OF_TERRAIN = {
    equus_map.PLAIN: 0,
    equus_map.FOREST: 1,
    equus_map.MOUNTAIN: 2,
    equus_map.SNOW: 3,       # слой grass перекрашен в снег
    equus_map.STEPPE: 4,     # холмы и степь — сухая земля
    equus_map.DESERT: 5,     # слой dirt2 перекрашен в песок
    equus_map.SWAMP: 6,      # слой forest2 перекрашен в болотную грязь
    equus_map.WATER: 7,      # слой river — «водное дно» ванильной карты
    equus_map.LAKE: 7,
}
LAYERS = 9
WATER_LAYER = 7
DEEP_LAYER = 8           # «глубокая вода» — добавляет make_map_entities.py
# Глубина, на которой вода становится тёмной, м (дно у берега -1, в открытом море -3)
DEEP_FROM, DEEP_TO = -1.2, -2.6
RIVER_STRENGTH = 0.85    # (не используется: русло рисуется лентой, см. layer_weights)
RIVER_CORE = 1           # на сколько метров расширить линию русла: ширина ленты = 2*CORE + 1
RIVER_SOFT = 1           # мягкость края ленты, метров
RIVER_GAIN = 1.8         # во сколько раз поднять размытую ленту, чтобы середина осталась сплошной
RIVER_BANK = 2           # ширина берега по сторонам русла, метров
MOUTH_REACH = 24         # на сколько метров дотягивать оборванное русло до моря
BANK_LAYER = 4           # берег — сухая земля, тот же слой, что у дорог
BANK_STRENGTH = 0.85     # насколько берег перекрывает то, что под ним
MAX_NODE_LAYERS = int(os.environ.get("EQ_NODE_LAYERS", "6"))
# Сколько слоёв несёт один узел. При четырёх слоям девяти видов местности не хватало, и
# соседние узлы брали РАЗНЫЕ четвёрки: на 87 границах из 480 набор менялся, у кромки слои
# сводились к общим, а вглубь расходились вдвое быстрее обычного — отсюда прямые полосы по
# сетке узлов (разобрано по данным 2026-09-22). Если слоёв хватает на всю карту сразу, набор
# у всех узлов один и швов нет по построению. Прежняя пометка «больше четырёх игра не
# рисует, пропадала вода» относится ко времени до починки записи пустых слотов; если вода
# снова пропадёт, вернуть 4 через EQ_NODE_LAYERS.
# Насколько при выборе сохраняемых видов местности узел оглядывается на соседей
KEEP_COHERENCE = float(os.environ.get("EQ_KEEP_COHERENCE", "0.35"))
KEEP_ROUNDS = 8
# Насколько при выборе учитывается доля вида на всей карте (чтобы выбрасывался
# везде один и тот же вид, а не разный в соседних узлах)
# Вес общей доли слоя на карте при выборе набора узла. Без него соседние узлы выбрасывают
# разные виды местности (на севере их пять на четыре слота) и карта распадается на
# прямоугольники. 2.5 подобрано по числу наборов на севере (10 -> 3) и стыков без
# общего слоя (2 -> 0); ценой почти исчезнувшей степи, которую там всё равно скрывает снег.
GLOBAL_BIAS = float(os.environ.get("EQ_GLOBAL_BIAS", "1.0"))
# Чем заменять слой, который в узел не поместился: похожим по виду, чтобы шов на границе
# узла был мягче. Лес и болото -> трава, песок -> степь, снег -> скалы и т.д.
SUBSTITUTE = {1: 0, 6: 0, 5: 4, 3: 2, 0: 4, 4: 0, 2: 4, 8: 7, 7: 8}
# Сочетание трава + степь + вода (0, 4, 7) без скал игра рисует неверно: узел целиком тёмный,
# слои не видны (проверено в игре, tools/tour.ps1 + EQ_NODE_PROBE). С добавленной почти
# нулевой маской скал (2) узел рисуется правильно.
BROKEN_SET = {0, 4, 7}
PAD_LAYER = 2
PAD_ORDER = [2, 0, 4, 1]   # чем дополнять узел до четырёх слоёв
FLORA_LAYERS = (1, 6)      # слои, из которых движок выращивает деревья
SHORE_HEIGHT = 0.5         # ниже этой высоты (м) деревьев быть не должно — это вода и урез
SHORE_MARGIN = 4           # на сколько отсчётов (метров) отодвинуть лес от воды
RIVER_MARGIN = 3           # то же для рек: русло плюс берег, метров
FLORA_BAN = None           # общая маска «здесь флоры быть не должно» (см. layer_weights)
SEA_NODE = 0.5             # доля воды, при которой узел считаем морским
HAS_WATER = 0.02           # доля воды, при которой узел обязан нести слой воды
HAS_DEEP = 0.01            # то же для глубокой воды
FOREST_LAYER = 1           # слой, из которого движок растит деревья
HAS_FOREST = 0.02          # доля леса, при которой узел обязан нести слой леса
OPEN_SEA = 0.8             # доля воды, при которой узел — открытое море
SEA_SET = (0, 2, 7, 8)     # единый набор слоёв открытого моря
ROADS = os.environ.get("EQ_ROADS", "1") != "0"   # рисовать ли дороги между поселениями
ROAD_LAYER = 4     # слой сухой земли (ground_earth) — им и рисуются дороги
SNOW_LINE = 22.0   # выше этой высоты на горах лежит снег, м
BLUR = 2           # радиус смягчения границ, в отсчётах (1 отсчёт = 1 м)
MIN_WEIGHT = 8     # доли слоя меньше этого (из 255) не записываем
# Порядок строк маски внутри узла. Проверено в игре (EQ_PAINT_PROBE=1: снежный круг под
# Пондеросой, песчаный в 30 м к северу): первая строка — южный край, как у высот.
ROW_ORDER = os.environ.get("EQ_WGHT_ROWS", "south")


def log(*a):
    print("[terrain]", *a, flush=True)


def box_blur(field, radius):
    """Среднее по квадрату (2r+1)^2 через накопленные суммы — scipy не нужен."""
    if radius <= 0:
        return field
    pad = np.pad(field, radius, mode="edge")
    k = 2 * radius + 1
    c = np.cumsum(np.cumsum(pad, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def layer_weights():
    """Доли слоёв на всей карте: (LAYERS, S, S), строка 0 — юг, сумма по слоям = 1."""
    terrain = equus_map.terrain_map()
    heights = equus_map.heights()
    if terrain.shape != heights.shape:
        raise SystemExit("карта местности %s и высот %s разного размера" % (terrain.shape, heights.shape))
    index = np.zeros(terrain.shape, dtype=np.int8)
    for kind, layer in LAYER_OF_TERRAIN.items():
        index[terrain == kind] = layer
    index[(index == 2) & (heights > SNOW_LINE)] = 3
    # Деревья движок растит из слоёв флоры, а у воды они оказываются в море. Убираем флору из самой
    # карты типов местности — до размытия и до дележа слоёв по узлам: тогда оба соседних узла видят
    # одинаковые данные и на границе не появляется шов (проверено в игре 18.09.2026).
    shore = heights < SHORE_HEIGHT
    if SHORE_MARGIN > 0:
        shore = box_blur(shore.astype(np.float32), SHORE_MARGIN) > 1e-3
    river = terrain == equus_map.RIVER
    river = reach_the_sea(river, np.isin(terrain, (equus_map.WATER, equus_map.LAKE)), log)
    # На реке деревья тоже не нужны, а сами собой они оттуда не уходят: река кладётся в веса
    # поверх готовой картины и гасит лес лишь на RIVER_STRENGTH, оставляя ему 15% — движку этого
    # хватает, чтобы посеять сосны прямо по руслу (замечено в игре 2026-09-22). Поэтому лес
    # убирается из самих видов местности по руслу и полосе берега.
    if RIVER_MARGIN > 0:
        near_river = box_blur(river.astype(np.float32), RIVER_MARGIN) > 1e-3
    else:
        near_river = river
    no_flora = shore | near_river
    for layer in FLORA_LAYERS:
        index[(index == layer) & no_flora] = substitute(layer, [k for k in range(LAYERS)
                                                               if k not in FLORA_LAYERS and k != WATER_LAYER])
    # под рекой — местность вокруг неё (берём из соседей по строке), сама река кладётся поверх
    for shift in (1, -1, 2, -2, 3, -3):
        fill = river & (index == 0) & ~np.roll(river, shift, 1)
        index[fill] = np.roll(index, shift, 1)[fill]
    if os.environ.get("EQ_PAINT_PROBE"):
        # Проверка ориентации масок: у Пондеросы (485.7, 461.9) всё трава, под ней снежный круг,
        # в 30 м к северу — песчаный.
        yy, xx = np.mgrid[0:terrain.shape[0], 0:terrain.shape[1]]
        k = (terrain.shape[0] - 1) / equus_map.MAP_SIZE
        cx, cy = 485.7 * k, 461.9 * k
        index[(xx - cx) ** 2 + (yy - cy) ** 2 < 100 ** 2] = 0
        index[(xx - cx) ** 2 + (yy - cy) ** 2 < 12 ** 2] = 3
        index[(xx - cx) ** 2 + (yy - cy - 30) ** 2 < 12 ** 2] = 5
    if os.environ.get("EQ_NODE_PROBE"):
        # Проверка, чем рисуется каждый слой: узлы вокруг (9,9) красятся полосами известных слоёв.
        plan = {(8, 10): [0], (9, 10): [4], (10, 10): [2],
                (8, 9): [0, 4], (9, 9): [0, 4, 7], (10, 9): [0, 2, 4, 7],
                (8, 8): [0, 1, 7], (9, 8): [4, 7], (10, 8): [0, 7]}
        for (nx, ny), layers in plan.items():
            for k, layer in enumerate(layers):
                x0 = nx * 64 + k * 64 // len(layers)
                x1 = nx * 64 + (k + 1) * 64 // len(layers) + 1
                index[ny * 64:ny * 64 + 65, x0:x1] = layer
    weights = np.stack([box_blur((index == layer).astype(np.float32), BLUR) for layer in range(LAYERS)])
    weights /= np.maximum(weights.sum(0), 1e-6)
    # Дороги между поселениями: в ванили они запечены в виртуальную текстуру карты, которой у нас
    # нет, поэтому прокладываем сами (tools/map_roads.py). Кладутся ПОСЛЕ размытия, как и реки:
    # если положить их в виды местности до него, дорога расплывается вдвое и читается не дорогой,
    # а светлой полосой в пол-обзора (замечено в игре 2026-09-22). Здесь же ширина и мягкость края
    # ровно те, что заданы в map_roads. Флора на дороге не вырастет: вес лесного слоя под ней
    # гаснет вместе с остальными.
    if ROADS:
        road = map_roads.mask(weights.shape[1], MOD, log)
        road *= 1.0 - np.clip(weights[WATER_LAYER] + weights[DEEP_LAYER], 0.0, 1.0)  # по воде не идём
        weights *= 1.0 - road
        weights[ROAD_LAYER] += road
        log("дороги: занято %.2f%% карты" % (100.0 * float((road > 0.5).mean())))
    # Реки поверх. Русло на карте местности — линия толщиной в отсчёт, и если класть её как есть
    # и не в полную силу, в игре выходит бледная голубая размазня: воды 85%, под ней просвечивает
    # трава, а край шириной в один текстурный отсчёт мажется фильтрацией. Поэтому делаем как с
    # дорогами — ленту постоянной ширины с мягким краем ровно в RIVER_SOFT и в полную силу, а по
    # сторонам кладём полосу сухой земли: это берег, без него вода лежит прямо на траве.
    # В ванили то же самое нарисовано художником прямо в запечённой текстуре карты, повторить её
    # нечем (Main_map/TileSets, 2.1 ГБ, печёт редактор для рельефа версии 1).
    core = box_blur(river.astype(np.float32), RIVER_CORE) > 1e-6
    banks = box_blur(core.astype(np.float32), RIVER_BANK) > 1e-6
    open_water = np.isin(terrain, (equus_map.WATER, equus_map.LAKE))
    bank = np.clip(box_blur((banks & ~core & ~open_water).astype(np.float32), 1), 0.0, 1.0)
    bank = bank * BANK_STRENGTH * (1.0 - open_water.astype(np.float32))
    weights *= 1.0 - bank
    weights[BANK_LAYER] += bank
    stream = np.clip(box_blur(core.astype(np.float32), RIVER_SOFT) * RIVER_GAIN, 0.0, 1.0)
    weights *= 1.0 - stream
    weights[WATER_LAYER] += stream
    log("реки: русло %.1f%% карты, берега %.1f%%"
        % (100.0 * float((stream > 0.5).mean()), 100.0 * float((bank > 0.2).mean())))
    # глубина: часть воды становится тёмной
    deep = np.clip((heights - DEEP_FROM) / (DEEP_TO - DEEP_FROM), 0.0, 1.0).astype(np.float32)
    weights[DEEP_LAYER] = weights[WATER_LAYER] * deep
    weights[WATER_LAYER] *= 1.0 - deep
    # Деревья растут из слоёв с флорой (1 — лес, 6 — болото): даже еле заметная маска на воде
    # даёт лес посреди моря. Поэтому там, где воды больше половины, флору убираем совсем,
    # а остаток весов перенормируем (проверено в игре 18.09.2026: деревья на севере в море).
    return weights


def reach_the_sea(river, sea, log):
    """Дотягивает русла до моря: в исходной карте они обрываются, не дойдя до берега.

    Ищем концы русел (точки, у которых меньше двух соседей по руслу) и, если рядом есть море,
    дорисовываем прямой отрезок до ближайшей его точки. Без этого у каждого устья остаётся
    перемычка суши между рекой и морем (замечено в игре 2026-09-22: из 3565 точек русла моря
    касались 40).
    """
    river = river.copy()
    a = river.astype(np.float32)
    around = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy or dx:
                around += np.roll(np.roll(a, dy, 0), dx, 1)
    ends = np.argwhere(river & (around <= 1.5))
    size = river.shape[0]
    joined = 0
    for y, x in ends:
        lo_y, hi_y = max(int(y) - MOUTH_REACH, 0), min(int(y) + MOUTH_REACH + 1, size)
        lo_x, hi_x = max(int(x) - MOUTH_REACH, 0), min(int(x) + MOUTH_REACH + 1, size)
        window = sea[lo_y:hi_y, lo_x:hi_x]
        if not window.any():
            continue
        ys, xs = np.nonzero(window)
        ys, xs = ys + lo_y, xs + lo_x
        best = np.argmin((ys - y) ** 2 + (xs - x) ** 2)
        ty, tx = int(ys[best]), int(xs[best])
        steps = max(abs(ty - int(y)), abs(tx - int(x)))
        if steps == 0:
            continue
        for i in range(steps + 1):
            py = int(round(y + (ty - y) * i / steps))
            px = int(round(x + (tx - x) * i / steps))
            river[py, px] = True
        joined += 1
    log("устья рек доведены до моря: %d" % joined)
    return river


def limit_node_layers(index, heights, per_node=64):
    """До сглаживания: в каждом узле не больше MAX_NODE_LAYERS видов местности.

    Какой вид выбросить, решаем не по одному узлу: если сосед выбросил другой, на границе видна
    прямая линия во всю клетку. Особенно на севере, где на четыре слота приходится пять видов
    (снег, лес, скалы, земля, вода) — там чанки были видны сплошняком (проверено 18.09.2026).
    Поэтому набор сохраняемых видов выбирается с оглядкой на соседей (KEEP_COHERENCE), а уже
    отброшенные заменяются похожими (substitute).
    """
    import itertools
    index = index.copy()
    n = (index.shape[0] - 1) // per_node
    areas, rooms, forced = {}, {}, {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            core = index[y0:y0 + per_node + 1, x0:x0 + per_node + 1]
            kinds, counts = np.unique(core, return_counts=True)
            areas[(ix, iy)] = {int(k): int(c) for k, c in zip(kinds.tolist(), counts.tolist())}
            # у глубокой воды свой слой: оставляем под него место
            deep = bool(((core == WATER_LAYER)
                         & (heights[y0:y0 + per_node + 1, x0:x0 + per_node + 1] < DEEP_FROM)).any())
            rooms[(ix, iy)] = MAX_NODE_LAYERS - (1 if deep else 0)
            forced[(ix, iy)] = {WATER_LAYER} if WATER_LAYER in areas[(ix, iy)] else set()

    total = float(index.size)
    global_share = {int(k): float(c) / total
                    for k, c in zip(*[a.tolist() for a in np.unique(index, return_counts=True)])}

    keep = {}
    for key, area in areas.items():
        order = sorted(area, key=lambda k: -area[k])
        keep[key] = (forced[key] | set(order))
        keep[key] = set(list(forced[key]) + [k for k in order if k not in forced[key]])
        keep[key] = set(list(keep[key])[:rooms[key]]) if len(keep[key]) > rooms[key] else keep[key]

    for _round in range(KEEP_ROUNDS):
        changed = 0
        for key in sorted(areas):
            ix, iy = key
            area, room = areas[key], rooms[key]
            if len(area) <= room:
                keep[key] = set(area)
                continue
            scale = max(area.values())
            neighbours = [keep[(ix + dx, iy + dy)] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                          if (ix + dx, iy + dy) in keep]
            must = forced[key] & set(area)
            rest = [k for k in area if k not in must]
            take = max(room - len(must), 0)
            best = None
            for combo in itertools.combinations(rest, min(take, len(rest))):
                chosen = must | set(combo)
                # к площади вида в узле добавляем его долю на всей карте: иначе в соседних узлах
                # выбрасываются РАЗНЫЕ виды и на границе видна прямая линия
                value = (sum(area[k] + GLOBAL_BIAS * scale * global_share.get(k, 0.0) for k in chosen)
                         + KEEP_COHERENCE * scale * sum(len(chosen & other) for other in neighbours))
                if best is None or value > best[0]:
                    best = (value, chosen)
            if best and best[1] != keep[key]:
                keep[key] = best[1]
                changed += 1
        if not changed:
            break

    changed = 0
    for key, area in areas.items():
        ix, iy = key
        y0, x0 = iy * per_node, ix * per_node
        core = index[y0:y0 + per_node + 1, x0:x0 + per_node + 1]
        for kind in sorted(area, key=lambda k: area[k]):
            if kind in keep[key]:
                continue
            target = substitute(int(kind), sorted(keep[key]))
            core[core == kind] = target
            changed += 1
    log("заменено мелких видов местности в узлах: %d" % changed)
    return index


def substitute(layer, allowed):
    """Похожий слой из allowed по цепочке SUBSTITUTE, иначе первый из allowed."""
    seen = set()
    while layer in SUBSTITUTE and layer not in seen:
        seen.add(layer)
        layer = SUBSTITUTE[layer]
        if layer in allowed:
            return layer
    if not allowed:
        return 0
    # Запасной слой берём не первый попавшийся: первым по номеру идёт лес, и в него утекали
    # вода со степью — на море вырастали деревья (проверено в игре 18.09.2026).
    return next((k for k in allowed if k not in FLORA_LAYERS), allowed[0])


def parse_chunk(chunk):
    """Кусок = таблица смещений (по 4 байта на узел) + 40 служебных байт + поток LZ4."""
    count = chunk.header_size // 4
    offsets = list(struct.unpack_from("<%dI" % count, chunk.data, 0))
    extra = list(struct.unpack_from("<10I", chunk.data, chunk.header_size))
    return offsets, extra


def build_chunk(extra, blobs):
    """Обратная сборка: таблица смещений, служебные числа, сжатый поток."""
    stream = b""
    offsets = []
    for blob in blobs:
        offsets.append(len(stream))
        stream += blob
    packed = tb.lz4_compress(stream)
    extra = list(extra)
    extra[2] = len(stream)        # длина без сжатия
    extra[4] = 40 + len(packed)   # длина потока ВМЕСТЕ с этими 40 служебными байтами
    header = b"".join(struct.pack("<I", o) for o in offsets)
    header += struct.pack("<10I", *extra)
    return header + packed


WATER_BONUS = 30      # во сколько раз вода важнее при выборе набора слоёв
# Глубокая вода — тоже тонкая полоса у берега: без своего веса она выпадала у соседнего
# узла, и в море была видна прямая граница между оттенками (проверено 18.09.2026).
DEEP_BONUS = 8
FEATHER = int(os.environ.get("EQ_FEATHER", "28"))   # ширина полосы у края узла, где слои
# сводятся к общим с соседом, отсчётов. Чем шире, тем мягче переход между узлами с разными
# наборами слоёв; 16 было мало — на севере, где видов местности больше слотов, стыки видно.
# Насколько согласие с соседями важнее собственных слоёв узла (в долях его же оценки).
# 0 — каждый узел сам по себе и на границах видны прямые линии; слишком много — карта
# теряет разнообразие. 0.12 подобрано по числу пар соседей с общими 4 слоями.
COHERENCE = float(os.environ.get("EQ_COHERENCE", "0.7"))
ROUNDS = 12           # проходов согласования, обычно сходится за 3-4
MIN_COMMON = 3        # сколько слоёв должно быть общих у соседних узлов
LAND_ORDER = [0, 4, 2, 1, 5, 3, 6, 7, 8]


def allowed(layer_set):
    """Сочетания, которые игра рисует неверно (проверено в игре): трава+степь+вода без скал."""
    return not (BROKEN_SET <= layer_set and PAD_LAYER not in layer_set)


def target_layer(layer, layer_set):
    """Куда отдать вес слоя, которого нет в наборе узла: похожий слой, иначе по порядку."""
    if layer in layer_set:
        return layer
    seen, x = set(), layer
    while x in SUBSTITUTE and x not in seen:
        seen.add(x)
        x = SUBSTITUTE[x]
        if x in layer_set:
            return x
    order = ([WATER_LAYER, DEEP_LAYER] if layer in (WATER_LAYER, DEEP_LAYER) else []) + LAND_ORDER
    return next(x for x in order if x in layer_set)


def project(part, layer_set):
    out = np.zeros_like(part)
    for layer in range(LAYERS):
        if part[layer].any():
            out[target_layer(layer, layer_set)] += part[layer]
    return out


def single_set(weights):
    """Один набор слоёв на всю карту, если видов местности не больше, чем слотов у узла.

    Берём слои по их весу на карте; вода и глубина идут с надбавкой — они тонкие по площади, но
    без них море и реки исчезают. Возвращает None, если всё не помещается: тогда набор выбирается
    для каждого узла отдельно, как раньше.
    """
    share = weights.reshape(LAYERS, -1).mean(1).astype(np.float64)
    score = share.copy()
    score[WATER_LAYER] *= WATER_BONUS
    score[DEEP_LAYER] *= DEEP_BONUS
    used = [k for k in range(LAYERS) if share[k] > 0.001]
    if len(used) > MAX_NODE_LAYERS:
        used = sorted(sorted(range(LAYERS), key=lambda k: -score[k])[:MAX_NODE_LAYERS])
    chosen = set(used)
    # добить до полного размера — узлы с неполным набором игра рисует неверно
    for layer in PAD_ORDER + LAND_ORDER:
        if len(chosen) >= MAX_NODE_LAYERS:
            break
        chosen.add(layer)
    if not allowed(chosen):
        chosen.add(PAD_LAYER)
    dropped = [k for k in range(LAYERS) if share[k] > 0.001 and k not in chosen]
    log("общий набор слоёв на всю карту: %s%s"
        % (sorted(chosen), (", не поместились: %s" % dropped) if dropped else ""))
    return sorted(chosen)


def choose_sets(weights, n, per_node):
    """Для каждого узла ровно MAX_NODE_LAYERS слоёв (узлы с 2-3 слоями игра рисует неверно).

    Набор выбирается не по одному узлу: у соседей должно быть как можно больше общих слоёв, иначе
    на границе видна прямая линия во всю длину узла — слой, которого у соседа нет, обрывается.
    Поэтому к оценке слоёв самого узла добавляется согласие с уже выбранными наборами соседей
    (COHERENCE), и выбор повторяется, пока не перестанет меняться.
    """
    import itertools
    size = weights.shape[1]
    total = float(weights.sum())
    map_share = (weights.sum(axis=(1, 2)) / max(total, 1e-6)).astype(np.float32)
    sums = {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            core = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1].sum(axis=(1, 2))
            ring = weights[:, max(y0 - FEATHER, 0):min(y0 + per_node + 1 + FEATHER, size),
                           max(x0 - FEATHER, 0):min(x0 + per_node + 1 + FEATHER, size)].sum(axis=(1, 2))
            score = core + 0.5 * (ring - core)
            # реки — тонкие линии и по площади всегда проигрывают, но без слоя воды они исчезают
            score[WATER_LAYER] *= WATER_BONUS
            score[DEEP_LAYER] *= DEEP_BONUS
            # Доля слоя на всей карте: без неё соседние узлы выбрасывают РАЗНЫЕ виды (на севере
            # их пять на четыре слота), и карта распадается на прямоугольники (проверено 18.09.2026).
            score = score + GLOBAL_BIAS * float(score.max()) * map_share
            sums[(ix, iy)] = score
    combos = [set(c) for c in itertools.combinations(range(LAYERS), MAX_NODE_LAYERS) if allowed(set(c))]
    # Морской узел обязан содержать оба слоя воды: если глубокая вода досталась одному узлу, а
    # соседу нет, в море виден тёмный квадрат во всю клетку (проверено в игре 18.09.2026).
    # Флоре в море делать нечего — из её слоёв движок выращивает деревья.
    choices = {}
    for iy in range(n):
        for ix in range(n):
            y0, x0 = iy * per_node, ix * per_node
            part = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1]
            water = float(part[WATER_LAYER].mean())
            deep = float(part[DEEP_LAYER].mean())
            need = set()
            forest = float(part[FOREST_LAYER].mean())
            if forest > HAS_FOREST:
                # деревья движок растит по слою леса: нет слоя — лес обрывается по краю узла
                need.add(FOREST_LAYER)
            if water > HAS_WATER:
                need.add(WATER_LAYER)
            if deep > HAS_DEEP:
                # у узла есть глубокая вода: без её слоя он выйдет светлее соседа, и в море
                # видна прямая граница в целую клетку (проверено в игре 18.09.2026)
                need.update((WATER_LAYER, DEEP_LAYER))
            allowed_here = [c for c in combos if need <= c]
            if water + deep > OPEN_SEA:
                # Открытое море: у всех таких узлов ОДИН набор слоёв. Иначе соседние узлы отличаются
                # не только глубиной, но и тем, что лежит под водой, и в море видна прямая граница
                # (проверено в игре 18.09.2026 на стыке узлов (14,15) и (15,15)).
                allowed_here = [set(SEA_SET)]
            elif water + deep > SEA_NODE:
                # почти сплошная вода: флоре тут делать нечего, иначе в море растут деревья
                no_flora = [c for c in allowed_here if not set(FLORA_LAYERS) & c]
                allowed_here = no_flora or allowed_here
            choices[(ix, iy)] = allowed_here or combos
    scale = {key: max(float(score.max()), 1.0) for key, score in sums.items()}
    # первый проход — без соседей, дальше согласуем
    sets = {key: max(choices[key], key=lambda c: sum(score[layer] for layer in c))
            for key, score in sums.items()}
    for _round in range(ROUNDS):
        changed = 0
        for key in sorted(sums):
            ix, iy = key
            score, own = sums[key], scale[key]
            neighbours = [sets[(ix + dx, iy + dy)] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                          if (ix + dx, iy + dy) in sets]

            def value(combo):
                same = sum(len(combo & other) for other in neighbours)
                return sum(score[layer] for layer in combo) + COHERENCE * own * same

            best = max(choices[key], key=value)
            if best != sets[key]:
                sets[key] = best
                changed += 1
        log("  согласование: проход %d, изменено узлов %d" % (_round, changed))
        if not changed:
            break

    # Добиваем оставшиеся слабые стыки (обычно берег: у моря {вода, глубина}, у суши трава со
    # скалами). Меняем в одном из узлов самый ненужный слой на слой соседа — так на общей границе
    # остаётся не меньше MIN_COMMON общих слоёв, и обрыва слоя во всю длину узла не видно.
    for _round in range(4):
        fixed = 0
        for (ix, iy) in sorted(sums):
            for dx, dy in ((1, 0), (0, 1)):
                key_b = (ix + dx, iy + dy)
                if key_b not in sets:
                    continue
                a, b = sets[(ix, iy)], sets[key_b]
                if len(a & b) >= MIN_COMMON:
                    continue
                best = None
                for key, other in (((ix, iy), b), (key_b, a)):
                    score, own = sums[key], scale[key]
                    current = sets[key]
                    for drop in current - other:
                        if drop == WATER_LAYER:
                            continue  # без воды исчезают реки и море
                        for add in other - current:
                            combo = (current - {drop}) | {add}
                            if combo not in choices[key]:
                                continue
                            loss = (score[drop] - score[add]) / own
                            if best is None or loss < best[0]:
                                best = (loss, key, combo)
                if best is not None:
                    sets[best[1]] = best[2]
                    fixed += 1
        if not fixed:
            break
    log("наборы слоёв: %d разных, север %d" % (
        len({frozenset(v) for v in sets.values()}),
        len({frozenset(v) for k, v in sets.items() if k[1] >= 10})))
    return sets


def node_part(weights, sets, ix, iy, n, per_node):
    """Веса узла: внутри — свой набор слоёв, к краю плавно — общий с соседями набор. На общем
    краю два соседа получают одинаковые веса, и шва нет."""
    y0, x0 = iy * per_node, ix * per_node
    part = weights[:, y0:y0 + per_node + 1, x0:x0 + per_node + 1]
    d = np.arange(per_node + 1, dtype=np.float32)
    low = np.clip(1.0 - d / FEATHER, 0.0, 1.0)
    high = low[::-1]
    ramp = {-1: low, 0: 1.0 - low - high, 1: high}
    out = np.zeros_like(part)
    missing = 0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            factor = ramp[dy][:, None] * ramp[dx][None, :]
            if not factor.any():
                continue
            layer_set = set(sets[(ix, iy)])
            for key in {(ix + a, iy + b) for a in {0, dx} for b in {0, dy}}:
                if key in sets:
                    layer_set &= sets[key]
            if not layer_set:
                layer_set = set(sets[(ix, iy)])
                missing += 1
            out += factor * project(part, layer_set)
    return out, missing


PROBE_SETS = [{0, 2, 4, 7}, {2, 4, 5, 6}, {1, 2, 3, 4}, {2, 3, 4, 5}]


def set_probe(weights, sets, per_node):
    """Проба смешивания: в узлах (8..11, 9) и (8..11, 10) плавный переход скалы -> земля слева
    направо, наборы слоёв в соседних узлах разные. Ряд 9 — доли слоёв (как пишем сейчас),
    ряд 10 — «накопительная» запись: маска слоя = его доля среди него и слоёв ниже."""
    out = {}
    total = 4 * per_node + 1
    for row, cumulative in ((9, False), (10, True)):
        for k, layer_set in enumerate(PROBE_SETS):
            ix = 8 + k
            sets[(ix, row)] = set(layer_set)
            x = (np.arange(per_node + 1) + k * per_node) / (total - 1)
            ramp = np.tile(x[None, :], (per_node + 1, 1)).astype(np.float32)
            part = np.zeros((LAYERS, per_node + 1, per_node + 1), dtype=np.float32)
            rock, dirt = 1.0 - ramp, ramp
            if cumulative:
                part[2] = np.where(rock > 0, 1.0, 0.0)   # слой 2 ниже слоя 4 во всех наборах
                part[4] = dirt
            else:
                part[2], part[4] = rock, dirt
            out[(ix, row)] = part
    return out


def to_alpha(part, present):
    """Доли слоёв -> маски, как их понимает игра. Проверено пробой (EQ_SET_PROBE): игра кладёт
    слои узла по очереди, от меньшего номера к большему, и маска слоя — его непрозрачность поверх
    уже нарисованного. Значит, маска слоя = его доля среди него самого и слоёв ниже. Нижний слой
    закрывает всё (иначе под ним чёрное — отсюда были тёмные узлы). Если писать просто доли,
    результат зависит от набора слоёв узла, и на границе узлов виден шов."""
    alpha = np.zeros_like(part)
    below = np.zeros(part.shape[1:], dtype=part.dtype)
    for k, layer in enumerate(present):
        below = below + part[layer]
        if k == 0:
            alpha[layer] = 1.0
        else:
            alpha[layer] = np.where(below > 1e-6, part[layer] / np.maximum(below, 1e-6), 0.0)
    return alpha


def main():
    version, chunks, _blob = tb.read(TERRAIN)
    weight_chunk = {c.name: c for c in chunks}["WGHT"]
    offsets, extra = parse_chunk(weight_chunk)

    tree = ET.parse(SCENE)
    root = tree.getroot()
    terrain_node = root.find(".//terrain")
    n = int(terrain_node.get("node_dimension_x"))
    if int(terrain_node.get("node_dimension_y")) != n or len(offsets) != n * n:
        raise SystemExit("ожидался квадратный рельеф: узлов в файле %d, в сцене %sx%s"
                         % (len(offsets), n, terrain_node.get("node_dimension_y")))
    nodes = {(int(e.get("idx")), int(e.get("idy"))): e for e in terrain_node.find("nodes").findall("node")}
    per_node = 64
    log("узлов рельефа: %dx%d, по %d отсчётов" % (n, n, per_node))

    weights = layer_weights()
    shares = weights.reshape(LAYERS, -1).mean(1)
    log("доли слоёв на карте: " + ", ".join("%d:%.0f%%" % (i, v * 100) for i, v in enumerate(shares)))

    blobs = []
    used_layers = {}
    common = single_set(weights)
    if common is not None:
        sets = {(ix, iy): set(common) for iy in range(n) for ix in range(n)}
    else:
        sets = choose_sets(weights, n, per_node)
    probe = set_probe(weights, sets, per_node) if os.environ.get("EQ_SET_PROBE") else {}
    no_common = 0
    for i in range(n * n):
        ix, iy = i % n, i // n
        node = nodes[(ix, iy)]
        slots = len(node.find(".//variable[@name='weightmap_levels']").findall("variable"))
        part, missing = node_part(weights, sets, ix, iy, n, per_node)
        if (ix, iy) in probe:
            part = probe[(ix, iy)]
        no_common += missing
        present = sorted(sets[(ix, iy)])
        if (ix, iy) in probe:
            alpha = part
        else:
            alpha = to_alpha(part, present)
        values = np.rint(np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        if ROW_ORDER == "north":
            values = values[:, ::-1, :]
        blob = b""
        for slot in range(slots):
            if slot in present:
                size = values.shape[1]
                rows = [values[slot, y].tobytes() for y in range(size)]
                image = tb.make_png(values.shape[2], size, 8, 0, rows)
                blob += struct.pack("<II", 1, len(image)) + image
            else:
                blob += struct.pack("<I", 0)
        blobs.append(blob)
        used_layers[(ix, iy)] = present

    log("наборы слоёв согласованы с соседями; участков без общего слоя: %d" % no_common)
    weight_chunk.data = build_chunk(extra, blobs)
    weight_chunk.header_size = 4 * len(blobs)
    weight_chunk.raw_length = struct.unpack_from("<I", weight_chunk.data, weight_chunk.header_size + 8)[0]
    backup = TERRAIN + ".bak"
    if not os.path.exists(backup):
        import shutil
        shutil.copy2(TERRAIN, backup)
        log("резервная копия", backup)
    tb.write(TERRAIN, version, chunks)
    log("записан %s (веса: %d байт)" % (TERRAIN, len(weight_chunk.data)))

    for key, node in nodes.items():
        mask = 0
        for layer in used_layers[key]:
            mask |= 1 << layer
        for season in ("summer", "fall", "winter", "spring"):
            node.set("layer_is_used_mask_%s" % season, str(mask))
        node.set("layer_is_used_mask", "true")
        levels = node.find(".//variable[@name='weightmap_levels']")
        if levels is not None:
            for variable in levels.findall("variable"):
                layer = int(variable.get("layer"))
                variable.set("value", "6" if (mask >> layer) & 1 else "0")
    ET.indent(root, space="\t")
    tree.write(SCENE, encoding="utf-8", xml_declaration=True)
    log("в сцене обновлены маски используемых слоёв")


if __name__ == "__main__":
    main()
