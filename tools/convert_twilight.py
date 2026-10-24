# Conversion of "Twilight Sparkle (Anthro)" (glTF, MMD skeleton) into a set of Bannerlord items
# on the human skeleton: head, body, gloves, legs.
#
# blender --background --factory-startup --python convert_twilight.py -- <scene.gltf> <human_skeleton.fbx> <out_dir>
#        [<face_morphs.bin>]   - dump of the vanilla head's vertex keys (tools\dump_face_morphs.ps1)
#
# Steps:
#  1. The Bannerlord skeleton is imported with bone axes X/-Y (as the documentation advises).
#  2. The pony (facing -Y, like a Bannerlord character) is scaled so that the pelvis and neck match the skeleton.
#  3. The arms are rotated and lengthened to the Bannerlord joints (with a smooth transition by MMD weights),
#     the calves with hooves are compressed in height so that the knees and the floor match.
#  4. Weights: head/mane/tail rigid on one bone, the rest automatic from a temporary copy
#     of the skeleton whose bones point at the child joints.
#  5. Export FBX (skeleton + 4 meshes), PNG textures, .blend and previews.
import math
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

_args = sys.argv[sys.argv.index("--") + 1:]
GLTF, SKEL, OUT = _args[:3]
# optional 4th argument: dump of the vanilla head's vertex keys (tools\dump_face_morphs.ps1).
# Through these 101 keys the engine does facial expressions, blinking and eye movement; without them the face is static.
FACE_MORPHS = _args[3] if len(_args) > 3 else ""
TEX_DIR = os.path.join(OUT, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

PREFIX = "eq_twilight"

# material from glTF -> model part
PARTS = {
    "Material__43": "body",
    "Material__84": "eyelash",
    "8_-_Default": "eyes",
    "Material__396": "legs",
    "Material__422": "hair_front",
    "glove": "gloves",
    "Material__421": "hair_back",
    "Material__19": "head",
    "Material__330": "horn",
    "queue": "tail",
    "2_-_Default": "hooves",
    "Material__35": "teeth",
    "Material__37": "tongue",
}
# Bannerlord item -> parts
ITEMS = {
    # the tail is in the body: the engine treats the head mesh as a face, and vertices with the pelvis bone in it fly apart
    # eyelid: eyelids built to the shape of the eye (see build_eyelids): in the base shape they are squeezed into a strip
    # above the eye and invisible, and in frames 86/87/88 the engine opens them over the whole eye; that is the blink.
    f"{PREFIX}_head": ["head", "eyes", "eyelash", "teeth", "tongue", "eyelid"],
    # The mane with ears is a separate item in the helmet slot (equestria_items.xml, eq_pony_mane, 0 armour):
    # the hairstyle slot does not work for the race (the engine tears any hairstyle into pieces), and a real helmet simply
    # replaces this "hairstyle", and nothing pokes through it. The ear holes in the head are closed up.
    f"{PREFIX}_mane": ["hair_front", "hair_back", "horn"],
    # The tail is a separate item in the cape slot (eq_pony_tail): in the body mesh any chest armour
    # with covers_body hid it, and the cape slot is worn together with chest armour.
    # cutiemark: the mark on the thigh as geometry (see build_cutiemarks). It cannot be done through engine decals
    # (tattoo_materials): in Bannerlord they are applied only to the face.
    f"{PREFIX}_tail": ["tail", "cutiemark"],
    f"{PREFIX}_body": ["body"],
    f"{PREFIX}_gloves": ["gloves"],
    f"{PREFIX}_legs": ["legs", "hooves"],
}
# parts that move entirely with one bone
RIGID = {p: "bip01_head_13" for p in ITEMS[f"{PREFIX}_head"] + ITEMS[f"{PREFIX}_mane"]}
RIGID["tail"] = "bip01_pelvis_0"
RIGID["cutiemark"] = "bip01_pelvis_0"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
vl = bpy.context.view_layer


def log(*a):
    print("[convert]", *a, flush=True)


def select_only(objs, active):
    for o in scene.objects:
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = active


# ---------------------------------------------------------------- 1. Bannerlord skeleton
bpy.ops.import_scene.fbx(filepath=SKEL, automatic_bone_orientation=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
skel = next(o for o in scene.objects if o.type == "ARMATURE")
orig_skel_scale = skel.scale.copy()
skel.scale = (1, 1, 1)  # in the TaleWorlds file the scale is 0.01 (height 1.8 cm); we work and export in metres
vl.update()


def human(name):
    return skel.matrix_world @ skel.data.bones[name].head_local


H = {
    "pelvis": human("bip01_pelvis_0"),
    "neck": human("bip01_neck_12"),
    "r_shoulder": human("bip01_r_upperarm_twist_22"), "r_wrist": human("bip01_r_hand_26"),
    "l_shoulder": human("bip01_l_upperarm_twist_15"), "l_wrist": human("bip01_l_hand_19"),
    "l_knee": human("bip01_l_calf_2"), "r_knee": human("bip01_r_calf_6"),
}
log("human joints:", {k: tuple(round(c, 3) for c in v) for k, v in H.items()})

# ---------------------------------------------------------------- 2. pony
before = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=GLTF)
pony_objs = [o for o in scene.objects if o not in before]
parm = next(o for o in pony_objs if o.type == "ARMATURE")
dg = bpy.context.evaluated_depsgraph_get()


def pbone(idx):
    suffix = f"_{idx}"
    return next(b for b in parm.pose.bones if b.name.endswith(suffix))


def pony(idx):
    return parm.matrix_world @ pbone(idx).head


def descendants(idx):
    root = pbone(idx).bone
    return {root.name} | {c.name for c in root.children_recursive}


hip_c = (pony(100) + pony(106)) / 2
neck = pony(14)
s = (H["neck"].z - H["pelvis"].z) / (neck.z - hip_c.z)
log(f"scale factor {s:.3f}")


def sim_raw(p):
    # rotation by 180° around Z (the pony faces -Y, the Bannerlord skeleton +Y), scale, pelvis -> pelvis.
    # The model and weights match the skeleton anatomically; the turn for the game is done by rotating the whole skeleton
    # on export (see TURN_SKELETON_ON_EXPORT).
    q = p - hip_c
    return Vector((-q.x * s, -q.y * s, q.z * s + H["pelvis"].z))


# The pony's torso leans forward relative to the Bannerlord spine: without a correction the chest and back at
# shoulder level stand 6-7 cm in front of the bones, and the arms (they are placed on the bones) behind the torso.
# We shift the upper body along Y: 0 at the pelvis, the full shift from shoulder level up (head, mane, horn too).
_pony_sh = (sim_raw(pony(42)) + sim_raw(pony(75))) / 2
_human_sh = (H["l_shoulder"] + H["r_shoulder"]) / 2
TORSO_SHIFT_Y = _human_sh.y - _pony_sh.y
log(f"torso shift y {TORSO_SHIFT_Y:+.3f} (pony shoulders y {_pony_sh.y:.3f}, human {_human_sh.y:.3f})")


def sim(p):
    q = sim_raw(p)
    t = min(max((q.z - H["pelvis"].z) / (_human_sh.z - H["pelvis"].z), 0.0), 1.0)
    t = t * t * (3 - 2 * t)  # smooth transition
    q.y += TORSO_SHIFT_Y * t
    return q


ARM_BACK = 0.06  # m, shift of the hand backward


def make_arm(shoulder_idx, wrist_idx, group_roots, h_shoulder, h_wrist):
    ps, pw = sim(pony(shoulder_idx)), sim(pony(wrist_idx))
    ap, ah = pw - ps, h_wrist - h_shoulder
    lp, lh = ap.length, ah.length
    rot = ap.normalized().rotation_difference(ah.normalized()).to_matrix()
    k = lh / lp
    axis = ah.normalized()
    groups = set().union(*(descendants(i) for i in group_roots))
    log(f"arm {shoulder_idx}: pony len {lp:.3f} -> human {lh:.3f} (x{k:.2f}), "
        f"angle {math.degrees(ap.angle(ah)):.1f}°, {len(groups)} bones")

    def transform(p):
        q = rot @ (p - ps)
        d = q.dot(axis)
        q += axis * ((k - 1) * min(max(d, 0.0), lp))
        # per a check in the Model Viewer the arms lag behind the torso, so bring them forward (in the engine this is +Y
        # before the skeleton turn; -Y was checked and turned out to be backward), from 0 at the shoulder to ARM_BACK at the wrist and beyond
        q.y += ARM_BACK * min(max(d / lp, 0.0), 1.0)
        return h_shoulder + q

    return groups, transform


# after the rotation the pony's arm on the -X side ends up at +X, where the bip01_r bones are
ARMS = [
    make_arm(42, 27, (42, 45), H["r_shoulder"], H["r_wrist"]),
    make_arm(75, 60, (75, 78), H["l_shoulder"], H["l_wrist"]),
]
knee_z = (sim(pony(99)).z + sim(pony(105)).z) / 2
log(f"pony knee z {knee_z:.3f}, human knee z {(H['l_knee'].z + H['r_knee'].z) / 2:.3f}")

parts = {}
for ob in pony_objs:
    if ob.type != "MESH" or ob.name.startswith("Icosphere"):
        continue
    part = PARTS[ob.material_slots[0].material.name]
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    names = {g.index: g.name for g in ob.vertex_groups}
    coords = []
    for v_src, v in zip(ob.data.vertices, me.vertices):
        p = sim(ob.matrix_world @ v.co)
        for groups, transform in ARMS:
            w = min(1.0, sum(g.weight for g in v_src.groups if names.get(g.group) in groups))
            if w > 0:
                p = p.lerp(transform(p), w)
        coords.append(p)
    parts[part] = (me, coords)

# calves: compress everything below the knee in height so that the sole stands on the floor
z_min = min(p.z for _, coords in parts.values() for p in coords)
leg_k = knee_z / (knee_z - z_min)
log(f"lowest point {z_min:.3f} -> 0, below-knee height x{leg_k:.2f}")

for part, (me, coords) in parts.items():
    for v, p in zip(me.vertices, coords):
        if p.z < knee_z:
            p = Vector((p.x, p.y, (p.z - z_min) * leg_k))
        v.co = p
    me.update()
    me.name = f"{PREFIX}_{part}"
    mat = me.materials[0]
    mat.name = f"{PREFIX}_{part}"
    ob = bpy.data.objects.new(f"{PREFIX}_{part}", me)
    scene.collection.objects.link(ob)
    ob.vertex_groups.clear()  # the MMD group names are stored in the mesh itself; remove them
    if part not in RIGID:
        # glTF splits the mesh along UV seams; without merging, the halves of a seam get different weights and separate.
        # Custom normals become wrong after merging, so we reset them and smooth again.
        select_only([ob], ob)
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
        bm = bmesh.new()
        bm.from_mesh(me)
        n_before = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        log(f"part {part}: merged {n_before - len(me.vertices)} seam verts")
    parts[part] = ob

for o in pony_objs:
    bpy.data.objects.remove(o, do_unlink=True)
vl.update()

# ---------------------------------------------------------------- 3. temporary skeleton for weights
wa = skel.copy()
wa.data = skel.data.copy()
wa.name = "weighting_rig"
scene.collection.objects.link(wa)
select_only([wa], wa)
bpy.ops.object.mode_set(mode="EDIT")
eb = wa.data.edit_bones
for side, n in (("l", (1, 2, 3, 4)), ("r", (5, 6, 7, 8))):
    thigh, calf, foot, toe = (f"bip01_{side}_thigh_{n[0]}", f"bip01_{side}_calf_{n[1]}",
                              f"bip01_{side}_foot_{n[2]}", f"bip01_{side}_toe0_{n[3]}")
    nub = "bip01_l_toe0_nub_notused" if side == "l" else "bip01_toe0_nub_notused"
    for a, b in ((thigh, calf), (calf, foot), (foot, toe), (toe, nub)):
        eb[a].tail = eb[b].head
for a, b in (("bip01_pelvis_0", "bip01_spine_9"), ("bip01_spine_9", "bip01_spine1_10"),
             ("bip01_spine1_10", "bip01_spine2_11"), ("bip01_spine2_11", "bip01_neck_12"),
             ("bip01_neck_12", "bip01_head_13"), ("bip01_head_13", "bip01_head_nub_notused")):
    eb[a].tail = eb[b].head
for side, n in (("l", (14, 15, 16, 17, 18, 19, 20)), ("r", (21, 22, 23, 24, 25, 26, 27))):
    chain = [f"bip01_{side}_clavicle_{n[0]}", f"bip01_{side}_upperarm_twist_{n[1]}",
             f"bip01_{side}_upperarm_twist1_{n[2]}", f"bip01_{side}_foretwist_{n[3]}",
             f"bip01_{side}_foretwist1_{n[4]}", f"bip01_{side}_hand_{n[5]}",
             f"bip01_{side}_finger0_{n[6]}"]
    for a, b in zip(chain, chain[1:]):
        eb[a].tail = eb[b].head  # hand: wrist -> base of the fingers (palm)
    # fingers: from the base along the forearm direction (that is how the pony's hand is stretched)
    finger, fore = eb[chain[-1]], eb[chain[-3]]
    finger.tail = finger.head + (eb[chain[-2]].head - fore.head).normalized() * 0.15
bpy.ops.object.mode_set(mode="OBJECT")
for b in wa.data.bones:
    # finger0 (the thumb) is not used by vanilla hands; with it, in the Model Viewer some glove vertices
    # stretched in a strip toward the floor; the pony's fingers go entirely on the hand bone
    b.use_deform = not b.name.endswith("notused") and "_finger0_" not in b.name

bone_segments = [(b.name, wa.matrix_world @ b.head_local, wa.matrix_world @ b.tail_local)
                 for b in wa.data.bones if b.use_deform]


def nearest_bone(p):
    best, best_d = None, 1e9
    for name, a, b in bone_segments:
        ab = b - a
        t = min(max((p - a).dot(ab) / ab.length_squared, 0.0), 1.0)
        d = (a + ab * t - p).length
        if d < best_d:
            best, best_d = name, d
    return best


def auto_weights(ob):
    select_only([ob, wa], wa)
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    mw = ob.matrix_world.copy()
    ob.parent = None
    ob.matrix_world = mw
    # Automatic weights sometimes find no solution for some vertices (separate pieces, double surfaces).
    # Such vertices take the weights of the nearest weighted vertex, and if there is none, of the nearest bone.
    verts = ob.data.vertices
    weighted = [v for v in verts if sum(g.weight for g in v.groups) > 1e-4]
    zero = [v for v in verts if sum(g.weight for g in v.groups) <= 1e-4]
    if weighted:
        tree = KDTree(len(weighted))
        for i, v in enumerate(weighted):
            tree.insert(v.co, i)
        tree.balance()
    group_names = {g.index: g.name for g in ob.vertex_groups}
    for v in zero:
        if weighted:
            _, i, _ = tree.find(v.co)
            for g in weighted[i].groups:
                ob.vertex_groups[group_names[g.group]].add([v.index], g.weight, "REPLACE")
        else:
            name = nearest_bone(ob.matrix_world @ v.co)
            vg = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
            vg.add([v.index], 1.0, "REPLACE")
    log(f"weights {ob.name}: {len(ob.vertex_groups)} groups, "
        f"{len(zero)}/{len(verts)} verts without auto weights fixed")


MAX_INFLUENCES = 3
MIN_WEIGHT = 0.02


def limit_weights(ob):
    # Vanilla Bannerlord meshes have no more than 3 bones per vertex and a weight sum of exactly 1 (checked on
    # Female_BodyBase). Automatic weights give up to 6 bones with a sum below 1; in the engine such vertices slide.
    groups = {g.index: g for g in ob.vertex_groups}
    trimmed = 0
    for v in ob.data.vertices:
        ws = sorted(((g.group, g.weight) for g in v.groups if g.weight > 1e-4), key=lambda gw: -gw[1])
        # weights below MIN_WEIGHT are apparently rounded to zero by the engine (8 bits per weight): with them some
        # glove vertices flew off in a strip to the origin
        keep = [gw for gw in ws[:MAX_INFLUENCES] if gw[1] >= MIN_WEIGHT] or ws[:1]
        total = sum(w for _, w in keep)
        if len(ws) > MAX_INFLUENCES:
            trimmed += 1
        for g in list(v.groups):
            groups[g.group].remove([v.index])
        for gi, w in keep:
            groups[gi].add([v.index], w / total, "REPLACE")
    log(f"weights {ob.name}: {trimmed} verts trimmed to {MAX_INFLUENCES} bones, all normalized")


# Previously the model was turned to face -Y with the left/right weights swapped. For a symmetric
# body at rest this looked right, but the turn swaps front and back of the arms: in game the thumb
# ended up at the back, and the arm twisted backward when bending. Now weights are by position, without swapping.
for part, ob in parts.items():
    if part in RIGID:
        vg = ob.vertex_groups.new(name=RIGID[part])
        vg.add(range(len(ob.data.vertices)), 1.0, "REPLACE")
    else:
        auto_weights(ob)
        limit_weights(ob)

bpy.data.objects.remove(wa, do_unlink=True)

# The head is taken from the original as is: the ears stay on it. Attempts to cut off the ears and close the holes
# spoiled the skull (ragged edges, holes, a faceted crown); if needed, the ears are hidden by cut-outs
# in helmets for ponies, not by editing the head.
# The lower forearm goes into the hands mesh, as in the vanilla body (there the hands start at ~0.82 of shoulder→wrist).
# Vanilla chest armour hides the sleeve on the forearm inside the arm, relying on the hands mesh: if the forearm
# is in the body mesh, the chest armour (covers_body) hides it, and instead of an arm squeezed cloth is visible.
FOREARM_TO_HANDS_T = 0.72


def arm_t(p):
    best = None
    for side in ("l", "r"):
        sh, wr = H[f"{side}_shoulder"], H[f"{side}_wrist"]
        v = wr - sh
        t = (p - sh).dot(v) / v.length_squared
        r = (p - (sh + v * t)).length
        if r < 0.15 and (best is None or r < best[1]):
            best = (t, r)
    return best[0] if best else -1.0


body_ob, gloves_ob = parts["body"], parts["gloves"]
select_only([body_ob], body_ob)
bm = bmesh.new()
bm.from_mesh(body_ob.data)
for elem in (*bm.verts, *bm.edges, *bm.faces):
    elem.select = False
for f in bm.faces:
    if arm_t(body_ob.matrix_world @ f.calc_center_median()) > FOREARM_TO_HANDS_T:
        f.select_set(True)
moved = sum(f.select for f in bm.faces)
bm.select_mode = {"FACE"}
bm.to_mesh(body_ob.data)
bm.free()
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_mode(type="FACE")
bpy.ops.mesh.separate(type="SELECTED")
bpy.ops.object.mode_set(mode="OBJECT")
forearms = next(o for o in vl.objects.selected if o is not body_ob)
select_only([gloves_ob, forearms], gloves_ob)
bpy.ops.object.join()
log(f"forearms: {moved} faces moved from body to gloves (t > {FOREARM_TO_HANDS_T})")

# The model's material is built without alpha, so the eyelashes are drawn as solid dark polygons. Next to the eyes
# they look fine, but the far ones (on the forehead and cheeks) looked like junk in front of the face in game; we delete them.
LASH_LIMIT = 0.02  # m from the eye surface
eyes_pts = [parts["eyes"].matrix_world @ v.co for v in parts["eyes"].data.vertices]
eyes_tree = KDTree(len(eyes_pts))
for i, p in enumerate(eyes_pts):
    eyes_tree.insert(p, i)
eyes_tree.balance()
# the pony's eye centres; the facial keys are later anchored to them (add_face_morphs)
_eyes_arr = np.array([tuple(p) for p in eyes_pts])
PONY_EYES = (_eyes_arr[_eyes_arr[:, 0] > 0].mean(0), _eyes_arr[_eyes_arr[:, 0] < 0].mean(0))
_eye_l = _eyes_arr[_eyes_arr[:, 0] > 0]
PONY_EYE_R = float((_eye_l[:, 0].max() - _eye_l[:, 0].min()) / 2)  # half the eye width
PONY_EYE_RADII = (_eye_l.max(0) - _eye_l.min(0)) / 2  # the eye is elongated vertically; the eyelid is built by the bounding box
log(f"pony eye box {np.round(_eye_l.min(0), 3)}..{np.round(_eye_l.max(0), 3)}, r {PONY_EYE_R:.3f}")
LID_RINGS, LID_SEGS, LID_ARC = 5, 20, math.radians(96)
# The engine often applies the eyelid frame not at full strength (animations have 0.1-0.5), so the eyelid is built
# with a margin: at partial opening the eye is already covered, at full the eyelid sticks out slightly beyond the eye.
LID_OVERSHOOT = 1.15  # the eyelid cap mesh and its opening over the eye sphere


def build_eyelids():
    """Builds the eyelid mesh: a dome over the front part of each eye.

    The export gets the "squeezed" shape: all vertices pressed to the upper edge of the eye, where they are invisible.
    The opened positions are returned separately: the blink frames are made from them (add_face_morphs).
    """
    skull_c = Vector((0.0, np.median([p[1] for p in eyes_pts]), np.median([p[2] for p in eyes_pts]) + 0.08))
    verts, faces, expanded, base = [], [], [], 0
    for side, center in enumerate(PONY_EYES):
        c = Vector(center)
        n = (c - skull_c).normalized()
        up = Vector((0, 0, 1)) - n * (Vector((0, 0, 1)).dot(n))
        up = up.normalized() if up.length > 1e-6 else Vector((0, 1, 0))
        side_v = n.cross(up).normalized()
        radii = Vector(PONY_EYE_RADII) * 1.16 * LID_OVERSHOOT  # with a margin, so the eyelid goes over the eye

        def on_eye(d):  # a point on the eye surface in direction d
            return c + Vector((d.x * radii.x, d.y * radii.y, d.z * radii.z))

        top = on_eye(n * math.cos(LID_ARC) + up * math.sin(LID_ARC))  # upper edge of the eye
        for ring in range(LID_RINGS + 1):
            a = LID_ARC * (1 - ring / LID_RINGS) if ring else LID_ARC
            for seg in range(LID_SEGS):
                t = 2 * math.pi * seg / LID_SEGS
                d = n * math.cos(a) + (up * math.cos(t) + side_v * math.sin(t)) * math.sin(a)
                expanded.append(on_eye(d))
                verts.append(top + (up * math.cos(t) + side_v * math.sin(t)) * (radii.z * 0.02))
        for ring in range(LID_RINGS):
            for seg in range(LID_SEGS):
                a0 = base + ring * LID_SEGS + seg
                a1 = base + ring * LID_SEGS + (seg + 1) % LID_SEGS
                b0, b1 = a0 + LID_SEGS, a1 + LID_SEGS
                faces.append((a0, a1, b1, b0) if side == 0 else (a0, b0, b1, a1))
        base = len(verts)
    me = bpy.data.meshes.new(f"{PREFIX}_eyelid")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.shade_smooth()
    # UV is taken from the nearest muzzle vertex: the eyelid must be the colour of the coat around the eye
    head_ob = parts["head"]
    head_uv = head_ob.data.uv_layers.active.data
    uv_of_vert = {}
    for poly in head_ob.data.polygons:
        for li in poly.loop_indices:
            uv_of_vert.setdefault(head_ob.data.loops[li].vertex_index, tuple(head_uv[li].uv))
    head_tree = KDTree(len(uv_of_vert))
    order = list(uv_of_vert)
    for i, vi in enumerate(order):
        head_tree.insert(head_ob.matrix_world @ head_ob.data.vertices[vi].co, i)
    head_tree.balance()
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            p = Vector(expanded[me.loops[li].vertex_index])
            _, i, _ = head_tree.find(p)
            layer.data[li].uv = uv_of_vert[order[i]]
    me.materials.append(bpy.data.materials[f"{PREFIX}_head"])  # coat colour, like the muzzle
    ob = bpy.data.objects.new(f"{PREFIX}_eyelid", me)
    scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name=RIGID["head"])
    vg.add(range(len(me.vertices)), 1.0, "REPLACE")
    log(f"eyelids: {len(verts)} verts, {len(faces)} faces")
    return ob, np.array([tuple(p) for p in expanded])


