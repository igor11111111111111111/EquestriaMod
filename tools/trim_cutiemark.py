"""Removes the small cutie mark stars from the pony model.

The cutie mark (tools/convert_twilight.py, build_cutiemarks) is geometry in the tail mesh: a big star
on the thigh and three small ones around it. All of it is rigidly bound to the pelvis, so the small stars
that already lie on the leg tear away from the skin when walking and "fly". The big one sits on the thigh
right by the pelvis and holds; we keep it.

The small stars differ by their UVs: their faces lie in the atlas column u≈0.44 (white colour),
the big star in u≈0.31. The original coordinates from convert_twilight.py (0.75 and 0.25) are no good
for the atlas: texture packing shifts the UVs, and cutting by them cuts the tail itself
(it spans u≈0.77…0.98).

Run (the file is overwritten, a .before_cutiemark copy is put next to it):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python trim_cutiemark.py
"""
import os
import shutil

import bmesh
import bpy

TAIL = "eq_twilight_tail"
SMALL_U = 0.44   # atlas column that covers the small stars
TOL = 0.03
EXPECT = 72      # 6 stars (three on each side), 12 triangles each


def log(*a):
    print("[cutiemark]", *a, flush=True)


blend = bpy.data.filepath
ob = bpy.data.objects[TAIL]
me = ob.data

before = len(me.polygons)
bm = bmesh.new()
bm.from_mesh(me)
uv = bm.loops.layers.uv.active
doomed = [f for f in bm.faces
          if all(abs(loop[uv].uv.x - SMALL_U) < TOL for loop in f.loops)]
bmesh.ops.delete(bm, geom=doomed, context="FACES")
bm.to_mesh(me)
bm.free()
me.update()
cut = before - len(me.polygons)
log(f"убрано граней: {cut} из {before}, осталось {len(me.polygons)}")

if cut != EXPECT:
    # better to touch nothing than to cut off part of the tail: check the atlas column
    log(f"ожидалось {EXPECT} граней — модель не трогаем")
else:
    for name, ext in (("eq_twilight.fbx", ".before_cutiemark.fbx"),):
        path = os.path.join(os.path.dirname(blend), name)
        if os.path.exists(path):
            shutil.copyfile(path, path.replace(".fbx", ext))

    # export as in convert_twilight.py
    skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    items = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("eq_twilight_")]
    bpy.ops.object.select_all(action="DESELECT")
    for o in [skel, *items]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = skel
    fbx = os.path.join(os.path.dirname(blend), "eq_twilight.fbx")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                             primary_bone_axis="X", secondary_bone_axis="-Y")
    log("экспортирован", fbx, [o.name for o in items])
    shutil.copyfile(blend, blend.replace(".blend", ".before_cutiemark.blend"))
    bpy.ops.wm.save_mainfile()
    log("сохранён", blend)
