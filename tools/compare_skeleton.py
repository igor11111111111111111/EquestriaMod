# Comparing the pony model with the Bannerlord human skeleton + preview renders.
# blender --background --factory-startup --python compare_skeleton.py -- <model.gltf> <human_skeleton.fbx> <out_dir>
import os
import sys
import math
import bpy
from mathutils import Vector

model_path, skel_path, out_dir = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def print_bones(arm, limit=None):
    for i, b in enumerate(arm.data.bones):
        if limit and i >= limit:
            break
        head = arm.matrix_world @ b.head_local
        print(f"  {b.name:32} parent={b.parent.name if b.parent else '-':24} head=({head.x:.3f},{head.y:.3f},{head.z:.3f})")


# --- Pony
bpy.ops.import_scene.gltf(filepath=model_path)
pony_objs = list(bpy.context.scene.objects)
for ob in pony_objs:
    if ob.name.startswith("Icosphere"):
        ob.hide_render = True
bpy.context.view_layer.update()
pony_meshes = [o for o in pony_objs if o.type == "MESH" and not o.name.startswith("Icosphere")]
pony_arm = next(o for o in pony_objs if o.type == "ARMATURE")
lo, hi = world_bounds(pony_meshes)
print("\n=== PONY")
print(f"bounds min={tuple(round(v, 3) for v in lo)} max={tuple(round(v, 3) for v in hi)}")
print(f"size X={hi.x - lo.x:.3f} Y={hi.y - lo.y:.3f} Z={hi.z - lo.z:.3f}")
print(f"armature world scale={tuple(round(v, 4) for v in pony_arm.matrix_world.to_scale())}")
print("bones:")
print_bones(pony_arm)

# --- Bannerlord human skeleton (separately, so it does not get in the way of the pony render)
before = set(bpy.context.scene.objects)
bpy.ops.import_scene.fbx(filepath=skel_path)
bpy.context.view_layer.update()
human = [o for o in bpy.context.scene.objects if o not in before]
human_arm = next(o for o in human if o.type == "ARMATURE")
print("\n=== BANNERLORD HUMAN SKELETON")
print(f"armature world scale={tuple(round(v, 4) for v in human_arm.matrix_world.to_scale())}")
zs = [(human_arm.matrix_world @ b.head_local).z for b in human_arm.data.bones]
zt = [(human_arm.matrix_world @ b.tail_local).z for b in human_arm.data.bones]
print(f"bone height range z={min(zs + zt):.3f}..{max(zs + zt):.3f}")
print_bones(human_arm)
for o in human:
    o.hide_render = True

# --- Pony preview: front and side
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = 800
scene.render.resolution_y = 1000
scene.render.film_transparent = False
world = bpy.data.worlds.new("w")
scene.world = world

center = (lo + hi) / 2
height = max(hi.z - lo.z, hi.y - lo.y, hi.x - lo.x)
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = height * 1.15
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

for name, direction in (("front", Vector((0, -1, 0))), ("side", Vector((1, 0, 0))), ("back", Vector((0, 1, 0)))):
    cam.location = center + direction * height * 3
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(out_dir, f"pony_{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {scene.render.filepath}")
