# -*- coding: utf-8 -*-
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
collection_name, obj_name = argv
col = bpy.data.collections[collection_name]
ob = col.objects.get(obj_name)
if ob is None:
    print("[diag] не нашёл объект", obj_name)
else:
    print("[diag]", obj_name, "вершин:", len(ob.data.vertices), "групп:", len(ob.vertex_groups))
    weight_by_group = {}
    for v in ob.data.vertices:
        for g in v.groups:
            name = ob.vertex_groups[g.group].name
            weight_by_group[name] = weight_by_group.get(name, 0) + g.weight
    for name, total in sorted(weight_by_group.items(), key=lambda kv: -kv[1]):
        print("  %-24s суммарный вес %.2f" % (name, total))
