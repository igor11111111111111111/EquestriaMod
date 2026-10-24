# Adapts vanilla Bannerlord armour to the pony body (Twilight).
#
# blender --background eq_twilight.blend --python adapt_armor.py -- <Female_BodyBase.fbx> <vanilla_armor_dir> <out_dir>
#
# For each piece:
#  1. The armour FBX (exported from tpac with the tpac_export tool) is aligned to our skeleton by joints
#     (in eq_twilight.blend the skeleton is already rotated 180° for export - fitting by joints repeats this
#     rotation, so no separate turn-around or l/r swap is needed). Weights are renamed to bip01_*.
#  2. The shape is transferred from the reference female human body to the pony body:
#       body / legs - by horizontal slices (width and depth at each height, legs and torso separately),
#       head        - head dimensions,
#       hands       - along the hand axis (length) and across it (thickness).
#  3. Inflation: armour vertices that ended up inside the pony are pushed outwards with a gap and smoothing.
#  4. FBX export (skeleton + eq_pony_* meshes), previews.
import os
import re
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_body import bone_name_map, fit_matrix, import_reference  # noqa: E402

# Blender's FBX importer cannot read the morph keys of vanilla gloves (finger curl) - it fails on an assert.
# Pony armour does not need them: the fingers follow the finger0 bone. Disable morph reading.
import io_scene_fbx.import_fbx as _fbx_import  # noqa: E402

_fbx_import.blen_read_shapes = lambda *args, **kwargs: {}

ARGV = sys.argv[sys.argv.index("--") + 1:]
FEMALE_REF, ARMOR_DIR, OUT = ARGV[:3]
PACK = ARGV[3] if len(ARGV) > 3 else "armor"
os.makedirs(OUT, exist_ok=True)

# Which items to fit comes from the shared catalogue (tools/armor_catalog.py): pack "armor" is the first
# 20 imperial items, "empire" is the rest of Equestria's troop armour. Meshes are exported by the
# tpac_export tool into assets/reference/vanilla_armor. Each pack is its own FBX.
import armor_catalog  # noqa: E402

PIECES = [  # (vanilla armour mesh, mode, mesh name for the pony)
    (row["mesh"], row["mode"], row["pony_mesh"])
    for row in armor_catalog.pieces(PACK) if row["new_mesh"]
]
FBX_NAME = armor_catalog.PACKS[PACK]
# Packs with their own colouring: meshes reference eq_ch_* materials instead of vanilla ones
MAT_PREFIX = "eq_ch_" if PACK == "changeling" else ""
GAP = 0.008          # gap between the pony body and the armour after inflation, m
HEAD_RADIUS = 0.14   # pony "skull": head points closer than this to the centre (no ears, horn or mane strands), m
HEAD_SCALE_OF_WIDTH = 1.0  # fraction of the skull width ratio used for the helmet scale
HELMET_HEIGHT = 0.82  # fraction of the overall scale in height: under the helmet the head has no horn, the dome was too tall
HELMET_DROP = 0.035    # m - how far to lower the whole helmet: without the horn it sat too high
# Helmet face opening (empire_lord_helmet_c after x1.45 scaling around the head joint, measured in Blender):
HELMET_OPEN_TOP = 0.09          # m above the head joint - top of the opening (helmet rim), nothing above it is moved
HELMET_OPENING_BOTTOM_Z = 1.59  # m - bottom of the opening (aventail under the face) before the fix
HELMET_CHIN_GAP = 0.02          # m - how far below the pony's chin to lower the aventail at the front
HELMET_FACE_WIDEN = 0.12        # fraction - widening of the front part below the rim, to uncover the cheeks
INFLATE_MODES = {"body", "hands", "legs"}  # the helmet is not inflated: pushing out crumpled the aventail around the muzzle
SMOOTH_STEPS = 10
SLICE = 0.05
TORSO_X = 0.25
FACTOR_RANGE = (0.75, 1.8)
ARM_FORWARD = 0.06  # = ARM_BACK in convert_twilight.py: the pony arm is shifted forward from the bones, towards the wrist

