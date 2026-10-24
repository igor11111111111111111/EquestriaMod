# -*- coding: utf-8 -*-
"""New pony (Meshy, alicorn: horn, wings, tail; T-pose, own Mixamo skeleton) — onto the donor
pony's skeleton, in parts, to FBX.

Run (headless Blender, opens the old pony — it holds the skeleton and the skinning sample):
  blender --background assets/twilight_anthro/export/eq_twilight.blend --python tools/make_pony_model.py       -- "<path to the new pony .fbx>" "<output folder>"

Copied from tools/make_deer_model.py (which is from make_yak_model.py and make_dragon.py; the
common parts are explained there). How the new pony differs:
  1. The source is an .fbx with a Mixamo skeleton and a run animation, and the textures are separate
     PNGs next to it (color, normals, roughness and metalness — four files, not a .glb with packed ones).
  2. Wings and tail can NOT be split off "far from the bones" as with the model: the pony is a single
     mesh (5 thousand vertices, not one separate piece), and the Mixamo skeleton runs along the body
     axis, so both the head with the muzzle and the wing end up far from it. The model's auto-skinning
     is bad: the tail and the right wing are weighted to the right thigh bone. So we find them by
     POSITION — the wings hang behind the arms at the sides, the tail behind the rump and legs.
  3. The mane is fused into the head and is cut by position: the back and top of the head are the
     hairstyle (tinted with the hair color), the face with the forelock near the eyes is the head.
     The horn is a separate body part: src/EquestriaBodyParts.cs hangs it on the skeleton, like the
     tail and wings.

Output parts:
  eq_pony_body   — torso and arms (body_meta_mesh)
  eq_pony_legs   — legs (legs_mesh)
  eq_pony_gloves — hands (hands_mesh)
  eq_pony_head   — head with muzzle, ears and mane (face_meta_mesh)
  eq_pony_hair   — mane (hairstyle, tinted with the hair color)
  eq_pony_horn   — horn (body part on the head, like the tail and wings)
  eq_pony_wings  — wings (item in the cape slot)
  eq_pony_tail   — tail (item)
Next — import the FBX into the Modding Kit by hand, then tools/pony_material.ps1.
"""
import math
import os
import shutil
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = os.path.abspath(args[0]), os.path.abspath(args[1])
os.makedirs(OUT, exist_ok=True)

RACE = "pony"
HEIGHT = 1.86          # pony height: level with the vanilla human
MAT = "eq_pony_body"

HEAD_BONES = ("bip01_head_13", "bip01_neck_12")
HAND_BONES = ("bip01_l_hand_19", "bip01_l_finger0_20", "bip01_r_hand_26", "bip01_r_finger0_27")
LEG_BONES = ("bip01_l_thigh_1", "bip01_l_calf_2", "bip01_l_foot_3", "bip01_l_toe0_4",
             "bip01_r_thigh_5", "bip01_r_calf_6", "bip01_r_foot_7", "bip01_r_toe0_8")
PELVIS = "bip01_pelvis_0"
ARM_BONES = ("mixamorig:LeftArm", "mixamorig:RightArm")


def log(*a):
    print("[pony]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
for ob in pony.values():
    if ob.data.shape_keys:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0
bones = {b.name: (skel.matrix_world @ b.head_local) for b in skel.data.bones}

# ---------------------------------------------------------------- 1. import and A-pose
before = set(bpy.data.objects)
if SRC.lower().endswith((".glb", ".gltf")):
    bpy.ops.import_scene.gltf(filepath=SRC)
else:
    bpy.ops.import_scene.fbx(filepath=SRC)
added = [o for o in bpy.data.objects if o not in before]
mdl = max((o for o in added if o.type == "MESH"), key=lambda o: len(o.data.vertices))
source_skel = next((o for o in added if o.type == "ARMATURE"), None)
for ob in added:            # generator junk: the placeholder ball and other small meshes
    if ob.type == "MESH" and ob is not mdl:
        bpy.data.objects.remove(ob, do_unlink=True)
log("импортирован %s: %d вершин, свой скелет: %s"
    % (mdl.name, len(mdl.data.vertices), source_skel.name if source_skel else "нет"))

if source_skel:
    # Rest pose: the file contains a run animation, and the import puts the model into its first
    # frame. The mesh itself is stored in the bind pose (T), so removing the animation and the
    # modifier is enough.
    source_skel.animation_data_clear()
    source_skel.data.pose_position = "REST"
    bpy.context.view_layer.objects.active = mdl
    for mod in list(mdl.modifiers):
        if mod.type == "ARMATURE":
            mdl.modifiers.remove(mod)
    mdl.parent = None
    bpy.data.objects.remove(source_skel, do_unlink=True)
    log("чужой скелет снят, модель в позе привязки")

bpy.ops.object.select_all(action="DESELECT")
mdl.select_set(True)
bpy.context.view_layer.objects.active = mdl
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# The generator outputs "soup": neighbouring triangles do not share vertices. We weld them —
# otherwise connected pieces cannot be found and gaps open along the seams when deforming.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
log("сшито: %d вершин" % len(mdl.data.vertices))


def coords():
    return np.array([(mdl.matrix_world @ v.co)[:] for v in mdl.data.vertices])


# ---------------------------------------------- wings and tail: selection by position in the source
# The Mixamo skeleton runs along the body axis, and Meshy's weights are bad (the tail and the right
# wing are weighted to the thigh), so neither "far from the bones" nor the weights help here. But the
# shape is clear: the small folded wings hang BEHIND the arms (in the T-pose her arms stretch strictly
# sideways and go forward of the wings), and the tail is behind the croup and legs. Thresholds are in
# source metres (muzzle faces -Y, height 1.92 with the horn); selection happens BEFORE fitting, and
# vertex indices do not change afterwards.
WING_X = 0.19           # closer to the axis is already the side of the torso: the wing root is cut there
WING_Y = 0.05           # the wings lie behind the back, the arms at y <= 0
WING_Z_TOP = 1.28
WING_Z_LOW = (0.90, 0.16, 1.20)   # lower edge: z = 0.90 at the root, dropping 1.2 m per metre sideways
WING_Z_FLOOR = 0.52
TAIL_X = 0.22           # wider than this from the axis is already the thighs and wings
TAIL_Y_LOW, TAIL_Y_HIGH = 0.10, 0.13   # beyond this depth (low / at the croup) is the tail
TAIL_Z_TOP = 1.02
PART_MIN = 0.03       # a piece smaller than this share of vertices is not a wing: goes back to the body
ISLAND_NEAR = 0.05    # an island farther than this share of height from the wing and tail is not theirs

# Neighbours of every vertex: used below to find connected pieces and to patch cuts.
neighbours = [[] for _ in range(len(mdl.data.vertices))]
for e in mdl.data.edges:
    neighbours[e.vertices[0]].append(e.vertices[1])
    neighbours[e.vertices[1]].append(e.vertices[0])


def components(member):
    """Connected pieces of the vertices for which member[i] is true, largest first."""
    seen = np.zeros(len(member), bool)
    out = []
    for start in range(len(member)):
        if not member[start] or seen[start]:
            continue
        stack, chunk = [start], []
        seen[start] = True
        while stack:
            cur = stack.pop()
            chunk.append(cur)
            for other in neighbours[cur]:
                if member[other] and not seen[other]:
                    seen[other] = True
                    stack.append(other)
        out.append(chunk)
    return sorted(out, key=len, reverse=True)


P = coords()
height = float(P[:, 2].max() - P[:, 2].min())
ax, ay, az = np.abs(P[:, 0]), P[:, 1], P[:, 2]
wing_low = np.maximum(WING_Z_FLOOR, WING_Z_LOW[0] - (ax - WING_Z_LOW[1]) * WING_Z_LOW[2])
wing_like = (ax >= WING_X) & (ay >= WING_Y) & (az <= WING_Z_TOP) & (az >= wing_low)
tail_like = (ax < TAIL_X) & (az < TAIL_Z_TOP) & (ay >= np.where(az < 0.80, TAIL_Y_LOW, TAIL_Y_HIGH)) & ~wing_like

appendage = [None] * len(P)
own_hand = set()      # the model has no own hand weights: the hand is found by span
for chunk in components(wing_like):
    if len(chunk) < PART_MIN * len(P):
        break
    for i in chunk:
        appendage[i] = "wings"
tail_chunks = components(tail_like)
if tail_chunks:
    for i in tail_chunks[0]:
        appendage[i] = "tail"

# Everything the selection left as small islands (feathers on the edge, the tail tip, a mane braid
# at the very root) goes back to the nearer of wing and tail if it is close; the rest to the body.
rest = components(np.array([a is None for a in appendage]))
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
log("крылья и хвост по положению: крылья %d вершин, хвост %d" % (found["wings"], found["tail"]))
if not found["wings"] or not found["tail"]:
    log("ВНИМАНИЕ: крылья или хвост не найдены — проверьте пороги WING_* и TAIL_*")


P = coords()
lo, hi = P.min(0), P.max(0)
log("исходник: размер %.2f x %.2f x %.2f" % (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))

# The muzzle must face -Y (as on the pony). The muzzle is the most protruding Y point of the top third.
top = P[P[:, 2] > lo[2] + 0.6 * (hi[2] - lo[2])]
middle_y = (lo[1] + hi[1]) / 2
nose_y = top[np.argmax(np.abs(top[:, 1] - middle_y)), 1]
if nose_y > middle_y:
    mdl.rotation_euler[2] += math.pi
    bpy.ops.object.transform_apply(rotation=True)
    P = coords()
    lo, hi = P.min(0), P.max(0)
    log("модель развёрнута мордой в -Y")

# Height is measured to the CROWN, not to the horn tips. The pony's horn reaches several centimetres
# above the crown, and with the bounding box the whole model sat a quarter lower: the face went below
# the jaw line and was given to the body, and the head bone only got the horns. The crown is found by
# slice thickness — the skull with ears is deep, the horns are thin branches.
def crown_z(pts):
    low, high = float(pts[:, 2].min()), float(pts[:, 2].max())
    tall = high - low
    step = 0.02 * tall
    bands = []
    for z0 in np.arange(low + 0.6 * tall, high, step):
        band = pts[(pts[:, 2] >= z0) & (pts[:, 2] < z0 + step)]
        if len(band) > 8:
            bands.append((float(z0), float(band[:, 1].max() - band[:, 1].min())))
    if not bands:
        return high
    thick = max(d for _, d in bands)
    return max(z0 for z0, d in bands if d > 0.5 * thick) + step


CROWN = crown_z(P)
log("макушка на %.3f из %.3f — рога выше неё в рост не идут" % (CROWN - lo[2], hi[2] - lo[2]))
scale = HEIGHT / (CROWN - lo[2])
mdl.scale = (scale, scale, scale)
mdl.location = Vector((-(lo[0] + hi[0]) / 2 * scale, -(lo[1] + hi[1]) / 2 * scale, -lo[2] * scale))
bpy.ops.object.transform_apply(location=True, scale=True)
P = coords()
lo, hi = P.min(0), P.max(0)
hand_pts = P[np.abs(P[:, 0]) > 0.9 * hi[0]]
log("посажен: рост %.2f, размах %.2f, глубина %.2f; кисти на высоте %.2f (у пони %.2f)"
    % (hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1], hand_pts[:, 2].mean(), bones["bip01_l_hand_19"].z))

