# Отчёт о модели: объекты, размеры, полигоны, материалы, скелет.
# Запуск: blender --background --factory-startup --python inspect_model.py -- <файл .gltf/.glb/.fbx>
import sys
import bpy
from mathutils import Vector

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
if path.lower().endswith((".gltf", ".glb")):
    bpy.ops.import_scene.gltf(filepath=path)
else:
    bpy.ops.import_scene.fbx(filepath=path)

bpy.context.view_layer.update()
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
total_tris = 0

print("\n=== OBJECTS")
for ob in bpy.context.scene.objects:
    line = f"{ob.name:40} type={ob.type:9} parent={ob.parent.name if ob.parent else '-'}"
    if ob.type == "MESH":
        me = ob.data
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        total_tris += tris
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        mats = [s.material.name for s in ob.material_slots if s.material]
        line += f" verts={len(me.vertices)} tris={tris} groups={len(ob.vertex_groups)} shapekeys={len(me.shape_keys.key_blocks) if me.shape_keys else 0} mats={mats}"
    if ob.type == "ARMATURE":
        line += f" bones={len(ob.data.bones)}"
    print(line)

size = hi - lo
print("\n=== TOTAL")
print(f"triangles={total_tris}")
print(f"bounds min={tuple(round(v, 3) for v in lo)} max={tuple(round(v, 3) for v in hi)}")
print(f"size X={size.x:.3f} Y={size.y:.3f} Z(height)={size.z:.3f}")

print("\n=== MATERIALS")
for m in bpy.data.materials:
    imgs = []
    if m.use_nodes:
        imgs = [n.image.name for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
    print(f"{m.name:30} images={imgs}")

print("\n=== IMAGES")
for img in bpy.data.images:
    print(f"{img.name:40} {img.size[0]}x{img.size[1]}")
