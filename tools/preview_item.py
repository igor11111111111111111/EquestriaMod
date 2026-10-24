"""Рендер одного предмета на модели — чтобы посмотреть вещь без соседних мешей.

  blender --background ../assets/changeling/eq_changeling.blend --python preview_item.py -- eq_chrysalis_crown

Скрывает все меши, кроме головы, тела и названного предмета, и кладёт снимки в
<папка blend>/preview/<предмет>_(front|side|three).png
"""
import os
import sys

import bpy
from mathutils import Vector

ITEM = sys.argv[sys.argv.index("--") + 1]
KEEP_SUFFIX = ("_head", "_body")
OUT = os.path.join(os.path.dirname(bpy.data.filepath), "preview")
os.makedirs(OUT, exist_ok=True)

for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    ob.hide_render = not (ob.name == ITEM or ob.name.endswith(KEEP_SUFFIX))

scene = bpy.context.scene
# свет и фон: в сохранённом .blend их может не быть — иначе кадр выходит чёрным
world = bpy.data.worlds.new("preview") if scene.world is None else scene.world
world.use_nodes = False
world.color = (0.55, 0.55, 0.60)
scene.world = world
scene.display.shading.background_type = "WORLD"
if not any(o.type == "LIGHT" for o in bpy.data.objects):
    light = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    light.data.energy = 4.0
    light.rotation_euler = (0.9, 0.2, 0.8)
    scene.collection.objects.link(light)

cam = next((o for o in bpy.data.objects if o.type == "CAMERA"), None)
if cam is None:
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"
scene.render.resolution_x = scene.render.resolution_y = 700

head_z = 1.66
for name, direction in (("front", (0.0, -1.0, 0.05)), ("side", (1.0, -0.15, 0.05)),
                        ("three", (0.8, -1.0, 0.25)), ("top", (0.2, -0.6, 1.0))):
    d = Vector(direction).normalized()
    cam.data.ortho_scale = 0.75
    cam.location = Vector((0.0, 0.0, head_z)) + d * 6
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, f"{ITEM}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("[preview]", scene.render.filepath, flush=True)