scene = bpy.context.scene
vl = bpy.context.view_layer
skel = bpy.data.objects["bip01_notused"]
names = bone_name_map(skel)


def log(*a):
    print("[armor]", *a, flush=True)


def mirror_name(name):
    """bip01_l_thigh_1 -> bip01_r_thigh_5 (paired bones have different number suffixes)."""
    base = re.sub(r"_\d+$", "", name)
    if "_l_" in base:
        other = base.replace("_l_", "_r_")
    elif "_r_" in base:
        other = base.replace("_r_", "_l_")
    else:
        return name
    return next((b.name for b in skel.data.bones if re.sub(r"_\d+$", "", b.name) == other), name)


def world_verts(ob):
    return np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])


def H(bone):
    return skel.matrix_world @ skel.data.bones[bone].head_local


pelvis_z = H("bip01_pelvis_0").z
CROTCH = pelvis_z - 0.08

# ---------------------------------------------------------------- reference (human) and pony
ref, info = import_reference(FEMALE_REF, skel, turn_around=False)
log("female reference fit:", info, list(ref))
human = {k.split("_")[0]: m for k, m in ref.items()}  # head, body, hands, feet

pony_obj = {n: bpy.data.objects[f"eq_twilight_{n}"] for n in ("body", "legs", "gloves", "head")}
pony = {n: world_verts(ob) for n, ob in pony_obj.items()}
# pony tail (part of the body mesh): behind and below the lower back - excluded from sizes and inflation
body_pts = pony["body"]
tail_mask = (body_pts[:, 1] > 0.12) & (body_pts[:, 2] < pelvis_z + 0.12)
log(f"pony tail verts excluded: {tail_mask.sum()}")


def pony_surface(parts, exclude_tail=True, head_radius=None):
    verts, faces, base = [], [], 0
    for part in parts:
        ob = pony_obj[part]
        pts = pony[part]
        keep = np.ones(len(pts), bool)
        if part == "body" and exclude_tail:
            keep &= ~tail_mask
        if part == "head" and head_radius is not None:
            keep &= np.linalg.norm(pts - HEAD_CENTER, axis=1) < head_radius
        verts += [Vector(p) for p in pts]
        faces += [tuple(i + base for i in poly.vertices) for poly in ob.data.polygons if all(keep[i] for i in poly.vertices)]
        base += len(pts)
    return BVHTree.FromPolygons(verts, faces)


# ---------------------------------------------------------------- shape transfer: slices
def slice_boxes(points, regions):
    boxes = {}
    n = int(2.0 / SLICE) + 1
    idx = np.clip((points[:, 2] / SLICE).astype(int), 0, n - 1)
    for s in range(n):
        pts = points[idx == s]
        for key, mask in regions(pts, (s + 0.5) * SLICE):
            sel = pts[mask]
            if len(sel) > 8:
                lo, hi = sel[:, :2].min(0), sel[:, :2].max(0)
                boxes[(key, s)] = ((lo + hi) / 2, np.maximum((hi - lo) / 2, 1e-3))
    return boxes, n


def body_regions(pts, z):
    if z < CROTCH:
        return [("l", pts[:, 0] > 0), ("r", pts[:, 0] < 0)]
    return [("t", np.abs(pts[:, 0]) < TORSO_X)]


