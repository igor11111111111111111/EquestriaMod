# -*- coding: utf-8 -*-
"""Зашить мелкие V-образные щели у корня крыла — bmesh triangle_fill их не берёт (не замкнутый контур).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_close_notches.py
"""
import bmesh
import bpy
from mathutils import Vector

MAX_DIST = 0.35
ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
skel = bpy.data.objects["bip01_notused"]
clav = {}
for side, bone in (("l", "bip01_l_clavicle_14"), ("r", "bip01_r_clavicle_21")):
    b = skel.data.bones[bone]
    clav[side] = skel.matrix_world @ ((b.head_local + b.tail_local) / 2)

bm = bmesh.new()
bm.from_mesh(ob.data)
uv = bm.loops.layers.uv.active


def boundary_loops():
    seen = set()
    out = []
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
        out.append(loop_edges)
    return out


closed = 0
for _round in range(3):          # закрытие одной щели может обнажить соседнюю
    progress = False
    for loop_edges in boundary_loops():
        verts = {v for e in loop_edges for v in e.verts}
        if not (1 <= len(loop_edges) <= 2):
            continue
        centre = Vector((0, 0, 0))
        for v in verts:
            centre += ob.matrix_world @ v.co
        centre /= len(verts)
        if min((centre - c).length for c in clav.values()) > MAX_DIST:
            continue
        if len(loop_edges) == 2:
            mid = next(v for v in verts if sum(1 for e in loop_edges if v in e.verts) == 2)
            a, b = [v for v in verts if v is not mid]
        else:
            a, b = loop_edges[0].verts
            mid = None
        try:
            if mid is not None:
                f = bm.faces.new((a, mid, b))
            else:
                # одиночное ребро без общей вершины со второй дырой — соединяем через ближайшую
                # уже существующую вершину третьей стороны треугольника
                third = min((v for v in bm.verts if v not in (a, b)),
                            key=lambda v: (v.co - a.co).length + (v.co - b.co).length)
                f = bm.faces.new((a, b, third))
        except ValueError as e:
            print("[notch] не вышло:", e)
            continue
        for lp in f.loops:
            near = next((l for l in lp.vert.link_loops if l.face is not f), None)
            if near and uv is not None:
                lp[uv].uv = near[uv].uv
        closed += 1
        progress = True
        print("[notch] закрыта щель у (%.3f,%.3f,%.3f)" % tuple(centre))
    if not progress:
        break

if closed:
    centre_all = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    bm.normal_update()
    for f in bm.faces:
        pass

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[notch] всего закрыто:", closed)

bpy.ops.wm.save_mainfile()
print("[notch] сохранено")
