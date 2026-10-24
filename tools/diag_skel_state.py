# -*- coding: utf-8 -*-
import bpy

ob = bpy.data.objects.get("bip01_notused")
print("[diag] exists:", ob is not None)
if ob:
    print("[diag] hide_viewport:", ob.hide_viewport, "hide_get:", ob.hide_get())
    print("[diag] collections:", [c.name for c in ob.users_collection])
    vl = bpy.context.view_layer
    print("[diag] in view layer objects:", ob.name in vl.objects)
    for col in bpy.data.collections:
        print("[diag] collection", col.name, "exclude in VL:",
              [l.exclude for l in vl.layer_collection.children if l.name == col.name])
