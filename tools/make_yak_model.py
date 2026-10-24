# -*- coding: utf-8 -*-
"""Yak from a ready-made model (T-pose, NO skeleton) onto the pony skeleton, split into parts, to FBX.

Run (headless Blender, opens the finished pony: it holds the skeleton and the skinning reference):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_yak_model.py \
      -- "<path to the yak .fbx>" "<output folder>"

Copied from tools/make_dragon.py, where the shared parts are explained. How the yak differs:
  1. The model has NO skeleton or weights of its own, so there is no "far from the bones" pass: it
     needs no wings, and the tail is found by position (behind the back, at pelvis height), as in the
     former tools/make_yak.py.
  2. Its proportions are almost human, so it needs almost no proportion fixes.

Output parts:
  eq_yak_body   — torso and arms (body_meta_mesh)
  eq_yak_legs   — legs (legs_mesh)
  eq_yak_gloves — hands (hands_mesh)
  eq_yak_head   — head with muzzle and horns (face_meta_mesh)
  eq_yak_hair   — mane on the crown and nape (hairstyle, tinted by hair colour)
  eq_yak_tail   — tail (item)
Then import the FBX into the Modding Kit by hand, then tools/yak_material.ps1.
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

RACE = "yak"
HEIGHT = 1.92          # yak height: the model's proportions are almost human
MAT = "eq_yak_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[yak]", *a, flush=True)


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
yak = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # generator junk: the placeholder sphere and other small meshes
    if ob.type == "MESH" and ob is not yak:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (yak.name, len(yak.data.vertices), source_skel.name if source_skel else "нет"))

own_bones = []
if source_skel:
    # Rest pose: the file holds a run animation, and the import puts the model in its first frame. The
    # mesh itself is stored in the bind pose (T), so removing the animation and the modifier is enough.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = yak
    for mod in list(yak.modifiers):
        if mod.type == "ARMATURE":
            yak.modifiers.remove(mod)
    yak.parent = None
    # Store the bones as world-space segments BEFORE deleting the skeleton: the wings and tail are
    # picked below by distance from them. Mixamo end bones ("_end") stick out sideways past the
    # mesh and only spoil the measurement.
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят (запомнено %d костей), модель в позе привязки" % len(own_bones))

bpy.ops.object.select_all(action="DESELECT")
yak.select_set(True)
bpy.context.view_layer.objects.active = yak
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# The generator outputs "soup": neighbouring triangles share no vertices. Weld them, otherwise
# connected pieces cannot be found and gaps open along the seams when deforming.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(yak.data.vertices))


def coords():
    return np.array([(yak.matrix_world @ v.co)[:] for v in yak.data.vertices])


# ------------------------------------------------- wings and tail: connected pieces far from bones
# Axis thresholds cannot separate them: the wing root reaches the spine itself (|x| down to 0.07), and
# the tail fin is wider than the pelvis, so the legs went off with a piece of tail, the head with a
# piece of wing, and a patch stayed on the back. But wings and tail have no bones OF THEIR OWN: the
# membrane is bound to the arm bones, the tail to the pelvis, and both stick out far from any skeleton
# segment, whereas the skin of the torso, arms and legs is always close to its bone. Take everything
# farther than FAR_FRAC from the bones and cut it into edge-connected pieces: exactly three are large,
# two wings and the tail.
# The threshold is stable at 0.10..0.16 of height (below that the wings merge on the back), take the middle.
FAR_FRAC = 0.114
PART_MIN = 0.04       # a piece below this share of vertices is horns, ears, muzzle: leave them alone
TAIL_HIGH = 0.45      # a piece whose middle is below this share of height is the tail, above is a wing
# The shoulder fins of the wing lie ON TOP of the arm and fall into its bone by distance. But the
# native skinning shows which is which: the arm is bound to its bone and never gets farther than 0.07
# of height from it, while the membrane and fins use the same arm bones but are 0.12..0.29 away.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


# Neighbours of each vertex: used below to find connected pieces and to seal cuts. Computed
# BEFORE the split into parts: for a model without a skeleton the split is skipped, but the
# neighbours are still needed.
neighbours = [[] for _ in range(len(yak.data.vertices))]
for e in yak.data.edges:
    neighbours[e.vertices[0]].append(e.vertices[1])
    neighbours[e.vertices[1]].append(e.vertices[0])

appendage = [None] * len(yak.data.vertices)
own_hand = set()      # a model without a skeleton has no native weights: find the hand by span
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in yak.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in yak.data.vertices])
    added = np.zeros(len(P), bool)
    for name in own_bones:
        if "Arm" not in name:          # only arm bones: the wings hang from them
            continue
        sel = dominant == name
        if sel.any():
            added[sel] |= bone_gap(name, P[sel]) > ARM_FAR * height
    added &= ~far
    far |= added
    # Where the model's hand is, by its NATIVE bone: below, these vertices are used to align the arm
    # with the skeleton arm. Measuring by the claw tips does not work, they are long.
    own_hand = {i for i, d in enumerate(dominant) if "Hand" in d}
    if added.any():
        pts = P[added]
        log("по костям рук добавлено %d вершин: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (рост %.2f)"
            % (int(added.sum()), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(),
               pts[:, 2].min(), pts[:, 2].max(), height))

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
    for chunk in sorted(chunks, key=len, reverse=True):
        if len(chunk) < PART_MIN * len(P):
            break
        mid = P[chunk].mean(0)
        if mid[1] < middle_y:          # everything of ours is behind the back; nothing should be in front
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        # By the height of the middle: wings sit at chest level, the tail near the floor. Splitting by X
        # is impossible: both wings may merge on the back into one piece with its middle on the axis.
        name = "tail" if mid[2] < TAIL_HIGH * height else "wings"
        for i in chunk:
            appendage[i] = name
    # The clawed leading edge of the wing lies right against the finger bones (in the T-pose the hand
    # and the wing claw end up at one point), so it is not picked by distance and stayed on the body
    # as shards sticking out. But it is held ONLY by the membrane: once the wings are removed, it
    # hangs as a separate island. So look at what the remainder breaks into: the big piece is the
    # dragon itself, everything else next to a wing or the tail goes back to it.
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
    ISLAND_NEAR = 0.05        # an island farther than this share of height from wing and tail is not theirs
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

# The muzzle must face -Y (like the pony's). The muzzle is the point of the upper third that sticks
# out most along Y.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    yak.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
yak.scale = (scale, scale, scale)
yak.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- depth: placed by the TORSO, not by the bounds
# Placing by the bounding box does not work: the dragon's tail pulls the box back and the torso moves
# forward off the spine. Then the spine bone runs right at the back, the chest wobbles with any torso
# turn, and the arms and legs hang in front of the armour.
# The depth reference is the VANILLA HUMAN, not the pony: the armour is made for it, and it sets the fit.
# The human body is exported from the game assets:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<game>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Vanilla models face +Y (ours face -Y), so the reference is turned around.
TORSO_Z = (1.00, 1.35)    # between bones bip01_spine_9 and bip01_spine2_11
TORSO_HALF = 0.22         # wider than this along X is already the arms
HUMAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "human_ref", "human.obj")
DEPTH_EXTRA = 0.0         # manual depth correction on top of the computed one, if still off in game


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
# Move the mesh itself, not the object: "baking" the shift (transform_apply) works only on the
# selected object, and importing the reference steals the selection; then the object moves away and
# all later edits are written in local coordinates and miss by exactly this shift.
for v in yak.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Where the neck ends and the head begins. The line slopes forward and down (under the muzzle), and
# it must be measured FROM THE MODEL ITSELF: placing by the torso shifted the dragon in depth, so the
# same shift is added to the world mark. It is needed already here: the head must not be touched along
# with the arms, its sides fall into the same X zone, and the arm fix tore the muzzle to shreds.
NECK_Z = bones["bip01_neck_12"].z + 0.06
# Slope of the jaw line: how far it drops towards the muzzle. The yak's muzzle is heavy and hangs low;
# with the dragon's 0.45 the chin stayed with the body and stuck out of it as a separate piece
# (seen in game 24.09.2026). 0.9 puts the line fully under the chin.
JAW_SLOPE, JAW_FROM = 0.9, -0.10 + shift


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ---------------------------------------------- arms from T-pose onto the pony arm (rotation + length)
# Rotating by 22 degrees is not enough: the dragon's arm is 10% longer than the pony's, so the elbow
# fell on the forearm bone and the hand missed the hand bone, and in game the arms looked crooked.
# Align the dragon's "shoulder to hand" segment with the same skeleton segment: a rotation about the
# shoulder plus a scale along the length. Near the joint itself the transform ramps in (ramp), or it tears.
SHOULDER_X = 0.18               # shoulder joint along X (the model's upper arm bone after placement)
ARM_RAMP = 0.10                 # over how many metres the transform ramps in
ARM_TIP = 0.9                   # share of span beyond which it is the hand
HEAD_RAMP = 0.12                # how many metres below the jaw the arm takes over

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
arm_y = float(np.median([P[i][1] for i in range(len(P)) if arm_far[i] and appendage[i] is None]))
ARM_BACK = arm_y + 0.12         # farther back is a wing, not the arm
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > SHOULDER_X - ARM_RAMP and p[1] < ARM_BACK and p[2] > 1.0
            and appendage[i] is None and not is_head(P[i])]
tip = max(abs(P[i][0]) for i in arm_zone)
# The hand is taken by the model's NATIVE bone, not by the claw tips: the dragon's claws are long, and
# by them the arm moved far sideways from the body (the hand landed at |x| 0.83 instead of 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# The shoulder joint is on the axis of the arm itself, extended to SHOULDER_X. A slice of the torso at
# that mark does not find it: the side is still there, and the slice middle drifts ~10 cm in height.
# The axis is computed from the middles of cross bands of the arm (from 0.30 to the tips), so that
# the hand and elbow do not dominate, and a straight line is fitted through them.
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
# Aim the WRIST at the hand bone. Pony fingertips cannot be used: her arm is longer than a human's
# (the fingers reach |x| 0.83, while the vanilla body's arm ends at 0.60), and the dragon
# got splayed arms. Let the claws stick past the bone, like human fingers.
H_p = bones["bip01_l_hand_19"]
# Exactly at the bone the arm comes out a bit short: the hand hides in the sleeve. Let it go further
# along the same axis and turn it down: that makes it both longer and close to the body, not splayed.
# 1.07 is per the test request of 24.09.2026: exactly at the bone the arm came out a bit short, the
# hand hid in the sleeve.
ARM_REACH = 1.07    # how many times farther than the hand bone the wrist goes
ARM_DROP = 0.0      # by how many degrees the arm is additionally lowered towards the body
ARM_THICK = 1.00    # how many times thicker across the axis (the alignment itself thins the arm)

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
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # towards the head the transform fades out
    mine = Vector((abs(p[0]), p[1], p[2]))
    # along the axis the arm is stretched/squeezed by the alignment, across it separately, otherwise
    # it gets thinner together with the shortening
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * ARM_THICK
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = yak.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука дракона %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ------------------------------------------------------------------- wider rib cage
# The model has a narrow chest: next to a wide pelvis it looks like a tube. Widen it along X, but not
# with one scale: otherwise the arms go along with the chest and the hands slide off their bones. Inside
# the torso the width grows proportionally, outside the shift fades out towards the wrist, and in height
# it fades smoothly beyond the ribs. Wings and tail move along with the rest so their roots stay put.
CHEST_WIDE = 1.0
CHEST_BAND = (1.15, 1.42)   # ribs: from the waist to the collarbones
CHEST_FADE = 0.13           # over how many metres in height it ramps in and out
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
    yak.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- smaller upper chest
# It is the ribs that should be widened, not the bust: at the top the chest bulged both forward and
# sideways. Shrink the upper chest in width and depth around its own middle, so the bottom (ribs) stays
# wide and the top tightens. It fades out towards the shoulders, otherwise the arms would tear off.
UPPER_SMALL = 1.00          # by how many times the upper chest is shrunk
UPPER_BAND = (1.34, 1.58)   # from the bust to the collarbones
UPPER_FADE = 0.10           # over how many metres in height it ramps in and out
UPPER_HALF = 0.26           # beyond this along X is already the shoulder, no shrinking there
UPPER_TAPER = 0.16          # over how many metres outward the shrinking fades out

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
    v = yak.data.vertices[i]
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

for g in list(yak.vertex_groups):     # foreign Mixamo groups are no longer needed
    yak.vertex_groups.remove(g)
for g in ref.vertex_groups:
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

# Hand bones go to the hands only: the pony's hands hang at belly height, and the sides of the dragon's
# torso end up closer to them than to her body (the same trouble the yak had).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = yak.data.vertices[i]
    for g in list(v.groups):
        if yak.vertex_groups[g.group].name in HAND_BONES:
            yak.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        yak.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# The head is rigidly on the head bone, otherwise the neck and chest bones drive the muzzle and it tears
# at the joint.
# The boundary (jaw_z/is_head) is set above, before the arm fix.
BLEND = 0.15

head_group = yak.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(yak.data.vertices[i].groups):
        yak.vertex_groups[g.group].remove([i])
head_group.add(head_idx, 1.0, "REPLACE")
blended = torn = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p) or appendage[i] is not None:
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]
    if d >= BLEND:
        # Below the neck there must be no head bone. The weight transfer gives it to the crest on the
        # chest: it sticks forward and up, and the nearest pony point is her chin. In game such a
        # chest folded with every head turn.
        if head_group.index in [g.group for g in yak.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not yak.data.vertices[i].groups:
                yak.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in yak.data.vertices[i].groups:
        yak.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. cutting into parts
group_names = {g.index: g.name for g in yak.vertex_groups}
dominant = []
for v in yak.data.vertices:
    best = max(v.groups, key=lambda g: g.weight, default=None)
    dominant.append(group_names[best.group] if best else PELVIS)
P = coords()
lo, hi = P.min(0), P.max(0)

# back: the rearmost point of a narrow band along the spine
spine = P[(np.abs(P[:, 0]) < 0.10) & (P[:, 2] > 0.9) & (P[:, 2] < 1.3)]
BACK = float(spine[:, 1].max())
head_pts = P[[i for i in range(len(P)) if is_head(P[i])]]
HEAD_TOP = float(head_pts[:, 2].max())
HEAD_BACK = float(head_pts[:, 1].max())
# Crown: below this share of the head height it is already the face
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Mane boundary in depth: share of the way from the eyes to the nape. Everything beyond it is mane and
# nape, closer is the muzzle with the frill (it must not go into the hair, it would be tinted by hair colour).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # front of the muzzle
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
LEG_TOP = 0.44 * HEIGHT / 1.86
# Where the hand starts: a little closer to the body than the wrist after the arm alignment (see the
# arms section). The mark follows ARM_REACH, otherwise the lengthened arm pushes the wrist past the
# boundary and a piece of forearm goes into the "gloves".
_shoulder_x = abs(bones["bip01_l_upperarm_twist_15"].x)
HAND_FROM = _shoulder_x + (abs(bones["bip01_l_hand_19"].x) - _shoulder_x) * ARM_REACH - 0.03
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# NO NEED TO COLLECT THE FORELOCK. I tried catching strands left on the face by the fact that a strand
# is a thin sheet (the back side with an opposite normal is nearby, KD-tree): along with them, scales
# above the brow and pieces of cheek went into the hairstyle, and the head shrank from 322 vertices to
# 150. The user: ("make it as it was
# before, the hair came out really bad"). Two marks remain: the crown and the nape.


# The tail is found BY POSITION: the model has no skeleton and no weights, hence no "far from the bone"
# pass. The yak's tail is a thin tuft sticking out BEHIND THE CROUP. One depth threshold cannot catch it:
# the tuft hangs at the same depth as the buttocks. So for each height band measure how far the croup
# reaches (at the sides, where there is surely no tail), and count as tail whatever is near the axis and
# farther back.
TAIL_HALF = 0.09      # wider than this from the axis is the croup, not the tail
TAIL_LOW, TAIL_UP = 0.30, 1.10    # search only within these heights
TAIL_OUT = 0.02       # how far the tuft must stick out past the croup

_bands = {}
for _z0 in np.arange(TAIL_LOW, TAIL_UP, 0.05):
    _side = P[(np.abs(P[:, 0]) > 0.11) & (np.abs(P[:, 0]) < 0.26)
              & (P[:, 2] >= _z0) & (P[:, 2] < _z0 + 0.05)]
    if len(_side) > 4:
        _bands[round(_z0, 2)] = float(np.percentile(_side[:, 1], 90))


def croup_y(z):
    """How far the croup reaches at this height (at the sides, where there is no tail)."""
    key = round(np.floor(z / 0.05) * 0.05, 2)
    return _bands.get(key)


def part_of(i):
    if appendage[i]:                 # for a winged race they are picked above, by bones
        return appendage[i]
    p = P[i]
    if abs(p[0]) < TAIL_HALF and TAIL_LOW <= p[2] < TAIL_UP:
        edge = croup_y(p[2])
        if edge is not None and p[1] > edge + TAIL_OUT:
            return "tail"
    if is_head(p):
        # "Hairstyle" is the horns, the crest on the crown and the mane falling from the nape onto the
        # shoulders: the hair colour from the appearance screen works on it. The frill along the muzzle
        # must not be taken (it would be tinted along with the horns), so the boundary is in depth:
        # the mane is all behind the skull, the muzzle in front.
        if p[2] > SKULL_TOP or p[1] > HAIR_BACK:
            return "hair"
        return "head"
    b = dominant[i]
    # The hand is taken BY POSITION, not only by bone. The yak's hand is short and furry, the pony
    # weights land on the forearm, and by bones some thirty vertices went into the "gloves": wearing
    # bracers, the yak would be left without hands (the body mesh is replaced by the armour).
    if abs(p[0]) > HAND_FROM:
        return "gloves"
    if b in HAND_BONES:
        return "gloves"
    if b in LEG_BONES and p[2] < LEG_TOP:
        return "legs"
    return "body"


labels = [part_of(i) for i in range(len(P))]

# The yak's tail does not hang along the axis but is thrown to the side: the tuft reaches |x| up to 0.41,
# and the rule "near the axis and behind the croup" takes only the root, while the tuft goes to the legs;
# in game it hung as a separate tuft next to the boots (seen 24.09.2026). Widening the rule in X is
# risky: at croup height the buttocks would get into the tail. So fix it by connectivity: a real leg
# reaches the ground, everything in the legs mesh hanging higher is not a leg.
LEG_GROUND = 0.15       # if the lowest point of a piece is above this, it does not stand on the ground
_done = set()
for _i in range(len(P)):
    if labels[_i] != "legs" or _i in _done:
        continue
    _stack, _comp = [_i], []
    _done.add(_i)
    while _stack:
        _j = _stack.pop()
        _comp.append(_j)
        for _k in neighbours[_j]:
            if labels[_k] == "legs" and _k not in _done:
                _done.add(_k)
                _stack.append(_k)
    if min(P[_j][2] for _j in _comp) <= LEG_GROUND:
        continue
    _mid = float(np.median([P[_j][1] for _j in _comp]))
    _to = "tail" if _mid > BACK else "body"
    for _j in _comp:
        labels[_j] = _to
    log("  висящий кусок из ног ушёл в %s: %d вершин, глубина %.2f" % (_to, len(_comp), _mid))

counts = {}
for name in labels:
    counts[name] = counts.get(name, 0) + 1
log("части по вершинам:", counts)

# ---------------------------------------------------------------- 4. material and textures
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
            if not img.has_data:
                guess = os.path.join(os.path.dirname(SRC), os.path.basename(img.filepath_raw or img.name))
                if os.path.exists(guess):
                    img.filepath = guess
                    img.reload()
            fname = "eq_yak_" + img.name.replace(".", "_").lower() + ".png"
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
# The engine blinks with head vertex keys: there are exactly 101 of them (key_000..key_100), and frames
# 86, 87, 88 are the left eye, the right and both (the pony does the same, tools/convert_twilight.py).
# Without the keys the face is simply frozen, like the yak's.
#
# The pony's eyelids are their own geometry hidden above the eye. The dragon has none: the model is one
# piece, the eye is simply PAINTED on the texture. So it is closed by squashing: the vertices around the
# eye are pulled to its middle in height, and the painted eye collapses into a slit. The same trick
# pushes the pony's eyeball shut when the engine applies a frame at less than full strength.
#
# The eyes are found on the texture itself: two symmetric dark spots on the muzzle. The colour sample
# is taken slightly inside the face: the model's UV layout is patchy, and right at an island edge the
# atlas is already black.
FACE_KEYS = 101         # the vanilla head has this many vertex keys
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
EYE_DARK = 0.30         # darker than this is eye paint, not scales
EYE_CORE = 0.075        # within this radius from the eye middle squash fully: this is the eye itself
EYE_REACH = 0.115       # beyond, the squash fades to zero so as not to crumple the cheek and brow
EYE_SQUASH = 0.92       # how strongly the vertices are pulled to the eye middle
# The dark spot on the texture is the PUPIL, and it is right by the muzzle, while the white goes outward
# and back: only the half of the eye near the nose closed (seen in game 24.09.2026). The muzzle is narrow
# in front (at eye height |x| is only 0.07) and widens to 0.17 towards the cheekbones, so the offset must
# go both sideways and back, otherwise the middle leaves the surface.
EYE_OUT = 0.040         # outward, from the muzzle towards the cheekbone
EYE_BACK = 0.030        # and back, following the widening of the muzzle


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
        spots.append(P[blob].mean(0))
    # Find ONE eye and mirror it: searching each side separately is unreliable, a furry muzzle has many
    # dark spots (fur shadows, nostrils), and the eyes came out at different heights.
    front = float(np.percentile(P[:, 1], 45))
    upper = float(P[:, 2].min() + P[:, 2].max()) / 2
    mine = [s for s in spots if abs(s[0]) > 0.02 and s[1] < front and s[2] > upper]
    if not mine:
        return []
    best = max(mine, key=lambda s: -abs(s[1]))
    right = np.array([abs(best[0]), best[1], best[2]])
    log("  зрачок найден на (%.2f,%.2f,%.2f), вторая сторона отражена" % tuple(right))
    # from the pupil to the eye middle (see EYE_OUT)
    right = right + np.array([EYE_OUT, EYE_BACK, 0.0])
    log("  середина глаза (%.2f,%.2f,%.2f)" % tuple(right))
    return [right, np.array([-right[0], right[1], right[2]])]


def add_blink(ob):
    spots = eye_spots(ob)
    if len(spots) != 2:
        log("ВНИМАНИЕ: глаз на текстуре не видно (%d пятен) — моргания не будет" % len(spots))
        return
    log("глаза найдены: (%.2f,%.2f,%.2f) и (%.2f,%.2f,%.2f)" % (*spots[0], *spots[1]))
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])

    def shut(sides):
        move = np.zeros_like(P)
        for side in sides:
            eye = spots[side]
            gap = np.linalg.norm(P - eye, axis=1)
            close = gap < EYE_REACH
            fade = np.clip((EYE_REACH - gap[close]) / max(EYE_REACH - EYE_CORE, 1e-6), 0.0, 1.0)
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
        % (FACE_KEYS, "/".join(str(k) for k in sorted(BLINK_FRAMES)), EYE_SQUASH, EYE_REACH))


# ---------------------------------------------------------------- 5. parts as separate meshes
PLUG = 0.18        # how far the wing and tail root goes inside the body: slack for the animation
SMOOTH_ROUNDS = 18  # how many times the socket from the wing and tail is relaxed so the back is smooth
SMOOTH_GROW = 2     # how many rings around the patch the smoothing spreads
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
    ob = yak.copy()
    ob.data = yak.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    was_index = {v: i for i, v in enumerate(bm.verts)}   # indices before deletion: labels use them
    keep_set = set(keep)
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # Close the tear with polygons: otherwise through-holes gape at the joints of wings, tail and neck
    # (back faces are not drawn, and in game it is black there). Only cuts must be closed: the wing
    # and membrane have a free edge all around, and it must not be sealed, that would cover the
    # membrane with a solid sheet. A cut is recognised by a vertex of another part having been next to
    # it in the source mesh. UVs for the new faces are taken from neighbouring faces of the same vertex,
    # otherwise they pull colour from a corner of the texture.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] != name for o in neighbours[was_index[v]])}

    # Wings and tail sit on their own bone, while the body at their root is on its own (the back near
    # the wing follows the collarbone), so in motion the seam opens and the gap shows through. So for
    # the wing and tail the root is extended INTO the body: a skirt is led from the cut towards the
    # spine. It is not visible from outside, and it covers the gaps with margin.
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
            continue                     # the free edge of the membrane itself: leave it alone
        # whose boundary this was: with wing and tail the socket is smoothed later, while the seam with
        # the head, legs and hands must not be touched: it joins the neighbouring part and must stay
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] != name]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # On the mane itself the base stays an open tube. But in the head the spot under the mane is
        # sealed: without the mane (helmet, map) a hole gaped on the crown between the ears (seen in the
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
                # otherwise from outside (the game does not draw back faces) the patch will be a hole.
                centre = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
                for f in patch:
                    if f.normal.dot(f.calc_center_median() - centre) < 0:
                        f.normal_flip()
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # The socket from the wing and tail is ragged: a patch over such an edge comes out crumpled.
        # Relax it together with the edge itself: the back becomes even and smooth, and the wing still
        # sits on top and goes inside. Also take the ring around, otherwise the patch comes out as a
        # dent, but do not touch vertices on the free edge: those are seams with the head, legs and hands.
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
        # Where the head touches the mane closely, the surfaces flicker through each other: equal
        # depth. Head vertices closer than SEPARATE_NEAR to the mane are sunk into the model.
        from mathutils.bvhtree import BVHTree
        horn_faces = [f for f in yak.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]
        if horn_faces:
            tree = BVHTree.FromPolygons([tuple(v.co) for v in yak.data.vertices],
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
bpy.data.objects.remove(yak)

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
# The vanilla human IN PLACE of the dragon: it shows what sticks out of the armour and how far the
# arms and legs are pushed forward. The same file as for the depth placement.
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
    ob.location.x -= 2.0        # the pony alongside, to compare height
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
# each dragon part gets its own colour, so it is visible where the cut went
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
# The "height" frame is next to the pony for comparison, the others without her: otherwise she
# hides the dragon from the side and you cannot see what stayed on the back and where the cut went.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # wings and tail removed: shows whether pieces of them stayed on the body or they took something
        # from the back: the sockets of the wings and tail are there, that is what the frame is for
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair")),
        # head only, as the modkit shows it: shows whether mane strands stayed on the face
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        # over the vanilla human: red is what sticks out of the silhouette the armour is made for
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
    scene.render.filepath = os.path.join(prev, "yak_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
