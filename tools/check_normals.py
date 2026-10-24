# Доля граней, у которых нормаль по порядку обхода и сохранённая нормаль смотрят наружу (от центра меша).
# blender --background --factory-startup --python check_normals.py -- <file.fbx>
import sys

import bpy
from mathutils import Vector

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    center = sum((v.co for v in me.vertices), Vector()) / len(me.vertices)
    corner = me.corner_normals
    winding_out = stored_out = 0
    for p in me.polygons:
        offset = me.vertices[me.loops[p.loop_start].vertex_index].co - center
        winding_out += p.normal.dot(offset) > 0
        stored_out += corner[p.loop_start].vector.dot(offset) > 0
    n = len(me.polygons)
    print(f"[chk] {ob.name}: winding outward {100 * winding_out / n:.0f}%, stored normals outward {100 * stored_out / n:.0f}%", flush=True)
