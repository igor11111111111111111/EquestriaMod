# Rigged beast model (glb with a skeleton) -> Bannerlord anthro character.
#
#   blender --background --factory-startup --python convert_rigged.py -- <species> <model.glb>
#           <skeleton.fbx> <output folder> [--preview] [--stop-tpose]
#
# Unlike convert_creature.py, here the model has its own skeleton and proper skinning
# (for example, rigged in Meshy). That changes everything: the skin can be bent any way, it follows
# the bones and does not tear. Workflow:
#   1. Import, junk cleanup (Meshy puts a sphere next to it), scale up to meters.
#   2. The rest pose is taken from the first animation frame: in such models the rest itself is often degenerate.
#   3. The beast is put into a stance: each bone gets a direction from the "tpose" map
#      (spine up, front legs out to the sides, hind legs down) - a plain rotation along the chain.
#   4. The pose is baked, the model is scaled to the Bannerlord skeleton.
#   5. The beast's bones are turned toward the Bannerlord bones of the same name ("bone_map"), the pose
#      is baked again - now the joints are where the engine expects them.
#   6. Vertex groups are renamed to Bannerlord bones, the mesh is bound to its skeleton,
#      cut into items and written to FBX.
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from creature_data import BONES, CHAINS, CREATURES  # noqa: E402

_args = [a for a in sys.argv[sys.argv.index("--") + 1:]]
PREVIEW = "--preview" in _args
STOP_TPOSE = "--stop-tpose" in _args
_args = [a for a in _args if not a.startswith("--")]
KEY, GLB, SKEL_FBX, OUT = _args[:4]
GLB, SKEL_FBX, OUT = os.path.abspath(GLB), os.path.abspath(SKEL_FBX), os.path.abspath(OUT)
CARD = CREATURES[KEY]
PREFIX = "eq_" + CARD["name"]
os.makedirs(OUT, exist_ok=True)
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
vl = bpy.context.view_layer


def log(*a):
    print("[rigged]", *a, flush=True)


def select_only(objs, active):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


def mesh_bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ---------------------------------------------------------------- 1. Bannerlord skeleton
before = set(scene.objects)
bpy.ops.import_scene.fbx(filepath=SKEL_FBX, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
imported = [o for o in scene.objects if o not in before]
skel = next(o for o in imported if o.type == "ARMATURE")
for o in imported:
    if o is not skel:
        bpy.data.objects.remove(o, do_unlink=True)
skel.scale = (1, 1, 1)
vl.update()
H = {key: skel.matrix_world @ skel.data.bones[name].head_local for key, name in BONES.items()
     if name in skel.data.bones}
log("скелет Bannerlord: %d костей, таз на высоте %.2f м" % (len(skel.data.bones), H["pelvis"].z))

# ---------------------------------------------------------------- 2. model with a skeleton
images_before = set(bpy.data.images.keys())
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLB)
new = [o for o in scene.objects if o not in before]
for junk in [o for o in new if o.type == "MESH" and len(o.vertex_groups) == 0]:
    log("выброшен мусорный объект", junk.name)
    bpy.data.objects.remove(junk, do_unlink=True)
new = [o for o in scene.objects if o not in before]
beast_rig = next(o for o in new if o.type == "ARMATURE")
beast = next(o for o in new if o.type == "MESH")
for o in new:
    if o not in (beast_rig, beast) and o.type not in ("MESH", "ARMATURE"):
        bpy.data.objects.remove(o, do_unlink=True)

# rest pose from the first animation frame: in Meshy models the rest itself can be degenerate
scene.frame_set(int(scene.frame_start))
vl.update()
select_only([beast_rig], beast_rig)
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.select_all(action="SELECT")
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode="OBJECT")
beast_rig.animation_data_clear()
vl.update()

# to meters: the model comes in centimeters (armature scale 0.01)
scale_up = Matrix.Scale(100.0, 4)
for o in (beast_rig, beast):
    o.matrix_world = scale_up @ o.matrix_world
select_only([beast_rig, beast], beast_rig)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
vl.update()
lo, hi = mesh_bounds(beast)
log("модель: %d вершин, %d костей, габариты %.2f x %.2f x %.2f м"
    % (len(beast.data.vertices), len(beast_rig.data.bones), *(hi - lo)))

# turn to face -Y
turn = Matrix.Rotation(math.radians(CARD.get("rigged_yaw", CARD["yaw"])), 4, "Z")
for o in (beast_rig, beast):
    o.matrix_world = turn @ o.matrix_world
