# Close-up of the right hand: rest and finger0 bent around three axes (which axis bends the fingers).
# blender --background <eq_twilight.blend> --python render_hand_test.py -- <out_dir>
import os
import sys

import bpy
from mathutils import Vector

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
skel = bpy.data.objects["bip01_notused"]
gloves = bpy.data.objects["eq_twilight_gloves"]

groups = {g.index: g.name for g in gloves.vertex_groups}
counts = {}
for v in gloves.data.vertices:
    for g in v.groups:
        if g.weight > 0.01:
            counts[groups[g.group]] = counts.get(groups[g.group], 0) + 1
print("[hand] glove verts per bone:", counts, flush=True)

hand = skel.pose.bones["bip01_r_hand_26"]
center = skel.matrix_world @ hand.head
size = 0.0035

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = scene.render.resolution_y = 500
if scene.world is None:
    scene.world = bpy.data.worlds.new("w")
cam = bpy.data.objects.new("hand_cam", bpy.data.cameras.new("hand_cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = size
cam.data.clip_start = 0.0001
cam.data.clip_end = 1
scene.collection.objects.link(cam)
scene.camera = cam
direction = Vector((0.3, 1, 0.4)).normalized()
cam.location = center + Vector((0.0012, 0, -0.0008)) + direction * 0.05
cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()

finger = skel.pose.bones["bip01_r_finger0_27"]
finger.rotation_mode = "XYZ"
for name, rot in (("rest", (0, 0, 0)), ("x", (1.2, 0, 0)), ("y", (0, 1.2, 0)), ("z", (0, 0, 1.2))):
    finger.rotation_euler = rot
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(out_dir, f"hand_{name}.png")
    bpy.ops.render.render(write_still=True)
print("[hand] done", flush=True)
