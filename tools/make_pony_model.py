# -*- coding: utf-8 -*-
"""Новая пони (Meshy, аликорн: рог, крылья, хвост; Т-поза, свой скелет Mixamo) — на скелет
пони-донора, по частям, в FBX.

Запуск (headless Blender, открывает прежнюю пони — в ней скелет и образец привязки):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_pony_model.py       -- "<путь к .fbx новой пони>" "<папка вывода>"

Списан с tools/make_deer_model.py (тот — с make_yak_model.py и make_dragon.py, там же объяснения
общих мест). Чем новая пони отличается:
  1. Исходник — .fbx со скелетом Mixamo и анимацией бега, а текстуры лежат отдельными PNG рядом
     (цвет, нормали, шероховатость и металличность — четыре файла, а не .glb с упакованными).
  2. Крылья и хвост НЕ отделить «вдали от костей», как у модели: сетка у пони одна (5 тысяч
     вершин, ни одного отдельного куска), а скелет Mixamo стоит по оси тела, поэтому и голова
     с мордой, и крыло оказываются далеко от него. Автоскиннинг у модели плохой: хвост и правое
     крыло записаны на кость правого бедра. Поэтому их ищем по ПОЛОЖЕНИЮ — крылья висят позади
     рук по бокам, хвост — за задом и ногами.
  3. Грива вшита в голову и режется по положению: затылок и верх — причёска (красится цветом
     волос), лицо с чёлкой у глаз — голова. Рог — отдельная часть тела: его вешает на скелет
     src/EquestriaBodyParts.cs, как хвост и крылья.

Части на выходе:
  eq_pony_body   — туловище и руки (body_meta_mesh)
  eq_pony_legs   — ноги (legs_mesh)
  eq_pony_gloves — кисти (hands_mesh)
  eq_pony_head   — голова с мордой, ушами и гривой (face_meta_mesh)
  eq_pony_hair   — грива (причёска, красится цветом волос)
  eq_pony_horn   — рог (часть тела на голове, как хвост и крылья)
  eq_pony_wings  — крылья (предмет в слот плаща)
  eq_pony_tail   — хвост (предмет)
Дальше — импорт FBX в Modding Kit руками, потом tools/pony_material.ps1.
"""
import math
import os
import shutil
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "pony"
HEIGHT = 1.86          # рост пони: вровень с ванильным человеком
MAT = "eq_pony_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[pony]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: (skel.matrix_world @ b.head_local) for b in skel.data.bones}

# ---------------------------------------------------------------- 1. импорт и А-поза
before = set(bpy.data.objects)
if SRC.lower().endswith((".glb", ".gltf")):
    bpy.ops.import_scene.gltf(filepath=SRC)
else:
    bpy.ops.import_scene.fbx(filepath=SRC)
added = [o for o in bpy.data.objects if o not in before]
mdl = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # мусор генератора: шарик-заготовка и прочие мелкие меши
    if ob.type == "MESH" and ob is not mdl:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (mdl.name, len(mdl.data.vertices), source_skel.name if source_skel else "нет"))

if source_skel:
    # Поза покоя: в файле лежит анимация бега, и импорт ставит модель в её первый кадр. Сама
    # сетка хранится в позе привязки (Т), поэтому достаточно снять анимацию и модификатор.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = mdl
    for mod in list(mdl.modifiers):
        if mod.type == "ARMATURE":
            mdl.modifiers.remove(mod)
    mdl.parent = None
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят, модель в позе привязки")

bpy.ops.object.select_all(action="DESELECT")
mdl.select_set(True)
bpy.context.view_layer.objects.active = mdl
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Генератор отдаёт «суп»: соседние треугольники не делят вершины. Сшиваем — иначе не найти
# связные куски и по швам при деформации расходятся щели.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(mdl.data.vertices))


def coords():
    return np.array([(mdl.matrix_world @ v.co)[:] for v in mdl.data.vertices])


# ---------------------------------------------- крылья и хвост: отбор по положению в исходнике
# Скелет Mixamo стоит по оси тела, а веса у Meshy плохие (хвост и правое крыло записаны на бедро),
# поэтому ни «вдали от костей», ни веса тут не помогают. Зато форма ясная: маленькие сложенные
# крылья висят ЗА руками (руки у неё вытянуты в Т-позе строго вбок и уходят вперёд от крыльев),
# а хвост — за крупом и ногами. Пороги — в исходных метрах (морда смотрит в -Y, рост 1.92 с рогом);
# отбор идёт ДО посадки, а номера вершин дальше не меняются.
WING_X = 0.19           # ближе к оси — уже бок туловища: корень крыла срезаем по нему
WING_Y = 0.05           # крылья лежат за спиной, а руки — у y <= 0
WING_Z_TOP = 1.28
WING_Z_LOW = (0.90, 0.16, 1.20)   # нижний край: z = 0.90 у корня, и на 1.2 м вниз на метр в сторону
WING_Z_FLOOR = 0.52
TAIL_X = 0.22           # шире этого от оси — уже бёдра и крылья
TAIL_Y_LOW, TAIL_Y_HIGH = 0.10, 0.13   # за этой глубиной (внизу / у крупа) — хвост
TAIL_Z_TOP = 1.02
PART_MIN = 0.03       # кусок меньше этой доли вершин — не крыло: возвращается телу
ISLAND_NEAR = 0.05    # островок дальше этой доли роста от крыла и хвоста — не их

# Соседи каждой вершины: по ним ниже ищутся связные куски и заделываются срезы.
neighbours = [[] for _ in range(len(mdl.data.vertices))]
for e in mdl.data.edges:
    neighbours[e.vertices[0]].append(e.vertices[1])
    neighbours[e.vertices[1]].append(e.vertices[0])


