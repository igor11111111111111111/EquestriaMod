# -*- coding: utf-8 -*-
"""Машущие крылья пони на ванильном скелете птицы (10.10.2026).

В human_skeleton нет костей для крыльев, а свои кости движок не даёт. Птицы в игре — проп со
скелетом bird_skeleton и клипами anim_bird_* (Native Bird.cs). Делаем так же: меш крыльев пони
привязываем к крыльевым костям bird_skeleton, в игре проп вешаем на spine2 и играем anim_bird_cycle.

Скелет птицы снят из игры (EquestriaWingsTest, дамп в tools/engine_rest_bird_skeleton.txt) и
собран здесь как арматура: оси как в make_flight_pose_engine.py (engine s = ось кости = Blender Y,
f = -Blender X, u = Blender Z), позиции — как в движке (масштаб птицы). Меш крыльев пони
ужимается в SCALE раз вокруг начала арматуры T ((v - T) / SCALE), а в игре сущность ставится в T
с масштабом SCALE (EquestriaWings.Scale) — так и кости, и меш возвращаются к размеру пони.
(Первая версия 10.10.2026 масштабировала кости ×SCALE и оставляла меш как есть — в игре меш
раздувался второй раз и уезжал в сторону.)

Запуск (из корня мода):
    blender --background assets/pony/eq_pony_edit.blend --python tools/make_wings_rig.py
Выход: assets/wings/eq_pony_wings_rig.fbx (меш eq_pony_wings_rig + арматура bird_skeleton),
затем Resource Browser → Assets/wings → Import new asset.
"""
import math
import os
import re
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, "tools", "engine_rest_bird_skeleton.txt")
OUT_DIR = os.path.join(ROOT, "assets", "wings")
OUT_FBX = os.path.join(OUT_DIR, "eq_pony_wings_rig.fbx")
MESH_NAME = "eq_pony_wings_rig"
ARM_NAME = "bird_skeleton"

# Цепочки крыла, которым раздаём веса (перья-кости не трогаем — они складываются в клипе сами)
# Только плечевая кость на каждую сторону (10.10.2026): у птицы wing_1/wing_2 — локоть и запястье,
# они на взмахе гнутся навстречу, и ось вращения для глаза уезжала в середину крыла. Пегасу нужен
# жёсткий взмах всего крыла вокруг плеча — одна кость, веса 1.0.
CHAINS = {
    "left": ["left_wing_shoulder"],
    "right": ["right_wing_shoulder"],
}
BLEND_DIST = 0.035  # м (в масштабе птицы, ≈0.06 м пони): плавный переход весов между соседними костями

# --------------------------------------------------------------- дамп
vec = r"\(([-\d.]+),([-\d.]+),([-\d.]+)\)"
bone_re = re.compile(r"\[(\d+)\] (\S+) parent=(-?\d+)")
rest_re = re.compile(r"entitialRest\s+o=" + vec + r" f=" + vec + r" s=" + vec + r" u=" + vec)
bones = []
cur = None
for line in open(DUMP, encoding="utf-8", errors="replace"):
    m = bone_re.search(line)
    if m:
        cur = {"i": int(m.group(1)), "name": m.group(2), "parent": int(m.group(3))}
        bones.append(cur)
        continue
    m = rest_re.search(line)
    if m and cur is not None and "o" not in cur:
        n = [float(x) for x in m.groups()]
        cur["o"], cur["f"], cur["s"], cur["u"] = Vector(n[0:3]), Vector(n[3:6]), Vector(n[6:9]), Vector(n[9:12])
by_name = {b["name"]: b for b in bones}
assert len(bones) >= 20, "дамп птицы неполный"

# --------------------------------------------------------------- меш крыльев
wings = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
W = wings.matrix_world
verts = [W @ v.co for v in wings.data.vertices]
tip_x = max(abs(v.x) for v in verts)
root = [v for v in verts if abs(v.x) < 0.12]
root_c = sum(root, Vector()) / len(root) if root else Vector((0, 0.2, 1.2))
bird_tip_x = abs(by_name["right_wing_2_feather"]["o"].x)
bird_sh = by_name["left_wing_shoulder"]["o"]
SCALE = (tip_x - 0.02) / bird_tip_x
# смещение арматуры: плечи птицы (×SCALE) кладём в корень крыльев пони
T = Vector((0.0, root_c.y - bird_sh.y * SCALE, root_c.z - bird_sh.z * SCALE))
print(f"[wings] размах пони {tip_x:.3f}, птицы {bird_tip_x:.3f} → SCALE={SCALE:.3f}; корень крыльев {tuple(round(c, 3) for c in root_c)}; T={tuple(round(c, 3) for c in T)}")

