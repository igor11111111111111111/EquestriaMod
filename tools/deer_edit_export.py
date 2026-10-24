# -*- coding: utf-8 -*-
"""Экспорт поправленной модели оленихи из assets/deer/eq_deer.blend в assets/deer/eq_deer.fbx.

Запуск: blender --background assets/deer/eq_deer.blend --python tools/deer_edit_export.py

Экспортируются скелет (bip01_notused) и части из коллекции «Meshy Braided Fawn» — имена объектов
там уже в финальном виде (eq_deer_*). Те же настройки экспорта, что и в основном конвейере
tools/make_deer_model.py (оси X/-Y, без анимации).

Четыре варианта рогов (10.10.2026): в файле они лежат как eq_deer_horn_1..4. Наружу уходят как
eq_deer_horn (вариант 1 — прежнее имя, на него смотрят EquestriaBodyParts/EquestriaDismemberment)
и eq_deer_horn_2..4. Выбор варианта — через список причёсок в редакторе: у оленя там четыре меша
кос eq_deer_hair, eq_deer_hair_2..4 (одна и та же коса под разными именами — копии делаются здесь),
и код показывает рога с тем же номером, что у надетой косы (src/EquestriaBodyParts.cs).
Всё переименование, привязка рогов к скелету и копии кос — только в памяти, .blend не сохраняется.
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
    """Родитель и модификатор скелета — без них FBX уйдёт без скиннинга (рога 2–4 были без них)."""
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

# Рога: вариант 1 — материал-образец для остальных (у всех четырёх та же текстура оленя)
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

# Косы: копии под именами eq_deer_hair_2..4 — по одной на вариант рогов
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
    # select_set() молча не выделяет скрытый объект (глаз в Outliner выключен) — у яка
    # скелет оказался именно таким, экспорт тихо ушёл без костей (замечено по А-позе в бою
    # 07.10.2026, см. yak_edit_export.py). Снимаем скрытие перед выделением на всякий случай.
    ob.hide_set(False)
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспортировано:", OUT)