def components(member):
    """Связные куски из вершин, для которых member[i] истинно, крупные первыми."""
    seen = np.zeros(len(member), bool)
    out = []
    for start in range(len(member)):
        if not member[start] or seen[start]:
            continue
        stack, chunk = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            chunk.append(cur)
            for other in neighbours[cur]:
                if member[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        out.append(chunk)
    return sorted(out, key=len, reverse=True)


P = coords()
height = float(P[:, 2].max() - P[:, 2].min())
ax, ay, az = np.abs(P[:, 0]), P[:, 1], P[:, 2]
wing_low = np.maximum(WING_Z_FLOOR, WING_Z_LOW[0] - (ax - WING_Z_LOW[1]) * WING_Z_LOW[2])
wing_like = (ax >= WING_X) & (ay >= WING_Y) & (az <= WING_Z_TOP) & (az >= wing_low)
tail_like = (ax < TAIL_X) & (az < TAIL_Z_TOP) & (ay >= np.where(az < 0.80, TAIL_Y_LOW, TAIL_Y_HIGH)) & ~wing_like

appendage = [None] * len(P)
own_hand = set()      # у модели своих весов кисти нет: кисть найдём по размаху
for chunk in components(wing_like):
    if len(chunk) < PART_MIN * len(P):
        break
    for i in chunk:
        appendage[i] = "wings"
tail_chunks = components(tail_like)
if tail_chunks:
    for i in tail_chunks[0]:
        appendage[i] = "tail"

# Всё, что осталось от отбора мелкими островками (перья на краю, кончик хвоста, косичка гривы
# у самого корня), возвращаем ближайшему из крыла и хвоста, если оно рядом; остальное — телу.
rest = components(np.array([a is None for a in appendage]))
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
log("крылья и хвост по положению: крылья %d вершин, хвост %d" % (found["wings"], found["tail"]))
if not found["wings"] or not found["tail"]:
    log("ВНИМАНИЕ: крылья или хвост не найдены — проверьте пороги WING_* и TAIL_*")


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: размер %.2f x %.2f x %.2f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))

# Морда должна смотреть в -Y (как у пони). Морда — самая выступающая по Y точка верхней трети.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    mdl.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

# Ростом считаем МАКУШКУ, а не кончики рогов. Рог у пони тянется на несколько сантиметров выше макушки, и
# по габаритному ящику вся модель садилась на четверть ниже: лицо уходило под линию челюсти и
# доставалось телу, а кости головы хватало на одни рога. Макушку узнаём по толщине среза —
# череп с ушами глубокий, рога же тонкие ветки.
def crown_z(pts):
    low, high = float(pts[:, 2].min()), float(pts[:, 2].max())
    tall = high - low
    step = 0.02 * tall
    bands = []
    for z0 in np.arange(low + 0.6 * tall, high, step):
        band = pts[(pts[:, 2] >= z0) & (pts[:, 2] < z0 + step)]
        if len(band) > 8:
            bands.append((float(z0), float(band[:, 1].max() - band[:, 1].min())))
    if not bands:
        return high
    thick = max(d for _, d in bands)
    return max(z0 for z0, d in bands if d > 0.5 * thick) + step


CROWN = crown_z(P)
log("макушка на %.3f из %.3f — рога выше неё в рост не идут" % (CROWN - lo[2], hi[2] - lo[2]))
scale = HEIGHT / (CROWN - lo[2])
mdl.scale = (scale, scale, scale)
mdl.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- глубина: сажаем по ТОРСУ, а не по габаритам
# По габаритному ящику сажать нельзя: хвост модели тянет ящик назад, и туловище уезжает вперёд
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
for v in mdl.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Где кончается шея и начинается голова. У этой пони череп с гривой спускается до подбородка и
# ниже (низ головы на 1.40-1.45 м), а шея тонкая. Прежняя наклонная линия «под мордой» шла на
# 1.6 м у затылка и отрезала телу низ головы и затылок с гривой (замечено в редакторе
# 26.09.2026), поэтому здесь ровная отметка чуть ниже подбородка: всё выше неё — голова.
NECK_Z = 1.40
JAW_SLOPE, JAW_FROM = 0.0, 0.0


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ------------------------------------------------------------------ голову с шеей — назад
# Посадка по глубине равняет ТОРС, а голова у этой модели вынесена вперёд сильнее, чем у человека:
# её затылок стоял на y 0.07, тогда как у пони 0.14. В доспехе это видно сразу — голова торчит
# перед нагрудником (замечено в игре 24.09.2026). Двигаем голову и шею назад, а к низу шеи сдвиг
# сходит на нет, иначе стык с телом разойдётся.
HEAD_SHIFT = 0.07        # на сколько метров назад уезжает голова
HEAD_SHIFT_FADE = 0.14   # на скольких метрах ниже линии челюсти сдвиг сходит на нет

P = coords()
_moved = 0
for i, p in enumerate(P):
    w = (p[2] - jaw_z(p) + HEAD_SHIFT_FADE) / HEAD_SHIFT_FADE
    w = min(1.0, max(0.0, w))
    if w <= 0:
        continue
    w = w * w * (3 - 2 * w)
    mdl.data.vertices[i].co.y += HEAD_SHIFT * w
    _moved += 1
P = coords()
log("голова с шеей сдвинута назад на %.2f м (затронуто %d вершин)" % (HEAD_SHIFT, _moved))


# ---------------------------------------------- руки из Т-позы на руку пони (поворот + длина)
# Просто повернуть на 22 градуса мало: рука модели длиннее пониной на 10%, поэтому локоть
# приходился на кость предплечья, а кисть — мимо кости кисти, и в игре руки выглядели кривыми.
# Совмещаем отрезок «плечо — кисть» модели с таким же отрезком скелета: поворот вокруг плеча
# плюс масштаб по длине. У самого сустава преобразование набирается плавно (ramp), иначе рвётся.
SHOULDER_X = 0.18               # плечевой сустав по X (кость плеча модели после посадки)
# Преобразование руки набирается ОТ КРАЯ ТУЛОВИЩА, а не от его середины. У этой пони руки сидят
# низко (z 1.23, а кость плеча ванильного скелета на 1.41), и рука при посадке поднимается на
# 0.18 м: если начать подъём внутри туловища, за рукой тянутся бока груди и грива у шеи и
# вытягиваются «капюшоном» (замечено в игре 26.09.2026). От края туловища подъём плавно
# сходит на нет вдоль плеча.
ARM_RAMP_FROM = 0.17            # с какого расстояния от оси начинается преобразование (край груди)
ARM_RAMP = 0.40                 # на скольких метрах набирается преобразование
ARM_TIP = 0.9                   # доля размаха, дальше которой — кисть
HEAD_RAMP = 0.12                # на скольких метрах ниже челюсти рука берёт своё

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
_far_idx = [i for i in range(len(P)) if arm_far[i] and appendage[i] is None]
arm_y = float(np.median([P[i][1] for i in _far_idx]))
ARM_BACK = arm_y + 0.12         # дальше назад — крыло, а не рука
# Зону руки ограничиваем ПОЛОСОЙ ПО ВЫСОТЕ вокруг самой руки, а не порогом «выше пояса».
# У этой модели таз шире плеч и начинается уже на z 1.15: при драконьем «p[2] > 1.0» бёдра попадали
# в зону руки целиком и получали весь её разворот — на пояснице вырастали два плоских лоскута
# (видно в редакторе 24.09.2026).
ARM_Z = float(np.median([P[i][2] for i in _far_idx]))
ARM_BAND = 0.20                 # на столько метров вверх и вниз от руки тянется её зона
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > ARM_RAMP_FROM and p[1] < ARM_BACK
            and abs(p[2] - ARM_Z) < ARM_BAND
            and appendage[i] is None and not is_head(P[i])]
