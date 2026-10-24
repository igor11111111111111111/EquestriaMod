# -*- coding: utf-8 -*-
"""Вычисляет, как редактор Bannerlord переводит локальные повороты костей из FBX в движок.

Входные данные:
  1. Дамп движка (Module/eq_exceptions.log, блок "ДАМП КОСТЕЙ"): для каждой кости entitialRest
     (rest-поза движка) и channel0 (как движок понял НАШ клип на канале 0) — фреймы в
     пространстве сущности, s/f/u = столбцы X/Y/Z.
  2. Исходный FBX скелета: PreRotation каждой кости = что реально лежит в нашем файле как
     локальный поворот (у непозированных костей; проверено tools/dump_fbx_prerotation.py).

Для каждой кости считаем parent-relative повороты: L_k = ch0_parent^-1 * ch0_k (как движок
ПОНЯЛ файл) и R_k = rest_parent^-1 * rest_k (как ДОЛЖНО быть). Гипотеза: движок применяет к
FBX-повороту P_k фиксированную смену базиса C (одна на все кости): L_k = C^-1 * P_k * C.
Перебираем все 24 правильных знаковых перестановки осей C и смотрим суммарную ошибку.
Если находится C с ошибкой ~0 — модель верна, и нужный нам FBX-поворот для любой целевой
локальной позы T_k (в осях движка) равен X_k = C * T_k * C^-1.

Запуск: blender --background --factory-startup --python tools/solve_bone_axes.py -- <log> <skeleton.fbx>
"""
import itertools
import math
import re
import sys

from io_scene_fbx import parse_fbx
from mathutils import Euler, Matrix, Vector

log_path, fbx_path = sys.argv[sys.argv.index("--") + 1:][:2]

# ---------------------------------------------------------------- дамп движка (последний блок)
text = open(log_path, encoding="utf-8", errors="replace").read()
block = text[text.rfind("ДАМП КОСТЕЙ"):]
vec = r"\(([-\d.]+),([-\d.]+),([-\d.]+)\)"
bone_re = re.compile(r"\[(\d+)\] (\S+) parent=(-?\d+)")
frame_re = re.compile(r"(localRest|entitialRest|entitialNow|channel0)\s+o=" + vec + r" f=" + vec + r" s=" + vec + r" u=" + vec)

bones = []  # (index, name, parent, {frames})
cur = None
for line in block.splitlines():
    m = bone_re.search(line)
    if m:
        cur = {"i": int(m.group(1)), "name": m.group(2), "parent": int(m.group(3))}
        bones.append(cur)
        continue
    m = frame_re.search(line)
    if m and cur is not None:
        nums = [float(x) for x in m.groups()[1:]]
        o, f, s, u = (Vector(nums[0:3]), Vector(nums[3:6]), Vector(nums[6:9]), Vector(nums[9:12]))
        rot = Matrix((s, f, u)).transposed()  # столбцы s,f,u = X,Y,Z
        cur[m.group(1)] = (o, rot)
print(f"костей в дампе: {len(bones)}")


def rel(frames_key, b):
    """parent-relative поворот кости b по фреймам frames_key."""
    rot = b[frames_key][1]
    if b["parent"] < 0:
        return rot
    parent = bones[b["parent"]]
    return parent[frames_key][1].inverted() @ rot


# ---------------------------------------------------------------- PreRotation из FBX (по имени)
root, _ = parse_fbx.parse(fbx_path)
objects = next(e for e in root.elems if e.id == b"Objects")
pre = {}
for m in objects.elems:
    if m.id != b"Model":
        continue
    name = m.props[1].decode(errors="replace").split("\x00")[0]
    for e in m.elems:
        if e.id == b"Properties70":
            for p in e.elems:
                if p.id == b"P" and p.props[0] == b"PreRotation":
                    pre[name] = Euler(tuple(math.radians(float(x)) for x in p.props[4:7]), "XYZ").to_matrix()
# имена движка без "bip01_" и без индекса: pelvis, l_thigh, spine...
def fbx_name_for(engine_name):
    for n in pre:
        core = re.sub(r"^bip01_", "", n)
        core = re.sub(r"_\d+$", "", core)
        if core == engine_name:
            return n
    return None


# ---------------------------------------------------------------- перебор C
axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
candidates = []
for perm in itertools.permutations(range(3)):
    for signs in itertools.product((1, -1), repeat=3):
        cols = [axes[perm[i]] * signs[i] for i in range(3)]
        C = Matrix(cols).transposed()
        if abs(C.determinant() - 1.0) < 1e-6:
            candidates.append(C)
print(f"кандидатов C: {len(candidates)}")

usable = [b for b in bones if b["parent"] >= 0 and fbx_name_for(b["name"]) and "channel0" in b]
# берём только непозированные кости (руки мы крутили): исключаем upperarm_twist/foretwist
usable = [b for b in usable if not re.search(r"upperarm_twist$|foretwist$", b["name"])]
print("кости для подбора:", [b["name"] for b in usable])


def angle_between(A, B):
    d = A.inverted() @ B
    c = max(-1.0, min(1.0, (d[0][0] + d[1][1] + d[2][2] - 1.0) / 2.0))
    return math.degrees(math.acos(c))


results = []
for C in candidates:
    Ci = C.inverted()
    err = 0.0
    worst = 0.0
    for b in usable:
        L = rel("channel0", b)
        P = pre[fbx_name_for(b["name"])]
        a = angle_between(L, Ci @ P @ C)
        err += a
        worst = max(worst, a)
    results.append((err, worst, C))
results.sort(key=lambda t: t[0])
for err, worst, C in results[:5]:
    print(f"C={[list(map(int, map(round, row))) for row in C]} суммарная ошибка={err:0.1f}° макс={worst:0.1f}°")

best = results[0][2]
print("\nПРОВЕРКА ПО КОСТЯМ для лучшего C (угол между L_k и C^-1 P_k C), и сравнение rest движка:")
for b in usable:
    L = rel("channel0", b)
    R = rel("entitialRest", b)
    P = pre[fbx_name_for(b["name"])]
    print(f"  {b['name']:18s} L vs C^-1PC: {angle_between(L, best.inverted() @ P @ best):6.1f}°   "
          f"R(rest движка) vs L(наш клип): {angle_between(R, L):6.1f}°")
