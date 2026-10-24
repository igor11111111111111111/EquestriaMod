# -*- coding: utf-8 -*-
"""Smooth out the crumpled patch of vertices under the armpit on eq_pony_body — the same symptoms as at
the top of the arm (the user fixed 2 vertices at the top himself; here the cluster is bigger, at the bottom).

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_relax_armpit.py

Vertices in this zone are strongly offset relative to their neighbours (measured: up to 0.11 m) —
apparently a trace of earlier arm/mirroring edits. We gently pull each such vertex toward the mean of its
neighbours several times in a row — the neighbours (non-crumpled vertices) act as anchors and do not move.
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

region = [i for i in range(len(P)) if 0.08 < P[i, 0] < 0.32 and 1.00 < P[i, 2] < 1.32]
outliers = []
for i in region:
    nb = neighbours[i]
    if len(nb) < 3:
        continue
    d = np.linalg.norm(P[i] - P[nb].mean(0))
    outliers.append((d, i))
outliers.sort(reverse=True)
flagged = [i for d, i in outliers if d > 0.03]
print("[relax] сглаживаю вершин:", len(flagged))

ROUNDS = 15
FACTOR = 0.6
for _ in range(ROUNDS):
    P = np.array([v.co[:] for v in me.vertices])
    new_pos = {}
    for i in flagged:
        nb = neighbours[i]
        target = P[nb].mean(0)
        new_pos[i] = P[i] * (1 - FACTOR) + target * FACTOR
    for i, pos in new_pos.items():
        me.vertices[i].co = pos

me.update()
bpy.ops.wm.save_mainfile()
print("[relax] сохранено")
