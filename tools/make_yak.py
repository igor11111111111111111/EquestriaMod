# -*- coding: utf-8 -*-
"""A yak from a ready anthro model (A-pose, no skeleton): onto the pony skeleton, in parts, to FBX.

Run (headless Blender, opens the finished pony: it holds the skeleton and the skinning reference):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_yak.py -- <yak.glb> <output folder>

How it differs from the earlier attempts (tools/convert_*.py): the model already stands on two legs in an A-pose,
nothing needs turning around. What remains is to bind it to the Bannerlord human skeleton and cut it
into items the same way the pony is cut:
  eq_yak_body   - torso and arms (body_meta_mesh)
  eq_yak_legs   - legs (legs_mesh)
  eq_yak_gloves - hands (hands_mesh)
  eq_yak_head   - head with horns and mane (face_meta_mesh; no facial-expression keys, the face is rigid)
  eq_yak_tail   - tail (an item in the cape slot, like the pony tail, entirely on the pelvis bone)

How it is done:
  1. The model is set with its hooves on the floor, muzzle toward -Y (like the pony), and scaled to height HEIGHT.
  2. Bone weights are transferred from the pony: from the nearest point of its surface (body+legs+hands+head,
     merged into one), so the yak bends in the same places as the pony. Heat-based automatic skinning does not
     suit such a mesh (fur plates, unmerged pieces).
  3. Cutting into items is by each vertex's main bone: head and neck → head, hands → gloves,
     thigh-calf-foot → legs, tail by position (behind the back, at pelvis height), the rest is the body.
  4. Material eq_yak_body with the model's baked textures; the textures themselves are written to <output>/textures.
     In the editor the material has to be created anew on these textures (a material from FBX comes without skinning).
Next: import the FBX into the Modding Kit by hand, then remove "yak" from NOT_IMPORTED in tools/make_pony_race.py.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "yak"
HEIGHT = 2.05          # yak height in metres (pony 1.86): yaks are bigger than ponies
MAT = "eq_yak_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"


def log(*a):
    print("[yak]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}

# ---------------------------------------------------------------- 1. import and placement
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=SRC)
new = [o for o in bpy.data.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
for o in new:
    if o.type != "MESH":
        bpy.data.objects.remove(o)
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
yak = bpy.context.view_layer.objects.active
yak.name = yak.data.name = "eq_yak_all"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# The generator outputs a "soup": neighbouring triangles do not share vertices (thousands of islands). We merge them,
# otherwise connected pieces (mane strands) cannot be found, and gaps may open along seams when deforming.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(yak.data.vertices))


def coords():
    return np.array([v.co[:] for v in yak.data.vertices])


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: %d вершин, размер %.2f x %.2f x %.2f" % (len(P), *(hi - lo)))
# The muzzle must face -Y. The muzzle is the point sticking out furthest in Y in the upper third of the model.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
nose_y = top[np.argmax(np.abs(top[:, 1] - (lo[1] + hi[1]) / 2)), 1]
if nose_y > (lo[1] + hi[1]) / 2:
    log("морда смотрела в +Y — разворачиваю")
    yak.rotation_euler.z = math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
scale = HEIGHT / (hi[2] - lo[2])
yak.scale = (scale,) * 3
yak.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
# Forward lean. In game the animations arch the spine backward, and the yak's massive torso with the hump
# on its back looks thrown back; we compensate in the model itself: everything above the pelvis rotates
# forward around the X axis through the pelvis, the angle builds up smoothly from pelvis to chest (LEAN_TO), full above.
LEAN_FORWARD = math.radians(12.0)
LEAN_FROM, LEAN_TO = bones[PELVIS].z * HEIGHT / 1.86, 1.35
if LEAN_FORWARD:
    for v in yak.data.vertices:
        if v.co.z <= LEAN_FROM:
            continue
        t = min(1.0, (v.co.z - LEAN_FROM) / (LEAN_TO - LEAN_FROM))
        a = LEAN_FORWARD * t
        y, z = v.co.y, v.co.z - LEAN_FROM
        v.co.y = y * math.cos(a) - z * math.sin(a)
        v.co.z = y * math.sin(a) + z * math.cos(a) + LEAN_FROM
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("наклон вперёд %.0f°: верх груди сместился на %.2f м вперёд" % (math.degrees(LEAN_FORWARD),
                                                                       (1.35 - LEAN_FROM) * math.sin(LEAN_FORWARD)))
# Arms forward. The model's arms are swept back: the hands at y≈+0.20, while the pony's arm bones run at y≈0.03
# (forward is -Y). The skinning keeps this offset in any pose, and in game the arms stick out behind
# the back. We move the arms forward by translation: fully from ARM_X1, smoothly from ARM_X0 (the shoulder).
# Two motions, neither tears the mesh:
#   1) shoulders forward: by translation, but with a wide zone from the axis itself (0 -> SHOULDER_X): the side of the
#      torso moves with the shoulder, and no "web" forms at the base of the arm;
#   2) the arm rotates around the vertical through the shoulder joint by ARM_SWING forward: the arm's shape
#      stays, the hand comes toward the middle of the torso.
SHOULDER_X = 0.42          # the yak's shoulder joint (pony 0.19)
SHOULDER_FORWARD = 0.12    # how far to bring the shoulders forward
ARM_SWING = math.radians(25.0)
ARM_OUT = 0.05             # slightly outward, also with a wide zone
root = P[(np.abs(P[:, 0]) > SHOULDER_X - 0.05) & (np.abs(P[:, 0]) < SHOULDER_X + 0.05) & (P[:, 2] > 1.0)]
pivot_y, pivot_z = float(root[:, 1].mean()), float(root[:, 2].mean())
for v in yak.data.vertices:
    if v.co.z < 0.85:
        continue
    ax = abs(v.co.x)
    sign = 1 if v.co.x > 0 else -1
    t = min(1.0, ax / SHOULDER_X)
    v.co.y -= SHOULDER_FORWARD * t
    v.co.x += ARM_OUT * t * sign
    if ax > SHOULDER_X - 0.08:
        # rotation around the vertical through (±SHOULDER_X, pivot_y): forward is -Y
        k = min(1.0, (ax - (SHOULDER_X - 0.08)) / 0.16)   # smooth entry into the rotation at the joint
        a = ARM_SWING * k
        dx, dy = ax - SHOULDER_X, v.co.y - (pivot_y - SHOULDER_FORWARD)
        rx = dx * math.cos(a) + dy * math.sin(a)
        ry = -dx * math.sin(a) + dy * math.cos(a)
        v.co.x = (SHOULDER_X + rx) * sign
        v.co.y = (pivot_y - SHOULDER_FORWARD) + ry
P = coords()
lo, hi = P.min(0), P.max(0)
hands = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("руки: плечи вперёд на %.2f м, поворот %.0f°, кисти теперь на y=%.2f (кость %.2f), x=%.2f"
    % (SHOULDER_FORWARD, math.degrees(ARM_SWING), hands[:, 1].mean(), bones["bip01_l_hand_19"].y, hands[:, 0].mean()))
# Where the yak's hands are: the points furthest in X (the pony's hand is at height 1.11, x 0.65)
hand = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони 1.11), таз пони на %.2f"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand[:, 2].mean(), bones[PELVIS].z))

# ---------------------------------------------------------------- 2. weights from the pony
ref_parts = []
for name in ("eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves", "eq_twilight_head"):
    src = pony[name]
    ob = src.copy()
    ob.data = src.data.copy()
    if ob.data.shape_keys:   # the keys get in the way of joining; the base shape is already set
        ob.shape_key_clear()
    bpy.context.scene.collection.objects.link(ob)
    ref_parts.append(ob)
bpy.ops.object.select_all(action="DESELECT")
for ob in ref_parts:
    ob.select_set(True)
bpy.context.view_layer.objects.active = ref_parts[0]
bpy.ops.object.join()
ref = bpy.context.view_layer.objects.active
ref.name = "pony_ref"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

for g in ref.vertex_groups:
    if g.name not in yak.vertex_groups:
        yak.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
yak.select_set(True)
bpy.context.view_layer.objects.active = yak
dt = yak.modifiers.new("веса", "DATA_TRANSFER")
dt.object = ref
dt.use_vert_data = True
dt.data_types_verts = {"VGROUP_WEIGHTS"}
dt.vert_mapping = "POLYINTERP_NEAREST"
dt.layers_vgroup_select_src = "ALL"
dt.layers_vgroup_select_dst = "NAME"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
bpy.data.objects.remove(ref)

# Hand and forearm bones only for the arm. In the pony's A-pose the hands hang at belly height, and the sides
# of the yak's wide torso were closer to its hands than to its body: the transfer gave them hand weights,
# a "ring" from the belly appeared in the gloves preview, and in game the belly would jerk along with the arms.
P = coords()
HAND_MIN_X, FOREARM_MIN_X = 0.62, 0.45
stripped = 0
for i, p in enumerate(P):
    ax = abs(p[0])
    if ax >= HAND_MIN_X:
        continue
    v = yak.data.vertices[i]
    for g in list(v.groups):
        name = yak.vertex_groups[g.group].name
        if name in HAND_BONES or (ax < FOREARM_MIN_X and "foretwist" in name):
            yak.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:   # it was held only by the hands; give it to the spine
        yak.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей и предплечий с корпуса: %d" % stripped)

# The head is rigid on the head bone. The yak's muzzle sits low and far in front of where the pony's head
# is, and the weight transfer gives it neck and chest bones: the top and bottom of the muzzle were driven by
# different bones, and it tore at the junction. The head boundary is the jaw line: above the neck (NECK_Z),
# and in front it drops following the muzzle (JAW_SLOPE m down per metre forward).
# The skeleton does not scale together with the model: the neck bone stands at 1.47 m at any yak height,
# and the narrowest point of its neck is at 1.56 m; we cut between them.
NECK_Z = bones["bip01_neck_12"].z + 0.03
JAW_SLOPE, JAW_FROM = 0.55, -0.15


def is_head(p):
    front = max(0.0, -p[1] + JAW_FROM)   # how far the point is in front of the neck line
    return p[2] > NECK_Z - JAW_SLOPE * front


P = coords()
head_idx = [i for i in range(len(P)) if is_head(P[i])]
head_group = yak.vertex_groups["bip01_head_13"]
for g in yak.vertex_groups:
    if g.name != "bip01_head_13":
        g.remove(head_idx)
head_group.add(head_idx, 1.0, "REPLACE")
# Below the jaw line, a smooth zone: the body right under the head is driven by neck and chest bones, and without
# a transition the skin at the junction (mane strands, throat) stretches between the rigid head and the neck.
BLEND = 0.15
blended = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p):
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]      # how far below the jaw line
    if d >= BLEND:
        continue
    w = 1.0 - d / BLEND
    v = yak.data.vertices[i]
    for g in v.groups:
        yak.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
log("голова жёстко на кости головы: %d вершин, плавная зона под челюстью: %d" % (len(head_idx), blended))

# ---------------------------------------------------------------- 3. cutting into items
group_names = {g.index: g.name for g in yak.vertex_groups}
dominant = []
for v in yak.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
back = P[(np.abs(P[:, 0]) < 0.08) & (np.abs(P[:, 2] - bones[PELVIS].z * HEIGHT / 1.86) < 0.15), 1].max()
tail_z = bones[PELVIS].z * HEIGHT / 1.86


LEG_TOP = 0.44 * HEIGHT / 1.86   # for the pony "legs" are the calves and hooves (up to 0.44 m), thighs are in the body
# The head is cut along the same jaw line as the weights (is_head above): the head and its bone go together.

# mesh islands (connected pieces)
parent = list(range(len(P)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


for e in yak.data.edges:
    a, b = find(e.vertices[0]), find(e.vertices[1])
    if a != b:
        parent[a] = b
island = [find(i) for i in range(len(P))]
island_top = {}
island_size = {}
for i, isl in enumerate(island):
    island_top[isl] = max(island_top.get(isl, -9.0), P[i][2])
    island_size[isl] = island_size.get(isl, 0) + 1
main_island = max(island_size, key=island_size.get)
log("островов в сетке: %d, главный — %d вершин" % (len(island_size), island_size[main_island]))


def part_of(i):
    p = P[i]
    if p[1] > back + 0.05 and abs(p[2] - tail_z) < 0.45 and abs(p[0]) < 0.25:
        return "tail"
    if is_head(p):        # the same jaw line as for the weights: the head and its bone are cut together
        return "head"
    b = dominant[i]
    if b in HAND_BONES:
        return "gloves"
    if b in LEG_BONES and p[2] < LEG_TOP:
        return "legs"
    return "body"


labels = [part_of(i) for i in range(len(P))]
counts = {}
for name in labels:
    counts[name] = counts.get(name, 0) + 1
log("части по вершинам:", counts)

# material with baked textures
src_mat = yak.data.materials[0] if yak.data.materials else None
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
if src_mat and src_mat.use_nodes:
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    for node in src_mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            img = node.image
            fname = "eq_yak_" + img.name.replace(".", "_") + ".png"
            img.filepath_raw = os.path.join(tex_dir, fname)
            img.file_format = "PNG"
            img.save()
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.label = img.name
            if bsdf and "normal" in img.name.lower():
                nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
                mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif bsdf and "metal" not in img.name.lower():
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            log("текстура", fname, "%dx%d" % tuple(img.size))

parts = {}
for name in ("body", "legs", "gloves", "head", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = yak.copy()
    ob.data = yak.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    keep_set = set(keep)
    # a face stays in the part if most of its vertices belong to this part
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if name == "tail":   # the tail is entirely on the pelvis, like the pony tail
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name=PELVIS).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    parts[name] = ob
    log("%s: %d вершин, %d граней" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
bpy.data.objects.remove(yak)

# ---------------------------------------------------------------- 4. export
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts.values()]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
path = os.path.join(OUT, "eq_%s.fbx" % RACE)
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспорт", path)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "eq_%s.blend" % RACE))

# ---------------------------------------------------------------- 5. preview: the yak next to the pony
prev = os.path.join(OUT, "preview")
os.makedirs(prev, exist_ok=True)
scene = bpy.context.scene
for ob in pony.values():
    ob.hide_render = ob.name in ("eq_twilight_mane", "eq_twilight_tail") or False
    ob.location.x -= 1.4   # the pony is moved left, to compare heights
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 3.2
scene.collection.objects.link(cam)
scene.camera = cam
for view, loc, rot in (("front", (-0.7, -6, 1.05), (math.pi / 2, 0, 0)),
                       ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2))):
    cam.location = loc
    cam.rotation_euler = rot
    scene.render.filepath = os.path.join(prev, "yak_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
