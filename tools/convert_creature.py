# Converting a third-party quadruped model into an anthro Bannerlord character.
#
#   blender --background --factory-startup --python convert_creature.py -- <kind> <model.glb>
#           <skeleton.fbx> <output folder> [--preview]
#
# <kind> is a key from tools/creature_data.py (griffon, yak); the joint coordinates are recorded there,
# taken by hand from views of the model with a coordinate grid (tools/preview_model.py). <skeleton.fbx> is
# any of our exports with the human Bannerlord skeleton (assets/twilight_anthro/export/eq_twilight.fbx).
#
# Steps:
#   1. The model is turned to face -Y and welded: the generator outputs a "soup" of disconnected
#      triangles, and any deformation tears such a mesh apart.
#   2. Thin parts (wings, tail) are separated right away - they cannot be remeshed by volume, the
#      feathers would stick together into plates. They go as separate items, wholly on one bone.
#   3. The torso is remeshed by volume (voxel remesh): the result is one closed shell without
#      internal junk. The UVs are transferred from the old model so the texture stays.
#   4. Everything is scaled so that the creature's spine becomes human-sized.
#   5. From the anatomy map a "creature" skeleton is built - a copy of the human one with the bones
#      moved to the creature's joints. The mesh is bound to it: each body region only to its own
#      bones (the belly does not grab a leg), weights are smoothed over neighbours.
#   6. The creature skeleton is given the human pose: the torso stands upright, the front legs
#      spread out as arms, the hind legs straighten. The pose is baked into the geometry.
#   7. Weights are recomputed for the human skeleton and limited to three bones per vertex.
#   8. The mesh is cut into items (head, body, legs, hands) and written to FBX, textures to PNG.
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_data import BONES, CHAINS, CREATURES  # noqa: E402

_args = [a for a in sys.argv[sys.argv.index("--") + 1:]]
PREVIEW = "--preview" in _args
NO_SCALE = "--no-scale" in _args
_args = [a for a in _args if not a.startswith("--")]
KEY, GLB, SKEL_FBX, OUT = _args[:4]
CARD = CREATURES[KEY]
PREFIX = "eq_" + CARD["name"]
os.makedirs(OUT, exist_ok=True)
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

MAX_INFLUENCES = 3      # as in vanilla Bannerlord meshes
MIN_WEIGHT = 0.02
# Bones whose length is not changed when retargeting the pose: head, hands and feet must keep
# their size, otherwise the beak stretches upward and the claws sideways.
NO_STRETCH = {"head", "l_hand", "r_hand", "l_foot", "r_foot", "l_toe", "r_toe"}
# which bones serve which body region
REGION_BONES = {
    "arms": ["l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_hand_end",
             "r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_hand_end"],
    "legs": ["l_thigh", "l_calf", "l_foot", "l_toe", "l_toe_end",
             "r_thigh", "r_calf", "r_foot", "r_toe", "r_toe_end"],
    "head": ["neck", "head", "head_end"],
    "torso": ["pelvis", "spine", "spine1", "spine2", "l_clavicle", "r_clavicle", "neck"],
}
# Regions in the already human pose - the final weights are computed from them.
HUMAN_REGIONS = {
    "arms": {"min_abs_x": 0.22},
    "head": {"min_z": 1.46},
    "legs": {"max_z": 0.90},
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
vl = bpy.context.view_layer


def log(*a):
    print("[creature]", *a, flush=True)


def select_only(objs, active):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def match(q, rule):
    """Whether a point (in anatomy map coordinates) matches a region rule."""
    for cond, value in rule.items():
        if cond == "min_z" and q.z < value:
            return False
        if cond == "max_z" and q.z > value:
            return False
        if cond == "min_y" and q.y < value:
            return False
        if cond == "max_y" and q.y > value:
            return False
        if cond == "min_x" and q.x < value:
            return False
        if cond == "max_x" and q.x > value:
            return False
        if cond == "min_abs_x" and abs(q.x) < value:
            return False
    return True


def separate(ob, indices, name):
    """Separates vertices into a new object (and returns it)."""
    if not indices:
        return None
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    chosen = set(indices)
    for i in indices:
        ob.data.vertices[i].select = True
    # a face goes along with the vertices only if fully selected - mark such faces ourselves,
    # otherwise the new object is left with a point cloud without a single face
    for f in ob.data.polygons:
        f.select = all(i in chosen for i in f.vertices)
    was = set(scene.objects)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    fresh = [o for o in scene.objects if o not in was]
    if not fresh:
        return None
    fresh[0].name = name
    return fresh[0]


# ---------------------------------------------------------------- 1. Bannerlord skeleton
before = set(scene.objects)
bpy.ops.import_scene.fbx(filepath=SKEL_FBX, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
imported = [o for o in scene.objects if o not in before]
skel = next(o for o in imported if o.type == "ARMATURE")
for o in imported:
    if o is not skel:
        bpy.data.objects.remove(o, do_unlink=True)
# In the file the skeleton is stored at scale 0.01; the rotation is kept as is (it is what brings the
# bones into the usual Z-up axes), only the scale is changed - we work in metres.
skel.scale = (1, 1, 1)
vl.update()
log("скелет: %d костей" % len(skel.data.bones))

missing = [k for k in CARD["joints"] if BONES[k] not in skel.data.bones]
if missing:
    raise SystemExit("в скелете нет костей для суставов: %s" % ", ".join(missing))

H_PELVIS = skel.matrix_world @ skel.data.bones[BONES["pelvis"]].head_local
H_NECK = skel.matrix_world @ skel.data.bones[BONES["neck"]].head_local

# ---------------------------------------------------------------- 2. model
images_before = set(bpy.data.images.keys())
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLB)
new = [o for o in scene.objects if o not in before]
meshes = [o for o in new if o.type == "MESH"]
for o in new:
    if o.type != "MESH":
        bpy.data.objects.remove(o, do_unlink=True)
select_only(meshes, meshes[0])
if len(meshes) > 1:
    bpy.ops.object.join()
mesh = vl.objects.active
mesh.name = PREFIX
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
log("модель: %d вершин, %d треугольников" % (len(mesh.data.vertices), tri_count(mesh)))

# turn to face -Y
turn = Matrix.Rotation(math.radians(CARD["yaw"]), 4, "Z")
mesh.matrix_world = turn @ mesh.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
J = {k: turn @ Vector(v) for k, v in CARD["joints"].items()}

# welding: in the generated model neighbouring triangles do not share vertices
select_only([mesh], mesh)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0008)
bpy.ops.object.mode_set(mode="OBJECT")
log("после сшивки: %d вершин, %d треугольников" % (len(mesh.data.vertices), tri_count(mesh)))