# ------------------------------------------------- depth: fit by the TORSO, not by the bounds
# Fitting by the bounding box is not allowed: the model's tail pulls the box back, and the torso moves
# forward of the spine. Then the spine bone runs right at the back, the chest wobbles with any turn
# of the body, and the arms and legs hang in front of the armour.
# The depth reference is the VANILLA HUMAN, not the pony: armour is made for him, and he sets its fit.
# The human body is exported from the game assets:
#   tools\tpac_export\bin\Release\tpac_export.exe obj "<game>\Modules\Native\AssetPackages" \
#       body_male_a assets\human_ref\human.obj
# Vanilla models face +Y (ours face -Y), so the reference is turned around.
TORSO_Z = (1.00, 1.35)    # between the bip01_spine_9 and bip01_spine2_11 bones
TORSO_HALF = 0.22         # wider than this in X is already the arms
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
# Move the mesh itself, not the object: "baking" the shift (transform_apply) only works on the
# selected object, and the reference import steals the selection — then the object moves, and all
# later edits are written in local coordinates and miss by exactly this shift.
for v in mdl.data.vertices:
    v.co.y += shift
log("вся модель сдвинута по глубине на %+.3f м: середина торса была %+.3f, у %s %+.3f"
    % (shift, mine, whose, target))

# Where the neck ends and the head begins. On this pony the skull with the mane goes down to the chin
# and below (bottom of the head at 1.40-1.45 m), and the neck is thin. The old slanted line "under the
# muzzle" ran at 1.6 m at the back of the head and gave the body the bottom of the head and the back
# of the head with the mane (noticed in the editor 26.09.2026), so here it is a flat mark just below
# the chin: everything above it is head.
NECK_Z = 1.40
JAW_SLOPE, JAW_FROM = 0.0, 0.0


def jaw_z(p):
    return NECK_Z - JAW_SLOPE * max(0.0, -p[1] + JAW_FROM)


def is_head(p):
    return p[2] > jaw_z(p)


# ------------------------------------------------------------------ head and neck — move back
# The depth fit aligns the TORSO, but this model's head sticks forward more than a human's: the back
# of her head was at y 0.07, while the pony's is at 0.14. In armour this is obvious at once — the head
# pokes out in front of the breastplate (noticed in game 24.09.2026). We move the head and neck back,
# and the shift fades out towards the bottom of the neck, otherwise the joint with the body splits.
HEAD_SHIFT = 0.07        # how many metres back the head moves
HEAD_SHIFT_FADE = 0.14   # over how many metres below the jaw line the shift fades out

P = coords()
_moved = 0
for i, p in enumerate(P):
    w = (p[2] - jaw_z(p) + HEAD_SHIFT_FADE) / HEAD_SHIFT_FADE
    w = min(1.0, max(0.0, w))
    if w <= 0:
        continue
    w = w * w * (3 - 2 * w)
    mdl.data.vertices[i].co.y += HEAD_SHIFT * w
    _moved += 1
P = coords()
log("голова с шеей сдвинута назад на %.2f м (затронуто %d вершин)" % (HEAD_SHIFT, _moved))


# ---------------------------------------------- arms from the T-pose onto the pony arm (rotation + length)
# Just rotating by 22 degrees is not enough: the model's arm is 10% longer than the pony's, so the
# elbow landed on the forearm bone and the hand missed the hand bone, and in game the arms looked bent.
# We align the model's "shoulder — hand" segment with the same skeleton segment: rotation about the
# shoulder plus scaling by length. Near the joint the transform ramps in smoothly, otherwise it tears.
SHOULDER_X = 0.18               # shoulder joint in X (the model's shoulder bone after fitting)
# The arm transform ramps in FROM THE EDGE OF THE TORSO, not from its middle. This pony's arms sit
# low (z 1.23, while the vanilla skeleton's shoulder bone is at 1.41), and the arm is raised by 0.18 m
# when fitting: if the raise starts inside the torso, the sides of the chest and the mane at the neck
# get dragged along with the arm and stretch into a "hood" (noticed in game 26.09.2026). From the
# edge of the torso the raise fades out smoothly along the shoulder.
ARM_RAMP_FROM = 0.17            # distance from the axis where the transform starts (edge of the chest)
ARM_RAMP = 0.40                 # over how many metres the transform ramps in
ARM_TIP = 0.9                   # share of the span beyond which is the hand
HEAD_RAMP = 0.12                # over how many metres below the jaw the arm takes over

