# -*- coding: utf-8 -*-
"""Экспорт поправленной модели яка из assets/yak/eq_yak.blend в assets/yak/eq_yak.fbx.

Запуск: blender --background assets/yak/eq_yak.blend --python tools/yak_edit_export.py

Экспортируются скелет (bip01_notused) и семь частей из коллекции «Meshy Highland Hugger» — имена
объектов там уже в финальном виде (eq_yak_*), переименовывать не нужно (в файле рядом лежат и
старые дубликаты eq_yak_*.001/.002 на той же арматуре — они не входят в эту коллекцию и в экспорт
не попадают). Те же настройки экспорта, что и в основном конвейере tools/make_yak_model.py
(оси X/-Y, без анимации).
"""
import os

import bpy

PARTS = ("body", "tail", "gloves", "legs", "horn", "hair", "head",
         "gloves_l", "gloves_r", "legs_l", "legs_r")
COLLECTION = "Meshy Highland Hugger"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "yak", "eq_yak.fbx")


def log(*a):
    print("[yak-export]", *a, flush=True)


skel = bpy.data.objects["bip01_notused"]
col = bpy.data.collections[COLLECTION]
parts = []
for name in PARTS:
    ob = col.objects.get("eq_yak_" + name)
    if ob is None:
        log("ВНИМАНИЕ: нет объекта eq_yak_" + name)
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
    # select_set() молча не выделяет скрытый объект (глаз в Outliner) — скелет у яка оказался
    # именно таким, и экспорт тихо ушёл без костей (замечено пользователем 07.10.2026 по
    # А-позе в бою, подтверждено: 0 LimbNode в eq_yak.fbx). Снимаем скрытие перед выделением.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
