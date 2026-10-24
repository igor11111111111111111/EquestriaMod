# -*- coding: utf-8 -*-
"""Продублировать, отзеркалить и заменить правую руку левой (в одном сеансе bmesh).

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_mirror_arm.py

Старые вершины правой руки запоминаются ДО дублирования — если определять «что удалить» заново
после дублирования и переименования групп, дубликат от старого правого не отличить (у обоих
теперь имена костей "_r_" и один и тот же диапазон координат — доказано на практике 28.09.2026).
Зеркалим в МИРОВЫХ координатах (у объекта нетривиальный transform — отрицательный масштаб по X
плюс поворот, локальное «просто X * -1» даёт перекос).
"""
import re

import bmesh
import bpy

ob = bpy.data.collections["Пони - цельная"].objects["eq_pony_body"]
skel = bpy.data.objects["bip01_notused"]
REAL = {b.name for b in skel.data.bones}
PAT = re.compile(r"^bip01_([lr])_(.+)_(\d+)$")
ROLES = {}
for n in REAL:
    m = PAT.match(n)
    if m:
        side, role, num = m.groups()
        ROLES.setdefault(role, {})[side] = n


def mirror_name(name):
    m = PAT.match(name)
    if not m:
        return None
    side, role, _ = m.groups()
    other = "r" if side == "l" else "l"
    return ROLES.get(role, {}).get(other)


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur.name)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    return chain


L = set(arm_chain("l"))
R = set(arm_chain("r"))
mw = ob.matrix_world
mw_inv = mw.inverted()

bm = bmesh.new()
bm.from_mesh(ob.data)
bm.verts.ensure_lookup_table()
dl = bm.verts.layers.deform.active
names_by_index = {g.index: g.name for g in ob.vertex_groups}


def dominant(v):
    d = v[dl]
    if not d:
        return None
    return names_by_index[max(d.items(), key=lambda kv: kv[1])[0]]


left_verts = [v for v in bm.verts if dominant(v) in L]
left_vset = set(left_verts)
left_faces = [f for f in bm.faces if sum(1 for v in f.verts if v in left_vset) * 2 >= len(f.verts)]

# старую правую руку запоминаем СЕЙЧАС, до дублирования — потом эти же BMVert можно удалить
old_right_verts = [v for v in bm.verts if dominant(v) in R]
old_right_set = set(old_right_verts)
old_right_faces = [f for f in bm.faces if any(v in old_right_set for v in f.verts)]
old_right_face_set = set(old_right_faces)
left_faces = [f for f in left_faces if f not in old_right_face_set]
edge_set = [e for e in bm.edges if e.verts[0] in left_vset and e.verts[1] in left_vset]
print("[mirror] левых вершин:", len(left_verts), "старых правых вершин:", len(old_right_verts))

# 1. удаляем старую правую руку
bmesh.ops.delete(bm, geom=old_right_faces, context="FACES")
loose = [v for v in old_right_verts if v.is_valid and not v.link_faces]
bmesh.ops.delete(bm, geom=loose, context="VERTS")
print("[mirror] удалено старых граней:", len(old_right_faces), "висящих вершин:", len(loose))

# 2. дублируем и зеркалим левую руку (left_verts/left_faces всё ещё валидны — их не трогали)
ret = bmesh.ops.duplicate(bm, geom=left_verts + left_faces + edge_set)
new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
new_faces = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)]
print("[mirror] дубликат: вершин", len(new_verts), "граней", len(new_faces))

for v in new_verts:
    world = mw @ v.co
    world.x = -world.x
    v.co = mw_inv @ world

bmesh.ops.reverse_faces(bm, faces=new_faces)

missing_role = set()
for v in new_verts:
    d = v[dl]
    for gi in list(d.keys()):
        name = names_by_index.get(gi)
        if name is None:
            continue
        new_name = mirror_name(name)
        if new_name is None:
            missing_role.add(name)
            continue
        w = d[gi]
        del d[gi]
        grp = ob.vertex_groups.get(new_name) or ob.vertex_groups.new(name=new_name)
        d[grp.index] = w
if missing_role:
    print("[mirror] без зеркала (оставлено как есть — общие кости):", missing_role)

# 3. сшиваем зеркальную копию со швом, что остался на теле после удаления старой руки
before_merge = len(bm.verts)
bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.006)
print("[mirror] слито у шва:", before_merge - len(bm.verts))

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[mirror] итого вершин:", len(ob.data.vertices))

bpy.ops.wm.save_mainfile()
print("[mirror] сохранено")
