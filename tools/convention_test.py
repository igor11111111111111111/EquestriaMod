# Тест ориентации экспорта на ванильных мешах с весами разработчиков (Female_BodyBase: тело, кисти, ступни, голова).
# Даёт два FBX для импорта в редактор и сравнения анимации в Model Viewer:
#   eq_convA.fbx — меши развёрнуты к -Y, веса l/r переставлены, скелет без поворота (как сейчас у пони)
#   eq_convB.fbx — меши как есть (+Y), веса по положению, весь скелет повёрнут на 180° при экспорте
#
# blender --background --factory-startup --python convention_test.py -- <human_skeleton.fbx> <Female_BodyBase.fbx> <out_dir>
import math
import os
import re
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_body import bone_name_map, fit_matrix  # noqa: E402

SKEL, REF, OUT = sys.argv[sys.argv.index("--") + 1:]
os.makedirs(OUT, exist_ok=True)
MATERIAL = "eq_twilight_body"  # уже есть в редакторе — импорт без ошибок материалов


def log(*a):
    print("[conv]", *a, flush=True)


def mirror_name(skel, name):
    base = re.sub(r"_\d+$", "", name)
    if "_l_" in base:
        other = base.replace("_l_", "_r_")
    elif "_r_" in base:
        other = base.replace("_r_", "_l_")
    else:
        return name
    return next((b.name for b in skel.data.bones if re.sub(r"_\d+$", "", b.name) == other), name)


def build(variant):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, vl = bpy.context.scene, bpy.context.view_layer
    bpy.ops.import_scene.fbx(filepath=SKEL, automatic_bone_orientation=False, primary_bone_axis="X", secondary_bone_axis="-Y")
    skel = next(o for o in scene.objects if o.type == "ARMATURE")
    skel.scale = (1, 1, 1)
    vl.update()
    names = bone_name_map(skel)
    mat = bpy.data.materials.new(MATERIAL)

    before = set(scene.objects)
    bpy.ops.import_scene.fbx(filepath=REF, automatic_bone_orientation=False, primary_bone_axis="X", secondary_bone_axis="-Y")
    new = [o for o in scene.objects if o not in before]
    vl.update()
    ref_arm = next(o for o in new if o.type == "ARMATURE")
    m, fit = fit_matrix(ref_arm, skel, turn_around=(variant == "A"))
    log(variant, "fit", fit)

    dg = bpy.context.evaluated_depsgraph_get()
    made = []
    for src in [o for o in new if o.type == "MESH"]:
        me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.transform(m @ src.matrix_world)
        me.materials.clear()
        me.materials.append(mat)
        name = f"eq_conv{variant}_{src.name.split('_')[0]}"
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
        ob.vertex_groups.clear()
        for g in src.vertex_groups:
            target = names.get(g.name, g.name)
            if variant == "A":
                target = mirror_name(skel, target)
            ob.vertex_groups.new(name=target)
        for v_src, v in zip(src.data.vertices, me.vertices):
            for g in v_src.groups:
                ob.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
        ob.parent = skel
        ob.matrix_parent_inverse = skel.matrix_world.inverted()
        ob.modifiers.new("Armature", "ARMATURE").object = skel
        made.append(ob)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)

    if variant == "B":
        skel.rotation_mode = "XYZ"
        skel.rotation_euler.z += math.pi
        vl.update()

    for o in scene.objects:
        o.select_set(False)
    skel.select_set(True)
    for o in made:
        o.select_set(True)
    vl.objects.active = skel
    path = os.path.join(OUT, f"eq_conv{variant}.fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y")
    log(variant, "exported", path, [o.name for o in made])


build("A")
build("B")
