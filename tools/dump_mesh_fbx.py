# Обзор FBX с мешами: объекты, габариты в мире, скелет, группы вершин, материалы.
# blender --background --factory-startup --python dump_mesh_fbx.py -- <file.fbx> [png превью]
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
path = args[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, primary_bone_axis="X", secondary_bone_axis="-Y")
bpy.context.view_layer.update()
for ob in bpy.context.scene.objects:
    line = (f"[mesh] {ob.name!r} type={ob.type} parent={ob.parent.name if ob.parent else None} "
            f"rot={tuple(round(v, 3) for v in ob.rotation_euler)} scale={tuple(round(v, 4) for v in ob.scale)}")
    if ob.type == "MESH":
        ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
        lo = Vector((min(p.x for p in ws), min(p.y for p in ws), min(p.z for p in ws)))
        hi = Vector((max(p.x for p in ws), max(p.y for p in ws), max(p.z for p in ws)))
        line += (f" verts={len(ws)} world lo={tuple(round(v, 3) for v in lo)} hi={tuple(round(v, 3) for v in hi)}"
                 f" groups={len(ob.vertex_groups)} {[g.name for g in ob.vertex_groups][:6]} mats={[m.name for m in ob.data.materials]}"
                 f" mods={[m.type for m in ob.modifiers]}")
    if ob.type == "ARMATURE":
        pel = ob.data.bones.get("bip01_pelvis_0") or ob.data.bones[0]
        line += f" bones={len(ob.data.bones)} first={pel.name} world_head={tuple(round(v, 3) for v in ob.matrix_world @ pel.head_local)}"
    print(line, flush=True)
