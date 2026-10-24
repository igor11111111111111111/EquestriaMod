import os
import bpy

PARTS = ("eq_hippogriff_body", "eq_hippogriff_legs", "eq_hippogriff_gloves", "eq_hippogriff_head",
         "eq_hippogriff_wings", "eq_hippogriff_tail")
OUT = r"C:\Users\New\EquestriaMod\assets\hippogriff\eq_hippogriff.fbx"

skel = bpy.data.objects["bip01_notused"]
parts = []
for name in PARTS:
    ob = bpy.data.objects.get(name)
    if ob is None:
        print("[export] ВНИМАНИЕ: нет объекта", name)
        continue
    parts.append(ob)
    verts = len(ob.data.vertices)
    groups = len(ob.vertex_groups)
    ungrouped = sum(1 for v in ob.data.vertices if len(v.groups) == 0)
    keys = len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0
    print("[export] %-18s вершин %-6d групп %-3d без веса %-4d шейпкизов %d" % (name, verts, groups, ungrouped, keys))

if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
for ob in [skel, *parts]:
    if ob.hide_get():
        print("[export] снимаю скрытие (глазик) с", ob.name)
        ob.hide_set(False)
    ob.select_set(True)
    if not ob.select_get():
        print("[export] ВНИМАНИЕ: %s не выделился после select_set!" % ob.name)
bpy.context.view_layer.objects.active = skel
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         primary_bone_axis="X", secondary_bone_axis="-Y", path_mode="STRIP")
print("[export] экспортировано:", OUT)
