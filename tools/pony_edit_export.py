# -*- coding: utf-8 -*-
"""Экспорт готовой ручной модели из assets/pony/eq_pony_edit.blend поверх assets/pony/eq_pony.fbx.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_export.py

Экспортируются скелет и девять частей из коллекции «Пони - цельная» (те же настройки экспорта,
что и в основном конвейере tools/make_pony_model.py: оси X/-Y, без анимации, без лишних костей).
"""
import os

import bpy

# ears — 07.10.2026, пользователь отделил уши от гривы (EquestriaBodyParts.cs PartByRace/EarMeshByRace)
# gloves_l/r, legs_l/r — 07.10.2026, разрез пополам для визуального отрубания конечностей
# (tools/pony_edit_split_limbs.py, EquestriaDismemberment.cs) — старые gloves/legs целиком всё ещё
# нужны обычному (не отрубленному) персонажу, экспортируем и то, и то.
PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings", "ears",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "pony", "eq_pony.fbx")


def log(*a):
    print("[export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
new_col = bpy.data.collections["Пони - цельная"]
parts = []
for name in PARTS:
    ob = new_col.objects.get("eq_pony_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_pony_" + name)
        continue
    parts.append(ob)
    verts = len(ob.data.vertices)
    groups = len(ob.vertex_groups)
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    keys = len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0
    log("%-8s вершин %-6d групп %-3d без веса %-4d шейпкизов %d" % (name, verts, groups, ungrouped, keys))

if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    # select_set() молча не выделяет скрытый объект (глаз в Outliner выключен) — у яка
    # скелет оказался именно таким, экспорт тихо ушёл без костей (замечено по А-позе в бою
    # 07.10.2026, см. yak_edit_export.py). Снимаем скрытие перед выделением на всякий случай.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
