# -*- coding: utf-8 -*-
"""Як из готовой антро-модели (А-поза, без скелета) — на скелет пони, по частям, в FBX.

Запуск (headless Blender, открывает готовую пони — в ней скелет и образец привязки):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_yak.py -- <як.glb> <папка вывода>

Чем отличается от прежних попыток (tools/convert_*.py): модель уже стоит на двух ногах в А-позе,
разворачивать ничего не надо. Остаётся привязать её к человеческому скелету Bannerlord и разрезать
на предметы так же, как разрезана пони:
  eq_yak_body   — туловище и руки (body_meta_mesh)
  eq_yak_legs   — ноги (legs_mesh)
  eq_yak_gloves — кисти (hands_mesh)
  eq_yak_head   — голова с рогами и гривой (face_meta_mesh; ключей мимики нет — лицо жёсткое)
  eq_yak_tail   — хвост (предмет в слот плаща, как хвост пони, целиком на кости таза)

Как делается:
  1. Модель ставится копытами на пол, мордой в -Y (как пони) и масштабируется до роста HEIGHT.
  2. Веса костей переносятся с пони: с ближайшей точки её поверхности (тело+ноги+кисти+голова,
     сшитые в одну), поэтому як гнётся там же, где пони. Автопривязка по теплу для такой сетки
     (пластины шерсти, несшитые куски) не годится.
  3. Разрез на предметы — по главной кости каждой вершины: голова и шея → голова, кисти → перчатки,
     бедро-голень-стопа → ноги, хвост — по положению (за спиной, на высоте таза), остальное — тело.
  4. Материал eq_yak_body с запечёнными текстурами модели; сами текстуры пишутся в <вывод>/textures.
     В редакторе материал надо создать заново на этих текстурах (материал из FBX идёт без скиннинга).
Дальше — импорт FBX в Modding Kit руками, затем в tools/make_pony_race.py убрать "yak" из NOT_IMPORTED.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "yak"
HEIGHT = 2.05          # рост яка в метрах (пони 1.86): яки крупнее пони
MAT = "eq_yak_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"


def log(*a):
    print("[yak]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}

# ---------------------------------------------------------------- 1. импорт и посадка
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=SRC)
new = [o for o in bpy.data.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
for o in new:
    if o.type != "MESH":
        bpy.data.objects.remove(o)
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
yak = bpy.context.view_layer.objects.active
yak.name = yak.data.name = "eq_yak_all"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# Генератор отдаёт «суп»: соседние треугольники не делят вершины (тысячи островов). Сшиваем —
# иначе не найти связные куски (пряди гривы), а по швам при деформации могут разойтись щели.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(yak.data.vertices))


def coords():
    return np.array([v.co[:] for v in yak.data.vertices])


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: %d вершин, размер %.2f x %.2f x %.2f" % (len(P), *(hi - lo)))
# Морда должна смотреть в -Y. Морда — самая выступающая по Y точка верхней трети модели.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
nose_y = top[np.argmax(np.abs(top[:, 1] - (lo[1] + hi[1]) / 2)), 1]
if nose_y > (lo[1] + hi[1]) / 2:
    log("морда смотрела в +Y — разворачиваю")
    yak.rotation_euler.z = math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
scale = HEIGHT / (hi[2] - lo[2])
yak.scale = (scale,) * 3
yak.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
# Наклон вперёд. В игре анимации прогибают позвоночник назад, и массивное туловище яка с горбом
# на спине выглядит откинутым; компенсируем в самой модели: всё, что выше таза, поворачивается
# вперёд вокруг оси X через таз, угол набирается плавно от таза до груди (LEAN_TO), выше — полный.
LEAN_FORWARD = math.radians(12.0)
LEAN_FROM, LEAN_TO = bones[PELVIS].z * HEIGHT / 1.86, 1.35
if LEAN_FORWARD:
    for v in yak.data.vertices:
        if v.co.z <= LEAN_FROM:
            continue
        t = min(1.0, (v.co.z - LEAN_FROM) / (LEAN_TO - LEAN_FROM))
        a = LEAN_FORWARD * t
        y, z = v.co.y, v.co.z - LEAN_FROM
        v.co.y = y * math.cos(a) - z * math.sin(a)
        v.co.z = y * math.sin(a) + z * math.cos(a) + LEAN_FROM
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("наклон вперёд %.0f°: верх груди сместился на %.2f м вперёд" % (math.degrees(LEAN_FORWARD),
                                                                       (1.35 - LEAN_FROM) * math.sin(LEAN_FORWARD)))
# Руки вперёд. У модели руки отведены назад: кисти на y≈+0.20, а кости рук у пони идут по y≈0.03
# (вперёд — это -Y). Привязка сохраняет это смещение в любой позе, и в игре руки торчат за
# спиной. Сдвигаем руки вперёд поступательно: полностью от ARM_X1, плавно от ARM_X0 (плечо).
# Два движения, ни одно не рвёт сетку:
#   1) плечи вперёд — поступательно, но широкой зоной от самой оси (0 -> SHOULDER_X): бок корпуса
#      уезжает вместе с плечом, и «косынки» у основания руки не образуется;
#   2) рука поворачивается вокруг вертикали через плечевой сустав на ARM_SWING вперёд — форма руки
#      остаётся, кисть выходит к середине корпуса.
SHOULDER_X = 0.42          # плечевой сустав яка (у пони 0.19)
SHOULDER_FORWARD = 0.12    # на сколько подать плечи вперёд
ARM_SWING = math.radians(25.0)
ARM_OUT = 0.05             # чуть наружу, тоже широкой зоной
root = P[(np.abs(P[:, 0]) > SHOULDER_X - 0.05) & (np.abs(P[:, 0]) < SHOULDER_X + 0.05) & (P[:, 2] > 1.0)]
pivot_y, pivot_z = float(root[:, 1].mean()), float(root[:, 2].mean())
for v in yak.data.vertices:
    if v.co.z < 0.85:
        continue
    ax = abs(v.co.x)
    sign = 1 if v.co.x > 0 else -1
    t = min(1.0, ax / SHOULDER_X)
    v.co.y -= SHOULDER_FORWARD * t
    v.co.x += ARM_OUT * t * sign
    if ax > SHOULDER_X - 0.08:
        # поворот вокруг вертикали через (±SHOULDER_X, pivot_y): вперёд — это в -Y
        k = min(1.0, (ax - (SHOULDER_X - 0.08)) / 0.16)   # плавный вход в поворот у сустава
        a = ARM_SWING * k
        dx, dy = ax - SHOULDER_X, v.co.y - (pivot_y - SHOULDER_FORWARD)
        rx = dx * math.cos(a) + dy * math.sin(a)
        ry = -dx * math.sin(a) + dy * math.cos(a)
        v.co.x = (SHOULDER_X + rx) * sign
        v.co.y = (pivot_y - SHOULDER_FORWARD) + ry
P = coords()
lo, hi = P.min(0), P.max(0)
hands = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("руки: плечи вперёд на %.2f м, поворот %.0f°, кисти теперь на y=%.2f (кость %.2f), x=%.2f"
    % (SHOULDER_FORWARD, math.degrees(ARM_SWING), hands[:, 1].mean(), bones["bip01_l_hand_19"].y, hands[:, 0].mean()))
# Где у яка кисти: самые дальние по X точки (у пони кисть на высоте 1.11, x 0.65)
hand = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони 1.11), таз пони на %.2f"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand[:, 2].mean(), bones[PELVIS].z))

# ---------------------------------------------------------------- 2. веса с пони
ref_parts = []
for name in ("eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves", "eq_twilight_head"):
    src = pony[name]
    ob = src.copy()
    ob.data = src.data.copy()
    if ob.data.shape_keys:   # ключи мешают объединению; базовая форма уже стоит
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

for g in ref.vertex_groups:
    if g.name not in yak.vertex_groups:
        yak.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
yak.select_set(True)
bpy.context.view_layer.objects.active = yak
dt = yak.modifiers.new("веса", "DATA_TRANSFER")
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

# Кости кистей и предплечий — только руке. У пони в А-позе кисти висят на высоте живота, и бока
# широкого торса яка оказались ближе к её кистям, чем к её телу: перенос дал им веса кистей,
# в предпросмотре перчаток появилось «кольцо» из живота, а в игре живот дёргался бы за руками.
P = coords()
HAND_MIN_X, FOREARM_MIN_X = 0.62, 0.45
stripped = 0
for i, p in enumerate(P):
    ax = abs(p[0])
    if ax >= HAND_MIN_X:
        continue
    v = yak.data.vertices[i]
    for g in list(v.groups):
        name = yak.vertex_groups[g.group].name
        if name in HAND_BONES or (ax < FOREARM_MIN_X and "foretwist" in name):
            yak.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:   # держалась только на кистях — отдаём позвоночнику
        yak.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей и предплечий с корпуса: %d" % stripped)

# Голова — жёстко на кости головы. Морда яка сидит низко и далеко впереди того места, где голова
# у пони, и перенос весов даёт ей кости шеи и груди: верх и низ морды вели разные кости, и она
# рвалась на стыке. Граница головы — линия челюсти: над шеей (NECK_Z), а впереди опускается
# вслед за мордой (JAW_SLOPE м вниз на метр вперёд).
# Скелет не масштабируется вместе с моделью: кость шеи стоит на 1.47 м при любом росте яка,
# а самое узкое место его шеи — на 1.56 м; режем между ними.
NECK_Z = bones["bip01_neck_12"].z + 0.03
JAW_SLOPE, JAW_FROM = 0.55, -0.15


def is_head(p):
    front = max(0.0, -p[1] + JAW_FROM)   # насколько точка впереди линии шеи
    return p[2] > NECK_Z - JAW_SLOPE * front


P = coords()
head_idx = [i for i in range(len(P)) if is_head(P[i])]
head_group = yak.vertex_groups["bip01_head_13"]
for g in yak.vertex_groups:
    if g.name != "bip01_head_13":
        g.remove(head_idx)
head_group.add(head_idx, 1.0, "REPLACE")
# Под линией челюсти — плавная зона: тело сразу под головой ведут кости шеи и груди, и без
# перехода кожа на стыке (пряди гривы, горло) растягивается между жёсткой головой и шеей.
BLEND = 0.15
blended = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p):
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]      # насколько ниже линии челюсти
    if d >= BLEND:
        continue
    w = 1.0 - d / BLEND
    v = yak.data.vertices[i]
    for g in v.groups:
        yak.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
log("голова жёстко на кости головы: %d вершин, плавная зона под челюстью: %d" % (len(head_idx), blended))

# ---------------------------------------------------------------- 3. разрез на предметы
group_names = {g.index: g.name for g in yak.vertex_groups}
dominant = []
for v in yak.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
back = P[(np.abs(P[:, 0]) < 0.08) & (np.abs(P[:, 2] - bones[PELVIS].z * HEIGHT / 1.86) < 0.15), 1].max()
tail_z = bones[PELVIS].z * HEIGHT / 1.86


LEG_TOP = 0.44 * HEIGHT / 1.86   # у пони «ноги» — это голени и копыта (до 0.44 м), бёдра в теле
# Голова режется по той же линии челюсти, что и веса (is_head выше): голова и её кость — вместе.

# острова сетки (связные куски)
parent = list(range(len(P)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


for e in yak.data.edges:
    a, b = find(e.vertices[0]), find(e.vertices[1])
    if a != b:
        parent[a] = b
island = [find(i) for i in range(len(P))]
island_top = {}
island_size = {}
for i, isl in enumerate(island):
    island_top[isl] = max(island_top.get(isl, -9.0), P[i][2])
    island_size[isl] = island_size.get(isl, 0) + 1
main_island = max(island_size, key=island_size.get)
log("островов в сетке: %d, главный — %d вершин" % (len(island_size), island_size[main_island]))


def part_of(i):
    p = P[i]
    if p[1] > back + 0.05 and abs(p[2] - tail_z) < 0.45 and abs(p[0]) < 0.25:
        return "tail"
    if is_head(p):        # та же линия челюсти, что и у весов: голова и её кость режутся вместе
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

# материал с запечёнными текстурами
src_mat = yak.data.materials[0] if yak.data.materials else None
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
if src_mat and src_mat.use_nodes:
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    for node in src_mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            img = node.image
            fname = "eq_yak_" + img.name.replace(".", "_") + ".png"
            img.filepath_raw = os.path.join(tex_dir, fname)
            img.file_format = "PNG"
            img.save()
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.label = img.name
            if bsdf and "normal" in img.name.lower():
                nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
                mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif bsdf and "metal" not in img.name.lower():
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            log("текстура", fname, "%dx%d" % tuple(img.size))

parts = {}
for name in ("body", "legs", "gloves", "head", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = yak.copy()
    ob.data = yak.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    keep_set = set(keep)
    # грань остаётся в части, если в ней большинство вершин этой части
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if name == "tail":   # хвост — целиком на тазу, как хвост пони
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name=PELVIS).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    parts[name] = ob
    log("%s: %d вершин, %d граней" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
bpy.data.objects.remove(yak)

# ---------------------------------------------------------------- 4. экспорт
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts.values()]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
path = os.path.join(OUT, "eq_%s.fbx" % RACE)
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспорт", path)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "eq_%s.blend" % RACE))

# ---------------------------------------------------------------- 5. превью: як рядом с пони
prev = os.path.join(OUT, "preview")
os.makedirs(prev, exist_ok=True)
scene = bpy.context.scene
for ob in pony.values():
    ob.hide_render = ob.name in ("eq_twilight_mane", "eq_twilight_tail") or False
    ob.location.x -= 1.4   # пони сдвигается влево — для сравнения роста
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 3.2
scene.collection.objects.link(cam)
scene.camera = cam
for view, loc, rot in (("front", (-0.7, -6, 1.05), (math.pi / 2, 0, 0)),
                       ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2))):
    cam.location = loc
    cam.rotation_euler = rot
    scene.render.filepath = os.path.join(prev, "yak_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
