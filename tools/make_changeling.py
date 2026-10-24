"""A rank-and-file changeling based on our anthro pony (our own model, no third-party meshes).

Run (headless Blender, opens the finished pony):
  blender --background ../assets/twilight_anthro/export/eq_twilight.blend --python make_changeling.py -- ../assets/changeling

What gets built (references - cartoon frames in assets/reference/changeling/images):
  eq_changeling_head   - the pony head (a face with 101 facial keys): no eyelashes, faceted blue eyes, two fangs;
  eq_changeling_body / _legs / _gloves - the pony body in black chitin, holes on the shins and forearms;
  eq_changeling_crest  - a serrated horn and a spiky crest (helmet slot, like the pony mane), head bone;
  eq_changeling_horn   - the horn only (helmet slot for those who wear a real hairstyle, tools/make_changeling_hair.py);
  eq_changeling_wings  - dragonfly wings with holes (back) and a short spiky tail (pelvis), cape slot;
  eq_chrysalis_crown   - the queen's horn and a crown with turquoise orbs (helmet slot, Chrysalis only).

Everything is on the shared material eq_twilight_body: the details are painted in two free cells of the pony atlas
(cells (2,3) - eyes and (3,3) - chitin, fangs, holes, wings). The chitin colour is in the texture, so the race's
coat palette is light: otherwise the engine would darken the eyes and fangs together with the coat.
The atlas with the new cells is written to <out>/textures/eq_twilight_body_d.png - it has to be reimported
in the editor in place of the pony texture. After convert_twilight.py is rerun this script must be run again.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)

MAT = "eq_twilight_body"
CELL, GRID = 1024, 4
HEAD_BONE, SPINE_BONE, PELVIS_BONE = "bip01_head_13", "bip01_spine2_11", "bip01_pelvis_0"
EYE_CELL, PARTS_CELL = (2, 3), (3, 3)   # free atlas cells (column, row from the bottom)
COAT_CELLS = {(0, 0), (0, 1), (0, 2), (2, 2), (3, 1)}  # coat, hooves, gloves, head skin
EYES_SRC_CELL, LASH_CELL = (3, 0), (2, 0)


def log(*a):
    print("[changeling]", *a, flush=True)


skel = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pony = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
bones = {b.name: skel.matrix_world @ b.head_local for b in skel.data.bones}
vl = bpy.context.view_layer


# ---------------------------------------------------------------- parts cell regions (cell pixels, from bottom)
REGIONS = {
    "chitin": (0, 0, 512, 512),      # x: 0 - matte, 1 - blue sheen on the ridges; y: 0 - bottom of the body, 1 - top
    "fang": (512, 256, 768, 512),
    "hole": (768, 256, 1024, 512),
    "glow": (512, 0, 1024, 256),
    "wing": (0, 512, 1024, 1024),    # x - along the wing from the root, y - across (-W..W)
}
INSET = 12


def region_uv(name, fx, fy, cell=PARTS_CELL):
    x0, y0, x1, y1 = REGIONS[name]
    px = x0 + INSET + min(max(fx, 0.0), 1.0) * (x1 - x0 - 2 * INSET)
    py = y0 + INSET + min(max(fy, 0.0), 1.0) * (y1 - y0 - 2 * INSET)
    return ((cell[0] * CELL + px) / (CELL * GRID), (cell[1] * CELL + py) / (CELL * GRID))


def chitin_uv(height01, sheen01=0.1):
    return region_uv("chitin", sheen01, height01)


def cell_of(u, v):
    return (min(int(u * GRID), GRID - 1), min(int(v * GRID), GRID - 1))


# ---------------------------------------------------------------- wing shape (shared by the mesh and the texture)
WING_LEN, WING_W = 0.46, 0.10
WING_HOLES = [(0.36, -0.012, 0.050, 0.020), (0.55, 0.006, 0.055, 0.026), (0.73, -0.004, 0.040, 0.016)]


def wing_half(s):
    """Wing half-width (m) at point s (0 - root, 1 - tip): the upper (leading) and lower (ragged) edges."""
    s = np.clip(s, 0.0, 1.0)
    base = WING_W * (s ** 0.6) * ((1.0 - s) ** 0.5) / 0.468 + 0.012 * (1.0 - s)
    saw = np.mod(s * 4.0 + 0.3, 1.0) ** 1.6
    return base * 0.72, base * (1.0 - 0.42 * saw * (s > 0.15))


# ---------------------------------------------------------------- 1. textures in the atlas
atlas_src = bpy.data.images[f"{MAT}_d"] if f"{MAT}_d" in bpy.data.images else next(
    n.image for n in bpy.data.materials[MAT].node_tree.nodes if n.type == "TEX_IMAGE")
W, H = atlas_src.size
atlas = np.empty(W * H * 4, dtype=np.float32)
atlas_src.pixels.foreach_get(atlas)
atlas = atlas.reshape(H, W, 4)


def cell_view(col, row):
    return atlas[row * CELL:(row + 1) * CELL, col * CELL:(col + 1) * CELL]


def mix(a, b, t):
    t = np.clip(t, 0.0, 1.0)[..., None]
    return np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t


def ramp(t, stops):
    """t: array 0..1, stops: [(position, (r,g,b))]"""
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        out[m] = mix(c0, c1, (t[m] - p0) / max(p1 - p0, 1e-6))
    out[t < stops[0][0]] = stops[0][1]
    out[t > stops[-1][0]] = stops[-1][1]
    return out


def hex_pattern(x, y, size):
    """0..1: cells of a faceted eye - light centres, dark seams"""
    q = (x * 0.57735 * 2) / size
    r = (y - x * 0.57735) / size
    cx, cy = q, r
    fx, fy = cx - np.round(cx), cy - np.round(cy)
    d = np.maximum(np.abs(fx), np.maximum(np.abs(fy), np.abs(fx + fy)))
    return np.clip(1.0 - d * 1.6, 0.0, 1.0)


yy, xx = np.mgrid[0:CELL, 0:CELL].astype(np.float32)

# ---------------------------------------------------------------- eyes: a round outline
# The eye is seen through a hole in the head skin, and the hole's edge is a polyline of few edges: hence the angular
# eyes in game. So we redraw the eye: we find which pixels of the eyeball texture are visible from the front
# through the hole (a ray from the eyeball point to the viewer does not hit the skin), fit a smooth ellipse into
# that area (in screen coordinates, so it is round on screen, not in the UV map) and draw the eye strictly inside it.
# Outside - the skin colour: the hole's edge lands on the same colour and disappears.
# The same layout for the pony (cell (3,0)) and the changeling (cell (2,3)) - the head meshes are identical.
EYE_VIEW_SIDE = 0.15   # the eye looks forward and slightly outward
EYE_FIT_VISIBLE = 0.985  # share of visible pixels inside the ellipse
# Pony: False - Twilight's original eye drawing (the user likes it more than the painted round one),
# True - the painted round eye. The underlay and blinking (tools/fix_pony_eyes.py) work in both cases.
PONY_ROUND_EYES = False
EYE_FILL = 1.0  # 0 - inscribed ellipse (smaller, but round everywhere), 1 - fills the whole eye socket
EYE_SIZE = 1.08  # on top of that - even larger (the edges go under the skin)
EYE_RAISE = 0.10  # eye centre higher by a fraction of its height


def eye_maps():
    """-> ell: for an eye-cell pixel, the distance in ellipse fractions (0 - centre, 1 - edge, inf - not an eye);
    ux, uy: coordinates inside the ellipse along the screen axes (x - across, y - up), side: the side (+1/-1)."""
    ob = pony["eq_twilight_head"]
    me = ob.data
    uvd = me.uv_layers.active.data
    eye_a, lid_a = me.attributes["eq_eye"], me.attributes["eq_lid"]
    world = [ob.matrix_world @ v.co for v in me.vertices]
    occluders, eye_polys = [], []
    for p in me.polygons:
        u, v = uvd[p.loop_indices[0]].uv
        c = cell_of(u, v)
        if any(lid_a.data[i].value for i in p.vertices):
            continue  # the eyelids in the basis shape are squeezed above the eye and hidden
        if all(eye_a.data[i].value for i in p.vertices):
            # 1 - eyeball, 2 - underlay in the eye socket (tools/fix_pony_eyes.py): it is not painted
            if c == EYES_SRC_CELL and all(eye_a.data[i].value == 1 for i in p.vertices):
                eye_polys.append(p)
            continue
        if c == LASH_CELL:
            continue  # thin eyelashes do not cover the eye
        occluders.append(list(p.vertices))
    bvh = BVHTree.FromPolygons(world, occluders)

    pos = np.full((CELL, CELL, 3), np.nan, np.float32)
    col0, row0 = EYES_SRC_CELL
    for p in eye_polys:
        uvs = np.array([((uvd[li].uv[0] * GRID - col0) * CELL - 0.5, (uvd[li].uv[1] * GRID - row0) * CELL - 0.5)
                        for li in p.loop_indices])
        ws = np.array([world[i][:] for i in p.vertices])
        for k in range(1, len(ws) - 1):
            tri, tw = uvs[[0, k, k + 1]], ws[[0, k, k + 1]]
            x0, y0 = np.maximum(np.floor(tri.min(0)).astype(int), 0)
            x1, y1 = np.minimum(np.ceil(tri.max(0)).astype(int), CELL - 1)
            if x1 < x0 or y1 < y0:
                continue
            gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
            (ax, ay), (bx, by), (cx, cy) = tri
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            l3 = 1 - l1 - l2
            ins = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
            if ins.any():
                pts = l1[..., None] * tw[0] + l2[..., None] * tw[1] + l3[..., None] * tw[2]
                pos[gy[ins], gx[ins]] = pts[ins]

    covered = ~np.isnan(pos[..., 0])
    ell = np.full((CELL, CELL), np.inf, np.float32)
    ux = np.zeros((CELL, CELL), np.float32)
    uy = np.zeros((CELL, CELL), np.float32)
    side_map = np.zeros((CELL, CELL), np.int8)
    xs_all = np.nan_to_num(pos[..., 0])
    for side in (1, -1):
        ys, xs = np.nonzero(covered & (xs_all * side > 0))
        d = Vector((EYE_VIEW_SIDE * side, -1.0, 0.0)).normalized()
        e1 = d.cross(Vector((0.0, 0.0, 1.0))).normalized()
        e2 = e1.cross(d)
        basis = np.array([e1[:], e2[:]])
        pts = pos[ys, xs]
        proj = pts @ basis.T
        sub = (ys % 3 == 0) & (xs % 3 == 0)
        sample = pts[sub]
        visible = np.array([bvh.ray_cast(Vector(p) + d * 0.0005, d, 0.5)[0] is None for p in sample])
        # keep the largest connected patch of the visible area (at the temple the eyeball also peeks out from the side)
        visible &= largest_blob(proj[sub], visible)
        vis_proj = proj[sub][visible]
        mean = vis_proj.mean(0)
        cov = np.cov(vis_proj.T)
        inv = np.linalg.inv(cov)
        q = proj[sub] - mean
        val = np.einsum("ij,jk,ik->i", q, inv, q) / 4.0  # for a uniform ellipse the variance = semi-axis²/4
        # only the front layer of the eyeball counts: back points project to the same place,
        # but the front always covers them
        depth = sample @ np.array(d[:])
        cells = np.floor(proj[sub] / 0.002).astype(int)
        front_depth = {}
        for key, dep in zip(map(tuple, cells), depth):
            front_depth[key] = max(front_depth.get(key, -9.0), dep)
        front = np.array([dep >= front_depth[key] - 0.004 for key, dep in zip(map(tuple, cells), depth)])
        k_in = 0.5  # inscribed ellipse: almost all of it is visible
        for k in np.arange(1.0, 0.5, -0.01):
            inside = (val <= k * k) & front
            if inside.any() and visible[inside].mean() >= EYE_FIT_VISIBLE:
                k_in = k
                break
        k_out = 1.5  # circumscribed: takes in almost the whole visible eye socket
        vis_val = val[front & visible]
        for k in np.arange(0.5, 1.5, 0.01):
            if (vis_val <= k * k).mean() >= 0.97:
                k_out = k
                break
        # the eye fills almost the whole socket (as before the rounding): the ellipse edge goes under the skin in places
        scale = (k_in + (k_out - k_in) * EYE_FILL) * EYE_SIZE
        mean = mean + np.array([0.0, EYE_RAISE * 2.0 * scale * np.sqrt(cov[1, 1])])
        qa = proj - mean
        ell[ys, xs] = np.sqrt(np.einsum("ij,jk,ik->i", qa, inv, qa) / 4.0) / scale
        ext = 2.0 * scale * np.sqrt(np.diag(cov))  # ellipse half-extent along the screen axes
        ux[ys, xs] = qa[:, 0] / ext[0] * side  # for both eyes x grows toward the temple
        uy[ys, xs] = qa[:, 1] / ext[1]
        side_map[ys, xs] = side
        log(f"eye {side:+d}: visible {visible.mean():.2f} of eyeball texels, ellipse scale {scale:.2f} "
            f"(inscribed {k_in:.2f}, whole socket {k_out:.2f}), "
            f"size {ext[0] * 2 * 100:.1f} x {ext[1] * 2 * 100:.1f} cm")
    return ell, ux, uy, covered


def largest_blob(points, mask, cell=0.002):
    """Mask of the points that fall into the largest connected region (a grid of cell metres) among the marked ones."""
    keys = [tuple(k) for k in np.floor(points / cell).astype(int)]
    occupied = {k for k, m in zip(keys, mask) if m}
    best, seen = set(), set()
    for start in occupied:
        if start in seen:
            continue
        blob, stack = set(), [start]
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            blob.add((cx, cy))
            for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if n in occupied and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if len(blob) > len(best):
            best = blob
    return np.array([k in best for k in keys])


def smooth_edge(x, edge, width):
    """0 inside (x < edge - width), 1 outside, smooth in between - an anti-aliased edge without staircase."""
    return np.clip((x - (edge - width)) / width, 0.0, 1.0)


ell, eux, euy, eye_cov = eye_maps()
finite = np.isfinite(ell)
r = np.where(finite, ell, 9.0)

# pony: a cartoon eye - sclera, purple iris (like Twilight's), pupil, highlights, dark outline
head_cell = cell_view(3, 1)[..., :3]
bright = head_cell[head_cell.max(-1) > 0.3]
COAT_GRAY = np.median(bright, axis=0) if len(bright) else np.array([0.9, 0.9, 0.9], np.float32)
pony_eye = np.empty((CELL, CELL, 3), np.float32)
pony_eye[:] = COAT_GRAY
sclera = np.array([0.97, 0.97, 0.98], np.float32)
# A large iris filling almost the whole eye and a big pupil, as for the ponies in the cartoon. The centre is almost
# in the middle: a small iris shifted toward the nose looked cross-eyed and scary in game.
# a gaze like the original Twilight's: slightly down and toward the nose, the pupil large and almost black
IRIS_X, IRIS_Y = -0.12, -0.06
iris_d = np.sqrt(((eux - IRIS_X) / 0.78) ** 2 + ((euy - IRIS_Y) / 1.0) ** 2)
pupil_d = np.sqrt(((eux - IRIS_X) / 0.52) ** 2 + ((euy - IRIS_Y) / 0.74) ** 2)
iris_col = mix((0.26, 0.10, 0.46), (0.80, 0.60, 1.00), (0.45 - euy * 0.55))
iris_col = mix(iris_col, (0.18, 0.06, 0.30), smooth_edge(iris_d, 1.0, 0.10))  # dark rim of the iris
col = mix(np.broadcast_to(sclera, pony_eye.shape), iris_col, 1.0 - smooth_edge(iris_d, 1.0, 0.03))
col = mix(col, (0.03, 0.01, 0.05), 1.0 - smooth_edge(pupil_d, 1.0, 0.05))
for hx, hy, hr in ((IRIS_X - 0.22, 0.34, 0.20), (IRIS_X + 0.22, -0.34, 0.09)):  # highlights
    hd = np.sqrt((eux - hx) ** 2 + (euy - hy) ** 2) / hr
    col = mix(col, (1.0, 1.0, 1.0), 1.0 - smooth_edge(hd, 1.0, 0.2))
col = mix(col, (0.06, 0.04, 0.08), smooth_edge(r, 0.93, 0.03))  # eye outline
pony_eye = mix(col, COAT_GRAY, smooth_edge(r, 1.0, 0.02))
pony_eye[~finite] = COAT_GRAY
if PONY_ROUND_EYES:
    cell_view(*EYES_SRC_CELL)[..., :3] = pony_eye

# changeling: a glowing faceted eye without a pupil, chitin background
EYE_BG = (0.02, 0.022, 0.03)
EYE_STOPS = [(0.0, (0.80, 1.00, 1.00)), (0.35, (0.45, 0.95, 1.00)), (0.7, (0.12, 0.72, 0.95)),
             (0.92, (0.05, 0.45, 0.78)), (1.0, (0.02, 0.25, 0.50))]
glow_center = np.sqrt((eux + 0.05) ** 2 + (euy - 0.12) ** 2)
glow = ramp(np.clip(np.minimum(r, glow_center * 1.1), 0, 1), EYE_STOPS)
glow *= (0.86 + 0.14 * hex_pattern(xx, yy, 34.0))[..., None]
glow = mix(glow, (0.01, 0.12, 0.25), smooth_edge(r, 0.95, 0.04))
ch_eye = mix(glow, EYE_BG, smooth_edge(r, 1.0, 0.02))
ch_eye[~finite] = EYE_BG
eye = np.ones((CELL, CELL, 4), np.float32)
eye[..., :3] = ch_eye
cell_view(*EYE_CELL)[:] = eye
log(f"eye cells: {int(eye_cov.sum())} eyeball pixels, coat gray {np.round(COAT_GRAY, 3)}")

parts = np.zeros((CELL, CELL, 4), np.float32)
parts[..., 3] = 1.0


def paint(name, fn):
    x0, y0, x1, y1 = REGIONS[name]
    fx = (xx[y0:y1, x0:x1] - x0 - INSET) / (x1 - x0 - 2 * INSET)
    fy = (yy[y0:y1, x0:x1] - y0 - INSET) / (y1 - y0 - 2 * INSET)
    parts[y0:y1, x0:x1, :3] = fn(np.clip(fx, 0, 1), np.clip(fy, 0, 1))


# chitin: almost black with a cold sheen, slightly lighter toward the top; on the right - a blue sheen for the ridges
paint("chitin", lambda fx, fy: mix(mix((0.018, 0.020, 0.028), (0.070, 0.078, 0.105), fy),
                                   (0.10, 0.20, 0.42), fx ** 1.5))
paint("fang", lambda fx, fy: mix((0.72, 0.74, 0.78), (0.97, 0.97, 0.98), fy))
# hole: you can "see" through it - a dull blue spot in a dark rim
paint("hole", lambda fx, fy: ramp(np.sqrt((fx - 0.5) ** 2 + (fy - 0.5) ** 2) * 2,
                                  [(0.0, (0.26, 0.36, 0.46)), (0.6, (0.18, 0.26, 0.36)),
                                   (0.8, (0.03, 0.04, 0.06)), (1.0, (0.02, 0.02, 0.03))]))
paint("glow", lambda fx, fy: mix((0.20, 0.80, 0.95), (0.70, 1.0, 1.0), fy))


def wing_tex(fx, fy):
    s = fx
    t = (fy * 2 - 1) * WING_W
    up, low = wing_half(s)
    edge = np.where(t >= 0, up, low)
    rel = np.abs(t) / np.maximum(edge, 1e-4)
    col = mix((0.62, 0.95, 0.97), (0.30, 0.78, 0.86), rel)
    for k in (-0.75, -0.4, 0.0, 0.35, 0.7):
        line = k * WING_W * 0.8 * s ** 0.8
        col = mix(col, (0.10, 0.45, 0.55), (np.abs(t - line) < 0.0022) * 0.8 * (s > 0.04))
    col = mix(col, (0.06, 0.32, 0.42), np.clip((rel - 0.82) / 0.1, 0, 1))
    for hs, ht, hr, hw in WING_HOLES:
        dh = np.sqrt(((s - hs) / hr) ** 2 + ((t - ht) / hw) ** 2)
        col = mix(col, (0.06, 0.32, 0.42), ((dh > 0.9) & (dh < 1.35)) * 1.0)
    return col


paint("wing", wing_tex)
cell_view(*PARTS_CELL)[:] = parts

atlas_img = bpy.data.images.new(f"{MAT}_d_changeling", W, H, alpha=False)
atlas_img.pixels.foreach_set(atlas.ravel())
atlas_img.filepath_raw = os.path.join(OUT, "textures", f"{MAT}_d.png")
atlas_img.file_format = "PNG"
atlas_img.save()
log("atlas saved", atlas_img.filepath_raw)


# ---------------------------------------------------------------- face variant: the queen (Chrysalis)
# The face material is chosen per character (face_textures in skins.xml, the "face" slider
# in the appearance editor) - verified in game 18.09.2026. So the queen's eyes are made not as a new race
# but as a second atlas: everything the same except the eye cell. The colours are taken from the reference
# assets/reference/chrysalis (mint sclera, green iris, dark vertical pupil).
QUEEN_SCLERA = (0.71, 0.95, 0.81)
QUEEN_IRIS_LO = (0.28, 0.62, 0.22)   # toward the edge of the iris
QUEEN_IRIS_HI = (0.72, 0.88, 0.25)   # toward the bottom, yellow-green
QUEEN_PUPIL = (0.02, 0.26, 0.22)     # dark green oval
QUEEN_SLIT = (0.01, 0.12, 0.10)      # slit inside the oval
QUEEN_GLINT = (0.62, 1.00, 0.86)


def queen_eye_cell():
    iris_d = np.sqrt(((eux + 0.05) / 0.58) ** 2 + ((euy + 0.04) / 0.80) ** 2)
    pupil_d = np.sqrt(((eux + 0.05) / 0.30) ** 2 + ((euy + 0.04) / 0.64) ** 2)
    slit_d = np.sqrt(((eux + 0.05) / 0.09) ** 2 + ((euy + 0.04) / 0.52) ** 2)
    iris = mix(QUEEN_IRIS_LO, QUEEN_IRIS_HI, np.clip(0.55 - euy * 0.7, 0, 1))
    col = mix(np.broadcast_to(np.array(QUEEN_SCLERA, np.float32), iris.shape),
              iris, 1.0 - smooth_edge(iris_d, 1.0, 0.04))
    col = mix(col, QUEEN_PUPIL, 1.0 - smooth_edge(pupil_d, 1.0, 0.05))
    col = mix(col, QUEEN_SLIT, 1.0 - smooth_edge(slit_d, 1.0, 0.08))
    hd = np.sqrt((eux + 0.34) ** 2 + (euy - 0.40) ** 2) / 0.15   # mint highlight at the top near the nose
    col = mix(col, QUEEN_GLINT, 1.0 - smooth_edge(hd, 1.0, 0.25))
    col = mix(col, (0.03, 0.14, 0.12), smooth_edge(r, 0.93, 0.03))  # dark eye outline
    out = np.ones((CELL, CELL, 4), np.float32)
    out[..., :3] = mix(col, EYE_BG, smooth_edge(r, 1.0, 0.02))
    out[~finite, :3] = EYE_BG
    return out


queen = atlas.copy()
queen[EYE_CELL[1] * CELL:(EYE_CELL[1] + 1) * CELL, EYE_CELL[0] * CELL:(EYE_CELL[0] + 1) * CELL] = queen_eye_cell()
queen_img = bpy.data.images.new("eq_changeling_queen_d_img", W, H, alpha=False)
queen_img.pixels.foreach_set(queen.ravel())
queen_img.filepath_raw = os.path.join(OUT, "textures", "eq_changeling_queen_d.png")
queen_img.file_format = "PNG"
queen_img.save()
log("queen atlas saved", queen_img.filepath_raw)


# ---------------------------------------------------------------- 2. skin meshes: copies of the pony with a new layout
def copy_object(src, name):
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    bpy.context.scene.collection.objects.link(ob)
    return ob


def remap_skin(ob, keep_cells=()):
    me = ob.data
    uv = me.uv_layers.active.data
    eye_attr = me.attributes.get("eq_eye")
    lid_attr = me.attributes.get("eq_lid")
    zmax = 1.9
    counts = {}
    for poly in me.polygons:
        c = cell_of(sum(uv[li].uv[0] for li in poly.loop_indices) / poly.loop_total,
                    sum(uv[li].uv[1] for li in poly.loop_indices) / poly.loop_total)
        is_eye = eye_attr is not None and all(eye_attr.data[v].value for v in poly.vertices)
        is_lid = lid_attr is not None and any(lid_attr.data[v].value for v in poly.vertices)
        if c == EYES_SRC_CELL and is_eye:
            kind = "eye"
            for li in poly.loop_indices:
                u, v = uv[li].uv
                uv[li].uv = (u + (EYE_CELL[0] - EYES_SRC_CELL[0]) / GRID, v + (EYE_CELL[1] - EYES_SRC_CELL[1]) / GRID)
        elif c in COAT_CELLS or is_lid:
            kind = "chitin"
            for li, vi in zip(poly.loop_indices, poly.vertices):
                z = (ob.matrix_world @ me.vertices[vi].co).z
                uv[li].uv = chitin_uv(z / zmax, 0.08)
        else:
            kind = f"keep{c}"
        counts[kind] = counts.get(kind, 0) + 1
    log(f"  {ob.name}: {counts}")


def delete_polys(ob, predicate):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    lid = bm.verts.layers.int.get("eq_lid")
    dead = [f for f in bm.faces if predicate(f, uv, lid)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(dead)


def is_lash(f, uv, lid):
    c = cell_of(sum(l[uv].uv[0] for l in f.loops) / len(f.loops), sum(l[uv].uv[1] for l in f.loops) / len(f.loops))
    return c == LASH_CELL and not (lid and any(v[lid] for v in f.verts))


# ---------------------------------------------------------------- 3. building the parts
class Builder:
    """Geometry accumulator in world coordinates: vertices with uv and a single bone."""

    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.bone = self.bm.verts.layers.int.new("eq_bone")
        self.bones = []
        self.tag = self.bm.verts.layers.int.new("eq_part")

    def bone_id(self, name):
        if name not in self.bones:
            self.bones.append(name)
        return self.bones.index(name)

    def face(self, pts, uvs, bone, tag=0):
        bi = self.bone_id(bone)
        vs = []
        for p in pts:
            v = self.bm.verts.new(p)
            v[self.bone] = bi
            v[self.tag] = tag
            vs.append(v)
        f = self.bm.faces.new(vs)
        for loop, uvv in zip(f.loops, uvs):
            loop[self.uv].uv = uvv
        return f

    def loft(self, path, rx, ry, ref, uv_fn, bone, segs=8, cap=True, tag=0):
        """A tube along the path points with an elliptical cross-section (rx along ref×T, ry - across), a spike at the end."""
        rings = []
        n = len(path)
        first = len(self.bm.verts)
        for i, p in enumerate(path):
            t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
            u = ref.cross(t).normalized()
            w = t.cross(u)
            ring = []
            for k in range(segs):
                a = 2 * math.pi * k / segs
                ring.append(p + u * (math.cos(a) * rx[i]) + w * (math.sin(a) * ry[i]))
            rings.append(ring)
        for i in range(n - 1):
            for k in range(segs):
                k2 = (k + 1) % segs
                a0, a1 = 2 * math.pi * k / segs, 2 * math.pi * k2 / segs
                pts = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
                uvs = [uv_fn(i / (n - 1), a0), uv_fn(i / (n - 1), a1),
                       uv_fn((i + 1) / (n - 1), a1), uv_fn((i + 1) / (n - 1), a0)]
                if rx[i + 1] < 1e-6 and ry[i + 1] < 1e-6:
                    self.face(pts[:2] + pts[2:3], uvs[:3], bone, tag)
                else:
                    self.face(pts, uvs, bone, tag)
        if cap:
            c = sum(rings[0], Vector()) / segs
            for k in range(segs):
                k2 = (k + 1) % segs
                self.face([c, rings[0][k2], rings[0][k]],
                          [uv_fn(0, 0), uv_fn(0, 0), uv_fn(0, 0)], bone, tag)
        # stitch the rings and turn the normals outward (the engine does not draw back faces)
        self.bm.verts.ensure_lookup_table()
        new = self.bm.verts[first:]
        bmesh.ops.remove_doubles(self.bm, verts=list(new), dist=1e-7)
        self.bm.verts.ensure_lookup_table()
        faces = {f for v in self.bm.verts[first:] for f in v.link_faces}
        bmesh.ops.recalc_face_normals(self.bm, faces=list(faces))

    def plane(self, outline, holes, frame, uv_fn, bone, tag=0, thickness=0.0012):
        """A flat shape with holes (filled via a 2D curve) in the plane frame=(origin, X, Y), double-sided."""
        cu = bpy.data.curves.new("eq_tmp_curve", "CURVE")
        cu.dimensions = "2D"
        cu.fill_mode = "BOTH"
        for loop in [outline] + holes:
            sp = cu.splines.new("POLY")
            sp.points.add(len(loop) - 1)
            for p, (x, y) in zip(sp.points, loop):
                p.co = (x, y, 0.0, 1.0)
            sp.use_cyclic_u = True
        tmp = bpy.data.objects.new("eq_tmp_curve", cu)
        bpy.context.scene.collection.objects.link(tmp)
        vl.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        origin, ax, ay = frame
        normal = ax.cross(ay).normalized()
        for side in (1, -1):
            for poly in me.polygons:
                co2 = [me.vertices[i].co for i in poly.vertices]
                if side < 0:
                    co2 = co2[::-1]
                pts = [origin + ax * c.x + ay * c.y + normal * (side * thickness / 2) for c in co2]
                self.face(pts, [uv_fn(c.x, c.y) for c in co2], bone, tag)
        bpy.data.objects.remove(tmp)
        bpy.data.curves.remove(cu)
        bpy.data.meshes.remove(me)

    def to_object(self, name):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-6)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        me.materials.append(bpy.data.materials[MAT])
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        groups = [ob.vertex_groups.new(name=b) for b in self.bones]
        attr = me.attributes["eq_bone"]
        for v in me.vertices:
            groups[attr.data[v.index].value].add([v.index], 1.0, "REPLACE")
        me.attributes.remove(me.attributes["eq_bone"])
        for poly in me.polygons:
            poly.use_smooth = True
        return ob


def world_verts(ob, poly_filter=None):
    me = ob.data
    uv = me.uv_layers.active.data
    idx = set()
    for poly in me.polygons:
        if poly_filter is None or poly_filter(cell_of(uv[poly.loop_indices[0]].uv[0], uv[poly.loop_indices[0]].uv[1])):
            idx.update(poly.vertices)
    idx = sorted(idx)
    return idx, np.array([(ob.matrix_world @ me.vertices[i].co)[:] for i in idx])


head_src = pony["eq_twilight_head"]
mane_src = pony["eq_twilight_mane"]
_, skin_pts = world_verts(head_src, lambda c: c == (3, 1))
_, teeth_pts = world_verts(head_src, lambda c: c == (0, 3))
_, horn_pts = world_verts(mane_src, lambda c: c == (1, 2))

# horn: the axis from the middle of the base to the tip of the unicorn horn
horn_base = Vector(horn_pts[horn_pts[:, 2] < horn_pts[:, 2].min() + 0.02].mean(0))
horn_tip = Vector(horn_pts[horn_pts[:, 2].argmax()])
horn_axis = (horn_tip - horn_base)
horn_base = horn_base - horn_axis.normalized() * 0.01
horn_tip = horn_base + horn_axis * 1.45  # drones have a longer and thicker horn than a unicorn
log(f"horn base {tuple(round(v, 3) for v in horn_base)}, tip {tuple(round(v, 3) for v in horn_tip)}")

HEAD_C = Vector((0.0, float(skin_pts[:, 1].mean()) + 0.02, float(bones[HEAD_BONE].z) + 0.09))


def surface_point(direction, band=0.012):
    """The head skin point farthest from the head centre in the given direction (along the midline)."""
    d = Vector(direction).normalized()
    rel = skin_pts - np.array(HEAD_C)
    near = np.abs(rel[:, 0]) < band
    proj = rel[near] @ np.array(d)
    lateral = np.linalg.norm(rel[near] - np.outer(proj, np.array(d)), axis=1)
    score = proj - lateral * 3.0
    return Vector(skin_pts[near][score.argmax()])


def spike_uv(fs, a):
    return chitin_uv(0.35 + 0.6 * fs, 0.15 + 0.85 * abs(math.cos(a)) ** 3)


def add_horn(builder):
    """Horn: a serrated cone from the forehead."""
    steps = 9
    path = [horn_base.lerp(horn_tip, i / steps) for i in range(steps + 1)]
    r0 = 0.032
    radii = []
    for i in range(steps + 1):
        s = i / steps
        notch = 1.0 + 0.35 * (math.fmod(s * 3.0 + 0.8, 1.0) > 0.7)
        radii.append(0.0 if i == steps else r0 * (1 - s) ** 0.9 * notch)
    builder.loft(path, radii, radii, Vector((1, 0, 0)),
                 lambda fs, a: chitin_uv(0.5 + 0.5 * fs, 0.35 + 0.65 * abs(math.sin(a)) ** 2), HEAD_BONE, segs=10)


# Horn only - for those with a real hairstyle (heroes, lords): the crest spikes would stick through the hair.
horn_only = Builder()
add_horn(horn_only)
horn_ob = horn_only.to_object("eq_changeling_horn")

crest = Builder()
add_horn(crest)

# crest: a row of flat spikes along the midline from the horn to the back of the head and two smaller rows on the sides
SPIKES = 9
for i in range(SPIKES):
    t = i / (SPIKES - 1)
    ang = math.radians(65 + 135 * t)  # from "up-forward" (the muzzle faces -Y) to "back-down"
    direction = Vector((0.0, -math.cos(ang), math.sin(ang)))
    for side, scale in ((0.0, 1.0), (-1.0, 0.6), (1.0, 0.6)):
        if side and i in (0, SPIKES - 1):
            continue
        root = surface_point(direction) - direction * 0.012
        root.x = side * 0.032
        length = (0.10 - 0.05 * t) * scale * (0.85 + 0.3 * ((i * 7 + int(side + 1) * 3) % 5) / 4)
        tilt = Vector((side * 0.35, 0.9, 0.25 - 0.5 * t)).normalized()
        dirn = (direction * 0.55 + tilt * 0.45).normalized()
        tip = root + dirn * length
        pts = [root.lerp(tip, k / 3) for k in range(4)]
        width = [0.026 * scale, 0.020 * scale, 0.011 * scale, 0.0]
        thick = [0.009, 0.007, 0.004, 0.0]
        crest.loft(pts, thick, width, Vector((0, 0, 1)) if abs(dirn.z) < 0.9 else Vector((0, 1, 0)),
                   spike_uv, HEAD_BONE, segs=6)
crest_ob = crest.to_object("eq_changeling_crest")


# ---------------------------------------------------------------- Chrysalis's helmet: horn and crown
# One item in the helmet slot (eq_chrysalis_crown): a long curved serrated horn and a small
# black crown with turquoise orbs - as in the cartoon (references assets/reference/chrysalis).
# All on the same atlas: the horn and the band - chitin, the orbs - turquoise glow (the parts cell).
def skull_point(direction):
    """The head skin point farthest from its centre in the given direction (in any direction)."""
    d = Vector(direction).normalized()
    rel = skin_pts - np.array(HEAD_C)
    proj = rel @ np.array(d)
    lateral = np.linalg.norm(rel - np.outer(proj, np.array(d)), axis=1)
    return Vector(skin_pts[(proj - lateral * 3.0).argmax()])


def bezier(p0, p1, p2, t):
    return p0 * (1 - t) ** 2 + p1 * (2 * (1 - t) * t) + p2 * (t ** 2)


QUEEN_HORN_LEN = 1.75     # fraction of the unicorn horn length: the queen's is noticeably longer
QUEEN_HORN_BEND = 0.95    # how far the tip goes back
QUEEN_HORN_R = 0.040      # radius at the base
CROWN_PRONGS = 5
CROWN_Z = 0.115           # height of the band above the head centre (the forehead above the eyes, in front of the ears)
CROWN_LIFT = 0.014        # the band slightly above the skin
CROWN_BAND = 0.010        # band thickness


def add_queen_horn(builder):
    steps = 14
    up = horn_axis.normalized()
    back = Vector((0.0, 1.0, 0.0))   # the muzzle faces -Y, so back is +Y
    length = horn_axis.length
    ctrl = horn_base + up * (length * 1.15)
    tip = horn_base + up * (length * QUEEN_HORN_LEN) + back * (length * QUEEN_HORN_BEND)
    path = [bezier(horn_base, ctrl, tip, i / steps) for i in range(steps + 1)]
    radii = []
    for i in range(steps + 1):
        s = i / steps
        notch = 1.0 + 0.32 * (math.fmod(s * 4.0 + 0.6, 1.0) > 0.62)  # serrations along the whole length
        radii.append(0.0 if i == steps else QUEEN_HORN_R * (1 - s) ** 0.85 * notch)
    builder.loft(path, radii, radii, Vector((1, 0, 0)),
                 lambda fs, a: chitin_uv(0.45 + 0.55 * fs, 0.3 + 0.7 * abs(math.sin(a)) ** 2),
                 HEAD_BONE, segs=10)


head_bvh = BVHTree.FromObject(head_src, bpy.context.evaluated_depsgraph_get())


def skull_ring_point(angle_deg, z):
    """A point on the skull at height z in the direction angle_deg (0 - forward, then clockwise).

    We cast the ray from outside inward: that way the crown lies on the surface, not on a random vertex
    of the UV map (with nearest vertices the band came out ragged).
    """
    a = math.radians(angle_deg)
    d = Vector((math.sin(a), -math.cos(a), 0.0)).normalized()
    centre = Vector((HEAD_C.x, HEAD_C.y, z))
    hit, normal, _, _ = head_bvh.ray_cast(head_src.matrix_world.inverted() @ (centre + d * 0.30),
                                          head_src.matrix_world.inverted().to_3x3() @ (-d))
    if hit is None:
        return centre + d * 0.08
    return (head_src.matrix_world @ hit) + d * CROWN_LIFT


def add_crown(builder):
    """A band around the skull and prongs with turquoise orbs (like Chrysalis's crown in the cartoon)."""
    z = HEAD_C.z + CROWN_Z
    angles = list(range(0, 360, 20))
    ring = [skull_ring_point(a, z) for a in angles]
    ring.append(ring[0])  # close the band
    band = [CROWN_BAND] * len(ring)
    builder.loft(ring, band, band, Vector((0, 0, 1)),
                 lambda fs, a: chitin_uv(0.95, 0.35 + 0.5 * abs(math.cos(a))), HEAD_BONE, segs=6, cap=False)

    for i in range(CROWN_PRONGS):
        deg = -60 + 30 * i
        root = skull_ring_point(deg, z)
        outward = (root - Vector((HEAD_C.x, HEAD_C.y, z))).normalized()
        dirn = (outward * 0.30 + Vector((0, 0, 1)) * 0.95).normalized()
        stem_top = root + dirn * (0.080 if i % 2 == 0 else 0.060)
        builder.loft([root, root.lerp(stem_top, 0.6), stem_top], [0.010, 0.007, 0.005], [0.010, 0.007, 0.005],
                     Vector((0, 0, 1)),
                     lambda fs, ang: chitin_uv(0.9, 0.3 + 0.6 * abs(math.cos(ang))), HEAD_BONE, segs=6)
        # an orb at the end: turquoise glow
        orb = [stem_top - dirn * 0.005, stem_top + dirn * 0.014, stem_top + dirn * 0.034]
        builder.loft(orb, [0.007, 0.021, 0.006], [0.007, 0.021, 0.006], Vector((0, 0, 1)),
                     lambda fs, ang: region_uv("glow", 0.5 + 0.45 * math.cos(ang), 0.25 + 0.7 * fs),
                     HEAD_BONE, segs=8)


crown = Builder()
add_queen_horn(crown)
add_crown(crown)
crown_ob = crown.to_object("eq_chrysalis_crown")

# wings + tail
back = Builder()
body_src = pony["eq_twilight_body"]
_, body_pts = world_verts(body_src)
sp2 = bones[SPINE_BONE]
band = body_pts[(np.abs(body_pts[:, 2] - sp2.z) < 0.03) & (np.abs(body_pts[:, 0]) < 0.05)]
back_y = float(band[:, 1].max())

ss = np.linspace(0.0, 1.0, 70)
up, low = wing_half(ss)
outline = [(s * WING_LEN, u) for s, u in zip(ss, up)] + [(s * WING_LEN, -w) for s, w in zip(ss[::-1], low[::-1])]
outline = [p for i, p in enumerate(outline) if i == 0 or (abs(p[0] - outline[i - 1][0]) + abs(p[1] - outline[i - 1][1])) > 1e-5]
holes = []
for hs, ht, hr, hw in WING_HOLES:
    holes.append([(hs * WING_LEN + hr * WING_LEN * 0.9 * math.cos(a), ht + hw * 0.9 * math.sin(a))
                  for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)])


