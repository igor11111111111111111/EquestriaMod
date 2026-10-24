# -*- coding: utf-8 -*-
"""Smooth out the crumpled dip in the middle of the chest (same technique as for the armpit).

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_relax_chest.py
"""
import numpy as np
import bpy

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_body"]
me = ob.data
P = np.array([v.co[:] for v in me.vertices])
neighbours = [[] for _ in range(len(P))]
for e in me.edges:
    neighbours[e.vertices[0]].append(e.vertices[1])
    neighbours[e.vertices[1]].append(e.vertices[0])

# only the middle of the chest; the armpit on the sides is already smoothed separately
region = [i for i in range(len(P)) if -0.15 < P[i, 0] < 0.15 and 1.15 < P[i, 2] < 1.45]
outliers = []
for i in region:
    nb = neighbours[i]
    if len(nb) < 3:
        continue
    d = np.linalg.norm(P[i] - P[nb].mean(0))
    outliers.append((d, i))
outliers.sort(reverse=True)
flagged = [i for d, i in outliers if d > 0.025]
print("[relax] сглаживаю вершин груди:", len(flagged))
for d, i in outliers[:10]:
    print("   v%d dist=%.4f" % (i, d))

ROUNDS = 15
FACTOR = 0.6
for _ in range(ROUNDS):
    P = np.array([v.co[:] for v in me.vertices])
    new_pos = {i: P[i] * (1 - FACTOR) + P[neighbours[i]].mean(0) * FACTOR for i in flagged}
    for i, pos in new_pos.items():
        me.vertices[i].co = pos

me.update()
bpy.ops.wm.save_mainfile()
print("[relax] сохранено")
