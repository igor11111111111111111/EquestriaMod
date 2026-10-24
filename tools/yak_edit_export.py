# -*- coding: utf-8 -*-
"""Export of the corrected yak model from assets/yak/eq_yak.blend to assets/yak/eq_yak.fbx.

Run: blender --background assets/yak/eq_yak.blend --python tools/yak_edit_export.py

Exported are the skeleton (bip01_notused) and seven parts from the "Meshy Highland Hugger" collection; the object
names there are already final (eq_yak_*), no renaming is needed (the file also contains
old duplicates eq_yak_*.001/.002 on the same armature; they are not in this collection and do not get
into the export). The same export settings as in the main pipeline tools/make_yak_model.py
(axes X/-Y, no animation).
"""
import os

import bpy

PARTS = ("body", "tail", "gloves", "legs", "horn", "hair", "head",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
COLLECTION = "Meshy Highland Hugger"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "yak", "eq_yak.fbx")


def log(*a):
    print("[yak-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_yak_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_yak_" + name)
        continue
    parts.append(ob)
    verts = len(ob.data.vertices)
    groups = len(ob.vertex_groups)
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    log("%-8s вершин %-6d групп %-3d без веса %d" % (name, verts, groups, ungrouped))

if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    # select_set() silently does not select a hidden object (the eye in the Outliner); the yak's skeleton turned out
    # to be exactly that, and the export quietly went out without bones (noticed by the user 07.10.2026 from
    # the A-pose in battle, confirmed: 0 LimbNode in eq_yak.fbx). We unhide before selecting.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