def wing_uv(x, y):
    return region_uv("wing", x / WING_LEN, (y / WING_W + 1) / 2)


for side in (1, -1):
    root = Vector((side * 0.045, back_y - 0.015, sp2.z + 0.01))
    ax = Vector((side * 0.30, 0.80, 0.52)).normalized()
    upv = Vector((side * 0.25, -0.15, 1.0))
    ay = (upv - ax * upv.dot(ax)).normalized()
    back.plane(outline, holes, (root, ax, ay), wing_uv, SPINE_BONE)
    # the second, lower wing - shorter and lower
    root2 = root + Vector((0, 0.0, -0.05))
    ax2 = Vector((side * 0.38, 0.86, 0.22)).normalized()
    ay2 = (upv - ax2 * upv.dot(ax2)).normalized()
    small = [(x * 0.72, y * 0.8) for x, y in outline]
    back.plane(small, [], (root2, ax2, ay2), lambda x, y: wing_uv(x / 0.72, y / 0.8), SPINE_BONE)

pelvis = bones[PELVIS_BONE]
band = body_pts[(np.abs(body_pts[:, 2] - pelvis.z) < 0.03) & (np.abs(body_pts[:, 0]) < 0.05)]
tail_root = Vector((0.0, float(band[:, 1].max()) - 0.03, pelvis.z - 0.03))
for k, (dx, dz, ln) in enumerate([(0.0, -0.35, 0.26), (-0.25, -0.55, 0.2), (0.25, -0.55, 0.2),
                                  (-0.12, -0.9, 0.22), (0.12, -0.9, 0.22), (0.0, 0.0, 0.15)]):
    d = Vector((dx, 1.0, dz)).normalized()
    bend = Vector((0, 0.3, -0.6))
    pts = [tail_root + d * (ln * f) + bend * (ln * f * f * 0.5) for f in (0, 0.33, 0.66, 1.0)]
    r = [0.02, 0.016, 0.009, 0.0]
    back.loft(pts, [x * 0.6 for x in r], r, Vector((1, 0, 0)), spike_uv, PELVIS_BONE, segs=6)
