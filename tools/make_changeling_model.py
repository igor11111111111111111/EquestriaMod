# -*- coding: utf-8 -*-
"""Changeling from a ready-made model (T-pose, its own Mixamo skeleton) onto the pony skeleton, in parts, to FBX.

Run (headless Blender, opens the finished pony, which holds the skeleton and the skinning reference):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_changeling_model.py \
      -- "<path to the changeling .fbx>" "<output folder>"

Copied from tools/make_griffon.py (which was copied from make_dragon.py); the shared parts are explained there.
How the changeling differs from the griffon:
  1. There are FOUR wings: two pairs of dragonfly wings, the upper at shoulder-blade level and the lower
     at the waist. We identify them not by size or height but by the fact that all four sit AWAY from the
     axis, while the tail is single and runs along the axis.
  2. Pony head with a horn and ears; the ears and horn are small chunks far from the bones, they do not
     pass the size threshold and stay with the head.

This script REPLACES the previous changeling, which was made from the pony mesh (tools/make_changeling.py):
the part names are the same, so the race XML does not need changes; a re-import in the editor is enough.

Output parts:
  eq_changeling_body   - torso and arms (body_meta_mesh)
  eq_changeling_legs   - legs (legs_mesh)
  eq_changeling_gloves - hands (hands_mesh)
  eq_changeling_head   - head with horn and ears (face_meta_mesh)
  eq_changeling_hair   - mane: crown and back of the head (a hairstyle, tinted with the hair colour)
  eq_changeling_wings  - both pairs of wings (an item)
  eq_changeling_tail   - tail (an item)
Next: import the FBX into the Modding Kit by hand, then tools/changeling_material.ps1.
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

RACE = "changeling"
HEIGHT = 1.88          # changeling height (pony 1.86, griffon 1.95, yak 2.05, dragon 2.10)
MAT = "eq_changeling_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[changeling]", *a, flush=True)


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
chl = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # generator junk: the placeholder sphere and other small meshes
    if ob.type == "MESH" and ob is not chl:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (chl.name, len(chl.data.vertices), source_skel.name if source_skel else "нет"))

own_bones = []
if source_skel:
    # Rest pose: the file contains a run animation, and the import puts the model in its first frame. The
    # mesh itself is stored in the bind pose (T), so removing the animation and the modifier is enough.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = chl
    for mod in list(chl.modifiers):
        if mod.type == "ARMATURE":
            chl.modifiers.remove(mod)
    chl.parent = None
    # Store the bones as segments in world coordinates BEFORE deleting the skeleton: the wings and tail
    # are picked below by their distance from them. Mixamo end bones ("_end") stick out sideways
    # past the mesh and only spoil the measurement.
    own_bones = {b.name: (np.array((source_skel.matrix_world @ b.head_local)[:]),
                          np.array((source_skel.matrix_world @ b.tail_local)[:]))
                 for b in source_skel.data.bones if not b.name.endswith("_end")}
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят (запомнено %d костей), модель в позе привязки" % len(own_bones))

bpy.ops.object.select_all(action="DESELECT")
chl.select_set(True)
bpy.context.view_layer.objects.active = chl
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# The generator outputs "soup": neighbouring triangles do not share vertices. Weld them, otherwise
# connected chunks cannot be found and gaps open along the seams during deformation.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(chl.data.vertices))


def coords():
    return np.array([(chl.matrix_world @ v.co)[:] for v in chl.data.vertices])


# ------------------------------------------------- wings and tail: connected chunks far from the bones
# Same trick as for the dragon: the feather and tail stick out far from any bone, while the skin of the
# torso, arms and legs is always close to its own. Take everything farther than FAR_FRAC from the bones
# and cut it into connected chunks.
#
# But the chunks are identified differently. The changeling has six at FAR_FRAC=0.114 (measured on the model):
#   169 and 154 vertices, |x| 0.19..0.60, z 1.22..1.75 - upper pair of wings;
#   120 and 120 vertices, |x| 0.13..0.49, z 0.83..1.16 - lower pair;
#   214 vertices, x near zero, z 0.15..0.82             - tail;
#   32 and 14 vertices on the crown                     - ears, they do not pass the size threshold.
# Telling them apart by height is impossible (the lower wings and the tail are at the same level), and by
# size too (the tail is larger than any wing). But all the wings sit AWAY from the axis, and the tail runs
# along the axis.
FAR_FRAC = 0.114
PART_MIN = 0.02       # a chunk smaller than this fraction of the vertices is ears or horn: leave it alone
WING_SIDE = 0.09      # a chunk whose middle is farther than this fraction of height from the axis is a wing
TAIL_HIGH = 0.55      # look for the tail below this fraction of height
TAIL_AXIS = 0.09      # and no farther than this fraction of height from the body axis
# The feather right by the shoulder lies over the arm and is not picked by distance. But the original
# skinning shows who is who: the arm never goes farther than ARM_FAR from its bone, the feather goes much farther.
ARM_FAR = 0.08


def bone_gap(name, pts):
    a, b = own_bones[name]
    ab = b - a
    t = np.clip(((pts - a) @ ab) / (float(ab @ ab) or 1e-9), 0, 1)[:, None]
    return np.linalg.norm(pts - (a + t * ab), axis=1)


appendage = [None] * len(chl.data.vertices)
if own_bones:
    P = coords()
    height = float(P[:, 2].max() - P[:, 2].min())
    near = np.full(len(P), 1e9)
    for name in own_bones:
        near = np.minimum(near, bone_gap(name, P))
    far = near > FAR_FRAC * height

    groups = {g.index: g.name for g in chl.vertex_groups}
    dominant = np.array([groups[max(v.groups, key=lambda g: g.weight).group] if v.groups else "?"
                         for v in chl.data.vertices])
    added = np.zeros(len(P), bool)
    for name in own_bones:
        if "Arm" not in name:          # arm bones only: the wings hang from them
            continue
        sel = dominant == name
        if sel.any():
            added[sel] |= bone_gap(name, P[sel]) > ARM_FAR * height
    added &= ~far
    far |= added
    # Where the model's hand is, by its ORIGINAL bone: further down, these vertices are used to align the
    # arm with the skeleton's arm. Measuring by the claw tips is impossible, they are long.
    own_hand = {i for i, d in enumerate(dominant) if "Hand" in d}
    if added.any():
        pts = P[added]
        log("по костям рук добавлено %d вершин: x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f (рост %.2f)"
            % (int(added.sum()), pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(),
               pts[:, 2].min(), pts[:, 2].max(), height))

    neighbours = [[] for _ in range(len(P))]
    for e in chl.data.edges:
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
        if mid[1] < middle_y:          # everything of ours is behind the back; nothing should be in front
            log("ВНИМАНИЕ: крупный кусок вдали от костей не опознан, центр (%.2f,%.2f,%.2f)" % tuple(mid))
            continue
        if abs(mid[0]) > WING_SIDE * height:
            name = "wings"          # both pairs: the one at the shoulder blades and the one at the waist
        elif mid[2] - floor < TAIL_HIGH * height and abs(mid[0]) < TAIL_AXIS * height:
            name = "tail"
        else:
            log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) оставлен телу"
                % (len(chunk), *mid, top))
            continue
        log("кусок %d вершин (центр %.2f,%.2f,%.2f, верх %.2f) -> %s"
            % (len(chunk), *mid, top, name))
        for i in chunk:
            appendage[i] = name
    # The clawed leading edge of the wing lies right against the finger bones (in the T-pose the hand and
    # the wing claw end up at the same point), so it is not picked by distance and stayed on the body as
    # shards sticking out. But it is attached ONLY to the membrane: once the wings are removed, it hangs
    # as a separate island. So we look at what the rest falls apart into: the big chunk is the dragon
    # itself, everything else near a wing or the tail is given back to it.
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
    ISLAND_NEAR = 0.05        # an island farther than this fraction of height from wing and tail is not theirs
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

# The muzzle must face -Y (as on the pony). The muzzle is the point of the upper third that sticks out most in Y.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    chl.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

scale = HEIGHT / (hi[2] - lo[2])
chl.scale = (scale, scale, scale)
chl.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- depth: place by the TORSO, not by the bounding box
# Placing by the bounding box is wrong: the dragon's tail pulls the box back, and the torso drifts forward
# off the spine. Then the spine bone runs right at the back, the chest wobbles on any turn of the body,
# and the arms and legs hang in front of the armour.
# The depth reference is the VANILLA HUMAN, not the pony: the armour is made for him, and he sets its fit.
# The human body is exported from the game assets:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<game>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Vanilla models face +Y (ours face -Y), so the reference is rotated.
TORSO_Z = (1.00, 1.35)    # between the bip01_spine_9 and bip01_spine2_11 bones
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
# Move the mesh itself, not the object: "baking" the offset (transform_apply) only works on the
# selected object, and importing the reference steals the selection; then the object moves away, and all
# later edits are written in local coordinates and miss by exactly this offset.
for v in chl.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Where the neck ends and the head begins. The line slopes forward and down (under the muzzle), and it
# must be measured FROM THE MODEL ITSELF: placing by the torso shifted the dragon in depth, so the same
# offset is added to the world mark. It is needed already here: the head must not be touched together
# with the arms, its sides fall into the same X zone, and the arm edit tore the muzzle to shreds.
NECK_Z = bones["bip01_neck_12"].z + 0.06
JAW_SLOPE, JAW_FROM = 0.45, -0.10 + shift


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ---------------------------------------------- arms from the T-pose onto the pony arm (rotation + length)
# Just rotating by 22 degrees is not enough: the dragon's arm is 10% longer than the pony's, so the elbow
# landed on the forearm bone and the hand missed the hand bone, and in game the arms looked crooked.
# Align the dragon's "shoulder - hand" segment with the same skeleton segment: rotation around the shoulder
# plus scaling along the length. Right at the joint the transform ramps in smoothly (ramp), otherwise it tears.
SHOULDER_X = 0.16               # shoulder joint in X (the model's shoulder bone after placement)
ARM_RAMP = 0.10                 # over how many metres the transform ramps in
ARM_TIP = 0.9                   # fraction of the span beyond which it is the hand
HEAD_RAMP = 0.12                # how many metres below the jaw the arm takes full effect

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
arm_y = float(np.median([P[i][1] for i in range(len(P)) if arm_far[i] and appendage[i] is None]))
ARM_BACK = arm_y + 0.12         # farther back is a wing, not the arm
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > SHOULDER_X - ARM_RAMP and p[1] < ARM_BACK and p[2] > 1.0
            and appendage[i] is None and not is_head(P[i])]
tip = max(abs(P[i][0]) for i in arm_zone)
# The hand is taken by the model's ORIGINAL bone, not by the claw tips: the dragon's claws are long, and
# with them the arm drifted far out from the body (the hand landed at |x| 0.83 instead of 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# The shoulder joint is on the axis of the arm itself, extended to SHOULDER_X. It cannot be found from a
# torso slice at that mark: the flank is still there, and the slice middle wanders by ten centimetres in
# height. The axis is computed from the middles of cross-section bands of the arm (from 0.30 to the tips),
# so that the hand and elbow do not dominate, and a straight line is fitted through them.
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
# Aim the WRIST at the hand bone. Not by the pony's fingertips: her arm is longer than a human's
# (the fingers reach |x| 0.83, while the vanilla body's arm ends at 0.60), and the dragon got
# splayed arms. Let the claws stick out past the bone, like a human's fingers.
H_p = bones["bip01_l_hand_19"]
# Exactly to the bone the arm comes out a bit short: the hand hides in the sleeve. Let it go further along
# the same axis and turn it down a little, so it is both longer and pressed to the body, not splayed out.
# The numbers are tuned from in-game feedback, as for the dragon.
ARM_REACH = 1.00    # how many times farther than the hand bone the wrist goes
ARM_DROP = 0.0      # by how many degrees the arm is additionally lowered towards the body
ARM_THICK = 1.00    # how many times thicker across the axis (the alignment itself thins the arm)
HAND_SMALL = 1.00   # how many times the hand itself is shrunk

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
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # the transform fades out towards the head
    mine = Vector((abs(p[0]), p[1], p[2]))
    # along the axis the arm is stretched/squeezed by the alignment, across it separately, otherwise
    # it gets thinner along with the shortening
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * ARM_THICK
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = chl.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука дракона %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ---------------------------------------------------------------- smaller hand
# The model's paw is large, with long claws, and next to a human sleeve it looks like a shovel.
# Shrink it AROUND THE WRIST (the pony hand bone), not around the middle of the paw: otherwise a gap
# opens at the joint with the forearm. ARM_DROP above brings the hand closer to the body; it also lays
# the whole arm along the torso instead of out to the sides.
if HAND_SMALL != 1.0:
    P = coords()
    shrunk = 0
    for i in (set(arm_zone) & own_hand):
        p = P[i]
        sign = 1.0 if p[0] > 0 else -1.0
        wrist = Vector((H_p.x * sign, H_p.y, H_p.z))
        chl.data.vertices[i].co = wrist + (Vector((p[0], p[1], p[2])) - wrist) * HAND_SMALL
        shrunk += 1
    P = coords()
    hands = P[[i for i in hand_idx]]
    log("кисть ужата в %.2f раза (%d вершин), центр лапы теперь (%.2f,%.2f,%.2f)"
        % (HAND_SMALL, shrunk, abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean()))

# ---------------------------------------------------------------- arms forward, legs back
# Depth shifts: arms forward, legs back. The griffon needed them; for the changeling they are
# off for now; enable them based on how it looks in game.
# The muzzle faces -Y, so forward is minus and towards the tail is plus.
#
# Both shifts fade out smoothly: the arm lets go at the shoulder (the same ramp as the rotation),
# the leg at the pelvis. Otherwise the joint tears.
ARM_FORWARD = 0.0       # how many metres the arms move forward, away from the tail
ARM_OUT = 0.0           # and how many out to the sides, away from the torso
LEG_BACK = 0.0          # how many metres the legs move back, towards the tail
LEG_FULL = 0.55         # below this height the leg moves as a whole
LEG_FADE = 0.95         # above this it is already the pelvis, leave it alone

P = coords()
for i in arm_zone:
    p = P[i]
    t = min(1.0, max(0.0, (abs(p[0]) - (SHOULDER_X - ARM_RAMP)) / ARM_RAMP))
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)
    chl.data.vertices[i].co.y -= ARM_FORWARD * t
    chl.data.vertices[i].co.x += math.copysign(ARM_OUT * t, p[0])

# ---------------------------------------------------------------- shoulders forward and down
# The model's shoulders are pulled back and raised, so the figure looks hunched ("the shoulders are pulled
# far back and up", 24.09.2026). Move the WHOLE shoulder girdle together with the arm: if only the
# shoulder cap is dragged, the arm lags behind and a step forms at the joint.
# Weight: grows across the width from the torso edge to the shoulder, fades in height towards the armpit,
# so that the flank stays in place.
SHOULDER_FORWARD = 0.045    # how many metres the shoulder moves forward
SHOULDER_DOWN = 0.030       # and down
SHOULDER_FROM_X = 0.06      # closer than this to the axis is already chest and neck, leave them alone
SHOULDER_FULL_X = 0.17      # beyond this the weight is full
SHOULDER_LOW = 1.02         # below this height there is no shift
SHOULDER_FULL_Z = 1.22      # above this it is full

P = coords()
moved_shoulders = 0
for i, p in enumerate(P):
    if appendage[i] is not None or is_head(p) or abs(p[0]) < SHOULDER_FROM_X or p[2] < SHOULDER_LOW:
        continue
    wx = min(1.0, (abs(p[0]) - SHOULDER_FROM_X) / max(SHOULDER_FULL_X - SHOULDER_FROM_X, 1e-6))
    wz = min(1.0, (p[2] - SHOULDER_LOW) / max(SHOULDER_FULL_Z - SHOULDER_LOW, 1e-6))
    w = (wx * wx * (3 - 2 * wx)) * (wz * wz * (3 - 2 * wz))
    if w <= 0:
        continue
    v = chl.data.vertices[i]
    v.co.y -= SHOULDER_FORWARD * w
    v.co.z -= SHOULDER_DOWN * w
    moved_shoulders += 1
log("плечевой пояс сдвинут вперёд на %.3f и вниз на %.3f м (%d вершин)"
    % (SHOULDER_FORWARD, SHOULDER_DOWN, moved_shoulders))

P = coords()
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
        chl.data.vertices[i].co.y += LEG_BACK * w
        moved_legs += 1
log("руки сдвинуты вперёд на %.2f м и в стороны на %.2f м (%d вершин), ноги назад на %.2f м (%d вершин)"
    % (ARM_FORWARD, ARM_OUT, len(arm_zone), LEG_BACK, moved_legs))

# ------------------------------------------------------------------- wider rib cage
# The model has a narrow chest; next to the wide pelvis it looks like a tube. Widen it in X, but not with
# a single scale: otherwise the arms move away with the chest and the hands leave their bones. Inside the
# torso the width grows proportionally, outside the shift fades out towards the wrist, and in height it
# fades smoothly beyond the ribs. The wings and tail move along with everything, so their roots stay put.
# First pass: the chest is left alone (1.0). The numbers are tuned from in-game feedback, as for the griffon.
CHEST_WIDE = 1.35
# Its own band: the changeling is 1.88 tall, its collarbones are at 1.34, the pelvis at 1.00.
CHEST_BAND = (1.00, 1.34)   # ribs and belly: from the pelvis to the collarbones
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
    chl.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- smaller upper chest
# The ribs should be widened, not the bust: at the top the chest stuck out both forward and sideways.
# Shrink the upper chest in width and depth around its own middle, so the bottom (ribs) stays wide and
# the top tightens. It fades out towards the shoulders, otherwise the arms come off them.
UPPER_SMALL = 1.00          # how many times the upper chest is shrunk (1.0 - left alone)
UPPER_BAND = (1.34, 1.58)   # from the bust to the collarbones
UPPER_FADE = 0.10           # over how many metres in height it ramps in and out
UPPER_HALF = 0.26           # beyond this in X it is already the shoulder, no shrinking there
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
    v = chl.data.vertices[i]
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

for g in list(chl.vertex_groups):     # the foreign Mixamo groups are no longer needed
    chl.vertex_groups.remove(g)
for g in ref.vertex_groups:
    chl.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
chl.select_set(True)
bpy.context.view_layer.objects.active = chl
dt = chl.modifiers.new("веса", "DATA_TRANSFER")
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

# Hand bones go to the hands only: the pony's hands hang at belly height, and the dragon's flanks
# end up closer to them than to her body (the same trouble the yak had).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = chl.data.vertices[i]
    for g in list(v.groups):
        if chl.vertex_groups[g.group].name in HAND_BONES:
            chl.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        chl.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# The head is rigidly on the head bone, otherwise the neck and chest bones drive the muzzle and it tears
# at the seam. The boundary (jaw_z/is_head) is set above, before the arm edit.
BLEND = 0.15

head_group = chl.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(chl.data.vertices[i].groups):
        chl.vertex_groups[g.group].remove([i])
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
        # chest: it sticks out forward and up, and the nearest pony point is her chin. In game
        # such a chest folded on every head turn.
        if head_group.index in [g.group for g in chl.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not chl.data.vertices[i].groups:
                chl.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in chl.data.vertices[i].groups:
        chl.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. cutting into parts
group_names = {g.index: g.name for g in chl.vertex_groups}
dominant = []
for v in chl.data.vertices:
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
# Crown: below this fraction of the head height it is already the face
HAIR_PART = False     # whether to cut the crown into the hairstyle (see part_of: the changeling has ears and horn there)
SKULL_PART = 70
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Mane boundary in depth: fraction of the way from the eyes to the back of the head. Everything beyond it is
# mane and back of the head, closer is the muzzle with the frill (it must not go into the hair, it would be
# tinted with the hair colour).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # front of the muzzle
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
# Where the cut between body and legs runs: as on the pony, 0.44 of the height. Raise it as on the griffon.
LEG_TOP = 0.44 * HEIGHT / 1.86
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# DO NOT PICK UP THE FORELOCK. I tried catching strands left on the face by the fact that a strand is a thin
# sheet (a back side with an opposite normal nearby, KD-tree): along with them the scales above the brow and
# pieces of the cheek went into the hairstyle, and the head shrank from 322 vertices to 150. The user:
# "make it as it was before, the hair turned out really bad". Two marks remain: the crown and the back
# of the head.


def part_of(i):
    if appendage[i]:                 # wings and tail were picked above, by distance from the bones
        return appendage[i]
    p = P[i]
    if is_head(p):
        # For the dragon and griffon the crown goes into the "hairstyle": there it is a crest and feathers,
        # and the hair colour from the appearance screen tints them. THE CHANGELING CANNOT DO THAT: it has
        # ears and a horn on the crown, and the hairstyle tag gives drones "Bald", so the ears would vanish
        # with the hairstyle. So the head stays whole, and the race has its own manes as separate meshes
        # (tools/make_changeling_hair.py, Chrysalis manes).
        if HAIR_PART and (p[2] > SKULL_TOP or p[1] > HAIR_BACK):
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
src_mat = chl.data.materials[0] if chl.data.materials else None
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
            fname = "eq_changeling_" + img.name.replace(".", "_").lower() + ".png"
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
# The engine blinks with the head's vertex keys: there are exactly 101 of them (key_000..key_100), and frames
# 86, 87, 88 are the left eye, the right eye and both (done the same way for the pony, tools/convert_twilight.py).
# Without the keys the face is simply frozen, like the yak's.
#
# The pony's eyelids are separate geometry hidden above the eye. The dragon has none: the model is one piece,
# the eye is just PAINTED on the texture. So we close it by squashing: the vertices around the eye are pulled
# to its middle in height, and the painted eye collapses into a slit. The same trick is used on the pony to
# finish closing the eyeball when the engine applies the frame at less than full strength.
#
# The eyes are found from the texture itself: they are two symmetric dark spots on the muzzle. The colour
# sample is taken slightly inside the face: the model's UV layout is patchy, and at the very edge of an island
# there is already the atlas black.
FACE_KEYS = 101         # the number of vertex keys on the vanilla head
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
# The griffon threshold is MUCH stricter than the dragon's 0.30: the eagle's brown brow feathers are darker
# than 0.3, and with such a threshold the brow came out as the largest dark spot, so the blink fired above the
# eye (noticed in game 24.09.2026). The black pupil is clearly darker than any feather, so we mark by it.
EYE_DARK = 0.16
# The squash zone is the semi-axes of a "lobe" around the eye middle: sideways, in depth, in height. The
# griffon's eye is almond-shaped and lies at a slant, so the zone is long along it and short in height,
# otherwise the brow and cheek collapse together with the eye and the muzzle folds like an accordion.
EYE_ZONE = (0.105, 0.095, 0.085)
EYE_FULL = 0.80         # inside this fraction of the zone squash fully, beyond it fade out smoothly
EYE_SQUASH = 0.92       # how much the vertices are pulled to the eye middle
EYE_SIDE = 0.02         # closer than this to the axis is the beak, not an eye
# The mark lands on the PUPIL, and on the griffon it is right by the beak, while the eye itself with the white
# goes outward and slightly back, so only the half by the nose closed (noticed in game 24.09.2026).
# So we step from the found pupil towards the eye middle.
EYE_OUT = 0.020         # outward from the pupil (on the changeling the pupil is almost in the eye middle)
EYE_BACK = 0.015        # and slightly back: the eye is large and almost round, not almond-shaped
EYE_DOWN = 0.020        # and lower: the mark lands on the pupil, which is above the middle of the large eye


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
    # One spot per side: in the front part of the head (the beak in the centre falls on no side, the shadows
    # of the back of the head are behind) and the DARKEST, not the largest. The largest is the brown brow:
    # it has more feathers than the pupil has polygons, and by size it won.
    front = float(np.percentile(P[:, 1], 45))
    out = []
    for side in (1, -1):
        mine = [(c, n, s) for c, n, s in spots if c[0] * side > EYE_SIDE and c[1] < front]
        out.append(min(mine, key=lambda s: s[2])[0] if mine else None)
    # The head is low-poly and asymmetric: the pupil gets one or two vertices, and on one side there may be
    # no dark sample at all. Then mirror the found eye; that is more reliable than loosening the threshold
    # down to the brown brow feathers.
    if out[0] is None and out[1] is not None:
        out[0] = np.array([-out[1][0], out[1][1], out[1][2]])
        log("  левый глаз отражён с правого")
    elif out[1] is None and out[0] is not None:
        out[1] = np.array([-out[0][0], out[0][1], out[0][2]])
        log("  правый глаз отражён с левого")
    # from the pupil towards the eye middle (see EYE_OUT)
    for spot in out:
        if spot is not None:
            spot[0] += math.copysign(EYE_OUT, spot[0])
            spot[1] += EYE_BACK
            spot[2] -= EYE_DOWN
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
            # The zone is not a sphere but a "lobe" shaped like the eye: wide sideways and in depth, low
            # in height. A sphere did not work: to close the outer corner the radius had to be so large
            # that the brow and cheek got crumpled too, and the muzzle folded like an accordion.
            step = (P - eye) / radius
            # Height is handled separately from "along the eye": the zone comes out a flat cake, not a ball.
            # If all three axes are counted together, the outer eye corner (far sideways AND slightly above
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
PLUG = 0.18        # how far the wing and tail root goes into the body: slack for animation
SMOOTH_ROUNDS = 18  # how many times the wing and tail socket is relaxed so the back becomes smooth
SMOOTH_GROW = 2     # how many rings around the patch the smoothing spreads to
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "wings", "tail"):
    keep = [i for i, l in enumerate(labels) if l == name]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = chl.copy()
    ob.data = chl.data.copy()
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
    # Close the tear-off spot with polygons: otherwise see-through holes gape at the joints of the wings,
    # tail and neck (faces are not drawn from the inside, and in game it is black there). Close ONLY the
    # cuts: the wing and membrane edge is free all around, and it must not be filled, that would cover
    # the membrane with a solid sheet. A cut is recognised by a vertex of another part being next to it
    # in the original mesh. UVs for the new faces are taken from neighbouring faces of the same vertex,
    # otherwise they pull colour from the corner of the texture.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] != name for o in neighbours[was_index[v]])}

    # The wings and tail sit on their own bone, and the body at their root on its own bones (the back by
    # the wing follows the clavicle), so in motion the seam opens and you can see through the gap. So the
    # wing and tail root is extended INTO the body: a skirt is led from the cut towards the spine. It is
    # not visible from outside, and it covers the gaps with margin.
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
            cut.update(fresh)        # close the far edge of the skirt too, so the pocket is sealed
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
        # whose boundary this was: the socket with a wing or tail is smoothed later, but the seam with the
        # head, legs and hands must not be touched: it joins the neighbouring part and must stay
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] != name]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # Hairstyle seams are not filled at all, neither with the head nor with the body: the hairstyle is
        # never removed from the character and covers them, so there are no holes to the outside. Two caps in
        # the same place flicker through each other in game, and the ragged hairstyle cap also lies across the face.
        if "hair" in (name, owner):
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
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # The wing and tail socket is ragged: a patch along such an edge comes out crumpled. Relax it
        # together with the edge itself: the back becomes even and smooth, and the wing still sits on top
        # and goes inside. Also take a ring around it, otherwise the patch comes out as a dent,
        # but do not touch vertices on the free edge: those are the seams with the head, legs and hands.
        for _ in range(SMOOTH_GROW):
            smooth.update(o for v in list(smooth) for e in v.link_edges for o in e.verts
                          if not any(len(x.link_faces) == 1 for x in o.link_edges))
        for _ in range(SMOOTH_ROUNDS):
            bmesh.ops.smooth_vert(bm, verts=list(smooth), factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        log("  %s: спина заглажена, %d вершин" % (name, len(smooth)))
    if patched:
        log("  %s: заделано %d граней на месте отрыва" % (name, patched))
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
bpy.data.objects.remove(chl)

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
# The vanilla human IN PLACE of the dragon: it shows what pokes out of the armour and how far
# the arms and legs are pushed forward. The same file as for the depth placement.
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
    ob.location.x -= 2.0        # pony alongside, to compare heights
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
# each part of the dragon gets its own colour, so you can see where the cut went
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
# The height frame (the "height" view) is next to the pony for comparison, the others are without her: otherwise
# she blocks the dragon from the side and you cannot see what is left on the back and where the cut went.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # wings and tail removed: shows whether pieces of them are left on the body and whether they took
        # anything from the back: the wing and tail sockets are there, that is what the frame is for
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair")),
        # the head alone, as the mod kit shows it: shows whether mane strands are left on the face
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "wings", "tail")),
        # over the vanilla human: red shows what pokes out of the silhouette the armour is made for
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
    scene.render.filepath = os.path.join(prev, "changeling_%s.png" % view)
    bpy.ops.render.render(write_still=True)
log("превью в", prev)
