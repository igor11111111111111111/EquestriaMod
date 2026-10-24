# -*- coding: utf-8 -*-
"""Пересчёт нормалей наружу для всех частей в assets/pony/eq_pony_edit.blend.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_normals.py

После ручного Separate/Join и заплаток на месте разреза часть граней осталась вывернутой внутрь
(видно в редакторе тёмными провалами — движок изнанку не рисует). Recalculate Normals (Outside)
разом делает все грани согласованными и развёрнутыми наружу.
"""
import bpy

new_col = bpy.data.collections["Пони - цельная"]
PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")

for name in PARTS:
    ob = new_col.objects.get("eq_pony_" + name)
    if ob is None:
        print("[normals] нет объекта", name)
        continue
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    print("[normals] пересчитано:", name)

bpy.ops.wm.save_mainfile()
print("[normals] сохранено")
