# -*- coding: utf-8 -*-
"""Собирает FBX позы полёта ПРЯМО на rest-позе движка, минуя Blender-арматуру.

ПОЧЕМУ (10.10.2026, см. tools/solve_bone_axes.py и equestria-flight-scroll.md): редактор
Bannerlord берёт parent-relative повороты костей из FBX ДОСЛОВНО (смена базиса C = identity,
ошибка < 2.4° на всех костях), но rest-поза движка НЕ совпадает с PreRotation из
modding_resources/human_skeleton.fbx (шея расходится на 180°, позвоночник ~120°, бедро 154°,
ключицы 91°). Любая анимация, собранная на том FBX-скелете, в игре получает эти расхождения —
отсюда "тело развёрнуто, голова нормальная" при любых осях экспорта. Поэтому rest берём из
дампа движка (EquestriaFlightScroll.DumpBones → Module/eq_exceptions.log, "ДАМП КОСТЕЙ",
entitialRest), а наши дельты задаём в пространстве сущности и переводим в локальные оси кости.

Для каждой кости k:  X_k = R_k * D_k,  R_k = E_parent^-1 * E_k (rest движка, parent-relative),
D_k = E_k^-1 * W_k * E_k, где W_k — желаемый поворот кости в пространстве сущности (Z вверх,
+Y вперёд, +X вправо с точки зрения камеры за спиной... знаки проверяются превью/игрой).
X_k пишется как абсолютный Lcl Rotation (PreRotation=0) и во все ключи кривых R.

Контейнер — любой экспорт Blender того же скелета (нужны узлы/кривые/связи). Файл делаем
Z-up с единичным корнем: тогда у таза parent = мир и его локальный поворот = entitialRest.

Запуск:
    blender --background --factory-startup --python tools/make_flight_pose_engine.py -- \
        <eq_exceptions.log с дампом> <контейнер.fbx из Blender> <выход.fbx>
"""
import math
import re
import sys

from io_scene_fbx import encode_bin, parse_fbx
from mathutils import Euler, Matrix, Vector

log_path, src_path, out_path = sys.argv[sys.argv.index("--") + 1:][:3]

# ---------------------------------------------------------------- желаемая поза (пространство сущности)
# Левая рука у движка в rest смотрит влево-вниз (entitialRest l_upperarm_twist s≈(-0.83,0,-0.55)),
# правая — зеркально. Поднимаем до горизонтали поворотом вокруг оси Y (вперёд) и чуть выводим
# вперёд поворотом вокруг Z (вверх). Предплечье дополнительно слегка вперёд.
ARM_LIFT_DEG = -30.0     # вокруг entity Y: левая +, правая -; rest рук ~33° ниже горизонтали, -50 = почти вдоль тела
ARM_FORWARD_DEG = 40.0   # вокруг entity Z: левая -, правая +; положительно = вперёд (10.10.2026: руки по бокам, чуть вперёд)
FOREARM_FORWARD_DEG = 30.0
# Покачивание рук при ходьбе: кадр 1 (Source1) — базовая поза, кадр 250 (Source2) — руки
# чуть выше и вперёд. Код (EquestriaFlightScroll) держит скорость клипа 0 и гоняет прогресс
# 0..1 туда-обратно только пока агент идёт; стоя — прогресс 0 (базовая поза).
ARM_SWAY_LIFT_DEG = 5.0
ARM_SWAY_FORWARD_DEG = 6.0
HEAD_DOWN_DEG = 10.0     # голова чуть вниз (вокруг entity X; минус = макушка вперёд)
THIGH_SWAY_DEG = 6.0     # ноги тоже покачиваются (10.10.2026)
CALF_SWAY_DEG = 10.0
LAST_FRAME = 250.0
# Ноги "как у джинна" (10.10.2026): бедро отведено назад и внутрь (накрест), колено согнуто
# назад. Кость бедра/голени в rest смотрит вниз (-Z): поворот вокруг entity X на -θ уводит её
# назад (-Y), вокруг Y на -θ — вправо (+X), т.е. левую ногу к правой.
THIGH_BACK_DEG = 35.0
THIGH_CROSS_DEG = 15.0   # вокруг entity Y: левая -, правая +
CALF_BACK_DEG = 70.0     # сверх поворота бедра (дельта дочерней кости складывается с родительской)


def rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, axis)


