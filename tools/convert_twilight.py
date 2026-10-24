# Конвертация "Twilight Sparkle (Anthro)" (glTF, MMD-скелет) в набор предметов Bannerlord
# на человеческом скелете: голова, тело, перчатки, ноги.
#
# blender --background --factory-startup --python convert_twilight.py -- <scene.gltf> <human_skeleton.fbx> <out_dir>
#        [<face_morphs.bin>]   — дамп вершинных ключей ванильной головы (tools\dump_face_morphs.ps1)
#
# Шаги:
#  1. Скелет Bannerlord импортируется с осями костей X/-Y (как советует документация).
#  2. Пони (лицом к -Y, как персонаж Bannerlord) масштабируется так, чтобы таз и шея совпали со скелетом.
#  3. Руки поворачиваются и удлиняются до суставов Bannerlord (с плавным переходом по весам MMD),
#     голени с копытами сжимаются по высоте, чтобы колени и пол совпали.
#  4. Веса: голова/грива/хвост жёстко на одну кость, остальное — автоматически по временной копии
#     скелета, у которой кости направлены на дочерние суставы.
#  5. Экспорт FBX (скелет + 4 меша), PNG-текстуры, .blend и превью.
import math
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

_args = sys.argv[sys.argv.index("--") + 1:]
GLTF, SKEL, OUT = _args[:3]
# необязательный 4-й аргумент: дамп вершинных ключей ванильной головы (tools\dump_face_morphs.ps1).
# Через эти 101 ключ движок делает мимику, моргание и движение глаз; без них лицо статичное.
FACE_MORPHS = _args[3] if len(_args) > 3 else ""
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

PREFIX = "eq_twilight"

# материал из glTF -> часть модели
PARTS = {
    "Material__43": "body",
    "Material__84": "eyelash",
    "8_-_Default": "eyes",
    "Material__396": "legs",
    "Material__422": "hair_front",
    "glove": "gloves",
    "Material__421": "hair_back",
    "Material__19": "head",
    "Material__330": "horn",
    "queue": "tail",
    "2_-_Default": "hooves",
    "Material__35": "teeth",
    "Material__37": "tongue",
}
# предмет Bannerlord -> части
ITEMS = {
    # хвост в теле: меш головы движок считает лицом и вершины с костью таза в нём разлетаются
    # eyelid — веки, построенные по форме глаза (см. build_eyelids): в базовой форме они сжаты в полоску
    # над глазом и не видны, а в кадрах 86/87/88 движок раскрывает их на весь глаз — это и есть моргание.
    f"{PREFIX}_head": ["head", "eyes", "eyelash", "teeth", "tongue", "eyelid"],
    # Грива с ушами — отдельный предмет в слот шлема (equestria_items.xml, eq_pony_mane, 0 защиты):
    # слот причёски у расы не работает (движок рвёт любую причёску на куски), а настоящий шлем просто
    # заменяет собой эту «причёску», и ничего сквозь него не торчит. Дыры от ушей в голове заращиваются.
    f"{PREFIX}_mane": ["hair_front", "hair_back", "horn"],
    # Хвост — отдельный предмет в слот плаща (eq_pony_tail): в меше тела его скрывал любой нагрудник
    # с covers_body, а слот плаща носится вместе с нагрудником.
    # cutiemark — метка на бедре геометрией (см. build_cutiemarks). Через накладки движка (tattoo_materials)
    # её не сделать: в Bannerlord они наносятся только на лицо.
    f"{PREFIX}_tail": ["tail", "cutiemark"],
    f"{PREFIX}_body": ["body"],
    f"{PREFIX}_gloves": ["gloves"],
    f"{PREFIX}_legs": ["legs", "hooves"],
}
# части, которые целиком двигаются с одной костью
RIGID = {p: "bip01_head_13" for p in ITEMS[f"{PREFIX}_head"] + ITEMS[f"{PREFIX}_mane"]}
RIGID["tail"] = "bip01_pelvis_0"
RIGID["cutiemark"] = "bip01_pelvis_0"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
vl = bpy.context.view_layer


def log(*a):
    print("[convert]", *a, flush=True)


def select_only(objs, active):
    for o in scene.objects:
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


# ---------------------------------------------------------------- 1. скелет Bannerlord
bpy.ops.import_scene.fbx(filepath=SKEL, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
skel = next(o for o in scene.objects if o.type == "ARMATURE")
orig_skel_scale = skel.scale.copy()
skel.scale = (1, 1, 1)  # в файле TaleWorlds масштаб 0.01 (рост 1.8 см) — работаем и экспортируем в метрах
vl.update()


def human(name):
    return skel.matrix_world @ skel.data.bones[name].head_local


H = {
    "pelvis": human("bip01_pelvis_0"),
    "neck": human("bip01_neck_12"),
    "r_shoulder": human("bip01_r_upperarm_twist_22"), "r_wrist": human("bip01_r_hand_26"),
    "l_shoulder": human("bip01_l_upperarm_twist_15"), "l_wrist": human("bip01_l_hand_19"),
    "l_knee": human("bip01_l_calf_2"), "r_knee": human("bip01_r_calf_6"),
}
log("human joints:", {k: tuple(round(c, 3) for c in v) for k, v in H.items()})

# ---------------------------------------------------------------- 2. пони
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLTF)
pony_objs = [o for o in scene.objects if o not in before]
parm = next(o for o in pony_objs if o.type == "ARMATURE")
dg = bpy.context.evaluated_depsgraph_get()


def pbone(idx):
    suffix = f"_{idx}"
    return next(b for b in parm.pose.bones if b.name.endswith(suffix))


def pony(idx):
    return parm.matrix_world @ pbone(idx).head