def build_slice_map(human_pts, pony_pts, keys):
    hb, n = slice_boxes(human_pts, body_regions)
    pb, _ = slice_boxes(pony_pts, body_regions)
    tables = {}
    for key in keys:
        hc, hh, pc, fac = (np.full((n, 2), np.nan) for _ in range(4))
        for s in range(n):
            if (key, s) in hb and (key, s) in pb:
                hc[s], hh[s] = hb[(key, s)]
                pc[s], ph = pb[(key, s)]
                fac[s] = np.clip(ph / hh[s], *FACTOR_RANGE)
        for arr, default in ((hc, 0.0), (pc, 0.0), (fac, 1.0)):
            for c in range(2):
                ok = ~np.isnan(arr[:, c])
                arr[:, c] = np.interp(np.arange(n), np.flatnonzero(ok), arr[ok, c]) if ok.any() else default
                arr[:, c] = np.convolve(np.pad(arr[:, c], 2, mode="edge"), np.ones(5) / 5, mode="valid")
        tables[key] = (hc, pc, fac, n)
        log(f"  slice map {key}: width x{fac[:, 0].min():.2f}..{fac[:, 0].max():.2f}, depth x{fac[:, 1].min():.2f}..{fac[:, 1].max():.2f}")

    def mapped(p, key):
        hc, pc, fac, n = tables[key]
        s = min(max(p[2] / SLICE - 0.5, 0.0), n - 1.0)
        grid = np.arange(n)
        h = np.array([np.interp(s, grid, hc[:, c]) for c in range(2)])
        q = np.array([np.interp(s, grid, pc[:, c]) for c in range(2)])
        f = np.array([np.interp(s, grid, fac[:, c]) for c in range(2)])
        return q + (p[:2] - h) * f

    def apply(p):
        side = "l" if p[0] > 0 else "r"
        if "t" not in tables:
            xy = mapped(p, side)
        else:
            t = min(max((p[2] - (CROTCH - 0.05)) / 0.10, 0.0), 1.0)
            xy = mapped(p, side) * (1 - t) + mapped(p, "t") * t
            arm = min(max((abs(p[0]) - TORSO_X) / 0.08, 0.0), 1.0) if p[2] >= CROTCH else 0.0
            xy = xy * (1 - arm) + p[:2] * arm
        return np.array([xy[0], xy[1], p[2]])

    return apply


# ---------------------------------------------------------------- shape transfer: head and hands
head_pts = pony["head"]
eyes_z = np.percentile(head_pts[:, 2], 40)
HEAD_CENTER = np.array([0.0, np.median(head_pts[:, 1]), eyes_z])
FRONT_SIGN = float(np.sign(np.median(head_pts[:, 1]) - H("bip01_head_13").y))  # the pony's muzzle is the front


def ear_mask():
    """Ear vertices in the head mesh - by position relative to the skull (as in convert_twilight.py)."""
    hj = H("bip01_head_13")
    c = np.array([0.0, hj.y + FRONT_SIGN * 0.042, hj.z + 0.056])
    return ((np.linalg.norm(head_pts - c, axis=1) > EAR_MIN_DIST) & (head_pts[:, 2] > hj.z + EAR_MIN_Z)
            & (np.abs(head_pts[:, 0]) > EAR_MIN_X) & ((head_pts[:, 1] - c[1]) * FRONT_SIGN < 0.0))