P = coords()
arm_far = np.abs(P[:, 0]) > 0.45
_far_idx = [i for i in range(len(P)) if arm_far[i] and appendage[i] is None]
arm_y = float(np.median([P[i][1] for i in _far_idx]))
ARM_BACK = arm_y + 0.12         # farther back is the wing, not the arm
# The arm zone is limited to a HEIGHT BAND around the arm itself, not by an "above the waist"
# threshold. This model's pelvis is wider than the shoulders and starts already at z 1.15: with the
# dragon's "p[2] > 1.0" the hips fell into the arm zone entirely and got its full rotation — two flat
# flaps grew on the lower back (seen in the editor 24.09.2026).
ARM_Z = float(np.median([P[i][2] for i in _far_idx]))
ARM_BAND = 0.20                 # the arm zone extends this many metres up and down from the arm
arm_zone = [i for i, p in enumerate(P)
            if abs(p[0]) > ARM_RAMP_FROM and p[1] < ARM_BACK
            and abs(p[2] - ARM_Z) < ARM_BAND
            and appendage[i] is None and not is_head(P[i])]
log("зона руки: высота %.2f +-%.2f, вершин %d" % (ARM_Z, ARM_BAND, len(arm_zone)))
tip = max(abs(P[i][0]) for i in arm_zone)
# The hand is taken by the model's OWN bone, not by the claw tips: the model's claws are long, and
# with them the arm went far out from the body (the hand landed at |x| 0.83 instead of 0.65).
hand_idx = [i for i in arm_zone if i in own_hand] or \
           [i for i in arm_zone if abs(P[i][0]) > ARM_TIP * tip]

# The shoulder joint is on the axis of the arm itself, extended to SHOULDER_X. It cannot be found from
# a torso slice at that mark: there is still the side there, and the slice middle wanders by ten or so
# centimetres in height. The axis is computed from the middles of cross bands of the arm (from 0.30
# to the tips), so the hand and elbow do not outweigh it, and a straight line is fitted through them.
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
# Aim the WRIST at the hand bone. The pony's fingertips cannot be used: her arm is longer than a
# human's (the fingers reach |x| 0.83, while the vanilla body's arm ends at 0.60), and the model
# got splayed arms. Let the claws stick out past the bone, like a human's fingers.
H_p = bones["bip01_l_hand_19"]
# Exactly to the bone the arm comes out a bit short: the hand hides in the sleeve. We let it go further
# along the same axis and turn it down — so it is both longer and pressed to the body, not splayed.
# 1.07 — requested after the test of 24.09.2026: exactly to the bone the arm came out a bit short,
# the hand hid in the sleeve.
# 1.07 — requested after the test of 24.09.2026: exactly to the bone the arm came out a bit short.
ARM_REACH = 1.07    # how many times farther than the hand bone the wrist goes
ARM_DROP = 0.0      # how many degrees the arm is additionally lowered toward the body
ARM_THICK = 1.0     # resulting thickness across the axis relative to the source: arm as in the original
                    # (at 1.25 it came out as a thick tube flaring at the hoof, 26.09.2026)

reach = (H_p - S_p) * ARM_REACH
drop = math.radians(ARM_DROP)
H_p = S_p + Vector((reach.x * math.cos(drop) + reach.z * math.sin(drop), reach.y,
                    -reach.x * math.sin(drop) + reach.z * math.cos(drop)))
turn = (H_d - S_d).rotation_difference(H_p - S_p).to_matrix()
stretch = (H_p - S_p).length / (H_d - S_d).length
along = (H_d - S_d).normalized()
log("  рука: наклон %.0f -> %.0f градусов ниже горизонта, толщина x%.2f"
    % (math.degrees(math.atan2(-(bones["bip01_l_hand_19"] - S_p).z, (bones["bip01_l_hand_19"] - S_p).x)),
       math.degrees(math.atan2(-(H_p - S_p).z, (H_p - S_p).x)), ARM_THICK))
log("  плечо модели (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f), кисть (%.2f,%.2f,%.2f) -> (%.2f,%.2f,%.2f)"
    % (*S_d, *S_p, *H_d, *(S_p + turn @ ((H_d - S_d) * stretch))))
for i in arm_zone:
    p = P[i]
    sign = 1.0 if p[0] > 0 else -1.0
    t = min(1.0, max(0.0, (abs(p[0]) - ARM_RAMP_FROM) / ARM_RAMP))
    t = t * t * (3 - 2 * t)
    t *= min(1.0, (jaw_z(p) - p[2]) / HEAD_RAMP)      # the transform fades out toward the head
    mine = Vector((abs(p[0]), p[1], p[2]))
    # along the axis the arm is stretched/squeezed by the alignment, across it separately, otherwise
    # it gets thinner along with the shortening
    local = mine - S_d
    shaft = along * local.dot(along)
    local = shaft + (local - shaft) * (ARM_THICK / stretch)   # stretch is applied to everything below
    moved_to = S_p + turn @ (local * stretch)
    now = mine.lerp(moved_to, t)
    v = mdl.data.vertices[i]
    v.co = Vector((now.x * sign, now.y, now.z))
P = coords()
hands = P[[i for i in hand_idx]]
log("рука модели %.2f м -> кость пони %.2f м (масштаб %.2f, поворот %.0f градусов), %d вершин"
    % ((H_d - S_d).length, (H_p - S_p).length, stretch,
       math.degrees((H_d - S_d).angle(H_p - S_p)), len(arm_zone)))
log("кисть теперь (%.2f,%.2f,%.2f), кость кисти пони (%.2f,%.2f,%.2f)"
    % (abs(hands[:, 0]).mean(), hands[:, 1].mean(), hands[:, 2].mean(), H_p.x, H_p.y, H_p.z))

# ------------------------------------------------------------------- a wider rib cage
# The model has a narrow chest — next to the wide pelvis it looks like a tube. We widen it in X, but
# not by a single scale: otherwise the arms move along with the chest and the hands leave their bones.
# Inside the torso the width grows proportionally, outside the shift fades out toward the wrist, and
# in height it fades smoothly beyond the ribs. Wings and tail move with everything so the roots stay.
CHEST_WIDE = 1.00           # this pony's chest is round and her own — not widened (at 1.3 the shoulders crumpled)
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
    mdl.data.vertices[i].co.x += math.copysign(grow * reach * w, p[0])
P = coords()
wide = P[(P[:, 2] > CHEST_BAND[0]) & (P[:, 2] < CHEST_BAND[1]) & (np.abs(P[:, 0]) < 0.45)]
log("грудная клетка: полуширина %.2f -> %.2f (в %.1f раза)"
    % (HALF, float(np.percentile(np.abs(wide[:, 0]), 90)), CHEST_WIDE))