def world_delta(frame):
    """Желаемые повороты костей (пространство сущности) для кадра frame (1..LAST_FRAME)."""
    s = max(0.0, min(1.0, (frame - 1.0) / (LAST_FRAME - 1.0)))  # 0 — база, 1 — руки сдвинуты
    lift = ARM_LIFT_DEG + ARM_SWAY_LIFT_DEG * s
    fwd = ARM_FORWARD_DEG + ARM_SWAY_FORWARD_DEG * s
    thigh_back = THIGH_BACK_DEG + THIGH_SWAY_DEG * s
    calf_back = CALF_BACK_DEG + CALF_SWAY_DEG * s
    return {
        "l_upperarm_twist": rot("Z", -fwd) @ rot("Y", lift),
        "r_upperarm_twist": rot("Z", fwd) @ rot("Y", -lift),
        "head": rot("X", -HEAD_DOWN_DEG),
        "l_foretwist": rot("Z", -FOREARM_FORWARD_DEG),
        "r_foretwist": rot("Z", FOREARM_FORWARD_DEG),
        "l_thigh": rot("Y", -THIGH_CROSS_DEG) @ rot("X", -thigh_back),
        "r_thigh": rot("Y", THIGH_CROSS_DEG) @ rot("X", -thigh_back),
        "l_calf": rot("X", -calf_back),
        "r_calf": rot("X", -calf_back),
    }


WORLD_DELTA = world_delta(1.0)

# ---------------------------------------------------------------- дамп движка
text = open(log_path, encoding="utf-8", errors="replace").read()
block = text[text.rfind("ДАМП КОСТЕЙ"):]
vec = r"\(([-\d.]+),([-\d.]+),([-\d.]+)\)"
bone_re = re.compile(r"\[(\d+)\] (\S+) parent=(-?\d+)")
rest_re = re.compile(r"entitialRest\s+o=" + vec + r" f=" + vec + r" s=" + vec + r" u=" + vec)
bones = []
cur = None
for line in block.splitlines():
    m = bone_re.search(line)
    if m:
        cur = {"i": int(m.group(1)), "name": m.group(2), "parent": int(m.group(3))}
        bones.append(cur)
        continue
    m = rest_re.search(line)
    if m and cur is not None and "E" not in cur:
        nums = [float(x) for x in m.groups()]
        f, s, u = Vector(nums[3:6]), Vector(nums[6:9]), Vector(nums[9:12])
        cur["E"] = Matrix((s, f, u)).transposed()  # столбцы X,Y,Z
if len(bones) < 28 or any("E" not in b for b in bones):
    raise RuntimeError("дамп движка не найден или неполный — сначала запусти игру со свитком")
print(f"[engine-pose] костей из дампа: {len(bones)}")

by_engine_name = {b["name"]: b for b in bones}


def engine_name_of(fbx_name):
    core = re.sub(r"^bip01_", "", fbx_name)
    core = re.sub(r"_\d+$", "", core)
    return core if core in by_engine_name else None


# ---------------------------------------------------------------- контейнер
root, version = parse_fbx.parse(src_path)
objects = next(e for e in root.elems if e.id == b"Objects")
connections = next(e for e in root.elems if e.id == b"Connections")
header = next(e for e in root.elems if e.id == b"GlobalSettings")

models_by_id = {m.props[0]: m for m in objects.elems if m.id == b"Model"}
curve_nodes_by_id = {m.props[0]: m for m in objects.elems if m.id == b"AnimationCurveNode"}
curves_by_id = {m.props[0]: m for m in objects.elems if m.id == b"AnimationCurve"}
rot_node_of_model, curves_of_node = {}, {}
for c in connections.elems:
    if c.id != b"C" or c.props[0] != b"OP":
        continue
    child_id, parent_id, prop_name = c.props[1], c.props[2], c.props[3]
    if parent_id in models_by_id and child_id in curve_nodes_by_id and prop_name == b"Lcl Rotation":
        rot_node_of_model[parent_id] = curve_nodes_by_id[child_id]
    elif parent_id in curve_nodes_by_id and child_id in curves_by_id:
        curves_of_node.setdefault(parent_id, {})[prop_name.decode()] = curves_by_id[child_id]


def node_name(model):
    return model.props[1].decode(errors="replace").split("\x00")[0]


def prop(elem, name):
    for e in elem.elems:
        if e.id == b"Properties70":
            for p in e.elems:
                if p.id == b"P" and p.props[0] == name.encode():
                    return p
    return None


