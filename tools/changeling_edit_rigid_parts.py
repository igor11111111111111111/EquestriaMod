# -*- coding: utf-8 -*-
"""Wings and tail in assets/changeling/eq_changeling.blend - rigidly on one character bone, no
blending (the same fix the ponies got earlier, see tools/pony_edit_rigid_parts.py).

Run: blender --background assets/changeling/eq_changeling.blend --python tools/changeling_edit_rigid_parts.py

eq_changeling_wings: 755 of 761 vertices are correctly on bip01_spine2_11, but a total weight of 6.0 leaked onto
bip01_pelvis_0 - a few vertices partly follow the pelvis/legs instead of the rigid bone.
eq_changeling_tail: smeared over 19 groups (thighs, calves, pelvis, back) - the same as the ponies had
before the fix (apparently the groups were also dragged in through a Join of body/leg pieces).
Both parts are items on the skeleton (see src/EquestriaBodyParts.cs); they are supposed to have exactly one bone
at 100% weight.
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