log("зона руки: высота %.2f +-%.2f, вершин %d" % (ARM_Z, ARM_BAND, len(arm_zone)))
tip = max(abs(P[i][0]) for i in arm_zone)
# Кисть — по РОДНОЙ кости модели, а не по кончикам когтей: когти у модели длинные, и по ним
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
# (пальцы уходят на |x| 0.83, тогда как у ванильного тела рука кончается на 0.60), и модель
# получал руки враскоряку. Когти пусть торчат за кость, как пальцы у человека.
H_p = bones["bip01_l_hand_19"]
# Ровно по кость рука выходит коротковатой: кисть прячется в рукав. Отпускаем её дальше вдоль
# той же оси и доворачиваем вниз — так она и длиннее, и прижата к телу, а не растопырена.
# 1.07 — по просьбе с теста 24.09.2026: ровно по кость рука выходила коротковатой, кисть
# пряталась в рукав.
# 1.07 — по просьбе с теста 24.09.2026: ровно по кость рука выходила коротковатой.
ARM_REACH = 1.07    # во сколько раз дальше кости кисти уходит запястье
ARM_DROP = 0.0      # на сколько градусов рука дополнительно опускается к телу
ARM_THICK = 1.0     # итоговая толщина поперёк оси относительно исходной: рука как у оригинала
                    # (при 1.25 она выходила толстой трубой с раструбом у копыта, 26.09.2026)

reach = (H_p - S_p) * ARM_REACH
drop = math.radians(ARM_DROP)
H_p = S_p + Vector((reach.x * math.cos(drop) + reach.z * math.sin(drop), reach.y,
                    -reach.x * math.sin(drop) + reach.z * math.cos(drop)))
turn = (H_d - S_d).rotation_difference(H_p - S_p).to_matrix()
stretch = (H_p - S_p).length / (H_d - S_d).length
along = (H_d - S_d).normalized()
log("  рука: наклон %.0f -> %.0f градусов ниже горизонта, толщина x%.2f"
    % (math.degrees(math.atan2(-(bones["bip01_l_hand_19"] - S_p).z, (bones["bip01_l_hand_19"] - S_p).x)),
       math.degrees(math.atan2(-(H_p - S_p).z, (H_p - S_p).x)), ARM_THICK))
log("  плечо модели (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f), кисть (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f)"
    % (*S_d, *S_p, *H_d, *(S_p + turn @ ((H_d - S_d) * stretch))))
for i in arm_zone:
    p = P[i]
    sign = 1.0 if p[0] > 0 else -1.0
    t = min(1.0, max(0.0, (abs(p[0]) - ARM_RAMP_FROM) / ARM_RAMP))
    t = t * t * (3 - 2 * t)
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # к голове преобразование сходит на нет
    mine = Vector((abs(p[0]), p[1], p[2]))
    # вдоль оси руку тянем/жмём совмещением, а поперёк — отдельно, иначе она худеет вместе
    # с укорочением
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * (ARM_THICK / stretch)   # stretch применится ниже ко всему
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = mdl.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука модели %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ------------------------------------------------------------------- грудная клетка пошире
# У модели узкая грудь — рядом с широким тазом смотрится трубой. Раздаём её по X, но не одним
# масштабом: иначе вместе с грудью уедут и руки, и кисти сойдут со своих костей. Внутри туловища
# ширина растёт пропорционально, снаружи сдвиг сходит на нет к запястью, а по высоте — плавно
# за пределами рёбер. Крылья и хвост двигаем вместе со всеми, чтобы корни остались на месте.
CHEST_WIDE = 1.00           # у этой пони грудь круглая и своя — не раздаём (при 1.3 плечи мялись)
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
    mdl.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- верх груди поменьше
# Раздавать надо рёбра, а не бюст: сверху грудь выпирала и вперёд, и в стороны. Ужимаем верхнюю
# часть груди по ширине и глубине вокруг её же середины — так низ (рёбра) остаётся широким, а
# верх подбирается. К плечам сходит на нет, иначе от них оторвутся руки.
UPPER_SMALL = 1.00          # во сколько раз ужимаем верх груди
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
    v = mdl.data.vertices[i]
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

for g in list(mdl.vertex_groups):     # чужие группы Mixamo больше не нужны
    mdl.vertex_groups.remove(g)
for g in ref.vertex_groups:
    mdl.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
mdl.select_set(True)
bpy.context.view_layer.objects.active = mdl
dt = mdl.modifiers.new("веса", "DATA_TRANSFER")
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

# Кости кистей — только кистям: у пони кисти висят на высоте живота, и бока корпуса модели
# оказываются к ним ближе, чем к её телу (та же беда, что была у яка).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = mdl.data.vertices[i]
    for g in list(v.groups):
        if mdl.vertex_groups[g.group].name in HAND_BONES:
            mdl.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        mdl.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# ----------------------------------------------------------- веса рук вдоль оси, а не по соседству
