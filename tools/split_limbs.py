# -*- coding: utf-8 -*-
"""Общий скрипт разреза gloves/legs пополам по X=0 — тот же приём, что tools/pony_edit_split_limbs.py
(07.10.2026), но параметризован по расе, чтобы не дублировать его шесть раз для changeling/deer/
dragon/griffon/hippogriff/yak. Половины нужны для визуального отрубания конечностей
(EquestriaDismemberment.cs) — снятая конечность и культя на теле должны быть отдельными мешами.

Запуск (аргументы после "--"):
  blender --background --factory-startup <race>.blend --python tools/split_limbs.py -- \
      "<Имя коллекции>" <исходное_имя_gloves> <исходное_имя_legs> <префикс_для_новых_имён>

Например, для дракона (в блендере объекты лежат без префикса расы — eq_gloves/eq_legs, расовый
префикс добавляется только на экспорте, см. tools/dragon_edit_export.py):
  blender --background --factory-startup assets/dragon/eq_dragon.blend --python tools/split_limbs.py -- \
      "Meshy Frostwing Princess" eq_gloves eq_legs eq_

А для яка (объекты уже с префиксом eq_yak_ прямо в блендере):
  blender --background --factory-startup assets/yak/eq_yak.blend --python tools/split_limbs.py -- \
      "Meshy Highland Hugger" eq_yak_gloves eq_yak_legs eq_yak_

Результат — 4 новых объекта <префикс>gloves_l/_r, <префикс>legs_l/_r в той же коллекции. Исходные
gloves/legs НЕ трогаем и не удаляем — целиком они по-прежнему нужны для обычного (не отрубленного)
персонажа. Дыра на срезе (если появится) заделывается автозаполнением (bmesh.ops.holes_fill).
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
    # Вершины ровно на X=0 после удаления могут оставлять вырожденные "ниточки" (ребро длиной
    # 2-4 мм, не входящее ни в одну замкнутую петлю — holes_fill такое не берёт, остаётся дырка
    # из 1-2 рёбер). Схлопываем совпадающие вершины и вырожденные грани — только на самой границе
    # среза (а не по всему мешу, иначе рискуем смазать мелкие детали вроде пальцев).
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary_edges:
        boundary_verts = list({v for e in boundary_edges for v in e.verts})
        bmesh.ops.remove_doubles(bm, verts=boundary_verts, dist=0.002)
        # Пересчитываем ПОСЛЕ слияния — старые ссылки на bmesh-элементы могли инвалидироваться.
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