wings_ob = back.to_object("eq_changeling_wings")


# ---------------------------------------------------------------- 4. skin copies
def attach(target, builder_ob, weights_from=None):
    """Add a part to a skin mesh: weights from the nearest vertex of weights_from (or its own), facial keys from the nearest."""
    me = builder_ob.data
    tag = me.attributes.get("eq_part")
    if weights_from is not None:
        src = weights_from.data
        kd = KDTree(len(src.vertices))
        for v in src.vertices:
            kd.insert(weights_from.matrix_world @ v.co, v.index)
        kd.balance()
        names = {g.index: g.name for g in weights_from.vertex_groups}
        for g in list(builder_ob.vertex_groups):
            builder_ob.vertex_groups.remove(g)
        for v in me.vertices:
            _, idx, _ = kd.find(v.co)
            for g in src.vertices[idx].groups:
                vg = builder_ob.vertex_groups.get(names[g.group]) or builder_ob.vertex_groups.new(name=names[g.group])
                vg.add([v.index], g.weight, "REPLACE")
    builder_ob.matrix_world = target.matrix_world.copy()
    inv = target.matrix_world.inverted()
    for v in me.vertices:
        v.co = inv @ v.co
    bpy.ops.object.select_all(action="DESELECT")
    builder_ob.select_set(True)
    target.select_set(True)
    vl.objects.active = target
    bpy.ops.object.join()
    return tag is not None