# ------------------------------------------------------------------- a smaller upper chest
# The ribs should be widened, not the bust: at the top the chest stuck out both forward and sideways.
# We shrink the upper part of the chest in width and depth around its own middle — so the bottom
# (ribs) stays wide and the top tightens. It fades out toward the shoulders, otherwise the arms tear off.
UPPER_SMALL = 1.00          # how many times the upper chest is shrunk
UPPER_BAND = (1.34, 1.58)   # from the bust to the collarbones
UPPER_FADE = 0.10           # over how many metres in height it ramps in and out
UPPER_HALF = 0.26           # beyond this in X is already the shoulder, no shrinking there
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
    v = mdl.data.vertices[i]
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

for g in list(mdl.vertex_groups):     # the foreign Mixamo groups are no longer needed
    mdl.vertex_groups.remove(g)
for g in ref.vertex_groups:
    mdl.vertex_groups.new(name=g.name)
bpy.ops.object.select_all(action="DESELECT")
mdl.select_set(True)
bpy.context.view_layer.objects.active = mdl
dt = mdl.modifiers.new("веса", "DATA_TRANSFER")
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

# Hand bones go to the hands only: the pony's hands hang at belly height, and the sides of the
# model's body end up closer to them than to her body (the same trouble the yak had).
P = coords()
HAND_MIN_X = 0.60
stripped = 0
for i, p in enumerate(P):
    if abs(p[0]) >= HAND_MIN_X:
        continue
    v = mdl.data.vertices[i]
    for g in list(v.groups):
        if mdl.vertex_groups[g.group].name in HAND_BONES:
            mdl.vertex_groups[g.group].remove([i])
            stripped += 1
    if not v.groups:
        mdl.vertex_groups["bip01_spine_9" if p[2] > 0.95 else PELVIS].add([i], 1.0, "REPLACE")
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("снято весов кистей с корпуса: %d" % stripped)

# ----------------------------------------------------------- arm weights along the axis, not by proximity
# The weight transfer from the pony takes the nearest point of her mesh, but her arms lie differently:
# the joint lands on the wrong bone, and in game the arm "breaks" in a pose — the shoulders come out
# square instead of round (noticed 26.09.2026; in the original the arms are perfectly round). The arm
# bones in the skeleton form a straight chain (clavicle, upper arm, four twists, hand, finger), and the
# model's arm lies along it after fitting. So the weight is computed by position along the arm: between
# two neighbouring joints it flows smoothly from one bone to the other, like a real tube. Right at the
# shoulder we blend smoothly with the torso weights so the joint does not tear.
ARM_WEIGHT_FROM = 0.20      # closer to the axis the torso weights stay
ARM_WEIGHT_BLEND = 0.12     # over how many metres they are replaced by the weights along the arm


def arm_chain(side):
    cur = next(b for b in skel.data.bones if b.name.startswith("bip01_%s_clavicle" % side))
    chain = []
    while cur is not None:
        chain.append(cur)
        kids = [k for k in cur.children if "notused" not in k.name and "nub" not in k.name]
        cur = kids[0] if kids else None
    # A bone's weight peaks at the MIDDLE of its segment, not at the joint: that is how the vanilla
    # body's weights work (checked on body_male_a: upperarm_twist peaks at x 0.25-0.29, twist1 at
    # 0.37-0.41, foretwist at 0.49-0.52). If the peak is put on the joint, the bend moves half a bone
    # toward the shoulder.
    return [(b.name, skel.matrix_world @ ((b.head_local + b.tail_local) / 2)) for b in chain]


chains = {1.0: arm_chain("l"), -1.0: arm_chain("r")}
log("цепочка руки: " + " > ".join("%s(%.2f,%.2f,%.2f)" % (n, *p) for n, p in chains[1.0]))

# The "distance along the arm" parameter used to be just |X|, but the arm does not hang strictly along
# the X axis, it slopes down (see the arm fix above), and in the same RING of vertices around the arm
# the front and back ended up at different |X|. Because of that half of the ring got the weight of one
# bone and half of the neighbouring one, and when the shoulder turned the ring tore in half in a twist
# (noticed in the editor 27.09.2026). Projecting onto the real arm axis (shoulder to hand in 3D) gives
# the same value for all vertices of a true cross-section — the ring bends instead of tearing.
AXES = {}
for sign, chain in chains.items():
    origin = chain[0][1]
    axis = (chain[-1][1] - origin)
    axis = axis / axis.length
    AXES[sign] = (origin, axis, [(name, (pos - origin).dot(axis)) for name, pos in chain])

P = coords()
_rewritten = 0
for i in arm_zone:
    sign = 1.0 if P[i][0] > 0 else -1.0
    origin, axis, chain = AXES[sign]
    # s (the transition from the torso weights) — by distance from the body axis, as before: it is
    # about "have we moved away from the body", not about where exactly along the arm we are.
    s = min(1.0, max(0.0, (abs(P[i][0]) - ARM_WEIGHT_FROM) / ARM_WEIGHT_BLEND))
    if s <= 0.0:
        continue
    s = s * s * (3 - 2 * s)
    # u — projection onto the true arm axis: decides between which bones along it to interpolate.
    u = (Vector(P[i]) - origin).dot(axis)
    along = {}
    if u <= chain[0][1]:
        along[chain[0][0]] = 1.0
    elif u >= chain[-1][1]:
        along[chain[-1][0]] = 1.0
    else:
        for (name_a, xa), (name_b, xb) in zip(chain[:-1], chain[1:]):
            if xa <= u < xb:
                k = (u - xa) / (xb - xa)
                k = k * k * (3 - 2 * k)
                along[name_a], along[name_b] = 1.0 - k, k
                break
    old = {mdl.vertex_groups[g.group].name: g.weight for g in mdl.data.vertices[i].groups}
    new = {}
    for name_g, w in old.items():
        new[name_g] = new.get(name_g, 0.0) + w * (1.0 - s)
    for name_g, w in along.items():
        new[name_g] = new.get(name_g, 0.0) + w * s
    for name_g in old:
        if name_g not in new:
            mdl.vertex_groups[name_g].remove([i])
    for name_g, w in new.items():
        group = mdl.vertex_groups.get(name_g) or mdl.vertex_groups.new(name=name_g)
        group.add([i], w, "REPLACE")
    _rewritten += 1
bpy.ops.object.vertex_group_limit_total(limit=4)
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("веса руки вдоль оси: %d вершин" % _rewritten)

# The head is rigidly on the head bone — otherwise the neck and chest bones drive the muzzle and it
# tears at the joint. The boundary (jaw_z/is_head) is set above, before the arm fix.
BLEND = 0.15

head_group = mdl.vertex_groups["bip01_head_13"]
head_idx = [i for i in range(len(P)) if is_head(P[i]) and appendage[i] is None]
for i in head_idx:
    for g in list(mdl.data.vertices[i].groups):
        mdl.vertex_groups[g.group].remove([i])
head_group.add(head_idx, 1.0, "REPLACE")
blended = torn = 0
for i in range(len(P)):
    p = P[i]
    if is_head(p) or appendage[i] is not None:
        continue
    front = max(0.0, -p[1] + JAW_FROM)
    d = (NECK_Z - JAW_SLOPE * front) - p[2]
    if d >= BLEND:
        # There must be no head bone below the neck. The weight transfer gives it to the ridge on
        # the chest: it sticks out forward and up, and the pony's nearest point is her chin. In game
        # such a chest folded at every turn of the head.
        if head_group.index in [g.group for g in mdl.data.vertices[i].groups]:
            head_group.remove([i])
            torn += 1
            if not mdl.data.vertices[i].groups:
                mdl.vertex_groups["bip01_neck_12"].add([i], 1.0, "REPLACE")
        continue
    w = 1.0 - d / BLEND
    for g in mdl.data.vertices[i].groups:
        mdl.vertex_groups[g.group].add([i], g.weight * (1.0 - w), "REPLACE")
    head_group.add([i], w, "ADD")
    blended += 1
