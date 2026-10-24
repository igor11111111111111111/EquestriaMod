# -*- coding: utf-8 -*-
"""Карта проходимости для скорости отрядов: где идти тяжелее.

  py -3 tools/make_speed_map.py [папка Module]

Ванильная модель скорости (DefaultPartySpeedCalculatingModel) смотрит ТОЛЬКО на тип грани сетки
проходимости и умеет всего три вещи: лес -30%, вода и броды -30%, пустыня и дюны -10%. У гор
штрафа нет вовсе — в ванили горы просто непроходимы. У нас горы проходимы (иначе карта Эквуса
распадается на куски), и размечены они как степь, потому что настоящий тип Mountain игра считает
непроходимым. Поэтому отдельная карта: на ней для каждой клетки записан множитель скорости,
а применяет его src/EquestriaPartySpeed.cs поверх ванильных правил.

Файл: Module/ModuleData/equestria_speed_map.bin — "EQSP", размер сетки, размер карты в метрах,
дальше по байту на клетку множитель скорости в процентах (100 — без изменений), а следом ещё
столько же байт: почему замедление (0 — местность, 1 — река), чтобы в разборе скорости писать
«Брод», а не «Тяжёлая местность».

Реку нельзя разметить в сетке проходимости: тип River игра считает НЕпроходимым (в наборе
проходимых только 1,2,3,4,5,6,15,16,17,20), и грани по 10 м перерезали бы карту. Поэтому
замедление на воде тоже отсюда.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else "Module"
GRID = 256                  # клеток по стороне: 1024 м / 256 = 4 м на клетку
OUT = os.path.join(MOD, "ModuleData", "equestria_speed_map.bin")

# Множители по виду местности. Лес и пустыню не трогаем — их уже штрафует сама игра, иначе
# штраф удвоится. Единица означает «как на равнине».
BY_KIND = {
    equus_map.MOUNTAIN: 0.70,   # камни и осыпи
    equus_map.SWAMP: 0.80,      # топь
    equus_map.SNOW: 0.85,       # снег
    equus_map.FOREST: 1.00,     # уже -30% у игры
    equus_map.DESERT: 1.00,     # уже -10% у игры
    equus_map.STEPPE: 0.95,     # холмы и сухая земля
    equus_map.PLAIN: 1.00,
}
# Уклон. Мерить его надо по нашей же карте, иначе штраф ложится и на равнину: медиана уклона на
# равнине 0.10, в степи и на холмах 0.42, в горах 0.59. Поэтому до SLOPE_FROM штрафа нет вовсе.
SLOPE_FROM = 0.25      # пологие места не штрафуем
SLOPE_FULL = 0.90      # здесь штраф за крутизну наибольший
SLOPE_PENALTY = 0.30   # каков этот штраф
FLOOR = 0.55           # ниже не опускаемся: иначе отряды в горах почти стоят
RIVER_FACTOR = 0.70    # брод: столько же, сколько ванильная игра берёт за переход воды
RIVER_REACH = 2        # на сколько метров расширить русло: у нарисованной ленты ширина ~3 м


def log(*a):
    print("[speed]", *a, flush=True)


def main():
    terrain = equus_map.terrain_map()
    heights = equus_map.heights().astype(np.float32)
    size = heights.shape[0]
    step = equus_map.MAP_SIZE / (size - 1)
    gy, gx = np.gradient(heights, step)
    slope = np.sqrt(gx ** 2 + gy ** 2)

    factor = np.ones(terrain.shape, dtype=np.float32)
    for kind, value in BY_KIND.items():
        factor[terrain == kind] = value
    steep = np.clip((slope - SLOPE_FROM) / (SLOPE_FULL - SLOPE_FROM), 0.0, 1.0)
    factor *= 1.0 - SLOPE_PENALTY * steep
    # Река: полоса брода поверх всего остального. Русло на карте местности — линия в один
    # отсчёт, поэтому расширяем её до ширины нарисованной ленты, иначе при усреднении по клетке
    # в 4 м замедление почти не чувствуется.
    river = terrain == equus_map.RIVER
    if RIVER_REACH > 0:
        radius = int(round(RIVER_REACH / step))
        wide = np.zeros_like(river)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                wide |= np.roll(np.roll(river, dy, 0), dx, 1)
        river = wide
    factor[river] = np.minimum(factor[river], RIVER_FACTOR)
    factor = np.clip(factor, FLOOR, 1.0)

    # ужимаем до сетки: берём среднее по клетке, чтобы отряд не дёргался на каждом метре
    take = np.linspace(0, size - 1, GRID + 1).round().astype(int)
    cells = np.zeros((GRID, GRID), dtype=np.uint8)
    why = np.zeros((GRID, GRID), dtype=np.uint8)
    for j in range(GRID):
        for i in range(GRID):
            ys = slice(take[j], max(take[j + 1], take[j] + 1))
            xs = slice(take[i], max(take[i + 1], take[i] + 1))
            cells[j, i] = int(round(float(factor[ys, xs].mean()) * 100))
            # клетка считается речной, если река занимает хотя бы треть её площади
            why[j, i] = 1 if float(river[ys, xs].mean()) > 0.33 else 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(b"EQSP")
        f.write(struct.pack("<ii", GRID, int(round(equus_map.MAP_SIZE))))
        f.write(cells.tobytes())
        f.write(why.tobytes())
    share = {name: float((cells <= limit).mean()) for name, limit in
             (("тяжелее 30%", 70), ("тяжелее 15%", 85), ("без штрафа", 99))}
    log("записан %s: сетка %dx%d по %.1f м" % (OUT, GRID, GRID, equus_map.MAP_SIZE / GRID))
    log("клеток " + ", ".join("%s — %.0f%%" % (k, 100 * v) for k, v in share.items()))
    log("самая тяжёлая клетка: %d%% скорости" % int(cells.min()))
    log("речных клеток (брод): %d, средний множитель на них %.2f"
        % (int(why.sum()), float(cells[why == 1].mean()) / 100 if why.any() else 1.0))


if __name__ == "__main__":
    main()
