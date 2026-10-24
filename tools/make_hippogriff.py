# -*- coding: utf-8 -*-
"""Hippogriff from a ready-made model (T-pose, its own Mixamo skeleton) onto the pony skeleton, in parts, to FBX.

Run (headless Blender, opens the finished pony - it holds the skeleton and the binding sample):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_hippogriff.py \
      -- "<path to the hippogriff .fbx>" "<output folder>"

The model is the same kind as the griffon (tools/make_griffon.py): eagle head, wings growing from the
arms, bird feet. So the script is copied wholesale from the griffon one, including the proportions tuned
in game - we re-check them against previews and feedback.

Output parts:
  eq_hippogriff_body   - torso and arms (body_meta_mesh)
  eq_hippogriff_legs   - legs (legs_mesh)
  eq_hippogriff_gloves - hands (hands_mesh)
  eq_hippogriff_head   - head with beak (face_meta_mesh)
  eq_hippogriff_hair   - crown and nape feathers (hairstyle, tinted with the hair colour)
  eq_hippogriff_wings  - wings (item)
  eq_hippogriff_tail   - tail (item)
Next: import the FBX into the Modding Kit by hand, then tools/hippogriff_material.ps1.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "hippogriff"
HEIGHT = 2.00          # hippogriff height: the model's native height; at it the head sits as far from the
                       # pony head bone as on the accepted griffon (pony 1.86, griffon 1.95, yak 2.05)
MAT = "eq_hippogriff_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[hippogriff]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: (skel.matrix_world @ b.head_local) for b in skel.data.bones}

# ---------------------------------------------------------------- 1. import and A-pose
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=SRC)
added = [o for o in bpy.data.objects if o not in before]
hippo = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # generator junk: the placeholder sphere and other small meshes
    if ob.type == "MESH" and ob is not hippo:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (hippo.name, len(hippo.data.vertices), source_skel.name if source_skel else "нет"))

# ---- A-pose WITH ITS OWN SKELETON, not by editing geometry
# Previously the arms were moved from T-pose to A-pose by hand: arm vertices were rotated around the
# shoulder with a smooth weight ramp. That broke the shoulder, bent the chest, and the model's own
# asymmetry turned into "one arm forward, the other back" (seen in game 24.09.2026:
# "you bend everything weirdly"). Now we do it properly: rotate the arm BONE,
# the mesh deforms by skinning - smoothly and the same on both sides - and the pose is baked into the mesh.
# This was not possible for the dragon (its wings hung on the arm bones and moved with the arm),
# but on the hippogriff the wing IS the arm, so that is exactly where it should go.
ARM_BONE = {1: "mixamorig:LeftArm", -1: "mixamorig:RightArm"}
HAND_BONE = {1: "mixamorig:LeftHand", -1: "mixamorig:RightHand"}
POSE_DROP = 27.0     # how many degrees below horizontal the pony's arm points (its A-pose)


def posed_height(mesh):
    """Mesh height IN THE CURRENT POSE - the fitting scale is computed from it."""
    deps = bpy.context.evaluated_depsgraph_get()
    shown = mesh.evaluated_get(deps)
    box = [shown.matrix_world @ v.co for v in shown.data.vertices]
    return max(p.z for p in box) - min(p.z for p in box)


def pose_arms_like_pony(skel, mesh):
    """Rotate the arm bones into the A-pose, fit their length and bake the pose into the mesh."""
    target = (bones["bip01_l_hand_19"] - bones["bip01_l_upperarm_twist_15"])
    want = math.radians(POSE_DROP)

    bpy.context.view_layer.objects.active = skel
    bpy.ops.object.mode_set(mode="POSE")
    for pb in skel.pose.bones:           # clear the animation pose, go to the bind pose
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()

    reach = {}
    for sign, name in ARM_BONE.items():
        pb = skel.pose.bones.get(name)
        hand = skel.pose.bones.get(HAND_BONE[sign])
        if pb is None or hand is None:
            continue
        here = (skel.matrix_world @ hand.head) - (skel.matrix_world @ pb.head)
        aim = Vector((sign * abs(target.x), target.y, 0.0)).normalized()
        aim = Vector((aim.x * math.cos(want), aim.y, -math.sin(want))).normalized()
        turn = here.normalized().rotation_difference(aim)
        rest = pb.bone.matrix_local.to_3x3()
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (rest.inverted() @ turn.to_matrix() @ rest).to_quaternion()
        reach[sign] = (pb, here.length, math.degrees(here.angle(aim)))
    bpy.context.view_layer.update()

    # The fitting scale is computed FROM THE POSE, not from the source: wings turned downwards stop
    # being the model's highest point, the height extent drops, and fitting enlarges the model
    # more. With the old measurement the arms came out one and a half times too long.
    pre_scale = HEIGHT / posed_height(mesh)
    for sign, (pb, was_len, angle) in reach.items():
        k = target.length / max(was_len * pre_scale, 1e-6)
        pb.scale = (1.0, k, 1.0)
        log("  рука %s: поворот %.0f градусов, длина x%.2f"
            % (pb.name.split(":")[-1], angle, k))
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    # Bake the pose into the mesh: the modifier is applied in the current pose
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    for mod in list(mesh.modifiers):
        if mod.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=mod.name)


own_bones = []
if source_skel:
    # The file contains a run animation, and import puts the model in its first frame - clear it.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"

# Weld BEFORE everything else: the generator outputs "soup", adjacent triangles do not share vertices.
# Also, after it the vertex indices no longer change - the part markup below relies on them.
bpy.ops.object.select_all(action="DESELECT")
hippo.select_set(True)
bpy.context.view_layer.objects.active = hippo
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(hippo.data.vertices))

if source_skel:
    # Bones are recorded IN THE REST POSE - wings and tail are selected by them below. The selection
    # must happen BEFORE the arms are turned: in the A-pose the wings meet behind the back and merge
    # with the neck collar and the feather fans on the thighs into one piece that can no longer be
    # separated (in game "part of the wings stayed on the body", 24.09.2026).
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    log("кости покоя запомнены: %d" % len(own_bones))


def coords():
    return np.array([(hippo.matrix_world @ v.co)[:] for v in hippo.data.vertices])


# ------------------------------------------------- wings and tail: connected pieces far from the bones
# Same trick as the dragon: feathers and tail stick out far from any bone, while the skin of the torso,
# arms and legs is always near its own. Take everything farther than FAR_FRAC from the bones and cut it
# into connected pieces.
#
# But the pieces are identified differently. On the griffon with FAR_FRAC=0.114 there are five
# (measured on the model):
#   732 and 716 vertices, z 1.21..1.97  - wings;
#   259 and 219 vertices, z 0.70..1.13  - feather tufts on the thighs, part of the body;
#   187 vertices, x near zero, z 0.08..0.75 - the lion tail.
# They cannot be told apart by size or by centre: the feather at the shoulder glues the tufts to the
# wing, so both "largest pieces" come with the thighs, and the tail (187 vertices) falls short of the
# size threshold. But the wing is the only thing that reaches the crown: look at the TOP of the piece.
FAR_FRAC = 0.114
PART_MIN = 0.025      # a piece smaller than this fraction of vertices - feather ears and bits: left alone
WING_TOP = 0.75       # a piece rising above this fraction of the height is a wing
TAIL_HIGH = 0.45      # the tail is searched below this fraction of the height
TAIL_AXIS = 0.12      # and no farther than this fraction of the height from the body axis
# The feather right at the shoulder lies over the arm and is not selected by distance. But the native
# skinning shows which is which: the arm never goes farther than ARM_FAR from its bone, the feather much farther.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


appendage = [None] * len(hippo.data.vertices)
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in hippo.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in hippo.data.vertices])
    # The bone a vertex hangs on IN THE model's NATIVE skinning. Below, after the weights are transferred
    # from the pony, the same variable will refer to pony bones, but the native one is needed for the neck:
    # on the model it ends exactly where the black-and-yellow chest plumage begins, and no height/radius
    # box can catch that (tried it - it either missed some or grabbed the chest).
    own_dominant = dominant.copy()
    added = np.zeros(len(P), bool)
    for name in own_bones:
        if "Arm" not in name:          # arm bones only: that is what the wings hang on
            continue
        sel = dominant == name
        if sel.any():
            added[sel] |= bone_gap(name, P[sel]) > ARM_FAR * height
    added &= ~far
    far |= added
    # Where the model's hand is - by its NATIVE bone: below, these vertices align the arm with the
    # skeleton's arm. Measuring by the claw tips is not possible, they are long.
    own_hand = {i for i, d in enumerate(dominant) if "Hand" in d}
    if added.any():
        pts = P[added]
        log("по костям рук добавлено %d вершин: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (рост %.2f)"
            % (int(added.sum()), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(),
               pts[:, 2].min(), pts[:, 2].max(), height))

    neighbours = [[] for _ in range(len(P))]
    for e in hippo.data.edges:
        i, j = e.vertices
        neighbours[i].append(j)
        neighbours[j].append(i)
    seen = np.zeros(len(P), bool)
    chunks = []
    for start in range(len(P)):
        if not far[start] or seen[start]:
            continue
        stack, chunk = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            chunk.append(cur)
            for other in neighbours[cur]:
                if far[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        chunks.append(chunk)

    # Sorting is done in the T-pose while the wings are spread to the sides: then they and the feather
    # fans on the thighs are separate pieces, and the neck collar does not get into "far from bones" at all.
    # ALL large pieces behind the back count as wings, except one low piece on the axis - the tail.
    middle_y = float(np.median(P[:, 1]))
    floor = float(P[:, 2].min())
    big = [c for c in sorted(chunks, key=len, reverse=True) if len(c) >= PART_MIN * len(P)]
    for chunk in big:
        mid = P[chunk].mean(0)
        top = float(P[chunk][:, 2].max()) - floor
        if mid[1] < middle_y:          # everything we want is behind the back; nothing should be in front
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        if mid[2] - floor < TAIL_HIGH * height and abs(mid[0]) < TAIL_AXIS * height:
            name = "tail"
        else:
            name = "wings"
        log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) -> %s"
            % (len(chunk), *mid, top, name))
        for i in chunk:
            appendage[i] = name
    # The clawed leading edge of the wing lies right against the finger bones (in the T-pose the hand and
    # the wing claw end up at the same point), so it is not selected by distance and stayed on the body as
    # shards sticking out. But it is attached ONLY to the membrane: once the wings are removed, it hangs
    # as a separate island. So we look at what the remainder falls apart into: the big piece is the
    # dragon itself, everything else near a wing or the tail goes back to it.
    seen = np.zeros(len(P), bool)
    rest = []
    for start in range(len(P)):
        if appendage[start] or seen[start]:
            continue
        stack, island = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            island.append(cur)
            for other in neighbours[cur]:
                if not appendage[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        rest.append(island)
    rest.sort(key=len, reverse=True)
    ISLAND_NEAR = 0.05        # an island farther than this fraction of the height from wing and tail is not theirs
    for island in rest[1:]:
        pick, gap = None, 1e9
        for name in ("wings", "tail"):
            owner = P[[i for i in range(len(P)) if appendage[i] == name]]
            if not len(owner):
                continue
            d = float(min(np.linalg.norm(owner - p, axis=1).min() for p in P[island]))
            if d < gap:
                pick, gap = name, d
        if pick and gap < ISLAND_NEAR * height:
            for i in island:
                appendage[i] = pick
            log("островок %d вершин возвращён в «%s» (зазор %.3f)" % (len(island), pick, gap))

    found = {n: sum(1 for a in appendage if a == n) for n in ("wings", "tail")}
    log("крылья и хвост по удалённости от костей: крылья %d вершин, хвост %d" % (found["wings"], found["tail"]))
    if not found["wings"] or not found["tail"]:
        log("ВНИМАНИЕ: крылья или хвост не найдены — проверьте FAR_FRAC")

# ---- now that the parts are marked, put the arms into the A-pose with the skeleton and remove the skeleton
if source_skel:
    source_skel.data.pose_position = "POSE"
    pose_arms_like_pony(source_skel, hippo)
    hippo.parent = None
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("руки поставлены в А-позу скелетом, скелет снят")

bpy.ops.object.select_all(action="DESELECT")
hippo.select_set(True)
bpy.context.view_layer.objects.active = hippo
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: размер %.2f x %.2f x %.2f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))

# The muzzle must face -Y (like the pony). The muzzle is the point of the upper third sticking out most
# along Y, but IT MUST BE COMPUTED WITHOUT WINGS AND TAIL: the hippogriff's wings reach farther back than
# the beak forward, and by them the model was judged already turned - in game it stood with its back
# to the camera (24.09.2026).
own = np.array([appendage[i] is None for i in range(len(P))])
top = P[own & (P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2]))]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
log("морда: самая выступающая точка верхней трети y=%.2f, середина %.2f" % (nose_y, middle_y))
if nose_y > middle_y:
    hippo.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
hippo.scale = (scale, scale, scale)
hippo.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- depth: fit by the TORSO, not by the bounding box
# Fitting by the bounding box does not work: the dragon's tail pulls the box back, and the torso moves
# forward of the spine. Then the spine bone runs right along the back, the chest wobbles on any turn of
# the body, and the arms and legs hang in front of the armour.
# The depth reference is the VANILLA HUMAN, not the pony: armour is made for it, and it sets the fit.
# The human body is exported from the game assets:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<game>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Vanilla models face +Y (ours face -Y), so the reference is turned around.
TORSO_Z = (1.00, 1.35)    # between bones bip01_spine_9 and bip01_spine2_11
TORSO_HALF = 0.22         # wider than this in X is already the arms
HUMAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "human_ref", "human.obj")
DEPTH_EXTRA = 0.0         # manual depth correction on top of the computed one, if it is still off in game


def torso_y(pts):
    band = pts[(np.abs(pts[:, 0]) < TORSO_HALF) & (pts[:, 2] > TORSO_Z[0]) & (pts[:, 2] < TORSO_Z[1])]
    if not len(band):
        return 0.0
    return float(np.percentile(band[:, 1], 2) + np.percentile(band[:, 1], 98)) / 2


P = coords()
if os.path.exists(HUMAN):
    known = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=HUMAN, forward_axis="Y", up_axis="Z")
    fresh = [o for o in bpy.data.objects if o not in known]
    man = np.vstack([np.array([(o.matrix_world @ v.co)[:] for v in o.data.vertices]) for o in fresh])
    man[:, :2] *= -1                       # turn the reference to face -Y, like ours
    target = torso_y(man)
    for ob in fresh:
        bpy.data.objects.remove(ob, do_unlink=True)
    whose = "человека"
else:
    target = torso_y(np.array([(pony["eq_twilight_body"].matrix_world @ v.co)[:]
                               for v in pony["eq_twilight_body"].data.vertices]))
    whose = "пони (нет assets/human_ref/human.obj)"
mine = torso_y(P[[i for i in range(len(P)) if appendage[i] is None]])
shift = target - mine + DEPTH_EXTRA
# Move the mesh itself, not the object: "baking" the offset (transform_apply) works only on the
# selected object, and importing the reference steals the selection - then the object moves, and all
# later edits are written in local coordinates and miss by exactly this offset.
for v in hippo.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Where the neck ends and the head begins. The line slopes forward-down (under the muzzle), and it must
# be measured FROM THE MODEL ITSELF: fitting by the torso moved the dragon in depth, so the same offset
# is added to the world mark. It is needed already here: the head must not be touched together with
# the arms - its sides fall into the same X zone, and editing the arms tore the muzzle to pieces.
# The line is taken from the model's OWN neck bone, not from the pony skeleton: the hippogriff has a
# short neck, its head sits 12 cm below the pony head bone, and by the pony mark only the crown went
# into the "head" while beak and cheeks stayed with the body - the face deformed along with the chest.
# The model's bones were recorded before it was scaled, so multiply by the same scale.
# NECK_UP: ("cut the body part higher up the neck", 24.09.2026) - with
# the old line the feather collar stayed with the head and lay over the armour collar. Raise the cut,
# and the neck goes to the body.
NECK_UP = 0.16
if "mixamorig:Neck" in own_bones:
    NECK_Z = float(own_bones["mixamorig:Neck"][0][2]) * scale + 0.04 + NECK_UP
    log("линия шеи по кости модели: z=%.2f (у скелета пони была бы %.2f)"
        % (NECK_Z, bones["bip01_neck_12"].z + 0.06))
else:
    NECK_Z = bones["bip01_neck_12"].z + 0.06
JAW_SLOPE, JAW_FROM = 0.45, -0.10 + shift

# THE NECK GOES TO THE HEAD. Armour replaces the body mesh, and the neck in the body vanished under the
# armour: a hole gaped between the beak and the collar (24.09.2026). Lowering the whole cut line for this
# is not an option - the chest and shoulders go into the head along with the neck. A column around the
# neck axis does not work either: the model's neck widens downwards, a narrow column missed some of it,
# a wide one grabbed the chest. We go by the model's skinning - see NECK_BONES in part_of.
                       # with 0.17 the column did not reach it and a piece of the neck stayed with the body
                       # on the chest - the piece of neck above it must also belong to the head


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ---------------------------------------------- arms from T-pose onto the pony arm (rotation + length)
# Just rotating by 22 degrees is not enough: the dragon's arm is 10% longer than the pony's, so the elbow
# landed on the forearm bone and the hand missed the hand bone, and in game the arms looked crooked.
# Align the dragon's "shoulder - hand" segment with the same segment of the skeleton: rotation around the
# shoulder plus scaling along the length. Right at the joint the transform ramps in smoothly, else it tears.
SHOULDER_X = 0.16               # shoulder joint in X (the model's shoulder bone after fitting)
ARM_RAMP = 0.18                 # over how many metres the transform ramps in
                                # (wider for the hippogriff: on a narrow band the shoulder broke)
ARM_TIP = 0.9                   # fraction of the span beyond which it is the hand
HEAD_RAMP = 0.12                # how many metres below the jaw the arm takes full effect

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
arm_y = float(np.median([P[i][1] for i in range(len(P)) if arm_far[i] and appendage[i] is None]))
ARM_BACK = arm_y + 0.12         # farther back is the wing, not the arm
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > SHOULDER_X - ARM_RAMP and p[1] < ARM_BACK and p[2] > 1.0
            and appendage[i] is None and not is_head(P[i])]
tip = max(abs(P[i][0]) for i in arm_zone)
# The hand is found by the model's NATIVE bone, not by the claw tips: the dragon's claws are long, and by
# them the arm went far out to the side of the body (the hand ended up at |x| 0.83 instead of 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# The shoulder joint lies on the axis of the arm itself, extended to SHOULDER_X. It cannot be found from
# a torso slice at that mark: the flank is still there, and the slice centre wanders by ~10 cm in height.
# The axis is computed from the centres of cross bands of the arm (from 0.30 to the tips), so that the
# hand and elbow do not outweigh the rest, and a straight line is fitted through them.
ARM_AXIS_FROM = 0.30
axis = np.array([[abs(P[i][0]), P[i][1], P[i][2]] for i in arm_zone
                 if abs(P[i][0]) > ARM_AXIS_FROM])
edges = np.linspace(ARM_AXIS_FROM, tip, 9)
middles = np.array([axis[(axis[:, 0] >= a) & (axis[:, 0] < b)].mean(0)
                    for a, b in zip(edges[:-1], edges[1:])
                    if (axis[:, 0] >= a).sum() and ((axis[:, 0] >= a) & (axis[:, 0] < b)).sum() > 5])
ky, by = np.polyfit(middles[:, 0], middles[:, 1], 1)
kz, bz = np.polyfit(middles[:, 0], middles[:, 2], 1)
S_d = Vector((SHOULDER_X, ky * SHOULDER_X + by, kz * SHOULDER_X + bz))
H_d = Vector([float(np.mean([abs(P[i][k]) if k == 0 else P[i][k] for i in hand_idx])) for k in range(3)])
S_p = bones["bip01_l_upperarm_twist_15"]
# Aim the WRIST at the hand bone. The pony's fingertips cannot be used: its arm is longer than a human's
# (fingers reach |x| 0.83, while the vanilla body's arm ends at 0.60), and the dragon got splayed arms.
# Let the claws stick out past the bone, like a human's fingers.
H_p = bones["bip01_l_hand_19"]
# Exactly to the bone the arm comes out a bit short: the hand hides in the sleeve. Let it go further along
# the same axis and turn it down - that way it is both longer and pressed to the body, not splayed.
# The numbers are tuned from in-game feedback, as for the dragon.
ARM_REACH = 1.10    # how many times farther than the hand bone the wrist goes ("lengthen the arms a bit")
ARM_DROP = 8.0      # how many extra degrees the arm is lowered towards the body
ARM_THICK = 1.00    # how many times thicker across the axis (the alignment itself thins the arm)
HAND_SMALL = 0.72   # how many times the hand itself is shrunk ("make the hands smaller", 24.09.2026)
# "move closer to the wings": the wing goes up-back from the shoulder, while
# the paw hung forward and down. Move it towards the wing plane - back and up along the body.
HAND_TO_WING = (0.02, 0.02)     # back (+Y) and up (+Z), metres

reach = (H_p - S_p) * ARM_REACH
drop = math.radians(ARM_DROP)
H_p = S_p + Vector((reach.x * math.cos(drop) + reach.z * math.sin(drop), reach.y,
                    -reach.x * math.sin(drop) + reach.z * math.cos(drop)))
turn = (H_d - S_d).rotation_difference(H_p - S_p).to_matrix()
stretch = (H_p - S_p).length / (H_d - S_d).length
along = (H_d - S_d).normalized()
log("  рука: наклон %.0f -> %.0f градусов ниже горизонта, толщина x%.2f"
    % (math.degrees(math.atan2(-(bones["bip01_l_hand_19"] - S_p).z, (bones["bip01_l_hand_19"] - S_p).x)),
       math.degrees(math.atan2(-(H_p - S_p).z, (H_p - S_p).x)), ARM_THICK * stretch))
log("  плечо дракона (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f), кисть (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f)"
    % (*S_d, *S_p, *H_d, *(S_p + turn @ ((H_d - S_d) * stretch))))
# The arm is NOT bent: it is already in the A-pose - the model's skeleton turned it (pose_arms_like_pony above).
# Only measurements are left here: where the hand ended up relative to the pony hand bone.
P = coords()
hands = P[[i for i in hand_idx]]
log("кисть после позы скелетом (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f), в зоне руки %d вершин"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z,
       len(arm_zone)))

# ---------------------------------------------------------------- smaller hand
# The model's paw is big, with long claws, and next to a human sleeve it looks like a shovel.
# Shrink it AROUND THE WRIST (the pony hand bone), not around the paw centre: otherwise a gap opens at the
# joint with the forearm. ARM_DROP above pulls the hand closer to the body - it also lays the whole arm
# along the torso rather than out to the sides.
if HAND_SMALL != 1.0:
    P = coords()
    shrunk = 0
    for i in (set(arm_zone) & own_hand):
        p = P[i]
        sign = 1.0 if p[0] > 0 else -1.0
        wrist = Vector((H_p.x * sign, H_p.y, H_p.z))
        moved = wrist + (Vector((p[0], p[1], p[2])) - wrist) * HAND_SMALL
        moved.y += HAND_TO_WING[0]      # towards the wing: back
        moved.z += HAND_TO_WING[1]      # and up
        hippo.data.vertices[i].co = moved
        shrunk += 1
    P = coords()
    hands = P[[i for i in hand_idx]]
    log("кисть ужата в %.2f раза (%d вершин), центр лапы теперь (%.2f,%.2f,%.2f)"
        % (HAND_SMALL, shrunk, abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean()))

# ---------------------------------------------------------------- arms forward, legs back
# From the side the arm hangs right by the tail and the leg is pushed forward - the figure topples.
# Move them towards each other in depth ("move the arms away
# from the tail and the legs towards it", 24.09.2026). The muzzle faces -Y, so forward is minus, towards
# the tail is plus.
#
# Both shifts fade out smoothly: the arm lets go at the shoulder (same ramp as the rotation),
# the leg at the pelvis. Otherwise the joint tears.
ARM_FORWARD = 0.0       # body taken as in the original - no depth shifts
ARM_OUT = 0.0           # nor to the sides
LEG_BACK = 0.0          # and the legs stay in place
LEG_FULL = 0.55         # below this height the leg moves as a whole
LEG_FADE = 0.95         # above this it is the pelvis, left alone

P = coords()
for i in arm_zone:
    p = P[i]
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t = t * t * (3 - 2 * t)          # smoothly, otherwise the shoulder kinks
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)
    hippo.data.vertices[i].co.y -= ARM_FORWARD * t
    hippo.data.vertices[i].co.x += math.copysign(ARM_OUT * t, p[0])

moved_legs = 0
for i, p in enumerate(P):
    if appendage[i] is not None or p[2] > LEG_FADE:
        continue
    if p[2] <= LEG_FULL:
        w = 1.0
    else:
        u = 1.0 - (p[2] - LEG_FULL) / (LEG_FADE - LEG_FULL)
        w = u * u * (3 - 2 * u)
    if w > 0:
        hippo.data.vertices[i].co.y += LEG_BACK * w
        moved_legs += 1
log("руки сдвинуты вперёд на %.2f м и в стороны на %.2f м (%d вершин), ноги назад на %.2f м (%d вершин)"
    % (ARM_FORWARD, ARM_OUT, len(arm_zone), LEG_BACK, moved_legs))

# ------------------------------------------------------------------- wider rib cage
# The model has a narrow chest - next to the wide pelvis it looks like a tube. Widen it in X, but not with
# a single scale: otherwise the arms move along with the chest and the hands leave their bones. Inside the
# torso the width grows proportionally, outside the shift fades out towards the wrist, and in height it
# fades smoothly beyond the ribs. Wings and tail move with everything else so their roots stay in place.
# In game the chest came out flat next to the wide hips (
# "the chest is squashed too much in width", 24.09.2026), then it was asked to be even wider and together
# with the belly - hence 1.45 and the band down to the pelvis.
CHEST_WIDE = 1.0    # the chest is not widened: that made the torso triangular
# Own band, not the dragon's: the griffon is shorter (1.95 vs 2.10), its collarbones at 1.41, pelvis at 0.95.
CHEST_BAND = (0.95, 1.36)   # ribs and belly: from pelvis to collarbones
CHEST_FADE = 0.13           # over how many metres in height it ramps in and out
CHEST_TAPER = 0.45          # over how many metres outwards the shift fades out


def band_weight(z):
    if CHEST_BAND[0] <= z <= CHEST_BAND[1]:
        return 1.0
    gap = CHEST_BAND[0] - z if z < CHEST_BAND[0] else z - CHEST_BAND[1]
    if gap >= CHEST_FADE:
        return 0.0
    u = 1.0 - gap / CHEST_FADE
    return u * u * (3 - 2 * u)


P = coords()
chest = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.35)]
HALF = float(np.percentile(np.abs(chest[:, 0]), 90))     # torso half-width at rib level
grow = (CHEST_WIDE - 1.0) * HALF
for i, p in enumerate(P):
    w = band_weight(p[2])
    if w <= 0:
        continue
    out = abs(p[0])
    reach = out / HALF if out < HALF else max(0.0, 1.0 - (out - HALF) / CHEST_TAPER)
    if reach <= 0:
        continue
    hippo.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- smaller upper chest
# It is the ribs that should be widened, not the bust: at the top the chest stuck out both forward and to
# the sides. Shrink the upper chest in width and depth around its own centre - so the bottom (ribs) stays
# wide and the top is tucked in. Fades out towards the shoulders, otherwise the arms tear off them.
UPPER_SMALL = 1.00          # how many times the upper chest is shrunk (1.0 - untouched)
UPPER_BAND = (1.34, 1.58)   # from bust to collarbones
UPPER_FADE = 0.10           # over how many metres in height it ramps in and out
UPPER_HALF = 0.26           # beyond this in X it is the shoulder, no shrinking there
UPPER_TAPER = 0.16          # over how many metres outwards the shrinking fades out

P = coords()
band = P[(P[:, 2] > UPPER_BAND[0]) & (P[:, 2] < UPPER_BAND[1]) & (np.abs(P[:, 0]) < UPPER_HALF)]
mid_y = float(np.percentile(band[:, 1], 2) + np.percentile(band[:, 1], 98)) / 2


def upper_size():
    # measure wider than the shrink band, otherwise the measurement hits its own limit
    s = P[(P[:, 2] > UPPER_BAND[0]) & (P[:, 2] < UPPER_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
    return float(np.percentile(np.abs(s[:, 0]), 90)), float(np.percentile(s[:, 1], 2))


was, was_front = upper_size()
for i, p in enumerate(P):
    if appendage[i] is not None:
        continue
    gap = max(UPPER_BAND[0] - p[2], p[2] - UPPER_BAND[1], 0.0)
    if gap >= UPPER_FADE:
        continue
    u = 1.0 - gap / UPPER_FADE
    w = u * u * (3 - 2 * u)
    out = abs(p[0])
    if out > UPPER_HALF:
        w *= max(0.0, 1.0 - (out - UPPER_HALF) / UPPER_TAPER)
    if w <= 0:
        continue
    f = 1.0 - (1.0 - UPPER_SMALL) * w
    v = hippo.data.vertices[i]
    v.co.x = p[0] * f
    v.co.y = mid_y + (p[1] - mid_y) * f
P = coords()
now, now_front = upper_size()
log("верх груди ужат: полуширина %.2f -> %.2f, вперёд выступал на %.2f -> %.2f"
    % (was, now, was_front, now_front))

# ---------------------------------------------------------------- 2. weights from the pony
ref_parts = []
for name in ("eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves", "eq_twilight_head"):
    src = pony[name]
    ob = src.copy()
    ob.data = src.data.copy()
    if ob.data.shape_keys:
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

for g in list(hippo.vertex_groups):     # the foreign Mixamo groups are no longer needed
    hippo.vertex_groups.remove(g)
for g in ref.vertex_groups:
    hippo.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
hippo.select_set(True)
bpy.context.view_layer.objects.active = hippo
dt = hippo.modifiers.new("веса", "DATA_TRANSFER")
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

# Hand bones go to the hands only: the pony's hands hang at belly height, and the sides of the dragon's
# torso end up closer to them than to its body (the same problem the yak had).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = hippo.data.vertices[i]
    for g in list(v.groups):
        if hippo.vertex_groups[g.group].name in HAND_BONES:
            hippo.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        hippo.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# The head is rigidly on the head bone - otherwise the neck and chest bones drive the muzzle and it tears
# at the seam. The boundary (jaw_z/is_head) is defined above, before the arm edits.
BLEND = 0.15

head_group = hippo.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(hippo.data.vertices[i].groups):
        hippo.vertex_groups[g.group].remove([i])
head_group.add(head_idx, 1.0, "REPLACE")
blended = torn = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p) or appendage[i] is not None:
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]
    if d >= BLEND:
        # There must be no head bone below the neck. The weight transfer gives it to the crest on the
        # chest: it sticks forward and up, and the nearest pony point turns out to be its chin. In game
        # such a chest folded on every head turn.
        if head_group.index in [g.group for g in hippo.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not hippo.data.vertices[i].groups:
                hippo.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in hippo.data.vertices[i].groups:
        hippo.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ------------------------------------------------------------------------ blinking
# The engine blinks with the head's vertex keys: there are exactly 101 (key_000..key_100), and frames 86,
# 87, 88 are the left eye, the right and both (done the same way for the pony, tools/convert_twilight.py).
# Without the keys the face is simply frozen, like the yak's.
#
# The pony's eyelids are separate geometry hidden above the eye. The dragon has none: the model is one
# piece, the eye is just PAINTED on the texture. So we close it by squashing: vertices around the eye are
# pulled towards its middle in height, and the painted eye collapses into a slit. The same trick finishes
# closing the pony's eyeball when the engine applies a frame at less than full strength.
#
# Eyes are found from the texture itself - two symmetrical dark spots on the muzzle. The colour sample is
# taken slightly inside the face: the model's UV layout is patchy, and right at an island's edge there is
# already the atlas black.
FACE_KEYS = 101         # this many vertex keys on the vanilla head
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
# The griffon threshold is MUCH stricter than the dragon's 0.30: the eagle's brown brow feathers are darker
# than 0.3, and with that threshold the brow came out as the largest dark spot - the blink fired above the
# eye (seen in game 24.09.2026). The black pupil is noticeably darker than any feather, so we key on it.
EYE_DARK = 0.16
# Squash zone - half-axes of a "segment" around the eye centre: sideways, in depth, in height. The griffon's
# eye is almond-shaped and slanted, so the zone is long along it and short in height - otherwise the brow
# and cheek collapse along with the eye and the muzzle folds like an accordion.
EYE_ZONE = (0.105, 0.095, 0.055)
EYE_FULL = 0.80         # inside this fraction of the zone squash fully, beyond it fades out smoothly
EYE_SQUASH = 0.92       # how much the vertices are pulled towards the eye centre
EYE_SIDE = 0.02         # closer than this to the axis is the beak, not the eye
# The mark lands on the PUPIL, and on the griffon it is right by the beak, while the eye itself with the
# white extends outwards and slightly back - only the half near the nose closed (seen in game 24.09.2026).
# So we step from the found pupil towards the eye centre.
EYE_OUT = 0.035         # outwards, from the beak to the temple
EYE_BACK = 0.030        # and back: the griffon's eye white extends to the temple, the eye is almond-shaped


def eye_spots(ob, only=None):
    """Eye centres: dark spots on the texture. only - which vertices to search
    (on the whole model these are the head vertices, otherwise dark spots are found all over the body)."""
    img = next((i for i in bpy.data.images
                if "texture_0" in i.name.lower() and i.has_data
                and not any(k in i.name.lower() for k in ("normal", "rough", "metal"))), None)
    uvs = ob.data.uv_layers.active
    if img is None or uvs is None:
        log("ВНИМАНИЕ: не нашёл текстуру или развёртку — моргания не будет")
        return []
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    tone = np.zeros(len(P))
    hits = np.zeros(len(P))
    for poly in ob.data.polygons:
        mid = np.mean([np.array(uvs.data[li].uv) for li in poly.loop_indices], axis=0)
        for li in poly.loop_indices:
            spot = np.array(uvs.data[li].uv) * 0.75 + mid * 0.25
            x = int(min(max(spot[0], 0.0), 0.999) * (w - 1))
            y = int(min(max(spot[1], 0.0), 0.999) * (h - 1))
            tone[ob.data.loops[li].vertex_index] += float(px[y, x, :3].mean())
            hits[ob.data.loops[li].vertex_index] += 1
    tone /= np.maximum(hits, 1)

    dark = (tone < EYE_DARK) & (hits > 0)
    if only is not None:
        keep = np.zeros(len(P), bool)
        keep[list(only)] = True
        dark &= keep
    near = [[] for _ in range(len(P))]
    for e in ob.data.edges:
        near[e.vertices[0]].append(e.vertices[1])
        near[e.vertices[1]].append(e.vertices[0])
    seen = np.zeros(len(P), bool)
    spots = []
    for start in np.flatnonzero(dark):
        if seen[start]:
            continue
        stack, blob = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            blob.append(cur)
            for other in near[cur]:
                if dark[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        spots.append((P[blob].mean(0), len(blob), float(tone[blob].mean())))
    for centre, size, shade in sorted(spots, key=lambda s: -s[1])[:8]:
        log("  тёмное пятно: %3d вершин, яркость %.2f, на (%.2f,%.2f,%.2f)" % (size, shade, *centre))
    # Find ONE eye and mirror it to the other side. Searching each side separately does not work: a
    # mottled bird has many dark spots on the head (feather shadows, nostril, collar edge), and on one
    # side the eye won while on the other a spot on the neck did; the eyes came out at different heights
    # (measured: 1.61 and 1.33). Selection: upper half of the head, front part, off the axis, darkest.
    # The model's head is symmetrical, mirroring is more reliable than a second search.
    # The "front" and "upper half" marks are computed FROM THE SAME vertices we search (only): measured
    # over the whole model, the "upper half" ends up at waist level and the filter cuts nothing - the
    # eye was found on the cheek (checked 24.09.2026).
    field = P[list(only)] if only is not None else P
    front = float(np.percentile(field[:, 1], 45))
    upper = float(field[:, 2].min() + field[:, 2].max()) / 2
    mine = [(c, n, s) for c, n, s in spots
            if abs(c[0]) > EYE_SIDE and c[1] < front and c[2] > upper]
    out = [None, None]
    if mine:
        best = min(mine, key=lambda s: s[2])[0]
        right = np.array([abs(best[0]), best[1], best[2]])
        out = [right, np.array([-right[0], right[1], right[2]])]
        log("  глаз найден на (%.2f,%.2f,%.2f), вторая сторона отражена" % tuple(right))
    # from the pupil to the eye centre (see EYE_OUT)
    for spot in out:
        if spot is not None:
            spot[0] += math.copysign(EYE_OUT, spot[0])
            spot[1] += EYE_BACK
    return [s for s in out if s is not None]


def add_blink(ob, spots=None):
    spots = spots or eye_spots(ob)
    if len(spots) != 2:
        log("ВНИМАНИЕ: глаз на текстуре не видно (%d пятен) — моргания не будет" % len(spots))
        return
    log("глаза найдены: (%.2f,%.2f,%.2f) и (%.2f,%.2f,%.2f)" % (*spots[0], *spots[1]))
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])

    def shut(sides):
        move = np.zeros_like(P)
        radius = np.array(EYE_ZONE)
        for side in sides:
            eye = spots[side]
            # The zone is not a ball but a "segment" shaped like the eye: wide sideways and in depth,
            # low in height. A ball did not work: to close the outer corner the radius had to be so big
            # that the brow and cheek got crushed too, and the muzzle folded like an accordion.
            step = (P - eye) / radius
            # Height is handled separately from "along the eye": the zone comes out as a flat cake, not
            # a ball. If all three axes are combined, the outer eye corner (far to the side AND slightly
            # above the centre) falls out of the zone and stays open.
            gap = np.maximum(np.sqrt((step[:, 0] ** 2 + step[:, 1] ** 2)), np.abs(step[:, 2]))
            close = gap < 1.0
            fade = np.clip((1.0 - gap[close]) / max(1.0 - EYE_FULL, 1e-6), 0.0, 1.0)
            move[close, 2] += (eye[2] - P[close, 2]) * EYE_SQUASH * fade
        return move

    ob.shape_key_add(name="Basis", from_mix=False)
    shifts = {k: shut(s) for k, s in ((86, [0]), (87, [1]), (88, [0, 1]))}
    for k in range(FACE_KEYS):
        key = ob.shape_key_add(name="key_%03d" % k, from_mix=False)
        if k not in shifts:
            continue
        for i, point in enumerate(key.data):
            point.co = point.co + Vector(shifts[k][i])
    log("моргание: %d ключей, в кадрах %s глаза закрываются (сжатие %.2f, радиус %.3f)"
        % (FACE_KEYS, "/".join(str(k) for k in sorted(BLINK_FRAMES)), EYE_SQUASH, EYE_ZONE[0]))


# ---------------------------------------------------------------- 3. cutting into parts
group_names = {g.index: g.name for g in hippo.vertex_groups}
dominant = []
for v in hippo.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
lo, hi = P.min(0), P.max(0)

# back: the rearmost point of a narrow band along the spine
spine = P[(np.abs(P[:, 0]) < 0.10) & (P[:, 2] > 0.9) & (P[:, 2] < 1.3)]
BACK = float(spine[:, 1].max())
# Only the head's OWN vertices: the wings rise above the crown and cross the jaw line, and if they are
# included in the measurement all head marks shift. Because of this, on the hippogriff the mane boundary
# moved onto the muzzle and almost the whole head went into the hairstyle (41 head vertices vs 198 mane).
head_pts = P[[i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]]
HEAD_TOP = float(head_pts[:, 2].max())
HEAD_BACK = float(head_pts[:, 1].max())
# Crown: below this fraction of the head height it is already the face
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# THE WHOLE EYE STAYS WITH THE HEAD. The crown line by height fraction fell right on the eye, and its upper
# half went into the hairstyle: in game the hair moved on blinking instead of the eyelid
# (seen 24.09.2026). So the line is raised above the eye with a margin.
EYE_KEEP = 0.05          # how far above the eye itself the crown line runs
eyes_early = eye_spots(hippo, only=[i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None])
if eyes_early:
    was_top = SKULL_TOP
    SKULL_TOP = max(SKULL_TOP, max(float(e[2]) for e in eyes_early) + EYE_KEEP)
    log("линия макушки поднята с %.2f до %.2f — глаз (%.2f) остаётся голове"
        % (was_top, SKULL_TOP, max(float(e[2]) for e in eyes_early)))
# Mane boundary in depth: fraction of the way from the eyes to the back of the head. Everything beyond it
# is mane and nape, closer is the muzzle with its frill (it must not go into the hair, it would be tinted
# with the hair colour).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # front of the muzzle
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
# Where the cut between body and legs runs. The pony has 0.44 of height 1.86, but the griffon has a bird
# leg: the joint is higher, and with a low cut a bare paw stuck out from under the boot (
# "cut the legs off the body a bit higher", 24.09.2026). Raise it by a palm - to mid-shin.
LEG_TOP = 0.55 * HEIGHT / 1.86
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# DO NOT COLLECT THE FORELOCK. I tried catching strands left on the face by the fact that a strand is a
# thin sheet (a back side with an opposite normal nearby, KD-tree): along with them, scales above the brow
# and pieces of cheek went into the hairstyle, and the head shrank from 322 vertices to 150. The user:
# ("make it like before, the hair
# came out really bad"). Two marks remain - the crown and the nape.


NECK_BONES = ("mixamorig:Neck", "mixamorig:Head", "mixamorig:HeadTop_End", "headfront")


def part_of(i):
    if appendage[i]:                 # wings and tail were selected above, by distance from the bones
        return appendage[i]
    p = P[i]
    # The neck is taken by the model's NATIVE skinning: everything hanging on its neck and head bones.
    # Armour replaces the body mesh, and the neck in the body vanished under the armour; and a height box
    # cannot cut it out - on the model it ends exactly at the edge of the black-and-yellow chest plumage.
    if own_dominant[i] in NECK_BONES and not is_head(p):
        return "head"
    if is_head(p):
        # The "hairstyle" is the horns, the crest on the crown and the mane falling from the nape onto the
        # shoulders: the hair colour from the appearance screen works on it. The frill along the muzzle must
        # not be included (it would be tinted along with the horns), hence the depth boundary: the mane is
        # entirely behind the skull, the muzzle in front.
        if p[2] > SKULL_TOP or p[1] > HAIR_BACK:
            return "hair"
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

# ---------------------------------------------------------------- 4. material and textures
src_mat = hippo.data.materials[0] if hippo.data.materials else None
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
if src_mat and src_mat.use_nodes:
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    for node in src_mat.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            img = node.image
            if not img.has_data:
                guess = os.path.join(os.path.dirname(SRC), os.path.basename(img.filepath_raw or img.name))
                if os.path.exists(guess):
                    img.filepath = guess
                    img.reload()
            fname = "eq_hippogriff_" + img.name.replace(".", "_").lower() + ".png"
            img.filepath_raw = os.path.join(tex_dir, fname)
            img.file_format = "PNG"
            try:
                img.save()
                log("текстура", fname, "%dx%d" % tuple(img.size))
            except RuntimeError as e:
                log("текстуру", fname, "сохранить не вышло:", e)
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.label = img.name
            low = img.name.lower()
            if bsdf and "normal" in low:
                nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
                mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            elif bsdf and "metal" not in low and "rough" not in low:
                mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

# ---------------------------------------------------------------- 5. parts as separate meshes
PLUG = 0.18        # how far the wing and tail root goes into the body - slack for animation
SMOOTH_ROUNDS = 18  # this many relax passes on the wing/tail socket so the back becomes smooth
SMOOTH_GROW = 2     # this many rings around the patch the smoothing spreads to
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


SEPARATE_NEAR = 0.025  # head vertices closer than this to the mane are sunk inwards (metres)
SEPARATE_PUSH = 0.010  # and by this much, right at the mane

parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "wings", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = hippo.copy()
    ob.data = hippo.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    was_index = {v: i for i, v in enumerate(bm.verts)}   # indices before deletion - labels use them
    keep_set = set(keep)
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")

    # Flying eyebrows. Above the eye the model has a separate feather stroke; the cut left it in a part
    # with no support, and in game it hung in the air ("remove the flying
    # eyebrows", 24.09.2026). This also removes all other crumbs left without neighbours. A piece smaller
    # than FLAKE vertices counts as a crumb: real pieces (wing, crest, paw) are an order of magnitude bigger.
    FLAKE = 25
    islands, seen_v = [], set()
    for start in bm.verts:
        if start in seen_v:
            continue
        stack, island = [start], []
        seen_v.add(start)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other not in seen_v:
                    seen_v.add(other)
                    stack.append(other)
        islands.append(island)
    crumbs = [v for island in islands if len(island) < FLAKE for v in island]
    if crumbs and len(crumbs) < len(bm.verts) / 2:
        bmesh.ops.delete(bm, geom=crumbs, context="VERTS")
        log("  %s: снято крошек %d вершин в %d кусках"
            % (name, len(crumbs), sum(1 for i in islands if len(i) < FLAKE)))
    # Close the tear-off spot with polygons: otherwise see-through holes gape at the joints of wings, tail
    # and neck (faces are not drawn from inside, and in game it is black there). ONLY the cuts must be
    # closed: the wing and membrane edge is free all the way round, and it must not be filled - it would
    # cover the membrane with a solid sheet. A cut is recognised by a vertex of another part being next to
    # it in the source mesh. UVs for the new faces are taken from neighbouring faces of the same vertex,
    # otherwise they pull colour from a corner of the texture.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] != name for o in neighbours[was_index[v]])}

    # Wings and tail sit on their own bone, while the body at their root sits on its own (the back at the
    # wing follows the collarbone), so in motion the seam opens and you can see through the gap. So the
    # root of the wing and tail is extended INTO the body: a skirt is led from the cut towards the spine.
    # It is not visible from outside, and it covers the gaps with a margin.
    if name in ("wings", "tail"):
        seam = [e for e in bm.edges if len(e.link_faces) == 1 and all(v in cut for v in e.verts)]
        if seam:
            made = bmesh.ops.extrude_edge_only(bm, edges=seam)
            fresh = [g for g in made["geom"] if isinstance(g, bmesh.types.BMVert)]
            for v in fresh:
                here = Vector(v.co)
                inside = min((closest_on(here, a, b) for a, b in SPINE_LINE),
                             key=lambda q: (q - here).length)
                step = inside - here
                if step.length > 1e-6:
                    v.co = here + step.normalized() * min(PLUG, 0.8 * step.length)
            skirt = [f for f in made["geom"] if isinstance(f, bmesh.types.BMFace)]
            if uv is not None:
                for f in skirt:
                    for loop in f.loops:
                        near = next((l for l in loop.vert.link_loops if l.face not in skirt), None)
                        if near:
                            loop[uv].uv = near[uv].uv
            cut.update(fresh)        # the far edge of the skirt is closed too, so the pocket is sealed
            log("  %s: корень продлён внутрь тела на %d граней" % (name, len(skirt)))

    seen_edge, patched, smooth = set(), 0, set()
    for start in [e for e in bm.edges if len(e.link_faces) == 1]:
        if start in seen_edge:
            continue
        loop_edges, stack = [], [start]
        seen_edge.add(start)
        while stack:                     # the whole connected loop of the free edge
            cur = stack.pop()
            loop_edges.append(cur)
            for v in cur.verts:
                for e in v.link_edges:
                    if len(e.link_faces) == 1 and e not in seen_edge:
                        seen_edge.add(e)
                        stack.append(e)
        ring = {v for e in loop_edges for v in e.verts}
        if len(ring) < 3 or sum(1 for v in ring if v in cut) < 0.6 * len(ring):
            continue                     # free edge of the membrane itself - leave it
        # whose boundary this was: with the wing and tail the socket is smoothed afterwards, but the seam
        # with the head, legs and hands must not be touched - it joins the neighbouring part and must stay
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] != name]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # On the mane itself the base stays an open tube. But in the head the spot under the mane is
        # filled: without the mane (helmet, map) a hole gaped on the crown between the ears (seen in the
        # editor 26.09.2026). The cap lies under the mane and does not flicker with it: the head is lower,
        # see SEPARATE_*.
        if name == "hair":
            continue
        was = set(bm.faces)
        try:
            bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
        except RuntimeError:
            bmesh.ops.holes_fill(bm, edges=loop_edges, sides=0)
        patch = [f for f in bm.faces if f not in was]
        for f in patch:
            for loop in f.loops:
                near = next((l for l in loop.vert.link_loops if l.face not in patch), None)
                if near and uv is not None:
                    loop[uv].uv = near[uv].uv
        if patch:
            bmesh.ops.recalc_face_normals(bm, faces=patch)
            if name == "head":
                # The head is almost convex: the patch normal must point away from the head centre,
                # otherwise from outside (the game does not draw back faces) there is a hole at the patch.
                centre = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
                for f in patch:
                    if f.normal.dot(f.calc_center_median() - centre) < 0:
                        f.normal_flip()
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # The wing/tail socket is ragged: a patch along such an edge comes out crumpled. Relax it together
        # with the edge itself - the back becomes even and smooth, and the wing still sits on top and goes
        # inside. Include a ring around it too, otherwise the patch comes out as a dent, but do not touch
        # vertices on the free edge: those are the seams with the head, legs and hands.
        for _ in range(SMOOTH_GROW):
            smooth.update(o for v in list(smooth) for e in v.link_edges for o in e.verts
                          if not any(len(x.link_faces) == 1 for x in o.link_edges))
        for _ in range(SMOOTH_ROUNDS):
            bmesh.ops.smooth_vert(bm, verts=list(smooth), factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        log("  %s: спина заглажена, %d вершин" % (name, len(smooth)))
    if patched:
        log("  %s: заделано %d граней на месте отрыва" % (name, patched))
    if name == "head":
        # Where the head touches the mane closely, the surfaces flicker through each other - same depth.
        # Head vertices closer than SEPARATE_NEAR to the mane are sunk into the model.
        from mathutils.bvhtree import BVHTree
        horn_faces = [f for f in hippo.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]
        if horn_faces:
            tree = BVHTree.FromPolygons([tuple(v.co) for v in hippo.data.vertices],
                                        [tuple(f.vertices) for f in horn_faces])
            bm.normal_update()
            pushed = 0
            for v in bm.verts:
                hit = tree.find_nearest(v.co)
                if hit[0] is None or hit[3] >= SEPARATE_NEAR:
                    continue
                v.co -= v.normal * (SEPARATE_PUSH * (0.4 + 0.6 * (1.0 - hit[3] / SEPARATE_NEAR)))
                pushed += 1
            log("  голова отодвинута от гривы вглубь: %d вершин" % pushed)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for poly in ob.data.polygons:
        poly.use_smooth = True
    if name in ("tail", "wings"):   # items entirely on one bone, like the pony tail
        anchor = PELVIS if name == "tail" else "bip01_spine2_11"
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name=anchor).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    if name == "hair":              # hairstyle entirely on the head
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name="bip01_head_13").add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    if name == "head":
        add_blink(ob, eyes_early)
    parts[name] = ob
    log("%s: %d вершин, %d граней" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
bpy.data.objects.remove(hippo)

# ---------------------------------------------------------------- 6. export and previews
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts.values()]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = skel
path = os.path.join(OUT, "eq_%s.fbx" % RACE)
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("экспорт", path)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "eq_%s.blend" % RACE))

prev = os.path.join(OUT, "preview")
os.makedirs(prev, exist_ok=True)
scene = bpy.context.scene
# The vanilla human IN PLACE of the dragon: it shows what sticks out of the armour and how far forward
# the arms and legs are. The same file as for the depth fitting.
overlay = []
if os.path.exists(HUMAN):
    known = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=HUMAN, forward_axis="Y", up_axis="Z")
    for ob in [o for o in bpy.data.objects if o not in known]:
        ob.rotation_euler[2] = math.pi      # vanilla models face +Y, ours face -Y
        ob.color = (0.95, 0.35, 0.35, 1.0)
        ob.hide_render = True
        overlay.append(ob)
for ob in pony.values():
    ob.location.x -= 2.0        # pony alongside - to compare height
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
# the pony alongside must be visible: some meshes are hidden in the source file
for ob in pony.values():
    ob.hide_render = ob.hide_viewport = False
    ob.color = (0.75, 0.70, 0.80, 1.0)
    if ob.name not in bpy.context.scene.collection.objects:
        try:                     # in the source file the pony may be in a disabled collection
            bpy.context.scene.collection.objects.link(ob)
        except RuntimeError:
            pass
# each part of the dragon gets its own colour - shows where the cut went
PART_COLOUR = {"body": (0.80, 0.75, 0.65, 1), "legs": (0.35, 0.55, 0.85, 1),
               "gloves": (0.95, 0.80, 0.25, 1), "head": (0.35, 0.80, 0.45, 1),
               "hair": (0.90, 0.35, 0.75, 1), "wings": (0.55, 0.40, 0.85, 1),
               "tail": (0.95, 0.45, 0.30, 1)}
for name, ob in parts.items():
    ob.color = PART_COLOUR.get(name, (1, 1, 1, 1))
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
# The "height" shot is next to the pony for comparison, the rest without it: otherwise it blocks
# the dragon from the side and you cannot see what is left on the back and where the cut went.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # wings and tail removed: shows whether pieces of them were left on the body and whether they took
        # anything of the body's with them; from the back: the wing and tail sockets, which this shot is for
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair")),
        # head only - as the mod kit shows it: shows whether mane strands were left on the face
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        # over the vanilla human: red shows what sticks out of the silhouette the armour is made for
        ("поверх человека", (0, -6, 1.05), FRONT, 2.6, "поверх", ("wings", "tail")),
        ("поверх человека сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, "поверх",
         ("wings", "tail"))):
    for ob in pony.values():
        ob.hide_render = with_pony is not True
    for ob in overlay:
        ob.hide_render = with_pony != "поверх"
    for name, ob in parts.items():
        ob.hide_render = name in hide
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "hippogriff_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
