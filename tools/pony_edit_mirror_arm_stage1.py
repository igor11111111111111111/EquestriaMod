# -*- coding: utf-8 -*-
"""Этап 1: дублировать и отзеркалить левую руку в мировых координатах, НЕ трогая правую.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_mirror_arm_stage1.py

Только создаёт зеркальную копию рядом (новые вершины/грани, отдельно от старой правой руки),
чтобы сначала визуально сверить, совпадает ли она с текущей правой рукой по месту. Старую правую
руку и объединение делает отдельный, второй скрипт — после того как эта проверка пройдёт.

Зеркалим именно в МИРОВЫХ координатах (не в локальных): у объекта нетривиальный transform
(отрицательный масштаб по X + поворот), и локальное «просто отразить X» даёт перекошенный
результат — с мировыми координатами это не важно.
"""
import re

import bmesh
import bpy
from mathutils import Vector

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
    best = max(d.items(), key=lambda kv: kv[1])
    return names_by_index[best[0]]


left_verts = [v for v in bm.verts if dominant(v) in L]
left_vset = set(left_verts)
left_faces = [f for f in bm.faces if sum(1 for v in f.verts if v in left_vset) * 2 >= len(f.verts)]
print("[stage1] левых вершин:", len(left_verts), "граней:", len(left_faces))

ret = bmesh.ops.duplicate(bm, geom=left_verts + left_faces +
                           [e for e in bm.edges if e.verts[0] in left_vset and e.verts[1] in left_vset])
new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
new_faces = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMFace)]
print("[stage1] дубликат: вершин", len(new_verts), "граней", len(new_faces))

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
        grp = ob.vertex_groups.get(new_name)
        if grp is None:
            grp = ob.vertex_groups.new(name=new_name)
        d[grp.index] = w
if missing_role:
    print("[stage1] ВНИМАНИЕ: не нашлось зеркала для", missing_role)

bm.to_mesh(ob.data)
bm.free()
ob.data.update()
print("[stage1] всего вершин теперь:", len(ob.data.vertices))

bpy.ops.wm.save_mainfile()
print("[stage1] сохранено")