parts["eyelid"], LID_EXPANDED = build_eyelids()

MARK_SIZE = 0.075      # m, radius of the big star
MARK_OFFSET = 0.0025   # m, offset from the skin so the mark does not flicker


def build_cutiemarks():
    """Cutie mark on the thigh: a star silhouette laid onto the body surface.

    Engine decals (tattoo_materials) are drawn only on the face, so the mark is made as geometry
    and goes into the tail item (the cape slot, which the pony wears anyway).
    """
    body = parts["body"]
    pts = np.array([tuple(body.matrix_world @ v.co) for v in body.data.vertices])
    z_lo, z_hi = np.percentile(pts[:, 2], [14, 30])
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mat = bpy.data.materials.new(f"{PREFIX}_cutiemark")
    # two halves: on the left the colour of the big star, on the right white for the small ones (a tiny image blurs
    # when scaled into the atlas, hence 64x64 rather than 2 pixels)
    img = bpy.data.images.new(f"{PREFIX}_cutiemark_d", 64, 64, alpha=False)
    half = np.zeros((64, 64, 4), dtype=np.float32)
    half[..., 3] = 1.0
    half[:, :32, :3] = np.array([0.85, 0.2, 0.75], dtype=np.float32)
    half[:, 32:, :3] = 1.0
    img.pixels.foreach_set(half.ravel())
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.links.new(mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"], tex.outputs["Color"])

    verts, faces, uvs = [], [], []

    def star_at(center, normal, radius, uv):
        """Lays a six-pointed star silhouette onto the body surface around the point center."""
        up = Vector((0, 0, 1)) - normal * Vector((0, 0, 1)).dot(normal)
        up = up.normalized()
        side = normal.cross(up).normalized()
        def on_skin(target):
            # a ray strictly along the normal: find_nearest pulled points sideways and the star came out crooked
            hit, hit_n, _, _ = bvh.ray_cast(target + normal * 0.12, -normal)
            return (hit + hit_n * MARK_OFFSET) if hit else (target + normal * MARK_OFFSET)

        base = len(verts)
        ring = []
        for k in range(12):
            a = math.pi * k / 6
            r = radius if k % 2 == 0 else radius * 0.34
            ring.append(on_skin(center + (up * math.cos(a) + side * math.sin(a)) * r))
        verts.append(on_skin(center))
        verts.extend(ring)
        uvs.extend([uv] * 13)
        for k in range(12):
            faces.append((base, base + 1 + k, base + 1 + (k + 1) % 12))

    for sign in (1, -1):
        sel = pts[(np.sign(pts[:, 0]) == sign) & (pts[:, 2] > z_lo) & (pts[:, 2] < z_hi) & (np.abs(pts[:, 1]) < 0.1)]
        center = Vector(sel.mean(0))
        normal = Vector((float(sign), 0, 0))
        star_at(center, normal, MARK_SIZE, (0.25, 0.5))
        # we no longer make small stars around the big one: the whole mark sits rigidly on the pelvis, while they
        # already lay on the leg and came off the skin when stepping, "flying" as a separate mesh
        # (removed 18.09.2026, see tools/trim_cutiemark.py)
    me = bpy.data.meshes.new(f"{PREFIX}_cutiemark")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    me.shade_smooth()
    me.materials.append(mat)
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[me.loops[li].vertex_index]
    ob = bpy.data.objects.new(f"{PREFIX}_cutiemark", me)
    scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name=RIGID["cutiemark"])
    vg.add(range(len(me.vertices)), 1.0, "REPLACE")
    log(f"cutiemarks: {len(verts)} verts, {len(faces)} faces")
    return ob


