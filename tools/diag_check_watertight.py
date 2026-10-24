# -*- coding: utf-8 -*-
import sys
import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
collection_name = argv[0]
names = argv[1:]
col = bpy.data.collections[collection_name]
for name in names:
    ob = col.objects.get(name)
    if ob is None:
        print("[diag]", name, "— нет такого объекта")
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    print("[diag]", name, "вершин:", len(bm.verts), "граничных рёбер:", len(boundary))
    bm.free()