def build_head_map():
    hp = human["head"]["verts"]
    hp = hp[hp[:, 2] > H("bip01_neck_12").z + 0.05]  # without the neck
    pp = head_pts[~ear_mask()]  # skull without ears: with them the width was overestimated, ignoring them underestimated it
    hlo, hhi = hp.min(0), hp.max(0)
    plo, phi = np.percentile(pp, 2, axis=0), np.percentile(pp, 98, axis=0)
    # The helmet and the pony head are rigidly bound to the same head bone - scale the helmet around its joint,
    # keeping the fit designed for a human. Bounding-box centres do not work: the mane and muzzle shift them.
    pivot = np.array(tuple(H("bip01_head_13")))
    fac = float(np.clip(HEAD_SCALE_OF_WIDTH * (phi[0] - plo[0]) / (hhi[0] - hlo[0]), 1.0, FACTOR_RANGE[1]))
    log(f"  head map: human width {hhi[0] - hlo[0]:.3f}, pony skull width {phi[0] - plo[0]:.3f} "
        f"-> x{fac:.2f} around head joint {np.round(pivot, 3)}")
    # The pony muzzle is longer than a human face: the front aventail ran across the muzzle and the side plates
    # covered the cheeks. The front part below the opening is lowered under the chin and the opening widened.
    chin_z = float(head_pts[head_pts[:, 1] * FRONT_SIGN > (pivot[1] * FRONT_SIGN + 0.08), 2].min())
    front_dir = FRONT_SIGN

    def apply(p):
        q = pivot + (p - pivot) * fac
        q = q.copy()
        q[2] -= HELMET_DROP
        if q[2] > pivot[2]:  # lower dome: the horn is now in the mane, and the helmet replaces the mane
            q[2] = pivot[2] + (q[2] - pivot[2]) * HELMET_HEIGHT
        w = min(max(((q[1] - pivot[1]) * front_dir - 0.02) / 0.10, 0.0), 1.0)  # 0 at the back -> 1 at the front
        if w <= 0:
            return q
        below = min(max((pivot[2] + HELMET_OPEN_TOP - q[2]) / 0.06, 0.0), 1.0)  # 1 below the top of the opening
        q = q.copy()
        q[2] -= w * below * max(HELMET_OPENING_BOTTOM_Z - (chin_z - HELMET_CHIN_GAP), 0.0)
        q[0] *= 1 + HELMET_FACE_WIDEN * w * below
        return q

    log(f"  helmet face: chin z {chin_z:.3f}, lower front moved down {HELMET_OPENING_BOTTOM_Z - (chin_z - HELMET_CHIN_GAP):.3f}")
    return apply


def build_hands_map():
    maps = {}
    for side in ("l", "r"):
        wrist = np.array(tuple(H(f"bip01_{side}_hand_{19 if side == 'l' else 26}")))
        sign = int(np.sign(wrist[0]))  # hand side from the joint position
        shoulder = np.array(tuple(H(f"bip01_{side}_upperarm_twist_{15 if side == 'l' else 22}")))
        axis = (wrist - shoulder) / np.linalg.norm(wrist - shoulder)
        hh = human["hands"]["verts"]
        hh = hh[np.sign(hh[:, 0]) == sign]
        ph = pony["gloves"][np.sign(pony["gloves"][:, 0]) == sign]
        ph = np.array([arm_shift(p, -1.0) for p in ph])  # measure the pony hand where its bones are

        def extent(pts):
            d = (pts - wrist) @ axis
            radial = np.linalg.norm((pts - wrist) - np.outer(d, axis), axis=1)
            sel = d > 0
            return d[sel].max(), np.percentile(radial[sel], 90)

        h_len, h_rad = extent(hh)
        p_len, p_rad = extent(ph)
        k_len = np.clip(p_len / h_len, *FACTOR_RANGE)
        k_rad = np.clip(p_rad / h_rad, *FACTOR_RANGE)
        log(f"  hand {side}: length {h_len:.3f}->{p_len:.3f} (x{k_len:.2f}), thickness {h_rad:.3f}->{p_rad:.3f} (x{k_rad:.2f})")
        maps[sign] = (wrist, axis, k_len, k_rad)

    def apply(p):
        wrist, axis, k_len, k_rad = maps[1 if p[0] > 0 else -1]
        v = p - wrist
        d = v @ axis
        radial = v - d * axis
        t = min(max(d / 0.05, 0.0), 1.0)  # smoothly from the wrist to the hand
        return wrist + axis * (d * (1 + (k_len - 1) * (1.0 if d > 0 else 0.0))) + radial * (1 + (k_rad - 1) * t)

    return apply


def build_arm_shift():
    # same shift as the pony arms: from 0 at the shoulder to ARM_FORWARD at the wrist and beyond. Front is the
    # pony's face (the skeleton is rotated in the blend, so the direction is taken from neck to muzzle, not a constant).
    front = np.sign(np.median(head_pts[:, 1]) - H("bip01_head_13").y)
    arms = {}
    for side, n_sh, n_wr in (("l", 15, 19), ("r", 22, 26)):
        sh = np.array(tuple(H(f"bip01_{side}_upperarm_twist_{n_sh}")))
        wr = np.array(tuple(H(f"bip01_{side}_hand_{n_wr}")))
        arms[int(np.sign(wr[0]))] = (sh, wr - sh)
    log(f"  arm shift: {ARM_FORWARD} m towards y sign {front:+.0f}")

    def apply(p, sign=1.0):
        sh, v = arms[1 if p[0] > 0 else -1]
        t = min(max(float((p - sh) @ v) / float(v @ v), 0.0), 1.0)
        return p + np.array([0.0, sign * front * ARM_FORWARD * t, 0.0])

    return apply