def descendants(idx):
    root = pbone(idx).bone
    return {root.name} | {c.name for c in root.children_recursive}


hip_c = (pony(100) + pony(106)) / 2
neck = pony(14)
s = (H["neck"].z - H["pelvis"].z) / (neck.z - hip_c.z)
log(f"scale factor {s:.3f}")


def sim_raw(p):
    # поворот на 180° вокруг Z (пони смотрит в -Y, скелет Bannerlord — в +Y), масштаб, таз -> таз.
    # Модель и веса анатомически совпадают со скелетом; разворот для игры делается поворотом всего скелета
    # при экспорте (см. TURN_SKELETON_ON_EXPORT).
    q = p - hip_c
    return Vector((-q.x * s, -q.y * s, q.z * s + H["pelvis"].z))


# Корпус пони наклонён вперёд относительно позвоночника Bannerlord: без поправки грудь и спина на уровне
# плеч стоят на 6–7 см впереди костей, а руки (они ставятся на кости) — позади корпуса. Сдвигаем верх
# тела по Y: 0 у таза, полный сдвиг от уровня плеч и выше (голова, грива, рог — тоже).
_pony_sh = (sim_raw(pony(42)) + sim_raw(pony(75))) / 2
_human_sh = (H["l_shoulder"] + H["r_shoulder"]) / 2
TORSO_SHIFT_Y = _human_sh.y - _pony_sh.y
log(f"torso shift y {TORSO_SHIFT_Y:+.3f} (pony shoulders y {_pony_sh.y:.3f}, human {_human_sh.y:.3f})")


def sim(p):
    q = sim_raw(p)
    t = min(max((q.z - H["pelvis"].z) / (_human_sh.z - H["pelvis"].z), 0.0), 1.0)
    t = t * t * (3 - 2 * t)  # плавный переход
    q.y += TORSO_SHIFT_Y * t
    return q


ARM_BACK = 0.06  # м, сдвиг кисти назад


def make_arm(shoulder_idx, wrist_idx, group_roots, h_shoulder, h_wrist):
    ps, pw = sim(pony(shoulder_idx)), sim(pony(wrist_idx))
    ap, ah = pw - ps, h_wrist - h_shoulder
    lp, lh = ap.length, ah.length
    rot = ap.normalized().rotation_difference(ah.normalized()).to_matrix()
    k = lh / lp
    axis = ah.normalized()
    groups = set().union(*(descendants(i) for i in group_roots))
    log(f"arm {shoulder_idx}: pony len {lp:.3f} -> human {lh:.3f} (x{k:.2f}), "
        f"angle {math.degrees(ap.angle(ah)):.1f}°, {len(groups)} bones")

    def transform(p):
        q = rot @ (p - ps)
        d = q.dot(axis)
        q += axis * ((k - 1) * min(max(d, 0.0), lp))
        # по проверке в Model Viewer руки отстают от корпуса — выносим вперёд (в движке это +Y
        # до разворота скелета; -Y проверено и оказалось назад), от 0 у плеча до ARM_BACK у запястья и дальше
        q.y += ARM_BACK * min(max(d / lp, 0.0), 1.0)
        return h_shoulder + q

    return groups, transform


# после поворота рука пони со стороны -X оказывается на +X — там кости bip01_r
ARMS = [
    make_arm(42, 27, (42, 45), H["r_shoulder"], H["r_wrist"]),
    make_arm(75, 60, (75, 78), H["l_shoulder"], H["l_wrist"]),
]
knee_z = (sim(pony(99)).z + sim(pony(105)).z) / 2
log(f"pony knee z {knee_z:.3f}, human knee z {(H['l_knee'].z + H['r_knee'].z) / 2:.3f}")

parts = {}
for ob in pony_objs:
    if ob.type != "MESH" or ob.name.startswith("Icosphere"):
        continue
    part = PARTS[ob.material_slots[0].material.name]
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    names = {g.index: g.name for g in ob.vertex_groups}
    coords = []
    for v_src, v in zip(ob.data.vertices, me.vertices):
        p = sim(ob.matrix_world @ v.co)
        for groups, transform in ARMS:
            w = min(1.0, sum(g.weight for g in v_src.groups if names.get(g.group) in groups))
            if w > 0:
                p = p.lerp(transform(p), w)
        coords.append(p)
    parts[part] = (me, coords)

# голени: сжать по высоте всё ниже колена, чтобы подошва стояла на полу
z_min = min(p.z for _, coords in parts.values() for p in coords)
leg_k = knee_z / (knee_z - z_min)
log(f"lowest point {z_min:.3f} -> 0, below-knee height x{leg_k:.2f}")

for part, (me, coords) in parts.items():
    for v, p in zip(me.vertices, coords):
        if p.z < knee_z:
            p = Vector((p.x, p.y, (p.z - z_min) * leg_k))
        v.co = p
    me.update()
    me.name = f"{PREFIX}_{part}"
    mat = me.materials[0]
    mat.name = f"{PREFIX}_{part}"
    ob = bpy.data.objects.new(f"{PREFIX}_{part}", me)
    scene.collection.objects.link(ob)
    ob.vertex_groups.clear()  # имена групп MMD хранятся в самом меше — убрать
    if part not in RIGID:
        # glTF разрезает сетку по UV-швам; без склейки половинки шва получат разные веса и разойдутся.
        # Сохранённые нормали после склейки становятся неверными — сбрасываем и сглаживаем заново.
        select_only([ob], ob)
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
        bm = bmesh.new()
        bm.from_mesh(me)
        n_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        log(f"part {part}: merged {n_before - len(me.vertices)} seam verts")
    parts[part] = ob

for o in pony_objs:
    bpy.data.objects.remove(o, do_unlink=True)
