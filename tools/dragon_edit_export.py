# -*- coding: utf-8 -*-
"""Export the corrected dragon model from assets/dragon/eq_dragon.blend to assets/dragon/eq_dragon.fbx.

Run: blender --background assets/dragon/eq_dragon.blend --python tools/dragon_edit_export.py

The "Meshy Frostwing Princess" collection holds eight parts under Meshy's generic names (eq_body,
eq_wings, ...); for export we give them the names the rest of the pipeline expects (eq_dragon_body,
eq_dragon_wings, ... - see tools/dragon_material.ps1 and src/EquestriaBodyParts.cs). The renaming is
in memory only; the .blend itself is not touched or saved, so this does not spoil work on the model.
Same export settings as in the main pipeline tools/make_dragon.py (axes X/-Y, no animation).
"""
import os

import bpy

PARTS = ("body", "wings", "tail", "legs", "gloves", "horn", "hair", "head",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "dragon", "eq_dragon.fbx")


def log(*a):
    print("[dragon-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections["Meshy Frostwing Princess"]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_" + name)
        continue
    ob.name = ob.data.name = "eq_dragon_" + name
    parts.append(ob)
    verts = len(ob.data.vertices)
    groups = len(ob.vertex_groups)
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    log("%-8s вершин %-6d групп %-3d без веса %d" % (name, verts, groups, ungrouped))

if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    # select_set() silently does not select a hidden object (eye toggled off in the Outliner); the yak's
    # skeleton turned out to be exactly that, and the export quietly went out without bones (noticed by
    # the A-pose in battle 07.10.2026, see yak_edit_export.py). Unhide before selecting, just in case.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