parts["cutiemark"] = build_cutiemarks()

# mark for the eyeballs: their eyelid must not move (otherwise the eye itself would shift)
for _part in ITEMS[f"{PREFIX}_head"]:
    _ob = parts[_part]
    _attr = _ob.data.attributes.new("eq_eye", "INT", "POINT")
    _lid = _ob.data.attributes.new("eq_lid", "INT", "POINT")  # eyelid vertex number (0 = not an eyelid)
    for _i in range(len(_ob.data.vertices)):
        _attr.data[_i].value = 1 if _part == "eyes" else 0
        _lid.data[_i].value = _i + 1 if _part == "eyelid" else 0
PONY_CHIN_Z = float(min((parts["head"].matrix_world @ v.co).z for v in parts["head"].data.vertices))
log(f"pony eyes {np.round(PONY_EYES[0], 3)} / {np.round(PONY_EYES[1], 3)}, chin z {PONY_CHIN_Z:.3f}")
lash = parts["eyelash"]
lash_bm = bmesh.new()
lash_bm.from_mesh(lash.data)
outside = [f for f in lash_bm.faces
           if min(eyes_tree.find(lash.matrix_world @ v.co)[2] for v in f.verts) > LASH_LIMIT]
bmesh.ops.delete(lash_bm, geom=outside, context="FACES")
bmesh.ops.delete(lash_bm, geom=[v for v in lash_bm.verts if not v.link_faces], context="VERTS")
lash_bm.to_mesh(lash.data)
lash_bm.free()
lash.data.update()
log(f"eyelashes trimmed: {len(outside)} faces farther than {LASH_LIMIT} m from the eyes")