SLEEVE_HIDDEN_T = (0.66, 0.74)  # fraction of shoulder -> wrist length where the vanilla sleeve goes inside the arm


def build_sleeve_keep():
    # Vanilla chest pieces squeeze the forearm sleeve inside the arm: it is covered by the hands mesh (on the pony
    # the lower forearm is in the gloves mesh too). Pushing it out turned this cloth into a crumpled tube - leave it.
    arms = {}
    for side, n_sh, n_wr in (("l", 15, 19), ("r", 22, 26)):
        sh = np.array(tuple(H(f"bip01_{side}_upperarm_twist_{n_sh}")))
        v = np.array(tuple(H(f"bip01_{side}_hand_{n_wr}"))) - sh
        arms[int(np.sign(sh[0] + v[0]))] = (sh, v)
    lo, hi = SLEEVE_HIDDEN_T

    def keep(p):
        sh, v = arms[1 if p[0] > 0 else -1]
        rel = p - sh
        t = float(rel @ v / (v @ v))
        if np.linalg.norm(rel - t * v) > 0.1:
            return 0.0
        return min(max((t - lo) / (hi - lo), 0.0), 1.0)

    return keep


EAR_CLEARANCE = 0.006  # m - helmet metal closer than this to an ear is cut away
EAR_SCRAP_FACES = 12   # pieces with fewer faces than this after the cut are treated as scraps and removed
EAR_CUT_FROM = -0.06
EAR_WHOLE_PART_FACES = 400  # a part smaller than this that touches an ear is removed entirely   # m relative to the head joint: cut the cheek plates too where the ear passes
EAR_MIN_DIST = 0.145   # m from the skull centre: beyond this are the ears (same values as in convert_twilight.py)
EAR_MIN_Z = 0.06       # m above the head joint
EAR_MIN_X = 0.06       # m from the head midline


def ear_surface():
    """Ear surface - holes in the helmet are cut along it."""
    ear = ear_mask()
    ob = pony_obj["head"]
    verts = [Vector(p) for p in head_pts]
    faces = [tuple(poly.vertices) for poly in ob.data.polygons if any(ear[i] for i in poly.vertices)]
    log(f"  ears: {ear.sum()} verts, {len(faces)} faces")
    return BVHTree.FromPolygons(verts, faces) if faces else None


def in_ear_zone(p):
    """Only the sides and the back of the head at ear level: the front must not be cut - the rim above the face disappeared."""
    hj = H("bip01_head_13")
    c = np.array([0.0, hj.y + FRONT_SIGN * 0.042, hj.z + 0.056])
    return abs(p[0]) > 0.05 and (p[1] - c[1]) * FRONT_SIGN < 0.02 and p[2] > hj.z + 0.02


def ear_hulls():
    """Convex hulls of the ears with a margin - holes are cut in the helmet along them (boolean difference)."""
    ear = ear_mask()
    objs = []
    for sign in (1, -1):
        # only the top of the ear: below are the cheek plates and mail, cutting them chopped them into scraps
        pts = head_pts[ear & (np.sign(head_pts[:, 0]) == sign)
                       & (head_pts[:, 2] > H("bip01_head_13").z + EAR_CUT_FROM)]
        if len(pts) < 8:
            continue
        c = pts.mean(0)
        grown = c + (pts - c) * (1.0 + EAR_CLEARANCE * 6)  # margin so the ear does not touch the cut edges
        bm = bmesh.new()
        for p in grown:
            bm.verts.new(Vector(p))
        bm.verts.ensure_lookup_table()
        bmesh.ops.convex_hull(bm, input=bm.verts)
        me = bpy.data.meshes.new(f"ear_hull_{sign}")
        bm.to_mesh(me)
        bm.free()
        hull = bpy.data.objects.new(me.name, me)
        scene.collection.objects.link(hull)
        objs.append(hull)
    log(f"  ear hulls: {len(objs)}")
    return objs


