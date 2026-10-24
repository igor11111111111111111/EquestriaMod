# -*- coding: utf-8 -*-
import sys
import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
collection_name = argv[0]
names = argv[1:]
col = bpy.data.collections[collection_name]
for name in names:
    ob = col.objects.get(name)
    if ob is None:
        print("[remove]", name, "— нет такого объекта")
        continue
    data = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if data and data.users == 0:
        bpy.data.meshes.remove(data)
    print("[remove]", name, "— удалён")
bpy.ops.wm.save_mainfile()
print("[remove] сохранено")
