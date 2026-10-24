# -*- coding: utf-8 -*-
"""Крылья и хвост в assets/changeling/eq_changeling.blend — жёстко на одну кость персонажа, без
смешивания (та же правка, что раньше делали пони, см. tools/pony_edit_rigid_parts.py).

Запуск: blender --background assets/changeling/eq_changeling.blend --python tools/changeling_edit_rigid_parts.py

eq_changeling_wings: 755 из 761 вершин верно на bip01_spine2_11, но суммарный вес 6.0 протёк на
bip01_pelvis_0 — несколько вершин частично следуют за тазом/ногами вместо жёсткой кости.
eq_changeling_tail: размазан по 19 группам (бёдра, голени, таз, спина) — то же самое, что было
у пони до правки (видимо, тоже протянуло группы через Join кусков тела/ног).
Обе части — предметы на скелете (см. src/EquestriaBodyParts.cs), им положена ровно одна кость
на 100% веса.
"""
import bpy

RIGID = {"eq_changeling_tail": "bip01_pelvis_0", "eq_changeling_wings": "bip01_spine2_11"}

col = bpy.data.collections["Meshy Midnight Changeling"]

for name, bone in RIGID.items():
    ob = col.objects.get(name)
    if ob is None:
        print("[rigid] ВНИМАНИЕ: нет объекта", name)
        continue
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    group = ob.vertex_groups.new(name=bone)
    group.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    print("[rigid] %-20s -> %s, вершин %d" % (name, bone, len(ob.data.vertices)))

bpy.ops.wm.save_mainfile()
print("[rigid] сохранено")