vl.update()

# ---------------------------------------------------------------- 3. временный скелет для весов
wa = skel.copy()
wa.data = skel.data.copy()
wa.name = "weighting_rig"
scene.collection.objects.link(wa)
select_only([wa], wa)
bpy.ops.object.mode_set(mode="EDIT")
eb = wa.data.edit_bones
for side, n in (("l", (1, 2, 3, 4)), ("r", (5, 6, 7, 8))):
    thigh, calf, foot, toe = (f"bip01_{side}_thigh_{n[0]}", f"bip01_{side}_calf_{n[1]}",
                              f"bip01_{side}_foot_{n[2]}", f"bip01_{side}_toe0_{n[3]}")
    nub = "bip01_l_toe0_nub_notused" if side == "l" else "bip01_toe0_nub_notused"
    for a, b in ((thigh, calf), (calf, foot), (foot, toe), (toe, nub)):
        eb[a].tail = eb[b].head
for a, b in (("bip01_pelvis_0", "bip01_spine_9"), ("bip01_spine_9", "bip01_spine1_10"),
             ("bip01_spine1_10", "bip01_spine2_11"), ("bip01_spine2_11", "bip01_neck_12"),
             ("bip01_neck_12", "bip01_head_13"), ("bip01_head_13", "bip01_head_nub_notused")):
    eb[a].tail = eb[b].head
for side, n in (("l", (14, 15, 16, 17, 18, 19, 20)), ("r", (21, 22, 23, 24, 25, 26, 27))):
    chain = [f"bip01_{side}_clavicle_{n[0]}", f"bip01_{side}_upperarm_twist_{n[1]}",
             f"bip01_{side}_upperarm_twist1_{n[2]}", f"bip01_{side}_foretwist_{n[3]}",
             f"bip01_{side}_foretwist1_{n[4]}", f"bip01_{side}_hand_{n[5]}",
             f"bip01_{side}_finger0_{n[6]}"]
    for a, b in zip(chain, chain[1:]):
        eb[a].tail = eb[b].head  # кисть: запястье -> основание пальцев (ладонь)
    # пальцы: от основания вдоль направления предплечья (так вытянута кисть пони)
    finger, fore = eb[chain[-1]], eb[chain[-3]]
    finger.tail = finger.head + (eb[chain[-2]].head - fore.head).normalized() * 0.15
bpy.ops.object.mode_set(mode="OBJECT")
for b in wa.data.bones:
    # finger0 (большой палец) ванильные кисти не используют; с ним в Model Viewer часть вершин перчатки
    # вытягивалась полосой к полу — пальцы пони целиком идут на кость кисти
    b.use_deform = not b.name.endswith("notused") and "_finger0_" not in b.name

bone_segments = [(b.name, wa.matrix_world @ b.head_local, wa.matrix_world @ b.tail_local)
                 for b in wa.data.bones if b.use_deform]


def nearest_bone(p):
    best, best_d = None, 1e9
    for name, a, b in bone_segments:
        ab = b - a
        t = min(max((p - a).dot(ab) / ab.length_squared, 0.0), 1.0)
        d = (a + ab * t - p).length
        if d < best_d:
            best, best_d = name, d
    return best


def auto_weights(ob):
    select_only([ob, wa], wa)
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    mw = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = mw
    # Автовеса иногда не находят решения для части вершин (отдельные куски, двойные поверхности).
    # Такие вершины берут веса ближайшей вершины с весами, а если таких нет — ближайшей кости.
    verts = ob.data.vertices
    weighted = [v for v in verts if sum(g.weight for g in v.groups) > 1e-4]
    zero = [v for v in verts if sum(g.weight for g in v.groups) <= 1e-4]
    if weighted:
        tree = KDTree(len(weighted))
        for i, v in enumerate(weighted):
            tree.insert(v.co, i)
        tree.balance()
    group_names = {g.index: g.name for g in ob.vertex_groups}
    for v in zero:
        if weighted:
            _, i, _ = tree.find(v.co)
            for g in weighted[i].groups:
                ob.vertex_groups[group_names[g.group]].add([v.index], g.weight, "REPLACE")
        else:
            name = nearest_bone(ob.matrix_world @ v.co)
            vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
            vg.add([v.index], 1.0, "REPLACE")
    log(f"weights {ob.name}: {len(ob.vertex_groups)} groups, "
        f"{len(zero)}/{len(verts)} verts without auto weights fixed")


MAX_INFLUENCES = 3
MIN_WEIGHT = 0.02


def limit_weights(ob):
    # У ванильных мешей Bannerlord не больше 3 костей на вершину и сумма весов ровно 1 (проверено на
    # Female_BodyBase). Автовеса дают до 6 костей с суммой меньше 1 — в движке такие вершины сползают.
    groups = {g.index: g for g in ob.vertex_groups}
    trimmed = 0
    for v in ob.data.vertices:
        ws = sorted(((g.group, g.weight) for g in v.groups if g.weight > 1e-4), key=lambda gw: -gw[1])
        # веса меньше MIN_WEIGHT движок, видимо, округляет до нуля (8 бит на вес): с ними часть вершин
        # перчатки улетала полосой в начало координат
        keep = [gw for gw in ws[:MAX_INFLUENCES] if gw[1] >= MIN_WEIGHT] or ws[:1]
        total = sum(w for _, w in keep)
        if len(ws) > MAX_INFLUENCES:
            trimmed += 1
        for g in list(v.groups):
            groups[g.group].remove([v.index])
        for gi, w in keep:
            groups[gi].add([v.index], w / total, "REPLACE")
    log(f"weights {ob.name}: {trimmed} verts trimmed to {MAX_INFLUENCES} bones, all normalized")


