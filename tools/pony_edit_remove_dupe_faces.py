# -*- coding: utf-8 -*-
"""Удалить три лишних дублирующих треугольника у корня крыла (см. debug_notch.py в scratchpad).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_remove_dupe_faces.py

Под каждым из них уже есть готовая, полностью сшитая поверхность — сами треугольники лишние
(мусор от Bridge/Merge при ручной перекройке), их свободный край и читался как дыра.
"""
import bmesh
import bpy

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_wings"]
bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()

TARGETS = ([379, 380, 65], [7, 30, 28], [30, 8, 34])
removed = 0
for idxs in TARGETS:
    target = set(idxs)
    face = next((f for f in bm.faces if set(v.index for v in f.verts) == target), None)
    if face is None:
        print("[dupe] не найдена грань", idxs, "— пропущено")
        continue
    lone = [v for v in face.verts if len(v.link_faces) == 1]
    lone_idx = [v.index for v in lone]
    bmesh.ops.delete(bm, geom=[face], context="FACES")
    for v in lone:
        if v.is_valid and not v.link_faces:
            bmesh.ops.delete(bm, geom=[v], context="VERTS")
    removed += 1
    print("[dupe] удалена грань", idxs, "и её висящие вершины", lone_idx)

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[dupe] удалено граней:", removed)

bpy.ops.wm.save_mainfile()
print("[dupe] сохранено")
