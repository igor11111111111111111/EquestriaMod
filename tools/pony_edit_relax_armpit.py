# -*- coding: utf-8 -*-
"""Разгладить смятый участок вершин под мышкой на eq_pony_body — те же symptoms, что и наверху руки
(пользователь сам поправил 2 вершины сверху; тут кластер побольше, снизу).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_relax_armpit.py

Вершины в этой зоне сильно смещены относительно своих соседей (замерено: до 0.11 м) — видимо,
след прежних правок руки/зеркалирования. Плавно подтягиваем каждую такую вершину к среднему её
соседей несколько раз подряд — соседи (не смятые вершины) служат якорем и не двигаются.
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