# ---------------------------------------------------------------- 4. assembling the items
items = {}
for item, part_names in ITEMS.items():
    objs = [parts[p] for p in part_names]
    select_only(objs, objs[0])
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = vl.objects.active
    ob.name = item
    ob.data.name = item
    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = skel
    items[item] = ob
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    log(f"item {item}: {tris} tris, materials {[m.name for m in ob.data.materials]}")

# The skeleton stays at scale 1: in the FBX the character will honestly be 1.8 m (180 cm), and when imported into the editor
# with "Convert to unit: m" the size will match the game skeleton. With the original 0.01 scale from human_skeleton.fbx
# the file described a figure 1.8 cm tall; in game the mesh collapsed into rays along the floor.
vl.update()

# ---------------------------------------------------------------- 5. atlas: all textures into one, one material
# Each source texture takes a cell of a 4x4 grid (the UVs of all parts lie in 0..1, no baking needed).
# The whole model gets one material eq_twilight_body; it is set up in the editor once.
CELL, GRID, PAD = 1024, 4, 8
INNER = CELL - 2 * PAD
ATLAS_MAT = f"{PREFIX}_body"

COAT_PARTS = {"body", "head", "legs", "gloves", "hooves"}  # coat and hooves: the engine tints them
COAT_LIGHTEN = 1.25  # the grey base is slightly lighter than the original, otherwise the colouring comes out dull
coat_tint = []

