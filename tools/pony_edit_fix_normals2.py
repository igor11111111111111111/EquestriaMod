# -*- coding: utf-8 -*-
"""Targeted normal fix: comparison against a reference (the old auto-cut piece), not guessing.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_normals2.py

The previous attempt (recalc "outside" over the whole mesh, then a blind inversion) guessed wrong:
for open pieces (arms, legs, a body without a closed volume) Blender's Recalculate Normals does not
itself know which side is really outside, and for some pieces it guessed the other way, and the blanket
inversion then flipped a mix of pieces, including the ones that were correct.

Here, instead of guessing, each face is compared with a donor (collection "Pony - parts", the same
piece with the .001 suffix: it has not been touched by hand since the build itself and its orientation
is right). For each face of the new part we find the donor face with the nearest centre and flip ours
only if its normal points in the OPPOSITE direction from the donor's normal. Matching faces are left alone.
"""
import bmesh
import bpy
from mathutils.kdtree import KDTree

PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")


def log(*a):
    print("[fix2]", *a, flush=True)


new_col = bpy.data.collections["Пони - цельная"]
old_col = bpy.data.collections["Пони - части"]

for part in PARTS:
    new_ob = new_col.objects.get("eq_pony_" + part)
    old_ob = old_col.objects.get("eq_pony_%s.001" % part) or old_col.objects.get("eq_pony_" + part)
    if new_ob is None or old_ob is None:
        log("пропущено (нет объекта):", part)
        continue

    tree = KDTree(len(old_ob.data.polygons))
    for i, p in enumerate(old_ob.data.polygons):
        tree.insert(old_ob.matrix_world @ p.center, i)
    tree.balance()
    old_normals = [ (old_ob.matrix_world.to_3x3() @ p.normal).normalized() for p in old_ob.data.polygons ]

    bm = bmesh.new()
    bm.from_mesh(new_ob.data)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    to_flip = []
    for f in bm.faces:
        centre = new_ob.matrix_world @ f.calc_center_median()
        _, idx, _ = tree.find(centre)
        donor_n = old_normals[idx]
        mine_n = (new_ob.matrix_world.to_3x3() @ f.normal).normalized()
        if mine_n.dot(donor_n) < 0:
            to_flip.append(f)
    if to_flip:
        bmesh.ops.reverse_faces(bm, faces=to_flip)
    bm.to_mesh(new_ob.data)
    bm.free()
    new_ob.data.update()
    log("%-8s граней всего %-6d перевёрнуто %d" % (part, len(new_ob.data.polygons), len(to_flip)))

bpy.ops.wm.save_mainfile()
log("сохранено")
