# -*- coding: utf-8 -*-
"""Инвертировать нормали всех частей в assets/pony/eq_pony_edit.blend (откат неверного recalc).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_flip_normals.py
"""
import bpy

new_col = bpy.data.collections["Пони - цельная"]
PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")

for name in PARTS:
    ob = new_col.objects.get("eq_pony_" + name)
    if ob is None:
        print("[flip] нет объекта", name)
        continue
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode="OBJECT")
    print("[flip] инвертировано:", name)

bpy.ops.wm.save_mainfile()
print("[flip] сохранено")
