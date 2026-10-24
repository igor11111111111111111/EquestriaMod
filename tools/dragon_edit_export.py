# -*- coding: utf-8 -*-
"""Экспорт поправленной модели дракона из assets/dragon/eq_dragon.blend в assets/dragon/eq_dragon.fbx.

Запуск: blender --background assets/dragon/eq_dragon.blend --python tools/dragon_edit_export.py

Коллекция "Meshy Frostwing Princess" хранит восемь частей под родовыми именами Meshy (eq_body,
eq_wings, ...) — на экспорт отдаём их под именами, которые ждёт остальной конвейер (eq_dragon_body,
eq_dragon_wings, ... — см. tools/dragon_material.ps1 и src/EquestriaBodyParts.cs). Переименование
только в памяти, сам .blend не трогаем и не сохраняем — работу над моделью это не портит.
Та же настройка экспорта, что и в основном конвейере tools/make_dragon.py (оси X/-Y, без анимации).
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
    # select_set() молча не выделяет скрытый объект (глаз в Outliner выключен) — у яка
    # скелет оказался именно таким, экспорт тихо ушёл без костей (замечено по А-позе в бою
    # 07.10.2026, см. yak_edit_export.py). Снимаем скрытие перед выделением на всякий случай.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
