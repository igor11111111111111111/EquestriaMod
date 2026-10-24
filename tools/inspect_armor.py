# Comparing the vanilla armour sources with what the pony ended up with.
#
#   blender --background --factory-startup --python inspect_armor.py -- <assets\reference\vanilla_armor> <eq_pony_armor.fbx> mesh1 mesh2 ...
#
# Prints for each mesh: how many objects and vertices and which materials are in the source and in the result.
import os
import sys

import bpy

import io_scene_fbx.import_fbx as _fbx_import  # noqa: E402

_fbx_import.blen_read_shapes = lambda *args, **kwargs: {}

ARGS = sys.argv[sys.argv.index("--") + 1:]
SOURCE_DIR, RESULT_FBX, NAMES = ARGS[0], ARGS[1], ARGS[2:]


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    out = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        mats = sorted({s.material.name for s in obj.material_slots if s.material})
        polys = {}
        for p in obj.data.polygons:
            polys[p.material_index] = polys.get(p.material_index, 0) + 1
        out[obj.name] = (len(obj.data.vertices), mats, polys, len(obj.vertex_groups))
    return out


print("=" * 70)
for name in NAMES:
    src = load(os.path.join(SOURCE_DIR, name, name + ".fbx"))
    print("ИСХОДНИК %s:" % name)
    for obj, (verts, mats, polys, groups) in src.items():
        print("   %-40s вершин %-6d материалы %s по полигонам %s групп %d" % (obj, verts, mats, polys, groups))

result = load(RESULT_FBX)
print("РЕЗУЛЬТАТ:")
for name in NAMES:
    for obj, (verts, mats, polys, groups) in result.items():
        if name in obj:
            print("   %-40s вершин %-6d материалы %s по полигонам %s групп %d" % (obj, verts, mats, polys, groups))
