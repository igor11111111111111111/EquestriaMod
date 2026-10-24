# -*- coding: utf-8 -*-
"""Export the fixed hippogriff model from assets/hippogriff/hippogriff.blend to
assets/hippogriff/eq_hippogriff.fbx.

Run: blender --background assets/hippogriff/hippogriff.blend --python tools/hippogriff_edit_export.py

Exports the skeleton (bip01_notused) and six parts from the "Meshy Skyclaw Guardian" collection - the
object names there are already final (eq_hippogriff_*), no renaming needed. Same export settings
as in the main pipeline tools/make_hippogriff.py (axes X/-Y, no animation).
"""
import os

import bpy

PARTS = ("body", "tail", "wings", "head", "legs", "gloves",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
COLLECTION = "Meshy Skyclaw Guardian"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets", "hippogriff", "eq_hippogriff.fbx")


def log(*a):
    print("[hippogriff-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_hippogriff_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_hippogriff_" + name)
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
    # select_set() silently does not select a hidden object (eye toggled off in the Outliner) - the
    # yak's skeleton turned out to be exactly that, and the export quietly went out without bones
    # (noticed from the A-pose in battle on 07.10.2026, see yak_edit_export.py). Unhide before
    # selecting just in case.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