# Перенос весов с пони берёт ближайшую точку её сетки, а руки у неё лежат иначе: сустав приходится
# не на ту кость, и в игре при позе рука «ломается» — плечи выходят квадратными, а не круглыми
# (замечено 26.09.2026; в оригинале руки идеально круглые). У кости руки в скелете идут прямой
# цепочкой (ключица, плечо, четыре скрутки, кисть, палец), и рука модели после подгонки лежит
# вдоль неё. Поэтому вес считаем по положению вдоль руки: между двумя соседними суставами он
# плавно перетекает от одной кости к другой, как у настоящей трубки. У самого плеча плавно
# смешиваем с весами туловища, чтобы не порвать стык.
ARM_WEIGHT_FROM = 0.20      # ближе к оси — остаются веса туловища
ARM_WEIGHT_BLEND = 0.12     # на скольких метрах они сменяются весами вдоль руки


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    # Вес кости наибольший на СЕРЕДИНЕ её отрезка, а не на суставе: так устроены веса ванильного
    # тела (проверено по body_male_a: у upperarm_twist пик на x 0.25-0.29, у twist1 — 0.37-0.41,
    # у foretwist — 0.49-0.52). Если ставить пик на сустав, сгиб уезжает на полкости к плечу.
    return [(b.name, skel.matrix_world @ ((b.head_local + b.tail_local) / 2)) for b in chain]


chains = {1.0: arm_chain("l"), -1.0: arm_chain("r")}
log("цепочка руки: " + " > ".join("%s(%.2f,%.2f,%.2f)" % (n, *p) for n, p in chains[1.0]))

# Параметр «расстояние вдоль руки» — раньше это была просто |X|, но рука висит не строго по оси X,
# а под наклоном вниз (см. правку рук выше), и у одного и того же КОЛЬЦА вершин вокруг руки перёд
# и зад по кругу оказывались на разном |X|. Из-за этого половина кольца получала вес одной кости,
# половина — соседней, и при повороте плеча кольцо рвалось пополам винтом (замечено в редакторе
# 27.09.2026). Проекция на настоящую ось руки (от плеча до кисти в 3D) даёт одно и то же значение
# для всех вершин истинного поперечного среза — кольцо гнётся, а не рвётся.
AXES = {}
for sign, chain in chains.items():
    origin = chain[0][1]
    axis = (chain[-1][1] - origin)
    axis = axis / axis.length
    AXES[sign] = (origin, axis, [(name, (pos - origin).dot(axis)) for name, pos in chain])

P = coords()
_rewritten = 0
for i in arm_zone:
    sign = 1.0 if P[i][0] > 0 else -1.0
    origin, axis, chain = AXES[sign]
    # s (переход от весов туловища) — по расстоянию от оси тела, как и раньше: он про «отошли ли
    # мы от корпуса», а не про то, где именно вдоль руки мы находимся.
    s = min(1.0, max(0.0, (abs(P[i][0]) - ARM_WEIGHT_FROM) / ARM_WEIGHT_BLEND))
    if s <= 0.0:
        continue
    s = s * s * (3 - 2 * s)
    # u — проекция на истинную ось руки: решает, между какими костями вдоль неё интерполировать.
    u = (Vector(P[i]) - origin).dot(axis)
    along = {}
    if u <= chain[0][1]:
        along[chain[0][0]] = 1.0
    elif u >= chain[-1][1]:
        along[chain[-1][0]] = 1.0
    else:
        for (name_a, xa), (name_b, xb) in zip(chain[:-1], chain[1:]):
            if xa <= u < xb:
                k = (u - xa) / (xb - xa)
                k = k * k * (3 - 2 * k)
                along[name_a], along[name_b] = 1.0 - k, k
                break
    old = {mdl.vertex_groups[g.group].name: g.weight for g in mdl.data.vertices[i].groups}
    new = {}
    for name_g, w in old.items():
        new[name_g] = new.get(name_g, 0.0) + w * (1.0 - s)
    for name_g, w in along.items():
        new[name_g] = new.get(name_g, 0.0) + w * s
    for name_g in old:
        if name_g not in new:
            mdl.vertex_groups[name_g].remove([i])
    for name_g, w in new.items():
        group = mdl.vertex_groups.get(name_g) or mdl.vertex_groups.new(name=name_g)
        group.add([i], w, "REPLACE")
    _rewritten += 1
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("веса руки вдоль оси: %d вершин" % _rewritten)

# Голова жёстко на кости головы — иначе морду ведут кости шеи и груди и она рвётся на стыке.
# Граница (jaw_z/is_head) задана выше, до правки рук.
BLEND = 0.15

