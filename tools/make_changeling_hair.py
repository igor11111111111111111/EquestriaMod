"""A mane like Queen Chrysalis's - a real hairstyle (hair slot in the appearance editor), not an item.

Run (headless Blender, on the finished pony):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_changeling_hair.py -- ../assets/changeling_hair

Shared hairstyle code (head, ears, eye zone, weights, export) is in tools/hair_common.py.
The mane is built from solid shell layers: neighbouring strand lines form strips, each strip is its own
"card" of the vanilla strand texture (assets/reference/vanilla_hair/female_hair_cards.json), root at the top
of the card, tips at the bottom. Normals face outward from the head and back, as in vanilla hairstyles.
Strands go around the ears (a cutout) and the eyes (EyeZone: anything in front of an eye is pushed to its edge).
"""
import json
import math
import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hair_common import (HERE, MeshBuilder, direction, export, hair_line, hairline_dir,  # noqa: E402
                         preview)

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
CARDS = json.load(open(os.path.join(HERE, "..", "assets", "reference", "vanilla_hair", "female_hair_cards.json")))["cards"]
CARDS = [c for c in CARDS if c["density"] > 0.5]  # thin single strands are not used

# Variants: mane length behind the back, length of the strands at the muzzle (0 - none), strand to one side
VARIANTS = {
    "eq_hair_chrysalis_short": {"back": 0.10, "front": 0.0, "side": None},
    "eq_hair_chrysalis_medium": {"back": 0.30, "front": 0.16, "side": None},
    "eq_hair_chrysalis_long": {"back": 0.58, "front": 0.34, "side": None},
    "eq_hair_chrysalis_side": {"back": 0.50, "front": 0.40, "side": 1.0},
}
N_SCALP = 14


class ShellHair(MeshBuilder):
    def shell(self, lines, first_card=0):
        rows = min(len(l) for l in lines)
        for i in range(len(lines) - 1):
            card = CARDS[(first_card + i) % len(CARDS)]
            left, right = lines[i], lines[i + 1]
            prev = None
            for j in range(rows):
                s = j / (rows - 1)
                v = card["v_top"] + (card["v_bottom"] - card["v_top"]) * s
                row = ((self.vertex(left[j]), card["u0"], v), (self.vertex(right[j]), card["u1"], v))
                if prev:
                    self.face((prev[0][0], prev[1][0], row[1][0], row[0][0]),
                              [(u, vv) for _, u, vv in (prev[0], prev[1], row[1], row[0])])
                prev = row
            self.parts += 1


def build(name, back, front, side):
    hair = ShellHair(name)
    rng = np.random.default_rng(7)
    sway = (side or 0.0) * 0.3

    def layer(across, offset, hang_mul, lift, first_card):
        n_hang = max(2, int(back * hang_mul / 0.02))
        lines = []
        for a in across:
            jitter = 1.0 + rng.uniform(-0.12, 0.12)
            hang = back * hang_mul * (0.85 + 0.15 * math.cos(math.pi * a / 2)) * jitter
            down = Vector((sway, 0.35 + 0.25 * (1 - abs(a)), -1.0)).normalized()
            exit_dir = direction(95 * a, -20)
            lines.append(hair_line(hairline_dir(a, lift), exit_dir, hang, offset, down, 0.5, N_SCALP, n_hang))
        hair.shell(lines, first_card)

    # main mass and the outer layer on top of it
    layer(np.linspace(-1.0, 1.0, 25), 0.006, 1.0, 0.0, 0)
    layer(np.linspace(-0.85, 0.85, 19), 0.02, 1.06, -4.0, 2)
    # strands at the muzzle: from the hairline in front of the ears - back past the eye and down onto the chest
    if front > 0:
        for sgn in ((side,) if side else (-1.0, 1.0)):
            n_hang = max(2, int(front / 0.02))
            lines = []
            for a in np.linspace(0.7, 1.0, 6):
                down = Vector((sgn * 0.05, -0.45, -1.0)).normalized()
                exit_dir = direction(sgn * 98, -20)
                hang = front * (1.0 + rng.uniform(-0.1, 0.1))
                lines.append(hair_line(hairline_dir(sgn * a, -2.0), exit_dir, hang, 0.014, down, 0.0, N_SCALP, n_hang))
            if sgn < 0:
                lines.reverse()
            hair.shell(lines, 1)
    return hair.to_object()


objects = [build(name, **v) for name, v in VARIANTS.items()]

# ---------------------------------------------------------------- fitting to the race's head
# The mane is built on the PONY head (hair_common finds its scalp by the atlas cell SKIN_CELL, while the new
# changeling model has its own atlas, and the scalp cannot be found by it). The new head's skull is smaller and
# narrower, so the hood-mane hung around it with a gap - "floating above the head" (noticed in game
# 24.09.2026). We shrink it toward the middle of the skull and move it forward.
FIT_SCALE = 0.92                    # how much to shrink the mane toward the middle of the skull
FIT_ABOUT = Vector((0.0, 0.02, 1.70))   # middle of the new head's skull
FIT_SHIFT = Vector((0.0, -0.035, -0.01))  # forward toward the back of the head and slightly down

for ob in objects:
    for v in ob.data.vertices:
        v.co = FIT_ABOUT + (v.co - FIT_ABOUT) * FIT_SCALE + FIT_SHIFT
print("[hair] грива подогнана под голову расы: масштаб %.2f, сдвиг (%.3f, %.3f, %.3f)"
      % (FIT_SCALE, *FIT_SHIFT), flush=True)

export(objects, os.path.join(OUT, "eq_changeling_hair.fbx"))
preview(objects, os.path.join(OUT, "preview"), (0.3, 0.95, 0.95))
