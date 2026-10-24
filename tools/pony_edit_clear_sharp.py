# -*- coding: utf-8 -*-
"""Снять все пометки Mark Sharp со всех восьми частей в eq_pony_edit.blend.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_clear_sharp.py

Sharp-ребро ломает освещение жёстко независимо от Shade Smooth и от того, как ровно лежат
вершины — ещё один независимый источник видимых складок вдобавок к смятым вершинам и весам.
"""
import bpy

PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")
new_col = bpy.data.collections["Пони - цельная"]

for part in PARTS:
    ob = new_col.objects.get("eq_pony_" + part)
    if ob is None:
        continue
    sharp = sum(1 for e in ob.data.edges if e.use_edge_sharp)
    for e in ob.data.edges:
        e.use_edge_sharp = False
    ob.data.update()
    print("[sharp] %-8s снято острых рёбер: %d" % (part, sharp))

bpy.ops.wm.save_mainfile()
print("[sharp] сохранено")