head_group = mdl.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(mdl.data.vertices[i].groups):
        mdl.vertex_groups[g.group].remove([i])
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
        if head_group.index in [g.group for g in mdl.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not mdl.data.vertices[i].groups:
                mdl.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in mdl.data.vertices[i].groups:
        mdl.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. разрез на части
group_names = {g.index: g.name for g in mdl.vertex_groups}
dominant = []
for v in mdl.data.vertices:
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
SIDE_LOCK_X = 0.17      # шире этого от оси — уже пряди по бокам морды, а не сама морда
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Граница гривы по глубине: доля пути от глаз к затылку. Всё дальше неё — грива и затылок,
# ближе — морда с оборкой (её в волосы брать нельзя, красилась бы цветом волос).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # перед морды
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
LEG_TOP = 0.44 * HEIGHT / 1.86
# Где начинается кисть: чуть ближе к телу, чем запястье после совмещения руки (см. раздел про
# руки). Отметку тянем вместе с ARM_REACH — иначе удлинённая рука заезжает запястьем за границу
# и в «перчатки» уходит кусок предплечья.
_shoulder_x = abs(bones["bip01_l_upperarm_twist_15"].x)
HAND_FROM = _shoulder_x + (abs(bones["bip01_l_hand_19"].x) - _shoulder_x) * ARM_REACH - 0.03
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86

# Копыта рук меньше (26.09.2026: сначала чуть-чуть, затем по просьбе ещё на 30% — 0.97 * 0.7). Сжимаем всё, что дальше
# запястья, к центру запястья: у самого запястья сжатие сходит на нет, чтобы не порвать стык.
HOOF_SCALE = 0.68       # во сколько раз меньше копыто
HOOF_BLEND = 0.05       # на скольких метрах от запястья набирается сжатие
P = coords()
for side in (1.0, -1.0):
    ring = [i for i in range(len(P)) if appendage[i] is None and P[i][0] * side > 0
            and HAND_FROM - 0.03 <= abs(P[i][0]) <= HAND_FROM + 0.01]
    if not ring:
        continue
    pivot = Vector(P[ring].mean(0))
    for i in range(len(P)):
        if appendage[i] is not None or P[i][0] * side <= 0 or abs(P[i][0]) <= HAND_FROM - 0.02:
            continue
        w = min(1.0, (abs(P[i][0]) - (HAND_FROM - 0.02)) / HOOF_BLEND)
        w = w * w * (3 - 2 * w)
        mdl.data.vertices[i].co = pivot + (Vector(P[i]) - pivot) * (1.0 - (1.0 - HOOF_SCALE) * w)
P = coords()
log("копыта рук уменьшены до %.0f%%" % (HOOF_SCALE * 100))
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# ЧЁЛКУ ДОБИРАТЬ НЕ НАДО. Пробовал ловить пряди, оставшиеся на лице, по тому, что прядь — тонкий
# лист (рядом изнанка со встречной нормалью, KD-дерево): вместе с ними в причёску уезжали чешуя
# над бровью и куски щеки, а голова усыхала со 322 вершин до 150. Пользователь: «сделай как до
# этого было, а то вообще плохо получилось с волосами». Остаются две отметки — макушка и затылок.


# «Причёска» пони — РОГ, и только он: на нём работает цвет волос из окна внешности. Грива вшита
# в голову и красится цветом окраса, уши остаются голове. Рог растёт из лба и уходит ниже
# макушки: срез по высоте отдавал ему только верхнюю половину (замечено 26.09.2026), а низ
# оставался в голове. Ищем его как конус вокруг оси рога: ось — по самой верхушке (главная ось
# ближайших к острию вершин), а от острия заливаем вниз по рёбрам, пока вершины лежат внутри
# конуса. Ушам и гриве до конуса далеко.
HORN_TIP = 0.05         # вершины не дальше этого от острия задают ось рога
HORN_R0, HORN_SLOPE = 0.015, 0.20   # радиус конуса у острия и как быстро он растёт вдоль оси
HORN_LEN = 0.27         # длина рога от острия до лба
_tip = P[int(np.argmax(P[:, 2]))]
_seed = np.flatnonzero(P[:, 2] > _tip[2] - HORN_TIP)


def _axis_of(pts):
    axis = np.linalg.svd(pts - pts.mean(0), full_matrices=False)[2][0]
    return -axis if axis[2] > 0 else axis    # вниз от острия, к основанию


_axis = _axis_of(P[_seed])


def in_horn(q):
    v = q - _tip
    s = float(v @ _axis)
    return -0.01 <= s <= HORN_LEN and float(np.linalg.norm(v - s * _axis)) <= HORN_R0 + HORN_SLOPE * s


# Ось по нескольким вершинам у острия неточна, поэтому уточняем: заливка, ось по найденному,
# и снова заливка — так конус ложится на весь рог, а не на его верхушку.
for _round in range(3):
    antler = {int(i) for i in _seed if in_horn(P[i])}
    _stack = list(antler)
    while _stack:
        _cur = _stack.pop()
        for _n in neighbours[_cur]:
            if _n not in antler and in_horn(P[_n]):
                antler.add(_n)
                _stack.append(_n)
    if len(antler) > 3:
        _axis = _axis_of(P[sorted(antler)])
_hp = P[sorted(antler)]
log("рог: %d вершин, острие (%.2f,%.2f,%.2f), ось (%.2f,%.2f,%.2f), z %.2f..%.2f"
    % (len(antler), *_tip, *_axis, _hp[:, 2].min(), _hp[:, 2].max()))


def part_of(i):
    if appendage[i]:                 # у расы с крыльями они отбираются выше, по костям
        return appendage[i]
    p = P[i]
    if i in antler:
        return "horn"
    if is_head(p):
        # Грива — отдельная причёска: затылок и верх головы (макушка и всё позади глаз). Лицо с
        # чёлкой у глаз и прядями у щёк остаётся голове.
        if p[1] > HAIR_BACK or p[2] > SKULL_TOP or abs(p[0]) > SIDE_LOCK_X:
            return "hair"
        return "head"
    b = dominant[i]
    # Кисть — ПО ПОЛОЖЕНИЮ, а не только по кости. У яка кисть короткая и мохнатая, веса с пони
    # ложатся на предплечье, и по костям в «перчатки» попадало три десятка вершин: надев
    # наручи, як остался бы без рук (меш тела подменяется доспехом).
    if abs(p[0]) > HAND_FROM:
        return "gloves"
    if b in HAND_BONES:
        return "gloves"
    if b in LEG_BONES and p[2] < LEG_TOP:
        return "legs"
    return "body"


labels = [part_of(i) for i in range(len(P))]

# Уши остаются голове: они лежат позади глаз и выше макушки, и по правилу выше попали бы в гриву
# (и красились бы цветом волос). Ухо — самая высокая точка каждой стороны, кроме рога; всё
# «гривное» в шаре вокруг него возвращаем голове.
EAR_R = 0.10            # радиус шара вокруг уха
EAR_DROP = 0.05         # на сколько центр шара ниже кончика уха
for _side in (1.0, -1.0):
    _cand = [i for i, l in enumerate(labels) if l == "hair" and P[i][0] * _side > 0.07]
    if not _cand:
        continue
    _top = max(_cand, key=lambda i: P[i][2])
    _mid = P[_top] - np.array([0.0, 0.0, EAR_DROP])
    _back = [i for i in _cand if np.linalg.norm(P[i] - _mid) < EAR_R]
    for i in _back:
        labels[i] = "head"
    log("ухо (%+.0f): кончик (%.2f,%.2f,%.2f), возвращено голове %d вершин" % (_side, *P[_top], len(_back)))

counts = {}
for name in labels:
    counts[name] = counts.get(name, 0) + 1
log("части по вершинам:", counts)

# ---------------------------------------------------------------- 4. материал и текстуры
DIFFUSE = None        # карта цвета: по ней ищутся глаза (см. eye_spots)
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
# Текстуры Meshy лежат отдельными PNG рядом с FBX; по имени файла узнаём роль и копируем под
# нашим именем — с них потом tools/make_pony_textures.py делает карты для игры.
ROLES = (("_normal", "normal"), ("_roughness", "roughness"), ("_metallic", "metallic"))
for fname in sorted(os.listdir(os.path.dirname(SRC))):
    if not fname.lower().endswith(".png"):
        continue
    low = fname.lower()
    role = next((r for key, r in ROLES if key in low), "color")
    dst = os.path.join(tex_dir, "eq_%s_%s.png" % (RACE, role))
    shutil.copyfile(os.path.join(os.path.dirname(SRC), fname), dst)
    img = bpy.data.images.load(dst)
    img.colorspace_settings.name = "sRGB" if role == "color" else "Non-Color"
    log("текстура", os.path.basename(dst), "%dx%d" % tuple(img.size))
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.label = role
    if role == "color":
        DIFFUSE = img
        if bsdf:
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    elif role == "normal" and bsdf:
        nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
        mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
        mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

# ------------------------------------------------------------------------ моргание
# Моргает движок вершинными ключами головы: их ровно 101 (key_000..key_100), и кадры 86, 87, 88 —
# левый глаз, правый и оба (так же сделано у пони, tools/convert_twilight.py). Без ключей лицо
# просто застывшее, как у яка.
#
# У пони веки — своя геометрия, спрятанная над глазом. У модели её нет: модель цельная, глаз
# просто НАРИСОВАН на текстуре. Поэтому закрываем его сжатием: вершины вокруг глаза сводим к его
# середине по высоте, и нарисованный глаз схлопывается в щёлочку. Этим же приёмом у пони
# дожимается глазное яблоко, когда движок применяет кадр не на полную силу.
#
# Глаза ищем по самой текстуре — это два симметричных тёмных пятна на морде. Пробу цвета берём
# чуть внутрь грани: развёртка у модели лоскутная, и на самом краю островка уже чернота атласа.
FACE_KEYS = 101         # столько вершинных ключей у ванильной головы
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
EYE_DARK = 0.30         # темнее этого — краска глаза, а не шерсть
EYE_CORE = 0.055        # в этом радиусе от середины глаза сжимаем полностью — это сам глаз
EYE_REACH = 0.090       # дальше сжатие спадает до нуля, чтобы не заминать щёку и надбровье
EYE_SQUASH = 0.92       # насколько сводим вершины к середине глаза
# У пони глаз крупный мультяшный с тёмным зрачком: пятно и есть середина глаза — отступать
# от него, как у грифона от зрачка, не надо.
EYE_OUT = 0.0
EYE_BACK = 0.0
# Пятно выбираем САМОЕ ТЁМНОЕ из крупных и только на морде: при выборе «ближе к середине по
# глубине» метка садилась на ухо, и она моргала ушами (замечено в игре 24.09.2026).
EYE_SIDE = 0.04         # ближе этого к оси — не глаз, а переносица
EYE_MIN = 5             # пятно мельче — шум развёртки, а не глаз
EYE_BLUE = 0.18         # разница синего и красного, с которой пиксель считается радужкой (шерсть — 0.10)
EYE_GROW = 0.09         # радужку ищем не дальше этого от зрачка
EYE_HALF = 0.0          # половина высоты глаза, её заполняет eye_spots


def eye_spots(ob):
    """Середины глаз на голове: два тёмных пятна на текстуре, по одному на сторону."""
    # Карту цвета берём ту, что ушла в Base Color при разборе материала: имена картинок в .glb
    # ничего не говорят, и подбор по имени («texture_0») промахивался — моргания не было вовсе.
    img = DIFFUSE if (DIFFUSE is not None and DIFFUSE.has_data) else None
    uvs = ob.data.uv_layers.active
    if img is None or uvs is None:
        log("ВНИМАНИЕ: не нашёл текстуру или развёртку — моргания не будет")
        return []
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    tone = np.zeros(len(P))
    blue = np.zeros(len(P))
    hits = np.zeros(len(P))
    for poly in ob.data.polygons:
        mid = np.mean([np.array(uvs.data[li].uv) for li in poly.loop_indices], axis=0)
        for li in poly.loop_indices:
            spot = np.array(uvs.data[li].uv) * 0.75 + mid * 0.25
            x = int(min(max(spot[0], 0.0), 0.999) * (w - 1))
            y = int(min(max(spot[1], 0.0), 0.999) * (h - 1))
            tone[ob.data.loops[li].vertex_index] += float(px[y, x, :3].mean())
            blue[ob.data.loops[li].vertex_index] += float(px[y, x, 2] - px[y, x, 0])
            hits[ob.data.loops[li].vertex_index] += 1
    tone /= np.maximum(hits, 1)
    blue /= np.maximum(hits, 1)

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
        spots.append((P[blob].mean(0), len(blob), float(tone[blob].mean()), blob))
    # Ищем ОДИН глаз и отражаем его: искать на каждой стороне отдельно ненадёжно — тёмных пятен
    # на голове много (тени шерсти, ноздри, косы), и глаза выходили на разной высоте.
    # Отбираем по морде: не у самой оси, в передней половине головы и выше её середины —
    # затылок с косой и подбородок отсекаются. Из оставшихся берём САМОЕ ТЁМНОЕ крупное пятно:
    # у пони темнее зрачка на голове ничего нет (ресницы тонкие и в крупное пятно не складываются).
    front = float(P[:, 1].min() + P[:, 1].max()) / 2
    upper = float(P[:, 2].min() + 0.35 * (P[:, 2].max() - P[:, 2].min()))   # глаза у пони на середине головы
    mine = [s for s in spots
            if abs(s[0][0]) > EYE_SIDE and s[0][1] < front and s[0][2] > upper and s[1] >= EYE_MIN]
    if not mine:
        return []
    best, count, shade, blob = min(mine, key=lambda s: s[2])
    # Тёмное пятно — только зрачок, он в верхней части глаза, а ниже идёт голубая радужка.
    # Сжимать надо весь глаз, иначе моргает половина (замечено в игре 26.09.2026): растим пятно
    # на соседние голубые вершины, но не дальше EYE_GROW от зрачка.
    iris = (hits > 0) & (tone < 0.80) & (blue > EYE_BLUE)
    eye = set(blob)
    stack = list(blob)
    while stack:
        cur = stack.pop()
        for other in near[cur]:
            if other not in eye and (dark[other] or iris[other]) and np.linalg.norm(P[other] - best) < EYE_GROW:
                eye.add(other)
                stack.append(other)
    ext = P[sorted(eye)]
    global EYE_HALF
    EYE_HALF = float(ext[:, 2].max() - ext[:, 2].min()) / 2
    best = np.array([ext[:, 0].mean(), ext[:, 1].mean(), (ext[:, 2].max() + ext[:, 2].min()) / 2])
    log("  глаз целиком: %d вершин (зрачок %d), высота %.3f, середина по высоте сдвинута на %+.3f"
        % (len(eye), count, 2 * EYE_HALF, best[2] - P[blob].mean(0)[2]))
    right = np.array([abs(best[0]), best[1], best[2]])
    log("  глаз найден на (%.2f,%.2f,%.2f): %d вершин, яркость %.2f; вторая сторона отражена"
        % (*right, count, shade))
    right = right + np.array([EYE_OUT, EYE_BACK, 0.0])
    return [right, np.array([-right[0], right[1], right[2]])]


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
            core = max(EYE_CORE, EYE_HALF * 1.15)      # весь глаз, с запасом на веко
            reach = core + (EYE_REACH - EYE_CORE)
            close = gap < reach
            fade = np.clip((reach - gap[close]) / max(reach - core, 1e-6), 0.0, 1.0)
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
PLUG = 0.10        # на сколько корень крыла и хвоста уходит внутрь тела (у пони спина тонкая: больше — торчит наружу)
SKULL_SMOOTH = 60   # раз расслабляем купол на месте гривы: пряди сплющиваются
SKULL_INSET = 0.012 # на сколько купол утоплен под гриву (метры)
SEPARATE_NEAR = 0.025  # головы ближе этого к гриве утапливаем вглубь (метры)
SEPARATE_PUSH = 0.010  # и на столько, у самой гривы
PLUG_MIN_X = 0.06   # ближе к оси юбка крыла не заходит
ROOT_BLEND = 0.12   # на скольких метрах от корня крыла и хвоста вес сходится от весов тела к одной кости
SMOOTH_ROUNDS = 18  # столько раз расслабляем гнездо от крыла и хвоста, чтобы спина стала гладкой
SMOOTH_GROW = 2     # на столько колец вокруг заплатки расходится заглаживание
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


from mathutils.kdtree import KDTree
body_tree = KDTree(sum(1 for l in labels if l not in ("wings", "tail")))
for _i, _l in enumerate(labels):
    if _l not in ("wings", "tail"):
        body_tree.insert(Vector(P[_i]), _i)
body_tree.balance()

parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "horn", "wings", "tail"):
    # Голова получает ЧЕРЕП на месте гривы, а не саму гриву: заплатки по рваному краю прядей
    # ложились плоскими хордами, лезли внутрь и оставляли щели (замечено в редакторе 26.09.2026).
    # Поэтому берём те же полигоны, но сглаживаем их до гладкой макушки-купола и утапливаем
    # под гриву (см. SKULL_* ниже): пряди в купол не превращаются, лишь сплющиваются.
    same = ("head", "hair") if name == "head" else (name,)
    keep = [i for i, l in enumerate(labels) if l in same]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = mdl.copy()
    ob.data = mdl.data.copy()
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
    cut = {v for v in bm.verts if any(labels[o] not in same for o in neighbours[was_index[v]])}

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
                # юбки левого и правого крыла не должны сходиться на спине в одну планку
                if name == "wings" and abs(v.co.x) < PLUG_MIN_X:
                    v.co.x = math.copysign(PLUG_MIN_X, here.x)
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
        # У головы срез с гривой рваный: в тот же контур входят свободные кончики прядей, и доля
        # «срезанных» вершин в нём мала — а закрывать его всё равно надо (под шлемом череп виден
        # изнутри пустым). Поэтому у головы порог ниже, чем у остальных частей.
        need = 0.15 if name == "head" else 0.6
        if len(ring) < 3 or sum(1 for v in ring if v in cut) < need * len(ring):
            continue                     # свободный край самой перепонки — не трогаем
        # чья это была граница: с крылом и хвостом гнездо потом заглаживаем, а шов с головой,
        # ногами и кистями трогать нельзя — там стык с соседней частью, он должен остаться
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] not in same]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # У самой причёски (рога) основание не заделываем: он остаётся открытой трубкой. А в голове
        # отверстие от рога заделываем — под шлемом рог скрыт, и дыры во лбу быть не должно;
        # крышка лежит внутри трубки рога и не мерцает с ним.
        if name in ("hair", "horn"):
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
                # Череп почти выпуклый, поэтому верную сторону заплатки видно по центру головы:
                # нормаль обязана смотреть от него. Без этого крышка на месте гривы оказывалась
                # вывернутой, и снаружи (игра не рисует изнанку) в голове зияла дыра.
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
        was_now = {v: labels[was_index[v]] for v in bm.verts if v in was_index}
        dome = [v for v, l in was_now.items() if l == "hair"]
        # рёбра между куполом и остальной головой держим на месте — иначе шов разойдётся
        movable = [v for v in dome
                   if all(was_now.get(e.other_vert(v)) == "hair" for e in v.link_edges)]
        for _ in range(SKULL_SMOOTH):
            bmesh.ops.smooth_vert(bm, verts=movable, factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.normal_update()
        for v in movable:
            v.co -= v.normal * SKULL_INSET
        log("  череп на месте гривы: %d вершин сглажено, утоплено на %.0f мм" % (len(movable), SKULL_INSET * 1000))
        # Где голова и грива всё равно сходятся вплотную (щёки у чёлки, шов купола, бока), они
        # мерцают друг сквозь друга: одинаковая глубина у двух поверхностей. Поэтому все вершины
        # головы, оказавшиеся ближе SEPARATE_NEAR к гриве, утапливаем ещё на SEPARATE_PUSH — тем
        # сильнее, чем ближе.
        from mathutils.bvhtree import BVHTree
        hair_faces = [f for f in mdl.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]   # то же правило, что при разрезе
        tree = BVHTree.FromPolygons([tuple(v.co) for v in mdl.data.vertices],
                                    [tuple(f.vertices) for f in hair_faces])
        bm.normal_update()
        pushed = 0
        for v in bm.verts:
            hit = tree.find_nearest(v.co)
            if hit[0] is None or hit[3] >= SEPARATE_NEAR:
                continue
            k = 1.0 - hit[3] / SEPARATE_NEAR
            v.co -= v.normal * (SEPARATE_PUSH * (0.4 + 0.6 * k))
            pushed += 1
        log("  голова отодвинута от гривы вглубь: %d вершин (ближе %.0f мм, до %.0f мм)"
            % (pushed, SEPARATE_NEAR * 1000, SEPARATE_PUSH * 1000))
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
        # У самого корня вес берётся у ближайшей вершины тела и плавно переходит в одну кость
        # дальше от него: иначе корень остаётся на «чужой» кости и в движении между хвостом,
        # крыльями и телом раскрываются щели (замечено в игре 26.09.2026).
        made = {}
        for v in ob.data.vertices:
            _, near_i, gap = body_tree.find(v.co)
            w = min(1.0, gap / ROOT_BLEND)
            w = w * w * (3 - 2 * w)
            for g in mdl.data.vertices[near_i].groups:
                if w < 1.0:
                    gname = mdl.vertex_groups[g.group].name
                    if gname not in made:
                        made[gname] = ob.vertex_groups.new(name=gname)
                    made[gname].add([v.index], g.weight * (1.0 - w), "ADD")
            if w > 0.0:
                if anchor not in made:
                    made[anchor] = ob.vertex_groups.new(name=anchor)
                made[anchor].add([v.index], w, "ADD")
    if name in ("hair", "horn"):    # причёска и рог целиком на голове
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
# Цельная посаженная модель остаётся в .blend скрытой (в FBX она не попадает — экспорт по выделению):
# по ней вручную режут части, см. tools/make_pony_edit_scene.py.
mdl.name = mdl.data.name = "eq_pony_FULL"
mdl.parent = skel
mdl.matrix_parent_inverse = skel.matrix_world.inverted()
mdl.modifiers.new("Armature", "ARMATURE").object = skel
mdl.data.materials.clear()
mdl.data.materials.append(mat)
mdl.hide_render = mdl.hide_viewport = True

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
# Ванильный человек НА МЕСТЕ модели: по нему видно, что вылезает из доспеха и насколько
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
# каждой части модели свой цвет — так видно, где прошёл разрез
PART_COLOUR = {"body": (0.80, 0.75, 0.65, 1), "legs": (0.35, 0.55, 0.85, 1),
               "gloves": (0.95, 0.80, 0.25, 1), "head": (0.35, 0.80, 0.45, 1),
               "hair": (0.90, 0.35, 0.75, 1), "horn": (0.95, 0.90, 0.30, 1), "wings": (0.55, 0.40, 0.85, 1),
               "tail": (0.95, 0.45, 0.30, 1)}
for name, ob in parts.items():
    ob.color = PART_COLOUR.get(name, (1, 1, 1, 1))
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
# Кадр «рост» — рядом с пони для сравнения, остальные без неё: иначе она заслоняет модели
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
         ("body", "legs", "gloves", "head", "hair", "horn")),
        # одна голова — так её показывает модкит: видно, не осталось ли на лице прядей гривы
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "horn", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "horn", "wings", "tail")),
        # поверх ванильного человека: красным то, что вылезает за силуэт, под который сшита броня
        ("поверх человека", (0, -6, 1.05), FRONT, 2.6, "поверх", ("wings", "tail")),
        ("поверх человека сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, "поверх",
         ("wings", "tail"))):
    for ob in pony.values():
        ob.hide_render = with_pony is not True
    for ob in overlay:
        ob.hide_render = with_pony != "поверх"
    for name, ob in parts.items():
        ob.hide_render = name in hide or (name == "horn" and "hair" in hide)
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)
log("превью в", prev)

