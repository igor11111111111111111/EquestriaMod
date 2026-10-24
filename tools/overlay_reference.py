# Diagnostics: Twilight (from eq_twilight.blend) + the reference body next to/over it, renders from the front and side,
# and statistics: how far the pony's vertices stick out beyond the reference surface.
# blender --background eq_twilight.blend --python overlay_reference.py -- <Male_BodyBase.fbx> <out_dir>
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(__file__))
from reference_body import build_object, import_reference  # noqa: E402

ref_path, out_dir = sys.argv[sys.argv.index("--") + 1:]
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
skel = bpy.data.objects["bip01_notused"]

meshes, info = import_reference(ref_path, skel)
print("[ref] fit:", info, flush=True)
for name, m in meshes.items():
    lo, hi = m["verts"].min(0), m["verts"].max(0)
    print(f"[ref] {name}: lo={np.round(lo, 3)} hi={np.round(hi, 3)}", flush=True)
ref_objs = [build_object("REF_" + n, m["verts"], m["faces"], (0.2, 0.8, 0.3, 1.0)) for n, m in meshes.items()]

# pony vertices sticking out beyond the reference body surface (without the head)
body_ref = [m for n, m in meshes.items() if not n.startswith("head")]
verts = np.vstack([m["verts"] for m in body_ref])
faces, offset = [], 0
for m in body_ref:
    faces += [tuple(i + offset for i in f) for f in m["faces"]]
    offset += len(m["verts"])
tree = BVHTree.FromPolygons([Vector(v) for v in verts], faces)
dg = bpy.context.evaluated_depsgraph_get()
for name in ("eq_twilight_body", "eq_twilight_legs", "eq_twilight_gloves", "eq_twilight_head", "eq_twilight_mane"):
    ob = bpy.data.objects[name]
    outside = []
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        loc, normal, _, dist = tree.find_nearest(p)
        if loc is not None and (p - loc).dot(normal) > 0:
            outside.append(dist)
    outside = np.array(outside) if outside else np.zeros(1)
    print(f"[ref] {name}: {len(outside)}/{len(ob.data.vertices)} verts outside reference body, "
          f"max {outside.max():.3f} m, 95% {np.percentile(outside, 95):.3f} m", flush=True)

# render: the pony with texture, the reference in the object's green color
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
scene.display.shading.show_xray = True
scene.display.shading.xray_alpha = 0.6
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.name.startswith("eq_twilight"):
        ob.color = (0.8, 0.5, 0.9, 1.0)
scene.render.resolution_x, scene.render.resolution_y = 700, 1000
cam = bpy.data.objects.new("overlay_cam", bpy.data.cameras.new("overlay_cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam)
scene.camera = cam
if scene.world is None:
    scene.world = bpy.data.worlds.new("w")
center, size = Vector((0, 0, 0.95)), 2.0
cam.data.ortho_scale = size * 1.05
cam.data.clip_start, cam.data.clip_end = 0.01, 100
for label, direction in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0)))):
    cam.location = center + direction * 6
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(out_dir, f"overlay_{label}.png")
    bpy.ops.render.render(write_still=True)
print("[ref] done", flush=True)
