# -*- coding: utf-8 -*-
"""Merge close/duplicate vertices at the wing root (Merge by Distance) - the source of thin spikes.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_merge_wing_root.py

There are no missing polygons there: the "holes" found are thin spike triangles on a single dangling
vertex, duplicating already existing geometry (junk from Bridge/Merge during manual re-cutting).
The right way to remove them is to merge close vertices in this zone, like a regular Merge by Distance.
"""
import bmesh
import bpy

MAX_DIST = 0.35
MERGE_THRESHOLD = 0.004

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
skel = bpy.data.objects["bip01_notused"]
clav = {}
for side, bone in (("l", "bip01_l_clavicle_14"), ("r", "bip01_r_clavicle_21")):
    b = skel.data.bones[bone]
    clav[side] = skel.matrix_world @ ((b.head_local + b.tail_local) / 2)

bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
zone = [v for v in bm.verts if min((ob.matrix_world @ v.co - c).length for c in clav.values()) < MAX_DIST]
print("[merge] вершин в зоне корня:", len(zone), "из", len(bm.verts))
before = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=zone, dist=MERGE_THRESHOLD)
after = len(bm.verts)
bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[merge] было вершин %d -> стало %d (удалено %d)" % (before, after, before - after))

bpy.ops.wm.save_mainfile()
print("[merge] сохранено")
