# Exact FBX structure: objects, transforms, bones (local coordinates), rest pose.
# blender --background --factory-startup --python dump_fbx.py -- <file.fbx>
import sys
import bpy

path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
for ob in bpy.context.scene.objects:
    print(f"OBJ {ob.name!r} type={ob.type} loc={tuple(round(v, 4) for v in ob.location)} "
          f"rot={tuple(round(v, 4) for v in ob.rotation_euler)} scale={tuple(round(v, 4) for v in ob.scale)} "
          f"parent={ob.parent.name if ob.parent else None}")
    if ob.type == "ARMATURE":
        print(f"  data name={ob.data.name!r}")
        for b in ob.data.bones:
            h, t = b.head_local, b.tail_local
            print(f"  BONE {b.name!r:34} parent={b.parent.name if b.parent else None!r:30} "
                  f"head=({h.x:.2f},{h.y:.2f},{h.z:.2f}) tail=({t.x:.2f},{t.y:.2f},{t.z:.2f}) deform={b.use_deform}")
    if ob.type == "MESH":
        print(f"  verts={len(ob.data.vertices)} groups={[g.name for g in ob.vertex_groups][:10]} mods={[m.type for m in ob.modifiers]}")
print("UNIT scale_length", bpy.context.scene.unit_settings.scale_length)
