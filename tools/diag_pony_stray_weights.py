# -*- coding: utf-8 -*-
"""Read-only: finds vertices whose DOMINANT weight falls on a bone whose rest position is
far from the vertex itself, i.e. bound not to neighbouring bones but to something unrelated
(an arm/leg/wing on the head mesh, etc.). Unlike diag_pony_neck_weights.py (weight sum),
this also catches vertices with a sum of exactly 1.0 but on the wrong bone.

Run:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\diag_pony_stray_weights.py
"""
import bpy
import mathutils

col = bpy.data.collections.get("Пони - цельная")
ARMATURE_NAME = "bip01_notused"
NAMES = ("eq_pony_head", "eq_pony_hair", "eq_pony_horn")
# A vertex farther than this from its dominant bone (in metres) is suspicious.
THRESHOLD = 0.25


def bone_world_points(armature):
    pts = {}
    for bone in armature.data.bones:
        head = armature.matrix_world @ bone.head_local
        tail = armature.matrix_world @ bone.tail_local
        pts[bone.name] = (head, tail)
    return pts


arm = bpy.data.objects.get(ARMATURE_NAME)
if arm is None:
    raise SystemExit(ARMATURE_NAME + " не найден")
bones = bone_world_points(arm)


def check(name):
    ob = col.objects.get(name) if col else bpy.data.objects.get(name)
    if ob is None:
        print(f"[diag] {name}: НЕ НАЙДЕН")
        return
    groups = {vg.index: vg.name for vg in ob.vertex_groups}
    flagged = []
    for v in ob.data.vertices:
        if not v.groups:
            continue
        dom = max(v.groups, key=lambda g: g.weight)
        bone_name = groups.get(dom.group)
        if bone_name not in bones:
            continue
        world_co = ob.matrix_world @ v.co
        head, tail = bones[bone_name]
        d = min((world_co - head).length, (world_co - tail).length)
        if d > THRESHOLD:
            flagged.append((v.index, bone_name, dom.weight, d, tuple(v.co)))
    print(f"[diag] {name}: вершин {len(ob.data.vertices)}, с далёкой доминирующей костью {len(flagged)}")
    flagged.sort(key=lambda x: -x[3])
    for idx, bone_name, w, d, co in flagged[:30]:
        print(f"[diag]   вершина {idx}: кость={bone_name} вес={w:.2f} расстояние={d:.3f} позиция={co}")


for n in NAMES:
    check(n)
