# -*- coding: utf-8 -*-
"""Точечная правка нормалей: сверка с эталоном (старый автонарезанный кусок), а не угадывание.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_fix_normals2.py

Предыдущая попытка (recalc «наружу» по всей сетке, потом слепая инверсия) угадывала неверно:
у открытых кусков (руки, ноги, тело без замкнутого объёма) Recalculate Normals у Blender сам не
знает, какая сторона на самом деле наружу, и для части кусков угадал в другую сторону, а сплошная
инверсия потом перевернула вперемешку и то, что было верно.

Здесь вместо угадывания — сравнение по грани с донором (коллекция «Пони - части», тот же кусок с
суффиксом .001: он с самой сборки не трогался руками и его ориентация верна). Для каждой грани новой
части ищем ближайшую по центру грань донора и переворачиваем свою, только если её нормаль смотрит
в ПРОТИВОПОЛОЖНУЮ сторону от нормали донора. Совпадающие грани не трогаем.
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