# Раньше модель разворачивалась лицом к -Y с перестановкой весов левой/правой стороны. Для симметричного
# тела в покое это выглядело верно, но разворот меняет местами перёд и зад у рук: в игре большой палец
# оказывался сзади, и рука при сгибе выворачивалась назад. Теперь веса по положению, без перестановки.
for part, ob in parts.items():
    if part in RIGID:
        vg = ob.vertex_groups.new(name=RIGID[part])
        vg.add(range(len(ob.data.vertices)), 1.0, "REPLACE")
    else:
        auto_weights(ob)
        limit_weights(ob)

bpy.data.objects.remove(wa, do_unlink=True)

# Голову берём из оригинала как есть: уши остаются на ней. Попытки отрезать уши и заращивать дыры
# портили череп (рваные края, дыры, гранёная макушка) — при необходимости уши скрываются вырезами
# в шлемах для пони, а не правкой головы.
# Низ предплечья — в меш кистей, как у ванильного тела (там кисти начинаются с ~0.82 длины плечо→запястье).
# Ванильные нагрудники прячут рукав на предплечье внутрь руки, рассчитывая на меш кистей: если предплечье
# в меше тела, нагрудник (covers_body) скрывает его и вместо руки видна сжатая ткань.
FOREARM_TO_HANDS_T = 0.72


def arm_t(p):
    best = None
    for side in ("l", "r"):
        sh, wr = H[f"{side}_shoulder"], H[f"{side}_wrist"]
        v = wr - sh
        t = (p - sh).dot(v) / v.length_squared
        r = (p - (sh + v * t)).length
        if r < 0.15 and (best is None or r < best[1]):
            best = (t, r)
    return best[0] if best else -1.0


body_ob, gloves_ob = parts["body"], parts["gloves"]
select_only([body_ob], body_ob)
bm = bmesh.new()
bm.from_mesh(body_ob.data)
for elem in (*bm.verts, *bm.edges, *bm.faces):
    elem.select = False
for f in bm.faces:
    if arm_t(body_ob.matrix_world @ f.calc_center_median()) > FOREARM_TO_HANDS_T:
        f.select_set(True)
moved = sum(f.select for f in bm.faces)
bm.select_mode = {"FACE"}
bm.to_mesh(body_ob.data)
bm.free()
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_mode(type="FACE")
bpy.ops.mesh.separate(type="SELECTED")
bpy.ops.object.mode_set(mode="OBJECT")
forearms = next(o for o in vl.objects.selected if o is not body_ob)
select_only([gloves_ob, forearms], gloves_ob)
bpy.ops.object.join()
log(f"forearms: {moved} faces moved from body to gloves (t > {FOREARM_TO_HANDS_T})")

# Материал модели собран без альфы, поэтому ресницы рисуются сплошными тёмными полигонами. У самих глаз
# они выглядят нормально, а дальние (на лбу и щеках) в игре смотрелись как мусор перед лицом — их удаляем.
LASH_LIMIT = 0.02  # м от поверхности глаза
eyes_pts = [parts["eyes"].matrix_world @ v.co for v in parts["eyes"].data.vertices]
eyes_tree = KDTree(len(eyes_pts))
for i, p in enumerate(eyes_pts):
    eyes_tree.insert(p, i)
eyes_tree.balance()
# центры глаз пони — по ним потом привязываются лицевые ключи (add_face_morphs)
_eyes_arr = np.array([tuple(p) for p in eyes_pts])
PONY_EYES = (_eyes_arr[_eyes_arr[:, 0] > 0].mean(0), _eyes_arr[_eyes_arr[:, 0] < 0].mean(0))
_eye_l = _eyes_arr[_eyes_arr[:, 0] > 0]
PONY_EYE_R = float((_eye_l[:, 0].max() - _eye_l[:, 0].min()) / 2)  # половина ширины глаза
PONY_EYE_RADII = (_eye_l.max(0) - _eye_l.min(0)) / 2  # глаз вытянут по высоте — веко строим по габаритам
log(f"pony eye box {np.round(_eye_l.min(0), 3)}..{np.round(_eye_l.max(0), 3)}, r {PONY_EYE_R:.3f}")
LID_RINGS, LID_SEGS, LID_ARC = 5, 20, math.radians(96)
# Движок часто применяет кадр века не на полную силу (в анимациях бывает 0.1–0.5), поэтому веко строится
# с запасом: при частичном раскрытии глаз уже прикрыт, при полном — веко чуть выступает за глаз.
LID_OVERSHOOT = 1.15  # сетка крышки-века и её раскрытие по сфере глаза


