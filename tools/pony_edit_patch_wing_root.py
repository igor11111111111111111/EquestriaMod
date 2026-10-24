# -*- coding: utf-8 -*-
"""Залатать мелкие незашитые дыры у корня крыла (заглушка, что уходит внутрь тела).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_patch_wing_root.py

При последней перекройке крыла «юбка»-заглушка у корня осталась не до конца зашитой — видно
сквозь неё в игре даже в позе покоя (замечено 27.09.2026, не связано с весами). Здесь ищем все
мелкие незашитые контуры (не сам свободный край перепонки крыла — тот большой и его трогать
нельзя) рядом с ключицей и зашиваем их полигонами.
"""
import bmesh
import bpy
from mathutils import Vector

MAX_EDGES = 20      # контур крупнее — уже свободный край перепонки, не трогаем
MAX_DIST = 0.35      # дальше этого от ключицы — не корень крыла

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
skel = bpy.data.objects["bip01_notused"]
clav = {}
for side, bone in (("l", "bip01_l_clavicle_14"), ("r", "bip01_r_clavicle_21")):
    b = skel.data.bones[bone]
    clav[side] = skel.matrix_world @ ((b.head_local + b.tail_local) / 2)

bm = bmesh.new()
bm.from_mesh(ob.data)
uv = bm.loops.layers.uv.active

seen = set()
patched_faces = []
for start in [e for e in bm.edges if len(e.link_faces) == 1]:
    if start in seen:
        continue
    stack, loop_edges = [start], []
    seen.add(start)
    while stack:
        cur = stack.pop()
        loop_edges.append(cur)
        for v in cur.verts:
            for e in v.link_edges:
                if len(e.link_faces) == 1 and e not in seen:
                    seen.add(e)
                    stack.append(e)
    verts = {v for e in loop_edges for v in e.verts}
    if len(verts) < 3 or len(loop_edges) > MAX_EDGES:
        continue
    centre = Vector((0, 0, 0))
    for v in verts:
        centre += ob.matrix_world @ v.co
    centre /= len(verts)
    d = min((centre - c).length for c in clav.values())
    if d > MAX_DIST:
        continue
    was = set(bm.faces)
    try:
        bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
    except RuntimeError:
        bmesh.ops.holes_fill(bm, edges=loop_edges, sides=0)
    patch = [f for f in bm.faces if f not in was]
    for f in patch:
        for lp in f.loops:
            near = next((l for l in lp.vert.link_loops if l.face not in patch), None)
            if near and uv is not None:
                lp[uv].uv = near[uv].uv
    patched_faces.extend(patch)
    print("[patch] контур на %.3f м от ключицы, рёбер %d -> заделано %d граней" % (d, len(loop_edges), len(patch)))

if patched_faces:
    bmesh.ops.recalc_face_normals(bm, faces=patched_faces)
    centre_all = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    for f in patched_faces:
        if f.normal.dot(f.calc_center_median() - centre_all) < 0:
            f.normal_flip()

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[patch] всего заплаток:", len(patched_faces))

bpy.ops.wm.save_mainfile()
print("[patch] сохранено")
