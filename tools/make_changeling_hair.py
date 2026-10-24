"""Грива как у королевы Кризалис — настоящая причёска (слот волос в редакторе внешности), не предмет.

Запуск (headless Blender, на готовой пони):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_changeling_hair.py -- ../assets/changeling_hair

Общее для причёсок (голова, уши, зона глаз, веса, экспорт) — tools/hair_common.py.
Грива собрана из сплошных слоёв-оболочек: соседние линии прядей образуют полосы, каждая полоса — своя
«карточка» ванильной текстуры прядей (assets/reference/vanilla_hair/female_hair_cards.json), корень сверху
карточки, кончики снизу. Нормали смотрят наружу от головы и спины, как у ванильных причёсок.
Пряди обходят уши (вырез) и глаза (EyeZone: всё, что попадает перед глазом, сдвигается к его краю).
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
CARDS = [c for c in CARDS if c["density"] > 0.5]  # тонкие одиночные пряди не берём

# Варианты: длина гривы за спиной, длина прядей у морды (0 — без них), прядь на одну сторону
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

    # основная масса и внешний слой поверх неё
    layer(np.linspace(-1.0, 1.0, 25), 0.006, 1.0, 0.0, 0)
    layer(np.linspace(-0.85, 0.85, 19), 0.02, 1.06, -4.0, 2)
    # пряди у морды: от линии волос перед ушами — назад за глаз и вниз, на грудь
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

# ---------------------------------------------------------------- подгонка под голову расы
# Грива строится по голове ПОНИ (hair_common берёт её скальп по клетке атласа SKIN_CELL, а у новой
# модели чейнджлинга свой атлас, и по нему скальп не найти). Череп у новой головы меньше и уже,
# поэтому грива-капюшон висела вокруг него с зазором — «парит над головой» (замечено в игре
# 24.09.2026). Ужимаем её к середине черепа и подаём вперёд.
FIT_SCALE = 0.92                    # во сколько раз ужать гриву к середине черепа
FIT_ABOUT = Vector((0.0, 0.02, 1.70))   # середина черепа новой головы
FIT_SHIFT = Vector((0.0, -0.035, -0.01))  # вперёд к затылку и чуть вниз

for ob in objects:
    for v in ob.data.vertices:
        v.co = FIT_ABOUT + (v.co - FIT_ABOUT) * FIT_SCALE + FIT_SHIFT
print("[hair] грива подогнана под голову расы: масштаб %.2f, сдвиг (%.3f, %.3f, %.3f)"
      % (FIT_SCALE, *FIT_SHIFT), flush=True)

export(objects, os.path.join(OUT, "eq_changeling_hair.fbx"))
preview(objects, os.path.join(OUT, "preview"), (0.3, 0.95, 0.95))