bpy.ops.object.vertex_group_normalize_all(lock_active=False)
log("голова жёстко на кости головы: %d вершин, плавная зона: %d, снято весов головы с корпуса: %d"
    % (len(head_idx), blended, torn))

# ---------------------------------------------------------------- 3. cutting into parts
group_names = {g.index: g.name for g in mdl.vertex_groups}
dominant = []
for v in mdl.data.vertices:
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
# Crown: below this share of the head height is already the face
SKULL_PART = 70
SIDE_LOCK_X = 0.17      # wider than this from the axis are the locks at the sides of the muzzle, not the muzzle
SKULL_TOP = float(np.percentile(head_pts[:, 2], SKULL_PART))
# Mane boundary in depth: the share of the way from the eyes to the back of the head. Everything
# beyond it is mane and back of the head, nearer is the muzzle with the frill (it must not go into
# the hair, it would be tinted with the hair color).
HAIR_FROM_EYES = 0.45
eye_y = float(np.percentile(head_pts[:, 1], 5))        # front of the muzzle
HAIR_BACK = eye_y + (HEAD_BACK - eye_y) * HAIR_FROM_EYES
LEG_TOP = 0.44 * HEIGHT / 1.86
# Where the hand begins: slightly closer to the body than the wrist after aligning the arm (see the
# arms section). The mark moves together with ARM_REACH — otherwise the lengthened arm pushes the
# wrist past the boundary and a piece of the forearm goes into the "gloves".
_shoulder_x = abs(bones["bip01_l_upperarm_twist_15"].x)
HAND_FROM = _shoulder_x + (abs(bones["bip01_l_hand_19"].x) - _shoulder_x) * ARM_REACH - 0.03
TAIL_Z = bones[PELVIS].z * HEIGHT / 1.86

# Smaller hand hooves (26.09.2026: first a little, then on request by another 30% — 0.97 * 0.7).
# Everything beyond the wrist is shrunk toward the wrist centre: right at the wrist the shrinking
# fades out so the joint does not tear.
HOOF_SCALE = 0.68       # how many times smaller the hoof is
HOOF_BLEND = 0.05       # over how many metres from the wrist the shrinking ramps in
P = coords()
for side in (1.0, -1.0):
    ring = [i for i in range(len(P)) if appendage[i] is None and P[i][0] * side > 0
            and HAND_FROM - 0.03 <= abs(P[i][0]) <= HAND_FROM + 0.01]
    if not ring:
        continue
    pivot = Vector(P[ring].mean(0))
    for i in range(len(P)):
        if appendage[i] is not None or P[i][0] * side <= 0 or abs(P[i][0]) <= HAND_FROM - 0.02:
            continue
        w = min(1.0, (abs(P[i][0]) - (HAND_FROM - 0.02)) / HOOF_BLEND)
        w = w * w * (3 - 2 * w)
        mdl.data.vertices[i].co = pivot + (Vector(P[i]) - pivot) * (1.0 - (1.0 - HOOF_SCALE) * w)
P = coords()
log("копыта рук уменьшены до %.0f%%" % (HOOF_SCALE * 100))
log("ориентиры: спина y=%.2f, голова верх %.2f (череп до %.2f), зад головы y=%.2f, "
    "грива от y=%.2f, ноги до %.2f" % (BACK, HEAD_TOP, SKULL_TOP, HEAD_BACK, HAIR_BACK, LEG_TOP))

# DO NOT PICK UP THE FORELOCK. I tried catching the locks left on the face by the fact that a lock is a
# thin sheet (a back side with an opposite normal nearby, KD-tree): along with them the scales above
# the brow and pieces of the cheek went into the hairstyle, and the head shrank from 322 vertices to
# 150. The user: ("make it as it
# was before, the hair came out really bad"). Two marks remain — the crown and the back of the head.


# The pony's "hairstyle" is the HORN, and only it: the hair color from the appearance screen works on
# it. The mane is fused into the head and is tinted with the coat color, the ears stay with the head.
# The horn grows from the forehead and goes below the crown: a height cut gave it only the upper half
# (noticed 26.09.2026), and the bottom stayed in the head. We find it as a cone around the horn axis:
# the axis is from the very top (principal axis of the vertices nearest the tip), and from the tip we
# flood down along the edges while the vertices are inside the cone. The ears and mane are far from it.
HORN_TIP = 0.05         # vertices no farther than this from the tip define the horn axis
HORN_R0, HORN_SLOPE = 0.015, 0.20   # cone radius at the tip and how fast it grows along the axis
HORN_LEN = 0.27         # horn length from the tip to the forehead
_tip = P[int(np.argmax(P[:, 2]))]
_seed = np.flatnonzero(P[:, 2] > _tip[2] - HORN_TIP)


def _axis_of(pts):
    axis = np.linalg.svd(pts - pts.mean(0), full_matrices=False)[2][0]
    return -axis if axis[2] > 0 else axis    # down from the tip, toward the base


_axis = _axis_of(P[_seed])


def in_horn(q):
    v = q - _tip
    s = float(v @ _axis)
    return -0.01 <= s <= HORN_LEN and float(np.linalg.norm(v - s * _axis)) <= HORN_R0 + HORN_SLOPE * s


# An axis from a few vertices at the tip is inaccurate, so we refine: flood, axis from what was found,
# and flood again — so the cone fits the whole horn, not just its top.
for _round in range(3):
    antler = {int(i) for i in _seed if in_horn(P[i])}
    _stack = list(antler)
    while _stack:
        _cur = _stack.pop()
        for _n in neighbours[_cur]:
            if _n not in antler and in_horn(P[_n]):
                antler.add(_n)
                _stack.append(_n)
    if len(antler) > 3:
        _axis = _axis_of(P[sorted(antler)])
_hp = P[sorted(antler)]
log("рог: %d вершин, острие (%.2f,%.2f,%.2f), ось (%.2f,%.2f,%.2f), z %.2f..%.2f"
    % (len(antler), *_tip, *_axis, _hp[:, 2].min(), _hp[:, 2].max()))


def part_of(i):
    if appendage[i]:                 # for a winged race they are selected above, by bones
        return appendage[i]
    p = P[i]
    if i in antler:
        return "horn"
    if is_head(p):
        # The mane is a separate hairstyle: the back and top of the head (the crown and everything
        # behind the eyes). The face with the forelock at the eyes and the locks at the cheeks stays head.
        if p[1] > HAIR_BACK or p[2] > SKULL_TOP or abs(p[0]) > SIDE_LOCK_X:
            return "hair"
        return "head"
    b = dominant[i]
    # The hand is chosen BY POSITION, not only by bone. The yak's hand is short and shaggy, the pony
    # weights land on the forearm, and by bones only some thirty vertices went into the "gloves":
    # wearing bracers, the yak would be left without hands (the body mesh is replaced by armour).
    if abs(p[0]) > HAND_FROM:
        return "gloves"
    if b in HAND_BONES:
        return "gloves"
    if b in LEG_BONES and p[2] < LEG_TOP:
        return "legs"
    return "body"


labels = [part_of(i) for i in range(len(P))]