# --------------------------------------------------------------- арматура
arm_data = bpy.data.armatures.new(ARM_NAME)
arm = bpy.data.objects.new(ARM_NAME, arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
children = {}
for b in bones:
    children.setdefault(b["parent"], []).append(b)
edit = {}
for b in bones:
    eb = arm_data.edit_bones.new(b["name"])
    o = b["o"]
    kids = children.get(b["i"], [])
    length = min(((k["o"] - b["o"]).length for k in kids), default=0.03)
    length = max(length, 0.01)
    X, Y, Z = -b["f"], b["s"], b["u"]
    eb.matrix = Matrix((
        (X.x, Y.x, Z.x, o.x),
        (X.y, Y.y, Z.y, o.y),
        (X.z, Y.z, Z.z, o.z),
        (0, 0, 0, 1)))
    eb.length = length
    edit[b["name"]] = eb
for b in bones:
    if b["parent"] >= 0:
        edit[b["name"]].parent = edit[bones[b["parent"]]["name"]]
bpy.ops.object.mode_set(mode="OBJECT")

# --------------------------------------------------------------- копия меша и веса
mesh_copy = wings.data.copy()
ob = bpy.data.objects.new(MESH_NAME, mesh_copy)
bpy.context.scene.collection.objects.link(ob)
ob.matrix_world = Matrix.Identity(4)
mesh_copy.transform(W)  # в мировые координаты (как лежат на пони)
# в пространство птицы: (v - T) / SCALE
mesh_copy.transform(Matrix.Translation(-T))
mesh_copy.transform(Matrix.Scale(1.0 / SCALE, 4))
for vg in list(ob.vertex_groups):
    ob.vertex_groups.remove(vg)
ob.modifiers.clear()
segs = {}
for side, chain in CHAINS.items():
    s = []
    for i, name in enumerate(chain):
        b = by_name[name]
        head = b["o"]
        nxt = by_name[chain[i + 1]]["o"] if i + 1 < len(chain) else head + b["s"] * 0.05
        s.append((name, head, nxt))
    segs[side] = s
groups = {name: ob.vertex_groups.new(name=name) for chain in CHAINS.values() for name in chain}


def seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


stats = {}
for v in mesh_copy.vertices:
    p = v.co
    # Движок зеркалит геометрию скинованного меша по X относительно скелета (см. память
    # equestria-bannerlord-mod: вершины с -X — на правые кости): без обмена сторон каждое крыло
    # вращалось вокруг плеча противоположной стороны (10.10.2026).
    side = "right" if p.x >= 0 else "left"
    d = sorted(((seg_dist(p, a, b), name) for name, a, b in segs[side]))
    (d0, n0) = d[0]
    (d1, n1) = d[1] if len(d) > 1 else (1e9, n0)
    if d1 - d0 < BLEND_DIST:
        w1 = 0.5 * (1.0 - (d1 - d0) / BLEND_DIST)
        groups[n0].add([v.index], 1.0 - w1, "REPLACE")
        groups[n1].add([v.index], w1, "REPLACE")
    else:
        groups[n0].add([v.index], 1.0, "REPLACE")
    stats[n0] = stats.get(n0, 0) + 1
print("[wings] вершин по костям:", stats)
mod = ob.modifiers.new("Armature", "ARMATURE")
mod.object = arm
ob.parent = arm
# Компенсация привязки (10.10.2026): при Z-up файле, совпадающем с движком, меш в игре оказался
# повёрнут к костям на 90° вокруг X (кости машут вверх-вниз, меш — назад-внутрь). Поворот одного
# меша давал параллельный сдвиг (движок компенсирует привязку вокруг начала каждой кости), поэтому
# поворачиваем ВЕСЬ риг — арматуру с мешем-потомком — через трансформ объекта арматуры (корневой
# узел FBX редактор берёт 1:1, как и у human_skeleton.fbx с его PreRotation (90,0,0)).
RIG_FIX_X_DEG = 90.0
arm.matrix_world = Matrix.Rotation(math.radians(RIG_FIX_X_DEG), 4, "X")
ob.matrix_parent_inverse = Matrix.Identity(4)
ob.matrix_basis = Matrix.Identity(4)

# --------------------------------------------------------------- экспорт
os.makedirs(OUT_DIR, exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
# Z-up файл (axis_forward="Y", axis_up="Z"): как контейнер клипа позы (make_flight_pose.py). С
# экспортом по умолчанию (Y-up) кости в игре стояли верно, а МЕШ оказался повёрнут на 90° к ним
# (bind-матрицы в Y-up против Z-up скелета движка) — крылья махали вперёд (измерено 10.10.2026).
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP",
                         axis_forward="Y", axis_up="Z")
print(f"[wings] записан {OUT_FBX}; SCALE={SCALE:.4f} T={tuple(round(c, 4) for c in T)}")
