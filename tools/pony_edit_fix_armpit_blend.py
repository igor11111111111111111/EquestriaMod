# -*- coding: utf-8 -*-
"""Пересчитать переход «вес тела -> вес руки» по правильной оси руки, не по |X|.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_armpit_blend.py

Раньше при повороте плеча один "along" (какую кость руки брать) был исправлен по проекции на
истинную ось руки (см. pony_edit_fix_arm_twist.py), а вот "s" — долю, на которую вес вообще
уходит от туловища к руке — я оставил по сырому |X|. У низа подмышки при том же |X| ось руки уже
дальше от тела, чем сверху (рука висит под углом), поэтому там переход начинался раньше — и рука
при взмахе «затягивалась» внутрь именно снизу (замечено в игре 27.09.2026). Здесь оба фактора
считаются одинаково — по проекции на ось, — и зона выбирается по расстоянию до самой оси, а не
по тому, что вершина уже как-то весит на кости руки.
"""
import bpy
from mathutils import Vector

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_body"]
skel = bpy.data.objects["bip01_notused"]

ARM_WEIGHT_FROM = 0.20
ARM_WEIGHT_BLEND = 0.12
RADIUS = 0.16          # дальше этого от оси руки — не рука, не трогаем


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    return [(b.name, skel.matrix_world @ ((b.head_local + b.tail_local) / 2)) for b in chain]


CHAINS = {}
for sign, side in ((1.0, "l"), (-1.0, "r")):
    chain = arm_chain(side)
    origin = chain[0][1]
    axis = (chain[-1][1] - origin)
    axis = axis / axis.length
    us = [(name, (pos - origin).dot(axis)) for name, pos in chain]
    CHAINS[sign] = (origin, axis, us)

names_by_index = {g.index: g.name for g in ob.vertex_groups}
TORSO_BONES = {"bip01_pelvis_0", "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12"}
ARM_BONE_NAMES = {n for chain in CHAINS.values() for n, _ in chain[2]}

touched = 0
for v in ob.data.vertices:
    p = ob.matrix_world @ v.co
    # сторону берём по тому, к какой ключице физически ближе — знак локальной координаты
    # ненадёжен: у объекта нетривиальный transform (отрицательный масштаб + поворот)
    sign = min(CHAINS, key=lambda s: (p - CHAINS[s][0]).length)
    origin, axis, chain = CHAINS[sign]
    rel = p - origin
    u = rel.dot(axis)
    perp = (rel - axis * u).length
    if perp > RADIUS or u < -0.05 or u > chain[-1][1] + 0.05:
        continue
    # своя доля веса от туловища у самого начала цепочки (та, что уже есть в других группах
    # помимо цепочки руки) — считаем один раз, до перезаписи
    old = {names_by_index[g.group]: g.weight for g in v.groups if names_by_index[g.group] not in ARM_BONE_NAMES}
    s = min(1.0, max(0.0, (u - ARM_WEIGHT_FROM) / ARM_WEIGHT_BLEND))
    s = s * s * (3 - 2 * s)
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
        if names_by_index[g.group] in ARM_BONE_NAMES:
            ob.vertex_groups[names_by_index[g.group]].remove([v.index])
    new_total = {}
    for name_g, w in old.items():
        new_total[name_g] = new_total.get(name_g, 0.0) + w * (1.0 - s)
    for name_g, w in along.items():
        new_total[name_g] = new_total.get(name_g, 0.0) + w * s
    for name_g, w in new_total.items():
        grp = ob.vertex_groups.get(name_g) or ob.vertex_groups.new(name=name_g)
        grp.add([v.index], w, "REPLACE")
    touched += 1

print("[armpitblend] пересчитано вершин:", touched)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
bpy.ops.wm.save_mainfile()
print("[armpitblend] сохранено")
