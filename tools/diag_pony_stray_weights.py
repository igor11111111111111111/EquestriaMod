# -*- coding: utf-8 -*-
"""Только чтение: ищет вершины, чей ДОМИНИРУЮЩИЙ вес приходится на кость, чья позиция в покое
далеко от самой вершины — то есть привязанные не к соседним костям, а к чему-то постороннему
(рука/нога/крыло у меша головы и т.п.). В отличие от diag_pony_neck_weights.py (сумма весов),
это ловит и вершины с суммой ровно 1.0, но не на той кости.

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\diag_pony_stray_weights.py
"""
import bpy
import mathutils

col = bpy.data.collections.get("Пони - цельная")
ARMATURE_NAME = "bip01_notused"
NAMES = ("eq_pony_head", "eq_pony_hair", "eq_pony_horn")
# Вершина дальше этого от своей доминирующей кости (в метрах) — подозрительна.
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
