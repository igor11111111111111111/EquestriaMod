# -*- coding: utf-8 -*-
"""Shared script that cuts gloves/legs in half at X=0 — the same trick as tools/pony_edit_split_limbs.py
(07.10.2026), but parameterised by race so it is not duplicated six times for changeling/deer/
dragon/griffon/hippogriff/yak. The halves are needed for visual dismemberment
(EquestriaDismemberment.cs) — the severed limb and the stump on the body must be separate meshes.

Run (arguments after "--"):
  blender --background --factory-startup <race>.blend --python tools/split_limbs.py -- \
      "<Collection name>" <source_gloves_name> <source_legs_name> <prefix_for_new_names>

For example, for the dragon (in Blender the objects have no race prefix — eq_gloves/eq_legs, the race
prefix is added only on export, see tools/dragon_edit_export.py):
  blender --background --factory-startup assets/dragon/eq_dragon.blend --python tools/split_limbs.py -- \
      "Meshy Frostwing Princess" eq_gloves eq_legs eq_

And for the yak (objects already have the eq_yak_ prefix right in Blender):
  blender --background --factory-startup assets/yak/eq_yak.blend --python tools/split_limbs.py -- \
      "Meshy Highland Hugger" eq_yak_gloves eq_yak_legs eq_yak_

Result — 4 new objects <prefix>gloves_l/_r, <prefix>legs_l/_r in the same collection. The source
gloves/legs are NOT touched or deleted — whole, they are still needed for a normal (not dismembered)
character. A hole at the cut (if it appears) is patched by auto-fill (bmesh.ops.holes_fill).
"""
import sys

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
if len(argv) != 4:
    raise SystemExit("нужно 4 аргумента после --: коллекция, gloves, legs, префикс")
collection_name, gloves_src, legs_src, out_prefix = argv

col = bpy.data.collections[collection_name]


def log(*a):
    print("[split-limbs]", *a, flush=True)


def split_half(src_name, side, out_name):
    if out_name in col.objects:
        log(out_name, "уже существует, пропускаю (запущено повторно?)")
        return
    src = col.objects.get(src_name)
    if src is None:
        log("ВНИМАНИЕ: нет объекта", src_name, "— пропускаю")
        return
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
    # Vertices exactly at X=0 may leave degenerate "threads" after deletion (an edge 2-4 mm long that
    # is not part of any closed loop — holes_fill does not take such, a hole of 1-2 edges remains).
    # We collapse coincident vertices and degenerate faces — only on the cut boundary itself
    # (not over the whole mesh, otherwise we risk smearing small details like fingers).
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary_edges:
        boundary_verts = list({v for e in boundary_edges for v in e.verts})
        bmesh.ops.remove_doubles(bm, verts=boundary_verts, dist=0.002)
        # Recompute AFTER merging — old references to bmesh elements may have been invalidated.
        boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
        boundary_verts = list({v for e in boundary_edges for v in e.verts})
        nearby_edges = list({e for v in boundary_verts for e in v.link_edges})
        bmesh.ops.dissolve_degenerate(bm, dist=0.002, edges=nearby_edges)
        boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary_edges:
        res = bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
        log(out_name, "вершин:", len(bm.verts), "залатано граней на срезе:", len(res.get("faces", [])))
    else:
        log(out_name, "вершин:", len(bm.verts), "— срез уже был герметичен, латать нечего")
    bm.to_mesh(dup.data)
    bm.free()
    dup.data.update()


split_half(gloves_src, "l", out_prefix + "gloves_l")
split_half(gloves_src, "r", out_prefix + "gloves_r")
split_half(legs_src, "l", out_prefix + "legs_l")
split_half(legs_src, "r", out_prefix + "legs_r")

bpy.ops.wm.save_mainfile()
log("сохранено")
