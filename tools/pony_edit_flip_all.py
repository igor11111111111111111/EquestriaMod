# -*- coding: utf-8 -*-
"""Flip all faces of all eight parts in assets/pony/eq_pony_edit.blend entirely.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_flip_all.py

Directly via bmesh (not bpy.ops.mesh.flip_normals): the previous attempt via operators in background
mode flipped every other face instead of all at once, which produced a ripple of holes.
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
