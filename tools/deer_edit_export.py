# -*- coding: utf-8 -*-
"""Export of the fixed doe model from assets/deer/eq_deer.blend to assets/deer/eq_deer.fbx.

Run: blender --background assets/deer/eq_deer.blend --python tools/deer_edit_export.py

Exported are the skeleton (bip01_notused) and the parts from the "Meshy Braided Fawn" collection: the object
names there are already final (eq_deer_*). The same export settings as in the main pipeline
tools/make_deer_model.py (axes X/-Y, no animation).

Four antler variants (10.10.2026): in the file they are eq_deer_horn_1..4. They are exported as
eq_deer_horn (variant 1, the old name that EquestriaBodyParts/EquestriaDismemberment look for)
and eq_deer_horn_2..4. The variant is chosen through the hairstyle list in the editor: the deer has four
braid meshes there, eq_deer_hair, eq_deer_hair_2..4 (one braid under different names, the copies are made here),
and the code shows the antlers with the same number as the worn braid (src/EquestriaBodyParts.cs).
All the renaming, binding of the antlers to the skeleton and braid copies happen only in memory, the .blend is not saved.
"""
import os

import bpy

PARTS = ("body", "legs", "tail", "gloves", "ears", "hair", "head",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
HORNS = 4
COLLECTION = "Meshy Braided Fawn"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "deer", "eq_deer.fbx")


def log(*a):
    print("[deer-export]", *a, flush=True)


def describe(ob, label):
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    log("%-10s вершин %-6d групп %-3d без веса %d" % (label, len(ob.data.vertices), len(ob.vertex_groups),
                                                        ungrouped))


def bind_to_skeleton(ob, skel):
    """Parent and skeleton modifier: without them the FBX goes out without skinning (antlers 2–4 lacked them)."""
    world = ob.matrix_world.copy()
    ob.parent = skel
    ob.matrix_world = world
    mods = [m for m in ob.modifiers if m.type == "ARMATURE"]
    if not mods:
        mods = [ob.modifiers.new("Armature", "ARMATURE")]
    for m in mods:
        m.object = skel


if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_deer_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_deer_" + name)
        continue
    parts.append(ob)
    describe(ob, name)

# Antlers: variant 1 is the reference material for the rest (all four have the same deer texture)
horn_material = None
for i in range(1, HORNS + 1):
    ob = col.objects.get("eq_deer_horn_%d" % i)
    if ob is None:
        raise SystemExit("нет объекта eq_deer_horn_%d" % i)
    bind_to_skeleton(ob, skel)
    if horn_material is None:
        horn_material = ob.data.materials[0]
    elif ob.data.materials:
        ob.data.materials[0] = horn_material
    out_name = "eq_deer_horn" if i == 1 else "eq_deer_horn_%d" % i
    ob.name = ob.data.name = out_name
    parts.append(ob)
    describe(ob, out_name[len("eq_deer_"):])

# Braids: copies named eq_deer_hair_2..4, one per antler variant
hair = col.objects["eq_deer_hair"]
for i in range(2, HORNS + 1):
    copy = hair.copy()
    copy.data = hair.data.copy()
    copy.name = copy.data.name = "eq_deer_hair_%d" % i
    col.objects.link(copy)
    for m in copy.modifiers:
        if m.type == "ARMATURE":
            m.object = skel
    parts.append(copy)
    describe(copy, copy.name[len("eq_deer_"):])

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
