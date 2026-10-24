# -*- coding: utf-8 -*-
"""Экспорт FBX-КОНТЕЙНЕРА для позы свитка полёта: human_skeleton.fbx с ключами на всех костях.

Сама поза здесь НЕ задаётся. Повороты всех костей в этом файле перезаписывает
tools/make_flight_pose_engine.py — на rest-позе движка (tools/engine_rest_human_skeleton.txt),
потому что rest скелета в движке не совпадает с PreRotation human_skeleton.fbx и любой клип,
собранный на Blender-арматуре с этого FBX, в игре разворачивает торс на 180° (10.10.2026,
подробности в equestria-flight-scroll.md). От контейнера нужны только узлы костей, кривые
Lcl Rotation с ключами (кадры 1..15) и связи между ними.

Файл обязан быть Z-up (axis_forward="Y", axis_up="Z"): тогда у таза родитель — мир, и его
локальный поворот = rest движка в пространстве сущности без каких-либо конвертаций.

Конвейер:
    blender --background --factory-startup --python tools/make_flight_pose.py -- export <human_skeleton.fbx> assets/flight_test/eq_flight_arms_pose_raw.fbx
    blender --background --factory-startup --python tools/make_flight_pose_engine.py -- tools/engine_rest_human_skeleton.txt assets/flight_test/eq_flight_arms_pose_raw.fbx assets/flight_test/eq_flight_arms_pose.fbx
    cp assets/flight_test/eq_flight_arms_pose.fbx Module/AssetSources/
    редактор: Resource Browser -> Assets -> eq_flight_arms_pose.fbx -> Reimport
"""
import sys

import bpy

ACTION_NAME = "eq_flight_arms_pose"

args = sys.argv[sys.argv.index("--") + 1:]
mode, skel_path, out_path = args[0], args[1], args[2]
if mode != "export":
    raise ValueError(f"неизвестный режим: {mode} (ожидался 'export')")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=skel_path, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
arm.hide_set(False)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm

bpy.ops.object.mode_set(mode="POSE")
for pb in arm.pose.bones:
    pb.rotation_mode = "XYZ"
    pb.keyframe_insert(data_path="rotation_euler", frame=1)
    pb.keyframe_insert(data_path="rotation_euler", frame=250)
arm.animation_data.action.name = ACTION_NAME
bpy.context.scene.name = ACTION_NAME
bpy.ops.object.mode_set(mode="OBJECT")

bpy.ops.export_scene.fbx(
    filepath=out_path, use_selection=True, add_leaf_bones=False, bake_anim=True,
    bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
    primary_bone_axis="X", secondary_bone_axis="-Y",
    axis_forward="Y", axis_up="Z")
print(f"[flight_pose] контейнер экспортирован в {out_path} (action={ACTION_NAME})")