def build_eyelids():
    """Строит меш век: купол по передней части каждого глаза.

    В экспорт идёт «сжатая» форма — все вершины прижаты к верхнему краю глаза, там их не видно.
    Раскрытые позиции возвращаются отдельно: из них делаются кадры моргания (add_face_morphs).
    """
    skull_c = Vector((0.0, np.median([p[1] for p in eyes_pts]), np.median([p[2] for p in eyes_pts]) + 0.08))
    verts, faces, expanded, base = [], [], [], 0
    for side, center in enumerate(PONY_EYES):
        c = Vector(center)
        n = (c - skull_c).normalized()
        up = Vector((0, 0, 1)) - n * (Vector((0, 0, 1)).dot(n))
        up = up.normalized() if up.length > 1e-6 else Vector((0, 1, 0))
        side_v = n.cross(up).normalized()
        radii = Vector(PONY_EYE_RADII) * 1.16 * LID_OVERSHOOT  # с запасом, чтобы веко шло поверх глаза

        def on_eye(d):  # точка на поверхности глаза в направлении d
            return c + Vector((d.x * radii.x, d.y * radii.y, d.z * radii.z))

        top = on_eye(n * math.cos(LID_ARC) + up * math.sin(LID_ARC))  # верхний край глаза
        for ring in range(LID_RINGS + 1):
            a = LID_ARC * (1 - ring / LID_RINGS) if ring else LID_ARC
            for seg in range(LID_SEGS):
                t = 2 * math.pi * seg / LID_SEGS
                d = n * math.cos(a) + (up * math.cos(t) + side_v * math.sin(t)) * math.sin(a)
                expanded.append(on_eye(d))
                verts.append(top + (up * math.cos(t) + side_v * math.sin(t)) * (radii.z * 0.02))
        for ring in range(LID_RINGS):
            for seg in range(LID_SEGS):
                a0 = base + ring * LID_SEGS + seg
                a1 = base + ring * LID_SEGS + (seg + 1) % LID_SEGS
                b0, b1 = a0 + LID_SEGS, a1 + LID_SEGS
                faces.append((a0, a1, b1, b0) if side == 0 else (a0, b0, b1, a1))
        base = len(verts)
    me = bpy.data.meshes.new(f"{PREFIX}_eyelid")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.shade_smooth()
    # UV берём у ближайшей вершины морды: веко должно быть цвета шерсти вокруг глаза
    head_ob = parts["head"]
    head_uv = head_ob.data.uv_layers.active.data
    uv_of_vert = {}
    for poly in head_ob.data.polygons:
        for li in poly.loop_indices:
            uv_of_vert.setdefault(head_ob.data.loops[li].vertex_index, tuple(head_uv[li].uv))
    head_tree = KDTree(len(uv_of_vert))
    order = list(uv_of_vert)
    for i, vi in enumerate(order):
        head_tree.insert(head_ob.matrix_world @ head_ob.data.vertices[vi].co, i)
    head_tree.balance()
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            p = Vector(expanded[me.loops[li].vertex_index])
            _, i, _ = head_tree.find(p)
            layer.data[li].uv = uv_of_vert[order[i]]
    me.materials.append(bpy.data.materials[f"{PREFIX}_head"])  # цвет шерсти, как у морды
    ob = bpy.data.objects.new(f"{PREFIX}_eyelid", me)
    scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name=RIGID["head"])
    vg.add(range(len(me.vertices)), 1.0, "REPLACE")
    log(f"eyelids: {len(verts)} verts, {len(faces)} faces")
    return ob, np.array([tuple(p) for p in expanded])


parts["eyelid"], LID_EXPANDED = build_eyelids()

MARK_SIZE = 0.075      # м, радиус большой звезды
MARK_OFFSET = 0.0025   # м, отступ от кожи, чтобы метка не мерцала


def build_cutiemarks():
    """Кьютимарка на бедре: силуэт звезды, положенный на поверхность тела.

    Накладки движка (tattoo_materials) рисуются только на лице, поэтому метка делается геометрией
    и входит в предмет-хвост (слот плаща, который пони и так носит).
    """
    body = parts["body"]
    pts = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])
    z_lo, z_hi = np.percentile(pts[:, 2], [14, 30])
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mat = bpy.data.materials.new(f"{PREFIX}_cutiemark")
    # две половины: слева цвет большой звезды, справа белый для маленьких (мелкая картинка мылится
    # при масштабировании в атлас, поэтому 64x64, а не 2 пикселя)
    img = bpy.data.images.new(f"{PREFIX}_cutiemark_d", 64, 64, alpha=False)
    half = np.zeros((64, 64, 4), dtype=np.float32)
    half[..., 3] = 1.0
    half[:, :32, :3] = np.array([0.85, 0.2, 0.75], dtype=np.float32)
    half[:, 32:, :3] = 1.0
    img.pixels.foreach_set(half.ravel())
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.links.new(mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"], tex.outputs["Color"])

    verts, faces, uvs = [], [], []

    def star_at(center, normal, radius, uv):
        """Кладёт силуэт шестиконечной звезды на поверхность тела вокруг точки center."""
        up = Vector((0, 0, 1)) - normal * Vector((0, 0, 1)).dot(normal)
        up = up.normalized()
        side = normal.cross(up).normalized()
        def on_skin(target):
            # луч строго вдоль нормали: find_nearest тянул точки вбок и звезда выходила кривой
            hit, hit_n, _, _ = bvh.ray_cast(target + normal * 0.12, -normal)
            return (hit + hit_n * MARK_OFFSET) if hit else (target + normal * MARK_OFFSET)

        base = len(verts)
        ring = []
        for k in range(12):
            a = math.pi * k / 6
            r = radius if k % 2 == 0 else radius * 0.34
            ring.append(on_skin(center + (up * math.cos(a) + side * math.sin(a)) * r))
        verts.append(on_skin(center))
        verts.extend(ring)
        uvs.extend([uv] * 13)
        for k in range(12):
            faces.append((base, base + 1 + k, base + 1 + (k + 1) % 12))

    for sign in (1, -1):
        sel = pts[(np.sign(pts[:, 0]) == sign) & (pts[:, 2] > z_lo) & (pts[:, 2] < z_hi) & (np.abs(pts[:, 1]) < 0.1)]
        center = Vector(sel.mean(0))
        normal = Vector((float(sign), 0, 0))
        star_at(center, normal, MARK_SIZE, (0.25, 0.5))
        # маленьких звёзд вокруг большой больше не делаем: вся метка жёстко сидит на тазе, а они
        # ложились уже на ногу и при шаге отрывались от кожи — «летали» отдельным мешем
        # (убраны 18.09.2026, см. tools/trim_cutiemark.py)
    me = bpy.data.meshes.new(f"{PREFIX}_cutiemark")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.shade_smooth()
    me.materials.append(mat)
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[me.loops[li].vertex_index]
    ob = bpy.data.objects.new(f"{PREFIX}_cutiemark", me)
    scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name=RIGID["cutiemark"])
    vg.add(range(len(me.vertices)), 1.0, "REPLACE")
    log(f"cutiemarks: {len(verts)} verts, {len(faces)} faces")
    return ob


