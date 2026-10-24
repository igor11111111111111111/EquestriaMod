# Building a race from someone else's model: animal details on the ready-made anthro pony body.
#
#   blender --background --factory-startup --python make_creature_parts.py -- <kind> <model.glb>
#           <pony.blend> <output folder> [--preview]
#
# What it does: cuts out of the quadruped model the parts that need no unfolding (the head with
# beak or horns, wings, tail, claws), places each one in its spot next to a bone
# of the Bannerlord human skeleton and rigidly binds it to it. The torso, arms and legs are taken
# ready-made from our anthro pony; they are already bound and animate correctly.
#
# Why this way and not "unfold the whole model": a quadruped has no geometry where
# a standing figure must have a flank, armpit and groin, and automatic unfolding tears the skin there (tested
# in four ways, see docs/reference/creatures). The details, on the other hand, are transferred rigidly and whole,
# so they look exactly as the generator sculpted them.
#
# Detail sizes and rotations are in tools/creature_data.py, key "graft".
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_data import BONES, CREATURES  # noqa: E402

_args = [a for a in sys.argv[sys.argv.index("--") + 1:]]
PREVIEW = "--preview" in _args
_args = [a for a in _args if not a.startswith("--")]
KEY, GLB, PONY, OUT = _args[:4]
OUT = os.path.abspath(OUT)      # paths must be absolute: Blender saves images
GLB = os.path.abspath(GLB)      # relative to the open .blend, not the current folder
CARD = CREATURES[KEY]
PREFIX = "eq_" + CARD["name"]
os.makedirs(OUT, exist_ok=True)
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)


def log(*a):
    print("[parts]", *a, flush=True)


# ---------------------------------------------------------------- 1. base: the pony with skeleton
bpy.ops.wm.open_mainfile(filepath=PONY)
scene = bpy.context.scene
vl = bpy.context.view_layer
skel = next(o for o in scene.objects if o.type == "ARMATURE")
pony_meshes = {o.name: o for o in scene.objects if o.type == "MESH"}
log("основа: скелет %s, мешей пони %d" % (skel.name, len(pony_meshes)))


def select_only(objs, active):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


def bone_head(key):
    return skel.matrix_world @ skel.data.bones[BONES[key]].head_local


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def match(q, rule):
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


# ---------------------------------------------------------------- 2. the animal model
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
beast = vl.objects.active
beast.name = PREFIX + "_beast"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# turn the muzzle to -Y, the way a Bannerlord character faces
turn = Matrix.Rotation(math.radians(CARD["yaw"]), 4, "Z")
beast.matrix_world = turn @ beast.matrix_world
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# stitching the "soup": neighbouring triangles of the generator's model do not share vertices
select_only([beast], beast)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0008)
bpy.ops.object.mode_set(mode="OBJECT")
log("модель зверя: %d вершин, %d треугольников" % (len(beast.data.vertices), tri_count(beast)))


def separate(ob, indices, name):
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
    # a face moves along with its vertices only if it is selected entirely; we mark such faces ourselves,
    # otherwise the new object is left with a cloud of points without a single face
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


def drop_small_islands(ob, min_verts=24):
    """Throws away small scraps: cutting by coordinates always catches foreign bits,
    and they hang in the air next to the detail."""
    me = ob.data
    parent = list(range(len(me.vertices)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    groups = {}
    for v in me.vertices:
        groups.setdefault(find(v.index), []).append(v.index)
    small = [i for cells in groups.values() if len(cells) < min_verts for i in cells]
    if not small:
        return 0
    select_only([ob], ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for i in small:
        me.vertices[i].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.delete(type="VERT")
    bpy.ops.object.mode_set(mode="OBJECT")
    return len(small)


def bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ---------------------------------------------------------------- 3. details
parts = {}
for name, spec in CARD.get("graft", {}).items():
    idx = [v.index for v in beast.data.vertices if match(beast.matrix_world @ v.co, spec["rule"])]
    part = separate(beast, idx, "%s_%s" % (PREFIX, name))
    if part is None:
        log("деталь %s: не нашлось вершин по правилу" % name)
        continue
    select_only([part], part)
    dropped = drop_small_islands(part)
    # the hole from the cut (the flat neck cut) is filled: otherwise from behind you can see the head is hollow
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # simplification to a reasonable number of triangles
    limit = spec.get("tris", 3000)
    if tri_count(part) > limit:
        dec = part.modifiers.new("dec", "DECIMATE")
        dec.ratio = limit / tri_count(part)
        bpy.ops.object.modifier_apply(modifier=dec.name)

    # scale: the detail must reach the given height (or width)
    lo, hi = bounds(part)
    size = hi - lo
    axis = {"z": 2, "y": 1, "x": 0}[spec.get("by", "z")]
    k = spec["size"] / max(size[axis], 1e-6)
    part.matrix_world = Matrix.Scale(k, 4) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # rotation around its own middle
    pitch, roll, yaw = (math.radians(a) for a in spec.get("rotate", (0, 0, 0)))
    lo, hi = bounds(part)
    mid = (lo + hi) / 2
    rot = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(pitch, 4, "X") @ Matrix.Rotation(roll, 4, "Y")
    part.matrix_world = Matrix.Translation(mid) @ rot @ Matrix.Translation(-mid) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # position: the given point of the detail is aligned with the point at the bone
    lo, hi = bounds(part)
    anchor = {"bottom": Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)),
              "top": Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z)),
              "middle": (lo + hi) / 2,
              "front": Vector(((lo.x + hi.x) / 2, lo.y, (lo.z + hi.z) / 2)),
              "back": Vector(((lo.x + hi.x) / 2, hi.y, (lo.z + hi.z) / 2))}[spec.get("anchor", "middle")]
    target = bone_head(spec["bone"]) + Vector(spec.get("offset", (0, 0, 0)))
    part.matrix_world = Matrix.Translation(target - anchor) @ part.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # rigid binding to the bone
    for vg in list(part.vertex_groups):
        part.vertex_groups.remove(vg)
    vg = part.vertex_groups.new(name=BONES[spec["bone"]])
    vg.add([v.index for v in part.data.vertices], 1.0, "REPLACE")
    part.parent = skel
    part.matrix_parent_inverse = skel.matrix_world.inverted()
    mod = part.modifiers.new("Armature", "ARMATURE")
    mod.object = skel
    parts[name] = part
    lo, hi = bounds(part)
    log("деталь %-6s: %d вершин (обрывков убрано %d), размер %.2f x %.2f x %.2f, на кости %s"
        % (name, len(part.data.vertices), dropped, *(hi - lo), BONES[spec["bone"]]))

bpy.data.objects.remove(beast, do_unlink=True)

# ---------------------------------------------------------------- 4. textures and export
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

# only our details and the skeleton go into the export: the body, legs and hands are taken from the pony as is
select_only(list(parts.values()) + [skel], skel)
fbx = os.path.join(OUT, PREFIX + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y",
                         bake_space_transform=False, mesh_smooth_type="FACE",
                         path_mode="COPY", embed_textures=False)
log("записан", fbx)
if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_parts.blend"))
    log("записан", os.path.join(OUT, PREFIX + "_parts.blend"))