# The ears stay with the head: they lie behind the eyes and above the crown, and by the rule above
# they would go into the mane (and be tinted with the hair color). The ear is the highest point of
# each side, except the horn; everything "mane" in a sphere around it goes back to the head.
EAR_R = 0.10            # radius of the sphere around the ear
EAR_DROP = 0.05         # how far the sphere centre is below the ear tip
for _side in (1.0, -1.0):
    _cand = [i for i, l in enumerate(labels) if l == "hair" and P[i][0] * _side > 0.07]
    if not _cand:
        continue
    _top = max(_cand, key=lambda i: P[i][2])
    _mid = P[_top] - np.array([0.0, 0.0, EAR_DROP])
    _back = [i for i in _cand if np.linalg.norm(P[i] - _mid) < EAR_R]
    for i in _back:
        labels[i] = "head"
    log("ухо (%+.0f): кончик (%.2f,%.2f,%.2f), возвращено голове %d вершин" % (_side, *P[_top], len(_back)))

counts = {}
for name in labels:
    counts[name] = counts.get(name, 0) + 1
log("части по вершинам:", counts)

# ---------------------------------------------------------------- 4. material and textures
DIFFUSE = None        # color map: the eyes are searched on it (see eye_spots)
mat = bpy.data.materials.new(MAT)
mat.use_nodes = True
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
# Meshy textures are separate PNGs next to the FBX; the role is taken from the file name and they are
# copied under our name — tools/make_pony_textures.py then makes the game maps from them.
ROLES = (("_normal", "normal"), ("_roughness", "roughness"), ("_metallic", "metallic"))
for fname in sorted(os.listdir(os.path.dirname(SRC))):
    if not fname.lower().endswith(".png"):
        continue
    low = fname.lower()
    role = next((r for key, r in ROLES if key in low), "color")
    dst = os.path.join(tex_dir, "eq_%s_%s.png" % (RACE, role))
    shutil.copyfile(os.path.join(os.path.dirname(SRC), fname), dst)
    img = bpy.data.images.load(dst)
    img.colorspace_settings.name = "sRGB" if role == "color" else "Non-Color"
    log("текстура", os.path.basename(dst), "%dx%d" % tuple(img.size))
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.label = role
    if role == "color":
        DIFFUSE = img
        if bsdf:
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    elif role == "normal" and bsdf:
        nm = mat.node_tree.nodes.new("ShaderNodeNormalMap")
        mat.node_tree.links.new(tex.outputs["Color"], nm.inputs["Color"])
        mat.node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

# ------------------------------------------------------------------------ blinking
# The engine blinks with the head's vertex keys: there are exactly 101 of them (key_000..key_100), and
# frames 86, 87, 88 are the left eye, the right and both (same as on the pony, tools/convert_twilight.py).
# Without the keys the face is just frozen, like the yak's.
#
# The pony's eyelids are their own geometry hidden above the eye. The model has none: the model is one
# piece, the eye is just PAINTED on the texture. So we close it by squashing: the vertices around the
# eye are pulled to its middle in height, and the painted eye collapses into a slit. The same trick on
# the pony finishes closing the eyeball when the engine applies a frame at less than full strength.
#
# The eyes are found on the texture itself — two symmetric dark spots on the muzzle. The color sample
# is taken slightly inside the face: the model's UV layout is patchy, and right at an island's edge
# there is already the atlas black.
FACE_KEYS = 101         # the vanilla head has this many vertex keys
BLINK_FRAMES = {86: "левый", 87: "правый", 88: "оба"}
EYE_DARK = 0.30         # darker than this is eye paint, not fur
EYE_CORE = 0.055        # within this radius of the eye middle squash fully — that is the eye itself
EYE_REACH = 0.090       # beyond that the squash falls to zero so the cheek and brow are not crumpled
EYE_SQUASH = 0.92       # how strongly the vertices are pulled to the eye middle
# The pony's eye is large and cartoonish with a dark pupil: the spot is the eye middle — no need to
# offset from it, as with the griffon's pupil.
EYE_OUT = 0.0
EYE_BACK = 0.0
# We pick the DARKEST of the large spots, and only on the muzzle: when choosing "closer to the middle
# in depth" the mark landed on the ear, and she blinked with her ears (noticed in game 24.09.2026).
EYE_SIDE = 0.04         # closer than this to the axis is not an eye but the bridge of the nose
EYE_MIN = 5             # a smaller spot is UV noise, not an eye
EYE_BLUE = 0.18         # blue minus red difference at which a pixel counts as iris (fur — 0.10)
EYE_GROW = 0.09         # the iris is searched no farther than this from the pupil
EYE_HALF = 0.0          # half of the eye height, filled in by eye_spots


def eye_spots(ob):
    """Eye middles on the head: two dark spots on the texture, one per side."""
    # The color map is the one that went into Base Color when parsing the material: image names in a
    # .glb say nothing, and picking by name ("texture_0") missed — there was no blinking at all.
    img = DIFFUSE if (DIFFUSE is not None and DIFFUSE.has_data) else None
    uvs = ob.data.uv_layers.active
    if img is None or uvs is None:
        log("ВНИМАНИЕ: не нашёл текстуру или развёртку — моргания не будет")
        return []
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)
    P = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    tone = np.zeros(len(P))
    blue = np.zeros(len(P))
    hits = np.zeros(len(P))
    for poly in ob.data.polygons:
        mid = np.mean([np.array(uvs.data[li].uv) for li in poly.loop_indices], axis=0)
        for li in poly.loop_indices:
            spot = np.array(uvs.data[li].uv) * 0.75 + mid * 0.25
            x = int(min(max(spot[0], 0.0), 0.999) * (w - 1))
            y = int(min(max(spot[1], 0.0), 0.999) * (h - 1))
            tone[ob.data.loops[li].vertex_index] += float(px[y, x, :3].mean())
            blue[ob.data.loops[li].vertex_index] += float(px[y, x, 2] - px[y, x, 0])
            hits[ob.data.loops[li].vertex_index] += 1
    tone /= np.maximum(hits, 1)
    blue /= np.maximum(hits, 1)

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
        spots.append((P[blob].mean(0), len(blob), float(tone[blob].mean()), blob))
    # We find ONE eye and mirror it: searching each side separately is unreliable — there are many dark
    # spots on the head (fur shadows, nostrils, braids), and the eyes came out at different heights.
    # Filter by the muzzle: not at the axis itself, in the front half of the head and above its middle —
    # the back of the head with the braid and the chin are cut off. Of the rest we take the DARKEST
    # large spot: on the pony's head nothing is darker than the pupil (eyelashes are thin and do not
    # form a large spot).
    front = float(P[:, 1].min() + P[:, 1].max()) / 2
    upper = float(P[:, 2].min() + 0.35 * (P[:, 2].max() - P[:, 2].min()))   # the pony's eyes are mid-head
    mine = [s for s in spots
            if abs(s[0][0]) > EYE_SIDE and s[0][1] < front and s[0][2] > upper and s[1] >= EYE_MIN]
    if not mine:
        return []
    best, count, shade, blob = min(mine, key=lambda s: s[2])
    # The dark spot is only the pupil, it is in the upper part of the eye, and below is the blue iris.
    # The whole eye must be squashed, otherwise half of it blinks (noticed in game 26.09.2026): we grow
    # the spot onto neighbouring blue vertices, but no farther than EYE_GROW from the pupil.
    iris = (hits > 0) & (tone < 0.80) & (blue > EYE_BLUE)
    eye = set(blob)
    stack = list(blob)
    while stack:
        cur = stack.pop()
        for other in near[cur]:
            if other not in eye and (dark[other] or iris[other]) and np.linalg.norm(P[other] - best) < EYE_GROW:
                eye.add(other)
                stack.append(other)
    ext = P[sorted(eye)]
    global EYE_HALF
    EYE_HALF = float(ext[:, 2].max() - ext[:, 2].min()) / 2
    best = np.array([ext[:, 0].mean(), ext[:, 1].mean(), (ext[:, 2].max() + ext[:, 2].min()) / 2])
    log("  глаз целиком: %d вершин (зрачок %d), высота %.3f, середина по высоте сдвинута на %+.3f"
        % (len(eye), count, 2 * EYE_HALF, best[2] - P[blob].mean(0)[2]))
    right = np.array([abs(best[0]), best[1], best[2]])
    log("  глаз найден на (%.2f,%.2f,%.2f): %d вершин, яркость %.2f; вторая сторона отражена"
        % (*right, count, shade))
    right = right + np.array([EYE_OUT, EYE_BACK, 0.0])
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
            core = max(EYE_CORE, EYE_HALF * 1.15)      # the whole eye, with a margin for the eyelid
            reach = core + (EYE_REACH - EYE_CORE)
            close = gap < reach
            fade = np.clip((reach - gap[close]) / max(reach - core, 1e-6), 0.0, 1.0)
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
PLUG = 0.10        # how deep the wing and tail root goes into the body (the pony's back is thin: more sticks out)
SKULL_SMOOTH = 60   # times the dome in place of the mane is relaxed: the locks flatten
SKULL_INSET = 0.012 # how deep the dome is sunk under the mane (metres)
SEPARATE_NEAR = 0.025  # head vertices closer than this to the mane are sunk inward (metres)
SEPARATE_PUSH = 0.010  # and by this much, right at the mane
PLUG_MIN_X = 0.06   # the wing skirt does not come closer to the axis than this
ROOT_BLEND = 0.12   # over how many metres from the wing/tail root the weight goes from body weights to one bone
SMOOTH_ROUNDS = 18  # times the wing and tail socket is relaxed so the back becomes smooth
SMOOTH_GROW = 2     # the smoothing spreads this many rings around the patch
SPINE_CHAIN = (PELVIS, "bip01_spine_9", "bip01_spine1_10", "bip01_spine2_11", "bip01_neck_12")
SPINE_LINE = [(bones[a], bones[b]) for a, b in zip(SPINE_CHAIN[:-1], SPINE_CHAIN[1:])]


