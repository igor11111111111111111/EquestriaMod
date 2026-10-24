# -*- coding: utf-8 -*-
"""Пересчёт весов руки в assets/pony/eq_pony_edit.blend: кольцо вершин рвалось винтом при повороте.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_arm_twist.py

Причина: старый вес считался по |X| — прямой координате, а рука висит не строго вдоль оси X,
а под наклоном вниз. Одно и то же ПОПЕРЕЧНОЕ кольцо вершин вокруг руки (перёд и зад по кругу)
из-за наклона оказывалось на разном |X| и получало вес РАЗНЫХ костей — при повороте плеча
половина кольца ещё держалась за старую кость, половина уже перешла на соседнюю, и кольцо рвалось
винтом (видно в редакторе 27.09.2026). Здесь вес вершин руки на eq_pony_body пересчитан по
проекции на настоящую 3D-ось руки (от плеча до кисти) — одно и то же значение для всех вершин
истинного среза, кольцо гнётся, а не рвётся.
"""
import bpy
from mathutils import Vector

skel = bpy.data.objects["bip01_notused"]
body = bpy.data.collections["Пони - цельная"].objects["eq_pony_body"]


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    return [b.name for b in chain], [skel.matrix_world @ ((b.head_local + b.tail_local) / 2) for b in chain]


CHAINS = {}
for side, sign in (("l", 1.0), ("r", -1.0)):
    names, mids = arm_chain(side)
    origin = mids[0]
    axis = (mids[-1] - origin)
    axis = axis / axis.length
    us = [(name, (pos - origin).dot(axis)) for name, pos in zip(names, mids)]
    CHAINS[sign] = (origin, axis, us)

ARM_BONE_NAMES = {name for chain in CHAINS.values() for name, _ in chain[2]}
group_index = {g.index: g.name for g in body.vertex_groups}

targets = []
for v in body.data.vertices:
    if any(group_index[g.group] in ARM_BONE_NAMES and g.weight > 0.02 for g in v.groups):
        targets.append(v.index)
print("[armtwist] вершин руки для пересчёта:", len(targets))

for i in targets:
    v = body.data.vertices[i]
    p = Vector((body.matrix_world @ v.co)[:])
    sign = 1.0 if p.x > 0 else -1.0
    origin, axis, chain = CHAINS[sign]
    u = (p - origin).dot(axis)
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
    for g in list(v.groups):
        name = group_index[g.group]
        if name in ARM_BONE_NAMES:
            body.vertex_groups[name].remove([i])
    for name, w in along.items():
        body.vertex_groups[name].add([i], w, "REPLACE")

bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
bpy.ops.wm.save_mainfile()
print("[armtwist] сохранено")
