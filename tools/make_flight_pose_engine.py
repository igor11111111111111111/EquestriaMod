# -*- coding: utf-8 -*-
"""Builds the flight pose FBX DIRECTLY on the engine's rest pose, bypassing a Blender armature.

WHY (10.10.2026, see tools/solve_bone_axes.py and equestria-flight-scroll.md): the Bannerlord
editor takes the bones' parent-relative rotations from the FBX VERBATIM (basis change C = identity,
error < 2.4° on all bones), but the engine's rest pose does NOT match the PreRotation from
modding_resources/human_skeleton.fbx (the neck differs by 180°, the spine ~120°, the thigh 154°,
the clavicles 91°). Any animation built on that FBX skeleton gets these differences in game,
hence "body turned around, head normal" with any export axes. So the rest is taken from the
engine dump (EquestriaFlightScroll.DumpBones → Module/eq_exceptions.log, "bone dump",
entitialRest), and our deltas are set in entity space and converted into the bone's local axes.

For each bone k:  X_k = R_k * D_k,  R_k = E_parent^-1 * E_k (engine rest, parent-relative),
D_k = E_k^-1 * W_k * E_k, where W_k is the desired bone rotation in entity space (Z up,
+Y forward, +X right from the point of view of a camera behind the back... signs are checked by preview/game).
X_k is written as an absolute Lcl Rotation (PreRotation=0) and into all keys of the R curves.

The container is any Blender export of the same skeleton (nodes/curves/links are needed). The file is made
Z-up with an identity root: then the pelvis's parent = world and its local rotation = entitialRest.

Run:
    blender --background --factory-startup --python tools/make_flight_pose_engine.py -- \
        <eq_exceptions.log with the dump> <container.fbx from Blender> <output.fbx>
"""
import math
import re
import sys

from io_scene_fbx import encode_bin, parse_fbx
from mathutils import Euler, Matrix, Vector

log_path, src_path, out_path = sys.argv[sys.argv.index("--") + 1:][:3]

# ---------------------------------------------------------------- desired pose (entity space)
# In the engine rest the left arm points left-down (entitialRest l_upperarm_twist s≈(-0.83,0,-0.55)),
# the right one mirrored. We raise it to horizontal by rotating around the Y axis (forward) and bring it
# slightly forward by rotating around Z (up). The forearm additionally goes slightly forward.
ARM_LIFT_DEG = -30.0     # around entity Y: left +, right -; arms rest ~33° below horizontal, -50 = almost along the body
ARM_FORWARD_DEG = 40.0   # around entity Z: left -, right +; positive = forward (10.10.2026: arms at the sides, slightly forward)
FOREARM_FORWARD_DEG = 30.0
# Arm sway while walking: frame 1 (Source1) is the base pose, frame 250 (Source2) has the arms
# slightly higher and forward. The code (EquestriaFlightScroll) keeps the clip speed at 0 and drives the progress
# 0..1 back and forth only while the agent walks; standing, progress is 0 (the base pose).
ARM_SWAY_LIFT_DEG = 5.0
ARM_SWAY_FORWARD_DEG = 6.0
HEAD_DOWN_DEG = 10.0     # head slightly down (around entity X; minus = crown forward)
THIGH_SWAY_DEG = 6.0     # the legs sway too (10.10.2026)
CALF_SWAY_DEG = 10.0
LAST_FRAME = 250.0
# Legs "like a genie's" (10.10.2026): the thigh is swung back and inward (crossed), the knee bent
# back. The thigh/calf bone points down (-Z) in rest: rotating around entity X by -θ takes it
# back (-Y), around Y by -θ to the right (+X), i.e. the left leg toward the right one.
THIGH_BACK_DEG = 35.0
THIGH_CROSS_DEG = 15.0   # around entity Y: left -, right +
CALF_BACK_DEG = 70.0     # on top of the thigh rotation (a child bone's delta adds to the parent's)


def rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, axis)


def world_delta(frame):
    """Desired bone rotations (entity space) for frame `frame` (1..LAST_FRAME)."""
    s = max(0.0, min(1.0, (frame - 1.0) / (LAST_FRAME - 1.0)))  # 0 = base, 1 = arms moved
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

# ---------------------------------------------------------------- engine dump
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
        cur["E"] = Matrix((s, f, u)).transposed()  # columns X,Y,Z
if len(bones) < 28 or any("E" not in b for b in bones):
    raise RuntimeError("дамп движка не найден или неполный — сначала запусти игру со свитком")
print(f"[engine-pose] костей из дампа: {len(bones)}")

by_engine_name = {b["name"]: b for b in bones}


def engine_name_of(fbx_name):
    core = re.sub(r"^bip01_", "", fbx_name)
    core = re.sub(r"_\d+$", "", core)
    return core if core in by_engine_name else None


# ---------------------------------------------------------------- container
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
    """euler_fn(s) -> XYZ Euler angles in degrees for normalized time s (0 = first key,
    1 = last); Lcl Rotation = euler_fn(0), curve keys by their own time."""
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


# the file is Z-up (the container must be exported with axis_up="Z"); the root is identity
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
        continue  # *_nub_notused: the engine ignores them
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

# ---------------------------------------------------------------- rebuild
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
