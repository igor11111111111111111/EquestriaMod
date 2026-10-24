# Close-up of the head and mane from the exported FBX (as the editor will see it) with the atlas texture.
# blender --background --factory-startup --python render_head_fbx.py -- <eq_twilight.fbx> <atlas.png> <out_dir>
import os
import sys

import bpy
from mathutils import Vector

fbx, atlas_path, out_dir = sys.argv[sys.argv.index("--") + 1:]
os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx, automatic_bone_orientation=False, primary_bone_axis="X", secondary_bone_axis="-Y")
scene = bpy.context.scene

atlas = bpy.data.images.load(atlas_path)
mat = bpy.data.materials.new("preview_atlas")
mat.use_nodes = True
tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = atlas
mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])

show = {"eq_twilight_head", "eq_twilight_mane", "eq_twilight_body"}
pts = []
for ob in scene.objects:
    if ob.type == "MESH":
        ob.hide_render = ob.name not in show
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        if ob.name in ("eq_twilight_head", "eq_twilight_mane"):
            pts += [ob.matrix_world @ v.co for v in ob.data.vertices]
        print(f"[head] {ob.name}: verts={len(ob.data.vertices)} groups={[g.name for g in ob.vertex_groups]}", flush=True)
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center, size = (lo + hi) / 2, max(hi - lo)
print(f"[head] head+mane bounds lo={tuple(round(c, 3) for c in lo)} hi={tuple(round(c, 3) for c in hi)}", flush=True)

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.resolution_x = scene.render.resolution_y = 500
scene.world = bpy.data.worlds.new("w")
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 1.3
cam.data.clip_start, cam.data.clip_end = 0.001, 100
scene.collection.objects.link(cam)
scene.camera = cam
for label, d in (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0)), ("top", (0.3, -0.4, 1))):
    direction = Vector(d).normalized()
    cam.location = center + direction * 3
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(out_dir, f"head_{label}.png")
    bpy.ops.render.render(write_still=True)
print("[head] done", flush=True)