def set_rotation(model_id, model, euler_fn):
    """euler_fn(s) -> эйлеры XYZ в градусах для нормированного времени s (0 — первый ключ,
    1 — последний); Lcl Rotation = euler_fn(0), ключи кривых — по своему времени."""
    base = euler_fn(0.0)
    p = prop(model, "Lcl Rotation")
    if p is not None:
        for i in range(3):
            p.props[4 + i] = float(base[i])
    p = prop(model, "PreRotation")
    if p is not None:
        for i in range(3):
            p.props[4 + i] = 0.0
    node = rot_node_of_model.get(model_id)
    if node is None:
        return
    curves = curves_of_node.get(node.props[0], {})
    for axis_i, axis_name in enumerate(("d|X", "d|Y", "d|Z")):
        c = curves.get(axis_name)
        if c is not None:
            times = next(e for e in c.elems if e.id == b"KeyTime").props[0]
            vals = next(e for e in c.elems if e.id == b"KeyValueFloat").props[0]
            t0, t1 = times[0], times[-1]
            for k in range(len(vals)):
                s = 0.0 if t1 == t0 else (times[k] - t0) / float(t1 - t0)
                vals[k] = float(euler_fn(s)[axis_i])
        p = prop(node, axis_name)
        if p is not None:
            p.props[4] = float(base[axis_i])


# файл Z-up (контейнер должен быть экспортирован с axis_up="Z"); корень — единичный
up = prop(header, "UpAxis")
if up is not None and int(up.props[4]) != 2:
    raise RuntimeError("контейнер должен быть Z-up (экспорт Blender с axis_forward='Y', axis_up='Z')")

done = 0
for model_id, model in models_by_id.items():
    name = node_name(model)
    if name == "bip01_notused":
        set_rotation(model_id, model, lambda s: (0.0, 0.0, 0.0))
        continue
    en = engine_name_of(name)
    if en is None:
        continue  # *_nub_notused — движок их игнорирует
    b = by_engine_name[en]
    E = b["E"]
    Ep = bones[b["parent"]]["E"] if b["parent"] >= 0 else Matrix.Identity(3)
    R = Ep.inverted() @ E

    def euler_at(s, E=E, R=R, en=en):
        W = world_delta(1.0 + s * (LAST_FRAME - 1.0)).get(en, Matrix.Identity(3))
        X = R @ (E.inverted() @ W @ E)
        return tuple(math.degrees(a) for a in X.to_euler("XYZ"))

    deg = euler_at(0.0)
    set_rotation(model_id, model, euler_at)
    done += 1
    tag = " <- поза" if en in WORLD_DELTA else ""
    print(f"[engine-pose] {name:28s} X={tuple(round(a, 2) for a in deg)}{tag}")
print(f"[engine-pose] записано костей: {done}")

# ---------------------------------------------------------------- пересборка
ADD = {
    b"C"[0]: "add_char", b"Y"[0]: "add_int16", b"B"[0]: "add_bool", b"Z"[0]: "add_int8",
    b"I"[0]: "add_int32", b"L"[0]: "add_int64", b"F"[0]: "add_float32", b"D"[0]: "add_float64",
    b"R"[0]: "add_bytes", b"S"[0]: "add_string",
    b"b"[0]: "add_bool_array", b"c"[0]: "add_byte_array", b"i"[0]: "add_int32_array",
    b"l"[0]: "add_int64_array", b"f"[0]: "add_float32_array", b"d"[0]: "add_float64_array",
}


def convert(src):
    dst = encode_bin.FBXElem(src.id)
    for value, code in zip(src.props, src.props_type):
        if code == b"B"[0]:
            value = bool(value)
        elif code in (b"I"[0], b"L"[0], b"Y"[0], b"Z"[0]):
            value = int(value)
        elif code in (b"F"[0], b"D"[0]):
            value = float(value)
        elif code == b"C"[0] and not isinstance(value, bytes):
            value = bytes([value])
        getattr(dst, ADD[code])(value)
    for child in src.elems:
        dst.elems.append(convert(child))
    return dst


out_root = encode_bin.FBXElem(b"")
for child in root.elems:
    out_root.elems.append(convert(child))
encode_bin.write(out_path, out_root, version)
print(f"[engine-pose] записано {out_path}")
