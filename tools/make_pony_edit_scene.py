# -*- coding: utf-8 -*-
"""A scene for manually fitting pony parts: the pony, the whole model, a human with skeleton and armour.

Run (after tools/make_pony_model.py, which writes assets/pony/eq_pony.blend):
  blender assets/pony/eq_pony.blend --python tools/make_pony_edit_scene.py

Result: assets/pony/eq_pony_edit.blend (eq_pony.blend is not touched: the pipeline overwrites it).
Collections:
  Pony - parts  - eq_pony_body/legs/gloves/head/hair/horn/wings/tail on the skeleton (what goes
                        into the game: the old automatic cut, for comparison);
  Pony - whole - eq_pony_FULL: the whole fitted model WITHOUT cutting into parts, with weights,
                        on the skeleton (visible by default: it is what gets cut by hand);
  Human and armour - the vanilla male (body, legs, hands, head) with his own skeleton (bones visible
                        as "sticks") and a full set of imperial armour (helmet, chest piece, gauntlets,
                        boots); all parts and all armour are put on ONE shared skeleton (the vanilla
                        parts and items have the same human_skeleton, so the bones match
                        1-to-1: the first import keeps its skeleton, from the rest only the meshes are taken,
                        and their Armature modifier is re-attached to the first one). The skeleton is parented to
                        the empty (Human (shift)) with X=0: the human stands exactly on the pony,
                        bone to bone (checked on pelvis/spine/spine1/spine2/neck/head: the discrepancy is
                        no more than 2 cm, it is the same human_skeleton rest pose). To spread them apart for
                        a side-by-side comparison, set SIDE at the top of the file and rebuild the scene, or
                        just move the empty along X by hand;
  The crossed "sticks" at the clavicle/elbow are twist bones (upperarm_twist1, foretwist1): in the vanilla
  skeleton they are offset to the side of the straight arm line for twisting the forearm during animation,
  and in STICK display this always looks like a cross. It is not an error and not my mistake, that is how
  human_skeleton itself is built; the pony has the same (see bip01_l_upperarm_twist_15 and bip01_l_upperarm_twist1_16).
  Old pony (Twilight): the old placeholder meshes (hidden).
The human is turned to face -Y, like the pony (vanilla models face +Y).
"""
import math
import os

import bpy
from mathutils import Vector

# The vanilla head has a hundred facial expression keys, and the FBX importer crashes on them (AssertionError in blen_read_shapes).
# The keys are not needed for fitting, so we disable reading them, as in tools/inspect_armor.py.
import io_scene_fbx.import_fbx as _fbx_import  # noqa: E402

_fbx_import.blen_read_shapes = lambda *args, **kwargs: {}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
HUMAN = os.path.join(ROOT, "assets", "human_ref")
OUT = os.path.join(ROOT, "assets", "pony", "eq_pony_edit.blend")
SIDE = 0.0                      # sideways offset of the human from the pony (0: stands right on top, bone to bone)

HUMAN_PARTS = [("body_male_a", os.path.join(HUMAN, "body_male_a.fbx", "body_male_a", "body_male_a.fbx")),
               ("feet_male_a", os.path.join(HUMAN, "feet_male_a.fbx", "feet_male_a", "feet_male_a.fbx")),
               ("hands_male_a", os.path.join(HUMAN, "hands_male_a.fbx", "hands_male_a", "hands_male_a.fbx")),
               ("head_male_a", os.path.join(HUMAN, "head_male_a.fbx", "head_male_a", "head_male_a.fbx"))]
# The full "Empire" set: the same as in the race review (empire_guarded_lord_helmet, empire_plate_vest_armor,
# decorated_imperial_gauntlets, decorated_imperial_boots); the mesh names are taken from the game's items.
ARMOUR = ["empire_lord_helmet_b", "empire_plate_vest_armor", "empire_plate_armor_gauntlets", "empire_plate_armor_boots"]


def log(*a):
    print("[edit]", *a, flush=True)


def collection(name, hidden=False):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    col.hide_viewport = hidden
    return col


def move(ob, col):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)


pony_col = collection("Пони - части")
full_col = collection("Пони - цельная")
old_col = collection("Старая пони (Twilight)", hidden=True)
human_col = collection("Человек и броня")

for ob in list(bpy.data.objects):
    if ob.type == "MESH" and ob.name.startswith("eq_pony_") and ob.name != "eq_pony_FULL":
        move(ob, pony_col)
    elif ob.type == "MESH" and ob.name == "eq_pony_FULL":
        move(ob, full_col)
        ob.hide_viewport = ob.hide_render = False
    elif ob.type == "MESH" and ob.name.startswith("eq_twilight_"):
        move(ob, old_col)
    elif ob.type == "ARMATURE":
        move(ob, pony_col)
if bpy.data.objects.get("eq_pony_FULL") is None:
    log("ВНИМАНИЕ: eq_pony_FULL нет — пересоберите пони: tools/make_pony_model.py")

shift = bpy.data.objects.new("Человек (сдвиг)", None)
shift.empty_display_type = "ARROWS"
shift.location = (SIDE, 0, 0)
shift.rotation_euler = (0, 0, math.pi)         # vanilla models face +Y, ours face -Y
human_col.objects.link(shift)

# Shared human skeleton: the first import (the body) keeps its own; all following parts and armour have
# the same bone names (one human_skeleton for all vanilla equipment), so the Armature modifier
# is simply re-attached to the first skeleton, and the FBX's own skeleton is deleted.
human_skel = None


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
                md.object = human_skel          # the same set of bone names: the weights are not touched
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

# The human is made grey and the armour dark, to tell them apart from the pony in Solid mode
for ob in human_col.objects:
    if ob.type != "MESH":
        continue
    ob.color = (0.85, 0.55, 0.45, 1) if ob.name.startswith("Человек") else (0.35, 0.45, 0.6, 1)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
log("сцена записана:", OUT)
