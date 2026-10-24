# -*- coding: utf-8 -*-
"""Remove all Mark Sharp marks from all eight parts in eq_pony_edit.blend.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_clear_sharp.py

A sharp edge breaks the shading hard regardless of Shade Smooth and of how evenly the
vertices lie: one more independent source of visible creases on top of crumpled vertices and weights.
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
