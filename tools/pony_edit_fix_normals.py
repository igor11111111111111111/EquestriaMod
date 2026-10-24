# -*- coding: utf-8 -*-
"""Recalculate normals outward for all parts in assets/pony/eq_pony_edit.blend.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_normals.py

After the manual Separate/Join and patches at the cut some faces stayed turned inward
(visible in the editor as dark holes — the engine does not draw back faces). Recalculate Normals (Outside)
makes all faces consistent and facing outward in one go.
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
