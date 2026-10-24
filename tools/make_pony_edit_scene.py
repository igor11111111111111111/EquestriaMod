# -*- coding: utf-8 -*-
"""Сцена для ручной подгонки частей пони: пони, цельная модель, человек со скелетом и бронёй.

Запуск (после tools/make_pony_model.py, который пишет assets/pony/eq_pony.blend):
  blender assets/pony/eq_pony.blend --python tools/make_pony_edit_scene.py

Результат — assets/pony/eq_pony_edit.blend (eq_pony.blend не трогаем: его перезаписывает конвейер).
Коллекции:
  Пони - части        — eq_pony_body/legs/gloves/head/hair/horn/wings/tail на скелете (то, что уходит
                        в игру — прежний автоматический разрез, для сравнения);
  Пони - цельная      — eq_pony_FULL: вся посаженная модель БЕЗ разреза на части, с весами, на скелете
                        (видна по умолчанию — по ней и режут вручную);
  Человек и броня     — ванильный мужчина (тело, ноги, кисти, голова) со своим скелетом (кости видны,
                        как «палки») и полный комплект брони империи (шлем, нагрудник, перчатки,
                        сапоги) — все части и вся броня надеты на ОДИН общий скелет (у ванильных
                        частей и вещей один и тот же human_skeleton, поэтому кости совпадают
                        1-в-1: первый импорт скелет оставляет, у остальных берутся только меши,
                        а их Armature-модификатор перецепляется на первый). Скелет подвешен на
                        пустышку «Человек (сдвиг)», у которой X=0 — человек стоит ровно на пони,
                        кость в кость (сверено по pelvis/spine/spine1/spine2/neck/head — расхождение
                        не больше 2 см, это одна и та же поза покоя human_skeleton). Раздвинуть для
                        сравнения бок о бок — задайте SIDE вверху файла и пересоберите сцену, или
                        просто подвиньте пустышку по X руками;
  Скрещенные «палки» у ключицы/локтя — это твист-кости (upperarm_twist1, foretwist1): у ванильного
  скелета они смещены в сторону от прямой линии руки для скручивания предплечья при анимации,
  и в отображении STICK это всегда выглядит как крест. Это не ошибка и не мой косяк, так собран сам
  human_skeleton — у пони то же самое (см. bip01_l_upperarm_twist_15 и bip01_l_upperarm_twist1_16).
  Старая пони (Twilight) — прежние меши-заглушки (скрыта).
Человек развёрнут лицом в -Y, как пони (ванильные модели смотрят в +Y).
"""
import math
import os

import bpy
from mathutils import Vector

# У ванильной головы сотня ключей мимики, и импортёр FBX на них падает (AssertionError в blen_read_shapes).
# Ключи для подгонки не нужны — отключаем их чтение, как в tools/inspect_armor.py.
import io_scene_fbx.import_fbx as _fbx_import  # noqa: E402

_fbx_import.blen_read_shapes = lambda *args, **kwargs: {}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "assets", "reference", "vanilla_armor")
HUMAN = os.path.join(ROOT, "assets", "human_ref")
OUT = os.path.join(ROOT, "assets", "pony", "eq_pony_edit.blend")
SIDE = 0.0                      # смещение человека вбок от пони (0 — стоит вплотную поверх, кость в кость)

HUMAN_PARTS = [("body_male_a", os.path.join(HUMAN, "body_male_a.fbx", "body_male_a", "body_male_a.fbx")),
               ("feet_male_a", os.path.join(HUMAN, "feet_male_a.fbx", "feet_male_a", "feet_male_a.fbx")),
               ("hands_male_a", os.path.join(HUMAN, "hands_male_a.fbx", "hands_male_a", "hands_male_a.fbx")),
               ("head_male_a", os.path.join(HUMAN, "head_male_a.fbx", "head_male_a", "head_male_a.fbx"))]
# Полный комплект «Империя»: тот же, что в смотре рас (empire_guarded_lord_helmet, empire_plate_vest_armor,
# decorated_imperial_gauntlets, decorated_imperial_boots) — имена мешей взяты из items игры.
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
shift.rotation_euler = (0, 0, math.pi)         # ванильные модели смотрят в +Y, наши — в -Y
human_col.objects.link(shift)

# Общий скелет человека: первый импорт (тело) оставляет свой, у всех следующих частей и брони —
# те же имена костей (один human_skeleton на всю ванильную экипировку), поэтому Armature-модификатор
# просто перецепляется на первый скелет, а собственный скелет из FBX удаляется.
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
                md.object = human_skel          # тот же набор имён костей — веса не трогаем
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

# Человека делаем серым, броню — тёмной, чтобы отличать от пони в режиме Solid
for ob in human_col.objects:
    if ob.type != "MESH":
        continue
    ob.color = (0.85, 0.55, 0.45, 1) if ob.name.startswith("Человек") else (0.35, 0.45, 0.6, 1)

bpy.ops.wm.save_as_mainfile(filepath=OUT)
log("сцена записана:", OUT)
