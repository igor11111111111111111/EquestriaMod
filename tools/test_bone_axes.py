# Какие оси костей при экспорте FBX сохраняют ориентацию костей оригинального human_skeleton.fbx.
# blender --background --factory-startup --python test_bone_axes.py -- <human_skeleton.fbx> <tmp_dir>
import os
import sys

import bpy

skel_path, tmp = sys.argv[sys.argv.index("--") + 1:]
os.makedirs(tmp, exist_ok=True)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def bone_mats(path):
    """Матрицы костей в мировом пространстве при импорте с настройками по умолчанию."""
    reset()
    bpy.ops.import_scene.fbx(filepath=path)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    return {b.name: arm.matrix_world @ b.matrix_local for b in arm.data.bones}


def export_variant(primary, secondary, out):
    reset()
    bpy.ops.import_scene.fbx(filepath=skel_path, automatic_bone_orientation=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y")
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, add_leaf_bones=False, bake_anim=False,
                             primary_bone_axis=primary, secondary_bone_axis=secondary)


def diff(a, b):
    worst = 0.0
    for name, ma in a.items():
        mb = b[name]
        for i in range(3):
            for j in range(4):
                scale = 1.0 if j < 3 else 100.0  # позиции крошечные (масштаб 0.01) — усилим
                worst = max(worst, abs(ma[i][j] - mb[i][j]) * scale)
    return worst


reference = bone_mats(skel_path)
for primary, secondary in (("X", "-Y"), ("Y", "X")):
    out = os.path.join(tmp, f"skel_{primary}_{secondary.replace('-', 'neg')}.fbx")
    export_variant(primary, secondary, out)
    print(f"[axes] export primary={primary} secondary={secondary}: max matrix difference {diff(reference, bone_mats(out)):.5f}", flush=True)