def closest_on(p, a, b):
    ab = b - a
    if ab.length_squared < 1e-9:
        return a.copy()
    return a + ab * min(1.0, max(0.0, (p - a).dot(ab) / ab.length_squared))


from mathutils.kdtree import KDTree
body_tree = KDTree(sum(1 for l in labels if l not in ("wings", "tail")))
for _i, _l in enumerate(labels):
    if _l not in ("wings", "tail"):
        body_tree.insert(Vector(P[_i]), _i)
body_tree.balance()

parts = {}
for name in ("body", "legs", "gloves", "head", "hair", "horn", "wings", "tail"):
    # The head gets a SKULL in place of the mane, not the mane itself: patches along the ragged edge of
    # the locks lay as flat chords, went inside and left gaps (noticed in the editor 26.09.2026).
    # So we take the same polygons but smooth them into a smooth crown dome and sink it under the mane
    # (see SKULL_* below): the locks do not turn into a dome, they only flatten.
    same = ("head", "hair") if name == "head" else (name,)
    keep = [i for i, l in enumerate(labels) if l in same]
    if not keep:
        log("часть", name, "пуста — пропущена")
        continue
    ob = mdl.copy()
    ob.data = mdl.data.copy()
    ob.name = ob.data.name = "eq_%s_%s" % (RACE, name)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    was_index = {v: i for i, v in enumerate(bm.verts)}   # indices before deletion — labels use them
    keep_set = set(keep)
    drop = [f for f in bm.faces if sum(1 for v in f.verts if v.index in keep_set) * 2 <= len(f.verts)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    # The tear-off spot is closed with polygons: otherwise see-through holes gape at the joints of the
    # wings, tail and neck (faces are not drawn from inside, and in game it is black there). ONLY cuts
    # must be closed: the wing and membrane edge is free all around, and it must not be patched — that
    # would cover the membrane with a solid sheet. A cut is recognised by a vertex of another part next
    # to it in the source mesh. UVs for the new faces are taken from neighbouring faces of the same
    # vertex, otherwise they pull color from the corner of the texture.
    uv = bm.loops.layers.uv.active
    cut = {v for v in bm.verts if any(labels[o] not in same for o in neighbours[was_index[v]])}

    # The wings and tail sit on their own bone, and the body at their root on its own (the back at the
    # wing follows the clavicle), so in motion the seam opens and you can see through the gap. So for
    # the wing and tail the root is extended INTO the body: from the cut a skirt is led to the spine.
    # It is not visible from outside, and it covers the gaps with margin.
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
                # the left and right wing skirts must not meet on the back in a single strip
                if name == "wings" and abs(v.co.x) < PLUG_MIN_X:
                    v.co.x = math.copysign(PLUG_MIN_X, here.x)
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
        # The head's cut with the mane is ragged: the free tips of the locks belong to the same loop,
        # and the share of "cut" vertices in it is small — but it must be closed anyway (under a helmet
        # the skull is seen empty from inside). So the head's threshold is lower than other parts'.
        need = 0.15 if name == "head" else 0.6
        if len(ring) < 3 or sum(1 for v in ring if v in cut) < need * len(ring):
            continue                     # the free edge of the membrane itself — leave it alone
        # whose boundary this was: with the wing and tail the socket is smoothed later, but the seam
        # with the head, legs and hands must not be touched — it joins the neighbouring part and must stay
        touching = [labels[o] for v in ring if v in was_index
                    for o in neighbours[was_index[v]] if labels[o] not in same]
        owner = max(set(touching), key=touching.count) if touching else None
        socket = owner in ("wings", "tail")
        # On the hairstyle itself (the horn) the base is not patched: it stays an open tube. But in the
        # head the hole from the horn is patched — under a helmet the horn is hidden, and there must be
        # no hole in the forehead; the cap lies inside the horn tube and does not flicker with it.
        if name in ("hair", "horn"):
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
                # The skull is almost convex, so the correct side of the patch is seen from the head
                # centre: the normal must point away from it. Without this the cap in place of the
                # mane ended up inside out, and from outside (the game does not draw back faces) a
                # hole gaped in the head.
                centre = sum((v.co for v in bm.verts), Vector()) / max(len(bm.verts), 1)
                for f in patch:
                    if f.normal.dot(f.calc_center_median() - centre) < 0:
                        f.normal_flip()
            if socket:
                smooth.update(v for f in patch for v in f.verts)
        patched += len(patch)
    if smooth:
        # The wing and tail socket is ragged: a patch along such an edge comes out crumpled. We relax
        # it together with the edge itself — the back becomes even and smooth, and the wing still sits
        # on top and goes inside. A ring around it is included too, otherwise the patch is a dent, but
        # vertices on the free edge are not touched: the seams with the head, legs and hands are there.
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
        was_now = {v: labels[was_index[v]] for v in bm.verts if v in was_index}
        dome = [v for v, l in was_now.items() if l == "hair"]
        # edges between the dome and the rest of the head are held in place — otherwise the seam opens
        movable = [v for v in dome
                   if all(was_now.get(e.other_vert(v)) == "hair" for e in v.link_edges)]
        for _ in range(SKULL_SMOOTH):
            bmesh.ops.smooth_vert(bm, verts=movable, factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.normal_update()
        for v in movable:
            v.co -= v.normal * SKULL_INSET
        log("  череп на месте гривы: %d вершин сглажено, утоплено на %.0f мм" % (len(movable), SKULL_INSET * 1000))
        # Where the head and mane still meet closely (cheeks at the forelock, the dome seam, the sides),
        # they flicker through each other: the two surfaces have the same depth. So all head vertices
        # closer than SEPARATE_NEAR to the mane are sunk by another SEPARATE_PUSH — the more, the closer.
        from mathutils.bvhtree import BVHTree
        hair_faces = [f for f in mdl.data.polygons
                      if sum(1 for i in f.vertices if labels[i] == "hair") * 2 > len(f.vertices)]   # the same rule as when cutting
        tree = BVHTree.FromPolygons([tuple(v.co) for v in mdl.data.vertices],
                                    [tuple(f.vertices) for f in hair_faces])
        bm.normal_update()
        pushed = 0
        for v in bm.verts:
            hit = tree.find_nearest(v.co)
            if hit[0] is None or hit[3] >= SEPARATE_NEAR:
                continue
            k = 1.0 - hit[3] / SEPARATE_NEAR
            v.co -= v.normal * (SEPARATE_PUSH * (0.4 + 0.6 * k))
            pushed += 1
        log("  голова отодвинута от гривы вглубь: %d вершин (ближе %.0f мм, до %.0f мм)"
            % (pushed, SEPARATE_NEAR * 1000, SEPARATE_PUSH * 1000))
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
        # Right at the root the weight is taken from the nearest body vertex and smoothly turns into a
        # single bone farther away: otherwise the root stays on a "foreign" bone and in motion gaps open
        # between the tail, wings and body (noticed in game 26.09.2026).
        made = {}
        for v in ob.data.vertices:
            _, near_i, gap = body_tree.find(v.co)
            w = min(1.0, gap / ROOT_BLEND)
            w = w * w * (3 - 2 * w)
            for g in mdl.data.vertices[near_i].groups:
                if w < 1.0:
                    gname = mdl.vertex_groups[g.group].name
                    if gname not in made:
                        made[gname] = ob.vertex_groups.new(name=gname)
                    made[gname].add([v.index], g.weight * (1.0 - w), "ADD")
            if w > 0.0:
                if anchor not in made:
                    made[anchor] = ob.vertex_groups.new(name=anchor)
                made[anchor].add([v.index], w, "ADD")
    if name in ("hair", "horn"):    # the hairstyle and horn entirely on the head
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
# The whole fitted model stays hidden in the .blend (it does not go into the FBX — export by selection):
# parts are cut from it by hand, see tools/make_pony_edit_scene.py.
mdl.name = mdl.data.name = "eq_pony_FULL"
mdl.parent = skel
mdl.matrix_parent_inverse = skel.matrix_world.inverted()
mdl.modifiers.new("Armature", "ARMATURE").object = skel
mdl.data.materials.clear()
mdl.data.materials.append(mat)
mdl.hide_render = mdl.hide_viewport = True

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
# The vanilla human IN PLACE of the model: it shows what pokes out of the armour and how far the
# arms and legs stick forward. The same file as for the depth fit.
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
    ob.location.x -= 2.0        # the pony alongside — to compare height
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
# each part of the model gets its own color — this shows where the cut went
PART_COLOUR = {"body": (0.80, 0.75, 0.65, 1), "legs": (0.35, 0.55, 0.85, 1),
               "gloves": (0.95, 0.80, 0.25, 1), "head": (0.35, 0.80, 0.45, 1),
               "hair": (0.90, 0.35, 0.75, 1), "horn": (0.95, 0.90, 0.30, 1), "wings": (0.55, 0.40, 0.85, 1),
               "tail": (0.95, 0.45, 0.30, 1)}
for name, ob in parts.items():
    ob.color = PART_COLOUR.get(name, (1, 1, 1, 1))
scene.render.resolution_x = scene.render.resolution_y = 900
scene.render.film_transparent = False
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
# The "height" shot is next to the pony for comparison, the others without her: otherwise
# she blocks the model from the side and you cannot see what is left on the back and where the cut went.
FRONT = (math.pi / 2, 0, 0)
for view, loc, rot, span, with_pony, hide in (
        ("рост", (-1.0, -6, 1.05), FRONT, 4.4, True, ()),
        ("front", (0, -6, 1.05), FRONT, 2.6, False, ()),
        ("side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, False, ()),
        ("back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ()),
        # wings and tail removed: shows whether pieces of them are left on the body and whether they
        # took something off the back: the wing and tail sockets are there, that is what the shot is for
        ("без крыльев", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, False, ("wings", "tail")),
        ("одни крылья", (0, -6, 1.05), FRONT, 2.6, False,
         ("body", "legs", "gloves", "head", "hair", "horn")),
        # the head alone — as the mod kit shows it: shows whether mane locks are left on the face
        ("одна голова", (0, -6, 1.80), FRONT, 0.75, False,
         ("body", "legs", "gloves", "hair", "horn", "wings", "tail")),
        ("одна голова сбоку", (6, 0, 1.80), (math.pi / 2, 0, math.pi / 2), 0.75, False,
         ("body", "legs", "gloves", "hair", "horn", "wings", "tail")),
        # over the vanilla human: red marks what pokes out of the silhouette the armour is made for
        ("поверх человека", (0, -6, 1.05), FRONT, 2.6, "поверх", ("wings", "tail")),
        ("поверх человека сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, "поверх",
         ("wings", "tail"))):
    for ob in pony.values():
        ob.hide_render = with_pony is not True
    for ob in overlay:
        ob.hide_render = with_pony != "поверх"
    for name, ob in parts.items():
        ob.hide_render = name in hide or (name == "horn" and "hair" in hide)
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)
log("превью в", prev)

# The same angles with the real texture: shows how the seams, eyes and mane came out
scene.display.shading.color_type = "TEXTURE"
for ob in parts.values():
    ob.hide_render = False
for ob in overlay:
    ob.hide_render = True
for ob in pony.values():
    ob.hide_render = True
for view, loc, rot, span, z in (
        ("текстура front", (0, -6, 1.05), FRONT, 2.6, 1.05),
        ("текстура side", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2), 2.6, 1.05),
        ("текстура back", (0, 6, 1.05), (math.pi / 2, 0, math.pi), 2.6, 1.05),
        ("текстура голова", (0, -6, 1.75), FRONT, 0.75, 1.75)):
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = span
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)

# Blinking: both eyes closed (key 88) — shows whether the eye closes completely
head = parts.get("head")
if head is not None and head.data.shape_keys:
    key = head.data.shape_keys.key_blocks.get("key_088")
    for view, value in (("моргание открыты", 0.0), ("моргание закрыты", 1.0)):
        if key:
            key.value = value
        cam.location = (0, -6, 1.66)
        cam.rotation_euler = FRONT
        cam.data.ortho_scale = 0.45
        scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
        bpy.ops.render.render(write_still=True)
    if key:
        key.value = 0.0

# Pose: the body is tilted and twisted — at rest the seams meet, but in motion they used to open
scene.display.shading.color_type = "OBJECT"
for ob in parts.values():
    ob.hide_render = False


def bend(bone, axis, deg):
    pb = skel.pose.bones[bone]
    pivot = pb.head.copy()
    turn = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-pivot)
    pb.matrix = turn @ pb.matrix
    bpy.context.view_layer.update()


bend(PELVIS, "Y", 14)
bend("bip01_spine_9", "X", 12)
bend("bip01_spine1_10", "X", 12)
for view, loc, rot in (("поза сзади", (0, 6, 1.05), (math.pi / 2, 0, math.pi)),
                       ("поза сбоку", (6, 0, 1.05), (math.pi / 2, 0, math.pi / 2))):
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.ortho_scale = 2.6
    scene.render.filepath = os.path.join(prev, "%s_%s.png" % (RACE, view))
    bpy.ops.render.render(write_still=True)
