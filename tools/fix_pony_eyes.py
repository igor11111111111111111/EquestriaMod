"""Pony eyes: backing in the eye sockets, blinking without broken eyelids, a round eye with any face sliders.

Run after tools/convert_twilight.py, on its result (the file is overwritten, a .before_eyes copy is kept):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python fix_pony_eyes.py
Then tools/make_changeling.py (the changeling head is a copy of this one).

What is done to the head mesh eq_twilight_head:
  1. The eyelids (eq_lid) are removed: in blink frames they opened to the bounds of the whole eyeball
     (which is much bigger than the visible eye) and stuck out of the muzzle as a huge triangle.
  2. Backing: behind each eye there is an elliptical skin-coloured "plug" slightly behind the front surface
     (of the eyeball or the skin). It covers the void in the socket near the nose, and in blink frames the
     eyeball squashes vertically into a line and reveals it — that is the closed eyelids. eq_eye = 2, UV is a
     corner of the eye cell (skin colour on ponies, chitin on changelings), face keys follow the nearest skin.
  3. Face sliders (all keys except blink 86–88) move the eyeball only as a whole: translation,
     rotation and uniform scale. Keys transferred from the human pulled its vertices unevenly — the painted
     round eye (make_changeling.py) got smeared.
"""
import math
import os
import shutil

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HEAD = "eq_twilight_head"
HEAD_BONE = "bip01_head_13"
BLINK_KEYS = {"key_086", "key_087", "key_088"}
EYE_CELL, LASH_CELL, SKIN_CELL = (3, 0), (2, 0), (3, 1)
CELL, GRID = 1024, 4
# a solid-colour patch of head skin (cell (3,1), found from the atlas): on ponies the backing is coat-coloured,
# on changelings make_changeling.py turns all head skin into chitin. The eye cell corner does not work —
# it is black in the source eye texture, and the blackness showed during blinks.
BACKING_UV = (0.798828125, 0.482177734375)
BACKING_SCALE = 1.5     # the backing is wider than the visible eye — covers the whole socket
BACKING_DEPTH = 0.02    # m behind the front surface: face sliders sink the eye, the backing must not cover it
VIEW_SIDE = 0.15


def log(*a):
    print("[eyes]", *a, flush=True)


blend = bpy.data.filepath
ob = bpy.data.objects[HEAD]
me = ob.data
RECOLOR_ONLY = any(a.value == 2 for a in me.attributes["eq_eye"].data)
if RECOLOR_ONLY:
    # the head is already processed: only update the backing UV and re-export
    _uv = me.uv_layers.active.data
    _eye = me.attributes["eq_eye"]
    for p in me.polygons:
        if all(_eye.data[i].value == 2 for i in p.vertices):
            for li in p.loop_indices:
                _uv[li].uv = BACKING_UV
    log("backing UV updated")
