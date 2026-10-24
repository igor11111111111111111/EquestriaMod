# -*- coding: utf-8 -*-
"""Дракон из готовой модели (Т-поза, свой скелет Mixamo) — на скелет пони, по частям, в FBX.

Запуск (headless Blender, открывает готовую пони — в ней скелет и образец привязки):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_dragon.py \
      -- "<путь к .fbx дракона>" "<папка вывода>"

Отличия от яка (tools/make_yak.py), с которого списан весь конвейер:
  1. У модели ЕСТЬ свой скелет и анимация бега. Импорт ставит её в первый кадр анимации, поэтому
     скелет переводится в позу покоя, а анимация снимается.
  2. Поза покоя — Т: руки строго в стороны (от плеча к кисти вниз всего 5 градусов), а у пони
     А-поза, 27 градусов вниз. Разница ломает перенос весов: горизонтальная рука дракона ближе
     к боку и ногам пони, чем к её руке. Опускаем руки ГЕОМЕТРИЧЕСКИ, поворотом вокруг плеча.
     Его же скелетом это делать нельзя: у модели крылья привязаны к костям рук (989 и 537 вершин
     на LeftArm/RightArm), и поворот кости уводил крылья вместе с рукой.
  3. Частей больше: у дракона есть крылья, хвост и гребень с рогами — их отделяем, чтобы гребень
     работал причёской, а крылья и хвост — предметами в слоты, как у чейнджлингов и пони.

Части на выходе:
  eq_dragon_body   — туловище и руки (body_meta_mesh)
  eq_dragon_legs   — ноги (legs_mesh)
  eq_dragon_gloves — кисти (hands_mesh)
  eq_dragon_head   — голова с мордой, рогами и гребнем (face_meta_mesh; причёски у расы нет)
  eq_dragon_wings  — крылья (предмет в слот плаща)
  eq_dragon_tail   — хвост (предмет)
Дальше — импорт FBX в Modding Kit руками, потом tools/dragon_material.ps1.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "dragon"
HEIGHT = 2.10          # рост дракона в метрах (пони 1.86, як 2.05)
MAT = "eq_dragon_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[dragon]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: (skel.matrix_world @ b.head_local) for b in skel.data.bones}

# ---------------------------------------------------------------- 1. импорт и А-поза
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=SRC)
added = [o for o in bpy.data.objects if o not in before]
dragon = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # мусор генератора: шарик-заготовка и прочие мелкие меши
    if ob.type == "MESH" and ob is not dragon:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (dragon.name, len(dragon.data.vertices), source_skel.name if source_skel else "нет"))

own_bones = []
if source_skel:
    # Поза покоя: в файле лежит анимация бега, и импорт ставит модель в её первый кадр. Сама
    # сетка хранится в позе привязки (Т), поэтому достаточно снять анимацию и модификатор.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = dragon
    for mod in list(dragon.modifiers):
        if mod.type == "ARMATURE":
            dragon.modifiers.remove(mod)
    dragon.parent = None
    # Кости запоминаем отрезками в мировых координатах ДО удаления скелета: по удалённости от
    # них ниже отбираются крылья и хвост. Концевые кости Mixamo («_end») торчат в стороны
    # мимо сетки и только портят замер.
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят (запомнено %d костей), модель в позе привязки" % len(own_bones))

bpy.ops.object.select_all(action="DESELECT")
dragon.select_set(True)
bpy.context.view_layer.objects.active = dragon
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Генератор отдаёт «суп»: соседние треугольники не делят вершины. Сшиваем — иначе не найти
# связные куски и по швам при деформации расходятся щели.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(dragon.data.vertices))


def coords():
    return np.array([(dragon.matrix_world @ v.co)[:] for v in dragon.data.vertices])


# ------------------------------------------------- крылья и хвост: связные куски вдали от костей
# Порогами по осям их не отделить: корень крыла подходит к самому позвоночнику (|x| до 0.07), а
# плавник хвоста шире таза — из-за этого ноги уезжали вместе с куском хвоста, голова с куском
# крыла, а на спине оставалась нашлёпка. Зато у крыльев и хвоста нет СВОИХ костей: перепонка
# привязана к костям рук, хвост — к тазу, и обе торчат далеко от любого отрезка скелета, тогда как
# кожа туловища, рук и ног всегда рядом со своей костью. Берём всё, что дальше FAR_FRAC от костей,
# и режем на связные куски по рёбрам: крупных ровно три — два крыла и хвост.
# Порог устойчив в 0.10..0.16 от роста (ниже крылья смыкаются на спине в один кусок), берём середину.
FAR_FRAC = 0.114
PART_MIN = 0.04       # кусок меньше этой доли вершин — рога, уши, морда: их не трогаем
TAIL_HIGH = 0.45      # кусок, у которого середина ниже этой доли роста, — хвост, выше — крыло
# Плечевые плавники крыла лежат ПОВЕРХ руки и попадают в её кость по удалённости. Но в родном
# скиннинге видно, кто есть кто: рука привязана к своей кости и не отходит от неё дальше 0.07
# роста, а перепонка и плавники — те же кости рук, но в 0.12..0.29 роста от них.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


appendage = [None] * len(dragon.data.vertices)
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in dragon.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in dragon.data.vertices])
    added = np.zeros(len(P), bool)
    for name in own_bones:
        if "Arm" not in name:          # только кости рук: к ним и подвешены крылья
            continue
        sel = dominant == name
        if sel.any():
            added[sel] |= bone_gap(name, P[sel]) > ARM_FAR * height
    added &= ~far
    far |= added
    # Где у модели кисть — по её РОДНОЙ кости: ниже по этим вершинам рука совмещается с рукой
    # скелета. По кончикам когтей мерить нельзя, они длинные.
    own_hand = {i for i, d in enumerate(dominant) if "Hand" in d}
    if added.any():
        pts = P[added]
        log("по костям рук добавлено %d вершин: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (рост %.2f)"
            % (int(added.sum()), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(),
               pts[:, 2].min(), pts[:, 2].max(), height))

    neighbours = [[] for _ in range(len(P))]
    for e in dragon.data.edges:
        i, j = e.vertices
        neighbours[i].append(j)
        neighbours[j].append(i)
    seen = np.zeros(len(P), bool)
    chunks = []
    for start in range(len(P)):
        if not far[start] or seen[start]:
            continue
        stack, chunk = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            chunk.append(cur)
            for other in neighbours[cur]:
                if far[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        chunks.append(chunk)

    middle_y = float(np.median(P[:, 1]))
    for chunk in sorted(chunks, key=len, reverse=True):
        if len(chunk) < PART_MIN * len(P):
            break
        mid = P[chunk].mean(0)
        if mid[1] < middle_y:          # всё наше — за спиной; впереди быть нечему
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        # По высоте середины: крылья сидят на уровне груди, хвост — у пола. Разделять по X нельзя:
        # оба крыла могут сойтись на спине в один кусок, и его середина окажется на оси.
        name = "tail" if mid[2] < TAIL_HIGH * height else "wings"
        for i in chunk:
            appendage[i] = name
    # Передняя кромка крыла с когтями лежит вплотную к костям пальцев (в Т-позе кисть и коготь
    # крыла оказываются в одной точке), поэтому по удалённости она не отбирается и оставалась на
    # теле торчащими наружу осколками. Но держится она ТОЛЬКО за перепонку: стоит снять крылья,
    # как она повисает отдельным островком. Поэтому смотрим, на что распадается остаток: большой
    # кусок — сам дракон, всё прочее рядом с крылом или хвостом возвращаем ему.
    seen = np.zeros(len(P), bool)
    rest = []
    for start in range(len(P)):
        if appendage[start] or seen[start]:
            continue
        stack, island = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            island.append(cur)
            for other in neighbours[cur]:
                if not appendage[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        rest.append(island)
    rest.sort(key=len, reverse=True)
    ISLAND_NEAR = 0.05        # островок дальше этой доли роста от крыла и хвоста — не их
    for island in rest[1:]:
        pick, gap = None, 1e9
        for name in ("wings", "tail"):
            owner = P[[i for i in range(len(P)) if appendage[i] == name]]
            if not len(owner):
                continue
            d = float(min(np.linalg.norm(owner - p, axis=1).min() for p in P[island]))
            if d < gap:
                pick, gap = name, d
        if pick and gap < ISLAND_NEAR * height:
            for i in island:
                appendage[i] = pick
            log("островок %d вершин возвращён в «%s» (зазор %.3f)" % (len(island), pick, gap))

    found = {n: sum(1 for a in appendage if a == n) for n in ("wings", "tail")}
    log("крылья и хвост по удалённости от костей: крылья %d вершин, хвост %d" % (found["wings"], found["tail"]))
    if not found["wings"] or not found["tail"]:
        log("ВНИМАНИЕ: крылья или хвост не найдены — проверьте FAR_FRAC")


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: размер %.2f x %.2f x %.2f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))

# Морда должна смотреть в -Y (как у пони). Морда — самая выступающая по Y точка верхней трети.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    dragon.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
dragon.scale = (scale, scale, scale)
dragon.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- глубина: сажаем по ТОРСУ, а не по габаритам
# По габаритному ящику сажать нельзя: хвост дракона тянет ящик назад, и туловище уезжает вперёд
# от позвоночника. Тогда кость позвоночника проходит у самой спины, грудь при любом повороте
# корпуса ходит ходуном, а руки и ноги висят впереди доспеха.
# Образец глубины — ВАНИЛЬНЫЙ ЧЕЛОВЕК, а не пони: броня сшита на него, и её посадку задаёт он.
# Тело человека выгружается из ассетов игры:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<игра>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Ванильные модели смотрят в +Y (наши — в -Y), поэтому образец разворачиваем.
TORSO_Z = (1.00, 1.35)    # между костями bip01_spine_9 и bip01_spine2_11
TORSO_HALF = 0.22         # шире этого по X — уже руки
HUMAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "human_ref", "human.obj")
DEPTH_EXTRA = 0.0         # ручная поправка глубины сверх расчётной, если в игре ещё не так


def torso_y(pts):
    band = pts[(np.abs(pts[:, 0]) < TORSO_HALF) & (pts[:, 2] > TORSO_Z[0]) & (pts[:, 2] < TORSO_Z[1])]
    if not len(band):
        return 0.0
    return float(np.percentile(band[:, 1], 2) + np.percentile(band[:, 1], 98)) / 2


P = coords()
if os.path.exists(HUMAN):
    known = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=HUMAN, forward_axis="Y", up_axis="Z")
    fresh = [o for o in bpy.data.objects if o not in known]
    man = np.vstack([np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for o in fresh])
    man[:, :2] *= -1                       # разворот образца лицом в -Y, как у нас
    target = torso_y(man)
    for ob in fresh:
        bpy.data.objects.remove(ob, do_unlink=True)
    whose = "человека"
else:
    target = torso_y(np.array([(pony["eq_twilight_body"].matrix_world @ v.co)[:]
                               for v in pony["eq_twilight_body"].data.vertices]))
    whose = "пони (нет assets/human_ref/human.obj)"
mine = torso_y(P[[i for i in range(len(P)) if appendage[i] is None]])
shift = target - mine + DEPTH_EXTRA
# Двигаем саму сетку, а не объект: «запекание» сдвига (transform_apply) работает только с
# выделенным объектом, а импорт образца выделение перехватывает — и тогда объект уезжает, а все
# последующие правки пишутся в локальные координаты и промахиваются ровно на этот сдвиг.
for v in dragon.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Где кончается шея и начинается голова. Линия идёт наклонно вперёд-вниз (под мордой), и
# отсчитывать её надо ОТ САМОЙ МОДЕЛИ: посадка по торсу сдвинула дракона по глубине, поэтому к
# мировой отметке прибавляем тот же сдвиг. Нужна она уже здесь: голову нельзя трогать вместе
# с руками — её бока попадают в ту же зону по X, и правка рук разносила морду в клочья.
NECK_Z = bones["bip01_neck_12"].z + 0.06
JAW_SLOPE, JAW_FROM = 0.45, -0.10 + shift


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ---------------------------------------------- руки из Т-позы на руку пони (поворот + длина)
# Просто повернуть на 22 градуса мало: рука дракона длиннее пониной на 10%, поэтому локоть
# приходился на кость предплечья, а кисть — мимо кости кисти, и в игре руки выглядели кривыми.
# Совмещаем отрезок «плечо — кисть» дракона с таким же отрезком скелета: поворот вокруг плеча
# плюс масштаб по длине. У самого сустава преобразование набирается плавно (ramp), иначе рвётся.
SHOULDER_X = 0.18               # плечевой сустав по X (кость плеча модели после посадки)
ARM_RAMP = 0.10                 # на скольких метрах набирается преобразование
ARM_TIP = 0.9                   # доля размаха, дальше которой — кисть
HEAD_RAMP = 0.12                # на скольких метрах ниже челюсти рука берёт своё

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
arm_y = float(np.median([P[i][1] for i in range(len(P)) if arm_far[i] and appendage[i] is None]))
ARM_BACK = arm_y + 0.12         # дальше назад — крыло, а не рука
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > SHOULDER_X - ARM_RAMP and p[1] < ARM_BACK and p[2] > 1.0
            and appendage[i] is None and not is_head(P[i])]
tip = max(abs(P[i][0]) for i in arm_zone)
# Кисть — по РОДНОЙ кости модели, а не по кончикам когтей: когти у дракона длинные, и по ним
# рука уезжала далеко в сторону от тела (кисть вставала на |x| 0.83 вместо 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# Плечевой сустав — на оси самой руки, продолженной до SHOULDER_X. По срезу туловища на этой
# отметке его не найти: там ещё бок, и середина среза гуляет на десяток сантиметров по высоте.
# Ось считаем по серединам поперечных полос руки (от 0.30 до кончиков), чтобы кисть и локоть
# не перевешивали, и проводим по ним прямую.
ARM_AXIS_FROM = 0.30
axis = np.array([[abs(P[i][0]), P[i][1], P[i][2]] for i in arm_zone
                 if abs(P[i][0]) > ARM_AXIS_FROM])
edges = np.linspace(ARM_AXIS_FROM, tip, 9)
middles = np.array([axis[(axis[:, 0] >= a) & (axis[:, 0] < b)].mean(0)
                    for a, b in zip(edges[:-1], edges[1:])
                    if (axis[:, 0] >= a).sum() and ((axis[:, 0] >= a) & (axis[:, 0] < b)).sum() > 5])
ky, by = np.polyfit(middles[:, 0], middles[:, 1], 1)
kz, bz = np.polyfit(middles[:, 0], middles[:, 2], 1)
S_d = Vector((SHOULDER_X, ky * SHOULDER_X + by, kz * SHOULDER_X + bz))
H_d = Vector([float(np.mean([abs(P[i][k]) if k == 0 else P[i][k] for i in hand_idx])) for k in range(3)])
S_p = bones["bip01_l_upperarm_twist_15"]
# Целим ЗАПЯСТЬЕМ в кость кисти. По кончикам пальцев пони нельзя: её рука длиннее человеческой
# (пальцы уходят на |x| 0.83, тогда как у ванильного тела рука кончается на 0.60), и дракон
# получал руки враскоряку. Когти пусть торчат за кость, как пальцы у человека.
H_p = bones["bip01_l_hand_19"]
# Ровно по кость рука выходит коротковатой: кисть прячется в рукав. Отпускаем её дальше вдоль
# той же оси и доворачиваем вниз — так она и длиннее, и прижата к телу, а не растопырена.
ARM_REACH = 1.16    # во сколько раз дальше кости кисти уходит запястье
ARM_DROP = 8.0      # на сколько градусов рука дополнительно опускается к телу
ARM_THICK = 1.20    # во сколько раз толще поперёк оси (само совмещение руку подтачивает)

reach = (H_p - S_p) * ARM_REACH
drop = math.radians(ARM_DROP)
H_p = S_p + Vector((reach.x * math.cos(drop) + reach.z * math.sin(drop), reach.y,
                    -reach.x * math.sin(drop) + reach.z * math.cos(drop)))
turn = (H_d - S_d).rotation_difference(H_p - S_p).to_matrix()
stretch = (H_p - S_p).length / (H_d - S_d).length
along = (H_d - S_d).normalized()
log("  рука: наклон %.0f -> %.0f градусов ниже горизонта, толщина x%.2f"
    % (math.degrees(math.atan2(-(bones["bip01_l_hand_19"] - S_p).z, (bones["bip01_l_hand_19"] - S_p).x)),
       math.degrees(math.atan2(-(H_p - S_p).z, (H_p - S_p).x)), ARM_THICK * stretch))
log("  плечо дракона (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f), кисть (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f)"
    % (*S_d, *S_p, *H_d, *(S_p + turn @ ((H_d - S_d) * stretch))))
for i in arm_zone:
    p = P[i]
    sign = 1.0 if p[0] > 0 else -1.0
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # к голове преобразование сходит на нет
    mine = Vector((abs(p[0]), p[1], p[2]))
    # вдоль оси руку тянем/жмём совмещением, а поперёк — отдельно, иначе она худеет вместе
    # с укорочением
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * ARM_THICK
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = dragon.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука дракона %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ------------------------------------------------------------------- грудная клетка пошире
# У модели узкая грудь — рядом с широким тазом смотрится трубой. Раздаём её по X, но не одним
# масштабом: иначе вместе с грудью уедут и руки, и кисти сойдут со своих костей. Внутри туловища
# ширина растёт пропорционально, снаружи сдвиг сходит на нет к запястью, а по высоте — плавно
# за пределами рёбер. Крылья и хвост двигаем вместе со всеми, чтобы корни остались на месте.
CHEST_WIDE = 1.5
CHEST_BAND = (1.15, 1.42)   # рёбра: от пояса до ключиц
CHEST_FADE = 0.13           # на скольких метрах по высоте набирается и спадает
CHEST_TAPER = 0.45          # на скольких метрах наружу сдвиг сходит на нет


def band_weight(z):
    if CHEST_BAND[0] <= z <= CHEST_BAND[1]:
        return 1.0
    gap = CHEST_BAND[0] - z if z < CHEST_BAND[0] else z - CHEST_BAND[1]
    if gap >= CHEST_FADE:
        return 0.0
    u = 1.0 - gap / CHEST_FADE
    return u * u * (3 - 2 * u)


P = coords()
chest = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.35)]
HALF = float(np.percentile(np.abs(chest[:, 0]), 90))     # полуширина туловища на уровне рёбер
grow = (CHEST_WIDE - 1.0) * HALF
for i, p in enumerate(P):
    w = band_weight(p[2])
    if w <= 0:
        continue
    out = abs(p[0])
    reach = out / HALF if out < HALF else max(0.0, 1.0 - (out - HALF) / CHEST_TAPER)
    if reach <= 0:
        continue
    dragon.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- верх груди поменьше
# Раздавать надо рёбра, а не бюст: сверху грудь выпирала и вперёд, и в стороны. Ужимаем верхнюю
# часть груди по ширине и глубине вокруг её же середины — так низ (рёбра) остаётся широким, а
# верх подбирается. К плечам сходит на нет, иначе от них оторвутся руки.
UPPER_SMALL = 0.82          # во сколько раз ужимаем верх груди
UPPER_BAND = (1.34, 1.58)   # от бюста до ключиц
UPPER_FADE = 0.10           # на скольких метрах по высоте набирается и спадает
UPPER_HALF = 0.26           # дальше этого по X — уже плечо, там ужимать нельзя
UPPER_TAPER = 0.16          # на скольких метрах наружу ужимание сходит на нет

P = coords()
band = P[(P[:, 2] > UPPER_BAND[0]) & (P[:, 2] < UPPER_BAND[1]) & (np.abs(P[:, 0]) < UPPER_HALF)]
mid_y = float(np.percentile(band[:, 1], 2) + np.percentile(band[:, 1], 98)) / 2


def upper_size():
    # мерить надо шире полосы ужимания, иначе замер упирается в собственный предел
    s = P[(P[:, 2] > UPPER_BAND[0]) & (P[:, 2] < UPPER_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
    return float(np.percentile(np.abs(s[:, 0]), 90)), float(np.percentile(s[:, 1], 2))


was, was_front = upper_size()
for i, p in enumerate(P):
    if appendage[i] is not None:
        continue
    gap = max(UPPER_BAND[0] - p[2], p[2] - UPPER_BAND[1], 0.0)
    if gap >= UPPER_FADE:
        continue
    u = 1.0 - gap / UPPER_FADE
    w = u * u * (3 - 2 * u)
    out = abs(p[0])
    if out > UPPER_HALF:
        w *= max(0.0, 1.0 - (out - UPPER_HALF) / UPPER_TAPER)
    if w <= 0:
        continue
    f = 1.0 - (1.0 - UPPER_SMALL) * w
    v = dragon.data.vertices[i]
    v.co.x = p[0] * f
    v.co.y = mid_y + (p[1] - mid_y) * f
P = coords()
now, now_front = upper_size()
log("верх груди ужат: полуширина %.2f -> %.2f, вперёд выступал на %.2f -> %.2f"
    % (was, now, was_front, now_front))

# ---------------------------------------------------------------- 2. веса с пони
ref_parts = []
for name in ("eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves", "eq_twilight_head"):
    src = pony[name]
    ob = src.copy()
    ob.data = src.data.copy()
    if ob.data.shape_keys:
        ob.shape_key_clear()
    bpy.context.scene.collection.objects.link(ob)
    ref_parts.append(ob)
bpy.ops.object.select_all(action="DESELECT")
for ob in ref_parts:
    ob.select_set(True)
bpy.context.view_layer.objects.active = ref_parts[0]
bpy.ops.object.join()
ref = bpy.context.view_layer.objects.active
ref.name = "pony_ref"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

for g in list(dragon.vertex_groups):     # чужие группы Mixamo больше не нужны
    dragon.vertex_groups.remove(g)
for g in ref.vertex_groups:
    dragon.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
dragon.select_set(True)
bpy.context.view_layer.objects.active = dragon
dt = dragon.modifiers.new("веса", "DATA_TRANSFER")
dt.object = ref
dt.use_vert_data = True
dt.data_types_verts = {"VGROUP_WEIGHTS"}
dt.vert_mapping = "POLYINTERP_NEAREST"
dt.layers_vgroup_select_src = "ALL"
dt.layers_vgroup_select_dst = "NAME"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
bpy.data.objects.remove(ref)

# Кости кистей — только кистям: у пони кисти висят на высоте живота, и бока корпуса дракона
# оказываются к ним ближе, чем к её телу (та же беда, что была у яка).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = dragon.data.vertices[i]
    for g in list(v.groups):
        if dragon.vertex_groups[g.group].name in HAND_BONES:
            dragon.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        dragon.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# Голова жёстко на кости головы — иначе морду ведут кости шеи и груди и она рвётся на стыке.
# Граница (jaw_z/is_head) задана выше, до правки рук.
BLEND = 0.15

head_group = dragon.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(dragon.data.vertices[i].groups):
        dragon.vertex_groups[g.group].remove([i])
head_group.add(head_idx, 1.0, "REPLACE")
blended = torn = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p) or appendage[i] is not None:
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]
    if d >= BLEND:
        # Ниже шеи кости головы быть не должно. Перенос весов даёт её гребню на груди: тот
        # торчит вперёд и вверх, и ближайшей точкой пони оказывается её подбородок. В игре
        # такая грудь складывалась при каждом повороте головы.
        if head_group.index in [g.group for g in dragon.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not dragon.data.vertices[i].groups:
                dragon.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in dragon.data.vertices[i].groups:
        dragon.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. разрез на части
group_names = {g.index: g.name for g in dragon.vertex_groups}
dominant = []
for v in dragon.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
lo, hi = P.min(0), P.max(0)

# спина: самая задняя точка узкой полосы вдоль позвоночника
spine = P[(np.abs(P[:, 0]) < 0.10) & (P[:, 2] > 0.9) & (P[:, 2] < 1.3)]
BACK = float(spine[:, 1].max())
head_pts = P[[i for i in range(len(P)) if is_head(P[i])]]
HEAD_TOP = float(head_pts[:, 2].max())
HEAD_BACK = float(head_pts[:, 1].max())
# Макушка: ниже этой доли высоты головы — уже лицо
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Граница гривы по глубине: доля пути от глаз к затылку. Всё дальше неё — грива и затылок,
# ближе — морда с оборкой (её в волосы брать нельзя, красилась бы цветом волос).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # перед морды
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
LEG_TOP = 0.44 * HEIGHT / 1.86
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# ЧЁЛКУ ДОБИРАТЬ НЕ НАДО. Пробовал ловить пряди, оставшиеся на лице, по тому, что прядь — тонкий
# лист (рядом изнанка со встречной нормалью, KD-дерево): вместе с ними в причёску уезжали чешуя
# над бровью и куски щеки, а голова усыхала со 322 вершин до 150. Пользователь: «сделай как до
# этого было, а то вообще плохо получилось с волосами». Остаются две отметки — макушка и затылок.


def part_of(i):
    if appendage[i]:                 # крылья и хвост отобраны выше, по удалённости от костей
        return appendage[i]
    p = P[i]
    if is_head(p):
        # «Причёска» — рога, гребень на макушке и грива, что спадает с затылка на плечи: на ней
        # работает цвет волос из окна внешности. Оборку вдоль морды брать нельзя (она красилась
        # бы заодно с рогами), поэтому граница по глубине: грива вся позади черепа, морда впереди.
        if p[2] > SKULL_TOP or p[1] > HAIR_BACK:
            return "hair"
        return "head"
    b = dominant[i]
    if b in HAND_BONES:
        return "gloves"
    if b in LEG_BONES and p[2] < LEG_TOP:
        return "legs"
    return "body"


labels = [part_of(i) for i in range(len(P))]
counts = {}
for name in labels:
    counts[name] = counts.get(name, 0) + 1
log("части по вершинам:", counts)

# ---------------------------------------------------------------- 4. материал и текстуры
src_mat = dragon.data.materials[0] if dragon.data.materials else None
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
if src_mat and src_mat.use_nodes:
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    for node in src_mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            img = node.image
            if not img.has_data:
                guess = os.path.join(os.path.dirname(SRC), os.path.basename(img.filepath_raw or img.name))
                if os.path.exists(guess):
                    img.filepath = guess
                    img.reload()
            fname = "eq_dragon_" + img.name.replace(".", "_").lower() + ".png"
            img.filepath_raw = os.path.join(tex_dir, fname)
            img.file_format = "PNG"
            try:
                img.save()
                log("текстура", fname, "%dx%d" % tuple(img.size))
            except RuntimeError as e:
                log("текстуру", fname, "сохранить не вышло:", e)
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.label = img.name
            low = img.name.lower()
            if bsdf and "normal" in low:
                nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
                mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif bsdf and "metal" not in low and "rough" not in low:
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

# ------------------------------------------------------------------------ моргание
# Моргает движок вершинными ключами головы: их ровно 101 (key_000..key_100), и кадры 86, 87, 88 —
# левый глаз, правый и оба (так же сделано у пони, tools/convert_twilight.py). Без ключей лицо
# просто застывшее, как у яка.
#
# У пони веки — своя геометрия, спрятанная над глазом. У дракона её нет: модель цельная, глаз
# просто НАРИСОВАН на текстуре. Поэтому закрываем его сжатием: вершины вокруг глаза сводим к его
# середине по высоте, и нарисованный глаз схлопывается в щёлочку. Этим же приёмом у пони
# дожимается глазное яблоко, когда движок применяет кадр не на полную силу.
#
# Глаза ищем по самой текстуре — это два симметричных тёмных пятна на морде. Пробу цвета берём
# чуть внутрь грани: развёртка у модели лоскутная, и на самом краю островка уже чернота атласа.
FACE_KEYS = 101         # столько вершинных ключей у ванильной головы
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
EYE_DARK = 0.30         # темнее этого — краска глаза, а не чешуя
EYE_CORE = 0.075        # в этом радиусе от середины глаза сжимаем полностью — это сам глаз
EYE_REACH = 0.115       # дальше сжатие спадает до нуля, чтобы не заминать щёку и надбровье
EYE_SQUASH = 0.92       # насколько сводим вершины к середине глаза


def eye_spots(ob):
    """Середины глаз на голове: два тёмных пятна на текстуре, по одному на сторону."""
    img = next((i for i in bpy.data.images
                if "texture_0" in i.name.lower() and i.has_data
                and not any(k in i.name.lower() for k in ("normal", "rough", "metal"))), None)
    uvs = ob.data.uv_layers.active
    if img is None or uvs is None:
        log("ВНИМАНИЕ: не нашёл текстуру или развёртку — моргания не будет")
        return []
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    tone = np.zeros(len(P))
    hits = np.zeros(len(P))
    for poly in ob.data.polygons:
        mid = np.mean([np.array(uvs.data[li].uv) for li in poly.loop_indices], axis=0)
        for li in poly.loop_indices:
            spot = np.array(uvs.data[li].uv) * 0.75 + mid * 0.25
            x = int(min(max(spot[0], 0.0), 0.999) * (w - 1))
            y = int(min(max(spot[1], 0.0), 0.999) * (h - 1))
            tone[ob.data.loops[li].vertex_index] += float(px[y, x, :3].mean())
            hits[ob.data.loops[li].vertex_index] += 1
    tone /= np.maximum(hits, 1)

    dark = (tone < EYE_DARK) & (hits > 0)
    near = [[] for _ in range(len(P))]
    for e in ob.data.edges:
        near[e.vertices[0]].append(e.vertices[1])
        near[e.vertices[1]].append(e.vertices[0])
    seen = np.zeros(len(P), bool)
    spots = []
    for start in np.flatnonzero(dark):
        if seen[start]:
            continue
        stack, blob = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            blob.append(cur)
            for other in near[cur]:
                if dark[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        spots.append(P[blob].mean(0))
    # по одному пятну на сторону — самое крупное скопление слева и справа
    out = []
    for side in (1, -1):
        mine = [s for s in spots if s[0] * side > 0]
        if mine:
            out.append(max(mine, key=lambda s: -abs(s[1])))
    return out


def add_blink(ob):
    spots = eye_spots(ob)
    if len(spots) != 2:
        log("ВНИМАНИЕ: глаз на текстуре не видно (%d пятен) — моргания не будет" % len(spots))
        return
    log("глаза найдены: (%.2f,%.2f,%.2f) и (%.2f,%.2f,%.2f)" % (*spots[0], *spots[1]))
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])

    def shut(sides):
        move = np.zeros_like(P)
        for side in sides:
            eye = spots[side]
            gap = np.linalg.norm(P - eye, axis=1)
            close = gap < EYE_REACH
            fade = np.clip((EYE_REACH - gap[close]) / max(EYE_REACH - EYE_CORE, 1e-6), 0.0, 1.0)
            move[close, 2] += (eye[2] - P[close, 2]) * EYE_SQUASH * fade
        return move

    ob.shape_key_add(name="Basis", from_mix=False)
    shifts = {k: shut(s) for k, s in ((86, [0]), (87, [1]), (88, [0, 1]))}
    for k in range(FACE_KEYS):
        key = ob.shape_key_add(name="key_%03d" % k, from_mix=False)
        if k not in shifts:
            continue
        for i, point in enumerate(key.data):
            point.co = point.co + Vector(shifts[k][i])
    log("моргание: %d ключей, в кадрах %s глаза закрываются (сжатие %.2f, радиус %.3f)"
        % (FACE_KEYS, "/".join(str(k) for k in sorted(BLINK_FRAMES)), EYE_SQUASH, EYE_REACH))


# ---------------------------------------------------------------- 5. части отдельными мешами
PLUG = 0.18        # на сколько корень крыла и хвоста уходит внутрь тела — запас хода при анимации
SMOOTH_ROUNDS = 18  # столько раз расслабляем гнездо от крыла и хвоста, чтобы спина стала гладкой
SMOOTH_GROW = 2     # на столько колец вокруг заплатки расходится заглаживание
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


SEPARATE_NEAR = 0.025  # головы ближе этого к гриве утапливаем вглубь (метры)
SEPARATE_PUSH = 0.010  # и на столько, у самых гривы

parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "wings", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = dragon.copy()
    ob.data = dragon.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    was_index = {v: i for i, v in enumerate(bm.verts)}   # номера до удаления — по ним labels
    keep_set = set(keep)
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # Место отрыва закрываем полигонами: иначе на стыке крыльев, хвоста и шеи зияют сквозные
    # дыры (изнутри грани не рисуются, и в игре там чернота). Закрывать надо ТОЛЬКО срезы:
    # у крыла и перепонки край свободен по всему обводу, и его заделывать нельзя — затянет
    # перепонку сплошным полотном. Срез узнаём по тому, что рядом в исходной сетке была
    # вершина другой части. Развёртку новым граням берём у соседних граней той же вершины,
    # иначе они тянут цвет из угла текстуры.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] != name for o in neighbours[was_index[v]])}

    # Крылья и хвост сидят на своей кости, а тело у их корня — на своих (спина у крыла идёт за
    # ключицей), поэтому при движении шов расходится и в щель видно насквозь. Поэтому у крыла и
    # хвоста корень продлеваем ВНУТРЬ тела: от среза уводим юбку к позвоночнику. Снаружи её не
    # видно, а щели она перекрывает с запасом.
    if name in ("wings", "tail"):
        seam = [e for e in bm.edges if len(e.link_faces) == 1 and all(v in cut for v in e.verts)]
        if seam:
            made = bmesh.ops.extrude_edge_only(bm, edges=seam)
            fresh = [g for g in made["geom"] if isinstance(g, bmesh.types.BMVert)]
            for v in fresh:
                here = Vector(v.co)
                inside = min((closest_on(here, a, b) for a, b in SPINE_LINE),
                             key=lambda q: (q - here).length)
                step = inside - here
                if step.length > 1e-6:
                    v.co = here + step.normalized() * min(PLUG, 0.8 * step.length)
            skirt = [f for f in made["geom"] if isinstance(f, bmesh.types.BMFace)]
            if uv is not None:
                for f in skirt:
                    for loop in f.loops:
                        near = next((l for l in loop.vert.link_loops if l.face not in skirt), None)
                        if near:
                            loop[uv].uv = near[uv].uv
            cut.update(fresh)        # дальний край юбки тоже закроем, чтобы карман был глухой
            log("  %s: корень продлён внутрь тела на %d граней" % (name, len(skirt)))

    seen_edge, patched, smooth = set(), 0, set()
    for start in [e for e in bm.edges if len(e.link_faces) == 1]:
        if start in seen_edge:
            continue
        loop_edges, stack = [], [start]
        seen_edge.add(start)
        while stack:                     # весь связный контур свободного края
            cur = stack.pop()
            loop_edges.append(cur)
            for v in cur.verts:
                for e in v.link_edges:
                    if len(e.link_faces) == 1 and e not in seen_edge:
                        seen_edge.add(e)
                        stack.append(e)
        ring = {v for e in loop_edges for v in e.verts}
        if len(ring) < 3 or sum(1 for v in ring if v in cut) < 0.6 * len(ring):
            continue                     # свободный край самой перепонки — не трогаем
        # чья это была граница: с крылом и хвостом гнездо потом заглаживаем, а шов с головой,
        # ногами и кистями трогать нельзя — там стык с соседней частью, он должен остаться
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] != name]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # У самих гривы основание остаётся открытой трубкой. А в голове место под гривеи
        # заделываем: без гривы (шлем, карта) на макушке зияла дыра между ушами (замечено в
        # редакторе 26.09.2026). Крышка лежит под гривеи и не мерцает с ними: голова ниже, см. SEPARATE_*.
        if name == "hair":
            continue
        was = set(bm.faces)
        try:
            bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
        except RuntimeError:
            bmesh.ops.holes_fill(bm, edges=loop_edges, sides=0)
        patch = [f for f in bm.faces if f not in was]
        for f in patch:
            for loop in f.loops:
                near = next((l for l in loop.vert.link_loops if l.face not in patch), None)
                if near and uv is not None:
                    loop[uv].uv = near[uv].uv
        if patch:
            bmesh.ops.recalc_face_normals(bm, faces=patch)
            if name == "head":
                # Голова почти выпуклая: нормаль заплатки обязана смотреть от центра головы,
                # иначе снаружи (изнанку игра не рисует) на месте заплатки будет дыра.
                centre = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
                for f in patch:
                    if f.normal.dot(f.calc_center_median() - centre) < 0:
                        f.normal_flip()
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # Гнездо от крыла и хвоста рваное: заплатка по такому краю выходит мятой. Расслабляем
        # её вместе с самим краем — спина становится ровной и гладкой, а крыло всё равно садится
        # поверх и заходит внутрь. Захватываем и кольцо вокруг, иначе заплатка выходит вмятиной,
        # но не трогаем вершины на свободном крае: там швы с головой, ногами и кистями.
        for _ in range(SMOOTH_GROW):
            smooth.update(o for v in list(smooth) for e in v.link_edges for o in e.verts
                          if not any(len(x.link_faces) == 1 for x in o.link_edges))
        for _ in range(SMOOTH_ROUNDS):
            bmesh.ops.smooth_vert(bm, verts=list(smooth), factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        log("  %s: спина заглажена, %d вершин" % (name, len(smooth)))
    if patched:
        log("  %s: заделано %d граней на месте отрыва" % (name, patched))
    if name == "head":
        # Где голова касается гривы вплотную, поверхности мерцают друг сквозь друга — одинаковая
        # глубина. Вершины головы ближе SEPARATE_NEAR к гриве утапливаем вглубь модели.
        from mathutils.bvhtree import BVHTree
        horn_faces = [f for f in dragon.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]
        if horn_faces:
            tree = BVHTree.FromPolygons([tuple(v.co) for v in dragon.data.vertices],
                                        [tuple(f.vertices) for f in horn_faces])
            bm.normal_update()
            pushed = 0
            for v in bm.verts:
                hit = tree.find_nearest(v.co)
                if hit[0] is None or hit[3] >= SEPARATE_NEAR:
                    continue
                v.co -= v.normal * (SEPARATE_PUSH * (0.4 + 0.6 * (1.0 - hit[3] / SEPARATE_NEAR)))
                pushed += 1
            log("  голова отодвинута от гривы вглубь: %d вершин" % pushed)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if name in ("tail", "wings"):   # предметы целиком на одной кости, как хвост пони
        anchor = PELVIS if name == "tail" else "bip01_spine2_11"
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name=anchor).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    if name == "hair":              # причёска целиком на голове
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name="bip01_head_13").add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    if name == "head":
        add_blink(ob)
    parts[name] = ob
    log("%s: %d вершин, %d граней" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
bpy.data.objects.remove(dragon)

# ---------------------------------------------------------------- 6. экспорт и превью
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts.values()]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
path = os.path.join(OUT, "eq_%s.fbx" % RACE)
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспорт", path)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "eq_%s.blend" % RACE))

prev = os.path.join(OUT, "preview")
os.makedirs(prev, exist_ok=True)
scene = bpy.context.scene
# Ванильный человек НА МЕСТЕ дракона: по нему видно, что вылезает из доспеха и насколько
# руки и ноги вынесены вперёд. Тот же файл, что и для посадки по глубине.
overlay = []
if os.path.exists(HUMAN):
    known = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=HUMAN, forward_axis="Y", up_axis="Z")
    for ob in [o for o in bpy.data.objects if o not in known]:
        ob.rotation_euler[2] = math.pi      # ванильные модели смотрят в +Y, наши — в -Y
        ob.color = (0.95, 0.35, 0.35, 1.0)
        ob.hide_render = True
        overlay.append(ob)
for ob in pony.values():
    ob.location.x -= 2.0        # пони рядом — для сравнения роста
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
# пони рядом должна быть видна: в исходном файле часть мешей скрыта
for ob in pony.values():
    ob.hide_render = ob.hide_viewport = False
    ob.color = (0.75, 0.70, 0.80, 1.0)
    if ob.name not in bpy.context.scene.collection.objects:
        try:                     # в исходном файле пони может лежать в отключённой коллекции
            bpy.context.scene.collection.objects.link(ob)
        except RuntimeError:
            pass
# каждой части дракона свой цвет — так видно, где прошёл разрез
PART_COLOUR = {"body": (0.80, 0.75, 0.65, 1), "legs": (0.35, 0.55, 0.85, 1),
               "gloves": (0.95, 0.80, 0.25, 1), "head": (0.35, 0.80, 0.45, 1),
               "hair": (0.90, 0.35, 0.75, 1), "wings": (0.55, 0.40, 0.85, 1),
               "tail": (0.95, 0.45, 0.30, 1)}
for name, ob in parts.items():
    ob.color = PART_COLOUR.get(name, (1, 1, 1, 1))
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
# Кадр «рост» — рядом с пони для сравнения, остальные без неё: иначе она заслоняет дракона
# сбоку и не видно, что осталось на спине и где прошёл разрез.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # крылья и хвост сняты: видно, не осталось ли их кусков на теле и не унесли ли они своё
        # со спины: там гнёзда от крыльев и хвоста, ради них кадр и нужен
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair")),
        # одна голова — так её показывает модкит: видно, не осталось ли на лице прядей гривы
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        # поверх ванильного человека: красным то, что вылезает за силуэт, под который сшита броня
        ("поверх человека", (0, -6, 1.05), FRONT, 2.6, "поверх", ("wings", "tail")),
        ("поверх человека сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, "поверх",
         ("wings", "tail"))):
    for ob in pony.values():
        ob.hide_render = with_pony is not True
    for ob in overlay:
        ob.hide_render = with_pony != "поверх"
    for name, ob in parts.items():
        ob.hide_render = name in hide
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "dragon_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
