# -*- coding: utf-8 -*-
"""Развернуть все грани всех восьми частей в assets/pony/eq_pony_edit.blend целиком.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_flip_all.py

Через bmesh напрямую (не bpy.ops.mesh.flip_normals): прошлый заход через операторы в фоновом
режиме перевернул часть граней через раз вместо всех разом, отчего появилась рябь из дыр.
"""
import bmesh
import bpy

PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")
new_col = bpy.data.collections["Пони - цельная"]

for part in PARTS:
    ob = new_col.objects.get("eq_pony_" + part)
    if ob is None:
        print("[flipall] нет объекта", part)
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    print("[flipall] перевёрнуто:", part, "граней", len(ob.data.polygons))

bpy.ops.wm.save_mainfile()
print("[flipall] сохранено")
