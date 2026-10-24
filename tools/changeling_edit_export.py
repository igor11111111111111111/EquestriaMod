# -*- coding: utf-8 -*-
"""Экспорт поправленной модели чейнджлинга из assets/changeling/eq_changeling.blend в
assets/changeling/eq_changeling.fbx.

Запуск: blender --background assets/changeling/eq_changeling.blend --python tools/changeling_edit_export.py

Экспортируются скелет (bip01_notused) и восемь частей из коллекции «Meshy Midnight Changeling» —
имена объектов там уже в финальном виде (eq_changeling_*), переименовывать не нужно. Те же
настройки экспорта, что и в основном конвейере tools/make_changeling_model.py (оси X/-Y, без анимации).
"""
import os

import bpy

PARTS = ("body", "tail", "wings", "legs", "gloves", "head", "ears", "horn",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
COLLECTION = "Meshy Midnight Changeling"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets", "changeling", "eq_changeling.fbx")


def log(*a):
    print("[changeling-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_changeling_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_changeling_" + name)
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
    # select_set() молча не выделяет скрытый объект (глаз в Outliner выключен) — у яка
    # скелет оказался именно таким, экспорт тихо ушёл без костей (замечено по А-позе в бою
    # 07.10.2026, см. yak_edit_export.py). Снимаем скрытие перед выделением на всякий случай.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
