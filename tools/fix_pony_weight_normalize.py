# -*- coding: utf-8 -*-
"""Normalizes bone weights over the vertices of eq_pony_head and eq_pony_body - the sum of a vertex's
weights is brought to 1.0, the proportions between bones are kept (not hand repainting, a purely
mathematical fix). Fixes vertices "flying apart" at the neck/shoulders in battle: some vertices had 1.0
on two bones at once (sum 2.0) - in a pose where the bones diverge, the engine pulled the vertex both ways
at once (see diag_pony_neck_weights.py, 30.09.2026). Saves the file.

Run:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\fix_pony_weight_normalize.py
"""
import bpy

col = bpy.data.collections.get("Пони - цельная")
NAMES = ("eq_pony_head", "eq_pony_body")


def normalize(name):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        print(f"[fix] {name}: НЕ НАЙДЕН")
        return

    for o in bpy.data.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    if bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    fixed = 0
    for v in ob.data.vertices:
        total = sum(g.weight for g in v.groups)
        if len(v.groups) > 0 and (total < 0.98 or total > 1.02):
            for g in v.groups:
                g.weight = g.weight / total
            fixed += 1

    print(f"[fix] {name}: нормализовано вершин {fixed}")


for n in NAMES:
    normalize(n)

bpy.ops.wm.save_mainfile()
print("[fix] файл сохранён")