def cut_ear_holes_boolean(ob, hulls):
    # Boolean difference instead of deleting faces: previously the cut chopped the rim and mail into small scraps.
    for hull in hulls:
        mod = ob.modifiers.new(f"ear_{hull.name}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = hull
        mod.solver = "EXACT"
    vl.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    name = ob.data.name
    ob.data = me                      # the old mesh is not deleted: the calling code still references it
    ob.data.name = name
    for mod in list(ob.modifiers):
        if mod.name.startswith("ear_"):
            ob.modifiers.remove(mod)
    # small pieces cut off right at the ears are removed (the mail strips themselves are large, left alone)
    bm = bmesh.new()
    bm.from_mesh(me)
    seen, scrap = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, island = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf not in seen:
                        seen.add(nf)
                        stack.append(nf)
        if len(island) < EAR_SCRAP_FACES and all(
                ear_tree.find_nearest(Vector(x.calc_center_median()), 0.05)[0] is not None for x in island):
            scrap.extend(island)
    if scrap:
        bmesh.ops.delete(bm, geom=scrap, context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(me)
    bm.free()
    me.update()
    log(f"  ear holes: boolean cut, {len(me.polygons)} faces left in {ob.name}, {len(scrap)} scraps removed")
    return me


def cut_ear_holes(ob, tree):
    # Simple per-face cut: remove metal closer than EAR_CLEARANCE to an ear, only at the sides
    # and back (in_ear_zone) - attempts to cut with a boolean or to delete whole parts broke the rim.
    me = ob.data
    doomed = []
    for poly in me.polygons:
        p = Vector(poly.center)
        if not in_ear_zone(p):
            continue
        loc, normal, _, _ = tree.find_nearest(p, 0.2)
        if loc is not None and (p - loc).dot(normal) < EAR_CLEARANCE:
            doomed.append(poly.index)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in doomed], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    log(f"  ear holes: {len(doomed)} faces removed from {ob.name}")

# ---------------------------------------------------------------- inflation
def inflate(ob, tree, keep_weight=None):
    """keep_weight(p) -> 0..1: fraction by which the point is NOT pushed out (sleeve hidden inside the arm)."""
    me = ob.data
    pos = np.array([tuple(v.co) for v in me.vertices])  # armour object in world coordinates (identity matrix)
    # vertices on UV seams coincide - smooth over clusters of coincident points so the armour does not crack
    kd = KDTree(len(pos))
    for i, p in enumerate(pos):
        kd.insert(p, i)
    kd.balance()
    cluster = np.arange(len(pos))
    for i, p in enumerate(pos):
        if cluster[i] == i:
            for _, j, _ in kd.find_range(p, 1e-5):
                cluster[j] = i
    ids, inverse = np.unique(cluster, return_inverse=True)
    nbrs = [set() for _ in ids]
    for e in me.edges:
        a, b = inverse[e.vertices[0]], inverse[e.vertices[1]]
        if a != b:
            nbrs[a].add(b)
            nbrs[b].add(a)
    rep = np.array([pos[np.flatnonzero(inverse == k)[0]] for k in range(len(ids))])

    # vertices were already shifted forward together with the arms - compute the sleeve fraction in the "bone" position
    free = np.array([1.0 - (keep_weight(arm_shift(p, -1.0)) if keep_weight else 0.0) for p in rep])

    def push(points):
        disp = np.zeros_like(points)
        for k, p in enumerate(points):
            if free[k] <= 0:
                continue
            loc, normal, _, _ = tree.find_nearest(Vector(p))
            if loc is None:
                continue
            depth = (Vector(p) - loc).dot(normal)
            if depth < GAP:
                disp[k] = np.array(tuple(normal)) * (GAP - depth) * free[k]
        return disp

    disp = push(rep)
    moved = int((np.linalg.norm(disp, axis=1) > 1e-6).sum())
    peak = float(np.linalg.norm(disp, axis=1).max()) if len(disp) else 0.0
    for _ in range(SMOOTH_STEPS):
        disp = np.array([0.5 * disp[k] + 0.5 * (disp[list(nb)].mean(0) if nb else disp[k])
                         for k, nb in enumerate(nbrs)])
    rep = rep + disp * free[:, None]
    rep = rep + push(rep)  # push again what went back inside after smoothing
    for i, v in enumerate(me.vertices):
        v.co = rep[inverse[i]]
    me.update()
    log(f"  inflate: {moved}/{len(ids)} points were inside the pony, max push {peak:.3f} m")


# ---------------------------------------------------------------- processing the pieces
female_body = human["body"]["verts"]
female_legs = np.vstack([human["body"]["verts"], human["feet"]["verts"]])
pony_torso = np.vstack([body_pts[~tail_mask], pony["legs"]])

arm_shift = build_arm_shift()
maps = {
    "body": build_slice_map(female_body, pony_torso, ("l", "r", "t")),
    "legs": build_slice_map(female_legs, np.vstack([body_pts[~tail_mask], pony["legs"]]), ("l", "r")),
    "head": build_head_map(),
    "hands": build_hands_map(),
}
sleeve_keep = build_sleeve_keep()
ear_tree = ear_surface()
EAR_HULLS = ear_hulls()
targets = {
    "body": pony_surface(["body", "legs", "gloves"]),
    "legs": pony_surface(["legs", "body"]),
    "head": pony_surface(["head"], head_radius=HEAD_RADIUS),
    "hands": pony_surface(["gloves", "body"]),
}

made = []
for src_name, mode, new_name in PIECES:
    log(f"{src_name} ({mode}) -> {new_name}")
    before = set(scene.objects)
    bpy.ops.import_scene.fbx(filepath=os.path.join(ARMOR_DIR, src_name, src_name + ".fbx"),
                             automatic_bone_orientation=False, primary_bone_axis="X", secondary_bone_axis="-Y")
    new = [o for o in scene.objects if o not in before]
    vl.update()
    arm = next(o for o in new if o.type == "ARMATURE")
    # Many vanilla items have two parts: the main one and a small "_alpha" with transparent details
    # (feathers, fringe). Previously the first one found was taken - and for three items it was the small one,
    # so in game only a ring and pauldrons remained of a helmet and two chest pieces. Join all parts
    # into one mesh: it keeps its own materials, and the editor splits them into parts on import.
    parts = [o for o in new if o.type == "MESH"]
    src = max(parts, key=lambda o: len(o.data.vertices))
    if len(parts) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in parts:
            o.select_set(True)
        vl.objects.active = src
        bpy.ops.object.join()
        new = [o for o in scene.objects if o not in before]
        log(f"  частей меша: {len(parts)}, объединены ({len(src.data.vertices)} вершин, "
            f"материалы {[s.material.name for s in src.material_slots if s.material]})")
    m, fit = fit_matrix(arm, skel, turn_around=False)
    log(f"  fit: {fit}")

    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(m @ src.matrix_world)
    me.name = new_name
    ob = bpy.data.objects.new(new_name, me)
    scene.collection.objects.link(ob)
    # weights: copy the source object's groups and rename the bones to bip01_*
    ob.vertex_groups.clear()
    for g in src.vertex_groups:
        ob.vertex_groups.new(name=names.get(g.name, g.name))
    for v_src, v in zip(src.data.vertices, me.vertices):
        for g in v_src.groups:
            ob.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)

    # side check: vertices weighted to bip01_l must be on the same side as the bip01_l bone
    lg = next((g for g in ob.vertex_groups if "_l_" in g.name), None)
    if lg is not None:
        xs = [v.co.x for v in me.vertices for g in v.groups if g.group == lg.index and g.weight > 0.5]
        bone_x = H(next(b.name for b in skel.data.bones if b.name.startswith("bip01_l_thigh"))).x
        log(f"  side check: bip01_l verts mean x = {np.mean(xs) if xs else float('nan'):+.3f}, bone x = {bone_x:+.3f}")
        if xs and np.mean(xs) * bone_x < 0:
            log("  left/right weights mirrored -> swapping l/r groups")
            groups = list(ob.vertex_groups)
            for g in groups:
                g.name = "__tmp__" + g.name
            for g in groups:
                g.name = mirror_name(g.name[len("__tmp__"):])

    mapper = maps[mode]
    shift = arm_shift if mode in ("body", "hands") else (lambda p: p)
    for v in me.vertices:
        v.co = Vector(shift(mapper(np.array(tuple(v.co)))))
    me.update()
    if mode in INFLATE_MODES:
        inflate(ob, targets[mode], sleeve_keep if mode == "body" else None)
    if mode == "head" and ear_tree is not None:
        cut_ear_holes(ob, ear_tree)

    ob.parent = skel
    ob.matrix_parent_inverse = skel.matrix_world.inverted()
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = skel
    made.append(ob)
    for mat in me.materials:  # "empire_plate_armor.001" -> vanilla name, the editor finds the game material by it
        if mat is not None and "." in mat.name and mat.name.rsplit(".", 1)[1].isdigit():
            base_name = mat.name.rsplit(".", 1)[0]
            me.materials[list(me.materials).index(mat)] = bpy.data.materials.get(base_name) or mat
    if MAT_PREFIX:
        # Hive armour is coloured as chitin: the mesh must take OUR material (tools/tpac_export mat-batch),
        # not the vanilla sandy one. The editor links materials by name, so rename them.
        for i, mat in enumerate(me.materials):
            if mat is None or mat.name.startswith(MAT_PREFIX):
                continue
            name = MAT_PREFIX + mat.name
            me.materials[i] = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    log(f"  done: {len(me.vertices)} verts, materials {[mt.name if mt else None for mt in me.materials]}, groups {len(ob.vertex_groups)}")

