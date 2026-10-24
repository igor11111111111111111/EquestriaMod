# Быстрый просмотр модели: три ортографических вида (спереди, сбоку, сверху) в один PNG.
#
#   blender --background --factory-startup --python preview_model.py -- <файл .glb/.gltf/.fbx> <out.png>
#
# Нужен, чтобы глазами оценить чужую модель до переделки: в какой она позе, куда смотрит,
# какого размера и не развалилась ли геометрия.
import os
import sys

import bpy
from mathutils import Vector

path, out = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
if path.lower().endswith((".gltf", ".glb")):
    bpy.ops.import_scene.gltf(filepath=path)
else:
    bpy.ops.import_scene.fbx(filepath=path)

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for ob in meshes:
    for corner in ob.bound_box:
        p = ob.matrix_world @ Vector(corner)
        lo = Vector((min(lo[i], p[i]) for i in range(3)))
        hi = Vector((max(hi[i], p[i]) for i in range(3)))
center = (lo + hi) / 2
size = max(hi - lo)

# свет и мир, иначе кадр чёрный
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.38, 0.42, 1)
bpy.context.scene.world = world
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 4.0
sun.rotation_euler = (0.8, 0.2, 0.6)
bpy.context.collection.objects.link(sun)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in \
    {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_WORKBENCH"
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.film_transparent = False

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 1.25
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam

VIEWS = {
    "спереди": ((0, -size * 2, 0), (1.5708, 0, 0)),
    "сбоку": ((size * 2, 0, 0), (1.5708, 0, 1.5708)),
    "сверху": ((0, 0, size * 2), (0, 0, 0)),
}
frames = []
for name, (offset, rot) in VIEWS.items():
    cam.location = center + Vector(offset)
    cam.rotation_euler = rot
    scene.render.filepath = out.replace(".png", "_%s.png" % name)
    bpy.ops.render.render(write_still=True)
    frames.append(scene.render.filepath)
# Координатная сетка поверх кадра: по ней снимаются координаты суставов для анатомической карты
# (tools/creature_data.py). Камера ортографическая, поэтому пересчёт точный.
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
AXES = {"спереди": (0, 2), "сбоку": (1, 2), "сверху": (1, 0)}   # какие мировые оси по горизонтали/вертикали
FLIP = {"спереди": (1, -1), "сбоку": (-1, -1), "сверху": (-1, 1)}
if Image is not None:
    for name, path_png in zip(VIEWS, frames):
        ah, av = AXES[name]
        fh, fv = FLIP[name]
        im = Image.open(path_png).convert("RGB")
        d = ImageDraw.Draw(im)
        w, h = im.size
        half = cam_data.ortho_scale / 2
        step = 0.1 if size < 2.5 else 0.25
        v = -half
        while v <= half + 1e-6:
            wx = center[ah] + v * fh
            px = int((v / half * 0.5 + 0.5) * w)
            d.line([px, 0, px, h], fill=(90, 110, 130))
            d.text((px + 2, 4), "%.2f" % wx, fill=(220, 220, 120))
            wy = center[av] + v * fv
            py = int((0.5 - v / half * 0.5) * h)
            d.line([0, py, w, py], fill=(90, 110, 130))
            d.text((4, py + 2), "%.2f" % wy, fill=(220, 220, 120))
            v += step
        d.text((6, h - 16), "%s: гор. %s, верт. %s" % (name, "XYZ"[ah], "XYZ"[av]), fill=(255, 255, 255))
        im.save(path_png)

print("[preview] размер модели %.3f x %.3f x %.3f, центр %s" % (*(hi - lo), tuple(round(v, 3) for v in center)))
for f in frames:
    print("[preview] кадр", f)
