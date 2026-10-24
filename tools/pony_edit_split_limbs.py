# -*- coding: utf-8 -*-
"""Cuts eq_pony_gloves/eq_pony_legs in half at X=0 - separate left/right halves are needed for
visual limb dismemberment (EquestriaDismemberment.cs): in DismembermentPlus (the reference,
nexusmods.com/mountandblade2bannerlord/mods/2190) the severed limb and the stump on the body are separate
meshes, not one piece for both sides at once as gloves/legs are now.

Verified by diagnostics on 07.10.2026: eq_pony_gloves is already TWO independent watertight halves in
one object (0 boundary edges both before and after the cut - nothing for the script to patch). eq_pony_legs
is one shared surface; after the cut a small hole remains at the cut (~40 vertices), which is filled
automatically (bmesh.ops.holes_fill) with one N-gon.

Result: 4 new objects in the "Pony - whole" collection: eq_pony_gloves_l/_r, eq_pony_legs_l/_r.
The old eq_pony_gloves/eq_pony_legs are NOT touched or deleted - they are still needed whole for
a normal (not dismembered) character.

Run: blender --background --factory-startup assets/pony/eq_pony_edit.blend --python tools/pony_edit_split_limbs.py
"""
import bmesh
import bpy

col = bpy.data.collections["Пони - цельная"]


def log(*a):
    print("[split-limbs]", *a, flush=True)


def split_half(src_name, side, out_name):
    if out_name in col.objects:
        log(out_name, "уже существует, пропускаю (запущено повторно?)")
        return
    src = col.objects[src_name]
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = dup.data.name = out_name
    col.objects.link(dup)

    bm = bmesh.new()
    bm.from_mesh(dup.data)
    bm.verts.ensure_lookup_table()
    keep_positive = side == "l"
    to_remove = [v for v in bm.verts if (v.co.x > 0) != keep_positive]
    bmesh.ops.delete(bm, geom=to_remove, context="VERTS")
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary_edges:
        res = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
        log(out_name, "вершин:", len(bm.verts), "залатано граней на срезе:", len(res.get("faces", [])))
    else:
        log(out_name, "вершин:", len(bm.verts), "— срез уже был герметичен, латать нечего")
    bm.to_mesh(dup.data)
    bm.free()
    dup.data.update()


split_half("eq_pony_gloves", "l", "eq_pony_gloves_l")
split_half("eq_pony_gloves", "r", "eq_pony_gloves_r")
split_half("eq_pony_legs", "l", "eq_pony_legs_l")
split_half("eq_pony_legs", "r", "eq_pony_legs_r")

bpy.ops.wm.save_mainfile()
log("сохранено: assets/pony/eq_pony_edit.blend")
