# -*- coding: utf-8 -*-
"""Bridges where a road crosses a river.

  Called from make_map_entities.py: place(entities, log).

How a vanilla bridge is built (Main_map/scene.xscene): it is not one mesh but a group. The parent
entity carries the rotation and scale (1.120, 0.735, 0.735), and inside lie several identical
`map_bridge_b` with the mesh `mi_emp_bridge_wooden` at scale 3.74, shifted one after another along
the local Y axis; that is how the needed deck length is built up. Checked on 32 vanilla bridges: the parent's
Z rotation matches the direction of the RIVER at that point (for nearby bridges the difference is 1..13
degrees), i.e. the deck runs along local Y, across the water. We repeat the same group and
place it across the river, along the road.
"""
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402
import map_roads  # noqa: E402

# Placement is disabled: bridges are placed by hand in the editor (automatic ones came out crooked:
# a party crosses the river at its own angle, while the deck follows the road direction at the point,
# and on winding river beds this is noticeable). To enable: EQ_BRIDGES=1. Old eq_bridge_* are removed
# on scene regeneration in any case, so they do not get in the way of the hand-placed ones.
ENABLED = os.environ.get("EQ_BRIDGES", "0") != "0"
PREFIX = "eq_bridge_"          # bridges are removed by this name on regeneration
SEGMENTS = 7                   # deck segments; vanilla bridges are built from 3-5
SEGMENT_STEP = 1.27            # segment step in the parent's local units (as in vanilla)
PARENT_SCALE = (1.120, 0.735, 0.735)
CHILD_SCALE = 3.740
CHILD_X = 0.130
CHILD_Z = -0.950
MESH = "mi_emp_bridge_wooden"
PHYSICS = "bo_mi_emp_bridge_wooden"
SAMPLE = 0.5                   # check step along the road, m
RIVER_REACH = 2.0              # how much to widen the river bed when searching for crossings, m
APART = 8.0                    # crossings closer than this count as one bridge, m


def log_nothing(*a):
    pass


def crossings(mod, log=log_nothing):
    """Points where a road crosses a river: (x, y, road angle)."""
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
    """Writes bridges into the scene's entities section."""
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
        # the deck runs along local Y, so we turn the parent across the road
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
    # the list of crossings to a file; it is handy for placing bridges by hand in the editor
    listing = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "map", "bridge_spots.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("# Где дорога пересекает реку: x, y, направление дороги в градусах.\n")
        f.write("# Настил моста идёт вдоль локальной оси Y, значит поворот по Z = угол дороги + 90.\n")
        for sx, sy, angle in spots:
            f.write("%.1f\t%.1f\t%.0f\n" % (sx, sy, math.degrees(angle) % 180))
    show("список пересечений записан в %s" % listing)