parts["cutiemark"] = build_cutiemarks()

# метка глазных яблок: их веко двигать нельзя (иначе поедет сам глаз)
for _part in ITEMS[f"{PREFIX}_head"]:
    _ob = parts[_part]
    _attr = _ob.data.attributes.new("eq_eye", "INT", "POINT")
    _lid = _ob.data.attributes.new("eq_lid", "INT", "POINT")  # номер вершины века (0 — не веко)
    for _i in range(len(_ob.data.vertices)):
        _attr.data[_i].value = 1 if _part == "eyes" else 0
        _lid.data[_i].value = _i + 1 if _part == "eyelid" else 0
PONY_CHIN_Z = float(min((parts["head"].matrix_world @ v.co).z for v in parts["head"].data.vertices))
log(f"pony eyes {np.round(PONY_EYES[0], 3)} / {np.round(PONY_EYES[1], 3)}, chin z {PONY_CHIN_Z:.3f}")
lash = parts["eyelash"]
lash_bm = bmesh.new()
lash_bm.from_mesh(lash.data)
outside = [f for f in lash_bm.faces
           if min(eyes_tree.find(lash.matrix_world @ v.co)[2] for v in f.verts) > LASH_LIMIT]
bmesh.ops.delete(lash_bm, geom=outside, context="FACES")
bmesh.ops.delete(lash_bm, geom=[v for v in lash_bm.verts if not v.link_faces], context="VERTS")
lash_bm.to_mesh(lash.data)
lash_bm.free()
lash.data.update()
log(f"eyelashes trimmed: {len(outside)} faces farther than {LASH_LIMIT} m from the eyes")

# ---------------------------------------------------------------- 4. сборка предметов
items = {}
for item, part_names in ITEMS.items():
    objs = [parts[p] for p in part_names]
    select_only(objs, objs[0])
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = vl.objects.active
    ob.name = item
    ob.data.name = item
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = skel
    items[item] = ob
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    log(f"item {item}: {tris} tris, materials {[m.name for m in ob.data.materials]}")

# Скелет остаётся с масштабом 1: в FBX персонаж будет честно 1.8 м (180 см), и при импорте в редактор
# с "Convert to unit: m" размер совпадёт со скелетом игры. С исходным масштабом 0.01 из human_skeleton.fbx
# файл описывал фигуру ростом 1.8 см — в игре меш сминался в лучи по полу.
vl.update()

# ---------------------------------------------------------------- 5. атлас: все текстуры в одну, один материал
# Каждая исходная текстура занимает клетку сетки 4x4 (UV всех частей лежат в 0..1, запекание не нужно).
# Вся модель получает один материал eq_twilight_body — его настраивают в редакторе один раз.
CELL, GRID, PAD = 1024, 4, 8
INNER = CELL - 2 * PAD
ATLAS_MAT = f"{PREFIX}_body"

COAT_PARTS = {"body", "head", "legs", "gloves", "hooves"}  # шерсть и копыта — их красит движок
COAT_LIGHTEN = 1.25  # серая база чуть светлее оригинала, иначе окрас выходит тусклым
coat_tint = []

