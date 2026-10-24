# -*- coding: utf-8 -*-
"""Довязать веса у частей, перекроенных вручную в assets/pony/eq_pony_edit.blend.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_rebind.py

Только ДОЛИВАЕТ веса: трогает вершину, только если у неё сейчас вообще нет ни одной группы.
Уже расставленные веса (в том числе то, что перенеслось через Join из старых кусков) не трогает.
Донор — старая автоматически нарезанная часть с тем же именем (коллекция «Пони - части», объекты
eq_pony_<часть>.001): у каждой вершины новой модели берётся набор (кость, вес) с ближайшей по
мировым координатам вершины донора. Части-подвески (рог, грива, хвост, крылья) у донора и так
жёстко на одной кости — перенос это просто повторит.
После переноса — предел 4 кости на вершину и нормализация (как требует движок), как в основном
конвейере (tools/make_pony_model.py).
"""
import bpy
from mathutils.kdtree import KDTree

PARTS = ("body", "gloves", "hair", "head", "horn", "legs", "tail", "wings")


def log(*a):
    print("[rebind]", *a, flush=True)


new_col = bpy.data.collections["Пони - цельная"]
old_col = bpy.data.collections["Пони - части"]


def build_tree(ob):
    me = ob.data
    tree = KDTree(len(me.vertices))
    for i, v in enumerate(me.vertices):
        tree.insert(ob.matrix_world @ v.co, i)
    tree.balance()
    return tree


for part in PARTS:
    new_ob = new_col.objects.get("eq_pony_" + part)
    old_ob = old_col.objects.get("eq_pony_%s.001" % part) or old_col.objects.get("eq_pony_" + part)
    if new_ob is None or old_ob is None:
        log("пропущено (нет объекта):", part, "new=", bool(new_ob), "old=", bool(old_ob))
        continue
    missing = [v.index for v in new_ob.data.vertices if len(v.groups) == 0]
    if not missing:
        log("%-8s уже все вершины с весом (%d), не трогаю" % (part, len(new_ob.data.vertices)))
        continue
    tree = build_tree(old_ob)
    old_groups = {g.index: g.name for g in old_ob.vertex_groups}
    filled = 0
    for i in missing:
        world = new_ob.matrix_world @ new_ob.data.vertices[i].co
        _, donor_idx, _ = tree.find(world)
        donor_v = old_ob.data.vertices[donor_idx]
        for g in donor_v.groups:
            name = old_groups[g.group]
            grp = new_ob.vertex_groups.get(name) or new_ob.vertex_groups.new(name=name)
            grp.add([i], g.weight, "REPLACE")
        filled += 1
    bpy.context.view_layer.objects.active = new_ob
    bpy.ops.object.vertex_group_limit_total(limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    log("%-8s довязано вершин: %d из %d, донор %s (%d вершин)"
        % (part, filled, len(new_ob.data.vertices), old_ob.name, len(old_ob.data.vertices)))

still = []
for part in PARTS:
    ob = new_col.objects.get("eq_pony_" + part)
    if ob is None:
        continue
    left = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    if left:
        still.append((part, left))
if still:
    log("ВНИМАНИЕ: остались вершины без веса:", still)
else:
    log("все части «Пони - цельная» полностью привязаны к костям")

bpy.ops.wm.save_mainfile()
log("сохранено: assets/pony/eq_pony_edit.blend")
