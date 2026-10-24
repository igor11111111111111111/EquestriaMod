# -*- coding: utf-8 -*-
"""Режет eq_pony_gloves/eq_pony_legs пополам по X=0 — отдельные левая/правая половины нужны для
визуального отрубания конечностей (EquestriaDismemberment.cs): у ДismembermentPlus (образец,
nexusmods.com/mountandblade2bannerlord/mods/2190) снятая конечность и культя на теле — отдельные
меши, а не один кусок на обе стороны разом, как сейчас gloves/legs.

Проверено диагностикой 07.10.2026: eq_pony_gloves — уже ДВЕ независимые герметичные половины в
одном объекте (0 граничных рёбер и до, и после разреза — скрипту заделывать нечего). eq_pony_legs —
одна общая поверхность, после разреза остаётся небольшая дыра на срезе (~40 вершин), заделывается
автозаполнением (bmesh.ops.holes_fill) в один N-угольник.

Результат — 4 новых объекта в коллекции «Пони - цельная»: eq_pony_gloves_l/_r, eq_pony_legs_l/_r.
Старые eq_pony_gloves/eq_pony_legs НЕ трогаем и не удаляем — они по-прежнему нужны целиком для
обычного (не отрубленного) персонажа.

Запуск: blender --background --factory-startup assets/pony/eq_pony_edit.blend --python tools/pony_edit_split_limbs.py
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
