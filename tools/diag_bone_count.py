# -*- coding: utf-8 -*-
import bpy

for ob in bpy.data.objects:
    if ob.type == 'ARMATURE':
        print("[diag] armature:", ob.name, "bones:", len(ob.data.bones))
