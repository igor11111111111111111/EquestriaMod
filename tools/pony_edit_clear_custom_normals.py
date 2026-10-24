# -*- coding: utf-8 -*-
"""Снять старые кастомные нормали (Custom Split Normals) и пересчитать заново.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_clear_custom_normals.py

У всех восьми частей обнаружен слой custom split normals (has_custom_normals=True) — отдельные
нормали по граням, независимые от обхода вершин (winding). Из-за него любой переворот через
flip_normals/reverse_faces/recalc менял только обход, а видимое освещение и экспорт в FBX
продолжали жить по старым, кем-то когда-то записанным нормалям — отсюда вся путаница с рябью.
Здесь слой стирается (mesh.free_normals_split), дальше Recalculate Normals (Outside) пересчитывает
по-настоящему, в согласии с обходом граней.
"""
import bpy

PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")
new_col = bpy.data.collections["Пони - цельная"]

for part in PARTS:
    ob = new_col.objects.get("eq_pony_" + part)
    if ob is None:
        print("[clearnrm] нет объекта", part)
        continue
    had = ob.data.has_custom_normals
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.data.update()
    print("[clearnrm] %-8s было кастомных: %s, пересчитано" % (part, had))

bpy.ops.wm.save_mainfile()
print("[clearnrm] сохранено")
