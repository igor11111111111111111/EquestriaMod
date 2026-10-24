# -*- coding: utf-8 -*-
"""Мосты там, где дорога пересекает реку.

  Вызывается из make_map_entities.py: place(entities, log).

Как устроен мост у ванили (Main_map/scene.xscene): это не один меш, а связка. Родительская
сущность несёт поворот и масштаб (1.120, 0.735, 0.735), а внутри лежат несколько одинаковых
`map_bridge_b` с мешем `mi_emp_bridge_wooden` в масштабе 3.74, сдвинутых друг за другом по
локальной оси Y — так набирается нужная длина настила. Проверено по 32 ванильным мостам: поворот
родителя по Z совпадает с направлением РЕКИ в этой точке (у ближних мостов расхождение 1..13
градусов), то есть настил идёт вдоль локальной Y, поперёк воды. Мы повторяем ту же связку и
ставим её поперёк реки — вдоль дороги.
"""
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import map_roads  # noqa: E402

# Расстановка выключена: мосты ставятся вручную в редакторе (автоматические вставали криво —
# отряд пересекает реку под своим углом, а настил повторяет направление дороги в точке,
# и на извилистых руслах это заметно). Включить: EQ_BRIDGES=1. Старые eq_bridge_* при
# перегенерации сцены убираются в любом случае, чтобы не мешали расставленным вручную.
ENABLED = os.environ.get("EQ_BRIDGES", "0") != "0"
PREFIX = "eq_bridge_"          # по этому имени мосты удаляются при перегенерации
SEGMENTS = 7                   # звеньев настила; ванильные мосты собраны из 3-5
SEGMENT_STEP = 1.27            # шаг звена в локальных единицах родителя (как у ванили)
PARENT_SCALE = (1.120, 0.735, 0.735)
CHILD_SCALE = 3.740
CHILD_X = 0.130
CHILD_Z = -0.950
MESH = "mi_emp_bridge_wooden"
PHYSICS = "bo_mi_emp_bridge_wooden"
SAMPLE = 0.5                   # шаг проверки вдоль дороги, м
RIVER_REACH = 2.0              # насколько расширить русло при поиске пересечений, м
APART = 8.0                    # ближе этого пересечения считаем одним мостом, м


def log_nothing(*a):
    pass


def crossings(mod, log=log_nothing):
    """Точки, где дорога пересекает реку: (x, y, угол дороги)."""
    terrain = equus_map.terrain_map()
    size = terrain.shape[0]
    step = equus_map.MAP_SIZE / (size - 1)
    river = terrain == equus_map.RIVER
    if RIVER_REACH > 0:
        radius = max(int(round(RIVER_REACH / step)), 1)
        wide = np.zeros_like(river)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                wide |= np.roll(np.roll(river, dy, 0), dx, 1)
        river = wide

    found = []
    for line in map_roads.routes(mod, log_nothing):
        run = []
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            steps = max(int(length / SAMPLE), 1)
            for i in range(steps + 1):
                t = i / steps
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                cy, cx = int(round(y / step)), int(round(x / step))
                if not (0 <= cy < size and 0 <= cx < size):
                    continue
                if river[cy, cx]:
                    run.append((x, y, math.atan2(y1 - y0, x1 - x0)))
                elif run:
                    found.append(run)
                    run = []
        if run:
            found.append(run)

    spots = []
    for run in found:
        middle = run[len(run) // 2]
        if any(math.hypot(middle[0] - s[0], middle[1] - s[1]) < APART for s in spots):
            continue
        spots.append(middle)
    log("мостов: пересечений дорог с реками %d" % len(spots))
    return spots


def place(entities, log=log_nothing, mod="Module"):
    """Вписывает мосты в раздел entities сцены."""
    for entity in list(entities):
        if (entity.get("name") or "").startswith(PREFIX):
            entities.remove(entity)

    if not ENABLED:
        log("мосты расставляются вручную в редакторе (EQ_BRIDGES=1 — ставить самим)")
        return []

    count = 0
    for index, (x, y, road_angle) in enumerate(crossings(mod, log)):
        height = float(equus_map.height(x, y))
        parent = ET.SubElement(entities, "game_entity")
        parent.set("name", "%s%d" % (PREFIX, index))
        parent.set("old_prefab_name", "")
        transform = ET.SubElement(parent, "transform")
        transform.set("position", "%.3f, %.3f, %.3f"
                      % (x, y, height - CHILD_Z * PARENT_SCALE[2]))
        # настил идёт вдоль локальной Y, поэтому поворачиваем родителя поперёк дороги
        transform.set("rotation_euler", "0.000, 0.000, %.3f" % (road_angle + math.pi / 2))
        transform.set("scale", "%.3f, %.3f, %.3f" % PARENT_SCALE)
        children = ET.SubElement(parent, "children")
        for k in range(SEGMENTS):
            offset = (k - (SEGMENTS - 1) / 2.0) * SEGMENT_STEP
            child = ET.SubElement(children, "game_entity")
            child.set("name", "map_bridge_b")
            child.set("old_prefab_name", "")
            child_transform = ET.SubElement(child, "transform")
            child_transform.set("position", "%.3f, %.3f, %.3f" % (CHILD_X, offset, CHILD_Z))
            child_transform.set("rotation_euler", "0.000, 0.000, 0.000")
            child_transform.set("scale", "%.3f, %.3f, %.3f" % ((CHILD_SCALE,) * 3))
            physics = ET.SubElement(child, "physics")
            physics.set("shape", PHYSICS)
            components = ET.SubElement(child, "components")
            mesh = ET.SubElement(components, "meta_mesh_component")
            mesh.set("name", MESH)
        count += 1
    log("мостов поставлено: %d, длина настила %.1f м"
        % (count, (SEGMENTS - 1) * SEGMENT_STEP * PARENT_SCALE[1]))
    return [MESH]


if __name__ == "__main__":
    def show(*a):
        print("[bridges]", *a, flush=True)

    where = sys.argv[1] if len(sys.argv) > 1 else "Module"
    spots = crossings(where, show)
    # список пересечений в файл — по нему удобно расставлять мосты вручную в редакторе
    listing = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "map", "bridge_spots.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("# Где дорога пересекает реку: x, y, направление дороги в градусах.\n")
        f.write("# Настил моста идёт вдоль локальной оси Y, значит поворот по Z = угол дороги + 90.\n")
        for sx, sy, angle in spots:
            f.write("%.1f\t%.1f\t%.0f\n" % (sx, sy, math.degrees(angle) % 180))
    show("список пересечений записан в %s" % listing)
