# -*- coding: utf-8 -*-
"""Хвост и крылья в assets/pony/eq_pony_edit.blend — жёстко на одну кость персонажа, без смешивания.

Запуск: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_rigid_parts.py

У eq_pony_tail и eq_pony_wings в коллекции «Пони - цельная» после ручной перекройки веса оказались
размазаны по костям НОГ (бёдра, голени) — видимо, при Join затянуло группы с кусков, что раньше
были частью тела/ног. В игре это означало бы, что хвост и крылья дёргаются вместе с ногами при ходьбе.
Обе части — предметы на скелете (см. src/EquestriaBodyParts.cs), а не часть скиннинга тела, поэтому
им положена ровно одна кость на 100% веса, как у хвоста самой пони до всех правок.
"""
import bpy

RIGID = {"eq_pony_tail": "bip01_pelvis_0", "eq_pony_wings": "bip01_spine2_11"}

new_col = bpy.data.collections["Пони - цельная"]

for name, bone in RIGID.items():
    ob = new_col.objects.get(name)
    if ob is None:
        print("[rigid] ВНИМАНИЕ: нет объекта", name)
        continue
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    group = ob.vertex_groups.new(name=bone)
    group.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    print("[rigid] %-14s -> %s, вершин %d" % (name, bone, len(ob.data.vertices)))

bpy.ops.wm.save_mainfile()
print("[rigid] сохранено")