if not RECOLOR_ONLY:
    shutil.copyfile(blend, blend.replace(".blend", ".before_eyes.blend"))
    _fbx = os.path.join(os.path.dirname(blend), "eq_twilight.fbx")
    if os.path.exists(_fbx):
        shutil.copyfile(_fbx, _fbx.replace(".fbx", ".before_eyes.fbx"))
    mw = ob.matrix_world
    mwi = mw.inverted()


    def cell_of(u, v):
        return (min(int(u * GRID), GRID - 1), min(int(v * GRID), GRID - 1))


    # ---------------------------------------------------------------- 1. remove the eyelids
    bm = bmesh.new()
    bm.from_mesh(me)
    lid = bm.verts.layers.int.get("eq_lid")
    dead = [v for v in bm.verts if v[lid]]
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    log(f"eyelids removed: {len(dead)} verts")

    # ---------------------------------------------------------------- 2. ellipse of the visible eye
    uvd = me.uv_layers.active.data
    eye_a = me.attributes["eq_eye"]
    world = [mw @ v.co for v in me.vertices]
    skin_polys, eye_polys = [], []
    for p in me.polygons:
        c = cell_of(*uvd[p.loop_indices[0]].uv)
        if all(eye_a.data[i].value for i in p.vertices):
            eye_polys.append(list(p.vertices))
        elif c != LASH_CELL:
            skin_polys.append(list(p.vertices))
    skin_bvh = BVHTree.FromPolygons(world, skin_polys)
    front_bvh = BVHTree.FromPolygons(world, skin_polys + eye_polys)
    eye_idx = np.array([i for i in range(len(me.vertices)) if eye_a.data[i].value])
    skin_idx = np.array(sorted({i for p in skin_polys for i in p}))
    W = np.array([w[:] for w in world])

    eyes = {}
    for side in (1, -1):
        idx = eye_idx[W[eye_idx, 0] * side > 0]
        center = W[idx].mean(0)
        d = Vector((VIEW_SIDE * side, -1.0, 0.0)).normalized()
        e1 = d.cross(Vector((0, 0, 1))).normalized()
        e2 = e1.cross(d)
        front = [i for i in idx if (W[i] - center) @ np.array(d[:]) > 0]
        vis = [i for i in front if skin_bvh.ray_cast(Vector(W[i]) + d * 0.0005, d, 0.5)[0] is None]
        pts = W[vis]
        proj = np.stack([pts @ np.array(e1[:]), pts @ np.array(e2[:])], 1)
        mean = proj.mean(0)
        cov = np.cov(proj.T)
        vals, vecs = np.linalg.eigh(cov)
        radii = 2 * np.sqrt(vals)
        eyes[side] = dict(idx=idx, d=d, e1=e1, e2=e2, mean=mean, axes=vecs, radii=radii,
                          depth=float(np.median(pts @ np.array(d[:]))))
        log(f"eye {side:+d}: {len(vis)} visible verts, ellipse {radii[0] * 200:.1f} x {radii[1] * 200:.1f} cm")

    # ---------------------------------------------------------------- 3. backing
    RINGS, SEGS = 6, 32
    bm = bmesh.new()
    bm.from_mesh(me)
    uv_layer = bm.loops.layers.uv.active
    eye_layer = bm.verts.layers.int.get("eq_eye")
    deform = bm.verts.layers.deform.verify()
    head_group = ob.vertex_groups[HEAD_BONE].index
    backing_world = []
    for side, e in eyes.items():
        d, e1, e2 = e["d"], e["e1"], e["e2"]
        rings = []
        for r in range(RINGS + 1):
            f = r / RINGS
            ring = []
            for sgi in range(SEGS if r else 1):
                t = 2 * math.pi * sgi / SEGS
                local = e["axes"] @ np.array([math.cos(t) * e["radii"][0], math.sin(t) * e["radii"][1]]) * f * BACKING_SCALE
                x, y = e["mean"] + local
                on_plane = e1 * x + e2 * y + d * (e["depth"] + 0.3)
                hit = front_bvh.ray_cast(on_plane, -d, 1.0)[0]
                pos = (hit - d * BACKING_DEPTH) if hit is not None else (e1 * x + e2 * y + d * (e["depth"] - 0.01))
                v = bm.verts.new(mwi @ pos)
                v[eye_layer] = 2
                v[deform][head_group] = 1.0
                backing_world.append(pos)
                ring.append(v)
            rings.append(ring)
        for r in range(RINGS):
            inner, outer = rings[r], rings[r + 1]
            for sgi in range(SEGS):
                a = inner[0] if r == 0 else inner[sgi]
                b = inner[0] if r == 0 else inner[(sgi + 1) % SEGS]
                quad = [a, outer[sgi], outer[(sgi + 1) % SEGS]] + ([] if r == 0 else [b])
                for verts in (quad, quad[::-1]):  # double-sided
                    try:
                        f = bm.faces.new(verts)
                    except ValueError:
                        continue
                    f.smooth = True
                    for loop in f.loops:
                        loop[uv_layer].uv = BACKING_UV
    bm.to_mesh(me)
    bm.free()
    me.update()
    eye_a = me.attributes["eq_eye"]
    backing = np.array([i for i in range(len(me.vertices)) if eye_a.data[i].value == 2])
    eyeball = np.array([i for i in range(len(me.vertices)) if eye_a.data[i].value == 1])
    log(f"backing: {len(backing)} verts")

    # ---------------------------------------------------------------- 4. face keys
    keys = me.shape_keys.key_blocks
    basis = np.array([v.co[:] for v in keys[0].data])
    n = len(basis)
    world_basis = np.array([(mw @ Vector(p))[:] for p in basis])
    uvd = me.uv_layers.active.data
    skin_verts = sorted({me.loops[li].vertex_index for p in me.polygons for li in p.loop_indices
                         if cell_of(*uvd[p.loop_indices[0]].uv) == SKIN_CELL})
    # The backing moves with the nearest vertices of the FRONT part of the eyeball: then with any face
    # sliders it stays behind the eye. Binding it to the skin pushed it in front of the eye.
    front_eye = []
    for s_ in (1, -1):
        idx = eyeball[world_basis[eyeball, 0] * s_ > 0]
        cy = world_basis[idx, 1].mean()
        front_eye.extend(int(i) for i in idx if world_basis[i, 1] < cy)
    kd = KDTree(len(front_eye))
    for i in front_eye:
        kd.insert(Vector(basis[i]), i)
    kd.balance()
    near = {int(b): [h[1] for h in kd.find_n(Vector(basis[b]), 8)] for b in backing}

    # EYES_RIGID: sliders move the eyeball only as a whole (needed for the painted round eye,
    # PONY_ROUND_EYES in make_changeling.py). With the source eye texture it is off: eye expressions as before.
    EYES_RIGID = False


    def similarity(src, dst):
        """Umeyama: dst ≈ s R src + t."""
        ms, md = src.mean(0), dst.mean(0)
        a, b = src - ms, dst - md
        u, sig, vt = np.linalg.svd(b.T @ a / len(src))
        sgn = np.ones(3)
        if np.linalg.det(u) * np.linalg.det(vt) < 0:
            sgn[2] = -1
        rot = u @ np.diag(sgn) @ vt
        scale = (sig * sgn).sum() / max((a ** 2).sum() / len(src), 1e-12)
        return scale, rot, md - scale * rot @ ms


    sides = {s_: eyeball[world_basis[eyeball, 0] * s_ > 0] for s_ in (1, -1)}
    for kb in keys[1:]:
        co = np.empty(n * 3)
        kb.data.foreach_get("co", co)
        co = co.reshape(n, 3)
        if EYES_RIGID and kb.name not in BLINK_KEYS:
            for s_, idx in sides.items():
                scale, rot, t = similarity(basis[idx], co[idx])
                co[idx] = (scale * (rot @ basis[idx].T)).T + t
        for b_, nb in near.items():
            # when blinking the eyeball flattens — the backing (closed eyelids) stays in place
            co[b_] = basis[b_] if kb.name in BLINK_KEYS else basis[b_] + (co[nb] - basis[nb]).mean(0)
        kb.data.foreach_set("co", co.ravel())
    log(f"face keys: eyeballs {'rigid' if EYES_RIGID else 'as transferred'}, backing follows the front of the eyeball")

    # backing normals face the viewer (otherwise the new corners get a zero custom normal)
    normals = [cn.vector.copy() for cn in me.corner_normals]
    back_set = set(int(i) for i in backing)
    for poly in me.polygons:
        if poly.vertices[0] in back_set:
            for li in poly.loop_indices:
                normals[li] = poly.normal.copy()
    me.normals_split_custom_set([n_[:] for n_ in normals])

# ---------------------------------------------------------------- 5. export as in convert_twilight.py
skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
items = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("eq_twilight_")]
bpy.ops.object.select_all(action="DESELECT")
for o in [skel, *items]:
    o.select_set(True)
bpy.context.view_layer.objects.active = skel
fbx = os.path.join(os.path.dirname(blend), "eq_twilight.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y")
log("exported", fbx, [o.name for o in items])
bpy.ops.wm.save_mainfile()
log("saved", blend)
