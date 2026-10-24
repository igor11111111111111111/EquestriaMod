# UV ranges per material in the finished eq_twilight.blend (whether an atlas can be built without baking).
import bpy

stats = {}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    uv = me.uv_layers.active.data
    for poly in me.polygons:
        name = me.materials[poly.material_index].name
        s = stats.setdefault(name, [1e9, 1e9, -1e9, -1e9, 0])
        for li in poly.loop_indices:
            u, v = uv[li].uv
            s[0], s[1] = min(s[0], u), min(s[1], v)
            s[2], s[3] = max(s[2], u), max(s[3], v)
        s[4] += 1
for name, (u0, v0, u1, v1, n) in sorted(stats.items()):
    print(f"[uv] {name:26} u {u0:7.3f}..{u1:7.3f}  v {v0:7.3f}..{v1:7.3f}  polys {n}  layers", flush=True)
for ob in bpy.data.objects:
    if ob.type == "MESH":
        print(f"[uv] object {ob.name}: uv layers {[l.name for l in ob.data.uv_layers]}", flush=True)
