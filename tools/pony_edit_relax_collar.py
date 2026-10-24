# -*- coding: utf-8 -*-
"""Smooth the crumpled cluster at the shoulder/collar - an extended height zone (same technique).

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_relax_collar.py
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

region = [i for i in range(len(P)) if 0.05 < P[i, 0] < 0.32 and 1.00 < P[i, 2] < 1.45]
outliers = []
for i in region:
    nb = neighbours[i]
    if len(nb) < 3:
        continue
    d = np.linalg.norm(P[i] - P[nb].mean(0))
    outliers.append((d, i))
outliers.sort(reverse=True)
flagged = [i for d, i in outliers if d > 0.02]
print("[relax] сглаживаю вершин плеча/воротника:", len(flagged))

ROUNDS = 20
FACTOR = 0.6
for _ in range(ROUNDS):
    P = np.array([v.co[:] for v in me.vertices])
    new_pos = {i: P[i] * (1 - FACTOR) + P[neighbours[i]].mean(0) * FACTOR for i in flagged}
    for i, pos in new_pos.items():
        me.vertices[i].co = pos

me.update()
bpy.ops.wm.save_mainfile()
print("[relax] сохранено")
