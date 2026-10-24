# Переделка чужой четвероногой модели в антро-персонажа Bannerlord.
#
#   blender --background --factory-startup --python convert_creature.py -- <вид> <модель.glb>
#           <скелет.fbx> <папка вывода> [--preview]
#
# <вид> — ключ из tools/creature_data.py (griffon, yak); там же записаны координаты суставов,
# снятые руками по видам модели с координатной сеткой (tools/preview_model.py). <скелет.fbx> —
# любой наш экспорт с человеческим скелетом Bannerlord (assets/twilight_anthro/export/eq_twilight.fbx).
#
# Порядок работы:
#   1. Модель разворачивается мордой в -Y и сшивается: генератор отдаёт «суп» из несвязанных
#      треугольников, а такую сетку рвёт любая деформация.
#   2. Тонкие части (крылья, хвост) отделяются сразу — их нельзя пересобирать по объёму, перья
#      слипнутся в пластины. Они поедут отдельными предметами, целиком на одной кости.
#   3. Туловище пересобирается по объёму (voxel remesh): получается одна замкнутая оболочка без
#      внутреннего мусора. Развёртка переносится со старой модели, чтобы текстура осталась.
#   4. Всё масштабируется так, чтобы позвоночник зверя стал человеческого размера.
#   5. По анатомической карте строится «звериный» скелет — копия человеческого, у которой кости
#      переставлены в суставы зверя. Меш привязывается к нему: каждая область тела только к своим
#      костям (живот не цепляется за лапу), веса сглаживаются по соседям.
#   6. Звериному скелету задаётся поза человеческого: корпус встаёт вертикально, передние лапы
#      разводятся руками, задние выпрямляются. Поза запекается в геометрию.
#   7. Веса считаются заново по человеческому скелету и ограничиваются тремя костями на вершину.
#   8. Меш режется на предметы (голова, тело, ноги, кисти) и пишется в FBX, текстуры — в PNG.
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_data import BONES, CHAINS, CREATURES  # noqa: E402

_args = [a for a in sys.argv[sys.argv.index("--") + 1:]]
PREVIEW = "--preview" in _args
NO_SCALE = "--no-scale" in _args
_args = [a for a in _args if not a.startswith("--")]
KEY, GLB, SKEL_FBX, OUT = _args[:4]
CARD = CREATURES[KEY]
PREFIX = "eq_" + CARD["name"]
os.makedirs(OUT, exist_ok=True)
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

