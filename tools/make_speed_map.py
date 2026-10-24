# -*- coding: utf-8 -*-
"""Passability map for party speed: where the going is harder.

  py -3 tools/make_speed_map.py [Module folder]

The vanilla speed model (DefaultPartySpeedCalculatingModel) looks ONLY at the navmesh face type
and can do just three things: forest -30%, water and fords -30%, desert and dunes -10%. Mountains
have no penalty at all - in vanilla mountains are simply impassable. In our mod mountains are passable
(otherwise the map of Equus falls apart into pieces), and they are marked as steppe, because the game
treats the real Mountain type as impassable. Hence a separate map: it stores a speed multiplier for
every cell, and src/EquestriaPartySpeed.cs applies it on top of the vanilla rules.

File: Module/ModuleData/equestria_speed_map.bin - "EQSP", grid size, map size in metres,
then one byte per cell with the speed multiplier in percent (100 - unchanged), followed by as many
bytes again: why it slows down (0 - terrain, 1 - river), so that the speed breakdown can say
"Ford" rather than "Rough terrain".

A river cannot be marked in the navmesh: the game treats the River type as IMpassable (the passable
set is only 1,2,3,4,5,6,15,16,17,20), and 10 m faces would cut the map apart. So the
slowdown on water comes from here too.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equus_map  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else "Module"
GRID = 256                  # cells per side: 1024 m / 256 = 4 m per cell
OUT = os.path.join(MOD, "ModuleData", "equestria_speed_map.bin")

# Multipliers by terrain kind. Forest and desert are left alone - the game itself already penalizes them,
# otherwise the penalty doubles. One means "as on a plain".
BY_KIND = {
    equus_map.MOUNTAIN: 0.70,   # rocks and scree
    equus_map.SWAMP: 0.80,      # bog
    equus_map.SNOW: 0.85,       # snow
    equus_map.FOREST: 1.00,     # already -30% from the game
    equus_map.DESERT: 1.00,     # already -10% from the game
    equus_map.STEPPE: 0.95,     # hills and dry ground
    equus_map.PLAIN: 1.00,
}
# Slope. It has to be measured on our own map, otherwise the penalty falls on the plain too: median slope on
# the plain 0.10, on steppe and hills 0.42, in the mountains 0.59. So there is no penalty at all up to SLOPE_FROM.
SLOPE_FROM = 0.25      # gentle spots are not penalized
SLOPE_FULL = 0.90      # the steepness penalty is greatest here
SLOPE_PENALTY = 0.30   # how big that penalty is
FLOOR = 0.55           # we do not go lower: otherwise parties in the mountains almost stand still
RIVER_FACTOR = 0.70    # ford: as much as vanilla takes for crossing water
RIVER_REACH = 2        # how many metres to widen the riverbed by: the painted ribbon is ~3 m wide


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
    # River: a ford strip on top of everything else. The riverbed on the terrain map is a line one
    # sample wide, so we widen it to the width of the painted ribbon, otherwise when averaged over a
    # 4 m cell the slowdown is barely felt.
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

    # shrink to the grid: take the mean over the cell so the party does not jerk at every metre
    take = np.linspace(0, size - 1, GRID + 1).round().astype(int)
    cells = np.zeros((GRID, GRID), dtype=np.uint8)
    why = np.zeros((GRID, GRID), dtype=np.uint8)
    for j in range(GRID):
        for i in range(GRID):
            ys = slice(take[j], max(take[j + 1], take[j] + 1))
            xs = slice(take[i], max(take[i + 1], take[i] + 1))
            cells[j, i] = int(round(float(factor[ys, xs].mean()) * 100))
            # a cell counts as river if the river covers at least a third of its area
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