chitin_meshes = {}
for src_name, name in (("eq_twilight_body", "eq_changeling_body"), ("eq_twilight_legs", "eq_changeling_legs"),
                       ("eq_twilight_gloves", "eq_changeling_gloves"), ("eq_twilight_head", "eq_changeling_head")):
    chitin_meshes[name] = copy_object(pony[src_name], name)

head = chitin_meshes["eq_changeling_head"]


def rigid_eyes(ob):
    """The face sliders move the eyeball (eq_eye=1) only as a whole - the painted round eye does not drift;
    the underlay (eq_eye=2) follows the nearest front vertices of the eyeball. Blinking (86-88) is left alone."""
    me_ = ob.data
    kbs = me_.shape_keys.key_blocks
    n_ = len(me_.vertices)
    base = np.empty(n_ * 3)
    kbs[0].data.foreach_get("co", base)
    base = base.reshape(n_, 3)
    world_b = np.array([(ob.matrix_world @ Vector(p))[:] for p in base])
    tag = np.array([a.value for a in me_.attributes["eq_eye"].data])
    ball, back = np.flatnonzero(tag == 1), np.flatnonzero(tag == 2)
    sides = {sd: ball[world_b[ball, 0] * sd > 0] for sd in (1, -1)}
    front = [i for sd, idx in sides.items() for i in idx if world_b[i, 1] < world_b[idx, 1].mean()]
    kd_ = KDTree(len(front))
    for i in front:
        kd_.insert(Vector(base[i]), i)
    kd_.balance()
    near_ = {int(b_): [h[1] for h in kd_.find_n(Vector(base[b_]), 8)] for b_ in back}
    for kb in kbs[1:]:
        co = np.empty(n_ * 3)
        kb.data.foreach_get("co", co)
        co = co.reshape(n_, 3)
        blink = kb.name in ("key_086", "key_087", "key_088")
        if not blink:
            for idx in sides.values():
                src, dst = base[idx], co[idx]
                ms, md = src.mean(0), dst.mean(0)
                u, sig, vt = np.linalg.svd((dst - md).T @ (src - ms) / len(idx))
                sg = np.ones(3)
                if np.linalg.det(u) * np.linalg.det(vt) < 0:
                    sg[2] = -1
                rot = u @ np.diag(sg) @ vt
                sc = (sig * sg).sum() / max(((src - ms) ** 2).sum() / len(idx), 1e-12)
                co[idx] = (sc * (rot @ (src - ms).T)).T + md
        for b_, nb in near_.items():
            co[b_] = base[b_] if blink else base[b_] + (co[nb] - base[nb]).mean(0)
        kb.data.foreach_set("co", co.ravel())
    log(f"changeling eyes rigid: {len(ball)} eyeball verts, {len(back)} backing verts")


