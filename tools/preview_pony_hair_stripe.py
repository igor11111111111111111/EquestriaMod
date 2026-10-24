# -*- coding: utf-8 -*-
"""Рендер хвоста/гривы с живым процедурным узором полос (тем же узлом, что печёт
make_pony_hair_stripe_bake.py) прямо на поверхности — чтобы проверить направление и ширину полос
на самой 3D-модели, а не по плоскому атласу (тот выглядит рвано всегда, даже когда на модели всё
ровно — россыпь UV-островов, см. make_pony_hair_stripe_bake.py).

Запуск:
  "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe" --background ^
    assets\\pony\\eq_pony_edit.blend --python tools\\preview_pony_hair_stripe.py

Результат — tools/../_preview_stripe.png (рядом с .blend, там же куда смотрит камера).
"""
import math
import os

import bpy

ROOT = r"C:\Users\New\EquestriaMod"
OUT = os.path.join(ROOT, "_preview_stripe.png")
NAME = "eq_pony_tail"
BANDS = 3

col = bpy.data.collections.get("Пони - цельная")
ob = col.objects.get(NAME) if col else bpy.data.objects.get(NAME)
if ob is None:
    raise SystemExit(NAME + " не найден")

mat = bpy.data.materials.new(NAME + "_stripe_preview")
mat.use_nodes = True
nt = mat.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)

coord = nt.nodes.new("ShaderNodeTexCoord")
center = nt.nodes.new("ShaderNodeVectorMath")
center.operation = "SUBTRACT"
center.inputs[1].default_value = (0.5, 0.5, 0.5)
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
angle = nt.nodes.new("ShaderNodeMath")
angle.operation = "ARCTAN2"
norm = nt.nodes.new("ShaderNodeMath")
norm.operation = "DIVIDE"
norm.inputs[1].default_value = 6.283185307
shift = nt.nodes.new("ShaderNodeMath")
shift.operation = "ADD"
shift.inputs[1].default_value = 0.5
scale = nt.nodes.new("ShaderNodeMath")
scale.operation = "MULTIPLY"
scale.inputs[1].default_value = BANDS
frac = nt.nodes.new("ShaderNodeMath")
frac.operation = "MODULO"
frac.inputs[1].default_value = 1.0
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = "CONSTANT"
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.4, 1.0)   # тёмно-синяя полоса (для контраста на превью)
ramp.color_ramp.elements[1].position = 0.5
ramp.color_ramp.elements[1].color = (1.0, 0.3, 0.6, 1.0)     # розовая полоса

bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
out = nt.nodes.new("ShaderNodeOutputMaterial")

nt.links.new(coord.outputs["Generated"], center.inputs[0])
nt.links.new(center.outputs["Vector"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Y"], angle.inputs[0])
nt.links.new(sep.outputs["X"], angle.inputs[1])
nt.links.new(angle.outputs["Value"], norm.inputs[0])
nt.links.new(norm.outputs["Value"], shift.inputs[0])
nt.links.new(shift.outputs["Value"], scale.inputs[0])
nt.links.new(scale.outputs["Value"], frac.inputs[0])
nt.links.new(frac.outputs["Value"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bsdf.inputs["Color"])
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

ob.data.materials.clear()
ob.data.materials.append(mat)

# Камера + свет, направленные на bounding box объекта в мировых координатах.
bbox = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
cx = sum(v.x for v in bbox) / 8
cy = sum(v.y for v in bbox) / 8
cz = sum(v.z for v in bbox) / 8
size = max((max(v[i] for v in bbox) - min(v[i] for v in bbox)) for i in range(3))

cam_data = bpy.data.cameras.new("preview_cam")
cam = bpy.data.objects.new("preview_cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.location = (cx + size * 1.6, cy - size * 1.6, cz + size * 0.8)
direction = __import__("mathutils").Vector((cx, cy, cz)) - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam

light_data = bpy.data.lights.new("preview_light", type="SUN")
light_data.energy = 3.0
light = bpy.data.objects.new("preview_light", light_data)
bpy.context.scene.collection.objects.link(light)
light.location = (cx, cy, cz + size * 3)

bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.samples = 32
bpy.context.scene.render.resolution_x = 900
bpy.context.scene.render.resolution_y = 900
bpy.context.scene.render.filepath = OUT
bpy.context.scene.render.image_settings.file_format = "PNG"

for o in bpy.data.objects:
    o.hide_render = o not in (ob, cam, light)

bpy.ops.render.render(write_still=True)
print("[preview] записано:", OUT)
