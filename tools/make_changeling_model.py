# -*- coding: utf-8 -*-
"""Чейнджлинг из готовой модели (Т-поза, свой скелет Mixamo) — на скелет пони, по частям, в FBX.

Запуск (headless Blender, открывает готовую пони — в ней скелет и образец привязки):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_changeling_model.py \
      -- "<путь к .fbx чейнджлинга>" "<папка вывода>"

Списан с tools/make_griffon.py (а тот — с make_dragon.py), там же объяснения общих мест.
Чем чейнджлинг отличается от грифона:
  1. Крыльев ЧЕТЫРЕ — две пары стрекозиных, верхняя на уровне лопаток и нижняя у пояса. Опознаём
     их не по величине и не по высоте, а по тому, что все четыре сидят В СТОРОНЕ от оси, а хвост
     один и идёт по оси.
  2. Голова пони с рогом и ушами; уши и рог — мелкие куски вдали от костей, в порог крупности
     не проходят и остаются голове.

Этот скрипт ЗАМЕНЯЕТ прежнего чейнджлинга, которого делали из меша пони (tools/make_changeling.py):
имена частей те же, поэтому XML расы менять не нужно — достаточно переимпорта в редакторе.

Части на выходе:
  eq_changeling_body   — туловище и руки (body_meta_mesh)
  eq_changeling_legs   — ноги (legs_mesh)
  eq_changeling_gloves — кисти (hands_mesh)
  eq_changeling_head   — голова с рогом и ушами (face_meta_mesh)
  eq_changeling_hair   — грива: макушка и затылок (причёска, красится цветом волос)
  eq_changeling_wings  — обе пары крыльев (предмет)
  eq_changeling_tail   — хвост (предмет)
Дальше — импорт FBX в Modding Kit руками, потом tools/changeling_material.ps1.
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

RACE = "changeling"
HEIGHT = 1.88          # рост чейнджлинга (пони 1.86, грифон 1.95, як 2.05, дракон 2.10)
MAT = "eq_changeling_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[changeling]", *a, flush=True)


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
chl = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # мусор генератора: шарик-заготовка и прочие мелкие меши
    if ob.type == "MESH" and ob is not chl:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (chl.name, len(chl.data.vertices), source_skel.name if source_skel else "нет"))

own_bones = []
if source_skel:
    # Поза покоя: в файле лежит анимация бега, и импорт ставит модель в её первый кадр. Сама
    # сетка хранится в позе привязки (Т), поэтому достаточно снять анимацию и модификатор.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = chl
    for mod in list(chl.modifiers):
        if mod.type == "ARMATURE":
            chl.modifiers.remove(mod)
    chl.parent = None
    # Кости запоминаем отрезками в мировых координатах ДО удаления скелета: по удалённости от
    # них ниже отбираются крылья и хвост. Концевые кости Mixamo («_end») торчат в стороны
    # мимо сетки и только портят замер.
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят (запомнено %d костей), модель в позе привязки" % len(own_bones))

bpy.ops.object.select_all(action="DESELECT")
chl.select_set(True)
bpy.context.view_layer.objects.active = chl
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Генератор отдаёт «суп»: соседние треугольники не делят вершины. Сшиваем — иначе не найти
# связные куски и по швам при деформации расходятся щели.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(chl.data.vertices))


def coords():
    return np.array([(chl.matrix_world @ v.co)[:] for v in chl.data.vertices])


# ------------------------------------------------- крылья и хвост: связные куски вдали от костей
# Приём тот же, что у дракона: перо и хвост торчат далеко от любой кости, а кожа туловища, рук и
# ног всегда рядом со своей. Берём всё, что дальше FAR_FRAC от костей, и режем на связные куски.
#
# А вот опознаём куски иначе. У чейнджлинга при FAR_FRAC=0.114 их шесть (замерено на модели):
#   169 и 154 вершины, |x| 0.19..0.60, z 1.22..1.75 — верхняя пара крыльев;
#   120 и 120 вершин,  |x| 0.13..0.49, z 0.83..1.16 — нижняя пара;
#   214 вершин, x около нуля, z 0.15..0.82         — хвост;
#   32 и 14 вершин на макушке                      — уши, в порог крупности не проходят.
# Отличать по высоте нельзя (нижние крылья и хвост на одном уровне), по величине тоже (хвост
# крупнее любого крыла). Зато все крылья сидят В СТОРОНЕ от оси, а хвост идёт по оси.
FAR_FRAC = 0.114
PART_MIN = 0.02       # кусок меньше этой доли вершин — уши и рог: их не трогаем
WING_SIDE = 0.09      # кусок, чья середина дальше этой доли роста от оси, — крыло
TAIL_HIGH = 0.55      # хвост ищем ниже этой доли роста
TAIL_AXIS = 0.09      # и не дальше этой доли роста от оси тела
# Перо у самого плеча лежит поверх руки и по удалённости не отбирается. Но в родном скиннинге
# видно, кто есть кто: рука не отходит от своей кости дальше ARM_FAR, а перо — заметно дальше.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


appendage = [None] * len(chl.data.vertices)
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in chl.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in chl.data.vertices])
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
    for e in chl.data.edges:
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
    floor = float(P[:, 2].min())
    big = [c for c in sorted(chunks, key=len, reverse=True) if len(c) >= PART_MIN * len(P)]
    for chunk in big:
        mid = P[chunk].mean(0)
        top = float(P[chunk][:, 2].max()) - floor
        if mid[1] < middle_y:          # всё наше — за спиной; впереди быть нечему
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        if abs(mid[0]) > WING_SIDE * height:
            name = "wings"          # обе пары: и та, что на лопатках, и та, что у пояса
        elif mid[2] - floor < TAIL_HIGH * height and abs(mid[0]) < TAIL_AXIS * height:
            name = "tail"
        else:
            log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) оставлен телу"
                % (len(chunk), *mid, top))
            continue
        log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) -> %s"
            % (len(chunk), *mid, top, name))
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
    chl.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
chl.scale = (scale, scale, scale)
chl.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
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
for v in chl.data.vertices:
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
SHOULDER_X = 0.16               # плечевой сустав по X (кость плеча модели после посадки)
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
# Числа набираются по замечаниям из игры, как и у дракона.
ARM_REACH = 1.00    # во сколько раз дальше кости кисти уходит запястье
ARM_DROP = 0.0      # на сколько градусов рука дополнительно опускается к телу
ARM_THICK = 1.00    # во сколько раз толще поперёк оси (само совмещение руку подтачивает)
HAND_SMALL = 1.00   # во сколько раз уменьшается сама кисть

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
    v = chl.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука дракона %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ---------------------------------------------------------------- кисть поменьше
# Лапа у модели крупная, с длинными когтями, и рядом с человеческим рукавом смотрится лопатой.
# Ужимаем ВОКРУГ ЗАПЯСТЬЯ (кость кисти пони), а не вокруг середины лапы: иначе на стыке
# с предплечьем открывается щель. Ближе к телу кисть подбирает ARM_DROP выше — он же кладёт
# всю руку вдоль корпуса, а не в стороны.
if HAND_SMALL != 1.0:
    P = coords()
    shrunk = 0
    for i in (set(arm_zone) & own_hand):
        p = P[i]
        sign = 1.0 if p[0] > 0 else -1.0
        wrist = Vector((H_p.x * sign, H_p.y, H_p.z))
        chl.data.vertices[i].co = wrist + (Vector((p[0], p[1], p[2])) - wrist) * HAND_SMALL
        shrunk += 1
    P = coords()
    hands = P[[i for i in hand_idx]]
    log("кисть ужата в %.2f раза (%d вершин), центр лапы теперь (%.2f,%.2f,%.2f)"
        % (HAND_SMALL, shrunk, abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean()))

# ---------------------------------------------------------------- руки вперёд, ноги назад
# Подвижки по глубине: руки вперёд, ноги назад. У грифона понадобились, у чейнджлинга
# пока выключены — включать по виду в игре.
# Морда смотрит в -Y, значит вперёд — это минус, к хвосту — плюс.
#
# Обе подвижки с плавным сходом на нет: рука отпускает у плеча (тот же ramp, что у разворота),
# нога — у таза. Иначе на суставе рвётся.
ARM_FORWARD = 0.0       # на сколько метров руки уезжают вперёд, от хвоста
ARM_OUT = 0.0           # и на сколько в стороны, от торса
LEG_BACK = 0.0          # на сколько метров ноги уезжают назад, к хвосту
LEG_FULL = 0.55         # ниже этой высоты нога двигается целиком
LEG_FADE = 0.95         # выше этой — уже таз, его не трогаем

P = coords()
for i in arm_zone:
    p = P[i]
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)
    chl.data.vertices[i].co.y -= ARM_FORWARD * t
    chl.data.vertices[i].co.x += math.copysign(ARM_OUT * t, p[0])

# ---------------------------------------------------------------- плечи вперёд и вниз
# У модели плечи заведены назад и подняты — фигура выглядит сгорбленной («плечи сильно уведены
# назад и вверх», 24.09.2026). Двигаем ВЕСЬ плечевой пояс вместе с рукой: если тащить только
# накладку плеча, рука отстаёт и на суставе получается ступенька.
# Вес: по ширине нарастает от края торса к плечу, по высоте затухает к подмышке, чтобы бок
# остался на месте.
SHOULDER_FORWARD = 0.045    # на сколько метров плечо уезжает вперёд
SHOULDER_DOWN = 0.030       # и вниз
SHOULDER_FROM_X = 0.06      # ближе этого к оси — уже грудь и шея, их не трогаем
SHOULDER_FULL_X = 0.17      # дальше этого вес полный
SHOULDER_LOW = 1.02         # ниже этой высоты подвижки нет
SHOULDER_FULL_Z = 1.22      # выше этой — полная

P = coords()
moved_shoulders = 0
for i, p in enumerate(P):
    if appendage[i] is not None or is_head(p) or abs(p[0]) < SHOULDER_FROM_X or p[2] < SHOULDER_LOW:
        continue
    wx = min(1.0, (abs(p[0]) - SHOULDER_FROM_X) / max(SHOULDER_FULL_X - SHOULDER_FROM_X, 1e-6))
    wz = min(1.0, (p[2] - SHOULDER_LOW) / max(SHOULDER_FULL_Z - SHOULDER_LOW, 1e-6))
    w = (wx * wx * (3 - 2 * wx)) * (wz * wz * (3 - 2 * wz))
    if w <= 0:
        continue
    v = chl.data.vertices[i]
    v.co.y -= SHOULDER_FORWARD * w
    v.co.z -= SHOULDER_DOWN * w
    moved_shoulders += 1
log("плечевой пояс сдвинут вперёд на %.3f и вниз на %.3f м (%d вершин)"
    % (SHOULDER_FORWARD, SHOULDER_DOWN, moved_shoulders))

P = coords()
moved_legs = 0
for i, p in enumerate(P):
    if appendage[i] is not None or p[2] > LEG_FADE:
        continue
    if p[2] <= LEG_FULL:
        w = 1.0
    else:
        u = 1.0 - (p[2] - LEG_FULL) / (LEG_FADE - LEG_FULL)
        w = u * u * (3 - 2 * u)
    if w > 0:
        chl.data.vertices[i].co.y += LEG_BACK * w
        moved_legs += 1
log("руки сдвинуты вперёд на %.2f м и в стороны на %.2f м (%d вершин), ноги назад на %.2f м (%d вершин)"
    % (ARM_FORWARD, ARM_OUT, len(arm_zone), LEG_BACK, moved_legs))

# ------------------------------------------------------------------- грудная клетка пошире
# У модели узкая грудь — рядом с широким тазом смотрится трубой. Раздаём её по X, но не одним
# масштабом: иначе вместе с грудью уедут и руки, и кисти сойдут со своих костей. Внутри туловища
# ширина растёт пропорционально, снаружи сдвиг сходит на нет к запястью, а по высоте — плавно
# за пределами рёбер. Крылья и хвост двигаем вместе со всеми, чтобы корни остались на месте.
# Первый проход: грудь не трогаем (1.0). Числа подбираются по замечаниям из игры, как у грифона.
CHEST_WIDE = 1.35
# Полоса своя: чейнджлинг ростом 1.88, ключицы у него на 1.34, таз на 1.00.
CHEST_BAND = (1.00, 1.34)   # рёбра и живот: от таза до ключиц
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
    chl.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- верх груди поменьше
# Раздавать надо рёбра, а не бюст: сверху грудь выпирала и вперёд, и в стороны. Ужимаем верхнюю
# часть груди по ширине и глубине вокруг её же середины — так низ (рёбра) остаётся широким, а
# верх подбирается. К плечам сходит на нет, иначе от них оторвутся руки.
UPPER_SMALL = 1.00          # во сколько раз ужимаем верх груди (1.0 — не трогаем)
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
    v = chl.data.vertices[i]
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

for g in list(chl.vertex_groups):     # чужие группы Mixamo больше не нужны
    chl.vertex_groups.remove(g)
for g in ref.vertex_groups:
    chl.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
chl.select_set(True)
bpy.context.view_layer.objects.active = chl
dt = chl.modifiers.new("веса", "DATA_TRANSFER")
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
    v = chl.data.vertices[i]
    for g in list(v.groups):
        if chl.vertex_groups[g.group].name in HAND_BONES:
            chl.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        chl.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# Голова жёстко на кости головы — иначе морду ведут кости шеи и груди и она рвётся на стыке.
# Граница (jaw_z/is_head) задана выше, до правки рук.
BLEND = 0.15

head_group = chl.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(chl.data.vertices[i].groups):
        chl.vertex_groups[g.group].remove([i])
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
        if head_group.index in [g.group for g in chl.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not chl.data.vertices[i].groups:
                chl.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in chl.data.vertices[i].groups:
        chl.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. разрез на части
group_names = {g.index: g.name for g in chl.vertex_groups}
dominant = []
for v in chl.data.vertices:
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
HAIR_PART = False     # резать ли макушку в причёску (см. part_of: у чейнджлинга там уши и рог)
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Граница гривы по глубине: доля пути от глаз к затылку. Всё дальше неё — грива и затылок,
# ближе — морда с оборкой (её в волосы брать нельзя, красилась бы цветом волос).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # перед морды
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
# Где проходит разрез между телом и ногами: как у пони, 0.44 от роста. Поднять — как у грифона.
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
        # У дракона и грифона макушка уезжает в «причёску» — там это гребень и перья, и цвет
        # волос из окна внешности их красит. ЧЕЙНДЖЛИНГУ ТАК НЕЛЬЗЯ: на макушке у него уши и рог,
        # а тег причёсок выдаёт трутням «Bald» — вместе с причёской пропали бы уши.
        # Поэтому голова остаётся целой, а гривы у расы свои, отдельными мешами
        # (tools/make_changeling_hair.py, гривы Кризалис).
        if HAIR_PART and (p[2] > SKULL_TOP or p[1] > HAIR_BACK):
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
src_mat = chl.data.materials[0] if chl.data.materials else None
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
            fname = "eq_changeling_" + img.name.replace(".", "_").lower() + ".png"
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
# Порог у грифона НАМНОГО строже драконьих 0.30: у орла бурые перья надбровья темнее 0.3, и по
# такому порогу самым крупным тёмным пятном выходила бровь — моргание срабатывало выше глаза
# (замечено в игре 24.09.2026). Чёрный зрачок заметно темнее любого пера, по нему и метим.
EYE_DARK = 0.16
# Зона сжатия — полуоси «дольки» вокруг середины глаза: вбок, вглубь, по высоте. Глаз у грифона
# миндалевидный и лежит наискось, поэтому вдоль него зона длинная, а по высоте короткая — иначе
# вместе с глазом схлопываются бровь и щека, и морда складывается гармошкой.
EYE_ZONE = (0.105, 0.095, 0.085)
EYE_FULL = 0.80         # внутри этой доли зоны сжимаем полностью, дальше плавно сходит на нет
EYE_SQUASH = 0.92       # насколько сводим вершины к середине глаза
EYE_SIDE = 0.02         # ближе этого к оси — не глаз, а клюв
# Метка садится на ЗРАЧОК, а он у грифона у самого клюва, тогда как сам глаз с белком уходит
# наружу и чуть назад — закрывалась только половина у носа (замечено в игре 24.09.2026).
# Поэтому от найденного зрачка отступаем к середине глаза.
EYE_OUT = 0.020         # наружу от зрачка (у чейнджлинга зрачок почти в середине глаза)
EYE_BACK = 0.015        # и чуть назад: глаз большой и почти круглый, не миндалевидный
EYE_DOWN = 0.020        # и ниже: метка садится на зрачок, а он выше середины большого глаза


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
        spots.append((P[blob].mean(0), len(blob), float(tone[blob].mean())))
    for centre, size, shade in sorted(spots, key=lambda s: -s[1])[:8]:
        log("  тёмное пятно: %3d вершин, яркость %.2f, на (%.2f,%.2f,%.2f)" % (size, shade, *centre))
    # По одному пятну на сторону: в передней части головы (клюв по центру на сторону не попадает,
    # затылочные тени — позади) и САМОЕ ТЁМНОЕ, а не самое крупное. Крупное — это бурая бровь:
    # перьев на ней больше, чем полигонов на зрачке, и по величине побеждала она.
    front = float(np.percentile(P[:, 1], 45))
    out = []
    for side in (1, -1):
        mine = [(c, n, s) for c, n, s in spots if c[0] * side > EYE_SIDE and c[1] < front]
        out.append(min(mine, key=lambda s: s[2])[0] if mine else None)
    # Голова низкополигональная и несимметричная: на зрачок приходится одна-две вершины, и на
    # одной стороне тёмной пробы может не оказаться вовсе. Тогда отражаем найденный глаз — это
    # надёжнее, чем ослаблять порог до бурых перьев брови.
    if out[0] is None and out[1] is not None:
        out[0] = np.array([-out[1][0], out[1][1], out[1][2]])
        log("  левый глаз отражён с правого")
    elif out[1] is None and out[0] is not None:
        out[1] = np.array([-out[0][0], out[0][1], out[0][2]])
        log("  правый глаз отражён с левого")
    # от зрачка — к середине глаза (см. EYE_OUT)
    for spot in out:
        if spot is not None:
            spot[0] += math.copysign(EYE_OUT, spot[0])
            spot[1] += EYE_BACK
            spot[2] -= EYE_DOWN
    return [s for s in out if s is not None]


def add_blink(ob):
    spots = eye_spots(ob)
    if len(spots) != 2:
        log("ВНИМАНИЕ: глаз на текстуре не видно (%d пятен) — моргания не будет" % len(spots))
        return
    log("глаза найдены: (%.2f,%.2f,%.2f) и (%.2f,%.2f,%.2f)" % (*spots[0], *spots[1]))
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])

    def shut(sides):
        move = np.zeros_like(P)
        radius = np.array(EYE_ZONE)
        for side in sides:
            eye = spots[side]
            # Зона не шар, а «долька» по форме глаза: широкая вбок и вглубь, низкая по высоте.
            # Шаром не выходило: чтобы дожать наружный угол, радиус приходилось брать таким,
            # что заодно сминались бровь и щека, и морда складывалась гармошкой.
            step = (P - eye) / radius
            # По высоте — отдельно от «вдоль глаза»: зона выходит лепёшкой, а не мячом.
            # Если считать все три оси вместе, наружный угол глаза (далеко вбок И чуть выше
            # середины) выпадает из зоны и остаётся открытым.
            gap = np.maximum(np.sqrt((step[:, 0] ** 2 + step[:, 1] ** 2)), np.abs(step[:, 2]))
            close = gap < 1.0
            fade = np.clip((1.0 - gap[close]) / max(1.0 - EYE_FULL, 1e-6), 0.0, 1.0)
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
        % (FACE_KEYS, "/".join(str(k) for k in sorted(BLINK_FRAMES)), EYE_SQUASH, EYE_ZONE[0]))


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


parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "wings", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = chl.copy()
    ob.data = chl.data.copy()
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
        # Швы причёски не заделываем вовсе — ни с головой, ни с телом: причёска с персонажа не
        # снимается и закрывает их собой, дыр наружу тут нет. А две крышки на одном месте в игре
        # мерцают друг сквозь друга, и рваная крышка причёски вдобавок ложится поперёк лица.
        if "hair" in (name, owner):
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
bpy.data.objects.remove(chl)

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
    scene.render.filepath = os.path.join(prev, "changeling_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
