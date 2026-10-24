# -*- coding: utf-8 -*-
"""Развернуть нормали только у указанных частей в assets/pony/eq_pony_edit.blend.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_flip_some.py -- legs wings tail
"""
import sys

import bmesh
import bpy

PARTS = sys.argv[sys.argv.index("--") + 1:]
new_col = bpy.data.collections["Пони - цельная"]

for part in PARTS:
    ob = new_col.objects.get("eq_pony_" + part)
    if ob is None:
        print("[flipsome] нет объекта", part)
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    print("[flipsome] перевёрнуто:", part, "граней", len(ob.data.polygons))

bpy.ops.wm.save_mainfile()
print("[flipsome] сохранено")
