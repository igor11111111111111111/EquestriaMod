# -*- coding: utf-8 -*-
"""Rigid wing meshes for flapping wings (10.10.2026): eq_<race>_wing_l / eq_<race>_wing_r.

The race's wing mesh is split by the sign of X, each half is moved so that the ORIGIN is
the wing root (the centre of the vertices at the spine). The flap is done by code (EquestriaWingsTest): rotating
the entity around the root by a sine. The bird skeleton and skinning are not used: their binding in game
cannot be measured, the trial-and-error search did not converge.

Run: blender --background <race blend> --python tools/make_wing_meshes.py -- <race>
    pony:       assets/pony/eq_pony_edit.blend   -- pony
    dragon:     assets/dragon/eq_dragon.blend    -- dragon
    griffon:    assets/griffon/eq_griffon.blend  -- griffon
    hippogriff: assets/hippogriff/hippogriff.blend -- hippogriff
    changeling: assets/changeling/eq_changeling.blend -- changeling
Output: assets/wings/eq_<race>_wing_lr.fbx (+ printing of the roots in model coordinates for the code:
RootLeft/RootRight in EquestriaWingsTest.Races).
"""
import os

import bpy
from mathutils import Matrix, Vector

import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RACE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "pony"
# race → (collection or None, wing object in the blend)
SOURCES = {
    "pony": ("Пони - цельная", "eq_pony_wings"),
    "dragon": (None, "eq_wings"),
    "griffon": (None, "eq_griffon_wings"),
    "hippogriff": (None, "eq_hippogriff_wings"),
    "changeling": (None, "eq_changeling_wings"),
}
# The mesh material in the FBX must be named like the race material in the module (pony_skins.xml: eq_<race>_body),
# otherwise the editor shows "Unable to find material" on every launch (noticed 10.10.2026 on the dragon:
# in the blend the material was called Material.001).
MATERIALS = {"pony": "eq_pony_body", "dragon": "eq_dragon_body", "griffon": "eq_griffon_body", "hippogriff": "eq_hippogriff_body", "changeling": "eq_changeling_body"}
OUT_FBX = os.path.join(ROOT, "assets", "wings", "eq_%s_wing_lr.fbx" % RACE)
ROOT_BAND = 0.03  # m: vertices closer than this to the symmetry plane count as the root

collection, obj_name = SOURCES[RACE]
wings = (bpy.data.collections[collection].objects if collection else bpy.data.objects)[obj_name]
W = wings.matrix_world
exported = []
for name, sign in (("eq_%s_wing_l" % RACE, 1), ("eq_%s_wing_r" % RACE, -1)):
    mesh = wings.data.copy()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    mesh.transform(W)
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    ob.modifiers.clear()
    mat_name = MATERIALS[RACE]
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    mesh.materials.clear()
    mesh.materials.append(mat)
    # keep one half
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in mesh.vertices:
        v.select = (v.co.x * sign) < 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")
    xs = [abs(v.co.x) for v in mesh.vertices]
    near = [v.co for v in mesh.vertices if abs(v.co.x) < min(xs) + ROOT_BAND]
    root = sum(near, Vector()) / len(near)
    mesh.transform(Matrix.Translation(-root))
    ob.matrix_world = Matrix.Identity(4)
    tip = max(abs(v.co.x) for v in mesh.vertices)
    print(f"[wing] {name}: корень в координатах модели {tuple(round(c, 4) for c in root)}, вершин {len(mesh.vertices)}, размах от корня {tip:.3f}")
    exported.append(ob)

os.makedirs(os.path.dirname(OUT_FBX), exist_ok=True)
bpy.ops.object.select_all(action="DESELECT")
for ob in exported:
    ob.select_set(True)
bpy.context.view_layer.objects.active = exported[0]
bpy.ops.export_scene.fbx(filepath=OUT_FBX, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         path_mode="STRIP", axis_forward="Y", axis_up="Z")
print(f"[wing] записан {OUT_FBX}")
