# -*- coding: utf-8 -*-
"""Углубить корень крыла внутрь тела — щель между отдельными объектами (не дыра в одном меше).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_deepen_wing_plug.py

Тело и крыло — разные объекты, а не одна сетка со швом. У самого узкого ракурса плечо приоткрывает
щель между ними (замечено в игре и подтверждено рендером 27.09.2026: без крыльев тело целое, само
крыло целое, вместе — просвет). Двигаем вершины корня крыла ДОПОЛНИТЕЛЬНО внутрь, к позвоночнику,
чтобы запас перекрытия был больше на всех углах обзора.
"""
import bmesh
import bpy
from mathutils import Vector

ROOT_NEAR = 0.18     # вершины ближе этого к ключице считаются корнем
PUSH = 0.05          # на сколько дополнительно продвинуть внутрь (метры)

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
skel = bpy.data.objects["bip01_notused"]
SPINE_CHAIN = ("bip01_pelvis_0", "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
spine_pts = [skel.matrix_world @ b.head_local for b in [skel.data.bones[n] for n in SPINE_CHAIN]]
SPINE_LINE = list(zip(spine_pts[:-1], spine_pts[1:]))
clav = {}
for side, bone in (("l", "bip01_l_clavicle_14"), ("r", "bip01_r_clavicle_21")):
    b = skel.data.bones[bone]
    clav[side] = skel.matrix_world @ ((b.head_local + b.tail_local) / 2)


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
moved = 0
for v in bm.verts:
    world = ob.matrix_world @ v.co
    side = "l" if v.co.x > 0 else "r"
    d = (world - clav[side]).length
    if d >= ROOT_NEAR:
        continue
    t = 1.0 - d / ROOT_NEAR
    t = t * t * (3 - 2 * t)
    inside = min((closest_on(world, a, b) for a, b in SPINE_LINE), key=lambda q: (q - world).length)
    step = inside - world
    if step.length > 1e-6:
        v.co += (v.co - (ob.matrix_world.inverted() @ world) + (ob.matrix_world.inverted() @ (world + step.normalized() * PUSH * t))) * 0 \
                 + ob.matrix_world.inverted().to_3x3() @ (step.normalized() * PUSH * t)
        moved += 1

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[plug] сдвинуто вершин корня:", moved)

bpy.ops.wm.save_mainfile()
print("[plug] сохранено")