# ---------------------------------------------------------------- export and previews
for o in scene.objects:
    o.select_set(False)
skel.select_set(True)
for o in made:
    o.select_set(True)
vl.objects.active = skel
fbx_path = os.path.join(OUT, FBX_NAME + ".fbx")
bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
log("exported", fbx_path)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, FBX_NAME + ".blend"))

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
for ob in pony_obj.values():
    ob.color = (0.78, 0.6, 0.9, 1)
for ob, color in zip(made, [(0.75, 0.75, 0.8, 1), (0.9, 0.75, 0.3, 1), (0.6, 0.65, 0.75, 1), (0.55, 0.55, 0.6, 1)]):
    ob.color = color
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
if scene.world is None:
    scene.world = bpy.data.worlds.new("w")
cam = bpy.data.objects.new("armor_cam", bpy.data.cameras.new("armor_cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = 2.1
cam.data.clip_start, cam.data.clip_end = 0.01, 100
scene.collection.objects.link(cam)
scene.camera = cam
center = Vector((0, 0, 0.98))
VIEWS = (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0)))


def render_views(prefix, views):
    for label, d in views:
        direction = Vector(d)
        cam.location = center + direction * 6
        cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(OUT, "preview", f"{prefix}_{label}.png")
        bpy.ops.render.render(write_still=True)


if len(made) <= 4:
    render_views("armor", VIEWS)
else:
    # Too many items at once cannot be examined - one shot per item (front and side).
    for ob in made:
        ob.hide_render = True
    for ob in made:
        ob.hide_render = False
        render_views(ob.name, VIEWS[:2])
        ob.hide_render = True
    for ob in made:
        ob.hide_render = False
log("done")