# wings and tail are separated before remeshing: voxel remesh would glue thin feathers into plates
to_card = turn.inverted()
extras = {}
for name, rule in CARD.get("extras", {}).items():
    idx = [v.index for v in mesh.data.vertices if match(to_card @ (mesh.matrix_world @ v.co), rule)]
    part = separate(mesh, idx, "%s_%s" % (PREFIX, name))
    if part:
        extras[name] = part
        log("отделено: %s, %d вершин" % (part.name, len(part.data.vertices)))

# Volume remesh of the torso: one closed shell instead of a soup of shells.
source = mesh.copy()
source.data = mesh.data.copy()
scene.collection.objects.link(source)
source.name = PREFIX + "_source"
select_only([mesh], mesh)
mesh.data.remesh_voxel_size = CARD.get("voxel", 0.012)
mesh.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
log("туловище пересобрано (шаг %.3f м): %d вершин, %d треугольников"
    % (mesh.data.remesh_voxel_size, len(mesh.data.vertices), tri_count(mesh)))

target = CARD["target_tris"]
if tri_count(mesh) > target * 1.2:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = min(1.0, target / tri_count(mesh))
    bpy.ops.object.modifier_apply(modifier=dec.name)
    log("упрощено до %d треугольников" % tri_count(mesh))

# UVs and material come from the old model
if not mesh.data.uv_layers:
    mesh.data.uv_layers.new(name="UVMap")
mesh.data.materials.clear()
for m in source.data.materials:
    mesh.data.materials.append(m)
dt = mesh.modifiers.new("uv", "DATA_TRANSFER")
dt.object = source
dt.use_loop_data = True
dt.data_types_loops = {"UV"}
dt.loop_mapping = "POLYINTERP_NEAREST"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.data.objects.remove(source, do_unlink=True)
log("развёртка перенесена со старой модели")

# thin parts are simplified with ordinary decimation
for part in extras.values():
    if tri_count(part) > 4000:
        select_only([part], part)
        dec = part.modifiers.new("dec", "DECIMATE")
        dec.ratio = 4000 / tri_count(part)
        bpy.ops.object.modifier_apply(modifier=dec.name)

