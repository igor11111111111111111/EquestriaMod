# -*- coding: utf-8 -*-
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
collection_name, obj_name = argv
col = bpy.data.collections[collection_name]
ob = col.objects.get(obj_name)
if ob is None:
    print("[diag] не нашёл", obj_name)
else:
    coords = [v.co for v in ob.data.vertices]
    xs = [c.x for c in coords]; ys = [c.y for c in coords]; zs = [c.z for c in coords]
    print("[diag]", obj_name, "min:", (min(xs), min(ys), min(zs)))
    print("[diag]", obj_name, "max:", (max(xs), max(ys), max(zs)))
    print("[diag]", obj_name, "center:", ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    print("[diag]", obj_name, "object origin (world):", tuple(ob.location))