MAX_INFLUENCES = 3      # как у ванильных мешей Bannerlord
MIN_WEIGHT = 0.02
# Кости, длину которых при переносе позы не меняем: голова, кисти и стопы должны остаться
# своего размера, иначе клюв вытягивается вверх, а когти — в стороны.
NO_STRETCH = {"head", "l_hand", "r_hand", "l_foot", "r_foot", "l_toe", "r_toe"}
# какие кости обслуживают какую область тела
REGION_BONES = {
    "arms": ["l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_hand_end",
             "r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_hand_end"],
    "legs": ["l_thigh", "l_calf", "l_foot", "l_toe", "l_toe_end",
             "r_thigh", "r_calf", "r_foot", "r_toe", "r_toe_end"],
    "head": ["neck", "head", "head_end"],
    "torso": ["pelvis", "spine", "spine1", "spine2", "l_clavicle", "r_clavicle", "neck"],
}
# Области в уже человеческой позе — по ним считаются окончательные веса.
HUMAN_REGIONS = {
    "arms": {"min_abs_x": 0.22},
    "head": {"min_z": 1.46},
    "legs": {"max_z": 0.90},
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
vl = bpy.context.view_layer


def log(*a):
    print("[creature]", *a, flush=True)


def select_only(objs, active):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def match(q, rule):
    """Подходит ли точка (в координатах анатомической карты) под правило области."""
    for cond, value in rule.items():
        if cond == "min_z" and q.z < value:
            return False
        if cond == "max_z" and q.z > value:
            return False
        if cond == "min_y" and q.y < value:
            return False
        if cond == "max_y" and q.y > value:
            return False
        if cond == "min_x" and q.x < value:
            return False
        if cond == "max_x" and q.x > value:
            return False
        if cond == "min_abs_x" and abs(q.x) < value:
            return False
    return True


def separate(ob, indices, name):
    """Отделяет вершины в новый объект (и возвращает его)."""
    if not indices:
        return None
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    chosen = set(indices)
    for i in indices:
        ob.data.vertices[i].select = True
    # грань уезжает вместе с вершинами только если выбрана целиком — отмечаем такие грани сами,
    # иначе в новом объекте остаётся облако точек без единой грани
    for f in ob.data.polygons:
        f.select = all(i in chosen for i in f.vertices)
    was = set(scene.objects)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    fresh = [o for o in scene.objects if o not in was]
    if not fresh:
        return None
    fresh[0].name = name
    return fresh[0]


# ---------------------------------------------------------------- 1. скелет Bannerlord
before = set(scene.objects)
bpy.ops.import_scene.fbx(filepath=SKEL_FBX, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
imported = [o for o in scene.objects if o not in before]
skel = next(o for o in imported if o.type == "ARMATURE")
for o in imported:
    if o is not skel:
        bpy.data.objects.remove(o, do_unlink=True)
# В файле скелет записан в масштабе 0.01; поворот оставляем как есть (он и переводит кости
# в привычные оси Z-вверх), меняем только масштаб — работаем в метрах.
skel.scale = (1, 1, 1)
vl.update()
log("скелет: %d костей" % len(skel.data.bones))

missing = [k for k in CARD["joints"] if BONES[k] not in skel.data.bones]
if missing:
    raise SystemExit("в скелете нет костей для суставов: %s" % ", ".join(missing))

H_PELVIS = skel.matrix_world @ skel.data.bones[BONES["pelvis"]].head_local
H_NECK = skel.matrix_world @ skel.data.bones[BONES["neck"]].head_local

# ---------------------------------------------------------------- 2. модель
images_before = set(bpy.data.images.keys())
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLB)
new = [o for o in scene.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
for o in new:
    if o.type != "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
select_only(meshes, meshes[0])
if len(meshes) > 1:
    bpy.ops.object.join()
mesh = vl.objects.active
mesh.name = PREFIX
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
log("модель: %d вершин, %d треугольников" % (len(mesh.data.vertices), tri_count(mesh)))

# поворот мордой в -Y
turn = Matrix.Rotation(math.radians(CARD["yaw"]), 4, "Z")
mesh.matrix_world = turn @ mesh.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
J = {k: turn @ Vector(v) for k, v in CARD["joints"].items()}

# сшивка: у модели от генератора соседние треугольники не делят вершины
select_only([mesh], mesh)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0008)
bpy.ops.object.mode_set(mode="OBJECT")
log("после сшивки: %d вершин, %d треугольников" % (len(mesh.data.vertices), tri_count(mesh)))

# крылья и хвост отделяем до пересборки: тонкие перья voxel remesh слепит в пластины
to_card = turn.inverted()
extras = {}
for name, rule in CARD.get("extras", {}).items():
    idx = [v.index for v in mesh.data.vertices if match(to_card @ (mesh.matrix_world @ v.co), rule)]
    part = separate(mesh, idx, "%s_%s" % (PREFIX, name))
    if part:
        extras[name] = part
        log("отделено: %s, %d вершин" % (part.name, len(part.data.vertices)))

# Пересборка туловища по объёму: одна замкнутая оболочка вместо супа из оболочек.
source = mesh.copy()
source.data = mesh.data.copy()
scene.collection.objects.link(source)
source.name = PREFIX + "_source"
select_only([mesh], mesh)
mesh.data.remesh_voxel_size = CARD.get("voxel", 0.012)
mesh.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
log("туловище пересобрано (шаг %.3f м): %d вершин, %d треугольников"
    % (mesh.data.remesh_voxel_size, len(mesh.data.vertices), tri_count(mesh)))

target = CARD["target_tris"]
if tri_count(mesh) > target * 1.2:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = min(1.0, target / tri_count(mesh))
    bpy.ops.object.modifier_apply(modifier=dec.name)
    log("упрощено до %d треугольников" % tri_count(mesh))

# развёртка и материал — со старой модели
if not mesh.data.uv_layers:
    mesh.data.uv_layers.new(name="UVMap")
mesh.data.materials.clear()
for m in source.data.materials:
    mesh.data.materials.append(m)
dt = mesh.modifiers.new("uv", "DATA_TRANSFER")
dt.object = source
dt.use_loop_data = True
dt.data_types_loops = {"UV"}
dt.loop_mapping = "POLYINTERP_NEAREST"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.data.objects.remove(source, do_unlink=True)
log("развёртка перенесена со старой модели")

# тонкие части упрощаем обычной децимацией
for part in extras.values():
    if tri_count(part) > 4000:
        select_only([part], part)
        dec = part.modifiers.new("dec", "DECIMATE")
        dec.ratio = 4000 / tri_count(part)
        bpy.ops.object.modifier_apply(modifier=dec.name)

# масштаб: позвоночник зверя = позвоночник человека, таз в таз
spine_len = (J["neck"] - J["pelvis"]).length
k = (H_NECK - H_PELVIS).length / spine_len
fit = Matrix.Translation(H_PELVIS) @ Matrix.Scale(k, 4) @ Matrix.Translation(-J["pelvis"])
log("масштаб модели x%.3f (позвоночник %.3f -> %.3f м)" % (k, spine_len, (H_NECK - H_PELVIS).length))
for ob in [mesh] + list(extras.values()):
    select_only([ob], ob)
    ob.matrix_world = fit @ ob.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
J = {key: fit @ v for key, v in J.items()}
to_card = turn.inverted() @ fit.inverted()

# ---------------------------------------------------------------- 3. звериный скелет
qrig = skel.copy()
qrig.data = skel.data.copy()
qrig.name = "creature_rig"
scene.collection.objects.link(qrig)
select_only([qrig], qrig)
to_rig = qrig.matrix_world.inverted()
bpy.ops.object.mode_set(mode="EDIT")
eb = qrig.data.edit_bones
mapped = set()
for chain in CHAINS:
    for a, b in zip(chain, chain[1:]):
        if a not in J or b not in J:
            continue
        bone = eb[BONES[a]]
        bone.head = to_rig @ J[a]
        bone.tail = to_rig @ J[b]
        mapped.add(BONES[a])
# Скрутка (roll) каждой кости — по одноимённой кости человека. Если оставить произвольную,
# при переносе позы каждая кость доворачивается на свой угол вокруг себя, соседние вершины
# закручиваются в разные стороны, и меш рассыпается на лоскуты.
for name in mapped:
    z_human = skel.data.bones[name].matrix_local.to_3x3() @ Vector((0.0, 0.0, 1.0))
    eb[name].align_roll(z_human)
bpy.ops.object.mode_set(mode="OBJECT")
for b in qrig.data.bones:
    b.use_deform = b.name in mapped
log("звериный скелет: %d костей участвуют в деформации" % len(mapped))

qbones = [(b.name, qrig.matrix_world @ b.head_local, qrig.matrix_world @ b.tail_local)
          for b in qrig.data.bones if b.use_deform]


# ---------------------------------------------------------------- 4. привязка
def smooth_weights(ob, rounds=6, factor=0.5):
    """Сглаживание весов по соседям: иначе на границах областей остаётся резкий шов и при
    повороте костей меш рвёт на лоскуты."""
    me = ob.data
    n = len(me.vertices)
    neigh = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        neigh[a].append(b)
        neigh[b].append(a)
    groups = list(ob.vertex_groups)
    if not groups:
        return
    col = {g.index: i for i, g in enumerate(groups)}
    W = np.zeros((n, len(groups)), np.float32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, col[g.group]] = g.weight
    for _ in range(rounds):
        nxt = W.copy()
        for i in range(n):
            if neigh[i]:
                nxt[i] = W[i] * (1.0 - factor) + W[neigh[i]].mean(0) * factor
        W = nxt
    W /= np.maximum(W.sum(1, keepdims=True), 1e-6)
    for gi, g in enumerate(groups):
        g.remove(list(range(n)))
        for i in np.nonzero(W[:, gi] > 0.003)[0]:
            g.add([int(i)], float(W[i, gi]), "REPLACE")


def weight_by_bones(ob, bones, regions, to_space, count=2, power=2.0):
    """Привязка по расстоянию до костей, но только к костям своей области тела."""
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    names = {name for name, _a, _b in bones}
    groups = {name: ob.vertex_groups.new(name=name) for name in names}
    allowed = {region: {BONES[k] for k in keys if BONES[k] in names}
               for region, keys in REGION_BONES.items()}
    mw = ob.matrix_world
    for v in ob.data.vertices:
        p = mw @ v.co
        q = to_space @ p
        region = next((name for name, rule in regions.items() if match(q, rule)), "torso")
        pool = allowed.get(region) or names
        dists = []
        for name, a, b in bones:
            if name not in pool:
                continue
            ab = b - a
            t = min(max((p - a).dot(ab) / ab.length_squared, 0.0), 1.0)
            dists.append(((a + ab * t - p).length, name))
        dists.sort()
        near = dists[:count] or [(1.0, BONES["pelvis"])]
        weights = [(name, 1.0 / max(d, 1e-4) ** power) for d, name in near]
        total = sum(w for _n, w in weights)
        for name, w in weights:
            groups[name].add([v.index], w / total, "REPLACE")


def weight_rigid(ob, bone_name):
    """Вся деталь на одной кости — так ездят крылья и хвост."""
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    vg = ob.vertex_groups.new(name=bone_name)
    vg.add([v.index for v in ob.data.vertices], 1.0, "REPLACE")


# По кости на вершину: кожа зверя делится на жёсткие куски. Мягкая привязка тут не работает —
# при выпрямлении четвероногого соседние куски кожи расходятся на десятки сантиметров, и меш
# превращается в лохмотья.
weight_by_bones(mesh, qbones, CARD.get("regions", {}), to_card, count=1)
rigid = CARD.get("rigid", {})
for name, part in extras.items():
    weight_rigid(part, BONES[rigid.get(name, "spine1")])
log("привязка: туловище по областям%s" % (", жёстко: " + ", ".join(extras) if extras else ""))

for ob in [mesh] + list(extras.values()):
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = qrig

if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_prepose.blend"))

# ---------------------------------------------------------------- 5. поза человека
# ---------------------------------------------------------------- 5. поза человека
# Перенос позы «по кускам». Мягкая привязка тут не работает: при выпрямлении четвероногого
# соседние участки кожи разъезжаются на десятки сантиметров, и меш превращается в лохмотья.
# Поэтому шкура режется на куски по костям, каждый кусок переносится целиком (поворот, сдвиг
# и растяжение вдоль кости), грани между разными кусками удаляются, а потом всё сплавляется
# в одну оболочку пересборкой по объёму — швы на суставах затягиваются.
bone_index = {}
names = {g.index: g.name for g in mesh.vertex_groups}
for v in mesh.data.vertices:
    best, bw = None, -1.0
    for g in v.groups:
        if g.weight > bw:
            best, bw = names[g.group], g.weight
    bone_index[v.index] = best

moves = {}
for bone in qrig.data.bones:
    if not bone.use_deform:
        continue
    target = skel.data.bones[bone.name]
    k = target.length / bone.length if bone.length > 1e-6 else 1.0
    if NO_SCALE or next((key for key, n in BONES.items() if n == bone.name), "") in NO_STRETCH:
        k = 1.0
    k = min(max(k, 0.6), 2.2)
    rest = qrig.matrix_world @ bone.matrix_local
    want = skel.matrix_world @ target.matrix_local @ Matrix.Scale(k, 4, Vector((0, 1, 0)))
    moves[bone.name] = want @ rest.inverted()

mw = mesh.matrix_world.copy()
inv = mw.inverted()
for v in mesh.data.vertices:
    move = moves.get(bone_index.get(v.index))
    if move is not None:
        v.co = inv @ (move @ (mw @ v.co))

# грани, натянутые между разными костями, выбрасываем — иначе при сплавлении из них
# получаются перепонки поперёк тела
select_only([mesh], mesh)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bpy.ops.object.mode_set(mode="OBJECT")
cut = 0
for f in mesh.data.polygons:
    if len({bone_index.get(i) for i in f.vertices}) > 1:
        f.select = True
        cut += 1
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.delete(type="FACE")
bpy.ops.object.mode_set(mode="OBJECT")
log("куски переставлены, выброшено граней между кусками: %d" % cut)

bpy.data.objects.remove(qrig, do_unlink=True)

# Второй проход пересборки. При выпрямлении зверя кожа между животом и лапой растягивается —
# там, где у четвероногого был плавный переход, у стоящего получается разрыв в четверть метра.
# Пересобираем оболочку ещё раз, уже в человеческой позе: остаётся чистая поверхность без
# растянутых граней и самопересечений. Развёртку снова берём с предыдущего состояния.
SKIP2 = False
posed_source = mesh.copy()
posed_source.data = mesh.data.copy()
scene.collection.objects.link(posed_source)
posed_source.name = PREFIX + "_posed_source"
select_only([mesh], mesh)
mesh.data.remesh_voxel_size = CARD.get("voxel", 0.012)
mesh.data.remesh_voxel_adaptivity = 0.0
if not SKIP2:
    bpy.ops.object.voxel_remesh()
if not SKIP2 and tri_count(mesh) > CARD["target_tris"] * 1.2:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = min(1.0, CARD["target_tris"] / tri_count(mesh))
    bpy.ops.object.modifier_apply(modifier=dec.name)
if not mesh.data.uv_layers:
    mesh.data.uv_layers.new(name="UVMap")
mesh.data.materials.clear()
for m in posed_source.data.materials:
    mesh.data.materials.append(m)
dt = mesh.modifiers.new("uv", "DATA_TRANSFER")
dt.object = posed_source
dt.use_loop_data = True
dt.data_types_loops = {"UV"}
dt.loop_mapping = "POLYINTERP_NEAREST"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.data.objects.remove(posed_source, do_unlink=True)
log("оболочка пересобрана в стоячей позе: %d вершин, %d треугольников"
    % (len(mesh.data.vertices), tri_count(mesh)))

_lo = [min((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices) for i in range(3)]
_hi = [max((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices) for i in range(3)]
log("поза применена, туловище: %s .. %s" % ([round(v, 2) for v in _lo], [round(v, 2) for v in _hi]))

if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_posed.blend"))

# ---------------------------------------------------------------- 6. веса по человеческому скелету
wa = skel.copy()
wa.data = skel.data.copy()
wa.name = "weighting_rig"
scene.collection.objects.link(wa)
select_only([wa], wa)
bpy.ops.object.mode_set(mode="EDIT")
web = wa.data.edit_bones
for chain in CHAINS:
    names = [BONES[c] for c in chain if c in BONES]
    for a, b in zip(names, names[1:]):
        if a in web and b in web:
            web[a].tail = web[b].head
bpy.ops.object.mode_set(mode="OBJECT")
for b in wa.data.bones:
    b.use_deform = b.name in {BONES[k] for k in CARD["joints"]} and not b.name.endswith("notused")
vl.update()
hbones = [(b.name, wa.matrix_world @ b.head_local, wa.matrix_world @ b.tail_local)
          for b in wa.data.bones if b.use_deform]
weight_by_bones(mesh, hbones, HUMAN_REGIONS, Matrix.Identity(4), count=3)
smooth_weights(mesh, rounds=4)
bpy.data.objects.remove(wa, do_unlink=True)


def limit_weights(ob):
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        pairs = sorted(((g.weight, names[g.group]) for g in v.groups), reverse=True)
        pairs = [(n, w) for w, n in pairs if w > MIN_WEIGHT][:MAX_INFLUENCES]
        total = sum(w for _n, w in pairs) or 1.0
        for name in {names[g.group] for g in v.groups}:
            ob.vertex_groups[name].remove([v.index])
        for name, w in pairs:
            ob.vertex_groups[name].add([v.index], w / total, "REPLACE")


limit_weights(mesh)
log("веса пересчитаны по человеческому скелету, не больше %d костей на вершину" % MAX_INFLUENCES)

# ---------------------------------------------------------------- 7. предметы
PART_BONES = {
    "head": {BONES["head"], BONES["neck"], BONES["head_end"]},
    "gloves": {BONES["l_hand"], BONES["r_hand"], BONES["l_hand_end"], BONES["r_hand_end"]},
    "legs": {BONES["l_thigh"], BONES["l_calf"], BONES["l_foot"], BONES["l_toe"],
             BONES["r_thigh"], BONES["r_calf"], BONES["r_foot"], BONES["r_toe"]},
}
parts = dict(extras)
for part_name, bones in PART_BONES.items():
    names = {g.index: g.name for g in mesh.vertex_groups}
    idx = []
    for v in mesh.data.vertices:
        best, bw = None, -1.0
        for g in v.groups:
            if g.weight > bw:
                best, bw = names[g.group], g.weight
        if best in bones:
            idx.append(v.index)
    part = separate(mesh, idx, "%s_%s" % (PREFIX, part_name))
    if part:
        parts[part_name] = part
        log("предмет %s: %d вершин" % (part.name, len(part.data.vertices)))
mesh.name = PREFIX + "_body"
parts["body"] = mesh
log("предмет %s: %d вершин" % (mesh.name, len(mesh.data.vertices)))

# ---------------------------------------------------------------- 8. текстуры и экспорт
for img in bpy.data.images:
    if img.size[0] == 0 or img.name in images_before:
        continue
    kind = "n" if "normal" in img.name.lower() else (
        "s" if "metallic" in img.name.lower() or "_rm" in img.name.lower() else "d")
    path = os.path.join(TEX_DIR, "%s_%s.png" % (PREFIX, kind))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    log("текстура %s -> %s" % (img.name, os.path.basename(path)))

for part in parts.values():
    part.parent = skel
    part.matrix_parent_inverse = skel.matrix_world.inverted()   # иначе поворот скелета ляжет дважды
    mod = part.modifiers.new("Armature", "ARMATURE")
    mod.object = skel

select_only(list(parts.values()) + [skel], skel)
fbx = os.path.join(OUT, PREFIX + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y",
                         bake_space_transform=False, mesh_smooth_type="FACE",
                         path_mode="COPY", embed_textures=False)
log("записан", fbx)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + ".blend"))
log("записан", os.path.join(OUT, PREFIX + ".blend"))
