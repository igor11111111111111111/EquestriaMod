# -*- coding: utf-8 -*-
"""A griffon from a ready-made model (T-pose, its own Mixamo skeleton) - onto the pony skeleton, in parts, to FBX.

Run (headless Blender, opens the finished pony - it holds the skeleton and the binding reference):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_griffon.py \
      -- "<path to the griffon .fbx>" "<output folder>"

Copied from tools/make_dragon.py - all explanations of the shared parts are there. How the griffon differs:
  1. The wings grow FROM THE ARMS: the feathers are bound to the LeftArm/RightArm/ForeArm/Hand bones, and at the end
     of the arm there is also a clawed hand. The dragon's wings were separate from the arms. So the pieces "far from
     the bones" are identified not by height but by size: the two largest are the wings, a separate
     low piece on the axis is the lion tail, the rest (feather tufts on the thighs) stays with the body.
  2. The head is an eagle's: a beak and feather "ears". The hairstyle is the feathers on the back of the head and
     the crown, like the dragon's crest.

Output parts:
  eq_griffon_body   - torso and arms (body_meta_mesh)
  eq_griffon_legs   - legs (legs_mesh)
  eq_griffon_gloves - hands (hands_mesh)
  eq_griffon_head   - head with the beak (face_meta_mesh)
  eq_griffon_hair   - feathers of the crown and the back of the head (a hairstyle, coloured with the hair colour)
  eq_griffon_wings  - wings (an item in the cape slot)
  eq_griffon_tail   - tail (an item)
Then - import the FBX into the Modding Kit by hand, then tools/griffon_material.ps1.
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

RACE = "griffon"
HEIGHT = 1.95          # griffon height in metres (pony 1.86, yak 2.05, dragon 2.10)
MAT = "eq_griffon_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[griffon]", *a, flush=True)


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
griffon = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # generator junk: a placeholder sphere and other small meshes
    if ob.type == "MESH" and ob is not griffon:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (griffon.name, len(griffon.data.vertices), source_skel.name if source_skel else "нет"))

own_bones = []
if source_skel:
    # Rest pose: the file contains a run animation, and the import puts the model into its first frame. The mesh
    # itself is stored in the bind pose (T), so it is enough to remove the animation and the modifier.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = griffon
    for mod in list(griffon.modifiers):
        if mod.type == "ARMATURE":
            griffon.modifiers.remove(mod)
    griffon.parent = None
    # The bones are remembered as segments in world coordinates BEFORE the skeleton is deleted: the wings and tail
    # are selected below by distance from them. The Mixamo end bones («_end») stick out sideways
    # past the mesh and only spoil the measurement.
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят (запомнено %d костей), модель в позе привязки" % len(own_bones))

bpy.ops.object.select_all(action="DESELECT")
griffon.select_set(True)
bpy.context.view_layer.objects.active = griffon
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# The generator outputs a "soup": neighbouring triangles do not share vertices. We weld them - otherwise
# connected pieces cannot be found and gaps open up along the seams under deformation.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(griffon.data.vertices))


def coords():
    return np.array([(griffon.matrix_world @ v.co)[:] for v in griffon.data.vertices])


# ------------------------------------------------- wings and tail: connected pieces far from the bones
# The same trick as for the dragon: the feathers and tail stick out far from any bone, while the skin of the
# torso, arms and legs is always near its own. We take everything farther than FAR_FRAC from the bones and cut it
# into connected pieces.
#
# But the pieces are identified differently. For the griffon at FAR_FRAC=0.114 there are five (measured on the model):
#   732 and 716 vertices, z 1.21..1.97  - wings;
#   259 and 219 vertices, z 0.70..1.13  - feather tufts on the thighs, part of the body;
#   187 vertices, x near zero, z 0.08..0.75 - the lion tail.
# They cannot be told apart by size or by middle: the feathers at the shoulder glue the tufts to the wing, and both
# "largest pieces" come together with the thighs, while the tail (187 vertices) falls short of the size
# threshold. But the wing is the only thing that reaches the crown: we look at the TOP of the piece.
FAR_FRAC = 0.114
PART_MIN = 0.025      # a piece smaller than this share of vertices - feather ears and small stuff: left alone
WING_TOP = 0.75       # a piece rising above this share of the height is a wing
TAIL_HIGH = 0.45      # the tail is looked for below this share of the height
TAIL_AXIS = 0.12      # and no farther than this share of the height from the body axis
# The feathers right at the shoulder lie on top of the arm and are not selected by distance. But in the
# original skinning you can tell which is which: the arm never gets farther than ARM_FAR from its bone,
# the feathers noticeably farther.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


appendage = [None] * len(griffon.data.vertices)
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in griffon.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in griffon.data.vertices])
    added = np.zeros(len(P), bool)
    for name in own_bones:
        if "Arm" not in name:          # only the arm bones: the wings hang from them
            continue
        sel = dominant == name
        if sel.any():
            added[sel] |= bone_gap(name, P[sel]) > ARM_FAR * height
    added &= ~far
    far |= added
    # Where the model's hand is - by its ORIGINAL bone: below, by these vertices the arm is aligned with the
    # skeleton's arm. It cannot be measured by the claw tips, they are long.
    own_hand = {i for i, d in enumerate(dominant) if "Hand" in d}
    if added.any():
        pts = P[added]
        log("по костям рук добавлено %d вершин: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (рост %.2f)"
            % (int(added.sum()), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(),
               pts[:, 2].min(), pts[:, 2].max(), height))

    neighbours = [[] for _ in range(len(P))]
    for e in griffon.data.edges:
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

    middle_y = float(np.median(P[:, 1]))
    floor = float(P[:, 2].min())
    big = [c for c in sorted(chunks, key=len, reverse=True) if len(c) >= PART_MIN * len(P)]
    for chunk in big:
        mid = P[chunk].mean(0)
        top = float(P[chunk][:, 2].max()) - floor
        if mid[1] < middle_y:          # everything of ours is behind the back; there is nothing to be in front
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        if top > WING_TOP * height:
            name = "wings"
        elif mid[2] - floor < TAIL_HIGH * height and abs(mid[0]) < TAIL_AXIS * height:
            name = "tail"
        else:
            # feather tufts on the thighs: they stay with the body, they deform together with the leg
            log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) оставлен телу"
                % (len(chunk), *mid, top))
            continue
        log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) -> %s"
            % (len(chunk), *mid, top, name))
        for i in chunk:
            appendage[i] = name
    # The leading edge of the wing with the claws lies right against the finger bones (in the T-pose the hand and the
    # wing claw end up at one point), so it is not selected by distance and stayed on the
    # body as shards sticking out. But it holds ONLY onto the membrane: once the wings are removed,
    # it hangs as a separate island. So we look at what the remainder falls apart into: the large
    # piece is the dragon itself, everything else near a wing or the tail is given back to it.
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
    ISLAND_NEAR = 0.05        # an island farther than this share of the height from the wing and tail is not theirs
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


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: размер %.2f x %.2f x %.2f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))

# The muzzle must face -Y (as with the pony). The muzzle is the point of the upper third protruding most along Y.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    griffon.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
griffon.scale = (scale, scale, scale)
griffon.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- depth: seat by the TORSO, not by the bounding box
# Seating by the bounding box is not possible: the dragon's tail pulls the box backward, and the torso shifts forward
# from the spine. Then the spine bone runs right along the back, the chest wobbles at any turn
# of the body, and the arms and legs hang in front of the armour.
# The depth reference is the VANILLA HUMAN, not the pony: the armour is made for him, and he defines its fit.
# The human body is exported from the game's assets:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<game>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Vanilla models face +Y (ours face -Y), so the reference is turned around.
TORSO_Z = (1.00, 1.35)    # between the bones bip01_spine_9 and bip01_spine2_11
TORSO_HALF = 0.22         # wider than this along X - already the arms
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
# We move the mesh itself, not the object: "baking" the shift (transform_apply) works only with
# a selected object, and the reference import grabs the selection - then the object moves, and all
# subsequent edits are written in local coordinates and miss by exactly this shift.
for v in griffon.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Where the neck ends and the head begins. The line runs obliquely forward and down (under the muzzle), and
# it must be measured FROM THE MODEL ITSELF: seating by the torso shifted the dragon in depth, so the same
# shift is added to the world mark. It is needed already here: the head must not be touched together
# with the arms - its sides fall into the same X zone, and the arm fix tore the muzzle to shreds.
NECK_Z = bones["bip01_neck_12"].z + 0.06
JAW_SLOPE, JAW_FROM = 0.45, -0.10 + shift


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ---------------------------------------------- arms from the T-pose onto the pony's arm (rotation + length)
# Just rotating by 22 degrees is not enough: the dragon's arm is 10% longer than the pony's, so the elbow
# landed on the forearm bone and the hand missed the hand bone, and in game the arms looked crooked.
# We align the dragon's "shoulder - hand" segment with the same skeleton segment: a rotation around the shoulder
# plus scaling along the length. At the joint itself the transform builds up smoothly (ramp), otherwise it tears.
SHOULDER_X = 0.16               # shoulder joint along X (the model's shoulder bone after seating)
ARM_RAMP = 0.10                 # over how many metres the transform builds up
ARM_TIP = 0.9                   # share of the span beyond which it is the hand
HEAD_RAMP = 0.12                # how many metres below the jaw the arm takes over

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
arm_y = float(np.median([P[i][1] for i in range(len(P)) if arm_far[i] and appendage[i] is None]))
ARM_BACK = arm_y + 0.12         # farther back - a wing, not an arm
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > SHOULDER_X - ARM_RAMP and p[1] < ARM_BACK and p[2] > 1.0
            and appendage[i] is None and not is_head(P[i])]
tip = max(abs(P[i][0]) for i in arm_zone)
# The hand - by the model's ORIGINAL bone, not by the claw tips: the dragon's claws are long, and by them
# the arm went far off to the side of the body (the hand ended up at |x| 0.83 instead of 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# The shoulder joint is on the axis of the arm itself, extended to SHOULDER_X. It cannot be found by a
# cross-section of the torso at this mark: the side is still there, and the middle of the section wanders
# by ten centimetres in height.
# The axis is computed from the middles of transverse strips of the arm (from 0.30 to the tips), so that the hand and
# elbow do not outweigh it, and a straight line is drawn through them.
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
# We aim the WRIST at the hand bone. Not by the pony's fingertips: her arm is longer than a human's
# (the fingers reach |x| 0.83, whereas on the vanilla body the arm ends at 0.60), and the dragon
# got splayed arms. Let the claws stick out past the bone, like a human's fingers.
H_p = bones["bip01_l_hand_19"]
# Exactly to the bone the arm comes out a bit short: the hand hides in the sleeve. We let it go farther along
# the same axis and turn it down - that way it is both longer and pressed to the body, not splayed.
# The numbers are tuned from feedback in game, as for the dragon.
ARM_REACH = 1.10    # how many times farther than the hand bone the wrist goes ("lengthen the arms a bit")
ARM_DROP = 8.0      # how many degrees the arm is additionally lowered toward the body
ARM_THICK = 1.00    # how many times thicker across the axis (the alignment itself thins the arm)
HAND_SMALL = 0.85   # how many times the hand itself is shrunk ("make the hands a bit smaller")

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
for i in arm_zone:
    p = P[i]
    sign = 1.0 if p[0] > 0 else -1.0
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # toward the head the transform fades out
    mine = Vector((abs(p[0]), p[1], p[2]))
    # along the axis the arm is stretched/squeezed by the alignment, and across it separately, otherwise it gets
    # thinner along with the shortening
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * ARM_THICK
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = griffon.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука дракона %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ---------------------------------------------------------------- a smaller hand
# The model's paw is large, with long claws, and next to a human sleeve it looks like a shovel.
# We shrink it AROUND THE WRIST (the pony's hand bone), not around the middle of the paw: otherwise a gap opens
# at the joint with the forearm. ARM_DROP above draws the hand closer to the body - it also lays
# the whole arm along the body rather than out to the sides.
if HAND_SMALL != 1.0:
    P = coords()
    shrunk = 0
    for i in (set(arm_zone) & own_hand):
        p = P[i]
        sign = 1.0 if p[0] > 0 else -1.0
        wrist = Vector((H_p.x * sign, H_p.y, H_p.z))
        griffon.data.vertices[i].co = wrist + (Vector((p[0], p[1], p[2])) - wrist) * HAND_SMALL
        shrunk += 1
    P = coords()
    hands = P[[i for i in hand_idx]]
    log("кисть ужата в %.2f раза (%d вершин), центр лапы теперь (%.2f,%.2f,%.2f)"
        % (HAND_SMALL, shrunk, abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean()))

# ---------------------------------------------------------------- arms forward, legs back
# From the side you can see the arm hangs right by the tail, and the leg is pushed forward - the figure topples.
# We move them in depth toward each other (move the arms away from the
# tail and the legs toward it, 24.09.2026). The muzzle faces -Y, so forward is minus, toward the tail is plus.
#
# Both shifts fade out smoothly: the arm lets go at the shoulder (the same ramp as for the rotation),
# the leg at the pelvis. Otherwise it tears at the joint.
ARM_FORWARD = 0.06      # how many metres the arms move forward, away from the tail
ARM_OUT = 0.035         # and how much sideways, away from the torso ("move the arms a bit away from the torso")
LEG_BACK = 0.06         # how many metres the legs move back, toward the tail
LEG_FULL = 0.55         # below this height the leg moves as a whole
LEG_FADE = 0.95         # above this - already the pelvis, left alone

P = coords()
for i in arm_zone:
    p = P[i]
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)
    griffon.data.vertices[i].co.y -= ARM_FORWARD * t
    griffon.data.vertices[i].co.x += math.copysign(ARM_OUT * t, p[0])

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
        griffon.data.vertices[i].co.y += LEG_BACK * w
        moved_legs += 1
log("руки сдвинуты вперёд на %.2f м и в стороны на %.2f м (%d вершин), ноги назад на %.2f м (%d вершин)"
    % (ARM_FORWARD, ARM_OUT, len(arm_zone), LEG_BACK, moved_legs))

# ------------------------------------------------------------------- a wider rib cage
# The model has a narrow chest - next to the wide pelvis it looks like a tube. We spread it along X, but not with
# a single scale: otherwise the arms would go along with the chest, and the hands would come off their bones. Inside
# the torso the width grows proportionally, outside the shift fades out toward the wrist, and in height - smoothly
# beyond the ribs. The wings and tail are moved together with everything, so the roots stay in place.
# In game the chest came out flat next to the wide thighs (the
# chest is squashed too much in width, 24.09.2026), then even wider was asked for, together with the belly -
# hence 1.45 and the band right down to the pelvis.
CHEST_WIDE = 1.45
# The band is its own, not the dragon's: the griffon is shorter (1.95 vs 2.10), its collarbones are at 1.41,
# the pelvis at 0.95.
CHEST_BAND = (0.95, 1.36)   # ribs and belly: from the pelvis to the collarbones
CHEST_FADE = 0.13           # over how many metres in height it builds up and falls off
CHEST_TAPER = 0.45          # over how many metres outward the shift fades out


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
HALF = float(np.percentile(np.abs(chest[:, 0]), 90))     # half-width of the torso at rib level
grow = (CHEST_WIDE - 1.0) * HALF
for i, p in enumerate(P):
    w = band_weight(p[2])
    if w <= 0:
        continue
    out = abs(p[0])
    reach = out / HALF if out < HALF else max(0.0, 1.0 - (out - HALF) / CHEST_TAPER)
    if reach <= 0:
        continue
    griffon.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- a smaller upper chest
# It is the ribs that must be spread, not the bust: on top the chest bulged both forward and sideways. We shrink
# the upper part of the chest in width and depth around its own middle - so the bottom (ribs) stays wide and
# the top tightens up. It fades out toward the shoulders, otherwise the arms would tear off them.
UPPER_SMALL = 1.00          # how many times the upper chest is shrunk (1.0 - left alone)
UPPER_BAND = (1.34, 1.58)   # from the bust to the collarbones
UPPER_FADE = 0.10           # over how many metres in height it builds up and falls off
UPPER_HALF = 0.26           # beyond this along X it is already the shoulder, no shrinking there
UPPER_TAPER = 0.16          # over how many metres outward the shrinking fades out

P = coords()
band = P[(P[:, 2] > UPPER_BAND[0]) & (P[:, 2] < UPPER_BAND[1]) & (np.abs(P[:, 0]) < UPPER_HALF)]
mid_y = float(np.percentile(band[:, 1], 2) + np.percentile(band[:, 1], 98)) / 2


def upper_size():
    # measure wider than the shrink band, otherwise the measurement runs into its own limit
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
    v = griffon.data.vertices[i]
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

for g in list(griffon.vertex_groups):     # foreign Mixamo groups are no longer needed
    griffon.vertex_groups.remove(g)
for g in ref.vertex_groups:
    griffon.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
griffon.select_set(True)
bpy.context.view_layer.objects.active = griffon
dt = griffon.modifiers.new("веса", "DATA_TRANSFER")
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

# The hand bones - only for the hands: the pony's hands hang at belly height, and the sides of the dragon's
# body turn out closer to them than to her body (the same trouble the yak had).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = griffon.data.vertices[i]
    for g in list(v.groups):
        if griffon.vertex_groups[g.group].name in HAND_BONES:
            griffon.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        griffon.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# The head rigidly on the head bone - otherwise the neck and chest bones drive the muzzle and it tears at the seam.
# The boundary (jaw_z/is_head) is set above, before the arm fix.
BLEND = 0.15

head_group = griffon.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(griffon.data.vertices[i].groups):
        griffon.vertex_groups[g.group].remove([i])
head_group.add(head_idx, 1.0, "REPLACE")
blended = torn = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p) or appendage[i] is not None:
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]
    if d >= BLEND:
        # Below the neck there must be no head bone. The weight transfer gives it to the crest on the chest: that
        # sticks out forward and up, and the pony's nearest point turns out to be her chin. In game
        # such a chest folded up at every head turn.
        if head_group.index in [g.group for g in griffon.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not griffon.data.vertices[i].groups:
                griffon.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in griffon.data.vertices[i].groups:
        griffon.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. cutting into parts
group_names = {g.index: g.name for g in griffon.vertex_groups}
dominant = []
for v in griffon.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
lo, hi = P.min(0), P.max(0)

# back: the rearmost point of a narrow strip along the spine
spine = P[(np.abs(P[:, 0]) < 0.10) & (P[:, 2] > 0.9) & (P[:, 2] < 1.3)]
BACK = float(spine[:, 1].max())
head_pts = P[[i for i in range(len(P)) if is_head(P[i])]]
HEAD_TOP = float(head_pts[:, 2].max())
HEAD_BACK = float(head_pts[:, 1].max())
# Crown of the head: below this share of the head height it is already the face
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# The mane boundary in depth: a share of the way from the eyes to the back of the head. Everything beyond it is
# mane and the back of the head, nearer - the muzzle with the frill (it must not go into the hair, it would get
# the hair colour).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # front of the muzzle
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
# Where the cut between the body and the legs runs. For the pony it is 0.44 of the 1.86 height, but the griffon has a
# bird's leg: the joint is higher, and with a low cut a bare paw stuck out from under the boot (
# cut the legs off the body a bit higher, 24.09.2026). We raise it by a palm - to mid-shin.
LEG_TOP = 0.55 * HEIGHT / 1.86
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# NO NEED TO PICK UP THE FORELOCK. I tried catching the strands left on the face by a strand being a thin
# sheet (a back face with an opposite normal nearby, a KD-tree): along with them the scales above the brow and
# pieces of the cheek went into the hairstyle, and the head shrank from 322 vertices to 150. The user:
# "make it as it was before, the hair came out really bad".
# Two marks remain - the crown and the back of the head.


def part_of(i):
    if appendage[i]:                 # the wings and tail were selected above, by distance from the bones
        return appendage[i]
    p = P[i]
    if is_head(p):
        # The "hairstyle" - horns, the crest on the crown and the mane falling from the back of the head onto the
        # shoulders: the hair colour from the appearance window works on it. The frill along the muzzle must not be
        # taken (it would be coloured along with the horns), hence a depth boundary: the mane is entirely behind the
        # skull, the muzzle in front.
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
src_mat = griffon.data.materials[0] if griffon.data.materials else None
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
            fname = "eq_griffon_" + img.name.replace(".", "_").lower() + ".png"
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

# ------------------------------------------------------------------------ blinking
# The engine blinks with the head's vertex keys: there are exactly 101 of them (key_000..key_100), and frames 86, 87, 88
# are the left eye, the right one and both (done the same way for the pony, tools/convert_twilight.py). Without the keys
# the face is just frozen, like the yak's.
#
# The pony's eyelids are separate geometry hidden above the eye. The dragon has none: the model is solid, the eye
# is just PAINTED on the texture. So we close it by squeezing: the vertices around the eye are drawn toward its
# middle in height, and the painted eye collapses into a slit. The same trick is used on the pony to
# squeeze the eyeball fully when the engine applies a frame at less than full strength.
#
# The eyes are found by the texture itself - they are two symmetric dark spots on the muzzle. The colour sample
# is taken slightly inside the face: the model's UV map is patchy, and at the very edge of an island it is
# already atlas black.
FACE_KEYS = 101         # this many vertex keys on a vanilla head
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
# The griffon's threshold is MUCH stricter than the dragon's 0.30: the eagle's brown brow feathers are darker than 0.3,
# and with such a threshold the largest dark spot came out as the brow - the blink fired above the eye
# (noticed in game 24.09.2026). The black pupil is noticeably darker than any feather, so we mark by it.
EYE_DARK = 0.16
# The squeeze zone - the semi-axes of a "segment" around the eye middle: sideways, inward, in height. The griffon's
# eye is almond-shaped and lies at a slant, so the zone is long along it and short in height - otherwise
# the brow and cheek collapse together with the eye, and the muzzle folds like an accordion.
EYE_ZONE = (0.105, 0.095, 0.055)
EYE_FULL = 0.80         # within this share of the zone we squeeze fully, beyond it fades out smoothly
EYE_SQUASH = 0.92       # how much the vertices are drawn toward the eye middle
EYE_SIDE = 0.02         # closer than this to the axis - not an eye but the beak
# The mark lands on the PUPIL, and for the griffon it is right by the beak, whereas the eye itself with the sclera
# goes outward and slightly back - only the half near the nose closed (noticed in game 24.09.2026).
# So from the found pupil we step toward the middle of the eye.
EYE_OUT = 0.035         # outward, from the beak toward the temple
EYE_BACK = 0.030        # and back: the griffon's sclera goes toward the temple, the eye is almond-shaped


def eye_spots(ob):
    """Eye middles on the head: two dark spots on the texture, one per side."""
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
    # One spot per side: in the front part of the head (the beak in the centre does not fall on a side,
    # shadows at the back of the head are behind) and the DARKEST, not the largest. The largest is the brown brow:
    # it has more feathers than the pupil has polygons, and by size it won.
    front = float(np.percentile(P[:, 1], 45))
    out = []
    for side in (1, -1):
        mine = [(c, n, s) for c, n, s in spots if c[0] * side > EYE_SIDE and c[1] < front]
        out.append(min(mine, key=lambda s: s[2])[0] if mine else None)
    # The head is low-poly and asymmetric: the pupil gets one or two vertices, and on
    # one side there may be no dark sample at all. Then we mirror the found eye - this is
    # more reliable than relaxing the threshold down to the brown brow feathers.
    if out[0] is None and out[1] is not None:
        out[0] = np.array([-out[1][0], out[1][1], out[1][2]])
        log("  левый глаз отражён с правого")
    elif out[1] is None and out[0] is not None:
        out[1] = np.array([-out[0][0], out[0][1], out[0][2]])
        log("  правый глаз отражён с левого")
    # from the pupil - toward the middle of the eye (see EYE_OUT)
    for spot in out:
        if spot is not None:
            spot[0] += math.copysign(EYE_OUT, spot[0])
            spot[1] += EYE_BACK
    return [s for s in out if s is not None]


def add_blink(ob):
    spots = eye_spots(ob)
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
            # The zone is not a ball but a "segment" shaped like the eye: wide sideways and inward, low in height.
            # A ball did not work: to squeeze the outer corner fully, the radius had to be so large
            # that the brow and cheek got crumpled too, and the muzzle folded like an accordion.
            step = (P - eye) / radius
            # Height is handled separately from "along the eye": the zone comes out as a flat cake, not a ball.
            # If all three axes are counted together, the outer corner of the eye (far sideways AND slightly above
            # the middle) falls out of the zone and stays open.
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


# ---------------------------------------------------------------- 5. parts as separate meshes
PLUG = 0.18        # how far the root of the wing and tail goes inside the body - slack for animation
SMOOTH_ROUNDS = 18  # how many times the socket from the wing and tail is relaxed so the back becomes smooth
SMOOTH_GROW = 2     # over how many rings around the patch the smoothing spreads
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


SEPARATE_NEAR = 0.025  # head vertices closer than this to the mane are sunk inward (metres)
SEPARATE_PUSH = 0.010  # and by this much, right at the mane

parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "wings", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = griffon.copy()
    ob.data = griffon.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    was_index = {v: i for i, v in enumerate(bm.verts)}   # indices before deletion - labels go by them
    keep_set = set(keep)
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # The tear-off spot is closed with polygons: otherwise through-holes gape at the joints of the wings, tail and neck
    # (faces are not drawn from the inside, and in game it is black there). ONLY the cuts must be closed:
    # the wing and membrane have a free edge all around, and it must not be filled - that would cover
    # the membrane with a solid sheet. A cut is recognized by a vertex of another part having been next to it
    # in the original mesh. The UV for new faces is taken from neighbouring faces of the same vertex,
    # otherwise they pull colour from a corner of the texture.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] != name for o in neighbours[was_index[v]])}

    # The wings and tail sit on their own bone, and the body at their root on its own (the back at the wing follows
    # the clavicle), so in motion the seam opens and you can see right through the gap. So for the wing and
    # tail we extend the root INTO the body: from the cut a skirt is led toward the spine. From outside it is not
    # visible, and it covers the gaps with margin.
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
        while stack:                     # the whole connected contour of the free edge
            cur = stack.pop()
            loop_edges.append(cur)
            for v in cur.verts:
                for e in v.link_edges:
                    if len(e.link_faces) == 1 and e not in seen_edge:
                        seen_edge.add(e)
                        stack.append(e)
        ring = {v for e in loop_edges for v in e.verts}
        if len(ring) < 3 or sum(1 for v in ring if v in cut) < 0.6 * len(ring):
            continue                     # the free edge of the membrane itself - left alone
        # whose boundary this was: with the wing and tail the socket is smoothed afterwards, but the seam with the head,
        # legs and hands must not be touched - it joins the neighbouring part there, it must stay
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] != name]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # On the manes themselves the base stays an open tube. But in the head the spot under the mane
        # is filled: without the mane (helmet, map) a hole gaped on the crown between the ears (noticed in the
        # editor 26.09.2026). The lid lies under the mane and does not flicker with it: the head is lower,
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
                # The head is almost convex: the patch normal must face away from the head centre,
                # otherwise from outside (the game does not draw back faces) there will be a hole in place of the patch.
                centre = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
                for f in patch:
                    if f.normal.dot(f.calc_center_median() - centre) < 0:
                        f.normal_flip()
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # The socket from the wing and tail is ragged: a patch along such an edge comes out crumpled. We relax
        # it together with the edge itself - the back becomes even and smooth, and the wing still sits
        # on top and goes inside. We take in the ring around it too, otherwise the patch comes out as a dent,
        # but we do not touch vertices on the free edge: those are the seams with the head, legs and hands.
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
        # Where the head touches the mane closely, the surfaces flicker through each other - the same
        # depth. Head vertices closer than SEPARATE_NEAR to the mane are sunk into the model.
        from mathutils.bvhtree import BVHTree
        horn_faces = [f for f in griffon.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]
        if horn_faces:
            tree = BVHTree.FromPolygons([tuple(v.co) for v in griffon.data.vertices],
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
    if name in ("tail", "wings"):   # items entirely on one bone, like the pony's tail
        anchor = PELVIS if name == "tail" else "bip01_spine2_11"
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name=anchor).add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    if name == "hair":              # the hairstyle entirely on the head
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        ob.vertex_groups.new(name="bip01_head_13").add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    ob.modifiers.new("Armature", "ARMATURE").object = skel
    if name == "head":
        add_blink(ob)
    parts[name] = ob
    log("%s: %d вершин, %d граней" % (ob.name, len(ob.data.vertices), len(ob.data.polygons)))
bpy.data.objects.remove(griffon)

# ---------------------------------------------------------------- 6. export and preview
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
# The vanilla human IN PLACE of the dragon: it shows what sticks out of the armour and how far
# the arms and legs are pushed forward. The same file as for the depth seating.
overlay = []
if os.path.exists(HUMAN):
    known = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=HUMAN, forward_axis="Y", up_axis="Z")
    for ob in [o for o in bpy.data.objects if o not in known]:
        ob.rotation_euler[2] = math.pi      # vanilla models face +Y, ours -Y
        ob.color = (0.95, 0.35, 0.35, 1.0)
        ob.hide_render = True
        overlay.append(ob)
for ob in pony.values():
    ob.location.x -= 2.0        # the pony alongside - to compare height
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
# the pony alongside must be visible: in the source file some meshes are hidden
for ob in pony.values():
    ob.hide_render = ob.hide_viewport = False
    ob.color = (0.75, 0.70, 0.80, 1.0)
    if ob.name not in bpy.context.scene.collection.objects:
        try:                     # in the source file the pony may be in a disabled collection
            bpy.context.scene.collection.objects.link(ob)
        except RuntimeError:
            pass
# each dragon part gets its own colour - this shows where the cut went
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
# The "height" shot - next to the pony for comparison, the others without her: otherwise she hides the dragon
# from the side and you cannot see what remained on the back and where the cut went.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # wings and tail removed: shows whether pieces of them remained on the body and whether they took something
        # of their own from the back: the sockets from the wings and tail are there, that is what the shot is for
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair")),
        # the head alone - the way the mod kit shows it: shows whether any mane strands remained on the face
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        # over the vanilla human: in red what sticks out past the silhouette the armour is made for
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
    scene.render.filepath = os.path.join(prev, "griffon_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