# scale: creature spine = human spine, pelvis to pelvis
spine_len = (J["neck"] - J["pelvis"]).length
k = (H_NECK - H_PELVIS).length / spine_len
fit = Matrix.Translation(H_PELVIS) @ Matrix.Scale(k, 4) @ Matrix.Translation(-J["pelvis"])
log("масштаб модели x%.3f (позвоночник %.3f -> %.3f м)" % (k, spine_len, (H_NECK - H_PELVIS).length))
for ob in [mesh] + list(extras.values()):
    select_only([ob], ob)
    ob.matrix_world = fit @ ob.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
J = {key: fit @ v for key, v in J.items()}
to_card = turn.inverted() @ fit.inverted()

# ---------------------------------------------------------------- 3. creature skeleton
qrig = skel.copy()
qrig.data = skel.data.copy()
qrig.name = "creature_rig"
scene.collection.objects.link(qrig)
select_only([qrig], qrig)
to_rig = qrig.matrix_world.inverted()
bpy.ops.object.mode_set(mode="EDIT")
eb = qrig.data.edit_bones
mapped = set()
for chain in CHAINS:
    for a, b in zip(chain, chain[1:]):
        if a not in J or b not in J:
            continue
        bone = eb[BONES[a]]
        bone.head = to_rig @ J[a]
        bone.tail = to_rig @ J[b]
        mapped.add(BONES[a])
# The roll of each bone follows the human bone of the same name. If left arbitrary, each bone
# turns by its own angle around itself when retargeting the pose, neighbouring vertices twist
# in different directions, and the mesh falls apart into shreds.
for name in mapped:
    z_human = skel.data.bones[name].matrix_local.to_3x3() @ Vector((0.0, 0.0, 1.0))
    eb[name].align_roll(z_human)
bpy.ops.object.mode_set(mode="OBJECT")
for b in qrig.data.bones:
    b.use_deform = b.name in mapped
log("звериный скелет: %d костей участвуют в деформации" % len(mapped))

qbones = [(b.name, qrig.matrix_world @ b.head_local, qrig.matrix_world @ b.tail_local)
          for b in qrig.data.bones if b.use_deform]


