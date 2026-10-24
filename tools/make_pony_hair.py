"""Грива Твайлайт — настоящая причёска пони (слот волос) вместе с рогом.

Запуск (headless Blender, на готовой пони после fix_pony_eyes.py):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_pony_hair.py -- ../assets/pony_hair

Из предмета-«шапки» eq_twilight_mane (грива + рог, жёстко на кости головы) получаются:
  eq_hair_pony_twilight — грива вместе с рогом; веса как у ванильных причёсок (голова → шея → spine2),
                          поэтому длинные пряди на спине следуют за телом, а не висят в воздухе при повороте головы.
Отдельного предмета-рога больше нет: рог входит в каждую причёску (tools/make_pony_manes.py).
Материал — общий атлас eq_twilight_body (в FBX только имя). Остальные причёски пони — мультяшные
гривы из tools/make_pony_manes.py (там рог добавляется вторым материалом).
"""
import os
import sys

import bmesh
import bpy

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(OUT, exist_ok=True)
HEAD, NECK, SPINE2 = "bip01_head_13", "bip01_neck_12", "bip01_spine2_11"
MANE = "eq_twilight_mane"
HORN_CELL = (1, 2)


def log(*a):
    print("[pony hair]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}
src = bpy.data.objects[MANE]


def part(name, keep):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    dead = []
    for f in bm.faces:
        u, v = f.loops[0][uv].uv
        if not keep((min(int(u * 4), 3), min(int(v * 4), 3))):
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    log(f"{name}: {len(ob.data.vertices)} verts, {len(ob.data.polygons)} faces")
    return ob


def bone_weights(z):
    zh, zn, zs = bones[HEAD].z, bones[NECK].z, bones[SPINE2].z
    if z >= zh - 0.06:
        return {HEAD: 1.0}
    if z >= zn:
        t = (z - zn) / (zh - 0.06 - zn)
        return {HEAD: t, NECK: 1 - t}
    if z >= zs:
        t = (z - zs) / (zn - zs)
        return {NECK: t, SPINE2: 1 - t}
    return {SPINE2: 1.0}


hair = part("eq_hair_pony_twilight", lambda c: True)
for g in list(hair.vertex_groups):
    hair.vertex_groups.remove(g)
groups = {n: hair.vertex_groups.new(name=n) for n in (HEAD, NECK, SPINE2)}
for v in hair.data.vertices:
    for bone, w in bone_weights((hair.matrix_world @ v.co).z).items():
        groups[bone].add([v.index], w, "REPLACE")

mat = bpy.data.materials["eq_twilight_body"]
for n in mat.node_tree.nodes:
    if n.type == "TEX_IMAGE":
        n.image = None
bpy.ops.object.select_all(action="DESELECT")
for ob in (skel, hair):
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
fbx = os.path.join(OUT, "eq_pony_hair.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("exported", fbx)
