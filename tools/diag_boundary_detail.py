# -*- coding: utf-8 -*-
import sys
import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
collection_name, name = argv
col = bpy.data.collections[collection_name]
ob = col.objects[name]
bm = bmesh.new()
bm.from_mesh(ob.data)
boundary = [e for e in bm.edges if len(e.link_faces) == 1]
print("[detail]", name, "граничных рёбер:", len(boundary))
for e in boundary:
    v1, v2 = e.verts
    print("  edge:", tuple(round(c, 5) for c in v1.co), "->", tuple(round(c, 5) for c in v2.co),
          "faces:", len(e.link_faces), "len:", round(e.calc_length(), 6))
bm.free()
