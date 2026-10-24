# Имена костей MMD (в виде escape-последовательностей, чтобы консоль не портила) и проверка
# совпадения костей с сеткой в мировых координатах.
import sys
import bpy
from mathutils import Vector

path = sys.argv[sys.argv.index("--") + 1]
out = sys.argv[sys.argv.index("--") + 2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=path)
dg = bpy.context.evaluated_depsgraph_get()
arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")

lines = []
lines.append(f"ARM {arm.name} mw=\n{arm.matrix_world}")
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        zs = [(ob.matrix_world @ v.co) for v in me.vertices]
        lo = Vector((min(p.x for p in zs), min(p.y for p in zs), min(p.z for p in zs)))
        hi = Vector((max(p.x for p in zs), max(p.y for p in zs), max(p.z for p in zs)))
        lines.append(f"MESH {ob.name} mat={[s.material.name for s in ob.material_slots]} "
                     f"parent_type={ob.parent_type} mods={[m.type for m in ob.modifiers]} "
                     f"evaluated lo={tuple(round(v, 4) for v in lo)} hi={tuple(round(v, 4) for v in hi)}")
        ev.to_mesh_clear()
for b in arm.data.bones:
    pb = arm.pose.bones[b.name]
    h = arm.matrix_world @ pb.head
    t = arm.matrix_world @ pb.tail
    lines.append(f"BONE {b.name} | parent={b.parent.name if b.parent else None} | "
                 f"head=({h.x:.4f},{h.y:.4f},{h.z:.4f}) tail=({t.x:.4f},{t.y:.4f},{t.z:.4f})")
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
