# -*- coding: utf-8 -*-
"""Adds the collection "Human and armour" to the finished
assets/dragon/eq_dragon.blend: the same vanilla male with a skeleton and a full set of Empire armour as in
assets/pony/eq_pony_edit.blend (see tools/make_pony_edit_scene.py). The dragon is already assembled and
is saved INTO THIS SAME file; none of its parts are touched, we only add the reference.

Run:
  blender --background assets/dragon/eq_dragon.blend --python tools/add_human_ref_dragon.py
"""
import math
import os

import bpy

# The vanilla head has a hundred facial shape keys, and the FBX importer crashes on them
# (AssertionError in blen_read_shapes).
import io_scene_fbx.import_fbx as _fbx_import  # noqa: E402

_fbx_import.blen_read_shapes = lambda *args, **kwargs: {}

ROOT = r"C:\Users\New\EquestriaMod"
REF = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
HUMAN = os.path.join(ROOT, "assets", "human_ref")
OUT = os.path.join(ROOT, "assets", "dragon", "eq_dragon.blend")
SIDE = 0.0  # sideways offset of the human from the dragon (0 = stands right on top, bone on bone)

HUMAN_PARTS = [("body_male_a", os.path.join(HUMAN, "body_male_a.fbx", "body_male_a", "body_male_a.fbx")),
               ("feet_male_a", os.path.join(HUMAN, "feet_male_a.fbx", "feet_male_a", "feet_male_a.fbx")),
               ("hands_male_a", os.path.join(HUMAN, "hands_male_a.fbx", "hands_male_a", "hands_male_a.fbx")),
               ("head_male_a", os.path.join(HUMAN, "head_male_a.fbx", "head_male_a", "head_male_a.fbx"))]
ARMOUR = ["empire_lord_helmet_b", "empire_plate_vest_armor", "empire_plate_armor_gauntlets", "empire_plate_armor_boots"]


def log(*a):
    print("[dragon-ref]", *a, flush=True)


if "Человек и броня" in bpy.data.collections:
    log("коллекция 'Человек и броня' уже есть — ничего не делаю (запущено повторно?)")
    raise SystemExit(0)

human_col = bpy.data.collections.new("Человек и броня")
bpy.context.scene.collection.children.link(human_col)

shift = bpy.data.objects.new("Человек (сдвиг)", None)
shift.empty_display_type = "ARROWS"
shift.location = (SIDE, 0, 0)
shift.rotation_euler = (0, 0, math.pi)  # vanilla models face +Y, ours face -Y
human_col.objects.link(shift)

human_skel = None


def move(ob, col):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)


def bring(label, path):
    global human_skel
    if not os.path.exists(path):
        log("НЕТ файла", path)
        return []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    fresh = [o for o in bpy.data.objects if o not in before]
    own_skel = next((o for o in fresh if o.type == "ARMATURE"), None)
    if human_skel is None and own_skel is not None:
        human_skel = own_skel
        human_skel.name = "Скелет человека"
        human_skel.data.display_type = "STICK"
        human_skel.show_in_front = True
        human_skel.parent = shift
        move(human_skel, human_col)
    meshes = []
    for ob in fresh:
        if ob.type != "MESH":
            continue
        for md in ob.modifiers:
            if md.type == "ARMATURE":
                md.object = human_skel
        ob.parent = human_skel
        ob.name = label
        move(ob, human_col)
        meshes.append(ob)
    if own_skel is not None and own_skel is not human_skel:
        bpy.data.objects.remove(own_skel, do_unlink=True)
    log("%-32s %d мешей" % (label, len(meshes)))
    return meshes


for label, path in HUMAN_PARTS:
    bring("Человек: " + label, path)
for name in ARMOUR:
    bring("Броня: " + name, os.path.join(REF, name, name + ".fbx"))

for ob in human_col.objects:
    if ob.type != "MESH":
        continue
    ob.color = (0.85, 0.55, 0.45, 1) if ob.name.startswith("Человек") else (0.35, 0.45, 0.6, 1)

bpy.ops.wm.save_mainfile(filepath=OUT)
log("сохранено в", OUT)