select_only([beast_rig, beast], beast_rig)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
vl.update()


def bone_dir(pb):
    return (pb.tail - pb.head).normalized()


def aim(rig, name, target, ref=None):
    """Turns the bone so that the direction to joint ref (or the bone's own tail)
    points the given way. Going via the joint is more reliable: in foreign skeletons a bone often points
    not where the limb goes (in the griffon the "chest" points toward the tail)."""
    pb = rig.pose.bones.get(name)
    if pb is None:
        return False
    want = Vector(target).normalized()
    if ref and rig.pose.bones.get(ref):
        cur = (rig.pose.bones[ref].head - pb.head)
        cur = cur.normalized() if cur.length > 1e-6 else bone_dir(pb)
    else:
        cur = bone_dir(pb)
    if cur.length < 1e-6 or cur.angle(want) < 1e-4:
        return True
    rot = cur.rotation_difference(want).to_matrix().to_4x4()
    m = pb.matrix.copy()
    pivot = Matrix.Translation(m.translation)
    pb.matrix = pivot @ rot @ pivot.inverted() @ m
    vl.update()
    return True


def spin(rig, name, degrees):
    """Rotates the bone around its head by the given angles (world axes X, Y, Z).
    Needed to raise the torso: "aiming" does not help here - in a quadruped the neck already
    points up and forward, so there is nothing to aim at, but the whole rib cage has to be raised."""
    pb = rig.pose.bones.get(name)
    if pb is None:
        return False
    rx, ry, rz = (math.radians(a) for a in degrees)
    rot = Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ Matrix.Rotation(rx, 4, "X")
    m = pb.matrix.copy()
    pivot = Matrix.Translation(m.translation)
    pb.matrix = pivot @ rot @ pivot.inverted() @ m
    vl.update()
    return True


# ---------------------------------------------------------------- 3. stance
TPOSE = CARD.get("tpose", {})
select_only([beast_rig], beast_rig)
bpy.ops.object.mode_set(mode="POSE")
order = sorted(beast_rig.data.bones, key=lambda b: len(b.parent_recursive))
done = 0
for bone in order:
    spec = TPOSE.get(bone.name)
    if spec is None:
        continue
    if isinstance(spec, dict) and "rotate" in spec:
        done += spin(beast_rig, bone.name, spec["rotate"])
    elif isinstance(spec, dict):
        done += aim(beast_rig, bone.name, spec["dir"], spec.get("ref"))
    else:
        done += aim(beast_rig, bone.name, spec)
bpy.ops.object.mode_set(mode="OBJECT")
vl.update()
log("стойка: развёрнуто костей %d из %d" % (done, len(TPOSE)))

# bake the stance into the geometry
select_only([beast], beast)
for m in list(beast.modifiers):
    if m.type == "ARMATURE":
        bpy.ops.object.modifier_apply(modifier=m.name)
select_only([beast_rig], beast_rig)
bpy.ops.object.mode_set(mode="POSE")
bpy.ops.pose.select_all(action="SELECT")
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode="OBJECT")
mod = beast.modifiers.new("Armature", "ARMATURE")
mod.object = beast_rig
vl.update()
lo, hi = mesh_bounds(beast)
log("после стойки: габариты %.2f x %.2f x %.2f м" % tuple(hi - lo))

if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + "_tpose.blend"))
    log("записан", os.path.join(OUT, PREFIX + "_tpose.blend"))
if STOP_TPOSE:
    raise SystemExit(0)

# ---------------------------------------------------------------- 4. size to fit the Bannerlord skeleton
BONE_MAP = CARD.get("bone_map", {})
rig_head = beast_rig.pose.bones.get("head") or beast_rig.pose.bones[0]
hips = beast_rig.pose.bones.get("Hips") or beast_rig.pose.bones[0]
beast_span = (rig_head.head - hips.head).length
human_span = (H["head"] - H["pelvis"]).length
k = human_span / max(beast_span, 1e-6)
fit = Matrix.Translation(H["pelvis"]) @ Matrix.Scale(k, 4) @ Matrix.Translation(-hips.head)
for o in (beast_rig, beast):
    o.matrix_world = fit @ o.matrix_world
select_only([beast_rig, beast], beast_rig)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
vl.update()
lo, hi = mesh_bounds(beast)
log("подгонка под скелет: масштаб x%.2f, рост %.2f м (таз->голова %.2f -> %.2f)"
    % (k, hi.z - lo.z, beast_span, human_span))