rigid_eyes(head)
log(f"lashes removed: {delete_polys(head, is_lash)} faces")
for ob in chitin_meshes.values():
    remap_skin(ob)


def ring_points(obj_pts, z, side_sign, direction):
    """A surface point at height z on the side side_sign (x), the farthest one along direction (x,y)."""
    sel = obj_pts[(np.abs(obj_pts[:, 2] - z) < 0.01) & (obj_pts[:, 0] * side_sign > 0.02)]
    c = sel[:, :2].mean(0)
    d = np.array(direction) / np.linalg.norm(direction)
    i = ((sel[:, :2] - c) @ d).argmax()
    return Vector(sel[i]), Vector((d[0], d[1], 0.0))


def hole_decal(builder, center, normal, radius, bone="bip01_pelvis_0", stretch=1.0):
    n = normal.normalized()
    ref = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    ax = ref.cross(n).normalized()
    ay = n.cross(ax)
    c = center + n * 0.002
    segs = 14
    ring = [c + ax * (math.cos(a) * radius) + ay * (math.sin(a) * radius * stretch)
            for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    uvr = [region_uv("hole", 0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))
           for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    for k in range(segs):
        k2 = (k + 1) % segs
        builder.face([c, ring[k], ring[k2]], [region_uv("hole", 0.5, 0.5), uvr[k], uvr[k2]], bone)


# holes on the shins: two on each leg, front-outer side
legs = chitin_meshes["eq_changeling_legs"]
_, legs_pts = world_verts(pony["eq_twilight_legs"])
holes_b = Builder()
for side in (1, -1):
    for z, r, dirn in ((0.21, 0.020, (side * 0.5, -0.85)), (0.32, 0.016, (side * 0.9, -0.3))):
        p, nrm = ring_points(legs_pts, z, side, dirn)
        hole_decal(holes_b, p, nrm, r, stretch=1.5)
attach(legs, holes_b.to_object("eq_tmp_holes_legs"), weights_from=pony["eq_twilight_legs"])

# holes on the forearms (arms in the T-pose, the top is the outer side)
body = chitin_meshes["eq_changeling_body"]
holes_a = Builder()
for side in (1, -1):
    x = side * 0.43
    sel = body_pts[np.abs(body_pts[:, 0] - x) < 0.008]
    p = Vector(sel[sel[:, 2].argmax()])
    hole_decal(holes_a, p, Vector((0, 0, 1)), 0.016, stretch=0.7)
attach(body, holes_a.to_object("eq_tmp_holes_arms"), weights_from=pony["eq_twilight_body"])

# fangs: white curved cones from under the upper lip
fangs = Builder()
upper = teeth_pts[teeth_pts[:, 2] > np.median(teeth_pts[:, 2])]
fang_roots = []
for side in (1, -1):
    sel = upper[(upper[:, 0] * side > 0.012) & (upper[:, 0] * side < 0.03)]
    front = sel[sel[:, 1].argmin()]
    lip = skin_pts[(np.abs(skin_pts[:, 0] - front[0]) < 0.006) & (np.abs(skin_pts[:, 2] - front[2]) < 0.02)]
    lip_y = float(lip[:, 1].min()) if len(lip) else float(front[1])
    root = Vector((side * 0.019, lip_y + 0.006, float(front[2]) + 0.004))
    tip = Vector((side * 0.016, lip_y - 0.002, root.z - 0.034))
    mid = root.lerp(tip, 0.5) + Vector((0, -0.004, 0))
    pts = [root, root.lerp(mid, 0.5), mid, mid.lerp(tip, 0.5), tip]
    r = [0.0065, 0.0058, 0.0048, 0.003, 0.0]
    fangs.loft(pts, r, [x * 0.8 for x in r], Vector((1, 0, 0)),
               lambda fs, a: region_uv("fang", 0.5 + 0.4 * math.cos(a), 1 - fs), HEAD_BONE, segs=7, tag=1)
    fang_roots.append(root)
log(f"fang roots {[tuple(round(c, 3) for c in r) for r in fang_roots]}")
fang_ob = fangs.to_object("eq_tmp_fangs")
fang_ob.data.attributes.new("eq_fang", "INT", "POINT")
for v in fang_ob.data.vertices:
    fang_ob.data.attributes["eq_fang"].data[v.index].value = 1
n_before = len(head.data.vertices)
attach(head, fang_ob)
# facial keys: a fang moves like the nearest upper tooth
me = head.data
keys = me.shape_keys.key_blocks
basis = keys[0]
fang_attr = me.attributes["eq_fang"]
teeth_idx = []
uvd = me.uv_layers.active.data
for poly in me.polygons:
    if cell_of(uvd[poly.loop_indices[0]].uv[0], uvd[poly.loop_indices[0]].uv[1]) == (0, 3):
        teeth_idx.extend(poly.vertices)
teeth_idx = sorted(set(teeth_idx))
kd = KDTree(len(teeth_idx))
for i in teeth_idx:
    kd.insert(basis.data[i].co, i)
kd.balance()


def world_z(i):
    return (head.matrix_world @ basis.data[i].co).z


upper_z = np.median([world_z(i) for i in teeth_idx])
fixed = 0
for v in me.vertices:
    if not fang_attr.data[v.index].value:
        continue
    # the nearest tooth of the upper row (in the mesh's local coordinates)
    best = min(kd.find_n(basis.data[v.index].co, 8), key=lambda h: (world_z(h[1]) < upper_z, h[2]))[1]
    for kb in keys[1:]:
        kb.data[v.index].co = basis.data[v.index].co + (kb.data[best].co - basis.data[best].co)
    fixed += 1
me.attributes.remove(fang_attr)
log(f"fangs: {fixed} verts follow the teeth in {len(keys) - 1} face keys")

items = [head, body, legs, chitin_meshes["eq_changeling_gloves"], crest_ob, horn_ob, crown_ob, wings_ob]
for ob in items:
    if "eq_part" in ob.data.attributes:
        ob.data.attributes.remove(ob.data.attributes["eq_part"])
    if ob.parent is None:
        ob.parent = skel
        ob.matrix_parent_inverse = skel.matrix_world.inverted()
    if not any(m.type == "ARMATURE" for m in ob.modifiers):
        ob.modifiers.new("Armature", "ARMATURE").object = skel
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    log(f"item {ob.name}: {len(ob.data.vertices)} verts, {tris} tris, groups {len(ob.vertex_groups)}, "
        f"keys {len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0}")

# ---------------------------------------------------------------- 5. export
# The material in the FBX is only a name (no image): the editor will bind the existing eq_twilight_body.
mat = bpy.data.materials[MAT]
tex_nodes = [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]
saved = [n.image for n in tex_nodes]
for n in tex_nodes:
    n.image = None
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *items]:
    ob.select_set(True)
