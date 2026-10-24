# -*- coding: utf-8 -*-
"""Export of the fixed griffon model from assets/griffon/eq_griffon.blend to assets/griffon/eq_griffon.fbx.

Run: blender --background assets/griffon/eq_griffon.blend --python tools/griffon_edit_export.py

Exported are the skeleton (bip01_notused) and seven parts from the collection «Meshy Skybound Griffin» - the object
names there are already final (eq_griffon_*, the ear is eq_griffon_ear in the singular),
no renaming needed. The same export settings as in the main pipeline tools/make_griffon.py
(axes X/-Y, no animation).
"""
import os

import bpy

PARTS = ("body", "legs", "tail", "wings", "gloves", "head", "ear",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
COLLECTION = "Meshy Skybound Griffin"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "griffon", "eq_griffon.fbx")


def log(*a):
    print("[griffon-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_griffon_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_griffon_" + name)
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
    # select_set() silently does not select a hidden object (eye in the Outliner turned off) - for the yak
    # the skeleton turned out to be exactly like that, the export quietly went out without bones (noticed by the
    # A-pose in battle 07.10.2026, see yak_edit_export.py). Unhide before selecting just in case.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
