# -*- coding: utf-8 -*-
"""Remove the old custom normals (Custom Split Normals) and recompute them from scratch.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_clear_custom_normals.py

All eight parts were found to have a custom split normals layer (has_custom_normals=True) — separate
per-face normals independent of the vertex order (winding). Because of it any flip via
flip_normals/reverse_faces/recalc changed only the winding, while the visible lighting and the FBX export
kept following the old normals someone once wrote — hence all the confusion with the ripples.
Here the layer is erased (mesh.free_normals_split), then Recalculate Normals (Outside) recomputes them
for real, consistent with the face winding.
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