part_mats = sorted({m.name for ob in items.values() for m in ob.data.materials})
cells = {name: i for i, name in enumerate(part_mats)}
atlas_px = np.zeros((CELL * GRID, CELL * GRID, 4), dtype=np.float32)
atlas_px[..., 3] = 1.0
for name, i in cells.items():
    col, row = i % GRID, i // GRID
    mat = bpy.data.materials[name]
    src = next((n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    if src is None:  # the teeth had no texture
        px = np.ones((INNER, INNER, 4), dtype=np.float32)
    else:
        # read the pixels directly and stretch with numpy: a copy of the procedural image (image.copy() + scale)
        # came out empty, and the atlas cell turned black
        w, h = src.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        src.pixels.foreach_get(buf)
        buf = buf.reshape(h, w, 4)
        ys = (np.arange(INNER) * h // INNER).clip(0, h - 1)
        xs = (np.arange(INNER) * w // INNER).clip(0, w - 1)
        px = buf[ys][:, xs].copy()
    # The coat is desaturated: the engine multiplies the texture by the chosen skin colour, and on the saturated lilac
    # base the colouring slider was barely readable. The mane, tail, horn and eyes stay coloured.
    part = name[len(PREFIX) + 1:]
    if part in COAT_PARTS:
        rgb = px[..., :3]
        gray = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        mean_rgb, mean_gray = rgb.reshape(-1, 3).mean(0), float(gray.mean())
        px[..., :3] = np.clip(gray[..., None] * COAT_LIGHTEN, 0.0, 1.0)
        coat_tint.append(mean_rgb / max(mean_gray * COAT_LIGHTEN, 1e-4))
        log(f"  coat cell {name}: mean {np.round(mean_rgb, 3)} -> grayscale, "
            f"tint {np.round(coat_tint[-1], 3)}")
    # the margins at the cell edge repeat the edge pixels, so mipmaps do not mix neighbouring cells
    px = np.pad(px, ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge")
    atlas_px[row * CELL:(row + 1) * CELL, col * CELL:(col + 1) * CELL] = px
    log(f"atlas cell {i} ({col},{row}): {name}")

# the _d suffix: the Bannerlord editor recognises such a texture as a DiffuseMap
atlas = bpy.data.images.new(f"{ATLAS_MAT}_d", CELL * GRID, CELL * GRID, alpha=False)
atlas.pixels.foreach_set(atlas_px.ravel())
atlas.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_d.png")
atlas.file_format = "PNG"
atlas.save()
log(f"texture {atlas.name}.png {atlas.size[0]}x{atlas.size[1]}")
if coat_tint:
    tint = np.mean(coat_tint, axis=0)
    log(f"coat palette hint: исходный цвет шерсти = point \"{tint[0]:.2f}, {tint[1]:.2f}, {tint[2]:.2f}\" "
        f"(вписать первой точкой в COAT_PALETTE, tools\\make_pony_race.py)")

atlas_mat = bpy.data.materials[ATLAS_MAT]
for ob in items.values():
    me = ob.data
    uv = me.uv_layers.active.data
    names = [m.name for m in me.materials]
    for poly in me.polygons:
        i = cells[names[poly.material_index]]
        col, row = i % GRID, i // GRID
        for li in poly.loop_indices:
            u, v = uv[li].uv
            uv[li].uv = ((col + (PAD + u * INNER) / CELL) / GRID, (row + (PAD + v * INNER) / CELL) / GRID)
        poly.material_index = 0
    me.materials.clear()
    me.materials.append(atlas_mat)
for node in atlas_mat.node_tree.nodes:
    if node.type == "TEX_IMAGE":
        node.image = atlas
for mat in list(bpy.data.materials):
    if mat.users == 0:
        bpy.data.materials.remove(mat)

# Do NOT reverse the face winding order: checked in the Model Viewer 2026-09-15, with the reversal
# the inside of the model was visible. The original order from Blender is correct.

# Flat normal map (0.5, 0.5, 1): a material with Vertex Layout -> Bumpmap needs a map in the NormalMap slot,
# without it the model's lighting in game breaks (dark in the sun, overexposed in the menu).
flat_n = bpy.data.images.new(f"{ATLAS_MAT}_n", 256, 256, alpha=False)
flat_n.pixels.foreach_set(np.tile(np.array([0.5, 0.5, 1.0, 1.0], dtype=np.float32), 256 * 256))
flat_n.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_n.png")
flat_n.file_format = "PNG"
flat_n.save()
log(f"texture {flat_n.name}.png (flat normal map)")

# A flat specular map for the faceshader_high skin shader: the editor placeholder default_editor_texture_s is
# blue noise and gives ripples on the coat. A dark grey map = a weak even highlight.
flat_s = bpy.data.images.new(f"{ATLAS_MAT}_s", 256, 256, alpha=False)
flat_s.pixels.foreach_set(np.tile(np.array([0.15, 0.15, 0.15, 1.0], dtype=np.float32), 256 * 256))
flat_s.filepath_raw = os.path.join(TEX_DIR, f"{ATLAS_MAT}_s.png")
flat_s.file_format = "PNG"
flat_s.save()
log(f"texture {flat_s.name}.png (flat specular map)")

# The model is built facing +Y, like the skeleton from modding_resources, but the engine shows such a mesh with its back
# to the skeleton. We rotate the whole skeleton together with the meshes by 180° around Z; the skeleton is rotated
# the same way in modders' reference FBXs (Skinned Body Base Meshes). Anatomy and weights do not change.
TURN_SKELETON_ON_EXPORT = True
if TURN_SKELETON_ON_EXPORT:
    skel.rotation_mode = "XYZ"
    skel.rotation_euler.z += math.pi
    vl.update()
    log(f"skeleton turned 180° for export, rotation {tuple(round(a, 3) for a in skel.rotation_euler)}")

def add_face_morphs(ob, path):
    """Transfers the vanilla head's vertex keys onto the pony head.

    The heads are very different, so we match them by the skull's bounding box: a pony point is converted
    to human head coordinates, the 4 nearest human vertices are taken, their offsets are averaged
    and scaled back. The key order is kept: the game's facial animations refer to it.
    """
    import struct

    EYE_FRAME = 17  # the eye_size frame from skins.xml; by it we find the eyes on the human head
    with open(path, "rb") as f:
        n, frames = struct.unpack("<ii", f.read(8))
        base = np.frombuffer(f.read(n * 12), dtype="<f4").reshape(n, 3).astype(float)
        deltas = []
        for _ in range(frames):
            struct.unpack("<i", f.read(4))
            pts = np.frombuffer(f.read(n * 12), dtype="<f4").reshape(n, 3).astype(float)
            deltas.append(pts - base)

    # Anchoring by the eyes, not by the head's bounding box: with the bounding box the offsets of the human face landed
    # on the pony's ears (the pony head is wider because of the ears and longer because of the muzzle).
    moved = np.linalg.norm(deltas[EYE_FRAME], axis=1) > 1e-4
    h_eye_l = base[moved & (base[:, 0] > 0)].mean(0)
    h_eye_r = base[moved & (base[:, 0] < 0)].mean(0)
    p_eye_l, p_eye_r = PONY_EYES
    k_x = abs(p_eye_l[0] - p_eye_r[0]) / max(abs(h_eye_l[0] - h_eye_r[0]), 1e-6)
    h_eye_mid, p_eye_mid = (h_eye_l + h_eye_r) / 2, (p_eye_l + p_eye_r) / 2
    k_z = (p_eye_mid[2] - PONY_CHIN_Z) / max(h_eye_mid[2] - base[:, 2].min(), 1e-6)
    scale = np.array([k_x, (k_x + k_z) / 2, k_z])  # in depth the average; the pony muzzle is longer than a face
    log(f"face morph fit: human eyes {np.round(h_eye_mid, 3)}, pony {np.round(p_eye_mid, 3)}, "
        f"scale {np.round(scale, 2)}")

    # local mesh coordinates: by this point the skeleton is already rotated by 180°, while the keys and reference data
    # are computed in the original system (it is also the mesh's local one)
    pony_pts = np.array([tuple(v.co) for v in ob.data.vertices])
    h_lo, p_lo = h_eye_mid, p_eye_mid

    tree = KDTree(len(base))
    for i, p in enumerate(base):
        tree.insert(Vector(p), i)
    tree.balance()

    idx, weight = [], []
    for p in pony_pts:
        q = h_lo + (p - p_lo) / scale  # pony point -> human head coordinates
        near = tree.find_n(Vector(q), 4)
        w = np.array([1.0 / max(d, 1e-4) for _, _, d in near])
        idx.append([i for _, i, _ in near])
        weight.append(w / w.sum())
    idx, weight = np.array(idx), np.array(weight)

    # Frames 86/87/88 are closed eyelids (the engine blinks by them, see the idle_normal animation). A human
    # eyelid moves 2-4 mm, while the pony's eye is the size of a palm, so transferring is useless here:
    # we draw the closed eyelid ourselves: the skin around the eye is pulled to its centre and brought in front of the eye.
    lid_attr = ob.data.attributes.get("eq_lid")
    lid_idx = np.array([lid_attr.data[i].value for i in range(len(ob.data.vertices))]) if lid_attr \
        else np.zeros(len(ob.data.vertices), int)
    is_lid = lid_idx > 0
    per_eye = len(LID_EXPANDED) // 2  # the first half of the vertices is the right eye (+X), the second the left

    eye_attr = ob.data.attributes.get("eq_eye")
    is_eye = np.array([eye_attr.data[i].value for i in range(len(ob.data.vertices))], bool) if eye_attr \
        else np.zeros(len(ob.data.vertices), bool)

    def eyelid_shift(halves):
        shift = np.zeros_like(pony_pts)
        sel = is_lid.copy()
        for i in np.flatnonzero(is_lid):
            half = 0 if (lid_idx[i] - 1) < per_eye else 1
            if half in halves:
                shift[i] = LID_EXPANDED[lid_idx[i] - 1] - pony_pts[i]
            else:
                sel[i] = False
        # The eyeball itself is squeezed vertically toward the eye centre in the blink frame. The engine often applies
        # the frame not at full strength, and the eyelid alone was barely visible; with the squeeze even a partial trigger
        # reads as a squint.
        for half in halves:
            c = PONY_EYES[half]
            mask = is_eye & ((pony_pts[:, 0] > 0) if half == 0 else (pony_pts[:, 0] < 0))
            shift[mask, 2] += (c[2] - pony_pts[mask, 2]) * 0.92
        log(f"  eyelid frame: {int(sel.sum())} lid verts, {int((is_eye).sum())} eye verts, "
            f"max {np.linalg.norm(shift, axis=1).max():.4f} m")
        return shift

    blink = {86: eyelid_shift({0}), 87: eyelid_shift({1}), 88: eyelid_shift({0, 1})}

    ob.shape_key_add(name="Basis", from_mix=False)
    for k, d in enumerate(deltas):
        key = ob.shape_key_add(name=f"key_{k:03d}", from_mix=False)
        shift = blink[k] if k in blink else (d[idx] * weight[:, :, None]).sum(1) * scale
        if k not in blink:
            shift[is_lid] = 0.0  # eyelids move only in the blink frames
        for i, v in enumerate(key.data):
            v.co = v.co + Vector(shift[i])
    log(f"face morphs: {frames} keys transferred to {ob.name} "
        f"(max shift {max(float(np.abs((d[idx] * weight[:, :, None]).sum(1) * scale).max()) for d in deltas):.4f} m)")


if FACE_MORPHS:
    add_face_morphs(items[f"{PREFIX}_head"], FACE_MORPHS)

select_only([skel, *items.values()], skel)
fbx_path = os.path.join(OUT, f"{PREFIX}.fbx")
bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
log("exported", fbx_path)

for img in list(bpy.data.images):
    if img.users == 0:
        bpy.data.images.remove(img)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{PREFIX}.blend"))
log("saved blend")

# ---------------------------------------------------------------- 6. preview: rest and a test pose
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for ob in items.values():
    for c in ob.bound_box:
        w = ob.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
center, size = (lo + hi) / 2, max(hi - lo)
log(f"final size (scene units) {tuple(round(v, 5) for v in (hi - lo))}")

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
scene.world = bpy.data.worlds.new("preview")
cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 1.25
cam.data.clip_start = size * 0.01
cam.data.clip_end = size * 100
scene.collection.objects.link(cam)
scene.camera = cam


def render(name, direction):
    cam.location = center + direction * size * 3
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, "preview", f"{name}.png")
    bpy.ops.render.render(write_still=True)


render("rest_front", Vector((0, -1, 0)))
render("rest_side", Vector((1, 0, 0)))

POSE = {  # an arbitrary pose, just to check the bends
    "bip01_r_upperarm_twist_22": (0, 0, -1.0),
    "bip01_r_foretwist_24": (0, 0, -1.2),
    "bip01_l_thigh_1": (0, 0, 0.9),
    "bip01_l_calf_2": (0, 0, -1.2),
    "bip01_spine1_10": (0, 0.3, 0),
    "bip01_head_13": (0.4, 0, 0),
}
for name, rot in POSE.items():
    pb = skel.pose.bones[name]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = rot
vl.update()
render("pose_front", Vector((0, -1, 0)))
render("pose_side", Vector((1, 0, 0)))
log("done")
