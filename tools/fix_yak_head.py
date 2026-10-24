# -*- coding: utf-8 -*-
"""Yak: top of the head and the gap with the mane - a fix to the finished assets/yak/eq_yak.blend.

Run: blender --background assets/yak/eq_yak.blend --python tools/fix_yak_head.py

The yak's source file (the generator's FBX) was not kept, so tools/make_yak_model.py cannot be
rerun on it. The same fix as in make_deer_model.py / make_dragon.py / make_griffon.py /
make_hippogriff.py is applied to the already cut parts: in the head we fill with polygons
the spot where the mane was cut off (without it there was a hole on the crown under a helmet), and sink the
head vertices that lie right against the mane - otherwise the surfaces flicker through each other.
"""
import os

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

NEAR_RING = 0.012       # a contour counts as a "mane" one if it is this close to the mane
SEPARATE_NEAR = 0.025   # head vertices closer than this to the mane are sunk inward (metres)
SEPARATE_PUSH = 0.010   # and by this much, right at the mane

head = bpy.data.objects["eq_yak_head"]
hair = bpy.data.objects["eq_yak_hair"]


def world(ob):
    return [ob.matrix_world @ v.co for v in ob.data.vertices]


hv = [tuple(p) for p in world(hair)]
tree = BVHTree.FromPolygons(hv, [tuple(p.vertices) for p in hair.data.polygons])

bm = bmesh.new()
bm.from_mesh(head.data)
uv = bm.loops.layers.uv.active
mw = head.matrix_world

seen, filled = set(), 0
for start in [e for e in bm.edges if len(e.link_faces) == 1]:
    if start in seen:
        continue
    loop, stack = [], [start]
    seen.add(start)
    while stack:
        cur = stack.pop()
        loop.append(cur)
        for v in cur.verts:
            for e in v.link_edges:
                if len(e.link_faces) == 1 and e not in seen:
                    seen.add(e)
                    stack.append(e)
    ring = {v for e in loop for v in e.verts}
    close = sum(1 for v in ring if (lambda h: h[0] is not None and h[3] < NEAR_RING)(tree.find_nearest(mw @ v.co)))
    if len(ring) < 3 or close < 0.3 * len(ring):
        continue
    was = set(bm.faces)
    try:
        bmesh.ops.triangle_fill(bm, edges=loop, use_beauty=True)
    except RuntimeError:
        bmesh.ops.holes_fill(bm, edges=loop, sides=0)
    patch = [f for f in bm.faces if f not in was]
    for f in patch:
        for lp in f.loops:
            near = next((l for l in lp.vert.link_loops if l.face not in patch), None)
            if near and uv is not None:
                lp[uv].uv = near[uv].uv
    bmesh.ops.recalc_face_normals(bm, faces=patch)
    centre = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    for f in patch:
        if f.normal.dot(f.calc_center_median() - centre) < 0:
            f.normal_flip()
    filled += len(patch)
print("[yak-fix] заделано граней:", filled)

shape_layers = list(bm.verts.layers.shape.values())
bm.normal_update()
pushed = 0
for v in bm.verts:
    hit = tree.find_nearest(mw @ v.co)
    if hit[0] is None or hit[3] >= SEPARATE_NEAR:
        continue
    delta = v.normal * (SEPARATE_PUSH * (0.4 + 0.6 * (1.0 - hit[3] / SEPARATE_NEAR)))
    v.co -= delta
    for layer in shape_layers:      # facial keys store absolute coordinates - move them too
        v[layer] -= delta
    pushed += 1
print("[yak-fix] голова отодвинута от гривы вглубь: %d вершин" % pushed)
bm.to_mesh(head.data)
bm.free()
for p in head.data.polygons:
    p.use_smooth = True

skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
parts = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("eq_yak_")]
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
out = os.path.join(os.path.dirname(bpy.data.filepath), "eq_yak.fbx")
bpy.ops.export_scene.fbx(filepath=out, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
bpy.ops.wm.save_mainfile()
print("[yak-fix] экспорт", out)