vl.objects.active = skel
fbx = os.path.join(OUT, "eq_changeling.fbx")
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
log("exported", fbx)
for n in tex_nodes:
    n.image = atlas_img  # preview - with the new atlas
for ob in pony.values():
    ob.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "eq_changeling.blend"), copy=True)

# ---------------------------------------------------------------- 6. preview
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_backface_culling = True
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
cam = bpy.data.objects.new("preview_cam", bpy.data.cameras.new("preview_cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
world = bpy.data.worlds.new("preview")
world.color = (0.55, 0.52, 0.6)
scene.world = world
scene.display.shading.background_type = "WORLD"


def render_views(prefix):
    for name, direction, center, size in [
            ("front", (0, -1, 0), (0, 0.1, 0.95), 2.2), ("side", (1, 0, 0), (0, 0.1, 0.95), 2.2),
            ("back", (0.3, 1, 0.3), (0, 0.1, 0.95), 2.2), ("three", (1, -1, 0.4), (0, 0.1, 0.95), 2.2),
            ("head", (0.35, -1, 0.15), (0, -0.03, 1.66), 0.55), ("head_side", (1, -0.2, 0.2), (0, 0.0, 1.66), 0.6),
            ("legs", (0.5, -1, 0.1), (0, 0.0, 0.25), 0.7)]:
        d = Vector(direction).normalized()
        cam.data.ortho_scale = size
        cam.location = Vector(center) + d * 6
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(OUT, "preview", f"{prefix}{name}.png")
        bpy.ops.render.render(write_still=True)


render_views("")
POSE = {"bip01_r_upperarm_twist_22": (0, 0, -1.0), "bip01_l_thigh_1": (0, 0, 0.9), "bip01_l_calf_2": (0, 0, -1.2),
        "bip01_spine1_10": (0, 0.3, 0), "bip01_head_13": (0.4, 0, 0)}
for bname, rot in POSE.items():
    if bname in skel.pose.bones:
        pb = skel.pose.bones[bname]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = rot
vl.update()
render_views("pose_")
log("done")