# ---------------------------------------------------------------- 4. binding
def smooth_weights(ob, rounds=6, factor=0.5):
    """Smoothing weights over neighbours: otherwise a sharp seam remains at region borders and
    rotating the bones tears the mesh into shreds."""
    me = ob.data
    n = len(me.vertices)
    neigh = [[] for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        neigh[a].append(b)
        neigh[b].append(a)
    groups = list(ob.vertex_groups)
    if not groups:
        return
    col = {g.index: i for i, g in enumerate(groups)}
    W = np.zeros((n, len(groups)), np.float32)
    for v in me.vertices:
        for g in v.groups:
            W[v.index, col[g.group]] = g.weight
    for _ in range(rounds):
        nxt = W.copy()
        for i in range(n):
            if neigh[i]:
                nxt[i] = W[i] * (1.0 - factor) + W[neigh[i]].mean(0) * factor
        W = nxt
    W /= np.maximum(W.sum(1, keepdims=True), 1e-6)
    for gi, g in enumerate(groups):
        g.remove(list(range(n)))
        for i in np.nonzero(W[:, gi] > 0.003)[0]:
            g.add([int(i)], float(W[i, gi]), "REPLACE")


def weight_by_bones(ob, bones, regions, to_space, count=2, power=2.0):
    """Binding by distance to bones, but only to the bones of the vertex's own body region."""
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    names = {name for name, _a, _b in bones}
    groups = {name: ob.vertex_groups.new(name=name) for name in names}
    allowed = {region: {BONES[k] for k in keys if BONES[k] in names}
               for region, keys in REGION_BONES.items()}
    mw = ob.matrix_world
    for v in ob.data.vertices:
        p = mw @ v.co
        q = to_space @ p
        region = next((name for name, rule in regions.items() if match(q, rule)), "torso")
        pool = allowed.get(region) or names
        dists = []
        for name, a, b in bones:
            if name not in pool:
                continue
            ab = b - a
            t = min(max((p - a).dot(ab) / ab.length_squared, 0.0), 1.0)
            dists.append(((a + ab * t - p).length, name))
        dists.sort()
        near = dists[:count] or [(1.0, BONES["pelvis"])]
        weights = [(name, 1.0 / max(d, 1e-4) ** power) for d, name in near]
        total = sum(w for _n, w in weights)
        for name, w in weights:
            groups[name].add([v.index], w / total, "REPLACE")


def weight_rigid(ob, bone_name):
    """The whole part on one bone - that is how the wings and tail ride."""
    for vg in list(ob.vertex_groups):
        ob.vertex_groups.remove(vg)
    vg = ob.vertex_groups.new(name=bone_name)
    vg.add([v.index for v in ob.data.vertices], 1.0, "REPLACE")


# One bone per vertex: the creature's skin is split into rigid pieces. Soft binding does not work here -
# when straightening a quadruped, neighbouring skin pieces drift apart by tens of centimetres, and the mesh
# turns into rags.
weight_by_bones(mesh, qbones, CARD.get("regions", {}), to_card, count=1)
rigid = CARD.get("rigid", {})
for name, part in extras.items():
    weight_rigid(part, BONES[rigid.get(name, "spine1")])
log("привязка: туловище по областям%s" % (", жёстко: " + ", ".join(extras) if extras else ""))

for ob in [mesh] + list(extras.values()):
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = qrig

if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_prepose.blend"))

# ---------------------------------------------------------------- 5. human pose
# ---------------------------------------------------------------- 5. human pose
# Pose retargeting "piece by piece". Soft binding does not work here: when straightening a quadruped,
# neighbouring skin areas drift apart by tens of centimetres, and the mesh turns into rags.
# So the hide is cut into pieces by bone, each piece is moved as a whole (rotation, shift
# and stretch along the bone), faces between different pieces are deleted, and then everything is fused
# into one shell by a volume remesh - the seams at the joints close up.
bone_index = {}
names = {g.index: g.name for g in mesh.vertex_groups}
for v in mesh.data.vertices:
    best, bw = None, -1.0
    for g in v.groups:
        if g.weight > bw:
            best, bw = names[g.group], g.weight
    bone_index[v.index] = best

moves = {}
for bone in qrig.data.bones:
    if not bone.use_deform:
        continue
    target = skel.data.bones[bone.name]
    k = target.length / bone.length if bone.length > 1e-6 else 1.0
    if NO_SCALE or next((key for key, n in BONES.items() if n == bone.name), "") in NO_STRETCH:
        k = 1.0
    k = min(max(k, 0.6), 2.2)
    rest = qrig.matrix_world @ bone.matrix_local
    want = skel.matrix_world @ target.matrix_local @ Matrix.Scale(k, 4, Vector((0, 1, 0)))
    moves[bone.name] = want @ rest.inverted()

mw = mesh.matrix_world.copy()
inv = mw.inverted()
for v in mesh.data.vertices:
    move = moves.get(bone_index.get(v.index))
    if move is not None:
        v.co = inv @ (move @ (mw @ v.co))

# faces stretched between different bones are discarded - otherwise fusing turns them
# into webbing across the body
select_only([mesh], mesh)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bpy.ops.object.mode_set(mode="OBJECT")
cut = 0
for f in mesh.data.polygons:
    if len({bone_index.get(i) for i in f.vertices}) > 1:
        f.select = True
        cut += 1
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.delete(type="FACE")
bpy.ops.object.mode_set(mode="OBJECT")
log("куски переставлены, выброшено граней между кусками: %d" % cut)

bpy.data.objects.remove(qrig, do_unlink=True)

# Second remesh pass. When the creature is straightened, the skin between belly and leg stretches -
# where the quadruped had a smooth transition, the standing one gets a gap of a quarter metre.
# We remesh the shell once more, now in the human pose: what remains is a clean surface without
# stretched faces and self-intersections. The UVs are again taken from the previous state.
SKIP2 = False
posed_source = mesh.copy()
posed_source.data = mesh.data.copy()
scene.collection.objects.link(posed_source)
posed_source.name = PREFIX + "_posed_source"
select_only([mesh], mesh)
mesh.data.remesh_voxel_size = CARD.get("voxel", 0.012)
mesh.data.remesh_voxel_adaptivity = 0.0
if not SKIP2:
    bpy.ops.object.voxel_remesh()
if not SKIP2 and tri_count(mesh) > CARD["target_tris"] * 1.2:
    dec = mesh.modifiers.new("dec", "DECIMATE")
    dec.ratio = min(1.0, CARD["target_tris"] / tri_count(mesh))
    bpy.ops.object.modifier_apply(modifier=dec.name)
if not mesh.data.uv_layers:
    mesh.data.uv_layers.new(name="UVMap")
mesh.data.materials.clear()
for m in posed_source.data.materials:
    mesh.data.materials.append(m)
dt = mesh.modifiers.new("uv", "DATA_TRANSFER")
dt.object = posed_source
dt.use_loop_data = True
dt.data_types_loops = {"UV"}
dt.loop_mapping = "POLYINTERP_NEAREST"
bpy.ops.object.modifier_apply(modifier=dt.name)
bpy.data.objects.remove(posed_source, do_unlink=True)
log("оболочка пересобрана в стоячей позе: %d вершин, %d треугольников"
    % (len(mesh.data.vertices), tri_count(mesh)))

_lo = [min((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices) for i in range(3)]
_hi = [max((mesh.matrix_world @ v.co)[i] for v in mesh.data.vertices) for i in range(3)]
log("поза применена, туловище: %s .. %s" % ([round(v, 2) for v in _lo], [round(v, 2) for v in _hi]))

if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_posed.blend"))

# ---------------------------------------------------------------- 6. weights for the human skeleton
wa = skel.copy()
wa.data = skel.data.copy()
wa.name = "weighting_rig"
scene.collection.objects.link(wa)
select_only([wa], wa)
bpy.ops.object.mode_set(mode="EDIT")
web = wa.data.edit_bones
for chain in CHAINS:
    names = [BONES[c] for c in chain if c in BONES]
    for a, b in zip(names, names[1:]):
        if a in web and b in web:
            web[a].tail = web[b].head
bpy.ops.object.mode_set(mode="OBJECT")
for b in wa.data.bones:
    b.use_deform = b.name in {BONES[k] for k in CARD["joints"]} and not b.name.endswith("notused")
vl.update()
hbones = [(b.name, wa.matrix_world @ b.head_local, wa.matrix_world @ b.tail_local)
          for b in wa.data.bones if b.use_deform]
weight_by_bones(mesh, hbones, HUMAN_REGIONS, Matrix.Identity(4), count=3)
smooth_weights(mesh, rounds=4)
bpy.data.objects.remove(wa, do_unlink=True)


def limit_weights(ob):
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        pairs = sorted(((g.weight, names[g.group]) for g in v.groups), reverse=True)
        pairs = [(n, w) for w, n in pairs if w > MIN_WEIGHT][:MAX_INFLUENCES]
        total = sum(w for _n, w in pairs) or 1.0
        for name in {names[g.group] for g in v.groups}:
            ob.vertex_groups[name].remove([v.index])
        for name, w in pairs:
            ob.vertex_groups[name].add([v.index], w / total, "REPLACE")


limit_weights(mesh)
log("веса пересчитаны по человеческому скелету, не больше %d костей на вершину" % MAX_INFLUENCES)

# ---------------------------------------------------------------- 7. items
PART_BONES = {
    "head": {BONES["head"], BONES["neck"], BONES["head_end"]},
    "gloves": {BONES["l_hand"], BONES["r_hand"], BONES["l_hand_end"], BONES["r_hand_end"]},
    "legs": {BONES["l_thigh"], BONES["l_calf"], BONES["l_foot"], BONES["l_toe"],
             BONES["r_thigh"], BONES["r_calf"], BONES["r_foot"], BONES["r_toe"]},
}
parts = dict(extras)
for part_name, bones in PART_BONES.items():
    names = {g.index: g.name for g in mesh.vertex_groups}
    idx = []
    for v in mesh.data.vertices:
        best, bw = None, -1.0
        for g in v.groups:
            if g.weight > bw:
                best, bw = names[g.group], g.weight
        if best in bones:
            idx.append(v.index)
    part = separate(mesh, idx, "%s_%s" % (PREFIX, part_name))
    if part:
        parts[part_name] = part
        log("предмет %s: %d вершин" % (part.name, len(part.data.vertices)))
mesh.name = PREFIX + "_body"
parts["body"] = mesh
log("предмет %s: %d вершин" % (mesh.name, len(mesh.data.vertices)))

# ---------------------------------------------------------------- 8. textures and export
for img in bpy.data.images:
    if img.size[0] == 0 or img.name in images_before:
        continue
    kind = "n" if "normal" in img.name.lower() else (
        "s" if "metallic" in img.name.lower() or "_rm" in img.name.lower() else "d")
    path = os.path.join(TEX_DIR, "%s_%s.png" % (PREFIX, kind))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    log("текстура %s -> %s" % (img.name, os.path.basename(path)))

for part in parts.values():
    part.parent = skel
    part.matrix_parent_inverse = skel.matrix_world.inverted()   # otherwise the skeleton rotation is applied twice
    mod = part.modifiers.new("Armature", "ARMATURE")
    mod.object = skel

select_only(list(parts.values()) + [skel], skel)
fbx = os.path.join(OUT, PREFIX + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y",
                         bake_space_transform=False, mesh_smooth_type="FACE",
                         path_mode="COPY", embed_textures=False)
log("записан", fbx)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + ".blend"))
log("записан", os.path.join(OUT, PREFIX + ".blend"))