# Те же ракурсы с настоящей текстурой: видно, как легли швы, глаза и грива
scene.display.shading.color_type = "TEXTURE"
for ob in parts.values():
    ob.hide_render = False
for ob in overlay:
    ob.hide_render = True
for ob in pony.values():
    ob.hide_render = True
for view, loc, rot, span, z in (
        ("текстура front", (0, -6, 1.05), FRONT, 2.6, 1.05),
        ("текстура side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, 1.05),
        ("текстура back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, 1.05),
        ("текстура голова", (0, -6, 1.75), FRONT, 0.75, 1.75)):
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)

# Моргание: оба глаза закрыты (ключ 88) — видно, закрывается ли глаз целиком
head = parts.get("head")
if head is not None and head.data.shape_keys:
    key = head.data.shape_keys.key_blocks.get("key_088")
    for view, value in (("моргание открыты", 0.0), ("моргание закрыты", 1.0)):
        if key:
            key.value = value
        cam.location = (0, -6, 1.66)
        cam.rotation_euler = FRONT
        cam.data.ortho_scale = 0.45
        scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
        bpy.ops.render.render(write_still=True)
    if key:
        key.value = 0.0

# Поза: корпус наклонён и скручен — в покое швы сходятся, а в движении расходились
scene.display.shading.color_type = "OBJECT"
for ob in parts.values():
    ob.hide_render = False


def bend(bone, axis, deg):
    pb = skel.pose.bones[bone]
    pivot = pb.head.copy()
    turn = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-pivot)
    pb.matrix = turn @ pb.matrix
    bpy.context.view_layer.update()


bend(PELVIS, "Y", 14)
bend("bip01_spine_9", "X", 12)
bend("bip01_spine1_10", "X", 12)
for view, loc, rot in (("поза сзади", (0, 6, 1.05), (math.pi / 2, 0, math.pi)),
                       ("поза сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2))):
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = 2.6
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)