# ---------------------------------------------------------------- 5. bones to Bannerlord bones
select_only([beast_rig], beast_rig)
bpy.ops.object.mode_set(mode="POSE")
# The direction of a Bannerlord bone is taken as "from its joint to the next one along the chain":
# the bone's own tail in the vanilla skeleton does not point along the limb (the pelvis bone,
# for example, points backward), so it cannot be aimed by.
NEXT_KEY = {}
for chain in CHAINS:
    for a, b in zip(chain, chain[1:]):
        NEXT_KEY[a] = b
RETARGET = CARD.get("retarget", {})
# Aiming and stretching are done in several passes: stretching a parent moves the child's
# joint, and its direction drifts off again. Three passes are enough for everything to converge.
moved = 0
for _pass in range(3):
    for bone in sorted(beast_rig.data.bones, key=lambda b: len(b.parent_recursive)):
        spec = RETARGET.get(bone.name)
        if spec is None:
            continue
        key = spec["key"]
        nxt = spec.get("to") or NEXT_KEY.get(key)
        if key not in H or nxt not in H:
            continue
        want = H[nxt] - H[key]
        if want.length < 1e-6:
            continue
        moved += aim(beast_rig, bone.name, want, spec.get("ref"))
        # Length is fitted only for limbs: arms and legs must reach the human
        # joints (otherwise the weapon ends up outside the hand). The beast's neck and torso are not
        # shortened - it should stay long-bodied.
        if not spec.get("stretch"):
            continue
        pb = beast_rig.pose.bones.get(bone.name)
        ref = beast_rig.pose.bones.get(spec.get("ref", ""))
        if pb is not None and ref is not None:
            cur = (ref.head - pb.head).length
            if cur > 1e-5:
                factor = min(max(want.length / cur, 0.35), 3.0)
                pb.scale = (1.0, pb.scale.y * factor, 1.0)
                vl.update()
moved //= 3

for bone_name, spec in RETARGET.items():
    pb = beast_rig.pose.bones.get(bone_name)
    ref = beast_rig.pose.bones.get(spec.get("ref", ""))
    key, nxt = spec["key"], NEXT_KEY.get(spec["key"])
    if pb is None or ref is None or key not in H or nxt not in H:
        continue
    cur = (ref.head - pb.head)
    want = H[nxt] - H[key]
    if cur.length > 1e-6:
        log("  %-14s угол до цели %5.1f°, длина зверя %.3f против %.3f у человека"
            % (bone_name, math.degrees(cur.angle(want)), cur.length, want.length))
bpy.ops.object.mode_set(mode="OBJECT")
vl.update()
select_only([beast], beast)
for m in list(beast.modifiers):
    if m.type == "ARMATURE":
        bpy.ops.object.modifier_apply(modifier=m.name)
log("кости довёрнуты к костям Bannerlord: %d" % moved)

# ---------------------------------------------------------------- 6. weights onto the Bannerlord skeleton
names = {g.index: g.name for g in beast.vertex_groups}
weights = {}          # vertex -> {Bannerlord bone: weight}
for v in beast.data.vertices:
    acc = {}
    for g in v.groups:
        key = BONE_MAP.get(names[g.group])
        target = BONES.get(key)
        if target is None:
            continue
        acc[target] = acc.get(target, 0.0) + g.weight
    weights[v.index] = acc
for vg in list(beast.vertex_groups):
    beast.vertex_groups.remove(vg)
groups = {}
for v_index, acc in weights.items():
    total = sum(acc.values()) or 1.0
    for name, w in sorted(acc.items(), key=lambda kv: -kv[1])[:3]:
        if name not in groups:
            groups[name] = beast.vertex_groups.new(name=name)
        groups[name].add([v_index], w / total, "REPLACE")
log("веса переписаны на кости Bannerlord: %d групп" % len(groups))

for m in list(beast.modifiers):
    beast.modifiers.remove(m)
bpy.data.objects.remove(beast_rig, do_unlink=True)
beast.parent = skel
beast.matrix_parent_inverse = skel.matrix_world.inverted()
mod = beast.modifiers.new("Armature", "ARMATURE")
mod.object = skel
beast.name = PREFIX + "_body"

# ---------------------------------------------------------------- 7. textures and export
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

select_only([beast, skel], skel)
fbx = os.path.join(OUT, PREFIX + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y",
                         bake_space_transform=False, mesh_smooth_type="FACE",
                         path_mode="COPY", embed_textures=False)
log("записан", fbx)
if PREVIEW:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, PREFIX + ".blend"))
    log("записан", os.path.join(OUT, PREFIX + ".blend"))