part_mats = sorted({m.name for ob in items.values() for m in ob.data.materials})
cells = {name: i for i, name in enumerate(part_mats)}
atlas_px = np.zeros((CELL * GRID, CELL * GRID, 4), dtype=np.float32)
atlas_px[..., 3] = 1.0
for name, i in cells.items():
    col, row = i % GRID, i // GRID
    mat = bpy.data.materials[name]
    src = next((n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    if src is None:  # у зубов текстуры не было
        px = np.ones((INNER, INNER, 4), dtype=np.float32)
    else:
        # читаем пиксели напрямую и растягиваем numpy: копия процедурной картинки (image.copy() + scale)
        # приходила пустой, и клетка атласа получалась чёрной
        w, h = src.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        src.pixels.foreach_get(buf)
        buf = buf.reshape(h, w, 4)
        ys = (np.arange(INNER) * h // INNER).clip(0, h - 1)
        xs = (np.arange(INNER) * w // INNER).clip(0, w - 1)
        px = buf[ys][:, xs].copy()
    # Шерсть обесцвечиваем: движок умножает текстуру на выбранный цвет кожи, и по насыщенной сиреневой
    # базе ползунок окраса почти не читался. Грива, хвост, рог и глаза остаются цветными.
    part = name[len(PREFIX) + 1:]
    if part in COAT_PARTS:
        rgb = px[..., :3]
        gray = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        mean_rgb, mean_gray = rgb.reshape(-1, 3).mean(0), float(gray.mean())
        px[..., :3] = np.clip(gray[..., None] * COAT_LIGHTEN, 0.0, 1.0)
        coat_tint.append(mean_rgb / max(mean_gray * COAT_LIGHTEN, 1e-4))
        log(f"  coat cell {name}: mean {np.round(mean_rgb, 3)} -> grayscale, "
            f"tint {np.round(coat_tint[-1], 3)}")
    # поля по краю клетки повторяют крайние пиксели — чтобы мипмапы не смешивали соседние клетки
    px = np.pad(px, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
    atlas_px[row * CELL:(row + 1) * CELL, col * CELL:(col + 1) * CELL] = px
    log(f"atlas cell {i} ({col},{row}): {name}")

# суффикс _d: редактор Bannerlord распознаёт такую текстуру как DiffuseMap
atlas = bpy.data.images.new(f"{ATLAS_MAT}_d", CELL * GRID, CELL * GRID, alpha=False)
atlas.pixels.foreach_set(atlas_px.ravel())
atlas.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_d.png")
atlas.file_format = "PNG"
atlas.save()
log(f"texture {atlas.name}.png {atlas.size[0]}x{atlas.size[1]}")
if coat_tint:
    tint = np.mean(coat_tint, axis=0)
    log(f"coat palette hint: исходный цвет шерсти = point \"{tint[0]:.2f}, {tint[1]:.2f}, {tint[2]:.2f}\" "
        f"(вписать первой точкой в COAT_PALETTE, tools\\make_pony_race.py)")

atlas_mat = bpy.data.materials[ATLAS_MAT]
for ob in items.values():
    me = ob.data
    uv = me.uv_layers.active.data
    names = [m.name for m in me.materials]
    for poly in me.polygons:
        i = cells[names[poly.material_index]]
        col, row = i % GRID, i // GRID
        for li in poly.loop_indices:
            u, v = uv[li].uv
            uv[li].uv = ((col + (PAD + u * INNER) / CELL) / GRID, (row + (PAD + v * INNER) / CELL) / GRID)
        poly.material_index = 0
    me.materials.clear()
    me.materials.append(atlas_mat)
for node in atlas_mat.node_tree.nodes:
    if node.type == "TEX_IMAGE":
        node.image = atlas
for mat in list(bpy.data.materials):
    if mat.users == 0:
        bpy.data.materials.remove(mat)

# Порядок обхода граней НЕ разворачивать: проверено в Model Viewer 2026-09-15 — с разворотом
# была видна изнанка модели. Исходный порядок из Blender правильный.

# Плоская карта нормалей (0.5, 0.5, 1): материалу с Vertex Layout -> Bumpmap нужна карта в слоте NormalMap,
# без неё освещение модели в игре ломается (тёмная на солнце, засвеченная в меню).
flat_n = bpy.data.images.new(f"{ATLAS_MAT}_n", 256, 256, alpha=False)
flat_n.pixels.foreach_set(np.tile(np.array([0.5, 0.5, 1.0, 1.0], dtype=np.float32), 256 * 256))
flat_n.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_n.png")
flat_n.file_format = "PNG"
flat_n.save()
log(f"texture {flat_n.name}.png (flat normal map)")

# Ровная карта бликов для шейдера кожи faceshader_high: редакторская заглушка default_editor_texture_s —
# синий шум и даёт рябь на шерсти. Тёмно-серая карта = слабый ровный блик.
flat_s = bpy.data.images.new(f"{ATLAS_MAT}_s", 256, 256, alpha=False)
flat_s.pixels.foreach_set(np.tile(np.array([0.15, 0.15, 0.15, 1.0], dtype=np.float32), 256 * 256))
flat_s.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_s.png")
flat_s.file_format = "PNG"
flat_s.save()
log(f"texture {flat_s.name}.png (flat specular map)")

# Модель построена лицом к +Y, как скелет из modding_resources, но движок показывает такой меш спиной
# к скелету. Поворачиваем весь скелет вместе с мешами на 180° вокруг Z — так же повёрнут скелет
# в эталонных FBX мододелов (Skinned Body Base Meshes). Анатомия и веса не меняются.
TURN_SKELETON_ON_EXPORT = True
if TURN_SKELETON_ON_EXPORT:
    skel.rotation_mode = "XYZ"
    skel.rotation_euler.z += math.pi
    vl.update()
    log(f"skeleton turned 180° for export, rotation {tuple(round(a, 3) for a in skel.rotation_euler)}")

def add_face_morphs(ob, path):
    """Переносит вершинные ключи ванильной головы на голову пони.

    Головы очень разные, поэтому сопоставляем их по габаритному ящику черепа: точка пони переводится
    в координаты человеческой головы, берётся 4 ближайшие вершины человека, их смещения усредняются
    и масштабируются обратно. Порядок ключей сохраняется — на него ссылаются лицевые анимации игры.
    """
    import struct

    EYE_FRAME = 17  # кадр eye_size из skins.xml — по нему находим глаза на человеческой голове
    with open(path, "rb") as f:
        n, frames = struct.unpack("<ii", f.read(8))
        base = np.frombuffer(f.read(n * 12), dtype="<f4").reshape(n, 3).astype(float)
        deltas = []
        for _ in range(frames):
            struct.unpack("<i", f.read(4))
            pts = np.frombuffer(f.read(n * 12), dtype="<f4").reshape(n, 3).astype(float)
            deltas.append(pts - base)

    # Привязка по глазам, а не по габаритам головы: с габаритами смещения человеческого лица ложились
    # пони на уши (у пони голова шире из-за ушей и длиннее из-за морды).
    moved = np.linalg.norm(deltas[EYE_FRAME], axis=1) > 1e-4
    h_eye_l = base[moved & (base[:, 0] > 0)].mean(0)
    h_eye_r = base[moved & (base[:, 0] < 0)].mean(0)
    p_eye_l, p_eye_r = PONY_EYES
    k_x = abs(p_eye_l[0] - p_eye_r[0]) / max(abs(h_eye_l[0] - h_eye_r[0]), 1e-6)
    h_eye_mid, p_eye_mid = (h_eye_l + h_eye_r) / 2, (p_eye_l + p_eye_r) / 2
    k_z = (p_eye_mid[2] - PONY_CHIN_Z) / max(h_eye_mid[2] - base[:, 2].min(), 1e-6)
    scale = np.array([k_x, (k_x + k_z) / 2, k_z])  # по глубине — среднее, морда пони длиннее лица
    log(f"face morph fit: human eyes {np.round(h_eye_mid, 3)}, pony {np.round(p_eye_mid, 3)}, "
        f"scale {np.round(scale, 2)}")

    # локальные координаты меша: к этому моменту скелет уже повёрнут на 180°, а ключи и эталонные данные
    # считаются в исходной системе (она же локальная для меша)
    pony_pts = np.array([tuple(v.co) for v in ob.data.vertices])
    h_lo, p_lo = h_eye_mid, p_eye_mid

    tree = KDTree(len(base))
    for i, p in enumerate(base):
        tree.insert(Vector(p), i)
    tree.balance()

    idx, weight = [], []
    for p in pony_pts:
        q = h_lo + (p - p_lo) / scale  # точка пони -> координаты человеческой головы
        near = tree.find_n(Vector(q), 4)
        w = np.array([1.0 / max(d, 1e-4) for _, _, d in near])
        idx.append([i for _, i, _ in near])
        weight.append(w / w.sum())
    idx, weight = np.array(idx), np.array(weight)

    # Кадры 86/87/88 — закрытые веки (по ним движок моргает, см. анимацию idle_normal). Человеческое
    # веко смещается на 2–4 мм, а глаз пони размером с ладонь, поэтому перенос тут бесполезен:
    # рисуем закрытое веко сами — кожу вокруг глаза стягиваем к его центру и выводим перед глазом.
    lid_attr = ob.data.attributes.get("eq_lid")
    lid_idx = np.array([lid_attr.data[i].value for i in range(len(ob.data.vertices))]) if lid_attr \
        else np.zeros(len(ob.data.vertices), int)
    is_lid = lid_idx > 0
    per_eye = len(LID_EXPANDED) // 2  # первая половина вершин — правый глаз (+X), вторая — левый

    eye_attr = ob.data.attributes.get("eq_eye")
    is_eye = np.array([eye_attr.data[i].value for i in range(len(ob.data.vertices))], bool) if eye_attr \
        else np.zeros(len(ob.data.vertices), bool)

    def eyelid_shift(halves):
        shift = np.zeros_like(pony_pts)
        sel = is_lid.copy()
        for i in np.flatnonzero(is_lid):
            half = 0 if (lid_idx[i] - 1) < per_eye else 1
            if half in halves:
                shift[i] = LID_EXPANDED[lid_idx[i] - 1] - pony_pts[i]
            else:
                sel[i] = False
        # Само глазное яблоко в кадре моргания сжимается по высоте к центру глаза. Движок часто применяет
        # кадр не на полную силу, и одного века было почти не видно; со сжатием даже частичное срабатывание
        # читается как прищур.
        for half in halves:
            c = PONY_EYES[half]
            mask = is_eye & ((pony_pts[:, 0] > 0) if half == 0 else (pony_pts[:, 0] < 0))
            shift[mask, 2] += (c[2] - pony_pts[mask, 2]) * 0.92
        log(f"  eyelid frame: {int(sel.sum())} lid verts, {int((is_eye).sum())} eye verts, "
            f"max {np.linalg.norm(shift, axis=1).max():.4f} m")
        return shift

    blink = {86: eyelid_shift({0}), 87: eyelid_shift({1}), 88: eyelid_shift({0, 1})}

    ob.shape_key_add(name="Basis", from_mix=False)
    for k, d in enumerate(deltas):
        key = ob.shape_key_add(name=f"key_{k:03d}", from_mix=False)
        shift = blink[k] if k in blink else (d[idx] * weight[:, :, None]).sum(1) * scale
        if k not in blink:
            shift[is_lid] = 0.0  # веки двигаются только в кадрах моргания
        for i, v in enumerate(key.data):
            v.co = v.co + Vector(shift[i])
    log(f"face morphs: {frames} keys transferred to {ob.name} "
        f"(max shift {max(float(np.abs((d[idx] * weight[:, :, None]).sum(1) * scale).max()) for d in deltas):.4f} m)")


if FACE_MORPHS:
    add_face_morphs(items[f"{PREFIX}_head"], FACE_MORPHS)

select_only([skel, *items.values()], skel)
fbx_path = os.path.join(OUT, f"{PREFIX}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
log("exported", fbx_path)

for img in list(bpy.data.images):
    if img.users == 0:
        bpy.data.images.remove(img)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{PREFIX}.blend"))
log("saved blend")

# ---------------------------------------------------------------- 6. превью: покой и тестовая поза
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for ob in items.values():
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
center, size = (lo + hi) / 2, max(hi - lo)
log(f"final size (scene units) {tuple(round(v, 5) for v in (hi - lo))}")

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
scene.world = bpy.data.worlds.new("preview")
cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 1.25
cam.data.clip_start = size * 0.01
cam.data.clip_end = size * 100
scene.collection.objects.link(cam)
scene.camera = cam


def render(name, direction):
    cam.location = center + direction * size * 3
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, "preview", f"{name}.png")
    bpy.ops.render.render(write_still=True)


render("rest_front", Vector((0, -1, 0)))
render("rest_side", Vector((1, 0, 0)))

POSE = {  # произвольная поза, только чтобы проверить сгибы
    "bip01_r_upperarm_twist_22": (0, 0, -1.0),
    "bip01_r_foretwist_24": (0, 0, -1.2),
    "bip01_l_thigh_1": (0, 0, 0.9),
    "bip01_l_calf_2": (0, 0, -1.2),
    "bip01_spine1_10": (0, 0.3, 0),
    "bip01_head_13": (0.4, 0, 0),
}
for name, rot in POSE.items():
    pb = skel.pose.bones[name]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = rot
vl.update()
render("pose_front", Vector((0, -1, 0)))
render("pose_side", Vector((1, 0, 0)))
log("done")
