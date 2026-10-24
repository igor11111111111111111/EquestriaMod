# -*- coding: utf-8 -*-
"""Export of the finished hand-edited model from assets/pony/eq_pony_edit.blend over assets/pony/eq_pony.fbx.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_export.py

Exported are the skeleton and nine parts from the "Pony - whole" collection (the same export
settings as in the main pipeline tools/make_pony_model.py: axes X/-Y, no animation, no extra bones).
"""
import os

import bpy

# ears: 07.10.2026, the user separated the ears from the mane (EquestriaBodyParts.cs PartByRace/EarMeshByRace)
# gloves_l/r, legs_l/r: 07.10.2026, cut in half for visual limb severing
# (tools/pony_edit_split_limbs.py, EquestriaDismemberment.cs); the old whole gloves/legs are still
# needed by an ordinary (not dismembered) character, so both are exported.
PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings", "ears",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "pony", "eq_pony.fbx")


def log(*a):
    print("[export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
new_col = bpy.data.collections["Пони - цельная"]
parts = []
for name in PARTS:
    ob = new_col.objects.get("eq_pony_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_pony_" + name)
        continue
    parts.append(ob)
    verts = len(ob.data.vertices)
    groups = len(ob.vertex_groups)
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    keys = len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0
    log("%-8s вершин %-6d групп %-3d без веса %-4d шейпкизов %d" % (name, verts, groups, ungrouped, keys))

if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    # select_set() silently does not select a hidden object (eye turned off in the Outliner); for the yak
    # the skeleton turned out to be exactly that, and the export quietly went out without bones (noticed
    # by the A-pose in battle 07.10.2026, see yak_edit_export.py). Unhide before selecting, just in case.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
