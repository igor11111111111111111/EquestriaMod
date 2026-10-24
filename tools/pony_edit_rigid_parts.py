# -*- coding: utf-8 -*-
"""Tail and wings in assets/pony/eq_pony_edit.blend — rigidly on a single character bone, no blending.

Run: blender --background assets/pony/eq_pony_edit.blend --python tools/pony_edit_rigid_parts.py

After the manual re-cut, the weights of eq_pony_tail and eq_pony_wings in the
"Pony - whole" collection turned out
smeared over the LEG bones (thighs, calves) — apparently Join pulled in groups from pieces that used to
be part of the body/legs. In game this would mean the tail and wings twitch along with the legs when
walking. Both parts are items on the skeleton (see src/EquestriaBodyParts.cs), not part of the body
skinning, so they get exactly one bone at 100% weight, like the pony's own tail before all the edits.
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
