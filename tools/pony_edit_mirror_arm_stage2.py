# -*- coding: utf-8 -*-
"""Этап 2: удалить старую правую руку и сшить зеркальную копию (из этапа 1) со швом на теле.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_mirror_arm_stage2.py
"""
import bmesh
import bpy

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_body"]
skel = bpy.data.objects["bip01_notused"]


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur.name)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    return chain


R = set(arm_chain("r"))

bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
dl = bm.verts.layers.deform.active
names_by_index = {g.index: g.name for g in ob.vertex_groups}


def dominant(v):
    d = v[dl]
    if not d:
        return None
    best = max(d.items(), key=lambda kv: kv[1])
    return names_by_index[best[0]]


# Старая правая рука: вершины с x >= 0 (все вершины дубликата зеркалированы в мировые -X, а
# исходная правая рука до сих пор с положительным локальным X — см. dry_run_mirror.py) и весом
# преимущественно на костях правой руки. Ограничение по x страхует от захвата свежего дубликата
# (он на тех же костях, но уже с отрицательным X).
old_right = [v for v in bm.verts if v.co.x > 0.0 and dominant(v) in R]
print("[stage2] старых вершин правой руки:", len(old_right))
old_right_set = set(old_right)
old_faces = [f for f in bm.faces if any(v in old_right_set for v in f.verts)]
bmesh.ops.delete(bm, geom=old_faces, context="FACES")
loose = [v for v in old_right if v.is_valid and not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context="VERTS")
print("[stage2] удалено граней:", len(old_faces), "вершин:", len(loose))

# Сшиваем: совпадающие по месту вершины дубликата и открытого края тела сливаем в одну.
res = bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.006)
print("[stage2] слито дублей у шва:", len(res.get("targetmap", {}) or {}) if isinstance(res, dict) else "?")

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[stage2] итого вершин:", len(ob.data.vertices))

bpy.ops.wm.save_mainfile()
print("[stage2] сохранено")
